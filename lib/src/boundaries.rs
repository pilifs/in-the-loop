//! Boundary contracts: where a framework enters a module and what it promises to do around each entry, read from
//! the annotations in the compiled classes and checked in. A Spring Boot service is mostly boundaries: HTTP routes,
//! message listeners, schedules, event listeners and bean definitions, with transactions, security, validation,
//! caching and retries declared as annotations whose effect the framework applies through a proxy. The contract
//! lists them all, so a pull request that drops a `@PreAuthorize`, widens a route, changes a transaction's rollback
//! rule or adds a scheduled job changes this file, and the diff is what a reviewer approves.
//!
//! It also finds the places where an annotation does not do what it says, which no test shows because the code runs
//! fine without the advice: a `@Transactional` or `@PreAuthorize` method called on `this` (the proxy is bypassed),
//! advice on a private, static or final method or a final class (the proxy cannot intercept it), a `@Transactional`
//! method whose declared checked exceptions commit (Spring rolls back on unchecked exceptions only), an `@Async`
//! method whose result is lost, a `@Cacheable` method returning nothing, and constraint annotations on a method the
//! framework never validates. Each is a `!` line in the contract, so introducing one changes the contract.
//!
//! After the beans, the activation block ([`crate::activation`]) names what switches each kind of annotation on: the
//! configuration with the `@Enable` annotation and how it is reached (local, imported, scanned, auto-configured),
//! the bean that applies the advice, or the provider on the class path. A `@Cacheable` with no `@EnableCaching` in
//! scope, an `@Async` with no `@EnableAsync`, a `@Valid` with no Bean Validation provider is read by nobody; each is a
//! `!` line.
//!
//! Then come the wire types: the JSON shape of every request body, response body and message type reachable
//! from the module's handlers, listeners and Jackson-annotated classes, from [`crate::wire`]. A renamed record
//! component or a subtype missing from `@JsonSubTypes` changes no signature and passes every test that encodes
//! and decodes with the same classes; here it is a changed line.
//!
//! The contract ends with the stored types ([`crate::store`]): the shape of each Spring Data MongoDB document
//! (the `_id`, each field under its stored name, the embedded types), with a `!` line for every query, update,
//! index, sort or projection string in the module that names a field the document does not have.
//!
//! Under each entry point and advised method go its reach lines ([`crate::reach`]): what it reads, writes, sends,
//! calls and publishes, found by following the calls in the bytecode through the application's own classes to the
//! data, messaging, HTTP client and event APIs, and placed with respect to transactions. A `GET` with side effects, a
//! read-only transaction that writes, a transaction that sends or makes an HTTP call (a dual write), an event
//! published with no transaction while a `@TransactionalEventListener` waits for it, and an after-commit listener
//! that writes are `!` lines. Under each entry point also goes what it throws, and for a route what each exception
//! becomes ([`crate::failures`]): the `@ExceptionHandler` that takes it and the status it answers with, the
//! `@ResponseStatus` on the exception, or a 500. An application exception nothing maps, and a second handler for a
//! type an advice already handles, are `!` lines.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::binding;
use crate::failures;
use crate::classfile::{flags, signature, simple_name_of, Annotation, ClassFile, ElementValue, Insn, Kind, Method, MethodDescriptor, Type, TypeTarget};
use crate::activation;
use crate::classpath::ClassPath;
use crate::config;
use crate::reach;
use crate::store;
use crate::validation;
use crate::wire;
use crate::Error;

pub const FILE_NAME: &str = "boundaries.contract";

/// The packages whose annotations a framework reads at run time. Anything else on a class is not a boundary.
const FRAMEWORK_PACKAGES: &[&str] = &[
    "org/springframework/",
    "jakarta/validation/",
    "jakarta/transaction/",
    "jakarta/annotation/",
    "javax/validation/",
    "javax/transaction/",
    "javax/annotation/",
    "org/hibernate/validator/constraints/",
    "io/github/resilience4j/",
    "io/micrometer/",
];

/// The HTTP request mappings, with the verb each shorthand stands for.
const MAPPINGS: &[(&str, &str)] = &[
    ("org/springframework/web/bind/annotation/RequestMapping", ""),
    ("org/springframework/web/bind/annotation/GetMapping", "GET"),
    ("org/springframework/web/bind/annotation/PostMapping", "POST"),
    ("org/springframework/web/bind/annotation/PutMapping", "PUT"),
    ("org/springframework/web/bind/annotation/DeleteMapping", "DELETE"),
    ("org/springframework/web/bind/annotation/PatchMapping", "PATCH"),
];

/// Listeners whose parameters arrive over the wire: their application types are wire types.
const WIRE_LISTENERS: &[&str] = &["KafkaListener", "KafkaHandler", "RabbitListener", "RabbitHandler", "JmsListener", "SqsListener", "MessageMapping", "SubscribeMapping"];

/// Annotations by which the framework calls into the module: a method with one is an entry point.
const ENTRIES: &[&str] = &[
    "KafkaListener",
    "KafkaHandler",
    "RabbitListener",
    "RabbitHandler",
    "JmsListener",
    "SqsListener",
    "EventListener",
    "TransactionalEventListener",
    "ApplicationModuleListener",
    "Scheduled",
    "Schedules",
    "MessageMapping",
    "SubscribeMapping",
    "ExceptionHandler",
    "InitBinder",
    "ServiceActivator",
    "Bean",
    "PostConstruct",
    "PreDestroy",
];

/// Advice the framework applies through a proxy around the bean: it works only for calls that reach the proxy.
const PROXIED: &[&str] = &[
    "Transactional",
    "Cacheable",
    "CachePut",
    "CacheEvict",
    "Caching",
    "Async",
    "PreAuthorize",
    "PostAuthorize",
    "PreFilter",
    "PostFilter",
    "Secured",
    "RolesAllowed",
    "PermitAll",
    "DenyAll",
    "Retryable",
    "CircuitBreaker",
    "RateLimiter",
    "Bulkhead",
    "TimeLimiter",
    "Retry",
    "Timed",
    "Counted",
    "Observed",
];

