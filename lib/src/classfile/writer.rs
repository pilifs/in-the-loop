//! A small class-file writer: a constant pool builder and a code assembler with labels, enough to generate
//! harness classes without a Java compiler. The classes it writes use the version 49 (Java 5) format, which needs
//! no `StackMapTable`, so the JVM verifies them by type inference and JBMC reads them as any other class.

use std::collections::HashMap;

use super::encode_modified_utf8;
use super::flags;
use super::{Cond, Kind};

/// Builds a constant pool, de-duplicating entries.
#[derive(Default)]
pub struct PoolBuilder {
    bytes: Vec<u8>,
    count: u16,
    index: HashMap<Vec<u8>, u16>,
}

impl PoolBuilder {
    pub fn new() -> PoolBuilder {
        PoolBuilder { bytes: Vec::new(), count: 1, index: HashMap::new() }
    }

    fn add(&mut self, entry: Vec<u8>, slots: u16) -> u16 {
        if let Some(&i) = self.index.get(&entry) {
            return i;
        }
        let i = self.count;
        self.bytes.extend_from_slice(&entry);
        self.index.insert(entry, i);
        self.count += slots;
        i
    }

    pub fn utf8(&mut self, s: &str) -> u16 {
        let encoded = encode_modified_utf8(s);
        let mut entry = vec![1];
        entry.extend((encoded.len() as u16).to_be_bytes());
        entry.extend(encoded);
        self.add(entry, 1)
    }

    pub fn class(&mut self, internal_name: &str) -> u16 {
        let name = self.utf8(internal_name);
        let mut entry = vec![7];
        entry.extend(name.to_be_bytes());
        self.add(entry, 1)
    }

    pub fn string(&mut self, s: &str) -> u16 {
        let utf = self.utf8(s);
        let mut entry = vec![8];
        entry.extend(utf.to_be_bytes());
        self.add(entry, 1)
    }

    pub fn integer(&mut self, v: i32) -> u16 {
        let mut entry = vec![3];
        entry.extend(v.to_be_bytes());
        self.add(entry, 1)
    }

    pub fn long(&mut self, v: i64) -> u16 {
        let mut entry = vec![5];
        entry.extend(v.to_be_bytes());
        self.add(entry, 2)
    }

    pub fn float(&mut self, v: f32) -> u16 {
        let mut entry = vec![4];
        entry.extend(v.to_bits().to_be_bytes());
        self.add(entry, 1)
    }

    pub fn double(&mut self, v: f64) -> u16 {
        let mut entry = vec![6];
        entry.extend(v.to_bits().to_be_bytes());
        self.add(entry, 2)
    }

    pub fn name_and_type(&mut self, name: &str, descriptor: &str) -> u16 {
        let n = self.utf8(name);
        let d = self.utf8(descriptor);
        let mut entry = vec![12];
        entry.extend(n.to_be_bytes());
        entry.extend(d.to_be_bytes());
        self.add(entry, 1)
    }

    pub fn field_ref(&mut self, owner: &str, name: &str, descriptor: &str) -> u16 {
        self.member(9, owner, name, descriptor)
    }

    pub fn method_ref(&mut self, owner: &str, name: &str, descriptor: &str) -> u16 {
        self.member(10, owner, name, descriptor)
    }

    pub fn interface_method_ref(&mut self, owner: &str, name: &str, descriptor: &str) -> u16 {
        self.member(11, owner, name, descriptor)
    }

    fn member(&mut self, tag: u8, owner: &str, name: &str, descriptor: &str) -> u16 {
        let c = self.class(owner);
        let nat = self.name_and_type(name, descriptor);
        let mut entry = vec![tag];
        entry.extend(c.to_be_bytes());
        entry.extend(nat.to_be_bytes());
        self.add(entry, 1)
    }

    fn finish(&self) -> Vec<u8> {
        let mut out = self.count.to_be_bytes().to_vec();
        out.extend_from_slice(&self.bytes);
        out
    }
}

/// A branch target, allocated with [`CodeBuilder::label`] and placed with [`CodeBuilder::bind`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Label(usize);

