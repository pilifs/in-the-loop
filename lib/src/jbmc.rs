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
    pub stage: Option<String>,
    pub problem: Option<String>,
    pub log: PathBuf,
    pub seconds: f64,
}

impl JbmcResult {
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

/// The command line, for logs.
pub fn command(run: &JbmcRun) -> Vec<String> {
    let classpath = std::env::join_paths(&run.classpath).map(|p| p.to_string_lossy().into_owned()).unwrap_or_default();
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
    cmd.extend(run.extra_args.iter().cloned());
    cmd
}

/// Runs JBMC and parses its output.
pub fn run(run: &JbmcRun) -> Result<JbmcResult, Error> {
    let cmd = command(run);
    if !available(&run.executable) {
        return Ok(JbmcResult {
            verdict: Verdict::Unverifiable,
            version: "JBMC".into(),
            properties: 0,
            raw_inputs: BTreeMap::new(),
            stage: run.stage.clone(),
            problem: Some(format!("jbmc is not installed ({} not found)", run.executable)),
            log: run.log.clone(),
            seconds: 0.0,
        });
    }
    let started = std::time::Instant::now();
    let cwd = run.log.parent().filter(|p| !p.as_os_str().is_empty()).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let output = crate::tla::run_with_timeout(&cmd, &cwd, run.timeout)?;
    let seconds = started.elapsed().as_secs_f64();
    std::fs::write(&run.log, &output)?;
    let mut result = parse_output(&output, &run.class, &run.function, run.unwind, run.stage.clone());
    result.log = run.log.clone();
    result.seconds = seconds;
    if output.contains("did not finish within") {
        result.verdict = Verdict::Unverifiable;
        result.problem = Some(format!("JBMC did not finish within {} s", run.timeout.as_secs()));
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
        stage: stage.clone(),
        problem,
        log: PathBuf::new(),
        seconds: 0.0,
    };
    let Some(failed) = Regex::new(r"\*\* (\d+) of (\d+) failed").unwrap().captures(output) else {
        let tail = output.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("no output");
        return base(Verdict::Unverifiable, 0, Some(format!("JBMC produced no verdict: {tail}")));
    };
    let properties: u32 = failed[2].parse().unwrap_or(0);
    if failed[1].parse::<u32>().unwrap_or(1) == 0 {
        return base(Verdict::Verified, properties, None);
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
    result
}

/// Parses a primitive value as JBMC prints it in a trace (`17`, `-3l`, `'a'`, `true`, `1.5`).
pub fn parse_value(t: &Type, raw: &str) -> Result<Value, Error> {
    let s = raw.trim_end_matches(['L', 'l', 'F', 'f', 'D', 'd']);
    let bad = || Error::new(format!("cannot parse {raw:?} as {}", t.java_name()));
    Ok(match t {
        Type::Long => Value::Long(s.parse().map_err(|_| bad())?),
        Type::Int => Value::Int(s.parse().map_err(|_| bad())?),
        Type::Short => Value::Int(i32::from(s.parse::<i16>().map_err(|_| bad())?)),
        Type::Byte => Value::Int(i32::from(s.parse::<i8>().map_err(|_| bad())?)),
        Type::Char => {
            if let Some(c) = raw.strip_prefix('\'').and_then(|r| r.chars().next()) {
                Value::Int(c as i32)
            } else {
                Value::Int(s.parse::<i32>().map_err(|_| bad())? as u16 as i32)
            }
        }
        Type::Boolean => Value::Int((raw == "true" || raw == "1") as i32),
        Type::Double => Value::Double(s.parse().map_err(|_| bad())?),
        Type::Float => Value::Float(s.parse().map_err(|_| bad())?),
        other => return Err(Error::new(format!("not a primitive: {}", other.java_name()))),
    })
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

        let unwound = "[java::EquivalenceHarness.check:(JI)V.unwind.0] unwinding assertion loop 0: FAILURE\n** 1 of 37 failed\n";
        let r = parse_output(unwound, "EquivalenceHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Unverifiable);
        assert!(r.problem.unwrap().contains("not fully unwound"));

        let r = parse_output("JBMC version 6.11.0\nsomething went wrong\n", "EquivalenceHarness", "check", 16, None);
        assert_eq!(r.verdict, Verdict::Unverifiable);
    }
}
