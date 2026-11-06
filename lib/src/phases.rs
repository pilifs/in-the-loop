//! Where a check's time goes, phase by phase: step 5b of the sound-verdicts brief
//! (`llm-dlc/loops/sound-verdicts.md`), so that an optimization of either checker is chosen from measurements.
//!
//! Each checker run has a [`Profile`]: its seconds split into the same [`Phases`] for both checkers, and the size
//! of what it solved ([`Formula`]). The phases are exclusive, and add up to the run's seconds:
//!
//! | Phase | The tool's own checker | JBMC 6.11.0 |
//! |---|---|---|
//! | `loading` | reading and parsing class files | from its first message to `Generating GOTO Program`: parsing the class files and converting them |
//! | `lowering` | decoding methods into the engine's instructions | `Generating GOTO Program` to `Starting Bounded Model Checking`: the GOTO program and its passes |
//! | `symbolic` | exploring the paths: interpretation, path management and merging, and evaluating gates in path models | `Runtime Symex` and `Runtime Postprocess Equation` |
//! | `encoding` | building circuits and handing their clauses to the solver, which happens as the paths are explored: estimated from one word-level operation in 64, timed (a clock read costs about 0.3 µs on the WSL2 machine, as much as a small operation) | `Runtime Convert SSA` and `Runtime Post-process` |
//! | `solving` | CaDiCaL's calls | `Runtime Solver` |
//! | `trace` | reading the witness out of the solver's model | `Building error trace` to the message after it |
//! | `other` | the rest | the rest: starting, printing, and what the messages do not cover |
//!
//! JBMC's times are its own `Runtime` lines, and the times of its messages, which `--timestamp monotonic` adds
//! (read from CBMC 6.11.0's `ui_message.cpp`, and seen in its output). A run cut off by its budget has no
//! `Runtime` line for the phase it was in: that phase gets the time from its first message to the run's end, so
//! a timeout says where it was spent.
//!
//! A check is more than its checker runs: extracting JDK classes and models, generating the harness, scanning for gaps, checking contracts, JBMC's
//! preflight, replaying and shrinking a witness, and running it on a JVM. [`Check`] times those, in the drivers
//! ([`begin`], [`timed`], [`end`]).

use serde::Serialize;
use std::cell::RefCell;
use std::collections::BTreeMap;
use std::time::Instant;

/// One checker run's seconds, phase by phase (see the module's table).
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Phases {
    pub loading: f64,
    pub lowering: f64,
    pub symbolic: f64,
    pub encoding: f64,
    pub solving: f64,
    pub trace: f64,
    pub other: f64,
}

impl Phases {
    /// The phases rounded to the millisecond, with `other` what is left of `seconds`.
    pub fn completed(mut self, seconds: f64) -> Phases {
        let named = self.loading + self.lowering + self.symbolic + self.encoding + self.solving + self.trace;
        self.other = (seconds - named).max(0.0);
        for v in [&mut self.loading, &mut self.lowering, &mut self.symbolic, &mut self.encoding, &mut self.solving, &mut self.trace, &mut self.other] {
            *v = round(*v);
        }
        self
    }

    /// The phases by name, in the table's order.
    pub fn named(&self) -> [(&'static str, f64); 7] {
        [("loading", self.loading), ("lowering", self.lowering), ("symbolic", self.symbolic), ("encoding", self.encoding), ("solving", self.solving), ("trace", self.trace), ("other", self.other)]
    }
}

/// The size of what a run solved: JBMC's program expression (its SSA steps) and verification conditions left after
/// simplification, and the formula's variables and clauses (JBMC's last, or the own checker's whole formula, which
/// one incremental solver keeps).
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Formula {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub steps: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub conditions: Option<u64>,
    pub variables: Option<u64>,
    pub clauses: Option<u64>,
}

/// A checker run's phases and formula.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Profile {
    /// `None` when the run's output has no times to read them from (JBMC read as text, a stand-in).
    pub phases: Option<Phases>,
    pub formula: Formula,
}

fn round(s: f64) -> f64 {
    (s * 1000.0).round() / 1000.0
}

