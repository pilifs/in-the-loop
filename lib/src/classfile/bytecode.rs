//! The JVM instruction set (JVMS chapter 6), decoded into a compact enum. Branch targets are absolute pcs.

use super::{err, Result};

/// A computational type category, for loads, stores, returns and arithmetic.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Kind {
    Int,
    Long,
    Float,
    Double,
    Ref,
}

/// The element kind of an array access instruction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ArrayKind {
    Int,
    Long,
    Float,
    Double,
    Ref,
    /// `baload`/`bastore`: boolean or byte arrays.
    Byte,
    Char,
    Short,
}

/// A comparison condition, for `if<cond>` and `if_icmp<cond>`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Cond {
    Eq,
    Ne,
    Lt,
    Ge,
    Gt,
    Le,
}

impl Cond {
    pub fn holds(self, ordering: std::cmp::Ordering) -> bool {
        use std::cmp::Ordering::*;
        match self {
            Cond::Eq => ordering == Equal,
            Cond::Ne => ordering != Equal,
            Cond::Lt => ordering == Less,
            Cond::Ge => ordering != Less,
            Cond::Gt => ordering == Greater,
            Cond::Le => ordering != Greater,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ArithOp {
    Add,
    Sub,
    Mul,
    Div,
    Rem,
    Neg,
    Shl,
    Shr,
    Ushr,
    And,
    Or,
    Xor,
}

/// `lcmp`, `fcmpl`, `fcmpg`, `dcmpl`, `dcmpg`: the `nan` field says what a NaN compares as (`-1` or `1`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct CmpOp {
    pub kind: Kind,
    pub nan: i32,
}

/// One instruction. `pc`-relative operands have been resolved to absolute targets.
#[derive(Debug, Clone, PartialEq)]
pub enum Insn {
    Nop,
    AConstNull,
    IConst(i32),
    LConst(i64),
    FConst(f32),
    DConst(f64),
    /// `ldc`, `ldc_w`, `ldc2_w`: a constant pool index.
    Ldc(u16),
    Load(Kind, u16),
    Store(Kind, u16),
    ArrayLoad(ArrayKind),
    ArrayStore(ArrayKind),
    Pop,
    Pop2,
    Dup,
    DupX1,
    DupX2,
    Dup2,
    Dup2X1,
    Dup2X2,
    Swap,
    Arith(ArithOp, Kind),
    IInc(u16, i16),
    /// `i2l`, `f2d`, ...: from, to. Narrowing conversions `i2b`, `i2c`, `i2s` use `To::Byte` etc.
    Convert(Kind, Narrow),
    Cmp(CmpOp),
    /// `ifeq` ... `ifle`: compare an int with zero, branch to the target.
    If(Cond, u32),
    IfICmp(Cond, u32),
    /// `if_acmpeq` (true) or `if_acmpne` (false).
    IfACmp(bool, u32),
    IfNull(u32),
    IfNonNull(u32),
    Goto(u32),
    Jsr(u32),
    Ret(u16),
    TableSwitch { default: u32, low: i32, high: i32, targets: Vec<u32> },
    LookupSwitch { default: u32, pairs: Vec<(i32, u32)> },
    Return(Option<Kind>),
    GetStatic(u16),
    PutStatic(u16),
    GetField(u16),
    PutField(u16),
    InvokeVirtual(u16),
    InvokeSpecial(u16),
    InvokeStatic(u16),
    InvokeInterface(u16),
    InvokeDynamic(u16),
    New(u16),
    /// `newarray` with the primitive element type.
    NewArray(ArrayKind),
    ANewArray(u16),
    ArrayLength,
    AThrow,
    CheckCast(u16),
    InstanceOf(u16),
    MonitorEnter,
    MonitorExit,
    MultiANewArray(u16, u8),
}

/// The target of a conversion: a computational type, or a narrowing to byte, char or short (an int result).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Narrow {
    To(Kind),
    Byte,
    Char,
    Short,
}

impl Insn {
    /// Whether this is an invoke instruction, with its constant pool index.
    pub fn invoke_index(&self) -> Option<u16> {
        match self {
            Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => Some(*i),
            _ => None,
        }
    }

