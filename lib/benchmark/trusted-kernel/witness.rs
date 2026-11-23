//! Refutations start at the public bytecode. A repeated full state on a
//! deterministic active invocation certifies divergence. A fuel limit never does.
use super::{
    bytecode::{instruction, Element, Op},
    classfile::{Class, Code},
    reject, unsupported, Request, Result,
};
use std::collections::HashSet;

#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
enum Value {
    Ref,
    Int(i32),
    Long(i64),
}
impl Value {
    fn from_cell(x: i64, width: Element) -> Result<Self> {
        match width {
            Element::Long => Ok(Self::Long(x)),
            Element::Int => i32::try_from(x)
                .map(Self::Int)
                .map_err(|_| reject("witness outside int domain")),
        }
    }
    fn cell(self, width: Element) -> Result<i64> {
        match (self, width) {
            (Self::Int(v), Element::Int) => Ok(i64::from(v)),
            (Self::Long(v), Element::Long) => Ok(v),
            _ => Err(reject("witness cell width")),
        }
    }
    fn int(self) -> Result<i32> {
        match self {
            Self::Int(v) => Ok(v),
            _ => Err(reject("witness needs int")),
        }
    }
}
#[derive(Debug)]
enum Outcome {
    Returned(i32),
    Cycle(usize),
    Bounds(usize),
}
struct Machine<'a> {
    class: &'a Class<'a>,
    req: &'a Request<'a>,
    heap: Vec<i64>,
    width: Element,
}
impl Machine<'_> {
    fn run(&mut self, method: &Code, args: &[(usize, Value)], public: bool) -> Result<Outcome> {
        let mut locals = vec![None; usize::from(method.locals)];
        for &(slot, value) in args {
            *locals
                .get_mut(slot)
                .ok_or_else(|| reject("witness arguments"))? = Some(value);
        }
        let mut stack: Vec<Value> = vec![];
        let mut seen = HashSet::new();
        let mut pc = 0;
        let pop = |s: &mut Vec<Value>| s.pop().ok_or_else(|| reject("witness stack underflow"));
        let load = |locals: &[Option<Value>], s: usize| {
            locals
                .get(s)
                .copied()
                .flatten()
                .ok_or_else(|| reject("undefined witness local"))
        };
        loop {
            if seen.len() >= 2048 {
                return Err(unsupported("finite witness replay budget"));
            }
            if !seen.insert((pc, locals.clone(), stack.clone(), self.heap.clone())) {
                return Ok(Outcome::Cycle(pc));
            }
            let (op, mut next) = instruction(method.bytes, pc)?;
            match op {
                Op::Nop => (),
                Op::Const(v) => stack.push(Value::Int(v)),
                Op::Load(s) => stack.push(load(&locals, s)?),
                Op::Store(s) => {
                    *locals
                        .get_mut(s)
                        .ok_or_else(|| reject("witness store local"))? = Some(pop(&mut stack)?)
                }
                Op::Length => {
                    if pop(&mut stack)? != Value::Ref {
                        return Err(reject("witness arraylength type"));
                    }
                    stack.push(Value::Int(self.heap.len() as i32));
                }
                Op::Read(width) | Op::Write(width) => {
                    if self.width != width {
                        return Err(reject("witness array width"));
                    }
                    let val = if matches!(op, Op::Write(_)) {
                        Some(pop(&mut stack)?.cell(width)?)
                    } else {
                        None
                    };
                    let i = pop(&mut stack)?.int()?;
                    if pop(&mut stack)? != Value::Ref {
                        return Err(reject("witness array type"));
                    }
                    let Some(cell) = self.heap.get_mut(i as usize) else {
                        return Ok(Outcome::Bounds(pc));
                    };
                    if let Some(v) = val {
                        *cell = v;
                    } else {
                        stack.push(Value::from_cell(*cell, width)?);
                    }
                }
                Op::LongCompare => {
                    let b = pop(&mut stack)?.cell(Element::Long)?;
                    let a = pop(&mut stack)?.cell(Element::Long)?;
                    let cmp = match a.cmp(&b) {
                        std::cmp::Ordering::Less => -1,
                        std::cmp::Ordering::Equal => 0,
                        std::cmp::Ordering::Greater => 1,
                    };
                    stack.push(Value::Int(cmp));
                }
                Op::LongToInt => {
                    let a = pop(&mut stack)?.cell(Element::Long)?;
                    stack.push(Value::Int(a as i32));
                }
                Op::Add => {
                    let right = pop(&mut stack)?.int()?;
                    let left = pop(&mut stack)?.int()?;
                    stack.push(Value::Int(left.wrapping_add(right)));
                }
                Op::Inc(s, d) => {
                    let v = load(&locals, s)?.int()?;
                    locals[s] = Some(Value::Int(v.wrapping_add(d)));
                }
                Op::If(test, pair, target) => {
                    let right = if pair { pop(&mut stack)?.int()? } else { 0 };
                    if test.value(pop(&mut stack)?.int()?.cmp(&right)) {
                        next = target;
                    }
                }
                Op::Goto(t) => next = t,
                Op::Call(idx) => {
                    if !public
                        || self.class.method_ref(idx)?
                            != (self.req.owner, self.req.companion.0, self.req.companion.1)
                    {
                        return Err(unsupported("witness unknown call"));
                    }
                    if stack.len() < 4 {
                        return Err(reject("witness call arguments"));
                    }
                    let a = stack.split_off(stack.len() - 4);
                    let m = self
                        .class
                        .method(self.req.companion.0, self.req.companion.1, false)?;
                    let end = self.width.end_slot();
                    let call = [(0, a[0]), (1, a[1]), (end - 1, a[2]), (end, a[3])];
                    match self.run(m, &call, false)? {
                        Outcome::Returned(v) => stack.push(Value::Int(v)),
                        other => return Ok(other),
                    }
                }
                Op::Return => return Ok(Outcome::Returned(pop(&mut stack)?.int()?)),
            }
            pc = next;
        }
    }
}
pub(super) fn explain(class: &Class, req: &Request, args: &[&str]) -> Result<Option<String>> {
    let width = Element::for_descriptors(req.entry.1, req.companion.1)?;
    let target: i64 = args[0]
        .parse()
        .map_err(|_| reject("invalid witness target"))?;
    let initial: Vec<i64> = if args[1] == "-" {
        vec![]
    } else {
        args[1]
            .split(',')
            .map(|v| v.parse().map_err(|_| reject("invalid witness cell")))
            .collect::<Result<_>>()?
    };
    if initial.len() > 32 {
        return Err(unsupported("witness length"));
    }
    for &v in &initial {
        Value::from_cell(v, width)?;
    }
    let expected = initial
        .iter()
        .position(|&v| v == target)
        .map_or(-1, |v| v as i32);
    let m = class.method(req.entry.0, req.entry.1, true)?;
    let mut machine = Machine {
        class,
        req,
        heap: initial.clone(),
        width,
    };
    let actual = match machine.run(
        m,
        &[(0, Value::Ref), (1, Value::from_cell(target, width)?)],
        true,
    ) {
        Ok(v) => v,
        Err(_) => return Ok(None), // An incomplete concrete run supplies no refutation.
    };
    let why = match actual {
        Outcome::Returned(r) if machine.heap != initial => {
            format!("frame changed, return {r}, after {:?}", machine.heap)
        }
        Outcome::Returned(r) if r != expected => {
            format!("returned {r}, expected first index {expected}")
        }
        Outcome::Returned(_) => return Ok(None),
        Outcome::Cycle(pc) => format!("termination: identical complete state repeats at {pc}"),
        Outcome::Bounds(pc) => format!("normality: out-of-bounds access at {pc}"),
    };
    Ok(Some(format!(
        "checked witness {initial:?} target {target}: {why}"
    )))
}
