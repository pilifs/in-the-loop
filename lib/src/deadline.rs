//! One deadline per check, and only the search stages that can change its domain (step 4a of
//! `llm-dlc/loops/sound-verdicts.md`).
//!
//! A check is everything that decides one verdict: the tool's own checker, JBMC's search stages, JBMC's fallback
//! under `--engine auto`, the runs again with shared callees written out, and the vacuity probe. It gets the
//! `--timeout` once, as a [`Deadline`], where each of those runs used to get all of it. Each run is given a
//! budget out of what is left:
//!
//! | Run | Budget |
//! |---|---|
//! | a preliminary interval stage (`[0:20]`, `[-100000:100000]`) | at most [`STAGE_SHARE`] of the check |
//! | the own checker, under `--engine auto` | the check but [`FALLBACK_SHARE`], which JBMC's fallback is sure of |
//! | the own checker under `native`, JBMC's last stage, the probe | what is left |
//!
//! A preliminary stage that runs out of its budget hands on to the next stage, since only the last one, over
//! every input, is the proof. `--confirm` is a second check, by a second checker, and gets a deadline of its own.
//!
//! The interval stages exist to find a small witness first. `--java-assume-inputs-interval` bounds the primitive
//! inputs of the harness's entry method, not the elements of an array, so a stage whose interval holds every value
//! of every such input is the last stage again: [`stages_for`] leaves it out. A harness over arrays alone runs
//! once.

use std::time::{Duration, Instant};

use serde::Serialize;

use crate::classfile::Type;

/// Searched first, so that a counterexample is small enough to read; the last stage is the proof over all inputs.
pub const STAGES: &[Option<&str>] = &[Some("[0:20]"), Some("[-100000:100000]"), None];

/// The most of a check one preliminary interval stage may take.
pub const STAGE_SHARE: f64 = 0.125;

/// Under `--engine auto`, the part of a check kept for JBMC, should the own checker give no verdict.
pub const FALLBACK_SHARE: f64 = 0.25;

/// When a check must be over by.
#[derive(Debug, Clone, Copy)]
pub struct Deadline {
    started: Instant,
    total: Duration,
}

impl Deadline {
    pub fn starting_now(total: Duration) -> Deadline {
        Deadline { started: Instant::now(), total }
    }

    pub fn total(&self) -> Duration {
        self.total
    }

    /// The time left until the deadline; zero past it.
    pub fn left(&self) -> Duration {
        self.total.saturating_sub(self.started.elapsed())
    }

    /// At most `share` of the whole check, and never past its deadline.
    pub fn share(&self, share: f64) -> Duration {
        self.left().min(self.total.mul_f64(share))
    }

    /// What is left once `share` of the whole check is kept back for a later run.
    pub fn all_but(&self, share: f64) -> Duration {
        self.left().saturating_sub(self.total.mul_f64(share))
    }

    /// The budget of a JBMC stage: a preliminary one's share, or what is left for the last.
    pub fn for_stage(&self, stage: Option<&str>) -> Duration {
        match stage {
            Some(_) => self.share(STAGE_SHARE),
            None => self.left(),
        }
    }
}

/// The values a primitive of type `t` takes, when bounded; `None` for a floating-point type, which an interval
/// always restricts. Not called for a reference.
fn range(t: &Type) -> Option<(i128, i128)> {
    Some(match t {
        Type::Boolean => (0, 1),
        Type::Byte => (i8::MIN.into(), i8::MAX.into()),
        Type::Char => (0, u16::MAX.into()),
        Type::Short => (i16::MIN.into(), i16::MAX.into()),
        Type::Int => (i32::MIN.into(), i32::MAX.into()),
        Type::Long => (i64::MIN.into(), i64::MAX.into()),
        _ => return None,
    })
}

/// The bounds of an interval stage written as JBMC takes it, `[lo:hi]`.
fn interval(stage: &str) -> Option<(i128, i128)> {
    let (lo, hi) = stage.strip_prefix('[')?.strip_suffix(']')?.split_once(':')?;
    Some((lo.trim().parse().ok()?, hi.trim().parse().ok()?))
}

/// Whether a stage leaves out some value of a primitive input among `params`.
pub fn restricts(stage: &str, params: &[Type]) -> bool {
    let Some((lo, hi)) = interval(stage) else { return true };
    params.iter().filter(|t| !matches!(t, Type::Array(_) | Type::Object(_) | Type::Void)).any(|t| match range(t) {
        Some((min, max)) => min < lo || max > hi,
        None => true,
    })
}

/// The stages of [`STAGES`] worth running on a harness whose entry method takes `params`: each preliminary stage
/// that leaves out some input, then the last, over every input.
pub fn stages_for(params: &[Type]) -> Vec<Option<&'static str>> {
    STAGES.iter().copied().filter(|s| s.is_none_or(|s| restricts(s, params))).collect()
}

