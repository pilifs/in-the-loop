//! An exception's message and cause, where the engine saw the JDK's constructor set them.
//!
//! The JDK's exceptions are opaque to the engine: `new IllegalStateException(message)` was reproduced exactly as a
//! call that changes nothing a proof observes, and the message was dropped. A library that records an error reads
//! it back (Spring's binder keeps `ex.getLocalizedMessage()` as a binding error's default message, and its
//! `NestedRuntimeException.getMessage` appends the cause's `toString()`), so the engine keeps what the constructor
//! set, where it can say exactly what that is:
//!
//! - `Throwable()`, `Throwable(String)` and `Throwable(String, Throwable)` set the message (null for the first) and
//!   the cause (none, which the JDK writes as the object itself, for the first two). A constructor of a JDK class
//!   below `Throwable` with one of those descriptors is taken for `Throwable`'s where its bytecode, and that of every
//!   class between it and `Throwable`, is only the call of its superclass's constructor of the same descriptor with
//!   its own arguments ([`plain_constructor`]). An application class's constructor runs as bytecode, and reaches
//!   these when it calls `super`.
//! - `Throwable`'s constructors call `fillInStackTrace()` on the object, virtually. Where an application class
//!   overrides it, the JVM runs that override inside the constructor, which the engine does not: the constructor
//!   is refused by name.
//! - `addSuppressed` and `getSuppressed` execute the selected JDK bodies, including validation, disabled suppression,
//!   append order and the shared empty array. The private list retains the exception references across path joins.
//! - `getMessage()`, `getCause()`, `getLocalizedMessage()` and `toString()` are modelled on an exception whose
//!   message and cause the engine kept, where the method the JVM runs is `Throwable`'s own ([`ClassPath::find_method`]
//!   from the receiver's class, or from the class an `invokespecial` names). `getLocalizedMessage()` is
//!   `getMessage()` called virtually: an application override runs as bytecode in its place. `toString()` is the
//!   class's name, then `": "` and the localized message where it is not null, and is modelled only where neither
//!   of the two message methods is overridden.
//! - `Object.getClass()` of an object of a JDK class below `Throwable` that no JDK call returned: its class is the
//!   one `new` or the engine's own throw named ([`super::runtime`]).
//! - An exception constructed while running a JDK bytecode model retains its class. Reading its detail message,
//!   localized message, cause or text refuses the observation because the model supplied the constructor arguments.
//! - `StringBuilder.append(Object)` of such an exception appends its `toString()` as above, of a String its units,
//!   and of null `null`; of any other object it is the JDK call it was ([`super::strings`]).
//!
//! Elsewhere (an exception a JDK call made or threw, one whose class overrides a message method in the JDK, or a
//! contract given for the call) each method is the JDK call it was, a gap.

use super::*;

/// `java.lang.Throwable`.
pub const THROWABLE: &str = "java/lang/Throwable";

/// Where an exception the engine kept the message of holds it: a key no field of a class can have, as a field's
/// name has no `/` ([`ClassPath::field_key`] gives a hidden field its declaring class and a `.`, never this form).
const MESSAGE: &str = "java/lang/Throwable#detailMessage";

/// Where it holds the cause: the object itself for none, as the JDK's `Throwable.cause` does.
const CAUSE: &str = "java/lang/Throwable#cause";

/// Private JDK fields have a separate key even when an application subclass hides their names.
pub(crate) const SUPPRESSED: &str = "java/lang/Throwable#suppressedExceptions";
const ENABLE_SUPPRESSION: &str = "java/lang/Throwable#enableSuppression";
pub(crate) const EMPTY_LIST: &str = "java/util/Collections$EmptyList";
pub(super) const THROWABLE_ARRAY: &str = "[Ljava/lang/Throwable;";

/// The calling JDK model chose the constructor arguments. The real JDK can supply different details.
const MODEL_DETAILS: &str = "java/lang/Throwable#modelDetails";

/// The descriptors of `Throwable`'s constructors whose effect the engine keeps.
const CONFIGURED: &str = "(Ljava/lang/String;Ljava/lang/Throwable;ZZ)V";
const KEPT: [&str; 3] = ["()V", "(Ljava/lang/String;)V", "(Ljava/lang/String;Ljava/lang/Throwable;)V"];

const GET_MESSAGE: (&str, &str) = ("getMessage", "()Ljava/lang/String;");
const GET_LOCALIZED_MESSAGE: (&str, &str) = ("getLocalizedMessage", "()Ljava/lang/String;");
const FILL_IN: (&str, &str) = ("fillInStackTrace", "()Ljava/lang/Throwable;");

