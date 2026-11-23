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
        let universe = self.constants_snapshot(path, &class, field)?;
        self.pop(path)?;
        self.push(path, Val::R(Some(universe)));
        self.advance(path);
        Ok(None)
    }

    fn constants_snapshot(&mut self, path: &mut Path, class: &str, field: String) -> Result<usize, Stop> {
        let key = (class.to_owned(), "<Class.enumConstantsShared>".to_owned());
        if let Some(held) = path.statics.get(&key) {
            return match held { Val::R(Some(o)) => Ok(*o), _ => unsupported("merged enum constants cache") };
        }
        let Some(Val::R(Some(o))) = path.statics.get(&(class.to_owned(),field)) else { return unsupported("enum universe read before its values were initialized") };
        let Some(array) = path.objects[*o].as_array().filter(|a| a.element == Type::object(class)).cloned() else { return unsupported("unknown enum constants array contents") };
        let copy = self.alloc(path, &format!("[L{class};"));
        path.objects[copy].array = Some(array);
        path.statics.insert(key, Val::R(Some(copy)));
        Ok(copy)
    }

    /// The JDK lazily indexes the shared constants by Enum.name(), retaining the constants
    /// themselves. Capture the same directory on its first use, including duplicate-key replacement.
    pub(super) fn enum_by_name(&mut self, path: &mut Path) -> Step {
        for depth in [1, 0] {
            if let Some(step) = self.concrete_ref(path, depth) { return step; }
        }
        let stack = &path.frames.last().expect("a frame").stack;
        let [.., Val::R(Some(mirror)), Val::R(name)] = &stack[..] else { return unsupported("Enum.valueOf requires a known enum class mirror"); };
        let name = *name;
        let Some(class) = self.class_named(path,*mirror) else { return unsupported("Enum.valueOf requires a known Class"); };
        let Some(field) = self.cp.enum_values_field(&class) else { return unsupported("Enum.valueOf requires the original enum values() array clone"); };
        if let Some(step) = self.initialise(path,&class) { return step; }
        let constants = self.constants_snapshot(path,&class,field)?;
        let key = (class.clone(), "<Class.enumConstantDirectory>".to_owned());
        let directory = match path.statics.get(&key) {
            Some(Val::R(Some(o))) => *o,
            Some(_) => return unsupported("merged enum name directory"),
            None => {
                let array = path.objects[constants].as_array().expect("constants");
                if self.b.constant_value(&array.length) != Some(array.refs.len() as i64) {
                    return unsupported("enum name directory with unknown extent");
                }
                let entries = array.refs.clone();
                let directory = self.alloc(path,"<Enum name directory>");
                for entry in entries {
                    let Val::R(Some(o)) = entry else { return unsupported("enum name directory with an unbound constant"); };
                    let name_field = self.field_key(path,o,"java/lang/Enum","name","Ljava/lang/String;")?;
                    let Some(Val::R(Some(text))) = path.objects[o].fields.get(&name_field) else { return unsupported("enum constant lacks its original name"); };
                    let Some(units) = self.constant_units(path,*text) else { return unsupported("enum constant has an unbound name"); };
                    path.objects[directory].fields.insert(enum_key(&units),entry);
                }
                path.statics.insert(key,Val::R(Some(directory)));
                directory
            }
        };
        self.pop(path)?;
        self.pop(path)?;
        let Some(name) = name else { return self.throw_class_only(path,"java/lang/NullPointerException"); };
        let Some(units) = self.constant_units(path,name) else { return unsupported("Enum.valueOf of a symbolic name"); };
        if let Some(value) = path.objects[directory].fields.get(&enum_key(&units)).cloned() {
            self.push(path,value);
            self.advance(path);
            Ok(None)
        } else {
            self.throw_class_only(path,"java/lang/IllegalArgumentException")
        }
    }
}

// A Java string is a sequence of UTF-16 units. Preserve even unpaired surrogate units in a cache key.
fn enum_key(units: &[u16]) -> String {
    units.iter().map(|unit| format!("{unit:04x}")).collect()
}
