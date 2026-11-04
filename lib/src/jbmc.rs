//! Running [JBMC](https://github.com/diffblue/cbmc), the bounded model checker for JVM bytecode, and reading its
//! verdict: proved (no property fails), a counterexample (the harness assertion fails, with the inputs from the
//! trace), or no verdict (a loop was not unwound, an unexpected property failed, a timeout).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::time::Duration;

use regex::Regex;
use serde::Serialize;

use crate::classfile::Type;
use crate::interp::Value;
use crate::{Error, Verdict};

/// One JBMC invocation.
#[derive(Debug, Clone)]
pub struct JbmcRun {
    pub executable: String,
    /// The harness class (default package) and the method in it.
    pub class: String,
    pub function: String,
    pub classpath: Vec<PathBuf>,
    pub unwind: u32,
    pub timeout: Duration,
    /// `--java-assume-inputs-interval`, such as `[0:20]`: a search stage over small inputs.
    pub stage: Option<String>,
    /// Whether JBMC's string solver is on. Off by default: with it on, JBMC replaces every call of
    /// `java.lang.Character` by an approximation of its own, in place of the class on the class path (the tool's
    /// model among them), and was seen to give such a call an arbitrary result; off, strings are opaque objects,
    /// which the proofs over primitives and arrays never look into.
    pub refine_strings: bool,
    /// The SAT solver JBMC is asked for (`--sat-solver`), `None` for its default. CaDiCaL by default: JBMC 6 bundles
    /// it, and the MiniSAT path JBMC takes with the string solver off stalled for minutes on a binary search over
    /// eight elements that CaDiCaL settles in a second. A build without the solver answers "unknown solver", and
    /// the run is repeated with the default.
    pub sat_solver: Option<String>,
    /// Where to write the log.
    pub log: PathBuf,
    pub extra_args: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct JbmcResult {
    pub verdict: Verdict,
    pub version: String,
    pub properties: u32,
    /// The counterexample's inputs by local-variable slot, as JBMC prints them.
    pub raw_inputs: BTreeMap<u32, String>,
    /// The counterexample's array inputs by slot: their elements as JBMC prints them, or `None` for `null`.
    pub raw_arrays: BTreeMap<u32, Option<Vec<String>>>,
    pub stage: Option<String>,
    pub problem: Option<String>,
    pub log: PathBuf,
    pub seconds: f64,
}

/// An argument of a counterexample: a primitive, an array of primitives, or `null`.
#[derive(Debug, Clone, PartialEq)]
pub enum Argument {
    Scalar(Value),
    Array(Vec<Value>),
    Null,
}

impl JbmcResult {
    /// The counterexample's arguments, in parameter order, arrays included.
    pub fn arguments(&self, params: &[Type]) -> Result<Vec<Argument>, Error> {
        let mut out = Vec::new();
        let mut slot = 0;
        for t in params {
            out.push(match t {
                Type::Array(element) => match self.raw_arrays.get(&slot) {
                    Some(Some(raw)) => Argument::Array(raw.iter().map(|r| parse_value(element, r)).collect::<Result<Vec<_>, _>>()?),
                    Some(None) => Argument::Null,
                    None => Argument::Array(Vec::new()),
                },
                _ => Argument::Scalar(parse_value(t, self.raw_inputs.get(&slot).map(String::as_str).unwrap_or("0"))?),
            });
            slot += u32::from(t.slots());
        }
        Ok(out)
    }

