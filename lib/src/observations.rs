//! Observation specs: for each entry point of a Spring application (a route, a message listener, a schedule, an
//! application-event listener), what its consumers can observe. The boundary analysis ([`crate::boundaries`])
//! finds the same entry points and renders them for a reviewer as `boundaries.contract`; this module reads the same
//! facts into the shared IR of `llm-dlc/loops/foundations.md` ([`crate::spec`]), as one
//! [`EntryPointSpec`] per entry point:
//!
//! - **its inputs**, the external inputs of its preservation contract: each request part a route binds (a request
//!   parameter, a path variable, a header, a cookie, the body), or each payload parameter of a listener, with its
//!   Java type and how it is bound. Their derivation is identity: both versions get the same request;
//! - **what a consumer observes**: the response (a route's result and its status for each outcome, from
//!   [`crate::failures`]), the exception, and each effect, an attempted call to a store, a broker, an HTTP client
//!   or the event publisher ([`crate::reach`]'s writes, sends, calls and publishes), with the payload paths it
//!   snapshots at the call and where it stands with respect to transactions;
//! - **which identity relations count**: none for a route or a listener, whose consumers see serialized values;
//! - **the environment** its effects run in: every modeled call (reads included, which return what the store
//!   holds) with the outcomes it may give, one model for both versions, a trace bound and the exact order;
//! - **what the analysis can't see**, named: a call it can't follow, a dynamic call site, a target computed at run
//!   time, a parameter the framework supplies. An unresolved part stays in the spec; it never vanishes.
//!
//! Ids are stable across builds: `POST /quotes`, `kafka payments.events`, `schedule fixedDelay = 1000`,
//! `event OrderPlaced`, and `effect:owner#name(descriptor)` per modeled call, so that two builds' specs compare
//! by id ([`crate::spec::observe::compare`]). The spec is static: it says what must be preserved, and proves
//! nothing.

use std::collections::{BTreeMap, BTreeSet};
use std::rc::Rc;

