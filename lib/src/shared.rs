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
//! when it does not reproduce, the proof is run again with the callees as written.
//!
//! The same comparison of the two versions' bytecode settles a prior question: when the target and everything it
//! reaches is identical in both versions, there is nothing to prove ([`Plan::identical`]).

use std::collections::{BTreeMap, BTreeSet, HashSet, VecDeque};
use std::path::Path;
use std::rc::Rc;

use serde::Serialize;

use crate::classfile::writer::{ClassWriter, CodeBuilder, FieldWriter, MethodWriter};
use crate::classfile::{encode_modified_utf8, flags, ArithOp, BootstrapArg, ClassFile, Cond, ConstantPool, Insn, Kind, MemberRef, Method, Type};
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
}

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
        if !closure.methods.iter().all(|m| !after.is_application(&m.owner) || same_method(before, after, m)) {
            continue;
        }
        if !closure.throws.iter().all(|t| constructor(after, t).is_some()) {
            continue;
        }
        inside.extend(closure.methods);
        candidates.push(Callee { owner: callee.owner.clone(), name: callee.name.clone(), descriptor: callee.descriptor.clone(), throws: closure.throws.into_iter().collect() });
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
    /// Application classes whose static fields the methods read or write.
    statics: BTreeSet<String>,
    /// Whether every call could be followed: false when a virtual call may reach an implementation not listed.
    closed: bool,
}

