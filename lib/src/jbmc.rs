//! Running [JBMC](https://github.com/diffblue/cbmc), the bounded model checker for JVM bytecode, and reading its
//! verdict: proved (no property fails), a counterexample (the harness assertion fails, with the inputs from the
//! trace), or no verdict, each kind of which is an [`Ending`] of its own (step 4b of
//! `llm-dlc/loops/sound-verdicts.md`).
//!
//! JBMC is read through `--json-ui` ([`parse_json`]): one JSON array of its messages, the property results with the
//! trace of each failed one, and the overall `cProverStatus`, as CBMC 6.11.0 writes them (`report_util.cpp`,
//! `json_goto_trace.cpp`, `json_expr.cpp`). A trace's values are read from their bits, not from how Java would print
//! them. The text parser ([`parse_output`]) is kept, as `JVMCONTRACT_JBMC_READ=text`, until a differential test over
//! every recorded JBMC example shows the two agree: `JVMCONTRACT_JBMC_READ=both` runs JBMC both ways, decides by the
//! JSON, and writes what each reading made of the run next to the log ([`Differential`]).

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
    /// How JBMC's output is read: [`Reading::from_env`] in the proof drivers.
    pub read: Reading,
}

/// How JBMC's output is read: through `--json-ui` (the default), as text, or both ways for a differential test.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Reading {
    Json,
    Text,
    /// JBMC run twice, with `--json-ui` and without, the JSON deciding; what each reading made of the run is
    /// written to `<log>.differential.json`, and appended to the file `JVMCONTRACT_JBMC_DIFFERENTIAL` names. The
    /// second run gets a budget of its own, so a check takes up to twice its deadline: a test mode.
    Both,
}

impl Reading {
    /// `JVMCONTRACT_JBMC_READ`: `json` (the default), `text` or `both`.
    pub fn from_env() -> Reading {
        match std::env::var("JVMCONTRACT_JBMC_READ").ok().as_deref().map(str::trim) {
            Some("text") => Reading::Text,
            Some("both") => Reading::Both,
            _ => Reading::Json,
        }
    }
}

/// How a run ended, before anything else is made of it: the kinds of no verdict stay apart, since each calls for
/// something else (a larger bound, more time or memory, another solver, a program JBMC can take).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Ending {
    /// Every property holds: the proof.
    Verified,
    /// The harness's assertion fails, with a trace.
    Counterexample,
    /// An unwinding assertion fails: a loop runs past `--unwind`.
    UnwindingFailure,
    /// Some other property fails, one the harness does not state (an exception check JBMC adds, say).
    OtherFailure,
    /// Killed at its budget.
    Timeout,
    /// Out of memory: the address-space limit, or the solver's own report.
    MemoryExhausted,
    /// Killed by a signal before it finished, possibly the kernel's out-of-memory killer.
    Killed,
    /// Nothing failed and nothing was proved: the solver gave up, or a property was left unknown.
    SolverFailure,
    /// JBMC could not take the program: an unreadable class path entry, a class or method it could not load or
    /// convert, an option it refused.
    UnsupportedInput,
    /// JBMC is not installed.
    Unavailable,
    /// Output that says none of these, cut off or of another shape.
    Unreadable,
    /// The tool's own checker gave no verdict for a reason of its own: a gap refused, a construct outside its
    /// fragment, its path budget.
    NoVerdict,
}

impl Ending {
    /// How a run of the tool's own checker ended, from its verdict and reason.
    pub fn of_native(verdict: Verdict, problem: Option<&str>) -> Ending {
        match verdict {
            Verdict::Verified => Ending::Verified,
            Verdict::Violation => Ending::Counterexample,
            Verdict::Unverifiable => match problem {
                Some(p) if p.contains("did not finish within") => Ending::Timeout,
                Some(p) if p.contains("not fully unwound") || p.contains("unwind") => Ending::UnwindingFailure,
                _ => Ending::NoVerdict,
            },
        }
    }
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
    /// The tool's own checker's account of its search, when it gave the result rather than JBMC.
    pub native: Option<crate::bmc::Stats>,
    /// The gaps the run met, refused or assumed: the tool's own checker's ([`crate::bmc::gaps`]), or JBMC's own
    /// approximations, from the preflight of its goto program ([`crate::jbmc_gaps`]).
    pub gaps: Vec<crate::bmc::gaps::GapRecord>,
    /// The gap mode the checker ran under; `None` for a JBMC run that was not held to its preflight (a preliminary
    /// stage, a test of the reader).
    pub gap_mode: Option<crate::bmc::gaps::GapMode>,
    /// How the run ended.
    pub ending: Ending,
}

/// An argument of a counterexample: a primitive, an array of primitives, or `null`.
#[derive(Debug, Clone, PartialEq)]
pub enum Argument {
    Scalar(Value),
    Array(Vec<Value>),
    Null,
}

