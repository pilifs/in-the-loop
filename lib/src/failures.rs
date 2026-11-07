//! What becomes of each exception an entry point throws. Spring resolves it at request time: the `@ExceptionHandler`
//! that takes it (the controller's own first, then the `@ControllerAdvice` beans in order, the closest type
//! winning within one), else the `@ResponseStatus` on the exception's class, else the status a
//! `ResponseStatusException` carries, else nothing, which is a 500 from the container's error page. So a new
//! exception type with no handler, or a handler whose parameter type the exception no longer extends, compiles,
//! starts, passes the service's tests, and is found by the first request that fails.
//!
//! The exceptions themselves come from the reach graph ([`crate::reach::Graph::throws`]). What a `@KafkaListener`
//! or a `@Scheduled` method throws is listed without an outcome: the error handler of its container decides,
//! and the configuration of that is not read.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::rc::Rc;

use crate::boundaries::pushing;
use crate::classfile::{Annotation, ClassFile, ElementValue, Insn, Method, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::reach::{base_type, display};

const HTTP_STATUS: &str = "org/springframework/http/HttpStatus";
const RESPONSE_STATUS: &str = "org/springframework/web/bind/annotation/ResponseStatus";
const EXCEPTION_HANDLER: &str = "org/springframework/web/bind/annotation/ExceptionHandler";
const ADVICES: &[&str] = &["org/springframework/web/bind/annotation/ControllerAdvice", "org/springframework/web/bind/annotation/RestControllerAdvice"];
const CARRIERS: &[&str] = &["org/springframework/web/server/ResponseStatusException", "org/springframework/web/ErrorResponseException"];

/// One `@ExceptionHandler` method: the exception types it takes and the status it answers with, when that is
/// an `@ResponseStatus` on it or an `HttpStatus` constant (or a literal code) its body passes on.
pub struct Handler {
    pub method: String,
    pub types: Vec<String>,
    pub status: Option<u16>,
}

/// A `@ControllerAdvice` bean: its handlers, its `@Order`, and the controllers it applies to (all, when it
/// names no packages, types or annotations).
struct Advice {
    class: String,
    order: i64,
    handlers: Vec<Handler>,
    packages: Vec<String>,
    assignable: Vec<String>,
    annotations: Vec<String>,
}

impl Advice {
    fn applies_to(&self, cp: &ClassPath, controller: &str, controller_annotations: &[String]) -> bool {
        if self.packages.is_empty() && self.assignable.is_empty() && self.annotations.is_empty() {
            return true;
        }
        let package = controller.rsplit_once('/').map_or("", |(p, _)| p);
        self.packages.iter().any(|p| package == p || package.starts_with(&format!("{p}/")))
            || self.assignable.iter().any(|t| cp.is_subtype(controller, t))
            || self.annotations.iter().any(|a| controller_annotations.contains(a))
    }
}

/// The module's exception handlers: those declared in controllers (by class) and those in advices, in the order
/// Spring consults them.
#[derive(Default)]
pub struct Handlers {
    local: HashMap<String, Vec<Handler>>,
    advices: Vec<Advice>,
}

/// What a thrown exception becomes.
#[derive(Debug, PartialEq, Eq)]
pub enum Outcome {
    /// An `@ExceptionHandler` takes it: the status it answers with, when known, and `Class.method`.
    Handled { status: Option<u16>, by: String },
    /// `@ResponseStatus` on the exception's class (or a superclass) gives the status.
    Marked(u16),
    /// A `ResponseStatusException` with the status it was built with, when that is a constant.
    Carried(Option<String>),
    /// Nothing takes it: a 500.
    Unmapped,
}

impl Handlers {
    /// The handlers in the local classes.
    pub fn collect(cp: &ClassPath, classes: &BTreeMap<String, Rc<ClassFile>>, local: Option<&BTreeSet<String>>) -> Handlers {
        let mut out = Handlers::default();
        for (name, class) in classes {
            if local.is_some_and(|l| !l.contains(name)) || class.is_interface() {
                continue;
            }
            let Ok(class_annotations) = class.annotations() else { continue };
            let advice = class_annotations.iter().find(|a| ADVICES.contains(&a.type_name.as_str()));
            let mut handlers = Vec::new();
            for method in &class.methods {
                let Ok(annotations) = method.annotations(&class.pool) else { continue };
                let Some(h) = annotations.iter().find(|a| a.type_name == EXCEPTION_HANDLER) else { continue };
                let mut types = h.classes("value");
                types.extend(h.classes("exception"));
                if types.is_empty() {
                    if let Ok(d) = MethodDescriptor::parse(&method.descriptor) {
                        types.extend(d.params.iter().filter_map(|p| match p {
                            Type::Object(t) if cp.is_subtype(t, "java/lang/Throwable") => Some(t.clone()),
                            _ => None,
                        }));
                    }
                }
                let status = annotations.iter().find(|a| a.type_name == RESPONSE_STATUS).and_then(response_status).or_else(|| status_in_body(class, method));
                handlers.push(Handler { method: method.name.clone(), types, status });
            }
            match advice {
                Some(a) => {
                    let order = class_annotations.iter().find(|a| a.type_name == "org/springframework/core/annotation/Order").and_then(|a| match a.element("value") {
                        Some(ElementValue::Int(v)) => Some(*v),
                        _ => None,
                    });
                    let mut packages = a.strings("basePackages");
                    packages.extend(a.strings("value"));
                    packages.extend(a.classes("basePackageClasses").iter().map(|c| c.rsplit_once('/').map_or("", |(p, _)| p).to_string()));
                    let packages = packages.into_iter().map(|p| p.replace('.', "/")).collect();
                    out.advices.push(Advice { class: name.clone(), order: order.unwrap_or(i64::from(i32::MAX)), handlers, packages, assignable: a.classes("assignableTypes"), annotations: a.classes("annotations") });
                }
                None if !handlers.is_empty() => {
                    out.local.insert(name.clone(), handlers);
                }
                None => {}
            }
        }
        out.advices.sort_by(|a, b| a.order.cmp(&b.order).then_with(|| a.class.cmp(&b.class)));
        out
    }

    /// What `exception` (an internal name, with a `ResponseStatusException`'s status after a colon) becomes when
    /// `controller`'s handler throws it.
    pub fn outcome(&self, cp: &ClassPath, controller: &str, controller_annotations: &[String], exception: &str) -> Outcome {
        let class = base_type(exception);
        let mut chain = vec![controller.to_string()];
        chain.extend(cp.superclasses(controller));
        for c in &chain {
            if let Some(found) = self.local.get(c).and_then(|handlers| closest(cp, handlers, class)) {
                return Outcome::Handled { status: found.status, by: format!("{}.{}", display(c), found.method) };
            }
        }
        for advice in &self.advices {
            if !advice.applies_to(cp, controller, controller_annotations) {
                continue;
            }
            if let Some(found) = closest(cp, &advice.handlers, class) {
                return Outcome::Handled { status: found.status, by: format!("{}.{}", display(&advice.class), found.method) };
            }
        }
        let mut exception_chain = vec![class.to_string()];
        exception_chain.extend(cp.superclasses(class));
        for c in &exception_chain {
            let Ok(Some(loaded)) = cp.load(c) else { continue };
            if let Some(status) = loaded.class.annotations().ok().and_then(|list| list.iter().find(|a| a.type_name == RESPONSE_STATUS).and_then(response_status)) {
                return Outcome::Marked(status);
            }
        }
        if CARRIERS.iter().any(|c| class == *c || cp.is_subtype(class, c)) {
            return Outcome::Carried(exception.split_once(':').map(|(_, s)| s.to_string()));
        }
        Outcome::Unmapped
    }

    /// A handler in `class` that takes a type an earlier handler of the same class already takes: Spring refuses
    /// the ambiguity, at startup for an advice and on the first such exception for a controller.
    pub fn duplicate(&self, class: &str, method: &str) -> Option<String> {
        let (handlers, advice) = match self.advices.iter().find(|a| a.class == class) {
            Some(a) => (&a.handlers, true),
            None => (self.local.get(class)?, false),
        };
        let position = handlers.iter().position(|h| h.method == method)?;
        let mine = &handlers[position];
        for earlier in &handlers[..position] {
            if let Some(t) = mine.types.iter().find(|t| earlier.types.contains(t)) {
                let consequence = if advice { "Spring refuses the ambiguity, so the context does not start" } else { "Spring refuses the ambiguity on the first one thrown, so the response is a 500" };
                return Some(format!("! @ExceptionHandler for {} twice in {} ({} and {method}): {consequence}", display(t), display(class), earlier.method));
            }
        }
        None
    }
}

/// The handler whose type is nearest to the exception's class, up its superclass chain.
fn closest<'a>(cp: &ClassPath, handlers: &'a [Handler], class: &str) -> Option<&'a Handler> {
    let mut chain = vec![class.to_string()];
    chain.extend(cp.superclasses(class));
    chain.push("java/lang/Throwable".to_string());
    let mut best: Option<(usize, &Handler)> = None;
    for h in handlers {
        for t in &h.types {
            let Some(depth) = chain.iter().position(|c| c == t) else { continue };
            if best.is_none_or(|(d, _)| depth < d) {
                best = Some((depth, h));
            }
        }
    }
    best.map(|(_, h)| h)
}

