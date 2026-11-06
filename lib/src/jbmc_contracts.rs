//! JBMC applies the contracts for its gaps (`--engine jbmc --gaps advised`, the second part of step 4c of
//! `llm-dlc/loops/sound-verdicts.md`). The gaps are the ones JBMC's goto program names ([`crate::jbmc_gaps`]):
//! a JDK call JBMC has no bytecode for keeps the id the tool's own checker gives it, so a contract is written,
//! checked (proved, tested on a JVM, or trusted) and kept in the contract library once, whichever checker applies it.
//!
//! The protocol is the own checker's ([`crate::advice`]): a gap JBMC's preflight reaches with no contract stops the
//! run before anything is solved, with the advice and the template. What no contract closes under JBMC (a monitor it
//! drops, an `invokedynamic` it does not link, a method outside the JDK it has no bytecode for) is listed in the
//! advice as approximated whatever the contracts, and is refused as under strict.
//!
//! **How JBMC applies a contract.** The class of contract methods the own checker runs ([`crate::gap_contracts::CLASS`])
//! is the one JBMC runs too. Each call site of a closed gap, in the harness and the application's classes, is
//! rewritten into a call of the contract's method ([`crate::shared::redirect_calls`]), and the classes rewritten go
//! first on JBMC's class path. A constructor's call goes through a method of [`CALLS`] that takes the receiver (still
//! uninitialized, which JBMC does not mind) and drops it, as the own checker does. The intrinsics the contract
//! methods call ([`crate::gap_contracts::INTRINSICS`]) are a class here, over JBMC's own `org.cprover.CProver`:
//!
//! | Intrinsic | JBMC runs |
//! |---|---|
//! | `anyInt()`, `anyLong()` | `CProver.nondetInt()`, `nondetLong()`: any value, which the contract's method narrows and its assertion constrains |
//! | `havoc(array)` | every element `CProver.nondet...()`, a loop over the array's length, which the unwinding bound covers as it covers the harness's own copying loops |
//! | `infeasible()` | `CProver.assume(false)`: no run of the JDK's call takes the path |
//! | `open(n)` | an assertion that fails, a property of its own (`jvmcontract.GapIntrinsics.open`): an input outside the contract's `assume:` reaches the gap, which stays open there, and the run is no verdict |
//!
//! A call site is not rewritten when an application class overrides the JDK method it names, since the JVM would
//! dispatch to the override there, and a call made from the JDK's own bytecode is not rewritten either. Either leaves
//! the gap open, and JBMC's second preflight, on the rewritten class path, names it. An exception a contract throws
//! that the harness does not catch by name has its class and superclasses taken from the JDK image, so that JBMC,
//! which matches a handler by class, knows it is a `Throwable`.

use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use crate::bmc::gaps::{self, Closing, Gap, GapKind, GapMode, GapRecord, GapSetting, GapTreatment, Refusal};
use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::{flags, ClassFile, Cond, Insn, Kind, MemberRef, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::jbmc::{Ending, JbmcResult};
use crate::jbmc_gaps::{Found, Preflight};
use crate::shared::Invoke;
use crate::Error;

/// The generated class whose methods take a constructor's receiver and apply its contract.
pub const CALLS: &str = "GapContractCalls";

/// JBMC's intrinsics for nondeterminism and assumptions.
const CPROVER: &str = "org/cprover/CProver";

/// Whether a contract closes a gap of this kind under JBMC: a call into the JDK, as for the own checker.
pub fn contractable(kind: GapKind) -> bool {
    matches!(kind, GapKind::JdkConstructor | GapKind::JdkVoidMethod | GapKind::JdkReferenceMethod | GapKind::JdkPrimitiveMethod | GapKind::JdkStaticMethod)
}

/// Why no contract closes a gap of this kind under JBMC, as the advice lists it.
fn uncontractable(kind: GapKind) -> &'static str {
    match kind {
        GapKind::Monitor => "JBMC drops monitors (it models them only under --java-threading), and no contract applies to an instruction",
        GapKind::InvokeDynamic => "JBMC gives an invokedynamic it does not link the value zero or null, and no contract applies to one",
        GapKind::MissingBody => "JBMC stubs a method outside the JDK it has no bytecode for, and a contract is for a JDK call: put the method's class on the class path",
        _ => "no contract applies to it under JBMC",
    }
}

