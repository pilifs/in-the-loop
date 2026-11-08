//! Callees the two versions of a regression proof share. A method both versions call, identical in both, that is
//! a pure function of its primitive arguments (no fields, no arrays, no calls beyond the arithmetic of the JDK)
//! need not be bit-blasted twice and related by the solver: the proof takes it as one function, the same in both
//! versions, as relational verification does with an uninterpreted function. A generated stub class holds a memo
//! table per such callee: a call with arguments seen before gives the outcome it gave then, and a call with new
//! arguments gets an arbitrary one, a result or an exception of a type the callee can throw. The call sites of
//! both versions are redirected to the stub, so that the solver relates the two versions' *uses* of the callee
//! and never its arithmetic. A 64-bit division in a helper is what turns a proof into a time-out when each version
//! carries its own copy; as one function, it costs nothing.
//!
//! The abstraction is sound for a proof: the stub behaves as every function the callee could be, the callee
//! itself included, so what holds of the two versions with the stub holds of them as written. It can be too
//! coarse for a counterexample, which is why one found with it is replayed through the bytecode as written and,
//! when it does not reproduce, the proof is run again with the callees whose stubs it rests on as written, and the
//! others still one function ([`spurious`], refinement per callee). A callee of a few instructions without a loop, a
//! multiplication, a division or a remainder (`Math.min`, `Math.abs`) is left as written: it costs the solver less
//! than the rerun a counterexample through its stub usually brings ([`trivial`]).
//!
//! The same comparison of the two versions' bytecode settles a prior question: when the target and everything it
//! reaches is identical in both versions, there is nothing to prove ([`Plan::identical`]).
//!
//! **A changed helper proved equivalent** (`llm-dlc/loops/foundations-summaries.md`, S4) is shared the same way,
//! narrowly. A callee both versions call whose code differs is a candidate when, in each version, it is a pure
//! function of the kind above over integral values only (no `float` or `double`, whose `0.0` and `-0.0` a regression
//! proof's comparison of results doesn't tell apart), and when neither version constructs or throws an exception
//! of its own (a regression proof compares exceptions by class, not by message, and the stub throws one with no
//! message): what it can throw is the JVM's own `ArithmeticException` of a division. [`plan_with`] asks its caller
//! for a proof of each candidate: a regression proof of the helper's two versions, unrestricted, on every input
//! ([`crate::proof_cache::Helpers`]). With one, the helper is one stub in both versions ([`Callee::proved`]), and
//! the caller's statement names that proof's claim key as an assumption with basis `proved`. Without one (refuted,
//! unresolved, or not asked for) it stays as written in both versions, as any other changed code does.
//!
//! Under the tool's own checker, the one function a proved helper becomes is its new version itself
//! ([`substitute_directory`]): the previous version's calls of the helper are redirected to the new version's
//! method, so that both versions call the same code, which the checker's hashing makes one circuit per arguments
//! (as it does for a helper identical in both). Since the two versions of the helper have the same outcome on every
//! input and neither has an effect, the previous version with its calls redirected behaves exactly as it did: the
//! proof is of the versions as written, and a counterexample to it is one to them, with no refinement to run. A class
//! whose methods the helper's closure holds, in either version, may have no static initializer, nor may its
//! application superclasses: a redirected call initializes the other version's class rather than its own.
//!
//! **A changed read-only heap helper** (an instance method, R2 of `llm-dlc/loops/application-core-reuse.md`) is
//! shared the same way once it has a summary ([`crate::reuse::application`]): [`plan_with`] asks for one for each
//! changed instance method both versions call, declared by the same class, and [`substitute`] sends each call of it,
//! in both versions, to that version's adapter, which reads the helper's footprint from the actual receiver and calls
//! the new version's lifted helper. Both versions so call one function of the same values. Every call is in the
//! summary's domain, which is every value of the fields and arguments it reads, so applicability at a call site is
//! discharged by reading them there; a receiver mutated between two calls is read twice.
//!
//! Either way the reuse is sound for the caller's proof only where the helper's two versions agree, which the
//! helper's proof shows for every input of its parameter types; so every call, in either version and with any
//! arguments, is in its domain, and the applicability check at a call site has nothing left to assert. A helper
//! proof whose domain is narrower (one with `--unchanged-unless`, or mapped arguments, or a relation between results
//! rather than equal ones) is never one the caller is given: its domain would have to become an assertion at each
//! call.

use std::collections::{BTreeMap, BTreeSet, HashSet, VecDeque};
use std::path::Path;
use std::rc::Rc;

use serde::Serialize;

use crate::classfile::writer::{ClassWriter, CodeBuilder, FieldWriter, MethodWriter};
use crate::classfile::{encode_modified_utf8, flags, ArithOp, BootstrapArg, BootstrapMethod, ClassFile, Cond, ConstantPool, Insn, Kind, MemberRef, Method, Type};
use crate::classpath::ClassPath;
use crate::Error;

/// The stub class (default package) the shared callees are redirected to.
pub const CLASS: &str = "SharedCallees";
/// How many outcomes a callee's memo table holds: calls beyond them get an arbitrary outcome each, which is still
/// sound for a proof.
pub const ENTRIES: u16 = 4;

/// JDK classes whose static methods may be shared: the ones whose real bytecode the proof analyses anyway.
const JDK_SHAREABLE: &[&str] = crate::equivalence::JDK_CLASSES;

const NONDET: &str = "org/cprover/CProver";

/// A callee taken as one function in both versions.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Callee {
    pub owner: String,
    pub name: String,
    pub descriptor: String,
    /// The exception classes it can throw, by internal name.
    pub throws: Vec<String>,
    /// For a callee whose two versions differ: the proof that they have the same outcome on every input, which is
    /// what lets one stub stand for both. `None` for a callee identical in both versions.
    pub proved: Option<Proved>,
}

/// A regression proof of a changed helper's two versions, unrestricted: the same result, or the same exception, on
/// every input of its parameter types.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Proved {
    /// The proof's claim key ([`crate::spec::cache::ClaimKey`]), under which its result is in the proof cache.
    pub key: String,
    /// The run that proved it, as its cache record says.
    pub from: String,
}

impl Callee {
    /// `Shares.perSeat`, for reports.
    pub fn display(&self) -> String {
        format!("{}.{}", self.owner.rsplit('/').next().unwrap_or(&self.owner), self.name)
    }

