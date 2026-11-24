//! Any-length frames for int and long range fills and an int caller with aliased roots.
use super::{
    bytecode::{instruction, Element, Op, Test},
    classfile::{Class, Code},
    obligation, reject, unsupported, Obligations, Request, Result,
};
use std::cmp::Ordering::{Equal, Greater, Less};
use std::collections::BTreeSet;

mod caller;
mod fastutil;
#[cfg(test)]
mod export;

pub(super) const DIRECT: &str = "range-fill-frame-v1";
pub(super) const CALLER: &str = "range-fill-caller-frame-observation-v1";
const FILL_DESC: &str = "([IIII)V";
const GUARD_DESC: &str = "(III)V";

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
enum Term {
    Int(i32),
    Root,
    Other,
    From,
    To,
    Length,
    Value,
    Cursor,
    Next,
    K,
    OldOther,
}
use Term::*;

#[derive(Clone)]
struct Frame {
    locals: Vec<Option<Term>>,
    stack: Vec<Term>,
}
impl Frame {
    fn new(m: &Code, args: &[Term]) -> Result<Self> {
        let mut locals = vec![None; m.locals as usize];
        let params = locals
            .get_mut(..args.len())
            .ok_or_else(|| reject("range argument slots"))?;
        for (local, &arg) in params.iter_mut().zip(args) {
            *local = Some(arg);
        }
        Ok(Self {
            locals,
            stack: vec![],
        })
    }
    fn load(&self, slot: usize) -> Result<Term> {
        self.locals
            .get(slot)
            .copied()
            .flatten()
            .ok_or_else(|| unsupported("unbound range local"))
    }
    fn store(&mut self, slot: usize, v: Term) -> Result<()> {
        *self
            .locals
            .get_mut(slot)
            .ok_or_else(|| reject("range local outside frame"))? = Some(v);
        Ok(())
    }
    fn pop<const N: usize>(&mut self) -> Result<[Term; N]> {
        let start = self
            .stack
            .len()
            .checked_sub(N)
            .ok_or_else(|| reject("range stack underflow"))?;
        Ok(self.stack.split_off(start).try_into().unwrap())
    }
    fn local_step(&mut self, op: Op) -> Result<bool> {
        match op {
            Op::Nop => (),
            Op::Const(x) => self.stack.push(Int(x)),
            Op::Load(s) => self.stack.push(self.load(s)?),
            Op::Store(s) => {
                let [v] = self.pop()?;
                self.store(s, v)?;
            }
            _ => return Ok(false),
        }
        Ok(true)
    }
    fn operands(&mut self, pair: bool) -> Result<[Term; 2]> {
        if pair {
            self.pop()
        } else {
            Ok([self.pop::<1>()?[0], Int(0)])
        }
    }
}

#[derive(Clone, Copy, PartialEq)]
enum Phase {
    Guard,
    Entry,
    Exhausted,
    Iteration,
}

// The admissible relation is a set: non-strict bounds alone cannot decide a strict test.
fn branch([a, b]: [Term; 2], test: Test, phase: Phase) -> Result<bool> {
    if let (Int(x), Int(y)) = (a, b) {
        return Ok(test.value(x.cmp(&y)));
    }
    if a == b {
        return Ok(test.value(Equal));
    }
    let rank = |v| match v {
        Int(0) => Some(0),
        From => Some(1),
        Cursor if phase == Phase::Exhausted => Some(3),
        Cursor => Some(2),
        To => Some(3),
        Length => Some(4),
        _ => None,
    };
    if let (Some(x), Some(y)) = (rank(a), rank(b)) {
        if x == y {
            return Ok(test.value(Equal));
        }
        let order = if x < y { Less } else { Greater };
        let strict = phase == Phase::Iteration && x.min(y) <= 2 && x.max(y) >= 3;
        if strict || test.value(order) == test.value(Equal) {
            return Ok(test.value(order));
        }
    }
    Err(unsupported(format!("range guard {a:?} {test:?} {b:?}")))
}

struct Cut {
    head: usize,
    slot: usize,
    element: Element,
}

