//! A loop that goes round more often than the bound, covered by an invariant the engine finds and proves.
//!
//! Unwinding stops at `--unwind` iterations per entry of a loop, and a path that needs more used to end the run
//! with no verdict. A hash that runs its key schedule `2^cost` times (bcrypt's `crypt_raw`), or a table of 1024
//! words filled two at a time, is beyond any bound, and what a claim needs of such a loop is often little: that it
//! throws nothing and leaves the arrays the length they were. Where a path takes the back edge once more than the
//! bound allows, the engine now looks for an invariant of the loop's further iterations, and goes on from it:
//!
//! 1. **What the loop writes.** One iteration is run from the state the path is in, and then from that state with
//!    everything an iteration wrote set to any value, until an iteration writes nothing else. What is written is
//!    read off the states, not off the code: a local of the loop's frame, a field or a static field that holds a
//!    number, the cells of an array of numbers. An iteration that leaves a reference changed (a local that is live
//!    at the head, a field, a cell), a String builder's content, or a class newly initialized, is not covered, and
//!    the loop stays the unwound loop it was.
//! 2. **What stays true.** Candidates are stated of each number written that is a local, a field, or a cell of an
//!    array of at most [`SMALL_ARRAY`] cells: it is at least, or at most, the constant it is now; its lowest one,
//!    two or three bits are what they are now; it is not negative; it is an index into an array the frame holds
//!    (a local of it, or a field of an object that is one). Each holds of the state the path is in. An iteration
//!    is run from the state with what is written set to any value the candidates allow, and a candidate that
//!    the state back at the head may fail is dropped, until none is (Houdini's algorithm). What is left is an
//!    invariant by induction: it holds now, and an iteration from any state it holds of ends in one it holds of.
//! 3. **Going on.** The path goes on from the head in that state: what is written any value the invariant allows,
//!    everything else as it is. It leaves the loop where the loop's condition lets it, by an exit, a return or an
//!    exception, as any path does, and a path that comes back to the head ends there, since the state it is in is
//!    one the head's state already stands for.
//!
//! The state the path goes on from stands for every state the loop may be in after the bound, and for more: a
//! proof from it is a proof, and a violation found from it may be of a state no run reaches, which is why a
//! witness is run on the method (the interpreter, a JVM) before it is reported, as every witness is. On such a
//! path, and in the iterations run to find an invariant, a read at an index that is no constant, from an array of
//! more than [`LOOSE_CELLS`] cells, is any value, and a write at one leaves every cell any value from then on, as
//! a loop's writes to such an array do ([`Obj::unknown`]): a table looked up by a computed index (a cipher's
//! S-box) is not followed, which is again more states and never fewer.
//!
//! In a pair of versions the state the path goes on from is named by the state it was summarized from
//! ([`ties`]): a summary of the same code from the same state, on the other side or the same, goes on from the same
//! values, where each side's were free bits of its own. Such a summary is not looked for again: what the first
//! wrote and its invariant are taken over ([`Summary`]), where the path's condition holds every literal the first
//! was proved under. And a loop is given its invariant at its entry, without unwinding to the bound, only where
//! this path summarized it since its version began ([`Path::summarized`]), so that both versions do so at the same
//! points.
//!
//! **What is written** leaves out the places of objects nothing reachable holds: an array a method made and
//! dropped is never read or written again, and a loop entered once in each of many calls of its method would
//! otherwise carry every earlier call's arrays into its search ([`reachable`]).
//!
//! **That the loop ends** is shown apart: a local of the frame that an iteration leaves strictly greater, or
//! strictly less, as a signed number, on every way back to the head. Such a loop ends, since the local has
//! finitely many values. Where no local does, the run says so among what it takes for granted
//! ([`Outcome::assumed`]): what was proved then holds of the runs in which the loop ends.

use super::*;
use std::collections::{BTreeSet, HashSet};

/// The most rounds of running an iteration and dropping what it does not keep, before the loop is left unwound.
const MOST_ROUNDS: usize = 24;

/// The most cells of an array whose cells a candidate is stated of, each on its own.
pub(super) const SMALL_ARRAY: usize = 4;

/// The fewest cells of an array that a path past a summarized loop does not follow a computed index into.
pub(super) const LOOSE_CELLS: usize = 64;

/// The loop an iteration of which is being run to find its invariant: the depth of its frame, its head and the
/// last instruction that goes back to it (pcs). A path that leaves these has left the loop.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct Probe {
    depth: usize,
    head: u32,
    last: u32,
}

impl Probe {
    /// Whether the loop is the one of this head in the frame at this depth.
    pub(super) fn is(&self, depth: usize, head: u32) -> bool {
        self.depth == depth && self.head == head
    }

    /// Whether the path is outside the loop.
    pub(super) fn left(&self, path: &Path) -> bool {
        match path.frames.len().cmp(&self.depth) {
            std::cmp::Ordering::Less => true,
            std::cmp::Ordering::Equal => !(self.head..=self.last).contains(&path.frames.last().expect("a frame").pc()),
            std::cmp::Ordering::Greater => false,
        }
    }
}

/// What an iteration writes: a local of the loop's frame, a field of an object (by the object's allocation), a
/// static field, or the cells of an array.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Place {
    Local(usize),
    Field(u64, String),
    Static(String, String),
    Cells(u64),
}

/// One number a candidate is stated of.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Scalar {
    Local(usize),
    Field(u64, String),
    Static(String, String),
    Cell(u64, usize),
}

/// What a candidate says of its number.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Form {
    AtLeast(i64),
    AtMost(i64),
    /// Its lowest bits: how many, and their value.
    Low(usize, i64),
    NonNegative,
    /// Not negative and below the length of the array of this allocation.
    Index(u64),
}

impl Form {
    /// The form with no constant: what a candidate of another state of the same loop has in common with it.
    fn shape(&self) -> Form {
        match self {
            Form::AtLeast(_) => Form::AtLeast(0),
            Form::AtMost(_) => Form::AtMost(0),
            Form::Low(bits, _) => Form::Low(*bits, 0),
            other => other.clone(),
        }
    }
}

/// What finding a loop's invariant found, kept for the next time the loop is entered in this run (a key schedule's
/// loop, once for each of a hash's rounds): what an iteration wrote, and the candidates an iteration did not keep,
/// each by its number and its form's shape. The next search starts from these and not from nothing, which is one
/// iteration run where it was four or five. Nothing is taken on trust: what is written is found again by running
/// an iteration, and every candidate is checked of the state at hand. A candidate the state at hand did not
/// satisfy is not among them: that is said of the state, not of the loop.
#[derive(Debug, Clone, Default)]
pub(super) struct Known {
    written: BTreeMap<Place, (usize, bool)>,
    failed: BTreeSet<(Scalar, Form)>,
}

