//! The ordered checks and prefix writes of System.arraycopy on bounded arrays.

use super::*;

pub(super) fn is_call(owner: &str, name: &str, descriptor: &str) -> bool {
    (owner, name, descriptor) == ("java/lang/System", "arraycopy", "(Ljava/lang/Object;ILjava/lang/Object;II)V")
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::tests::{harness, run};

    #[test]
    fn bounds_and_component_checks_precede_only_the_writes_the_jvm_has_not_made() {
        let cp = harness("()V", |code, w, fail| {
            let object = w.pool.class("java/lang/Object");
            let string = w.pool.class("java/lang/String");
            let store = w.pool.class("java/lang/ArrayStoreException");
            let copy = w.pool.method_ref("java/lang/System", "arraycopy", "(Ljava/lang/Object;ILjava/lang/Object;II)V");
            let boxed = w.pool.method_ref("java/lang/Integer", "valueOf", "(I)Ljava/lang/Integer;");
            let a = w.pool.string("A");
            code.iconst(2); code.op_u16(0xbd, object); code.store(Kind::Ref, 0);
            code.iconst(2); code.op_u16(0xbd, string); code.store(Kind::Ref, 1);
            code.load(Kind::Ref, 0); code.iconst(0); code.ldc(a); code.op(0x53);
            code.load(Kind::Ref, 0); code.iconst(1); code.iconst(1); code.op_u16(0xb8, boxed); code.op(0x53);
            let (start, end, caught) = (code.label(), code.label(), code.label());
            code.bind(start);
            code.load(Kind::Ref, 0); code.iconst(0); code.load(Kind::Ref, 1); code.iconst(0); code.iconst(2);
            code.op_u16(0xb8, copy);
            code.bind(end); code.goto(fail);
            code.bind(caught); code.op(0x57);
            code.load(Kind::Ref, 1); code.iconst(0); code.op(0x32); code.ldc(a); code.if_acmpne(fail);
            code.load(Kind::Ref, 1); code.iconst(1); code.op(0x32); code.if_nonnull(fail);
            code.handler(start,end,caught,Some(store));
        });
        assert_eq!(run(&cp).verdict, Verdict::Verified);
    }
}

