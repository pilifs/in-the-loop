//! The JVM's own objects a class initializer asks for: a class by its name, its loader, a logger.
//!
//! Library code probes its surroundings before it does anything else: Spring's `LogFactory.getLog(DataBinder.class)`
//! asks `Class.forName` for Log4j and SLF4J, each absent from a class path that has neither, and then
//! `java.util.logging.Logger.getLogger` for a logger it keeps in a static field. These are answers about the run's
//! class path and the JDK, which the engine has: each is modelled where the answer is one, under an assumption the
//! run states ([`CLASS_PATH_ASSUMPTION`]), and stays the JDK call it was elsewhere.
//!
//! - `Object.getClass()` of an object of an application class that the run made with `new`, or of a `Throwable`
//!   the run made (with `new`, or the engine for the JVM or a model of a JDK method, as `athrow`'s handlers already
//!   take it): that class's literal, the one object a class literal of it is (JLS §15.8.2). Of any other object (an
//!   array, a lambda's, a JDK class's) it is the JDK call it was.
//! - `Class.getName()` of a class literal: the class's binary name, the interned String (the JVM interns it).
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
//!   its formatting throws. Formatting calls the record's getters, a subclass's overrides included, so a record of a
//!   class that could write elsewhere from one of them stays the JDK call. A level, a handler, a filter or a bundle
//!   set on a Logger is a call of it no model takes, so a check that sets one stops there.
//! - `new ArrayList()`: the JDK's no-argument constructor only sets the list's own fields, so the object is made
//!   as any object with no content is, its methods the JDK calls they were.
//! - `new ConcurrentHashMap()` and `new ConcurrentHashMap(int)`: likewise (the JDK allocates the table at the first
//!   entry), the second with its `IllegalArgumentException` for a negative capacity. A library makes such maps as
//!   caches in a constructor, and a path that never asks one anything goes on.

use super::*;

/// What a run that asked for a class by name, or for a class's loader, took for granted.
pub const CLASS_PATH_ASSUMPTION: &str = "the classes of the check's class path are loaded by one class loader, which finds the classes of that class path and of the JDK and no other: a class neither has is not found (Class.forName throws ClassNotFoundException)";

/// What a run that asked the current thread for its context class loader took for granted.
pub const CONTEXT_LOADER_ASSUMPTION: &str = "the check runs on one thread, whose context class loader is the class loader of the check's class path: nothing has set another (Thread.setContextClassLoader), as on a JVM started with that class path";

/// What a run that asked a logger whether a level is logged took for granted.
pub const LOGGING_ASSUMPTION: &str = "java.util.logging is configured as the JDK configures it by default: no logging configuration file or class is named, and nothing sets a logger's level, so each logger's level is the root's, INFO, and nothing below INFO is logged (Logger.isLoggable is false for CONFIG, FINE, FINER, FINEST and ALL, and true for INFO, WARNING and SEVERE)";

/// What a run that gave a logger a record to log took for granted.
pub const PUBLISHING_ASSUMPTION: &str = "a record given to a logger goes to the handler the JDK's default logging configuration gives the root logger and nowhere else: no logger has a filter, a handler of its own or a resource bundle, and the root's one handler is a ConsoleHandler, which writes the record to System.err (no check observes it) and reports to its ErrorManager, without throwing, an exception its formatting throws";

/// The levels of `java.util.logging.Level` below `INFO`, by their fields' names.
const BELOW_INFO: [&str; 5] = ["CONFIG", "FINE", "FINER", "FINEST", "ALL"];
/// The levels at `INFO` and above that a logger of the default configuration logs (`OFF` is not one: its value is
/// above every level, and `isLoggable(OFF)` is true too, which no library asks).
const LOGGED: [&str; 3] = ["INFO", "WARNING", "SEVERE"];
pub(super) const LEVEL: &str = "java/util/logging/Level";
const LOG_RECORD: &str = "java/util/logging/LogRecord";

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
const COLLECTIONS: &str = "java/util/Collections";
pub(super) const EMPTY_MAP: &str = "java/util/Collections$EmptyMap";
const FOR_NAME: &str = "(Ljava/lang/String;)Ljava/lang/Class;";

/// Whether the engine models the static call here, where its arguments let it.
pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!(
        (owner, name, descriptor),
        (CLASS, "forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;" | FOR_NAME) | (LOGGER, "getLogger", "(Ljava/lang/String;)Ljava/util/logging/Logger;") | (THREAD, "currentThread", "()Ljava/lang/Thread;") | (COLLECTIONS, "emptyMap", "()Ljava/util/Map;")
    )
}

/// Whether the engine models the instance call here, on a class literal, or `getClass()` on an object it made.
pub fn models_instance(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!(
        (owner, name, descriptor),
        (CLASS, "getName", "()Ljava/lang/String;")
            | (CLASS, "getSuperclass", "()Ljava/lang/Class;")
            | (CLASS, "getClassLoader", "()Ljava/lang/ClassLoader;")
            | (CLASS, "isAssignableFrom", "(Ljava/lang/Class;)Z")
            | ("java/lang/Object", "getClass", "()Ljava/lang/Class;")
            | (THREAD, "getContextClassLoader", "()Ljava/lang/ClassLoader;")
    )
}

/// The JDK constructors that only set their object's own fields, throw nothing and take nothing: the object is
/// made as one with no content.
pub fn plain_constructor(owner: &str, descriptor: &str) -> bool {
    matches!((owner, descriptor), ("java/util/ArrayList" | CONCURRENT_MAP, "()V"))
}