    /// Branch targets, for control-flow analyses.
    pub fn targets(&self) -> Vec<u32> {
        match self {
            Insn::If(_, t) | Insn::IfICmp(_, t) | Insn::IfACmp(_, t) | Insn::IfNull(t) | Insn::IfNonNull(t) | Insn::Goto(t) | Insn::Jsr(t) => vec![*t],
            Insn::TableSwitch { default, targets, .. } => {
                let mut v = vec![*default];
                v.extend(targets);
                v
            }
            Insn::LookupSwitch { default, pairs } => {
                let mut v = vec![*default];
                v.extend(pairs.iter().map(|p| p.1));
                v
            }
            _ => Vec::new(),
        }
    }
}

struct Cursor<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl Cursor<'_> {
    fn u8(&mut self) -> Result<u8> {
        let b = *self.bytes.get(self.pos).ok_or_else(|| super::ParseError("truncated instruction".into()))?;
        self.pos += 1;
        Ok(b)
    }
    fn i8(&mut self) -> Result<i8> {
        Ok(self.u8()? as i8)
    }
    fn u16(&mut self) -> Result<u16> {
        Ok(u16::from_be_bytes([self.u8()?, self.u8()?]))
    }
    fn i16(&mut self) -> Result<i16> {
        Ok(self.u16()? as i16)
    }
    fn i32(&mut self) -> Result<i32> {
        Ok(i32::from_be_bytes([self.u8()?, self.u8()?, self.u8()?, self.u8()?]))
    }
}

fn target(pc: usize, offset: i32) -> Result<u32> {
    let t = pc as i64 + offset as i64;
    if t < 0 || t > u32::MAX as i64 {
        return err(format!("branch target {t} out of range"));
    }
    Ok(t as u32)
}

