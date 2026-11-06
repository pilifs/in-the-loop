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
    /// Where JBMC runs the bytecode otherwise than the JVM, whatever is on its class path ([`Defect`]).
    pub defects: Vec<Defect>,
}

/// A place where JBMC 6.11.0 runs a method's bytecode otherwise than the JVM: not an approximation of a call it has
/// no bytecode for, which a statement could name as an assumption, but code it has and translates wrongly: a
/// counterexample that does not reproduce, or a proof of what the JVM does not do. The first two kinds let a runtime
/// exception past the handler that catches it on the JVM, so the exception escapes the method; the third computes
/// another value. Found from the bytecode of the functions the harness reaches
/// (`tests/fixtures/jbmc-defects/README.md` has the reproducers):
///
/// - `return-past-handler`: a `return` of a value whose computation may throw (an integer division or remainder,
///   an array element, a field, an array's length, a cast) inside a try block whose handler catches the exception.
///   javac ends the handler's range before the return instruction; JBMC keeps the value on its operand stack and
///   computes it, with the check that throws, at the return, after the range has ended.
/// - `stubbed-handler`: a handler of a JDK class JBMC has no class file of (`catch (RuntimeException e)`), and an
///   exception of a subclass of it raised in the program (`ArithmeticException` from a division, or an
///   `IllegalArgumentException` thrown): JBMC's stub of a class has no superclass, so it does not know the
///   exception's class extends the handler's.
/// - `unmasked-shift`: a right shift (`>>`, `>>>`, of an `int` or a `long`) by a distance not known to be within
///   the type's width. The JVM shifts by the distance's low five bits (six for a `long`); JBMC lowers `ishr`,
///   `iushr`, `lshr` and `lushr` to a shift by the whole distance, so one of 32 or more, or a negative one, fills
///   the value with its sign or with zeros (`x >> 33` is `x >> 1` on the JVM, `0` or `-1` in JBMC). It lowers the
///   left shifts with the mask.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct Defect {
    /// `return-past-handler`, `stubbed-handler` or `unmasked-shift`.
    pub kind: &'static str,
    /// Where: the instruction that throws, or the handler's method and line.
    pub site: String,
    /// What JBMC does there, against what the JVM does.
    pub what: String,
}

impl Defect {
    pub fn line(&self) -> String {
        format!("{} at {}: {}", self.kind, self.site, self.what)
    }
}

/// The runtime exceptions JBMC raises under `--throw-runtime-exceptions` at an instruction, as the JVM does, and
/// whether it computes the instruction's value where it consumes it rather than at the instruction (an expression
/// left on its operand stack, not a statement of its own).
fn raises(insn: &Insn) -> (&'static [&'static str], bool) {
    use crate::classfile::bytecode::{ArithOp, Kind};
    const ARITHMETIC: &[&str] = &["java/lang/ArithmeticException"];
    const ELEMENT: &[&str] = &["java/lang/ArrayIndexOutOfBoundsException", "java/lang/NullPointerException"];
    const NULL: &[&str] = &["java/lang/NullPointerException"];
    const CAST: &[&str] = &["java/lang/ClassCastException"];
    const SIZE: &[&str] = &["java/lang/NegativeArraySizeException"];
    match insn {
        Insn::Arith(ArithOp::Div | ArithOp::Rem, Kind::Int | Kind::Long) => (ARITHMETIC, true),
        Insn::ArrayLoad(_) => (ELEMENT, true),
        Insn::GetField(_) | Insn::ArrayLength => (NULL, true),
        Insn::CheckCast(_) => (CAST, true),
        Insn::ArrayStore(_) => (ELEMENT, false),
        Insn::PutField(_) | Insn::InvokeVirtual(_) | Insn::InvokeInterface(_) | Insn::AThrow => (NULL, false),
        Insn::NewArray(_) | Insn::ANewArray(_) | Insn::MultiANewArray(..) => (SIZE, false),
        _ => (&[], false),
    }
}

