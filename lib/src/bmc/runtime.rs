//! The JVM's own objects a class initializer asks for: a class by its name, its loader, a logger.
//!
//! Library code probes its surroundings before it does anything else: Spring's `LogFactory.getLog(DataBinder.class)`
//! asks `Class.forName` for Log4j and SLF4J, each absent from a class path that has neither, and then
//! `java.util.logging.Logger.getLogger` for a logger it keeps in a static field. These are answers about the run's
//! class path and the JDK, which the engine has: each is modelled where the answer is one, under an assumption the
//! run states ([`CLASS_PATH_ASSUMPTION`]), and stays the JDK call it was elsewhere.
//!
//! - `Object.getClass()` of an object of an application class that the run made with `new`, of a String (a final
//!   class), and of a `Throwable` the run made and no JDK call returned (with `new`, or the engine for the JVM or a
//!   model of a JDK method, as `athrow`'s handlers already take it; its class is the one `new` or the engine's own
//!   throw named, [`super::throwables`]): that class's literal, the one object a class literal of it is (JLS
//!   §15.8.2). Of any other object (an array, a lambda's, another JDK class's) it is the JDK call it was.
//! - `Class.getName()` of a class literal: the class's binary name, the interned String (the JVM interns it).
//!   `Class.getTypeName()` of the literal of a class that is no array: the same String, as the JDK's returns
//!   `getName()` for such a class (an array's is its element type's name and `[]`, the JDK call it was).
//!   `Class.isArray()` of a class literal: whether it names an array class (a name that starts with `[`). Spring's
//!   `ObjectUtils.isArray` asks it of the class of every value a binding error records.
//! - `java.lang.reflect.Proxy.isProxyClass(Class)` of a class literal: false. The engine makes the literal of a
//!   class it finds on the class path or in the JDK, by a constant name, and a proxy class is one the JVM generates
//!   while it runs, which neither has. `NullPointerException` for null. Spring's `ClassUtils.getDescriptiveType`
//!   asks it of every value it names in a message.
//! - `Class.getSuperclass()` of a class literal of a class the class path or the JDK has and can load: its direct
//!   superclass's literal, as its class file names it; null of `Object` and of an interface; `Object`'s of an
//!   array's. Of a copy in a pair of versions it is the copy's superclass, a copy itself where the previous
//!   version declared it. Of any other class it is the JDK call it was.
//! - `Class.getClassLoader()` of the literal of a class of the check's class path: the one loader object of the
//!   run; of a JDK class, the JDK call it was.
//! - `Class.forName(String, boolean, ClassLoader)` with that loader, a name that is a constant and `false`
//!   (no initialization): the class literal of a class of the class path, `ClassNotFoundException` for a name
//!   neither the class path nor the JDK has. A name the JDK has stays the JDK's call (which of its modules a run
//!   resolves is the launcher's to say), as does a name that is no constant, an array's, or `true`.
//!   `NullPointerException` for a null name.
//! - `Class.forName(String)`, called by a class of the check's class path, with a name that is a constant: as the
//!   form above with that class's loader, and with initialization (JLS §12.4, JVMS §5.5): the class literal of a
//!   class of the class path, initialized first as any use initializes it (its superclasses before it; an
//!   exception its initializer throws leaves as `ExceptionInInitializerError`, and an erroneous class is
//!   `NoClassDefFoundError`).
//! - Both forms load the class, which needs each class and interface above it (JVMS §5.3.5): where one of those is
//!   on neither the class path nor in the JDK, the JVM throws a `NoClassDefFoundError` the engine does not model,
//!   and the call stays the JDK's.
//! - `Class.isAssignableFrom(Class)` of two class literals, each of a class or an interface the class path or the
//!   JDK has: whether the argument's class is the receiver's or below it, as `instanceof` decides it
//!   ([`ClassPath::is_subtype`]). `NullPointerException` for a null argument. Of a primitive type's or an array's
//!   `Class` it is the JDK call it was.
//! - In a regression check made as a property of the pair of versions ([`crate::pairing`]) the previous version's
//!   classes are copies under another package beside the new version's ([`crate::relocate::Previous`]). A copy's
//!   `getName()` is its class's own name. A `Class.forName` called by a copy finds the copy of the class named,
//!   and no class that only the new version's class path has (`ClassNotFoundException`); a class the previous
//!   version's class path has and the check holds no copy of stays the JDK's call. Called by any other class,
//!   it finds no copy.
//! - `Collections.emptyMap()`: the JDK's one empty map, the same object on every call, never null. The object has
//!   no content: every method of it is the JDK call it was.
//! - `Thread.currentThread()`: the one thread of the run, the same object on every call. Its
//!   `getContextClassLoader()`: the loader of the check's class path, under the assumption the run states
//!   ([`CONTEXT_LOADER_ASSUMPTION`]). Every other method of the thread is the JDK call it was.
//! - `java.util.logging.Logger.getLogger(String)` of a constant name: a Logger, the same object for the same name,
//!   never null (its Javadoc: find or create); `NullPointerException` for null. The object has no content: every
//!   method of it is the JDK call it was. The logging configuration it reads is JDK state no check observes.
//! - `getstatic` of a level of `java.util.logging.Level` other than `OFF` (`SEVERE`, `WARNING`, `INFO`, `CONFIG`,
//!   `FINE`, `FINER`, `FINEST`, `ALL`): the one object the constant is. `Logger.isLoggable(Level)` of such a Logger
//!   and such a level, under the assumption the run states ([`LOGGING_ASSUMPTION`]): false below `INFO`, so a
//!   library's debug line is not written and what it would have formatted is not run, and true at `INFO` and
//!   above. On any other Logger, or of a null level, it is the JDK call it was.
//! - What a library does to log a line at a level that is logged (Spring's `LogAdapter.JavaUtilLog`): `new
//!   LogRecord(Level, String)`, or a constructor of a subclass that calls it, `NullPointerException` for a null
//!   level and otherwise nothing a check observes (the record's own fields, a global sequence number, the time);
//!   the record's setters `setLoggerName`, `setResourceBundleName`, `setResourceBundle`, `setSourceClassName`,
//!   `setSourceMethodName` and `setThrown`, where the JDK's method is the one called: nothing (the record's own
//!   fields, which a later getter is the JDK call for, a gap); the Logger's `getResourceBundleName()` and
//!   `getResourceBundle()`: null, since nothing gave it a bundle ([`PUBLISHING_ASSUMPTION`]); and `Logger.log(record)`:
//!   `NullPointerException` for null, and for a record whose class is confined to itself ([`Engine::confined_record`])
//!   a normal return, under [`PUBLISHING_ASSUMPTION`]: the default handler writes it to `System.err` and swallows what
//!   its formatting throws, and each number field the record's own classes declare, on any object of them, holds any
//!   value afterwards ([`Engine::formatted`]), since a getter may have written it. Formatting calls the record's getters, a subclass's overrides included, so a record of a
//!   class that could write elsewhere from one of them stays the JDK call. A level, a handler, a filter or a bundle
//!   set on a Logger is a call of it no model takes, so a check that sets one stops there.
//! - `getstatic` of `Boolean.TRUE` or `Boolean.FALSE` and `Boolean.valueOf(boolean)` share two
//!   canonical objects. `booleanValue()` on either returns the corresponding truth.
//! - `new ArrayList()`: the JDK's no-argument constructor only sets the list's own fields, so the object is made
//!   as any object with no content is, its methods the JDK calls they were.
//! - `new ConcurrentHashMap()` and `new ConcurrentHashMap(int)`: likewise (the JDK allocates the table at the first
//!   entry), the second with its `IllegalArgumentException` for a negative capacity. A library makes such maps as
//!   caches in a constructor, and a path that never asks one anything goes on.

