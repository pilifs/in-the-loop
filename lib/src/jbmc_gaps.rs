//! JBMC's own approximations, named as gaps (step 4c of `llm-dlc/loops/sound-verdicts.md`).
//!
//! JBMC 6.11 gives a method it has no bytecode for a body of its own, a *stub*: a `void` method does nothing, a
//! constructor constructs the object and nothing else, and any other method returns any value of its type (for an
//! object, `null` or a new object). None of them throws, or changes its receiver or arguments. And an
//! `invokedynamic` it cannot link to a class of its own making gets the value zero (`null`, `false`): a string
//! concatenation (`StringConcatFactory`), a record's `equals`, `hashCode` and `toString` (`ObjectMethods`), and a
//! lambda for an interface JBMC has no class file of (as `java.util.function.Function`). And it drops `monitorenter`
//! and `monitorexit` (it models monitors only under `--java-threading`), so `synchronized (null)` throws nothing. A
//! void stub can drop the exception or the change a claim is about, so a proof can be `Verified` for a claim the JVM
//! refutes.
//!
//! The preflight runs JBMC with `--show-goto-functions` on the harness, with the class path and options of the
//! proof: it loads and converts what the proof would, and solves nothing. Its goto program is JBMC's own account of
//! what it runs, so the call graph is JBMC's, virtual dispatch included. From the harness's entry, a function
//! reached with no bytecode on JBMC's class path is a stub, an `invokedynamic` of a function reached whose
//! instructions JBMC made no `lambda_synthetic_class$` for is the zero fallback, and a function reached that
//! synchronizes is a `monitor` gap. Two kinds of stub are not gaps:
//!
//! - calls JBMC's stub reproduces exactly, as the own checker's [`gaps::exact_jdk_call`] says, and a JDK
//!   constructor whose bytecode only calls such a constructor of its superclass (`Number.<init>()`);
//! - stubs reached only from a JDK class's initializer (`Class.getPrimitiveClass` from `Integer.<clinit>`), which
//!   the statement names under the engine assumption that JDK classes are initialized, as the own checker's is.
//!
//! The gaps have the own checker's ids where the call is the same (`jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-...`),
//! so a gap reads the same whichever checker meets it. Under `--gaps strict` a JBMC proof that reaches a gap is no
//! verdict, and a violation stands only when the interpreter replays it (a stub's value may be one the JDK never
//! gives). Under `--gaps assume` the verdict stands, naming each stub as an assumption. JBMC applies no contract
//! (`--gaps advised`): a contract is the own checker's to apply, so under `--engine auto` the own checker runs first.
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::time::Duration;

use serde::Serialize;

use crate::bmc::gaps::{self, Gap, GapKind, GapMode, GapRecord, GapTreatment, Site};
use crate::classfile::bytecode::Insn;
use crate::classfile::{MethodDescriptor, Type};
use crate::classpath::{is_jdk_name, ClassPath};
use crate::jbmc::{JbmcResult, JbmcRun};
use crate::{Error, Verdict};

/// The longest a preflight may take, within the check's deadline: it converts what the proof would, no more.
pub const PREFLIGHT_SECONDS: u64 = 60;

/// One function of JBMC's goto program.
#[derive(Debug, Default, Clone)]
pub struct Function {
    /// The functions it calls, by id, with the source line of the first call to each.
    pub calls: BTreeMap<String, Option<u16>>,
    /// Its instructions' text by the bytecode index they come from.
    pub at: BTreeMap<u32, String>,
}

/// JBMC's goto program as `--show-goto-functions` prints it: each function under its id (`java::pkg.C.m:(I)V`).
#[derive(Debug, Default, Clone)]
pub struct Program {
    pub functions: BTreeMap<String, Function>,
}