use crate::boundaries::{is_framework, mapping_verb, routes, type_names};
use crate::classfile::{flags, Annotation, ClassFile, Method, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::failures::{self, status_code, Handlers, Outcome as Failure};
use crate::reach::{self, display, method_label, Placed, Placement, SiteKind};
use crate::spec::observe::{Binding, BindingSource, Change, EffectSite, EntryKind, EntryPointSpec, Obligation, StatusOutcome};
use crate::spec::{Derivation, EnvironmentModel, ExternalInput, ModeledCall, Observation, OrderPolicy};
use crate::Error;

/// The fewest effects one trace records unless a caller asks for another bound: reaching it leaves a check
/// unresolved, never a shorter trace. A spec raises it to its number of effect sites, so that one pass through
/// each fits (a site in a loop may still reach it).
pub const TRACE_BOUND: u32 = 4;

/// What every spec's environment model assumes about the modeled calls, stated in each spec.
pub const RETURNS_NORMALLY: &str = "every modeled call returns normally: a failure of a store, broker or client call is outside this environment model";

/// Message listeners whose parameters arrive over the wire, with the id prefix and the elements naming their
/// destination.
const LISTENERS: &[(&str, &str, &[&str])] = &[
    ("KafkaListener", "kafka", &["topics", "topicPattern"]),
    ("KafkaHandler", "kafka", &[]),
    ("RabbitListener", "rabbit", &["queues"]),
    ("RabbitHandler", "rabbit", &[]),
    ("JmsListener", "jms", &["destination"]),
    ("SqsListener", "sqs", &["value", "queueNames"]),
    ("MessageMapping", "message", &["value"]),
    ("SubscribeMapping", "subscribe", &["value"]),
];

const EVENT_LISTENERS: &[&str] = &["EventListener", "TransactionalEventListener", "ApplicationModuleListener"];

/// Annotations that bind a route parameter to a request part.
const ROUTE_BINDINGS: &[(&str, BindingSource)] = &[
    ("RequestParam", BindingSource::RequestParameter),
    ("PathVariable", BindingSource::PathVariable),
    ("RequestHeader", BindingSource::Header),
    ("CookieValue", BindingSource::Cookie),
    ("MatrixVariable", BindingSource::MatrixVariable),
    ("RequestBody", BindingSource::Body),
    ("RequestPart", BindingSource::Part),
    ("ModelAttribute", BindingSource::ModelAttribute),
];

/// Parameter types the framework supplies to a handler rather than binding from the request or the message.
const SUPPLIED: &[&str] = &[
    "jakarta/servlet/", "javax/servlet/", "java/security/Principal", "org/springframework/ui/", "org/springframework/validation/",
    "org/springframework/web/context/request/", "org/springframework/web/util/UriComponentsBuilder", "org/springframework/http/HttpEntity",
    "org/springframework/http/HttpMethod", "org/springframework/data/domain/Pageable", "org/springframework/data/domain/Sort",
    "org/springframework/kafka/support/Acknowledgment", "org/springframework/messaging/MessageHeaders", "java/util/Locale", "java/io/",
    "org/springframework/web/servlet/", "org/springframework/security/",
];

/// The parameter names of the modeled APIs the walk knows, when the class path doesn't carry them: owner suffix,
/// name, and the names in order (by arity).
const PARAMETER_NAMES: &[(&str, &str, &[&str])] = &[
    ("KafkaTemplate", "send", &["topic", "data"]),
    ("KafkaTemplate", "send", &["topic", "key", "data"]),
    ("KafkaTemplate", "send", &["topic", "partition", "key", "data"]),
    ("KafkaTemplate", "send", &["topic", "partition", "timestamp", "key", "data"]),
    ("KafkaOperations", "send", &["topic", "data"]),
    ("KafkaOperations", "send", &["topic", "key", "data"]),
    ("RabbitTemplate", "convertAndSend", &["object"]),
    ("RabbitTemplate", "convertAndSend", &["routingKey", "object"]),
    ("RabbitTemplate", "convertAndSend", &["exchange", "routingKey", "object"]),
    ("JmsTemplate", "convertAndSend", &["destinationName", "message"]),
    ("StreamBridge", "send", &["bindingName", "data"]),
    ("ApplicationEventPublisher", "publishEvent", &["event"]),
    ("ApplicationContext", "publishEvent", &["event"]),
    ("MongoTemplate", "insert", &["objectToSave"]),
    ("MongoTemplate", "insert", &["objectToSave", "collectionName"]),
    ("MongoTemplate", "save", &["objectToSave"]),
    ("MongoTemplate", "save", &["objectToSave", "collectionName"]),
    ("MongoOperations", "insert", &["objectToSave"]),
    ("MongoOperations", "save", &["objectToSave"]),
    ("MongoTemplate", "updateFirst", &["query", "update", "entityClass"]),
    ("MongoTemplate", "updateMulti", &["query", "update", "entityClass"]),
    ("MongoTemplate", "upsert", &["query", "update", "entityClass"]),
    ("MongoTemplate", "findAndModify", &["query", "update", "entityClass"]),
    ("MongoTemplate", "findAndModify", &["query", "update", "options", "entityClass"]),
    ("MongoTemplate", "remove", &["query", "entityClass"]),
    ("MongoTemplate", "find", &["query", "entityClass"]),
    ("MongoTemplate", "findOne", &["query", "entityClass"]),
    ("MongoTemplate", "findById", &["id", "entityClass"]),
    ("RestTemplate", "postForObject", &["url", "request", "responseType", "uriVariables"]),
    ("RestTemplate", "getForObject", &["url", "responseType", "uriVariables"]),
];

/// How deep a payload's fields are followed into application classes.
const PAYLOAD_DEPTH: usize = 4;

/// The specs of the entry points in the classes under `only` (internal names), or in every application class. What
/// each reaches is followed into the `local` classes (the module and its sibling modules, as for the boundary
/// contract), or into every application class when `local` is `None`; the whole class path resolves the types.
pub fn analyse(cp: &ClassPath, only: Option<&BTreeSet<String>>, local: Option<&BTreeSet<String>>) -> Result<Vec<EntryPointSpec>, Error> {
    let classes = cp.application_classes()?;
    let graph = reach::Graph::new(cp, &classes, local);
    let handlers = Handlers::collect(cp, &classes, local);
    let mut specs = Vec::new();
    for (name, class) in &classes {
        if only.is_some_and(|l| !l.contains(name)) || class.access & (flags::ANNOTATION | flags::SYNTHETIC) != 0 {
            continue;
        }
        let class_annotations = class.annotations().map_err(|e| Error::new(format!("{name}: {e}")))?;
        let class_annotation_names: Vec<String> = class_annotations.iter().map(|a| a.type_name.clone()).collect();
        let framework: Vec<&Annotation> = class_annotations.iter().filter(|a| is_framework(a)).collect();
        let class_mappings: Vec<&Annotation> = framework.iter().copied().filter(|a| mapping_verb(a).is_some()).collect();
        for method in &class.methods {
            if method.is_synthetic() || method.is_bridge() || method.is_constructor() || method.is_class_initializer() {
                continue;
            }
            let annotations: Vec<Annotation> = method.annotations(&class.pool).map_err(|e| Error::new(format!("{name}: {e}")))?.into_iter().filter(is_framework).collect();
            let Ok(d) = MethodDescriptor::parse(&method.descriptor) else { continue };
            let entry = Entry { cp, graph: &graph, handlers: &handlers, class, method, d: &d, class_annotations: &class_annotation_names };
            for a in &annotations {
                if mapping_verb(a).is_some() {
                    for route in routes(&class_mappings, a) {
                        let id = route.split(" (").next().unwrap_or(&route).to_string();
                        specs.push(entry.spec(EntryKind::Route, id, &route));
                    }
                } else if let Some((_, prefix, elements)) = LISTENERS.iter().find(|(n, _, _)| *n == a.simple_name()) {
                    let mut destinations: Vec<String> = elements.iter().flat_map(|e| a.strings(e)).collect();
                    if destinations.is_empty() {
                        // A @KafkaHandler or @RabbitHandler takes its destination from the class's listener.
                        destinations = framework.iter().filter(|c| LISTENERS.iter().any(|(n, p, _)| *n == c.simple_name() && p == prefix)).flat_map(|c| LISTENERS.iter().find(|(n, _, _)| *n == c.simple_name()).into_iter().flat_map(|(_, _, es)| es.iter().flat_map(|e| c.strings(e)))).collect();
                    }
                    if destinations.is_empty() {
                        let mut spec = entry.spec(EntryKind::Listener, format!("{prefix} {}", handler_name(class, method)), &a.render());
                        spec.unresolved.push(format!("{}: no constant destination, so the id is the handler's", a.render()));
                        specs.push(spec);
                    }
                    for destination in destinations {
                        let mut spec = entry.spec(EntryKind::Listener, format!("{prefix} {destination}"), &a.render());
                        if destination.contains("${") || destination.contains("#{") {
                            spec.unresolved.push(format!("the destination {destination} comes from configuration"));
                        }
                        specs.push(spec);
                    }
                } else if matches!(a.simple_name().as_str(), "Scheduled" | "Schedules") {
                    let rendered = a.render();
                    let args = rendered.strip_prefix(&format!("@{}", a.simple_name())).unwrap_or("").trim_start_matches('(').trim_end_matches(')').to_string();
                    let id = if args.is_empty() { format!("schedule {}", handler_name(class, method)) } else { format!("schedule {args}") };
                    specs.push(entry.spec(EntryKind::Schedule, id, &rendered));
                } else if EVENT_LISTENERS.contains(&a.simple_name().as_str()) {
                    let mut events = a.classes("classes");
                    events.extend(a.classes("value"));
                    if events.is_empty() {
                        events.extend(d.params.first().and_then(|t| t.class_name().map(str::to_string)));
                    }
                    for event in events {
                        specs.push(entry.spec(EntryKind::Event, format!("event {}", display(&event)), &a.render()));
                    }
                }
            }
        }
    }
    // Two entry points under one id (two schedules with the same timing): each keeps its handler in the id.
    let mut count: BTreeMap<String, usize> = BTreeMap::new();
    for s in &specs {
        *count.entry(s.id.clone()).or_default() += 1;
    }
    for s in &mut specs {
        if count[&s.id] > 1 {
            s.id = format!("{} ({})", s.id, s.handler);
        }
    }
    specs.sort_by(|a, b| a.id.cmp(&b.id));
    Ok(specs)
}

/// `shop.QuotesController#quote`.
fn handler_name(class: &ClassFile, method: &Method) -> String {
    format!("{}#{}", class.name.replace('/', "."), method.name)
}

struct Entry<'a> {
    cp: &'a ClassPath,
    graph: &'a reach::Graph<'a>,
    handlers: &'a Handlers,
    class: &'a Rc<ClassFile>,
    method: &'a Method,
    d: &'a MethodDescriptor,
    class_annotations: &'a [String],
}

