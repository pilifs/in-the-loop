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
//! **A call taken as one function of both versions.** Where a method the two versions share (the same code,
//! [`crate::shared::fingerprint`]) is called with arguments and static state the engine holds as values (numbers,
//! Strings, arrays of numbers), the call is not run: its outcome is a function of what it reads, as relational
//! verification takes an unchanged callee. What decides the outcome is its inputs: the arguments, the receiver's
//! fields for an instance method, and the static fields of the application classes its code uses, which must be
//! initialized. [`crate::shared::one_function`] says from the code that nothing else can: no static field written
//! outside an initializer, none of the JDK's read, no JDK call that reads state a run can change (the default locale,
//! a property, the clock, an identity), no lambda, no exception of the application's own. The outcome is new bits:
//! whether the call throws, and which class of the ones it may throw ([`crate::shared::OneFunction::throws`]); the
//! result, a number, an opaque String, or an array the call made; and, where its code stores into arrays, the cells
//! of every array it may reach: through an argument or the receiver, or through a static field its code takes other
//! than to copy it at once ([`crate::shared::OneFunction::taken_statics`]). A later call of the same code on the
//! path, on either side, takes each of these as the earlier call's wherever their inputs are equal (the lengths and
//! cells of each array and String, each number; an array whose cells hold any values by the name of its content),
//! and new bits elsewhere: two calls are related by congruence, so that equal inputs give equal outcomes and unequal
//! ones any. The inputs must have one shape (which references are null, which are one object, each array's type and
//! cells), or the calls are not related. The new bits are named by the inputs as formulas, so two calls on the same
//! formulas end alike even where a merge let go of the record that relates them ([`Engine::absorb`] keeps only the
//! calls both paths made). A record holds an array result's cells as the call returned them ([`Call`]): a later
//! related call takes those, not what the array holds when it is made, which the caller may have written since
//! (`stale` in `tests/fixtures/record-countermodels`, I028). A merge chooses a String result by its guard where the
//! two paths name different objects by it.
//!
//! What a run of the callee can show that its inputs' values do not decide is kept out by the code it may have
//! ([`crate::shared::one_function`]): no comparison of references (the inputs name a String by its content, not by
//! which object it is), no call that can come back to itself, and no array of a length the inputs give, made by the
//! code or by a JDK method given a length (a `StackOverflowError` or an `OutOfMemoryError` is not among the
//! outcomes). Nor anything that lets a loop keep what each round makes past any heap: an array of references, an
//! object of the application's own class, a String made longer (`append`, `insert`, `concat`, `a + b`); an exception
//! given a cause is no sealed argument, so the reach refuses it (`tests/fixtures/allocation-countermodels` and `KEPT`
//! in `lib/tests/pairing.rs`, I029). A JDK method given an array (`Arrays.fill`, `System.arraycopy`) counts as a store
//! into it. Each array the code makes has a length known at the call, within what the engine makes as written. A String result is null
//! or a new String, under bits an earlier call's take where their inputs are equal, and which object it is, is not
//! computed: a comparison of it by reference ends the path with no verdict. The countermodels are in
//! `tests/fixtures/function-countermodels` (`lib/tests/function_countermodels.rs`) and `lib/tests/pairing.rs`
//! (`NAMED`). `--no-shared-callees` takes no call as one function.
//!
//! An instance method is taken where nothing can read its receiver after the call: no live local of any frame holds
//! it (an exception's handler is a way on from the call), no other place on a stack, no static field and no other
//! object. What the call leaves in the receiver is then no part of what the caller sees, and is not computed. bcrypt's
//! `crypt_raw` (example 287) is such a call: `hashpw` makes a `BCrypt`, calls it, and drops it. An array result is
//! taken where the code returns an array it made (`newarray` into a local nothing else sets, [`crate::shared::OneFunction::returns_made`])
//! of a length it computes from constants and the lengths of static fields' arrays ([`crate::shared::OneFunction::result_length`]),
//! which is a constant at the call: its cells are new bits named by the inputs as formulas, and an earlier call's
//! where their inputs are equal. One of any length would leave each read of it a fork and a loop over it unbounded,
//! so such a call runs as written. The countermodels are in `lib/tests/pairing.rs` (`KEYED`).
//!
//! This is sound for a proof, since every outcome a run of the callee has is among the ones the bits allow, and it
//! is what makes a cipher both versions run on equal inputs (bcrypt's, in example 307) cost nothing. It can be too
//! coarse for a counterexample, which is run on a JVM before it is believed, as one past a loop's invariant is: one
//! that does not reproduce leaves the check undecided. A check this leaves undecided is run again with every call
//! as written ([`super::check`]). A String result's content is not computed: a String method on it ends the path
//! with no verdict, but `equals` of two, which is true of one object and of the results of two calls whose inputs are
//! equal. A call that ends no run (a loop that does not stop) is taken to end; two versions that make such a call on
//! equal inputs are proved to agree, which is the regression check's partial reading. The countermodels are in
//! `lib/tests/pairing.rs` (`unchanged_callee_*`).
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
/// What a call taken as one function wrote into an array whose cells hold any values, and the cells it returned.
const RESULT: i64 = 6;
/// The first number of a place under a call's key ([`Ties::bits`]) for what it ended with: whether it threw, which
/// class, a number it returned, whether a String it returned is null, and the cells it left in each array it reached.
const OUTCOME: i64 = 7;

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
    /// What [`crate::shared::one_function`] said of each static method, by class, name and descriptor.
    ones: HashMap<(String, String, String), Option<Rc<crate::shared::OneFunction>>>,
    /// The calls taken as one function, the ones of them related to an earlier call, and the last call's number.
    pub(super) calls: u64,
    pub(super) calls_related: u64,
    last_call: u64,
}