impl JbmcResult {
    /// Whether the run gave no verdict for want of time: JBMC killed at its budget, or the own checker or its
    /// solver past the deadline. A preliminary stage that ran out of time hands on to the next
    /// ([`crate::deadline`]); any other no-verdict ends the search.
    pub fn out_of_time(&self) -> bool {
        self.verdict == Verdict::Unverifiable && self.ending == Ending::Timeout
    }

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
    if run.read == Reading::Json {
        cmd.push("--json-ui".into());
    }
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
pub(crate) fn memory_limit_mb() -> Option<u64> {
    let configured = std::env::var("JVMCONTRACT_JBMC_MEMORY_MB").ok().and_then(|v| v.trim().parse().ok());
    Some(configured.unwrap_or(DEFAULT_MEMORY_MB)).filter(|mb| *mb > 0)
}

/// The command under a memory limit: past it allocation fails, and JBMC stops by itself. The shell then replaces
/// itself with JBMC, so a timeout's kill reaches it. Should the kernel run out of memory anyway, the raised
/// `oom_score_adj` makes JBMC its first choice, ahead of whatever launched it.
pub(crate) fn limited(cmd: Vec<String>, memory_mb: Option<u64>) -> Vec<String> {
    let Some(mb) = memory_mb.filter(|_| cfg!(unix)) else { return cmd };
    let script = r#"ulimit -v "$0" || exit 125; echo 1000 > /proc/self/oom_score_adj 2>/dev/null; exec "$@""#;
    let mut limited = vec!["sh".to_string(), "-c".into(), script.into(), (mb * 1024).to_string()];
    limited.extend(cmd);
    limited
}

/// Why the run gives no verdict although its output may read like one: it died before it could stand behind it.
fn abnormal_end(output: &str, memory_mb: Option<u64>) -> Option<(Ending, String)> {
    let limit = memory_mb.map(|mb| format!(" (the limit is {mb} MiB; JVMCONTRACT_JBMC_MEMORY_MB changes it)")).unwrap_or_default();
    if output.to_ascii_lowercase().contains("out of memory") || output.contains("bad_alloc") {
        return Some((Ending::MemoryExhausted, format!("JBMC ran out of memory{limit}")));
    }
    if output.contains(crate::tla::KILLED_BY_SIGNAL) {
        return Some((Ending::Killed, format!("JBMC was killed before it finished, possibly for lack of memory{limit}")));
    }
    None
}

/// Runs JBMC and reads its output as `run.read` says.
pub fn run(run: &JbmcRun) -> Result<JbmcResult, Error> {
    if run.read != Reading::Both {
        return run_once(run);
    }
    let json = run_once(&JbmcRun { read: Reading::Json, ..run.clone() })?;
    let text = run_once(&JbmcRun { read: Reading::Text, log: sibling(&run.log, "text.log"), ..run.clone() })?;
    let d = Differential::of(run, &json, &text);
    let record = serde_json::to_string(&d).map_err(|e| Error::new(e.to_string()))?;
    std::fs::write(sibling(&run.log, "differential.json"), format!("{record}\n"))?;
    if let Some(file) = std::env::var_os("JVMCONTRACT_JBMC_DIFFERENTIAL").filter(|f| !f.is_empty()) {
        use std::io::Write;
        let mut f = std::fs::OpenOptions::new().create(true).append(true).open(file)?;
        writeln!(f, "{record}")?;
    }
    Ok(json)
}

/// `jbmc.log` with its extension replaced by `ext`: `jbmc.text.log`, `jbmc.differential.json`.
fn sibling(log: &Path, ext: &str) -> PathBuf {
    let stem = log.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "jbmc".into());
    log.with_file_name(format!("{stem}.{ext}"))
}

/// What one reading made of a run: its account of it, for [`Differential`].
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct Account {
    pub verdict: Verdict,
    pub ending: Ending,
    pub properties: u32,
    /// The counterexample's inputs by slot, each value in one canonical form ([`canonical`]), arrays as lists.
    pub inputs: BTreeMap<u32, String>,
    pub problem: Option<String>,
}

/// What the JSON and the text reading made of one run of JBMC each, and whether they agree: the same verdict,
/// the same counterexample, and the same ending, except that the text may not tell an unreadable output from one
/// the JSON names (an error before any result, as JBMC refusing the program).
#[derive(Debug, Clone, Serialize)]
pub struct Differential {
    pub class: String,
    pub function: String,
    pub stage: Option<String>,
    pub log: PathBuf,
    pub json: Account,
    pub text: Account,
    pub agree: bool,
    pub differences: Vec<String>,
}

impl Differential {
    pub fn of(run: &JbmcRun, json: &JbmcResult, text: &JbmcResult) -> Differential {
        let read = |r: &JbmcResult| Account {
            verdict: r.verdict,
            ending: r.ending,
            properties: r.properties,
            inputs: canonical_inputs(r),
            problem: r.problem.clone(),
        };
        let (j, t) = (read(json), read(text));
        let mut differences = Vec::new();
        if j.verdict != t.verdict {
            differences.push(format!("verdict: {:?} from the JSON, {:?} from the text", j.verdict, t.verdict));
        }
        let finer = t.ending == Ending::Unreadable && j.verdict == Verdict::Unverifiable && t.verdict == Verdict::Unverifiable;
        if j.ending != t.ending && !finer {
            differences.push(format!("ending: {:?} from the JSON, {:?} from the text", j.ending, t.ending));
        }
        if j.verdict == Verdict::Violation && j.inputs != t.inputs {
            differences.push(format!("counterexample: {:?} from the JSON, {:?} from the text", j.inputs, t.inputs));
        }
        if j.properties != t.properties && j.ending != Ending::UnsupportedInput {
            differences.push(format!("properties: {} from the JSON, {} from the text", j.properties, t.properties));
        }
        Differential {
            class: run.class.clone(),
            function: run.function.clone(),
            stage: run.stage.clone(),
            log: run.log.clone(),
            agree: differences.is_empty(),
            json: j,
            text: t,
            differences,
        }
    }
}

fn canonical_inputs(r: &JbmcResult) -> BTreeMap<u32, String> {
    let mut out: BTreeMap<u32, String> = r.raw_inputs.iter().filter(|(slot, _)| !r.raw_arrays.contains_key(slot)).map(|(slot, v)| (*slot, canonical(v))).collect();
    for (slot, array) in &r.raw_arrays {
        out.insert(*slot, match array {
            Some(values) => format!("[{}]", values.iter().map(|v| canonical(v)).collect::<Vec<_>>().join(", ")),
            None => "null".into(),
        });
    }
    out
}

