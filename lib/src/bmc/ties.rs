//! Values a pair of versions' two runs share where they run the same code from the same state.
//!
//! A regression check of a pair of versions ([`crate::pairing`]) runs the previous version and then the new one on
//! one path. Where both run a loop past the bound, each is covered by an invariant ([`loops`]), and the state past
//! it is new free bits on each side: what the loop wrote is any value the invariant allows, on each side
//! independently. Two runs that are equal in fact are then not equal in the formula. A hash's key schedule (bcrypt's
//! `ekskey` in example 287) ends there in a counterexample no run has, and no bound brings it back, since the
//! schedule runs `2^cost` times. What is lost is the relation between the sides, not precision on either.
//!
//! The relation is kept by making each free value the checker introduces past a bound a function of what decides
//! it, as relational verification takes an unchanged callee as one function and as the checker ties equal
//! products ([`bits`]): a function gives equal results on equal arguments.
//!
//! - **A loop's state past the bound** is what its iterations leave at its head the last time they come back to
//!   it, before the loop is left by its condition, a return or an exception. That is a function of the state
//!   at the head the loop is summarized from, given the code it runs. So the bits a place the loop writes is given
//!   are named by that state's key ([`Engine::state_key`]) and the place. A second summary from a state of the
//!   same key, on the other side or on the same, takes the same bits. The bits an iteration is tried from while
//!   the invariant is looked for are not named: they stand for every state the invariant allows, and are fresh.
//! - **A cell read past a summarized loop** at an index the path does not follow into a large array is a function
//!   of the array's content and the index. The content is named: the cells' bits of an array whose cells are
//!   known; of one whose cells hold any values ([`Obj::unknown`]), the summary that made them so, then each write
//!   since, by its index and value. A read of a content and an index already read takes the bits read then.
//! - **The summary itself** is a function of the state and the code: what an iteration from that state writes,
//!   and whether a candidate is kept, depend on nothing else. A second summary from a state of the same key takes
//!   over the first's written places and invariant ([`loops::Summary`]), each object by its number in the key,
//!   where its path's condition has every literal the first was proved under (an input of the second is one of
//!   the first). The new version then searches for no invariant the previous one found from the same state.
//!   Both versions summarize a loop at its entry, rather than past the bound, by their own run's history alone
//!   (`Path::summarized`): the check's history would have one side's run start at the entry where the other's
//!   started past the bound, and no state of one would be the other's.
//!
//! **The key** is everything an iteration can read: the code (the method's text with everything it reaches,
//! [`crate::shared::fingerprint`]) and the pc of the head, the frame's live locals, every object reachable from
//! them or from a static field, numbered as they are reached so that which references are one object (an alias)
//! is part of it, each object's class, fields, length and cells, which object is an interned literal, every static
//! field written, and each class's state of initialization. The previous version's copies are named by their own
//! names (`before/x/Y` is `x/Y`) where the code is compared as text: a method's fingerprint, the static fields,
//! and an object's class where the two versions' classes agree on everything a call from outside the fingerprint
//! can reach (the superclasses and interfaces, the fields, the methods that are neither static nor private). An
//! object whose class differs keeps its own name, and its states are tied on its own side only. An object that is
//! a lambda, or an array whose cells hold any values not named, makes the state one with no key: nothing is tied.
//!
//! **Why this is sound.** Every free bit is what some run gives it: a tied place's bits, in a run, are the place's
//! value when the loop is last at its head, a function of the state at the summary. Two summaries of one key are
//! from states that are the same in every run (the same bits, the same structure), of the same code, so the
//! function gives the same value, and the one set of bits stands for both. The invariant each side finds holds of
//! that value on each side. What each side does past the loop (its exits, its exceptions, what it returns) is its
//! own code from its own state: only the values are shared, never a path. The countermodels are in
//! `lib/tests/pairing.rs`: a changed callee inside the loop, unequal arrays, an alias on one side only, a mutable
//! static, an exceptional exit on one side, and a write after the loop on one side, each a violation. The same
//! file holds a fork of the previous version past its loops, on whose second branch the new version's loops tie
//! only because whether a loop is summarized at its entry is each run's own history.
//!
//! The ties are made only in a check of a pair of versions, which is where two runs of one code meet.

use super::*;
use std::collections::{BTreeSet, HashMap};

/// The first number of a key, by what it names.
const STATE: i64 = 1;
const CELLS: i64 = 2;
const SUMMARIZED: i64 = 3;
const WRITTEN: i64 = 4;
const READ: i64 = 5;

