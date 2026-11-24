//! The JVM's own objects a class initializer asks for: a class by its name, its loader, a logger.
//!
//! Library code probes its surroundings before it does anything else: Spring's `LogFactory.getLog(DataBinder.class)`
//! asks `Class.forName` for Log4j and SLF4J, each absent from a class path that has neither, and then
//! `java.util.logging.Logger.getLogger` for a logger it keeps in a static field. These are answers about the run's
//! class path and the JDK, which the engine has: each is modelled where the answer is one, under an assumption the
//! run states ([`CLASS_PATH_ASSUMPTION`]), and stays the JDK call it was elsewhere.
//!
//! - `Object.getClass()` of an object of an application class that the run made with `new`, a String, an object
//!   of a final class in the selected JDK image, or a `Throwable` the run made and no JDK call returned (with `new`, or the engine for the JVM or a
//!   model of a JDK method, as `athrow`'s handlers already take it; its class is the one `new` or the engine's own
//!   throw named, [`super::throwables`]): that class's literal, the one object a class literal of it is (JLS
//!   §15.8.2). A successful JVM `new` instruction also fixes the runtime class of an object
//!   whose fields use a library model, including a mutable map viewed through its interface.
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
//! - Both regression harnesses hold copies of the previous version under another package beside the new
//!   version's classes ([`crate::relocate::Previous`]). A copy's
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
const SEPARATOR_EQUALS: &str = "<JVM.equalsInitialLineSeparator>";
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
pub fn property_call(owner: &str, name: &str, descriptor: &str) -> bool {
    const ONE: &str = "(Ljava/lang/String;)Ljava/lang/String;";
    const TWO: &str = "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;";
    owner == "java/lang/System" && matches!((name, descriptor),
        ("getProperty" | "clearProperty", ONE) | ("getProperty" | "setProperty", TWO)
        | ("getProperties", "()Ljava/util/Properties;") | ("setProperties", "(Ljava/util/Properties;)V"))
}

pub(crate) const LIVE_TABLE: &str = "<JVM.installedProperties>";

/// On the qualified image System checks the key and permissions, then invokes one of
/// these methods on the installed table. The two writes cast the returned Object to String.
pub(crate) fn properties_delegate(name: &str, arity: usize) -> Option<(&'static str, &'static str, bool)> {
    Some(match (name, arity) {
        ("getProperty", 1) => ("getProperty", "(Ljava/lang/String;)Ljava/lang/String;", false),
        ("getProperty", 2) => ("getProperty", "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;", false),
        ("setProperty", 2) => ("setProperty", "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/Object;", true),
        ("clearProperty", 1) => ("remove", "(Ljava/lang/Object;)Ljava/lang/Object;", true),
        _ => return None,
    })
}

pub const REENTRANT_LOCK: &str = "java/util/concurrent/locks/ReentrantLock";
pub(super) const REGISTERED_QUEUE: &str = "<JVM.originalReferenceQueue>";
pub const HOLD_COUNT: &str = "<JVM.reentrantHoldCount>";

pub fn sequential_lock_call(owner: &str, name: &str, descriptor: &str) -> bool {
    owner == REENTRANT_LOCK && matches!((name, descriptor),
        ("<init>" | "lock" | "unlock", "()V") | ("tryLock" | "isHeldByCurrentThread" | "isLocked", "()Z") | ("getHoldCount", "()I"))
}

/// The hold-count write and primitive return in a completed single-thread operation.
pub fn sequential_lock_transition(name: &str, count: i32) -> Option<(Option<i32>, Option<i32>)> {
    Some(match name {
        "<init>" => (Some(0), None),
        "lock" => (Some(count.checked_add(1)?), None),
        "tryLock" => (Some(count.checked_add(1)?), Some(1)),
        "unlock" if count > 0 => (Some(count - 1), None),
        "getHoldCount" => (None, Some(count)),
        "isHeldByCurrentThread" | "isLocked" => (None, Some(i32::from(count != 0))),
        _ => return None,
    })
}