/// JBMC's gaps as a scan the advice protocol reads: the gaps a contract closes, and in `refused` what no contract
/// closes under JBMC, with the first call and site of each kind.
pub fn scan_of(found: &Found, jdk: Option<String>) -> gaps::Scan {
    let mut scan = gaps::Scan { jdk: jdk.clone(), ..gaps::Scan::default() };
    for (g, sites) in &found.gaps {
        if contractable(g.kind) {
            scan.gaps.insert(g.clone(), sites.clone());
            continue;
        }
        let id = g.id(jdk.as_deref());
        let call = found.records.iter().find(|r| r.id == id).map(|r| r.call.clone()).unwrap_or_else(|| g.call());
        let at = sites.iter().next().map(gaps::Site::display).unwrap_or_default();
        scan.refused.entry(uncontractable(g.kind).to_string()).or_insert(Refusal { first: call, at, sites: 0 }).sites += sites.len().max(1);
    }
    scan
}

/// What `--gaps advised` makes of JBMC's preflight before anything is solved.
pub struct Prepared {
    /// The gap setting with the contracts read and checked: what the own checker's probe runs with, and what
    /// [`apply`] applies.
    pub setting: GapSetting,
    /// The contracts as read, accepted and refused.
    pub loaded: Option<crate::gap_contracts::Loaded>,
    /// The advice, when a gap JBMC reaches has no contract: the run stops with it.
    pub advice: Option<crate::advice::Advice>,
    /// A note line for each contract refused, and for each of the library's this run checks again.
    pub notes: String,
}

/// Reads the contracts for the gaps JBMC's preflight `pre` reached, the agent's (`options.file`) first and then the
/// contract library's, each checked as the own checker's driver checks them ([`crate::gap_contracts::setting`]),
/// against the class path `entries` (with the tool's models when `models`); and the advice when a gap has none.
/// A preflight that could not be read gives no contracts and no advice: the proof is then refused as under strict
/// ([`crate::jbmc_gaps::hold`]).
pub fn prepare(pre: &Preflight, options: &crate::gap_contracts::ContractOptions, claim: crate::advice::Claim, entries: &[PathBuf], models: bool, work: &Path) -> Result<Prepared, Error> {
    let Some(found) = &pre.found else {
        return Ok(Prepared { setting: GapSetting::from(GapMode::Advised), loaded: None, advice: None, notes: String::new() });
    };
    let scan = scan_of(found, gaps::jdk_release());
    let (setting, loaded, notes) = crate::gap_contracts::setting(GapMode::Advised, options, Some(&scan), entries, models, work)?;
    let cp = crate::witness::classpath(entries.iter().map(PathBuf::as_path))?.with_models(models);
    let advice = crate::advice::preflight(&cp, &scan, claim, work, loaded.as_ref(), Some("jbmc"))?;
    Ok(Prepared { setting, loaded, advice, notes })
}

/// The contracts applied on a class path.
#[derive(Debug, Clone, Default)]
pub struct Applied {
    /// The class path JBMC runs on: the rewritten classes, the contracts' classes, then the class path as it was.
    pub classpath: Vec<PathBuf>,
    /// A record for each gap whose call sites were rewritten, with its contract, treated as `contract`.
    pub records: Vec<GapRecord>,
    /// How many classes were rewritten.
    pub classes: usize,
    /// A note line for each gap with a contract left open, and why.
    pub notes: String,
}