impl Entry<'_> {
    fn spec(&self, kind: EntryKind, id: String, declared: &str) -> EntryPointSpec {
        let (class, method, d) = (self.class, self.method, self.d);
        let label = method_label(class, method);
        let (param_types, ret) = type_names(method, &class.pool, d);
        let names = method.parameter_names(&class.pool);
        let reflective = method.reflective_parameter_names(&class.pool);
        let parameter_annotations: Vec<Vec<Annotation>> = method.parameter_annotations(&class.pool).unwrap_or_default().into_iter().map(|l| l.into_iter().filter(is_framework).collect()).collect();
        let mut unresolved = Vec::new();
        let mut inputs = Vec::new();
        let mut bindings = Vec::new();
        for (i, t) in d.params.iter().enumerate() {
            let pname = names.get(i).cloned().unwrap_or_else(|| format!("arg{i}"));
            let shown = param_types.get(i).cloned().unwrap_or_else(|| t.simple_name());
            let list = parameter_annotations.get(i).map(Vec::as_slice).unwrap_or(&[]);
            if t.class_name().is_some_and(|c| SUPPLIED.iter().any(|s| c.starts_with(s))) {
                unresolved.push(format!("the parameter {pname} ({shown}) is supplied by the framework, not by the request: not modeled"));
                continue;
            }
            let source = match kind {
                EntryKind::Route => {
                    match list.iter().find_map(|a| ROUTE_BINDINGS.iter().find(|(n, _)| *n == a.simple_name()).map(|(_, s)| (*s, a))) {
                        Some((s, a)) => Some((s, explicit_name(a))),
                        // Spring binds an unannotated simple value as a request parameter, anything else as a model attribute.
                        None if is_simple(t) => Some((BindingSource::RequestParameter, None)),
                        None => Some((BindingSource::ModelAttribute, None)),
                    }
                }
                EntryKind::Listener => {
                    if list.iter().any(|a| matches!(a.simple_name().as_str(), "Header" | "Headers")) {
                        Some((BindingSource::Header, list.iter().find_map(explicit_name)))
                    } else {
                        Some((BindingSource::Payload, None))
                    }
                }
                EntryKind::Event => Some((BindingSource::Event, None)),
                EntryKind::Schedule => None,
            };
            let Some((source, explicit)) = source else { continue };
            let name = explicit.or_else(|| reflective.as_ref().and_then(|r| r.get(i).cloned())).unwrap_or(pname);
            inputs.push(ExternalInput { name: name.clone(), ty: shown.clone(), derivation: Derivation::Identity });
            bindings.push(Binding { input: name, source, wire_type: t.class_name().map(|c| c.replace('/', ".")).unwrap_or_else(|| shown.clone()) });
        }

        let reached = self.graph.reach(&class.name, &method.name, &method.descriptor);
        let thrown = self.graph.throws(&class.name, &method.name, &method.descriptor);
        let mut observations = Vec::new();
        if d.ret != Type::Void {
            observations.push(Observation::Result);
        }
        observations.push(Observation::Exception);
        let mut statuses = Vec::new();
        if kind == EntryKind::Route {
            observations.push(Observation::Status);
            statuses.push(self.normal_status(&ret));
            for e in &thrown {
                let base = reach::base_type(e);
                let (status, by) = match self.handlers.outcome(self.cp, &class.name, self.class_annotations, e) {
                    Failure::Handled { status, by } => (status, format!("@ExceptionHandler {by}")),
                    Failure::Marked(s) => (Some(s), "its @ResponseStatus".to_string()),
                    Failure::Carried(Some(s)) => (status_code(&s), format!("the status it carries, {s}")),
                    Failure::Carried(None) => (None, "a status chosen at run time".to_string()),
                    Failure::Unmapped => (Some(500), "nothing maps it".to_string()),
                };
                if status.is_none() {
                    unresolved.push(format!("the status for {}: {by}", display(base)));
                }
                statuses.push(StatusOutcome { outcome: display(e), status, by });
            }
        }
        let mut effects = Vec::new();
        let mut calls: Vec<ModeledCall> = Vec::new();
        for Placed { placement, site } in &reached.sites {
            let parameters = self.parameter_names(&site.call);
            let payload = payload_paths(self.cp, &parameters, &site.arguments);
            if site.kind != SiteKind::Read {
                match observations.iter_mut().find(|o| matches!(o, Observation::Effect { call, .. } if call == &site.call)) {
                    Some(Observation::Effect { payload: existing, .. }) => {
                        for p in &payload {
                            if !existing.contains(p) {
                                existing.push(p.clone());
                            }
                        }
                    }
                    _ => observations.push(Observation::Effect { call: site.call.clone(), payload: payload.clone() }),
                }
            }
            if !calls.iter().any(|c| c.call == site.call) {
                calls.push(ModeledCall { call: site.call.clone(), outcomes: vec!["returns".to_string()] });
            }
            if computed_target(&site.target) {
                unresolved.push(format!("the target of {} in {}: computed at run time ({})", short_call(&site.call), site.in_method, site.target));
            }
            effects.push(EffectSite { kind: site.kind, target: site.target.clone(), call: site.call.clone(), payload, placement: *placement, in_method: site.in_method.clone() });
        }
        unresolved.extend(reached.dynamic.iter().map(|d| format!("a dynamic call site the walk doesn't follow: {d}{}", dynamic_note(d))));
        unresolved.extend(reached.unresolved.iter().map(|u| format!("a call the walk can't follow: {u}")));
        if id_has_placeholder(&id) {
            unresolved.push(format!("{id}: part of it comes from configuration"));
        }
        let assumptions = if calls.is_empty() { Vec::new() } else { vec![RETURNS_NORMALLY.to_string()] };
        let identity = match kind {
            EntryKind::Route | EntryKind::Listener => "none: its consumers see serialized values".to_string(),
            EntryKind::Schedule => "none: nothing is returned to a caller".to_string(),
            EntryKind::Event => "none: the publisher gets nothing back".to_string(),
        };
        EntryPointSpec {
            id,
            handler: handler_name(class, method),
            inputs,
            observations,
            environment: EnvironmentModel { calls, trace_bound: TRACE_BOUND.max(effects.iter().filter(|e| e.kind != SiteKind::Read).count() as u32), order: OrderPolicy::Exact },
            unresolved,
            kind,
            declared: declared.to_string(),
            bindings,
            response: (d.ret != Type::Void).then(|| ret.clone()),
            statuses,
            effects,
            identity,
            assumptions,
            source_line: method.first_line(),
            method: label,
        }
    }

    /// The status of a normal return: the method's `@ResponseStatus`, the one a `ResponseEntity` is built with
    /// (chosen by the handler), or 200.
    fn normal_status(&self, ret: &str) -> StatusOutcome {
        let annotations = self.method.annotations(&self.class.pool).unwrap_or_default();
        if let Some(s) = annotations.iter().find(|a| a.simple_name() == "ResponseStatus").and_then(failures::response_status) {
            return StatusOutcome { outcome: "returns".into(), status: Some(s), by: "its @ResponseStatus".into() };
        }
        if ret.starts_with("ResponseEntity") {
            return StatusOutcome { outcome: "returns".into(), status: None, by: "the ResponseEntity the handler builds".into() };
        }
        if self.d.ret == Type::Void {
            return StatusOutcome { outcome: "returns".into(), status: Some(200), by: "no body".into() };
        }
        StatusOutcome { outcome: "returns".into(), status: Some(200), by: "the default".into() }
    }

    /// The names of a modeled call's parameters: from its class on the class path when it records them, else from
    /// the table of known APIs, else `arg0`, `arg1`.
    fn parameter_names(&self, call: &str) -> Vec<String> {
        let Some((owner, rest)) = call.split_once('#') else { return Vec::new() };
        let Some(paren) = rest.find('(') else { return Vec::new() };
        let (name, descriptor) = rest.split_at(paren);
        let arity = MethodDescriptor::parse(descriptor).map(|d| d.params.len()).unwrap_or(0);
        if let Some((c, m)) = self.cp.bytecode_method(owner, name, descriptor) {
            if let Some(names) = m.reflective_parameter_names(&c.pool).filter(|n| n.len() == arity) {
                return names;
            }
        }
        let simple = owner.rsplit('/').next().unwrap_or(owner);
        if let Some((_, _, names)) = PARAMETER_NAMES.iter().find(|(o, n, ps)| simple.ends_with(o) && *n == name && ps.len() == arity) {
            return names.iter().map(|s| s.to_string()).collect();
        }
        (0..arity).map(|i| format!("arg{i}")).collect()
    }
}