/// The keys met so far and the bits each tied place was given.
#[derive(Default)]
pub(super) struct Ties {
    keys: HashMap<Vec<i64>, u64>,
    names: HashMap<String, i64>,
    bits: HashMap<(u64, Vec<i64>), Bits>,
    /// Each method's fingerprint's key, with the application classes its code uses, by class, name and
    /// descriptor; `None` where it has none.
    code: HashMap<(String, String, String), Option<(i64, Rc<BTreeSet<String>>)>>,
    /// Each class's name in a key, by its name in the program.
    classes: HashMap<String, String>,
    /// How many times a place or a read took bits made before.
    pub(super) shared: u64,
    /// Each loop's summary from a state with a key, by the key ([`loops::Summary`]).
    pub(super) summaries: HashMap<u64, loops::Summary>,
    /// How many summaries were a summary made before from a state of the same key.
    pub(super) reused: u64,
}

impl Ties {
    fn key(&mut self, key: Vec<i64>) -> u64 {
        let next = self.keys.len() as u64;
        *self.keys.entry(key).or_insert(next)
    }

    fn name(&mut self, name: &str) -> i64 {
        let next = self.names.len() as i64;
        *self.names.entry(name.to_string()).or_insert(next)
    }

    /// The bits of `place` under `key`, made the first time.
    pub(super) fn bits(&mut self, b: &mut Blaster, key: u64, place: Vec<i64>, width: usize) -> (Bits, bool) {
        match self.bits.get(&(key, place.clone())) {
            Some(bits) if bits.len() == width => {
                self.shared += 1;
                (bits.clone(), false)
            }
            _ => {
                let bits = b.fresh(width);
                self.bits.insert((key, place), bits.clone());
                (bits, true)
            }
        }
    }
}

/// `text` with every class name the previous version's copy holds taken back to its own name: `before/x/Y` is
/// `x/Y` where `x/Y` is a class copied, as a name begins (after a character that is not one of a name, or a
/// descriptor's `L`).
pub(super) fn unprefixed(text: &str, previous: &crate::relocate::Previous) -> String {
    let marker = format!("{}/", previous.prefix);
    let part = |c: char| c.is_alphanumeric() || c == '_' || c == '$' || c == '/';
    let mut out = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(i) = rest.find(&marker) {
        out.push_str(&rest[..i]);
        let tail = &rest[i..];
        let end = tail.find(|c: char| !part(c)).unwrap_or(tail.len());
        let name = &tail[..end];
        let mut back = out.chars().rev();
        let begins = match back.next() {
            None => true,
            Some('L') => back.next().is_none_or(|c| !part(c)),
            Some(c) => !part(c),
        };
        match previous.original(name) {
            Some(own) if begins => out.push_str(own),
            _ => out.push_str(name),
        }
        rest = &tail[end..];
    }
    out.push_str(rest);
    out
}