const VALIDATION_PACKAGES: &[&str] = &["jakarta/validation/", "javax/validation/", "org/hibernate/validator/constraints/"];

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Member {
    /// `POST /orders => ResponseEntity<Order> place(@Valid @RequestBody PlaceOrder request)`, or the signature alone.
    pub line: String,
    /// The advice on the member (`@Transactional(readOnly = true)`), what it reaches (`reads A, B`, `writes C`,
    /// `sends t`, `calls GET /x`, `publishes E`) and its problems (`! ...`), in that order.
    pub details: Vec<String>,
    /// Whether the framework calls this member (a route, a listener, a schedule, a bean definition).
    pub entry: bool,
    /// Whether the framework applies advice to it, on the member or on the whole class.
    pub advised: bool,
    pub problems: usize,
    /// The member's first source line, when the class was compiled with line numbers; for a configuration key,
    /// the line of the file that sets it.
    pub source_line: Option<u16>,
    /// The file the line is in, when it is not the class's own source (a configuration key set in a file).
    pub source_file: Option<PathBuf>,
    /// The class the line is in, when the block is not a class (a configuration key read by a class).
    pub source_class: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Bean {
    /// `@RestController @RequestMapping("/orders")`: the class's framework annotations.
    pub annotations: String,
    pub members: Vec<Member>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize)]
pub struct Boundaries {
    /// By binary name with dots.
    pub beans: BTreeMap<String, Bean>,
    /// What enables each annotation family the module uses ([`activation`]): the header names the application
    /// class and the packages it scans, the members are one line per family (`@Scheduled: @EnableScheduling on
    /// ...`) with a `!` problem when nothing enables it. `None` when the module uses no family.
    pub activation: Option<Bean>,
    /// The configuration keys: the files read in the header, one member per key with its type and values, the
    /// classes that read it and the `!` problems ([`config`]). `None` when the module has no application files and
    /// reads no keys.
    pub configuration: Option<Bean>,
    /// The wire types, by binary name with dots: the header is the kind of type and how it is encoded, the members
    /// are its properties (`name: Type`), subtypes, enum constants and `!` problems.
    pub types: BTreeMap<String, Bean>,
    /// The stored types ([`store`]), by binary name with dots: a `@Document` class or a type embedded in one; the
    /// header is the kind of type and its collection, the members its fields under their stored names and the `!`
    /// problems: the strings in the module's queries that name a field the document does not have.
    #[serde(default)]
    pub stored: BTreeMap<String, Bean>,
}

pub(crate) fn is_framework(annotation: &Annotation) -> bool {
    FRAMEWORK_PACKAGES.iter().any(|p| annotation.type_name.starts_with(p))
}

pub(crate) fn is_validation(annotation: &Annotation) -> bool {
    VALIDATION_PACKAGES.iter().any(|p| annotation.type_name.starts_with(p))
}

pub(crate) fn mapping_verb(annotation: &Annotation) -> Option<&'static str> {
    MAPPINGS.iter().find(|(t, _)| *t == annotation.type_name).map(|(_, verb)| *verb)
}

fn is_entry(annotation: &Annotation) -> bool {
    mapping_verb(annotation).is_some() || ENTRIES.contains(&annotation.simple_name().as_str())
}

fn is_proxied(annotation: &Annotation) -> bool {
    PROXIED.contains(&annotation.simple_name().as_str())
}

pub(crate) fn render_all(annotations: &[Annotation]) -> String {
    annotations.iter().map(Annotation::render).collect::<Vec<_>>().join(" ")
}

/// The paths of a mapping annotation: `value` or `path`, or one empty path.
fn mapping_paths(annotation: &Annotation) -> Vec<String> {
    let mut paths = annotation.strings("value");
    paths.extend(annotation.strings("path"));
    if paths.is_empty() {
        paths.push(String::new());
    }
    paths
}

pub(crate) fn join_paths(prefix: &str, path: &str) -> String {
    let mut out = String::new();
    for part in [prefix, path] {
        let part = part.trim_matches('/');
        if !part.is_empty() {
            out.push('/');
            out.push_str(part);
        }
    }
    if out.is_empty() {
        out.push('/');
    }
    out
}

/// `POST /orders/{id}/cancellation (consumes application/json)`, one route per verb and path.
pub(crate) fn routes(class_mappings: &[&Annotation], method: &Annotation) -> Vec<String> {
    let verb = mapping_verb(method).unwrap_or("");
    let mut verbs: Vec<String> = if verb.is_empty() { method.enum_names("method") } else { vec![verb.to_string()] };
    if verbs.is_empty() {
        verbs = class_mappings.iter().flat_map(|m| m.enum_names("method")).collect();
    }
    if verbs.is_empty() {
        verbs.push("ANY".to_string());
    }
    let prefixes: Vec<String> = if class_mappings.is_empty() { vec![String::new()] } else { class_mappings.iter().flat_map(|m| mapping_paths(m)).collect() };
    let mut conditions = Vec::new();
    for (name, label) in [("consumes", "consumes"), ("produces", "produces"), ("params", "params"), ("headers", "headers")] {
        let mut values = method.strings(name);
        if values.is_empty() {
            values = class_mappings.iter().flat_map(|m| m.strings(name)).collect();
        }
        if !values.is_empty() {
            conditions.push(format!("{label} {}", values.join(", ")));
        }
    }
    let suffix = if conditions.is_empty() { String::new() } else { format!(" ({})", conditions.join("; ")) };
    let mut out = Vec::new();
    for verb in &verbs {
        for prefix in &prefixes {
            for path in mapping_paths(method) {
                out.push(format!("{verb} {}{suffix}", join_paths(prefix, &path)));
            }
        }
    }
    out
}