/// A value as either reading gives it, in one form: `17l`, `(byte)-128`, `'a'` and `true` as the numbers they are
/// (`17`, `-128`, `97`, `1`), a floating-point value as Rust prints the `f64` it is, and a special one by name.
pub fn canonical(raw: &str) -> String {
    let raw = raw.trim();
    let raw = match raw.strip_prefix('(').and_then(|r| r.split_once(')')) {
        Some(("byte" | "short" | "char" | "int" | "long" | "float" | "double" | "boolean", rest)) => rest.trim_start(),
        _ => raw,
    };
    if let Some(literal) = raw.strip_prefix('\'').and_then(|r| r.strip_suffix('\'')) {
        if let Some(c) = parse_char_literal(literal) {
            return c.to_string();
        }
    }
    match raw {
        "true" => return "1".into(),
        "false" => return "0".into(),
        _ => {}
    }
    if let Some(f) = parse_special(raw) {
        return if f.is_nan() { "NaN".into() } else { format!("{f}") };
    }
    let s = raw.trim_end_matches(['L', 'l', 'F', 'f', 'D', 'd']);
    if let Ok(i) = s.parse::<i128>() {
        return i.to_string();
    }
    if let Ok(f) = s.parse::<f64>() {
        return format!("{f:?}");
    }
    raw.to_string()
}

/// Runs JBMC once and reads its output.
fn run_once(run: &JbmcRun) -> Result<JbmcResult, Error> {
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
            native: None,
            gaps: Vec::new(),
            gap_mode: None,
            ending: Ending::Unavailable,
        });
    }
    let started = std::time::Instant::now();
    let cwd = run.log.parent().filter(|p| !p.as_os_str().is_empty()).map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let mut output = crate::tla::run_with_timeout(&cmd, &cwd, run.timeout)?;
    if run.sat_solver.is_some() && output.contains("unknown solver '") {
        // This JBMC was built without the solver asked for: its own default will do.
        let fallback = JbmcRun { sat_solver: None, ..run.clone() };
        let note = format!("note: {}; running again with JBMC's default solver\n", output.lines().find(|l| l.contains("unknown solver")).unwrap_or_default().trim());
        // Within what is left of the run's budget, not a budget of its own.
        let left = run.timeout.saturating_sub(started.elapsed());
        output = note + &crate::tla::run_with_timeout(&limited(command(&fallback), memory_mb), &cwd, left)?;
    }
    let seconds = started.elapsed().as_secs_f64();
    std::fs::write(&run.log, &output)?;
    let mut result = match run.read {
        Reading::Text => parse_output(&output, &run.class, &run.function, run.unwind, run.stage.clone()),
        _ => parse_json(&output, &run.class, &run.function, run.unwind, run.stage.clone()),
    };
    result.log = run.log.clone();
    result.seconds = seconds;
    if output.contains("did not finish within") {
        result.verdict = Verdict::Unverifiable;
        result.ending = Ending::Timeout;
        result.problem = Some(format!("JBMC did not finish within {} s", crate::deadline::seconds(run.timeout)));
    } else if let Some((ending, problem)) = abnormal_end(&output, memory_mb) {
        result.verdict = Verdict::Unverifiable;
        result.ending = ending;
        result.problem = Some(problem);
    }
    Ok(result)
}

/// A result of JBMC's with nothing in it yet.
fn blank(version: &str, stage: Option<String>, ending: Ending, verdict: Verdict, properties: u32, problem: Option<String>) -> JbmcResult {
    JbmcResult {
        verdict,
        version: version.to_string(),
        properties,
        raw_inputs: BTreeMap::new(),
        raw_arrays: BTreeMap::new(),
        stage,
        problem,
        log: PathBuf::new(),
        seconds: 0.0,
        native: None,
        gaps: Vec::new(),
        gap_mode: None,
        ending,
    }
}