    /// `Math.multiplyExact(long, int)`: the display with the parameter types, for an overload.
    pub fn display_with_params(&self) -> String {
        let params = crate::classfile::MethodDescriptor::parse(&self.descriptor).map(|d| d.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
        format!("{}({params})", self.display())
    }

    /// The stub method standing for this callee.
    pub fn stub_method(&self, index: usize) -> String {
        format!("m{index}_{}", self.name)
    }

    fn member(&self) -> MemberRef {
        MemberRef::new(&self.owner, &self.name, &self.descriptor)
    }

    /// `pkg.Class#name(long, int)`: the callee as a target of its own check.
    pub fn target(&self) -> String {
        target_of(&self.member())
    }
}

/// `pkg.Class#name(long, int)`, a method as `equivalence --target` names it, with its parameter types.
pub fn target_of(m: &MemberRef) -> String {
    let params = crate::classfile::MethodDescriptor::parse(&m.descriptor).map(|d| d.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
    format!("{}#{}({params})", m.owner.replace('/', "."), m.name)
}

/// What a caller of [`plan_with`] is asked for a changed helper: its proof, or `None` to leave it as written.
pub type Prover<'a> = dyn FnMut(&MemberRef) -> Option<Proved> + 'a;

/// What the comparison of the two versions decided.
#[derive(Debug, Clone, Default)]
pub struct Plan {
    pub callees: Vec<Callee>,
    /// Set when the target and every method it reaches is identical in both versions: how many methods were
    /// compared.
    pub identical: Option<usize>,
}

/// Compares the two versions of the target (`before_target` in the old classes, `target` in the new) and chooses the
/// callees to share. Both class paths need the JDK. `plain` says the statement is the usual one, the same arguments
/// to both versions: only then is a target identical in both, with everything it reaches, verified without a proof
/// (with the previous version's arguments mapped, `f(a, b)` against `f(b, a)` say, identical bytecode proves nothing).
pub fn plan(before: &ClassPath, after: &ClassPath, before_target: &MemberRef, target: &MemberRef, plain: bool) -> Plan {
    plan_with(before, after, before_target, target, plain, &mut |_| None)
}

/// [`plan`], with a changed helper shared too where `prove` gives a proof of its two versions' equivalence (the
/// module's documentation says which helpers are asked about). `prove` is asked once per candidate, in the order the
/// calls sort in.
pub fn plan_with(before: &ClassPath, after: &ClassPath, before_target: &MemberRef, target: &MemberRef, plain: bool, prove: &mut Prover) -> Plan {
    let after_reach = reach(after, target);
    let before_reach = reach(before, before_target);
    let mut plan = Plan::default();
    if plain && before_target == target && after_reach.closed && before_reach.closed && same_everywhere(before, &after_reach) {
        plan.identical = Some(after_reach.methods.len());
        return plan;
    }
    let mut inside: HashSet<MemberRef> = HashSet::new();
    let mut candidates = Vec::new();
    for callee in after_reach.static_calls.intersection(&before_reach.static_calls) {
        if *callee == *target || *callee == *before_target {
            continue;
        }
        let Some(closure) = pure_closure(after, callee) else { continue };
        let identical = closure.methods.iter().all(|m| !after.is_application(&m.owner) || same_method(before, after, m));
        let (throws, proved) = if identical {
            if trivial(after, &closure) || !closure.throws.iter().all(|t| constructor(after, t).is_some()) {
                continue;
            }
            (closure.throws.clone(), None)
        } else {
            // A changed helper: pure in both versions, provable as one function, and proved so.
            let Some(previous) = pure_closure(before, callee) else { continue };
            if !provable(after, callee, &closure) || !provable(before, callee, &previous) || (trivial(after, &closure) && trivial(before, &previous)) {
                continue;
            }
            if !uninitialized(after, &closure) || !uninitialized(before, &previous) {
                continue;
            }
            let throws: BTreeSet<String> = closure.throws.union(&previous.throws).cloned().collect();
            if !throws.iter().all(|t| constructor(after, t).is_some()) {
                continue;
            }
            let Some(proof) = prove(callee) else { continue };
            (throws, Some(proof))
        };
        inside.extend(closure.methods);
        candidates.push(Callee { owner: callee.owner.clone(), name: callee.name.clone(), descriptor: callee.descriptor.clone(), throws: throws.into_iter().collect(), proved });
    }
    // R2: a changed instance method both versions call, declared by the same class, is shared where `prove` gives
    // its read-only summary ([`crate::proof_cache::Helpers`] asks [`crate::reuse::application`]), and applied at each
    // call in both versions by [`substitute`]. Its footprint is established there, for both versions, from the
    // bytecode: here only the calls are matched.
    for callee in after_reach.instance_calls.intersection(&before_reach.instance_calls) {
        if *callee == *target || *callee == *before_target || identical_closure(before, after, std::slice::from_ref(callee)) {
            continue;
        }
        let Some(proof) = prove(callee) else { continue };
        candidates.push(Callee { owner: callee.owner.clone(), name: callee.name.clone(), descriptor: callee.descriptor.clone(), throws: Vec::new(), proved: Some(proof) });
    }
    // A callee only ever called from inside another shared callee is never reached once that one is a stub.
    plan.callees = candidates.into_iter().filter(|c| after_reach.callers.get(&c.member()).is_some_and(|callers| callers.iter().any(|caller| !inside.contains(caller)))).collect();
    plan
}

/// Whether each of `roots`, with everything it reaches, is identical in both versions: a record's constructor,
/// which the harness calls in both to build the receiver or an argument, must be for a target identical in both
/// to need no proof.
pub fn identical_closure(before: &ClassPath, after: &ClassPath, roots: &[MemberRef]) -> bool {
    roots.iter().all(|root| {
        let reached = reach(after, root);
        reached.closed && same_everywhere(before, &reached)
    })
}

/// The callees' names for a report, with parameter types where two overloads would otherwise read the same.
pub fn names(callees: &[Callee]) -> Vec<String> {
    callees
        .iter()
        .map(|c| {
            let plain = c.display();
            if callees.iter().filter(|o| o.display() == plain).count() > 1 {
                c.display_with_params()
            } else {
                plain
            }
        })
        .collect()
}

/// What a proof line says of the callees it took as one function (`used`, as [`names`] gives them): the unchanged
/// ones, then each changed one with the claim its equivalence was proved under. Empty when none was used.
pub fn sharing(callees: &[Callee], used: &[String]) -> String {
    let all = names(callees);
    let used: Vec<(&String, &Callee)> = all.iter().zip(callees).filter(|(n, _)| used.contains(n)).collect();
    let unchanged: Vec<&String> = used.iter().filter(|(_, c)| c.proved.is_none()).map(|(n, _)| *n).collect();
    let mut out = match unchanged.len() {
        0 => String::new(),
        1 => format!("; {} unchanged in both versions and taken as one function in both", unchanged[0]),
        n => format!("; {n} callees unchanged in both versions and taken as one function in both: {}", unchanged.iter().map(|s| s.as_str()).collect::<Vec<_>>().join(", ")),
    };
    for (name, callee) in used.iter().filter(|(_, c)| c.proved.is_some()) {
        let proof = callee.proved.as_ref().expect("filtered");
        match crate::reuse::applied(&proof.key, &callee.member()) {
            Some(a) => out.push_str(&format!(
                "; {name} changed, applied by its summary at each call: its two versions, lifted over what they read ({}), proved to have the same outcome on every value of it (claim {}), and each call's values read from its actual receiver",
                a.summary.reads.join(", "),
                proof.key
            )),
            None => out.push_str(&format!("; {name} changed, its two versions proved to have the same outcome on every input (claim {}), and taken as one function in both", proof.key)),
        }
    }
    out
}

/// The methods a target reaches, in one version.
struct Reach {
    /// Every application method reached, and the JDK ones whose bytecode the proof analyses, with the shape of
    /// each (`None` when its code could not be decoded).
    methods: Vec<(MemberRef, Option<Vec<String>>)>,
    /// The application classes those methods belong to or read static fields of.
    classes: BTreeMap<String, Rc<ClassFile>>,
    /// The targets of `invokestatic` instructions in those methods, with the methods that make the call.
    static_calls: BTreeSet<MemberRef>,
    callers: BTreeMap<MemberRef, BTreeSet<MemberRef>>,
    /// The application instance methods `invokevirtual` and `invokespecial` instructions in those methods call (no
    /// constructor), as the class path resolves them, with the methods that make the call (in `callers`): the
    /// read-only helpers a summary may stand for (R2).
    instance_calls: BTreeSet<MemberRef>,
    /// Application classes whose static fields the methods read or write.
    statics: BTreeSet<String>,
    /// Whether every call could be followed: false when a virtual call may reach an implementation not listed.
    closed: bool,
}

fn reach(cp: &ClassPath, root: &MemberRef) -> Reach {
    let mut out = Reach { methods: Vec::new(), classes: BTreeMap::new(), static_calls: BTreeSet::new(), callers: BTreeMap::new(), instance_calls: BTreeSet::new(), statics: BTreeSet::new(), closed: true };
    let mut seen: HashSet<MemberRef> = HashSet::new();
    let mut work: VecDeque<MemberRef> = VecDeque::from([root.clone()]);
    while let Some(reference) = work.pop_front() {
        if !seen.insert(reference.clone()) {
            continue;
        }
        let Some((class, method)) = cp.find_method(&reference.owner, &reference.name, &reference.descriptor) else {
            out.closed = false;
            continue;
        };
        let declared = MemberRef::new(&class.name, &reference.name, &reference.descriptor);
        if cp.is_application(&class.name) {
            out.classes.insert(class.name.clone(), class.clone());
        }
        let Some(code) = &method.code else {
            if !method.is_abstract() {
                out.closed = false; // native
            }
            out.methods.push((declared, None));
            continue;
        };
        out.methods.push((declared.clone(), shape(&class, &method)));
        let Ok(insns) = code.instructions() else {
            out.closed = false;
            continue;
        };
        for (_, insn) in insns {
            match insn {
                Insn::GetStatic(i) | Insn::PutStatic(i) => {
                    if let Ok(field) = class.pool.member(i) {
                        if cp.is_application(&field.owner) {
                            if let Ok(Some(owner)) = cp.application(&field.owner) {
                                out.classes.insert(field.owner.clone(), owner);
                            }
                            out.statics.insert(field.owner);
                        }
                    }
                }
                Insn::InvokeStatic(i) | Insn::InvokeSpecial(i) => {
                    let Ok(callee) = class.pool.member(i) else { continue };
                    if !followed(cp, &callee.owner) {
                        continue;
                    }
                    if matches!(insn, Insn::InvokeStatic(_)) {
                        out.static_calls.insert(callee.clone());
                        out.callers.entry(callee.clone()).or_default().insert(declared.clone());
                    } else if callee.name != "<init>" {
                        out.instance_call(cp, &callee, &declared);
                    }
                    work.push_back(callee);
                }
                Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => {
                    let Ok(callee) = class.pool.member(i) else { continue };
                    if !cp.is_application(&callee.owner) {
                        continue; // the JDK is the same in both versions
                    }
                    if matches!(insn, Insn::InvokeVirtual(_)) {
                        out.instance_call(cp, &callee, &declared);
                    }
                    let resolved = cp.find_method(&callee.owner, &callee.name, &callee.descriptor);
                    let fixed = cp.is_effectively_final(&callee.owner) || resolved.as_ref().is_some_and(|(_, m)| m.is_private() || m.is_final() || m.is_static());
                    if fixed {
                        work.push_back(callee);
                    } else {
                        out.closed = false;
                    }
                }
                Insn::InvokeDynamic(i) => {
                    let Ok((bootstrap_index, _, _)) = class.pool.invoke_dynamic(i) else { continue };
                    let bootstraps = class.bootstrap_methods().unwrap_or_default();
                    let Some(bootstrap) = bootstraps.get(bootstrap_index as usize) else { continue };
                    if bootstrap.method.member.owner == "java/lang/invoke/LambdaMetafactory" {
                        match bootstrap.args.get(1) {
                            Some(BootstrapArg::MethodHandle(handle)) if cp.is_application(&handle.member.owner) => work.push_back(handle.member.clone()),
                            Some(BootstrapArg::MethodHandle(_)) => {}
                            _ => out.closed = false,
                        }
                    }
                }
                _ => {}
            }
        }
    }
    out
}

impl Reach {
    /// Records a call of the instance method `callee` (as the instruction names it) from `caller`, as the class
    /// path resolves it.
    fn instance_call(&mut self, cp: &ClassPath, callee: &MemberRef, caller: &MemberRef) {
        let Some((class, method)) = cp.find_method(&callee.owner, &callee.name, &callee.descriptor) else { return };
        if method.is_static() || !cp.is_application(&class.name) {
            return;
        }
        let declared = MemberRef::new(&class.name, &callee.name, &callee.descriptor);
        self.callers.entry(declared.clone()).or_default().insert(caller.clone());
        self.instance_calls.insert(declared);
    }
}

/// Whether a callee's bytecode is part of the proof: an application class, or a JDK class the proof analyses.
fn followed(cp: &ClassPath, owner: &str) -> bool {
    cp.is_application(owner) || JDK_SHAREABLE.contains(&owner)
}

/// Whether every application method the after version reaches, and the static state it reads, is the same in
/// the before version.
fn same_everywhere(before: &ClassPath, after_reach: &Reach) -> bool {
    if after_reach.methods.is_empty() {
        return false;
    }
    for (m, after_shape) in &after_reach.methods {
        if JDK_SHAREABLE.contains(&m.owner.as_str()) {
            continue;
        }
        let Some(after_shape) = after_shape else { return false };
        let Some((before_class, before_method)) = before.find_method(&m.owner, &m.name, &m.descriptor) else { return false };
        if before_class.name != m.owner || shape(&before_class, &before_method).as_ref() != Some(after_shape) {
            return false;
        }
    }
    for owner in &after_reach.statics {
        let (Ok(Some(b)), Some(a)) = (before.application(owner), after_reach.classes.get(owner)) else { return false };
        if initializer_shape(&b) != initializer_shape(a) || constant_values(&b) != constant_values(a) {
            return false;
        }
    }
    true
}

/// Whether a method is declared by the same class with the same code in both versions.
fn same_method(before: &ClassPath, after: &ClassPath, m: &MemberRef) -> bool {
    let (Some((bc, bm)), Some((ac, am))) = (before.find_method(&m.owner, &m.name, &m.descriptor), after.find_method(&m.owner, &m.name, &m.descriptor)) else { return false };
    bc.name == ac.name && bm.access == am.access && shape(&bc, &bm).is_some() && shape(&bc, &bm) == shape(&ac, &am)
}

/// A method's code with its constant pool references resolved, so that two class files compare by what they
/// say and not by how their pools are numbered. `None` when the code cannot be decoded. A dynamic constant
/// (`ldc`, or a bootstrap argument) is resolved through its own bootstrap entry, since that entry is where what it
/// says lives: javac makes `case Color.GREEN` in a pattern switch a dynamic constant whose bootstrap names `GREEN`.
pub(crate) fn shape(class: &ClassFile, method: &Method) -> Option<Vec<String>> {
    let code = method.code.as_ref()?;
    let insns = code.instructions().ok()?;
    let pool = &class.pool;
    // An unreadable table leaves it empty, and a body that needs it undecodable.
    let bootstraps = class.bootstrap_methods().unwrap_or_default();
    let mut out = Vec::with_capacity(insns.len() + code.exception_table.len());
    for (_, insn) in &insns {
        out.push(match insn {
            Insn::Ldc(i) => match pool.loadable(*i).ok()? {
                BootstrapArg::Dynamic { bootstrap_method_attr_index, name, descriptor } => {
                    format!("ldc dynamic {name}{descriptor} {}", bootstrap_text(&bootstraps, bootstrap_method_attr_index, 0)?)
                }
                other => format!("ldc {other:?}"),
            },
            Insn::GetStatic(i) | Insn::PutStatic(i) | Insn::GetField(i) | Insn::PutField(i) | Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => {
                format!("{} {:?}", opname(insn), pool.member(*i).ok()?)
            }
            Insn::New(i) | Insn::ANewArray(i) | Insn::CheckCast(i) | Insn::InstanceOf(i) => format!("{} {}", opname(insn), pool.class_name(*i).ok()?),
            Insn::MultiANewArray(i, dims) => format!("multianewarray {} {dims}", pool.class_name(*i).ok()?),
            Insn::InvokeDynamic(i) => {
                let (b, name, descriptor) = pool.invoke_dynamic(*i).ok()?;
                format!("invokedynamic {name}{descriptor} {}", bootstrap_text(&bootstraps, b, 0)?)
            }
            other => format!("{other:?}"),
        });
    }
    for handler in &code.exception_table {
        out.push(format!("{handler:?}"));
    }
    Some(out)
}

/// A bootstrap entry as text: its method handle and its arguments, a dynamic constant among them resolved through
/// its own entry in turn. `None` past a few levels, or for an index the table doesn't have.
fn bootstrap_text(bootstraps: &[BootstrapMethod], index: u16, depth: u32) -> Option<String> {
    if depth > 8 {
        return None;
    }
    let entry = bootstraps.get(index as usize)?;
    let mut args = Vec::with_capacity(entry.args.len());
    for arg in &entry.args {
        args.push(match arg {
            BootstrapArg::Dynamic { bootstrap_method_attr_index, name, descriptor } => {
                format!("Dynamic {name}{descriptor} {}", bootstrap_text(bootstraps, *bootstrap_method_attr_index, depth + 1)?)
            }
            other => format!("{other:?}"),
        });
    }
    Some(format!("{:?} [{}]", entry.method, args.join(", ")))
}

fn opname(insn: &Insn) -> &'static str {
    match insn {
        Insn::GetStatic(_) => "getstatic",
        Insn::PutStatic(_) => "putstatic",
        Insn::GetField(_) => "getfield",
        Insn::PutField(_) => "putfield",
        Insn::InvokeVirtual(_) => "invokevirtual",
        Insn::InvokeSpecial(_) => "invokespecial",
        Insn::InvokeStatic(_) => "invokestatic",
        Insn::InvokeInterface(_) => "invokeinterface",
        Insn::New(_) => "new",
        Insn::ANewArray(_) => "anewarray",
        Insn::CheckCast(_) => "checkcast",
        Insn::InstanceOf(_) => "instanceof",
        _ => "?",
    }
}

fn initializer_shape(class: &ClassFile) -> Option<Vec<String>> {
    class.method("<clinit>", "()V").and_then(|m| shape(class, m))
}

/// The `ConstantValue` of every field that has one, by name.
fn constant_values(class: &ClassFile) -> Vec<(String, String)> {
    class
        .fields
        .iter()
        .filter_map(|f| {
            let attr = f.attributes.iter().find(|a| a.name == "ConstantValue")?;
            let index = u16::from_be_bytes([*attr.data.first()?, *attr.data.get(1)?]);
            Some((f.name.clone(), format!("{:?}", class.pool.loadable(index).ok()?)))
        })
        .collect()
}

/// A pure function of primitive arguments and what it reaches.
struct Closure {
    methods: Vec<MemberRef>,
    throws: BTreeSet<String>,
    /// Whether a method in it constructs or throws an exception itself (`new` of a `Throwable`, or `athrow`),
    /// rather than the JVM throwing one for an instruction.
    raises: bool,
    /// Whether a parameter or result in it is a `float` or a `double`.
    floating: bool,
}

/// Whether no application class whose methods `closure` holds, nor any of its application superclasses, has a
/// static initializer: a call into them, redirected or not, initializes nothing.
fn uninitialized(cp: &ClassPath, closure: &Closure) -> bool {
    closure.methods.iter().filter(|m| cp.is_application(&m.owner)).all(|m| {
        let mut class = Some(m.owner.clone());
        while let Some(name) = class.filter(|c| cp.is_application(c)) {
            let Ok(Some(file)) = cp.application(&name) else { return false };
            if file.method("<clinit>", "()V").is_some() {
                return false;
            }
            class = file.super_class.clone();
        }
        true
    })
}

/// Whether a changed helper's closure in one version is of the narrow kind a proof of its equivalence lets one stub
/// stand for: integral values only, and no exception of its own (see the module's documentation).
fn provable(cp: &ClassPath, root: &MemberRef, closure: &Closure) -> bool {
    !closure.raises && !closure.floating && cp.is_application(&root.owner) && closure.throws.iter().all(|t| t == "java/lang/ArithmeticException")
}

/// A closure of at most this many instructions, without a loop, a multiplication, a division or a remainder, is
/// not worth a stub.
const TRIVIAL_INSNS: usize = 16;

/// Whether a callee costs the solver less as written than as one function in both versions: `Math.min`,
/// `Math.abs`, a small comparison or a sum. As one function its result on different arguments in the two versions
/// is unconstrained, so a counterexample through it rarely reproduces and the proof is run again as written; as
/// written it is a few constraints.
fn trivial(cp: &ClassPath, closure: &Closure) -> bool {
    let mut total = 0;
    for m in &closure.methods {
        let Some((_, method)) = cp.find_method(&m.owner, &m.name, &m.descriptor) else { return false };
        let Some(code) = &method.code else { return false };
        let Ok(insns) = code.instructions() else { return false };
        total += insns.len();
        for (offset, insn) in &insns {
            let costly = matches!(insn, Insn::Arith(ArithOp::Mul | ArithOp::Div | ArithOp::Rem, _) | Insn::TableSwitch { .. } | Insn::LookupSwitch { .. }) || insn.targets().iter().any(|t| t <= offset);
            if costly {
                return false;
            }
        }
    }
    total <= TRIVIAL_INSNS
}

/// The closure of `root` when every method in it is a static method over primitives that touches no field, no
/// array and nothing of the JDK beyond its arithmetic, the building of an exception message, and the exception
/// itself; `None` otherwise. The exceptions it can throw are the ones it constructs and the arithmetic ones.
fn pure_closure(cp: &ClassPath, root: &MemberRef) -> Option<Closure> {
    let mut out = Closure { methods: Vec::new(), throws: BTreeSet::new(), raises: false, floating: false };
    let mut seen: HashSet<MemberRef> = HashSet::new();
    let mut work: VecDeque<MemberRef> = VecDeque::from([root.clone()]);
    while let Some(reference) = work.pop_front() {
        if !seen.insert(reference.clone()) {
            continue;
        }
        let (class, method) = cp.find_method(&reference.owner, &reference.name, &reference.descriptor)?;
        let declared = MemberRef::new(&class.name, &reference.name, &reference.descriptor);
        let callees = local_facts(cp, &class, &method, reference == *root, &mut out)?;
        out.methods.push(declared);
        work.extend(callees);
    }
    Some(out)
}

/// Checks one method of a pure closure and returns the static callees it has; adds what it can throw.
fn local_facts(cp: &ClassPath, class: &ClassFile, method: &Method, root: bool, closure: &mut Closure) -> Option<Vec<MemberRef>> {
    if !method.is_static() || method.is_native() {
        return None;
    }
    let code = method.code.as_ref()?;
    let descriptor = method.parsed_descriptor().ok()?;
    if !descriptor.params.iter().all(Type::is_primitive) || !(descriptor.ret.is_primitive() || (!root && descriptor.ret == Type::Void)) || (root && descriptor.ret == Type::Void) {
        return None;
    }
    if descriptor.params.iter().chain([&descriptor.ret]).any(|t| matches!(t, Type::Float | Type::Double)) {
        closure.floating = true;
    }
    let throws = &mut closure.throws;
    let pool = &class.pool;
    let mut callees = Vec::new();
    for (_, insn) in code.instructions().ok()? {
        match insn {
            Insn::Ldc(i) => {
                if !matches!(pool.loadable(i).ok()?, BootstrapArg::Int(_) | BootstrapArg::Float(_) | BootstrapArg::Long(_) | BootstrapArg::Double(_) | BootstrapArg::Str(_)) {
                    return None;
                }
            }
            Insn::GetStatic(_) | Insn::PutStatic(_) | Insn::GetField(_) | Insn::PutField(_) => return None,
            Insn::ArrayLoad(_) | Insn::ArrayStore(_) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::MultiANewArray(..) | Insn::ArrayLength => return None,
            Insn::MonitorEnter | Insn::MonitorExit | Insn::Jsr(_) | Insn::Ret(_) | Insn::CheckCast(_) | Insn::InstanceOf(_) | Insn::InvokeInterface(_) => return None,
            Insn::New(i) => {
                let name = pool.class_name(i).ok()?;
                if cp.is_subtype(name, "java/lang/Throwable") {
                    throws.insert(name.to_string());
                    closure.raises = true;
                } else if name != "java/lang/StringBuilder" {
                    return None;
                }
            }
            Insn::InvokeSpecial(i) => {
                let callee = pool.member(i).ok()?;
                if callee.name != "<init>" || !(callee.owner == "java/lang/StringBuilder" || cp.is_subtype(&callee.owner, "java/lang/Throwable")) {
                    return None;
                }
            }
            Insn::InvokeVirtual(i) => {
                let callee = pool.member(i).ok()?;
                if callee.owner != "java/lang/StringBuilder" && callee.owner != "java/lang/String" {
                    return None;
                }
            }
            Insn::InvokeStatic(i) => {
                let callee = pool.member(i).ok()?;
                if followed(cp, &callee.owner) {
                    callees.push(callee);
                } else if callee.owner != "java/lang/String" {
                    return None;
                }
            }
            Insn::InvokeDynamic(i) => {
                let (b, _, _) = pool.invoke_dynamic(i).ok()?;
                let bootstraps = class.bootstrap_methods().ok()?;
                if bootstraps.get(b as usize)?.method.member.owner != "java/lang/invoke/StringConcatFactory" {
                    return None;
                }
            }
            Insn::Arith(ArithOp::Div | ArithOp::Rem, Kind::Int | Kind::Long) => {
                throws.insert("java/lang/ArithmeticException".to_string());
            }
            Insn::AThrow => closure.raises = true,
            _ => {}
        }
    }
    Some(callees)
}

/// The constructor the stub uses to throw an exception class: the no-argument one, else the one taking a
/// message, which gets `null`.
fn constructor(cp: &ClassPath, class: &str) -> Option<&'static str> {
    let loaded = cp.load(class).ok()??;
    ["()V", "(Ljava/lang/String;)V"].into_iter().find(|d| loaded.class.method("<init>", d).is_some())
}

