//! Live views share the actual JDK map, including its bucket order and structural
//! modification count. A map restored from an initializer or an insertion-ordered
//! subclass keeps its existing representation. The two layouts never share methods.
use super::*;

/// A private heap key which cannot be a JVM field name (JVMS 4.2.2).
pub(super) const IMAGE: &str = "<JDK.HashMap>";
const MAP: &str = "java/util/HashMap";
pub(super) const CONCURRENT_IMAGE: &str = "<JDK.ConcurrentHashMap>";
const PROPERTIES_IMAGE: &str = "<JDK.Properties>";

impl Engine<'_> {
    pub(super) fn image_map_call(&mut self, path: &mut Path, o: usize, special: bool, member: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        let class = &path.objects[o].class;
        let (owner, name, descriptor) = (member.owner.as_str(), member.name.as_str(), member.descriptor.as_str());
        if matches!(class.as_str(), crate::models::CONCURRENT_MAP | "java/util/Properties")
            && !path.objects[o].assumed && !path.objects[o].given && !path.objects[o].unknown {
            let concurrent = class == crate::models::CONCURRENT_MAP;
            let marker = if concurrent { CONCURRENT_IMAGE } else { PROPERTIES_IMAGE };
            let fresh = special && owner == class && name == "<init>";
            if concurrent && fresh && descriptor == "(I)V" && !matches!(args, [Val::I(n)] if self.b.constant_value(n).is_some()) {
                // The existing capacity check handles a symbolic size without assuming the JDK fields.
                return None;
            }
            if fresh || path.objects[o].fields.contains_key(marker) {
                let selected = if concurrent {
                    if special && owner != class { None } else { self.cp.concurrent_map_method(name, descriptor) }
                } else {
                    self.cp.properties_method(class, owner, name, descriptor, special)
                };
                if let Some((cf, method)) = selected {
                    if fresh { path.objects[o].fields.insert(marker.into(), Val::I(self.b.constant(1, 32))); }
                    let mut full = vec![Val::R(Some(o))];
                    full.extend_from_slice(args);
                    return Some(self.enter_method(path, owner, cf, method, full));
                }
            }
        }
        let marked = path.objects[o].fields.contains_key(IMAGE);
        let constructor = special && name == "<init>";
        let image_caller = path.frames.last().is_some_and(|f| self.cp.is_map_image(&f.class));
        let new_map = constructor && class == MAP && owner == MAP
            && (descriptor == "()V" || (image_caller && descriptor == "(I)V"));
        let new_set = constructor && !path.objects[o].given && !path.objects[o].assumed && !path.objects[o].unknown
            && self.gap_mode == GapMode::Strict && class == "java/util/HashSet"
            && owner == class && matches!(descriptor, "()V" | "(I)V" | "(Ljava/util/Collection;)V");
        let nested = constructor && image_caller && class.starts_with("java/util/HashMap$") && class == owner;
        // The Commons Collections view itself extends AbstractSet. These two JDK constructors
        // just chain to Object; their actual bodies run on the application's receiver as well.
        let base = constructor && descriptor == "()V" && matches!(owner, "java/util/AbstractCollection" | "java/util/AbstractSet" | "java/util/AbstractMap");
        if !(marked || new_map || new_set || nested || base) { return None; }
        let lookup = if special { owner } else { class.as_str() };
        let Some((cf, method)) = self.cp.map_image_method(lookup, name, descriptor) else {
            // A method only in the old model cannot read or mutate these real JDK fields.
            if marked && self.cp.checker_method(lookup, name, descriptor).is_some_and(|(cf, _)| matches!(cf.name.as_str(), MAP | "java/util/HashMap$Node")) {
                return Some(unsupported(format!("{}.{}{} is outside the selected JDK HashMap bytecode", lookup.replace('/', "."), name, descriptor)));
            }
            return None;
        };
        if method.is_static() { return None; }
        if new_map || new_set || nested { path.objects[o].fields.insert(IMAGE.into(), Val::I(self.b.constant(1, 32))); }
        let mut full = vec![Val::R(Some(o))];
        full.extend_from_slice(args);
        Some(self.enter_method(path, owner, cf, method, full))
    }
}
