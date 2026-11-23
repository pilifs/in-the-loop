use super::{
    classfile::{Class, Code},
    obligation, reject, unsupported, Obligations, Request, Result,
};

// Each stack entry denotes a*x+b in Z/(2^32), with no heap or exception effects.
fn affine(method: &Code<'_>, out: &mut Obligations) -> Result<(u32, u32)> {
    let mut stack: Vec<(u32, u32)> = vec![];
    for (pc, &op) in method.bytes.iter().enumerate() {
        match op {
            0x1a => stack.push((1, 0)),
            0x02..=0x08 => stack.push((0, (i32::from(op) - 3) as u32)),
            0x60 | 0x68 => {
                let (c, d) = stack
                    .pop()
                    .ok_or_else(|| reject("scalar stack underflow"))?;
                let (a, b) = stack
                    .pop()
                    .ok_or_else(|| reject("scalar stack underflow"))?;
                let term = if op == 0x60 {
                    (a.wrapping_add(c), b.wrapping_add(d))
                } else if a == 0 || c == 0 {
                    (
                        a.wrapping_mul(d).wrapping_add(b.wrapping_mul(c)),
                        b.wrapping_mul(d),
                    )
                } else {
                    return Err(unsupported("nonlinear scalar multiplication"));
                };
                stack.push(term);
            }
            0xac => {
                if stack.len() != 1 {
                    return Err(reject("scalar return stack"));
                }
                obligation(out, method, pc, "exit", "normal-frame-value");
                return Ok(stack[0]);
            }
            _ => return Err(unsupported(format!("scalar opcode {op:#04x} at {pc}"))),
        }
    }
    Err(reject("scalar falls off Code"))
}
pub(super) fn check(
    class: &Class,
    req: &Request,
    hints: &str,
    out: &mut Obligations,
) -> Result<()> {
    if req.entry.1 != "(I)I" || req.companion.1 != "(I)I" || hints != "hints scalar" {
        return Err(unsupported("scalar descriptor or hints"));
    }
    let first = affine(class.method(req.entry.0, req.entry.1, true)?, out)?;
    let second = affine(class.method(req.companion.0, req.companion.1, true)?, out)?;
    if first != second {
        let x: u32 = if first.1 != second.1 { 0 } else { 1 };
        return Err(reject(format!(
            "scalar values differ at x={x}: {} versus {}",
            first.0.wrapping_mul(x).wrapping_add(first.1),
            second.0.wrapping_mul(x).wrapping_add(second.1)
        )));
    }
    Ok(())
}