fn kind_of(t: &Type) -> Kind {
    match t {
        Type::Long => Kind::Long,
        Type::Float => Kind::Float,
        Type::Double => Kind::Double,
        Type::Object(_) | Type::Array(_) => Kind::Ref,
        _ => Kind::Int,
    }
}

fn nondet(t: &Type) -> (&'static str, &'static str) {
    match t {
        Type::Boolean => ("nondetBoolean", "()Z"),
        Type::Byte => ("nondetByte", "()B"),
        Type::Char => ("nondetChar", "()C"),
        Type::Short => ("nondetShort", "()S"),
        Type::Long => ("nondetLong", "()J"),
        Type::Float => ("nondetFloat", "()F"),
        Type::Double => ("nondetDouble", "()D"),
        _ => ("nondetInt", "()I"),
    }
}

/// The stub class: one static method per callee, with the memo table in static fields.
pub fn stub(cp: &ClassPath, callees: &[Callee]) -> Result<Vec<u8>, Error> {
    let mut w = ClassWriter::new(CLASS);
    w.source_file = Some("SharedCallees.java".into());
    for (index, callee) in callees.iter().enumerate() {
        let descriptor = crate::classfile::MethodDescriptor::parse(&callee.descriptor).map_err(|e| Error::new(format!("{}: {e}", callee.display())))?;
        let params = &descriptor.params;
        let ret = &descriptor.ret;
        let count = format!("n{index}");
        let arg = |e: u16, j: usize| format!("a{index}_{e}_{j}");
        let res = |e: u16| format!("r{index}_{e}");
        let kind_field = |e: u16| format!("t{index}_{e}");
        w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: count.clone(), descriptor: "I".into() });
        for e in 0..ENTRIES {
            for (j, p) in params.iter().enumerate() {
                w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: arg(e, j), descriptor: p.descriptor() });
            }
            w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: res(e), descriptor: ret.descriptor() });
            w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: kind_field(e), descriptor: "I".into() });
        }
        let count_ref = w.pool.field_ref(CLASS, &count, "I");
        let field = |w: &mut ClassWriter, name: &str, descriptor: &str| w.pool.field_ref(CLASS, name, descriptor);
        let mut slots = Vec::new();
        let mut slot = 0u16;
        for p in params {
            slots.push(slot);
            slot += p.slots();
        }
        let r_slot = slot;
        let t_slot = r_slot + ret.slots();
        let ret_kind = kind_of(ret);
        let mut code = CodeBuilder::new();
        code.max_locals = t_slot + 1;
        let done = code.label();
        // An outcome given before on these arguments is given again.
        for e in 0..ENTRIES {
            let next = code.label();
            code.op_u16(0xb2, count_ref);
            code.iconst(i32::from(e));
            code.if_icmp(Cond::Le, next);
            for (j, p) in params.iter().enumerate() {
                let f = field(&mut w, &arg(e, j), &p.descriptor());
                code.load(kind_of(p), slots[j]);
                code.op_u16(0xb2, f);
                match kind_of(p) {
                    Kind::Int => code.if_icmp(Cond::Ne, next),
                    Kind::Long => {
                        code.op(0x94);
                        code.if_zero(Cond::Ne, next);
                    }
                    Kind::Float => {
                        code.op(0x95);
                        code.if_zero(Cond::Ne, next);
                    }
                    Kind::Double => {
                        code.op(0x97);
                        code.if_zero(Cond::Ne, next);
                    }
                    Kind::Ref => return Err(Error::new("a shared callee takes primitives only")),
                }
            }
            let t = field(&mut w, &kind_field(e), "I");
            code.op_u16(0xb2, t);
            code.store(Kind::Int, t_slot);
            let r = field(&mut w, &res(e), &ret.descriptor());
            code.op_u16(0xb2, r);
            code.store(ret_kind, r_slot);
            code.goto(done);
            code.bind(next);
        }
        // New arguments: an arbitrary outcome, a result or one of the exceptions, remembered while there is room.
        let (name, nd) = nondet(ret);
        let fresh = w.pool.method_ref(NONDET, name, nd);
        code.op_u16(0xb8, fresh);
        code.store(ret_kind, r_slot);
        if callee.throws.is_empty() {
            code.iconst(0);
            code.store(Kind::Int, t_slot);
        } else {
            let fresh_int = w.pool.method_ref(NONDET, "nondetInt", "()I");
            code.op_u16(0xb8, fresh_int);
            code.store(Kind::Int, t_slot);
            let reset = code.label();
            let in_range = code.label();
            code.load(Kind::Int, t_slot);
            code.if_zero(Cond::Lt, reset);
            code.load(Kind::Int, t_slot);
            code.iconst(callee.throws.len() as i32);
            code.if_icmp(Cond::Le, in_range);
            code.bind(reset);
            code.iconst(0);
            code.store(Kind::Int, t_slot);
            code.bind(in_range);
        }
        for e in 0..ENTRIES {
            let skip = code.label();
            code.op_u16(0xb2, count_ref);
            code.iconst(i32::from(e));
            code.if_icmp(Cond::Ne, skip);
            for (j, p) in params.iter().enumerate() {
                let f = field(&mut w, &arg(e, j), &p.descriptor());
                code.load(kind_of(p), slots[j]);
                code.op_u16(0xb3, f);
            }
            let r = field(&mut w, &res(e), &ret.descriptor());
            code.load(ret_kind, r_slot);
            code.op_u16(0xb3, r);
            let t = field(&mut w, &kind_field(e), "I");
            code.load(Kind::Int, t_slot);
            code.op_u16(0xb3, t);
            code.iconst(i32::from(e) + 1);
            code.op_u16(0xb3, count_ref);
            code.goto(done);
            code.bind(skip);
        }
        code.bind(done);
        for (k, exception) in callee.throws.iter().enumerate() {
            let next = code.label();
            code.load(Kind::Int, t_slot);
            code.iconst(k as i32 + 1);
            code.if_icmp(Cond::Ne, next);
            let class = w.pool.class(exception);
            let ctor = constructor(cp, exception).ok_or_else(|| Error::new(format!("{exception} has no constructor the stub can call")))?;
            let init = w.pool.method_ref(exception, "<init>", ctor);
            code.op_u16(0xbb, class);
            code.op(0x59);
            if ctor != "()V" {
                code.op(0x01);
            }
            code.op_u16(0xb7, init);
            code.op(0xbf);
            code.bind(next);
        }
        code.load(ret_kind, r_slot);
        code.return_(Some(ret_kind));
        w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: callee.stub_method(index), descriptor: callee.descriptor.clone(), code: Some(code) });
    }
    Ok(w.to_bytes())
}