/// Reads the text `--show-goto-functions` prints. A function starts at a line `<pretty name> /* <id> */` and ends
/// at a line of `^`; within it, a comment `// N file F line L function G bytecode-index K` says where the next
/// instructions come from.
pub fn parse_goto(text: &str) -> Program {
    let mut raw: Vec<(String, Vec<(String, Option<u16>)>, BTreeMap<u32, String>)> = Vec::new();
    let mut current: Option<(String, Vec<(String, Option<u16>)>, BTreeMap<u32, String>)> = None;
    let (mut bci, mut line): (Option<u32>, Option<u16>) = (None, None);
    for l in text.lines() {
        if l.starts_with('^') {
            raw.extend(current.take());
            continue;
        }
        if !l.starts_with(char::is_whitespace) && l.ends_with(" */") {
            if let Some(start) = l.rfind(" /* ") {
                raw.extend(current.take());
                current = Some((l[start + 4..l.len() - 3].to_string(), Vec::new(), BTreeMap::new()));
                (bci, line) = (None, None);
                continue;
            }
        }
        let Some((_, calls, at)) = current.as_mut() else { continue };
        let t = l.trim_start();
        if let Some(comment) = t.strip_prefix("// ") {
            bci = after_word(comment, "bytecode-index").and_then(|v| v.parse().ok());
            line = after_word(comment, "line").and_then(|v| v.parse().ok());
            continue;
        }
        // An instruction, after its label if it has one: `3: CALL ...`.
        let insn = t.split_once(": ").filter(|(label, _)| !label.is_empty() && label.bytes().all(|b| b.is_ascii_digit())).map(|(_, rest)| rest).unwrap_or(t);
        if let Some(callee) = insn.strip_prefix("CALL ") {
            // `CALL lhs := f(args)` in some versions, `CALL f(args)` in 6.11.
            let callee = callee.split_once(" := ").map(|(_, f)| f).unwrap_or(callee);
            calls.push((callee.to_string(), line));
        }
        if let Some(k) = bci {
            let entry = at.entry(k).or_default();
            entry.push_str(insn);
            entry.push('\n');
        }
    }
    raw.extend(current.take());
    let ids: BTreeSet<String> = raw.iter().map(|(id, _, _)| id.clone()).collect();
    let mut program = Program::default();
    for (id, calls, at) in raw {
        let mut f = Function { calls: BTreeMap::new(), at };
        for (text, line) in calls {
            // The callee is the longest function id the call's text starts with, followed by its arguments.
            let callee = ids.iter().filter(|c| text.starts_with(c.as_str()) && text[c.len()..].starts_with('(')).max_by_key(|c| c.len());
            if let Some(c) = callee {
                f.calls.entry(c.clone()).or_insert(line);
            }
        }
        program.functions.insert(id, f);
    }
    program
}

/// The value after `word ` in a goto comment: `line 5` gives `5`.
fn after_word<'a>(comment: &'a str, word: &str) -> Option<&'a str> {
    let mut parts = comment.split_whitespace();
    while let Some(p) = parts.next() {
        if p == word {
            return parts.next();
        }
    }
    None
}

/// A function id of a Java method: its class (internal name), name and descriptor. `None` for JBMC's own
/// functions (`__CPROVER_*`, `java::array[int].clone:()`, a `<clinit_wrapper>`, a synthetic lambda class's).
pub fn method_of(id: &str) -> Option<(String, String, String)> {
    let rest = id.strip_prefix("java::")?;
    if rest.starts_with("array[") || rest.starts_with("lambda_synthetic_class$") || rest.starts_with("org.cprover.") {
        return None;
    }
    let (qualified, descriptor) = rest.split_once(':')?;
    let (owner, name) = qualified.rsplit_once('.')?;
    if !descriptor.starts_with('(') {
        return None;
    }
    Some((owner.replace('.', "/"), name.to_string(), descriptor.to_string()))
}

