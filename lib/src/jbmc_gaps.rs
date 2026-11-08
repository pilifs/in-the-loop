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
//! synchronizes is a `monitor` gap. The call graph takes every branch, so a stub it reaches may be on no path: when
//! it reaches one, the preflight runs JBMC's symbolic execution of the proof too ([`symbolic_command`]), which follows
//! the paths the bounds allow, and a stub it never enters is no gap ([`entered`]). Symbolic execution drops a branch
//! only when it simplifies the condition to false, so it still enters a stub behind a condition only a solver decides
//! (one an `--assume` makes false). For those, the preflight runs the proof once more, with a probe before each call
//! site of each ([`probe`]): a method of its own that, on a branch of its own, fails an assertion, and otherwise makes
//! the call, so no path is cut. A stub whose every probe holds, in a run whose unwinding assertions all hold, is on no
//! path within the bounds and assumptions, and is no gap either; a run that cannot tell (out of time, no verdict, a
//! call site no probe can be placed at) leaves the stubs gaps. Two more kinds of stub are not gaps:
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
    /// Its instructions' text by the bytecode index they come from: JBMC numbers a method's instructions in order
    /// from 0, so the index is an instruction's place in the method, not its offset (`pc`) in the code.
    pub at: BTreeMap<u32, String>,
    /// Its instructions' location numbers, unique in the program, each with the text of its comment after the number
    /// (`file F line L function G bytecode-index K`, or `no location`): how JBMC's symbolic execution names its steps.
    pub locations: BTreeMap<u32, String>,
    /// The functions it calls at an instruction the listing gives no bytecode index, where no probe can be placed
    /// ([`probe`]).
    pub unplaced: BTreeSet<String>,
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
    type Calls = Vec<(String, Option<u16>, bool)>;
    let mut raw: Vec<(String, Calls, Function)> = Vec::new();
    let mut current: Option<(String, Calls, Function)> = None;
    let (mut bci, mut line): (Option<u32>, Option<u16>) = (None, None);
    for l in text.lines() {
        if l.starts_with('^') {
            raw.extend(current.take());
            continue;
        }
        if !l.starts_with(char::is_whitespace) && l.ends_with(" */") {
            if let Some(start) = l.rfind(" /* ") {
                raw.extend(current.take());
                current = Some((l[start + 4..l.len() - 3].to_string(), Vec::new(), Function::default()));
                (bci, line) = (None, None);
                continue;
            }
        }
        let Some((_, calls, function)) = current.as_mut() else { continue };
        let t = l.trim_start();
        if let Some(comment) = t.strip_prefix("// ") {
            // `// Labels: pc0` names the labels of the instruction that follows, which keeps its location.
            if comment.starts_with("Labels:") {
                continue;
            }
            let (number, rest) = comment.split_once(' ').unwrap_or((comment, ""));
            if let Ok(n) = number.parse::<u32>() {
                function.locations.insert(n, rest.trim().to_string());
            }
            bci = after_word(comment, "bytecode-index").and_then(|v| v.parse().ok());
            line = after_word(comment, "line").and_then(|v| v.parse().ok());
            continue;
        }
        // An instruction, after its label if it has one: `3: CALL ...`.
        let insn = t.split_once(": ").filter(|(label, _)| !label.is_empty() && label.bytes().all(|b| b.is_ascii_digit())).map(|(_, rest)| rest).unwrap_or(t);
        if let Some(callee) = insn.strip_prefix("CALL ") {
            // `CALL lhs := f(args)` in some versions, `CALL f(args)` in 6.11.
            let callee = callee.split_once(" := ").map(|(_, f)| f).unwrap_or(callee);
            calls.push((callee.to_string(), line, bci.is_some()));
        }
        if let Some(k) = bci {
            let entry = function.at.entry(k).or_default();
            entry.push_str(insn);
            entry.push('\n');
        }
    }
    raw.extend(current.take());
    let ids: BTreeSet<String> = raw.iter().map(|(id, _, _)| id.clone()).collect();
    let mut program = Program::default();
    for (id, calls, mut f) in raw {
        for (text, line, placed) in calls {
            if let Some(c) = callee(&ids, &text) {
                f.calls.entry(c.clone()).or_insert(line);
                if !placed {
                    f.unplaced.insert(c.clone());
                }
            }
        }
        program.functions.insert(id, f);
    }
    program
}

/// The callee of a call's text (`f(args)`): the longest function id it starts with, followed by its arguments.
fn callee<'a>(ids: &'a BTreeSet<String>, text: &str) -> Option<&'a String> {
    ids.iter().filter(|c| text.starts_with(c.as_str()) && text[c.len()..].starts_with('(')).max_by_key(|c| c.len())
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

/// The functions of `program` that JBMC's symbolic execution enters, from what `--program-only` prints: the formula
/// a proof solves, a step to a line, each after a comment `// N ...` that names the location it comes from by the
/// number the goto listing gives it. Symbolic execution follows the paths the bounds allow and leaves out a branch
/// whose condition it simplifies to false, so a function none of its steps comes from is on no path the proof
/// checks. An `Err` says why the output cannot be read so: it is not a finished symbolic execution, or its
/// locations are not the listing's (a location the listing lacks, or one whose comment differs).
pub fn entered(program: &Program, ssa: impl std::io::BufRead) -> Result<BTreeSet<String>, String> {
    let mut located: BTreeMap<u32, (&str, &str)> = BTreeMap::new();
    for (id, f) in &program.functions {
        for (n, text) in &f.locations {
            located.insert(*n, (id.as_str(), text.as_str()));
        }
    }
    let (mut constraints, mut steps) = (false, 0usize);
    let mut entered = BTreeSet::new();
    for line in ssa.lines() {
        let line = line.map_err(|e| format!("its output cannot be read: {e}"))?;
        if line == "Program constraints:" {
            constraints = true;
            continue;
        }
        let Some(comment) = line.strip_prefix("// ").filter(|_| constraints) else { continue };
        let (number, rest) = comment.split_once(' ').unwrap_or((comment, ""));
        let Ok(n) = number.parse::<u32>() else { continue };
        let Some((id, text)) = located.get(&n) else { return Err(format!("its step at location {n} is at none of the listing's")) };
        // The listing says `no location` where symbolic execution prints nothing.
        let rest = rest.trim();
        if rest != *text && !(rest.is_empty() && *text == "no location") {
            return Err(format!("its location {n} is `{rest}`, the listing's `{text}`"));
        }
        steps += 1;
        entered.insert(id.to_string());
    }
    if !constraints {
        return Err("it printed no formula (no `Program constraints:`)".into());
    }
    if steps == 0 {
        return Err("its formula names no location".into());
    }
    Ok(entered)
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
    /// The stubs the call graph reaches but no path within the proof's bounds and assumptions enters, as calls, so
    /// not gaps: those JBMC's symbolic execution of the proof never enters ([`entered`]), and those of
    /// [`Found::solved`].
    pub unreached: Vec<String>,
    /// Of [`Found::unreached`], the stubs JBMC's symbolic execution enters but its solver shows no path reaches, as
    /// calls: a probe at each of their call sites held ([`probe`]).
    pub solved: Vec<String>,
}

/// A place where JBMC 6.11.0 runs a method's bytecode otherwise than the JVM: not an approximation of a call it has
/// no bytecode for, which a statement could name as an assumption, but code it has and translates wrongly: a
/// counterexample that does not reproduce, or a proof of what the JVM does not do. The first two kinds let a runtime
/// exception past the handler that catches it on the JVM, so the exception escapes the method; the third computes
/// another value; the fourth runs an initializer the JVM does not; the fifth gives an initializer's exception to its
/// caller unwrapped. Found from the bytecode of the functions the harness reaches
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
/// - `extra-initializer`: a `new`, `getstatic`, `putstatic` or `invokestatic` at which JBMC runs the `<clinit>` of
///   an application class the JVM does not initialize there (JVMS §5.5): JBMC initializes the class the instruction
///   names, where the JVM initializes the class that declares the field or method (`Sub.value` declared by
///   `Holder` initializes `Holder` alone), and with a class it initializes every superinterface, where the JVM
///   initializes only those that declare a default method.
/// - `throwing-initializer`: the `<clinit>` of an application class that may throw an exception other than an
///   `Error`, where a handler tells JBMC's from the JVM's: the JVM gives the caller an
///   `ExceptionInInitializerError`, and later uses of the class a `NoClassDefFoundError` (JVMS §5.5), where JBMC
///   gives the exception as it is and runs later uses as if the class were initialized ([`throwing_initializers`]).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct Defect {
    /// `return-past-handler`, `stubbed-handler`, `unmasked-shift`, `extra-initializer` or `throwing-initializer`.
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

/// The application classes whose `<clinit>` JBMC runs from the initializer wrapper `wrapper`
/// (`java::p.C.<clinit_wrapper>`), as its goto program says: the wrapper calls the class's own `<clinit>`, if it has
/// one, after the wrappers of its superclass and of every superinterface.
fn jbmc_initializes(program: &Program, cp: &ClassPath, wrapper: &str, out: &mut BTreeSet<String>, seen: &mut BTreeSet<String>) {
    if !seen.insert(wrapper.to_string()) {
        return;
    }
    let Some(f) = program.functions.get(wrapper) else { return };
    for callee in f.calls.keys() {
        if callee.ends_with(".<clinit_wrapper>") {
            jbmc_initializes(program, cp, callee, out, seen);
        } else if let Some((owner, _, _)) = method_of(callee).filter(|(_, n, d)| n == "<clinit>" && d == "()V") {
            if !is_jdk_name(&owner) && cp.is_application(&owner) {
                out.insert(owner);
            }
        }
    }
}