/// Applies the contracts of `setting` at the gaps of `found` on `classpath`: the call sites in the class path's
/// directories `rewrite` (in class path order, the first class of a name the one rewritten) are redirected to the
/// contracts' methods, into `dir/redirected`, and the classes JBMC needs to run them are written into
/// `dir/classes`. `cp` is the class path with the JDK, for the overrides and the exceptions.
pub fn apply(setting: &GapSetting, found: &Found, classpath: &[PathBuf], rewrite: &[PathBuf], cp: &ClassPath, dir: &Path) -> Result<Applied, Error> {
    let mut applied = Applied { classpath: classpath.to_vec(), ..Applied::default() };
    let Some(contracts_dir) = &setting.class_dir else { return Ok(applied) };
    let classes_dir = dir.join("classes");
    let redirected_dir = dir.join("redirected");
    for d in [&classes_dir, &redirected_dir] {
        if d.exists() {
            std::fs::remove_dir_all(d)?;
        }
        std::fs::create_dir_all(d)?;
    }
    let application = cp.application_classes()?;
    // Each gap reached that a contract closes, with the method its call sites go to.
    let mut targets: BTreeMap<Gap, MemberRef> = BTreeMap::new();
    let mut calls = ClassWriter::new(CALLS);
    calls.source_file = Some(format!("{CALLS}.java"));
    for (gap, closure) in setting.contracts.iter() {
        let Closing::Stub { method, descriptor, .. } = &closure.how else { continue };
        if !found.gaps.contains_key(gap) || !contractable(gap.kind) {
            continue;
        }
        if let Some(by) = overridden(&application, cp, gap) {
            applied.notes.push_str(&format!("note: the contract for {} is not applied by JBMC: {} overrides the method, and the JVM calls the override on its objects; the gap stays open\n", gap.id(gaps::jdk_release().as_deref()), by.replace('/', ".")));
            continue;
        }
        let target = if gap.kind == GapKind::JdkConstructor {
            let params = MethodDescriptor::parse(&gap.descriptor).map_err(|e| Error::new(e.to_string()))?.params;
            let name = format!("k{}", closure.contract.index);
            let wrapper = format!("(Ljava/lang/Object;{})V", params.iter().map(Type::descriptor).collect::<String>());
            let mut code = CodeBuilder::new();
            let mut slot = 1;
            for t in &params {
                code.load(kind(t), slot);
                slot += t.slots();
            }
            let m = calls.pool.method_ref(crate::gap_contracts::CLASS, method, descriptor);
            code.op_u16(0xb8, m);
            code.return_(None);
            code.max_locals = slot;
            code.max_stack = slot + 2;
            calls.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: name.clone(), descriptor: wrapper.clone(), code: Some(code) });
            MemberRef::new(CALLS, &name, &wrapper)
        } else {
            MemberRef::new(crate::gap_contracts::CLASS, method, descriptor)
        };
        targets.insert(gap.clone(), target);
    }
    if targets.is_empty() {
        return Ok(applied);
    }

    // The call sites, rewritten.
    let used: RefCell<BTreeSet<Gap>> = RefCell::new(BTreeSet::new());
    let lookup = |invoke: Invoke, m: &MemberRef| -> Option<MemberRef> {
        let (gap, target) = targets.iter().find(|(g, _)| g.owner == m.owner && g.name == m.name && g.descriptor == m.descriptor)?;
        let fits = match gap.kind {
            GapKind::JdkStaticMethod => invoke == Invoke::Static,
            GapKind::JdkConstructor => invoke == Invoke::Special,
            _ => invoke != Invoke::Static,
        };
        if !fits {
            return None;
        }
        used.borrow_mut().insert(gap.clone());
        Some(target.clone())
    };
    let mut seen: BTreeSet<PathBuf> = BTreeSet::new();
    for entry in rewrite.iter().filter(|e| e.is_dir()) {
        let mut dirs = vec![entry.clone()];
        while let Some(d) = dirs.pop() {
            for item in std::fs::read_dir(&d)? {
                let path = item?.path();
                if path.is_dir() {
                    dirs.push(path);
                    continue;
                }
                if path.extension().is_none_or(|e| e != "class") {
                    continue;
                }
                let relative = path.strip_prefix(entry).unwrap_or(&path).to_path_buf();
                // A class an earlier entry has is the one JBMC loads.
                if !seen.insert(relative.clone()) {
                    continue;
                }
                if let Some(patched) = crate::shared::redirect_calls(&std::fs::read(&path)?, &lookup)? {
                    let target = redirected_dir.join(&relative);
                    if let Some(parent) = target.parent() {
                        std::fs::create_dir_all(parent)?;
                    }
                    std::fs::write(target, patched)?;
                    applied.classes += 1;
                }
            }
        }
    }
    let used = used.into_inner();
    if used.is_empty() {
        return Ok(applied);
    }

    // The classes the contracts' methods need under JBMC.
    let intrinsics = classes_dir.join(format!("{}.class", crate::gap_contracts::INTRINSICS));
    std::fs::create_dir_all(intrinsics.parent().expect("a package"))?;
    std::fs::write(intrinsics, intrinsics_class())?;
    if !calls.methods.is_empty() {
        std::fs::write(classes_dir.join(format!("{CALLS}.class")), calls.to_bytes())?;
    }
    let contracts_class = std::fs::read(contracts_dir.join(format!("{}.class", crate::gap_contracts::CLASS)))?;
    let thrown = thrown_classes(&ClassFile::parse(&contracts_class)?, cp);
    crate::property::extract_exceptions(&classes_dir, cp, &thrown)?;

    let jdk = gaps::jdk_release();
    for gap in &used {
        let closure = setting.contracts.get(gap).expect("a closed gap");
        let id = gap.id(jdk.as_deref());
        let sites = found.gaps.get(gap).map(|s| s.iter().map(gaps::Site::display).collect()).unwrap_or_default();
        let mut record = found.records.iter().find(|r| r.id == id).cloned().unwrap_or_else(|| GapRecord { id: id.clone(), kind: gap.kind, call: gap.call(), sites, approximation: gap.kind.approximation().to_string(), jbmc: false, treatment: None, contract: None, checker: Some("jbmc".into()) });
        record.treatment = Some(GapTreatment::Contract);
        record.contract = Some(closure.contract.clone());
        applied.records.push(record);
    }
    let mut front = vec![redirected_dir, classes_dir, contracts_dir.clone()];
    front.extend(classpath.iter().cloned());
    applied.classpath = front;
    Ok(applied)
}