/// Whether the JDK's constructor `owner.<init>(descriptor)` sets the message and the cause as `Throwable`'s of that
/// descriptor does, and nothing else: `owner` is `Throwable`, or a JDK class whose constructor's code is exactly
/// `aload_0`, its arguments in order, `invokespecial` of its superclass's constructor of the same descriptor and
/// `return`, with no handler, and the same holds of that superclass. Between the call and the `return` it may have
/// the JDK's flight-recorder hook ([`traces_only`]), which `java.lang.Error`'s constructors have since JDK 25.
pub fn plain_constructor(cp: &ClassPath, owner: &str, descriptor: &str) -> bool {
    let arguments = match descriptor {
        CONFIGURED => 4,
        _ => match KEPT.iter().position(|d| *d == descriptor) {
            Some(n) => n,
            None => return false,
        },
    };
    // With no JDK image the bytecode is not there to read: the built-in facts say which are plain.
    if !cp.has_jdk() {
        return crate::jdk_facts::plain_throwable_constructor(owner, arguments);
    }
    let mut class = owner.to_string();
    for _ in 0..32 {
        if class == THROWABLE {
            return true;
        }
        if !crate::classpath::is_jdk_name(&class) {
            return false;
        }
        let Ok(Some(loaded)) = cp.load(&class) else { return false };
        let cf = &loaded.class;
        let (Some(code), Some(above)) = (cf.method("<init>", descriptor).and_then(|m| m.code.as_ref()), cf.super_class.clone()) else { return false };
        let Ok(insns) = code.instructions() else { return false };
        if !code.exception_table.is_empty() || insns.len() < arguments + 3 {
            return false;
        }
        let loads = insns.iter().take(arguments + 1).enumerate().all(|(i, (_, insn))| {
            let kind = if i >= 3 { Kind::Int } else { Kind::Ref };
            matches!(insn, Insn::Load(k, n) if *k == kind && usize::from(*n) == i)
        });
        let calls = matches!(&insns[arguments + 1].1, Insn::InvokeSpecial(index) if cf.pool.member(*index).is_ok_and(|m| m.owner == above && m.name == "<init>" && m.descriptor == descriptor));
        let rest: Vec<&Insn> = insns[arguments + 2..].iter().map(|(_, i)| i).collect();
        let returns = match rest.as_slice() {
            [Insn::Return(None)] => true,
            [hook @ .., Insn::Return(None)] => traces_only(cf, hook, arguments, insns[arguments + 2..].last().map(|(pc, _)| *pc)),
            _ => false,
        };
        if !loads || !calls || !returns {
            return false;
        }
        class = above;
    }
    false
}

/// Whether `hook` is exactly the flight recorder's hook of a JDK 25 `Error` constructor, which changes nothing a
/// proof observes: `if (Throwable.jfrTracing) ThrowableTracer.traceError(getClass(), message)`, with null for no
/// message, its `ifeq` jumping to the `return` at `end`.
fn traces_only(cf: &ClassFile, hook: &[&Insn], arguments: usize, end: Option<u32>) -> bool {
    let member = |index: &u16, owner: &str, name: &str, descriptor: &str| cf.pool.member(*index).is_ok_and(|m| m.owner == owner && m.name == name && m.descriptor == descriptor);
    let message_ok = |insn: &Insn| if arguments == 0 { matches!(insn, Insn::AConstNull) } else { matches!(insn, Insn::Load(Kind::Ref, 1)) };
    match hook {
        [Insn::GetStatic(flag), Insn::If(Cond::Eq, to), Insn::Load(Kind::Ref, 0), Insn::InvokeVirtual(class), message, Insn::InvokeStatic(trace)] => {
            member(flag, THROWABLE, "jfrTracing", "Z")
                && Some(*to) == end
                && member(class, "java/lang/Object", "getClass", "()Ljava/lang/Class;")
                && message_ok(message)
                && member(trace, "jdk/internal/event/ThrowableTracer", "traceError", "(Ljava/lang/Class;Ljava/lang/String;)V")
        }
        _ => false,
    }
}

/// Whether the method the JVM runs for `name(descriptor)`, looked up from `class`, is `Throwable`'s own.
fn throwables_own(cp: &ClassPath, class: &str, (name, descriptor): (&str, &str)) -> bool {
    cp.find_method(class, name, descriptor).is_some_and(|(cf, _)| cf.name == THROWABLE)
}