/// Assembles the bytecode of one method. Branch offsets are 16-bit; the harnesses this writes are small.
pub struct CodeBuilder {
    code: Vec<u8>,
    labels: Vec<Option<u32>>,
    fixups: Vec<(usize, Label)>,
    handlers: Vec<(Label, Label, Label, Option<u16>)>,
    pub max_stack: u16,
    pub max_locals: u16,
}

impl Default for CodeBuilder {
    fn default() -> Self {
        Self::new()
    }
}

impl CodeBuilder {
    pub fn new() -> CodeBuilder {
        CodeBuilder { code: Vec::new(), labels: Vec::new(), fixups: Vec::new(), handlers: Vec::new(), max_stack: 16, max_locals: 0 }
    }

    pub fn pc(&self) -> u32 {
        self.code.len() as u32
    }

    pub fn label(&mut self) -> Label {
        self.labels.push(None);
        Label(self.labels.len() - 1)
    }

    pub fn bind(&mut self, label: Label) {
        self.labels[label.0] = Some(self.pc());
    }

    pub fn op(&mut self, opcode: u8) {
        self.code.push(opcode);
    }

    pub fn op_u8(&mut self, opcode: u8, operand: u8) {
        self.code.push(opcode);
        self.code.push(operand);
    }

    pub fn op_u16(&mut self, opcode: u8, operand: u16) {
        self.code.push(opcode);
        self.code.extend(operand.to_be_bytes());
    }

    fn branch(&mut self, opcode: u8, target: Label) {
        self.code.push(opcode);
        self.fixups.push((self.code.len() - 1, target));
        self.code.extend([0, 0]);
    }

    pub fn goto(&mut self, target: Label) {
        self.branch(0xa7, target);
    }

    /// `if<cond>`: compare the int on the stack with zero.
    pub fn if_zero(&mut self, cond: Cond, target: Label) {
        self.branch(0x99 + cond_index(cond), target);
    }

    /// `if_icmp<cond>`.
    pub fn if_icmp(&mut self, cond: Cond, target: Label) {
        self.branch(0x9f + cond_index(cond), target);
    }

    /// `if_acmpne`: the two references on the stack are not the same object.
    pub fn if_acmpne(&mut self, target: Label) {
        self.branch(0xa6, target);
    }

    pub fn if_null(&mut self, target: Label) {
        self.branch(0xc6, target);
    }

    pub fn if_nonnull(&mut self, target: Label) {
        self.branch(0xc7, target);
    }

    pub fn iconst(&mut self, v: i32) {
        match v {
            -1..=5 => self.op((v + 3) as u8),
            -128..=127 => self.op_u8(0x10, v as i8 as u8),
            -32768..=32767 => self.op_u16(0x11, v as i16 as u16),
            _ => unreachable!("use ldc for large int constants"),
        }
    }

    pub fn ldc(&mut self, index: u16) {
        if index < 256 {
            self.op_u8(0x12, index as u8);
        } else {
            self.op_u16(0x13, index);
        }
    }

    pub fn ldc2(&mut self, index: u16) {
        self.op_u16(0x14, index);
    }

    pub fn load(&mut self, kind: Kind, slot: u16) {
        let base = match kind {
            Kind::Int => 0x15,
            Kind::Long => 0x16,
            Kind::Float => 0x17,
            Kind::Double => 0x18,
            Kind::Ref => 0x19,
        };
        self.local(base, slot);
        let needed = slot + if matches!(kind, Kind::Long | Kind::Double) { 2 } else { 1 };
        self.max_locals = self.max_locals.max(needed);
    }

    pub fn store(&mut self, kind: Kind, slot: u16) {
        let base = match kind {
            Kind::Int => 0x36,
            Kind::Long => 0x37,
            Kind::Float => 0x38,
            Kind::Double => 0x39,
            Kind::Ref => 0x3a,
        };
        self.local(base, slot);
        let needed = slot + if matches!(kind, Kind::Long | Kind::Double) { 2 } else { 1 };
        self.max_locals = self.max_locals.max(needed);
    }