/// How JBMC's operand stack computes the value an instruction pushes, walked back from where the value is
/// consumed: `Some(n)`, the values it pops into that expression (a constant or a local is a leaf, `0`; a call or
/// an allocation is a statement of its own, whose value is a leaf too), or `None` for one the walk does not follow.
fn operands(class: &crate::classfile::ClassFile, insn: &Insn) -> Option<i32> {
    use crate::classfile::bytecode::ArithOp;
    match insn {
        Insn::Load(..) | Insn::AConstNull | Insn::IConst(_) | Insn::LConst(_) | Insn::FConst(_) | Insn::DConst(_) | Insn::Ldc(_) | Insn::GetStatic(_) => Some(0),
        Insn::New(_) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::MultiANewArray(..) => Some(0),
        Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => {
            let member = class.pool.member(*i).ok()?;
            (MethodDescriptor::parse(&member.descriptor).ok()?.ret != Type::Void).then_some(0)
        }
        Insn::Arith(ArithOp::Neg, _) | Insn::Convert(..) | Insn::CheckCast(_) | Insn::InstanceOf(_) | Insn::ArrayLength | Insn::GetField(_) => Some(1),
        Insn::Arith(..) | Insn::Cmp(_) | Insn::ArrayLoad(_) => Some(2),
        _ => None,
    }
}

/// The `return-past-handler` defects of a method: for each handler whose range ends at a `return` of a value, the
/// instructions in the range that compute that value and may throw what the handler catches on the JVM.
fn returns_past_handlers(cp: &ClassPath, owner: &str, name: &str, class: &crate::classfile::ClassFile, code: &crate::classfile::Code, insns: &[(u32, Insn)]) -> Vec<Defect> {
    let mut out = Vec::new();
    for handler in &code.exception_table {
        let Some(end) = insns.iter().position(|(pc, _)| *pc == handler.end_pc as u32) else { continue };
        if !matches!(insns[end].1, Insn::Return(Some(_))) {
            continue;
        }
        // Back from the return, the instructions whose values make up the one returned, within the range.
        let mut need = 1;
        for (pc, insn) in insns[..end].iter().rev() {
            if *pc < handler.start_pc as u32 || need == 0 {
                break;
            }
            let Some(popped) = operands(class, insn) else { break };
            let (exceptions, deferred) = raises(insn);
            if deferred {
                let caught: Vec<&&str> = exceptions.iter().filter(|e| handler.catch_type.as_deref().is_none_or(|t| cp.is_subtype(e, t))).collect();
                if let Some(exception) = caught.first() {
                    let what = match &handler.catch_type {
                        Some(t) => format!("catch ({})", t.replace('/', ".")),
                        None => "finally".to_string(),
                    };
                    out.push(Defect {
                        kind: "return-past-handler",
                        site: Site { class: owner.to_string(), method: name.to_string(), line: code.line_at(*pc) }.display(),
                        what: format!(
                            "returns a value that may throw {} inside a try block whose {what} catches it on the JVM; JBMC computes the value at the return, after it leaves the try block, so the exception escapes the method",
                            exception.replace('/', ".")
                        ),
                    });
                    break;
                }
            }
            need += popped - 1;
        }
    }
    out
}

/// The `unmasked-shift` defects of a method: each right shift whose distance is not a constant within the shifted
/// type's width, nor such a constant's bitwise and with another value (`s & 31`), the instructions computing it
/// reached by no branch. JBMC 6.11.0 shifts by the whole distance where the JVM masks it.
fn unmasked_shifts(owner: &str, name: &str, code: &crate::classfile::Code, insns: &[(u32, Insn)]) -> Vec<Defect> {
    use crate::classfile::bytecode::{ArithOp, Kind};
    let mut joins: BTreeSet<u32> = insns.iter().flat_map(|(_, insn)| insn.targets()).collect();
    joins.extend(code.exception_table.iter().map(|h| h.handler_pc as u32));
    let within = |insn: &Insn, width: i32| matches!(insn, Insn::IConst(c) if (0..width).contains(c));
    let mut out = Vec::new();
    for (i, (pc, insn)) in insns.iter().enumerate() {
        let (op, width) = match insn {
            Insn::Arith(op @ (ArithOp::Shr | ArithOp::Ushr), Kind::Int) => (op, 32),
            Insn::Arith(op @ (ArithOp::Shr | ArithOp::Ushr), Kind::Long) => (op, 64),
            _ => continue,
        };
        // The distance is the value pushed last: the instruction before, or a mask the two before it and it compute.
        let before = |k: usize| i.checked_sub(k).map(|j| &insns[j]).filter(|_| (0..k).all(|m| !joins.contains(&insns[i - m].0)));
        let constant = before(1).is_some_and(|(_, d)| within(d, width));
        let masked = before(1).is_some_and(|(_, d)| matches!(d, Insn::Arith(ArithOp::And, Kind::Int)))
            && (before(2).is_some_and(|(_, m)| within(m, width)) || (before(2).is_some_and(|(_, l)| matches!(l, Insn::Load(..))) && before(3).is_some_and(|(_, m)| within(m, width))));
        if constant || masked {
            continue;
        }
        let shift = if *op == ArithOp::Shr { ">>" } else { ">>>" };
        let bits = if width == 32 { "five" } else { "six" };
        let ty = if width == 32 { "an int" } else { "a long" };
        out.push(Defect {
            kind: "unmasked-shift",
            site: Site { class: owner.to_string(), method: name.to_string(), line: code.line_at(*pc) }.display(),
            what: format!(
                "shifts {ty} with {shift} by a distance that may be outside 0..{}: the JVM shifts by the distance's low {bits} bits, JBMC by the whole distance, so it fills the value with {} where the JVM does not",
                width - 1,
                if *op == ArithOp::Shr { "its sign" } else { "zeros" }
            ),
        });
    }
    out
}