/// Whether a function is a JDK class's initializer, or JBMC's wrapper around it.
fn jdk_initializer(id: &str) -> bool {
    let Some(rest) = id.strip_prefix("java::") else { return false };
    let qualified = rest.split(':').next().unwrap_or(rest);
    let Some((owner, name)) = qualified.rsplit_once('.') else { return false };
    (name == "<clinit>" || name == "<clinit_wrapper>") && is_jdk_name(&owner.replace('.', "/"))
}

/// What the preflight found: the gaps the harness reaches, each with its sites, and the stubs only a JDK class's
/// initializer reaches.
#[derive(Debug, Clone, Default, Serialize)]
pub struct Found {
    #[serde(skip)]
    pub gaps: BTreeMap<Gap, BTreeSet<Site>>,
    /// Each gap as a record, with JBMC's approximation of it.
    pub records: Vec<GapRecord>,
    /// The stubs JBMC gives the JDK methods that only a JDK class's initializer calls, as calls.
    pub initializer_stubs: Vec<String>,
    /// The functions of JBMC's program the harness reaches.
    pub functions: usize,
    /// The stubs JBMC reproduces exactly, as calls, with how many functions call each.
    pub exact: BTreeMap<String, usize>,
}

/// The gaps of JBMC's `program` from the function `java::<class>.<method>:...`, with JBMC's class path `jbmc_cp`
/// (its entries, and the JDK image to tell what a JDK member is).
pub fn find(program: &Program, class: &str, method: &str, jbmc_cp: &ClassPath, jdk: Option<&str>) -> Result<Found, Error> {
    let prefix = format!("java::{}.{method}:", class.replace('/', "."));
    let roots: Vec<&String> = program.functions.keys().filter(|id| id.starts_with(&prefix)).collect();
    if roots.is_empty() {
        return Err(Error::new(format!("JBMC's goto program has no function {prefix}...: the preflight could not read it")));
    }
    // From the entry, the functions reached and by whom first; a JDK class's initializer is walked apart.
    let walk = |starts: &[&String], skip: &BTreeSet<String>, stop_at_jdk_init: bool| -> BTreeMap<String, Option<(String, Option<u16>)>> {
        let mut seen: BTreeMap<String, Option<(String, Option<u16>)>> = BTreeMap::new();
        let mut queue: VecDeque<String> = VecDeque::new();
        for s in starts {
            seen.insert((*s).clone(), None);
            queue.push_back((*s).clone());
        }
        while let Some(id) = queue.pop_front() {
            if stop_at_jdk_init && jdk_initializer(&id) {
                continue;
            }
            let Some(f) = program.functions.get(&id) else { continue };
            for (callee, line) in &f.calls {
                if skip.contains(callee) || seen.contains_key(callee) {
                    continue;
                }
                seen.insert(callee.clone(), Some((id.clone(), *line)));
                queue.push_back(callee.clone());
            }
        }
        seen
    };
    let reached = walk(&roots, &BTreeSet::new(), true);
    let initializers: Vec<&String> = reached.keys().filter(|id| jdk_initializer(id)).collect();
    let skip: BTreeSet<String> = reached.keys().cloned().collect();
    let only_initializers = walk(&initializers, &skip, false);

    let mut found = Found { functions: reached.len(), ..Found::default() };
    for (id, caller) in &reached {
        // The harness is the tool's own, its bytecode generated with the proof.
        let Some((owner, name, descriptor)) = method_of(id).filter(|_| caller.is_some()) else { continue };
        let site = |caller: &Option<(String, Option<u16>)>| -> Site {
            match caller.as_ref().and_then(|(c, line)| method_of(c).map(|(o, n, _)| (o, n, *line))) {
                Some((o, n, line)) => Site { class: o, method: n, line },
                None => Site { class: class.to_string(), method: method.to_string(), line: None },
            }
        };
        match body(jbmc_cp, &owner, &name, &descriptor) {
            Body::Bytecode(sites) => {
                // Its call sites JBMC linked to no class of its own: the zero fallback.
                let f = &program.functions[id];
                for (bci, gap, always) in sites {
                    let linked = !always && f.at.get(&bci).is_some_and(|text| text.contains("lambda_synthetic_class$"));
                    if !linked {
                        let line = jbmc_cp.application(&owner).ok().flatten().and_then(|c| c.method(&name, &descriptor).and_then(|m| m.code.as_ref()).and_then(|code| code.line_at(bci)));
                        found.gaps.entry(gap).or_default().insert(Site { class: owner.clone(), method: name.clone(), line });
                    }
                }
            }
            Body::Exact => *found.exact.entry(gaps_call(&owner, &name, &descriptor)).or_default() += 1,
            Body::Stub(kind) => {
                found.gaps.entry(Gap { kind, owner, name, descriptor }).or_default().insert(site(caller));
            }
        }
    }
    for id in only_initializers.keys() {
        let Some((owner, name, descriptor)) = method_of(id).filter(|(_, n, _)| n != "<clinit>") else { continue };
        if let Body::Stub(_) = body(jbmc_cp, &owner, &name, &descriptor) {
            found.initializer_stubs.push(gaps_call(&owner, &name, &descriptor));
        }
    }
    found.records = found
        .gaps
        .iter()
        .map(|(g, sites)| GapRecord {
            id: g.id(jdk),
            kind: g.kind,
            call: call(g),
            sites: sites.iter().map(Site::display).collect(),
            approximation: approximation(jbmc_cp, g),
            jbmc: false,
            treatment: None,
            contract: None,
            checker: Some("jbmc".into()),
        })
        .collect();
    Ok(found)
}