/// Decodes a method's bytecode into `(pc, instruction)` pairs.
pub fn decode(code: &[u8]) -> Result<Vec<(u32, Insn)>> {
    let mut c = Cursor { bytes: code, pos: 0 };
    let mut out = Vec::new();
    while c.pos < code.len() {
        let pc = c.pos;
        let op = c.u8()?;
        let insn = match op {
            0x00 => Insn::Nop,
            0x01 => Insn::AConstNull,
            0x02..=0x08 => Insn::IConst(op as i32 - 0x03),
            0x09 | 0x0a => Insn::LConst((op - 0x09) as i64),
            0x0b..=0x0d => Insn::FConst((op - 0x0b) as f32),
            0x0e | 0x0f => Insn::DConst((op - 0x0e) as f64),
            0x10 => Insn::IConst(c.i8()? as i32),
            0x11 => Insn::IConst(c.i16()? as i32),
            0x12 => Insn::Ldc(c.u8()? as u16),
            0x13 | 0x14 => Insn::Ldc(c.u16()?),
            0x15 => Insn::Load(Kind::Int, c.u8()? as u16),
            0x16 => Insn::Load(Kind::Long, c.u8()? as u16),
            0x17 => Insn::Load(Kind::Float, c.u8()? as u16),
            0x18 => Insn::Load(Kind::Double, c.u8()? as u16),
            0x19 => Insn::Load(Kind::Ref, c.u8()? as u16),
            0x1a..=0x1d => Insn::Load(Kind::Int, (op - 0x1a) as u16),
            0x1e..=0x21 => Insn::Load(Kind::Long, (op - 0x1e) as u16),
            0x22..=0x25 => Insn::Load(Kind::Float, (op - 0x22) as u16),
            0x26..=0x29 => Insn::Load(Kind::Double, (op - 0x26) as u16),
            0x2a..=0x2d => Insn::Load(Kind::Ref, (op - 0x2a) as u16),
            0x2e => Insn::ArrayLoad(ArrayKind::Int),
            0x2f => Insn::ArrayLoad(ArrayKind::Long),
            0x30 => Insn::ArrayLoad(ArrayKind::Float),
            0x31 => Insn::ArrayLoad(ArrayKind::Double),
            0x32 => Insn::ArrayLoad(ArrayKind::Ref),
            0x33 => Insn::ArrayLoad(ArrayKind::Byte),
            0x34 => Insn::ArrayLoad(ArrayKind::Char),
            0x35 => Insn::ArrayLoad(ArrayKind::Short),
            0x36 => Insn::Store(Kind::Int, c.u8()? as u16),
            0x37 => Insn::Store(Kind::Long, c.u8()? as u16),
            0x38 => Insn::Store(Kind::Float, c.u8()? as u16),
            0x39 => Insn::Store(Kind::Double, c.u8()? as u16),
            0x3a => Insn::Store(Kind::Ref, c.u8()? as u16),
            0x3b..=0x3e => Insn::Store(Kind::Int, (op - 0x3b) as u16),
            0x3f..=0x42 => Insn::Store(Kind::Long, (op - 0x3f) as u16),
            0x43..=0x46 => Insn::Store(Kind::Float, (op - 0x43) as u16),
            0x47..=0x4a => Insn::Store(Kind::Double, (op - 0x47) as u16),
            0x4b..=0x4e => Insn::Store(Kind::Ref, (op - 0x4b) as u16),
            0x4f => Insn::ArrayStore(ArrayKind::Int),
            0x50 => Insn::ArrayStore(ArrayKind::Long),
            0x51 => Insn::ArrayStore(ArrayKind::Float),
            0x52 => Insn::ArrayStore(ArrayKind::Double),
            0x53 => Insn::ArrayStore(ArrayKind::Ref),
            0x54 => Insn::ArrayStore(ArrayKind::Byte),
            0x55 => Insn::ArrayStore(ArrayKind::Char),
            0x56 => Insn::ArrayStore(ArrayKind::Short),
            0x57 => Insn::Pop,
            0x58 => Insn::Pop2,
            0x59 => Insn::Dup,
            0x5a => Insn::DupX1,
            0x5b => Insn::DupX2,
            0x5c => Insn::Dup2,
            0x5d => Insn::Dup2X1,
            0x5e => Insn::Dup2X2,
            0x5f => Insn::Swap,
            0x60..=0x63 => Insn::Arith(ArithOp::Add, kind4(op - 0x60)),
            0x64..=0x67 => Insn::Arith(ArithOp::Sub, kind4(op - 0x64)),
            0x68..=0x6b => Insn::Arith(ArithOp::Mul, kind4(op - 0x68)),
            0x6c..=0x6f => Insn::Arith(ArithOp::Div, kind4(op - 0x6c)),
            0x70..=0x73 => Insn::Arith(ArithOp::Rem, kind4(op - 0x70)),
            0x74..=0x77 => Insn::Arith(ArithOp::Neg, kind4(op - 0x74)),
            0x78 => Insn::Arith(ArithOp::Shl, Kind::Int),
            0x79 => Insn::Arith(ArithOp::Shl, Kind::Long),
            0x7a => Insn::Arith(ArithOp::Shr, Kind::Int),
            0x7b => Insn::Arith(ArithOp::Shr, Kind::Long),
            0x7c => Insn::Arith(ArithOp::Ushr, Kind::Int),
            0x7d => Insn::Arith(ArithOp::Ushr, Kind::Long),
            0x7e => Insn::Arith(ArithOp::And, Kind::Int),
            0x7f => Insn::Arith(ArithOp::And, Kind::Long),
            0x80 => Insn::Arith(ArithOp::Or, Kind::Int),
            0x81 => Insn::Arith(ArithOp::Or, Kind::Long),
            0x82 => Insn::Arith(ArithOp::Xor, Kind::Int),
            0x83 => Insn::Arith(ArithOp::Xor, Kind::Long),
            0x84 => Insn::IInc(c.u8()? as u16, c.i8()? as i16),
            0x85 => Insn::Convert(Kind::Int, Narrow::To(Kind::Long)),
            0x86 => Insn::Convert(Kind::Int, Narrow::To(Kind::Float)),
            0x87 => Insn::Convert(Kind::Int, Narrow::To(Kind::Double)),
            0x88 => Insn::Convert(Kind::Long, Narrow::To(Kind::Int)),
            0x89 => Insn::Convert(Kind::Long, Narrow::To(Kind::Float)),
            0x8a => Insn::Convert(Kind::Long, Narrow::To(Kind::Double)),
            0x8b => Insn::Convert(Kind::Float, Narrow::To(Kind::Int)),
            0x8c => Insn::Convert(Kind::Float, Narrow::To(Kind::Long)),
            0x8d => Insn::Convert(Kind::Float, Narrow::To(Kind::Double)),
            0x8e => Insn::Convert(Kind::Double, Narrow::To(Kind::Int)),
            0x8f => Insn::Convert(Kind::Double, Narrow::To(Kind::Long)),
            0x90 => Insn::Convert(Kind::Double, Narrow::To(Kind::Float)),
            0x91 => Insn::Convert(Kind::Int, Narrow::Byte),
            0x92 => Insn::Convert(Kind::Int, Narrow::Char),
            0x93 => Insn::Convert(Kind::Int, Narrow::Short),
            0x94 => Insn::Cmp(CmpOp { kind: Kind::Long, nan: 0 }),
            0x95 => Insn::Cmp(CmpOp { kind: Kind::Float, nan: -1 }),
            0x96 => Insn::Cmp(CmpOp { kind: Kind::Float, nan: 1 }),
            0x97 => Insn::Cmp(CmpOp { kind: Kind::Double, nan: -1 }),
            0x98 => Insn::Cmp(CmpOp { kind: Kind::Double, nan: 1 }),
            0x99..=0x9e => Insn::If(cond6(op - 0x99), target(pc, c.i16()? as i32)?),
            0x9f..=0xa4 => Insn::IfICmp(cond6(op - 0x9f), target(pc, c.i16()? as i32)?),
            0xa5 => Insn::IfACmp(true, target(pc, c.i16()? as i32)?),
            0xa6 => Insn::IfACmp(false, target(pc, c.i16()? as i32)?),
            0xa7 => Insn::Goto(target(pc, c.i16()? as i32)?),
            0xa8 => Insn::Jsr(target(pc, c.i16()? as i32)?),
            0xa9 => Insn::Ret(c.u8()? as u16),
            0xaa => {
                while c.pos % 4 != 0 {
                    c.u8()?;
                }
                let default = target(pc, c.i32()?)?;
                let low = c.i32()?;
                let high = c.i32()?;
                if high < low {
                    return err("tableswitch with high < low");
                }
                let n = (high as i64 - low as i64 + 1) as usize;
                let mut targets = Vec::with_capacity(n);
                for _ in 0..n {
                    targets.push(target(pc, c.i32()?)?);
                }
                Insn::TableSwitch { default, low, high, targets }
            }
            0xab => {
                while c.pos % 4 != 0 {
                    c.u8()?;
                }
                let default = target(pc, c.i32()?)?;
                let n = c.i32()?;
                if n < 0 {
                    return err("lookupswitch with negative pair count");
                }
                let mut pairs = Vec::with_capacity(n as usize);
                for _ in 0..n {
                    let key = c.i32()?;
                    pairs.push((key, target(pc, c.i32()?)?));
                }
                Insn::LookupSwitch { default, pairs }
            }
            0xac => Insn::Return(Some(Kind::Int)),
            0xad => Insn::Return(Some(Kind::Long)),
            0xae => Insn::Return(Some(Kind::Float)),
            0xaf => Insn::Return(Some(Kind::Double)),
            0xb0 => Insn::Return(Some(Kind::Ref)),
            0xb1 => Insn::Return(None),
            0xb2 => Insn::GetStatic(c.u16()?),
            0xb3 => Insn::PutStatic(c.u16()?),
            0xb4 => Insn::GetField(c.u16()?),
            0xb5 => Insn::PutField(c.u16()?),
            0xb6 => Insn::InvokeVirtual(c.u16()?),
            0xb7 => Insn::InvokeSpecial(c.u16()?),
            0xb8 => Insn::InvokeStatic(c.u16()?),
            0xb9 => {
                let index = c.u16()?;
                c.u8()?; // count
                c.u8()?; // 0
                Insn::InvokeInterface(index)
            }
            0xba => {
                let index = c.u16()?;
                c.u16()?; // 0 0
                Insn::InvokeDynamic(index)
            }
            0xbb => Insn::New(c.u16()?),
            0xbc => Insn::NewArray(match c.u8()? {
                4 => ArrayKind::Byte, // boolean arrays are byte arrays to the instruction set
                5 => ArrayKind::Char,
                6 => ArrayKind::Float,
                7 => ArrayKind::Double,
                8 => ArrayKind::Byte,
                9 => ArrayKind::Short,
                10 => ArrayKind::Int,
                11 => ArrayKind::Long,
                other => return err(format!("bad newarray type {other}")),
            }),
            0xbd => Insn::ANewArray(c.u16()?),
            0xbe => Insn::ArrayLength,
            0xbf => Insn::AThrow,
            0xc0 => Insn::CheckCast(c.u16()?),
            0xc1 => Insn::InstanceOf(c.u16()?),
            0xc2 => Insn::MonitorEnter,
            0xc3 => Insn::MonitorExit,
            0xc4 => {
                let wide_op = c.u8()?;
                let index = c.u16()?;
                match wide_op {
                    0x15 => Insn::Load(Kind::Int, index),
                    0x16 => Insn::Load(Kind::Long, index),
                    0x17 => Insn::Load(Kind::Float, index),
                    0x18 => Insn::Load(Kind::Double, index),
                    0x19 => Insn::Load(Kind::Ref, index),
                    0x36 => Insn::Store(Kind::Int, index),
                    0x37 => Insn::Store(Kind::Long, index),
                    0x38 => Insn::Store(Kind::Float, index),
                    0x39 => Insn::Store(Kind::Double, index),
                    0x3a => Insn::Store(Kind::Ref, index),
                    0xa9 => Insn::Ret(index),
                    0x84 => Insn::IInc(index, c.i16()?),
                    other => return err(format!("bad wide opcode {other:#x}")),
                }
            }
            0xc5 => Insn::MultiANewArray(c.u16()?, c.u8()?),
            0xc6 => Insn::IfNull(target(pc, c.i16()? as i32)?),
            0xc7 => Insn::IfNonNull(target(pc, c.i16()? as i32)?),
            0xc8 => Insn::Goto(target(pc, c.i32()?)?),
            0xc9 => Insn::Jsr(target(pc, c.i32()?)?),
            other => return err(format!("unknown opcode {other:#x} at pc {pc}")),
        };
        out.push((pc as u32, insn));
    }
    Ok(out)
}

