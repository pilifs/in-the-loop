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
//!
//! Which of those stages JBMC runs is its [`Staging`] policy (`--jbmc-staging`, step 2a of
//! `llm-dlc/loops/engine-priorities.md`): all of them, as above (`staged`); the full range alone (`full-range`,
//! the default), whose counterexample the shrinker makes small instead; or the first alone, on [`TIGHT_SHARE`],
//! then the full range (`tight`). The deadline, the bounds, the models and what a verdict needs are the same under
//! each: only the last stage proves, and a preliminary stage out of its budget hands on.
//!
//! `full-range` is the default on the evidence of benchmark job `20261106-201041` (step 2c): over the corpus it
//! gave every proof `staged` gave, in less time (575 s against 654 s under strict, and half the time on the hard
//! ones: 26 s against 56 s on the bounded binary search, 31 s against 61 s on example 141), found its
//! counterexamples in a third of the time (9 s against 27 s), left no fallback under `--engine auto` without time
//! for the full range, and its witnesses, shrunk, were no larger. The one case it lost, `conformance/shiftRight/2`,
//! is JBMC's unmasked right shift ([`crate::jbmc_gaps`]), which `staged`'s witness happened to miss.

use std::time::{Duration, Instant};

use serde::Serialize;

use crate::classfile::Type;

/// Searched first, so that a counterexample is small enough to read; the last stage is the proof over all inputs.
pub const STAGES: &[Option<&str>] = &[Some("[0:20]"), Some("[-100000:100000]"), None];

/// The most of a check one preliminary interval stage may take.
pub const STAGE_SHARE: f64 = 0.125;

/// Under `--engine auto`, the part of a check kept for JBMC, should the own checker give no verdict.
pub const FALLBACK_SHARE: f64 = 0.25;

/// The most of a check the one preliminary stage of [`Staging::Tight`] may take: 3 s of a 120 s check, where a
/// stage of [`Staging::Staged`] may take 15 s.
pub const TIGHT_SHARE: f64 = 0.025;

/// Which of JBMC's interval stages a check runs before the full range (`--jbmc-staging`). The own checker's stages
/// are its own and do not follow it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Staging {
    /// Every stage of [`STAGES`] that leaves out an input, each on at most [`STAGE_SHARE`], then the full range.
    Staged,
    /// The full range alone: a counterexample is made small by the shrinker, not by a narrower search first. The
    /// default since job `20261106-201041` (the module's comment says why).
    #[default]
    FullRange,
    /// The first stage that leaves out an input, on at most [`TIGHT_SHARE`], then the full range.
    Tight,
}

impl Staging {
    pub const NAMES: &[&str] = &["staged", "full-range", "tight"];

    /// The stages to run, in order, on a harness whose entry method takes `params`; the last is the full range.
    pub fn stages(self, params: &[Type]) -> Vec<Option<&'static str>> {
        let all = stages_for(params);
        match self {
            Staging::Staged => all,
            Staging::FullRange => vec![None],
            Staging::Tight => all.iter().copied().filter(Option::is_some).take(1).chain([None]).collect(),
        }
    }

    /// The most of a check a preliminary stage may take.
    pub fn stage_share(self) -> f64 {
        match self {
            Staging::Tight => TIGHT_SHARE,
            Staging::Staged | Staging::FullRange => STAGE_SHARE,
        }
    }
}

impl std::fmt::Display for Staging {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Staging::Staged => "staged",
            Staging::FullRange => "full-range",
            Staging::Tight => "tight",
        })
    }
}