/// A gap's call as a reader writes it: for an unlinked call site, what it is and what would link it,
/// `the invokedynamic equals(fixtures.Gaps$Point, java.lang.Object) of java.lang.runtime.ObjectMethods.bootstrap`.
fn call(g: &Gap) -> String {
    if g.kind == GapKind::Monitor {
        return format!("a synchronized block or method in {}", g.call());
    }
    if g.kind != GapKind::InvokeDynamic {
        return g.call();
    }
    let (site, descriptor) = g.descriptor.split_at(g.descriptor.find('(').unwrap_or(g.descriptor.len()));
    let params = MethodDescriptor::parse(descriptor).map(|d| d.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
    format!("the invokedynamic {site}({params}) of {}.{}", g.owner.replace('/', "."), g.name)
}

fn gaps_call(owner: &str, name: &str, descriptor: &str) -> String {
    Gap { kind: GapKind::MissingBody, owner: owner.into(), name: name.into(), descriptor: descriptor.into() }.call()
}

/// What JBMC runs for a method.
enum Body {
    /// Its bytecode, with its sites JBMC may approximate, each as the gap it would be: an `invokedynamic`, a gap
    /// unless JBMC linked it (`false`), and a monitor, always one (`true`).
    Bytecode(Vec<(u32, Gap, bool)>),
    /// JBMC's stub, which reproduces the call exactly.
    Exact,
    /// JBMC's stub, a gap of this kind.
    Stub(GapKind),
}

fn body(cp: &ClassPath, owner: &str, name: &str, descriptor: &str) -> Body {
    if let Ok(Some(class)) = cp.application(owner) {
        if let Some(code) = class.method(name, descriptor).and_then(|m| m.code.as_ref()) {
            let mut sites = Vec::new();
            for (pc, insn) in code.instructions().unwrap_or_default() {
                // JBMC drops a monitor instruction (it models monitors only under --java-threading), so a null one
                // throws nothing: one gap per method that synchronizes, met at its first monitorenter.
                if insn == Insn::MonitorEnter {
                    if !sites.iter().any(|(_, g, _): &(u32, Gap, bool)| g.kind == GapKind::Monitor) {
                        sites.push((pc, Gap { kind: GapKind::Monitor, owner: owner.into(), name: name.into(), descriptor: descriptor.into() }, true));
                    }
                    continue;
                }
                let Insn::InvokeDynamic(i) = insn else { continue };
                let Ok((index, site_name, site_descriptor)) = class.pool.invoke_dynamic(i) else { continue };
                let bootstraps = class.bootstrap_methods().unwrap_or_default();
                let (bsm_owner, bsm_name) = bootstraps.get(index as usize).map(|b| (b.method.member.owner.clone(), b.method.member.name.clone())).unwrap_or_else(|| ("java/lang/invoke/CallSite".into(), site_name.to_string()));
                sites.push((pc, Gap { kind: GapKind::InvokeDynamic, owner: bsm_owner, name: bsm_name, descriptor: format!("{site_name}{site_descriptor}") }, false));
            }
            return Body::Bytecode(sites);
        }
    }
    if is_jdk_name(owner) {
        if gaps::exact_jdk_call(cp, owner, name, descriptor) || trivial_constructor(cp, owner, name, descriptor, 0) {
            return Body::Exact;
        }
        if name == "<init>" {
            return Body::Stub(GapKind::JdkConstructor);
        }
        let is_static = cp.load(owner).ok().flatten().and_then(|l| l.class.method(name, descriptor).map(|m| m.is_static())).unwrap_or(false);
        if is_static {
            return Body::Stub(GapKind::JdkStaticMethod);
        }
        return Body::Stub(match MethodDescriptor::parse(descriptor).map(|d| d.ret) {
            Ok(Type::Void) => GapKind::JdkVoidMethod,
            Ok(Type::Object(_) | Type::Array(_)) => GapKind::JdkReferenceMethod,
            _ => GapKind::JdkPrimitiveMethod,
        });
    }
    Body::Stub(GapKind::MissingBody)
}

/// A JDK constructor of no arguments whose bytecode only calls its superclass's, itself exact or trivial:
/// `Number.<init>()`, which JBMC's stub (it constructs the object, and nothing else) reproduces.
fn trivial_constructor(cp: &ClassPath, owner: &str, name: &str, descriptor: &str, depth: u32) -> bool {
    if name != "<init>" || descriptor != "()V" || depth > 8 {
        return false;
    }
    let Some(loaded) = cp.load(owner).ok().flatten() else { return false };
    let Some(code) = loaded.class.method(name, descriptor).and_then(|m| m.code.as_ref()) else { return false };
    let insns: Vec<Insn> = code.instructions().unwrap_or_default().into_iter().map(|(_, i)| i).collect();
    let [Insn::Load(_, 0), Insn::InvokeSpecial(i), Insn::Return(None)] = insns.as_slice() else { return false };
    let Ok(m) = loaded.class.pool.member(*i) else { return false };
    m.name == "<init>" && m.descriptor == "()V" && Some(m.owner.as_str()) == loaded.class.super_class.as_deref() && (gaps::exact_jdk_call(cp, &m.owner, &m.name, &m.descriptor) || trivial_constructor(cp, &m.owner, &m.name, &m.descriptor, depth + 1))
}

/// What JBMC does at a gap: the assumption a verdict under `--gaps assume` states.
fn approximation(cp: &ClassPath, g: &Gap) -> String {
    let ret = MethodDescriptor::parse(&g.descriptor).map(|d| d.ret).unwrap_or(Type::Void);
    let value = match ret {
        Type::Void => "does nothing".to_string(),
        Type::Object(_) | Type::Array(_) => "returns null or a new object of its type, with any contents".to_string(),
        Type::Boolean => "returns either boolean".to_string(),
        ref t => format!("returns any {}", t.java_name()),
    };
    let effects = "it throws nothing and changes neither its receiver nor its arguments";
    match g.kind {
        GapKind::Monitor => "synchronizes, and JBMC drops its monitor instructions: a null monitor throws nothing, where the JVM throws NullPointerException".to_string(),
        GapKind::InvokeDynamic => {
            let zero = match MethodDescriptor::parse(g.descriptor.get(g.descriptor.find('(').unwrap_or(0)..).unwrap_or("")).map(|d| d.ret) {
                Ok(Type::Object(_) | Type::Array(_)) => "null",
                Ok(Type::Boolean) => "false",
                _ => "zero",
            };
            format!("is a call site JBMC does not link: it takes the value {zero} and runs nothing, neither the bootstrap method nor what it would link")
        }
        GapKind::JdkConstructor => format!("is JBMC's stub: it constructs the object and does nothing else: {effects}"),
        GapKind::MissingBody => {
            let why = match cp.application(&g.owner).ok().flatten() {
                Some(c) if c.method(&g.name, &g.descriptor).is_some_and(|m| m.is_abstract()) => "is abstract and no class on JBMC's class path implements it for this call",
                Some(c) if c.method(&g.name, &g.descriptor).is_some_and(|m| m.is_native()) => "is native",
                Some(_) => "is not declared by its class on JBMC's class path",
                None => "has no class file on JBMC's class path",
            };
            if g.name == "<init>" {
                format!("{why}, so JBMC's stub constructs the object and does nothing else: {effects}")
            } else {
                format!("{why}, so JBMC's stub {value}: {effects}")
            }
        }
        _ => format!("is JBMC's stub: it {value}: {effects}"),
    }
}

/// The command of the preflight: the proof's, listing the goto program in place of checking it.
pub fn command(run: &JbmcRun) -> Vec<String> {
    let entries: Vec<PathBuf> = run.classpath.iter().map(|p| crate::jbmc::absolute(p)).collect();
    let classpath = std::env::join_paths(&entries).map(|p| p.to_string_lossy().into_owned()).unwrap_or_default();
    let mut cmd = vec![run.executable.clone(), run.class.clone(), "--function".into(), format!("{}.{}", run.class, run.function), "--classpath".into(), classpath, "--throw-runtime-exceptions".into()];
    if !run.refine_strings {
        cmd.push("--no-refine-strings".into());
    }
    cmd.extend(run.extra_args.iter().cloned());
    cmd.push("--show-goto-functions".into());
    cmd
}

/// What the preflight of a JBMC proof found, or why it could not tell.
#[derive(Debug, Clone)]
pub struct Preflight {
    pub found: Option<Found>,
    /// Why the program could not be listed or read.
    pub problem: Option<String>,
    pub log: PathBuf,
    pub seconds: f64,
}

/// Runs the preflight for `run` (its log next to the run's), within `budget`.
pub fn preflight(run: &JbmcRun, budget: Duration) -> Result<Preflight, Error> {
    let log = run.log.with_file_name("jbmc-goto.txt");
    let started = std::time::Instant::now();
    if !crate::jbmc::available(&run.executable) {
        return Ok(Preflight { found: None, problem: Some(format!("jbmc is not installed ({} not found)", run.executable)), log, seconds: 0.0 });
    }
    let cwd = run.log.parent().filter(|p| !p.as_os_str().is_empty()).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let output = crate::tla::run_with_timeout(&crate::jbmc::limited(command(run), crate::jbmc::memory_limit_mb()), &cwd, budget.min(Duration::from_secs(PREFLIGHT_SECONDS)))?;
    std::fs::write(&log, &output)?;
    let seconds = started.elapsed().as_secs_f64();
    if output.contains("did not finish within") {
        return Ok(Preflight { found: None, problem: Some(format!("listing JBMC's program did not finish within {} s", crate::deadline::seconds(budget.min(Duration::from_secs(PREFLIGHT_SECONDS))))), log, seconds });
    }
    let mut cp = ClassPath::new().with_models(false).with_default_jdk();
    for entry in &run.classpath {
        if entry.exists() {
            cp.add(entry)?;
        }
    }
    let program = parse_goto(&output);
    match find(&program, &run.class, &run.function, &cp, gaps::jdk_release().as_deref()) {
        Ok(found) => Ok(Preflight { found: Some(found), problem: None, log, seconds }),
        Err(e) => Ok(Preflight { found: None, problem: Some(e.to_string()), log, seconds }),
    }
}

impl Preflight {
    /// The gaps it found, as records treated as `mode` treats them on JBMC: refused under strict and advised (JBMC
    /// applies no contract), assumed under assume.
    pub fn records(&self, mode: GapMode) -> Vec<GapRecord> {
        let treatment = if mode == GapMode::Assume { GapTreatment::Assumed } else { GapTreatment::Refused };
        self.found.iter().flat_map(|f| f.records.iter().cloned()).map(|mut r| {
            r.treatment = Some(treatment);
            r
        }).collect()
    }

    /// The note a report prints for it.
    pub fn note(&self) -> String {
        match (&self.found, &self.problem) {
            (Some(f), _) if f.records.is_empty() => String::new(),
            (Some(f), _) => {
                let mut out = String::new();
                let _ = writeln!(out, "note: JBMC reaches {} construct{} it approximates (its stubs and unlinked call sites, {}):", f.records.len(), if f.records.len() == 1 { "" } else { "s" }, self.log.display());
                for r in &f.records {
                    let _ = writeln!(out, "  jbmc gap: {}", r.line());
                }
                out
            }
            (None, Some(p)) => format!("note: JBMC's own approximations are not known: {p}\n"),
            (None, None) => String::new(),
        }
    }
}

/// A JBMC result held to the gaps its preflight found, under `mode`. Under assume the verdict stands, with each
/// gap named as assumed. Under strict (and advised, as JBMC applies no contract), a proof that reaches a gap is
/// no verdict, and so is one whose gaps are not known; a counterexample stands, for the interpreter's replay to
/// confirm, since a stub's value may be one the JDK never gives.
pub fn hold(result: &mut JbmcResult, pre: &Preflight, mode: GapMode) {
    result.gap_mode = Some(mode);
    let records = pre.records(mode);
    let ids: Vec<String> = records.iter().map(|r| r.id.clone()).collect();
    result.gaps.extend(records);
    if mode == GapMode::Assume || result.verdict != Verdict::Verified {
        return;
    }
    if let Some(p) = &pre.problem {
        result.verdict = Verdict::Unverifiable;
        result.problem = Some(format!("JBMC proved it, but what it approximated is not known ({p}), so the proof is refused (--gaps {}); --gaps assume accepts it", mode.name()));
    } else if !ids.is_empty() {
        let n = ids.len();
        result.verdict = Verdict::Unverifiable;
        result.problem = Some(format!(
            "JBMC proved it, but reaches {n} construct{} it approximates without implementing, and refused {} (--gaps {}): {}; --gaps assume accepts the proof under {}, and --engine native or auto lets the tool's own checker try it",
            if n == 1 { "" } else { "s" },
            if n == 1 { "it" } else { "them" },
            mode.name(),
            ids.join(", "),
            if n == 1 { "it" } else { "them" }
        ));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const GOTO: &str = r#"JBMC version 6.11.0 (cbmc-6.11.0) 64-bit arm64 linux
Generating GOTO Program

__CPROVER__start /* __CPROVER__start */
        CALL java::H.check:(I)V(__CPROVER__start::arg0i)

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

H.check(int) /* java::H.check:(I)V */
        // 1 file H.java line 3 function java::H.check:(I)V bytecode-index 1
     1: CALL java::p.K.m:(I)I(java::H.check:(I)V::arg0i)
        // 2 file H.java line 4 function java::H.check:(I)V bytecode-index 5
        CALL java::java.lang.Integer.<clinit_wrapper>()
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

p.K.m(int) /* java::p.K.m:(I)I */
        // 3 file K.java line 7 function java::p.K.m:(I)I bytecode-index 2
        CALL java::java.util.ArrayList.<init>:(I)V(new_tmp0, arg0i)
        // 4 file K.java line 8 function java::p.K.m:(I)I bytecode-index 9
        ASSIGN java::p.K.m:(I)I::lambda_new_tmp0 := { { "java::lambda_synthetic_class$p_K_m_(I)I$0" } }
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java::java.lang.Integer.<clinit_wrapper> /* java::java.lang.Integer.<clinit_wrapper> */
        CALL java::java.lang.Integer.<clinit>:()V()

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java.lang.Integer.<clinit>() /* java::java.lang.Integer.<clinit>:()V */
        CALL java::java.lang.Class.getPrimitiveClass:(Ljava/lang/String;)Ljava/lang/Class;(address_of(x))

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java.lang.Class.getPrimitiveClass() /* java::java.lang.Class.getPrimitiveClass:(Ljava/lang/String;)Ljava/lang/Class; */
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java.util.ArrayList.<init>() /* java::java.util.ArrayList.<init>:(I)V */
        END_FUNCTION
"#;

    #[test]
    fn reads_jbmc_goto_program_as_functions_calls_and_bytecode_indices() {
        let p = parse_goto(GOTO);
        assert_eq!(p.functions.len(), 7, "{:?}", p.functions.keys());
        let check = &p.functions["java::H.check:(I)V"];
        assert_eq!(check.calls.keys().collect::<Vec<_>>(), ["java::java.lang.Integer.<clinit_wrapper>", "java::p.K.m:(I)I"]);
        assert_eq!(check.calls["java::p.K.m:(I)I"], Some(3));
        let m = &p.functions["java::p.K.m:(I)I"];
        assert!(m.at[&9].contains("lambda_synthetic_class$"), "{:?}", m.at);
        assert!(m.at[&2].starts_with("CALL java::java.util.ArrayList"), "{:?}", m.at);
        assert_eq!(method_of("java::java.util.ArrayList.<init>:(I)V"), Some(("java/util/ArrayList".into(), "<init>".into(), "(I)V".into())));
        assert_eq!(method_of("java::java.lang.Integer.<clinit_wrapper>"), None);
        assert_eq!(method_of("java::array[int].clone:()Ljava/lang/Object;"), None);
        assert_eq!(method_of("java::lambda_synthetic_class$S_lam_(I)I$0.ap:(I)I"), None);
        assert!(jdk_initializer("java::java.lang.Integer.<clinit_wrapper>") && jdk_initializer("java::java.lang.Integer.<clinit>:()V") && !jdk_initializer("java::p.K.<clinit>:()V"));
    }

    #[test]
    fn a_stub_the_harness_reaches_is_a_gap_and_one_only_a_jdk_initializer_reaches_is_not() {
        let p = parse_goto(GOTO);
        // No class file of p.K: a stub too, of an application class (the harness H is the tool's own); the JDK image
        // tells the rest.
        let cp = ClassPath::new().with_models(false).with_default_jdk();
        if !cp.has_jdk() {
            return;
        }
        let found = find(&p, "H", "check", &cp, Some("25")).unwrap();
        let ids: Vec<&str> = found.records.iter().map(|r| r.id.as_str()).collect();
        assert_eq!(ids, ["jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25", "missing-body:p.K.m(I)I"], "{found:?}");
        assert_eq!(found.initializer_stubs, ["java.lang.Class.getPrimitiveClass(java.lang.String)"]);
        let list = found.records.iter().find(|r| r.kind == GapKind::JdkConstructor).unwrap();
        assert_eq!(list.sites, ["p.K.m:7"]);
        assert!(list.approximation.starts_with("is JBMC's stub: it constructs the object and does nothing else"), "{}", list.approximation);
        assert_eq!(list.checker.as_deref(), Some("jbmc"));
        assert!(find(&p, "H", "other", &cp, None).is_err());
    }
}
