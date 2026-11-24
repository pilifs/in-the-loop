//! Live views share the actual JDK map, including its bucket order and structural
//! modification count. A map restored from an initializer or an insertion-ordered
//! subclass keeps its existing representation. The two layouts never share methods.
use super::*;

/// A private heap key which cannot be a JVM field name (JVMS 4.2.2).
pub(super) const IMAGE: &str = "<JDK.HashMap>";
const MAP: &str = "java/util/HashMap";
pub(super) const CONCURRENT_IMAGE: &str = "<JDK.ConcurrentHashMap>";
pub(super) const PROPERTIES_IMAGE: &str = "<JDK.Properties>";

impl Engine<'_> {
    /// In a single-threaded JDK map with no counter cells the first baseCount CAS
    /// succeeds. Stop here only when the following resize loop has no iterations.
    fn uncontended_add_count(&mut self, path: &mut Path, o: usize, args: &[Val]) -> Option<Step> {
        let [Val::J(delta), Val::I(check)] = args else { return None };
        let fields = &path.objects[o].fields;
        if !self.cp.known_concurrent_table() || !matches!(fields.get("counterCells"), None | Some(Val::R(None))) { return None; }
        let current = match fields.get("baseCount") {
            None => self.b.constant(0, 64),
            Some(Val::J(word)) => word.clone(),
            _ => return None,
        };
        let next = self.b.add(&current, delta);
        let Some(Val::I(threshold)) = fields.get("sizeCtl") else { return None };
        if self.b.constant_value(check)? >= 0 && self.b.constant_value(&next)? >= self.b.constant_value(threshold)? { return None; }
        if self.there_before(path, o) {
            if let Err(e) = self.reads(path, || "reads a concurrent map's count and resize threshold".into()) { return Some(Err(e)); }
        }
        if let Err(e) = self.keeps(path, Some(o), "updates the base count of a concurrent map") { return Some(Err(e)); }
        path.objects[o].fields.insert("baseCount".into(), Val::J(next));
        self.advance(path);
        Some(Ok(None))
    }

    /// The selected image's array-base and shift designate the supplied Node[] slot.
    pub(super) fn concurrent_slot_cas(&mut self, path: &mut Path) -> Step {
        let args = self.pop_args(path, 4)?;
        let [Val::R(Some(table)), Val::I(index), expected, Val::R(update)] = args.as_slice() else {
            return unsupported("a concurrent map CAS on an unknown node array or replacement");
        };
        let node = "java/util/concurrent/ConcurrentHashMap$Node";
        if path.objects[*table].class != "[Ljava/util/concurrent/ConcurrentHashMap$Node;"
            || update.is_some_and(|o| !self.cp.is_subtype(&path.objects[o].class, node)) {
            return unsupported("a concurrent map CAS with an incompatible node");
        }
        let array = path.objects[*table].as_array().ok_or_else(|| Stop::Unsupported("unbound concurrent map node array".into()))?;
        let Some(slot) = self.b.constant_value(index).and_then(|n| usize::try_from(n).ok())
            .filter(|n| self.b.constant_value(&array.length).is_some_and(|length| (*n as i64) < length)) else {
            return unsupported("a concurrent map CAS needs a known in-bounds index");
        };
        let old = array.refs.get(slot).cloned().ok_or_else(|| Stop::Unsupported("unbound concurrent map slot".into()))?;
        if self.there_before(path, *table) { self.reads(path, || "reads an existing map slot".into())?; }
        self.keeps(path, Some(*table), "updates a concurrent map slot")?;
        let matched = self.same_lit(path, &old, expected)?;
        let value = choose(&mut self.b, matched, &Val::R(*update), &old).expect("node references");
        path.objects[*table].array.as_mut().expect("node array").refs[slot] = value;
        self.push(path, Val::I(self.b.zext(&vec![matched], 32)));
        self.advance(path);
        Ok(None)
    }

    pub(super) fn image_map_call(&mut self, path: &mut Path, o: usize, special: bool, member: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        let (owner, name, descriptor) = (member.owner.as_str(), member.name.as_str(), member.descriptor.as_str());
        if path.objects[o].class == crate::models::CONCURRENT_MAP && owner == crate::models::CONCURRENT_MAP
            && path.objects[o].fields.contains_key(CONCURRENT_IMAGE) && name == "addCount" && descriptor == "(JI)V" {
            if let Some(step) = self.uncontended_add_count(path, o, args) { return Some(step); }
        }
        let class = &path.objects[o].class;
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
        let new_linked_map = constructor && class == "java/util/LinkedHashMap" && owner == class
            && ((image_caller && descriptor == "(IF)V" && path.frames.last()?.class.name == "java/util/HashSet")
                || (descriptor == "()V" && self.gap_mode == GapMode::Strict && self.previous.is_none()
                    && self.contracts.is_empty() && self.cp.linked_map_image()));
        // A fieldless direct subclass uses the same JDK map layout. Its virtual overrides
        // still dispatch on the original application class, including removeEldestEntry.
        let linked_subclass = constructor && owner == "java/util/LinkedHashMap" && descriptor == "(IFZ)V"
            && self.gap_mode == GapMode::Strict && self.previous.is_none() && self.contracts.is_empty()
            && !path.objects[o].given && !path.objects[o].assumed && !path.objects[o].unknown
            && self.cp.application(class).ok().flatten().is_some_and(|cf| cf.super_class.as_deref() == Some(owner)
                && cf.fields.iter().all(|f| f.is_static())) && self.cp.linked_map_image();
        let new_set = constructor && !path.objects[o].given && !path.objects[o].assumed && !path.objects[o].unknown
            && self.gap_mode == GapMode::Strict && matches!(class.as_str(), "java/util/HashSet" | "java/util/LinkedHashSet")
            && owner == class && matches!(descriptor, "()V" | "(I)V" | "(Ljava/util/Collection;)V");
        let nested = constructor && image_caller && (class.starts_with("java/util/HashMap$") || class.starts_with("java/util/LinkedHashMap$")) && class == owner;
        // The Commons Collections view itself extends AbstractSet. These two JDK constructors
        // just chain to Object; their actual bodies run on the application's receiver as well.
        let base = constructor && descriptor == "()V" && matches!(owner, "java/util/AbstractCollection" | "java/util/AbstractSet" | "java/util/AbstractMap");
        if !(marked || new_map || new_linked_map || linked_subclass || new_set || nested || base) { return None; }
        let implementation;
        let lookup = if special { owner } else if marked && self.cp.is_application(class) {
            let Some((cf, _)) = self.cp.find_method(class, name, descriptor) else {
                return Some(unsupported(format!("unresolved virtual map method {class}.{name}{descriptor}")));
            };
            if self.cp.is_application(&cf.name) { return None; }
            implementation = cf;
            implementation.name.as_str()
        } else { class.as_str() };
        let Some((cf, method)) = self.cp.map_image_method(lookup, name, descriptor) else {
            // A method only in the old model cannot read or mutate these real JDK fields.
            if marked && self.cp.checker_method(lookup, name, descriptor).is_some_and(|(cf, _)| matches!(cf.name.as_str(), MAP | "java/util/HashMap$Node" | "java/util/LinkedHashMap")) {
                return Some(unsupported(format!("{}.{}{} is outside the selected JDK HashMap bytecode", lookup.replace('/', "."), name, descriptor)));
            }
            return None;
        };
        if method.is_static() { return None; }
        if new_map || new_linked_map || linked_subclass || new_set || nested { path.objects[o].fields.insert(IMAGE.into(), Val::I(self.b.constant(1, 32))); }
        let mut full = vec![Val::R(Some(o))];
        full.extend_from_slice(args);
        Some(self.enter_method(path, owner, cf, method, full))
    }
}
