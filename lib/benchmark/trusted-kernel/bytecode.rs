use super::{reject, unsupported, Result};

#[derive(Clone, Copy, Debug)]
pub enum Test {
    Eq,
    Ne,
    Lt,
    Ge,
    Gt,
    Le,
}
impl Test {
    pub fn value(self, relation: std::cmp::Ordering) -> bool {
        use std::cmp::Ordering::*;
        match self {
            Self::Eq => relation == Equal,
            Self::Ne => relation != Equal,
            Self::Lt => relation == Less,
            Self::Ge => relation != Less,
            Self::Gt => relation == Greater,
            Self::Le => relation != Greater,
        }
    }
}
#[derive(Clone, Copy, Debug)]
pub enum Op {
    Nop,
    Const(i32),
    Load(usize),
    Store(usize),
    Length,
    Read,
    Write,
    Add,
    Inc(usize, i32),
    If(Test, bool, usize),
    Goto(usize),
    Call(u16),
    Return,
}
pub fn instruction(code: &[u8], pc: usize) -> Result<(Op, usize)> {
    use Op::*;
    let byte = |i: usize| {
        code.get(pc + i)
            .copied()
            .ok_or_else(|| reject(format!("truncated instruction at {pc}")))
    };
    let short = || Ok::<_, super::Failure>(u16::from_be_bytes([byte(1)?, byte(2)?]));
    let target = || {
        let t = pc
            .checked_add_signed(short()? as i16 as isize)
            .filter(|&t| t < code.len());
        t.ok_or_else(|| reject(format!("branch target outside Code at {pc}")))
    };
    let b = byte(0)?;
    let (op, size) = match b {
        0x00 => (Nop, 1),
        0x02..=0x08 => (Const(i32::from(b) - 3), 1),
        0x10 => (Const(i32::from(byte(1)? as i8)), 2),
        0x11 => (Const(i32::from(short()? as i16)), 3),
        0x15 | 0x19 => (Load(byte(1)? as usize), 2),
        0x1a..=0x1d => (Load((b - 0x1a) as usize), 1),
        0x2a..=0x2d => (Load((b - 0x2a) as usize), 1),
        0x36 | 0x3a => (Store(byte(1)? as usize), 2),
        0x3b..=0x3e => (Store((b - 0x3b) as usize), 1),
        0x4b..=0x4e => (Store((b - 0x4b) as usize), 1),
        0xbe => (Length, 1),
        0x2e => (Read, 1),
        0x4f => (Write, 1),
        0x60 => (Add, 1),
        0x84 => (Inc(byte(1)? as usize, i32::from(byte(2)? as i8)), 3),
        0x99..=0xa4 => {
            let cond = [Test::Eq, Test::Ne, Test::Lt, Test::Ge, Test::Gt, Test::Le]
                [(b - 0x99) as usize % 6];
            (If(cond, b >= 0x9f, target()?), 3)
        }
        0xa7 => (Goto(target()?), 3),
        0xb8 => (Call(short()?), 3),
        0xac => (Return, 1),
        _ => return Err(unsupported(format!("opcode {b:#04x} at {pc}"))),
    };
    Ok((op, pc + size))
}