    /// The counterexample's arguments, in parameter order.
    pub fn inputs(&self, params: &[Type]) -> Result<Vec<Value>, Error> {
        let mut values = Vec::new();
        let mut slot = 0;
        for t in params {
            let raw = self.raw_inputs.get(&slot).map(String::as_str).unwrap_or("0");
            values.push(parse_value(t, raw)?);
            slot += u32::from(t.slots());
        }
        Ok(values)
    }
}

/// Whether `jbmc` can be run.
pub fn available(executable: &str) -> bool {
    std::process::Command::new(executable).arg("--version").output().map(|o| o.status.success()).unwrap_or(false)
}

/// An absolute path: JBMC runs in the work directory, so class path entries given relative to the current
/// directory must be resolved before they reach it.
pub fn absolute(path: &Path) -> PathBuf {
    if path.is_absolute() {
        return path.to_path_buf();
    }
    std::fs::canonicalize(path).unwrap_or_else(|_| std::env::current_dir().map(|d| d.join(path)).unwrap_or_else(|_| path.to_path_buf()))
}

/// The command line, for logs.
pub fn command(run: &JbmcRun) -> Vec<String> {
    let entries: Vec<PathBuf> = run.classpath.iter().map(|p| absolute(p)).collect();
    let classpath = std::env::join_paths(&entries).map(|p| p.to_string_lossy().into_owned()).unwrap_or_default();
    let mut cmd = vec![
        run.executable.clone(),
        run.class.clone(),
        "--function".into(),
        format!("{}.{}", run.class, run.function),
        "--classpath".into(),
        classpath,
        "--trace".into(),
        "--throw-runtime-exceptions".into(),
        "--unwind".into(),
        run.unwind.to_string(),
        "--unwinding-assertions".into(),
    ];
    if let Some(stage) = &run.stage {
        cmd.extend(["--java-assume-inputs-interval".into(), stage.clone()]);
    }
    if !run.refine_strings {
        cmd.push("--no-refine-strings".into());
    }
    if let Some(solver) = &run.sat_solver {
        cmd.extend(["--sat-solver".into(), solver.clone()]);
    }
    cmd.extend(run.extra_args.iter().cloned());
    cmd
}

/// The address space, in MiB, a JBMC run may use. One proof of a small method has reached 5.7 GB, and nothing in the
/// solver stops it short of the whole machine. That proof (examples 142 and 143) is the tool's own checker's now.
const DEFAULT_MEMORY_MB: u64 = 3072;

/// The limit on a JBMC run in MiB: `JVMCONTRACT_JBMC_MEMORY_MB`, or the default. 0 turns it off.
fn memory_limit_mb() -> Option<u64> {
    let configured = std::env::var("JVMCONTRACT_JBMC_MEMORY_MB").ok().and_then(|v| v.trim().parse().ok());
    Some(configured.unwrap_or(DEFAULT_MEMORY_MB)).filter(|mb| *mb > 0)
}

/// The command under a memory limit: past it allocation fails, and JBMC stops by itself. The shell then replaces
/// itself with JBMC, so a timeout's kill reaches it. Should the kernel run out of memory anyway, the raised
/// `oom_score_adj` makes JBMC its first choice, ahead of whatever launched it.
fn limited(cmd: Vec<String>, memory_mb: Option<u64>) -> Vec<String> {
    let Some(mb) = memory_mb.filter(|_| cfg!(unix)) else { return cmd };
    let script = r#"ulimit -v "$0" || exit 125; echo 1000 > /proc/self/oom_score_adj 2>/dev/null; exec "$@""#;
    let mut limited = vec!["sh".to_string(), "-c".into(), script.into(), (mb * 1024).to_string()];
    limited.extend(cmd);
    limited
}

/// Why the run gives no verdict although its output may read like one: it died before it could stand behind it.
fn abnormal_end(output: &str, memory_mb: Option<u64>) -> Option<String> {
    let limit = memory_mb.map(|mb| format!(" (the limit is {mb} MiB; JVMCONTRACT_JBMC_MEMORY_MB changes it)")).unwrap_or_default();
    if output.to_ascii_lowercase().contains("out of memory") || output.contains("bad_alloc") {
        return Some(format!("JBMC ran out of memory{limit}"));
    }
    if output.contains(crate::tla::KILLED_BY_SIGNAL) {
        return Some(format!("JBMC was killed before it finished, possibly for lack of memory{limit}"));
    }
    None
}

/// Runs JBMC and parses its output.
pub fn run(run: &JbmcRun) -> Result<JbmcResult, Error> {
    let memory_mb = memory_limit_mb();
    let cmd = limited(command(run), memory_mb);
    if !available(&run.executable) {
        return Ok(JbmcResult {
            verdict: Verdict::Unverifiable,
            version: "JBMC".into(),
            properties: 0,
            raw_inputs: BTreeMap::new(),
            raw_arrays: BTreeMap::new(),
            stage: run.stage.clone(),
            problem: Some(format!("jbmc is not installed ({} not found)", run.executable)),
            log: run.log.clone(),
            seconds: 0.0,
        });
    }
    let started = std::time::Instant::now();
    let cwd = run.log.parent().filter(|p| !p.as_os_str().is_empty()).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let mut output = crate::tla::run_with_timeout(&cmd, &cwd, run.timeout)?;
    if run.sat_solver.is_some() && output.contains("unknown solver '") {
        // This JBMC was built without the solver asked for: its own default will do.
        let fallback = JbmcRun { sat_solver: None, ..run.clone() };
        let note = format!("note: {}; running again with JBMC's default solver\n", output.lines().find(|l| l.contains("unknown solver")).unwrap_or_default().trim());
        output = note + &crate::tla::run_with_timeout(&limited(command(&fallback), memory_mb), &cwd, run.timeout)?;
    }
    let seconds = started.elapsed().as_secs_f64();
    std::fs::write(&run.log, &output)?;
    let mut result = parse_output(&output, &run.class, &run.function, run.unwind, run.stage.clone());
    result.log = run.log.clone();
    result.seconds = seconds;
    if output.contains("did not finish within") {
        result.verdict = Verdict::Unverifiable;
        result.problem = Some(format!("JBMC did not finish within {} s", run.timeout.as_secs()));
    } else if let Some(problem) = abnormal_end(&output, memory_mb) {
        result.verdict = Verdict::Unverifiable;
        result.problem = Some(problem);
    }
    Ok(result)
}

/// Parses JBMC's console output.
pub fn parse_output(output: &str, class: &str, function: &str, unwind: u32, stage: Option<String>) -> JbmcResult {
    let version = Regex::new(r"(?m)^JBMC version (\S+)").unwrap().captures(output).map(|c| format!("JBMC {}", &c[1])).unwrap_or_else(|| "JBMC".into());
    let base = |verdict: Verdict, properties: u32, problem: Option<String>| JbmcResult {
        verdict,
        version: version.clone(),
        properties,
        raw_inputs: BTreeMap::new(),
        raw_arrays: BTreeMap::new(),
        stage: stage.clone(),
        problem,
        log: PathBuf::new(),
        seconds: 0.0,
    };
    // A class path entry JBMC could not read makes every method in it a stub with an arbitrary result, and the
    // harness assertion then fails for no reason; that is no verdict.
    if let Some(c) = Regex::new(r"(?m)^Warning: failed to access directory '([^']*)'").unwrap().captures(output) {
        return base(Verdict::Unverifiable, 0, Some(format!("JBMC could not read the class path entry {}", &c[1])));
    }
    let Some(failed) = Regex::new(r"\*\* (\d+) of (\d+) failed").unwrap().captures(output) else {
        let tail = output.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("no output");
        return base(Verdict::Unverifiable, 0, Some(format!("JBMC produced no verdict: {tail}")));
    };
    let properties: u32 = failed[2].parse().unwrap_or(0);
    if failed[1].parse::<u32>().unwrap_or(1) == 0 {
        // "0 failed" is not a proof. A solver that gives up leaves every property as ERROR, none of them failed, and
        // JBMC ends with VERIFICATION ERROR; a run that stops after the count leaves no last line at all.
        if Regex::new(r"(?m)^VERIFICATION SUCCESSFUL\s*$").unwrap().is_match(output) {
            return base(Verdict::Verified, properties, None);
        }
        let tail = output.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("no output");
        return base(Verdict::Unverifiable, properties, Some(format!("JBMC produced no verdict: {tail}")));
    }
    let failures: Vec<String> = Regex::new(r"(?m)^\[([^\]]+)\] .*: FAILURE$").unwrap().captures_iter(output).map(|c| c[1].to_string()).collect();
    if let Some(unwound) = failures.iter().find(|f| f.contains(".unwind.")) {
        return base(Verdict::Unverifiable, properties, Some(format!("a loop was not fully unwound with --unwind {unwind} ({unwound})")));
    }
    let marker = format!("{class}.{function}");
    if !failures.iter().any(|f| f.contains(&marker) && f.contains("assertion")) {
        return base(Verdict::Unverifiable, properties, Some(format!("an unexpected property failed: {}", failures.join(", "))));
    }
    let mut result = base(Verdict::Violation, properties, None);
    for c in Regex::new(r"(?m)^\s*INPUT arg(\d+)[a-z]: (\S+)").unwrap().captures_iter(output) {
        if let Ok(slot) = c[1].parse::<u32>() {
            result.raw_inputs.insert(slot, c[2].to_string());
        }
    }
    result.raw_arrays = parse_arrays(output);
    result
}

/// The array inputs of a trace. JBMC prints an array argument as `INPUT arg0a: &dynamic_object` after assigning
/// the object's `length` and `data` fields, and the data array's elements, both whole (`dynamic_object$0={ 1, 2 }`)
/// and one by one (`dynamic_object$0[1L]=2`); the assignments before the `INPUT` line are the input.
fn parse_arrays(output: &str) -> BTreeMap<u32, Option<Vec<String>>> {
    let length = Regex::new(r"^\s*([A-Za-z0-9_$]+)\.length=(\d+)").unwrap();
    let data = Regex::new(r"^\s*([A-Za-z0-9_$]+)\.data=&?([A-Za-z0-9_$]+)").unwrap();
    let whole = Regex::new(r"^\s*([A-Za-z0-9_$]+)=\{ ?([^{}.]*?) ?\}").unwrap();
    let element = Regex::new(r"^\s*([A-Za-z0-9_$]+)\[(\d+)L?\]=(.+?) \(").unwrap();
    let input = Regex::new(r"^\s*INPUT arg(\d+)[a-z]: (?:&([A-Za-z0-9_$]+)|(null))").unwrap();
    let mut lengths: BTreeMap<String, usize> = BTreeMap::new();
    let mut datas: BTreeMap<String, String> = BTreeMap::new();
    let mut elements: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut arrays = BTreeMap::new();
    for line in output.lines() {
        if let Some(c) = input.captures(line) {
            let Ok(slot) = c[1].parse::<u32>() else { continue };
            if c.get(3).is_some() {
                arrays.insert(slot, None);
                continue;
            }
            let object = &c[2];
            let len = lengths.get(object).copied().unwrap_or(0);
            let mut values = datas.get(object).and_then(|d| elements.get(d)).cloned().unwrap_or_default();
            values.resize(len, "0".into());
            arrays.insert(slot, Some(values));
        } else if let Some(c) = length.captures(line) {
            lengths.insert(c[1].to_string(), c[2].parse().unwrap_or(0));
        } else if let Some(c) = data.captures(line) {
            datas.insert(c[1].to_string(), c[2].to_string());
        } else if let Some(c) = whole.captures(line) {
            let values: Vec<String> = if c[2].trim().is_empty() { Vec::new() } else { c[2].split(", ").map(str::to_string).collect() };
            elements.insert(c[1].to_string(), values);
        } else if let Some(c) = element.captures(line) {
            let Ok(index) = c[2].parse::<usize>() else { continue };
            let values = elements.entry(c[1].to_string()).or_default();
            if values.len() <= index {
                values.resize(index + 1, "0".into());
            }
            values[index] = c[3].to_string();
        }
    }
    arrays
}

/// Parses a primitive value as JBMC prints it in a trace (`17`, `-3l`, `'a'`, `'\u0000'`, `true`, `1.5f`,
/// `Float.NaN`, `-Double.POSITIVE_INFINITY`, and an array element's `(byte)-128`).
pub fn parse_value(t: &Type, raw: &str) -> Result<Value, Error> {
    // An array element carries its type as a cast: `(byte)-128`, `(short)7`.
    let raw = match raw.strip_prefix('(').and_then(|r| r.split_once(')')) {
        Some(("byte" | "short" | "char" | "int" | "long", rest)) => rest.trim_start(),
        _ => raw,
    };
    let s = raw.trim_end_matches(['L', 'l', 'F', 'f', 'D', 'd']);
    let bad = || Error::new(format!("cannot parse {raw:?} as {}", t.java_name()));
    Ok(match t {
        Type::Long => Value::Long(s.parse().map_err(|_| bad())?),
        Type::Int => Value::Int(s.parse().map_err(|_| bad())?),
        Type::Short => Value::Int(i32::from(s.parse::<i16>().map_err(|_| bad())?)),
        Type::Byte => Value::Int(i32::from(s.parse::<i8>().map_err(|_| bad())?)),
        Type::Char => {
            if let Some(literal) = raw.strip_prefix('\'').and_then(|r| r.strip_suffix('\'')) {
                Value::Int(parse_char_literal(literal).ok_or_else(bad)?)
            } else {
                Value::Int(s.parse::<i32>().map_err(|_| bad())? as u16 as i32)
            }
        }
        Type::Boolean => Value::Int((raw == "true" || raw == "1") as i32),
        Type::Double => Value::Double(parse_special(raw).map(|f| f as f64).or_else(|| s.parse().ok()).ok_or_else(bad)?),
        Type::Float => Value::Float(parse_special(raw).or_else(|| s.parse().ok()).ok_or_else(bad)?),
        other => return Err(Error::new(format!("not a primitive: {}", other.java_name()))),
    })
}

/// The body of a Java char literal as JBMC prints it: `a`, `\n`, `\'`, `\\`, `\u0000`.
fn parse_char_literal(literal: &str) -> Option<i32> {
    let mut chars = literal.chars();
    let first = chars.next()?;
    if first != '\\' {
        return (chars.next().is_none()).then_some(first as i32);
    }
    let escaped = chars.next()?;
    let rest: String = chars.collect();
    Some(match escaped {
        'u' => i32::from(u16::from_str_radix(&rest, 16).ok()?),
        'n' if rest.is_empty() => '\n' as i32,
        't' if rest.is_empty() => '\t' as i32,
        'r' if rest.is_empty() => '\r' as i32,
        'b' if rest.is_empty() => 8,
        'f' if rest.is_empty() => 12,
        '0' if rest.is_empty() => 0,
        '\'' | '"' | '\\' if rest.is_empty() => escaped as i32,
        _ => return None,
    })
}

/// `Float.NaN`, `Double.POSITIVE_INFINITY` and the like, with an optional sign.
fn parse_special(raw: &str) -> Option<f32> {
    let (negative, name) = match raw.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, raw),
    };
    let name = name.strip_prefix("Float.").or_else(|| name.strip_prefix("Double.")).unwrap_or(name);
    let value = match name {
        "NaN" | "nan" => f32::NAN,
        "POSITIVE_INFINITY" | "Infinity" | "inf" => f32::INFINITY,
        "NEGATIVE_INFINITY" | "-Infinity" | "-inf" => f32::NEG_INFINITY,
        _ => return None,
    };
    Some(if negative { -value } else { value })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_verdicts() {
        let proved = "JBMC version 6.11.0 (cbmc-6.11.0)\n** 0 of 37 failed (1 iterations)\nVERIFICATION SUCCESSFUL\n";
        let r = parse_output(proved, "EquivalenceHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Verified);
        assert_eq!(r.properties, 37);
        assert_eq!(r.version, "JBMC 6.11.0");

        // JBMC names the inputs by local-variable slot: a long in slot 0 puts the int in slot 2.
        let refuted = "JBMC version 6.11.0\n[EquivalenceHarness.check:(JI)V.assertion.1] line 1 assertion at file EquivalenceHarness.java line 1 function java::EquivalenceHarness.check:(JI)V bytecode-index 60: FAILURE\n  INPUT arg0a: 17l\n  INPUT arg2a: 6\n** 1 of 37 failed (2 iterations)\nVERIFICATION FAILED\n";
        let r = parse_output(refuted, "EquivalenceHarness", "check", 16, Some("[0:20]".into()));
        assert_eq!(r.verdict, Verdict::Violation);
        assert_eq!(r.inputs(&[Type::Long, Type::Int]).unwrap(), vec![Value::Long(17), Value::Int(6)]);

        // What JBMC prints when its solver runs out of memory: nothing failed, and nothing was proved.
        let gave_up = "JBMC version 6.11.0\nSolver ran out of memory during propositional reduction.\n[EquivalenceHarness.check:(JI)V.assertion.1] assertion: ERROR\n** 0 of 4 failed (1 iterations)\nVERIFICATION ERROR\n";
        let r = parse_output(gave_up, "EquivalenceHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Unverifiable);
        assert_eq!(r.problem.as_deref(), Some("JBMC produced no verdict: VERIFICATION ERROR"));

        // A count with no last line is no proof either.
        let cut_off = parse_output("** 0 of 4 failed (1 iterations)\n", "EquivalenceHarness", "check", 16, None);
        assert_eq!(cut_off.verdict, Verdict::Unverifiable);

        let unwound = "[java::EquivalenceHarness.check:(JI)V.unwind.0] unwinding assertion loop 0: FAILURE\n** 1 of 37 failed\n";
        let r = parse_output(unwound, "EquivalenceHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Unverifiable);
        assert!(r.problem.unwrap().contains("not fully unwound"));

        let r = parse_output("JBMC version 6.11.0\nsomething went wrong\n", "EquivalenceHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Unverifiable);

        // A missing class path entry would otherwise look like a counterexample.
        let unreadable = "JBMC version 6.11.0\nParsing ...\nWarning: failed to access directory 'build/main'\n[PropertyHarness.check:(I)V.assertion.1] assertion: FAILURE\n  INPUT arg0a: 1\n** 1 of 2 failed\n";
        let r = parse_output(unreadable, "PropertyHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Unverifiable);
        assert_eq!(r.problem.as_deref(), Some("JBMC could not read the class path entry build/main"));
    }

    #[test]
    fn parses_array_inputs() {
        let trace = "JBMC version 6.11.0\n[PropertyHarness.check:([II)V.assertion.1] assertion: FAILURE\n\
            Trace for java::PropertyHarness.check:([II)V.assertion.1:\n\
            State 17 file PropertyHarness.java function __CPROVER__start line 12 thread 0\n\
              dynamic_object={ .@java.lang.Object={ .@class_identifier=\"java::java.lang.Class\" },\n    .length=0, .data=null } ({ { ? }, 0, 0 })\n\
              dynamic_object.length=0 (00000000)\n  dynamic_object.data=null (00000000)\n  arg0a=&dynamic_object (00000000)\n\
              dynamic_object.length=3 (00000000 00000000 00000000 00000011)\n  dynamic_object.data=dynamic_array (00000000)\n\
              dynamic_array={ 0, 0, 0 } ({ 0, 0, 0 })\n  dynamic_object$0={ 0, 0, 0 } ({ 0, 0, 0 })\n  dynamic_object$0[0L]=0 (0)\n\
              dynamic_object$0={ -2147483646, 2, 19 } ({ 1, 1, 1 })\n  dynamic_object$0[0L]=-2147483646 (10000000)\n  dynamic_object$0[1L]=2 (00000010)\n  dynamic_object$0[2L]=19 (00010011)\n\
              dynamic_object.data=dynamic_object$0 (00000100)\n  INPUT arg0a: &dynamic_object (00000010)\n  arg1i=19 (00010011)\n  INPUT arg1i: 19 (00010011)\n\
              dynamic_object$0[1L]=7 (00000111)\n** 1 of 5 failed (2 iterations)\nVERIFICATION FAILED\n";
        let r = parse_output(trace, "PropertyHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Violation);
        let args = r.arguments(&[Type::Array(Box::new(Type::Int)), Type::Int]).unwrap();
        assert_eq!(args, vec![Argument::Array(vec![Value::Int(-2147483646), Value::Int(2), Value::Int(19)]), Argument::Scalar(Value::Int(19))], "the elements before INPUT, not the store after it");

        let null = "[PropertyHarness.check:([II)V.assertion.1] assertion: FAILURE\n  INPUT arg0a: null (00000000)\n  INPUT arg1i: 5 (00000101)\n** 1 of 2 failed\n";
        let r = parse_output(null, "PropertyHarness", "check", 16, None);
        assert_eq!(r.arguments(&[Type::Array(Box::new(Type::Int)), Type::Int]).unwrap(), vec![Argument::Null, Argument::Scalar(Value::Int(5))]);

        let empty = "[PropertyHarness.check:([II)V.assertion.1] assertion: FAILURE\n  dynamic_object.length=0 (0)\n  dynamic_object.data=null (0)\n  INPUT arg0a: &dynamic_object (0)\n  INPUT arg1i: 5 (00000101)\n** 1 of 2 failed\n";
        let r = parse_output(empty, "PropertyHarness", "check", 16, None);
        assert_eq!(r.arguments(&[Type::Array(Box::new(Type::Int)), Type::Int]).unwrap(), vec![Argument::Array(Vec::new()), Argument::Scalar(Value::Int(5))]);
    }

    #[test]
    fn parses_the_values_jbmc_prints() {
        assert_eq!(parse_value(&Type::Char, "'a'").unwrap(), Value::Int(97));
        assert_eq!(parse_value(&Type::Char, "'\\u0000'").unwrap(), Value::Int(0));
        assert_eq!(parse_value(&Type::Char, "'\\u07ff'").unwrap(), Value::Int(0x7ff));
        assert_eq!(parse_value(&Type::Char, "'\\n'").unwrap(), Value::Int(10));
        assert_eq!(parse_value(&Type::Char, "'\\\\'").unwrap(), Value::Int(92));
        assert_eq!(parse_value(&Type::Char, "65").unwrap(), Value::Int(65));
        assert_eq!(parse_value(&Type::Char, "'\\b'").unwrap(), Value::Int(8));
        assert_eq!(parse_value(&Type::Byte, "(byte)-128").unwrap(), Value::Int(-128), "an array element carries a cast");
        assert_eq!(parse_value(&Type::Short, "(short)7").unwrap(), Value::Int(7));
        assert!(matches!(parse_value(&Type::Float, "Float.NaN").unwrap(), Value::Float(f) if f.is_nan()));
        assert!(matches!(parse_value(&Type::Float, "-Float.POSITIVE_INFINITY").unwrap(), Value::Float(f) if f == f32::NEG_INFINITY));
        assert!(matches!(parse_value(&Type::Double, "Double.NaN").unwrap(), Value::Double(f) if f.is_nan()));
        assert_eq!(parse_value(&Type::Float, "1.5f").unwrap(), Value::Float(1.5));
        assert_eq!(parse_value(&Type::Double, "-0.0").unwrap(), Value::Double(-0.0));
        assert!(parse_value(&Type::Float, "Float.MAX").is_err());
    }

    #[test]
    fn class_path_entries_are_made_absolute() {
        let run = JbmcRun {
            executable: "jbmc".into(),
            class: "PropertyHarness".into(),
            function: "check".into(),
            classpath: vec![PathBuf::from("build/main"), PathBuf::from("/tmp/work/harness")],
            unwind: 16,
            timeout: Duration::from_secs(1),
            stage: None,
            refine_strings: false,
            sat_solver: Some("cadical".into()),
            log: PathBuf::from("/tmp/work/jbmc.log"),
            extra_args: Vec::new(),
        };
        let cmd = command(&run);
        let classpath = &cmd[cmd.iter().position(|a| a == "--classpath").unwrap() + 1];
        assert!(classpath.starts_with('/'), "{classpath}");
        assert!(classpath.contains("/build/main") && classpath.ends_with("/tmp/work/harness"), "{classpath}");
        assert!(cmd.contains(&"--no-refine-strings".to_string()), "the string solver is off unless asked for");
        let mut refined = run.clone();
        refined.refine_strings = true;
        assert!(!command(&refined).contains(&"--no-refine-strings".to_string()));
        assert!(cmd.windows(2).any(|w| w == ["--sat-solver", "cadical"]));
        let mut plain = run.clone();
        plain.sat_solver = None;
        assert!(!command(&plain).contains(&"--sat-solver".to_string()));
    }

    /// A run of a stand-in for JBMC, whose body follows the answer to `--version`.
    #[cfg(unix)]
    fn stand_in(dir: &Path, name: &str, body: &str) -> JbmcResult {
        use std::os::unix::fs::PermissionsExt;
        let executable = dir.join(name);
        std::fs::write(&executable, format!("#!/bin/sh\n[ \"$1\" = --version ] && exit 0\n{body}\n")).unwrap();
        std::fs::set_permissions(&executable, std::fs::Permissions::from_mode(0o755)).unwrap();
        run(&JbmcRun {
            executable: executable.to_string_lossy().into_owned(),
            class: "PropertyHarness".into(),
            function: "check".into(),
            classpath: Vec::new(),
            unwind: 16,
            timeout: Duration::from_secs(30),
            stage: None,
            refine_strings: false,
            sat_solver: Some("cadical".into()),
            log: dir.join(format!("{name}.log")),
            extra_args: Vec::new(),
        })
        .unwrap()
    }

    #[cfg(unix)]
    #[test]
    fn a_run_that_dies_gives_no_verdict_whatever_it_printed() {
        let dir = tempfile::tempdir().unwrap();
        let proved = "echo '** 0 of 3 failed (1 iterations)'; echo 'VERIFICATION SUCCESSFUL'";

        let r = stand_in(dir.path(), "fine", proved);
        assert_eq!(r.verdict, Verdict::Verified, "{:?}", r.problem);

        let r = stand_in(dir.path(), "killed", &format!("{proved}\nkill -9 $$"));
        assert_eq!(r.verdict, Verdict::Unverifiable);
        assert!(r.problem.unwrap().contains("killed before it finished"));

        let r = stand_in(dir.path(), "starved", &format!("{proved}\necho 'Out of memory'\nexit 6"));
        assert_eq!(r.verdict, Verdict::Unverifiable);
        assert!(r.problem.unwrap().contains("ran out of memory"));

        let solver = "echo 'SAT checker ran out of memory'; echo '** 0 of 3 failed (1 iterations)'; echo 'VERIFICATION ERROR'; exit 6";
        let r = stand_in(dir.path(), "solver", solver);
        assert_eq!(r.verdict, Verdict::Unverifiable);
        assert!(r.problem.unwrap().contains("ran out of memory"));
    }

    #[cfg(unix)]
    #[test]
    fn a_run_is_limited_and_goes_first_when_memory_runs_out() {
        let dir = tempfile::tempdir().unwrap();
        let r = stand_in(dir.path(), "probe", "ulimit -v; cat /proc/self/oom_score_adj; echo '** 0 of 1 failed'; echo 'VERIFICATION SUCCESSFUL'");
        assert_eq!(r.verdict, Verdict::Verified, "{:?}", r.problem);
        let log = std::fs::read_to_string(&r.log).unwrap();
        assert!(log.lines().next().unwrap().parse::<u64>().unwrap() < u64::MAX / 1024, "{log}");
        assert_eq!(log.lines().nth(1), Some("1000"), "{log}");
    }

    #[cfg(unix)]
    #[test]
    fn a_jbmc_without_the_solver_asked_for_is_run_again_with_its_own() {
        let dir = tempfile::tempdir().unwrap();
        let body = "for a in \"$@\"; do [ \"$a\" = --sat-solver ] && { echo \"unknown solver 'cadical'\"; exit 1; }; done; echo '** 0 of 3 failed (1 iterations)'; echo 'VERIFICATION SUCCESSFUL'";
        let r = stand_in(dir.path(), "minisat-only", body);
        assert_eq!(r.verdict, Verdict::Verified, "{:?}", r.problem);
        let log = std::fs::read_to_string(&r.log).unwrap();
        assert!(log.starts_with("note: unknown solver 'cadical'; running again"), "{log}");
    }

    #[test]
    fn the_limit_is_left_out_when_turned_off() {
        assert_eq!(limited(vec!["jbmc".into()], None), vec!["jbmc".to_string()]);
    }
}