    fn local(&mut self, opcode: u8, slot: u16) {
        if slot > 255 {
            self.op(0xc4);
            self.op_u16(opcode, slot);
        } else {
            self.op_u8(opcode, slot as u8);
        }
    }

    /// `iinc`: adds `delta` to the int in `slot`.
    pub fn iinc(&mut self, slot: u16, delta: i8) {
        if slot > 255 {
            self.op(0xc4);
            self.op_u16(0x84, slot);
            self.code.extend((delta as i16).to_be_bytes());
        } else {
            self.op_u8(0x84, slot as u8);
            self.code.push(delta as u8);
        }
        self.max_locals = self.max_locals.max(slot + 1);
    }

    pub fn return_(&mut self, kind: Option<Kind>) {
        self.op(match kind {
            None => 0xb1,
            Some(Kind::Int) => 0xac,
            Some(Kind::Long) => 0xad,
            Some(Kind::Float) => 0xae,
            Some(Kind::Double) => 0xaf,
            Some(Kind::Ref) => 0xb0,
        });
    }

    /// Registers an exception handler covering `[start, end)`; `catch_type` is a `Class` pool index, or `None`
    /// for any throwable.
    pub fn handler(&mut self, start: Label, end: Label, handler: Label, catch_type: Option<u16>) {
        self.handlers.push((start, end, handler, catch_type));
    }

    fn resolve(&self, label: Label) -> u32 {
        self.labels[label.0].expect("label bound")
    }

    /// The `Code` attribute body: max_stack, max_locals, code, exception table, no attributes.
    fn finish(mut self) -> Vec<u8> {
        for (at, label) in self.fixups.clone() {
            let target = self.resolve(label) as i64 - at as i64;
            let offset = i16::try_from(target).expect("branch within 16 bits");
            self.code[at + 1..at + 3].copy_from_slice(&offset.to_be_bytes());
        }
        let mut out = Vec::new();
        out.extend(self.max_stack.to_be_bytes());
        out.extend(self.max_locals.to_be_bytes());
        out.extend((self.code.len() as u32).to_be_bytes());
        out.extend_from_slice(&self.code);
        out.extend((self.handlers.len() as u16).to_be_bytes());
        for (start, end, handler, catch_type) in &self.handlers {
            out.extend((self.resolve(*start) as u16).to_be_bytes());
            out.extend((self.resolve(*end) as u16).to_be_bytes());
            out.extend((self.resolve(*handler) as u16).to_be_bytes());
            out.extend(catch_type.unwrap_or(0).to_be_bytes());
        }
        out.extend(0u16.to_be_bytes()); // attributes
        out
    }
}

fn cond_index(cond: Cond) -> u8 {
    match cond {
        Cond::Eq => 0,
        Cond::Ne => 1,
        Cond::Lt => 2,
        Cond::Ge => 3,
        Cond::Gt => 4,
        Cond::Le => 5,
    }
}

/// A method being written.
pub struct MethodWriter {
    pub access: u16,
    pub name: String,
    pub descriptor: String,
    pub code: Option<CodeBuilder>,
}

/// A field being written: no initial value, so a static one starts at zero, `false` or `null`.
pub struct FieldWriter {
    pub access: u16,
    pub name: String,
    pub descriptor: String,
}

/// Writes a class with methods and fields.
pub struct ClassWriter {
    pub pool: PoolBuilder,
    pub access: u16,
    pub name: String,
    pub super_class: String,
    pub fields: Vec<FieldWriter>,
    pub methods: Vec<MethodWriter>,
    pub source_file: Option<String>,
}

impl ClassWriter {
    pub fn new(name: &str) -> ClassWriter {
        ClassWriter {
            pool: PoolBuilder::new(),
            access: flags::PUBLIC | flags::FINAL | flags::SUPER,
            name: name.to_string(),
            super_class: "java/lang/Object".to_string(),
            fields: Vec::new(),
            methods: Vec::new(),
            source_file: None,
        }
    }