/// A loop's summary from a state with a key ([`ties`]), in that key's terms: an object by its number in the state,
/// a field and a class by the names a previous version's copy has as its own. A summary of the same code from a
/// state of the same key, on the other side of a pair of versions, is this one: what an iteration writes, the
/// invariant, whether the loop is shown to end, and the path condition it was proved under.
#[derive(Debug, Clone)]
pub(super) struct Summary {
    written: Vec<(Place, (usize, bool))>,
    candidates: Vec<Candidate>,
    ends: bool,
    cond: Vec<Lit>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct Candidate {
    of: Scalar,
    form: Form,
    /// Whether it is shown to hold in the state the path is in: by its form, or by the solver.
    shown: bool,
}

/// Where each object of a path is, by its allocation.
fn by_allocation(path: &Path) -> HashMap<u64, usize> {
    path.objects.iter().enumerate().map(|(i, o)| (o.made, i)).collect()
}

/// The objects of `path` that something it can still read holds, by allocation: whatever a frame's locals or
/// operand stack, a static field or an interned literal reaches through fields, cells of references and the
/// objects one is the same as ([`Obj::same`]). An object outside it is one no instruction reads or writes again,
/// such as the arrays a method made and returned without.
fn reachable(path: &Path) -> HashSet<u64> {
    let mut seen: HashSet<usize> = HashSet::new();
    let mut queue: Vec<usize> = Vec::new();
    let reach = |v: &Val, seen: &mut HashSet<usize>, queue: &mut Vec<usize>| {
        for (_, target) in v.options().unwrap_or_default() {
            if let Some(o) = target.filter(|o| seen.insert(*o)) {
                queue.push(o);
            }
        }
    };
    for frame in &path.frames {
        frame.locals.iter().flatten().chain(&frame.stack).for_each(|v| reach(v, &mut seen, &mut queue));
    }
    path.statics.values().for_each(|v| reach(v, &mut seen, &mut queue));
    for &o in path.literals.values() {
        if seen.insert(o) {
            queue.push(o);
        }
    }
    while let Some(o) = queue.pop() {
        let obj = &path.objects[o];
        obj.fields.values().for_each(|v| reach(v, &mut seen, &mut queue));
        if let Some(array) = &obj.array {
            array.refs.iter().for_each(|v| reach(v, &mut seen, &mut queue));
        }
        for &(_, same) in &obj.same {
            if seen.insert(same) {
                queue.push(same);
            }
        }
    }
    seen.into_iter().map(|o| path.objects[o].made).collect()
}

/// Whether the values `x` of `a` and `y` of `b` are the same: `None` where they differ and one is a reference.
fn same(a: &Path, b: &Path, x: &Val, y: &Val) -> Option<bool> {
    let object = |p: Option<usize>, q: Option<usize>| match (p, q) {
        (None, None) => true,
        (Some(p), Some(q)) => a.objects[p].made == b.objects[q].made,
        _ => false,
    };
    match (x, y) {
        (Val::I(x), Val::I(y)) | (Val::J(x), Val::J(y)) => Some(x == y),
        (Val::R(p), Val::R(q)) => object(*p, *q).then_some(true),
        (Val::C(p), Val::C(q)) => (p.0.len() == q.0.len() && p.0.iter().zip(&q.0).all(|((g, p), (h, q))| g == h && object(*p, *q))).then_some(true),
        _ => None,
    }
}

/// What a reference of `path` denotes, for a reason: the class of each object it may be, each with the number it was
/// made with, or null.
fn held(path: &Path, v: &Val) -> String {
    let one = |t: &Option<usize>| match t {
        Some(o) => format!("{} {}", path.objects[*o].class.replace('/', "."), path.objects[*o].made),
        None => "null".to_string(),
    };
    match v {
        Val::R(t) => one(t),
        Val::C(c) => format!("one of {} by a condition", c.0.iter().map(|(_, t)| one(t)).collect::<Vec<_>>().join(", ")),
        _ => "a number".to_string(),
    }
}

/// The width of a number and whether it is a long.
fn kind(v: &Val) -> Option<(usize, bool)> {
    match v {
        Val::I(bits) => Some((bits.len(), false)),
        Val::J(bits) => Some((bits.len(), true)),
        _ => None,
    }
}

/// What the state `back`, at the back edge of the loop, holds that the state `start` at its head did not: the
/// places an iteration wrote, each with its kind, or why the iteration is not one an invariant of numbers covers.
fn differences(start: &Path, back: &Path) -> Result<Vec<(Place, (usize, bool))>, String> {
    let mut out = Vec::new();
    let reference = |what: String| format!("an iteration changes {what}, which holds a reference");
    // The frame's locals, the ones dead at the head apart.
    let (frame, after) = (start.frames.last().expect("a frame"), back.frames.last().expect("a frame"));
    let live = &frame.code.live[frame.at];
    for slot in 0..frame.locals.len().max(after.locals.len()) {
        if !live.get(slot).copied().unwrap_or(true) {
            continue;
        }
        match (frame.locals.get(slot).cloned().flatten(), after.locals.get(slot).cloned().flatten()) {
            (None, None) => {}
            (Some(x), Some(y)) => match same(start, back, &x, &y) {
                Some(true) => {}
                Some(false) => out.push((Place::Local(slot), kind(&y).expect("a number"))),
                None => return Err(format!("{} (at the head {}; back at it {})", reference(format!("local {slot}")), held(start, &x), held(back, &y))),
            },
            (x, y) => return Err(format!("local {slot} is set on one way to the loop's head and not on another ({} at the head, {} back at it; live at the back edge: {:?})", if x.is_some() { "set" } else { "unset" }, if y.is_some() { "set" } else { "unset" }, after.code.live[after.at].get(slot))),
        }
    }
    if !after.stack.is_empty() {
        return Err("an iteration leaves a value on the operand stack".into());
    }
    if start.classes != back.classes || start.unheld_statics != back.unheld_statics {
        return Err("an iteration initializes a class".into());
    }
    for (key, y) in &back.statics {
        let place = || Place::Static(key.0.clone(), key.1.clone());
        match start.statics.get(key) {
            Some(x) => match same(start, back, x, y) {
                Some(true) => {}
                Some(false) => out.push((place(), kind(y).expect("a number"))),
                None => return Err(reference(format!("the static field {}.{}", key.0.replace('/', "."), key.1))),
            },
            None => match kind(y) {
                Some(kind) => out.push((place(), kind)),
                None => return Err(reference(format!("the static field {}.{}", key.0.replace('/', "."), key.1))),
            },
        }
    }
    let there = by_allocation(back);
    for o in &start.objects {
        // An object the state back at the head no longer holds is one nothing reads again.
        let Some(q) = there.get(&o.made).map(|&i| &back.objects[i]) else { continue };
        let class = o.class.replace('/', ".");
        for (key, y) in &q.fields {
            let place = || Place::Field(o.made, key.clone());
            match o.fields.get(key) {
                Some(x) => match same(start, back, x, y) {
                    Some(true) => {}
                    Some(false) => out.push((place(), kind(y).expect("a number"))),
                    None => return Err(reference(format!("the field {key} of a {class}"))),
                },
                None => match kind(y) {
                    Some(kind) => out.push((place(), kind)),
                    None => return Err(reference(format!("the field {key} of a {class}"))),
                },
            }
        }
        match (&o.array, &q.array) {
            (None, None) => {}
            (Some(x), Some(y)) => {
                if !o.class.starts_with('[') {
                    if x.length != y.length || x.cells != y.cells {
                        return Err(format!("an iteration changes the content of a {class}"));
                    }
                    continue;
                }
                if x.refs.len() != y.refs.len() || x.refs.iter().zip(&y.refs).any(|(x, y)| same(start, back, x, y) != Some(true)) {
                    return Err(reference(format!("a cell of a {}[]", x.element.java_name())));
                }
                // Cells that hold any values already are written to no effect ([`Obj::unknown`]).
                if !o.unknown && (q.unknown || x.cells != y.cells) {
                    out.push((Place::Cells(o.made), (cell_width(&x.element), false)));
                }
            }
            _ => return Err(format!("an iteration changes the content of a {class}")),
        }
    }
    Ok(out)
}

/// A summary's places, candidates and forms in the terms of a state's key ([`Summary`]), and back in the terms of
/// a path whose state has that key. Each is `None` where it has no such terms: an object the key does not number,
/// or a field or static field the path does not hold under that name.
struct Terms<'a> {
    previous: &'a crate::relocate::Previous,
    /// From allocation to number, the state's objects as [`Engine::state_key`] numbers them, and back.
    numbers: &'a HashMap<u64, i64>,
    made: HashMap<u64, u64>,
}