/// After the run on the class path [`apply`] gave: the contracts' records join the result's gaps, and a failure of
/// `open` (an input outside a contract's `assume:`) is said in words.
pub fn settle(result: &mut JbmcResult, applied: &Applied) {
    result.gaps.extend(applied.records.iter().cloned());
    let open = format!("{}.open", crate::gap_contracts::INTRINSICS.replace('/', "."));
    if result.ending == Ending::OtherFailure && result.problem.as_deref().is_some_and(|p| p.contains(&open)) {
        let ids: Vec<&str> = applied.records.iter().map(|r| r.id.as_str()).collect();
        let which = if ids.len() == 1 { format!("the contract for {}", ids[0]) } else { format!("one of the contracts for {}", ids.join(", ")) };
        result.problem = Some(format!("an input outside the `assume:` of {which} reaches its gap, which stays open there (--gaps advised): a contract that covers the input closes it"));
    }
}

/// The application class that overrides the JDK method a gap is about, if any: a call site naming the JDK's
/// method may then run the override, which the contract is not about.
fn overridden(application: &BTreeMap<String, std::rc::Rc<ClassFile>>, cp: &ClassPath, gap: &Gap) -> Option<String> {
    if matches!(gap.kind, GapKind::JdkConstructor | GapKind::JdkStaticMethod) {
        return None;
    }
    application.iter().find(|(name, class)| class.method(&gap.name, &gap.descriptor).is_some_and(|m| m.code.is_some()) && cp.is_subtype(name, &gap.owner)).map(|(name, _)| name.clone())
}

/// The JDK exception classes a contract's method throws (the classes it makes with `new` that are throwables),
/// beyond the ones the harness catches by name.
fn thrown_classes(class: &ClassFile, cp: &ClassPath) -> Vec<String> {
    let mut out = BTreeSet::new();
    for m in &class.methods {
        let Some(code) = &m.code else { continue };
        let Ok(insns) = code.instructions() else { continue };
        for (_, insn) in insns {
            if let Insn::New(i) = insn {
                if let Ok(name) = class.pool.class_name(i) {
                    if crate::classpath::is_jdk_name(name) && cp.is_subtype(name, "java/lang/Throwable") {
                        out.insert(name.to_string());
                    }
                }
            }
        }
    }
    out.into_iter().collect()
}

