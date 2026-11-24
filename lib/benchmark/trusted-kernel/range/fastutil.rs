//! Prove the two range-fill loops reached through a checked external bounds guard.
use super::*;
use super::super::classfile::Code;

// A semantic template over the decoded instructions. The separate external guard
// is interpreted on the valid-range domain with both values of its boolean field.
struct Path<'a, 'b> {
    method: &'a Code<'a>,
    pc: usize,
    keys: &'b mut Obligations,
}
impl Path<'_, '_> {
    fn emit(&mut self, pc: usize, edge: usize, key: &str) {
        obligation(self.keys, self.method, pc, &edge.to_string(), key)
    }
    fn step(&mut self, want: Op) -> Result<usize> {
        let pc = self.pc;
        let (actual, next) = instruction(self.method.bytes, pc)?;
        if actual != want {
            return Err(unsupported(format!("{}@{pc}: expected {want:?}, found {actual:?}", self.method.name)));
        }
        self.emit(pc, next, "step");
        self.pc = next;
        Ok(pc)
    }
    fn local(&mut self, slot: usize) -> Result<()> {
        self.step(Op::Load(slot)).map(|_| ())
    }
    fn branch_to(&mut self, test: Test, pair: bool) -> Result<(usize, usize)> {
        let pc = self.pc;
        let (op, next) = instruction(self.method.bytes, pc)?;
        let Op::If(actual, two, target) = op else {
            return Err(unsupported(format!("expected range branch at {pc}")));
        };
        if test != actual || two != pair {
            return Err(unsupported(format!("range branch comparison at {pc}")));
        }
        self.emit(pc, next, "step");
        self.emit(pc, target, "step");
        self.pc = next;
        Ok((pc, target))
    }
    fn call(&mut self, class: &Class, owner: &str, name: &str, desc: &str) -> Result<()> {
        let pc = self.pc;
        let (Op::Call(i), _) = instruction(self.method.bytes, pc)? else {
            return Err(unsupported(format!("expected static range guard at {pc}")));
        };
        if class.method_ref(i)? != (owner, name, desc) {
            return Err(unsupported(format!("range guard resolution at {}@{pc}", self.method.name)));
        }
        self.step(Op::Call(i))?;
        self.emit(pc, self.pc, "resolved-valid-range");
        Ok(())
    }
    fn done(&mut self, kind: &str) -> Result<()> {
        let pc = self.pc;
        if instruction(self.method.bytes, pc)?.0 != Op::ReturnVoid {
            return Err(unsupported(format!("expected normal return at {pc}")));
        }
        obligation(self.keys, self.method, pc, "exit", kind);
        Ok(())
    }
}

fn guard(class: &Class, method: &Code, enabled: bool, keys: &mut Obligations) -> Result<()> {
    let mut frame = Frame::new(method, &[Length, From, To])?;
    let mut pc = 0;
    let mut seen = BTreeSet::new();
    let mut read_flag = false;
    while seen.insert(pc) {
        if method.bytes.get(pc) == Some(&0xb2) {
            if read_flag {
                return Err(unsupported("multiple Boolean reads in the range guard"));
            }
            read_flag = true;
            let bytes = method.bytes.get(pc + 1..pc + 3).ok_or_else(|| reject("truncated getstatic"))?;
            if !class.local_static_bool(u16::from_be_bytes([bytes[0], bytes[1]]))? {
                return Err(unsupported("external guard reads an unresolved boolean field"));
            }
            frame.stack.push(Int(i32::from(enabled)));
            let next = pc + 3;
            obligation(keys, method, pc, &next.to_string(), "local-static-boolean");
            obligation(keys, method, pc, &next.to_string(), "step");
            pc = next;
            continue;
        }
        let (op, mut next) = instruction(method.bytes, pc)?;
        if !frame.local_step(op)? {
            match op {
                Op::If(test, pair, target) => {
                    if branch(frame.operands(pair)?, test, Phase::Guard)? {
                        next = target;
                    }
                    obligation(keys, method, pc, &next.to_string(), "implied-by-range");
                }
                Op::Goto(target) => next = target,
                Op::ReturnVoid if frame.stack.is_empty() => {
                    obligation(keys, method, pc, "exit", "normal-unchanged");
                    return Ok(());
                }
                _ => return Err(unsupported(format!("external guard {}@{pc}: {op:?}", method.name))),
            }
        }
        obligation(keys, method, pc, &next.to_string(), "step");
        pc = next;
    }
    Err(unsupported("cycle in the external bounds guard"))
}