use super::*;
use std::collections::BTreeSet;

/// What a run that asked for a class by name, or for a class's loader, took for granted.
pub const CLASS_PATH_ASSUMPTION: &str = "the classes of the check's class path are loaded by one class loader, which finds the classes of that class path and of the JDK and no other: a class neither has is not found (Class.forName throws ClassNotFoundException)";

/// What a run that asked the current thread for its context class loader took for granted.
pub const CONTEXT_LOADER_ASSUMPTION: &str = "the check runs on one thread, whose context class loader is the class loader of the check's class path: nothing has set another (Thread.setContextClassLoader), as on a JVM started with that class path";

/// What a run that asked a logger whether a level is logged took for granted.
pub const LOGGING_ASSUMPTION: &str = "java.util.logging is configured as the JDK configures it by default: no logging configuration file or class is named, and nothing sets a logger's level, so each logger's level is the root's, INFO, and nothing below INFO is logged (Logger.isLoggable is false for CONFIG, FINE, FINER, FINEST and ALL, and true for INFO, WARNING and SEVERE)";

/// What a run that gave a logger a record to log took for granted.
pub const PUBLISHING_ASSUMPTION: &str = "a record given to a logger goes to the handler the JDK's default logging configuration gives the root logger and nowhere else: no logger has a filter, a handler of its own or a resource bundle, and the root's one handler is a ConsoleHandler, which writes the record to System.err (no check observes it) and reports to its ErrorManager, without throwing, an exception its formatting throws";

pub(super) const BOOLEAN: &str = "java/lang/Boolean";

/// Whether the static field is `Boolean.TRUE` or `Boolean.FALSE`, and which: one object each for a run, as each is
/// one on a JVM, distinct from each other and from any other object. `valueOf` returns one of these objects
/// and `booleanValue` reads the corresponding truth.
pub fn truth_constant(owner: &str, name: &str) -> Option<bool> {
    match (owner, name) {
        (BOOLEAN, "TRUE") => Some(true),
        (BOOLEAN, "FALSE") => Some(false),
        _ => None,
    }
}

/// The levels of `java.util.logging.Level` below `INFO`, by their fields' names.
const BELOW_INFO: [&str; 5] = ["CONFIG", "FINE", "FINER", "FINEST", "ALL"];
/// The levels at `INFO` and above that a logger of the default configuration logs (`OFF` is not one: its value is
/// above every level, and `isLoggable(OFF)` is true too, which no library asks).
const LOGGED: [&str; 3] = ["INFO", "WARNING", "SEVERE"];
pub(super) const LEVEL: &str = "java/util/logging/Level";
const LOG_RECORD: &str = "java/util/logging/LogRecord";
/// The longest array a confined record's getter may make ([`Engine::confined_record`]).
const SMALL_ARRAY: i32 = 1024;

/// Whether the static field is a level the engine has one object of for a run.
pub fn level_constant(owner: &str, name: &str) -> Option<&'static str> {
    BELOW_INFO.into_iter().chain(LOGGED).find(|level| owner == LEVEL && *level == name)
}

/// The setters of a `LogRecord` that only set the record's own fields.
const RECORD_SETTERS: [(&str, &str); 6] = [
    ("setLoggerName", "(Ljava/lang/String;)V"),
    ("setResourceBundleName", "(Ljava/lang/String;)V"),
    ("setResourceBundle", "(Ljava/util/ResourceBundle;)V"),
    ("setSourceClassName", "(Ljava/lang/String;)V"),
    ("setSourceMethodName", "(Ljava/lang/String;)V"),
    ("setThrown", "(Ljava/lang/Throwable;)V"),
];