fn explicit_name(a: &Annotation) -> Option<String> {
    a.strings("value").into_iter().chain(a.strings("name")).find(|s| !s.is_empty())
}

/// A type Spring binds from one request value: a primitive, its box, a `String`, a number, a date, an enum.
fn is_simple(t: &Type) -> bool {
    match t {
        Type::Object(c) => c.starts_with("java/lang/") || c.starts_with("java/time/") || c == "java/math/BigDecimal" || c == "java/math/BigInteger" || c == "java/util/UUID",
        Type::Array(_) => false,
        _ => true,
    }
}

/// The paths a call's payload is observed at: each parameter by name, an application class's fields followed into
/// (`data.total`), a class literal left out (it names a type, not a value).
fn payload_paths(cp: &ClassPath, parameters: &[String], arguments: &[Option<String>]) -> Vec<String> {
    let mut out = Vec::new();
    for (i, name) in parameters.iter().enumerate() {
        let ty = arguments.get(i).cloned().flatten();
        if ty.as_deref() == Some("java/lang/Class") {
            continue;
        }
        let mut seen = BTreeSet::new();
        fields_of(cp, name, ty.as_deref(), 0, &mut seen, &mut out);
    }
    out
}

fn fields_of(cp: &ClassPath, path: &str, ty: Option<&str>, depth: usize, seen: &mut BTreeSet<String>, out: &mut Vec<String>) {
    let class = ty.filter(|t| depth < PAYLOAD_DEPTH && !reach::is_leaf(t)).and_then(|t| cp.application(t).ok().flatten());
    let Some(class) = class.filter(|c| !c.is_enum() && seen.insert(c.name.clone())) else {
        out.push(path.to_string());
        return;
    };
    let mut chain = vec![class.clone()];
    let mut sup = class.super_class.clone();
    while let Some(s) = sup {
        match cp.application(&s).ok().flatten() {
            Some(c) => {
                sup = c.super_class.clone();
                chain.push(c);
            }
            None => break,
        }
    }
    let mut any = false;
    for c in chain.iter().rev() {
        for f in c.fields.iter().filter(|f| !f.is_static() && f.access & flags::SYNTHETIC == 0) {
            any = true;
            let t = Type::parse(&f.descriptor).ok();
            fields_of(cp, &format!("{path}.{}", f.name), t.as_ref().and_then(|t| t.class_name()), depth + 1, seen, out);
        }
    }
    if !any {
        out.push(path.to_string());
    }
    seen.remove(&class.name);
}

