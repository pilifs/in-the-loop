//! R3's measurement (`llm-dlc/loops/application-core-reuse.md`): where a run's proofs spend their time around the
//! proof cache, recorded as a ledger of spans while a caller asks for it ([`begin`], [`end`]), and nothing otherwise.
//!
//! The spans are the proof cache's own steps, timed where they run, in this stream's files:
//!
//! | Stage | What it times | Where |
//! |---|---|---|
//! | `plan` | what the two versions share: the reach of both targets, their closures compared, and the helpers asked for | [`crate::shared::plan_with`] |
//! | `helper-proof` | a changed helper's own check or summary, inside its caller's `plan`, a whole proof of its own | [`crate::proof_cache::Helpers::prove`] |
//! | `key` | the claim and its key: both versions' closures digested (`closures`, inside it), the harness's digest, the tools' identity and the models' digest | [`crate::proof_cache::Regression::lookup`] |
//! | `lookup` | reading the store, and a stored refutation's witness replayed (`replay`, inside it) | the same |
//! | `store` | writing a result, and a refutation's witness replayed first (`replay`, inside it) | [`crate::proof_cache::Entry::store`] |
//!
//! Each proof's checker runs are recorded once it has a verdict, at `store` ([`solved`]): their seconds, and their
//! own phases, the class files read and decoded for the checker (`loading`) and decoded into its instructions
//! (`lowering`) apart from exploring and solving. What none of these covers is the rest of a proof's preparation
//! (relocating the old version, reading the target's classes, the layout, generating and writing the harness), what
//! follows its runs (replaying and shrinking a witness, running it on a JVM, the statement), and what the caller does
//! between proofs. [`proofs`] splits a ledger into proofs and gives each its stretch before its first span, so that
//! the rest is placed proof by proof without a hook in another stream's files.

use std::cell::RefCell;
use std::time::Instant;

use serde::Serialize;

/// A step of a proof around the proof cache (the module's table).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Stage {
    Plan,
    HelperProof,
    Key,
    Closures,
    Lookup,
    Replay,
    Store,
}

/// One span: its stage, the proof's target, when it started (seconds since [`begin`]), how long it took, and the
/// span it is inside, if any.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Span {
    pub stage: Stage,
    pub target: String,
    pub start: f64,
    pub seconds: f64,
    pub parent: Option<usize>,
}

/// A proof's checker runs, as they ended (recorded at `store`, so a hit has none).
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Solved {
    pub target: String,
    /// The span the runs belong under: the `store` span recording them.
    pub span: Option<usize>,
    pub verdict: String,
    pub runs: usize,
    /// The runs' seconds.
    pub seconds: f64,
    /// Their phases, summed: reading and decoding classes, lowering, exploring, encoding, solving, the witness and
    /// the rest ([`crate::phases::Phases`]).
    pub phases: crate::phases::Phases,
}

/// What a run recorded.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Ledger {
    /// From [`begin`] to [`end`].
    pub seconds: f64,
    pub spans: Vec<Span>,
    pub solved: Vec<Solved>,
}

struct Recording {
    started: Instant,
    ledger: Ledger,
    open: Vec<usize>,
}

thread_local! {
    static RECORDING: RefCell<Option<Recording>> = const { RefCell::new(None) };
}

/// Starts a ledger on this thread; one begun before and not ended is dropped.
pub fn begin() {
    RECORDING.with(|r| *r.borrow_mut() = Some(Recording { started: Instant::now(), ledger: Ledger::default(), open: Vec::new() }));
}

/// Ends the ledger begun on this thread; `None` when none was.
pub fn end() -> Option<Ledger> {
    let recording = RECORDING.with(|r| r.borrow_mut().take())?;
    let mut ledger = recording.ledger;
    ledger.seconds = recording.started.elapsed().as_secs_f64();
    Some(ledger)
}

/// Runs `f`, as a span of `stage` for the proof of `target` when a ledger is being recorded.
pub fn span<T>(stage: Stage, target: &str, f: impl FnOnce() -> T) -> T {
    let index = RECORDING.with(|r| {
        let mut r = r.borrow_mut();
        let rec = r.as_mut()?;
        let index = rec.ledger.spans.len();
        let parent = rec.open.last().copied();
        rec.ledger.spans.push(Span { stage, target: target.to_string(), start: rec.started.elapsed().as_secs_f64(), seconds: 0.0, parent });
        rec.open.push(index);
        Some(index)
    });
    let out = f();
    if let Some(index) = index {
        RECORDING.with(|r| {
            if let Some(rec) = r.borrow_mut().as_mut() {
                let now = rec.started.elapsed().as_secs_f64();
                if let Some(s) = rec.ledger.spans.get_mut(index) {
                    s.seconds = now - s.start;
                }
                rec.open.retain(|i| *i != index);
            }
        });
    }
    out
}

