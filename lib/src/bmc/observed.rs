//! The static state of a class whose initializer was observed on a JVM ([`crate::observed`]), made the path's: the
//! objects the observation holds become objects of the path, and each static field it holds a value of gets it.
//! A field it holds none of has none: a read of it before the path writes it is refused, by name.

use super::*;
use crate::observed::{Object, Observed, Slot};

/// The classes of the `HashMap` model an observed map is made of, and the fields the model keeps it in.
const MAP: &str = "java/util/HashMap";
const NODE: &str = "java/util/HashMap$Node";
pub(super) const WEAK_NULLS: &str = "<observed.WeakHashMap.nullValues>";
pub(super) const LOOKUP_MAP: &str = "<observed/HashMap>";
pub(super) const ATOMIC_REF: &str = "<observed/AtomicReference>";

fn lookup_key(units: Option<&[u16]>) -> String {
    use std::fmt::Write;
    let Some(units) = units else { return "<key/null>".into() };
    let mut field = String::from("<key/string>");
    for u in units { write!(field, "{u:04x}").expect("writing to a String"); }
    field
}

impl Engine<'_> {
    /// Whether `class`'s initializer is one the check was given the observed state of.
    pub(super) fn is_observed(&self, class: &str) -> bool {
        self.observed.contains_key(class)
    }

    /// Gives the path the state `class`'s initializer left on the JVM, and states what that rests on.
    pub(super) fn take_observed(&mut self, path: &mut Path, class: &str) -> Result<(), Stop> {
        let all = self.observed.clone();
        let observed = &all[class];
        let members = std::iter::once((class, &observed.fields)).chain(observed.joint_fields.iter().flat_map(|m| m.iter().map(|(name, state)| (name.as_str(), state))));
        if let Some(joint) = &observed.joint_fields {
            for (owner, _) in members.clone() {
                if self.cp.checker_class(owner).is_none() { return unsupported(format!("no class {owner} to install from the joint initializer snapshot")); }
                if path.classes.contains_key(owner) {
                    return unsupported(format!("the joint initialization snapshots overlap at {owner}; the JVM object identity across separate snapshots is unknown"));
                }
                for parent in gaps::initialization_supers(self.cp, owner) {
                    if self.cp.checker_statics(&parent) && parent != class && !joint.contains_key(&parent) {
                        return unsupported(format!("joint initialization of {class} does not cover the required supertype {parent} of {owner}"));
                    }
                }
            }
        }
        let mut made: BTreeMap<usize, usize> = BTreeMap::new();
        for (owner, fields) in members {
            let cf = self.cp.checker_class(owner).ok_or_else(|| Stop::Unsupported(format!("no class {owner} to give its observed state to")))?;
            for field in cf.fields.iter().filter(|f| f.is_static()) {
                let key = (owner.to_owned(), field.name.clone());
                let start = path.objects.len();
                let value = match fields.get(&field.name) {
                    None => Err("a field the observation does not name".to_string()),
                    Some(slot) => match observed.unheld(slot) {
                        Some(what) => Err(what),
                        None => self.observed_value(path, observed, slot, Some(&field.descriptor), &mut made),
                    },
                };
                match value {
                    Ok(v) => { path.statics.insert(key, v); }
                    Err(what) => {
                        // A partially filled map or array cannot become visible through a second alias.
                        made.retain(|_, object| *object < start);
                        if observed.joint_fields.is_some() && matches!(field.descriptor.as_bytes().first(), Some(b'L' | b'[')) {
                            let reason = format!("the observed static field {}.{} holds {what}. The snapshot supplies no referent to inspect", owner.replace('/', "."), field.name);
                            path.statics.insert(key, Val::Unobserved(reason.into()));
                        } else {
                            Rc::make_mut(&mut path.unheld_statics).insert(key, what);
                        }
                    }
                }
            }
            path.classes.insert(owner.to_owned(), ClassState::Done);
        }
        let text = crate::observed::assumption(class, observed);
        self.assumption_ids.insert(text.clone(), format!("observed-initializer:{}:{}:{}", class.replace('/', "."), observed.on.sha256, observed.state_sha256));
        self.assumed.insert(text);
        for (index, (name, digest)) in observed.additional_roots.iter().enumerate() {
            let binary = name.replace('/', ".");
            let text = format!("{binary} was startup root {} in the same JVM as {}, before the checked entry", index + 2, class.replace('/', "."));
            self.assumption_ids.insert(text.clone(), format!("observed-initializer:{binary}:{digest}:{}", observed.state_sha256));
            self.assumed.insert(text);
        }
        Ok(())
    }

    /// Java locals and application fields can carry an unavailable reference without examining it.
    /// All other uses stop before dispatch, even a null test or an identity comparison. In particular
    /// a constructor receiving the value runs its selected application bytecode, including exceptions.
    pub(super) fn transport_unobserved(&mut self, path: &mut Path, class: &ClassFile, insn: &Insn, reason: &str) -> Option<Step> {
        let stack = &path.frames.last()?.stack;
        match insn {
            Insn::Load(..) | Insn::Store(Kind::Ref, _) | Insn::Nop | Insn::Pop | Insn::Dup | Insn::Swap => return None,
            Insn::PutField(i) if matches!(stack.as_slice(), [.., Val::R(Some(_)), Val::Unobserved(_)]) => {
                if let Ok(m) = class.pool.member(*i) {
                    if self.cp.is_application(&m.owner) && Type::parse(&m.descriptor).is_ok_and(|t| t.is_reference()) { return None; }
                }
            }
            Insn::InvokeSpecial(i) => {
                if let Ok(m) = class.pool.member(*i) {
                    if let Some(step) = self.unobserved_constructor(path, &m) { return Some(step); }
                }
            }
            _ => {}
        }
        Some(unsupported(format!("{reason} ({insn:?} in {}.{})", class.name.replace('/', "."), path.frames.last()?.method)))
    }

    fn unobserved_constructor(&mut self, path: &mut Path, member: &crate::classfile::MemberRef) -> Option<Step> {
        if member.name != "<init>" { return None; }
        let cf = self.cp.application(&member.owner).ok()??;
        let body = cf.method("<init>", &member.descriptor).filter(|b| b.code.is_some() && !b.is_static())?.clone();
        let desc = MethodDescriptor::parse(&member.descriptor).ok()?;
        let stack = &mut path.frames.last_mut()?.stack;
        let start = stack.len().checked_sub(desc.params.len() + 1)?;
        let Val::R(Some(o)) = stack[start] else { return None };
        if !self.cp.is_subtype(&path.objects[o].class, &member.owner)
            || desc.params.iter().zip(&stack[start + 1..]).any(|(ty, v)| matches!(v, Val::Unobserved(_)) && !ty.is_reference()) {
            return None;
        }
        let args = stack.split_off(start);
        Some(self.enter_method(path, &member.owner, cf, body, args))
    }

    /// Why a read of the static field is refused, where the observation of its class's initializer holds no value
    /// of it and the path has written none.
    pub(super) fn unheld_static(&self, path: &Path, declaring: &str, name: &str) -> Option<String> {
        let key = (declaring.to_string(), name.to_string());
        if path.statics.contains_key(&key) {
            return None;
        }
        path.unheld_statics.get(&key).map(|what| {
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
                    Some("J" | "D") => Val::J(self.b.constant(*n, 64)),
                    Some("Z" | "B" | "C" | "S" | "I" | "F") => Val::I(self.b.constant(*n, 32)),
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
            Object::Value(chain) | Object::Instance(chain) => {
                let class = &chain.first().ok_or("an immutable value without a runtime class")?.name;
                let o = self.alloc(path, class);
                made.insert(i, o);
                for part in chain {
                    for ((name, ty), value) in &part.fields {
                        let key = self.cp.field_key(class, &part.name, name);
                        let v = if matches!(&observed.objects[i], Object::Instance(_)) && (ty.starts_with('L') || ty.starts_with('[')) {
                            self.captured_reference(path, observed, value, made)
                        } else {
                            self.observed_value(path, observed, value, Some(ty), made)?
                        };
                        path.objects[o].fields.insert(key, v);
                    }
                }
                o
            }
            Object::AtomicReference(value) => {
                if self.cp.atomic_reference_accessor("get", "()Ljava/lang/Object;").is_none() {
                    return Err("an AtomicReference whose JDK getter does not read the captured value field".into());
                }
                let o = self.alloc(path, "java/util/concurrent/atomic/AtomicReference");
                made.insert(i, o);
                let v = self.captured_reference(path, observed, value, made);
                path.objects[o].fields.insert("value".into(), v);
                path.objects[o].fields.insert(ATOMIC_REF.into(), Val::Unobserved("uncaptured atomic operations".into()));
                o
            }
            Object::LookupMap(entries) => {
                let o = self.alloc(path, MAP);
                made.insert(i, o);
                for (key, value) in entries {
                    let key = match key {
                        Slot::Null => lookup_key(None),
                        Slot::Object(k) => match &observed.objects[*k] {
                            Object::Str { units, .. } => lookup_key(Some(units)),
                            _ => return Err("an observed lookup table has a non-String key".into()),
                        },
                        _ => return Err("an observed lookup table has an unknown key".into()),
                    };
                    let v = self.captured_reference(path, observed, value, made);
                    if path.objects[o].fields.insert(key, v).is_some() { return Err("duplicate observed String key".into()); }
                }
                let count = self.b.constant(entries.len() as i64, 32);
                path.objects[o].fields.insert("<observed/size>".into(), Val::I(count));
                path.objects[o].fields.insert(LOOKUP_MAP.into(), Val::Unobserved("unobserved HashMap bucket order".into()));
                o
            }
            Object::NullValuedWeakMap => {
                if !self.cp.weak_map_null_operations() {
                    return Err("an observed WeakHashMap on a JDK whose key callbacks have not been qualified".into());
                }
                let map = self.alloc(path, "java/util/WeakHashMap");
                // A pair's cached-call key cannot identify the unobserved entries of two maps.
                path.objects[map].fields.insert(WEAK_NULLS.into(), Val::Unobserved("the GC-sensitive keys of the observed WeakHashMap".into()));
                map
            }
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

    /// A missing child must not erase the class, aliases, or other fields of its captured parent.
    fn captured_reference(&mut self, path: &mut Path, observed: &Observed, slot: &Slot, made: &mut BTreeMap<usize, usize>) -> Val {
        let start = path.objects.len();
        let value = match observed.unheld(slot) {
            Some(why) => Err(why),
            None => self.observed_value(path, observed, slot, None, made),
        };
        value.unwrap_or_else(|why| {
            made.retain(|_, object| *object < start);
            Val::Unobserved(format!("uncaptured reference in the observed heap: {why}").into())
        })
    }

    pub(super) fn captured_lookup(&mut self, path: &mut Path, o: usize, special: bool, member: &crate::classfile::MemberRef, args: &[Val]) -> Step {
        if special || !self.cp.is_subtype(MAP, &member.owner) { return unsupported("incompatible dispatch on an observed lookup table"); }
        let fields = &path.objects[o].fields;
        let result = match (member.name.as_str(), member.descriptor.as_str(), args) {
            ("size", "()I", []) => fields["<observed/size>"].clone(),
            ("isEmpty", "()Z", []) => {
                let Val::I(count) = &fields["<observed/size>"] else { return unsupported("an invalid observed map size"); };
                Val::I(self.b.constant(i64::from(self.b.constant_value(count) == Some(0)), 32))
            }
            (name @ ("get" | "containsKey"), desc, [key]) if (name == "get" && desc == "(Ljava/lang/Object;)Ljava/lang/Object;")
                || (name == "containsKey" && desc == "(Ljava/lang/Object;)Z") => {
                let key = match key {
                    Val::R(None) => lookup_key(None),
                    Val::R(Some(k)) if path.objects[*k].class == STRING => {
                        let Some(units) = self.constant_units(path, *k) else { return unsupported("a symbolic String key on the observed lookup table"); };
                        lookup_key(Some(&units))
                    }
                    _ => return unsupported("an observed lookup table needs a concrete String or null key"),
                };
                let entry = fields.get(&key);
                if name == "get" { entry.cloned().unwrap_or(Val::R(None)) } else { Val::I(self.b.constant(i64::from(entry.is_some()), 32)) }
            }
            _ => return unsupported(format!("HashMap.{}{} is outside the captured read-only lookup table", member.name, member.descriptor)),
        };
        if self.there_before(path, o) { self.reads(path, || "reads entries from a previously allocated HashMap".into())?; }
        self.push(path, result);
        self.advance(path);
        Ok(None)
    }
}

impl Engine<'_> {
    /// The exact JDK map has only null values. Both absent and present keys therefore return
    /// null, and writing null preserves the invariant through every alias. The collector may
    /// remove any dead key. No size, membership, traversal or weak-key liveness is inferred.
    pub(super) fn null_valued_weak_map_call(&mut self, path: &mut Path, map: usize, special: bool, member: &crate::classfile::MemberRef, args: &[Val]) -> Step {
        match (special, member.name.as_str(), member.descriptor.as_str(), args) {
            (false, "get", "(Ljava/lang/Object;)Ljava/lang/Object;", [key])
            | (false, "put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;", [key, Val::R(None)]) => {
                if !self.cp.is_subtype("java/util/WeakHashMap", &member.owner) {
                    return unsupported("an incompatible owner for an observed WeakHashMap operation");
                }
                match key {
                    Val::R(None) => {}
                    Val::R(Some(k)) if !path.objects[*k].unknown && !path.objects[*k].assumed && !path.objects[*k].given
                        && [("hashCode", "()I"), ("equals", "(Ljava/lang/Object;)Z")].into_iter().all(|(n, d)|
                            self.cp.find_method(&path.objects[*k].class, n, d).is_some_and(|(cf, _)| cf.name == "java/lang/Object")) => {}
                    _ => return unsupported("an observed WeakHashMap key whose hashCode or equals may run application code"),
                }
                // Even get may expunge stale mappings from the queue.
                self.keeps(path, Some(map), "updates a WeakHashMap that existed before the call")?;
                self.push(path, Val::R(None));
                self.advance(path);
                Ok(None)
            }
            _ => unsupported(format!("WeakHashMap.{}{} is outside the observed null-value invariant", member.name, member.descriptor)),
        }
    }
}