const CONCURRENT_MAP: &str = "java/util/concurrent/ConcurrentHashMap";

/// The JDK constructors that take an initial capacity and nothing else, and only set their object's own fields:
/// `IllegalArgumentException` for a negative capacity, and otherwise the object made as one with no content.
pub fn capacity_constructor(owner: &str, descriptor: &str) -> bool {
    matches!((owner, descriptor), (CONCURRENT_MAP, "(I)V"))
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

    /// `Class.getName()`, `Class.getSuperclass()` and `Class.getClassLoader()` on the object `o`, and `getClass()` on it: see the module's
    /// notes. `None` where the call stays the JDK's.
    pub(super) fn class_method(&mut self, path: &mut Path, o: usize, owner: &str, name: &str, descriptor: &str) -> Option<Step> {
        if (name, descriptor) == ("getClass", "()Ljava/lang/Class;") {
            let class = path.objects[o].class.clone();
            // A Throwable the run made (with `new`, or the engine for the JVM or a model) is of the class it was
            // made as, whoever made it: a handler already takes it for that class.
            let made_throwable = !path.objects[o].given && class.contains('/') && self.cp.loads(&class) && self.cp.is_subtype(&class, "java/lang/Throwable");
            if class.starts_with('[') || path.objects[o].lambda.is_some() || !(self.cp.is_application(&class) || made_throwable) {
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
        if path.objects[o].class != CLASS || !models_instance(owner, name, descriptor) || name == "isAssignableFrom" {
            return None;
        }
        let class = self.class_named(path, o)?;
        let value = match name {
            "getName" => {
                // A copy of a class of the previous version of a pair has that class's own name.
                let own = self.previous.as_ref().and_then(|p| p.original(&class)).unwrap_or(&class);
                let units: Vec<u16> = own.replace('/', ".").encode_utf16().collect();
                self.literal(path, Literal::Str(units), STRING)
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
            _ => {
                if !self.cp.is_application(&class) {
                    return None;
                }
                self.assumed.insert(CLASS_PATH_ASSUMPTION.to_string());
                self.literal(path, Literal::Loader, LOADER)
            }
        };
        self.push(path, Val::R(Some(value)));
        self.advance(path);
        Some(Ok(None))
    }

    /// `Class.isAssignableFrom(other)` on the class literal `o`: see the module's notes. `None` where the call stays
    /// the JDK's.
    pub(super) fn class_relation(&mut self, path: &mut Path, o: usize, name: &str, descriptor: &str, args: &[Val]) -> Option<Step> {
        if path.objects[o].class != CLASS || (name, descriptor) != ("isAssignableFrom", "(Ljava/lang/Class;)Z") {
            return None;
        }
        let [Val::R(other)] = args else { return None };
        let above = self.class_named(path, o)?;
        let Some(other) = *other else { return Some(self.raise(path, "java/lang/NullPointerException")) };
        let below = self.class_named(path, other)?;
        // A class or an interface by its internal name, with everything above it at hand: no primitive type
        // (`int` has no `/`, and neither has a class of the unnamed package, which is left to the JDK with it)
        // and no array.
        let known = |cp: &ClassPath, class: &str| class.contains('/') && !class.starts_with('[') && cp.loads(class);
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
            }
            _ => return None,
        }
        self.advance(path);
        Some(Ok(None))
    }

    /// Whether what the default handler calls on a record of `class` when it formats it (its getters, which a
    /// subclass may override) can do nothing a check observes: the class is `LogRecord`, or an application class
    /// below it each of whose classes down from `LogRecord` has, in its methods other than its constructors and
    /// initializer (which the engine runs itself), no write of a static field or an array element, no
    /// `invokedynamic` and no native method, reads only final static fields, writes only fields of those classes,
    /// and calls only methods of those classes, of `LogRecord`, `Object`, `String` and `StackTraceElement`, and a
    /// `Throwable`'s constructors and getters. Spring's `LocationResolvingLogRecord` is such a class: it finds the
    /// caller in a new `Throwable`'s stack trace and keeps it in its own fields.
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
        chain.iter().all(|c| {
            let Ok(Some(cf)) = self.cp.bytecode(c) else { return false };
            cf.methods.iter().filter(|m| m.name != "<init>" && m.name != "<clinit>").all(|m| {
                if m.is_native() {
                    return false;
                }
                let Some(code) = &m.code else { return true };
                let Ok(insns) = code.instructions() else { return false };
                insns.into_iter().all(|(_, insn)| match insn {
                    Insn::PutStatic(_) | Insn::ArrayStore(_) | Insn::InvokeDynamic(_) => false,
                    Insn::GetStatic(i) => cf.pool.member(i).is_ok_and(|f| {
                        self.cp.bytecode(&f.owner).ok().flatten().and_then(|owner| owner.field(&f.name).map(|d| d.is_static() && d.is_final())).unwrap_or(false)
                    }),
                    Insn::PutField(i) => cf.pool.member(i).is_ok_and(|f| chain.iter().any(|c| *c == f.owner)),
                    Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => cf.pool.member(i).is_ok_and(|m| allowed(&m.owner, &m.name)),
                    _ => true,
                })
            })
        })
    }

    /// `Class.forName(name, false, loader)` and `Logger.getLogger(name)`: see the module's notes. `None` where
    /// the call stays the JDK's.
    pub(super) fn runtime_static(&mut self, path: &mut Path, owner: &str, name: &str, args: &[Val]) -> Option<Step> {
        match (owner, name, args) {
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