impl<'a> Terms<'a> {
    fn new(previous: &'a crate::relocate::Previous, numbers: &'a HashMap<u64, i64>) -> Terms<'a> {
        Terms { previous, numbers, made: numbers.iter().map(|(&made, &n)| (n as u64, made)).collect() }
    }

    fn name(&self, text: &str) -> String {
        ties::unprefixed(text, self.previous)
    }

    fn place_out(&self, place: &Place) -> Option<Place> {
        Some(match place {
            Place::Local(slot) => Place::Local(*slot),
            Place::Field(made, key) => Place::Field(*self.numbers.get(made)? as u64, self.name(key)),
            Place::Static(class, name) => Place::Static(self.name(class), name.clone()),
            Place::Cells(made) => Place::Cells(*self.numbers.get(made)? as u64),
        })
    }

    fn scalar_out(&self, scalar: &Scalar) -> Option<Scalar> {
        Some(match scalar {
            Scalar::Local(slot) => Scalar::Local(*slot),
            Scalar::Field(made, key) => Scalar::Field(*self.numbers.get(made)? as u64, self.name(key)),
            Scalar::Static(class, name) => Scalar::Static(self.name(class), name.clone()),
            Scalar::Cell(made, i) => Scalar::Cell(*self.numbers.get(made)? as u64, *i),
        })
    }

    fn form_out(&self, form: &Form) -> Option<Form> {
        Some(match form {
            Form::Index(made) => Form::Index(*self.numbers.get(made)? as u64),
            other => other.clone(),
        })
    }

    /// The object of number `n` of `path`, by allocation and by index.
    fn object(&self, here: &HashMap<u64, usize>, n: u64) -> Option<(u64, usize)> {
        let made = *self.made.get(&n)?;
        Some((made, *here.get(&made)?))
    }

    /// The field of the object `o` of `path` whose name in the key's terms is `key`.
    fn field(&self, path: &Path, o: usize, key: &str) -> Option<String> {
        path.objects[o].fields.keys().find(|k| self.name(k) == key).cloned()
    }

    /// The static field of `path` whose class in the key's terms is `class`.
    fn static_class(&self, path: &Path, class: &str, name: &str) -> Option<String> {
        path.statics.keys().find(|(c, n)| n == name && self.name(c) == class).map(|(c, _)| c.clone())
    }

    fn place_in(&self, path: &Path, here: &HashMap<u64, usize>, place: &Place) -> Option<Place> {
        Some(match place {
            Place::Local(slot) => Place::Local(*slot),
            Place::Field(n, key) => {
                let (made, o) = self.object(here, *n)?;
                Place::Field(made, self.field(path, o, key)?)
            }
            Place::Static(class, name) => Place::Static(self.static_class(path, class, name)?, name.clone()),
            Place::Cells(n) => Place::Cells(self.object(here, *n)?.0),
        })
    }

    fn scalar_in(&self, path: &Path, here: &HashMap<u64, usize>, scalar: &Scalar) -> Option<Scalar> {
        Some(match scalar {
            Scalar::Local(slot) => Scalar::Local(*slot),
            Scalar::Field(n, key) => {
                let (made, o) = self.object(here, *n)?;
                Scalar::Field(made, self.field(path, o, key)?)
            }
            Scalar::Static(class, name) => Scalar::Static(self.static_class(path, class, name)?, name.clone()),
            Scalar::Cell(n, i) => Scalar::Cell(self.object(here, *n)?.0, *i),
        })
    }

    fn form_in(&self, here: &HashMap<u64, usize>, form: &Form) -> Option<Form> {
        Some(match form {
            Form::Index(n) => Form::Index(self.object(here, *n)?.0),
            other => other.clone(),
        })
    }
}

