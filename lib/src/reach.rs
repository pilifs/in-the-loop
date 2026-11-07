//! What each entry point reaches: the documents and tables it reads and writes, the topics it sends to, the HTTP
//! calls it makes and the application events it publishes, found by following the calls in the bytecode from the
//! entry point through the application's own classes (the module and its sibling modules) to the framework APIs
//! that do the work.
//!
//! The walk is a may-reach approximation. Every call site is followed: a virtual call to every local subtype
//! that overrides the method, a lambda to its body whether or not the receiver ever runs it, a call on `this`
//! like any other. It does not follow the framework: a call into Spring, the JDK or a driver is a leaf, and the
//! leaves that matter are classified by their owner and name. The Spring Data templates and repositories, the
//! JPA `EntityManager` and Spring's JDBC helpers give reads and writes, the Kafka, RabbitMQ, JMS and Spring
//! Cloud Stream templates give sends, `RestTemplate`, `RestClient`, `WebClient` and `@HttpExchange` or Feign
//! interfaces give HTTP calls, `ApplicationEventPublisher` gives events.
//!
//! Each effect is also placed with respect to transactions: reached with no transaction on the path, or inside a
//! transaction the method itself opens (its `@Transactional`, or a lambda it passes to `TransactionTemplate` or
//! to a helper that runs its argument through one). A `@Transactional` method of another class on the path
//! takes its effects for itself. The checks on dual writes (a send or an HTTP call inside a transaction), on
//! an event published outside one, and on a write in an after-commit listener read these.
//!
//! What a read or write is of comes from the call site: a class literal argument (`find(query,
//! SeatDocument.class)`), else the static type of the entity argument (`insert(hold)`, from the local variable
//! table, a `new`, a field or the return type of the call that produced it), else the documents the method
//! mentions, else `a document`. A topic, a URL or a table is the constant string the call site passes; a value
//! computed at run time is `to Kafka`, `a computed URL` or `SQL`.
//!
//! The same graph gives what each entry point throws ([`Graph::throws`]): the `throw` statements, `orElseThrow`
//! suppliers and Spring `Assert` calls in every method it reaches, less the exceptions a `catch` on the path
//! takes and does not rethrow. A handler that rethrows its caught variable (a `finally`, a retry loop, a log
//! and rethrow) passes everything through. What becomes of each exception at the boundary is
//! [`crate::failures`]'s question.

use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::rc::Rc;

use crate::boundaries::{join_paths, jump_targets, pushing};
use crate::classfile::{Annotation, BootstrapArg, ClassFile, Constant, ElementValue, Insn, Kind, MemberRef, Method, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::store;

/// Packages whose classes are leaves: a call into one is an effect or nothing, and is never followed.
const LEAF_PACKAGES: &[&str] = &[
    "java/",
    "javax/",
    "jakarta/",
    "jdk/",
    "sun/",
    "kotlin/",
    "scala/",
    "org/springframework/",
    "org/apache/",
    "com/mongodb/",
    "org/bson/",
    "org/hibernate/",
    "io/micrometer/",
    "reactor/",
    "org/reactivestreams/",
    "org/slf4j/",
    "ch/qos/",
    "com/fasterxml/",
    "tools/jackson/",
    "io/netty/",
    "org/postgresql/",
    "com/zaxxer/",
    "org/jetbrains/",
    "io/awspring/",
    "feign/",
];

const LAMBDA_METAFACTORY: &str = "java/lang/invoke/LambdaMetafactory";

/// The HTTP client interfaces: Spring's `@HttpExchange` family and the MVC mappings Feign clients use.
const EXCHANGES: &[(&str, &str)] = &[
    ("org/springframework/web/service/annotation/HttpExchange", ""),
    ("org/springframework/web/service/annotation/GetExchange", "GET"),
    ("org/springframework/web/service/annotation/PostExchange", "POST"),
    ("org/springframework/web/service/annotation/PutExchange", "PUT"),
    ("org/springframework/web/service/annotation/PatchExchange", "PATCH"),
    ("org/springframework/web/service/annotation/DeleteExchange", "DELETE"),
    ("org/springframework/web/bind/annotation/RequestMapping", ""),
    ("org/springframework/web/bind/annotation/GetMapping", "GET"),
    ("org/springframework/web/bind/annotation/PostMapping", "POST"),
    ("org/springframework/web/bind/annotation/PutMapping", "PUT"),
    ("org/springframework/web/bind/annotation/DeleteMapping", "DELETE"),
    ("org/springframework/web/bind/annotation/PatchMapping", "PATCH"),
];

/// Annotations that make a class a stored type, for the fallback when a call site does not say which one it
/// reads or writes.
const STORED: &[&str] = &["org/springframework/data/mongodb/core/mapping/Document", "jakarta/persistence/Entity", "javax/persistence/Entity", "org/springframework/data/relational/core/mapping/Table", "org/springframework/data/elasticsearch/annotations/Document", "org/springframework/data/redis/core/RedisHash"];

/// A set of effects: each set holds display names (`SeatDocument`, `payments.commands`, `GET /users/{id}`,
/// `OrderPlaced`), sorted.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Effects {
    pub reads: BTreeSet<String>,
    pub writes: BTreeSet<String>,
    pub sends: BTreeSet<String>,
    pub calls: BTreeSet<String>,
    pub publishes: BTreeSet<String>,
}

/// What a method reaches, transitively, and where that stands with respect to transactions.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Reach {
    /// Everything, on any path.
    pub all: Effects,
    /// Reached on a path with no transaction: not under the method's own `@Transactional`, not inside a lambda a
    /// transaction runner executes, not under a `@Transactional` method of another class.
    pub outside: Effects,
    /// Reached inside a transaction this method opens: its own `@Transactional`, or a lambda it (or a callee)
    /// passes to `TransactionTemplate` or to a helper that runs its argument through one. What a
    /// `@Transactional` method of another class on the path reaches is left to that method.
    pub inside: Effects,
    /// Each call that gives one of the effects above, with where it stands with respect to transactions, for the
    /// observation spec ([`crate::observations`]). Sorted, each once.
    pub sites: Vec<Placed>,
    /// The `invokedynamic` call sites the walk doesn't follow (anything but a lambda), as `Bootstrap.method in
    /// Class.method(Types)`.
    pub dynamic: BTreeSet<String>,
    /// The calls into application code the walk can't follow: a class outside the followed ones, or an
    /// application interface nothing followed implements and that is no repository or HTTP client.
    pub unresolved: BTreeSet<String>,
}

/// What kind of effect a call site gives.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SiteKind {
    Read,
    Write,
    Send,
    Call,
    Publish,
}

/// One call into a framework API (or an application interface the framework implements) that gives an effect.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Site {
    pub kind: SiteKind,
    /// What it is of or to, as the reach lines name it: `SeatDocument`, `quotes`, `GET /users/{id}`.
    pub target: String,
    /// The method called, as `owner#name(descriptor)` with the owner's internal name.
    pub call: String,
    /// The static type at the call site of each argument (an internal class name), when the walk can tell.
    pub arguments: Vec<Option<String>>,
    /// The method the call is in, as `Class.method(Types)`.
    pub in_method: String,
}

