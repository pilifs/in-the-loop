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
//! The contract ends with the wire types: the JSON shape of every request body, response body and message type
//! reachable from the module's handlers, listeners and Jackson-annotated classes, from [`crate::wire`]. A renamed
//! record component or a subtype missing from `@JsonSubTypes` changes no signature and passes every test that
//! encodes and decodes with the same classes; here it is a changed line.

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use serde::Serialize;

use crate::classfile::{flags, signature, Annotation, ClassFile, Insn, Kind, Method, MethodDescriptor, Type};
use crate::classpath::ClassPath;
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
    /// The advice on the member (`@Transactional(readOnly = true)`) and its problems (`! ...`), in that order.
    pub details: Vec<String>,
    /// Whether the framework calls this member (a route, a listener, a schedule, a bean definition).
    pub entry: bool,
    /// Whether the framework applies advice to it, on the member or on the whole class.
    pub advised: bool,
    pub problems: usize,
    /// The member's first source line, when the class was compiled with line numbers.
    pub source_line: Option<u16>,
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
    /// The wire types, by binary name with dots: the header is the kind of type and how it is encoded, the members
    /// are its properties (`name: Type`), subtypes, enum constants and `!` problems.
    pub types: BTreeMap<String, Bean>,
}

fn is_framework(annotation: &Annotation) -> bool {
    FRAMEWORK_PACKAGES.iter().any(|p| annotation.type_name.starts_with(p))
}

pub(crate) fn is_validation(annotation: &Annotation) -> bool {
    VALIDATION_PACKAGES.iter().any(|p| annotation.type_name.starts_with(p))
}

fn mapping_verb(annotation: &Annotation) -> Option<&'static str> {
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

fn join_paths(prefix: &str, path: &str) -> String {
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
fn routes(class_mappings: &[&Annotation], method: &Annotation) -> Vec<String> {
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

fn kebab(name: &str) -> String {
    let mut out = String::new();
    for c in name.chars() {
        if c.is_ascii_uppercase() {
            if !out.is_empty() {
                out.push('-');
            }
            out.push(c.to_ascii_lowercase());
        } else {
            out.push(c);
        }
    }
    out
}

/// The receiver of a call on an instance method of the same class, when it is `this` loaded directly before the
/// arguments: `this.m(a, b)` compiles to `aload_0`, the arguments, `invokevirtual`. The walk goes back over the
/// argument expressions counting stack values, and gives up (`None`) at a jump target, a stack shuffle it does
/// not model, or a receiver that is anything else.
fn receiver_is_this(class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, call: usize, arguments: usize) -> Option<bool> {
    let mut depth = arguments;
    let mut i = call;
    while i > 0 {
        if targets.contains(&insns[i].0) {
            return None;
        }
        i -= 1;
        let insn = &insns[i].1;
        let (pops, pushes) = stack_effect(class, insn)?;
        if pushes > depth {
            return Some(pushes == 1 && matches!(insn, Insn::Load(Kind::Ref, 0)));
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

fn jump_targets(insns: &[(u32, Insn)], method: &Method) -> BTreeSet<u32> {
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

fn type_names(method: &Method, pool: &crate::classfile::ConstantPool, d: &MethodDescriptor) -> (Vec<String>, String) {
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
    analyse_in(cp, None, None)
}

/// The boundaries of the named application classes (internal names), or of all of them; the whole class path
/// resolves the types the checks ask about (which exceptions are checked, what an `@Async` method returns). The
/// wire types are followed into `local` classes (the module and its sibling modules), or into every application
/// class when `local` is `None`.
pub fn analyse_in(cp: &ClassPath, only: Option<&BTreeSet<String>>, local: Option<&BTreeSet<String>>) -> Result<Boundaries, Error> {
    let mut boundaries = Boundaries::default();
    let classes = cp.application_classes()?;
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
        let mut jackson = all_class_annotations.iter().any(wire::is_jackson);
        let class_annotations: Vec<Annotation> = all_class_annotations.into_iter().filter(is_framework).collect();
        let class_mappings: Vec<&Annotation> = class_annotations.iter().filter(|a| mapping_verb(a).is_some()).collect();
        let class_advice: Vec<&Annotation> = class_annotations.iter().filter(|a| is_proxied(a)).collect();
        let class_validated = class_annotations.iter().any(|a| a.simple_name() == "Validated");
        let class_final = class.is_final() && !class.is_record() && !class.is_enum();
        let calls = self_calls(class);
        let mut members = Vec::new();
        let mut method_members = false;

        // Configuration properties: the keys the class binds, with Boot's relaxed names.
        if let Some(props) = class_annotations.iter().find(|a| a.simple_name() == "ConfigurationProperties") {
            let mut prefix = props.strings("prefix");
            prefix.extend(props.strings("value"));
            let prefix = prefix.into_iter().next().unwrap_or_default();
            for field in &class.fields {
                if field.is_static() || field.access & flags::SYNTHETIC != 0 {
                    continue;
                }
                let t = field.generic_signature(&class.pool).and_then(|s| signature::field_type(&s)).or_else(|| Type::parse(&field.descriptor).ok().map(|t| t.simple_name())).unwrap_or_else(|| field.descriptor.clone());
                let key = if prefix.is_empty() { kebab(&field.name) } else { format!("{prefix}.{}", kebab(&field.name)) };
                members.push(Member { line: format!("{key}: {t}"), details: Vec::new(), entry: false, advised: false, problems: 0, source_line: None });
            }
        }

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
            members.push(Member { line: format!("{} {t} {}", render_all(&annotations), field.name), details: Vec::new(), entry: false, advised: false, problems: 0, source_line: None });
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
                for (i, list) in parameter_annotations.iter().enumerate() {
                    if list.iter().any(|a| matches!(a.simple_name().as_str(), "RequestBody" | "RequestPart")) {
                        roots.extend(param_refs[i].iter().cloned());
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
            }

            let mut details = advice;
            let problem_count = problems.len();
            details.extend(problems);
            members.push(Member { line, details, entry: !entries.is_empty(), advised: !applied.is_empty(), problems: problem_count, source_line: method.first_line() });
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
        self.beans.values().chain(self.types.values()).flat_map(|b| &b.members).map(|m| m.problems).sum()
    }

    pub fn stats(&self) -> String {
        format!("{} beans, {} entry points, {} advised methods, {} wire types, {} problems", self.beans.len(), self.entry_points(), self.advised(), self.types.len(), self.problems())
    }

    /// The beans, then the wire types under their `wire ` prefix, as the contract lists them.
    fn blocks(&self) -> impl Iterator<Item = (String, &Bean)> {
        self.beans.iter().map(|(n, b)| (n.clone(), b)).chain(self.types.iter().map(|(n, b)| (format!("wire {n}"), b)))
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
                        return Some((name.strip_prefix("wire ").unwrap_or(&name).to_string(), m));
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
            "# compiled classes, then the wire types: the JSON shape of each request, response and message type.".to_string(),
            "# A `!` line is a place where an annotation does not do what it says.".to_string(),
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
        assert_eq!(kebab("sweepInterval"), "sweep-interval");
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