pub fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    if property_call(owner, name, descriptor) { return true; }
    if (owner, name, descriptor) == ("java/lang/Integer", "valueOf", "(I)Ljava/lang/Integer;") { return true; }
    matches!(
        (owner, name, descriptor),
        ("java/lang/System", "lineSeparator", "()Ljava/lang/String;") | (COLLECTIONS, "emptyList", "()Ljava/util/List;") | (COLLECTIONS, "emptySet", "()Ljava/util/Set;") |
        (BOOLEAN, "valueOf", "(Z)Ljava/lang/Boolean;") | ("java/lang/reflect/Array", "getLength", "(Ljava/lang/Object;)I")
        | ("java/lang/reflect/Array", "newInstance", "(Ljava/lang/Class;I)Ljava/lang/Object;") | (CLASS, "forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;" | FOR_NAME) | (LOGGER, "getLogger", "(Ljava/lang/String;)Ljava/util/logging/Logger;") | (THREAD, "currentThread", "()Ljava/lang/Thread;") | (COLLECTIONS, "emptyMap", "()Ljava/util/Map;") | (PROXY, "isProxyClass", "(Ljava/lang/Class;)Z")
    )
}

fn canonical_truth(path: &Path, object: usize) -> Option<bool> {
    [true, false].into_iter().find(|v| path.literals.get(&Literal::Truth(*v)) == Some(&object))
}