/// Where JBMC is, after a message: the phase the time from it to the next message belongs to, when the message
/// starts one.
fn jbmc_phase_started(text: &str) -> Option<&'static str> {
    if text.starts_with("Generating GOTO Program") {
        Some("lowering")
    } else if text.starts_with("Starting Bounded Model Checking") {
        Some("symbolic")
    } else if text.starts_with("Passing problem to propositional reduction") || text.starts_with("converting SSA") || text.starts_with("Running propositional reduction") {
        Some("encoding")
    } else if text.starts_with("Runtime Post-process:") {
        Some("solving")
    } else if text.starts_with("Building error trace") {
        Some("trace")
    } else if text.starts_with("Runtime Symex") || text.starts_with("Runtime Convert SSA") || text.starts_with("Runtime Solver") || text.starts_with("Runtime decision procedure") || text.starts_with("VERIFICATION") {
        Some("other")
    } else {
        None
    }
}

/// JBMC's run read from its `--json-ui` output, which `run_seconds` took from start to end.
pub fn of_jbmc(items: &[serde_json::Value], run_seconds: f64) -> Profile {
    let messages: Vec<(Option<f64>, &str)> = items.iter().filter_map(|i| Some((i.get("timestamp").and_then(timestamp), i.get("messageText")?.as_str()?))).collect();
    let number = |text: &str, prefix: &str| -> Option<f64> { text.strip_prefix(prefix)?.trim().trim_end_matches('s').parse().ok() };
    let count = |re: &str| -> Option<u64> {
        let re = regex::Regex::new(re).unwrap();
        messages.iter().rev().find_map(|(_, t)| re.captures(t).and_then(|c| c[1].parse().ok()))
    };
    let formula = Formula {
        steps: count(r"^size of program expression: (\d+) steps"),
        conditions: count(r"^Generated \d+ VCC\(s\), (\d+) remaining after simplification"),
        variables: count(r"^(\d+) variables, \d+ clauses"),
        clauses: count(r"^\d+ variables, (\d+) clauses"),
    };
    let Some(first) = messages.iter().find_map(|(t, _)| *t) else {
        return Profile { phases: None, formula };
    };
    // JBMC's own account of the phases it times.
    let mut p = Phases::default();
    for (_, text) in &messages {
        let (phase, v) = if let Some(v) = number(text, "Runtime Symex:").or_else(|| number(text, "Runtime Postprocess Equation:")) {
            ("symbolic", v)
        } else if let Some(v) = number(text, "Runtime Convert SSA:").or_else(|| number(text, "Runtime Post-process:")) {
            ("encoding", v)
        } else if let Some(v) = number(text, "Runtime Solver:") {
            ("solving", v)
        } else {
            continue;
        };
        *slot(&mut p, phase) += v;
    }
    // The times between messages for those it does not time: an interval belongs to the phase JBMC was in at its
    // start, and the trace to the message after `Building error trace`.
    let by_messages = |phase: &str| matches!(phase, "loading" | "lowering" | "trace");
    let (mut current, mut since, mut phase_started) = ("loading", first, first);
    for (t, text) in &messages {
        let Some(t) = *t else { continue };
        if by_messages(current) {
            *slot(&mut p, current) += (t - since).max(0.0);
        }
        since = t;
        if current == "trace" {
            current = "other";
        }
        if let Some(next) = jbmc_phase_started(text) {
            current = next;
            phase_started = t;
        }
    }
    // The end of the run on the messages' clock, its first message being printed as it starts. Cut off, the
    // phase it was in has no `Runtime` line yet, and gets the rest of the run.
    let end = first + run_seconds;
    if by_messages(current) {
        *slot(&mut p, current) += (end - since).max(0.0);
    } else if current != "other" {
        *slot(&mut p, current) += (end - phase_started).max(0.0);
    }
    Profile { phases: Some(p.completed(run_seconds)), formula }
}

fn timestamp(v: &serde_json::Value) -> Option<f64> {
    v.as_f64().or_else(|| v.as_str().and_then(|s| s.trim().parse().ok()))
}

fn slot<'a>(p: &'a mut Phases, phase: &str) -> &'a mut f64 {
    match phase {
        "loading" => &mut p.loading,
        "lowering" => &mut p.lowering,
        "symbolic" => &mut p.symbolic,
        "encoding" => &mut p.encoding,
        "solving" => &mut p.solving,
        "trace" => &mut p.trace,
        _ => &mut p.other,
    }
}