/// Rewrites every `invokestatic` of a shared callee in a class file to the stub method `lookup` names for it.
/// Returns `None` when the class calls none of them. The constant pool gains the entries the new references
/// need; nothing else moves, so the code's offsets are unchanged.
pub fn redirect(bytes: &[u8], lookup: &dyn Fn(&MemberRef) -> Option<String>) -> Result<Option<Vec<u8>>, Error> {
    redirect_calls(bytes, &|invoke, m| if invoke == Invoke::Static { lookup(m).map(|name| MemberRef::new(CLASS, &name, &m.descriptor)) } else { None })
}

/// How a call site invokes its method.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Invoke {
    Static,
    /// `invokespecial`: a constructor, a private method or a superclass's.
    Special,
    Virtual,
    Interface,
}

/// Rewrites each call site `lookup` gives a static method for into an `invokestatic` of that method, which takes
/// what the call left on the stack: for any call but a static one, the receiver first, then the arguments. Returns
/// `None` when no call site is rewritten. The constant pool gains the entries the new references need, and
/// nothing else moves: an `invokeinterface`, five bytes long, becomes an `invokestatic` and two `nop`s, so the
/// code's offsets are unchanged. The class is no longer one a verifier accepts when a constructor's receiver,
/// still uninitialized, is passed on; JBMC, the one checker that runs such classes, verifies nothing.
pub fn redirect_calls(bytes: &[u8], lookup: &dyn Fn(Invoke, &MemberRef) -> Option<MemberRef>) -> Result<Option<Vec<u8>>, Error> {
    redirect_calls_at(bytes, &|_, _, invoke, m| lookup(invoke, m))
}