impl Engine<'_> {
    /// Only the pinned public put overloads reach this helper, after their original
    /// identity, read-only, cursor and bounds checks. They update the cursors on return.
    pub(super) fn heap_byte_buffer_copy(&mut self, path: &mut Path, start: usize) -> Step {
        let args = &path.frames.last().expect("a frame").stack[start..];
        let [Val::R(Some(dst)), Val::I(dst_pos), Val::R(Some(src)), Val::I(src_pos), Val::I(len)] = args else {
            return unsupported("heap ByteBuffer transfer requires two bound buffers");
        };
        let backing = |o: usize| {
            let b = &path.objects[o];
            if b.assumed || b.unknown || b.given || !matches!(b.fields.get("segment"), None | Some(Val::R(None))) {
                return None;
            }
            let Some(Val::R(Some(array))) = b.fields.get("hb") else { return None };
            let offset = match b.fields.get("offset") {
                None => 0,
                Some(Val::I(offset)) => self.b.constant_value(offset)?,
                _ => return None,
            };
            let data = path.objects[*array].as_array()?;
            (data.element == Type::Byte && !path.objects[*array].assumed && offset >= 0)
                .then_some((*array, offset, data.cells.len(), data.length.clone()))
        };
        if path.objects[*dst].class != "java/nio/HeapByteBuffer"
            || !matches!(path.objects[*src].class.as_str(), "java/nio/HeapByteBuffer" | "java/nio/HeapByteBufferR") {
            return unsupported("ByteBuffer transfer requires ordinary heap storage");
        }
        let (Some((src, src_base, src_cap, src_len)), Some((dst, dst_base, dst_cap, dst_len))) =
            (backing(*src), backing(*dst)) else { return unsupported("unbound heap ByteBuffer storage or session") };
        // Split on the public call's stack. A resumed path must still have buffer arguments.
        let symbolic = [(3, src_pos, src_cap), (1, dst_pos, dst_cap), (4, len, src_cap.min(dst_cap))]
            .into_iter().find(|(_, value, _)| self.b.constant_value(value).is_none())
            .map(|(slot, value, cap)| (start + slot, value.clone(), cap + 1));
        if let Some((slot, value, limit)) = symbolic {
            return self.split_index(path, value, slot, limit);
        }
        let from = src_base + self.b.constant_value(src_pos).unwrap();
        let into = dst_base + self.b.constant_value(dst_pos).unwrap();
        let count = self.b.constant_value(len).unwrap();
        if from < 0 || into < 0 || count < 0 || from + count > src_cap as i64 || into + count > dst_cap as i64 {
            return unsupported("heap ByteBuffer range outside the bound backing arrays");
        }
        let end_src = self.b.constant(from + count, 32);
        let end_dst = self.b.constant(into + count, 32);
        let short_src = self.b.ult(&src_len, &end_src);
        let short_dst = self.b.ult(&dst_len, &end_dst);
        let outside = self.b.or(short_src, short_dst);
        if !matches!(self.sides(path, outside)?, Sides::Else) {
            return unsupported("heap ByteBuffer transfer lacks valid backing-array ranges");
        }
        // Arraycopy can now finish in this instruction. Its snapshot handles overlap
        // and its ordinary read/write checks keep the caller's mutable-heap boundary.
        if outside != FALSE { path.cond.push(-outside); }
        let frame = path.frames.last_mut().expect("a frame");
        frame.stack.truncate(start);
        frame.stack.extend([Val::R(Some(src)), Val::I(self.b.constant(from,32)), Val::R(Some(dst)),
                            Val::I(self.b.constant(into,32)), Val::I(self.b.constant(count,32))]);
        self.array_copy(path)
    }

    pub(super) fn array_copy(&mut self, path: &mut Path) -> Step {
        for depth in [4, 2] {
            if let Some(step) = self.concrete_ref(path, depth) { return step; }
        }
        let stack = &path.frames.last().expect("a frame").stack;
        let start = stack.len().checked_sub(5).ok_or_else(|| Stop::Unsupported("arraycopy arguments".into()))?;
        let [Val::R(src), Val::I(src_pos), Val::R(dst), Val::I(dst_pos), Val::I(len)] = &stack[start..] else {
            return unsupported("invalid arraycopy arguments");
        };
        let (Some(src), Some(dst)) = (*src, *dst) else { return self.raise(path, "java/lang/NullPointerException") };
        if path.objects[src].assumed || path.objects[dst].assumed {
            return unsupported("arraycopy with an unknown runtime array type");
        }
        if !path.objects[src].is_array() || !path.objects[dst].is_array() {
            return self.raise(path, "java/lang/ArrayStoreException");
        }
        let (Some(source), Some(dest)) = (path.objects[src].as_array(), path.objects[dst].as_array()) else {
            return unsupported("arraycopy of summarized array cells");
        };
        if source.element != dest.element && !(holds_references(&source.element) && holds_references(&dest.element)) {
            return self.raise(path, "java/lang/ArrayStoreException");
        }
        let src_capacity = source.refs.len().max(source.cells.len());
        let dst_capacity = dest.refs.len().max(dest.cells.len());
        let symbolic = [(1, src_pos, src_capacity), (3, dst_pos, dst_capacity), (4, len, src_capacity.min(dst_capacity))]
            .into_iter().find(|(_, value, _)| self.b.constant_value(value).is_none())
            .map(|(slot, value, limit)| (start + slot, value.clone(), limit + 1));
        if let Some((slot, value, limit)) = symbolic {
            return self.split_index(path, value, slot, limit);
        }
        let source_index = self.b.constant_value(src_pos).expect("concrete index");
        let dest_index = self.b.constant_value(dst_pos).expect("concrete index");
        let length = self.b.constant_value(len).expect("concrete length");
        if source_index < 0 || dest_index < 0 || length < 0 || source_index + length > src_capacity as i64 || dest_index + length > dst_capacity as i64 {
            return self.raise(path, "java/lang/ArrayIndexOutOfBoundsException");
        }
        let end_src = self.b.constant(source_index + length, 32);
        let end_dst = self.b.constant(dest_index + length, 32);
        let short_src = self.b.ult(&source.length, &end_src);
        let short_dst = self.b.ult(&dest.length, &end_dst);
        let outside = self.b.or(short_src, short_dst);
        if outside != FALSE && !path.cond.contains(&-outside) {
            // Leave all arguments in place. A valid path re-enters after recording its bounds check.
            return self.branch_throw_or(path, outside, "java/lang/ArrayIndexOutOfBoundsException", |_, valid| valid.resumed = true);
        }
        let (from, into, count) = (source_index as usize, dest_index as usize, length as usize);
        let mut copied = count;
        if holds_references(&source.element) {
            let target = class_of(&dest.element);
            for (i, cell) in source.refs[from..from + count].iter().enumerate() {
                let options = cell.options().expect("a reference array");
                let mut compatible = false;
                let mut incompatible = false;
                for (_, object) in options {
                    if let Some(o) = object.filter(|o| !path.objects[*o].is_instance(self.cp, &target)) {
                        if path.objects[o].assumed { return self.of_unknown_class(path, o, "an arraycopy component check"); }
                        incompatible = true;
                    } else {
                        compatible = true;
                    }
                }
                if incompatible && compatible {
                    let Val::C(choice) = cell else { unreachable!("mixed reference types require a choice") };
                    return self.split_choice(path, &choice.clone());
                }
                if incompatible {
                    copied = i;
                    break;
                }
            }
        }
        if count != 0 && self.there_before(path, src) {
            self.reads(path, || "arraycopy reads an array that existed before the call".into())?;
        }
        if copied != 0 {
            self.keeps(path, Some(dst), "arraycopy writes a destination that existed before the call")?;
            if holds_references(&source.element) {
                let values = source.refs[from..from + copied].to_vec();
                path.objects[dst].array.as_mut().unwrap().refs[into..into + copied].clone_from_slice(&values);
            } else {
                let values = source.cells[from..from + copied].to_vec();
                path.objects[dst].array.as_mut().unwrap().cells[into..into + copied].clone_from_slice(&values);
            }
        }
        path.frames.last_mut().expect("a frame").stack.truncate(start);
        if copied != count { return self.raise(path, "java/lang/ArrayStoreException"); }
        self.advance(path);
        Ok(None)
    }
}
