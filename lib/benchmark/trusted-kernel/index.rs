//! Induction over every legal array length. A cut point partitions an iteration
//! into exhaustion, a matching cell, and a nonmatching cell. Prefix and frame
//! refer to the entry heap. Only the nonmatching path may re-enter the loop.
use super::{
    bytecode::{instruction, Element, Op, Test},
    classfile::{Class, Code},
    obligation, reject, unsupported, Obligations, Request, Result,
};
use std::cmp::Ordering;
use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Val {
    Root,
    Target,
    Length,
    Cursor,
    Next,
    Cell,
    Answer,
    // Sign is unknown on a miss, but zero is impossible. Orientation preserves identity.
    CellComparedToTarget,
    TargetComparedToCell,
    Const(i32),
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Path {
    Public,
    Entry,
    End,
    Hit,
    Miss,
}
#[derive(Clone)]
struct State {
    locals: Vec<Option<Val>>,
    stack: Vec<Val>,
}
impl State {
    fn new(method: &Code, initial: &[(usize, Val)]) -> Result<Self> {
        let mut state = Self {
            locals: vec![None; usize::from(method.locals)],
            stack: vec![],
        };
        for &(slot, value) in initial {
            state.store(slot, value)?;
        }
        Ok(state)
    }
    fn pop(&mut self) -> Result<Val> {
        self.stack
            .pop()
            .ok_or_else(|| reject("operand stack underflow"))
    }
    fn load(&self, slot: usize) -> Result<Val> {
        self.locals
            .get(slot)
            .copied()
            .flatten()
            .ok_or_else(|| reject(format!("undefined local {slot}")))
    }
    fn store(&mut self, slot: usize, value: Val) -> Result<()> {
        *self
            .locals
            .get_mut(slot)
            .ok_or_else(|| reject("local outside frame"))? = Some(value);
        Ok(())
    }
}
struct Context<'a> {
    class: &'a Class<'a>,
    req: &'a Request<'a>,
    head: usize,
    slot: usize,
    element: Element,
}
enum Exit {
    Head(State),
    Return,
}
fn guard(left: Val, right: Val, test: Test, path: Path) -> Result<bool> {
    use Val::*;
    let ord = if left == right {
        Some(Ordering::Equal)
    } else {
        match (left, right) {
            (Const(a), Const(b)) => Some(a.cmp(&b)),
            (Cursor, Length) | (Length, Cursor)
                if matches!(path, Path::End | Path::Hit | Path::Miss) =>
            {
                let o = if path == Path::End {
                    Ordering::Equal
                } else {
                    Ordering::Less
                };
                Some(if left == Cursor { o } else { o.reverse() })
            }
            _ => None,
        }
    };
    if let Some(o) = ord {
        return Ok(test.value(o));
    }
    let long_zero = matches!(
        (left, right),
        (CellComparedToTarget | TargetComparedToCell, Const(0))
            | (Const(0), CellComparedToTarget | TargetComparedToCell)
    );
    if (long_zero || matches!((left, right), (Cell, Target) | (Target, Cell)))
        && matches!(path, Path::Hit | Path::Miss)
    {
        match test {
            Test::Eq => return Ok(path == Path::Hit),
            Test::Ne => return Ok(path == Path::Miss),
            _ => (),
        }
    }
    Err(unsupported(format!(
        "unresolved guard {left:?} {test:?} {right:?} on {path:?}"
    )))
}
fn add(a: Val, b: Val, path: Path) -> Result<Val> {
    match (a, b) {
        (Val::Const(x), Val::Const(y)) => Ok(Val::Const(x.wrapping_add(y))),
        (x, Val::Const(0)) | (Val::Const(0), x) => Ok(x),
        (Val::Cursor, Val::Const(1)) | (Val::Const(1), Val::Cursor)
            if matches!(path, Path::Hit | Path::Miss) =>
        {
            Ok(Val::Next)
        }
        _ => Err(unsupported("cannot establish signed cursor arithmetic")),
    }
}
fn walk(
    cx: &Context,
    m: &Code,
    mut state: State,
    path: Path,
    keys: &mut Obligations,
) -> Result<Exit> {
    use Val::*;
    let body = matches!(path, Path::End | Path::Hit | Path::Miss);
    let mut pc = if body { cx.head } else { 0 };
    let mut seen = BTreeSet::new();
    loop {
        if !seen.insert(pc) {
            return Err(unsupported(format!("unrepresented cycle at {pc}")));
        }
        let (op, mut next) = instruction(m.bytes, pc)?;
        match op {
            Op::Nop => (),
            Op::Load(slot) => state.stack.push(state.load(slot)?),
            Op::Store(slot) => {
                let v = state.pop()?;
                state.store(slot, v)?;
            }
            Op::Const(v) => state.stack.push(Const(v)),
            Op::Length => {
                if state.pop()? != Root {
                    return Err(unsupported("unbound arraylength receiver"));
                }
                state.stack.push(Length);
                obligation(keys, m, pc, &next.to_string(), "safe");
            }
            Op::Read(width) | Op::Write(width) => {
                if width != cx.element {
                    return Err(reject("array cell width"));
                }
                let value = if matches!(op, Op::Write(_)) {
                    Some(state.pop()?)
                } else {
                    None
                };
                let offset = state.pop()?;
                let array = state.pop()?;
                if array != Root || offset != Cursor || !matches!(path, Path::Hit | Path::Miss) {
                    return Err(unsupported(format!("array safety at {pc}")));
                }
                if let Some(v) = value {
                    // Writing back the same element is a supported frame-preserving store.
                    if v != Cell && !(path == Path::Hit && v == Target) {
                        return Err(reject(format!("heap frame at store {pc}")));
                    }
                } else {
                    state.stack.push(Cell);
                }
                obligation(keys, m, pc, &next.to_string(), "safe");
            }
            Op::LongCompare => {
                let right = state.pop()?;
                let left = state.pop()?;
                let value = match (left, right) {
                    (Cell, Target) => CellComparedToTarget,
                    (Target, Cell) => TargetComparedToCell,
                    (Cell, Cell) | (Target, Target) => Const(0),
                    _ => return Err(unsupported("unbound lcmp operands")),
                };
                state.stack.push(value);
            }
            Op::LongToInt => return Err(unsupported("l2i drops high cell or target bits")),
            Op::Add => {
                let b = state.pop()?;
                let a = state.pop()?;
                state.stack.push(add(a, b, path)?);
            }
            Op::Inc(slot, d) => {
                let v = add(state.load(slot)?, Const(d), path)?;
                state.store(slot, v)?;
            }
            Op::If(test, pair, target) => {
                let right = if pair { state.pop()? } else { Const(0) };
                if guard(state.pop()?, right, test, path)? {
                    next = target;
                }
            }
            Op::Goto(target) => next = target,
            Op::Call(index) => {
                if path != Path::Public
                    || cx.class.method_ref(index)?
                        != (cx.req.owner, cx.req.companion.0, cx.req.companion.1)
                {
                    return Err(unsupported(format!("call resolution at {pc}")));
                }
                let n = state.stack.len();
                if n < 4 || state.stack[n - 4..] != [Root, Target, Const(0), Length] {
                    return Err(reject(format!("public call range or arguments at {pc}")));
                }
                state.stack.truncate(n - 4);
                state.stack.push(Answer);
                obligation(keys, m, pc, &next.to_string(), "resolved-full-range");
            }
            Op::Return => {
                let result = state.pop()?;
                if !state.stack.is_empty() {
                    return Err(unsupported("nonempty return stack"));
                }
                let want = match path {
                    Path::Public => Answer,
                    Path::Hit => Cursor,
                    Path::End => Const(-1),
                    _ => return Err(reject(format!("early return on {path:?} at {pc}"))),
                };
                if result != want {
                    return Err(reject(format!(
                        "return value at {pc} on {path:?}: {result:?}"
                    )));
                }
                obligation(keys, m, pc, "exit", "result");
                obligation(keys, m, pc, "exit", "frame");
                return Ok(Exit::Return);
            }
        }
        let edge = &next.to_string();
        obligation(keys, m, pc, edge, "step");
        if path != Path::Public && next == cx.head {
            if !state.stack.is_empty() {
                return Err(unsupported("nonempty cut-point stack"));
            }
            if path == Path::Entry {
                if state.load(cx.slot)? != Const(0) {
                    return Err(reject("prefix not empty on loop entry"));
                }
                obligation(keys, m, pc, edge, "invariant-entry");
            } else {
                // Invariant: 0 <= i <= length, no match on [0,i), entire heap unchanged.
                // Miss at i < length <= INT_MAX extends this prefix by exactly one.
                if path != Path::Miss || state.load(cx.slot)? != Next {
                    return Err(reject(format!(
                        "prefix progress or strictly decreasing variant at {pc}"
                    )));
                }
                obligation(keys, m, pc, edge, "invariant-preserved");
                obligation(keys, m, pc, edge, "variant-decreases");
            }
            return Ok(Exit::Head(state));
        }
        pc = next;
    }
}