/// [`redirect_calls`], for a `lookup` that also sees where the call site is: the method it is in, and the
/// instruction's place in that method's code, counted from 0 (how JBMC's goto listing numbers it as its
/// `bytecode-index`).
pub fn redirect_calls_at(bytes: &[u8], lookup: &dyn Fn(&crate::classfile::Method, u32, Invoke, &MemberRef) -> Option<MemberRef>) -> Result<Option<Vec<u8>>, Error> {
    let class = ClassFile::parse(bytes)?;
    let (pool_end, mut count) = pool_extent(bytes)?;
    let code_offsets = code_offsets(bytes, &class.pool, pool_end)?;
    let mut added: Vec<u8> = Vec::new();
    let mut classes: BTreeMap<String, u16> = BTreeMap::new();
    let mut refs: BTreeMap<(String, String, String), u16> = BTreeMap::new();
    // Where each rewritten instruction's opcode is, the method reference it takes, and whether it was an
    // `invokeinterface`.
    let mut patches: Vec<(usize, u16, bool)> = Vec::new();
    let push_utf8 = |added: &mut Vec<u8>, count: &mut u16, s: &str| -> u16 {
        let encoded = encode_modified_utf8(s);
        added.push(1);
        added.extend((encoded.len() as u16).to_be_bytes());
        added.extend(encoded);
        *count += 1;
        *count - 1
    };
    for (method, offset) in class.methods.iter().zip(&code_offsets) {
        let (Some(code), Some(offset)) = (&method.code, offset) else { continue };
        for (place, (pc, insn)) in code.instructions()?.into_iter().enumerate() {
            let (invoke, i) = match insn {
                Insn::InvokeStatic(i) => (Invoke::Static, i),
                Insn::InvokeSpecial(i) => (Invoke::Special, i),
                Insn::InvokeVirtual(i) => (Invoke::Virtual, i),
                Insn::InvokeInterface(i) => (Invoke::Interface, i),
                _ => continue,
            };
            let Ok(callee) = class.pool.member(i) else { continue };
            let Some(target) = lookup(method, place as u32, invoke, &callee) else { continue };
            let key = (target.owner.clone(), target.name.clone(), target.descriptor.clone());
            let index = match refs.get(&key) {
                Some(index) => *index,
                None => {
                    let class_index = match classes.get(&target.owner) {
                        Some(c) => *c,
                        None => {
                            let name = push_utf8(&mut added, &mut count, &target.owner);
                            added.push(7);
                            added.extend(name.to_be_bytes());
                            count += 1;
                            classes.insert(target.owner.clone(), count - 1);
                            count - 1
                        }
                    };
                    let name = push_utf8(&mut added, &mut count, &target.name);
                    let descriptor = push_utf8(&mut added, &mut count, &target.descriptor);
                    added.push(12);
                    added.extend(name.to_be_bytes());
                    added.extend(descriptor.to_be_bytes());
                    count += 1;
                    let nat = count - 1;
                    added.push(10);
                    added.extend(class_index.to_be_bytes());
                    added.extend(nat.to_be_bytes());
                    count += 1;
                    refs.insert(key, count - 1);
                    count - 1
                }
            };
            patches.push((offset + pc as usize, index, invoke == Invoke::Interface));
        }
    }
    if patches.is_empty() {
        return Ok(None);
    }
    let mut out = Vec::with_capacity(bytes.len() + added.len());
    out.extend_from_slice(&bytes[..8]);
    out.extend(count.to_be_bytes());
    out.extend_from_slice(&bytes[10..pool_end]);
    out.extend_from_slice(&added);
    out.extend_from_slice(&bytes[pool_end..]);
    let shift = added.len();
    for (at, index, interface) in patches {
        let at = at + shift;
        out[at] = 0xb8; // invokestatic
        out[at + 1..at + 3].copy_from_slice(&index.to_be_bytes());
        if interface {
            out[at + 3] = 0x00; // nop
            out[at + 4] = 0x00;
        }
    }
    Ok(Some(out))
}