/// Where a call site stands with respect to transactions, from the root's point of view.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Placement {
    /// On a path with no transaction.
    Outside,
    /// Inside a transaction the root opens.
    Inside,
    /// Inside a `@Transactional` method of another class, which opens or joins its own.
    Callee,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Placed {
    pub placement: Placement,
    pub site: Site,
}

/// Where on the walk a method runs with respect to transactions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum Scope {
    /// No transaction on the path so far.
    Outside,
    /// Inside a transaction the root opened: by its own annotation, or by a lambda handed to a runner.
    Own,
    /// Inside a `@Transactional` method of another class, which accounts for its own effects.
    Callee,
}

impl Effects {
    pub fn is_empty(&self) -> bool {
        self.reads.is_empty() && self.writes.is_empty() && self.sends.is_empty() && self.calls.is_empty() && self.publishes.is_empty()
    }

    fn extend(&mut self, other: &Effects) {
        self.reads.extend(other.reads.iter().cloned());
        self.writes.extend(other.writes.iter().cloned());
        self.sends.extend(other.sends.iter().cloned());
        self.calls.extend(other.calls.iter().cloned());
        self.publishes.extend(other.publishes.iter().cloned());
    }

    /// The contract's lines: `reads A, B`, `writes C`, `sends t`, `calls GET /x`, `publishes E`, those that apply.
    pub fn lines(&self) -> Vec<String> {
        [("reads", &self.reads), ("writes", &self.writes), ("sends", &self.sends), ("calls", &self.calls), ("publishes", &self.publishes)]
            .into_iter()
            .filter(|(_, set)| !set.is_empty())
            .map(|(verb, set)| format!("{verb} {}", join(set)))
            .collect()
    }

    /// The effects that change state somewhere: the writes, sends, publishes and the HTTP calls that are not
    /// `GET`s, as phrases (`writes A and B`).
    pub fn side_effects(&self) -> Vec<String> {
        let mut out = Vec::new();
        if !self.writes.is_empty() {
            out.push(format!("writes {}", join_and(&self.writes)));
        }
        if !self.sends.is_empty() {
            out.push(format!("sends {}", join_and(&self.sends)));
        }
        if !self.publishes.is_empty() {
            out.push(format!("publishes {}", join_and(&self.publishes)));
        }
        let unsafe_calls: BTreeSet<String> = self.calls.iter().filter(|c| !c.starts_with("GET ") && !c.starts_with("HEAD ") && !c.starts_with("OPTIONS ")).cloned().collect();
        if !unsafe_calls.is_empty() {
            out.push(format!("calls {}", join_and(&unsafe_calls)));
        }
        out
    }
}

fn join(set: &BTreeSet<String>) -> String {
    set.iter().cloned().collect::<Vec<_>>().join(", ")
}

pub(crate) fn join_and(set: &BTreeSet<String>) -> String {
    let items: Vec<&String> = set.iter().collect();
    match items.len() {
        0 => String::new(),
        1 => items[0].clone(),
        n => format!("{} and {}", items[..n - 1].iter().map(|s| s.as_str()).collect::<Vec<_>>().join(", "), items[n - 1]),
    }
}

enum Effect {
    Read(String),
    Write(String),
    Send(String),
    Call(String),
    Publish(String),
}

/// What one method does itself: its leaf effects and the application methods it calls, by key.
#[derive(Default)]
struct Direct {
    reach: Effects,
    callees: Vec<String>,
    /// The lambdas handed to a call that may run them inside a transaction: the callee's key (empty for
    /// `TransactionTemplate` itself) and the lambda's.
    scoped: Vec<(String, String)>,
    /// Calls `TransactionTemplate.execute` (or `executeWithoutResult`) itself.
    opens_transaction: bool,
    /// The exceptions the method throws itself, by internal name, less those a handler of its own catches without
    /// rethrowing. A `ResponseStatusException` carries the status it was built with: `...ResponseStatusException:NOT_FOUND`.
    throws: Vec<String>,
    /// For each callee, one entry per site that calls it: the catch types of the handlers covering the site that
    /// swallow what they catch (empty at a site under no such handler).
    guards: HashMap<String, Vec<Vec<String>>>,
    /// The effect-giving call sites of the method itself.
    sites: Vec<Site>,
    /// Its `invokedynamic` sites that are not lambdas.
    dynamic: Vec<String>,
    /// Its calls into application code the walk can't follow.
    unresolved: Vec<String>,
}

const RESPONSE_STATUS_EXCEPTIONS: &[&str] = &["org/springframework/web/server/ResponseStatusException", "org/springframework/web/ErrorResponseException"];
const HTTP_STATUS: &str = "org/springframework/http/HttpStatus";

/// A handler's range and what it catches (`Throwable` for a `finally` or a synchronized block's release), when
/// its code never rethrows the caught variable.
struct Swallowing {
    start: u32,
    end: u32,
    catches: String,
}

const TRANSACTIONAL: &[&str] = &["org/springframework/transaction/annotation/Transactional", "jakarta/transaction/Transactional", "javax/transaction/Transactional"];

/// `TransactionTemplate.execute(callback)` and the like: the callback runs inside a transaction.
fn opens_transaction(member: &MemberRef) -> bool {
    matches!(member.owner.as_str(), "org/springframework/transaction/support/TransactionTemplate" | "org/springframework/transaction/support/TransactionOperations") && member.name.starts_with("execute")
}

fn key(owner: &str, name: &str, descriptor: &str) -> String {
    format!("{owner}.{name}{descriptor}")
}

pub fn is_leaf(owner: &str) -> bool {
    LEAF_PACKAGES.iter().any(|p| owner.starts_with(p))
}

/// The application's call graph, over the classes to follow, with each method's direct effects computed once.
pub struct Graph<'a> {
    cp: &'a ClassPath,
    /// The classes the walk goes into, by internal name.
    classes: BTreeMap<String, Rc<ClassFile>>,
    /// The direct subtypes of each followed class, among the followed classes.
    children: HashMap<String, Vec<String>>,
    direct: RefCell<HashMap<String, Rc<Direct>>>,
    /// Whether each method runs a functional argument inside a transaction, once asked.
    runners: RefCell<HashMap<String, bool>>,
    /// Whether each method is `@Transactional` (itself or through its class), once asked.
    annotated: RefCell<HashMap<String, bool>>,
    /// Whether each method is `@Async` (itself or through its class), once asked.
    asynchronous: RefCell<HashMap<String, bool>>,
}