/// A target the reach walk could not read as a constant.
fn computed_target(target: &str) -> bool {
    target.starts_with("to ") || target.contains("a computed URL") || target == "a document" || target == "an entity" || target == "an event" || target == "SQL" || target.starts_with("a request to")
}

fn id_has_placeholder(id: &str) -> bool {
    id.contains("${") || id.contains("#{")
}

/// `KafkaTemplate.send`.
fn short_call(call: &str) -> String {
    let (owner, rest) = call.split_once('#').unwrap_or((call, ""));
    format!("{}.{}", display(owner), rest.split('(').next().unwrap_or(rest))
}

fn dynamic_note(site: &str) -> &'static str {
    if site.starts_with("StringConcatFactory.") {
        " (string concatenation: the string's value isn't modeled)"
    } else if site.starts_with("ObjectMethods.") {
        " (a record's equals, hashCode or toString)"
    } else if site.starts_with("SwitchBootstraps.") {
        " (a pattern or enum switch)"
    } else {
        ""
    }
}

/// The specs as text, one block per entry point, for `jvmcontract observations`.
pub fn render(specs: &[EntryPointSpec]) -> String {
    let mut out = String::new();
    for s in specs {
        out.push_str(&format!("{} => {}\n", s.id, s.handler));
        let inputs: Vec<String> = s.inputs.iter().zip(&s.bindings).map(|(i, b)| format!("{}: {} ({})", i.name, i.ty, b.source.words())).collect();
        out.push_str(&format!("  inputs: {}\n", if inputs.is_empty() { "none".to_string() } else { inputs.join(", ") }));
        if let Some(r) = &s.response {
            out.push_str(&format!("  response: {r}\n"));
        }
        for st in &s.statuses {
            out.push_str(&format!("  status when {}: {} ({})\n", st.outcome, st.status.map_or_else(|| "unknown".to_string(), |c| c.to_string()), st.by));
        }
        for e in &s.effects {
            out.push_str(&format!("  {} {} by {}, {}, in {}{}\n", if e.kind == SiteKind::Send && e.target.starts_with("to ") { "sends" } else { e.kind.verb() }, e.target, short_call(&e.call), e.placement.words(), e.in_method, if e.payload.is_empty() { String::new() } else { format!(", snapshot of {}", e.payload.join(", ")) }));
        }
        out.push_str(&format!("  observes: {}\n", s.observations.iter().map(Observation::id).collect::<Vec<_>>().join(", ")));
        out.push_str(&format!("  identity relations: {}\n", s.identity));
        out.push_str(&format!("  environment: {} modeled call{}, trace bound {}, exact order\n", s.environment.calls.len(), if s.environment.calls.len() == 1 { "" } else { "s" }, s.environment.trace_bound));
        for a in &s.assumptions {
            out.push_str(&format!("  assumes {a}\n"));
        }
        for u in &s.unresolved {
            out.push_str(&format!("  unresolved: {u}\n"));
        }
    }
    out
}

impl SiteKind {
    fn verb(self) -> &'static str {
        match self {
            SiteKind::Read => "reads",
            SiteKind::Write => "writes",
            SiteKind::Send => "sends to",
            SiteKind::Call => "calls",
            SiteKind::Publish => "publishes",
        }
    }
}

impl Placement {
    fn words(self) -> &'static str {
        match self {
            Placement::Outside => "outside a transaction",
            Placement::Inside => "inside its transaction",
            Placement::Callee => "inside a @Transactional callee's transaction",
        }
    }
}

// Two builds compared.

const NEEDS_RESULT: &str = "a proof that both versions answer each request with the same value, under one environment model for both";
const NEEDS_EXCEPTION: &str = "a proof that for each request both versions return normally or both throw, and throw the same category";
const NEEDS_STATUS: &str = "a proof that both versions take the same outcome for each request, so that they answer with the same status";
const NEEDS_EFFECT: &str = "an effect-trace proof: under one environment model for both versions, the same ordered attempts of this call, with the same payload values snapshotted at each, within the trace bound; the same payload paths make it well formed and discharge nothing";
const NEEDS_OTHER: &str = "a proof that both versions agree on it for each input";
const NEEDS_CHANGED: &str = "a person's approval of the change, recorded in the preservation contract, or a proof that the difference never shows (then it is preserved)";
const NEEDS_REMOVED: &str = "a person's approval that it is gone, recorded in the preservation contract; there is nothing to prove preserved";
const NEEDS_NEW: &str = "nothing to preserve: an intended-behaviour contract, or a person's approval";
const NEEDS_INPUTS: &str = "a stated derivation of each version's inputs from one logical request, approved by a person: the preservation contract's input domain isn't inferred";
const NEEDS_UNRESOLVED: &str = "a model of what the analysis can't see: until then no obligation of this entry point is discharged without the assumption that it doesn't matter";
const NEEDS_AMBIGUOUS: &str = "a person to say which entry point of the new build this one is";