/// Whether `class` is a JDK class at or below `Throwable`.
pub fn jdk_throwable(cp: &ClassPath, class: &str) -> bool {
    crate::classpath::is_jdk_name(class) && cp.is_subtype(class, THROWABLE)
}

impl Engine<'_> {
    /// These VM or library failures have a known class. Keep unqualified diagnostic
    /// messages and causes opaque to later observers.
    pub(super) fn throw_class_only(&mut self, path: &mut Path, class: &str) -> Step {
        let object = self.alloc(path, class);
        path.objects[object].fields.insert(MODEL_DETAILS.into(), Val::R(None));
        self.throw(path, object)
    }
    /// The selected Class.getDeclaredField throws new NoSuchFieldException(name) on a miss.
    pub(super) fn missing_declared_field(&mut self, path: &mut Path, name: usize) -> Step {
        let object = self.alloc(path, "java/lang/NoSuchFieldException");
        path.objects[object].fields.insert(MESSAGE.into(), Val::R(Some(name)));
        path.objects[object].fields.insert(CAUSE.into(), Val::R(Some(object)));
        self.throw(path, object)
    }

    /// The first failed initialization wraps the original non-Error throwable with a null detail message.
    pub(super) fn initialization_error(&mut self, path: &mut Path, cause: usize) -> usize {
        let wrapper = self.alloc(path, "java/lang/ExceptionInInitializerError");
        path.objects[wrapper].fields.insert(MESSAGE.into(), Val::R(None));
        path.objects[wrapper].fields.insert(CAUSE.into(), Val::R(Some(cause)));
        wrapper
    }

    /// A constructor or a message method of `Throwable` on the object `o`: see the module's notes. `None` where the
    /// call stays the JDK's.
    pub(super) fn throwable_method(&mut self, path: &mut Path, o: usize, special: bool, member: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        let class = path.objects[o].class.clone();
        if member.name == "<init>" {
            if !special || !plain_constructor(self.cp, &member.owner, &member.descriptor) {
                return None;
            }
            let fills_stack = !matches!(args.get(3), Some(Val::I(writable)) if self.b.constant_value(writable) == Some(0));
            if let Some((cf, _)) = self.cp.find_method(&class, FILL_IN.0, FILL_IN.1).filter(|(cf, _)| fills_stack && cf.name != THROWABLE && self.cp.is_application(&cf.name)) {
                return Some(unsupported(format!("{}.<init>{} on an object of {}, whose {}.fillInStackTrace() the JVM runs inside the constructor, which the engine does not", member.owner.replace('/', "."), member.descriptor, class.replace('/', "."), cf.name.replace('/', "."))));
            }
            if let Err(stop) = self.keeps(path, Some(o), "writes a field of an object made before it was called") {
                return Some(Err(stop));
            }
            let (message, cause) = match args {
                [] => (Val::R(None), Val::R(Some(o))),
                [m] => (m.clone(), Val::R(Some(o))),
                [m, c] | [m, c, Val::I(_), Val::I(_)] => (m.clone(), c.clone()),
                _ => return None,
            };
            if self.cp.has_models() && path.frames.iter().any(|frame| self.cp.runs_model(&frame.class.name)) {
                path.objects[o].fields.insert(MODEL_DETAILS.to_string(), Val::R(None));
            } else {
                if let Some(flag) = args.get(2) {
                    path.objects[o].fields.insert(ENABLE_SUPPRESSION.into(), flag.clone());
                }
                path.objects[o].fields.insert(MESSAGE.to_string(), message);
                path.objects[o].fields.insert(CAUSE.to_string(), cause);
            }
            self.advance(path);
            return Some(Ok(None));
        }
        let from = if special { member.owner.clone() } else { class.clone() };
        let method = (member.name.as_str(), member.descriptor.as_str());
        if path.objects[o].fields.contains_key(MODEL_DETAILS)
            && matches!(method, GET_MESSAGE | GET_LOCALIZED_MESSAGE | ("getCause", "()Ljava/lang/Throwable;") | ("toString", "()Ljava/lang/String;"))
        {
            return Some(unsupported(format!("{}.{} reads exception details supplied by a JDK model; the JDK's message and cause are unqualified", class.replace('/', "."), member.name)));
        }
        // The explicit non-null message takes the JDK's superclass branch. VM-generated
        // helpful NPE messages can consult native stack state and stay outside this profile.
        let npe = "java/lang/NullPointerException";
        if method == GET_MESSAGE && matches!(path.objects[o].fields.get(MESSAGE), Some(Val::R(Some(_))))
            && self.cp.find_method(&from, method.0, method.1).is_some_and(|(cf, _)| cf.name == npe)
            && self.cp.throwable_image_method(npe, method.0, method.1).is_some() {
            return Some(self.call(path, npe, method.0, method.1, vec![Val::R(Some(o))]));
        }
        if !path.objects[o].fields.contains_key(CAUSE) || !throwables_own(self.cp, &from, method) {
            return None;
        }
        if self.cp.throwable_image_method(THROWABLE, method.0, method.1).is_some() {
            // Initialize the private field on first use. Its absence on an opaque throwable
            // is never evidence of an empty list: the constructor check above must pass.
            if !path.objects[o].fields.contains_key(SUPPRESSED) {
                let sentinel = self.literal(path, Literal::CollectionsEmptyList, EMPTY_LIST);
                let initial = match path.objects[o].fields.get(ENABLE_SUPPRESSION) {
                    Some(Val::I(flag)) => {
                        let disabled = self.b.is_zero(flag);
                        choice(&mut self.b, vec![(disabled, None), (-disabled, Some(sentinel))])
                    }
                    _ => Val::R(Some(sentinel)),
                };
                path.objects[o].fields.insert(SUPPRESSED.into(), initial);
            }
            let mut full = vec![Val::R(Some(o))];
            full.extend_from_slice(args);
            return Some(self.call(path, THROWABLE, method.0, method.1, full));
        }
        match method {
            GET_MESSAGE => {
                let message = match self.kept(path, o, true)? {
                    Ok(v) => v,
                    Err(step) => return Some(step),
                };
                self.push(path, message);
            }
            ("getCause", "()Ljava/lang/Throwable;") => {
                let cause = match self.kept(path, o, false)? {
                    Ok(Val::R(Some(c))) if c == o => Val::R(None),
                    Ok(other) => other,
                    Err(step) => return Some(step),
                };
                self.push(path, cause);
            }
            GET_LOCALIZED_MESSAGE => {
                // `getMessage()`, virtually: an override the check runs is called in this call's place.
                if let Some((cf, m)) = self.cp.checker_method(&class, GET_MESSAGE.0, GET_MESSAGE.1).filter(|(cf, _)| self.cp.checker_runs(&cf.name)) {
                    if m.code.is_none() {
                        return None;
                    }
                    return Some(self.call(path, &cf.name, GET_MESSAGE.0, GET_MESSAGE.1, vec![Val::R(Some(o))]));
                }
                if !throwables_own(self.cp, &class, GET_MESSAGE) {
                    return None;
                }
                let message = match self.kept(path, o, true)? {
                    Ok(v) => v,
                    Err(step) => return Some(step),
                };
                self.push(path, message);
            }
            ("toString", "()Ljava/lang/String;") => {
                let text = match self.throwable_text(path, o)? {
                    Ok(text) => text,
                    Err(step) => return Some(step),
                };
                let r = match text {
                    Text::Name(units) => self.literal(path, Literal::Str(units), STRING),
                    Text::Joined(s) => self.new_string(path, s.length, s.cells, Vec::new()),
                };
                self.push(path, Val::R(Some(r)));
            }
            _ => return None,
        }
        self.advance(path);
        Some(Ok(None))
    }

    /// The message (`message`) or the cause the engine kept of the exception `o`, read as the JDK's method reads
    /// its field. `None` where it is not one known reference (a merge of paths left a choice), which the JDK call
    /// then stays; `Some(Err)` where the read is refused.
    fn kept(&mut self, path: &mut Path, o: usize, message: bool) -> Option<Result<Val, Step>> {
        let (key, name, descriptor) = if message { (MESSAGE, "detailMessage", "Ljava/lang/String;") } else { (CAUSE, "cause", "Ljava/lang/Throwable;") };
        let value = path.objects[o].fields.get(key).cloned()?;
        if !matches!(value, Val::R(_)) {
            return None;
        }
        // A method proved to read nothing that was there before its call reads no exception that was.
        if let Err(stop) = self.reads_field(path, o, THROWABLE, name, descriptor) {
            return Some(Err(Err(stop)));
        }
        Some(Ok(value))
    }

    /// What `toString()` of the exception `o` gives, where it is `Throwable`'s and the engine kept the message:
    /// `None` where it is the JDK call, `Some(Err)` where reading the message ends the path.
    pub(super) fn throwable_text(&mut self, path: &mut Path, o: usize) -> Option<Result<Text, Step>> {
        let class = path.objects[o].class.clone();
        if path.objects[o].fields.contains_key(MODEL_DETAILS) {
            return Some(Err(unsupported(format!("{}.toString reads exception details supplied by a JDK model; the JDK's message is unqualified", class.replace('/', ".")))));
        }
        if !path.objects[o].fields.contains_key(CAUSE) || ![("toString", "()Ljava/lang/String;"), GET_LOCALIZED_MESSAGE, GET_MESSAGE].iter().all(|m| throwables_own(self.cp, &class, *m)) {
            return None;
        }
        // A copy of a class of the previous version of a pair has that class's own name ([`super::runtime`]).
        let own = self.previous.as_ref().and_then(|p| p.original(&class)).unwrap_or(&class);
        let name: Vec<u16> = own.replace('/', ".").encode_utf16().collect();
        let message = match self.kept(path, o, true)? {
            Ok(Val::R(message)) => message,
            Ok(_) => return None,
            Err(step) => return Some(Err(step)),
        };
        let Some(m) = message else { return Some(Ok(Text::Name(name))) };
        let units = match self.string_argument(path, Some(m), (THROWABLE, "toString", "()Ljava/lang/String;")) {
            Ok(units) => units,
            Err(step) => return Some(Err(step)),
        };
        let head: Vec<u16> = name.iter().copied().chain(": ".encode_utf16()).collect();
        let head = Array { element: Type::Char, length: self.b.constant(head.len() as i64, 32), cells: head.iter().map(|u| self.b.constant(i64::from(*u), 16)).collect(), refs: Vec::new() };
        Some(Ok(Text::Joined(self.joined(&head, &units))))
    }
}