/// The receiver of a call on an instance method of the same class, when it is `this` loaded directly before the
/// arguments: `this.m(a, b)` compiles to `aload_0`, the arguments, `invokevirtual`. The walk goes back over the
/// argument expressions counting stack values, and gives up (`None`) at a jump target, a stack shuffle it does
/// not model, or a receiver that is anything else.
fn receiver_is_this(class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, call: usize, arguments: usize) -> Option<bool> {
    let at = pushing(class, insns, targets, call, arguments)?;
    Some(matches!(insns[at].1, Insn::Load(Kind::Ref, 0)))
}

/// The index of the instruction that pushed the value `depth` slots below the top of the stack at `call` (`0` is
/// the last argument, `arguments` the receiver), walking back over the instructions before it; `None` at a jump
/// target or a stack shuffle the walk does not model.
pub(crate) fn pushing(class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, call: usize, depth: usize) -> Option<usize> {
    let mut depth = depth;
    let mut i = call;
    while i > 0 {
        if targets.contains(&insns[i].0) {
            return None;
        }
        i -= 1;
        let insn = &insns[i].1;
        // `dup` pushes two copies of the value below it: either copy was pushed by the instruction before.
        if matches!(insn, Insn::Dup) {
            if depth < 2 {
                depth = 0;
                continue;
            }
            depth -= 1;
            continue;
        }
        let (pops, pushes) = stack_effect(class, insn)?;
        if pushes > depth {
            return (pushes == 1).then_some(i);
        }
        depth = depth - pushes + pops;
    }
    None
}

/// How many values an instruction pops and pushes, counting a `long` or `double` as one value; `None` for the
/// instructions whose effect depends on the values' categories.
fn stack_effect(class: &ClassFile, insn: &Insn) -> Option<(usize, usize)> {
    use crate::classfile::ArithOp;
    Some(match insn {
        Insn::Nop | Insn::IInc(..) | Insn::Goto(_) => (0, 0),
        Insn::AConstNull | Insn::IConst(_) | Insn::LConst(_) | Insn::FConst(_) | Insn::DConst(_) | Insn::Ldc(_) | Insn::Load(..) | Insn::New(_) => (0, 1),
        Insn::Store(..) | Insn::Pop | Insn::If(..) | Insn::IfNull(_) | Insn::IfNonNull(_) | Insn::TableSwitch { .. } | Insn::LookupSwitch { .. } | Insn::AThrow | Insn::MonitorEnter | Insn::MonitorExit | Insn::PutStatic(_) => (1, 0),
        Insn::ArrayLoad(_) | Insn::Cmp(_) => (2, 1),
        Insn::ArrayStore(_) => (3, 0),
        Insn::Arith(ArithOp::Neg, _) | Insn::Convert(..) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::ArrayLength | Insn::CheckCast(_) | Insn::InstanceOf(_) | Insn::GetField(_) => (1, 1),
        Insn::Arith(..) => (2, 1),
        Insn::IfICmp(..) | Insn::IfACmp(..) | Insn::PutField(_) => (2, 0),
        Insn::Return(kind) => (usize::from(kind.is_some()), 0),
        Insn::GetStatic(_) => (0, 1),
        Insn::MultiANewArray(_, dims) => (*dims as usize, 1),
        Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => {
            let member = class.pool.member(*i).ok()?;
            let d = MethodDescriptor::parse(&member.descriptor).ok()?;
            let receiver = usize::from(!matches!(insn, Insn::InvokeStatic(_)));
            (d.params.len() + receiver, usize::from(d.ret != Type::Void))
        }
        Insn::InvokeDynamic(i) => {
            let (_, _, descriptor) = class.pool.invoke_dynamic(*i).ok()?;
            let d = MethodDescriptor::parse(descriptor).ok()?;
            (d.params.len(), usize::from(d.ret != Type::Void))
        }
        Insn::Pop2 | Insn::Dup | Insn::DupX1 | Insn::DupX2 | Insn::Dup2 | Insn::Dup2X1 | Insn::Dup2X2 | Insn::Swap | Insn::Jsr(_) | Insn::Ret(_) => return None,
    })
}

pub(crate) fn jump_targets(insns: &[(u32, Insn)], method: &Method) -> BTreeSet<u32> {
    let mut targets = BTreeSet::new();
    for (_, insn) in insns {
        match insn {
            Insn::If(_, t) | Insn::IfICmp(_, t) | Insn::IfACmp(_, t) | Insn::IfNull(t) | Insn::IfNonNull(t) | Insn::Goto(t) | Insn::Jsr(t) => {
                targets.insert(*t);
            }
            Insn::TableSwitch { default, targets: ts, .. } => {
                targets.insert(*default);
                targets.extend(ts.iter().copied());
            }
            Insn::LookupSwitch { default, pairs } => {
                targets.insert(*default);
                targets.extend(pairs.iter().map(|(_, t)| *t));
            }
            _ => {}
        }
    }
    if let Some(code) = &method.code {
        targets.extend(code.exception_table.iter().map(|h| u32::from(h.handler_pc)));
    }
    targets
}

/// Every call of an instance method of `class` on `this`, as (caller name and descriptor, callee name, callee
/// descriptor).
fn self_calls(class: &ClassFile) -> Vec<(String, String, String, String)> {
    let mut out = Vec::new();
    for method in &class.methods {
        if method.is_static() {
            continue;
        }
        let Some(code) = &method.code else { continue };
        let Ok(insns) = code.instructions() else { continue };
        let targets = jump_targets(&insns, method);
        for (i, (_, insn)) in insns.iter().enumerate() {
            let index = match insn {
                Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeInterface(i) => *i,
                _ => continue,
            };
            let Ok(member) = class.pool.member(index) else { continue };
            if member.owner != class.name || member.name == "<init>" {
                continue;
            }
            let Ok(d) = MethodDescriptor::parse(&member.descriptor) else { continue };
            if receiver_is_this(class, &insns, &targets, i, d.params.len()) == Some(true) {
                out.push((method.name.clone(), method.descriptor.clone(), member.name.clone(), member.descriptor.clone()));
            }
        }
    }
    out
}