/// The parameters of the harness's entry method, read from its class file.
pub fn entry_parameters(class: &[u8], method: &str) -> Result<Vec<Type>, crate::Error> {
    let class = crate::classfile::ClassFile::parse(class)?;
    let m = class.methods.iter().find(|m| m.name == method).ok_or_else(|| crate::Error::new(format!("the harness has no method {method}")))?;
    Ok(m.parsed_descriptor()?.params)
}

/// One checker run of a check, with its budget: what [`crate::equivalence::Search::runs`] records, so that a
/// result shows that no run went past the check's deadline, and where the time went.
#[derive(Debug, Clone, Serialize)]
pub struct Run {
    /// `native` for the tool's own checker, `jbmc` for JBMC.
    pub checker: String,
    /// What the run was for: `proof`, `fallback` (JBMC after the own checker gave no verdict), `shared` (with the
    /// shared callees as one function), `as-written` (again, without them), or `probe` (vacuity).
    pub purpose: String,
    /// The input interval of a preliminary JBMC stage; none for every input.
    pub stage: Option<String>,
    pub budget_seconds: f64,
    pub seconds: f64,
    /// `verified`, `violation`, `no-verdict`, or `out-of-time` when the budget ran out.
    pub ended: String,
    /// How the checker said the run ended ([`crate::jbmc::Ending`]): which kind of no verdict it was, above all.
    pub ending: crate::jbmc::Ending,
}

impl Run {
    pub fn of(result: &crate::jbmc::JbmcResult, purpose: &str, budget: Duration) -> Run {
        let ended = match result.verdict {
            crate::Verdict::Verified => "verified",
            crate::Verdict::Violation => "violation",
            crate::Verdict::Unverifiable if result.out_of_time() => "out-of-time",
            crate::Verdict::Unverifiable => "no-verdict",
        };
        Run {
            checker: if result.native.is_some() { "native" } else { "jbmc" }.into(),
            purpose: purpose.into(),
            stage: result.stage.clone().filter(|_| result.native.is_none()),
            budget_seconds: round(budget.as_secs_f64()),
            seconds: round(result.seconds),
            ended: ended.into(),
            ending: result.ending,
        }
    }
}

fn round(s: f64) -> f64 {
    (s * 1000.0).round() / 1000.0
}

/// Seconds as a message gives them: whole ones from ten up, tenths below.
pub fn seconds(d: Duration) -> String {
    let s = d.as_secs_f64();
    if s >= 10.0 { format!("{s:.0}") } else { format!("{s:.1}") }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_stage_runs_only_where_its_interval_leaves_out_an_input() {
        let all: Vec<Option<&str>> = STAGES.to_vec();
        assert_eq!(stages_for(&[Type::Int]), all);
        assert_eq!(stages_for(&[Type::Array(Box::new(Type::Int)), Type::Long]), all);
        assert_eq!(stages_for(&[]), vec![None], "nothing to bound");
        let arrays = [Type::Array(Box::new(Type::Char)), Type::Array(Box::new(Type::Byte))];
        assert_eq!(stages_for(&arrays), vec![None], "an interval does not bound an array's elements: 142's harness runs once");
        assert_eq!(stages_for(&[Type::Boolean, Type::Boolean]), vec![None], "[0:20] holds both booleans");
        assert_eq!(stages_for(&[Type::Byte]), vec![Some("[0:20]"), None], "[-100000:100000] holds every byte");
        assert_eq!(stages_for(&[Type::Char, Type::Short, Type::Boolean]), vec![Some("[0:20]"), None]);
        assert_eq!(stages_for(&[Type::Double]), all, "a floating-point input is bounded by any interval");
        assert!(restricts("not an interval", &[]), "a stage it cannot read is kept");
    }

    #[test]
    fn a_check_has_one_deadline_and_each_run_a_budget_out_of_it() {
        let d = Deadline::starting_now(Duration::from_secs(80));
        assert!(d.left() <= Duration::from_secs(80) && d.left() > Duration::from_secs(79));
        assert!(d.for_stage(Some("[0:20]")) <= Duration::from_secs(10));
        assert!(d.for_stage(None) > Duration::from_secs(79));
        assert!(d.all_but(FALLBACK_SHARE) <= Duration::from_secs(60) && d.all_but(FALLBACK_SHARE) > Duration::from_secs(59));
        let past = Deadline { started: Instant::now() - Duration::from_secs(5), total: Duration::from_secs(2) };
        assert_eq!(past.left(), Duration::ZERO);
        assert_eq!(past.share(STAGE_SHARE), Duration::ZERO);
        assert_eq!(past.all_but(FALLBACK_SHARE), Duration::ZERO);
        assert_eq!(seconds(Duration::from_millis(750)), "0.8");
        assert_eq!(seconds(Duration::from_secs(600)), "600");
    }
}
