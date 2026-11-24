//! Plain, unaligned VarHandle accesses on a byte array on the bound OpenJDK image.
//! The value holds only its view type and byte order. Object identity, access-mode adaptation
//! and atomic operations cannot be inferred from this representation.
use super::*;
use crate::classfile::MemberRef;

pub(super) const HANDLES: &str = "java/lang/invoke/MethodHandles";
pub(super) const FACTORY: &str = "(Ljava/lang/Class;Ljava/nio/ByteOrder;)Ljava/lang/invoke/VarHandle;";
pub(super) const HANDLE: &str = "java/lang/invoke/VarHandle";
const ORDER: &str = "java/nio/ByteOrder";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct ByteView {
    component: u8,
    little: bool,
}

impl Engine<'_> {
    pub(super) fn byte_view_factory(&mut self, path: &mut Path, args: &[Val]) -> Step {
        let [Val::R(Some(class)), Val::R(Some(order))] = args else {
            return unsupported("byteArrayViewVarHandle requires a bound array class and byte order");
        };
        let mirror = self.class_named(path, *class);
        let Some([b'[', component @ (b'S' | b'C' | b'I' | b'J' | b'F' | b'D')]) = mirror.as_deref().map(str::as_bytes) else {
            return unsupported("byteArrayViewVarHandle requires a supported primitive view array class");
        };
        let is_order = |field: &str| matches!(path.statics.get(&(ORDER.into(), field.into())), Some(Val::R(Some(o))) if o == order);
        let little = match (is_order("LITTLE_ENDIAN"), is_order("BIG_ENDIAN")) {
            (true, false) => true,
            (false, true) => false,
            _ => return unsupported("byte-array view order is not a bound ByteOrder singleton"),
        };
        self.push(path, Val::ByteView(ByteView { component: *component, little }));
        self.advance(path);
        Ok(None)
    }

    pub(super) fn byte_view_access(&mut self, path: &mut Path, view: ByteView, m: &MemberRef, start: usize, special: bool) -> Step {
        let (load, width, read_desc, write_desc) = match view.component {
            b'S' => (ArrayKind::Short, 2, "([BI)S", "([BIS)V"),
            b'C' => (ArrayKind::Char, 2, "([BI)C", "([BIC)V"),
            b'I' => (ArrayKind::Int, 4, "([BI)I", "([BII)V"),
            b'J' => (ArrayKind::Long, 8, "([BI)J", "([BIJ)V"),
            _ => return unsupported("a floating-point byte-array view access"),
        };
        let write = match (m.name.as_str(), m.descriptor.as_str()) {
            ("get", d) if d == read_desc => false,
            ("set", d) if d == write_desc => true,
            _ => return unsupported(format!("unsupported byte-array VarHandle access {}{}", m.name, m.descriptor)),
        };
        if special || m.owner != HANDLE {
            return unsupported("a call outside the plain byte-array VarHandle access methods");
        }
        if let Some(step) = self.concrete_ref(path, if write { 2 } else { 1 }) {
            return step;
        }
        let stack = &path.frames.last().expect("a frame").stack;
        let (Val::R(o), Val::I(index)) = (&stack[start + 1], &stack[start + 2]) else {
            return unsupported("byte-array VarHandle requires byte[] and int coordinates");
        };
        let Some(o) = *o else { return self.raise(path, "java/lang/NullPointerException") };
        let Some(array) = path.objects[o].as_array().filter(|a| a.element == Type::Byte) else {
            return unsupported("byte-array VarHandle needs concrete byte-array storage");
        };
        if path.probing.is_some() || path.loose {
            return unsupported("a byte-array VarHandle access inside a loop summary");
        }
        let cells = array.cells.len();
        let length = array.length.clone();
        let Some(i) = self.b.constant_value(index) else {
            // split_index resumes this instruction with the chosen offset still on the stack.
            let starts = cells.checked_sub(width).map_or(0, |last| last + 1);
            return self.split_index(path, index.clone(), start + 2, starts);
        };
        let Some(i) = usize::try_from(i).ok().filter(|i| i.checked_add(width).is_some_and(|end| end <= cells)) else {
            return self.raise(path, "java/lang/ArrayIndexOutOfBoundsException");
        };
        let stored = if write {
            self.keeps(path, Some(o), "writes a byte-array view of an existing array")?;
            match (&stack[start + 3], load) {
                (Val::J(bits), ArrayKind::Long) => Some(bits.clone()),
                (Val::I(bits), ArrayKind::Short | ArrayKind::Char | ArrayKind::Int) => Some(bits.clone()),
                _ => return unsupported("incorrect byte-array view store operand"),
            }
        } else {
            if self.there_before(path, o) { self.reads(path, || "reads a byte-array view of an existing array".into())?; }
            None
        };
        let end = self.b.constant((i + width) as i64, 32);
        let short = self.b.ult(&length, &end);
        path.frames.last_mut().expect("a frame").stack.truncate(start);
        self.branch_throw_or(path, short, "java/lang/ArrayIndexOutOfBoundsException", |engine, path| {
            let cells = &mut path.objects[o].array.as_mut().expect("bound byte array").cells[i..i + width];
            let mut read = Vec::with_capacity(width * 8);
            for j in 0..width {
                let cell = &mut cells[if view.little { j } else { width - 1 - j }];
                if let Some(bits) = &stored {
                    cell.copy_from_slice(&bits[8*j..8*j+8]);
                } else {
                    read.extend_from_slice(cell);
                }
            }
            if !write {
                let v = match load {
                    ArrayKind::Short => Val::I(engine.b.sext(&read, 32)),
                    ArrayKind::Char => Val::I(engine.b.zext(&read, 32)),
                    ArrayKind::Long => Val::J(read),
                    _ => Val::I(read),
                };
                engine.push(path, v);
            }
            engine.advance(path);
        })
    }
}