/// The obligations between two builds' entry points ([`crate::spec::observe::compare`]). Entry points correspond
/// by what their consumers address, not by handler: the same verb and route (path variable names aside), the same
/// topic or queue, the same schedule. A renamed handler is the same entry point; a renamed route is a removed one
/// and a new one. For each pair, each observation of the old entry point gets one obligation: preserved (to be
/// proved), changed, removed, or unresolved; each observation only the new one has is new. A difference in the
/// inputs and what the analysis can't see are obligations of their own. Every old observation is accounted for
/// ([`unaccounted`] is empty). Static: nothing here is proved.
pub fn compare(before: &[EntryPointSpec], after: &[EntryPointSpec]) -> Vec<Obligation> {
    let mut groups: BTreeMap<String, (Vec<&EntryPointSpec>, Vec<&EntryPointSpec>)> = BTreeMap::new();
    for s in before {
        groups.entry(match_key(s)).or_default().0.push(s);
    }
    for s in after {
        groups.entry(match_key(s)).or_default().1.push(s);
    }
    let mut pairs: Vec<(&EntryPointSpec, &EntryPointSpec)> = Vec::new();
    let mut ambiguous: Vec<(&EntryPointSpec, String)> = Vec::new();
    let mut gone: Vec<&EntryPointSpec> = Vec::new();
    let mut added: Vec<&EntryPointSpec> = Vec::new();
    for (key, (mut olds, mut news)) in groups {
        // Several under one key (two schedules with the same timing): the same handler pairs first.
        olds.retain(|o| match news.iter().position(|n| n.handler == o.handler) {
            Some(i) => {
                pairs.push((o, news.remove(i)));
                false
            }
            None => true,
        });
        match (olds.len(), news.len()) {
            (1, 1) => pairs.push((olds[0], news[0])),
            (_, 0) => gone.extend(olds),
            (0, _) => added.extend(news),
            _ => {
                let names: Vec<&str> = news.iter().map(|n| n.id.as_str()).collect();
                ambiguous.extend(olds.into_iter().map(|o| (o, format!("{key}: the new build has {} candidates, {}", names.len(), names.join(", ")))));
                added.extend(news);
            }
        }
    }
    let mut out = Vec::new();
    for o in before {
        if let Some((_, n)) = pairs.iter().find(|(p, _)| std::ptr::eq(*p, o)) {
            pair_obligations(o, n, &mut out);
        } else if let Some((_, why)) = ambiguous.iter().find(|(p, _)| std::ptr::eq(*p, o)) {
            for obs in &o.observations {
                out.push(obligation(&o.id, obs.id(), Change::Unresolved, vec![why.clone()], NEEDS_AMBIGUOUS));
            }
        } else if gone.iter().any(|p| std::ptr::eq(*p, o)) {
            let mut why = vec![format!("no entry point of the new build is {}", o.id)];
            why.extend(added.iter().filter(|n| n.handler == o.handler).map(|n| format!("its handler {} now serves {}: to its consumers that is another entry point, the same only if a person approves the change", o.handler, n.id)));
            for obs in &o.observations {
                out.push(obligation(&o.id, obs.id(), Change::Removed, why.clone(), NEEDS_REMOVED));
            }
        }
    }
    for n in after.iter().filter(|n| added.iter().any(|a| std::ptr::eq(*a, *n))) {
        for obs in &n.observations {
            out.push(obligation(&n.id, obs.id(), Change::New, vec![format!("the old build has no entry point {}", n.id)], NEEDS_NEW));
        }
    }
    out
}

/// The old build's observations that no obligation accounts for, as `entry: observation`: empty for what
/// [`compare`] gives, which is the point of it.
pub fn unaccounted(before: &[EntryPointSpec], obligations: &[Obligation]) -> Vec<String> {
    let mut out = Vec::new();
    for s in before {
        for obs in &s.observations {
            let id = obs.id();
            let n = obligations.iter().filter(|o| o.entry == s.id && o.observation == id && o.change != Change::New).count();
            if n != 1 {
                out.push(format!("{}: {id} ({n} obligations)", s.id));
            }
        }
    }
    out
}

/// What consumers address an entry point by: its kind and id, without a handler appended to tell two apart, and
/// with a route's path variables unnamed (`GET /holds/{}`), since a client's path doesn't name them.
fn match_key(s: &EntryPointSpec) -> String {
    let id = s.id.strip_suffix(&format!(" ({})", s.handler)).unwrap_or(&s.id);
    let id = if s.kind == EntryKind::Route {
        let mut out = String::new();
        let mut depth = 0;
        for c in id.chars() {
            match c {
                '{' => {
                    if depth == 0 {
                        out.push('{');
                    }
                    depth += 1;
                }
                '}' if depth > 0 => {
                    depth -= 1;
                    if depth == 0 {
                        out.push('}');
                    }
                }
                _ if depth > 0 => {}
                _ => out.push(c),
            }
        }
        out
    } else {
        id.to_string()
    };
    format!("{:?} {id}", s.kind)
}

fn obligation(entry: &str, observation: String, change: Change, differences: Vec<String>, needs: &str) -> Obligation {
    Obligation { entry: entry.to_string(), observation, change, new_entry: None, differences, needs: needs.to_string() }
}

