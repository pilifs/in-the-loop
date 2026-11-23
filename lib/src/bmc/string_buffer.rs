//! The JDK StringBuffer range append called by StringWriter.write(String,off,len).
//! Read and write the real backing byte array. A compact buffer accepts a Latin-1
//! range even if its source also contains wide units elsewhere. The original JDK
//! methods handle the lock and invalidate or reuse the toString cache.

use super::*;
use crate::classfile::MemberRef;

const BUFFER: &str = "java/lang/StringBuffer";
const BASE: &str = "java/lang/AbstractStringBuilder";

impl Engine<'_> {
    pub(super) fn string_buffer_copy(&mut self, path: &mut Path, o: usize, m: &MemberRef, args: &[Val]) -> Option<Step> {
        let (buffer, snapshot) = match (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str(), args) {
            (BASE, "append", "(Ljava/lang/CharSequence;II)Ljava/lang/AbstractStringBuilder;" |
                "(Ljava/lang/String;)Ljava/lang/AbstractStringBuilder;", _) => (o, false),
            (STRING, "<init>", "(Ljava/lang/AbstractStringBuilder;Ljava/lang/Void;)V", [Val::R(Some(b)), Val::R(None)]) => (*b, true),
            _ => return None,
        };
        if let [Val::R(Some(s))] = args {
            if path.objects[*s].limit.as_deref() == Some(runtime::LINE_SEPARATOR) {
                if let Err(stop) = self.resolve_separator(path, *s) { return Some(Err(stop)); }
                if path.objects[*s].content().is_none() { return Some(unsupported(runtime::LINE_SEPARATOR)); }
            } else if !path.literals.iter().any(|(k, id)| *id == *s && matches!(k, Literal::Str(_))) {
                return None;
            }
        }
        let obj = &path.objects[buffer];
        if obj.class != BUFFER || obj.assumed || obj.unknown { return None; }
        let big_endian = self.cp.string_buffer_byte_order()?;
        let Val::R(Some(storage)) = *obj.fields.get("value")? else { return None };
        let field = |name| match obj.fields.get(name) {
            Some(Val::I(w)) => usize::try_from(self.b.constant_value(w)?).ok(),
            None => Some(0),
            _ => None,
        };
        let coder = field("coder")?;
        let count = field("count")?;
        let array = path.objects[storage].as_array()?;
        if coder > 1 || array.element != Type::Byte || self.b.constant_value(&array.length)? != array.cells.len() as i64 { return None; }
        let width = 1 << coder;
        let capacity = array.cells.len() / width;
        if count > capacity || capacity > strings::MOST_BUILDER_CONTENT { return None; }
        if self.there_before(path, buffer) || self.there_before(path, storage) {
            if let Err(stop) = self.reads(path, || "reads the StringBuffer and its backing bytes".into()) { return Some(Err(stop)); }
        }
        if snapshot {
            let cells = array.cells[..count * width].chunks_exact(width).map(|bytes| {
                if width == 1 { return self.b.zext(&bytes[0], 16); }
                let [lo, hi] = if big_endian { [&bytes[1], &bytes[0]] } else { [&bytes[0], &bytes[1]] };
                [lo.as_slice(), hi.as_slice()].concat()
            }).collect();
            if let Err(stop) = self.keeps(path, Some(o), "initializes a String from a StringBuffer") { return Some(Err(stop)); }
            path.objects[o].array = Some(Array { element: Type::Char, length: self.b.constant(count as i64, 32), cells, refs: vec![] });
        } else {
            let Val::R(source) = args.first()? else { return None };
            let units = match source {
                Some(s) if path.objects[*s].class == STRING => self.constant_units(path, *s)?,
                None => "null".encode_utf16().collect(),
                _ => return None,
            };
            let (start, end) = match args {
                [_] => (0, units.len()),
                [_, Val::I(start), Val::I(end)] => (usize::try_from(self.b.constant_value(start)?).ok()?,
                    usize::try_from(self.b.constant_value(end)?).ok()?),
                _ => return None,
            };
            let range = units.get(start..end)?;
            if coder == 0 && range.iter().any(|&unit| unit > 255) { return None; }
            let needed = count.checked_add(range.len())?;
            if needed > strings::MOST_BUILDER_CONTENT { return None; }
            let mut data = array.clone();
            if let Err(stop) = self.keeps(path, Some(buffer), "appends a character range to a StringBuffer") { return Some(Err(stop)); }
            let dest = if needed > capacity {
                // In this bounded range ArraysSupport.newLength takes max(minimum, preferred growth).
                let bytes = needed.max(2 * capacity + 2) * width;
                data.length = self.b.constant(bytes as i64, 32);
                if let Err(stop) = self.new_array_cells(path, &data.length) { return Some(Err(stop)); }
                data.cells.resize(bytes, self.b.constant(0, 8));
                let fresh = self.alloc(path, "[B");
                path.objects[buffer].fields.insert("value".into(), Val::R(Some(fresh)));
                fresh
            } else {
                if let Err(stop) = self.keeps(path, Some(storage), "writes the StringBuffer backing array") { return Some(Err(stop)); }
                storage
            };
            for (&unit, cells) in range.iter().zip(data.cells[count * width..].chunks_exact_mut(width)) {
                let bytes = if big_endian && width == 2 { unit.to_be_bytes() } else { unit.to_le_bytes() };
                for (cell, byte) in cells.iter_mut().zip(bytes) { *cell = self.b.constant(i64::from(byte), 8); }
            }
            path.objects[dest].array = Some(data);
            path.objects[buffer].fields.insert("count".into(), Val::I(self.b.constant(needed as i64, 32)));
            self.push(path, Val::R(Some(buffer)));
        }
        self.advance(path);
        Some(Ok(None))
    }
}