pub(crate) fn response_status(a: &Annotation) -> Option<u16> {
    match a.element("code").or_else(|| a.element("value")) {
        Some(ElementValue::Enum(_, name)) => status_code(name),
        _ => None,
    }
}

/// The status a handler's body answers with: the first `HttpStatus` constant it loads, or the literal code it
/// passes to `ResponseEntity.status`, `ProblemDetail.forStatus` or `HttpStatusCode.valueOf`, or the status of a
/// `ResponseEntity.notFound()`-style builder.
fn status_in_body(class: &ClassFile, method: &Method) -> Option<u16> {
    let code = method.code.as_ref()?;
    let insns = code.instructions().ok()?;
    let targets = crate::boundaries::jump_targets(&insns, method);
    for (i, (_, insn)) in insns.iter().enumerate() {
        match insn {
            Insn::GetStatic(idx) => {
                let member = class.pool.member(*idx).ok()?;
                if member.owner == HTTP_STATUS {
                    if let Some(s) = status_code(&member.name) {
                        return Some(s);
                    }
                }
            }
            Insn::InvokeStatic(idx) | Insn::InvokeVirtual(idx) | Insn::InvokeInterface(idx) => {
                let member = class.pool.member(*idx).ok()?;
                let builder = member.owner == "org/springframework/http/ResponseEntity" || member.owner == "org/springframework/http/ProblemDetail" || member.owner == "org/springframework/http/HttpStatusCode" || member.owner == HTTP_STATUS;
                if !builder {
                    continue;
                }
                if member.descriptor.starts_with("(I)") {
                    if let Some(Insn::IConst(v)) = pushing(class, &insns, &targets, i, 0).map(|k| &insns[k].1) {
                        return u16::try_from(*v).ok();
                    }
                }
                let named = match member.name.as_str() {
                    "ok" => 200,
                    "created" => 201,
                    "accepted" => 202,
                    "noContent" => 204,
                    "badRequest" => 400,
                    "notFound" => 404,
                    "unprocessableEntity" => 422,
                    "internalServerError" => 500,
                    _ => continue,
                };
                return Some(named);
            }
            _ => {}
        }
    }
    None
}