    /// Adds a trivial public constructor that calls `super()`.
    pub fn default_constructor(&mut self) {
        let init = self.pool.method_ref(&self.super_class.clone(), "<init>", "()V");
        let mut code = CodeBuilder::new();
        code.load(Kind::Ref, 0);
        code.op_u16(0xb7, init);
        code.return_(None);
        code.max_stack = 1;
        self.methods.push(MethodWriter { access: flags::PUBLIC, name: "<init>".into(), descriptor: "()V".into(), code: Some(code) });
    }

    pub fn to_bytes(mut self) -> Vec<u8> {
        let this = self.pool.class(&self.name.clone());
        let superclass = self.pool.class(&self.super_class.clone());
        let code_name = self.pool.utf8("Code");
        let source = self.source_file.clone().map(|s| (self.pool.utf8("SourceFile"), self.pool.utf8(&s)));
        let mut field_names = Vec::new();
        for f in &self.fields {
            field_names.push((self.pool.utf8(&f.name), self.pool.utf8(&f.descriptor)));
        }
        let mut method_names = Vec::new();
        for m in &self.methods {
            method_names.push((self.pool.utf8(&m.name), self.pool.utf8(&m.descriptor)));
        }
        let mut out = Vec::new();
        out.extend(0xCAFE_BABEu32.to_be_bytes());
        out.extend(0u16.to_be_bytes()); // minor
        out.extend(49u16.to_be_bytes()); // major: Java 5, no StackMapTable needed
        out.extend(self.pool.finish());
        out.extend(self.access.to_be_bytes());
        out.extend(this.to_be_bytes());
        out.extend(superclass.to_be_bytes());
        out.extend(0u16.to_be_bytes()); // interfaces
        out.extend((self.fields.len() as u16).to_be_bytes());
        for (f, (name, descriptor)) in self.fields.iter().zip(field_names) {
            out.extend(f.access.to_be_bytes());
            out.extend(name.to_be_bytes());
            out.extend(descriptor.to_be_bytes());
            out.extend(0u16.to_be_bytes()); // attributes
        }
        out.extend((self.methods.len() as u16).to_be_bytes());
        for (m, (name, descriptor)) in self.methods.into_iter().zip(method_names) {
            out.extend(m.access.to_be_bytes());
            out.extend(name.to_be_bytes());
            out.extend(descriptor.to_be_bytes());
            match m.code {
                None => out.extend(0u16.to_be_bytes()),
                Some(code) => {
                    let body = code.finish();
                    out.extend(1u16.to_be_bytes());
                    out.extend(code_name.to_be_bytes());
                    out.extend((body.len() as u32).to_be_bytes());
                    out.extend(body);
                }
            }
        }
        match source {
            None => out.extend(0u16.to_be_bytes()),
            Some((attr, file)) => {
                out.extend(1u16.to_be_bytes());
                out.extend(attr.to_be_bytes());
                out.extend(2u32.to_be_bytes());
                out.extend(file.to_be_bytes());
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::ClassFile;

    #[test]
    fn writes_a_class_the_reader_accepts() {
        let mut w = ClassWriter::new("gen/Harness");
        w.default_constructor();
        let mut code = CodeBuilder::new();
        let done = code.label();
        code.load(Kind::Int, 0);
        code.if_zero(Cond::Eq, done);
        code.iconst(1);
        code.return_(Some(Kind::Int));
        code.bind(done);
        code.iconst(0);
        code.return_(Some(Kind::Int));
        w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "f".into(), descriptor: "(I)I".into(), code: Some(code) });
        let bytes = w.to_bytes();
        let class = ClassFile::parse(&bytes).unwrap();
        assert_eq!(class.name, "gen/Harness");
        assert_eq!(class.major, 49);
        let f = class.method("f", "(I)I").unwrap();
        let insns = f.code.as_ref().unwrap().instructions().unwrap();
        // iload 0 (2 bytes), ifeq (3), iconst_1 (1), ireturn (1): the label binds at pc 7.
        assert_eq!(insns[1].1, crate::classfile::Insn::If(Cond::Eq, 7));
    }
}