impl Engine<'_> {
    /// The key of the state `path` is in at the head of the loop its top frame runs, with each reachable object's
    /// number in it by allocation; `None` outside a pair of versions, or where the state has no key (see the
    /// module's notes).
    pub(super) fn state_key(&mut self, path: &Path) -> Option<(u64, HashMap<u64, i64>)> {
        let previous = self.previous.clone()?;
        let frame = path.frames.last()?;
        let (code, uses) = self.code_key(&frame.class, &frame.method, &frame.code.descriptor, &previous)?;
        // The static state the code can read: the JDK's, and its own application classes'.
        let read = |class: &str| !self.cp.is_application(class) || uses.contains(class);
        let mut key = vec![STATE, code, frame.pc() as i64];
        let literals: HashMap<usize, String> = path.literals.iter().map(|(l, &o)| (o, unprefixed(&format!("{l:?}"), &previous))).collect();
        let mut numbers: HashMap<usize, i64> = HashMap::new();
        let mut queue: Vec<usize> = Vec::new();
        key.push(frame.locals.len() as i64);
        for local in &frame.locals {
            self.value(&mut key, local.as_ref(), &mut numbers, &mut queue);
        }
        key.push(frame.stack.len() as i64);
        for v in &frame.stack {
            self.value(&mut key, Some(v), &mut numbers, &mut queue);
        }
        let mut statics: Vec<(String, String, &Val)> = path.statics.iter().filter(|((c, _), _)| read(c)).map(|((c, n), v)| (unprefixed(c, &previous), n.clone(), v)).collect();
        statics.sort_by(|x, y| (&x.0, &x.1).cmp(&(&y.0, &y.1)));
        if statics.windows(2).any(|w| (&w[0].0, &w[0].1) == (&w[1].0, &w[1].1)) {
            return None;
        }
        key.push(statics.len() as i64);
        for (class, name, v) in statics {
            let (c, n) = (self.ties.name(&class), self.ties.name(&name));
            key.extend([c, n]);
            self.value(&mut key, Some(v), &mut numbers, &mut queue);
        }
        let mut classes: Vec<(String, ClassState)> = path.classes.iter().filter(|(c, _)| read(c)).map(|(c, s)| (unprefixed(c, &previous), *s)).collect();
        classes.sort_by(|x, y| x.0.cmp(&y.0));
        if classes.windows(2).any(|w| w[0].0 == w[1].0) {
            return None;
        }
        key.push(classes.len() as i64);
        for (class, state) in classes {
            let c = self.ties.name(&class);
            key.extend([c, state as i64]);
        }
        let mut next = 0;
        while next < queue.len() {
            let o = queue[next];
            next += 1;
            let obj = &path.objects[o];
            if obj.lambda.is_some() {
                return None;
            }
            let class = self.class_key(&obj.class, &previous);
            let literal = literals.get(&o).map_or(-1, |l| self.ties.name(l));
            let limit = obj.limit.as_ref().map_or(-1, |l| self.ties.name(l));
            let regex = obj.regex.as_ref().map_or(-1, |r| self.ties.name(&format!("{r:?}")));
            key.extend([class, obj.given as i64, literal, limit, regex, obj.fields.len() as i64]);
            for (name, v) in &obj.fields {
                let n = self.ties.name(&unprefixed(name, &previous));
                key.push(n);
                self.value(&mut key, Some(v), &mut numbers, &mut queue);
            }
            match &obj.array {
                None => key.push(-1),
                Some(array) => {
                    let element = self.ties.name(&unprefixed(&array.element.descriptor(), &previous));
                    key.push(element);
                    bits_into(&mut key, &array.length);
                    if obj.unknown {
                        key.push(obj.content? as i64);
                    } else {
                        key.push(array.cells.len() as i64);
                        for cell in &array.cells {
                            bits_into(&mut key, cell);
                        }
                    }
                    key.push(array.refs.len() as i64);
                    for r in &array.refs {
                        self.value(&mut key, Some(r), &mut numbers, &mut queue);
                    }
                }
            }
            key.push(obj.same.len() as i64);
            for (guard, target) in &obj.same {
                key.push(*guard as i64);
                key.push(number(*target, &mut numbers, &mut queue));
            }
        }
        let id = self.ties.key(key);
        let by_allocation = numbers.into_iter().map(|(o, n)| (path.objects[o].made, n)).collect();
        Some((id, by_allocation))
    }

    fn value(&mut self, key: &mut Vec<i64>, v: Option<&Val>, numbers: &mut HashMap<usize, i64>, queue: &mut Vec<usize>) {
        match v {
            None => key.push(0),
            Some(Val::I(bits)) => {
                key.push(1);
                bits_into(key, bits);
            }
            Some(Val::J(bits)) => {
                key.push(2);
                bits_into(key, bits);
            }
            Some(Val::R(None)) => key.push(3),
            Some(Val::R(Some(o))) => {
                key.push(4);
                key.push(number(*o, numbers, queue));
            }
            Some(Val::C(choice)) => {
                key.push(5);
                key.push(choice.0.len() as i64);
                for (guard, target) in &choice.0 {
                    key.push(*guard as i64);
                    key.push(target.map_or(-1, |o| number(o, numbers, queue)));
                }
            }
        }
    }

    /// The key of the code of `class`'s method `name``descriptor`: its fingerprint, with a previous version's copy
    /// named by its own names.
    fn code_key(&mut self, class: &ClassFile, name: &str, descriptor: &str, previous: &crate::relocate::Previous) -> Option<(i64, Rc<BTreeSet<String>>)> {
        let at = (class.name.clone(), name.to_string(), descriptor.to_string());
        if let Some(known) = self.ties.code.get(&at) {
            return known.clone();
        }
        let root = crate::classfile::MemberRef::new(&class.name, name, descriptor);
        let found = crate::shared::fingerprint(self.cp, &root, &|t| unprefixed(t, previous));
        let key = found.map(|(text, uses)| (self.ties.name(&format!("{}.{name}{descriptor}\n{text}", unprefixed(&class.name, previous))), Rc::new(uses)));
        self.ties.code.insert(at, key.clone());
        key
    }

    /// An object's class in a key: a previous version's copy by its own name where the two versions' classes agree
    /// on what a call from outside a fingerprint reaches, else by the name it has.
    fn class_key(&mut self, class: &str, previous: &crate::relocate::Previous) -> i64 {
        if let Some(known) = self.ties.classes.get(class) {
            let known = known.clone();
            return self.ties.name(&known);
        }
        let element = class.trim_start_matches('[');
        let inner = element.strip_prefix('L').and_then(|e| e.strip_suffix(';')).unwrap_or(element);
        let named = match previous.original(inner) {
            Some(own) if self.surface(inner, previous).is_some() && self.surface(inner, previous) == self.surface(own, previous) => class.replacen(inner, own, 1),
            _ => class.to_string(),
        };
        self.ties.classes.insert(class.to_string(), named.clone());
        self.ties.name(&named)
    }

    /// What a call from outside a fingerprint can reach of an application class, with a copy's names taken back:
    /// its superclasses and interfaces, its fields, and its methods that are neither static nor private, with their
    /// code; and the same of its superclass. `None` where it is not an application class or does not load.
    fn surface(&self, class: &str, previous: &crate::relocate::Previous) -> Option<String> {
        let mut out = String::new();
        let mut current = Some(class.to_string());
        while let Some(name) = current {
            if !self.cp.is_application(&name) {
                out.push_str(&name);
                break;
            }
            let cf = self.cp.application(&name).ok()??;
            out.push_str(&format!("{name} {:?} {:?}\n", cf.super_class, cf.interfaces));
            for f in &cf.fields {
                out.push_str(&format!("{} {} {}\n", f.access, f.name, f.descriptor));
            }
            for m in cf.methods.iter().filter(|m| !m.is_static() && !m.is_private() && m.name != "<init>") {
                out.push_str(&format!("{} {}{} {:?}\n", m.access, m.name, m.descriptor, crate::shared::shape(&cf, m)));
            }
            current = cf.super_class.clone();
        }
        Some(unprefixed(&out, previous))
    }

    /// The name of the content of the array `o`: its cells' bits where they are known, else what made them any
    /// values and each write since ([`Obj::content`]); `None` outside a pair of versions or where none is kept.
    pub(super) fn content(&mut self, path: &Path, o: usize) -> Option<u64> {
        self.previous.as_ref()?;
        let obj = &path.objects[o];
        if obj.unknown {
            return obj.content;
        }
        let array = obj.array.as_ref()?;
        let mut key = vec![CELLS, cell_width(&array.element) as i64];
        bits_into(&mut key, &array.length);
        for cell in &array.cells {
            bits_into(&mut key, cell);
        }
        Some(self.ties.key(key))
    }

    /// A name in a key, a previous version's copy taken back to its own.
    pub(super) fn ties_name(&mut self, text: &str) -> i64 {
        let text = match &self.previous {
            Some(previous) => unprefixed(text, previous),
            None => text.to_string(),
        };
        self.ties.name(&text)
    }

    /// The content of the array `o` once `value` is written at `index`, where its cells are or become any values.
    pub(super) fn written(&mut self, before: Option<u64>, index: &Bits, value: &Bits) -> Option<u64> {
        let before = before?;
        let mut key = vec![WRITTEN, before as i64];
        bits_into(&mut key, index);
        bits_into(&mut key, value);
        Some(self.ties.key(key))
    }

    /// The content a loop summarized from the state `state` leaves in the large array numbered `number` in it.
    pub(super) fn summarized(&mut self, state: u64, number: i64) -> u64 {
        self.ties.key(vec![SUMMARIZED, state as i64, number])
    }

    /// A cell of the array `o` read at `index`, which the path does not follow: any value, the same for one
    /// content and one index.
    pub(super) fn loose_read(&mut self, path: &Path, o: usize, index: &Bits, width: usize) -> Bits {
        match self.content(path, o) {
            Some(content) => {
                let mut place = vec![READ];
                bits_into(&mut place, index);
                self.ties.bits(&mut self.b, content, place, width).0
            }
            None => self.b.fresh(width),
        }
    }
}

fn bits_into(key: &mut Vec<i64>, bits: &Bits) {
    key.push(bits.len() as i64);
    key.extend(bits.iter().map(|&l| l as i64));
}

fn number(o: usize, numbers: &mut HashMap<usize, i64>, queue: &mut Vec<usize>) -> i64 {
    let next = numbers.len() as i64;
    *numbers.entry(o).or_insert_with(|| {
        queue.push(o);
        next
    })
}