/// What an exception's `toString()` is: its class's name alone (the String `Class.getName()` returns, the JVM's
/// interned one), or a new String of the name, `": "` and the message.
pub(super) enum Text {
    Name(Vec<u16>),
    Joined(Array),
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A JDK exception's constructor is `Throwable`'s where it only passes its arguments up, with JDK 25's flight
    /// recorder hook in `Error`'s, and a gap where it does more: `UnknownFormatConversionException(String)` throws
    /// for null, `ClassNotFoundException(String)` calls another constructor.
    #[test]
    fn a_jdk_exceptions_constructor_is_throwables_where_it_only_passes_its_arguments_up() {
        let cp = ClassPath::new().with_default_jdk();
        if !cp.has_jdk() {
            return;
        }
        for (owner, descriptor) in [
            ("java/lang/IllegalStateException", KEPT[1]),
            ("java/lang/RuntimeException", KEPT[2]),
            ("java/lang/IllegalArgumentException", KEPT[0]),
            ("java/lang/AssertionError", KEPT[0]),
            ("java/lang/Error", KEPT[1]),
            ("java/lang/Error", KEPT[2]),
            ("java/lang/Throwable", KEPT[1]),
        ] {
            assert!(plain_constructor(&cp, owner, descriptor), "{owner}.<init>{descriptor}");
            assert!(gaps::exact_jdk_call(&cp, owner, "<init>", descriptor), "{owner}.<init>{descriptor}");
        }
        for (owner, descriptor) in [("java/util/UnknownFormatConversionException", KEPT[1]), ("java/lang/ClassNotFoundException", KEPT[1]), ("java/lang/IllegalStateException", "(Ljava/lang/Throwable;)V")] {
            assert!(!plain_constructor(&cp, owner, descriptor), "{owner}.<init>{descriptor}");
            assert!(!gaps::exact_jdk_call(&cp, owner, "<init>", descriptor), "{owner}.<init>{descriptor}");
        }
        assert!(jdk_throwable(&cp, "java/lang/IllegalStateException") && !jdk_throwable(&cp, "java/lang/String"));
        // What the built-in facts say for a run with no image is what the image's bytecode says.
        for (class, arguments) in crate::jdk_facts::plain_throwable_constructors() {
            assert!(plain_constructor(&cp, class, KEPT[arguments]), "{class}.<init>{}", KEPT[arguments]);
        }
        let bare = ClassPath::new();
        assert!(!bare.has_jdk());
        assert!(plain_constructor(&bare, "java/lang/AssertionError", KEPT[0]) && !plain_constructor(&bare, "java/util/UnknownFormatConversionException", KEPT[1]));
    }
}