/// Reads what JBMC printed under `--json-ui`: a JSON array of objects, each a message (`messageType`,
/// `messageText`), the `program`, a `result` (every property with its `status`, and a `trace` for each that
/// failed), or the `cProverStatus` (`success`, `failure`, `inconclusive`, `error`). A run cut off leaves the array
/// unclosed; what came before is read, and the run says nothing more.
pub fn parse_json(output: &str, class: &str, function: &str, unwind: u32, stage: Option<String>) -> JbmcResult {
    let items = json_items(output);
    let messages: Vec<(&str, &str)> = items.iter().filter_map(|i| Some((i.get("messageType")?.as_str()?, i.get("messageText")?.as_str()?))).collect();
    let version_of = Regex::new(r"JBMC (?:version )?(\d\S*)").unwrap();
    let version = items
        .iter()
        .filter_map(|i| i.get("program").and_then(|p| p.as_str()))
        .chain(messages.iter().map(|(_, text)| *text))
        .find_map(|t| version_of.captures(t).map(|c| format!("JBMC {}", &c[1])))
        .unwrap_or_else(|| "JBMC".into());
    let base = |ending: Ending, verdict: Verdict, properties: u32, problem: Option<String>| blank(&version, stage.clone(), ending, verdict, properties, problem);
    // A class path entry JBMC could not read makes every method in it a stub with an arbitrary result, and the
    // harness assertion then fails for no reason; that is no verdict.
    let unreadable = Regex::new(r"failed to access directory '([^']*)'").unwrap();
    if let Some(c) = messages.iter().find_map(|(_, text)| unreadable.captures(text)) {
        return base(Ending::UnsupportedInput, Verdict::Unverifiable, 0, Some(format!("JBMC could not read the class path entry {}", &c[1])));
    }
    let status = items.iter().find_map(|i| i.get("cProverStatus").and_then(|s| s.as_str()));
    let Some(results) = items.iter().find_map(|i| i.get("result").and_then(|r| r.as_array())) else {
        // No property was checked: an error before any result is JBMC refusing the program.
        if let Some((_, error)) = messages.iter().find(|(kind, _)| *kind == "ERROR") {
            return base(Ending::UnsupportedInput, Verdict::Unverifiable, 0, Some(format!("JBMC refused the program: {error}")));
        }
        let last = messages.last().map(|(_, t)| *t).unwrap_or("no output");
        return base(Ending::Unreadable, Verdict::Unverifiable, 0, Some(format!("JBMC produced no verdict: {last}")));
    };
    let properties = results.len() as u32;
    let status_of = |p: &serde_json::Value| p.get("status").and_then(|s| s.as_str()).unwrap_or("").to_string();
    let id_of = |p: &serde_json::Value| p.get("property").and_then(|s| s.as_str()).unwrap_or("").to_string();
    let failed: Vec<&serde_json::Value> = results.iter().filter(|p| status_of(p) == "FAILURE").collect();
    if failed.is_empty() {
        // Nothing failed is not a proof: a solver that gives up leaves every property as ERROR, none of them
        // failed, and the status is `error`; a run that stops after the results leaves no status at all.
        if status == Some("success") && results.iter().all(|p| matches!(status_of(p).as_str(), "SUCCESS" | "UNREACHABLE")) {
            return base(Ending::Verified, Verdict::Verified, properties, None);
        }
        let left: Vec<String> = results.iter().filter(|p| !matches!(status_of(p).as_str(), "SUCCESS" | "UNREACHABLE")).map(|p| format!("{} {}", id_of(p), status_of(p))).collect();
        let left = if left.is_empty() { String::new() } else { format!(" ({})", left.join(", ")) };
        let Some(status) = status else {
            return base(Ending::Unreadable, Verdict::Unverifiable, properties, Some(format!("JBMC produced no verdict: it stopped after the results{left}")));
        };
        return base(Ending::SolverFailure, Verdict::Unverifiable, properties, Some(format!("JBMC produced no verdict: VERIFICATION {}{left}", status.to_ascii_uppercase())));
    }
    if let Some(unwound) = failed.iter().map(|p| id_of(p)).find(|f| f.contains(".unwind.")) {
        return base(Ending::UnwindingFailure, Verdict::Unverifiable, properties, Some(format!("a loop was not fully unwound with --unwind {unwind} ({unwound})")));
    }
    let marker = format!("{class}.{function}");
    let Some(assertion) = failed.iter().find(|p| { let id = id_of(p); id.contains(&marker) && id.contains("assertion") }) else {
        let ids: Vec<String> = failed.iter().map(|p| id_of(p)).collect();
        return base(Ending::OtherFailure, Verdict::Unverifiable, properties, Some(format!("an unexpected property failed: {}", ids.join(", "))));
    };
    let mut result = base(Ending::Counterexample, Verdict::Violation, properties, None);
    let steps = assertion.get("trace").and_then(|t| t.as_array()).map(Vec::as_slice).unwrap_or(&[]);
    (result.raw_inputs, result.raw_arrays) = trace_inputs(steps);
    result
}

/// The elements of the JSON array JBMC prints, up to the first that does not parse (a run cut off, or text from
/// standard error in between).
fn json_items(output: &str) -> Vec<serde_json::Value> {
    let Some(start) = output.lines().scan(0, |at, line| { let here = *at; *at += line.len() + 1; Some((here, line)) }).find(|(_, l)| l.trim_start().starts_with('[')).map(|(at, l)| at + l.find('[').unwrap_or(0)) else {
        return Vec::new();
    };
    let mut items = Vec::new();
    let mut rest = &output[start + 1..];
    loop {
        rest = rest.trim_start_matches(|c: char| c.is_whitespace() || c == ',');
        if rest.is_empty() || rest.starts_with(']') {
            break;
        }
        let mut stream = serde_json::Deserializer::from_str(rest).into_iter::<serde_json::Value>();
        match stream.next() {
            Some(Ok(item)) => {
                let used = stream.byte_offset();
                items.push(item);
                rest = &rest[used..];
            }
            _ => break,
        }
    }
    items
}