/// `place(String, String)`, or `a lambda in place(String, String)` for the synthetic method of a lambda.
fn caller_label(class: &ClassFile, name: &str, descriptor: &str) -> String {
    let params = |d: &str| MethodDescriptor::parse(d).map(|d| d.params.iter().map(Type::simple_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
    if let Some(rest) = name.strip_prefix("lambda$") {
        if let Some((outer, _)) = rest.rsplit_once('$') {
            let outer_descriptor = class.methods.iter().find(|m| m.name == outer).map(|m| m.descriptor.clone()).unwrap_or_default();
            return format!("a lambda in {outer}({})", params(&outer_descriptor));
        }
    }
    format!("{name}({})", params(descriptor))
}

pub(crate) fn type_names(method: &Method, pool: &crate::classfile::ConstantPool, d: &MethodDescriptor) -> (Vec<String>, String) {
    if let Some(sig) = method.generic_signature(pool) {
        if let Some((params, ret)) = signature::method_types(&sig) {
            if params.len() == d.params.len() {
                return (params, ret);
            }
        }
    }
    (d.params.iter().map(Type::simple_name).collect(), d.ret.simple_name())
}

fn d_params_empty(descriptor: &str) -> bool {
    descriptor.starts_with("()")
}

fn is_checked(cp: &ClassPath, exception: &str) -> bool {
    cp.exists(exception) && !cp.is_subtype(exception, "java/lang/RuntimeException") && !cp.is_subtype(exception, "java/lang/Error")
}

/// The boundaries of every application class on the class path.
pub fn analyse(cp: &ClassPath) -> Result<Boundaries, Error> {
    analyse_in(cp, None, None, &[])
}

/// The boundaries of the named application classes (internal names), or of all of them; the whole class path
/// resolves the types the checks ask about (which exceptions are checked, what an `@Async` method returns). The
/// wire types are followed into `local` classes (the module and its sibling modules), or into every application
/// class when `local` is `None`; the configuration keys are those the local classes read and those the
/// application files under `resources` set.
pub fn analyse_in(cp: &ClassPath, only: Option<&BTreeSet<String>>, local: Option<&BTreeSet<String>>, resources: &[PathBuf]) -> Result<Boundaries, Error> {
    let mut boundaries = Boundaries::default();
    let classes = cp.application_classes()?;
    let graph = reach::Graph::new(cp, &classes, local);
    // The events a `@TransactionalEventListener` waits for, by the name the reach lines use: an event published
    // with no transaction to commit never reaches one (unless it asks for fallbackExecution).
    let mut transactional_listeners: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (name, class) in &classes {
        if local.is_some_and(|l| !l.contains(name)) {
            continue;
        }
        for method in &class.methods {
            let Ok(annotations) = method.annotations(&class.pool) else { continue };
            let Some(listener) = annotations.iter().find(|a| a.simple_name() == "TransactionalEventListener") else { continue };
            if listener.element("fallbackExecution") == Some(&ElementValue::Boolean(true)) {
                continue;
            }
            let mut events = listener.classes("classes");
            events.extend(listener.classes("value"));
            if events.is_empty() {
                if let Ok(d) = MethodDescriptor::parse(&method.descriptor) {
                    if let Some(Type::Object(c)) = d.params.first() {
                        events.push(c.clone());
                    }
                }
            }
            for event in events {
                transactional_listeners.entry(reach::display(&event)).or_default().push(format!("{}.{}", simple_name_of(name), method.name));
            }
        }
    }
    // With a transactional Kafka producer, a send inside a transaction is synchronised with it (committed after
    // the database commit, aborted on rollback): not atomic, but not the plain dual write either.
    let kafka_transactional = config::read_files(resources)?.1.iter().any(|s| s.key == "spring.kafka.producer.transaction-id-prefix");
    // The exception handlers, to say what each exception a route throws becomes.
    let exception_handlers = failures::Handlers::collect(cp, &classes, local);
    let is_local = |c: &str| classes.contains_key(c) && local.is_none_or(|l| l.contains(c));
    // Every route of the module by its pattern, to find two handlers that claim the same requests.
    let mut handlers: BTreeMap<String, Vec<(String, String)>> = BTreeMap::new();
    for (name, class) in &classes {
        if local.is_some_and(|l| !l.contains(name)) || class.access & (flags::ANNOTATION | flags::SYNTHETIC) != 0 {
            continue;
        }
        let Ok(class_annotations) = class.annotations() else { continue };
        let class_mappings: Vec<&Annotation> = class_annotations.iter().filter(|a| mapping_verb(a).is_some()).collect();
        for method in &class.methods {
            if method.is_synthetic() || method.is_bridge() {
                continue;
            }
            let Ok(annotations) = method.annotations(&class.pool) else { continue };
            for a in annotations.iter().filter(|a| mapping_verb(a).is_some()) {
                for route in routes(&class_mappings, a) {
                    handlers.entry(binding::pattern_key(&route)).or_default().push((format!("{}.{}", simple_name_of(name), method.name), route));
                }
            }
        }
    }
    let mut roots: Vec<String> = Vec::new();
    let mut field_only: BTreeSet<String> = BTreeSet::new();
    for (name, class) in &classes {
        if class.access & flags::ANNOTATION != 0 || class.access & flags::SYNTHETIC != 0 {
            continue;
        }
        if only.is_some_and(|set| !set.contains(name)) {
            continue;
        }
        let all_class_annotations = class.annotations().map_err(|e| Error::new(format!("{name}: {e}")))?;
        let class_annotation_names: Vec<String> = all_class_annotations.iter().map(|a| a.type_name.clone()).collect();
        let mut jackson = all_class_annotations.iter().any(wire::is_jackson);
        let class_annotations: Vec<Annotation> = all_class_annotations.into_iter().filter(is_framework).collect();
        let class_mappings: Vec<&Annotation> = class_annotations.iter().filter(|a| mapping_verb(a).is_some()).collect();
        let class_advice: Vec<&Annotation> = class_annotations.iter().filter(|a| is_proxied(a)).collect();
        let class_validated = class_annotations.iter().any(|a| a.simple_name() == "Validated");
        let class_final = class.is_final() && !class.is_record() && !class.is_enum();
        let calls = self_calls(class);
        let mut members = Vec::new();
        let mut method_members = false;


        for field in &class.fields {
            if field.access & flags::SYNTHETIC != 0 {
                continue;
            }
            let all = field.annotations(&class.pool).map_err(|e| Error::new(format!("{name}: {e}")))?;
            jackson |= all.iter().any(wire::is_jackson);
            let annotations: Vec<Annotation> = all.into_iter().filter(is_framework).collect();
            if annotations.is_empty() {
                continue;
            }
            let t = wire::field_type_name(class, field);
            members.push(Member { line: format!("{} {t} {}", render_all(&annotations), field.name), details: Vec::new(), entry: false, advised: false, problems: 0, source_line: None, source_file: None, source_class: None });
        }

        for method in &class.methods {
            if method.is_synthetic() || method.is_bridge() || method.is_class_initializer() || method.is_constructor() {
                continue;
            }
            let all = method.annotations(&class.pool).map_err(|e| Error::new(format!("{name}: {e}")))?;
            jackson |= all.iter().any(wire::is_jackson);
            let annotations: Vec<Annotation> = all.into_iter().filter(is_framework).collect();
            // A record component's constraints are copied by the compiler onto the accessor: the field line has them.
            if class.is_record() && d_params_empty(&method.descriptor) && class.fields.iter().any(|f| f.name == method.name) && !annotations.is_empty() && annotations.iter().all(|a| is_validation(a) || a.type_name.starts_with("org/springframework/data/")) {
                continue;
            }
            let parameter_annotations: Vec<Vec<Annotation>> = method
                .parameter_annotations(&class.pool)
                .map_err(|e| Error::new(format!("{name}: {e}")))?
                .into_iter()
                .map(|list| list.into_iter().filter(is_framework).collect())
                .collect();
            let under_class_advice = !class_advice.is_empty() && method.is_public() && !method.is_static();
            if annotations.is_empty() && parameter_annotations.iter().all(Vec::is_empty) && !under_class_advice {
                continue;
            }
            let Ok(d) = MethodDescriptor::parse(&method.descriptor) else { continue };
            let (param_types, ret) = type_names(method, &class.pool, &d);
            let names = method.parameter_names(&class.pool);
            let params: Vec<String> = param_types
                .iter()
                .enumerate()
                .map(|(i, t)| {
                    let anns = render_all(&parameter_annotations[i]);
                    let pname = names.get(i).cloned().unwrap_or_else(|| format!("arg{i}"));
                    if anns.is_empty() { format!("{t} {pname}") } else { format!("{anns} {t} {pname}") }
                })
                .collect();
            let signature = format!("{ret} {}({})", method.name, params.join(", "));

            let mut entries: Vec<String> = Vec::new();
            let mut advice: Vec<String> = Vec::new();
            for a in &annotations {
                if mapping_verb(a).is_some() {
                    entries.extend(routes(&class_mappings, a));
                } else if is_entry(a) {
                    entries.push(a.render());
                } else {
                    advice.push(a.render());
                }
            }
            let line = if entries.is_empty() { signature.clone() } else { format!("{} => {signature}", entries.join(", ")) };

            // The advice that applies: the method's own, then the class's for a public instance method.
            let mut applied: Vec<&Annotation> = annotations.iter().filter(|a| is_proxied(a)).collect();
            if under_class_advice {
                applied.extend(class_advice.iter().copied());
            }
            let mut problems: Vec<String> = Vec::new();
            if !applied.is_empty() {
                let listed = applied.iter().map(|a| format!("@{}", a.simple_name())).collect::<BTreeSet<_>>().into_iter().collect::<Vec<_>>().join(", ");
                let reason = if method.is_private() {
                    Some("a private method: the proxy cannot intercept it")
                } else if method.is_static() {
                    Some("a static method: the proxy cannot intercept it")
                } else if method.is_final() {
                    Some("a final method: the CGLIB proxy cannot override it")
                } else if class_final {
                    Some("a method of a final class: the CGLIB proxy cannot subclass it")
                } else {
                    None
                };
                if let Some(reason) = reason {
                    problems.push(format!("! {listed} on {reason}"));
                }
                for (caller, caller_descriptor, callee, callee_descriptor) in &calls {
                    if callee == &method.name && callee_descriptor == &method.descriptor {
                        problems.push(format!("! self-invocation from {}: the call does not go through the proxy, so {listed} does not apply to it", caller_label(class, caller, caller_descriptor)));
                    }
                }
                for a in &applied {
                    match a.simple_name().as_str() {
                        "Transactional" => {
                            let rollback_classes = {
                                let mut c = a.classes("rollbackFor");
                                c.extend(a.classes("rollbackOn"));
                                c
                            };
                            let rollback_names = a.strings("rollbackForClassName");
                            for exception in method.declared_exceptions(&class.pool).unwrap_or_default() {
                                if !is_checked(cp, &exception) {
                                    continue;
                                }
                                let covered = rollback_classes.iter().any(|r| cp.is_subtype(&exception, r)) || rollback_names.iter().any(|n| exception.replace('/', ".").contains(n));
                                if !covered {
                                    problems.push(format!("! commits on {}: a checked exception is not a rollback cause unless rollbackFor names it", crate::classfile::simple_name_of(&exception)));
                                }
                            }
                        }
                        "Async" => {
                            let ok = match &d.ret {
                                Type::Void => true,
                                Type::Object(c) => cp.is_subtype(c, "java/util/concurrent/Future") || cp.is_subtype(c, "java/util/concurrent/CompletionStage"),
                                _ => false,
                            };
                            if !ok {
                                problems.push(format!("! @Async returns {ret}: a result that is not a Future is lost, the caller gets null"));
                            }
                        }
                        "Cacheable" if d.ret == Type::Void => problems.push("! @Cacheable on a void method caches nothing".to_string()),
                        _ => {}
                    }
                }
            }
            if annotations.iter().any(|a| a.simple_name() == "Scheduled" || a.simple_name() == "Schedules") && !d.params.is_empty() {
                problems.push("! @Scheduled method takes parameters: the scheduler cannot call it".to_string());
            }
            // Whether each parameter of a handler can bind to the request, and whether another handler claims its routes.
            let route_entries: Vec<String> = annotations.iter().filter(|a| mapping_verb(a).is_some()).flat_map(|a| routes(&class_mappings, a)).collect();
            if !route_entries.is_empty() {
                let reflective = method.reflective_parameter_names(&class.pool);
                problems.extend(binding::check(&route_entries, &d, &param_types, &names, reflective.as_deref(), &parameter_annotations));
                problems.extend(binding::clashes(&route_entries, &format!("{}.{}", simple_name_of(name), method.name), &handlers));
            }
            let constrained: Vec<String> = parameter_annotations
                .iter()
                .enumerate()
                .filter(|(_, list)| list.iter().any(is_validation))
                .map(|(i, _)| names.get(i).cloned().unwrap_or_else(|| format!("arg{i}")))
                .collect();
            let handler = annotations.iter().any(|a| mapping_verb(a).is_some());
            // The wire types: request bodies and responses of handlers, payloads of listeners.
            let (param_refs, ret_refs) = wire::method_refs(class, method);
            if handler || annotations.iter().any(|a| a.simple_name() == "ExceptionHandler") {
                let type_annotations = method.type_annotations(&class.pool).unwrap_or_default();
                for (i, list) in parameter_annotations.iter().enumerate() {
                    if !list.iter().any(|a| matches!(a.simple_name().as_str(), "RequestBody" | "RequestPart")) {
                        continue;
                    }
                    roots.extend(param_refs[i].iter().cloned());
                    // The body's constraints run only under a @Valid or @Validated, and only those of the groups asked for.
                    let constrained_types: Vec<&String> = param_refs[i].iter().filter(|c| validation::constrained(cp, local, c)).collect();
                    if constrained_types.is_empty() {
                        continue;
                    }
                    let pname = names.get(i).cloned().unwrap_or_else(|| format!("arg{i}"));
                    let valid = list.iter().any(validation::is_valid) || type_annotations.iter().any(|t| t.target == TypeTarget::Parameter(i as u8) && validation::is_valid(&t.annotation));
                    let validated = list.iter().find(|a| a.simple_name() == "Validated");
                    if !valid && validated.is_none() {
                        problems.push(format!("! constraints on {} are not checked: no @Valid on {pname}", constrained_types.iter().map(|c| simple_name_of(c)).collect::<Vec<_>>().join(", ")));
                        continue;
                    }
                    let groups = validated.and_then(validation::validated_groups);
                    let unchecked: Vec<String> = constrained_types.iter().flat_map(|c| validation::unchecked(cp, local, c, groups.as_deref())).collect();
                    if unchecked.is_empty() {
                        continue;
                    }
                    let shown = if unchecked.len() > 3 { format!("{} and {} more", unchecked[..3].join(", "), unchecked.len() - 3) } else { unchecked.join(", ") };
                    match &groups {
                        None => problems.push(format!("! @Valid validates the Default group only: {shown} {} not checked", if unchecked.len() == 1 { "is" } else { "are" })),
                        Some(g) => problems.push(format!("! @Validated({}) validates {} only: {shown} {} not checked", g.iter().map(|c| format!("{}.class", simple_name_of(c))).collect::<Vec<_>>().join(", "), if g.len() == 1 { "that group" } else { "those groups" }, if unchecked.len() == 1 { "is" } else { "are" })),
                    }
                }
                roots.extend(ret_refs);
            } else if annotations.iter().any(|a| WIRE_LISTENERS.contains(&a.simple_name().as_str())) {
                for (i, list) in parameter_annotations.iter().enumerate() {
                    if !list.iter().any(|a| matches!(a.simple_name().as_str(), "Header" | "Headers")) {
                        roots.extend(param_refs[i].iter().cloned());
                    }
                }
            }
            let validated = class_validated || annotations.iter().any(|a| a.simple_name() == "Validated");
            if !constrained.is_empty() && !handler && !validated {
                problems.push(format!("! constraints on {} are not enforced: the method is not a request handler and the class is not @Validated", constrained.join(", ")));
            } else if !constrained.is_empty() && !handler && (method.is_private() || method.is_static()) {
                problems.push(format!("! constraints on {} are not enforced: method validation goes through the proxy, which intercepts public instance methods only", constrained.join(", ")));
            }

            // What the entry point or advised method reaches, and the places where that contradicts its contract.
            let reached = if entries.is_empty() && applied.is_empty() { reach::Reach::default() } else { graph.reach(name, &method.name, &method.descriptor) };
            let mut throws_line: Option<String> = None;
            if entries.iter().any(|e| e.starts_with("GET ") || e.starts_with("HEAD ")) {
                let effects = reached.all.side_effects();
                if !effects.is_empty() {
                    problems.push(format!("! a GET that {}: a safe method with side effects, so a retry, a prefetch or a crawler changes state", effects.join(" and ")));
                }
            }
            if !reached.all.writes.is_empty() && applied.iter().any(|a| a.simple_name() == "Transactional" && a.element("readOnly") == Some(&ElementValue::Boolean(true))) {
                problems.push(format!("! @Transactional(readOnly = true) but writes {}: a read-only transaction drops or rejects writes", reached.all.writes.iter().cloned().collect::<Vec<_>>().join(", ")));
            }
            // Dual writes: a send or an HTTP call inside a transaction this method opens is not part of it.
            if !kafka_transactional && !reached.inside.sends.is_empty() {
                let to: Vec<String> = reached.inside.sends.iter().map(|t| if t.starts_with("to ") { t.clone() } else { format!("to {t}") }).collect();
                problems.push(format!("! a transaction that sends {}: the send is not part of the transaction, so a rollback leaves the message sent and a crash before the send leaves the commit unannounced", reach::join_and(&to.into_iter().collect())));
            }
            if !reached.inside.calls.is_empty() {
                problems.push(format!("! a transaction that calls {}: the call is not part of the transaction, so a rollback does not undo it, and the transaction stays open for the round trip", reach::join_and(&reached.inside.calls)));
            }
            // An event published with no transaction to commit never reaches a @TransactionalEventListener.
            for event in &reached.outside.publishes {
                if let Some(listeners) = transactional_listeners.get(event) {
                    let (verb, noun, run) = if listeners.len() == 1 { ("is", "a @TransactionalEventListener", "does") } else { ("are", "@TransactionalEventListeners", "do") };
                    problems.push(format!("! publishes {event} outside a transaction: {} {verb} {noun}, which {run} not run when no transaction commits (fallbackExecution is false)", reach::join_and(&listeners.iter().cloned().collect())));
                }
            }
            // After the commit, the transaction's resources are still bound to the thread and nothing commits again.
            if let Some(listener) = annotations.iter().find(|a| a.simple_name() == "TransactionalEventListener") {
                let phase = match listener.element("phase") {
                    Some(ElementValue::Enum(_, p)) => p.clone(),
                    _ => "AFTER_COMMIT".to_string(),
                };
                let own_transaction = applied.iter().any(|a| a.simple_name() == "Transactional" && matches!(a.element("propagation"), Some(ElementValue::Enum(_, p)) if p == "REQUIRES_NEW"));
                let asynchronous = applied.iter().any(|a| a.simple_name() == "Async");
                if phase != "BEFORE_COMMIT" && !own_transaction && !asynchronous && !reached.all.writes.is_empty() {
                    problems.push(format!("! an {phase} listener that writes {}: the transaction has committed and nothing commits again, so a JPA or JDBC write here is never committed unless the method opens its own transaction (propagation = REQUIRES_NEW)", reach::join_and(&reached.all.writes)));
                }
            }
            // What it throws, and what each exception becomes at the boundary.
            if !entries.is_empty() {
                let thrown = graph.throws(name, &method.name, &method.descriptor);
                if handler {
                    let (line, unmapped) = failures::describe(cp, &exception_handlers, name, &class_annotation_names, &thrown, &is_local);
                    throws_line = line;
                    problems.extend(unmapped);
                } else {
                    throws_line = failures::list(&thrown);
                }
            }
            if annotations.iter().any(|a| a.simple_name() == "ExceptionHandler") {
                problems.extend(exception_handlers.duplicate(name, &method.name));
            }
            let mut details = advice;
            details.extend(reached.all.lines());
            details.extend(throws_line);
            let problem_count = problems.len();
            details.extend(problems);
            members.push(Member { line, details, entry: !entries.is_empty(), advised: !applied.is_empty(), problems: problem_count, source_line: method.first_line(), source_file: None, source_class: None });
            method_members = true;
        }

        if jackson {
            roots.push(name.clone());
        }
        if class_annotations.is_empty() && members.is_empty() {
            continue;
        }
        let dotted = name.replace('/', ".");
        if class_annotations.is_empty() && !method_members {
            field_only.insert(dotted.clone());
        }
        boundaries.beans.insert(dotted, Bean { annotations: render_all(&class_annotations), members });
    }
    boundaries.types = wire::analyse(cp, local, &roots)?;
    // A request type whose only framework annotations are its constraints is shown once, as a wire type with the
    // constraints on its properties.
    for name in field_only {
        if boundaries.types.contains_key(&name) {
            boundaries.beans.remove(&name);
        }
    }
    boundaries.activation = activation::analyse(cp, &classes, only)?;
    boundaries.configuration = config::analyse(cp, local, resources)?;
    boundaries.stored = store::analyse(cp, only, local)?;
    Ok(boundaries)
}

impl Boundaries {
    pub fn entry_points(&self) -> usize {
        self.beans.values().flat_map(|b| &b.members).filter(|m| m.entry).count()
    }

    pub fn advised(&self) -> usize {
        self.beans.values().flat_map(|b| &b.members).filter(|m| m.advised).count()
    }

    pub fn problems(&self) -> usize {
        self.blocks().flat_map(|(_, b)| &b.members).map(|m| m.problems).sum()
    }

    pub fn configuration_keys(&self) -> usize {
        self.configuration.as_ref().map_or(0, |c| c.members.len())
    }

    pub fn stats(&self) -> String {
        format!("{} beans, {} entry points, {} advised methods, {} configuration keys, {} wire types, {} stored types, {} problems", self.beans.len(), self.entry_points(), self.advised(), self.configuration_keys(), self.types.len(), self.stored.len(), self.problems())
    }

    /// The beans, then the activation and configuration blocks, then the wire types under their `wire ` prefix and
    /// the stored types under `stored `, as the contract lists them.
    fn blocks(&self) -> impl Iterator<Item = (String, &Bean)> {
        self.beans
            .iter()
            .map(|(n, b)| (n.clone(), b))
            .chain(self.activation.iter().map(|b| ("activation".to_string(), b)))
            .chain(self.configuration.iter().map(|b| ("configuration".to_string(), b)))
            .chain(self.types.iter().map(|(n, b)| (format!("wire {n}"), b)))
            .chain(self.stored.iter().map(|(n, b)| (format!("stored {n}"), b)))
    }

    /// Comparable entries: `type: annotations`, `type: member` and `type: member: detail` lines.
    pub fn entries(&self) -> BTreeSet<String> {
        let mut out = BTreeSet::new();
        for (name, bean) in self.blocks() {
            out.insert(format!("{name}: {}", bean.annotations));
            for m in &bean.members {
                out.insert(format!("{name}: {}", m.line));
                for d in &m.details {
                    out.insert(format!("{name}: {}: {d}", m.line));
                }
            }
        }
        out
    }

    /// The first member whose line or details are among the added entries of a diff, with its class, for anchoring
    /// a finding.
    pub fn first_added(&self, diff: &[String]) -> Option<(String, &Member)> {
        for line in diff {
            let Some(entry) = line.strip_prefix("  added ") else { continue };
            for (name, bean) in self.blocks() {
                for m in &bean.members {
                    if entry == format!("{name}: {}", m.line) || entry.starts_with(&format!("{name}: {}: ", m.line)) {
                        let class = name.strip_prefix("wire ").or_else(|| name.strip_prefix("stored ")).unwrap_or(&name);
                        return Some((class.to_string(), m));
                    }
                }
            }
        }
        None
    }

    pub fn render(&self, module: &str) -> String {
        let mut lines = vec![
            "# Boundary contract, generated by jvmcontract. Do not edit: regenerate it with `jvmcontract update`.".to_string(),
            "# It lists where the framework enters this module (routes, listeners, schedules, bean definitions) and the".to_string(),
            "# advice on each bean (transactions, security, validation, caching, retries), from the annotations in the".to_string(),
            "# compiled classes, then what enables each kind of annotation (an @Enable annotation, an auto-configuration,".to_string(),
            "# a provider on the class path), then the configuration keys (what the classes read, what the application".to_string(),
            "# files set, what the class path's metadata declares), then the wire types (the JSON shape of each request,".to_string(),
            "# response and message type) and the stored types (the shape of each document, and the query strings that".to_string(),
            "# name a field it does not have). Under each entry point, what it reaches: the documents it reads and writes,".to_string(),
            "# the topics it sends to, the HTTP calls it makes, the events it publishes, the exceptions it throws and what".to_string(),
            "# each becomes (the handler that takes it, or a 500). A `!` line is a place where something does not do".to_string(),
            "# what it says.".to_string(),
            "kind: boundaries".to_string(),
            format!("module: {module}, {}", self.stats()),
            String::new(),
        ];
        for (name, bean) in self.blocks() {
            lines.push(if bean.annotations.is_empty() { format!("{name}:") } else { format!("{name}: {}", bean.annotations) });
            for m in &bean.members {
                lines.push(format!("  {}", m.line));
                for d in &m.details {
                    lines.push(format!("    {d}"));
                }
            }
            lines.push(String::new());
        }
        let mut text = lines.join("\n");
        text.push('\n');
        text
    }

    pub fn write(&self, file: &Path, module: &str) -> Result<(), Error> {
        if let Some(parent) = file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(file, self.render(module))?;
        Ok(())
    }
}

/// The entries of a checked-in boundary contract, comparable with [`Boundaries::entries`].
pub fn read(file: &Path) -> Result<BTreeSet<String>, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("cannot read {}: {e}", file.display())))?;
    parse(&text)
}