impl<'a> Graph<'a> {
    /// The graph over `classes` (the application classes) restricted to `local` (the module and its siblings)
    /// and to the packages that are not a framework's.
    pub fn new(cp: &'a ClassPath, classes: &BTreeMap<String, Rc<ClassFile>>, local: Option<&BTreeSet<String>>) -> Graph<'a> {
        let classes: BTreeMap<String, Rc<ClassFile>> = classes.iter().filter(|(name, _)| local.is_none_or(|l| l.contains(*name)) && !is_leaf(name)).map(|(n, c)| (n.clone(), c.clone())).collect();
        let mut children: HashMap<String, Vec<String>> = HashMap::new();
        for (name, class) in &classes {
            if let Some(sup) = &class.super_class {
                children.entry(sup.clone()).or_default().push(name.clone());
            }
            for i in &class.interfaces {
                children.entry(i.clone()).or_default().push(name.clone());
            }
        }
        Graph { cp, classes, children, direct: RefCell::new(HashMap::new()), runners: RefCell::new(HashMap::new()), annotated: RefCell::new(HashMap::new()), asynchronous: RefCell::new(HashMap::new()) }
    }

    /// Everything the method reaches, transitively, placed with respect to transactions. A method is visited
    /// once per scope it is reached in.
    pub fn reach(&self, owner: &str, name: &str, descriptor: &str) -> Reach {
        let mut out = Reach::default();
        let mut seen: HashSet<(String, Scope)> = HashSet::new();
        let root = key(owner, name, descriptor);
        let start = if self.transactional(&root) { Scope::Own } else { Scope::Outside };
        let mut work = vec![(root, start)];
        while let Some((k, scope)) = work.pop() {
            if !seen.insert((k.clone(), scope)) {
                continue;
            }
            let Some(direct) = self.direct(&k) else { continue };
            out.all.extend(&direct.reach);
            match scope {
                Scope::Outside => out.outside.extend(&direct.reach),
                Scope::Own => out.inside.extend(&direct.reach),
                Scope::Callee => {}
            }
            let placement = match scope {
                Scope::Outside => Placement::Outside,
                Scope::Own => Placement::Inside,
                Scope::Callee => Placement::Callee,
            };
            out.sites.extend(direct.sites.iter().map(|site| Placed { placement, site: site.clone() }));
            out.dynamic.extend(direct.dynamic.iter().cloned());
            out.unresolved.extend(direct.unresolved.iter().cloned());
            let owner_of = |k: &str| k.split_once('.').map(|(o, _)| o.to_string()).unwrap_or_default();
            let caller_owner = owner_of(&k);
            for c in &direct.callees {
                // A `@Transactional` callee of another class takes its effects for itself; on `this` the proxy
                // is bypassed and nothing changes. A lambda handed to a runner enters the root's own transaction.
                let next = if scope == Scope::Callee || (owner_of(c) != caller_owner && self.transactional(c)) {
                    Scope::Callee
                } else if scope == Scope::Outside && direct.scoped.iter().any(|(runner, lambda)| lambda == c && (runner.is_empty() || self.runner(runner))) {
                    Scope::Own
                } else {
                    scope
                };
                if !seen.contains(&(c.clone(), next)) {
                    work.push((c.clone(), next));
                }
            }
        }
        out.sites.sort();
        out.sites.dedup();
        out
    }

    /// The exceptions the method may throw to its caller, by internal name: what every method it reaches throws
    /// itself, less what a handler on the path catches without rethrowing. An exception escapes a callee when some
    /// site that calls it is under no handler that takes the exception's type. An `@Async` callee of another class
    /// throws on its own thread, and nothing reaches the caller.
    pub fn throws(&self, owner: &str, name: &str, descriptor: &str) -> BTreeSet<String> {
        let root = key(owner, name, descriptor);
        let mut order = Vec::new();
        let mut seen: HashSet<String> = HashSet::new();
        let mut work = vec![root.clone()];
        while let Some(k) = work.pop() {
            if !seen.insert(k.clone()) {
                continue;
            }
            let Some(direct) = self.direct(&k) else { continue };
            order.push(k);
            work.extend(direct.callees.iter().cloned());
        }
        let owner_of = |k: &str| k.split_once('.').map(|(o, _)| o.to_string()).unwrap_or_default();
        let mut thrown: HashMap<String, BTreeSet<String>> = HashMap::new();
        loop {
            let mut changed = false;
            for k in &order {
                let Some(direct) = self.direct(k) else { continue };
                let mut set: BTreeSet<String> = direct.throws.iter().cloned().collect();
                for c in &direct.callees {
                    if owner_of(c) != owner_of(k) && self.asynchronous(c) {
                        continue;
                    }
                    let Some(from_callee) = thrown.get(c) else { continue };
                    let sites = direct.guards.get(c);
                    for e in from_callee {
                        let escapes = sites.is_none_or(|sites| sites.iter().any(|catches| !catches.iter().any(|t| self.cp.is_subtype(base_type(e), t))));
                        if escapes {
                            set.insert(e.clone());
                        }
                    }
                }
                if thrown.get(k) != Some(&set) {
                    thrown.insert(k.clone(), set);
                    changed = true;
                }
            }
            if !changed {
                break;
            }
        }
        thrown.remove(&root).unwrap_or_default()
    }

    /// Whether the method is `@Async`, itself or through its class (for an instance method).
    fn asynchronous(&self, k: &str) -> bool {
        if let Some(a) = self.asynchronous.borrow().get(k) {
            return *a;
        }
        let found = (|| {
            let (owner, rest) = k.split_once('.')?;
            let paren = rest.find('(')?;
            let (name, descriptor) = rest.split_at(paren);
            let class = self.classes.get(owner)?;
            let method = class.method(name, descriptor)?;
            let is_async = |annotations: &[Annotation]| annotations.iter().any(|a| a.type_name == "org/springframework/scheduling/annotation/Async");
            if is_async(&method.annotations(&class.pool).ok()?) {
                return Some(true);
            }
            if method.is_static() {
                return Some(false);
            }
            Some(is_async(&class.annotations().ok()?))
        })()
        .unwrap_or(false);
        self.asynchronous.borrow_mut().insert(k.to_string(), found);
        found
    }

    /// Whether the method is `@Transactional`, itself or through its class (for an instance method), with a
    /// propagation that joins or opens a transaction.
    fn transactional(&self, k: &str) -> bool {
        if let Some(t) = self.annotated.borrow().get(k) {
            return *t;
        }
        let found = (|| {
            let (owner, rest) = k.split_once('.')?;
            let paren = rest.find('(')?;
            let (name, descriptor) = rest.split_at(paren);
            let class = self.classes.get(owner)?;
            let method = class.method(name, descriptor)?;
            let joins = |annotations: &[Annotation]| {
                annotations.iter().any(|a| TRANSACTIONAL.contains(&a.type_name.as_str()) && !matches!(a.element("propagation"), Some(ElementValue::Enum(_, p)) if p == "NOT_SUPPORTED" || p == "NEVER"))
            };
            let own = method.annotations(&class.pool).ok()?;
            if joins(&own) {
                return Some(true);
            }
            if method.is_static() {
                return Some(false);
            }
            Some(joins(&class.annotations().ok()?))
        })()
        .unwrap_or(false);
        self.annotated.borrow_mut().insert(k.to_string(), found);
        found
    }

    /// Whether a call to the method runs its functional arguments inside a transaction: it, or something it
    /// reaches, is `@Transactional` or calls `TransactionTemplate`. An over-approximation: a lambda the method
    /// takes may run outside the transaction it opens.
    fn runner(&self, k: &str) -> bool {
        if let Some(r) = self.runners.borrow().get(k) {
            return *r;
        }
        let mut found = false;
        let mut seen: HashSet<String> = HashSet::new();
        let mut work = vec![k.to_string()];
        while let Some(m) = work.pop() {
            if !seen.insert(m.clone()) {
                continue;
            }
            if self.transactional(&m) {
                found = true;
                break;
            }
            let Some(direct) = self.direct(&m) else { continue };
            if direct.opens_transaction {
                found = true;
                break;
            }
            work.extend(direct.callees.iter().cloned());
        }
        self.runners.borrow_mut().insert(k.to_string(), found);
        found
    }

    fn direct(&self, k: &str) -> Option<Rc<Direct>> {
        if let Some(d) = self.direct.borrow().get(k) {
            return Some(d.clone());
        }
        let (owner, rest) = k.split_once('.')?;
        let paren = rest.find('(')?;
        let (name, descriptor) = rest.split_at(paren);
        let class = self.classes.get(owner)?.clone();
        let method = class.method(name, descriptor)?.clone();
        let d = Rc::new(self.compute(&class, &method));
        self.direct.borrow_mut().insert(k.to_string(), d.clone());
        Some(d)
    }

    fn compute(&self, class: &ClassFile, method: &Method) -> Direct {
        let mut out = Direct::default();
        let Some(code) = &method.code else { return out };
        let Ok(insns) = code.instructions() else { return out };
        let targets = jump_targets(&insns, method);
        let bootstrap = class.bootstrap_methods().unwrap_or_default();
        let (swallowing, caught_slots) = handlers(class, code, &insns, &targets);
        let catches_at = |pc: u32| -> Vec<String> { swallowing.iter().filter(|h| h.start <= pc && pc < h.end).map(|h| h.catches.clone()).collect() };
        // A throw at `pc` escapes the method unless a swallowing handler there takes its type. The compiler's own
        // guards (the `MatchException` of an exhaustive switch, an `assert`) are not the application's.
        let throws = |out: &mut Direct, pc: u32, e: String| {
            if matches!(base_type(&e), "java/lang/MatchException" | "java/lang/AssertionError") {
                return;
            }
            if !catches_at(pc).iter().any(|t| self.cp.is_subtype(base_type(&e), t)) && !out.throws.contains(&e) {
                out.throws.push(e);
            }
        };
        // The verb of the fluent HTTP client chain being built (`client.get().uri(...)`).
        let mut verb: Option<String> = None;
        let here = method_label(class, method);
        for (i, (pc, insn)) in insns.iter().enumerate() {
            match insn {
                Insn::InvokeVirtual(idx) | Insn::InvokeSpecial(idx) | Insn::InvokeStatic(idx) | Insn::InvokeInterface(idx) => {
                    let Ok(member) = class.pool.member(*idx) else { continue };
                    if is_leaf(&member.owner) || !self.classes.contains_key(&member.owner) {
                        if opens_transaction(&member) {
                            out.opens_transaction = true;
                            for lambda in self.lambda_args(class, &insns, &targets, i, &member, &bootstrap) {
                                out.scoped.push((String::new(), lambda));
                            }
                        }
                        let effects = self.leaf(class, method, &insns, &targets, i, &member, &mut verb);
                        if !effects.is_empty() {
                            let arguments = self.argument_types(class, method, &insns, &targets, i, &member);
                            out.sites.extend(effects.iter().map(|e| site(e, &member, &arguments, &here)));
                        } else if !is_leaf(&member.owner) && !self.classes.contains_key(&member.owner) && self.cp.is_application(&member.owner) {
                            out.unresolved.push(format!("{}.{} in {here}: a class the walk doesn't follow", display(&member.owner), member.name));
                        }
                        for effect in effects {
                            apply(&mut out.reach, effect);
                        }
                        for e in self.leaf_throws(class, &insns, &targets, i, &member, &bootstrap) {
                            throws(&mut out, *pc, e);
                        }
                        continue;
                    }
                    let exact = matches!(insn, Insn::InvokeSpecial(_) | Insn::InvokeStatic(_));
                    let callees = self.resolve(&member, exact);
                    if callees.is_empty() {
                        let effects = self.interface_effects(class, method, &insns, &targets, i, &member);
                        if effects.is_empty() {
                            out.unresolved.push(format!("{}.{} in {here}: nothing followed implements it", display(&member.owner), member.name));
                        } else {
                            let arguments = self.argument_types(class, method, &insns, &targets, i, &member);
                            out.sites.extend(effects.iter().map(|e| site(e, &member, &arguments, &here)));
                        }
                        for effect in effects {
                            apply(&mut out.reach, effect);
                        }
                    }
                    let lambdas = self.lambda_args(class, &insns, &targets, i, &member, &bootstrap);
                    for callee in &callees {
                        for lambda in &lambdas {
                            out.scoped.push((callee.clone(), lambda.clone()));
                        }
                        out.guards.entry(callee.clone()).or_default().push(catches_at(*pc));
                    }
                    out.callees.extend(callees);
                }
                Insn::InvokeDynamic(idx) => {
                    for callee in self.lambda_targets(class, &bootstrap, *idx) {
                        out.guards.entry(callee.clone()).or_default().push(catches_at(*pc));
                        out.callees.push(callee);
                    }
                    if let Some(b) = class.pool.invoke_dynamic(*idx).ok().and_then(|(bsm, _, _)| bootstrap.get(usize::from(bsm))) {
                        if b.method.member.owner != LAMBDA_METAFACTORY {
                            let what = format!("{}.{} in {here}", display(&b.method.member.owner), b.method.member.name);
                            if !out.dynamic.contains(&what) {
                                out.dynamic.push(what);
                            }
                        }
                    }
                }
                Insn::AThrow => {
                    if let Some(e) = self.thrown_type(class, method, &insns, &targets, i, &caught_slots) {
                        throws(&mut out, *pc, e);
                    }
                }
                _ => {}
            }
        }
        out
    }

    /// What a `throw` at `at` throws: the class a `new` built (with its status, for a `ResponseStatusException`),
    /// the type of the variable, field or call that produced the value; nothing for a caught variable thrown again
    /// (the handler passes its exceptions through) or a value the walk cannot type.
    fn thrown_type(&self, class: &ClassFile, method: &Method, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, caught_slots: &HashSet<u16>) -> Option<String> {
        let k = pushing(class, insns, targets, at, 0)?;
        let object = |t: &str| Type::parse(t).ok().and_then(|t| match t {
            Type::Object(name) => Some(name),
            _ => None,
        });
        match &insns[k].1 {
            Insn::New(idx) => {
                let name = class.pool.class_name(*idx).ok()?.to_string();
                Some(self.with_status(class, insns, targets, k, at, name))
            }
            Insn::Load(Kind::Ref, slot) if caught_slots.contains(slot) => None,
            Insn::Load(Kind::Ref, slot) => {
                let pc = insns[k].0;
                let code = method.code.as_ref()?;
                let local = code.local_variables.iter().find(|v| v.index == *slot && u32::from(v.start_pc) <= pc && pc < u32::from(v.start_pc) + u32::from(v.length))?;
                object(&local.descriptor)
            }
            Insn::InvokeVirtual(idx) | Insn::InvokeStatic(idx) | Insn::InvokeSpecial(idx) | Insn::InvokeInterface(idx) => {
                let member = class.pool.member(*idx).ok()?;
                match MethodDescriptor::parse(&member.descriptor).ok()?.ret {
                    Type::Object(name) if name != "java/lang/Object" => Some(name),
                    _ => None,
                }
            }
            Insn::CheckCast(idx) => Some(class.pool.class_name(*idx).ok()?.to_string()),
            Insn::GetField(idx) | Insn::GetStatic(idx) => object(&class.pool.member(*idx).ok()?.descriptor),
            _ => None,
        }
    }

    /// A `ResponseStatusException` (or `ErrorResponseException`) with the status its constructor was given, when
    /// that is an `HttpStatus` constant: `org/springframework/web/server/ResponseStatusException:NOT_FOUND`.
    fn with_status(&self, class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, new_at: usize, until: usize, name: String) -> String {
        if !RESPONSE_STATUS_EXCEPTIONS.iter().any(|c| name == *c || self.cp.is_subtype(&name, c)) {
            return name;
        }
        for i in new_at + 1..=until {
            if let Insn::InvokeSpecial(idx) = &insns[i].1 {
                let Ok(member) = class.pool.member(*idx) else { continue };
                if member.owner != name || member.name != "<init>" {
                    continue;
                }
                let Ok(d) = MethodDescriptor::parse(&member.descriptor) else { break };
                if d.params.is_empty() {
                    break;
                }
                if let Some(p) = pushing(class, insns, targets, i, d.params.len() - 1) {
                    if let Insn::GetStatic(f) = &insns[p].1 {
                        if let Ok(field) = class.pool.member(*f) {
                            if field.owner == HTTP_STATUS {
                                return format!("{name}:{}", field.name);
                            }
                        }
                    }
                }
                break;
            }
        }
        name
    }

    /// What a call into the JDK or Spring throws by design: `Optional.orElseThrow` the exception its supplier
    /// builds (or `NoSuchElementException` with no supplier), `Assert.state` an `IllegalStateException`, the other
    /// `Assert` methods an `IllegalArgumentException`.
    fn leaf_throws(&self, class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef, bootstrap: &[crate::classfile::BootstrapMethod]) -> Vec<String> {
        if member.owner == "org/springframework/util/Assert" {
            return vec![if member.name.starts_with("state") { "java/lang/IllegalStateException" } else { "java/lang/IllegalArgumentException" }.to_string()];
        }
        if !(member.owner.starts_with("java/util/Optional") && member.name == "orElseThrow") {
            return Vec::new();
        }
        if member.descriptor.starts_with("()") {
            return vec!["java/util/NoSuchElementException".to_string()];
        }
        let Some(pushed) = pushing(class, insns, targets, at, 0) else { return Vec::new() };
        let Insn::InvokeDynamic(idx) = &insns[pushed].1 else { return Vec::new() };
        let Ok((bsm, _, _)) = class.pool.invoke_dynamic(*idx) else { return Vec::new() };
        let Some(b) = bootstrap.get(usize::from(bsm)) else { return Vec::new() };
        let Some(BootstrapArg::MethodHandle(h)) = b.args.get(1) else { return Vec::new() };
        if h.kind == 8 {
            return vec![h.member.owner.clone()];
        }
        let Ok(d) = MethodDescriptor::parse(&h.member.descriptor) else { return Vec::new() };
        let Type::Object(name) = d.ret else { return Vec::new() };
        if name == "java/lang/Object" || !self.cp.is_subtype(&name, "java/lang/Throwable") {
            return Vec::new();
        }
        // A `ResponseStatusException` built in the supplier's body: the status is the `new` in the lambda's method.
        if RESPONSE_STATUS_EXCEPTIONS.iter().any(|c| name == *c || self.cp.is_subtype(&name, c)) {
            if let Some(lambda) = self.classes.get(&h.member.owner).and_then(|c| c.method(&h.member.name, &h.member.descriptor).map(|m| (c.clone(), m.clone()))) {
                let (lambda_class, lambda_method) = lambda;
                if let Some(code) = &lambda_method.code {
                    if let Ok(body) = code.instructions() {
                        let body_targets = jump_targets(&body, &lambda_method);
                        for (i, (_, insn)) in body.iter().enumerate() {
                            if let Insn::New(n) = insn {
                                if lambda_class.pool.class_name(*n).ok() == Some(name.as_str()) {
                                    return vec![self.with_status(&lambda_class, &body, &body_targets, i, body.len() - 1, name)];
                                }
                            }
                        }
                    }
                }
            }
        }
        vec![name]
    }

    /// The followed methods behind a lambda: the body the `LambdaMetafactory` call site names, when it is local.
    fn lambda_targets(&self, class: &ClassFile, bootstrap: &[crate::classfile::BootstrapMethod], idx: u16) -> Vec<String> {
        let Ok((bsm, _, _)) = class.pool.invoke_dynamic(idx) else { return Vec::new() };
        let Some(b) = bootstrap.get(usize::from(bsm)) else { return Vec::new() };
        if b.method.member.owner != LAMBDA_METAFACTORY {
            return Vec::new();
        }
        match b.args.get(1) {
            Some(BootstrapArg::MethodHandle(h)) if self.classes.contains_key(&h.member.owner) => self.resolve(&h.member, h.kind != 5 && h.kind != 9),
            _ => Vec::new(),
        }
    }

    /// The lambdas among the arguments of the call at `at`: the bodies of the `invokedynamic`s that pushed them.
    fn lambda_args(&self, class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef, bootstrap: &[crate::classfile::BootstrapMethod]) -> Vec<String> {
        let Ok(d) = MethodDescriptor::parse(&member.descriptor) else { return Vec::new() };
        let n = d.params.len();
        let mut out = Vec::new();
        for position in 0..n {
            let Some(pushed) = pushing(class, insns, targets, at, n - 1 - position) else { continue };
            if let Insn::InvokeDynamic(idx) = &insns[pushed].1 {
                out.extend(self.lambda_targets(class, bootstrap, *idx));
            }
        }
        out
    }

    /// The followed methods a call may run: the nearest declaration with a body up the receiver's class chain and
    /// its interfaces, and (for a virtual call) every override in a followed subtype.
    fn resolve(&self, member: &MemberRef, exact: bool) -> Vec<String> {
        let mut out = Vec::new();
        if let Some(k) = self.declared_up(&member.owner, &member.name, &member.descriptor) {
            out.push(k);
        }
        if !exact {
            for sub in self.subtypes(&member.owner) {
                if self.classes.get(&sub).is_some_and(|c| c.method(&member.name, &member.descriptor).is_some_and(|m| m.code.is_some())) {
                    out.push(key(&sub, &member.name, &member.descriptor));
                }
            }
        }
        out
    }

    fn declared_up(&self, owner: &str, name: &str, descriptor: &str) -> Option<String> {
        let mut current = Some(owner.to_string());
        let mut hops = 0;
        while let Some(c) = current {
            let class = self.classes.get(&c)?;
            if class.method(name, descriptor).is_some_and(|m| m.code.is_some()) {
                return Some(key(&c, name, descriptor));
            }
            current = class.super_class.clone();
            hops += 1;
            if hops > 64 {
                break;
            }
        }
        for iface in self.cp.all_interfaces(owner) {
            if self.classes.get(&iface).is_some_and(|c| c.method(name, descriptor).is_some_and(|m| m.code.is_some())) {
                return Some(key(&iface, name, descriptor));
            }
        }
        None
    }

    fn subtypes(&self, owner: &str) -> Vec<String> {
        let mut out = Vec::new();
        let mut work = vec![owner.to_string()];
        let mut seen: HashSet<String> = HashSet::new();
        while let Some(c) = work.pop() {
            for child in self.children.get(&c).into_iter().flatten() {
                if seen.insert(child.clone()) {
                    out.push(child.clone());
                    work.push(child.clone());
                }
            }
        }
        out
    }

    /// A call on a followed interface that nothing implements: a Spring Data repository (a read or a write of its
    /// domain type) or an HTTP client interface (a call).
    fn interface_effects(&self, caller: &ClassFile, method: &Method, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef) -> Vec<Effect> {
        let Some(class) = self.classes.get(&member.owner) else { return Vec::new() };
        if !class.is_interface() {
            return Vec::new();
        }
        let declared = class.method(&member.name, &member.descriptor);
        let annotations = declared.and_then(|m| m.annotations(&class.pool).ok()).unwrap_or_default();
        if let Some(domain) = store::repository_domain(self.cp, class, 0) {
            let name = &member.name;
            let deleting = annotations.iter().any(|a| matches!(a.simple_name().as_str(), "Modifying") || (a.simple_name() == "Query" && a.element("delete") == Some(&ElementValue::Boolean(true))));
            let writes = deleting || ["save", "insert", "delete", "remove", "update", "upsert"].iter().any(|p| name.starts_with(p));
            let subject = if ["save", "insert", "delete", "remove"].contains(&name.as_str()) || name == "saveAll" || name == "deleteAll" {
                self.subject(caller, method, insns, targets, at, member).unwrap_or_else(|| display(&domain))
            } else {
                display(&domain)
            };
            return vec![if writes { Effect::Write(subject) } else { Effect::Read(subject) }];
        }
        if let Some(call) = client_call(class, &annotations) {
            return vec![Effect::Call(call)];
        }
        Vec::new()
    }

    /// The effect of a call into the framework, if its owner and name are one the walk knows.
    #[allow(clippy::too_many_arguments)]
    fn leaf(&self, class: &ClassFile, method: &Method, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef, verb: &mut Option<String>) -> Vec<Effect> {
        let owner = member.owner.as_str();
        let name = member.name.as_str();
        let starts = |prefixes: &[&str]| prefixes.iter().any(|p| name.starts_with(p));
        let string_arg = |k: usize| self.string_arg(class, insns, targets, at, member, k);
        if owner.starts_with("org/springframework/data/mongodb/core/") && (owner.ends_with("MongoTemplate") || owner.ends_with("MongoOperations")) || owner.starts_with("org/springframework/data/") && owner.ends_with("Template") && !owner.contains("/mongodb/core/index") {
            let subject = || self.subject(class, method, insns, targets, at, member).unwrap_or_else(|| "a document".to_string());
            if starts(&["find", "exists", "count", "query", "stream", "aggregate", "mapReduce", "estimatedCount", "get", "scroll", "search"]) && !starts(&["findAndModify", "findAndReplace", "findAndRemove", "findAllAndRemove"]) {
                return vec![Effect::Read(subject())];
            }
            if starts(&["insert", "save", "upsert", "update", "remove", "delete", "findAndModify", "findAndReplace", "findAndRemove", "findAllAndRemove", "bulkOps", "dropCollection", "createCollection", "replace"]) {
                return vec![Effect::Write(subject())];
            }
            return Vec::new();
        }
        if owner == "jakarta/persistence/EntityManager" || owner == "javax/persistence/EntityManager" {
            let subject = || self.subject(class, method, insns, targets, at, member).unwrap_or_else(|| "an entity".to_string());
            if starts(&["persist", "merge", "remove"]) {
                return vec![Effect::Write(subject())];
            }
            if starts(&["find", "getReference", "createQuery", "createNamedQuery", "createNativeQuery"]) {
                return vec![Effect::Read(subject())];
            }
            return Vec::new();
        }
        if owner.starts_with("org/springframework/jdbc/core/") || owner.starts_with("org/springframework/r2dbc/core/") {
            let sql = string_arg(0);
            let tables = sql.as_deref().map(tables).unwrap_or_default();
            let subjects: Vec<String> = if tables.is_empty() { vec!["SQL".to_string()] } else { tables };
            let first_word = sql.as_deref().and_then(|s| s.split_whitespace().next()).map(|w| w.to_ascii_lowercase());
            let writes = if name == "sql" || name == "execute" || name == "query" && owner.ends_with("DatabaseClient") {
                first_word.is_some_and(|w| !matches!(w.as_str(), "select" | "with" | "show" | "explain"))
            } else if starts(&["update", "batchUpdate", "execute"]) {
                true
            } else if starts(&["query"]) {
                false
            } else {
                return Vec::new();
            };
            return subjects.into_iter().map(|t| if writes { Effect::Write(t) } else { Effect::Read(t) }).collect();
        }
        if owner.starts_with("org/springframework/kafka/core/") && starts(&["send", "executeInTransaction"]) {
            return vec![Effect::Send(string_arg(0).unwrap_or_else(|| "to Kafka".to_string()))];
        }
        if owner.starts_with("org/springframework/amqp/rabbit/core/") && starts(&["send", "convertAndSend", "convertSendAndReceive", "sendAndReceive"]) {
            return vec![Effect::Send(string_arg(0).unwrap_or_else(|| "to RabbitMQ".to_string()))];
        }
        if owner.starts_with("org/springframework/jms/core/") && starts(&["send", "convertAndSend"]) {
            return vec![Effect::Send(string_arg(0).unwrap_or_else(|| "to JMS".to_string()))];
        }
        if owner == "org/springframework/cloud/stream/function/StreamBridge" && name == "send" {
            return vec![Effect::Send(string_arg(0).unwrap_or_else(|| "to a binding".to_string()))];
        }
        if owner.starts_with("io/awspring/cloud/sqs/") && name.starts_with("send") || owner.starts_with("io/awspring/cloud/sns/") && name.starts_with("send") {
            return vec![Effect::Send(string_arg(0).unwrap_or_else(|| "to a queue".to_string()))];
        }
        if owner == "org/springframework/messaging/MessageChannel" && name == "send" {
            return vec![Effect::Send("to a channel".to_string())];
        }
        if (owner == "org/springframework/context/ApplicationEventPublisher" || owner.ends_with("ApplicationContext")) && name == "publishEvent" {
            let event = self.subject(class, method, insns, targets, at, member).unwrap_or_else(|| "an event".to_string());
            return vec![Effect::Publish(event)];
        }
        if owner.starts_with("org/springframework/web/client/RestClient") || owner.starts_with("org/springframework/web/reactive/function/client/WebClient") {
            match name {
                "get" | "post" | "put" | "patch" | "delete" | "head" | "options" => *verb = Some(name.to_ascii_uppercase()),
                "method" => *verb = Some(self.http_method_arg(class, insns, targets, at, member).unwrap_or_else(|| "a request to".to_string())),
                "uri" => {
                    if let Some(v) = verb.take() {
                        return vec![Effect::Call(format!("{v} {}", string_arg(0).unwrap_or_else(|| "a computed URL".to_string())))];
                    }
                }
                _ => {}
            }
            return Vec::new();
        }
        if owner == "org/springframework/web/client/RestTemplate" || owner == "org/springframework/web/client/RestOperations" {
            let v = match name {
                "getForObject" | "getForEntity" => "GET".to_string(),
                "postForObject" | "postForEntity" | "postForLocation" => "POST".to_string(),
                "put" => "PUT".to_string(),
                "delete" => "DELETE".to_string(),
                "patchForObject" => "PATCH".to_string(),
                "headForHeaders" => "HEAD".to_string(),
                "optionsForAllow" => "OPTIONS".to_string(),
                "exchange" | "execute" => self.http_method_arg(class, insns, targets, at, member).unwrap_or_else(|| "a request to".to_string()),
                _ => return Vec::new(),
            };
            return vec![Effect::Call(format!("{v} {}", string_arg(0).unwrap_or_else(|| "a computed URL".to_string())))];
        }
        Vec::new()
    }

    /// The `k`-th `String` parameter of the call, when a constant.
    fn string_arg(&self, class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef, k: usize) -> Option<String> {
        let d = MethodDescriptor::parse(&member.descriptor).ok()?;
        let position = d.params.iter().enumerate().filter(|(_, t)| matches!(t, Type::Object(c) if c == "java/lang/String")).nth(k)?.0;
        let pushed = pushing(class, insns, targets, at, d.params.len() - 1 - position)?;
        match &insns[pushed].1 {
            Insn::Ldc(c) => match class.pool.get(*c).ok()? {
                Constant::String { string_index } => class.pool.utf8(*string_index).ok().map(str::to_string),
                _ => None,
            },
            _ => None,
        }
    }

    /// The `HttpMethod` constant the call passes, as its name (`GET`), from the `getstatic` that pushed it.
    fn http_method_arg(&self, class: &ClassFile, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef) -> Option<String> {
        let d = MethodDescriptor::parse(&member.descriptor).ok()?;
        let position = d.params.iter().position(|t| matches!(t, Type::Object(c) if c == "org/springframework/http/HttpMethod"))?;
        let pushed = pushing(class, insns, targets, at, d.params.len() - 1 - position)?;
        match &insns[pushed].1 {
            Insn::GetStatic(idx) => class.pool.member(*idx).ok().map(|f| f.name),
            _ => None,
        }
    }

    /// The static type of each argument of the call at `at`, when the walk can tell (an internal class name).
    fn argument_types(&self, class: &ClassFile, method: &Method, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef) -> Vec<Option<String>> {
        let Ok(d) = MethodDescriptor::parse(&member.descriptor) else { return Vec::new() };
        let n = d.params.len();
        (0..n)
            .map(|position| {
                let declared = d.params[position].class_name().map(str::to_string);
                let found = pushing(class, insns, targets, at, n - 1 - position).and_then(|pushed| self.type_at(class, method, insns, pushed));
                found.or(declared)
            })
            .collect()
    }

    /// What a data call is about: the class literal it passes, else the static type of its entity argument when
    /// that is an application class, else the stored types the method mentions.
    fn subject(&self, class: &ClassFile, method: &Method, insns: &[(u32, Insn)], targets: &BTreeSet<u32>, at: usize, member: &MemberRef) -> Option<String> {
        let d = MethodDescriptor::parse(&member.descriptor).ok()?;
        let n = d.params.len();
        let display = display;
        if let Some(position) = d.params.iter().position(|t| matches!(t, Type::Object(c) if c == "java/lang/Class")) {
            if let Some(pushed) = pushing(class, insns, targets, at, n - 1 - position) {
                if let Insn::Ldc(c) = &insns[pushed].1 {
                    if let Ok(Constant::Class { name_index }) = class.pool.get(*c) {
                        if let Ok(name) = class.pool.utf8(*name_index) {
                            return Some(display(name));
                        }
                    }
                }
            }
        }
        for (position, t) in d.params.iter().enumerate() {
            let Type::Object(c) = t else { continue };
            if !matches!(c.as_str(), "java/lang/Object" | "java/util/Collection" | "java/util/List" | "java/lang/Iterable" | "java/util/Set") {
                continue;
            }
            let Some(pushed) = pushing(class, insns, targets, at, n - 1 - position) else { continue };
            if let Some(ty) = self.type_at(class, method, insns, pushed) {
                if self.classes.contains_key(&ty) {
                    return Some(display(&ty));
                }
            }
        }
        let mentioned = self.mentioned_stored(class, insns);
        (!mentioned.is_empty()).then(|| mentioned.iter().map(|m| display(m)).collect::<Vec<_>>().join(", "))
    }

    /// The static type of the value an instruction pushed, as an internal class name.
    fn type_at(&self, class: &ClassFile, method: &Method, insns: &[(u32, Insn)], at: usize) -> Option<String> {
        let (pc, insn) = &insns[at];
        let of_descriptor = |d: &str| Type::parse(d).ok().and_then(|t| t.class_name().map(str::to_string));
        match insn {
            Insn::New(c) | Insn::CheckCast(c) => class.pool.class_name(*c).ok().map(str::to_string),
            Insn::Ldc(c) => match class.pool.get(*c).ok()? {
                Constant::Class { name_index } => class.pool.utf8(*name_index).ok().map(str::to_string),
                _ => None,
            },
            Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => {
                let member = class.pool.member(*i).ok()?;
                MethodDescriptor::parse(&member.descriptor).ok()?.ret.class_name().map(str::to_string)
            }
            Insn::InvokeDynamic(i) => {
                let (_, _, descriptor) = class.pool.invoke_dynamic(*i).ok()?;
                MethodDescriptor::parse(descriptor).ok()?.ret.class_name().map(str::to_string)
            }
            Insn::GetField(i) | Insn::GetStatic(i) => of_descriptor(&class.pool.member(*i).ok()?.descriptor),
            Insn::Load(Kind::Ref, slot) => {
                let code = method.code.as_ref()?;
                if let Some(v) = code.local_variables.iter().find(|v| v.index == *slot && u32::from(v.start_pc) <= *pc && *pc < u32::from(v.start_pc) + u32::from(v.length)) {
                    return of_descriptor(&v.descriptor);
                }
                // No debug information: the parameters' slots are known from the descriptor.
                let d = MethodDescriptor::parse(&method.descriptor).ok()?;
                let mut next = u16::from(!method.is_static());
                if !method.is_static() && *slot == 0 {
                    return Some(class.name.clone());
                }
                for t in &d.params {
                    if next == *slot {
                        return t.class_name().map(str::to_string);
                    }
                    next += t.slots();
                }
                None
            }
            _ => None,
        }
    }

    /// The stored types (documents, entities) the method names in a `new` or a class literal.
    fn mentioned_stored(&self, class: &ClassFile, insns: &[(u32, Insn)]) -> BTreeSet<String> {
        let mut out = BTreeSet::new();
        for (_, insn) in insns {
            let name = match insn {
                Insn::New(c) => class.pool.class_name(*c).ok().map(str::to_string),
                Insn::Ldc(c) => match class.pool.get(*c) {
                    Ok(Constant::Class { name_index }) => class.pool.utf8(*name_index).ok().map(str::to_string),
                    _ => None,
                },
                _ => None,
            };
            if let Some(name) = name {
                if self.is_stored(&name) {
                    out.insert(name);
                }
            }
        }
        out
    }

    fn is_stored(&self, name: &str) -> bool {
        self.classes.get(name).is_some_and(|c| c.annotations().unwrap_or_default().iter().any(|a| STORED.contains(&a.type_name.as_str())))
    }
}

/// A class as the lines name it: the simple name, with a nested class under its outer one (`Outbox.Entry`), so
/// that two nested classes of one name stay apart.
/// The exception's class, without the status a `ResponseStatusException` carries.
pub fn base_type(thrown: &str) -> &str {
    thrown.split_once(':').map_or(thrown, |(t, _)| t)
}

/// The method's exception handlers that swallow what they catch, and the local slots every handler stores its
/// exception in. A handler rethrows when some `athrow` after it throws the variable it stored at its entry: a
/// `finally`, a `synchronized` release, a retry loop or a log-and-rethrow; such a handler passes its exceptions
/// through and is not listed.
fn handlers(class: &ClassFile, code: &crate::classfile::Code, insns: &[(u32, Insn)], targets: &BTreeSet<u32>) -> (Vec<Swallowing>, HashSet<u16>) {
    let mut swallowing = Vec::new();
    let mut slots = HashSet::new();
    for h in &code.exception_table {
        let entry = insns.iter().position(|(pc, _)| *pc == u32::from(h.handler_pc));
        let slot = match entry.map(|i| &insns[i].1) {
            Some(Insn::Store(Kind::Ref, n)) => Some(*n),
            _ => None,
        };
        let rethrows = match (entry, slot) {
            (Some(entry), Some(n)) => {
                slots.insert(n);
                insns.iter().enumerate().skip(entry + 1).any(|(j, (_, insn))| matches!(insn, Insn::AThrow) && pushing(class, insns, targets, j, 0).is_some_and(|k| k > entry && matches!(insns[k].1, Insn::Load(Kind::Ref, m) if m == n)))
            }
            _ => false,
        };
        if !rethrows {
            swallowing.push(Swallowing { start: u32::from(h.start_pc), end: u32::from(h.end_pc), catches: h.catch_type.clone().unwrap_or_else(|| "java/lang/Throwable".to_string()) });
        }
    }
    (swallowing, slots)
}

pub(crate) fn display(internal: &str) -> String {
    internal.rsplit('/').next().unwrap_or(internal).replace('$', ".")
}

fn site(effect: &Effect, member: &MemberRef, arguments: &[Option<String>], in_method: &str) -> Site {
    let (kind, target) = match effect {
        Effect::Read(t) => (SiteKind::Read, t),
        Effect::Write(t) => (SiteKind::Write, t),
        Effect::Send(t) => (SiteKind::Send, t),
        Effect::Call(t) => (SiteKind::Call, t),
        Effect::Publish(t) => (SiteKind::Publish, t),
    };
    Site { kind, target: target.clone(), call: format!("{}#{}{}", member.owner, member.name, member.descriptor), arguments: arguments.to_vec(), in_method: in_method.to_string() }
}

/// `QuotesController.quote(long, int)`.
pub(crate) fn method_label(class: &ClassFile, method: &Method) -> String {
    let params = MethodDescriptor::parse(&method.descriptor).map(|d| d.params.iter().map(Type::simple_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
    format!("{}.{}({params})", display(&class.name), method.name)
}

fn apply(reach: &mut Effects, effect: Effect) {
    match effect {
        Effect::Read(s) => reach.reads.insert(s),
        Effect::Write(s) => reach.writes.insert(s),
        Effect::Send(s) => reach.sends.insert(s),
        Effect::Call(s) => reach.calls.insert(s),
        Effect::Publish(s) => reach.publishes.insert(s),
    };
}

/// The HTTP call an `@HttpExchange` or Feign interface method makes: its verb and path, under the interface's
/// path prefix.
fn client_call(class: &ClassFile, annotations: &[Annotation]) -> Option<String> {
    let (verb, path) = annotations.iter().find_map(|a| EXCHANGES.iter().find(|(t, _)| *t == a.type_name).map(|(_, v)| (exchange_verb(a, v), exchange_path(a))))?;
    let class_annotations = class.annotations().unwrap_or_default();
    let prefix = class_annotations
        .iter()
        .find_map(|a| {
            if EXCHANGES.iter().any(|(t, _)| *t == a.type_name) {
                Some(exchange_path(a))
            } else if a.type_name == "org/springframework/cloud/openfeign/FeignClient" {
                Some(a.strings("path").into_iter().next().unwrap_or_default())
            } else {
                None
            }
        })
        .unwrap_or_default();
    Some(format!("{verb} {}", join_paths(&prefix, &path)))
}

fn exchange_verb(a: &Annotation, fixed: &str) -> String {
    if !fixed.is_empty() {
        return fixed.to_string();
    }
    a.strings("method").into_iter().next().or_else(|| a.enum_names("method").into_iter().next()).unwrap_or_else(|| "ANY".to_string())
}

fn exchange_path(a: &Annotation) -> String {
    a.strings("value").into_iter().chain(a.strings("path")).chain(a.strings("url")).next().unwrap_or_default()
}

/// The table names a SQL statement reads or writes: what follows `from`, `into`, `update`, `join` and `table`.
pub(crate) fn tables(sql: &str) -> Vec<String> {
    let mut out = Vec::new();
    let words: Vec<&str> = sql.split(|c: char| c.is_whitespace() || c == '(' || c == ')' || c == ',' || c == ';').filter(|w| !w.is_empty()).collect();
    for pair in words.windows(2) {
        let keyword = pair[0].to_ascii_lowercase();
        if matches!(keyword.as_str(), "from" | "into" | "update" | "join" | "table") {
            let name = pair[1].trim_matches(|c| c == '"' || c == '`' || c == '[' || c == ']');
            let first = name.chars().next().unwrap_or(' ');
            if (first.is_alphabetic() || first == '_') && !matches!(name.to_ascii_lowercase().as_str(), "select" | "only" | "if" | "lateral") && !out.iter().any(|o| o == name) {
                out.push(name.to_string());
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tables_come_after_from_into_update_and_join() {
        assert_eq!(tables("select o.id from orders o join seats s on s.order_id = o.id where o.id = ?"), vec!["orders", "seats"]);
        assert_eq!(tables("INSERT INTO audit(id, what) VALUES (?, ?)"), vec!["audit"]);
        assert_eq!(tables("update \"holds\" set expires_at = ? where id = ?"), vec!["holds"]);
        assert_eq!(tables("delete from outbox where published_at < ?"), vec!["outbox"]);
        assert_eq!(tables("select 1"), Vec::<String>::new());
    }

    #[test]
    fn side_effects_leave_out_reads_and_gets() {
        let mut r = Effects::default();
        r.reads.insert("A".into());
        r.calls.insert("GET /x".into());
        assert!(r.side_effects().is_empty());
        r.writes.insert("B".into());
        r.writes.insert("C".into());
        r.calls.insert("POST /y".into());
        assert_eq!(r.side_effects(), vec!["writes B and C", "calls POST /y"]);
        assert_eq!(r.lines(), vec!["reads A", "writes B, C", "calls GET /x, POST /y"]);
    }
}