fn pair_obligations(o: &EntryPointSpec, n: &EntryPointSpec, out: &mut Vec<Obligation>) {
    let start = out.len();
    let inputs = input_differences(o, n);
    if !inputs.is_empty() {
        out.push(obligation(&o.id, "inputs".into(), Change::Changed, inputs, NEEDS_INPUTS));
    }
    for obs in &o.observations {
        let id = obs.id();
        let kept = n.observations.iter().any(|x| x.id() == id);
        out.push(match obs {
            _ if !kept => obligation(&o.id, id, Change::Removed, vec![format!("the new build's {} doesn't observe it", n.id)], NEEDS_REMOVED),
            Observation::Result => match (&o.response, &n.response) {
                (Some(a), Some(b)) if a != b => obligation(&o.id, id, Change::Changed, vec![format!("the response was {a}, now {b}")], NEEDS_CHANGED),
                _ => obligation(&o.id, id, Change::Preserved, Vec::new(), NEEDS_RESULT),
            },
            Observation::Exception => obligation(&o.id, id, Change::Preserved, thrown_differences(o, n), NEEDS_EXCEPTION),
            Observation::Status => status_obligation(o, n),
            Observation::Effect { call, payload } => effect_obligation(o, n, call, payload),
            _ => obligation(&o.id, id, Change::Preserved, Vec::new(), NEEDS_OTHER),
        });
    }
    for obs in n.observations.iter().filter(|x| !o.observations.iter().any(|y| y.id() == x.id())) {
        let mut why = vec![format!("only the new build's {} observes it", n.id)];
        if let Observation::Effect { call, .. } = obs {
            why.extend(n.effects.iter().filter(|e| &e.call == call).map(|e| format!("it {}", site_words(e))));
        }
        out.push(obligation(&o.id, obs.id(), Change::New, why, NEEDS_NEW));
    }
    if !o.unresolved.is_empty() || !n.unresolved.is_empty() {
        let mut why: Vec<String> = o.unresolved.iter().map(|u| format!("before: {u}")).collect();
        why.extend(n.unresolved.iter().map(|u| format!("after: {u}")));
        out.push(obligation(&o.id, "unresolved".into(), Change::Unresolved, why, NEEDS_UNRESOLVED));
    }
    if n.id != o.id {
        for ob in &mut out[start..] {
            ob.new_entry = Some(n.id.clone());
        }
    }
}

fn input_differences(o: &EntryPointSpec, n: &EntryPointSpec) -> Vec<String> {
    let describe = |s: &EntryPointSpec| -> Vec<String> { s.inputs.iter().zip(&s.bindings).map(|(i, b)| format!("{}: {} ({})", i.name, i.ty, b.source.words())).collect() };
    let (a, b) = (describe(o), describe(n));
    let mut out: Vec<String> = a.iter().filter(|x| !b.contains(x)).map(|x| format!("the input {x} is gone")).collect();
    out.extend(b.iter().filter(|x| !a.contains(x)).map(|x| format!("a new input {x}")));
    out
}

fn thrown_differences(o: &EntryPointSpec, n: &EntryPointSpec) -> Vec<String> {
    let thrown = |s: &EntryPointSpec| -> BTreeSet<String> { s.statuses.iter().filter(|st| st.outcome != "returns").map(|st| st.outcome.clone()).collect() };
    let (a, b) = (thrown(o), thrown(n));
    let mut out: Vec<String> = a.difference(&b).map(|e| format!("the new build no longer throws {e}")).collect();
    out.extend(b.difference(&a).map(|e| format!("the new build may throw {e}, the old one doesn't")));
    out
}

fn status_words(st: &StatusOutcome) -> String {
    format!("{} ({})", st.status.map_or_else(|| "unknown".to_string(), |c| c.to_string()), st.by)
}

/// A route's status for each outcome. Changed when an outcome both have maps to another known status, or, with
/// every status known, one build can answer with a status the other never does; otherwise unresolved when a status
/// is unknown, and preserved when none is, with any outcome only one build has as a difference its proof must cover.
fn status_obligation(o: &EntryPointSpec, n: &EntryPointSpec) -> Obligation {
    let mut changed = Vec::new();
    let mut notes = Vec::new();
    for a in &o.statuses {
        match n.statuses.iter().find(|b| b.outcome == a.outcome) {
            Some(b) if a.status.is_some() && b.status.is_some() && b.status != a.status => changed.push(format!("{}: {}, now {}", a.outcome, status_words(a), status_words(b))),
            Some(b) if b.status != a.status => notes.push(format!("{}: {}, now {}", a.outcome, status_words(a), status_words(b))),
            Some(_) => {}
            None => notes.push(format!("the outcome {} ({}) is gone", a.outcome, status_words(a))),
        }
    }
    for b in n.statuses.iter().filter(|b| !o.statuses.iter().any(|a| a.outcome == b.outcome)) {
        notes.push(format!("a new outcome {} ({})", b.outcome, status_words(b)));
    }
    let codes = |s: &EntryPointSpec| -> BTreeSet<Option<u16>> { s.statuses.iter().map(|st| st.status).collect() };
    let (a, b) = (codes(o), codes(n));
    let unknown = a.contains(&None) || b.contains(&None);
    // With a status unknown on either side, a code only one side lists may be the unknown one.
    let differs = if unknown { &mut notes } else { &mut changed };
    for c in a.difference(&b).flatten() {
        differs.push(format!("the old build may answer {c}, the new one never does"));
    }
    for c in b.difference(&a).flatten() {
        differs.push(format!("the new build may answer {c}, the old one never does"));
    }
    let id = Observation::Status.id();
    if !changed.is_empty() {
        changed.extend(notes);
        obligation(&o.id, id, Change::Changed, changed, NEEDS_CHANGED)
    } else if unknown {
        notes.push("a status the analysis can't tell: the proof needs it modeled".into());
        obligation(&o.id, id, Change::Unresolved, notes, NEEDS_STATUS)
    } else {
        obligation(&o.id, id, Change::Preserved, notes, NEEDS_STATUS)
    }
}