pub fn parse(text: &str) -> Result<BTreeSet<String>, Error> {
    let mut out = BTreeSet::new();
    let mut bean: Option<String> = None;
    let mut member: Option<String> = None;
    for line in text.lines() {
        if line.trim().is_empty() || line.starts_with('#') || line.starts_with("kind:") || line.starts_with("module:") {
            continue;
        }
        if let Some(detail) = line.strip_prefix("    ") {
            let (b, m) = match (&bean, &member) {
                (Some(b), Some(m)) => (b, m),
                _ => return Err(Error::new(format!("boundary contract: detail before any member: {line:?}"))),
            };
            out.insert(format!("{b}: {m}: {detail}"));
        } else if let Some(m) = line.strip_prefix("  ") {
            let b = bean.as_deref().ok_or_else(|| Error::new(format!("boundary contract: member before any bean: {line:?}")))?;
            out.insert(format!("{b}: {m}"));
            member = Some(m.to_string());
        } else {
            let (name, rest) = line.split_once(':').ok_or_else(|| Error::new(format!("boundary contract: bad bean line {line:?}")))?;
            bean = Some(name.to_string());
            member = None;
            out.insert(format!("{name}: {}", rest.trim_start()));
        }
    }
    Ok(out)
}

pub fn diff(contract: &BTreeSet<String>, actual: &BTreeSet<String>) -> Vec<String> {
    let mut lines: Vec<String> = actual.difference(contract).map(|e| format!("  added {e}")).collect();
    lines.extend(contract.difference(actual).map(|e| format!("  removed {e}")));
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn routes_compose_the_class_prefix_and_the_verb() {
        let class = Annotation { type_name: MAPPINGS[0].0.to_string(), elements: vec![("value".into(), crate::classfile::ElementValue::Array(vec![crate::classfile::ElementValue::String("/orders".into())]))] };
        let get = Annotation { type_name: MAPPINGS[1].0.to_string(), elements: vec![("value".into(), crate::classfile::ElementValue::String("/{id}".into()))] };
        assert_eq!(routes(&[&class], &get), vec!["GET /orders/{id}"]);
        let any = Annotation { type_name: MAPPINGS[0].0.to_string(), elements: vec![] };
        assert_eq!(routes(&[&class], &any), vec!["ANY /orders"]);
        assert_eq!(routes(&[], &any), vec!["ANY /"]);
        assert_eq!(join_paths("/a/", "/b"), "/a/b");
    }

    #[test]
    fn a_contract_reads_back_as_its_entries() {
        let text = "kind: boundaries\nmodule: m\n\na.B: @Service @Transactional\n  void run(int n)\n    @Async\n    ! @Async returns int\n\na.C:\n  GET /x => int get()\n";
        let entries = parse(text).unwrap();
        assert!(entries.contains("a.B: @Service @Transactional"));
        assert!(entries.contains("a.B: void run(int n)"));
        assert!(entries.contains("a.B: void run(int n): ! @Async returns int"));
        assert!(entries.contains("a.C: "));
        assert!(entries.contains("a.C: GET /x => int get()"));
        assert_eq!(entries.len(), 6);
    }
}