/// Records a proof's checker runs under the span open now (its `store`).
pub fn solved(target: &str, verdict: &str, search: Option<&crate::equivalence::Search>) {
    RECORDING.with(|r| {
        let mut r = r.borrow_mut();
        let Some(rec) = r.as_mut() else { return };
        let mut solved = Solved { target: target.to_string(), span: rec.open.last().copied(), verdict: verdict.to_string(), ..Default::default() };
        for run in search.map(|s| s.runs.as_slice()).unwrap_or_default() {
            solved.runs += 1;
            solved.seconds += run.seconds;
            if let Some(p) = &run.profile.phases {
                let s = &mut solved.phases;
                s.loading += p.loading;
                s.lowering += p.lowering;
                s.symbolic += p.symbolic;
                s.encoding += p.encoding;
                s.solving += p.solving;
                s.trace += p.trace;
                s.other += p.other;
            }
        }
        rec.ledger.solved.push(solved);
    });
}

/// One proof of a ledger, its spans placed in it: among the spans with the same parent, a proof starts at a `plan`,
/// at a `key` when the proof before it already has one, and at any span of another target.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Proof {
    pub target: String,
    /// The `helper-proof` it is inside, by its proof's index, for a helper's own proof.
    pub inside: Option<usize>,
    /// Hit, miss (proved and stored, or proved and not stored), identical (nothing to prove), or not keyed.
    pub cache: String,
    /// From the end of what came before it (the proof before it at the same level, the start of the helper proof
    /// it is inside, or [`begin`]) to its first span: the rest of its preparation, with the caller's own steps
    /// between proofs.
    pub before: f64,
    /// `plan`, less the helper proofs inside it.
    pub plan: f64,
    pub helpers: f64,
    /// `key`, `closures` included.
    pub key: f64,
    pub closures: f64,
    /// `lookup` and `store`, `replay` included.
    pub lookup: f64,
    pub store: f64,
    pub replay: f64,
    /// From the lookup's end to the store's start: the checker's runs and what follows them.
    pub after_lookup: f64,
    /// The checker's runs, of `after_lookup`.
    pub runs: f64,
    /// Of `runs`, reading and decoding classes (`loading`) and decoding methods (`lowering`).
    pub loading: f64,
    pub lowering: f64,
}

/// The proofs of a ledger, in order, a helper's own proof right after its caller's, which it is inside.
pub fn proofs(ledger: &Ledger) -> Vec<Proof> {
    let mut out = Vec::new();
    place(ledger, None, None, 0.0, &mut out);
    out
}

fn children(ledger: &Ledger, parent: Option<usize>) -> impl Iterator<Item = (usize, &Span)> {
    ledger.spans.iter().enumerate().filter(move |(_, s)| s.parent == parent)
}

fn within(ledger: &Ledger, parent: usize, stage: Stage) -> f64 {
    children(ledger, Some(parent)).filter(|(_, s)| s.stage == stage).map(|(_, s)| s.seconds).sum()
}