/// Whether the engine models the instance call here, where its receiver and arguments let it: a Logger's
/// `isLoggable(Level)`, `getResourceBundleName()`, `getResourceBundle()` and `log(LogRecord)`, and a `LogRecord`'s
/// constructor of a level and a message and its setters.
pub fn models_logging(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!(
        (owner, name, descriptor),
        (LOGGER, "isLoggable", "(Ljava/util/logging/Level;)Z")
            | (LOGGER, "getResourceBundleName", "()Ljava/lang/String;")
            | (LOGGER, "getResourceBundle", "()Ljava/util/ResourceBundle;")
            | (LOGGER, "log", "(Ljava/util/logging/LogRecord;)V")
            | (LOG_RECORD, "<init>", "(Ljava/util/logging/Level;Ljava/lang/String;)V")
    ) || (owner == LOG_RECORD && RECORD_SETTERS.contains(&(name, descriptor)))
}

const CLASS: &str = "java/lang/Class";
const LOADER: &str = "java/lang/ClassLoader";
const LOGGER: &str = "java/util/logging/Logger";
const THREAD: &str = "java/lang/Thread";
pub(super) const LINE_SEPARATOR: &str = "the contents and external string identity of the JVM's initial line separator are not bound";
pub(super) fn enum_identity_read(caller: &str, method: &str, m: &crate::classfile::MemberRef) -> bool {
    (caller, method, m.owner.as_str(), m.name.as_str(), m.descriptor.as_str())
        == ("java/lang/Enum", "hashCode", "java/lang/System", "identityHashCode", "(Ljava/lang/Object;)I")
}
const COLLECTIONS: &str = "java/util/Collections";
pub(super) const EMPTY_MAP: &str = "java/util/Collections$EmptyMap";
const FOR_NAME: &str = "(Ljava/lang/String;)Ljava/lang/Class;";
const PROXY: &str = "java/lang/reflect/Proxy";

/// Integral factories with a mandated cache. Character's cache covers ASCII only.
pub(super) fn cached_wrapper(owner: &str, name: &str, descriptor: &str) -> Option<&'static str> {
    match (owner, name, descriptor) {
        ("java/lang/Byte", "valueOf", "(B)Ljava/lang/Byte;") => Some("java/lang/Byte"),
        ("java/lang/Short", "valueOf", "(S)Ljava/lang/Short;") => Some("java/lang/Short"),
        ("java/lang/Character", "valueOf", "(C)Ljava/lang/Character;") => Some("java/lang/Character"),
        ("java/lang/Long", "valueOf", "(J)Ljava/lang/Long;") => Some("java/lang/Long"),
        _ => None,
    }
}

/// Whether the engine models the static call here, where its arguments let it.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    if (owner, name, descriptor) == ("java/lang/Integer", "valueOf", "(I)Ljava/lang/Integer;") { return true; }
    matches!(
        (owner, name, descriptor),
        ("java/lang/System", "lineSeparator", "()Ljava/lang/String;") | (COLLECTIONS, "emptyList", "()Ljava/util/List;") | (COLLECTIONS, "emptySet", "()Ljava/util/Set;") |
        (BOOLEAN, "valueOf", "(Z)Ljava/lang/Boolean;") | ("java/lang/reflect/Array", "getLength", "(Ljava/lang/Object;)I") | (CLASS, "forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;" | FOR_NAME) | (LOGGER, "getLogger", "(Ljava/lang/String;)Ljava/util/logging/Logger;") | (THREAD, "currentThread", "()Ljava/lang/Thread;") | (COLLECTIONS, "emptyMap", "()Ljava/util/Map;") | (PROXY, "isProxyClass", "(Ljava/lang/Class;)Z")
    )
}

fn canonical_truth(path: &Path, object: usize) -> Option<bool> {
    [true, false].into_iter().find(|v| path.literals.get(&Literal::Truth(*v)) == Some(&object))
}

/// Whether the engine models the instance call here, on a class literal, or `getClass()` on an object it made.
pub fn models_instance(owner: &str, name: &str, descriptor: &str) -> bool {
    if matches!((owner, name, descriptor), ("java/lang/Integer" | "java/lang/Number", "intValue", "()I")) { return true; }
    matches!(
        (owner, name, descriptor),
        (BOOLEAN, "booleanValue", "()Z") | (BOOLEAN, "equals", "(Ljava/lang/Object;)Z") | (CLASS, "getName" | "getTypeName", "()Ljava/lang/String;")
            | (CLASS, "isArray" | "isPrimitive", "()Z")
            | (CLASS, "getSuperclass" | "getComponentType", "()Ljava/lang/Class;")
            | (CLASS, "getClassLoader", "()Ljava/lang/ClassLoader;")
            | (CLASS, "isAssignableFrom", "(Ljava/lang/Class;)Z") | (CLASS, "isInstance", "(Ljava/lang/Object;)Z")
            | ("java/lang/Object", "getClass", "()Ljava/lang/Class;")
            | (THREAD, "getContextClassLoader", "()Ljava/lang/ClassLoader;")
    )
}

/// The JDK constructors that only set their object's own fields, throw nothing and take nothing: the object is
/// made as one with no content.
pub fn plain_constructor(owner: &str, descriptor: &str) -> bool {
    matches!((owner, descriptor), ("java/util/ArrayList" | CONCURRENT_MAP, "()V"))
}