fn kind(t: &Type) -> Kind {
    match t {
        Type::Long => Kind::Long,
        Type::Float => Kind::Float,
        Type::Double => Kind::Double,
        Type::Object(_) | Type::Array(_) => Kind::Ref,
        _ => Kind::Int,
    }
}

/// The intrinsics' class as JBMC runs it, over `org.cprover.CProver`.
pub fn intrinsics_class() -> Vec<u8> {
    let mut w = ClassWriter::new(crate::gap_contracts::INTRINSICS);
    w.source_file = Some("GapIntrinsics.java".into());
    let method = |w: &mut ClassWriter, name: &str, descriptor: &str, code: CodeBuilder| w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: name.into(), descriptor: descriptor.into(), code: Some(code) });

    // open(int): the gap is met, a property of its own that fails.
    let mut code = CodeBuilder::new();
    let error = w.pool.class("java/lang/AssertionError");
    let init = w.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
    code.op_u16(0xbb, error); // new
    code.op(0x59); // dup
    code.op_u16(0xb7, init);
    code.op(0xbf); // athrow
    code.max_locals = 1;
    code.max_stack = 2;
    method(&mut w, "open", "(I)V", code);

    for (name, nondet, descriptor, kind) in [("anyInt", "nondetInt", "()I", Kind::Int), ("anyLong", "nondetLong", "()J", Kind::Long)] {
        let mut code = CodeBuilder::new();
        let m = w.pool.method_ref(CPROVER, nondet, descriptor);
        code.op_u16(0xb8, m);
        code.return_(Some(kind));
        code.max_locals = 0;
        code.max_stack = 2;
        method(&mut w, name, descriptor, code);
    }

    let mut code = CodeBuilder::new();
    let assume = w.pool.method_ref(CPROVER, "assume", "(Z)V");
    code.iconst(0);
    code.op_u16(0xb8, assume);
    code.return_(None);
    code.max_locals = 0;
    code.max_stack = 1;
    method(&mut w, "infeasible", "()V", code);

    // havoc(array): each element any value of its type.
    let mut code = CodeBuilder::new();
    for (array, nondet, descriptor, store) in [("[I", "nondetInt", "()I", 0x4f), ("[J", "nondetLong", "()J", 0x50), ("[B", "nondetByte", "()B", 0x54), ("[Z", "nondetBoolean", "()Z", 0x54), ("[C", "nondetChar", "()C", 0x55), ("[S", "nondetShort", "()S", 0x56)] {
        let next = code.label();
        let class = w.pool.class(array);
        let fresh = w.pool.method_ref(CPROVER, nondet, descriptor);
        code.load(Kind::Ref, 0);
        code.op_u16(0xc1, class); // instanceof
        code.if_zero(Cond::Eq, next);
        code.load(Kind::Ref, 0);
        code.op_u16(0xc0, class); // checkcast
        code.store(Kind::Ref, 1);
        code.iconst(0);
        code.store(Kind::Int, 2);
        let top = code.label();
        let done = code.label();
        code.bind(top);
        code.load(Kind::Int, 2);
        code.load(Kind::Ref, 1);
        code.op(0xbe); // arraylength
        code.if_icmp(Cond::Ge, done);
        code.load(Kind::Ref, 1);
        code.load(Kind::Int, 2);
        code.op_u16(0xb8, fresh);
        code.op(store);
        code.iinc(2, 1);
        code.goto(top);
        code.bind(done);
        code.return_(None);
        code.bind(next);
    }
    code.return_(None);
    code.max_locals = 3;
    code.max_stack = 4;
    method(&mut w, "havoc", "(Ljava/lang/Object;)V", code);
    w.to_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_intrinsics_class_declares_what_the_contract_methods_call() {
        let class = ClassFile::parse(&intrinsics_class()).unwrap();
        assert_eq!(class.name, crate::gap_contracts::INTRINSICS);
        for (name, descriptor) in [("open", "(I)V"), ("anyInt", "()I"), ("anyLong", "()J"), ("infeasible", "()V"), ("havoc", "(Ljava/lang/Object;)V")] {
            let m = class.method(name, descriptor).unwrap_or_else(|| panic!("{name}{descriptor}"));
            assert!(m.code.as_ref().unwrap().instructions().is_ok(), "{name}");
        }
    }

    #[test]
    fn a_call_site_of_each_kind_is_rewritten_in_place() {
        // A class calling a static method, a constructor, a virtual and an interface method, written here.
        let mut w = ClassWriter::new("a/Calls");
        let mut code = CodeBuilder::new();
        let s = w.pool.method_ref("java/lang/Integer", "bitCount", "(I)I");
        let list = w.pool.class("java/util/ArrayList");
        let init = w.pool.method_ref("java/util/ArrayList", "<init>", "(I)V");
        let size = w.pool.method_ref("java/util/ArrayList", "size", "()I");
        let add = w.pool.interface_method_ref("java/util/List", "add", "(Ljava/lang/Object;)Z");
        code.iconst(3);
        code.op_u16(0xb8, s);
        code.op(0x57); // pop
        code.op_u16(0xbb, list);
        code.op(0x59);
        code.iconst(4);
        code.op_u16(0xb7, init);
        code.store(Kind::Ref, 0);
        code.load(Kind::Ref, 0);
        code.op_u16(0xb6, size);
        code.op(0x57);
        code.load(Kind::Ref, 0);
        code.op(0x01);
        code.op_u16(0xb9, add);
        code.op(2); // the count: the receiver and one argument
        code.op(0);
        code.op(0x57);
        code.return_(None);
        code.max_locals = 1;
        code.max_stack = 4;
        w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "f".into(), descriptor: "()V".into(), code: Some(code) });
        let bytes = w.to_bytes();
        let before = ClassFile::parse(&bytes).unwrap();
        let length = before.method("f", "()V").unwrap().code.as_ref().unwrap().bytes.len();
        let lookup = |invoke: Invoke, m: &MemberRef| -> Option<MemberRef> {
            match (invoke, m.name.as_str()) {
                (Invoke::Special, "<init>") => Some(MemberRef::new(CALLS, "k0", "(Ljava/lang/Object;I)V")),
                (Invoke::Virtual, "size") => Some(MemberRef::new("GapContracts", "c1", "(Ljava/lang/Object;)I")),
                (Invoke::Interface, "add") => Some(MemberRef::new("GapContracts", "c2", "(Ljava/lang/Object;Ljava/lang/Object;)Z")),
                _ => None,
            }
        };
        let patched = crate::shared::redirect_calls(&bytes, &lookup).unwrap().expect("rewritten");
        let after = ClassFile::parse(&patched).unwrap();
        let code = after.method("f", "()V").unwrap().code.as_ref().unwrap();
        assert_eq!(code.bytes.len(), length, "no offset moves");
        let calls: Vec<String> = code.instructions().unwrap().into_iter().filter_map(|(_, i)| match i {
            Insn::InvokeStatic(i) => after.pool.member(i).ok().map(|m| format!("static {}.{}{}", m.owner, m.name, m.descriptor)),
            Insn::InvokeSpecial(_) | Insn::InvokeVirtual(_) | Insn::InvokeInterface(_) => Some("left".into()),
            _ => None,
        }).collect();
        assert_eq!(calls, vec!["static java/lang/Integer.bitCount(I)I", "static GapContractCalls.k0(Ljava/lang/Object;I)V", "static GapContracts.c1(Ljava/lang/Object;)I", "static GapContracts.c2(Ljava/lang/Object;Ljava/lang/Object;)Z"]);
        let nops = code.instructions().unwrap().into_iter().filter(|(_, i)| matches!(i, Insn::Nop)).count();
        assert_eq!(nops, 2, "the invokeinterface's two extra bytes");
    }
}
