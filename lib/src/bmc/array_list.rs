//! Bounded ArrayList objects constructed by the check. Execute the selected JDK's list
//! methods, including its actual growth policy, array stores and typed toArray. An
//! explicit list model or a gap contract keeps its existing dispatch. An opaque receiver
//! or an unbounded capacity cannot establish a fact about the list's fields.

use super::*;

const LIST: &str = "java/util/ArrayList";
pub(super) const OBJECT_ARRAY: &str = "[Ljava/lang/Object;";

/// Both private storage sentinels must be freshly allocated Object[0]s in the image.
/// One selects default growth, the other growth from an explicitly empty capacity.
pub(super) fn empty_storage(cp: &ClassPath, member: &crate::classfile::MemberRef) -> Option<bool> {
    if member.owner != LIST || member.descriptor != OBJECT_ARRAY { return None; }
    let default = match member.name.as_str() {
        "DEFAULTCAPACITY_EMPTY_ELEMENTDATA" => true,
        "EMPTY_ELEMENTDATA" => false,
        _ => return None,
    };
    let cf = cp.load(LIST).ok()??.class;
    let code = cf.method("<clinit>", "()V")?.code.as_ref()?;
    let insns = code.instructions().ok()?;
    let [(_, Insn::IConst(0)), (_, Insn::ANewArray(a)), (_, Insn::PutStatic(x)),
         (_, Insn::IConst(0)), (_, Insn::ANewArray(b)), (_, Insn::PutStatic(y)), (_, Insn::Return(None))] = insns.as_slice() else { return None };
    let x = cf.pool.member(*x).ok()?;
    let y = cf.pool.member(*y).ok()?;
    (code.exception_table.is_empty() && cf.pool.class_name(*a).ok()? == "java/lang/Object" && cf.pool.class_name(*b).ok()? == "java/lang/Object"
        && [x.owner.as_str(), y.owner.as_str()] == [LIST, LIST] && [x.descriptor.as_str(), y.descriptor.as_str()] == [OBJECT_ARRAY, OBJECT_ARRAY]
        && [x.name.as_str(), y.name.as_str()].contains(&"EMPTY_ELEMENTDATA") && [x.name.as_str(), y.name.as_str()].contains(&"DEFAULTCAPACITY_EMPTY_ELEMENTDATA")).then_some(default)
}

impl Engine<'_> {
    pub(super) fn image_list_call(&mut self, path: &mut Path, o: usize, special: bool, member: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        if path.objects[o].class != LIST || self.cp.runs_model(LIST) { return None; }
        let (name, descriptor) = (member.name.as_str(), member.descriptor.as_str());
        if special && member.owner != LIST { return None; }
        self.cp.library_image_method(LIST, name, descriptor)?;
        if name == "<init>" {
            if !special { return None; }
            if let [Val::I(capacity)] = args {
                // Negative capacities throw in the constructor itself. A successful
                // allocation must fit the checker, just like an ordinary anewarray.
                match self.new_array_cells(path, capacity) {
                    Ok(_) => {}
                    Err(Stop::Unsupported(_)) => return None,
                    Err(stop) => return Some(Err(stop)),
                }
            }
        } else if !path.objects[o].fields.contains_key("elementData") {
            return None;
        }
        let mut full = vec![Val::R(Some(o))];
        full.extend_from_slice(args);
        Some(self.call(path, LIST, name, descriptor, full))
    }

    /// Helpers reached from real list bytecode. The JDK performs typed copying using
    /// the actual destination component and System.arraycopy, including partial stores.
    pub(super) fn image_list_static(&mut self, path: &mut Path, caller: &str, m: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        match (caller, m.owner.as_str(), m.name.as_str(), m.descriptor.as_str(), args) {
            (LIST, "java/util/Objects", "checkIndex", "(II)I", [Val::I(i), Val::I(n)]) => {
                let inside = self.b.ult(i, n); // n is the initialized list's nonnegative size
                Some(self.branch_throw(path, -inside, "java/lang/IndexOutOfBoundsException", Val::I(i.clone())))
            }
            ("java/util/Arrays", "java/lang/reflect/Array", "newInstance", "(Ljava/lang/Class;I)Ljava/lang/Object;", [Val::R(Some(component)), Val::I(count)]) => {
                let name = self.class_named(path, *component)?;
                let element = if name.starts_with('[') {
                    if name.bytes().take_while(|c| *c == b'[').count() >= 255 { return Some(unsupported("reflective array allocation above 255 dimensions")); }
                    Type::parse(&name).ok()?
                } else {
                    if !self.cp.loads(&name) { return None; }
                    Type::object(&name)
                };
                Some(self.new_reference_array(path, element, count.clone()))
            }
            (LIST, _, _, _, _) | ("jdk/internal/util/ArraysSupport", _, _, _, _)
                if m.owner != LIST && self.cp.library_image_method(&m.owner, &m.name, &m.descriptor).is_some() => {
                Some(self.call(path, &m.owner, &m.name, &m.descriptor, args.to_vec()))
            }
            _ => None,
        }
    }
}