pub(super) fn check(
    class: &Class, dep: &Class, req: &Request, hints: &str, keys: &mut Obligations,
) -> Result<()> {
    if req.entry.1 != FILL_DESC || req.companion.1 != "([III)V" || hints != "hints prefix-and-suffix remaining" {
        return Err(unsupported("two-loop fill request or hints"));
    }
    let f = class.method(req.entry.0, req.entry.1, true)?;
    let local = class.method(req.companion.0, req.companion.1, true)?;
    let mut p = Path { method: local, pc: 0, keys };
    p.local(0)?;
    let length = p.step(Op::Length)?;
    p.emit(length, p.pc, "nonnull");
    p.local(1)?;
    p.local(2)?;
    let (Op::Call(call), _) = instruction(local.bytes, p.pc)? else {
        return Err(unsupported("missing external bounds call"));
    };
    let (_, ext_name, _) = class.method_ref(call)?;
    p.call(class, dep.owner, ext_name, GUARD_DESC)?;
    p.done("normal-unchanged")?;
    let external = dep.method(ext_name, GUARD_DESC, true)?;
    for value in [false, true] {
        guard(dep, external, value, keys)?;
    }

    let mut p = Path { method: f, pc: 0, keys };
    p.local(0)?;
    p.local(1)?;
    p.local(2)?;
    p.call(class, class.owner, req.companion.0, req.companion.1)?;
    p.local(1)?;
    let (split, fwd) = p.branch_to(Test::Ne, false)?;
    let down = p.pc;
    p.emit(split, down, "empty-written-suffix");
    // At the descending cut, [cursor,to) is filled and all other cells retain
    // their entry values. The operand stack saves the value before post-decrement.
    p.local(2)?;
    let sub = p.step(Op::Inc(2, -1))?;
    p.emit(sub, p.pc, "no-signed-overflow");
    let (test, down_exit) = p.branch_to(Test::Eq, false)?;
    p.emit(test, down_exit, "exhausted-cursor-minus-one");
    p.local(0)?;
    p.local(2)?;
    p.local(3)?;
    let write = p.step(Op::Write(Element::Int))?;
    p.emit(write, p.pc, "in-bounds-suffix-store");
    let jump = p.pc;
    let (op, _) = instruction(f.bytes, jump)?;
    if op != Op::Goto(down) {
        return Err(unsupported(format!("descending back edge at {jump}")));
    }
    p.emit(jump, down, "step");
    p.emit(jump, down, "extend-written-suffix");
    p.emit(jump, down, "variant-decreases");

    p.pc = fwd;
    p.local(1)?;
    let (Op::Store(cursor), _) = instruction(f.bytes, p.pc)? else {
        return Err(unsupported("forward cursor initialization"));
    };
    if !(4..usize::from(f.locals)).contains(&cursor) {
        return Err(unsupported("forward cursor aliases a parameter"));
    }
    let init = p.step(Op::Store(cursor))?;
    let head = p.pc;
    p.emit(init, head, "empty-written-prefix");
    p.local(cursor)?;
    p.local(2)?;
    let (_, exit) = p.branch_to(Test::Ge, true)?;
    p.local(0)?;
    p.local(cursor)?;
    p.local(3)?;
    let write = p.step(Op::Write(Element::Int))?;
    p.emit(write, p.pc, "in-bounds-prefix-store");
    let inc = p.step(Op::Inc(cursor, 1))?;
    p.emit(inc, p.pc, "no-signed-overflow");
    let jump = p.pc;
    if instruction(f.bytes, jump)?.0 != Op::Goto(head) {
        return Err(unsupported(format!("forward back edge at {jump}")));
    }
    p.emit(jump, head, "step");
    p.emit(jump, head, "extend-written-prefix");
    p.emit(jump, head, "variant-decreases");
    for target in [down_exit, exit] {
        p.pc = target;
        p.done("exact-write-frame")?;
    }
    Ok(())
}