/// If a property read starts a static initializer, its value can sometimes be
/// observed only by null, emptiness and equality to literals. Check the whole
/// suffix, including every branch and write, before choosing representatives.
fn property_comparisons(frame: &Frame) -> Option<std::collections::BTreeSet<Vec<u16>>> {
    use Insn::*;
    let [Ldc(_), InvokeStatic(_), Store(Kind::Ref, slot), tail @ ..] = frame.code.insns.as_slice() else { return None };
    if frame.at != 1 || frame.method != "<clinit>" || !frame.code.handlers.is_empty() { return None; }
    let mut literals = std::collections::BTreeSet::from([Vec::new()]);
    for (i, insn) in tail.iter().enumerate() {
        if insn.targets().iter().any(|pc| *pc <= frame.code.pcs[i + 3]) { return None; }
        match insn {
            Load(Kind::Ref, local) if local == slot => {}
            Ldc(index) => { literals.insert(frame.class.pool.loadable(*index).ok()?.string_units()?.into_owned()); }
            InvokeVirtual(index) => {
                let call = frame.class.pool.member(*index).ok()?;
                if call.owner != STRING || !matches!((call.name.as_str(), call.descriptor.as_str()),
                    ("isEmpty", "()Z") | ("equals", "(Ljava/lang/Object;)Z")) { return None; }
            }
            PutStatic(index) => {
                let field = frame.class.pool.member(*index).ok()?;
                if field.owner != frame.class.name || field.descriptor != "Z" { return None; }
            }
            IConst(0 | 1) | IfNull(_) | IfNonNull(_) | If(_, _) | Goto(_) | Return(None) => {}
            _ => return None,
        }
    }
    Some(literals)
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
            | (CLASS, "cast", "(Ljava/lang/Object;)Ljava/lang/Object;")
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
    /// Content comparisons partition a single immutable startup value. Keep an open
    /// remainder for every untested string, including an empty or custom separator.
    pub(super) fn separator_equals(&mut self, path: &mut Path, a: usize, b: usize) -> Option<Step> {
        let &separator = path.literals.get(&Literal::LineSeparator)?;
        let other = if a == separator { b } else if b == separator { a } else { return None };
        let answer = if other == separator {
            Val::I(self.b.constant(1, 32))
        } else {
            let units = self.constant_units(path, other)?;
            let literal = self.literal(path, Literal::Str(units), STRING);
            if let Some(eq) = path.objects[literal].fields.get(SEPARATOR_EQUALS) { eq.clone() } else {
                let mut bit = self.b.var();
                for &id in path.literals.values() {
                    if let Some(Val::I(other)) = path.objects[id].fields.get(SEPARATOR_EQUALS) {
                        bit = self.b.and(bit, -other[0]);
                    }
                }
                let value = Val::I(self.b.zext(&vec![bit], 32));
                path.objects[literal].fields.insert(SEPARATOR_EQUALS.into(), value.clone());
                value
            }
        };
        path.unbound_platform_value = Some(LINE_SEPARATOR);
        self.push(path, answer);
        self.advance(path);
        Some(Ok(None))
    }

    /// Materialize code units only once the caller's own guard entails equality.
    /// The object's external reference identity remains opaque on every branch.
    pub(super) fn resolve_separator(&mut self, path: &mut Path, o: usize) -> Result<(), Stop> {
        if path.objects[o].limit.as_deref() != Some(LINE_SEPARATOR) || path.objects[o].content().is_some() { return Ok(()); }
        for &id in path.literals.values() {
            let Some(Val::I(word)) = path.objects[id].fields.get(SEPARATOR_EQUALS) else { continue };
            let mut no = path.cond.clone();
            no.push(-word[0]);
            if !self.solve(&no)? {
                path.objects[o].array = path.objects[id].array.clone();
                break;
            }
        }
        Ok(())
    }

    pub(super) fn identity_hash(&mut self, path: &mut Path, object: usize) -> Val {
        // An alias observes the same word. Different objects may collide, including at zero.
        path.unbound_platform_value = Some("a JVM-chosen identity hash");
        path.objects[object].fields.entry("<JVM.identityHashCode>".into())
            .or_insert_with(|| Val::I(self.b.fresh(32))).clone()
    }

    pub(super) fn object_hash(&mut self, path: &mut Path, object: usize, special: bool, m: &crate::classfile::MemberRef) -> Option<Step> {
        if m.name != "hashCode" || m.descriptor != "()I" || path.objects[object].assumed || path.objects[object].unknown { return None; }
        let loader = path.literals.get(&Literal::Loader) == Some(&object);
        let class = &path.objects[object].class;
        if !special && !loader && class != "java/lang/Object" && class != "java/lang/Class"
            && !self.cp.is_application(class) { return None; }
        let lookup = if special { &m.owner } else if loader { "jdk/internal/loader/ClassLoaders$AppClassLoader" }
            else { &path.objects[object].class };
        let (declaring, method) = self.cp.find_method(lookup, &m.name, &m.descriptor)?;
        if declaring.name != "java/lang/Object" || !method.is_native() { return None; }
        if loader {
            self.assumed.insert("the application loader is the JDK's ordinary AppClassLoader with inherited Object.hashCode".into());
        }
        let word = self.identity_hash(path, object);
        self.push(path, word);
        self.advance(path);
        Some(Ok(None))
    }
    /// An exact freshly created lock on the native engine's single executing thread.
    /// Thread starts stay outside this rule. Nonstandard receivers, symbolic
    /// exceptional states and unsupported operations keep their own diagnostics.
    pub(super) fn sequential_lock(&mut self, path: &mut Path, o: usize, name: &str) -> Step {
        if !self.cp.is_subtype(&path.objects[o].class, REENTRANT_LOCK) || path.objects[o].assumed {
            return unsupported("a reentrant lock without a known implementation");
        }
        if name != "<init>" && self.there_before(path, o) { self.reads(path, || "reads a pre-existing lock's hold count".into())?; }
        let count = if name == "<init>" { 0 } else {
            match path.objects[o].fields.get(HOLD_COUNT) {
                Some(Val::I(word)) => match self.b.constant_value(word) {
                    Some(count) => count,
                    None => return self.symbolic_lock(path, o, name, word.clone()),
                },
                _ => return unsupported("a lock whose initial hold count is unknown"),
            }
        };
        let Some((write, returned)) = sequential_lock_transition(name, count as i32) else {
            return unsupported("an unbalanced unlock or excessive recursion on a reentrant lock");
        };
        if let Some(next) = write {
            self.keeps(path, Some(o), "changes a reentrant lock's hold count")?;
            path.objects[o].fields.insert(HOLD_COUNT.into(), Val::I(self.b.constant(i64::from(next), 32)));
        }
        if let Some(v) = returned { self.push(path, Val::I(self.b.constant(i64::from(v), 32))); }
        self.advance(path);
        Ok(None)
    }

    fn symbolic_lock(&mut self, path: &mut Path, o: usize, name: &str, count: Bits) -> Step {
        let zero = self.b.eq(&count, &self.b.constant(0, 32));
        let one = self.b.constant(1, 32);
        match name {
            "getHoldCount" => self.push(path, Val::I(count)),
            "isHeldByCurrentThread" | "isLocked" => self.push(path, Val::I(self.b.zext(&vec![-zero], 32))),
            "lock" | "tryLock" | "unlock" => {
                let releasing = name == "unlock";
                let invalid = if releasing { zero } else { self.b.eq(&count, &self.b.constant(i32::MAX.into(), 32)) };
                let mut cond = path.cond.clone();
                cond.push(invalid);
                if self.solve(&cond)? { return unsupported("a possible unbalanced unlock or excessive recursion on a reentrant lock"); }
                self.keeps(path, Some(o), "changes a reentrant lock's hold count")?;
                let next = if releasing { self.b.sub(&count, &one) } else { self.b.add(&count, &one) };
                path.objects[o].fields.insert(HOLD_COUNT.into(), Val::I(next));
                if name == "tryLock" { self.push(path, Val::I(one)); }
            }
            _ => return unsupported("an unknown reentrant lock operation"),
        }
        self.advance(path);
        Ok(None)
    }
    /// The property reference goes straight into String.equals. The caller can
    /// observe only the boolean, so equality to the receiver partitions all values.
    fn immediate_property_comparison(&self, path: &Path, frame: &Frame) -> Option<std::collections::BTreeSet<Vec<u16>>> {
        let Insn::InvokeVirtual(index) = frame.code.insns.get(frame.at + 1)? else { return None };
        let member = frame.class.pool.member(*index).ok()?;
        if (member.owner.as_str(), member.name.as_str(), member.descriptor.as_str())
            != (STRING, "equals", "(Ljava/lang/Object;)Z") || !self.contracts.is_empty() { return None; }
        // invoke_static has already taken the property key off the operand stack.
        let Val::R(Some(receiver)) = frame.stack.last()? else { return None };
        if path.objects[*receiver].class != STRING { return None; }
        Some(std::collections::BTreeSet::from([Vec::new(), self.constant_units(path, *receiver)?]))
    }

    fn compared_property(&mut self, path: &mut Path, key: &str) -> Option<Val> {
        let frame = path.frames.last()?;
        let literals = property_comparisons(frame).or_else(|| self.immediate_property_comparison(path, frame))?;
        let owner = format!("<JVM.propertyComparisons>{key}");
        let slot = (owner.clone(), serde_json::to_string(&literals).ok()?);
        if let Some(value) = path.statics.get(&slot) { return Some(value.clone()); }
        // A second, different partition would require refinement of its earlier representative.
        if path.statics.keys().any(|(domain, _)| domain == &owner) { return None; }
        let mut other = vec![0u16];
        while literals.contains(&other) { other.push(0); }
        let mut options = vec![];
        let mut remaining = TRUE;
        for units in literals.into_iter().chain([other]) {
            let selected = self.b.var();
            let guard = self.b.and(remaining, selected);
            let string = self.literal(path, Literal::Str(units), STRING);
            options.push((guard, Some(string)));
            remaining = self.b.and(remaining, -selected);
        }
        options.push((remaining, None));
        let value = choice(&mut self.b, options);
        path.statics.insert(slot, value.clone());
        path.unbound_platform_value = Some("an initially unspecified JVM system property");
        Some(value)
    }
    /// A property explicitly set or cleared on this path has a known reference
    /// (possibly null). Application code may ignore the old value on its first
    /// write. An unobserved initial setting never becomes an invented String.
    fn property_call(&mut self, path: &mut Path, name: &str, args: &[Val]) -> Option<Step> {
        let table_slot = (LIVE_TABLE.to_owned(), "current".to_owned());
        if name == "setProperties" {
            let [Val::R(Some(table))] = args else { return None };
            let object = &path.objects[*table];
            if object.class != "java/util/Properties" || !object.fields.contains_key(super::map_views::PROPERTIES_IMAGE)
                || !self.cp.system_properties_image() { return None; }
            if let Err(stop) = self.keeps(path, None, "replaces the JVM system properties") { return Some(Err(stop)); }
            path.statics.insert(table_slot, Val::R(Some(*table)));
            self.assumed.insert("the single-threaded JVM has no active SecurityManager during system property access".into());
            self.advance(path);
            return Some(Ok(None));
        }
        if name == "getProperties" {
            // An ambient table can have arbitrary entries, aliases, defaults, and an overriding class.
            let table = path.statics.get(&table_slot)?.clone();
            if let Err(stop) = self.reads(path, || "reads the installed JVM properties object".into()) { return Some(Err(stop)); }
            self.push(path, table);
            self.advance(path);
            return Some(Ok(None));
        }
        let Val::R(key) = args.first()? else { return None };
        let key = (*key)?;
        let units = self.constant_units(path, key)?;
        if units.is_empty() { return None; }
        if let Some(table) = path.statics.get(&table_slot) {
            let Val::R(Some(table)) = table else { return None };
            let table = *table;
            let (member, descriptor, write) = properties_delegate(name, args.len())?;
            let permission = if write { self.keeps(path, None, "changes the installed JVM properties") }
                else { self.reads(path, || "reads the installed JVM properties".into()) };
            if let Err(stop) = permission { return Some(Err(stop)); }
            let (class, method) = self.cp.properties_method("java/util/Properties", "java/util/Properties", member, descriptor, false)?;
            if write {
                let caller = path.frames.last_mut()?;
                if caller.lambda_return != LambdaReturn::Pass { return None; }
                caller.lambda_return = LambdaReturn::Adapt(Type::object("java/lang/Object"), Type::object(STRING));
            }
            let mut full = vec![Val::R(Some(table))];
            full.extend_from_slice(args);
            return Some(self.enter_method(path, "java/util/Properties", class, method, full));
        }
        let slot = ("<JVM.systemProperties>".to_owned(), String::from_utf16(&units).ok()?);
        let previous = path.statics.get(&slot).cloned();
        let result = if name == "getProperty" {
            let value = previous.or_else(|| (args.len() == 1).then(|| self.compared_property(path, &slot.1)).flatten())?;
            if let Err(stop) = self.reads(path, || "reads a mutable system property".into()) { return Some(Err(stop)); }
            if let Some(Val::R(fallback)) = args.get(1) {
                let options = value.options()?.into_iter().map(|(guard, v)| (guard, v.or(*fallback))).collect();
                choice(&mut self.b, options)
            } else { value }
        } else {
            let value = match (name, args.get(1)) {
                ("clearProperty", None) => Val::R(None),
                ("setProperty", Some(v @ Val::R(Some(_)))) => v.clone(),
                _ => return None,
            };
            let frame = path.frames.last()?;
            let ignored = frame.lambda_return == super::LambdaReturn::Discard || matches!(frame.code.insns.get(frame.at + 1), Some(Insn::Pop));
            if previous.is_none() && !ignored { return None; }
            if let Err(stop) = self.keeps(path, None, "changes a JVM system property") { return Some(Err(stop)); }
            path.statics.insert(slot, value);
            previous.unwrap_or(Val::R(None))
        };
        self.assumed.insert("system properties use the standard JVM Properties table and the running JVM permits this property access".into());
        self.push(path, result);
        self.advance(path);
        Some(Ok(None))
    }
    /// Materialize only a range the solver proves contains every possible value on this path.
    /// Outside the mandatory cache the selected JDK's factory decides what it constructs.
    pub(super) fn cached_integral(&mut self, path: &mut Path, class: &'static str, word: &Bits) -> Option<Step> {
        let minimum = if class == "java/lang/Character" { 0 } else { i8::MIN };
        if class == "java/lang/Integer" && path.statics.contains_key(&("java/lang/Integer$IntegerCache".into(), "<symbolic>".into())) {
            return self.symbolic_integer(path, word);
        }
        let boxed = if let Some(n) = self.b.constant_value(word) {
            if class == "java/lang/Integer" && i8::try_from(n).is_err() {
                return self.wide_integer(path, word, i32::try_from(n).ok()?);
            }
            let n = i8::try_from(n).ok().filter(|n| *n >= minimum)?;
            Val::R(Some(self.literal(path, Literal::CachedIntegral(class, i32::from(n)), class)))
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
            if range.is_none() && class == "java/lang/Integer" { return self.symbolic_integer(path, word); }
            let mut choices = Vec::new();
            for n in range? {
                let guard = self.b.eq(word, &self.b.constant(i64::from(n), word.len()));
                choices.push((guard, Some(self.literal(path, Literal::CachedIntegral(class, i32::from(n)), class))));
            }
            choice(&mut self.b, choices)
        };
        self.push(path, boxed);
        self.advance(path);
        Some(Ok(None))
    }

    /// The selected JDK's Long.valueOf has taken its mandatory cache branch.
    /// Its next instructions index by (int)value + 128 and return that box.
    /// Reuse the same canonical entries the ordinary boxed-constant model uses.
    pub(super) fn long_cache_return(&mut self, path: &mut Path) -> Option<Step> {
        let frame = path.frames.last()?;
        let next = frame.at + 1;
        if frame.class.name != "java/lang/Long" || frame.method != "valueOf"
            || frame.lambda_return != LambdaReturn::Pass || !frame.stack.is_empty()
            || frame.code.descriptor != "(J)Ljava/lang/Long;"
            || !matches!(frame.code.insns.get(next..)?,
                [Insn::Load(Kind::Long,0), Insn::Convert(Kind::Long,Narrow::To(Kind::Int)), Insn::IConst(128),
                 Insn::Arith(ArithOp::Add,Kind::Int), Insn::ArrayLoad(ArrayKind::Ref), Insn::Return(Some(Kind::Ref)), ..])
            || self.is_observed("java/lang/Long$LongCache")
            || !self.cp.load("java/lang/Long").ok().flatten().is_some_and(|c| c.origin == crate::classpath::Origin::Jdk) {
            return None;
        }
        let Val::J(word) = frame.locals.first()?.as_ref()?.clone() else { return None; };
        let below = self.b.slt(&word, &self.b.constant(-128, 64));
        let above = self.b.slt(&self.b.constant(127, 64), &word);
        let mut outside = path.cond.clone();
        outside.push(self.b.or(below, above));
        match self.solve(&outside) {
            Ok(false) => {}
            Ok(true) => return None,
            Err(stop) => return Some(Err(stop)),
        }
        let step = self.cached_integral(path, "java/lang/Long", &word)?;
        if matches!(step, Ok(None)) {
            // Leave the original areturn to deliver the canonical reference to its caller.
            path.frames.last_mut().expect("Long.valueOf").at = next + 5;
        }
        Some(step)
    }

    /// Materialize the cache entries a path asks for, even when the key is an arbitrary
    /// int. For each concrete assignment the oldest candidate with equal value is the
    /// cached object. Outside the single VM-wide cache interval every call allocates.
    fn symbolic_integer(&mut self, path: &mut Path, word: &Bits) -> Option<Step> {
        const INTEGER: &str = "java/lang/Integer";
        const CACHE: &str = "java/lang/Integer$IntegerCache";
        const ENTRIES: &str = "<Integer.valueOf entries>";
        if word.len() != 32 || self.previous.is_some() || self.pure.is_some() || self.frame.is_some() { return None; }
        let marker = (CACHE.into(), "<symbolic>".into());
        if !path.statics.contains_key(&marker) {
            if !self.cp.known_integer_cache() { return None; }
            for (index, &object) in path.literals.iter().filter_map(|(key, o)|
                matches!(key, Literal::CachedIntegral(INTEGER, _)).then_some(o)).enumerate() {
                path.statics.insert((ENTRIES.into(), format!("{index:08}")), Val::R(Some(object)));
            }
            path.statics.insert(marker, Val::I(self.b.constant(1, 32)));
        }
        let mut entries = Vec::new();
        let candidates = path.statics.range((ENTRIES.to_string(), String::new())..);
        for (_, value) in candidates.take_while(|((owner, _), _)| owner == ENTRIES) {
            let Val::R(Some(object)) = value else { return Some(unsupported("merged symbolic Integer cache entries")); };
            let Some(Val::I(bits)) = path.objects[*object].fields.get("value") else { return Some(unsupported("unbound Integer cache entry")); };
            entries.push((*object, bits.clone()));
        }
        let fresh = self.alloc(path, INTEGER);
        path.objects[fresh].fields.insert("value".into(), Val::I(word.clone()));
        if !entries.iter().any(|(_, bits)| bits == word) {
            if entries.len() >= 512 { return Some(unsupported("more than 512 distinct Integer cache candidates on one path")); }
            path.statics.insert((ENTRIES.into(), format!("{:08}", entries.len())), Val::R(Some(fresh)));
        }
        let mut cached = Val::R(Some(fresh));
        for (object, bits) in entries.iter().rev() {
            let equal = self.b.eq(word, bits);
            if equal != FALSE { cached = choose(&mut self.b, equal, &Val::R(Some(*object)), &cached)?; }
        }
        let high = path.statics.entry((CACHE.into(), "<qualified-high>".into())).or_insert_with(|| Val::I(self.b.fresh(32)));
        let Val::I(high) = high else { return Some(unsupported("unbound Integer cache cutoff")); };
        let below = self.b.slt(word, &self.b.constant(-128, 32));
        let above_mandatory = self.b.slt(&self.b.constant(127, 32), word);
        let above_vm = self.b.slt(high, word);
        let above = self.b.and(above_mandatory, above_vm);
        let outside = self.b.or(below, above);
        let value = choose(&mut self.b, outside, &Val::R(Some(fresh)), &cached)?;
        path.unbound_platform_value = Some("the JVM's Integer cache limit");
        self.push(path, value);
        self.advance(path);
        Some(Ok(None))
    }

    /// The selected JDKs allow their Integer cache to extend above 127. Keep one VM-wide cutoff
    /// across calls and values. A claim about a stored number can then hold for either identity.
    fn wide_integer(&mut self, path: &mut Path, word: &Bits, n: i32) -> Option<Step> {
        let slot = ("java/lang/Integer$IntegerCache".to_string(), "<qualified-high>".to_string());
        if !path.statics.contains_key(&slot) {
            if !self.cp.known_integer_cache() { return None; }
            path.statics.insert(slot.clone(), Val::I(self.b.fresh(32)));
        }
        let fresh = self.alloc(path, "java/lang/Integer");
        path.objects[fresh].fields.insert("value".into(), Val::I(word.clone()));
        let boxed = if n < -128 {
            Val::R(Some(fresh))
        } else {
            let Val::I(high) = path.statics.get(&slot)? else { return None };
            let above = self.b.slt(high, word);
            let cached = self.literal(path, Literal::CachedIntegral("java/lang/Integer", n), "java/lang/Integer");
            path.unbound_platform_value = Some("the JVM's Integer cache limit");
            choose(&mut self.b, above, &Val::R(Some(fresh)), &Val::R(Some(cached))).expect("two boxed references")
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
        if (owner, name, descriptor) == (super::bytes::CHARSET, "newDecoder", "()Ljava/nio/charset/CharsetDecoder;")
            && path.literals.get(&Literal::Charset("UTF_8")) == Some(&o) && path.objects[o].class == "sun/nio/cs/UTF_8" {
            let loaded = self.cp.load("sun/nio/cs/UTF_8").ok()??;
            if !matches!(loaded.origin, crate::classpath::Origin::Jdk) { return None; }
            let method = loaded.class.method(name, descriptor)?.clone();
            let body = method.code.as_ref()?;
            let insns = body.instructions().ok()?;
            let [(_, Insn::New(c)), (_, Insn::Dup), (_, Insn::Load(Kind::Ref, 0)), (_, Insn::InvokeSpecial(m)), (_, Insn::Return(Some(Kind::Ref)))] = insns.as_slice() else { return None };
            let target = loaded.class.pool.member(*m).ok()?;
            if !body.exception_table.is_empty() || loaded.class.pool.class_name(*c).ok()? != "sun/nio/cs/UTF_8$Decoder"
                || (target.owner.as_str(), target.name.as_str(), target.descriptor.as_str()) != ("sun/nio/cs/UTF_8$Decoder", "<init>", "(Ljava/nio/charset/Charset;)V") { return None; }
            return Some(self.enter_method(path, owner, loaded.class, method, vec![Val::R(Some(o))]));
        }
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
            if path.objects[o].class != "java/lang/Integer" { return None; }
            let Val::I(value) = path.objects[o].fields.get("value")?.clone() else { return None };
            self.push(path, Val::I(value));
            self.advance(path);
            return Some(Ok(None));
        }
        if (owner, name, descriptor) == (CLASS, "desiredAssertionStatus", "()Z") {
            let class = self.class_named(path, o)?;
            let frame = path.frames.last()?;
            let image_host = self.cp.state_image_class(&class).is_some()
                || (frame.class.name.starts_with(&format!("{class}$")) && self.cp.load(&class).ok().flatten()
                    .is_some_and(|loaded| matches!(loaded.origin, crate::classpath::Origin::Jdk)));
            if frame.method != "<clinit>" { return None; }
            let own_prologue = self.cp.is_application(&frame.class.name) && self.cp.is_application(&class)
                && frame.class.method("<clinit>", "()V")?.code.as_ref()?.instructions().ok()
                    .and_then(|ops| super::gaps::assertion_prologue(&frame.class, &ops)) == Some(frame.pc());
            if !own_prologue && (self.cp.state_image_class(&frame.class.name).is_none() || !image_host) { return None; }
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
            let list_storage = class == "java/util/ArrayList" && !self.cp.runs_model(&class) && o_.fields.contains_key("elementData");
            let image = self.cp.load(&class).ok().flatten().filter(|c| c.origin == crate::classpath::Origin::Jdk);
            let allocated = o_.bytecode_new && image.as_ref().is_some_and(|c| !c.class.is_abstract() && !c.class.is_interface());
            let image_object = !o_.assumed && !self.there_before(path, o) && (allocated || list_storage || o_.fields.contains_key(map_views::IMAGE)
                || o_.initialized_big_number() || self.cp.state_image_class(&class).is_some());
            let final_image_class = !o_.assumed && image.is_some_and(|loaded| loaded.class.is_final());
            // javac 8 emits dup/getClass/pop before capturing a bound method reference. The JVM
            // has already checked this concrete receiver for null. No hidden class mirror escapes.
            let caller = path.frames.last()?;
            if o_.lambda.is_some() && caller.lambda_return == LambdaReturn::Pass
                && matches!(caller.code.insns.get(caller.at), Some(Insn::InvokeVirtual(_)))
                && matches!(caller.code.insns.get(caller.at + 1), Some(Insn::Pop)) {
                self.advance(path);
                self.advance(path);
                return Some(Ok(None));
            }
            if o_.lambda.is_some() || !(array || image_object || final_image_class || self.cp.is_application(&class) || class == STRING || exception) {
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
                let units: Vec<u16> = crate::relocate::binary_name(&class, self.cp.previous.as_deref().or(self.previous.as_deref())).encode_utf16().collect();
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
        if matches!(name, "cast" | "cannotCastMsg") {
            let (cf, method) = self.cp.library_image_method(CLASS, name, descriptor)?;
            return Some(self.enter_method(path, CLASS, cf, method, vec![Val::R(Some(o)), Val::R(*other)]));
        }
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
        if owner == "java/lang/System" && matches!(name, "getProperty" | "setProperty" | "clearProperty" | "getProperties" | "setProperties") {
            return self.property_call(path, name, args);
        }
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
            ("java/lang/reflect/Array", "newInstance", [Val::R(component), Val::I(count)]) => {
                let Some(component) = component else { return Some(self.raise(path, "java/lang/NullPointerException")); };
                let name = self.class_named(path, *component)?;
                let element = if name.starts_with('[') {
                    if name.bytes().take_while(|c| *c == b'[').count() >= 255 {
                        return Some(unsupported("reflective array allocation above 255 dimensions"));
                    }
                    Type::parse(&name).ok()?
                } else {
                    if !self.cp.loads(&name) { return None; }
                    Type::object(&name)
                };
                Some(self.new_reference_array(path, element, count.clone()))
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
                if let Some(previous) = self.cp.previous.as_ref().or(self.previous.as_ref()) {
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
                // Released libraries check for VarHandle before selecting their byte-array implementation.
                // The qualified bootstrap image supplies the class under the engine's stated JDK startup.
                let bootstrap_view = internal == super::byte_views::HANDLE && self.gap_mode == GapMode::Strict
                    && self.cp.byte_array_view_image();
                if found && !bootstrap_view && (!self.cp.is_application(&internal) || !self.cp.loads(&internal)) {
                    return None;
                }
                self.assumed.insert(CLASS_PATH_ASSUMPTION.to_string());
                if !found {
                    return Some(self.raise(path, "java/lang/ClassNotFoundException"));
                }
                if initializes && !bootstrap_view {
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
