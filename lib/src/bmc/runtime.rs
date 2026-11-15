//! The JVM's own objects a class initializer asks for: a class by its name, its loader, a logger.
//!
//! Library code probes its surroundings before it does anything else: Spring's `LogFactory.getLog(DataBinder.class)`
//! asks `Class.forName` for Log4j and SLF4J, each absent from a class path that has neither, and then
//! `java.util.logging.Logger.getLogger` for a logger it keeps in a static field. These are answers about the run's
//! class path and the JDK, which the engine has: each is modelled where the answer is one, under an assumption the
//! run states ([`CLASS_PATH_ASSUMPTION`]), and stays the JDK call it was elsewhere.
//!
//! - `Class.getName()` of a class literal: the class's binary name, the interned String (the JVM interns it).
//! - `Class.getClassLoader()` of the literal of a class of the check's class path: the one loader object of the
//!   run; of a JDK class, the JDK call it was.
//! - `Class.forName(String, boolean, ClassLoader)` with that loader, a name that is a constant and `false`
//!   (no initialization): the class literal of a class of the class path, `ClassNotFoundException` for a name
//!   neither the class path nor the JDK has. A name the JDK has stays the JDK's call (which of its modules a run
//!   resolves is the launcher's to say), as does a name that is no constant, an array's, or `true`.
//!   `NullPointerException` for a null name.
//! - `java.util.logging.Logger.getLogger(String)` of a constant name: a Logger, the same object for the same name,
//!   never null (its Javadoc: find or create); `NullPointerException` for null. The object has no content: every
//!   method of it is the JDK call it was. The logging configuration it reads is JDK state no check observes.
//! - `new ArrayList()`: the JDK's no-argument constructor only sets the list's own fields, so the object is made
//!   as any object with no content is, its methods the JDK calls they were.

use super::*;

/// What a run that asked for a class by name, or for a class's loader, took for granted.
pub const CLASS_PATH_ASSUMPTION: &str = "the classes of the check's class path are loaded by one class loader, which finds the classes of that class path and of the JDK and no other: a class neither has is not found (Class.forName throws ClassNotFoundException)";

const CLASS: &str = "java/lang/Class";
const LOADER: &str = "java/lang/ClassLoader";
const LOGGER: &str = "java/util/logging/Logger";

/// Whether the engine models the static call here, where its arguments let it.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!((owner, name, descriptor), (CLASS, "forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;") | (LOGGER, "getLogger", "(Ljava/lang/String;)Ljava/util/logging/Logger;"))
}

/// Whether the engine models the instance call here, on a class literal.
pub fn models_instance(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!((owner, name, descriptor), (CLASS, "getName", "()Ljava/lang/String;") | (CLASS, "getClassLoader", "()Ljava/lang/ClassLoader;"))
}

/// The JDK constructors that only set their object's own fields, throw nothing and take nothing: the object is
/// made as one with no content.
pub fn plain_constructor(owner: &str, descriptor: &str) -> bool {
    matches!((owner, descriptor), ("java/util/ArrayList", "()V"))
}

impl Engine<'_> {
    /// The class a class literal's object names, by its internal name.
    fn class_named(&self, path: &Path, o: usize) -> Option<String> {
        path.literals.iter().find_map(|(l, &at)| match l {
            Literal::Class(name) if at == o => Some(name.clone()),
            _ => None,
        })
    }

    /// A String's units where every one is a constant.
    pub(super) fn constant_units(&self, path: &Path, o: usize) -> Option<Vec<u16>> {
        let s = path.objects[o].content()?;
        let length = usize::try_from(self.b.constant_value(&s.length)?).ok()?;
        s.cells.get(..length)?.iter().map(|c| self.b.constant_value(c).map(|u| u as u16)).collect()
    }

    /// `Class.getName()` and `Class.getClassLoader()` on the object `o`: see the module's notes. `None` where the
    /// call stays the JDK's.
    pub(super) fn class_method(&mut self, path: &mut Path, o: usize, owner: &str, name: &str, descriptor: &str) -> Option<Step> {
        if path.objects[o].class != CLASS || !models_instance(owner, name, descriptor) {
            return None;
        }
        let class = self.class_named(path, o)?;
        let value = match name {
            "getName" => {
                let units: Vec<u16> = class.replace('/', ".").encode_utf16().collect();
                self.literal(path, Literal::Str(units), STRING)
            }
            _ => {
                if !self.cp.is_application(&class) {
                    return None;
                }
                self.assumed.insert(CLASS_PATH_ASSUMPTION);
                self.literal(path, Literal::Loader, LOADER)
            }
        };
        self.push(path, Val::R(Some(value)));
        self.advance(path);
        Some(Ok(None))
    }

    /// `Class.forName(name, false, loader)` and `Logger.getLogger(name)`: see the module's notes. `None` where
    /// the call stays the JDK's.
    pub(super) fn runtime_static(&mut self, path: &mut Path, owner: &str, name: &str, args: &[Val]) -> Option<Step> {
        match (owner, name, args) {
            (CLASS, "forName", [Val::R(named), Val::I(initialize), Val::R(Some(loader))]) => {
                if self.b.constant_value(initialize) != Some(0) || path.literals.get(&Literal::Loader) != Some(loader) {
                    return None;
                }
                let Some(named) = *named else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                let text = String::from_utf16(&self.constant_units(path, named)?).ok()?;
                if text.starts_with('[') {
                    return None;
                }
                // A binary name has no `/`: one that does names no class.
                let internal = text.replace('.', "/");
                let found = !text.contains('/') && self.cp.exists(&internal);
                self.assumed.insert(CLASS_PATH_ASSUMPTION);
                if !found {
                    return Some(self.raise(path, "java/lang/ClassNotFoundException"));
                }
                if !self.cp.is_application(&internal) {
                    return None;
                }
                let o = self.literal(path, Literal::Class(internal), CLASS);
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            (LOGGER, "getLogger", [Val::R(named)]) => {
                let Some(named) = *named else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                let units = self.constant_units(path, named)?;
                let o = self.literal(path, Literal::Logger(units), LOGGER);
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            _ => None,
        }
    }
}
