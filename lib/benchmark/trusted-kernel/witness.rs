//! Refutations start at the public bytecode. A repeated full state on a
//! deterministic active invocation certifies divergence. A fuel limit never does.
use super::{
    bytecode::{instruction, Op},
    classfile::{Class, Code},
    reject, unsupported, Request, Result,
};
use std::collections::HashSet;

#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
enum Value {
    Ref,
    Int(i32),
}
impl Value {
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
    heap: Vec<i32>,
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
                Op::Read | Op::Write => {
                    let val = if matches!(op, Op::Write) {
                        Some(pop(&mut stack)?.int()?)
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
                        stack.push(Value::Int(*cell));
                    }
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
                    let call = [(0, a[0]), (1, a[1]), (2, a[2]), (3, a[3])];
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
    let target: i32 = args[0]
        .parse()
        .map_err(|_| reject("invalid witness target"))?;
    let initial: Vec<i32> = if args[1] == "-" {
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
    let expected = initial
        .iter()
        .position(|&v| v == target)
        .map_or(-1, |v| v as i32);
    let m = class.method(req.entry.0, req.entry.1, true)?;
    let mut machine = Machine {
        class,
        req,
        heap: initial.clone(),
    };
    let actual = match machine.run(m, &[(0, Value::Ref), (1, Value::Int(target))], true) {
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