pub(super) fn check(
    class: &Class,
    req: &Request,
    hints: &str,
    keys: &mut Obligations,
) -> Result<()> {
    let parts: Vec<_> = hints.split_ascii_whitespace().collect();
    let ["hints", "first-prefix", "remaining", head, slot, _witness_target, _witness_cells] =
        parts[..]
    else {
        return Err(reject(
            "missing prefix invariant or remaining-length measure",
        ));
    };
    let element = Element::for_descriptors(req.entry.1, req.companion.1)?;
    let cx = Context {
        class,
        req,
        head: head.parse().map_err(|_| reject("invalid cut PC"))?,
        slot: slot.parse().map_err(|_| reject("invalid cursor slot"))?,
        element,
    };
    let public = class.method(req.entry.0, req.entry.1, true)?;
    let helper = class.method(req.companion.0, req.companion.1, false)?;
    if cx.slot <= element.end_slot() || cx.head >= helper.bytes.len() {
        return Err(unsupported("cut point or cursor local"));
    }
    let parameters = [
        (0, Val::Root),
        (1, Val::Target),
        (element.end_slot() - 1, Val::Const(0)),
        (element.end_slot(), Val::Length),
    ];
    let proof = (|| {
        if !matches!(
            walk(
                &cx,
                public,
                State::new(public, &parameters[..2])?,
                Path::Public,
                keys
            )?,
            Exit::Return
        ) {
            return Err(reject("public call did not return"));
        }
        let Exit::Head(mut base) = walk(
            &cx,
            helper,
            State::new(helper, &parameters)?,
            Path::Entry,
            keys,
        )?
        else {
            return Err(reject("entry does not establish invariant"));
        };
        base.store(cx.slot, Val::Cursor)?;
        for path in [Path::End, Path::Hit, Path::Miss] {
            match (path, walk(&cx, helper, base.clone(), path, keys)?) {
                (Path::End | Path::Hit, Exit::Return) => (),
                (Path::Miss, Exit::Head(mut after)) => {
                    after.store(cx.slot, Val::Cursor)?;
                    if after.locals != base.locals {
                        return Err(unsupported("untracked local changes across induction edge"));
                    }
                }
                _ => return Err(reject(format!("incorrect induction exit for {path:?}"))),
            }
        }
        Ok(())
    })();
    match proof {
        Ok(()) => Ok(()),
        Err(failure) => match super::witness::explain(class, req, &parts[5..])? {
            Some(reason) => Err(reject(format!("{reason}; first rule: {}", failure.1))),
            None => Err(failure),
        },
    }
}