/// Where the constant pool ends, and its count.
fn pool_extent(bytes: &[u8]) -> Result<(usize, u16), Error> {
    let mut pos = 8usize;
    let count = u16::from_be_bytes([*bytes.get(8).ok_or_else(truncated)?, *bytes.get(9).ok_or_else(truncated)?]);
    pos += 2;
    let mut i = 1;
    while i < count {
        let tag = *bytes.get(pos).ok_or_else(truncated)?;
        pos += 1;
        match tag {
            1 => {
                let len = u16::from_be_bytes([*bytes.get(pos).ok_or_else(truncated)?, *bytes.get(pos + 1).ok_or_else(truncated)?]) as usize;
                pos += 2 + len;
            }
            3 | 4 => pos += 4,
            5 | 6 => {
                pos += 8;
                i += 1;
            }
            7 | 8 | 16 | 19 | 20 => pos += 2,
            9 | 10 | 11 | 12 | 17 | 18 => pos += 4,
            15 => pos += 3,
            other => return Err(Error::new(format!("unknown constant pool tag {other}"))),
        }
        i += 1;
    }
    if pos > bytes.len() {
        return Err(truncated());
    }
    Ok((pos, count))
}

fn truncated() -> Error {
    Error::new("truncated class file")
}

/// The offset of each method's code bytes in the class file, in declaration order (`None` without a `Code`
/// attribute).
fn code_offsets(bytes: &[u8], pool: &ConstantPool, pool_end: usize) -> Result<Vec<Option<usize>>, Error> {
    let u16_at = |pos: usize| -> Result<u16, Error> { Ok(u16::from_be_bytes([*bytes.get(pos).ok_or_else(truncated)?, *bytes.get(pos + 1).ok_or_else(truncated)?])) };
    let u32_at = |pos: usize| -> Result<u32, Error> {
        Ok(u32::from_be_bytes([*bytes.get(pos).ok_or_else(truncated)?, *bytes.get(pos + 1).ok_or_else(truncated)?, *bytes.get(pos + 2).ok_or_else(truncated)?, *bytes.get(pos + 3).ok_or_else(truncated)?]))
    };
    let mut pos = pool_end + 6;
    let interfaces = u16_at(pos)? as usize;
    pos += 2 + 2 * interfaces;
    let fields = u16_at(pos)?;
    pos += 2;
    for _ in 0..fields {
        pos += 6;
        let attributes = u16_at(pos)?;
        pos += 2;
        for _ in 0..attributes {
            pos += 6 + u32_at(pos + 2)? as usize;
        }
    }
    let methods = u16_at(pos)?;
    pos += 2;
    let mut out = Vec::with_capacity(methods as usize);
    for _ in 0..methods {
        pos += 6;
        let attributes = u16_at(pos)?;
        pos += 2;
        let mut code = None;
        for _ in 0..attributes {
            let name = pool.utf8(u16_at(pos)?).unwrap_or("");
            if name == "Code" {
                code = Some(pos + 6 + 8);
            }
            pos += 6 + u32_at(pos + 2)? as usize;
        }
        out.push(code);
    }
    Ok(out)
}

/// Copies into `output` every class under `input` that calls a shared callee, with the calls redirected; the
/// classes that call none stay where they are. Returns how many were written.
pub fn redirect_directory(input: &Path, output: &Path, lookup: &dyn Fn(&MemberRef) -> Option<String>) -> Result<usize, Error> {
    redirect_calls_directory(input, output, &|invoke, m| if invoke == Invoke::Static { lookup(m).map(|name| MemberRef::new(CLASS, &name, &m.descriptor)) } else { None })
}

/// Copies into `output` every class under `input` with a call site `lookup` redirects ([`redirect_calls`]); the
/// others stay where they are. Returns how many were written.
pub fn redirect_calls_directory(input: &Path, output: &Path, lookup: &dyn Fn(Invoke, &MemberRef) -> Option<MemberRef>) -> Result<usize, Error> {
    let mut written = 0;
    let mut dirs = vec![input.to_path_buf()];
    while let Some(dir) = dirs.pop() {
        for entry in std::fs::read_dir(&dir)? {
            let path = entry?.path();
            if path.is_dir() {
                dirs.push(path);
            } else if path.extension().is_some_and(|e| e == "class") {
                let bytes = std::fs::read(&path)?;
                if let Some(patched) = redirect_calls(&bytes, lookup)? {
                    let target = output.join(path.strip_prefix(input).unwrap_or(&path));
                    if let Some(parent) = target.parent() {
                        std::fs::create_dir_all(parent)?;
                    }
                    std::fs::write(target, patched)?;
                    written += 1;
                }
            }
        }
    }
    Ok(written)
}

/// Copies into `output` every class of the previous version (under `before_dir`, relocated under `prefix`) that calls
/// a proved helper of `callees`, with each such call redirected to the new version's method: the one function a
/// proved helper is in both versions under the tool's own checker (see the module's documentation). Returns how many
/// were written.
pub fn substitute_directory(before_dir: &Path, output: &Path, prefix: &str, callees: &[Callee]) -> Result<usize, Error> {
    redirect_calls_directory(before_dir, output, &|invoke, m| {
        if invoke != Invoke::Static {
            return None;
        }
        let owner = original_owner(&m.owner, prefix);
        callees.iter().find(|c| c.proved.is_some() && owner != m.owner && c.owner == owner && c.name == m.name && c.descriptor == m.descriptor).map(Callee::member)
    })
}