/// A check's seconds outside its checker runs, by what the driver was doing, and the runs' own.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Check {
    /// From the driver's start to its verdict.
    pub seconds: f64,
    /// Extracting the JDK's classes JBMC is given, and writing the models, into the work directory.
    pub setup: f64,
    /// Generating the harness (and the probe), and writing it out.
    pub harness: f64,
    /// Scanning the harness for gaps (`--gaps advised`) and JBMC's preflights of its goto program.
    pub gaps: f64,
    /// Reading, proving and testing contracts, and rewriting call sites for JBMC.
    pub contracts: f64,
    /// The checker runs of `search.runs`, the vacuity probe among them.
    pub runs: f64,
    /// Replaying a witness in the interpreter, and shrinking it.
    pub replay: f64,
    /// Running a witness on a JVM.
    pub jvm: f64,
    /// The rest: reading the target, building class paths, comparing versions, writing the report.
    pub other: f64,
}

/// What a driver phase is: one of [`Check`]'s fields other than `seconds`, `runs` and `other`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Step {
    Setup,
    Harness,
    Gaps,
    Contracts,
    Replay,
    Jvm,
}

struct Clock {
    started: Instant,
    spent: BTreeMap<Step, f64>,
    /// Whether a step is being timed, so that one inside another counts once, for the outer.
    inside: bool,
}

thread_local! {
    static CLOCK: RefCell<Option<Clock>> = const { RefCell::new(None) };
}

/// Starts timing a check on this thread (a driver's `run`); a check begun before and not ended is dropped.
pub fn begin() {
    CLOCK.with(|c| *c.borrow_mut() = Some(Clock { started: Instant::now(), spent: BTreeMap::new(), inside: false }));
}

/// Runs `f`, counting its time to `step` of the check being timed, if any and if no other step is being timed.
pub fn timed<T>(step: Step, f: impl FnOnce() -> T) -> T {
    let outermost = CLOCK.with(|c| match c.borrow_mut().as_mut() {
        Some(clock) if !clock.inside => {
            clock.inside = true;
            true
        }
        _ => false,
    });
    if !outermost {
        return f();
    }
    let started = Instant::now();
    let out = f();
    let spent = started.elapsed().as_secs_f64();
    CLOCK.with(|c| {
        if let Some(clock) = c.borrow_mut().as_mut() {
            *clock.spent.entry(step).or_default() += spent;
            clock.inside = false;
        }
    });
    out
}