/// The inputs of a counterexample's trace: each `input` step names a harness parameter (`arg0i`, by slot), and an
/// array parameter's value is an object whose `length`, `data` and elements the assignments before it set, as in
/// the text ([`parse_arrays`]).
fn trace_inputs(steps: &[serde_json::Value]) -> (BTreeMap<u32, String>, BTreeMap<u32, Option<Vec<String>>>) {
    let input_id = Regex::new(r"^arg(\d+)[a-z]$").unwrap();
    let field = Regex::new(r"^([A-Za-z0-9_$]+)\.(length|data)$").unwrap();
    let whole = Regex::new(r"^([A-Za-z0-9_$]+)$").unwrap();
    let element = Regex::new(r"^([A-Za-z0-9_$]+)\[(\d+)L?\]$").unwrap();
    let mut lengths: BTreeMap<String, usize> = BTreeMap::new();
    let mut datas: BTreeMap<String, String> = BTreeMap::new();
    let mut elements: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let (mut scalars, mut arrays) = (BTreeMap::new(), BTreeMap::new());
    for step in steps {
        match step.get("stepType").and_then(|t| t.as_str()) {
            Some("input") => {
                let Some(slot) = step.get("inputID").and_then(|i| i.as_str()).and_then(|i| input_id.captures(i)).and_then(|c| c[1].parse::<u32>().ok()) else { continue };
                let Some(value) = step.get("values").and_then(|v| v.as_array()).and_then(|v| v.first()) else { continue };
                if value.get("name").and_then(|n| n.as_str()) == Some("pointer") {
                    match pointee(value) {
                        None => {
                            arrays.insert(slot, None);
                        }
                        Some(object) => {
                            let len = lengths.get(&object).copied().unwrap_or(0);
                            let mut values = datas.get(&object).and_then(|d| elements.get(d)).cloned().unwrap_or_default();
                            values.resize(len, "0".into());
                            arrays.insert(slot, Some(values));
                        }
                    }
                } else if let Some(v) = scalar(value) {
                    scalars.insert(slot, v);
                }
            }
            Some("assignment") => {
                let (Some(lhs), Some(value)) = (step.get("lhs").and_then(|l| l.as_str()), step.get("value")) else { continue };
                if let Some(c) = field.captures(lhs) {
                    if &c[2] == "length" {
                        if let Some(n) = scalar(value).and_then(|v| v.parse().ok()) {
                            lengths.insert(c[1].to_string(), n);
                        }
                    } else if let Some(d) = pointee(value) {
                        datas.insert(c[1].to_string(), d);
                    }
                } else if let Some(c) = element.captures(lhs) {
                    let (Ok(index), Some(v)) = (c[2].parse::<usize>(), scalar(value)) else { continue };
                    let values = elements.entry(c[1].to_string()).or_default();
                    if values.len() <= index {
                        values.resize(index + 1, "0".into());
                    }
                    values[index] = v;
                } else if let Some(c) = whole.captures(lhs) {
                    if value.get("name").and_then(|n| n.as_str()) != Some("array") {
                        continue;
                    }
                    let mut values = Vec::new();
                    for e in value.get("elements").and_then(|e| e.as_array()).map(Vec::as_slice).unwrap_or(&[]) {
                        let (Some(index), Some(v)) = (e.get("index").and_then(json_index), e.get("value").and_then(scalar)) else { continue };
                        if values.len() <= index {
                            values.resize(index + 1, "0".into());
                        }
                        values[index] = v;
                    }
                    elements.insert(c[1].to_string(), values);
                }
            }
            _ => {}
        }
    }
    (scalars, arrays)
}

/// An index as JSON gives it: a number, or a string of one.
fn json_index(v: &serde_json::Value) -> Option<usize> {
    v.as_u64().map(|n| n as usize).or_else(|| v.as_str().and_then(|s| s.parse().ok()))
}

/// The object a pointer value names, `None` for `null`.
fn pointee(value: &serde_json::Value) -> Option<String> {
    let data = value.get("data").and_then(|d| d.as_str())?;
    let data = data.trim().trim_start_matches('&');
    (!data.is_empty() && data != "null" && data != "NULL").then(|| data.to_string())
}

/// A primitive value of a trace, in decimal, from its bits where it has them: an integer by its width and whether
/// its type is unsigned (`char`, `boolean`), a floating-point value as an IEEE 754 value of its width.
fn scalar(value: &serde_json::Value) -> Option<String> {
    let name = value.get("name").and_then(|n| n.as_str())?;
    let bits = value.get("binary").and_then(|b| b.as_str()).filter(|b| !b.is_empty() && b.len() <= 128 && b.chars().all(|c| c == '0' || c == '1'));
    match name {
        "integer" => {
            let Some(bits) = bits else { return value.get("data").and_then(|d| d.as_str()).map(str::to_string) };
            let raw = u128::from_str_radix(bits, 2).ok()?;
            let width = bits.len() as u32;
            // JBMC writes a parameter's type as `const long`.
            let ty = value.get("type").and_then(|t| t.as_str()).unwrap_or("").trim_start_matches("const ").trim();
            let unsigned = ty == "char" || ty == "boolean" || ty.starts_with("unsigned") || ty.starts_with("__CPROVER_bool");
            Some(if unsigned || width == 128 || raw >> (width - 1) == 0 {
                raw.to_string()
            } else {
                (raw as i128 - (1i128 << width)).to_string()
            })
        }
        "float" => {
            let raw = u64::from_str_radix(bits?, 2).ok()?;
            let f = match bits?.len() {
                32 => f64::from(f32::from_bits(raw as u32)),
                64 => f64::from_bits(raw),
                _ => return None,
            };
            Some(if f.is_nan() {
                "NaN".into()
            } else if f.is_infinite() {
                if f > 0.0 { "Infinity".into() } else { "-Infinity".into() }
            } else {
                format!("{f:?}")
            })
        }
        "boolean" => value.get("data").and_then(|d| d.as_bool()).map(|b| if b { "true" } else { "false" }.into()),
        _ => value.get("data").and_then(|d| d.as_str()).map(str::to_string),
    }
}