fn site_words(e: &EffectSite) -> String {
    format!("{} {}, {}, in {}", if e.kind == SiteKind::Send && e.target.starts_with("to ") { "sends" } else { e.kind.verb() }, e.target, e.placement.words(), e.in_method)
}

/// One effect. Changed when its payload's paths differ, or its call sites differ in kind, target or transaction
/// placement; a different number of call sites is a difference the trace proof covers (it compares attempts, not
/// sites).
fn effect_obligation(o: &EntryPointSpec, n: &EntryPointSpec, call: &str, payload: &[String]) -> Obligation {
    let id = format!("effect:{call}");
    let Some(Observation::Effect { payload: now, .. }) = n.observations.iter().find(|x| x.id() == id) else { unreachable!("kept") };
    let mut changed: Vec<String> = payload.iter().filter(|p| !now.contains(p)).map(|p| format!("its payload no longer snapshots {p}")).collect();
    changed.extend(now.iter().filter(|p| !payload.contains(p)).map(|p| format!("its payload now also snapshots {p}")));
    let shape = |s: &EntryPointSpec| -> BTreeSet<(SiteKind, String, Placement)> { s.effects.iter().filter(|e| e.call == call).map(|e| (e.kind, e.target.clone(), e.placement)).collect() };
    let (a, b) = (shape(o), shape(n));
    let placements = |set: &BTreeSet<(SiteKind, String, Placement)>, k: SiteKind, t: &str| -> Vec<Placement> { set.iter().filter(|(k2, t2, _)| *k2 == k && t2 == t).map(|x| x.2).collect() };
    for (k, t, p) in a.difference(&b) {
        let elsewhere = placements(&b, *k, t);
        if elsewhere.is_empty() {
            changed.push(format!("the old build {} {t} by it ({}), the new one doesn't", k.verb(), p.words()));
        } else {
            changed.push(format!("{} {t}: {}, now {}", k.verb(), p.words(), elsewhere.iter().map(|p| p.words()).collect::<Vec<_>>().join(" and ")));
        }
    }
    for (k, t, p) in b.difference(&a) {
        if placements(&a, *k, t).is_empty() {
            changed.push(format!("the new build {} {t} by it ({}), the old one doesn't", k.verb(), p.words()));
        }
    }
    let count = |s: &EntryPointSpec| s.effects.iter().filter(|e| e.call == call).count();
    let notes: Vec<String> = if count(o) != count(n) { vec![format!("{} call sites in the old build, {} in the new", count(o), count(n))] } else { Vec::new() };
    if changed.is_empty() {
        obligation(&o.id, id, Change::Preserved, notes, NEEDS_EFFECT)
    } else {
        changed.extend(notes);
        obligation(&o.id, id, Change::Changed, changed, NEEDS_CHANGED)
    }
}

/// The obligations as text, grouped by entry point, with the accounting at the end, for
/// `jvmcontract observations --against`.
pub fn render_obligations(before: &[EntryPointSpec], obligations: &[Obligation]) -> String {
    let mut out = String::new();
    let mut last: Option<(&str, Option<&str>)> = None;
    let mut i = 0;
    while i < obligations.len() {
        let ob = &obligations[i];
        let here = (ob.entry.as_str(), ob.new_entry.as_deref());
        if last != Some(here) {
            match &ob.new_entry {
                Some(n) => out.push_str(&format!("{} (now {n})\n", ob.entry)),
                None => out.push_str(&format!("{}\n", ob.entry)),
            }
            last = Some(here);
        }
        // A run that differs only in the observation (an entry point removed or new) is one line.
        let same = |o: &Obligation| (o.entry.as_str(), o.new_entry.as_deref()) == here && o.change == ob.change && o.differences == ob.differences && o.needs == ob.needs;
        let run: Vec<&Obligation> = obligations[i..].iter().take_while(|o| same(o)).collect();
        let named: Vec<&str> = run
            .iter()
            .map(|o| match o.observation.as_str() {
                "unresolved" => "what the analysis can't see",
                other => other,
            })
            .collect();
        out.push_str(&format!("  {} {}\n", ob.change.words(), named.join(", ")));
        for d in &ob.differences {
            out.push_str(&format!("    - {d}\n"));
        }
        out.push_str(&format!("    needs {}\n", ob.needs));
        i += run.len();
    }
    let old: usize = before.iter().map(|s| s.observations.len()).sum();
    let count = |c: Change| obligations.iter().filter(|o| o.change == c && before.iter().any(|s| s.id == o.entry && s.observations.iter().any(|x| x.id() == o.observation))).count();
    let new = obligations.iter().filter(|o| o.change == Change::New).count();
    out.push_str(&format!(
        "{old} observations of {} entry points: {} to prove preserved, {} changed and {} removed (each preserved only with a person's approval), {} unresolved; {new} new\n",
        before.len(),
        count(Change::Preserved),
        count(Change::Changed),
        count(Change::Removed),
        count(Change::Unresolved),
    ));
    let gaps = unaccounted(before, obligations);
    if !gaps.is_empty() {
        out.push_str(&format!("not accounted for: {}\n", gaps.join("; ")));
    }
    out
}

impl Change {
    fn words(self) -> &'static str {
        match self {
            Change::Preserved => "preserved, to prove:",
            Change::Changed => "changed:",
            Change::New => "new:",
            Change::Removed => "removed:",
            Change::Unresolved => "unresolved:",
        }
    }
}