/// For the tool's own checker: when `callees` has a proved helper, writes the previous version's classes (under
/// `before_dir`, relocated under `before`) that call one into `dir`, with those calls redirected to the new version
/// ([`substitute_directory`]), puts `dir` second on the checker's class path `entries` (after the harness), and
/// returns the names of the helpers so shared, as [`names`] gives them; otherwise changes nothing.
///
/// A proved instance method is a read-only helper whose summary [`crate::reuse::application`] made (R2): each call of
/// it, in both versions, becomes a call of that version's adapter ([`crate::reuse::footprint::adapters`]), which
/// reads the fields of its footprint from the actual receiver and calls the new version's lifted helper; the lifted
/// helper and the adapters are written into `dir` too. A call is so redirected only where the version's class path
/// resolves it to the helper as declared, by name and descriptor, and only from an `invokevirtual` or an
/// `invokespecial`. A proved instance method with no application on this thread keeps its body in both versions,
/// which is the versions as written.
pub fn substitute(callees: &[Callee], before_dir: &Path, dir: &Path, entries: &mut Vec<std::path::PathBuf>) -> Result<Vec<String>, Error> {
    if callees.iter().all(|c| c.proved.is_none()) {
        return Ok(Vec::new());
    }
    std::fs::create_dir_all(dir)?;
    let applications: Vec<crate::reuse::Application> = callees.iter().filter_map(|c| c.proved.as_ref().and_then(|p| crate::reuse::applied(&p.key, &c.member()))).collect();
    if let Some(other) = applications.iter().find(|a| a.after != applications[0].after) {
        return Err(Error::new(format!("the summaries of one check apply to two builds, {} and {}", applications[0].after.display(), other.after.display())));
    }
    let summarized = |c: &Callee| applications.iter().any(|a| a.helper == c.member());
    let statics: Vec<Callee> = callees.iter().filter(|c| !summarized(c)).cloned().collect();
    if applications.is_empty() {
        substitute_directory(before_dir, dir, "before", &statics)?;
    } else {
        let mut before_cp = ClassPath::new();
        before_cp.add(before_dir)?;
        let after_dir = applications[0].after.clone();
        let mut after_cp = ClassPath::new();
        after_cp.add(&after_dir)?;
        let summary_call = |cp: &ClassPath, prefix: Option<&str>, invoke: Invoke, m: &MemberRef| -> Option<MemberRef> {
            if !matches!(invoke, Invoke::Virtual | Invoke::Special) {
                return None;
            }
            let (class, method) = cp.find_method(&m.owner, &m.name, &m.descriptor)?;
            if method.is_static() {
                return None;
            }
            let declared = original_owner(&class.name, prefix.unwrap_or(""));
            if prefix.is_some() && declared == class.name {
                return None; // not one of the previous version's relocated classes
            }
            applications.iter().find(|a| a.helper.owner == declared && a.helper.name == m.name && a.helper.descriptor == m.descriptor).map(|a| if prefix.is_some() { a.adapters.before.clone() } else { a.adapters.after.clone() })
        };
        redirect_calls_directory(before_dir, dir, &|invoke, m| {
            if invoke == Invoke::Static {
                let owner = original_owner(&m.owner, "before");
                return statics.iter().find(|c| c.proved.is_some() && owner != m.owner && c.owner == owner && c.name == m.name && c.descriptor == m.descriptor).map(Callee::member);
            }
            summary_call(&before_cp, Some("before"), invoke, m)
        })?;
        redirect_calls_directory(&after_dir, dir, &|invoke, m| summary_call(&after_cp, None, invoke, m))?;
        for a in &applications {
            for (name, bytes) in &a.classes {
                let file = dir.join(format!("{name}.class"));
                if let Some(parent) = file.parent() {
                    std::fs::create_dir_all(parent)?;
                }
                std::fs::write(file, bytes)?;
            }
        }
    }
    entries.insert(1.min(entries.len()), dir.to_path_buf());
    Ok(names(callees).into_iter().zip(callees).filter(|(_, c)| c.proved.is_some()).map(|(n, _)| n).collect())
}

/// The owner a relocated call names, back in the original package: `before/a/B` is `a/B`.
pub fn original_owner<'a>(owner: &'a str, prefix: &str) -> &'a str {
    owner.strip_prefix(prefix).and_then(|s| s.strip_prefix('/')).unwrap_or(owner)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_relocated_owner_is_mapped_back() {
        assert_eq!(original_owner("before/a/B", "before"), "a/B");
        assert_eq!(original_owner("a/B", "before"), "a/B");
        assert_eq!(original_owner("beforehand/B", "before"), "beforehand/B");
    }

    #[test]
    fn the_stub_class_parses_and_declares_a_method_per_callee() {
        let cp = ClassPath::new().with_default_jdk();
        let callees = vec![
            Callee { owner: "a/Shares".into(), name: "perSeat".into(), descriptor: "(JI)J".into(), throws: vec!["java/lang/ArithmeticException".into(), "java/lang/IllegalArgumentException".into()], proved: None },
            Callee { owner: "java/lang/Math".into(), name: "abs".into(), descriptor: "(D)D".into(), throws: Vec::new(), proved: None },
        ];
        let bytes = stub(&cp, &callees).unwrap();
        let class = ClassFile::parse(&bytes).unwrap();
        assert_eq!(class.name, CLASS);
        assert!(class.method("m0_perSeat", "(JI)J").is_some());
        assert!(class.method("m1_abs", "(D)D").is_some());
        assert_eq!(class.fields.iter().filter(|f| f.name.starts_with("a0_")).count(), usize::from(ENTRIES) * 2);
        let code = class.method("m0_perSeat", "(JI)J").unwrap().code.as_ref().unwrap();
        let insns = code.instructions().unwrap();
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::AThrow)).count(), 2);
    }
}

/// Writes into `dir` the stub class for `callees` and the classes of each of `versions` (the new version's
/// directory, and the previous version's relocated one) that call one of them, with those calls redirected to the
/// stub: the class path entry that goes ahead of the versions as written when the callees are shared under JBMC.
pub fn stub_directory(cp: &ClassPath, callees: &[Callee], versions: &[&Path], dir: &Path) -> Result<(), Error> {
    std::fs::create_dir_all(dir)?;
    std::fs::write(dir.join(format!("{CLASS}.class")), stub(cp, callees)?)?;
    let lookup = |m: &MemberRef| -> Option<String> {
        let owner = original_owner(&m.owner, "before");
        callees.iter().position(|c| c.owner == owner && c.name == m.name && c.descriptor == m.descriptor).map(|i| callees[i].stub_method(i))
    };
    for version in versions {
        redirect_directory(version, dir, &lookup)?;
    }
    Ok(())
}

// Refinement per callee (`llm-dlc/loops/foundations-summaries.md`, S5). A counterexample JBMC finds with the callees
// as stubs is one to the versions as written only if it reproduces through their bytecode; when it doesn't, some
// stub gave an answer its callee never gives. Which one is read off the counterexample itself: the stubs' memo
// tables, as the trace leaves them, are what each stub answered and on which arguments ([`answers`]). The two
// versions are replayed on the counterexample's input with a stub that gives those answers again ([`replay_stub`]),
// once with every callee so, which must show the disagreement JBMC found, and then once per callee with that one
// computed as written instead. A callee whose real answers make the disagreement vanish is one the counterexample
// rests on ([`spurious`]), and only those are computed as written in the next run; the others stay one function.
// Whichever callees are blamed, the next run is still sound for a proof (any subset of the stubs over-approximates
// the callees), and its counterexample is replayed as written in turn, so the blame decides only how much of the
// proof is computed again, never a verdict.

/// What a stub answered on one call, as a counterexample's trace leaves its memo table.
#[derive(Debug, Clone, PartialEq)]
pub struct Answer {
    pub arguments: Vec<crate::interp::Value>,
    pub outcome: Answered,
}

/// A stub's answer: a result (`None` for a `void` callee), or an exception of the class named.
#[derive(Debug, Clone, PartialEq)]
pub enum Answered {
    Returned(Option<crate::interp::Value>),
    Threw(String),
}