/// The code of an `HttpStatus` constant.
pub fn status_code(name: &str) -> Option<u16> {
    Some(match name {
        "CONTINUE" => 100,
        "SWITCHING_PROTOCOLS" => 101,
        "PROCESSING" => 102,
        "EARLY_HINTS" | "CHECKPOINT" => 103,
        "OK" => 200,
        "CREATED" => 201,
        "ACCEPTED" => 202,
        "NON_AUTHORITATIVE_INFORMATION" => 203,
        "NO_CONTENT" => 204,
        "RESET_CONTENT" => 205,
        "PARTIAL_CONTENT" => 206,
        "MULTI_STATUS" => 207,
        "ALREADY_REPORTED" => 208,
        "IM_USED" => 226,
        "MULTIPLE_CHOICES" => 300,
        "MOVED_PERMANENTLY" => 301,
        "FOUND" | "MOVED_TEMPORARILY" => 302,
        "SEE_OTHER" => 303,
        "NOT_MODIFIED" => 304,
        "USE_PROXY" => 305,
        "TEMPORARY_REDIRECT" => 307,
        "PERMANENT_REDIRECT" => 308,
        "BAD_REQUEST" => 400,
        "UNAUTHORIZED" => 401,
        "PAYMENT_REQUIRED" => 402,
        "FORBIDDEN" => 403,
        "NOT_FOUND" => 404,
        "METHOD_NOT_ALLOWED" => 405,
        "NOT_ACCEPTABLE" => 406,
        "PROXY_AUTHENTICATION_REQUIRED" => 407,
        "REQUEST_TIMEOUT" => 408,
        "CONFLICT" => 409,
        "GONE" => 410,
        "LENGTH_REQUIRED" => 411,
        "PRECONDITION_FAILED" => 412,
        "PAYLOAD_TOO_LARGE" | "REQUEST_ENTITY_TOO_LARGE" | "CONTENT_TOO_LARGE" => 413,
        "URI_TOO_LONG" | "REQUEST_URI_TOO_LONG" => 414,
        "UNSUPPORTED_MEDIA_TYPE" => 415,
        "REQUESTED_RANGE_NOT_SATISFIABLE" => 416,
        "EXPECTATION_FAILED" => 417,
        "I_AM_A_TEAPOT" => 418,
        "INSUFFICIENT_SPACE_ON_RESOURCE" => 419,
        "METHOD_FAILURE" => 420,
        "DESTINATION_LOCKED" => 421,
        "UNPROCESSABLE_ENTITY" | "UNPROCESSABLE_CONTENT" => 422,
        "LOCKED" => 423,
        "FAILED_DEPENDENCY" => 424,
        "TOO_EARLY" => 425,
        "UPGRADE_REQUIRED" => 426,
        "PRECONDITION_REQUIRED" => 428,
        "TOO_MANY_REQUESTS" => 429,
        "REQUEST_HEADER_FIELDS_TOO_LARGE" => 431,
        "UNAVAILABLE_FOR_LEGAL_REASONS" => 451,
        "INTERNAL_SERVER_ERROR" => 500,
        "NOT_IMPLEMENTED" => 501,
        "BAD_GATEWAY" => 502,
        "SERVICE_UNAVAILABLE" => 503,
        "GATEWAY_TIMEOUT" => 504,
        "HTTP_VERSION_NOT_SUPPORTED" => 505,
        "VARIANT_ALSO_NEGOTIATES" => 506,
        "INSUFFICIENT_STORAGE" => 507,
        "LOOP_DETECTED" => 508,
        "BANDWIDTH_LIMIT_EXCEEDED" => 509,
        "NOT_EXTENDED" => 510,
        "NETWORK_AUTHENTICATION_REQUIRED" => 511,
        _ => return None,
    })
}

