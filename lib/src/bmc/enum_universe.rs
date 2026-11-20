//! EnumMap and EnumSet share the JVM's enum constants array. For a checked values()
//! method the array is a snapshot of its backing field, with the original element identities.
use super::*;

impl Engine<'_> {
    pub(super) fn enum_universe(&mut self, path: &mut Path) -> Step {
        if let Some(step) = self.concrete_ref(path, 0) { return step; }
        let value = path.frames.last().and_then(|f| f.stack.last());
        let Some(Val::R(Some(mirror))) = value else { return unsupported("enum universe needs a known non-null Class literal") };
        let Some(class) = self.class_named(path, *mirror) else { return unsupported("enum universe needs a known enum class") };
        let Some(field) = self.cp.enum_values_field(&class) else { return unsupported(format!("enum universe of {} needs a checked values() array clone", class.replace('/', "."))) };
        if let Some(step) = self.initialise(path, &class) { return step; }
        let key = (class.clone(), "<Class.enumConstantsShared>".to_string());
        let universe = if let Some(held) = path.statics.get(&key) { held.clone() } else {
            let Some(Val::R(Some(o))) = path.statics.get(&(class.clone(), field)) else { return unsupported("enum universe read before its values were initialized") };
            let Some(a) = path.objects[*o].as_array().filter(|a| a.element == Type::object(&class)).cloned() else { return unsupported("unknown enum constants array contents") };
            let copy = self.alloc(path, &format!("[L{class};"));
            path.objects[copy].array = Some(a);
            let result = Val::R(Some(copy));
            path.statics.insert(key, result.clone());
            result
        };
        self.pop(path)?;
        self.push(path, universe);
        self.advance(path);
        Ok(None)
    }
}