use crate::models::CONCURRENT_MAP;

/// The JDK constructors that take an initial capacity and nothing else, and only set their object's own fields:
/// `IllegalArgumentException` for a negative capacity, and otherwise the object made as one with no content.
pub fn capacity_constructor(owner: &str, descriptor: &str) -> bool {
    matches!((owner, descriptor), (CONCURRENT_MAP, "(I)V"))
}

impl Engine<'_> {
    /// Materialize only a range the solver proves contains every possible value on this path.
    /// Outside the mandatory cache the selected JDK's factory decides what it constructs.
    pub(super) fn cached_integral(&mut self, path: &mut Path, class: &'static str, word: &Bits) -> Option<Step> {
        let minimum = if class == "java/lang/Character" { 0 } else { i8::MIN };
        let boxed = if let Some(n) = self.b.constant_value(word) {
            let n = i8::try_from(n).ok().filter(|n| *n >= minimum)?;
            Val::R(Some(self.literal(path, Literal::CachedIntegral(class, n), class)))
        } else {
            let mut range = None;
            for (lo, hi) in [(0, 3), ((-1).max(minimum), 15), (minimum, i8::MAX)] {
                let below = self.b.slt(word, &self.b.constant(i64::from(lo), word.len()));
                let above = self.b.slt(&self.b.constant(i64::from(hi), word.len()), word);
                let mut outside = path.cond.clone();
                outside.push(self.b.or(below, above));
                match self.solve(&outside) {
                    Ok(false) => { range = Some(lo..=hi); break; }
                    Ok(true) => {}
                    Err(stop) => return Some(Err(stop)),
                }
            }
            let mut choices = Vec::new();
            for n in range? {
                let guard = self.b.eq(word, &self.b.constant(i64::from(n), word.len()));
                choices.push((guard, Some(self.literal(path, Literal::CachedIntegral(class, n), class))));
            }
            choice(&mut self.b, choices)
        };
        self.push(path, boxed);
        self.advance(path);
        Some(Ok(None))
    }

    /// Boolean.equals also dispatches here when the invocation names Object.equals.
    /// Untracked Boolean receivers or arguments still require their own evidence.
    pub(super) fn boolean_equals(&mut self, path: &mut Path, receiver: usize, args: &[Val]) -> Option<Step> {
        let truth = canonical_truth(path, receiver)?;
        let [Val::R(other)] = args else { return None };
        let equal = match *other {
            None => false,
            Some(o) if o == receiver => true,
            Some(o) if path.objects[o].assumed => return None,
            Some(o) if path.objects[o].class != BOOLEAN => false,
            Some(o) => canonical_truth(path, o)? == truth,
        };
        self.push(path, Val::I(self.b.constant(i64::from(equal), 32)));
        self.advance(path);
        Some(Ok(None))
    }

    /// The class a class literal's object names, by its internal name.
    pub(super) fn class_named(&self, path: &Path, o: usize) -> Option<String> {
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

    /// `Class.getName()`, `Class.getTypeName()`, `Class.isArray()`, `Class.getSuperclass()` and `Class.getClassLoader()`
    /// on the object `o`, and `getClass()` on it: see the module's
    /// notes. `None` where the call stays the JDK's.
    pub(super) fn class_method(&mut self, path: &mut Path, o: usize, owner: &str, name: &str, descriptor: &str) -> Option<Step> {
        if (owner, name, descriptor) == (super::bytes::CHARSET, "name", "()Ljava/lang/String;") {
            let field = path.literals.iter().find_map(|(key, &r)| match key {
                Literal::Charset(field) if r == o => Some(*field), _ => None,
            })?;
            let units = self.cp.charset_name_literal(field)?;
            let text = self.literal(path, Literal::Str(units), "java/lang/String");
            self.push(path, Val::R(Some(text)));
            self.advance(path);
            return Some(Ok(None));
        }
        if (owner, name, descriptor) == (BOOLEAN, "booleanValue", "()Z") {
            let truth = canonical_truth(path, o)?;
            self.push(path, Val::I(self.b.constant(i64::from(truth), 32)));
            self.advance(path);
            return Some(Ok(None));
        }
        if matches!((owner, name, descriptor), ("java/lang/Integer" | "java/lang/Number", "intValue", "()I")) {
            let value = path.literals.iter().find_map(|(literal, &object)| match literal {
                Literal::CachedIntegral("java/lang/Integer", value) if object == o => Some(*value), _ => None,
            })?;
            self.push(path, Val::I(self.b.constant(i64::from(value), 32)));
            self.advance(path);
            return Some(Ok(None));
        }
        if (owner, name, descriptor) == (CLASS, "desiredAssertionStatus", "()Z") {
            let class = self.class_named(path, o)?;
            let frame = path.frames.last()?;
            let image_host = self.cp.state_image_class(&class).is_some()
                || (frame.class.name.starts_with(&format!("{class}$")) && self.cp.load(&class).ok().flatten()
                    .is_some_and(|loaded| matches!(loaded.origin, crate::classpath::Origin::Jdk)));
            if frame.method != "<clinit>" || self.cp.state_image_class(&frame.class.name).is_none() || !image_host { return None; }
            let flag = path.statics.entry((class, "<VM.desiredAssertionStatus>".into())).or_insert_with(|| {
                let bit = self.b.var(); Val::I(self.b.zext(&vec![bit], 32))
            }).clone();
            path.unbound_platform_value = Some("a JVM-chosen assertion setting");
            self.push(path, flag);
            self.advance(path);
            return Some(Ok(None));
        }
        if (name, descriptor) == ("getClass", "()Ljava/lang/Class;") {
            let class = path.objects[o].class.clone();
            // An exception the run made (with `new`, or the engine for the JVM or a model of a JDK method), and no JDK
            // call returned, is of the class it was made as: a handler already takes it for that class
            // ([`super::throwables`]).
            let o_ = &path.objects[o];
            let exception = !o_.given && !o_.assumed && (super::throwables::jdk_throwable(self.cp, &class) || (self.cp.loads(&class) && self.cp.is_subtype(&class, "java/lang/Throwable")));
            let array = o_.is_array() && !o_.assumed && !self.there_before(path, o);
            let image_object = !o_.assumed && !self.there_before(path, o) && self.cp.state_image_class(&class).is_some();
            if o_.lambda.is_some() || !(array || image_object || self.cp.is_application(&class) || class == STRING || exception) {
                return None;
            }
            let literal = self.literal(path, Literal::Class(class), CLASS);
            self.push(path, Val::R(Some(literal)));
            self.advance(path);
            return Some(Ok(None));
        }
        if (name, descriptor) == ("getContextClassLoader", "()Ljava/lang/ClassLoader;") {
            if path.literals.get(&Literal::Thread) != Some(&o) {
                return None;
            }
            self.assumed.insert(CLASS_PATH_ASSUMPTION.to_string());
            self.assumed.insert(CONTEXT_LOADER_ASSUMPTION.to_string());
            let loader = self.literal(path, Literal::Loader, LOADER);
            self.push(path, Val::R(Some(loader)));
            self.advance(path);
            return Some(Ok(None));
        }
        if path.objects[o].class != CLASS || !models_instance(owner, name, descriptor) || matches!(name, "isAssignableFrom" | "isInstance") {
            return None;
        }
        let primitive = path.literals.iter().any(|(literal, object)| *object == o && matches!(literal, Literal::PrimitiveClass(_)));
        if name == "isPrimitive" && (primitive || self.class_named(path, o).is_some()) {
            self.push_truth(path, if primitive { TRUE } else { FALSE });
            return Some(Ok(None));
        }
        if primitive {
            match name {
                "isArray" => self.push_truth(path, FALSE),
                "getSuperclass" | "getComponentType" | "getClassLoader" => { self.push(path, Val::R(None)); self.advance(path); }
                _ => return None,
            }
            return Some(Ok(None));
        }
        let class = self.class_named(path, o)?;
        if name == "isArray" {
            let value = self.b.constant(i64::from(class.starts_with('[')), 32);
            self.push(path, Val::I(value));
            self.advance(path);
            return Some(Ok(None));
        }
        let value = match name {
            "getName" | "getTypeName" => {
                if name == "getTypeName" && class.starts_with('[') {
                    return None;
                }
                // A copy of a class of the previous version of a pair has that class's own name.
                let own = self.previous.as_ref().and_then(|p| p.original(&class)).unwrap_or(&class);
                let units: Vec<u16> = own.replace('/', ".").encode_utf16().collect();
                self.literal(path, Literal::Str(units), STRING)
            }
            "getComponentType" => {
                let Some(desc) = class.strip_prefix('[') else {
                    self.push(path, Val::R(None));
                    self.advance(path);
                    return Some(Ok(None));
                };
                let component = Type::parse(desc).ok()?;
                let key = if holds_references(&component) { Literal::Class(class_of(&component)) } else { Literal::PrimitiveClass(component.descriptor()) };
                self.literal(path, key, CLASS)
            }
            "getSuperclass" => {
                let above = if class.starts_with('[') {
                    Some("java/lang/Object".to_string())
                } else {
                    if !self.cp.loads(&class) {
                        return None;
                    }
                    let interface = matches!(self.cp.load(&class), Ok(Some(l)) if l.class.is_interface());
                    if interface { None } else { self.cp.superclass(&class) }
                };
                let value = above.map(|c| self.literal(path, Literal::Class(c), CLASS));
                self.push(path, Val::R(value));
                self.advance(path);
                return Some(Ok(None));
            }
            "getClassLoader" => {
                if !self.cp.is_application(&class) {
                    return None;
                }
                self.assumed.insert(CLASS_PATH_ASSUMPTION.to_string());
                self.literal(path, Literal::Loader, LOADER)
            }
            _ => return None,
        };
        self.push(path, Val::R(Some(value)));
        self.advance(path);
        Some(Ok(None))
    }

    /// `Class.isAssignableFrom(other)` on the class literal `o`: see the module's notes. `None` where the call stays
    /// the JDK's.
    pub(super) fn class_relation(&mut self, path: &mut Path, o: usize, name: &str, descriptor: &str, args: &[Val]) -> Option<Step> {
        if path.objects[o].class != CLASS { return None; }
        let [Val::R(other)] = args else { return None };
        let primitive = |at: usize| path.literals.iter().any(|(l, n)| *n == at && matches!(l, Literal::PrimitiveClass(_)));
        if !primitive(o) && self.class_named(path, o).is_none() { return None; }
        if primitive(o) || (name == "isAssignableFrom" && other.is_some_and(primitive)) {
            let truth = match (name, descriptor, other) {
                ("isInstance", "(Ljava/lang/Object;)Z", _) => FALSE,
                ("isAssignableFrom", "(Ljava/lang/Class;)Z", None) => return Some(self.raise(path, "java/lang/NullPointerException")),
                ("isAssignableFrom", "(Ljava/lang/Class;)Z", Some(p)) if primitive(*p) || self.class_named(path, *p).is_some() => if *p == o { TRUE } else { FALSE },
                _ => return None,
            };
            self.push_truth(path, truth);
            return Some(Ok(None));
        }
        let above = self.class_named(path, o)?;
        let below = match (name, descriptor, other) {
            ("isInstance", "(Ljava/lang/Object;)Z", None) => {
                self.push_truth(path, FALSE);
                return Some(Ok(None));
            }
            ("isInstance", "(Ljava/lang/Object;)Z", Some(other)) => {
                let obj = &path.objects[*other];
                if obj.assumed || obj.lambda.is_some() { return None; }
                obj.class.clone()
            }
            ("isAssignableFrom", "(Ljava/lang/Class;)Z", None) => return Some(self.raise(path, "java/lang/NullPointerException")),
            ("isAssignableFrom", "(Ljava/lang/Class;)Z", Some(other)) => self.class_named(path, *other)?,
            _ => return None,
        };
        // Resolve the leaf of an array literal as well. Primitive array descriptors
        // determine their type without a primitive Class mirror.
        let known = |cp: &ClassPath, class: &str| {
            if class.starts_with('[') {
                let element = class.trim_start_matches('[');
                return match element.strip_prefix('L').and_then(|s| s.strip_suffix(';')) {
                    Some(name) => cp.loads(name),
                    None => matches!(element, "B" | "S" | "C" | "I" | "J" | "F" | "D" | "Z"),
                };
            }
            cp.loads(class)
        };
        if !known(self.cp, &above) || !known(self.cp, &below) {
            return None;
        }
        let value = self.b.constant(i64::from(self.cp.is_subtype(&below, &above)), 32);
        self.push(path, Val::I(value));
        self.advance(path);
        Some(Ok(None))
    }

    /// A call of `java.util.logging` on the object `o` ([`models_logging`]; `owner` is the class the call names,
    /// `special` whether it is an `invokespecial`): see the module's notes. `None` where the call stays the JDK's.
    pub(super) fn logging_method(&mut self, path: &mut Path, o: usize, special: bool, owner: &str, name: &str, descriptor: &str, args: &[Val]) -> Option<Step> {
        let is = |path: &Path, at: usize, wanted: fn(&Literal) -> bool| path.literals.iter().any(|(l, &held)| held == at && wanted(l));
        // A record's constructor and setters, where the JDK's method is the one that runs.
        if self.cp.is_subtype(owner, LOG_RECORD) {
            let dispatched = if special { owner.to_string() } else { path.objects[o].class.clone() };
            let constructor = special && (owner, name, descriptor) == (LOG_RECORD, "<init>", "(Ljava/util/logging/Level;Ljava/lang/String;)V");
            if !(constructor || RECORD_SETTERS.contains(&(name, descriptor))) || self.cp.checker_method(&dispatched, name, descriptor).is_some() {
                return None;
            }
            if constructor && matches!(args.first(), Some(Val::R(None))) {
                return Some(self.raise(path, "java/lang/NullPointerException"));
            }
            self.advance(path);
            return Some(Ok(None));
        }
        if owner != LOGGER || !models_logging(owner, name, descriptor) || !is(path, o, |l| matches!(l, Literal::Logger(_))) {
            return None;
        }
        match (name, args) {
            ("isLoggable", [Val::R(Some(level))]) => {
                let logged = path.literals.iter().find_map(|(l, &held)| match l {
                    Literal::Level(name) if held == *level => Some(LOGGED.contains(name)),
                    _ => None,
                })?;
                self.assumed.insert(LOGGING_ASSUMPTION.to_string());
                let value = self.b.constant(i64::from(logged), 32);
                self.push(path, Val::I(value));
            }
            ("getResourceBundleName" | "getResourceBundle", []) => {
                self.assumed.insert(PUBLISHING_ASSUMPTION.to_string());
                self.push(path, Val::R(None));
            }
            ("log", [Val::R(None)]) => return Some(self.raise(path, "java/lang/NullPointerException")),
            ("log", [Val::R(Some(record))]) => {
                let class = path.objects[*record].class.clone();
                if !self.confined_record(&class) {
                    return None;
                }
                self.assumed.insert(LOGGING_ASSUMPTION.to_string());
                self.assumed.insert(PUBLISHING_ASSUMPTION.to_string());
                // The formatting ran the getters, which may have written the number fields of the record's own
                // classes, on this record or another the caller holds: each such field now holds any value.
                if let Err(stop) = self.formatted(path, &class) {
                    return Some(Err(stop));
                }
            }
            _ => return None,
        }
        self.advance(path);
        Some(Ok(None))
    }

    /// What logging a record of `class` (a [`Engine::confined_record`]) leaves: every object of the classes from
    /// `class` down to `LogRecord` (the record, or another the getters reach) holds any value in each number field
    /// those classes declare, since a getter the formatting called may have written it. Nothing else changes: those
    /// classes write no other field, no static and no array element.
    fn formatted(&mut self, path: &mut Path, class: &str) -> Result<(), Stop> {
        let chain: Vec<String> = std::iter::once(class.to_string()).chain(self.cp.superclasses(class)).take_while(|c| c != LOG_RECORD).collect();
        let mut fields = Vec::new();
        for c in &chain {
            let Ok(Some(cf)) = self.cp.bytecode(c) else { return unsupported(&format!("no class {c}")) };
            fields.extend(cf.fields.iter().filter(|f| !f.is_static()).map(|f| (c.clone(), f.name.clone(), f.descriptor.clone())));
        }
        for o in 0..path.objects.len() {
            let held = path.objects[o].class.clone();
            for (owner, name, descriptor) in &fields {
                if !self.cp.is_subtype(&held, owner) {
                    continue;
                }
                let key = self.field_key(path, o, owner, name, descriptor)?;
                let value = if descriptor == "J" { Val::J(self.b.fresh(64)) } else { Val::I(self.b.fresh(32)) };
                path.objects[o].fields.insert(key, value);
            }
        }
        Ok(())
    }

    /// Whether what the default handler calls on a record of `class` when it formats it (its getters, which a
    /// subclass may override) can do nothing a check observes beyond what [`Engine::formatted`] makes of it: the
    /// class is `LogRecord`, or an application class below it each of whose classes down from `LogRecord` has, in
    /// its methods other than its constructors and initializer (which the engine runs itself), no write of a static
    /// field or an array element, no `athrow`, no `invokedynamic` and no native method, reads only final static
    /// fields, writes only number fields (`int`, `boolean`, `byte`, `char`, `short`, `long`) of those classes, and
    /// calls only methods of those classes, of `LogRecord`, `Object`, `String` and `StackTraceElement`, and a
    /// `Throwable`'s constructors and getters. Spring's `LocationResolvingLogRecord` is such a class: it finds the
    /// caller in a new `Throwable`'s stack trace and keeps it in its own fields.
    ///
    /// The handler catches `Exception` around the formatting, and what else can leave a getter is a `Throwable` an
    /// `athrow` throws, which is why there is none, or an `Error` the JVM raises with no `athrow`. Of those, the
    /// scan refuses what the code itself decides: an array of a length other than a constant up to
    /// [`SMALL_ARRAY`] (an `OutOfMemoryError` for `new long[Integer.MAX_VALUE]`), and a call that can come back to
    /// itself through methods of those classes (a `StackOverflowError` for a recursion without end; every method of
    /// the name and descriptor called in those classes is taken as a callee, so an override counts). What is left is
    /// the JVM's own limits, a heap or a stack already all but full, which no check models anywhere. A field the
    /// getters write is one the caller may read after `log` (a record it holds), which is why each is any value
    /// afterwards and only number fields are taken: a reference written there would be any object.
    pub(super) fn confined_record(&self, class: &str) -> bool {
        use crate::classfile::Insn;
        let chain: Vec<String> = std::iter::once(class.to_string()).chain(self.cp.superclasses(class)).take_while(|c| c != LOG_RECORD).collect();
        if !self.cp.is_subtype(class, LOG_RECORD) || chain.iter().any(|c| !self.cp.is_application(c)) {
            return false;
        }
        let allowed = |owner: &str, name: &str| {
            chain.iter().any(|c| c == owner)
                || matches!(owner, LOG_RECORD | "java/lang/Object" | STRING | "java/lang/StackTraceElement")
                || owner == "java/lang/Throwable" && (name == "<init>" || name.starts_with("get"))
        };
        // The calls among the chain's own methods, by name and descriptor, for the recursion check below.
        let mut calls: BTreeMap<(String, String), BTreeSet<(String, String)>> = BTreeMap::new();
        let confined = chain.iter().all(|c| {
            let Ok(Some(cf)) = self.cp.bytecode(c) else { return false };
            cf.methods.iter().filter(|m| m.name != "<init>" && m.name != "<clinit>").all(|m| {
                if m.is_native() {
                    return false;
                }
                let Some(code) = &m.code else { return true };
                let Ok(insns) = code.instructions() else { return false };
                let mut targets: BTreeSet<u32> = insns.iter().flat_map(|(_, insn)| insn.targets()).collect();
                targets.extend(code.exception_table.iter().map(|h| u32::from(h.handler_pc)));
                let callees = calls.entry((m.name.clone(), m.descriptor.clone())).or_default();
                insns.iter().enumerate().all(|(at, (pc, insn))| match insn {
                    Insn::PutStatic(_) | Insn::ArrayStore(_) | Insn::InvokeDynamic(_) | Insn::AThrow | Insn::MultiANewArray(..) => false,
                    // The length, a constant pushed just before and not reached by a jump.
                    Insn::NewArray(_) | Insn::ANewArray(_) => {
                        !targets.contains(pc) && matches!(at.checked_sub(1).map(|i| &insns[i].1), Some(Insn::IConst(n)) if (0..=SMALL_ARRAY).contains(n))
                    }
                    Insn::GetStatic(i) => cf.pool.member(*i).is_ok_and(|f| {
                        self.cp.bytecode(&f.owner).ok().flatten().and_then(|owner| owner.field(&f.name).map(|d| d.is_static() && d.is_final())).unwrap_or(false)
                    }),
                    Insn::PutField(i) => cf.pool.member(*i).is_ok_and(|f| chain.iter().any(|c| *c == f.owner) && matches!(f.descriptor.as_str(), "I" | "Z" | "B" | "C" | "S" | "J")),
                    Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => cf.pool.member(*i).is_ok_and(|m| {
                        if chain.iter().any(|c| *c == m.owner) {
                            callees.insert((m.name.clone(), m.descriptor.clone()));
                        }
                        allowed(&m.owner, &m.name)
                    }),
                    _ => true,
                })
            })
        });
        // No call among them can come back to itself.
        confined
            && calls.keys().all(|start| {
                let mut seen = BTreeSet::new();
                let mut work: Vec<&(String, String)> = calls.get(start).into_iter().flatten().collect();
                while let Some(m) = work.pop() {
                    if m == start {
                        return false;
                    }
                    if seen.insert(m.clone()) {
                        work.extend(calls.get(m).into_iter().flatten());
                    }
                }
                true
            })
    }

    /// `Class.forName(name, false, loader)` and `Logger.getLogger(name)`: see the module's notes. `None` where
    /// the call stays the JDK's.
    pub(super) fn runtime_static(&mut self, path: &mut Path, owner: &str, name: &str, args: &[Val]) -> Option<Step> {
        match (owner, name, args) {
            ("java/lang/System", "lineSeparator", []) => {
                // Identity across calls is visible in the image: both load the same startup field.
                let loaded = self.cp.load(owner).ok()??;
                if loaded.origin != crate::classpath::Origin::Jdk { return None; }
                let code = loaded.class.method(name, "()Ljava/lang/String;")?.code.as_ref()?;
                let insns = code.instructions().ok()?;
                let [(_, Insn::GetStatic(i)), (_, Insn::Return(Some(Kind::Ref)))] = insns.as_slice() else { return None };
                let f = loaded.class.pool.member(*i).ok()?;
                if (f.owner.as_str(), f.name.as_str(), f.descriptor.as_str()) != (owner, name, "Ljava/lang/String;") { return None; }
                let o = self.literal(path, Literal::LineSeparator, STRING);
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            (BOOLEAN, "valueOf", [Val::I(word)]) => {
                let zero = self.b.is_zero(word);
                let yes = self.literal(path, Literal::Truth(true), BOOLEAN);
                let no = self.literal(path, Literal::Truth(false), BOOLEAN);
                let result = choice(&mut self.b, vec![(-zero, Some(yes)), (zero, Some(no))]);
                self.push(path, result);
                self.advance(path);
                Some(Ok(None))
            }
            ("java/lang/reflect/Array", "getLength", [Val::R(object)]) => {
                let Some(o) = *object else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                let obj = &path.objects[o];
                if !obj.is_array() {
                    if obj.assumed { return Some(self.of_unknown_class(path, o, "Array.getLength")); }
                    return Some(self.raise(path, "java/lang/IllegalArgumentException"));
                }
                let length = obj.array.as_ref().expect("an array").length.clone();
                self.push(path, Val::I(length));
                self.advance(path);
                Some(Ok(None))
            }
            ("java/lang/Integer", "valueOf", [Val::I(bits)]) => self.cached_integral(path, "java/lang/Integer", bits),
            (CLASS, "forName", [Val::R(named), rest @ ..]) => {
                // With a loader and no initialization, or by the caller's loader and with it.
                let initializes = match rest {
                    [Val::I(initialize), Val::R(Some(loader))] if self.b.constant_value(initialize) == Some(0) && path.literals.get(&Literal::Loader) == Some(loader) => false,
                    [] if self.cp.is_application(&path.frames.last().expect("a frame").class.name) => true,
                    _ => return None,
                };
                let Some(named) = *named else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                let text = String::from_utf16(&self.constant_units(path, named)?).ok()?;
                if text.starts_with('[') {
                    return None;
                }
                // A binary name has no `/`: one that does names no class.
                let mut internal = text.replace('.', "/");
                let mut found = !text.contains('/') && self.cp.exists(&internal);
                // In a pair of versions, the previous version's code finds its own classes, which the check holds
                // as copies, and none that only the new version has; the new version's finds no copy.
                if let Some(previous) = self.previous.clone() {
                    use crate::relocate::Found;
                    let caller = &path.frames.last().expect("a frame").class.name;
                    if previous.original(caller).is_some() {
                        match previous.find(&internal) {
                            Found::Class(held) => {
                                found = !text.contains('/') && self.cp.exists(&held);
                                internal = held;
                            }
                            Found::NotCopied => return None,
                            Found::Elsewhere => found = found && !self.cp.is_application(&internal),
                        }
                    } else if previous.original(&internal).is_some() {
                        found = false;
                    }
                }
                if found && (!self.cp.is_application(&internal) || !self.cp.loads(&internal)) {
                    return None;
                }
                self.assumed.insert(CLASS_PATH_ASSUMPTION.to_string());
                if !found {
                    return Some(self.raise(path, "java/lang/ClassNotFoundException"));
                }
                if initializes {
                    // The call runs again once an initializer it starts has returned, its argument where it was.
                    self.push(path, Val::R(Some(named)));
                    if let Some(step) = self.initialise(path, &internal) {
                        return Some(step);
                    }
                    if let Err(stop) = self.pop(path) {
                        return Some(Err(stop));
                    }
                }
                let o = self.literal(path, Literal::Class(internal), CLASS);
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            (PROXY, "isProxyClass", [Val::R(class)]) => {
                let Some(class) = *class else { return Some(self.raise(path, "java/lang/NullPointerException")) };
                self.class_named(path, class)?;
                let no = self.b.constant(0, 32);
                self.push(path, Val::I(no));
                self.advance(path);
                Some(Ok(None))
            }
            (COLLECTIONS, "emptySet", []) if self.cp.collections_empty_singleton("emptySet") => {
                let o = self.literal(path, Literal::CollectionsEmptySet, "java/util/Collections$EmptySet");
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            (COLLECTIONS, "emptyList", []) if self.cp.collections_empty_singleton("emptyList") => {
                let o = self.literal(path, Literal::CollectionsEmptyList, throwables::EMPTY_LIST);
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            (COLLECTIONS, "emptyMap", []) => {
                let o = self.literal(path, Literal::EmptyMap, EMPTY_MAP);
                self.push(path, Val::R(Some(o)));
                self.advance(path);
                Some(Ok(None))
            }
            (THREAD, "currentThread", []) => {
                let o = self.literal(path, Literal::Thread, THREAD);
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