impl Engine<'_> {
    /// Summarize a compiled half-open int fill at its loop head. With
    /// 0 <= cursor <= end <= array.length, each iteration writes one cell and
    /// increments a signed index strictly below MAX_VALUE. The final cursor
    /// is end and all earlier or later cells retain their entry values.
    pub(super) fn fill_loop(&mut self, path: &mut Path) -> Option<Step> {
        use Insn::*;
        if !self.invariants || path.probing.is_some() || path.loose || self.pure.is_some() || self.frame.is_some() { return None; }
        let frame = path.frames.last()?;
        let at = frame.at;
        let [Load(Kind::Int, cursor), Load(Kind::Int, end), IfICmp(Cond::Ge, exit),
            Load(Kind::Ref, array), Load(Kind::Int, index), Load(Kind::Int, value),
            ArrayStore(ArrayKind::Int), IInc(changed, 1), Goto(head)] = frame.code.insns.get(at..at + 9)? else { return None };
        if cursor != index || cursor != changed || cursor == end || cursor == value
            || *head != frame.pc() || Some(exit) != frame.code.pcs.get(at + 9) { return None; }
        let local = |i: u16| frame.locals.get(usize::from(i))?.as_ref();
        let (Val::I(start), Val::I(end), Val::R(Some(object)), Val::I(value)) =
            (local(*cursor)?, local(*end)?, local(*array)?, local(*value)?) else { return None };
        let object = *object;
        let contents = path.objects[object].as_array()?;
        if contents.element != Type::Int { return None; }
        let bad = [self.b.negative(start), self.b.slt(end, start), self.b.slt(&contents.length, end)];
        let mut outside = path.cond.clone();
        outside.push(self.any(&bad));
        match self.solve(&outside) {
            Ok(false) => {}
            Ok(true) => return None,
            Err(reason) => return Some(Err(reason)),
        }
        let (start, end, value, cursor) = (start.clone(), end.clone(), value.clone(), usize::from(*cursor));
        let cells = &mut path.objects[object].array.as_mut()?.cells;
        for (i, cell) in cells.iter_mut().enumerate() {
            let index = self.b.constant(i as i64, 32);
            let before = self.b.slt(&index, &start);
            let below = self.b.slt(&index, &end);
            let inside = self.b.and(-before, below);
            *cell = self.b.ite_bits(inside, &value, cell);
        }
        let frame = path.frames.last_mut()?;
        frame.locals[cursor] = Some(Val::I(end));
        frame.at = at + 9;
        Some(Ok(None))
    }

    /// Notes that the array `o` of `path` is read or written at `index`, while an iteration is run to find an
    /// invariant and the index is no constant.
    pub(super) fn index_used(&mut self, path: &Path, o: usize, index: &Bits) {
        if self.indexed.is_some() && self.b.constant_value(index).is_none() {
            let made = path.objects[o].made;
            self.indexed.as_mut().expect("some").push((made, index.clone()));
        }
    }

    /// Sets each place of `written` in `path` to any value: for each number set, the bits it had and the new,
    /// free ones, and whether a candidate may be stated of it (not of a cell of an array of more than
    /// [`SMALL_ARRAY`] cells), and whether the bits are made now. Under `tie`, the key of the state the loop is
    /// summarized from with its objects' numbers ([`Engine::state_key`]), the bits of a place are the ones that
    /// state's place was given before, if it was ([`ties`]).
    fn havoc(&mut self, path: &mut Path, written: &BTreeMap<Place, (usize, bool)>, tie: Option<&(u64, HashMap<u64, i64>)>) -> Vec<(Bits, Bits, bool, bool)> {
        let there = by_allocation(path);
        let mut new: Vec<(Bits, Bits, bool, bool)> = Vec::new();
        for (place, &(width, long)) in written {
            let zero = self.b.constant(0, width);
            // The place's name under the tie: `None` where it has none (an object the state does not reach).
            let named: Option<Vec<i64>> = tie.and_then(|(_, numbers)| match place {
                Place::Local(slot) => Some(vec![0, *slot as i64]),
                Place::Field(made, key) => Some(vec![1, *numbers.get(made)?, self.ties_name(key)]),
                Place::Static(class, name) => Some(vec![2, self.ties_name(class), self.ties_name(name)]),
                Place::Cells(made) => Some(vec![3, *numbers.get(made)?]),
            });
            let any = |engine: &mut Self, old: Option<&Val>, new: &mut Vec<(Bits, Bits, bool, bool)>, cell: Option<usize>| {
                let (bits, made) = match (tie, &named) {
                    (Some((state, _)), Some(place)) => {
                        let mut place = place.clone();
                        place.extend(cell.map(|c| c as i64));
                        engine.ties.bits(&mut engine.b, *state, place, width)
                    }
                    _ => (engine.b.fresh(width), true),
                };
                let before = match old {
                    Some(Val::I(old) | Val::J(old)) if old.len() == width => old.clone(),
                    _ => zero.clone(),
                };
                new.push((before, bits.clone(), true, made));
                if long {
                    Val::J(bits)
                } else {
                    Val::I(bits)
                }
            };
            match place {
                Place::Local(slot) => {
                    let old = path.frames.last().expect("a frame").locals[*slot].clone();
                    let value = any(self, old.as_ref(), &mut new, None);
                    path.frames.last_mut().expect("a frame").locals[*slot] = Some(value);
                }
                Place::Field(made, key) => {
                    if let Some(&o) = there.get(made) {
                        let old = path.objects[o].fields.get(key).cloned();
                        let value = any(self, old.as_ref(), &mut new, None);
                        path.objects[o].fields.insert(key.clone(), value);
                    }
                }
                Place::Static(class, name) => {
                    let key = (class.clone(), name.clone());
                    let old = path.statics.get(&key).cloned();
                    let value = any(self, old.as_ref(), &mut new, None);
                    path.statics.insert(key, value);
                }
                Place::Cells(made) => {
                    if let Some(&o) = there.get(made) {
                        // A large array's cells are not named one by one ([`Obj::unknown`]): what they hold is
                        // named by the summary under a tie, and is no content kept otherwise ([`ties`]).
                        if path.objects[o].unknown || path.objects[o].array.as_ref().is_some_and(|a| a.cells.len() > LOOSE_CELLS) {
                            path.objects[o].unknown = true;
                            path.objects[o].content = match (tie, &named) {
                                (Some((state, _)), Some(place)) => Some(self.summarized(*state, place[1])),
                                _ => None,
                            };
                        } else if let Some(cells) = path.objects[o].array.as_ref().map(|a| a.cells.clone()) {
                            let small = cells.len() <= SMALL_ARRAY;
                            for (i, cell) in cells.iter().enumerate() {
                                let Val::I(fresh) = any(self, Some(&Val::I(cell.clone())), &mut new, Some(i)) else { unreachable!("a cell is a number") };
                                new.last_mut().expect("just pushed").2 = small;
                                path.objects[o].array.as_mut().expect("an array").cells[i] = fresh;
                            }
                        }
                    }
                }
            }
        }
        new
    }

    /// The number `scalar` is in the state `path`, sign- or zero-extended as a load of it is.
    fn scalar(&self, path: &Path, there: &HashMap<u64, usize>, scalar: &Scalar) -> Option<Bits> {
        let number = |v: &Val| match v {
            Val::I(bits) | Val::J(bits) => Some(bits.clone()),
            _ => None,
        };
        match scalar {
            Scalar::Local(slot) => path.frames.last()?.locals.get(*slot)?.as_ref().and_then(number),
            Scalar::Field(made, key) => path.objects[*there.get(made)?].fields.get(key).and_then(number),
            Scalar::Static(class, name) => path.statics.get(&(class.clone(), name.clone())).and_then(number),
            Scalar::Cell(made, i) => {
                let array = path.objects[*there.get(made)?].array.as_ref()?;
                Some(self.b.extend_cell(&array.element, array.cells.get(*i)?))
            }
        }
    }

    /// Whether `candidate` holds in the state `path`, as a literal; `None` where the state has no such number.
    fn holds(&mut self, path: &Path, there: &HashMap<u64, usize>, candidate: &Candidate) -> Option<Lit> {
        let value = self.scalar(path, there, &candidate.of)?;
        let width = value.len();
        Some(match &candidate.form {
            Form::AtLeast(c) => {
                let c = self.b.constant(*c, width);
                self.b.sle(&c, &value)
            }
            Form::AtMost(c) => {
                let c = self.b.constant(*c, width);
                self.b.sle(&value, &c)
            }
            Form::Low(bits, c) => {
                let c = self.b.constant(*c, *bits);
                self.b.eq(&value[..*bits].to_vec(), &c)
            }
            Form::NonNegative => -self.b.negative(&value),
            Form::Index(made) => {
                let length = path.objects[*there.get(made)?].array.as_ref()?.length.clone();
                if width != length.len() {
                    return None;
                }
                self.b.ult(&value, &length)
            }
        })
    }

    /// The candidates of the numbers among `written` that an input taking the path to the state `base` satisfies
    /// there: see the module's notes. Whether every input does is shown later, of the ones an iteration keeps
    /// ([`Engine::summarize`]): what a loop computes fails most candidates in an iteration from any state, which
    /// asks the solver about one iteration, where the state the path is in holds everything computed so far.
    fn candidates(&mut self, base: &Path, written: &BTreeMap<Place, (usize, bool)>, failed: &BTreeSet<(Scalar, Form)>) -> Vec<Candidate> {
        let there = by_allocation(base);
        let mut scalars = Vec::new();
        for place in written.keys() {
            match place {
                Place::Local(slot) => scalars.push(Scalar::Local(*slot)),
                Place::Field(made, key) => scalars.push(Scalar::Field(*made, key.clone())),
                Place::Static(class, name) => scalars.push(Scalar::Static(class.clone(), name.clone())),
                Place::Cells(made) => {
                    let cells = there.get(made).and_then(|&o| base.objects[o].array.as_ref()).map_or(0, |a| a.cells.len());
                    if cells <= SMALL_ARRAY {
                        scalars.extend((0..cells).map(|i| Scalar::Cell(*made, i)));
                    }
                }
            }
        }
        // The arrays the frame holds: its locals, and the fields of the objects that are its locals.
        let mut arrays: Vec<u64> = Vec::new();
        let frame = base.frames.last().expect("a frame");
        let held = |v: &Val, arrays: &mut Vec<u64>, deeper: bool| {
            let Val::R(Some(o)) = v else { return Vec::new() };
            let obj = &base.objects[*o];
            if obj.is_array() {
                if !arrays.contains(&obj.made) {
                    arrays.push(obj.made);
                }
                return Vec::new();
            }
            if deeper {
                obj.fields.values().cloned().collect()
            } else {
                Vec::new()
            }
        };
        for local in frame.locals.iter().flatten() {
            for field in held(local, &mut arrays, true) {
                held(&field, &mut arrays, false);
            }
        }
        let mut out = Vec::new();
        // An input that takes the path, with other values of what the path has read and not asked about.
        let mut models: Vec<Model> = base.models.first().map(|m| (0..MOST_MODELS as u64).map(|k| if k == 0 { m.clone() } else { m.salted(k.wrapping_mul(0x9E37_79B9_7F4A_7C15)) }).collect()).unwrap_or_default();
        for of in scalars {
            let Some(value) = self.scalar(base, &there, &of) else { continue };
            let mut forms = Vec::new();
            match self.b.constant_value(&value) {
                Some(c) => {
                    forms.extend([Form::AtLeast(c), Form::AtMost(c)]);
                    forms.extend((1..=3usize).map(|bits| Form::Low(bits, c & ((1 << bits) - 1))));
                    if c >= 0 {
                        forms.push(Form::NonNegative);
                    }
                }
                None => forms.push(Form::NonNegative),
            }
            forms.extend(arrays.iter().map(|&made| Form::Index(made)));
            for form in forms {
                if failed.contains(&(of.clone(), form.shape())) {
                    continue;
                }
                let mut candidate = Candidate { of: of.clone(), form, shown: false };
                let Some(lit) = self.holds(base, &there, &candidate) else { continue };
                candidate.shown = lit == TRUE;
                if lit == TRUE || (lit != FALSE && models.iter_mut().all(|m| self.b.holds(m, lit))) {
                    out.push(candidate);
                }
            }
        }
        out
    }

    /// Runs the path `start`, which is at the head of the loop it probes, and every path that splits off it, until
    /// each is back at the head or has left the loop: the states back at the head. `None` where a path ends in a
    /// way an iteration that is covered does not (a gap refused, a loop inside it left unwound).
    fn iterate(&mut self, start: Path) -> Result<Option<(Vec<Path>, Vec<(u64, Bits)>)>, Stop> {
        let outer = (std::mem::take(&mut self.pending), std::mem::take(&mut self.waiting), std::mem::take(&mut self.deferred));
        let indexed = self.indexed.replace(Vec::new());
        self.pending.push(start);
        let mut backs = Vec::new();
        let result = loop {
            let path = match self.next_path() {
                Ok(Some(path)) => path,
                Ok(None) => break Ok(true),
                Err(stop) => break Err(stop),
            };
            if self.paths > self.max_paths {
                break Err(Stop::Budget(format!("more than {} paths; the budget is spent", self.max_paths)));
            }
            match self.run(path) {
                Ok(End::Back(_, Some(back))) => backs.push(*back),
                // A path back at the head of a loop inside this one is covered there.
                Ok(End::Back(_, None) | End::Left | End::Infeasible | End::Parked | End::Returned) => {}
                Ok(End::Gap | End::Violation(..) | End::Unwound(_)) => break Ok(false),
                Err(stop) => break Err(stop),
            }
        };
        (self.pending, self.waiting, self.deferred) = outer;
        let indexed = std::mem::replace(&mut self.indexed, indexed).unwrap_or_default();
        Ok(result?.then_some((backs, indexed)))
    }

    /// The path took the back edge from `from` to the loop head `head` once more than the bound allows: finds an
    /// invariant of the loop's further iterations and leaves the path at the head in the state that stands for
    /// them all, or ends it unwound, as it was before, with why none was found. See the module's notes.
    pub(super) fn summarize(&mut self, path: &mut Path, head: u32, from: u32) -> Step {
        let frame = path.frames.last().expect("a frame");
        let what = format!("{}.{} at pc {head}", frame.class.name.replace('/', "."), frame.method);
        if !self.invariants {
            return Ok(Some(End::Unwound(what)));
        }
        Ok(self.covered(path, head, from)?.map(|why| End::Unwound(format!("{what}; no invariant was found that covers its further iterations: {why}"))))
    }

    /// Whether the path is at the head of a loop that needed an invariant before in this run, entered afresh, on
    /// a path that is past a summarized loop already: the loop is then given its invariant at once, of all its
    /// iterations, and not unwound to the bound first. A loop of many iterations inside one of many more (a key
    /// schedule's, run for each of a hash's rounds) is otherwise unwound to the bound each time the outer one
    /// goes round. Where no invariant is found the loop is unwound as any other. In a pair of versions the loop is
    /// one this path summarized since its version began ([`Path::summarized`]), so that whether a loop is given its
    /// invariant at its entry or past the bound is the same on both sides, and their states tie ([`ties`]).
    pub(super) fn summarize_at_entry(&mut self, path: &mut Path) -> Result<bool, Stop> {
        if !path.loose || self.known_loops.is_empty() {
            return Ok(false);
        }
        let frame = path.frames.last().expect("a frame");
        let pc = frame.pc();
        let known = match &self.previous {
            Some(previous) => path.summarized.contains(&(ties::unprefixed(&frame.class.name, previous), frame.method.clone(), pc)),
            None => self.known_loops.contains_key(&(frame.class.name.clone(), frame.method.clone(), pc)),
        };
        if !frame.code.loops.iter().any(|(head, _)| *head == pc) || frame.back_edges.contains_key(&pc) || frame.summarized.contains(&pc) || !known {
            return Ok(false);
        }
        if self.covered(path, pc, pc)?.is_some() {
            path.frames.last_mut().expect("a frame").back_edges.insert(pc, 0);
            return Ok(false);
        }
        Ok(true)
    }

    /// Finds an invariant of the iterations of the loop headed at `head` from the state `path` is in, and leaves
    /// the path at the head in the state that stands for them all: `Some` with why, where none was found, the
    /// path as it was.
    fn covered(&mut self, path: &mut Path, head: u32, from: u32) -> Result<Option<String>, Stop> {
        let depth = path.frames.len();
        let frame = path.frames.last().expect("a frame");
        let what = format!("{}.{} at pc {head}", frame.class.name.replace('/', "."), frame.method);
        let known = (frame.class.name.clone(), frame.method.clone(), head);
        let unwound = |why: String| -> Result<Option<String>, Stop> { Ok(Some(why)) };
        let Some(&at) = frame.code.index.get(&head) else { return unsupported(format!("jump to no instruction at pc {head}")) };
        let last = frame.code.loops.iter().find(|(h, _)| *h == head).map_or(from, |(_, last)| *last);
        if !frame.stack.is_empty() {
            return unwound("a value is on the operand stack at its head".into());
        }
        // What an iteration computes is mostly not what is asked of it: the solver is given a gate when asked.
        self.b.defer();
        let mut base = path.clone();
        base.resumed = false;
        let top = base.frames.last_mut().expect("a frame");
        top.at = at;
        top.forget_dead();
        // On the main path of a pair of versions, a state whose key a summary was made from goes on as that one.
        let tie = if self.indexed.is_none() { self.state_key(&base) } else { None };
        if let Some(tie) = &tie {
            if let Some(tied) = self.reused(&base, tie)? {
                let (written, ends) = tied.1;
                if !ends {
                    self.assumed.insert(format!("the loop of {what} ends: no local of its frame was found that every iteration leaves greater, or every iteration leaves less, so what is proved holds of the runs in which it ends"));
                }
                self.loops.insert(what);
                let failed = self.known_loops.get(&known).map(|k| k.failed.clone()).unwrap_or_default();
                self.known_loops.insert(known, Known { written, failed });
                *path = tied.0;
                self.passed(path, head);
                return Ok(None);
            }
        }
        // What the loop wrote the last time it was summarized, where the state holds such a place, and no
        // candidate of a shape an iteration did not keep then. A place of an object nothing reachable holds (an
        // array an earlier call of the loop's method made and dropped) is one no iteration writes: it is left out,
        // and a loop entered once for each of many calls does not carry every earlier call's arrays.
        let Known { mut written, failed } = self.known_loops.get(&known).cloned().unwrap_or_default();
        let here = by_allocation(&base);
        let held = reachable(&base);
        written.retain(|place, was| match place {
            Place::Local(slot) => base.frames.last().and_then(|f| f.locals.get(*slot)).and_then(|v| v.as_ref()).and_then(kind) == Some(*was),
            Place::Field(made, key) => held.contains(made) && here.get(made).and_then(|&o| base.objects[o].fields.get(key)).and_then(kind) == Some(*was),
            Place::Static(class, name) => base.statics.get(&(class.clone(), name.clone())).and_then(kind) == Some(*was),
            Place::Cells(made) => held.contains(made) && here.get(made).is_some_and(|&o| base.objects[o].class.starts_with('[') && base.objects[o].array.as_ref().is_some_and(|a| cell_width(&a.element) == was.0)),
        });
        let mut failed = failed;
        let mut candidates = if written.is_empty() { Vec::new() } else { self.candidates(&base, &written, &failed) };
        // The candidates of a loop summarized before are mostly kept: whether they hold now is asked first, and
        // not after an iteration from a state that takes them for granted.
        if !candidates.is_empty() {
            candidates = self.shown(&base, candidates)?;
        }
        for _ in 0..MOST_ROUNDS {
            // The state an iteration starts in: what is written any value the candidates allow.
            let mut start = base.clone();
            let any = self.havoc(&mut start, &written, None);
            let there = by_allocation(&start);
            for candidate in &candidates {
                match self.holds(&start, &there, candidate) {
                    Some(TRUE) | None => {}
                    Some(lit) => start.cond.push(lit),
                }
            }
            // Inputs that take the path to the state it starts in, with no question to the solver: the ones that
            // take the path to the state it is in, what is written set to what that state holds (which the
            // candidates hold of), and, but for the first, the cells no candidate speaks of and everything the
            // path has not asked about drawn anew ([`Model::salted`]). An iteration from each shows what it does
            // not keep (what a cipher computes from a table is not negative in one state and negative in the
            // next). Where none of them is one, the solver gives the first.
            let assumed = start.cond[base.cond.len()..].to_vec();
            let mut models = Vec::new();
            for k in 0..MOST_MODELS as u64 / 2 {
                let Some(mut model) = base.models.get(k as usize % base.models.len().max(1)).cloned() else { break };
                if k > 0 {
                    model = model.salted(k.wrapping_mul(0x9E37_79B9_7F4A_7C15) ^ self.b.variables() as u64);
                }
                for (old, new, stated, _) in &any {
                    if *stated || k == 0 {
                        self.b.carry(&mut model, old, new);
                    }
                }
                if assumed.iter().all(|&lit| self.b.holds(&mut model, lit)) {
                    models.push(model);
                }
            }
            if models.is_empty() {
                if !self.solve(&start.cond)? {
                    return unwound("the state it is in after the bound is one no input reaches".into());
                }
                models.push(self.b.snapshot());
            }
            start.models = models;
            let mut probe = start.clone();
            probe.probing = Some(Probe { depth, head, last });
            probe.loose = true;
            probe.frames.last_mut().expect("a frame").summarized.insert(head);
            let Some((backs, indexed)) = self.iterate(probe)? else {
                return unwound("an iteration from the states it may be in meets a gap, or a loop inside it that is not covered".into());
            };
            let mut grew = false;
            for back in &backs {
                match differences(&start, back) {
                    Ok(places) => {
                        for (place, kind) in places {
                            grew |= written.insert(place, kind).is_none();
                        }
                    }
                    Err(why) => return unwound(why),
                }
            }
            if grew {
                candidates = self.candidates(&base, &written, &failed);
                continue;
            }
            // An index into an array is a candidate of a number the iteration used as one into that array. The
            // iteration ran from a state that took every candidate for granted: one dropped is another round.
            let before = candidates.len();
            candidates.retain(|candidate| match &candidate.form {
                Form::Index(array) if !self.scalar(&start, &there, &candidate.of).is_some_and(|value| indexed.iter().any(|(made, index)| made == array && *index == value)) => {
                    failed.insert((candidate.of.clone(), candidate.form.shape()));
                    false
                }
                _ => true,
            });
            // What the states back at the head keep: every candidate of every state in one question, and the ones
            // a state fails dropped, by the inputs that come back there before the solver is asked. A state back
            // at the head is reached under the start's condition and what the iteration took on its way.
            let mut models: Vec<Vec<Model>> = backs.iter().map(|back| back.models.clone()).collect();
            loop {
                let mut keep = vec![true; candidates.len()];
                let mut lits: Vec<Vec<Lit>> = vec![Vec::new(); backs.len()];
                for (b, back) in backs.iter().enumerate() {
                    let there = by_allocation(back);
                    for (k, candidate) in candidates.iter().enumerate() {
                        match self.holds(back, &there, candidate) {
                            Some(lit) if lit != FALSE && models[b].iter_mut().all(|model| self.b.holds(model, lit)) => lits[b].push(lit),
                            _ => keep[k] = false,
                        }
                    }
                }
                if keep.contains(&false) {
                    let mut kept = keep.iter();
                    candidates.retain(|candidate| {
                        let kept = *kept.next().expect("one for each");
                        if !kept {
                            failed.insert((candidate.of.clone(), candidate.form.shape()));
                        }
                        kept
                    });
                    continue;
                }
                // Where the conditions were made one at a join, each state's whole condition; else what it took
                // after the start's.
                let shared = backs.iter().all(|back| back.cond.starts_with(&start.cond));
                let mut failing = Vec::with_capacity(backs.len());
                let mut owns = Vec::with_capacity(backs.len());
                for (b, back) in backs.iter().enumerate() {
                    let all = self.b.all(&lits[b]);
                    let own = self.b.all(if shared { &back.cond[start.cond.len()..] } else { &back.cond });
                    failing.push(self.b.and(own, -all));
                    owns.push(own);
                }
                let fails = self.any(&failing);
                if fails == FALSE {
                    break;
                }
                let mut assumptions = if shared { start.cond.clone() } else { Vec::new() };
                assumptions.push(fails);
                if !self.solve(&assumptions)? {
                    break;
                }
                // The solver's input comes back to the head in one state at least and fails a candidate there:
                // it is dropped, with the others that input fails where it comes back.
                let mut model = self.b.snapshot();
                models = owns.iter().map(|&own| if self.b.holds(&mut model, own) { vec![model.clone()] } else { Vec::new() }).collect();
            }
            if candidates.len() < before {
                continue;
            }
            // What an iteration keeps holds from here on if it holds now: of every input that takes the path.
            candidates = self.shown(&base, candidates)?;
            if candidates.len() < before {
                continue;
            }
            // Inductive: the path goes on from the head in the state that stands for every later iteration.
            let ends = self.ends(&start, &backs, &written)?;
            if !ends {
                self.assumed.insert(format!("the loop of {what} ends: no local of its frame was found that every iteration leaves greater, or every iteration leaves less, so what is proved holds of the runs in which it ends"));
            }
            self.loops.insert(what);
            // A number kept an index into an array is used as one, for a loop this one is inside.
            if self.indexed.is_some() {
                for candidate in &candidates {
                    if let Form::Index(made) = candidate.form {
                        let value = self.scalar(&base, &here, &candidate.of).expect("a number");
                        if self.b.constant_value(&value).is_none() {
                            self.indexed.as_mut().expect("some").push((made, value));
                        }
                    }
                }
            }
            self.known_loops.insert(known, Known { written: written.clone(), failed });
            if let (Some((state, numbers)), Some(previous)) = (&tie, self.previous.clone()) {
                let terms = Terms::new(&previous, numbers);
                let written: Option<Vec<_>> = written.iter().map(|(place, kind)| Some((terms.place_out(place)?, *kind))).collect();
                let candidates: Option<Vec<_>> = candidates.iter().map(|c| Some(Candidate { of: terms.scalar_out(&c.of)?, form: terms.form_out(&c.form)?, shown: true })).collect();
                if let (Some(written), Some(candidates)) = (written, candidates) {
                    self.ties.summaries.entry(*state).or_insert(Summary { written, candidates, ends, cond: base.cond.clone() });
                }
            }
            *path = match self.tie(&base, &written, &candidates)? {
                Some(tied) => tied,
                None => start,
            };
            self.passed(path, head);
            return Ok(None);
        }
        unwound(format!("none was found in {MOST_ROUNDS} rounds"))
    }

    /// Marks the path as past the loop headed at `head` of its top frame, which an invariant covers.
    fn passed(&mut self, path: &mut Path, head: u32) {
        path.loose = true;
        let frame = path.frames.last_mut().expect("a frame");
        frame.summarized.insert(head);
        if let Some(previous) = &self.previous {
            let at = (ties::unprefixed(&frame.class.name, previous), frame.method.clone(), head);
            if !path.summarized.contains(&at) {
                Rc::make_mut(&mut path.summarized).insert(at);
            }
        }
    }

    /// The state the path goes on from past the loop: `start`, the state the invariant was shown of, with the bits
    /// of what the loop writes named by the state `base` at its head where that state has a key ([`ties`]), so that
    /// a summary of the same code from the same state, on the other side of a pair of versions, goes on from the
    /// same values. The invariant is stated of them as of `start`'s. Where no input takes the path in that state
    /// (bits named before, which the path has said things of), it is `start`, untied.
    fn tie(&mut self, base: &Path, written: &BTreeMap<Place, (usize, bool)>, candidates: &[Candidate]) -> Result<Option<Path>, Stop> {
        let Some(tie) = self.state_key(base) else { return Ok(None) };
        let mut tied = base.clone();
        let any = self.havoc(&mut tied, written, Some(&tie));
        let there = by_allocation(&tied);
        for candidate in candidates {
            match self.holds(&tied, &there, candidate) {
                Some(TRUE) | None => {}
                Some(lit) => tied.cond.push(lit),
            }
        }
        let assumed = tied.cond[base.cond.len()..].to_vec();
        let mut models = Vec::new();
        for model in &base.models {
            let mut model = model.clone();
            for (old, new, _, made) in &any {
                if *made {
                    self.b.carry(&mut model, old, new);
                }
            }
            if assumed.iter().all(|&lit| self.b.holds(&mut model, lit)) {
                models.push(model);
            }
        }
        if models.is_empty() {
            if !self.solve(&tied.cond)? {
                return Ok(None);
            }
            models.push(self.b.snapshot());
        }
        tied.models = models;
        Ok(Some(tied))
    }

    /// The state the path goes on from past the loop where a summary was made from a state of the key `tie` that
    /// `base` is in ([`Summary`]), on this path or the other side's, with what the loop writes and whether it is
    /// shown to end: the summary's places and invariant in `base`'s terms, tied as that summary's were ([`tie`]).
    /// `None` where none was, or where it does not carry over: a place or candidate `base` has no terms for, a
    /// path condition that does not hold every literal the summary was proved under, or a tied state no input
    /// takes the path in. An iteration from a state of one key runs the same code on the same values (the same
    /// bits) and writes the same places, so the invariant shown inductive under the summary's condition is
    /// inductive under a condition that has it, and holds at the head where it held at the other's.
    #[allow(clippy::type_complexity)]
    fn reused(&mut self, base: &Path, tie: &(u64, HashMap<u64, i64>)) -> Result<Option<(Path, (BTreeMap<Place, (usize, bool)>, bool))>, Stop> {
        let (Some(summary), Some(previous)) = (self.ties.summaries.get(&tie.0).cloned(), self.previous.clone()) else { return Ok(None) };
        let had: HashSet<Lit> = base.cond.iter().copied().collect();
        if !summary.cond.iter().all(|lit| had.contains(lit)) {
            return Ok(None);
        }
        let terms = Terms::new(&previous, &tie.1);
        let here = by_allocation(base);
        let written: Option<BTreeMap<_, _>> = summary.written.iter().map(|(place, kind)| Some((terms.place_in(base, &here, place)?, *kind))).collect();
        let candidates: Option<Vec<_>> = summary.candidates.iter().map(|c| Some(Candidate { of: terms.scalar_in(base, &here, &c.of)?, form: terms.form_in(&here, &c.form)?, shown: true })).collect();
        let (Some(written), Some(candidates)) = (written, candidates) else { return Ok(None) };
        let Some(tied) = self.tie(base, &written, &candidates)? else { return Ok(None) };
        self.ties.reused += 1;
        Ok(Some((tied, (written, summary.ends))))
    }

    /// The candidates among `candidates` that hold in the state `base`, of every input that takes the path there.
    fn shown(&mut self, base: &Path, candidates: Vec<Candidate>) -> Result<Vec<Candidate>, Stop> {
        let here = by_allocation(base);
        let mut kept = Vec::with_capacity(candidates.len());
        for mut candidate in candidates {
            if !candidate.shown {
                let Some(lit) = self.holds(base, &here, &candidate) else { continue };
                let mut assumptions = base.cond.clone();
                assumptions.push(-lit);
                if self.solve(&assumptions)? {
                    continue;
                }
                candidate.shown = true;
            }
            kept.push(candidate);
        }
        Ok(kept)
    }

    /// Whether the loop is shown to end: a local among `written` that every state back at the head holds strictly
    /// greater than `start` does, or every one strictly less, as a signed number.
    fn ends(&mut self, start: &Path, backs: &[Path], written: &BTreeMap<Place, (usize, bool)>) -> Result<bool, Stop> {
        if backs.is_empty() {
            return Ok(true);
        }
        let there = by_allocation(start);
        for place in written.keys() {
            let Place::Local(slot) = place else { continue };
            let scalar = Scalar::Local(*slot);
            let Some(before) = self.scalar(start, &there, &scalar) else { continue };
            'direction: for grows in [true, false] {
                for back in backs {
                    let Some(after) = self.scalar(back, &by_allocation(back), &scalar) else { continue 'direction };
                    if after.len() != before.len() {
                        continue 'direction;
                    }
                    let moved = if grows { self.b.slt(&before, &after) } else { self.b.slt(&after, &before) };
                    if moved == TRUE {
                        continue;
                    }
                    let mut assumptions = back.cond.clone();
                    assumptions.push(-moved);
                    if self.solve(&assumptions)? {
                        continue 'direction;
                    }
                }
                return Ok(true);
            }
        }
        Ok(false)
    }
}