fn place(ledger: &Ledger, parent: Option<usize>, inside: Option<usize>, from: f64, out: &mut Vec<Proof>) {
    let mut last_end = from;
    let mut current: Option<(usize, f64)> = None;
    let mut keyed = false;
    for (i, s) in children(ledger, parent) {
        // A plan names its target with its parameters, the cache as the check's options do, with or without them.
        let method = |t: &str| t.split('(').next().unwrap_or(t).to_string();
        let other = current.is_none_or(|(p, _)| method(&out[p].target) != method(&s.target));
        let starts = match s.stage {
            Stage::Plan => true,
            Stage::Key => keyed || other,
            _ => other,
        };
        if starts {
            if let Some((_, end)) = current {
                last_end = end;
            }
            out.push(Proof { target: s.target.clone(), inside, cache: "identical".into(), before: s.start - last_end, ..Default::default() });
            current = Some((out.len() - 1, s.start));
            keyed = false;
        }
        let Some((p, _)) = current else { continue };
        match s.stage {
            Stage::Plan => {
                let mut helpers = 0.0;
                for (h, hs) in children(ledger, Some(i)).filter(|(_, c)| c.stage == Stage::HelperProof) {
                    helpers += hs.seconds;
                    place(ledger, Some(h), Some(p), hs.start, out);
                }
                out[p].plan += s.seconds - helpers;
                out[p].helpers += helpers;
            }
            Stage::Key => {
                keyed = true;
                out[p].key += s.seconds;
                out[p].closures += within(ledger, i, Stage::Closures);
                out[p].cache = "not keyed".into();
            }
            Stage::Lookup => {
                out[p].lookup += s.seconds;
                out[p].replay += within(ledger, i, Stage::Replay);
                out[p].cache = "hit".into();
            }
            Stage::Store => {
                let lookup_end = children(ledger, parent).filter(|(j, x)| *j < i && x.stage == Stage::Lookup).map(|(_, x)| x.start + x.seconds).last().unwrap_or(s.start);
                out[p].after_lookup += s.start - lookup_end;
                out[p].store += s.seconds;
                out[p].replay += within(ledger, i, Stage::Replay);
                out[p].cache = "miss".into();
                for solved in ledger.solved.iter().filter(|x| x.span == Some(i)) {
                    out[p].runs += solved.seconds;
                    out[p].loading += solved.phases.loading;
                    out[p].lowering += solved.phases.lowering;
                }
            }
            _ => {}
        }
        if let Some((p, _)) = current {
            current = Some((p, s.start + s.seconds));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(stage: Stage, target: &str, start: f64, seconds: f64, parent: Option<usize>) -> Span {
        Span { stage, target: target.into(), start, seconds, parent }
    }

    #[test]
    fn a_ledger_is_split_into_proofs_with_a_helpers_own_proof_inside_its_callers_plan() {
        // Caller `t`: before 0.1, plan 0.1..0.6 holding the helper `h`'s proof 0.2..0.5 (its plan at 0.25, key, a
        // lookup that misses, runs, store); then t's key, a lookup that hits. Then `u`: a key and a lookup only.
        let spans = vec![
            s(Stage::Plan, "t", 0.1, 0.5, None),
            s(Stage::HelperProof, "t", 0.2, 0.3, Some(0)),
            s(Stage::Plan, "h", 0.25, 0.01, Some(1)),
            s(Stage::Key, "h", 0.26, 0.02, Some(1)),
            s(Stage::Closures, "h", 0.26, 0.01, Some(3)),
            s(Stage::Lookup, "h", 0.28, 0.01, Some(1)),
            s(Stage::Store, "h", 0.4, 0.05, Some(1)),
            s(Stage::Replay, "h", 0.41, 0.03, Some(6)),
            s(Stage::Key, "t(int)", 0.6, 0.1, None),
            s(Stage::Lookup, "t", 0.7, 0.05, None),
            s(Stage::Key, "u", 1.0, 0.1, None),
            s(Stage::Lookup, "u", 1.1, 0.1, None),
        ];
        let solved = vec![Solved { target: "h".into(), span: Some(6), verdict: "verified".into(), runs: 1, seconds: 0.08, phases: crate::phases::Phases { loading: 0.01, lowering: 0.02, ..Default::default() } }];
        let ledger = Ledger { seconds: 1.3, spans, solved };
        let p = proofs(&ledger);
        let close = |a: f64, b: f64| (a - b).abs() < 1e-9;
        assert_eq!(p.iter().map(|x| (x.target.as_str(), x.cache.as_str(), x.inside)).collect::<Vec<_>>(), [("t", "hit", None), ("h", "miss", Some(0)), ("u", "hit", None)]);
        let (t, h, u) = (&p[0], &p[1], &p[2]);
        assert!(close(t.before, 0.1) && close(t.plan, 0.2) && close(t.helpers, 0.3) && close(t.key, 0.1) && close(t.lookup, 0.05), "{t:?}");
        assert!(close(h.before, 0.05) && close(h.plan, 0.01) && close(h.key, 0.02) && close(h.closures, 0.01) && close(h.lookup, 0.01), "{h:?}");
        assert!(close(h.after_lookup, 0.4 - 0.29) && close(h.runs, 0.08) && close(h.loading, 0.01) && close(h.lowering, 0.02) && close(h.store, 0.05) && close(h.replay, 0.03), "{h:?}");
        assert!(close(u.before, 1.0 - 0.75) && close(u.key, 0.1), "{u:?}");
    }

    #[test]
    fn nothing_is_recorded_without_a_ledger_and_spans_nest_with_one() {
        assert_eq!(span(Stage::Key, "t", || 7), 7);
        assert!(end().is_none());
        begin();
        span(Stage::Lookup, "t", || span(Stage::Replay, "t", || ()));
        let ledger = end().expect("a ledger");
        assert_eq!(ledger.spans.iter().map(|s| (s.stage, s.parent)).collect::<Vec<_>>(), [(Stage::Lookup, None), (Stage::Replay, Some(0))]);
        assert!(end().is_none(), "ended once");
    }
}