/// Parses JBMC's console output.
pub fn parse_output(output: &str, class: &str, function: &str, unwind: u32, stage: Option<String>) -> JbmcResult {
    let version = Regex::new(r"(?m)^JBMC version (\S+)").unwrap().captures(output).map(|c| format!("JBMC {}", &c[1])).unwrap_or_else(|| "JBMC".into());
    let base = |ending: Ending, verdict: Verdict, properties: u32, problem: Option<String>| blank(&version, stage.clone(), ending, verdict, properties, problem);
    // A class path entry JBMC could not read makes every method in it a stub with an arbitrary result, and the
    // harness assertion then fails for no reason; that is no verdict.
    if let Some(c) = Regex::new(r"(?m)^Warning: failed to access directory '([^']*)'").unwrap().captures(output) {
        return base(Ending::UnsupportedInput, Verdict::Unverifiable, 0, Some(format!("JBMC could not read the class path entry {}", &c[1])));
    }
    let Some(failed) = Regex::new(r"\*\* (\d+) of (\d+) failed").unwrap().captures(output) else {
        let tail = output.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("no output");
        return base(Ending::Unreadable, Verdict::Unverifiable, 0, Some(format!("JBMC produced no verdict: {tail}")));
    };
    let properties: u32 = failed[2].parse().unwrap_or(0);
    if failed[1].parse::<u32>().unwrap_or(1) == 0 {
        // "0 failed" is not a proof. A solver that gives up leaves every property as ERROR, none of them failed, and
        // JBMC ends with VERIFICATION ERROR; a run that stops after the count leaves no last line at all.
        if Regex::new(r"(?m)^VERIFICATION SUCCESSFUL\s*$").unwrap().is_match(output) {
            return base(Ending::Verified, Verdict::Verified, properties, None);
        }
        let tail = output.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("no output");
        return base(Ending::SolverFailure, Verdict::Unverifiable, properties, Some(format!("JBMC produced no verdict: {tail}")));
    }
    let failures: Vec<String> = Regex::new(r"(?m)^\[([^\]]+)\] .*: FAILURE$").unwrap().captures_iter(output).map(|c| c[1].to_string()).collect();
    if let Some(unwound) = failures.iter().find(|f| f.contains(".unwind.")) {
        return base(Ending::UnwindingFailure, Verdict::Unverifiable, properties, Some(format!("a loop was not fully unwound with --unwind {unwind} ({unwound})")));
    }
    let marker = format!("{class}.{function}");
    if !failures.iter().any(|f| f.contains(&marker) && f.contains("assertion")) {
        return base(Ending::OtherFailure, Verdict::Unverifiable, properties, Some(format!("an unexpected property failed: {}", failures.join(", "))));
    }
    let mut result = base(Ending::Counterexample, Verdict::Violation, properties, None);
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

    /// What JBMC 6.11.0 prints under `--json-ui`, in the shape `report_util.cpp` and `json_goto_trace.cpp` give it:
    /// the program, messages, the results, and the overall status.
    fn json_run(results: &str, status: Option<&str>) -> String {
        let status = status.map(|s| format!(",\n  {{\n    \"messageText\": \"VERIFICATION {}\",\n    \"messageType\": \"STATUS-MESSAGE\"\n  }},\n  {{\n    \"cProverStatus\": \"{s}\"\n  }}", s.to_ascii_uppercase())).unwrap_or_default();
        format!("[\n  {{\n    \"program\": \"JBMC 6.11.0 (cbmc-6.11.0)\"\n  }},\n  {{\n    \"messageText\": \"JBMC version 6.11.0 (cbmc-6.11.0) 64-bit arm64 linux\",\n    \"messageType\": \"STATUS-MESSAGE\"\n  }},\n  {{\n    \"result\": [{results}]\n  }}{status}\n]\n")
    }

    fn property(id: &str, status: &str, trace: Option<&str>) -> String {
        let trace = trace.map(|t| format!(", \"trace\": [{t}]")).unwrap_or_default();
        format!("{{\"description\": \"assertion\", \"property\": \"{id}\", \"sourceLocation\": {{\"file\": \"H.java\", \"line\": \"1\"}}, \"status\": \"{status}\"{trace}}}")
    }

    fn int(width: u32, ty: &str, value: i128) -> String {
        let bits: String = (0..width).rev().map(|i| if (value >> i) & 1 == 1 { '1' } else { '0' }).collect();
        format!("{{\"binary\": \"{bits}\", \"data\": \"{value}\", \"name\": \"integer\", \"type\": \"{ty}\", \"width\": {width}}}")
    }

    fn input(id: &str, value: &str) -> String {
        format!("{{\"hidden\": false, \"inputID\": \"{id}\", \"internal\": false, \"mode\": \"java\", \"stepType\": \"input\", \"thread\": 0, \"values\": [{value}]}}")
    }

    fn assign(lhs: &str, value: &str) -> String {
        format!("{{\"assignmentType\": \"variable\", \"hidden\": false, \"internal\": false, \"lhs\": \"{lhs}\", \"mode\": \"java\", \"stepType\": \"assignment\", \"thread\": 0, \"value\": {value}}}")
    }

    #[test]
    fn reads_the_json_jbmc_prints() {
        let id = "java::EquivalenceHarness.check:(JI)V.assertion.1";
        let proved = json_run(&[property(id, "SUCCESS", None), property("java::EquivalenceHarness.check:(JI)V.unwind.0", "SUCCESS", None)].join(", "), Some("success"));
        let r = parse_json(&proved, "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending, r.properties, r.version.as_str()), (Verdict::Verified, Ending::Verified, 2, "JBMC 6.11.0"));

        // The inputs by slot, from their bits: a long in slot 0 puts the int in slot 2.
        let trace = [input("arg0a", &int(64, "long", 17)), input("arg2a", &int(32, "int", -6)), format!("{{\"stepType\": \"failure\", \"property\": \"{id}\", \"reason\": \"assertion\"}}")].join(", ");
        let refuted = json_run(&[property(id, "FAILURE", Some(&trace)), property("java::EquivalenceHarness.check:(JI)V.null-pointer-exception.1", "SUCCESS", None)].join(", "), Some("failure"));
        let r = parse_json(&refuted, "EquivalenceHarness", "check", 16, Some("[0:20]".into()));
        assert_eq!((r.verdict, r.ending, r.stage.as_deref()), (Verdict::Violation, Ending::Counterexample, Some("[0:20]")));
        assert_eq!(r.inputs(&[Type::Long, Type::Int]).unwrap(), vec![Value::Long(17), Value::Int(-6)]);

        // A solver that gives up leaves every property as ERROR, none of them failed.
        let gave_up = json_run(&property(id, "ERROR", None), Some("error"));
        let r = parse_json(&gave_up, "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Unverifiable, Ending::SolverFailure));
        assert!(r.problem.as_deref().unwrap().contains("VERIFICATION ERROR"), "{:?}", r.problem);
        let unknown = json_run(&property(id, "UNKNOWN", None), Some("inconclusive"));
        assert_eq!(parse_json(&unknown, "EquivalenceHarness", "check", 16, None).ending, Ending::SolverFailure);

        // Results with no status after them, and an array cut off, are no verdict either.
        let cut = json_run(&property(id, "SUCCESS", None), None);
        let r = parse_json(cut.trim_end().trim_end_matches(']'), "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Unverifiable, Ending::Unreadable));
        let r = parse_json(&proved[..proved.len() / 2], "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Unverifiable, Ending::Unreadable));
        assert_eq!(parse_json("", "EquivalenceHarness", "check", 16, None).ending, Ending::Unreadable);

        let unwound = json_run(&[property(id, "SUCCESS", None), property("java::EquivalenceHarness.check:(JI)V.unwind.0", "FAILURE", Some(""))].join(", "), Some("failure"));
        let r = parse_json(&unwound, "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Unverifiable, Ending::UnwindingFailure));
        assert!(r.problem.unwrap().contains("not fully unwound with --unwind 16"));

        let other = json_run(&property("java::Lib.f:()V.array-index-out-of-bounds.1", "FAILURE", Some("")), Some("failure"));
        let r = parse_json(&other, "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Unverifiable, Ending::OtherFailure));

        // A missing class path entry would otherwise look like a counterexample.
        let unreadable = refuted.replacen("  {\n    \"result\"", "  {\n    \"messageText\": \"failed to access directory 'build/main'\",\n    \"messageType\": \"WARNING\"\n  },\n  {\n    \"result\"", 1);
        let r = parse_json(&unreadable, "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Unverifiable, Ending::UnsupportedInput));
        assert_eq!(r.problem.as_deref(), Some("JBMC could not read the class path entry build/main"));

        // An error before any result: JBMC did not take the program.
        let refused = "[\n  {\n    \"program\": \"JBMC 6.11.0 (cbmc-6.11.0)\"\n  },\n  {\n    \"messageText\": \"the program has no entry point\",\n    \"messageType\": \"ERROR\"\n  }\n]\n";
        let r = parse_json(refused, "EquivalenceHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Unverifiable, Ending::UnsupportedInput));
        assert_eq!(r.problem.as_deref(), Some("JBMC refused the program: the program has no entry point"));

        // Text around the array (a note before it, a timeout's line after it) is not read as part of it.
        let noted = format!("note: unknown solver 'cadical'; running again with JBMC's default solver\n{proved}\nError: jbmc did not finish within 3 s\n");
        assert_eq!(parse_json(&noted, "EquivalenceHarness", "check", 16, None).ending, Ending::Verified);
    }

    #[test]
    fn reads_array_inputs_and_their_elements_from_json() {
        let id = "java::PropertyHarness.check:([B[CZ)V.assertion.1";
        let pointer = |data: &str| format!("{{\"data\": \"{data}\", \"name\": \"pointer\", \"type\": \"struct java::array[byte] *\"}}");
        let array = |values: &[String]| format!("{{\"elements\": [{}], \"name\": \"array\"}}", values.iter().enumerate().map(|(i, v)| format!("{{\"index\": {i}, \"value\": {v}}}")).collect::<Vec<_>>().join(", "));
        let trace = [
            assign("dynamic_object.length", &int(32, "int", 0)),
            assign("dynamic_object.data", &pointer("null")),
            assign("dynamic_object.length", &int(32, "int", 3)),
            assign("dynamic_object$0", &array(&[int(8, "byte", 0), int(8, "byte", 0), int(8, "byte", 0)])),
            assign("dynamic_object$0", &array(&[int(8, "byte", -128), int(8, "byte", 2), int(8, "byte", 0)])),
            assign("dynamic_object$0[2L]", &int(8, "byte", 127)),
            assign("dynamic_object.data", &pointer("dynamic_object$0")),
            input("arg0a", &pointer("dynamic_object")),
            assign("dynamic_object$1.length", &int(32, "int", 1)),
            assign("dynamic_object$1.data", &pointer("&dynamic_object$2")),
            assign("dynamic_object$2[0L]", &int(16, "const char", 0xfffe)),
            input("arg1a", &pointer("dynamic_object$1")),
            input("arg2z", "{\"binary\": \"1\", \"data\": true, \"name\": \"boolean\"}"),
            // A store after the input is the method's, not the input.
            assign("dynamic_object$0[1L]", &int(8, "byte", 7)),
        ]
        .join(", ");
        let out = json_run(&property(id, "FAILURE", Some(&trace)), Some("failure"));
        let r = parse_json(&out, "PropertyHarness", "check", 16, None);
        assert_eq!((r.verdict, r.ending), (Verdict::Violation, Ending::Counterexample));
        let args = r.arguments(&[Type::Array(Box::new(Type::Byte)), Type::Array(Box::new(Type::Char)), Type::Boolean]).unwrap();
        assert_eq!(
            args,
            vec![
                Argument::Array(vec![Value::Int(-128), Value::Int(2), Value::Int(127)]),
                Argument::Array(vec![Value::Int(0xfffe)]),
                Argument::Scalar(Value::Int(1)),
            ]
        );

        let null = json_run(&property(id, "FAILURE", Some(&[input("arg0a", &pointer("null")), input("arg1a", &pointer("null"))].join(", "))), Some("failure"));
        let r = parse_json(&null, "PropertyHarness", "check", 16, None);
        assert_eq!(r.arguments(&[Type::Array(Box::new(Type::Byte)), Type::Array(Box::new(Type::Char))]).unwrap(), vec![Argument::Null, Argument::Null]);

        // A floating-point input from its IEEE 754 bits: 1.5f, and a double NaN.
        let float = |width: u32, bits: u64| format!("{{\"binary\": \"{bits:0w$b}\", \"data\": \"x\", \"name\": \"float\", \"type\": \"t\", \"width\": {width}}}", w = width as usize);
        let fp = json_run(&property("java::PropertyHarness.check:(FD)V.assertion.1", "FAILURE", Some(&[input("arg0f", &float(32, 0x3fc0_0000)), input("arg1d", &float(64, 0x7ff8_0000_0000_0000))].join(", "))), Some("failure"));
        let r = parse_json(&fp, "PropertyHarness", "check", 16, None);
        let values = r.inputs(&[Type::Float, Type::Double]).unwrap();
        assert_eq!(values[0], Value::Float(1.5));
        assert!(matches!(values[1], Value::Double(d) if d.is_nan()));
    }

    #[test]
    fn a_value_has_one_canonical_form_whichever_reading_gave_it() {
        for (raw, canonical_form) in [("17l", "17"), ("17", "17"), ("(byte)-128", "-128"), ("'a'", "97"), ("97", "97"), ("'\\u0000'", "0"), ("true", "1"), ("1.5f", "1.5"), ("1.5", "1.5"), ("Float.NaN", "NaN"), ("NaN", "NaN"), ("-Double.POSITIVE_INFINITY", "-inf"), ("-Infinity", "-inf"), ("-0.0", "-0.0")] {
            assert_eq!(canonical(raw), canonical_form, "{raw}");
        }
    }

    #[cfg(unix)]
    #[test]
    fn both_readings_of_one_run_are_compared() {
        let dir = tempfile::tempdir().unwrap();
        let id = "java::PropertyHarness.check:(I)V.assertion.1";
        let json = json_run(&property(id, "FAILURE", Some(&input("arg0i", &int(32, "int", 5)))), Some("failure"));
        std::fs::write(dir.path().join("answer.json"), &json).unwrap();
        let text = "JBMC version 6.11.0 (cbmc-6.11.0)\n[PropertyHarness.check:(I)V.assertion.1] assertion: FAILURE\n  INPUT arg0i: 5\n** 1 of 1 failed (2 iterations)\nVERIFICATION FAILED\n";
        std::fs::write(dir.path().join("answer.txt"), text).unwrap();
        std::fs::write(dir.path().join("other.txt"), text.replace("arg0i: 5", "arg0i: 6")).unwrap();
        let body = |txt: &str| format!("d=$(dirname \"$0\"); case \"$*\" in *--json-ui*) cat \"$d/answer.json\";; *) cat \"$d/{txt}\";; esac");

        let r = stand_in_reading(dir.path(), "agreeing", &body("answer.txt"), Reading::Both);
        assert_eq!((r.verdict, r.ending), (Verdict::Violation, Ending::Counterexample));
        let d: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(dir.path().join("agreeing.differential.json")).unwrap()).unwrap();
        assert_eq!(d["agree"], true, "{d}");
        assert_eq!(d["json"]["inputs"]["0"], "5");
        assert!(dir.path().join("agreeing.text.log").exists());

        let r = stand_in_reading(dir.path(), "disagreeing", &body("other.txt"), Reading::Both);
        assert_eq!(r.verdict, Verdict::Violation, "the JSON decides");
        let d: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(dir.path().join("disagreeing.differential.json")).unwrap()).unwrap();
        assert_eq!(d["agree"], false, "{d}");
        assert!(d["differences"][0].as_str().unwrap().starts_with("counterexample:"), "{d}");

        // The JSON reading asks for it; the text reading does not.
        let args = stand_in_reading(dir.path(), "json", "echo \"$@\"", Reading::Json);
        assert!(std::fs::read_to_string(&args.log).unwrap().contains("--json-ui"));
        let args = stand_in_reading(dir.path(), "text", "echo \"$@\"", Reading::Text);
        assert!(!std::fs::read_to_string(&args.log).unwrap().contains("--json-ui"));
        assert_eq!(args.ending, Ending::Unreadable);
        // A JBMC that is not there is an ending of its own.
        let mut gone = JbmcRun { executable: dir.path().join("absent").display().to_string(), class: "H".into(), function: "check".into(), classpath: Vec::new(), unwind: 1, timeout: Duration::from_secs(1), stage: None, refine_strings: false, sat_solver: None, log: dir.path().join("absent.log"), extra_args: Vec::new(), read: Reading::Json };
        assert_eq!(run(&gone).unwrap().ending, Ending::Unavailable);
        gone.read = Reading::Text;
        assert_eq!(run(&gone).unwrap().ending, Ending::Unavailable);
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
            read: Reading::Text,
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
        stand_in_reading(dir, name, body, Reading::Text)
    }

    /// [`stand_in`], read as `read` says.
    #[cfg(unix)]
    fn stand_in_reading(dir: &Path, name: &str, body: &str, read: Reading) -> JbmcResult {
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
            read,
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