impl std::str::FromStr for Staging {
    type Err = crate::Error;
    fn from_str(s: &str) -> Result<Staging, crate::Error> {
        match s {
            "staged" => Ok(Staging::Staged),
            "full-range" => Ok(Staging::FullRange),
            "tight" => Ok(Staging::Tight),
            _ => Err(crate::Error::new(format!("unknown JBMC staging `{s}`: {}", Staging::NAMES.join(", ")))),
        }
    }
}

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

    /// The budget of a JBMC stage under `staging`: a preliminary one's share, or what is left for the last.
    pub fn for_stage(&self, stage: Option<&str>, staging: Staging) -> Duration {
        match stage {
            Some(_) => self.share(staging.stage_share()),
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
    /// Where its time went, phase by phase, and its formula's size: `phases` and `formula` ([`crate::phases`]).
    #[serde(flatten)]
    pub profile: crate::phases::Profile,
    /// The seconds by which the run's phases add up past `seconds`, beyond the tolerance ([`crate::phases::Phases::excess`]):
    /// a run whose phases cannot be trusted, flagged rather than scaled to fit. Absent when they fit.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub phases_excess: Option<f64>,
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
            profile: result.profile.clone(),
            phases_excess: result.profile.phases.as_ref().and_then(|p| p.excess(result.seconds)),
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
        assert!(d.for_stage(Some("[0:20]"), Staging::Staged) <= Duration::from_secs(10));
        assert!(d.for_stage(None, Staging::Staged) > Duration::from_secs(79));
        assert!(d.all_but(FALLBACK_SHARE) <= Duration::from_secs(60) && d.all_but(FALLBACK_SHARE) > Duration::from_secs(59));
        let past = Deadline { started: Instant::now() - Duration::from_secs(5), total: Duration::from_secs(2) };
        assert_eq!(past.left(), Duration::ZERO);
        assert_eq!(past.share(STAGE_SHARE), Duration::ZERO);
        assert_eq!(past.all_but(FALLBACK_SHARE), Duration::ZERO);
        assert_eq!(seconds(Duration::from_millis(750)), "0.8");
        assert_eq!(seconds(Duration::from_secs(600)), "600");
    }

    #[test]
    fn each_staging_policy_runs_its_stages_and_ends_on_the_full_range() {
        let int = [Type::Int];
        assert_eq!(Staging::Staged.stages(&int), vec![Some("[0:20]"), Some("[-100000:100000]"), None]);
        assert_eq!(Staging::FullRange.stages(&int), vec![None]);
        assert_eq!(Staging::Tight.stages(&int), vec![Some("[0:20]"), None], "the first stage only");
        // A stage that bounds nothing is left out under each policy.
        let byte = [Type::Byte];
        assert_eq!(Staging::Staged.stages(&byte), vec![Some("[0:20]"), None]);
        assert_eq!(Staging::Tight.stages(&byte), vec![Some("[0:20]"), None]);
        let arrays = [Type::Array(Box::new(Type::Int))];
        for staging in [Staging::Staged, Staging::FullRange, Staging::Tight] {
            assert_eq!(staging.stages(&arrays), vec![None], "{staging}: an array harness runs once");
            assert_eq!(staging.stages(&[Type::Long, Type::Char]).last(), Some(&None), "{staging}: the full range is last");
            assert_eq!(staging.to_string().parse::<Staging>().unwrap(), staging);
        }
        assert_eq!(Staging::default(), Staging::FullRange, "decided by job 20261106-201041");
        assert!("full".parse::<Staging>().unwrap_err().to_string().contains("staged, full-range, tight"));
        assert_eq!(serde_json::to_value(Staging::FullRange).unwrap(), "full-range");
    }

    #[test]
    fn the_tight_stage_has_a_smaller_budget_and_the_full_range_what_is_left() {
        let d = Deadline::starting_now(Duration::from_secs(120));
        let staged = d.for_stage(Some("[0:20]"), Staging::Staged);
        let tight = d.for_stage(Some("[0:20]"), Staging::Tight);
        assert!(staged <= Duration::from_secs(15) && staged > Duration::from_secs(14), "{staged:?}");
        assert!(tight <= Duration::from_secs(3) && tight > Duration::from_millis(2900), "{tight:?}");
        for staging in [Staging::Staged, Staging::FullRange, Staging::Tight] {
            assert!(d.for_stage(None, staging) > Duration::from_secs(119), "{staging}: the full range gets the rest of the check");
        }
        // Never past the deadline: under `auto`'s fallback, a stage's share can be all that is left.
        let late = Deadline { started: Instant::now() - Duration::from_secs(118), total: Duration::from_secs(120) };
        assert!(late.for_stage(Some("[0:20]"), Staging::Tight) <= Duration::from_secs(2));
    }
}