fn reach(cp: &ClassPath, root: &MemberRef) -> Reach {
    let mut out = Reach { methods: Vec::new(), classes: BTreeMap::new(), static_calls: BTreeSet::new(), callers: BTreeMap::new(), statics: BTreeSet::new(), closed: true };
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
                    }
                    work.push_back(callee);
                }
                Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => {
                    let Ok(callee) = class.pool.member(i) else { continue };
                    if !cp.is_application(&callee.owner) {
                        continue; // the JDK is the same in both versions
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
/// say and not by how their pools are numbered. `None` when the code cannot be decoded.
fn shape(class: &ClassFile, method: &Method) -> Option<Vec<String>> {
    let code = method.code.as_ref()?;
    let insns = code.instructions().ok()?;
    let pool = &class.pool;
    let mut out = Vec::with_capacity(insns.len() + code.exception_table.len());
    for (_, insn) in &insns {
        out.push(match insn {
            Insn::Ldc(i) => format!("ldc {:?}", pool.loadable(*i).ok()?),
            Insn::GetStatic(i) | Insn::PutStatic(i) | Insn::GetField(i) | Insn::PutField(i) | Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => {
                format!("{} {:?}", opname(insn), pool.member(*i).ok()?)
            }
            Insn::New(i) | Insn::ANewArray(i) | Insn::CheckCast(i) | Insn::InstanceOf(i) => format!("{} {}", opname(insn), pool.class_name(*i).ok()?),
            Insn::MultiANewArray(i, dims) => format!("multianewarray {} {dims}", pool.class_name(*i).ok()?),
            Insn::InvokeDynamic(i) => {
                let (b, name, descriptor) = pool.invoke_dynamic(*i).ok()?;
                let bootstraps = class.bootstrap_methods().ok()?;
                format!("invokedynamic {name}{descriptor} {:?}", bootstraps.get(b as usize)?)
            }
            other => format!("{other:?}"),
        });
    }
    for handler in &code.exception_table {
        out.push(format!("{handler:?}"));
    }
    Some(out)
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
}

/// The closure of `root` when every method in it is a static method over primitives that touches no field, no
/// array and nothing of the JDK beyond its arithmetic, the building of an exception message, and the exception
/// itself; `None` otherwise. The exceptions it can throw are the ones it constructs and the arithmetic ones.
fn pure_closure(cp: &ClassPath, root: &MemberRef) -> Option<Closure> {
    let mut out = Closure { methods: Vec::new(), throws: BTreeSet::new() };
    let mut seen: HashSet<MemberRef> = HashSet::new();
    let mut work: VecDeque<MemberRef> = VecDeque::from([root.clone()]);
    while let Some(reference) = work.pop_front() {
        if !seen.insert(reference.clone()) {
            continue;
        }
        let (class, method) = cp.find_method(&reference.owner, &reference.name, &reference.descriptor)?;
        let declared = MemberRef::new(&class.name, &reference.name, &reference.descriptor);
        let callees = local_facts(cp, &class, &method, reference == *root, &mut out.throws)?;
        out.methods.push(declared);
        work.extend(callees);
    }
    Some(out)
}

/// Checks one method of a pure closure and returns the static callees it has; adds what it can throw.
fn local_facts(cp: &ClassPath, class: &ClassFile, method: &Method, root: bool, throws: &mut BTreeSet<String>) -> Option<Vec<MemberRef>> {
    if !method.is_static() || method.is_native() {
        return None;
    }
    let code = method.code.as_ref()?;
    let descriptor = method.parsed_descriptor().ok()?;
    if !descriptor.params.iter().all(Type::is_primitive) || !(descriptor.ret.is_primitive() || (!root && descriptor.ret == Type::Void)) || (root && descriptor.ret == Type::Void) {
        return None;
    }
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
    let class = ClassFile::parse(bytes)?;
    let (pool_end, mut count) = pool_extent(bytes)?;
    let code_offsets = code_offsets(bytes, &class.pool, pool_end)?;
    let mut added: Vec<u8> = Vec::new();
    let mut stub_class: Option<u16> = None;
    let mut refs: BTreeMap<String, u16> = BTreeMap::new();
    let mut patches: Vec<(usize, u16)> = Vec::new();
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
        for (pc, insn) in code.instructions()? {
            let Insn::InvokeStatic(i) = insn else { continue };
            let Ok(callee) = class.pool.member(i) else { continue };
            let Some(stub_method) = lookup(&callee) else { continue };
            let index = match refs.get(&stub_method) {
                Some(index) => *index,
                None => {
                    let class_index = match stub_class {
                        Some(c) => c,
                        None => {
                            let name = push_utf8(&mut added, &mut count, CLASS);
                            added.push(7);
                            added.extend(name.to_be_bytes());
                            count += 1;
                            stub_class = Some(count - 1);
                            count - 1
                        }
                    };
                    let name = push_utf8(&mut added, &mut count, &stub_method);
                    let descriptor = push_utf8(&mut added, &mut count, &callee.descriptor);
                    added.push(12);
                    added.extend(name.to_be_bytes());
                    added.extend(descriptor.to_be_bytes());
                    count += 1;
                    let nat = count - 1;
                    added.push(10);
                    added.extend(class_index.to_be_bytes());
                    added.extend(nat.to_be_bytes());
                    count += 1;
                    refs.insert(stub_method, count - 1);
                    count - 1
                }
            };
            patches.push((offset + pc as usize + 1, index));
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
    for (at, index) in patches {
        out[at + shift..at + shift + 2].copy_from_slice(&index.to_be_bytes());
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
    let mut written = 0;
    let mut dirs = vec![input.to_path_buf()];
    while let Some(dir) = dirs.pop() {
        for entry in std::fs::read_dir(&dir)? {
            let path = entry?.path();
            if path.is_dir() {
                dirs.push(path);
            } else if path.extension().is_some_and(|e| e == "class") {
                let bytes = std::fs::read(&path)?;
                if let Some(patched) = redirect(&bytes, lookup)? {
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
            Callee { owner: "a/Shares".into(), name: "perSeat".into(), descriptor: "(JI)J".into(), throws: vec!["java/lang/ArithmeticException".into(), "java/lang/IllegalArgumentException".into()] },
            Callee { owner: "java/lang/Math".into(), name: "abs".into(), descriptor: "(D)D".into(), throws: Vec::new() },
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