/// Whether JBMC knows `class` extends `ancestor`: up the superclasses it has class files of, a stub's being unknown.
fn jbmc_extends(cp: &ClassPath, class: &str, ancestor: &str) -> bool {
    let mut current = class.to_string();
    for _ in 0..64 {
        if current == ancestor {
            return true;
        }
        match cp.application(&current).ok().flatten().and_then(|c| c.super_class.clone()) {
            Some(parent) => current = parent,
            None => return false,
        }
    }
    false
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
    // Where JBMC runs the bytecode it has otherwise than the JVM: the handlers each method reached has, and the
    // exceptions the program may raise, for the handlers of a class JBMC has a stub of.
    let mut handlers: Vec<(String, Site)> = Vec::new();
    let mut raised: BTreeSet<String> = BTreeSet::new();
    for id in reached.iter().filter(|(_, caller)| caller.is_some()).map(|(id, _)| id) {
        let Some((owner, name, descriptor)) = method_of(id) else { continue };
        let Some(class) = jbmc_cp.application(&owner).ok().flatten() else { continue };
        let Some(code) = class.method(&name, &descriptor).and_then(|m| m.code.as_ref()) else { continue };
        let insns = code.instructions().unwrap_or_default();
        found.defects.extend(returns_past_handlers(jbmc_cp, &owner, &name, &class, code, &insns));
        found.defects.extend(unmasked_shifts(&owner, &name, code, &insns));
        for (_, insn) in &insns {
            raised.extend(raises(insn).0.iter().map(|e| e.to_string()));
            if let Insn::New(i) = insn {
                raised.extend(class.pool.class_name(*i).ok().filter(|c| jbmc_cp.is_subtype(c, "java/lang/Throwable")).map(str::to_string));
            }
        }
        for h in &code.exception_table {
            if let Some(t) = &h.catch_type {
                handlers.push((t.clone(), Site { class: owner.clone(), method: name.clone(), line: code.line_at(h.handler_pc as u32) }));
            }
        }
    }
    for (t, site) in handlers {
        if jbmc_cp.application(&t).ok().flatten().is_some() {
            continue;
        }
        let missed: Vec<&String> = raised.iter().filter(|e| *e != &t && jbmc_cp.is_subtype(e, &t) && !jbmc_extends(jbmc_cp, e, &t)).collect();
        if missed.is_empty() {
            continue;
        }
        let names: Vec<String> = missed.iter().map(|e| e.replace('/', ".")).collect();
        found.defects.push(Defect {
            kind: "stubbed-handler",
            site: site.display(),
            what: format!(
                "catch ({}) catches {} on the JVM, which the program may raise, but JBMC has no class file of {} and its stub has no superclass, so JBMC does not know {} extend{} it: the exception escapes the handler",
                t.replace('/', "."),
                names.join(", "),
                t.replace('/', "."),
                if names.len() == 1 { "the exception's class" } else { "their classes" },
                if names.len() == 1 { "s" } else { "" }
            ),
        });
    }
    found.defects.sort();
    found.defects.dedup();
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
    crate::phases::timed(crate::phases::Step::Gaps, || preflight_untimed(run, budget))
}