/// What an opaque String a call taken as one function returned holds as its limit ([`Obj::limit`]).
pub(super) const ONE_FUNCTION_RESULT: &str = "the String a call taken as one function of both versions returned (lib/src/bmc/ties.rs): its content is not computed";

/// A call taken as one function of both versions, on a path: what decided it and what it gave.
#[derive(Debug, Clone)]
pub(super) struct Call {
    /// Its number, unique in the check.
    pub(super) id: u64,
    /// Its code's key ([`Engine::code_key`]), and its inputs' shape.
    function: i64,
    shape: Vec<i64>,
    inputs: Vec<Input>,
    /// One bit: whether it threw; and the index of the class it threw.
    threw: Bits,
    which: Bits,
    /// What it returned, if anything: a String by its object's number, which a merge chooses by its guard where the
    /// two paths name different objects ([`super::Engine::absorb`]).
    pub(super) result: Option<Val>,
    /// An array result's cells as the call returned them. A later related call takes these, not the cells the
    /// object holds when it is made, which the caller may have written since.
    returned: Vec<Bits>,
    /// The cells of each array it reached, after it, in the order its inputs reach them.
    written: Vec<Vec<Bits>>,
}

#[cfg(test)]
impl Call {
    /// A record of a call that returned `result`, for the tests of what keeps it ([`super::collect`]).
    pub(super) fn returning(id: u64, result: Val) -> Call {
        Call { id, function: 0, shape: Vec::new(), inputs: Vec::new(), threw: vec![FALSE], which: vec![FALSE], result: Some(result), returned: Vec::new(), written: Vec::new() }
    }
}

/// A value a call taken as one function reads: a number, the length and cells of an array or a String, or the
/// length and the name of the content of an array whose cells hold any values ([`Obj::content`]).
#[derive(Debug, Clone)]
enum Input {
    Bits(Bits),
    Content { length: Bits, cells: Vec<Bits> },
    Named { length: Bits, content: u64 },
}