fn kind4(i: u8) -> Kind {
    match i {
        0 => Kind::Int,
        1 => Kind::Long,
        2 => Kind::Float,
        _ => Kind::Double,
    }
}

fn cond6(i: u8) -> Cond {
    match i {
        0 => Cond::Eq,
        1 => Cond::Ne,
        2 => Cond::Lt,
        3 => Cond::Ge,
        4 => Cond::Gt,
        _ => Cond::Le,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decodes_branches_and_switches() {
        // iload_0; ifeq +5 (to pc 6); iconst_1; ireturn; nop; iconst_0; ireturn
        let code = [0x1a, 0x99, 0x00, 0x05, 0x04, 0xac, 0x00, 0x03, 0xac];
        let insns = decode(&code).unwrap();
        assert_eq!(insns[1], (1, Insn::If(Cond::Eq, 6)));
        assert_eq!(insns[2], (4, Insn::IConst(1)));
        // tableswitch at pc 1 with padding: iconst_0 at pc 0, then aa, 2 pad bytes, default, low=1, high=2, 2 targets
        let mut code = vec![0x03, 0xaa, 0, 0];
        for v in [10i32, 1, 2, 20, 30] {
            code.extend(v.to_be_bytes());
        }
        let insns = decode(&code).unwrap();
        assert_eq!(insns[1], (1, Insn::TableSwitch { default: 11, low: 1, high: 2, targets: vec![21, 31] }));
    }
}