// Only the iteration may change the heap, and only by writing Value to Root[Cursor].
// The optional result is the state at the next cut; None is a checked normal return.
fn walk(
    class: &Class,
    method: &Code,
    guard_name: &str,
    cut: &Cut,
    phase: Phase,
    mut state: Frame,
    keys: &mut Obligations,
) -> Result<Option<Frame>> {
    let body = matches!(phase, Phase::Exhausted | Phase::Iteration);
    let mut pc = if body { cut.head } else { 0 };
    let mut seen = BTreeSet::new();
    let mut wrote = false;
    let mut checked_range = false;
    loop {
        if !seen.insert(pc) {
            return Err(unsupported(format!("unrepresented range cycle at {pc}")));
        }
        let (op, mut next) = instruction(method.bytes, pc)?;
        let edge = next.to_string();
        if !state.local_step(op)? {
            match op {
                Op::Length if state.pop::<1>()? == [Root] => {
                    state.stack.push(Length);
                    obligation(keys, method, pc, &edge, "nonnull");
                }
                Op::Call(i) if phase == Phase::Entry => {
                    if class.method_ref(i)? != (class.owner, guard_name, GUARD_DESC)
                        || state.pop::<3>()? != [Length, From, To]
                    {
                        return Err(unsupported(format!(
                            "rangeCheck target or arguments at {pc}"
                        )));
                    }
                    checked_range = true;
                    obligation(keys, method, pc, &edge, "resolved-valid-range");
                }
                Op::If(test, pair, dest) => {
                    let taken = branch(state.operands(pair)?, test, phase)
                        .map_err(|e| unsupported(format!("{} at {}@{pc}", e.1, method.name)))?;
                    if taken {
                        next = dest;
                    }
                    if phase == Phase::Guard {
                        obligation(keys, method, pc, &next.to_string(), "implied-by-range");
                    }
                }
                Op::Goto(dest) => next = dest,
                Op::Write(element) if phase == Phase::Iteration && element == cut.element => {
                    if state.pop::<3>()? != [Root, Cursor, Value] {
                        return Err(reject(format!(
                            "written prefix or outside frame at store {pc}"
                        )));
                    }
                    wrote = true;
                    obligation(keys, method, pc, &edge, "in-bounds-prefix-store");
                }
                Op::Inc(s, 1) if phase == Phase::Iteration && state.load(s)? == Cursor => {
                    state.store(s, Next)?;
                    obligation(keys, method, pc, &edge, "no-signed-overflow");
                }
                Op::ReturnVoid if state.stack.is_empty() => {
                    let kind = match phase {
                        Phase::Guard => "normal-unchanged",
                        Phase::Exhausted => "exact-write-frame",
                        _ => return Err(reject(format!("premature range return at {pc}"))),
                    };
                    obligation(keys, method, pc, "exit", kind);
                    return Ok(None);
                }
                _ => {
                    return Err(unsupported(format!(
                        "range rule {op:?} at {}@{pc}",
                        method.name
                    )))
                }
            }
        }
        obligation(keys, method, pc, &next.to_string(), "step");
        if phase != Phase::Guard && next == cut.head {
            if !state.stack.is_empty() {
                return Err(unsupported("nonempty range cut stack"));
            }
            match phase {
                Phase::Entry if checked_range && state.load(cut.slot)? == From => {
                    obligation(keys, method, pc, &next.to_string(), "empty-written-prefix");
                }
                Phase::Iteration if wrote && state.load(cut.slot)? == Next => {
                    obligation(keys, method, pc, &next.to_string(), "extend-written-prefix");
                    obligation(keys, method, pc, &next.to_string(), "variant-decreases");
                }
                _ => {
                    return Err(reject(format!(
                        "written prefix or progress at back edge {pc}"
                    )))
                }
            }
            return Ok(Some(state));
        }
        pc = next;
    }
}

pub(super) fn check(
    class: &Class,
    callee: Option<&Class>,
    req: &Request,
    hints: &str,
    keys: &mut Obligations,
) -> Result<()> {
    if req.theorem == DIRECT {
        if let Some(dep) = callee {
            return fastutil::check(class, dep, req, hints, keys);
        }
    }
    let parts: Vec<_> = hints.split_ascii_whitespace().collect();
    let ["hints", "written-prefix", "remaining", head, slot] = parts[..] else {
        return Err(reject("missing written-prefix cut"));
    };
    let (target, fill_spec, guard_spec) = if req.theorem == DIRECT {
        (class, req.entry, req.companion)
    } else {
        (
            callee.ok_or_else(|| reject("missing external fill callee"))?,
            req.companion,
            ("rangeCheck", GUARD_DESC),
        )
    };
    let (element, parameter_slots) = match fill_spec.1 {
        FILL_DESC => (Element::Int, 4),
        "([JIIJ)V" if req.theorem == DIRECT => (Element::Long, 5),
        _ => return Err(unsupported("range-fill descriptors")),
    };
    if guard_spec.1 != GUARD_DESC {
        return Err(unsupported("range-fill descriptors"));
    }
    let cut = Cut {
        head: head.parse().map_err(|_| reject("invalid range cut PC"))?,
        slot: slot
            .parse()
            .map_err(|_| reject("invalid range cursor slot"))?,
        element,
    };
    let fill = target.method(fill_spec.0, fill_spec.1, true)?;
    let guard = target.package_method(guard_spec.0, guard_spec.1)?;
    if cut.slot < parameter_slots
        || cut.slot >= fill.locals as usize
        || cut.head >= fill.bytes.len()
    {
        return Err(unsupported("range cut point or cursor"));
    }
    let run = |method, phase, state, keys: &mut Obligations| {
        walk(target, method, guard_spec.0, &cut, phase, state, keys)
    };
    run(
        guard,
        Phase::Guard,
        Frame::new(guard, &[Length, From, To])?,
        keys,
    )?;
    let base = run(
        fill,
        Phase::Entry,
        Frame::new(fill, &[Root, From, To, Value])?,
        keys,
    )?;
    let mut base = base.ok_or_else(|| reject("missing range loop entry"))?;
    base.store(cut.slot, Cursor)?;
    if run(fill, Phase::Exhausted, base.clone(), keys)?.is_some() {
        return Err(reject("range loop continues at to"));
    }
    let back = run(fill, Phase::Iteration, base.clone(), keys)?;
    let mut after = back.ok_or_else(|| reject("range loop abandoned its prefix"))?;
    after.store(cut.slot, Cursor)?;
    if after.locals != base.locals {
        return Err(unsupported("untracked range induction local"));
    }
    if req.theorem == CALLER {
        caller::check(class, target, req, keys)?;
    }
    Ok(())
}