/// Whether a parameter of this type is one a call taken as one function may have.
fn one_function_input(t: &Type) -> bool {
    match t {
        Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long => true,
        Type::Object(c) => c == "java/lang/String",
        Type::Array(e) => matches!(**e, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long),
        _ => false,
    }
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
        let adapter = match &frame.lambda_return {
            LambdaReturn::Pass => 0, LambdaReturn::Discard => 1, LambdaReturn::BoxInt => 2, LambdaReturn::IntegerValueOf => 3,
            // A pending reference cast or primitive conversion belongs to its exact call site.
            LambdaReturn::Adapt(..) | LambdaReturn::AdaptResult(..) => return None,
        };
        let mut key = vec![STATE, code, frame.pc() as i64, adapter, i64::from(path.unbound_platform_value.is_some())];
        let literals: HashMap<usize, String> = path.literals.iter().map(|(l, &o)| (o, unprefixed(&format!("{l:?}"), &previous))).collect();
        let mut numbers: HashMap<usize, i64> = HashMap::new();
        let mut queue: Vec<usize> = Vec::new();
        key.push(frame.locals.len() as i64);
        for local in &frame.locals {
            self.value(&mut key, local.as_ref(), &mut numbers, &mut queue)?;
        }
        key.push(frame.stack.len() as i64);
        for v in &frame.stack {
            self.value(&mut key, Some(v), &mut numbers, &mut queue)?;
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
            self.value(&mut key, Some(v), &mut numbers, &mut queue)?;
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
                self.value(&mut key, Some(v), &mut numbers, &mut queue)?;
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
                        self.value(&mut key, Some(r), &mut numbers, &mut queue)?;
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

    fn value(&mut self, key: &mut Vec<i64>, v: Option<&Val>, numbers: &mut HashMap<usize, i64>, queue: &mut Vec<usize>) -> Option<()> {
        match v {
            Some(Val::Unobserved(_)) => return None,
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
        Some(())
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

impl Engine<'_> {
    /// A call of the method `member` (its arguments on the stack, its class initialized) taken as one function of
    /// both versions: see the module's notes. `receiver` is, for an instance method, the receiver's object and the
    /// class the call runs the method of (the one named for `invokespecial`, the object's own otherwise). `None`
    /// where the call runs as written: outside a pair of versions, in a lemma's proof, from the pair's own class, or
    /// where the method, its code, its inputs or the state of its classes is not one the rule takes.
    pub(super) fn call_as_one_function(&mut self, path: &mut Path, caller: &str, member: &crate::classfile::MemberRef, descriptor: &MethodDescriptor, receiver: Option<(usize, &str)>) -> Option<Step> {
        if !self.calls_as_one_function || self.pure.is_some() || caller == crate::pairing::CLASS || member.name == "<init>" {
            return None;
        }
        let previous = self.previous.clone().filter(|p| p.calls_as_one_function)?;
        let numeric = |t: &Type| matches!(t, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long);
        let array_result = matches!(&descriptor.ret, Type::Array(e) if numeric(e));
        let result_type = numeric(&descriptor.ret) || descriptor.ret == Type::Void || descriptor.ret == Type::Object("java/lang/String".into()) || array_result;
        if !result_type || !descriptor.params.iter().all(one_function_input) {
            return None;
        }
        let owner = receiver.map_or(member.owner.as_str(), |(_, owner)| owner);
        let (class, method) = self.cp.checker_method(owner, &member.name, &member.descriptor)?;
        if method.is_static() != receiver.is_none() || method.code.is_none() || !self.cp.is_application(&class.name) {
            return None;
        }
        let at = (class.name.clone(), member.name.clone(), member.descriptor.clone());
        let one = match self.ties.ones.get(&at) {
            Some(known) => known.clone(),
            None => {
                let root = crate::classfile::MemberRef::new(&class.name, &member.name, &member.descriptor);
                let found = crate::shared::one_function(self.cp, &root).ok().map(Rc::new);
                self.ties.ones.insert(at, found.clone());
                found
            }
        }?;
        // An array result is taken where the call makes it with a length the code gives as a constant here: one
        // of any length would leave every read of it a fork, and a loop over it unbounded.
        let result_length = match &one.result_length {
            Some(l) if array_result && one.returns_made => self.length_value(path, l).filter(|n| (0..=1 << 16).contains(n)).map(|n| n as usize),
            _ => None,
        };
        if array_result && result_length.is_none() {
            return None;
        }
        // Each array the code makes has a length known here, and one the engine would make as written: else the
        // call's outcome may be an `OutOfMemoryError`, which is not among the bits.
        if !one.allocations.iter().all(|l| self.length_value(path, l).is_some_and(|n| n <= 1 << 16)) {
            return None;
        }
        let (function, uses) = self.code_key(&class, &member.name, &member.descriptor, &previous)?;
        // The other version has the same code: else no call of the other's is ever related to this one.
        let other = match previous.original(&class.name) {
            Some(own) => own.to_string(),
            None if previous.relocated.contains(&class.name) => format!("{}/{}", previous.prefix, class.name),
            None => class.name.clone(),
        };
        if other != class.name {
            let (theirs, _) = self.cp.checker_method(&other, &member.name, &member.descriptor)?;
            if self.code_key(&theirs, &member.name, &member.descriptor, &previous)?.0 != function {
                return None;
            }
        }
        // The classes whose static state the code reads are initialized, or have no initializer to run.
        for c in uses.iter() {
            if !matches!(path.classes.get(c), Some(ClassState::Done | ClassState::Assumed)) {
                let runs = std::iter::once(c.clone()).chain(self.cp.superclasses(c)).any(|s| self.cp.application(&s).ok().flatten().is_some_and(|cf| cf.method("<clinit>", "()V").is_some()));
                if runs {
                    return None;
                }
            }
        }
        // The receiver: nothing reads it after the call, so what the call leaves in it is no part of the outcome.
        let n = descriptor.params.len();
        if let Some((o, _)) = receiver {
            let at = path.frames.last()?.stack.len().checked_sub(n + 1)?;
            if !self.unreachable_after(path, o, at) {
                return None;
            }
        }
        // The inputs: the arguments, the receiver's fields, then the static fields of those classes, by their own
        // names. An array the call may store into is one it reaches through any of these but a static it does not
        // take ([`crate::shared::OneFunction::taken_statics`]).
        let stack = &path.frames.last()?.stack;
        let args: Vec<Val> = stack.get(stack.len().checked_sub(n)?..)?.to_vec();
        let (mut shape, mut inputs, mut numbers, mut arrays) = (vec![function], Vec::new(), HashMap::new(), Vec::new());
        for v in &args {
            self.one_function_input(path, v, true, &mut shape, &mut inputs, &mut numbers, &mut arrays)?;
        }
        if let Some((o, _)) = receiver {
            let fields = self.instance_fields(path, o)?;
            let class = path.objects[o].class.clone();
            let name = self.class_key(&class, &previous);
            shape.extend([6, name, fields.len() as i64]);
            for (key, descriptor) in &fields {
                let v = match path.objects[o].fields.get(key) {
                    Some(v) => v.clone(),
                    None => self.default_value(descriptor).ok()?,
                };
                let name = self.ties.name(key);
                shape.push(name);
                self.one_function_input(path, &v, true, &mut shape, &mut inputs, &mut numbers, &mut arrays)?;
            }
        }
        let mut statics: Vec<(String, String, bool, Val)> = path.statics.iter().filter(|((c, _), _)| uses.contains(c)).map(|((c, f), v)| (unprefixed(c, &previous), f.clone(), one.taken_statics.contains(&(c.clone(), f.clone())), v.clone())).collect();
        statics.sort_by(|x, y| (&x.0, &x.1).cmp(&(&y.0, &y.1)));
        shape.push(statics.len() as i64);
        for (c, f, taken, v) in &statics {
            let (c, f) = (self.ties.name(c), self.ties.name(f));
            shape.extend([c, f]);
            self.one_function_input(path, v, *taken, &mut shape, &mut inputs, &mut numbers, &mut arrays)?;
        }
        // The earlier calls of the same code with inputs of the same shape, each with whether its inputs are these.
        let earlier: Vec<(Lit, Call)> = path.calls.iter().filter(|c| c.function == function && c.shape == shape).cloned().collect::<Vec<_>>().into_iter().map(|c| (self.same_inputs(&inputs, &c.inputs), c)).filter(|(same, _)| *same != FALSE).collect();
        // The call's inputs as formulas: what names an array result's content, and an array's of any cells it may
        // write.
        let mut key = vec![RESULT];
        key.extend(&shape);
        for input in &inputs {
            match input {
                Input::Bits(b) => bits_into(&mut key, b),
                Input::Content { length, cells } => {
                    bits_into(&mut key, length);
                    for cell in cells {
                        bits_into(&mut key, cell);
                    }
                }
                Input::Named { length, content } => {
                    bits_into(&mut key, length);
                    key.push(*content as i64);
                }
            }
        }
        let call_key = self.ties.key(key);
        // What it ended with: bits named by the inputs as formulas, as an array result's cells are, so that two calls
        // on the same formulas end alike even where a merge let go of the record that relates them; and an earlier
        // call's wherever their inputs are equal.
        let k = one.throws.len();
        let width = (usize::BITS - (k.max(2) - 1).leading_zeros()) as usize;
        let mut threw = self.ties.bits(&mut self.b, call_key, vec![OUTCOME, 0], 1).0;
        let mut which = self.ties.bits(&mut self.b, call_key, vec![OUTCOME, 1], width).0;
        for (same, c) in earlier.iter().rev() {
            threw = self.b.ite_bits(*same, &c.threw, &threw);
            which = self.b.ite_bits(*same, &c.which, &which);
        }
        let mut written = Vec::new();
        if one.writes_arrays {
            for (j, &o) in arrays.iter().enumerate() {
                if path.objects[o].unknown {
                    written.push(Vec::new());
                    continue;
                }
                let array = path.objects[o].array.as_ref()?;
                let w = cell_width(&array.element);
                let mut cells: Vec<Bits> = (0..array.cells.len()).map(|i| self.ties.bits(&mut self.b, call_key, vec![OUTCOME, 4, j as i64, i as i64], w).0).collect();
                // Where the inputs are equal, the cells below the length are the earlier call's; the length is
                // within both arrays' cells, so a cell one has and the other doesn't is past it.
                for (same, c) in earlier.iter().rev() {
                    let theirs = c.written.get(j)?;
                    for (mine, theirs) in cells.iter_mut().zip(theirs) {
                        *mine = self.b.ite_bits(*same, theirs, mine);
                    }
                }
                written.push(cells);
            }
        }
        // From here the call is taken: the path changes.
        let mut returned = Vec::new();
        let result = match &descriptor.ret {
            Type::Void => None,
            // An array the call made ([`crate::shared::OneFunction::returns_made`]), of the length the code gives
            // ([`crate::shared::OneFunction::result_length`]): a new object whose cells are new bits named by the
            // inputs as formulas, and an earlier call's wherever their inputs are equal.
            Type::Array(element) => {
                let n = result_length?;
                let width = cell_width(element);
                let mut cells: Vec<Bits> = (0..n).map(|i| self.ties.bits(&mut self.b, call_key, vec![RESULT, i as i64], width).0).collect();
                // The earlier call's cells as it returned them: its array may have been written since.
                for (same, c) in earlier.iter().rev() {
                    if c.returned.len() == n {
                        for (mine, theirs) in cells.iter_mut().zip(&c.returned) {
                            *mine = self.b.ite_bits(*same, theirs, mine);
                        }
                    }
                }
                returned = cells.clone();
                let length = self.b.constant(n as i64, 32);
                let class = descriptor.ret.descriptor();
                path.objects.push(Obj { array: Some(Array { element: (**element).clone(), length, cells, refs: Vec::new() }), ..Obj::new(&class) });
                Some(Val::R(Some(path.objects.len() - 1)))
            }
            // A String: null, or a new String whose content is not computed, and an earlier call's wherever their
            // inputs are equal. Which object it is is not computed either: a comparison of it by reference ends the
            // path with no verdict ([`Engine::same_lit`]).
            Type::Object(_) => {
                let o = self.alloc(path, "java/lang/String");
                path.objects[o].limit = Some(ONE_FUNCTION_RESULT.to_string());
                let null = self.ties.bits(&mut self.b, call_key, vec![OUTCOME, 3], 1).0[0];
                let mut v = choose(&mut self.b, null, &Val::R(None), &Val::R(Some(o))).unwrap_or(Val::R(Some(o)));
                for (same, c) in earlier.iter().rev() {
                    v = c.result.as_ref().and_then(|theirs| choose(&mut self.b, *same, theirs, &v)).unwrap_or(v);
                }
                Some(v)
            }
            t => {
                let fresh = self.typed_fresh(t, call_key);
                let mut v = if *t == Type::Long { Val::J(fresh) } else { Val::I(fresh) };
                for (same, c) in earlier.iter().rev() {
                    v = c.result.as_ref().and_then(|theirs| choose(&mut self.b, *same, theirs, &v)).unwrap_or(v);
                }
                Some(v)
            }
        };
        self.assumed.insert(format!("each call of {}.{} taken as one function of both versions (lib/src/bmc/ties.rs) ends: two versions that make it on equal inputs are taken to agree, so what is proved holds of the runs in which it ends", unprefixed(&class.name, &previous).replace('/', "."), member.name));
        self.ties.last_call += 1;
        self.ties.calls += 1;
        if !earlier.is_empty() {
            self.ties.calls_related += 1;
        }
        let call = Call { id: self.ties.last_call, function, shape, inputs, threw: threw.clone(), which: which.clone(), result: result.clone(), returned, written: written.clone() };
        Rc::make_mut(&mut path.calls).push(call);
        for (j, (&o, cells)) in arrays.iter().zip(written).enumerate() {
            if path.objects[o].unknown {
                path.objects[o].content = Some(self.ties.key(vec![RESULT, call_key as i64, j as i64]));
            } else if let Some(array) = path.objects[o].array.as_mut() {
                array.cells = cells;
            }
        }
        if let Err(e) = self.pop_args(path, n + usize::from(receiver.is_some())) {
            return Some(Err(e));
        }
        let mut thrown = Vec::with_capacity(k);
        for (i, class) in one.throws.iter().enumerate() {
            let index = self.b.constant(i as i64, width);
            let picked = if i + 1 == k { -self.b.ult(&which, &index) } else { self.b.eq(&which, &index) };
            thrown.push((self.b.and(threw[0], picked), class.clone()));
        }
        Some(self.one_function_outcome(path, thrown, result))
    }

    /// Adds the value `v` to a call's inputs and their shape; `None` where it is not one the rule takes.
    /// `writable`: whether the call may store into an array reached here ([`Self::call_as_one_function`]).
    #[allow(clippy::too_many_arguments)]
    fn one_function_input(&mut self, path: &Path, v: &Val, writable: bool, shape: &mut Vec<i64>, inputs: &mut Vec<Input>, numbers: &mut HashMap<usize, i64>, arrays: &mut Vec<usize>) -> Option<()> {
        match v {
            Val::I(b) => {
                shape.push(1);
                inputs.push(Input::Bits(b.clone()));
            }
            Val::J(b) => {
                shape.push(2);
                inputs.push(Input::Bits(b.clone()));
            }
            Val::R(None) => shape.push(3),
            Val::R(Some(o)) => {
                if let Some(&n) = numbers.get(o) {
                    shape.extend([4, n]);
                    // One object reached first through a static the call does not take and now through an input
                    // it may store into.
                    if writable && path.objects[*o].class.starts_with('[') && !arrays.contains(o) {
                        arrays.push(*o);
                    }
                    return Some(());
                }
                let n = numbers.len() as i64;
                numbers.insert(*o, n);
                let obj = &path.objects[*o];
                let string = obj.class == "java/lang/String";
                let array = obj.array.as_ref()?;
                let numeric = matches!(array.element, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long);
                if obj.lambda.is_some() || obj.limit.is_some() || !array.refs.is_empty() || !numeric || !(string || obj.class.starts_with('[')) {
                    return None;
                }
                // An array whose cells hold any values: by the name of its content, where one is kept.
                if obj.unknown {
                    let content = obj.content.filter(|_| !string)?;
                    let length = array.length.clone();
                    let element = self.ties.name(&array.element.descriptor());
                    if writable {
                        arrays.push(*o);
                    }
                    shape.extend([7, n, element, length.len() as i64]);
                    inputs.push(Input::Named { length, content });
                    return Some(());
                }
                if !string && writable {
                    arrays.push(*o);
                }
                let element = self.ties.name(&array.element.descriptor());
                // Not the number of cells: two encodings of one String may have room for different numbers of
                // bytes, and are equal where their lengths and the cells below them are.
                shape.extend([5, n, string as i64, element, array.length.len() as i64]);
                inputs.push(Input::Content { length: array.length.clone(), cells: array.cells.clone() });
            }
            Val::C(_) | Val::Unobserved(_) => return None,
        }
        Some(())
    }

    /// The value of a length the code computes ([`crate::shared::Length`]) on this path: `None` where a static
    /// field's array or its length is not known here.
    fn length_value(&self, path: &Path, length: &crate::shared::Length) -> Option<i64> {
        use crate::classfile::ArithOp;
        use crate::shared::Length;
        Some(match length {
            Length::Constant(v) => i64::from(*v),
            Length::Static(class, name) => {
                let Some(Val::R(Some(o))) = path.statics.get(&(class.clone(), name.clone())) else { return None };
                self.b.constant_value(&path.objects[*o].array.as_ref()?.length)?
            }
            Length::Op(op, a, b) => {
                let (a, b) = (i32::try_from(self.length_value(path, a)?).ok()?, i32::try_from(self.length_value(path, b)?).ok()?);
                i64::from(match op {
                    ArithOp::Add => a.wrapping_add(b),
                    ArithOp::Sub => a.wrapping_sub(b),
                    ArithOp::Mul => a.wrapping_mul(b),
                    _ => return None,
                })
            }
        })
    }

    /// Whether nothing can read the object `o` once the call whose receiver it is (at `at` on the top frame's stack)
    /// returns: no live local of any frame holds it, no other place on a stack, no static field and no other
    /// object's field or cell. Then what the call leaves in it is no part of what the caller sees. A local that is
    /// not live is one every way on from the call writes before it reads, an exception's handler included
    /// ([`Decoded::live`]).
    fn unreachable_after(&self, path: &Path, o: usize, at: usize) -> bool {
        let refers = |v: &Val| v.options().is_some_and(|options| options.iter().any(|(_, r)| *r == Some(o)));
        let top = path.frames.len() - 1;
        for (i, frame) in path.frames.iter().enumerate() {
            let live = &frame.code.live[frame.at];
            for (slot, local) in frame.locals.iter().enumerate() {
                if local.as_ref().is_some_and(refers) && live.get(slot).copied().unwrap_or(true) {
                    return false;
                }
            }
            if frame.stack.iter().enumerate().any(|(k, v)| (i != top || k != at) && refers(v)) {
                return false;
            }
        }
        if path.statics.values().any(refers) || path.literals.values().any(|&l| l == o) {
            return false;
        }
        path.objects.iter().enumerate().all(|(p, obj)| p == o || !(obj.fields.values().any(refers) || obj.array.as_ref().is_some_and(|a| a.refs.iter().any(refers)) || obj.same.iter().any(|(_, s)| *s == o)))
    }

    /// The instance fields of the object `o`, by their keys in it and their descriptors, its class's first and then
    /// each superclass's up to `Object`; `None` where a superclass is the JDK's and not `Object`.
    fn instance_fields(&mut self, path: &Path, o: usize) -> Option<Vec<(String, String)>> {
        let mut out = Vec::new();
        let mut class = Some(path.objects[o].class.clone());
        while let Some(c) = class.filter(|c| c != "java/lang/Object") {
            let file = self.cp.application(&c).ok().flatten()?;
            for f in file.fields.iter().filter(|f| !f.is_static()) {
                out.push((self.field_key(path, o, &c, &f.name, &f.descriptor).ok()?, f.descriptor.clone()));
            }
            class = file.super_class.clone();
        }
        Some(out)
    }

    /// Whether two calls' inputs of one shape are equal: each number, and each array's or String's length and its
    /// cells below the length.
    fn same_inputs(&mut self, x: &[Input], y: &[Input]) -> Lit {
        let mut lits = Vec::new();
        for (a, b) in x.iter().zip(y) {
            match (a, b) {
                (Input::Bits(p), Input::Bits(q)) if p.len() == q.len() => lits.push(self.b.eq(p, q)),
                (Input::Content { length: lp, cells: cp }, Input::Content { length: lq, cells: cq }) if lp.len() == lq.len() => {
                    lits.push(self.b.eq(lp, lq));
                    // Both lengths within the cells both have, so that the cells compared are all there are. Of one
                    // length and as many cells, the cells compared are all either has: a length is within its
                    // array's cells on every path ([`Engine::new_array_cells`]).
                    if lp != lq || cp.len() != cq.len() {
                        let room = self.b.constant(cp.len().min(cq.len()) as i64, lp.len());
                        let within = self.b.slt(&room, lp);
                        lits.push(-within);
                    }
                    for (i, (c, d)) in cp.iter().zip(cq).enumerate() {
                        let here = self.b.constant(i as i64, lp.len());
                        let inside = self.b.slt(&here, lp);
                        let same = self.b.eq(c, d);
                        lits.push(self.b.or(-inside, same));
                    }
                }
                // Two contents of one name are the same cells; of two names, not known to be.
                (Input::Named { length: lp, content: x }, Input::Named { length: lq, content: y }) if lp.len() == lq.len() && x == y => lits.push(self.b.eq(lp, lq)),
                _ => return FALSE,
            }
            if lits.last() == Some(&FALSE) {
                return FALSE;
            }
        }
        self.b.all(&lits)
    }

    /// The bits of a result of the type `t` under the call's key, within its range as an `int` holds it (a `boolean`
    /// is 0 or 1).
    fn typed_fresh(&mut self, t: &Type, call_key: u64) -> Bits {
        let (width, signed, to) = match t {
            Type::Boolean => (1, false, 32),
            Type::Byte => (8, true, 32),
            Type::Char => (16, false, 32),
            Type::Short => (16, true, 32),
            Type::Long => (64, false, 64),
            _ => (32, false, 32),
        };
        let mut bits = self.ties.bits(&mut self.b, call_key, vec![OUTCOME, 2], width).0;
        let top = if signed { *bits.last().expect("a bit") } else { FALSE };
        bits.resize(to, top);
        bits
    }

    /// A call taken as one function ends: it throws each class of `thrown` where its literal holds, and returns
    /// `result` (or nothing) on the rest. A side no input takes is not run.
    fn one_function_outcome(&mut self, path: &mut Path, mut thrown: Vec<(Lit, String)>, result: Option<Val>) -> Step {
        let rest = thrown.split_off(thrown.len().min(1));
        let Some((lit, class)) = thrown.pop() else {
            if let Some(v) = result {
                self.push(path, v);
            }
            self.advance(path);
            return Ok(None);
        };
        let raise = |engine: &mut Self, twin: &mut Path| -> Result<(), Stop> {
            match engine.raise(twin, &class)? {
                None => Ok(()),
                Some(_) => Err(Stop::Unsupported("an exception a call taken as one function threw left the harness".into())),
            }
        };
        match self.sides(path, lit)? {
            Sides::Then => {
                path.cond.push(lit);
                raise(self, path)?;
                Ok(None)
            }
            Sides::Else => {
                path.cond.push(-lit);
                self.one_function_outcome(path, rest, result)
            }
            Sides::Both { then_models, else_models } => {
                let mut twin = self.split(path, lit, then_models, else_models, true);
                raise(self, &mut twin)?;
                self.pending.push(twin);
                self.one_function_outcome(path, rest, result)
            }
            Sides::Undecided { model_takes_then: true } => {
                let mut twin = self.split_undecided(path, lit, true);
                self.one_function_outcome(&mut twin, rest, result)?;
                self.pending.push(twin);
                raise(self, path)?;
                Ok(None)
            }
            Sides::Undecided { model_takes_then: false } => {
                let twin = self.split_undecided(path, lit, false);
                if let Some(mut twin) = self.settle(twin)? {
                    raise(self, &mut twin)?;
                    self.pending.push(twin);
                }
                self.one_function_outcome(path, rest, result)
            }
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