/// The `throws` line under a route, and the `!` lines for the exceptions nothing maps: the exception types the
/// module's own classes declare, since a JDK or framework exception that reaches the boundary is a 500 by
/// design (a guard that fired, a driver that failed) rather than a response the service forgot to shape.
pub fn describe(cp: &ClassPath, handlers: &Handlers, controller: &str, controller_annotations: &[String], thrown: &BTreeSet<String>, local: &dyn Fn(&str) -> bool) -> (Option<String>, Vec<String>) {
    if thrown.is_empty() {
        return (None, Vec::new());
    }
    let mut parts = Vec::new();
    let mut problems = Vec::new();
    for e in by_simple_name(thrown) {
        let name = display(base_type(e));
        let outcome = handlers.outcome(cp, controller, controller_annotations, e);
        parts.push(match &outcome {
            Outcome::Handled { status: Some(s), by } => format!("{name} ({s} by {by})"),
            Outcome::Handled { status: None, by } => format!("{name} (by {by})"),
            Outcome::Marked(s) => format!("{name} ({s} by its @ResponseStatus)"),
            Outcome::Carried(Some(s)) => format!("{name} ({})", status_code(s).map_or_else(|| s.clone(), |c| c.to_string())),
            Outcome::Carried(None) => format!("{name} (a status chosen at run time)"),
            Outcome::Unmapped => format!("{name} (500)"),
        });
        if outcome == Outcome::Unmapped && local(base_type(e)) {
            problems.push(format!("! throws {name}: no @ExceptionHandler takes it and it carries no @ResponseStatus, so the response is a 500"));
        }
    }
    (Some(format!("throws {}", parts.join(", "))), problems)
}

/// The `throws` line under a listener or a schedule: the exceptions, with no outcome.
pub fn list(thrown: &BTreeSet<String>) -> Option<String> {
    if thrown.is_empty() {
        return None;
    }
    Some(format!("throws {}", by_simple_name(thrown).into_iter().map(|e| display(base_type(e))).collect::<Vec<_>>().join(", ")))
}

/// The exceptions in the order the line shows them: by simple name, so that the application's own and the JDK's
/// mix as a reader expects rather than by package.
fn by_simple_name(thrown: &BTreeSet<String>) -> Vec<&String> {
    let mut out: Vec<&String> = thrown.iter().collect();
    out.sort_by_key(|e| (display(base_type(e)), e.as_str()));
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_constants_have_their_codes() {
        assert_eq!(status_code("NOT_FOUND"), Some(404));
        assert_eq!(status_code("UNPROCESSABLE_CONTENT"), Some(422));
        assert_eq!(status_code("TEAPOT"), None);
    }

    #[test]
    fn an_advice_with_no_selector_applies_to_every_controller() {
        let cp = ClassPath::new();
        let all = Advice { class: "a/Errors".into(), order: 0, handlers: Vec::new(), packages: Vec::new(), assignable: Vec::new(), annotations: Vec::new() };
        assert!(all.applies_to(&cp, "b/api/Things", &[]));
        let scoped = Advice { class: "a/Errors".into(), order: 0, handlers: Vec::new(), packages: vec!["b/api".into()], assignable: Vec::new(), annotations: Vec::new() };
        assert!(scoped.applies_to(&cp, "b/api/Things", &[]));
        assert!(scoped.applies_to(&cp, "b/api/v2/Things", &[]));
        assert!(!scoped.applies_to(&cp, "b/apix/Things", &[]));
        assert!(!scoped.applies_to(&cp, "b/Things", &[]));
    }
}
