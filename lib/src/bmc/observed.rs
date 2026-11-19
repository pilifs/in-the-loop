//! The static state of a class whose initializer was observed on a JVM ([`crate::observed`]), made the path's: the
//! objects the observation holds become objects of the path, and each static field it holds a value of gets it.
//! A field it holds none of has none: a read of it before the path writes it is refused, by name.

use super::*;
use crate::observed::{Object, Observed, Slot};

/// The classes of the `HashMap` model an observed map is made of, and the fields the model keeps it in.
const MAP: &str = "java/util/HashMap";
const NODE: &str = "java/util/HashMap$Node";

impl Engine<'_> {
    /// Whether `class`'s initializer is one the check was given the observed state of.
    pub(super) fn is_observed(&self, class: &str) -> bool {
        self.observed.contains_key(class)
    }

    /// Gives the path the state `class`'s initializer left on the JVM, and states what that rests on.
    pub(super) fn take_observed(&mut self, path: &mut Path, class: &str) -> Result<(), Stop> {
        let all = self.observed.clone();
        let observed = &all[class];
        let cf = self.cp.checker_class(class).ok_or_else(|| Stop::Unsupported(format!("no class {} to give its observed state to", class.replace('/', "."))))?;
        let mut made: BTreeMap<usize, usize> = BTreeMap::new();
        for field in cf.fields.iter().filter(|f| f.is_static()) {
            let key = (class.to_string(), field.name.clone());
            let value = match observed.fields.get(&field.name) {
                None => Err("a field the observation does not name".to_string()),
                Some(slot) => match observed.unheld(slot) {
                    Some(what) => Err(what),
                    None => self.observed_value(path, observed, slot, Some(&field.descriptor), &mut made),
                },
            };
            match value {
                Ok(v) => {
                    path.statics.insert(key, v);
                }
                Err(what) => {
                    self.unheld.insert(key, what);
                }
            }
        }
        let text = crate::observed::assumption(class, observed);
        self.assumption_ids.insert(text.clone(), format!("observed-initializer:{}:{}:{}", class.replace('/', "."), observed.on.sha256, observed.state_sha256));
        self.assumed.insert(text);
        Ok(())
    }

    /// Why a read of the static field is refused, where the observation of its class's initializer holds no value
    /// of it and the path has written none.
    pub(super) fn unheld_static(&self, path: &Path, declaring: &str, name: &str) -> Option<String> {
        let key = (declaring.to_string(), name.to_string());
        if path.statics.contains_key(&key) {
            return None;
        }
        self.unheld.get(&key).map(|what| {
            format!(
                "reads the static field {}.{name}, which the class's observed initializer left as {what}: the observation holds no value of it (--observed-initializer, lib/src/observed.rs)",
                declaring.replace('/', ".")
            )
        })
    }

    /// The value on the path of a value the observation holds; `descriptor` is the field's or the array's element's,
    /// which says how wide a number is. `Err` with what is in the way where the path cannot hold it after all.
    fn observed_value(&mut self, path: &mut Path, observed: &Observed, slot: &Slot, descriptor: Option<&str>, made: &mut BTreeMap<usize, usize>) -> Result<Val, String> {
        let i = match slot {
            Slot::Null => return Ok(Val::R(None)),
            Slot::Number(n) => {
                return Ok(match descriptor {
                    Some("J") => Val::J(self.b.constant(*n, 64)),
                    Some("Z" | "B" | "C" | "S" | "I") => Val::I(self.b.constant(*n, 32)),
                    _ => return Err("a number where the field is none".to_string()),
                })
            }
            Slot::Unheld(what) => return Err(what.clone()),
            Slot::Object(i) => *i,
        };
        if let Some(&o) = made.get(&i) {
            return Ok(Val::R(Some(o)));
        }
        let o = match &observed.objects[i] {
            Object::Str { units, interned: true } => self.literal(path, Literal::Str(units.clone()), STRING),
            Object::Str { units, interned: false } => self.string(path, units),
            Object::Class(name) => self.literal(path, Literal::Class(name.clone()), "java/lang/Class"),
            Object::EmptyConcurrentMap => {
                let class = crate::models::CONCURRENT_MAP;
                if !self.cp.checker_runs(class) || !self.cp.checker_runs(MAP) {
                    return Err("an empty java.util.concurrent.ConcurrentHashMap, which needs --model java.util.concurrent.ConcurrentHashMap".into());
                }
                self.assume_model(class);
                let entries = self.alloc(path, MAP);
                let map = self.alloc(path, class);
                path.objects[map].fields.insert("entries".into(), Val::R(Some(entries)));
                map
            }
            Object::Map(entries) => {
                if !self.cp.checker_runs(MAP) || !self.cp.checker_runs(NODE) {
                    return Err("a java.util.HashMap, which this check has no model of".to_string());
                }
                let map = self.alloc(path, MAP);
                made.insert(i, map);
                let mut last: Option<usize> = None;
                for (k, v) in entries {
                    let hash = match k {
                        Slot::Null => 0,
                        Slot::Object(s) => match &observed.objects[*s] {
                            Object::Str { units, .. } => crate::observed::string_hash(units),
                            _ => return Err("a java.util.HashMap with a key that is no String".to_string()),
                        },
                        _ => return Err("a java.util.HashMap with a key that is no String".to_string()),
                    };
                    let key = self.observed_value(path, observed, k, None, made)?;
                    let value = self.observed_value(path, observed, v, None, made)?;
                    let node = self.alloc(path, NODE);
                    let hash = self.b.constant(i64::from(hash), 32);
                    path.objects[node].fields.extend([("hash".to_string(), Val::I(hash)), ("key".to_string(), key), ("value".to_string(), value), ("next".to_string(), Val::R(None))]);
                    match last {
                        Some(before) => path.objects[before].fields.insert("next".to_string(), Val::R(Some(node))),
                        None => path.objects[map].fields.insert("first".to_string(), Val::R(Some(node))),
                    };
                    last = Some(node);
                }
                let size = self.b.constant(entries.len() as i64, 32);
                path.objects[map].fields.entry("first".to_string()).or_insert(Val::R(None));
                path.objects[map].fields.extend([("last".to_string(), Val::R(last)), ("size".to_string(), Val::I(size))]);
                return Ok(Val::R(Some(map)));
            }
            Object::Array { element, cells } => {
                let parsed = Type::parse(element).map_err(|e| e.to_string())?;
                let class = Type::Array(Box::new(parsed.clone())).descriptor();
                let length = self.b.constant(cells.len() as i64, 32);
                if holds_references(&parsed) {
                    path.objects.push(Obj { array: Some(Array { element: parsed, length, cells: Vec::new(), refs: vec![Val::R(None); cells.len()] }), ..Obj::new(&class) });
                    let array = path.objects.len() - 1;
                    made.insert(i, array);
                    for (at, cell) in cells.iter().enumerate() {
                        let v = self.observed_value(path, observed, cell, None, made)?;
                        path.objects[array].array.as_mut().expect("an array").refs[at] = v;
                    }
                    return Ok(Val::R(Some(array)));
                }
                let width = cell_width(&parsed);
                let mut bits = Vec::with_capacity(cells.len());
                for cell in cells {
                    let Slot::Number(n) = cell else { return Err("an array of numbers with a cell that is none".to_string()) };
                    bits.push(self.b.constant(*n, width));
                }
                path.objects.push(Obj { array: Some(Array { element: parsed, length, cells: bits, refs: Vec::new() }), ..Obj::new(&class) });
                path.objects.len() - 1
            }
        };
        made.insert(i, o);
        Ok(Val::R(Some(o)))
    }
}