/// Ends the check begun on this thread: its steps, and `runs_seconds` for its checker runs, with the rest as
/// `other`. `None` when no check was begun.
pub fn end(runs_seconds: f64) -> Option<Check> {
    let clock = CLOCK.with(|c| c.borrow_mut().take())?;
    let seconds = clock.started.elapsed().as_secs_f64();
    let get = |s: Step| clock.spent.get(&s).copied().unwrap_or(0.0);
    let mut check = Check { seconds, setup: get(Step::Setup), harness: get(Step::Harness), gaps: get(Step::Gaps), contracts: get(Step::Contracts), runs: runs_seconds, replay: get(Step::Replay), jvm: get(Step::Jvm), other: 0.0 };
    // A run inside a timed step (the preflight is in `gaps`, a contract's proof in `contracts`) is counted there,
    // and the runs' own seconds are the checker's, so the rest is what neither covers.
    check.other = (seconds - check.setup - check.harness - check.gaps - check.contracts - check.runs - check.replay - check.jvm).max(0.0);
    for v in [&mut check.seconds, &mut check.setup, &mut check.harness, &mut check.gaps, &mut check.contracts, &mut check.runs, &mut check.replay, &mut check.jvm, &mut check.other] {
        *v = round(*v);
    }
    Some(check)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn message(t: f64, text: &str) -> serde_json::Value {
        json!({"messageType": "STATUS-MESSAGE", "messageText": text, "timestamp": t})
    }

    /// A violation's run as JBMC 6.11.0 printed it under `--json-ui --timestamp monotonic`, on the benchmark's
    /// broken midpoint (times shifted to start at 100).
    fn counterexample() -> Vec<serde_json::Value> {
        vec![
            json!({"program": "JBMC 6.11.0 (cbmc-6.11.0)"}),
            message(100.000, "JBMC version 6.11.0 (cbmc-6.11.0) 64-bit arm64 linux"),
            message(100.002, "Parsing ..."),
            message(100.004, "Converting"),
            message(100.006, "Generating GOTO Program"),
            message(100.008, "Running GOTO functions transformation passes"),
            message(100.009, "Starting Bounded Model Checking"),
            message(100.017, "Runtime Symex: 0.00830184s"),
            message(100.017, "size of program expression: 114 steps"),
            message(100.017, "Generated 2 VCC(s), 1 remaining after simplification"),
            message(100.017, "Runtime Postprocess Equation: 2.23e-05s"),
            message(100.017, "Passing problem to propositional reduction"),
            message(100.017, "converting SSA"),
            message(100.019, "Runtime Convert SSA: 0.00194801s"),
            message(100.019, "Running propositional reduction"),
            message(100.019, "Runtime Post-process: 5.1e-06s"),
            message(100.019, "1674 variables, 3686 clauses"),
            message(100.020, "SAT checker: instance is SATISFIABLE"),
            message(100.020, "Runtime Solver: 0.000224801s"),
            message(100.020, "Runtime decision procedure: 0.00224501s"),
            message(100.020, "Building error trace"),
            json!({"result": []}),
            message(100.022, "VERIFICATION FAILED"),
            json!({"cProverStatus": "failure"}),
        ]
    }

    #[test]
    fn jbmc_phases_come_from_its_runtime_lines_and_the_times_of_its_messages() {
        let profile = of_jbmc(&counterexample(), 0.030);
        let p = profile.phases.expect("timed");
        assert_eq!(p.loading, 0.006, "first message to the GOTO program");
        assert_eq!(p.lowering, 0.003);
        assert_eq!(p.symbolic, 0.008, "Symex and Postprocess Equation");
        assert_eq!(p.encoding, 0.002, "Convert SSA and Post-process");
        assert_eq!(p.solving, 0.0);
        assert_eq!(p.trace, 0.002, "Building error trace to the next message");
        let sum: f64 = p.named().iter().map(|(_, v)| v).sum();
        assert!((sum - 0.030).abs() < 0.002, "the phases add up to the run: {p:?}");
        assert_eq!(profile.formula, Formula { steps: Some(114), conditions: Some(1), variables: Some(1674), clauses: Some(3686) });
    }

    #[test]
    fn a_jbmc_run_cut_off_gives_the_rest_of_its_time_to_the_phase_it_was_in() {
        let mut solving = counterexample();
        solving.truncate(17); // up to "1674 variables, 3686 clauses": the solver is running
        let p = of_jbmc(&solving, 60.0).phases.unwrap();
        assert!(p.solving > 59.9, "{p:?}");
        let mut converting = counterexample();
        converting.truncate(13); // up to "converting SSA"
        let p = of_jbmc(&converting, 60.0).phases.unwrap();
        assert!(p.encoding > 59.9 && p.solving == 0.0, "{p:?}");
        let mut symex = counterexample();
        symex.truncate(7); // up to "Starting Bounded Model Checking"
        let p = of_jbmc(&symex, 60.0).phases.unwrap();
        assert!(p.symbolic > 59.9, "{p:?}");
        let p = of_jbmc(&counterexample()[..3], 60.0).phases.unwrap();
        assert!(p.loading > 59.9, "still parsing: {p:?}");
    }

    #[test]
    fn output_without_times_has_sizes_but_no_phases() {
        let untimed: Vec<serde_json::Value> = counterexample().into_iter().map(|mut v| {
            v.as_object_mut().map(|o| o.remove("timestamp"));
            v
        }).collect();
        let profile = of_jbmc(&untimed, 1.0);
        assert_eq!(profile.phases, None);
        assert_eq!(profile.formula.clauses, Some(3686));
    }

    #[test]
    fn a_check_counts_each_step_once_and_the_rest_as_other() {
        begin();
        timed(Step::Harness, || std::thread::sleep(std::time::Duration::from_millis(20)));
        timed(Step::Contracts, || {
            std::thread::sleep(std::time::Duration::from_millis(10));
            timed(Step::Gaps, || std::thread::sleep(std::time::Duration::from_millis(10)));
        });
        std::thread::sleep(std::time::Duration::from_millis(10));
        let check = end(0.0).expect("begun");
        assert!(check.harness >= 0.02 && check.contracts >= 0.02, "{check:?}");
        assert_eq!(check.gaps, 0.0, "inside contracts, counted there");
        assert!(check.other >= 0.01, "{check:?}");
        assert!(end(0.0).is_none(), "ended");
        assert_eq!(timed(Step::Jvm, || 7), 7, "no check begun: just runs");
    }
}