/// The `extra-initializer` defects of a method: each `new`, `getstatic`, `putstatic` or `invokestatic` at which
/// JBMC's goto program runs the initializer of an application class the JVM does not initialize there (JVMS §5.5).
/// The JVM initializes the class that declares the resolved field or method, which may be a superclass or a
/// superinterface of the one the instruction names, and with a class its superclasses and those of its
/// superinterfaces that declare a default method. JBMC 6.11.0 initializes the class the instruction names, and with
/// it every superinterface.
fn extra_initializers(program: &Program, function: &Function, cp: &ClassPath, owner: &str, name: &str, class: &crate::classfile::ClassFile, code: &crate::classfile::Code, insns: &[(u32, Insn)]) -> Vec<Defect> {
    let mut out = Vec::new();
    for (index, (pc, insn)) in insns.iter().enumerate() {
        let (op, named, member, declaring) = match insn {
            Insn::New(i) => {
                let Ok(c) = class.pool.class_name(*i) else { continue };
                ("new", c.to_string(), None, c.to_string())
            }
            Insn::GetStatic(i) | Insn::PutStatic(i) | Insn::InvokeStatic(i) => {
                let Ok(m) = class.pool.member(*i) else { continue };
                let declaring = match insn {
                    Insn::InvokeStatic(_) => cp.bytecode_method(&m.owner, &m.name, &m.descriptor).map(|(cf, _)| cf.name.clone()),
                    _ => cp.resolve_field(&m.owner, &m.name, &m.descriptor),
                };
                let op = match insn {
                    Insn::GetStatic(_) => "getstatic",
                    Insn::PutStatic(_) => "putstatic",
                    _ => "invokestatic",
                };
                let declaring = declaring.unwrap_or_else(|| m.owner.clone());
                (op, m.owner.clone(), Some(m.name.clone()), declaring)
            }
            _ => continue,
        };
        if is_jdk_name(&named) {
            continue;
        }
        // What JBMC initializes there: the wrappers it calls at the instruction, listed under its index.
        let mut jbmc = BTreeSet::new();
        let mut seen = BTreeSet::new();
        for text in function.at.get(&(index as u32)).map(|t| t.lines()).into_iter().flatten() {
            let Some(callee) = text.strip_prefix("CALL ") else { continue };
            let callee = callee.split_once(" := ").map(|(_, f)| f).unwrap_or(callee);
            if let Some(wrapper) = callee.strip_suffix("()").filter(|w| w.ends_with(".<clinit_wrapper>")) {
                jbmc_initializes(program, cp, wrapper, &mut jbmc, &mut seen);
            }
        }
        let jvm: BTreeSet<String> = gaps::initializers(cp, &declaring).into_iter().collect();
        let extra: Vec<String> = jbmc.difference(&jvm).map(|c| c.replace('/', ".")).collect();
        if extra.is_empty() {
            continue;
        }
        let what = match &member {
            Some(m) if declaring != named => format!(
                "{op} {}.{m} resolves to a member {} declares, and the JVM initializes the declaring class, where JBMC initializes the class the instruction names",
                named.replace('/', "."),
                declaring.replace('/', ".")
            ),
            _ => format!(
                "{op} initializes {}: the JVM initializes with a class its superclasses and only those of its superinterfaces that declare a default method, where JBMC initializes every superinterface",
                named.replace('/', ".")
            ),
        };
        out.push(Defect {
            kind: "extra-initializer",
            site: Site { class: owner.to_string(), method: name.to_string(), line: code.line_at(*pc) }.display(),
            what: format!(
                "{what} (JVMS §5.5), so JBMC runs the initializer of {} where the JVM does not: what it sets, or throws, is not what the JVM does",
                extra.join(", ")
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

/// The runtime exceptions a method's instructions may raise under `--throw-runtime-exceptions` ([`raises`]), less
/// those that straight-line code shows cannot be raised. Without that, every enum's initializer and constructor
/// would count, though neither throws:
/// - an array made with a constant length, and stored to or read at a constant index within it before any branch,
///   as javac compiles an enum's `$VALUES` and a constant array (`{ 1, 2 }`);
/// - a field or a virtual call of `this`, in an instance method that never stores another value in local 0, as an
///   enum's constructor sets its fields.
///
/// An `athrow`'s own `NullPointerException` (of a `throw null`) is not counted either: the class of what it throws is,
/// where it is made. Anything the walk doesn't follow loses what it knew, and the exceptions count again.
fn may_raise(class: &crate::classfile::ClassFile, is_static: bool, code: &crate::classfile::Code, insns: &[(u32, Insn)]) -> BTreeSet<&'static str> {
    #[derive(Clone, Copy, PartialEq)]
    enum Value {
        Constant(i64),
        Array(i64),
        This,
        Other,
    }
    let this_kept = !is_static && !insns.iter().any(|(_, insn)| matches!(insn, Insn::Store(_, 0)));
    let mut joins: BTreeSet<u32> = insns.iter().flat_map(|(_, insn)| insn.targets()).collect();
    joins.extend(code.exception_table.iter().map(|h| h.handler_pc as u32));
    let mut out = BTreeSet::new();
    // The operand stack, one value an entry, while the walk knows it.
    let mut stack: Option<Vec<Value>> = Some(Vec::new());
    for (pc, insn) in insns {
        if joins.contains(pc) {
            stack = None;
        }
        let top = |stack: &Option<Vec<Value>>, k: usize| -> Option<Value> { stack.as_ref().and_then(|s| s.len().checked_sub(k + 1).map(|i| s[i])) };
        let within = |array: Option<Value>, index: Option<Value>| matches!((array, index), (Some(Value::Array(n)), Some(Value::Constant(i))) if (0..n).contains(&i));
        let (exceptions, _) = raises(insn);
        let safe = match insn {
            Insn::AThrow => true,
            Insn::NewArray(_) | Insn::ANewArray(_) => matches!(top(&stack, 0), Some(Value::Constant(n)) if n >= 0),
            Insn::ArrayStore(_) => within(top(&stack, 2), top(&stack, 1)),
            Insn::ArrayLoad(_) => within(top(&stack, 1), top(&stack, 0)),
            Insn::PutField(_) => top(&stack, 1) == Some(Value::This),
            Insn::GetField(_) => top(&stack, 0) == Some(Value::This),
            Insn::InvokeVirtual(i) => class.pool.member(*i).ok().and_then(|m| MethodDescriptor::parse(&m.descriptor).ok()).is_some_and(|d| top(&stack, d.params.len()) == Some(Value::This)),
            _ => false,
        };
        if !safe {
            out.extend(exceptions.iter().copied());
        }
        // The stack after it, where the walk follows the instruction.
        let Some(s) = stack.as_mut() else { continue };
        let pops = |s: &mut Vec<Value>, n: usize| -> bool { s.len().checked_sub(n).map(|k| s.truncate(k)).is_some() };
        let invoked = |i: &u16| class.pool.member(*i).ok().and_then(|m| MethodDescriptor::parse(&m.descriptor).ok());
        let followed = match insn {
            Insn::IConst(c) => {
                s.push(Value::Constant(i64::from(*c)));
                true
            }
            Insn::Load(_, 0) if this_kept => {
                s.push(Value::This);
                true
            }
            Insn::Load(..) | Insn::AConstNull | Insn::LConst(_) | Insn::FConst(_) | Insn::DConst(_) | Insn::Ldc(_) | Insn::GetStatic(_) | Insn::New(_) => {
                s.push(Value::Other);
                true
            }
            Insn::Dup => match s.last().copied() {
                Some(v) => {
                    s.push(v);
                    true
                }
                None => false,
            },
            Insn::NewArray(_) | Insn::ANewArray(_) => match s.pop() {
                Some(Value::Constant(n)) => {
                    s.push(Value::Array(n));
                    true
                }
                Some(_) => {
                    s.push(Value::Other);
                    true
                }
                None => false,
            },
            Insn::ArrayStore(_) => pops(s, 3),
            Insn::ArrayLoad(_) => pops(s, 2) && {
                s.push(Value::Other);
                true
            },
            Insn::PutField(_) => pops(s, 2),
            Insn::GetField(_) => pops(s, 1) && {
                s.push(Value::Other);
                true
            },
            Insn::PutStatic(_) | Insn::Pop | Insn::Store(..) => pops(s, 1),
            Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) => match invoked(i) {
                Some(d) => {
                    let receiver = usize::from(!matches!(insn, Insn::InvokeStatic(_)));
                    pops(s, d.params.len() + receiver) && {
                        if d.ret != Type::Void {
                            s.push(Value::Other);
                        }
                        true
                    }
                }
                None => false,
            },
            _ => false,
        };
        if !followed {
            stack = None;
        }
    }
    out
}

/// The exceptions other than an `Error` that an application class's initializer, the function `clinit` of JBMC's
/// `program`, may complete with: those the instructions of the application methods it reaches may raise
/// ([`may_raise`]), and the throwables they instantiate.
fn initializer_raises(program: &Program, cp: &ClassPath, clinit: &str) -> BTreeSet<String> {
    let mut raised = BTreeSet::new();
    let mut seen = BTreeSet::new();
    let mut queue = VecDeque::from([clinit.to_string()]);
    while let Some(id) = queue.pop_front() {
        if !seen.insert(id.clone()) || jdk_initializer(&id) {
            continue;
        }
        let Some(f) = program.functions.get(&id) else { continue };
        queue.extend(f.calls.keys().cloned());
        let Some((owner, name, descriptor)) = method_of(&id) else { continue };
        let Some(class) = cp.application(&owner).ok().flatten() else { continue };
        let Some(method) = class.method(&name, &descriptor) else { continue };
        let Some(code) = method.code.as_ref() else { continue };
        let insns = code.instructions().unwrap_or_default();
        raised.extend(may_raise(&class, method.is_static(), code, &insns).into_iter().map(str::to_string));
        for (_, insn) in &insns {
            if let Insn::New(i) = insn {
                raised.extend(class.pool.class_name(*i).ok().filter(|c| cp.is_subtype(c, "java/lang/Throwable")).map(str::to_string));
            }
        }
    }
    raised.retain(|e| !cp.is_subtype(e, "java/lang/Error"));
    raised
}

/// The `throwing-initializer` defects of what the harness reaches: each application class whose `<clinit>` JBMC
/// runs, that may complete with an exception other than an `Error`, where a handler of the program tells what JBMC
/// does from what the JVM does (JVMS §5.5). The JVM wraps the exception in an `ExceptionInInitializerError` (step
/// 11), marks the class erroneous (step 12), and throws `NoClassDefFoundError` at its next use without running the
/// initializer again (step 5). JBMC 6.11.0's initializer wrapper sets the class's `clinit_already_run` before it
/// calls `<clinit>`, so the exception reaches the caller as it is, and the next use runs on as if the class were
/// initialized. A handler tells them apart when it catches the exception, or the `ExceptionInInitializerError` or
/// the `NoClassDefFoundError` the JVM throws instead. The handlers of the harness class `harness` count only where
/// its assertion tells one exception's class from another (`tells`, [`JbmcRun::tells_exceptions`]): a property
/// without a `throws` clause fails on any exception alike. Its `catch (Throwable)`, last, never counts, since it
/// catches both alike. With no handler that counts, the exception escapes on both, and the harness finds it so.
fn throwing_initializers(program: &Program, cp: &ClassPath, harness: &str, tells: bool, reached: &BTreeMap<String, Option<(String, Option<u16>)>>) -> Vec<Defect> {
    const WRAPPED: &str = "java/lang/ExceptionInInitializerError";
    const ERRONEOUS: &str = "java/lang/NoClassDefFoundError";
    let mut handlers: Vec<(String, Site)> = Vec::new();
    let mut initializers: Vec<(&String, String)> = Vec::new();
    for id in reached.keys() {
        let Some((owner, name, descriptor)) = method_of(id) else { continue };
        if name == "<clinit>" && descriptor == "()V" {
            if !is_jdk_name(&owner) && cp.is_application(&owner) {
                initializers.push((id, owner));
            }
            continue;
        }
        let Some(class) = cp.application(&owner).ok().flatten() else { continue };
        let Some(code) = class.method(&name, &descriptor).and_then(|m| m.code.as_ref()) else { continue };
        for h in &code.exception_table {
            let Some(t) = &h.catch_type else { continue };
            if owner == harness && (!tells || t == "java/lang/Throwable") {
                continue;
            }
            handlers.push((t.clone(), Site { class: owner.clone(), method: name.clone(), line: code.line_at(h.handler_pc as u32) }));
        }
    }
    if handlers.is_empty() {
        return Vec::new();
    }
    let mut out = Vec::new();
    for (clinit, owner) in initializers {
        let raised = initializer_raises(program, cp, clinit);
        if raised.is_empty() {
            continue;
        }
        let telling: Vec<String> = handlers
            .iter()
            .filter(|(t, _)| cp.is_subtype(WRAPPED, t) || cp.is_subtype(ERRONEOUS, t) || raised.iter().any(|e| cp.is_subtype(e, t)))
            .map(|(t, site)| format!("catch ({}) at {}", t.replace('/', "."), site.display()))
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect();
        if telling.is_empty() {
            continue;
        }
        let names: Vec<String> = raised.iter().map(|e| e.replace('/', ".")).collect();
        out.push(Defect {
            kind: "throwing-initializer",
            site: Site { class: owner.clone(), method: "<clinit>".into(), line: None }.display(),
            what: format!(
                "the initializer of {} may throw {}, which the JVM gives its caller as an ExceptionInInitializerError, and later uses of the class as a NoClassDefFoundError (JVMS §5.5); JBMC gives the caller the exception as it is, and runs later uses as if the class were initialized, and {} tell{} them apart",
                owner.replace('/', "."),
                names.join(", "),
                telling.join(", "),
                if telling.len() == 1 { "s" } else { "" }
            ),
        });
    }
    out
}

/// The gaps of JBMC's `program` from the function `java::<class>.<method>:...`, with JBMC's class path `jbmc_cp`
/// (its entries, and the JDK image to tell what a JDK member is). With `entered`, the functions JBMC's symbolic
/// execution of the proof enters ([`entered`]), a stub it does not enter is no gap: the call graph reaches it, but no
/// path within the bounds does. The call sites JBMC does not link, the monitors and the defects are the call graph's.
pub fn find(program: &Program, class: &str, method: &str, jbmc_cp: &ClassPath, jdk: Option<&str>, entered: Option<&BTreeSet<String>>) -> Result<Found, Error> {
    find_told(program, class, method, jbmc_cp, jdk, entered, &BTreeSet::new(), true)
}

/// [`find`], with the stubs JBMC's solver shows no path reaches, by function id (`solved`, from [`probe`]), and for
/// a harness whose assertion tells one exception's class from another where `tells` ([`JbmcRun::tells_exceptions`]).
#[allow(clippy::too_many_arguments)]
fn find_told(program: &Program, class: &str, method: &str, jbmc_cp: &ClassPath, jdk: Option<&str>, entered: Option<&BTreeSet<String>>, solved: &BTreeSet<String>, tells: bool) -> Result<Found, Error> {
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
                for (bci, index, gap, always) in sites {
                    let linked = !always && f.at.get(&index).is_some_and(|text| text.contains("lambda_synthetic_class$"));
                    if !linked {
                        let line = jbmc_cp.application(&owner).ok().flatten().and_then(|c| c.method(&name, &descriptor).and_then(|m| m.code.as_ref()).and_then(|code| code.line_at(bci)));
                        found.gaps.entry(gap).or_default().insert(Site { class: owner.clone(), method: name.clone(), line });
                    }
                }
            }
            Body::Exact => *found.exact.entry(gaps_call(&owner, &name, &descriptor)).or_default() += 1,
            Body::Stub(_) if entered.is_some_and(|e| !e.contains(id)) => found.unreached.push(gaps_call(&owner, &name, &descriptor)),
            Body::Stub(_) if solved.contains(id) => {
                found.unreached.push(gaps_call(&owner, &name, &descriptor));
                found.solved.push(gaps_call(&owner, &name, &descriptor));
            }
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
        if let Some(function) = program.functions.get(id) {
            found.defects.extend(extra_initializers(program, function, jbmc_cp, &owner, &name, &class, code, &insns));
        }
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
    found.defects.extend(throwing_initializers(program, jbmc_cp, &class.replace('.', "/"), tells, &reached));
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
    /// Its bytecode, with its sites JBMC may approximate, each at its offset and its instruction's index (how JBMC's
    /// listing numbers it), as the gap it would be: an `invokedynamic`, a gap unless JBMC linked it (`false`), and a
    /// monitor, always one (`true`).
    Bytecode(Vec<(u32, u32, Gap, bool)>),
    /// JBMC's stub, which reproduces the call exactly.
    Exact,
    /// JBMC's stub, a gap of this kind.
    Stub(GapKind),
}

fn body(cp: &ClassPath, owner: &str, name: &str, descriptor: &str) -> Body {
    if let Ok(Some(class)) = cp.application(owner) {
        if let Some(code) = class.method(name, descriptor).and_then(|m| m.code.as_ref()) {
            let mut sites = Vec::new();
            for (nth, (pc, insn)) in code.instructions().unwrap_or_default().into_iter().enumerate() {
                let nth = nth as u32;
                // JBMC drops a monitor instruction (it models monitors only under --java-threading), so a null one
                // throws nothing: one gap per method that synchronizes, met at its first monitorenter.
                if insn == Insn::MonitorEnter {
                    if !sites.iter().any(|(_, _, g, _): &(u32, u32, Gap, bool)| g.kind == GapKind::Monitor) {
                        sites.push((pc, nth, Gap { kind: GapKind::Monitor, owner: owner.into(), name: name.into(), descriptor: descriptor.into() }, true));
                    }
                    continue;
                }
                let Insn::InvokeDynamic(i) = insn else { continue };
                let Ok((index, site_name, site_descriptor)) = class.pool.invoke_dynamic(i) else { continue };
                let bootstraps = class.bootstrap_methods().unwrap_or_default();
                let (bsm_owner, bsm_name) = bootstraps.get(index as usize).map(|b| (b.method.member.owner.clone(), b.method.member.name.clone())).unwrap_or_else(|| ("java/lang/invoke/CallSite".into(), site_name.to_string()));
                sites.push((pc, nth, Gap { kind: GapKind::InvokeDynamic, owner: bsm_owner, name: bsm_name, descriptor: format!("{site_name}{site_descriptor}") }, false));
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
    let mut cmd = program_command(run, &[]);
    cmd.push("--show-goto-functions".into());
    cmd
}

/// The command of the preflight's second step, when the call graph reaches a stub: the proof's, with its bounds,
/// through symbolic execution alone (`--program-only`), which prints the formula and solves nothing ([`entered`]).
/// It runs over every input, as the proof's last run does, which an earlier stage only restricts.
pub fn symbolic_command(run: &JbmcRun) -> Vec<String> {
    let unwind = run.unwind.to_string();
    let mut cmd = program_command(run, &["--unwind", &unwind, "--unwinding-assertions"]);
    cmd.push("--program-only".into());
    cmd
}

/// The proof's program, class path and options that change it, with `bounds`.
fn program_command(run: &JbmcRun, bounds: &[&str]) -> Vec<String> {
    let entries: Vec<PathBuf> = run.classpath.iter().map(|p| crate::jbmc::absolute(p)).collect();
    let classpath = std::env::join_paths(&entries).map(|p| p.to_string_lossy().into_owned()).unwrap_or_default();
    let mut cmd = vec![run.executable.clone(), run.class.clone(), "--function".into(), format!("{}.{}", run.class, run.function), "--classpath".into(), classpath];
    cmd.extend(bounds.iter().map(|b| b.to_string()));
    cmd.push("--throw-runtime-exceptions".into());
    if !run.refine_strings {
        cmd.push("--no-refine-strings".into());
    }
    cmd.extend(run.extra_args.iter().cloned());
    cmd
}

/// Runs JBMC's symbolic execution of the proof ([`symbolic_command`]) within `budget`, its output in `out`, and reads
/// which functions of `program` it enters; an `Err` says why it cannot tell. The output is kept for a reader only
/// while it is small: a large program prints a long formula.
fn symbolic(run: &JbmcRun, program: &Program, out: &Path, budget: Duration) -> Result<BTreeSet<String>, String> {
    if budget < Duration::from_secs(1) {
        return Err("the listing left it no time".into());
    }
    let cwd = run.log.parent().filter(|p| !p.as_os_str().is_empty()).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let memory = crate::jbmc::memory_limit_mb();
    let cmd = crate::jbmc::limited(symbolic_command(run), memory);
    let file = std::fs::File::create(out).map_err(|e| format!("{} cannot be written: {e}", out.display()))?;
    let err = file.try_clone().map_err(|e| e.to_string())?;
    let mut child = std::process::Command::new(&cmd[0]).args(&cmd[1..]).current_dir(&cwd).stdout(file).stderr(err).spawn().map_err(|e| format!("it cannot be run: {e}"))?;
    let started = std::time::Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
            break status;
        }
        if started.elapsed() > budget {
            let _ = child.kill();
            let _ = child.wait();
            let _ = std::fs::remove_file(out);
            return Err(format!("it did not finish within {} s", crate::deadline::seconds(budget)));
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    let read = if status.success() {
        std::fs::File::open(out).map_err(|e| e.to_string()).and_then(|f| entered(program, std::io::BufReader::new(f)))
    } else {
        let limit = memory.map(|mb| format!(", perhaps out of memory (the limit is {mb} MiB)")).unwrap_or_default();
        Err(format!("it ended with {status}{limit}"))
    };
    if std::fs::metadata(out).is_ok_and(|m| m.len() > 16 << 20) {
        let _ = std::fs::remove_file(out);
    }
    read
}

/// The class of the probes the preflight's third step places ([`probe`]).
pub const PROBES: &str = "jvmcontract/StubProbe";

/// The probes placed for a probe run: for each stub probed, by function id, the numbers of the probes at its call
/// sites (probe `k` is the method `p<k>` of [`PROBES`], its assertion a property of its own).
#[derive(Debug, Default)]
struct Placed {
    stubs: BTreeMap<String, BTreeSet<usize>>,
    /// The probes written, each with the call it makes.
    probes: usize,
}

/// Places a probe at every call site of each stub of `stubs` (function ids) in JBMC's `program`: the class of each
/// function that calls it, as JBMC's class path `cp` has it, is written into `dir` with the call redirected to a
/// method of [`PROBES`] that takes what the call left on the stack. On a branch of its own, chosen by
/// `CProver.nondetBoolean()`, the method fails an assertion of its own (`throw new AssertionError()`, which JBMC takes
/// as an assertion, and as the end of that branch); on the other it makes the call, and returns what the call
/// returns, so every path of the proof goes on as before and a stub reached only after another's probe is still
/// reached. A stub is probed only when every call site of it is: a call the listing gives no bytecode index, an
/// instruction there that is not a call of it, a caller that is no Java method, or one whose class file JBMC's class
/// path lacks, leaves it out.
fn place(program: &Program, cp: &ClassPath, stubs: &BTreeSet<String>, dir: &Path) -> Result<Placed, Error> {
    use crate::classfile::writer::ClassWriter;
    use crate::shared::Invoke;
    // The call sites of each class, by method and instruction, with the stubs each calls.
    type Sites = BTreeMap<(String, String), BTreeMap<u32, BTreeSet<String>>>;
    let mut sites: BTreeMap<String, Sites> = BTreeMap::new();
    let mut unprobed: BTreeSet<String> = BTreeSet::new();
    let ids: BTreeSet<String> = program.functions.keys().cloned().collect();
    for (caller, f) in &program.functions {
        let called: Vec<&String> = f.calls.keys().filter(|c| stubs.contains(*c)).collect();
        if called.is_empty() {
            continue;
        }
        let Some((owner, name, descriptor)) = method_of(caller) else {
            unprobed.extend(called.into_iter().cloned());
            continue;
        };
        let mut placed: BTreeSet<&String> = BTreeSet::new();
        for (index, text) in &f.at {
            for insn in text.lines() {
                let Some(call) = insn.strip_prefix("CALL ") else { continue };
                let call = call.split_once(" := ").map(|(_, c)| c).unwrap_or(call);
                if let Some(stub) = callee(&ids, call).filter(|c| stubs.contains(*c)) {
                    sites.entry(owner.clone()).or_default().entry((name.clone(), descriptor.clone())).or_default().entry(*index).or_default().insert(stub.clone());
                    placed.insert(stub);
                }
            }
        }
        unprobed.extend(called.into_iter().filter(|c| f.unplaced.contains(*c) || !placed.contains(c)).cloned());
    }
    if dir.exists() {
        std::fs::remove_dir_all(dir)?;
    }
    std::fs::create_dir_all(dir)?;
    let mut w = ClassWriter::new(PROBES);
    w.source_file = Some("StubProbe.java".into());
    let mut out = Placed::default();
    for (owner, methods) in &sites {
        let Some((_, bytes)) = cp.resources(&format!("{owner}.class"))?.into_iter().next() else {
            unprobed.extend(methods.values().flat_map(|m| m.values().flatten().cloned()));
            continue;
        };
        // Each site rewritten, with its probe's number.
        let done: std::cell::RefCell<BTreeMap<(String, String, u32), usize>> = Default::default();
        let failed: std::cell::RefCell<Option<Error>> = Default::default();
        let writer = std::cell::RefCell::new(&mut w);
        let next = std::cell::Cell::new(out.probes);
        let lookup = |method: &crate::classfile::Method, place: u32, invoke: Invoke, m: &crate::classfile::MemberRef| -> Option<crate::classfile::MemberRef> {
            let called = methods.get(&(method.name.clone(), method.descriptor.clone()))?.get(&place)?;
            // The instruction there calls the stub: its method, or one of its name and descriptor JBMC dispatches to it.
            let calls = |stub: &String| method_of(stub).is_some_and(|(owner, name, descriptor)| name == m.name && descriptor == m.descriptor && (owner == m.owner || matches!(invoke, Invoke::Virtual | Invoke::Interface)));
            if !called.iter().any(calls) {
                return None;
            }
            let k = next.get();
            match forwarder(&mut writer.borrow_mut(), k, invoke, m) {
                Ok(descriptor) => {
                    next.set(k + 1);
                    done.borrow_mut().insert((method.name.clone(), method.descriptor.clone(), place), k);
                    Some(crate::classfile::MemberRef::new(PROBES, &format!("p{k}"), &descriptor))
                }
                Err(e) => {
                    failed.borrow_mut().get_or_insert(e);
                    None
                }
            }
        };
        let patched = crate::shared::redirect_calls_at(&bytes, &lookup)?;
        if let Some(e) = failed.into_inner() {
            return Err(e);
        }
        out.probes = next.get();
        let done = done.into_inner();
        for ((name, descriptor), at) in methods {
            for (place, called) in at {
                match done.get(&(name.clone(), descriptor.clone(), *place)) {
                    Some(k) => called.iter().for_each(|stub| {
                        out.stubs.entry(stub.clone()).or_default().insert(*k);
                    }),
                    None => unprobed.extend(called.iter().cloned()),
                }
            }
        }
        if let Some(patched) = patched {
            let target = dir.join(format!("{owner}.class"));
            std::fs::create_dir_all(target.parent().expect("a class file's directory"))?;
            std::fs::write(target, patched)?;
        }
    }
    out.stubs.retain(|stub, _| !unprobed.contains(stub));
    if out.probes > 0 {
        let target = dir.join(format!("{PROBES}.class"));
        std::fs::create_dir_all(target.parent().expect("a package"))?;
        std::fs::write(target, w.to_bytes())?;
    }
    Ok(out)
}

/// Adds probe `k` to `w`, for a call site that invokes `m` so, and returns its descriptor: the call's, with the
/// receiver first for any call but a static one.
fn forwarder(w: &mut crate::classfile::writer::ClassWriter, k: usize, invoke: crate::shared::Invoke, m: &crate::classfile::MemberRef) -> Result<String, Error> {
    use crate::classfile::writer::{CodeBuilder, MethodWriter};
    use crate::classfile::{flags, Cond, Kind};
    use crate::shared::Invoke;
    let kind = |t: &Type| match t {
        Type::Long => Kind::Long,
        Type::Float => Kind::Float,
        Type::Double => Kind::Double,
        Type::Object(_) | Type::Array(_) => Kind::Ref,
        _ => Kind::Int,
    };
    let d = MethodDescriptor::parse(&m.descriptor).map_err(|e| Error::new(format!("{}.{}{}: {e}", m.owner, m.name, m.descriptor)))?;
    let receiver = match invoke {
        Invoke::Static => String::new(),
        _ if m.owner.starts_with('[') => m.owner.clone(),
        _ => format!("L{};", m.owner),
    };
    let ret = &m.descriptor[m.descriptor.rfind(')').map(|i| i + 1).unwrap_or(m.descriptor.len())..];
    let descriptor = format!("({receiver}{}){ret}", d.params.iter().map(Type::descriptor).collect::<String>());
    let mut code = CodeBuilder::new();
    let nondet = w.pool.method_ref("org/cprover/CProver", "nondetBoolean", "()Z");
    code.op_u16(0xb8, nondet); // invokestatic
    let call = code.label();
    code.if_zero(Cond::Eq, call);
    let error = w.pool.class("java/lang/AssertionError");
    let init = w.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
    code.op_u16(0xbb, error); // new
    code.op(0x59); // dup
    code.op_u16(0xb7, init); // invokespecial
    code.op(0xbf); // athrow
    code.bind(call);
    let mut slot = 0u16;
    if invoke != Invoke::Static {
        code.load(Kind::Ref, 0);
        slot = 1;
    }
    for t in &d.params {
        code.load(kind(t), slot);
        slot += t.slots();
    }
    let target = if m.interface { w.pool.interface_method_ref(&m.owner, &m.name, &m.descriptor) } else { w.pool.method_ref(&m.owner, &m.name, &m.descriptor) };
    match invoke {
        Invoke::Static => code.op_u16(0xb8, target),
        Invoke::Special => code.op_u16(0xb7, target),
        Invoke::Virtual => code.op_u16(0xb6, target),
        Invoke::Interface => {
            code.op_u16(0xb9, target);
            code.op(slot as u8);
            code.op(0);
        }
    }
    code.return_(if d.ret == Type::Void { None } else { Some(kind(&d.ret)) });
    code.max_locals = slot;
    code.max_stack = slot.max(2) + 2;
    w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: format!("p{k}"), descriptor: descriptor.clone(), code: Some(code) });
    Ok(descriptor)
}

/// The command of the preflight's third step: the proof's, with its bounds and solver, over every input, on its
/// class path behind the probes' classes in `dir` ([`place`]). It solves, as the proof does, and prints each
/// property's outcome without a trace.
pub fn probe_command(run: &JbmcRun, dir: &Path) -> Vec<String> {
    let probed = JbmcRun { classpath: std::iter::once(dir.to_path_buf()).chain(run.classpath.iter().cloned()).collect(), ..run.clone() };
    let unwind = run.unwind.to_string();
    let mut cmd = program_command(&probed, &["--unwind", &unwind, "--unwinding-assertions"]);
    if let Some(solver) = &run.sat_solver {
        cmd.extend(["--sat-solver".into(), solver.clone()]);
    }
    cmd
}

/// The stubs of `placed` the probe run's `output` shows no path within the bounds reaches, by function id: those all
/// of whose probes' assertions hold. The run tells only when it finished with a verdict and every unwinding
/// assertion held, so that no path was cut at the bound; an `Err` says why it cannot tell. A probe whose outcome the
/// output lacks does not hold.
fn probed(output: &str, placed: &Placed) -> Result<BTreeSet<String>, String> {
    if let Some(line) = output.lines().find(|l| l.contains("did not finish within") || l.contains(crate::tla::KILLED_BY_SIGNAL)) {
        return Err(line.trim_start_matches("Error: ").trim().to_string());
    }
    if !output.lines().any(|l| l == "VERIFICATION SUCCESSFUL" || l == "VERIFICATION FAILED") {
        return Err("it gave no verdict".into());
    }
    // Each property's outcome, by id: `[id] description: SUCCESS`.
    let mut holds: BTreeMap<&str, bool> = BTreeMap::new();
    for line in output.lines() {
        let Some(rest) = line.strip_prefix('[') else { continue };
        let Some((id, rest)) = rest.split_once("] ") else { continue };
        let Some((description, outcome)) = rest.rsplit_once(": ") else { continue };
        let held = outcome == "SUCCESS";
        if description.contains("unwinding assertion") && !held {
            return Err(format!("its unwinding assertion {id} is {outcome}: paths past the bound were cut"));
        }
        holds.insert(id, held);
    }
    let held = |k: usize| {
        let prefix = format!("java::{}.p{k}:", PROBES.replace('/', "."));
        let mine: Vec<bool> = holds.iter().filter(|(id, _)| id.starts_with(&prefix) && id.contains(".assertion.")).map(|(_, h)| *h).collect();
        !mine.is_empty() && mine.iter().all(|h| *h)
    };
    Ok(placed.stubs.iter().filter(|(_, probes)| !probes.is_empty() && probes.iter().all(|k| held(*k))).map(|(stub, _)| stub.clone()).collect())
}

/// The preflight's third step, for the stubs JBMC's symbolic execution still enters (`stubs`, function ids): the
/// proof with a probe at each of their call sites ([`place`], [`probe_command`]), within `budget`, its output in
/// `run`'s directory. `None` when no stub could be probed; otherwise the stubs the solver shows no path reaches
/// ([`probed`]), or why it cannot tell.
fn probe(run: &JbmcRun, program: &Program, cp: &ClassPath, stubs: &BTreeSet<String>, budget: Duration) -> Option<Result<BTreeSet<String>, String>> {
    let dir = run.log.with_file_name("jbmc-probes");
    let placed = match place(program, cp, stubs, &dir) {
        Ok(placed) if placed.stubs.is_empty() => return None,
        Ok(placed) => placed,
        Err(e) => return Some(Err(format!("its probes cannot be placed: {e}"))),
    };
    if budget < Duration::from_secs(1) {
        return Some(Err("the listing and the symbolic execution left it no time".into()));
    }
    let started = std::time::Instant::now();
    let cwd = run.log.parent().filter(|p| !p.as_os_str().is_empty()).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let memory = crate::jbmc::memory_limit_mb();
    let mut output = match crate::tla::run_with_timeout(&crate::jbmc::limited(probe_command(run, &dir), memory), &cwd, budget) {
        Ok(output) => output,
        Err(e) => return Some(Err(format!("it cannot be run: {e}"))),
    };
    if run.sat_solver.is_some() && output.contains("unknown solver '") {
        // This JBMC was built without the solver asked for: its own default will do, within what is left.
        let fallback = JbmcRun { sat_solver: None, ..run.clone() };
        output = match crate::tla::run_with_timeout(&crate::jbmc::limited(probe_command(&fallback, &dir), memory), &cwd, budget.saturating_sub(started.elapsed())) {
            Ok(output) => output,
            Err(e) => return Some(Err(format!("it cannot be run: {e}"))),
        };
    }
    let _ = std::fs::write(run.log.with_file_name("jbmc-probes.txt"), &output);
    Some(probed(&output, &placed))
}

/// What the preflight of a JBMC proof found, or why it could not tell.
#[derive(Debug, Clone)]
pub struct Preflight {
    pub found: Option<Found>,
    /// Why the program could not be listed or read.
    pub problem: Option<String>,
    pub log: PathBuf,
    pub seconds: f64,
    /// When the call graph reaches a stub, what JBMC's symbolic execution of the proof told of it: `Ok` with the
    /// seconds it took, the stubs it never enters then left out of the gaps ([`Found::unreached`]), or `Err` with why
    /// it could not tell, the gaps then the call graph's. Symbolic execution drops a branch only when it simplifies
    /// its condition to false, so a stub behind a condition the solver would decide (an `--assume`) is entered:
    /// [`Preflight::probes`] says more of those.
    pub paths: Option<Result<f64, String>>,
    /// When the symbolic execution still enters a stub that a probe can be placed at every call site of, what the
    /// proof with those probes told ([`probe`]): `Ok` with the seconds it took, each stub whose every probe held then
    /// left out of the gaps ([`Found::solved`]), or `Err` with why it could not tell, the stubs then gaps.
    pub probes: Option<Result<f64, String>>,
}

/// Runs the preflight for `run` (its log next to the run's), within `budget`.
pub fn preflight(run: &JbmcRun, budget: Duration) -> Result<Preflight, Error> {
    crate::phases::timed(crate::phases::Step::Gaps, || preflight_untimed(run, budget))
}

fn preflight_untimed(run: &JbmcRun, budget: Duration) -> Result<Preflight, Error> {
    let log = run.log.with_file_name("jbmc-goto.txt");
    let started = std::time::Instant::now();
    if !crate::jbmc::available(&run.executable) {
        return Ok(Preflight { found: None, problem: Some(format!("jbmc is not installed ({} not found)", run.executable)), log, seconds: 0.0, paths: None, probes: None });
    }
    let cwd = run.log.parent().filter(|p| !p.as_os_str().is_empty()).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let output = crate::tla::run_with_timeout(&crate::jbmc::limited(command(run), crate::jbmc::memory_limit_mb()), &cwd, budget.min(Duration::from_secs(PREFLIGHT_SECONDS)))?;
    std::fs::write(&log, &output)?;
    let seconds = started.elapsed().as_secs_f64();
    if output.contains("did not finish within") {
        return Ok(Preflight { found: None, problem: Some(format!("listing JBMC's program did not finish within {} s", crate::deadline::seconds(budget.min(Duration::from_secs(PREFLIGHT_SECONDS))))), log, seconds, paths: None, probes: None });
    }
    let mut cp = ClassPath::new().with_models(false).with_default_jdk();
    for entry in &run.classpath {
        if entry.exists() {
            cp.add(entry)?;
        }
    }
    let program = parse_goto(&output);
    let jdk = gaps::jdk_release();
    let none = BTreeSet::new();
    let mut found = match find_told(&program, &run.class, &run.function, &cp, jdk.as_deref(), None, &none, run.tells_exceptions) {
        Ok(found) => found,
        Err(e) => return Ok(Preflight { found: None, problem: Some(e.to_string()), log, seconds, paths: None, probes: None }),
    };
    // The call graph takes every branch: a stub the program calls only where a condition the bounds decide is false
    // is reached there too. JBMC's symbolic execution of the proof says which it enters.
    let stub = |g: &Gap| !matches!(g.kind, GapKind::Monitor | GapKind::InvokeDynamic);
    let cap = budget.min(Duration::from_secs(PREFLIGHT_SECONDS));
    let (mut paths, mut probes) = (None, None);
    if found.gaps.keys().any(stub) {
        let begun = std::time::Instant::now();
        paths = Some(match symbolic(run, &program, &run.log.with_file_name("jbmc-symex.txt"), cap.saturating_sub(started.elapsed())) {
            Ok(entered) => {
                found = find_told(&program, &run.class, &run.function, &cp, jdk.as_deref(), Some(&entered), &none, run.tells_exceptions)?;
                let seconds = begun.elapsed().as_secs_f64();
                // Symbolic execution keeps a branch whose condition only the solver decides: the proof with a probe
                // at each call site of the stubs it still enters says which no path reaches.
                let stubs: BTreeSet<String> = program
                    .functions
                    .keys()
                    .filter(|id| method_of(id).is_some_and(|(owner, name, descriptor)| found.gaps.keys().any(|g| stub(g) && g.owner == owner && g.name == name && g.descriptor == descriptor)))
                    .cloned()
                    .collect();
                if !stubs.is_empty() {
                    let begun = std::time::Instant::now();
                    probes = match probe(run, &program, &cp, &stubs, cap.saturating_sub(started.elapsed())) {
                        Some(Ok(solved)) => {
                            if !solved.is_empty() {
                                found = find_told(&program, &run.class, &run.function, &cp, jdk.as_deref(), Some(&entered), &solved, run.tells_exceptions)?;
                            }
                            Some(Ok(begun.elapsed().as_secs_f64()))
                        }
                        Some(Err(why)) => Some(Err(why)),
                        None => None,
                    };
                }
                Ok(seconds)
            }
            Err(why) => Err(why),
        });
    }
    Ok(Preflight { found: Some(found), problem: None, log, seconds: started.elapsed().as_secs_f64(), paths, probes })
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
            (Some(f), _) => {
                let mut out = String::new();
                let never: Vec<&str> = f.unreached.iter().filter(|c| !f.solved.contains(c)).map(String::as_str).collect();
                match &self.paths {
                    Some(Ok(seconds)) if !never.is_empty() => {
                        let n = never.len();
                        let _ = writeln!(
                            out,
                            "note: JBMC's call graph reaches {n} stub{} that its symbolic execution of the proof ({:.1} s, nothing solved) never enters, on no path within the bounds, so no gap{}: {}",
                            if n == 1 { "" } else { "s" },
                            seconds,
                            if n == 1 { "" } else { "s" },
                            never.join(", ")
                        );
                    }
                    Some(Err(why)) => {
                        let _ = writeln!(out, "note: which stubs JBMC's paths reach is not known, since its symbolic execution of the proof could not tell ({why}): the gaps are those of its call graph");
                    }
                    _ => {}
                }
                match &self.probes {
                    Some(Ok(seconds)) if !f.solved.is_empty() => {
                        let n = f.solved.len();
                        let _ = writeln!(
                            out,
                            "note: JBMC's symbolic execution of the proof enters {n} stub{} that its solver shows no path within the bounds and assumptions reaches, by the proof with an assertion of its own before each call ({:.1} s, every one held, and every unwinding assertion), so no gap{}: {}",
                            if n == 1 { "" } else { "s" },
                            seconds,
                            if n == 1 { "" } else { "s" },
                            f.solved.join(", ")
                        );
                    }
                    Some(Err(why)) => {
                        let _ = writeln!(out, "note: whether a path reaches the stubs JBMC's symbolic execution enters is not known, since the proof with a probe at their calls could not tell ({why}): they stay gaps");
                    }
                    _ => {}
                }
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
        // Labels: pc9
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
        assert_eq!(m.locations[&4], "file K.java line 8 function java::p.K.m:(I)I bytecode-index 9", "{:?}", m.locations);
        assert_eq!(check.locations.keys().collect::<Vec<_>>(), [&1, &2]);
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
        let found = find(&p, "H", "check", &cp, Some("25"), None).unwrap();
        let ids: Vec<&str> = found.records.iter().map(|r| r.id.as_str()).collect();
        assert_eq!(ids, ["jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25", "missing-body:p.K.m(I)I"], "{found:?}");
        assert_eq!(found.initializer_stubs, ["java.lang.Class.getPrimitiveClass(java.lang.String)"]);
        let list = found.records.iter().find(|r| r.kind == GapKind::JdkConstructor).unwrap();
        assert_eq!(list.sites, ["p.K.m:7"]);
        assert!(list.approximation.starts_with("is JBMC's stub: it constructs the object and does nothing else"), "{}", list.approximation);
        assert_eq!(list.checker.as_deref(), Some("jbmc"));
        assert!(find(&p, "H", "other", &cp, None, None).is_err());
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
            let found = find(&calling(method, descriptor), "H", method, &cp, None, None).unwrap();
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
        let found = find(&calling("returned", "(I)I"), "H", "returned", &cp, None, None).unwrap();
        let what = &found.defects[0].what;
        assert!(what.contains("java.lang.ArithmeticException") && what.contains("after it leaves the try block"), "{what}");
        let found = find(&calling("thrown", "(I)I"), "H", "thrown", &cp, None, None).unwrap();
        let what = &found.defects[0].what;
        assert!(what.contains("catch (java.lang.RuntimeException)") && what.contains("java.lang.IllegalArgumentException"), "{what}");
        let found = find(&calling("shiftedUnsigned", "(JI)J"), "H", "shiftedUnsigned", &cp, None, None).unwrap();
        let what = &found.defects[0].what;
        assert!(what.contains("a long with >>>") && what.contains("0..63") && what.contains("low six bits") && what.contains("zeros"), "{what}");
    }

    /// A goto program whose harness `H.<method>` calls `p.D.<method>`, which calls the initializer wrapper `wrapper`
    /// at bytecode index `bci`, with the wrappers of `p.D`'s nested classes as JBMC 6.11.0 lists them for the
    /// fixture: a class's wrapper calls its superclass's and every superinterface's, then its own `<clinit>`.
    fn initializing(method: &str, descriptor: &str, bci: u32, wrapper: &str) -> Program {
        let mut text = format!(
            "H.{method}() /* java::H.{method}:()V */\n        // 1 file H.java line 1 function java::H.{method}:()V bytecode-index 1\n        CALL java::p.D.{method}:{descriptor}(x)\n        END_FUNCTION\n\n^^^^^^^^\n\np.D.{method}() /* java::p.D.{method}:{descriptor} */\n        // 2 file p/D.java line 21 function java::p.D.{method}:{descriptor} bytecode-index {bci}\n        // Labels: pc{bci}\n        CALL java::p.D${wrapper}.<clinit_wrapper>()\n        END_FUNCTION\n\n^^^^^^^^\n\n"
        );
        for (class, calls) in [("Holder", vec!["CALL java::p.D$Holder.<clinit>:()V()"]), ("Sub", vec!["CALL java::p.D$Holder.<clinit_wrapper>()", "CALL java::p.D$Sub.<clinit>:()V()"]), ("Bare", vec!["CALL java::p.D$Bare.<clinit>:()V()"]), ("Greeter", vec!["CALL java::p.D$Greeter.<clinit>:()V()"]), ("Hello", vec!["CALL java::p.D$Bare.<clinit_wrapper>()", "     1: CALL java::p.D$Greeter.<clinit_wrapper>()"])] {
            text.push_str(&format!("java::p.D${class}.<clinit_wrapper> /* java::p.D${class}.<clinit_wrapper> */\n        IF ¬(java::p.D${class}::clinit_already_run ⇔ false) THEN GOTO 1\n        ASSIGN java::p.D${class}::clinit_already_run := true\n"));
            for call in calls {
                text.push_str(&format!("        {}\n", call.trim_start()));
            }
            text.push_str("     1: END_FUNCTION\n\n^^^^^^^^\n\n");
            if class != "Hello" {
                text.push_str(&format!("p.D${class}.<clinit>() /* java::p.D${class}.<clinit>:()V */\n        END_FUNCTION\n\n^^^^^^^^\n\n"));
            }
        }
        parse_goto(&text)
    }

    /// The reproducer of `conformance/declaring/2` and `defaults/3`, which JBMC proved where the JVM refutes them:
    /// JBMC 6.11.0 initializes the class a static member is named through rather than the one that declares it, and a
    /// class's superinterfaces that declare no default method. Each is named where the program reaches it; a
    /// member named through its own class, and a `new`, which the JVM initializes as JBMC does, are not.
    #[test]
    fn the_preflight_names_an_initializer_jbmc_runs_where_the_jvm_does_not() {
        let Some((_dir, cp)) = defect_fixture() else { return };
        let defects = |method: &str, descriptor: &str, bci: u32, wrapper: &str| -> Vec<Defect> { find(&initializing(method, descriptor, bci, wrapper), "H", method, &cp, None, None).unwrap().defects };
        let kinds = |d: Vec<Defect>| -> Vec<(String, String)> { d.iter().map(|d| (d.kind.to_string(), d.site.clone())).collect() };
        assert_eq!(kinds(defects("declaring", "(I)I", 0, "Sub")), [("extra-initializer".to_string(), "p.D.declaring:21".to_string())]);
        assert_eq!(kinds(defects("assigned", "(I)V", 1, "Sub")), [("extra-initializer".to_string(), "p.D.assigned:22".to_string())]);
        assert_eq!(kinds(defects("inherited", "(I)I", 0, "Sub")), [("extra-initializer".to_string(), "p.D.inherited:23".to_string())]);
        assert_eq!(kinds(defects("defaults", "(I)I", 1, "Hello")), [("extra-initializer".to_string(), "p.D.defaults:25".to_string())]);
        assert_eq!(kinds(defects("direct", "(I)I", 0, "Holder")), []);
        assert_eq!(kinds(defects("created", "(I)I", 0, "Sub")), []);
        let what = &defects("declaring", "(I)I", 0, "Sub")[0].what;
        assert!(what.contains("getstatic p.D$Sub.value resolves to a member p.D$Holder declares") && what.contains("initializer of p.D$Sub where the JVM does not"), "{what}");
        let what = &defects("defaults", "(I)I", 1, "Hello")[0].what;
        assert!(what.contains("invokestatic initializes p.D$Hello") && what.contains("initializer of p.D$Bare where") && !what.contains("Greeter"), "{what}");
    }

    /// A goto program of the functions `functions`, each an id with the ids it calls, as JBMC 6.11.0 lists them.
    fn listing(functions: &[(&str, &[&str])]) -> Program {
        let mut text = String::new();
        for (id, calls) in functions {
            text.push_str(&format!("f() /* {id} */\n"));
            for call in *calls {
                text.push_str(&format!("        CALL {call}()\n"));
            }
            text.push_str("        END_FUNCTION\n\n^^^^^^^^\n\n");
        }
        parse_goto(&text)
    }

    /// The program of `p.D.<method>` called from the harness class `harness` (`H`, which has no class file here, or
    /// `p.D` itself standing in for one), where `p.D.<method>` initializes `p.D$<class>`, whose `<clinit>` calls
    /// `p.D$<class>.<callees>`. JBMC's wrapper sets `clinit_already_run` and calls the class's `<clinit>`.
    fn initializer_throwing(harness: &str, method: &str, class: &str, callees: &[&str]) -> Program {
        let target = format!("java::p.D.{method}:(I)I");
        let root = format!("java::H.{method}:()V");
        let wrapper = format!("java::p.D${class}.<clinit_wrapper>");
        let clinit = format!("java::p.D${class}.<clinit>:()V");
        let called: Vec<String> = callees.iter().map(|c| format!("java::p.D${class}.{c}")).collect();
        let mut functions: Vec<(&str, Vec<&str>)> = vec![(&target, vec![&wrapper]), (&wrapper, vec![&clinit]), (&clinit, called.iter().map(String::as_str).collect())];
        functions.extend(called.iter().map(|c| (c.as_str(), Vec::new())));
        if harness == "H" {
            functions.push((&root, vec![&target]));
        }
        let borrowed: Vec<(&str, &[&str])> = functions.iter().map(|(id, calls)| (*id, calls.as_slice())).collect();
        listing(&borrowed)
    }

    /// The reproducer of `conformance/boomTwice/1` and `enumBroken/1` (VF-009), whose JBMC counterexamples do not
    /// reproduce: JBMC 6.11.0 gives the exception of a class initializer to its caller as it is, where the JVM gives
    /// an `ExceptionInInitializerError` (job `20261107-163056` ran `tests/fixtures/jbmc-defects/F.java`). It is named
    /// where a handler tells the two apart: one of `ExceptionInInitializerError`, or of the exception itself, or an
    /// application's `catch (Throwable)`, after which the class is erroneous on the JVM and initialized in JBMC. An
    /// initializer that escapes uncaught, throws an `Error` (which the JVM does not wrap), or throws nothing is not
    /// named, nor is the harness's own `catch (Throwable)`.
    #[test]
    fn the_preflight_names_a_class_initializer_that_throws_where_a_handler_tells_jbmc_from_the_jvm() {
        let Some((_dir, cp)) = defect_fixture() else { return };
        let defects = |harness: &str, method: &str, class: &str, callees: &[&str]| -> Vec<Defect> {
            find(&initializer_throwing(harness, method, class, callees), harness, method, &cp, None, None).unwrap().defects.into_iter().filter(|d| d.kind == "throwing-initializer").collect()
        };
        let sites = |d: Vec<Defect>| -> Vec<String> { d.iter().map(|d| d.site.clone()).collect() };
        let table = ["table:()[I"];
        assert_eq!(sites(defects("H", "boomed", "Boom", &table)), ["p.D$Boom.<clinit>"]);
        assert_eq!(sites(defects("H", "divided", "Ratio", &[])), ["p.D$Ratio.<clinit>"]);
        assert_eq!(sites(defects("H", "caughtAll", "Boom", &table)), ["p.D$Boom.<clinit>"]);
        assert_eq!(sites(defects("p/D", "caughtAll", "Boom", &table)), Vec::<String>::new(), "the harness's own catch (Throwable)");
        assert_eq!(sites(defects("H", "escaped", "Boom", &table)), Vec::<String>::new());
        assert_eq!(sites(defects("H", "fatal", "Fatal", &table)), Vec::<String>::new());
        assert_eq!(sites(defects("H", "quiet", "Quiet", &[])), Vec::<String>::new());
        // An enum's initializer and constructor, and a constant array, throw nothing: their array stores are within a
        // fresh array of constant length, and their field stores are of `this`. An array of a length read from a
        // field may be negative.
        assert_eq!(sites(defects("H", "toned", "Tone", &["<init>:(Ljava/lang/String;II)V", "$values:()[Lp/D$Tone;"])), Vec::<String>::new());
        assert_eq!(sites(defects("H", "tabled", "Table", &[])), Vec::<String>::new());
        assert_eq!(sites(defects("H", "sized", "Sized", &[])), ["p.D$Sized.<clinit>"]);
        assert!(defects("H", "sized", "Sized", &[])[0].what.contains("may throw java.lang.NegativeArraySizeException"));
        let what = &defects("H", "boomed", "Boom", &table)[0].what;
        assert!(what.contains("may throw java.lang.IllegalStateException") && what.contains("catch (java.lang.ExceptionInInitializerError) at p.D.boomed:") && what.contains("NoClassDefFoundError"), "{what}");
        let what = &defects("H", "divided", "Ratio", &[])[0].what;
        assert!(what.contains("may throw java.lang.ArithmeticException") && what.contains("catch (java.lang.ArithmeticException) at p.D.divided:"), "{what}");
    }

    /// The same on JBMC 6.11.0's own listings of the corpus's `boomTwice` and `enumBroken` under their property
    /// harness, which job `20261107-163056` kept (`tests/fixtures/jbmc-defects/vf009/`): the initializers of
    /// `Boom` and `Broken` are named, by the corpus methods' `catch (ExceptionInInitializerError)`. The harness's
    /// handlers count only where it tells exceptions apart: without a `throws` clause, any exception fails it alike.
    #[test]
    fn the_corpus_initializers_that_throw_are_named_in_jbmcs_own_listings() {
        let javac = std::process::Command::new("javac").arg("-version").output().is_ok_and(|o| o.status.success());
        let mut cp = ClassPath::new().with_models(false).with_default_jdk();
        if !javac || !cp.has_jdk() {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "javac or a JDK not found: put them on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            return;
        }
        let root = Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixtures = root.join("tests/fixtures/jbmc-defects/vf009");
        let out = tempfile::tempdir().unwrap();
        let corpus = root.join("tests/conformance/conformance/Conformance.java");
        let status = std::process::Command::new("javac").args(["-g", "-d"]).arg(out.path()).arg(&corpus).arg(fixtures.join("PropertyHarness.java")).status().unwrap();
        assert!(status.success(), "the corpus and the harness compile");
        cp.add(out.path()).unwrap();
        for (method, class) in [("boomTwice", "Boom"), ("enumBroken", "Broken")] {
            let program = parse_goto(&std::fs::read_to_string(fixtures.join(format!("{method}-goto.txt"))).unwrap());
            for tells in [false, true] {
                let found = find_told(&program, "PropertyHarness", "check", &cp, None, None, &BTreeSet::new(), tells).unwrap();
                let named: Vec<&Defect> = found.defects.iter().filter(|d| d.kind == "throwing-initializer").collect();
                assert_eq!(named.iter().map(|d| d.site.as_str()).collect::<Vec<_>>(), [format!("conformance.Conformance${class}.<clinit>")], "{method} tells={tells}: {:?}", found.defects);
                let what = &named[0].what;
                assert!(what.contains(&format!("catch (java.lang.ExceptionInInitializerError) at conformance.Conformance.{method}:")), "{what}");
                assert_eq!(what.contains("at PropertyHarness.check"), tells, "{what}");
            }
        }
    }

    /// A JBMC proof that reaches a defect is refused under every gap mode, assume too: the defect is not an
    /// approximation a statement could name, but code JBMC runs otherwise than the JVM. A counterexample stands,
    /// for the interpreter's replay, and the replay's message names the defect as the likely cause.
    #[test]
    fn a_proof_through_a_defect_is_refused_under_every_mode_and_a_counterexample_is_left_to_the_replay() {
        let defect = Defect { kind: "return-past-handler", site: "p.D.returned:7".into(), what: "raises it after it leaves the try block".into() };
        let pre = Preflight { found: Some(Found { defects: vec![defect], ..Found::default() }), problem: None, log: PathBuf::from("jbmc-goto.txt"), seconds: 0.0, paths: None, probes: None };
        let result = |verdict: Verdict| crate::jbmc::JbmcResult {
            verdict,
            version: "6.11.0".into(),
            properties: 2,
            raw_inputs: BTreeMap::new(),
            raw_arrays: BTreeMap::new(),
            raw_same: BTreeMap::new(),
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

    /// What `--program-only` prints for [`GOTO`] when the harness's call of `p.K.m` is on no path: the steps of
    /// `H.check` alone, each after the comment of its location in the listing.
    const SSA: &str = "JBMC version 6.11.0 (cbmc-6.11.0) 64-bit x86_64 linux\nsize of program expression: 2 steps\nProgram constraints:\n// 1 file H.java line 3 function java::H.check:(I)V bytecode-index 1\n(1) x!0#1 == 0\n// 2 file H.java line 4 function java::H.check:(I)V bytecode-index 5\n";

    #[test]
    fn the_functions_symbolic_execution_enters_are_read_by_the_listings_locations() {
        let p = parse_goto(GOTO);
        let entered = entered(&p, SSA.as_bytes()).unwrap();
        assert_eq!(entered.iter().collect::<Vec<_>>(), ["java::H.check:(I)V"]);
        // Another program's locations, an unfinished run, or a formula of no location tell nothing.
        let moved = SSA.replace("line 4 function", "line 5 function");
        assert!(entered_err(&p, &moved).contains("location 2 is `file H.java line 5"), "{}", entered_err(&p, &moved));
        assert!(entered_err(&p, &SSA.replace("// 2 ", "// 99 ")).contains("location 99"));
        assert!(entered_err(&p, &SSA.replace("Program constraints:", "")).contains("no formula"));
        assert!(entered_err(&p, "Program constraints:\n(1) x == 0\n").contains("no location"));
        // A stub the call graph reaches and symbolic execution does not enter is no gap.
        let cp = ClassPath::new().with_models(false).with_default_jdk();
        if !cp.has_jdk() {
            return;
        }
        let mut entered = entered;
        entered.insert("java::p.K.m:(I)I".into());
        let found = find(&p, "H", "check", &cp, Some("25"), Some(&entered)).unwrap();
        assert_eq!(found.records.iter().map(|r| r.id.as_str()).collect::<Vec<_>>(), ["missing-body:p.K.m(I)I"]);
        assert_eq!(found.unreached, ["java.util.ArrayList.<init>(int)"]);
    }

    fn entered_err(p: &Program, ssa: &str) -> String {
        entered(p, ssa.as_bytes()).unwrap_err()
    }

    /// `tests/fixtures/jbmc-paths/P.java` through the preflight on JBMC 6.11.0, with the models on its class path:
    /// the model of `List.copyOf` calls `Collection.isEmpty` and `toArray` only for a collection other than the
    /// immutable lists `List.of` makes. Over a list `List.of` made, the call graph reaches the two stubs and the
    /// symbolic execution of the proof enters neither, so the proof meets no gap; over a collection JBMC knows
    /// nothing of, it enters them. Neither run solves anything.
    #[test]
    fn a_stub_on_no_path_the_proof_takes_is_no_gap() {
        let Some((dir, _cp)) = defect_fixture() else { return };
        if !crate::jbmc::available("jbmc") {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "jbmc not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            return;
        }
        let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/jbmc-paths/P.java");
        let status = std::process::Command::new("javac").args(["-g", "-d"]).arg(dir.path()).arg(&source).status().unwrap();
        assert!(status.success(), "the fixture compiles");
        let run = |function: &str| JbmcRun {
            executable: "jbmc".into(),
            class: "P".into(),
            function: function.into(),
            classpath: vec![dir.path().to_path_buf(), Path::new(env!("CARGO_MANIFEST_DIR")).join("models/classes")],
            unwind: 5,
            timeout: Duration::from_secs(60),
            stage: None,
            refine_strings: false,
            sat_solver: None,
            log: dir.path().join(format!("{function}.log")),
            extra_args: Vec::new(),
            tells_exceptions: true,
        };
        let pre = preflight(&run("copied"), Duration::from_secs(60)).unwrap();
        let found = pre.found.as_ref().unwrap_or_else(|| panic!("{:?}", pre.problem));
        assert!(matches!(pre.paths, Some(Ok(_))), "{:?}", pre.paths);
        assert_eq!(found.records.iter().map(|r| r.id.as_str()).collect::<Vec<_>>(), Vec::<&str>::new(), "{}", pre.note());
        assert!(found.unreached.contains(&"java.util.Collection.isEmpty()".to_string()) && found.unreached.contains(&"java.util.Collection.toArray()".to_string()), "{:?}", found.unreached);
        assert!(pre.note().contains("never enters") && pre.note().contains("java.util.Collection.isEmpty()"), "{}", pre.note());
        let pre = preflight(&run("opaque"), Duration::from_secs(60)).unwrap();
        let found = pre.found.as_ref().unwrap();
        assert!(matches!(pre.paths, Some(Ok(_))), "{:?}", pre.paths);
        let ids: Vec<&str> = found.records.iter().map(|r| r.id.as_str()).collect();
        assert!(ids.iter().any(|id| id.starts_with("jdk-primitive-method:java.util.Collection.isEmpty()Z")), "{ids:?}");
    }

    /// The reproducer of job `20261107-012013`'s refusal of example 071's two proofs: JBMC 6.11.0's goto listing
    /// numbers an instruction's `bytecode-index` by its place in the method, not by its byte offset. `p.D.later`'s
    /// `getstatic Sub.value` is at offset 6, the method's fifth instruction (index 4), and its extra initializer is
    /// named there; `p.D.apart`'s `getstatic Quiet.value` is at offset 3, where index 3 is `getstatic Loud.value`,
    /// and none of its three reads, each through the class that declares it, is one. Nothing is solved.
    #[test]
    fn the_preflight_reads_jbmc_listing_by_instruction_index() {
        let Some((dir, _cp)) = defect_fixture() else { return };
        if !crate::jbmc::available("jbmc") {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "jbmc not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            return;
        }
        // The proof's harness is the tool's own, and the preflight reads the methods it calls.
        let harness = dir.path().join("H.java");
        std::fs::write(&harness, "class H { static int later(int n) { return p.D.later(n); } static int apart(int n) { return p.D.apart(n); } }").unwrap();
        let status = std::process::Command::new("javac").args(["-g", "-cp"]).arg(dir.path()).arg("-d").arg(dir.path()).arg(&harness).status().unwrap();
        assert!(status.success(), "the harness compiles");
        let run = |function: &str| JbmcRun {
            executable: "jbmc".into(),
            class: "H".into(),
            function: function.into(),
            classpath: vec![dir.path().to_path_buf(), Path::new(env!("CARGO_MANIFEST_DIR")).join("models/classes")],
            unwind: 5,
            timeout: Duration::from_secs(60),
            stage: None,
            refine_strings: false,
            sat_solver: None,
            log: dir.path().join(format!("{function}.log")),
            extra_args: Vec::new(),
            tells_exceptions: true,
        };
        let defects = |function: &str| -> Vec<(String, String)> {
            let pre = preflight(&run(function), Duration::from_secs(60)).unwrap();
            let found = pre.found.as_ref().unwrap_or_else(|| panic!("{:?}", pre.problem));
            found.defects.iter().map(|d| (d.kind.to_string(), d.site.clone())).collect()
        };
        assert_eq!(defects("later"), [("extra-initializer".to_string(), "p.D.later:27".to_string())]);
        assert_eq!(defects("apart"), []);
    }

    /// A listing of a class `S` whose `two` calls two stubs in sequence, at its second and fifth instructions, and
    /// whose `three` calls one at an instruction that calls another method (its fifth) and one where the listing
    /// gives no bytecode index.
    const PROBED_GOTO: &str = r#"S.two(int) /* java::S.two:(I)Ljava/lang/String; */
        // 1 file S.java line 3 function java::S.two:(I)Ljava/lang/String; bytecode-index 1
        CALL java::java.lang.Integer.toHexString:(I)Ljava/lang/String;(arg0i)
        // 2 file S.java line 4 function java::S.two:(I)Ljava/lang/String; bytecode-index 4
     2: CALL java::java.lang.Integer.toOctalString:(I)Ljava/lang/String;(arg0i)
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

S.three(int) /* java::S.three:(I)V */
        // 3 file S.java line 7 function java::S.three:(I)V bytecode-index 4
        CALL java::java.lang.Integer.toBinaryString:(I)Ljava/lang/String;(arg0i)
        // 4 no location
        CALL java::java.lang.Integer.toUnsignedString:(I)Ljava/lang/String;(arg0i)
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java.lang.Integer.toHexString(int) /* java::java.lang.Integer.toHexString:(I)Ljava/lang/String; */
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java.lang.Integer.toOctalString(int) /* java::java.lang.Integer.toOctalString:(I)Ljava/lang/String; */
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java.lang.Integer.toBinaryString(int) /* java::java.lang.Integer.toBinaryString:(I)Ljava/lang/String; */
        END_FUNCTION

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

java.lang.Integer.toUnsignedString(int) /* java::java.lang.Integer.toUnsignedString:(I)Ljava/lang/String; */
        END_FUNCTION
"#;

    /// `S` of [`PROBED_GOTO`], as bytecode.
    fn probed_class() -> Vec<u8> {
        use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
        use crate::classfile::{flags, Kind};
        let mut w = ClassWriter::new("S");
        let method = |w: &mut ClassWriter, name: &str, descriptor: &str, calls: &[&str], ret: Option<Kind>| {
            let mut code = CodeBuilder::new();
            for (k, call) in calls.iter().enumerate() {
                let m = w.pool.method_ref("java/lang/Integer", call, "(I)Ljava/lang/String;");
                code.load(Kind::Int, 0);
                code.op_u16(0xb8, m);
                if k + 1 < calls.len() || ret.is_none() {
                    code.op(0x57); // pop
                }
            }
            code.return_(ret);
            code.max_stack = 1;
            w.methods.push(MethodWriter { access: flags::STATIC, name: name.into(), descriptor: descriptor.into(), code: Some(code) });
        };
        method(&mut w, "two", "(I)Ljava/lang/String;", &["toHexString", "toOctalString"], Some(Kind::Ref));
        method(&mut w, "three", "(I)V", &["toBinaryString", "toUnsignedString"], None);
        w.to_bytes()
    }

    /// The probes of the preflight's third step: each call site of a stub goes to a method of its own that fails an
    /// assertion on a branch of its own and makes the call on the other, so the second of two stubs in sequence is
    /// still reached past the first's probe. A stub with a call site no probe can be placed at is not probed.
    #[test]
    fn a_probe_before_each_call_site_fails_on_a_branch_of_its_own_and_makes_the_call() {
        let p = parse_goto(PROBED_GOTO);
        assert_eq!(p.functions["java::S.three:(I)V"].unplaced.iter().collect::<Vec<_>>(), ["java::java.lang.Integer.toUnsignedString:(I)Ljava/lang/String;"]);
        let classes = tempfile::tempdir().unwrap();
        std::fs::write(classes.path().join("S.class"), probed_class()).unwrap();
        let mut cp = ClassPath::new().with_models(false);
        cp.add(classes.path()).unwrap();
        let stubs: BTreeSet<String> = p.functions.keys().filter(|id| id.starts_with("java::java.lang.Integer.")).cloned().collect();
        let dir = tempfile::tempdir().unwrap();
        let placed = place(&p, &cp, &stubs, dir.path()).unwrap();
        let hex = "java::java.lang.Integer.toHexString:(I)Ljava/lang/String;";
        let octal = "java::java.lang.Integer.toOctalString:(I)Ljava/lang/String;";
        assert_eq!(placed.stubs, BTreeMap::from([(hex.to_string(), BTreeSet::from([0])), (octal.to_string(), BTreeSet::from([1]))]));
        assert_eq!(placed.probes, 2);

        // The calls of `two` go to the probes, and `three`'s are as they were.
        let s = crate::classfile::ClassFile::parse(&std::fs::read(dir.path().join("S.class")).unwrap()).unwrap();
        let calls = |class: &crate::classfile::ClassFile, name: &str| -> Vec<String> {
            let code = class.methods.iter().find(|m| m.name == name).and_then(|m| m.code.as_ref()).unwrap();
            code.instructions().unwrap().into_iter().filter_map(|(_, insn)| match insn {
                Insn::InvokeStatic(i) | Insn::InvokeSpecial(i) => class.pool.member(i).ok().map(|m| format!("{}.{}", m.owner, m.name)),
                Insn::New(_) => Some("new".into()),
                Insn::AThrow => Some("athrow".into()),
                Insn::If(..) => Some("if".into()),
                _ => None,
            }).collect()
        };
        assert_eq!(calls(&s, "two"), ["jvmcontract/StubProbe.p0", "jvmcontract/StubProbe.p1"]);
        assert_eq!(calls(&s, "three"), ["java/lang/Integer.toBinaryString", "java/lang/Integer.toUnsignedString"]);
        let probes = crate::classfile::ClassFile::parse(&std::fs::read(dir.path().join("jvmcontract/StubProbe.class")).unwrap()).unwrap();
        assert_eq!(calls(&probes, "p1"), ["org/cprover/CProver.nondetBoolean", "if", "new", "java/lang/AssertionError.<init>", "athrow", "java/lang/Integer.toOctalString"]);
        assert_eq!(probes.methods.iter().find(|m| m.name == "p1").map(|m| m.descriptor.as_str()), Some("(I)Ljava/lang/String;"));

        // A probe run that shows the second unreached leaves out that one alone.
        let output = "[java::jvmcontract.StubProbe.p0:(I)Ljava/lang/String;.assertion.1] assertion at function java::jvmcontract.StubProbe.p0:(I)Ljava/lang/String; bytecode-index 7: FAILURE\n[java::jvmcontract.StubProbe.p1:(I)Ljava/lang/String;.assertion.1] assertion at function java::jvmcontract.StubProbe.p1:(I)Ljava/lang/String; bytecode-index 7: SUCCESS\nVERIFICATION FAILED\n";
        assert_eq!(probed(output, &placed).unwrap(), BTreeSet::from([octal.to_string()]));
    }

    /// The results of the probe run of step 2 of `llm-dlc/loops/stub-reachability.md` (job
    /// `20261107-233000-stub-reachability-step-1-can-jbmc-s-solv`), on VF-015's proof of `Hex#toDigit` under
    /// `--assume 'ch == 1632'`, with its probe, there `Reach.reach`, renamed to the preflight's.
    const PROBED_CASE: &str = "\
Runtime decision procedure: 0.0277424s

** Results:
function java::PropertyHarness.check:(CI)V
[java::PropertyHarness.check:(CI)V.assertion.1] assertion at function java::PropertyHarness.check:(CI)V bytecode-index 93: SUCCESS
[java::PropertyHarness.check:(CI)V.1] file PropertyHarness.java no uncaught exception: SUCCESS

function java::jvmcontract.StubProbe.p0:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;
[java::jvmcontract.StubProbe.p0:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;.assertion.1] assertion at function java::jvmcontract.StubProbe.p0:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String; bytecode-index 7: SUCCESS

** 0 of 3 failed (1 iterations)
VERIFICATION SUCCESSFUL
";

    /// The reproducer of VF-015's refusal: the symbolic execution of `Hex#toDigit`'s proof under `ch == 1632` enters
    /// the stub of `String.format`, on the exception path the assumption closes, and the probe at its one call site
    /// holds, so the stub is no gap. The same run without the assumption (the step's control), a probe whose outcome
    /// the output lacks, a stub one of whose probes fails, an unwinding assertion that fails, a run that ends without
    /// a verdict or out of time: none shows the stub unreached.
    #[test]
    fn a_stub_whose_every_probe_holds_is_unreached_and_nothing_else_tells() {
        let format = "java::java.lang.String.format:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;".to_string();
        let one = Placed { stubs: BTreeMap::from([(format.clone(), BTreeSet::from([0]))]), probes: 1 };
        assert_eq!(probed(PROBED_CASE, &one).unwrap(), BTreeSet::from([format.clone()]));
        let control = PROBED_CASE.replace("bytecode-index 7: SUCCESS", "bytecode-index 7: FAILURE").replace("VERIFICATION SUCCESSFUL", "VERIFICATION FAILED");
        assert_eq!(probed(&control, &one).unwrap(), BTreeSet::new());
        let absent = Placed { stubs: BTreeMap::from([(format.clone(), BTreeSet::from([3]))]), probes: 4 };
        assert_eq!(probed(PROBED_CASE, &absent).unwrap(), BTreeSet::new());
        let two = Placed { stubs: BTreeMap::from([(format.clone(), BTreeSet::from([0, 1]))]), probes: 2 };
        let second = "[java::jvmcontract.StubProbe.p1:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;.assertion.1] assertion at function java::jvmcontract.StubProbe.p1:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String; bytecode-index 7: FAILURE\n";
        assert_eq!(probed(&PROBED_CASE.replace("\n** 0 of", &format!("{second}\n** 0 of")), &two).unwrap(), BTreeSet::new());
        let cut = PROBED_CASE.replace("\n** 0 of", "[java::org.apache.commons.codec.binary.Hex.decodeHex:([C[B)I.unwind.0] file Hex.java line 120 unwinding assertion loop 0: FAILURE\n\n** 0 of");
        assert!(probed(&cut, &one).unwrap_err().contains("unwinding assertion java::org.apache.commons.codec.binary.Hex.decodeHex:([C[B)I.unwind.0 is FAILURE"), "{:?}", probed(&cut, &one));
        let held = PROBED_CASE.replace("\n** 0 of", "[java::org.apache.commons.codec.binary.Hex.decodeHex:([C[B)I.unwind.0] file Hex.java line 120 unwinding assertion loop 0: SUCCESS\n\n** 0 of");
        assert_eq!(probed(&held, &one).unwrap(), BTreeSet::from([format.clone()]));
        assert!(probed(&PROBED_CASE.replace("VERIFICATION SUCCESSFUL", ""), &one).unwrap_err().contains("no verdict"));
        let late = format!("{}\nError: jbmc did not finish within 3 s\n", PROBED_CASE.replace("VERIFICATION SUCCESSFUL\n", ""));
        assert_eq!(probed(&late, &one).unwrap_err(), "jbmc did not finish within 3 s");
    }

    /// A stub the solver shows no path reaches is no gap, and the note names why, apart from the stubs symbolic
    /// execution never enters.
    #[test]
    fn a_stub_the_solver_shows_unreached_is_no_gap_and_the_note_says_why() {
        let p = parse_goto(GOTO);
        let cp = ClassPath::new().with_models(false).with_default_jdk();
        if !cp.has_jdk() {
            return;
        }
        let entered: BTreeSet<String> = ["java::H.check:(I)V", "java::p.K.m:(I)I", "java::java.util.ArrayList.<init>:(I)V"].map(String::from).into();
        let solved = BTreeSet::from(["java::java.util.ArrayList.<init>:(I)V".to_string()]);
        let found = find_told(&p, "H", "check", &cp, Some("25"), Some(&entered), &solved, true).unwrap();
        assert_eq!(found.records.iter().map(|r| r.id.as_str()).collect::<Vec<_>>(), ["missing-body:p.K.m(I)I"]);
        assert_eq!((found.unreached.as_slice(), found.solved.as_slice()), (["java.util.ArrayList.<init>(int)".to_string()].as_slice(), ["java.util.ArrayList.<init>(int)".to_string()].as_slice()));
        let pre = Preflight { found: Some(found), problem: None, log: PathBuf::from("jbmc-goto.txt"), seconds: 0.2, paths: Some(Ok(0.1)), probes: Some(Ok(0.1)) };
        let note = pre.note();
        assert!(note.contains("its solver shows no path within the bounds and assumptions reaches") && note.contains("so no gap: java.util.ArrayList.<init>(int)") && !note.contains("never enters"), "{note}");
        let failed = Preflight { probes: Some(Err("it gave no verdict".into())), ..pre };
        assert!(failed.note().contains("could not tell (it gave no verdict): they stay gaps"), "{}", failed.note());
    }

    /// `tests/fixtures/jbmc-paths/P.java`'s `sequenced` through the preflight on JBMC 6.11.0: its first two stubs are
    /// called in sequence on every path, and the third only where `n * n == 7`, which no `int` meets (a square is 0,
    /// 1 or 4 modulo 8) and which symbolic execution, which does not solve, keeps. The probe of the first does not
    /// cut the path to the second, and the solver shows the third unreached.
    #[test]
    fn a_stub_behind_a_condition_only_the_solver_decides_is_no_gap() {
        let Some((dir, _cp)) = defect_fixture() else { return };
        if !crate::jbmc::available("jbmc") {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "jbmc not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            return;
        }
        let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/jbmc-paths/P.java");
        let status = std::process::Command::new("javac").args(["-g", "-d"]).arg(dir.path()).arg(&source).status().unwrap();
        assert!(status.success(), "the fixture compiles");
        let run = JbmcRun {
            executable: "jbmc".into(),
            class: "P".into(),
            function: "sequenced".into(),
            classpath: vec![dir.path().to_path_buf(), Path::new(env!("CARGO_MANIFEST_DIR")).join("models/classes")],
            unwind: 5,
            timeout: Duration::from_secs(60),
            stage: None,
            refine_strings: false,
            sat_solver: Some("cadical".into()),
            log: dir.path().join("sequenced.log"),
            extra_args: Vec::new(),
            tells_exceptions: true,
        };
        let pre = preflight(&run, Duration::from_secs(60)).unwrap();
        let found = pre.found.as_ref().unwrap_or_else(|| panic!("{:?}", pre.problem));
        assert!(matches!(pre.paths, Some(Ok(_))) && matches!(pre.probes, Some(Ok(_))), "{:?} {:?}\n{}", pre.paths, pre.probes, std::fs::read_to_string(dir.path().join("jbmc-probes.txt")).unwrap_or_default());
        let ids: Vec<&str> = found.records.iter().map(|r| r.id.as_str()).collect();
        assert!(ids.iter().any(|id| id.starts_with("jdk-static-method:java.lang.Integer.toHexString(I)")) && ids.iter().any(|id| id.starts_with("jdk-static-method:java.lang.Integer.toOctalString(I)")), "{ids:?}\n{}", pre.note());
        assert!(!ids.iter().any(|id| id.contains("toBinaryString")), "{ids:?}");
        assert!(found.solved.contains(&"java.lang.Integer.toBinaryString(int)".to_string()), "{:?}\n{}", found.solved, pre.note());
        assert!(pre.note().contains("its solver shows no path"), "{}", pre.note());
    }
}