fn preflight_untimed(run: &JbmcRun, budget: Duration) -> Result<Preflight, Error> {
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
            (Some(f), _) if f.records.is_empty() && f.defects.is_empty() => String::new(),
            (Some(f), _) => {
                let mut out = String::new();
                if !f.records.is_empty() {
                    let _ = writeln!(out, "note: JBMC reaches {} construct{} it approximates (its stubs and unlinked call sites, {}):", f.records.len(), if f.records.len() == 1 { "" } else { "s" }, self.log.display());
                    for r in &f.records {
                        let _ = writeln!(out, "  jbmc gap: {}", r.line());
                    }
                }
                if !f.defects.is_empty() {
                    let _ = writeln!(out, "note: JBMC runs {} construct{} otherwise than the JVM, whatever its class path:", f.defects.len(), if f.defects.len() == 1 { "" } else { "s" });
                    for d in &f.defects {
                        let _ = writeln!(out, "  jbmc defect: {}", d.line());
                    }
                }
                out
            }
            (None, Some(p)) => format!("note: JBMC's own approximations are not known: {p}\n"),
            (None, None) => String::new(),
        }
    }

    /// Why a JBMC counterexample may not reproduce in the interpreter, when JBMC runs a construct the path may go
    /// through otherwise than the JVM: `None` when it runs none.
    pub fn unreproduced_cause(&self) -> Option<String> {
        let defects = &self.found.as_ref()?.defects;
        if defects.is_empty() {
            return None;
        }
        Some(format!("The path to it probably goes through what JBMC runs otherwise than the JVM, whatever its class path: {}", defects.iter().map(Defect::line).collect::<Vec<_>>().join("; ")))
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
    if result.verdict != Verdict::Verified {
        return;
    }
    // A defect is no approximation a statement could assume: a proof through one is refused in every mode.
    if let Some(f) = pre.found.as_ref().filter(|f| !f.defects.is_empty()) {
        let n = f.defects.len();
        result.verdict = Verdict::Unverifiable;
        result.problem = Some(format!(
            "JBMC proved it, but runs {n} construct{} otherwise than the JVM ({}), so the proof is refused under every --gaps mode; --engine native or auto lets the tool's own checker try it",
            if n == 1 { "" } else { "s" },
            f.defects.iter().map(|d| format!("{} at {}", d.kind, d.site)).collect::<Vec<_>>().join(", ")
        ));
        return;
    }
    if mode == GapMode::Assume {
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

    /// `tests/fixtures/jbmc-defects/p/D.java`, compiled, on JBMC's class path with the JDK image: `None` without
    /// javac or a JDK.
    fn defect_fixture() -> Option<(tempfile::TempDir, ClassPath)> {
        let javac = std::process::Command::new("javac").arg("-version").output().is_ok_and(|o| o.status.success());
        let cp = ClassPath::new().with_models(false).with_default_jdk();
        if !javac || !cp.has_jdk() {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "javac or a JDK not found: put them on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            return None;
        }
        let out = tempfile::tempdir().unwrap();
        let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/jbmc-defects/p/D.java");
        let status = std::process::Command::new("javac").args(["-g", "-d"]).arg(out.path()).arg(&source).status().unwrap();
        assert!(status.success(), "the fixture compiles");
        let mut cp = cp;
        cp.add(out.path()).unwrap();
        Some((out, cp))
    }

    /// A goto program whose harness `H.<method>` calls `p.D.<method>` alone.
    fn calling(method: &str, descriptor: &str) -> Program {
        parse_goto(&format!(
            "H.{method}() /* java::H.{method}:()V */\n        // 1 file H.java line 1 function java::H.{method}:()V bytecode-index 1\n        CALL java::p.D.{method}:{descriptor}(x)\n        END_FUNCTION\n\n^^^^^^^^\n\np.D.{method}() /* java::p.D.{method}:{descriptor} */\n        END_FUNCTION\n\n^^^^^^^^\n"
        ))
    }

    /// The reproducers of `conformance/caught/1`, `nestedHandler/1` and `shiftRight/2`, whose JBMC counterexamples do
    /// not reproduce: JBMC 6.11.0 raises a runtime exception past the handler that catches it on the JVM, for a value
    /// returned from a try block, and for a handler of a JDK class it has a stub of, which it does not know the
    /// exception's class extends; and it right-shifts by the whole distance, unmasked. Each is named where the program
    /// reaches it; their neighbours, which JBMC runs as the JVM does, are not.
    #[test]
    fn the_preflight_names_where_jbmc_runs_the_bytecode_otherwise_than_the_jvm() {
        let Some((_dir, cp)) = defect_fixture() else { return };
        let defects = |method: &str, descriptor: &str| -> Vec<(String, String)> {
            let found = find(&calling(method, descriptor), "H", method, &cp, None).unwrap();
            found.defects.iter().map(|d| (d.kind.to_string(), d.site.clone())).collect()
        };
        assert_eq!(defects("returned", "(I)I"), [("return-past-handler".to_string(), "p.D.returned:7".to_string())]);
        assert_eq!(defects("field", "(Lp/D;)I"), [("return-past-handler".to_string(), "p.D.field:8".to_string())]);
        assert_eq!(defects("superCatch", "(I)I"), [("stubbed-handler".to_string(), "p.D.superCatch:12".to_string())]);
        assert_eq!(defects("thrown", "(I)I"), [("stubbed-handler".to_string(), "p.D.thrown:13".to_string())]);
        assert_eq!(defects("shifted", "(II)I"), [("unmasked-shift".to_string(), "p.D.shifted:15".to_string())]);
        assert_eq!(defects("shiftedUnsigned", "(JI)J"), [("unmasked-shift".to_string(), "p.D.shiftedUnsigned:16".to_string())]);
        assert_eq!(defects("literal", "(I)I"), [("unmasked-shift".to_string(), "p.D.literal:17".to_string())]);
        for (method, descriptor) in [("stored", "(I)I"), ("uncaught", "([II)I"), ("called", "(I)I"), ("exact", "(I)I"), ("masked", "(II)I"), ("halved", "(I)I"), ("left", "(II)I")] {
            assert_eq!(defects(method, descriptor), [], "{method}");
        }
        let found = find(&calling("returned", "(I)I"), "H", "returned", &cp, None).unwrap();
        let what = &found.defects[0].what;
        assert!(what.contains("java.lang.ArithmeticException") && what.contains("after it leaves the try block"), "{what}");
        let found = find(&calling("thrown", "(I)I"), "H", "thrown", &cp, None).unwrap();
        let what = &found.defects[0].what;
        assert!(what.contains("catch (java.lang.RuntimeException)") && what.contains("java.lang.IllegalArgumentException"), "{what}");
        let found = find(&calling("shiftedUnsigned", "(JI)J"), "H", "shiftedUnsigned", &cp, None).unwrap();
        let what = &found.defects[0].what;
        assert!(what.contains("a long with >>>") && what.contains("0..63") && what.contains("low six bits") && what.contains("zeros"), "{what}");
    }

    /// A JBMC proof that reaches a defect is refused under every gap mode, assume too: the defect is not an
    /// approximation a statement could name, but code JBMC runs otherwise than the JVM. A counterexample stands,
    /// for the interpreter's replay, and the replay's message names the defect as the likely cause.
    #[test]
    fn a_proof_through_a_defect_is_refused_under_every_mode_and_a_counterexample_is_left_to_the_replay() {
        let defect = Defect { kind: "return-past-handler", site: "p.D.returned:7".into(), what: "raises it after it leaves the try block".into() };
        let pre = Preflight { found: Some(Found { defects: vec![defect], ..Found::default() }), problem: None, log: PathBuf::from("jbmc-goto.txt"), seconds: 0.0 };
        let result = |verdict: Verdict| crate::jbmc::JbmcResult {
            verdict,
            version: "6.11.0".into(),
            properties: 2,
            raw_inputs: BTreeMap::new(),
            raw_arrays: BTreeMap::new(),
            stage: None,
            problem: None,
            log: PathBuf::new(),
            seconds: 0.0,
            native: None,
            gaps: Vec::new(),
            gap_mode: None,
            ending: crate::jbmc::Ending::Verified,
            profile: Default::default(),
        };
        for mode in [GapMode::Strict, GapMode::Assume, GapMode::Advised] {
            let mut proved = result(Verdict::Verified);
            hold(&mut proved, &pre, mode);
            assert_eq!(proved.verdict, Verdict::Unverifiable, "{mode:?}");
            let problem = proved.problem.unwrap();
            assert!(problem.contains("return-past-handler at p.D.returned:7") && problem.contains("every --gaps mode"), "{problem}");
            let mut refuted = result(Verdict::Violation);
            hold(&mut refuted, &pre, mode);
            assert_eq!((refuted.verdict, refuted.problem), (Verdict::Violation, None), "{mode:?}");
        }
        assert!(pre.note().contains("jbmc defect: return-past-handler at p.D.returned:7"), "{}", pre.note());
        assert!(pre.unreproduced_cause().is_some_and(|c| c.contains("return-past-handler at p.D.returned:7")));
        assert_eq!(Preflight { found: Some(Found::default()), ..pre }.unreproduced_cause(), None);
    }
}