/// The answers each of `callees` gave in the counterexample of the JBMC run whose `--json-ui` output is `output`, in
/// the order of `callees` (the stub's own, by index). `marker` is the harness's `Class.method`, which names the
/// assertion whose trace is read. `None` when the output holds no such trace or a memo table can't be read from it:
/// then nothing can be told about the stubs.
pub fn answers(output: &str, callees: &[Callee], marker: &str) -> Option<Vec<Vec<Answer>>> {
    let items = crate::jbmc::json_items(output);
    let results = items.iter().find_map(|i| i.get("result").and_then(|r| r.as_array()))?;
    let failed = results.iter().find(|p| {
        let id = p.get("property").and_then(|s| s.as_str()).unwrap_or_default();
        p.get("status").and_then(|s| s.as_str()) == Some("FAILURE") && id.contains(marker) && id.contains("assertion")
    })?;
    let steps = failed.get("trace")?.as_array()?;
    // The memo fields' last values, assigned in the stub's own methods (its locals are anonymous, and a field of the
    // application's assigned elsewhere is not one of its).
    let mut fields: BTreeMap<String, serde_json::Value> = BTreeMap::new();
    let mut stack: Vec<String> = Vec::new();
    let prefix = format!("java::{CLASS}.");
    for step in steps {
        match step.get("stepType").and_then(|t| t.as_str()) {
            Some("function-call") => stack.push(step.get("function").and_then(|f| f.get("identifier")).and_then(|i| i.as_str()).unwrap_or_default().to_string()),
            Some("function-return") => {
                stack.pop();
            }
            Some("assignment") if stack.last().is_some_and(|f| f.starts_with(&prefix)) => {
                if let (Some(lhs), Some(value)) = (step.get("lhs").and_then(|l| l.as_str()), step.get("value")) {
                    fields.insert(lhs.to_string(), value.clone());
                }
            }
            _ => {}
        }
    }
    let mut out = Vec::new();
    for (index, callee) in callees.iter().enumerate() {
        let descriptor = crate::classfile::MethodDescriptor::parse(&callee.descriptor).ok()?;
        let count = match fields.get(&format!("n{index}")) {
            Some(v) => trace_value(&Type::Int, v)?.as_int(),
            None => 0,
        };
        let mut entries = Vec::new();
        for e in 0..count.clamp(0, i32::from(ENTRIES)) {
            let arguments = descriptor.params.iter().enumerate().map(|(j, p)| trace_value(p, fields.get(&format!("a{index}_{e}_{j}"))?)).collect::<Option<Vec<_>>>()?;
            let kind = trace_value(&Type::Int, fields.get(&format!("t{index}_{e}"))?)?.as_int();
            let outcome = if kind == 0 {
                Answered::Returned(if descriptor.ret == Type::Void { None } else { Some(trace_value(&descriptor.ret, fields.get(&format!("r{index}_{e}"))?)?) })
            } else {
                Answered::Threw(callee.throws.get(usize::try_from(kind - 1).ok()?)?.clone())
            };
            entries.push(Answer { arguments, outcome });
        }
        out.push(entries);
    }
    Some(out)
}

/// A primitive of a trace, from its bits.
fn trace_value(t: &Type, value: &serde_json::Value) -> Option<crate::interp::Value> {
    use crate::interp::Value;
    let bits = value.get("binary")?.as_str()?;
    let raw = u64::from_str_radix(bits, 2).ok()?;
    let width = bits.len() as u32;
    let signed = |w: u32| -> i64 { if w == 0 || w >= 64 { raw as i64 } else { ((raw << (64 - w)) as i64) >> (64 - w) } };
    Some(match t {
        Type::Long => Value::Long(raw as i64),
        Type::Float => Value::Float(f32::from_bits(raw as u32)),
        Type::Double => Value::Double(f64::from_bits(raw)),
        Type::Boolean | Type::Char => Value::Int(raw as i32),
        Type::Int | Type::Short | Type::Byte => Value::Int(signed(width) as i32),
        _ => return None,
    })
}

/// A stub class for replaying a counterexample: each of `callees` (by the index the stub JBMC ran with gave it)
/// gives the answers `answers` holds for it on those arguments, compared as the stub compares them, and on any
/// other arguments, or with no answers given, is the callee as written.
pub fn replay_stub(cp: &ClassPath, callees: &[Callee], answers: &[Option<&[Answer]>]) -> Result<Vec<u8>, Error> {
    use crate::interp::Value;
    let mut w = ClassWriter::new(CLASS);
    w.source_file = Some("SharedCallees.java".into());
    for (index, callee) in callees.iter().enumerate() {
        let descriptor = crate::classfile::MethodDescriptor::parse(&callee.descriptor).map_err(|e| Error::new(format!("{}: {e}", callee.display())))?;
        let mut slots = Vec::new();
        let mut slot = 0u16;
        for p in &descriptor.params {
            slots.push(slot);
            slot += p.slots();
        }
        let ret = (descriptor.ret != Type::Void).then(|| kind_of(&descriptor.ret));
        let mut code = CodeBuilder::new();
        code.max_locals = slot;
        let push = |w: &mut ClassWriter, code: &mut CodeBuilder, v: &Value| match *v {
            Value::Int(i) if (-32768..=32767).contains(&i) => code.iconst(i),
            Value::Int(i) => code.ldc(w.pool.integer(i)),
            Value::Long(l) => code.ldc2(w.pool.long(l)),
            Value::Float(f) => code.ldc(w.pool.float(f)),
            Value::Double(d) => code.ldc2(w.pool.double(d)),
            _ => code.op(0x01),
        };
        for answer in answers.get(index).copied().flatten().unwrap_or(&[]) {
            let next = code.label();
            for (j, p) in descriptor.params.iter().enumerate() {
                code.load(kind_of(p), slots[j]);
                push(&mut w, &mut code, &answer.arguments[j]);
                match kind_of(p) {
                    Kind::Int => code.if_icmp(Cond::Ne, next),
                    Kind::Long => {
                        code.op(0x94);
                        code.if_zero(Cond::Ne, next);
                    }
                    Kind::Float => {
                        code.op(0x95);
                        code.if_zero(Cond::Ne, next);
                    }
                    Kind::Double => {
                        code.op(0x97);
                        code.if_zero(Cond::Ne, next);
                    }
                    Kind::Ref => return Err(Error::new("a shared callee takes primitives only")),
                }
            }
            match &answer.outcome {
                Answered::Returned(value) => {
                    if let Some(v) = value {
                        push(&mut w, &mut code, v);
                    }
                    code.return_(ret);
                }
                Answered::Threw(exception) => {
                    let class = w.pool.class(exception);
                    let ctor = constructor(cp, exception).ok_or_else(|| Error::new(format!("{exception} has no constructor the stub can call")))?;
                    let init = w.pool.method_ref(exception, "<init>", ctor);
                    code.op_u16(0xbb, class);
                    code.op(0x59);
                    if ctor != "()V" {
                        code.op(0x01);
                    }
                    code.op_u16(0xb7, init);
                    code.op(0xbf);
                }
            }
            code.bind(next);
        }
        for (j, p) in descriptor.params.iter().enumerate() {
            code.load(kind_of(p), slots[j]);
        }
        let real = w.pool.method_ref(&callee.owner, &callee.name, &callee.descriptor);
        code.op_u16(0xb8, real);
        code.return_(ret);
        w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: callee.stub_method(index), descriptor: callee.descriptor.clone(), code: Some(code) });
    }
    Ok(w.to_bytes())
}

/// Which of `callees` a counterexample found with all of them as stubs rests on, by index: those whose answers as
/// written, in place of the stub's, make the two versions agree on its input (the notes above [`Answer`]). `disagrees`
/// replays the two versions on that input with the class path entry it is given (a directory holding a replay
/// stub) ahead of the redirected classes, and says whether they still differ. Each replay stub is written under
/// `dir`. `None` when the stubs' answers, given again, don't reproduce the disagreement (the trace was not read
/// whole, or a stub's table overflowed), or when no one callee's answers undo it: then nothing is told apart.
pub fn spurious(cp: &ClassPath, callees: &[Callee], answers: &[Vec<Answer>], dir: &Path, disagrees: &mut dyn FnMut(&Path) -> bool) -> Result<Option<Vec<usize>>, Error> {
    let write = |name: &str, real: Option<usize>| -> Result<std::path::PathBuf, Error> {
        let given: Vec<Option<&[Answer]>> = answers.iter().enumerate().map(|(i, a)| (Some(i) != real).then_some(a.as_slice())).collect();
        let entry = dir.join(name);
        std::fs::create_dir_all(&entry)?;
        std::fs::write(entry.join(format!("{CLASS}.class")), replay_stub(cp, callees, &given)?)?;
        Ok(entry)
    };
    if !disagrees(&write("as-found", None)?) {
        return Ok(None);
    }
    let mut blamed = Vec::new();
    for i in 0..callees.len() {
        if !disagrees(&write(&format!("real-{i}"), Some(i))?) {
            blamed.push(i);
        }
    }
    Ok((!blamed.is_empty()).then_some(blamed))
}
