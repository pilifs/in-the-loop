//! Transcripts of the own checker's solver calls: every clause the engine gives the SAT solver and every call it
//! makes, in order, so that the same sequence of incremental queries can be run again, on the same solver or another,
//! without the engine. A check is hundreds of calls on one growing formula (942 on the bounded binary search, 1,044
//! on example 141), and the lemmas the engine adds between them depend on the models it was given, so a solver is
//! judged here on the sequence as the engine asked it, not on one final formula.
//!
//! The format is CaDiCaL's incremental CNF (`p inccnf`), which CaDiCaL's own front end reads: a clause is a line of
//! literals ending in `0`, as in DIMACS, and a call is a line `a` of the call's assumptions ending in `0`. Each call
//! is followed by a comment saying how it went, which a reader of `inccnf` skips:
//!
//! ```text
//! c answer sat 0.000412 limit 599.871
//! c answer unknown 0.081250 limit 599.790 conflicts 2048
//! ```
//!
//! the answer (`sat`, `unsat`, or `unknown` when the solver stopped at its limit), the seconds the call took, the
//! per-call time limit it was given, and the conflict limit when it was given one (a branch probe's budget). Comments before the `p inccnf` line say what was checked and with what (the
//! tool's version, the solver, the method and the engine's options), and a last comment says how the check ended.
//! A call the engine settles without the solver (an assumption that is the constant false) is not a call, and is not
//! written.
//!
//! A transcript is written when [`super::Options::transcript`] names a file, or, for a check whose options don't, when
//! the environment variable [`ENV`] names a directory: each check in the process then writes a file of its own there,
//! named by the process and a count. The variable reaches checks that the proof drivers, the benchmark or a job run
//! without a flag of their own for it. [`replay`] runs a transcript again (`jvmcontract transcript FILE`).

use std::fs::File;
use std::io::{self, BufRead, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};

use super::bits::Lit;

/// The environment variable naming a directory to write every check's transcript into.
pub const ENV: &str = "JVMCONTRACT_TRANSCRIPTS";

/// The checks of this process that wrote a transcript into [`ENV`]'s directory, for their file names.
static WRITTEN: AtomicU64 = AtomicU64::new(0);

/// Where a check's transcript goes: the file named, or a new file in [`ENV`]'s directory, or nowhere.
pub fn destination(named: Option<&Path>) -> Option<PathBuf> {
    if let Some(path) = named {
        return Some(path.to_path_buf());
    }
    let dir = std::env::var_os(ENV).filter(|d| !d.is_empty())?;
    let n = WRITTEN.fetch_add(1, Ordering::Relaxed) + 1;
    Some(Path::new(&dir).join(format!("{}-{n}.icnf", std::process::id())))
}

/// A transcript being written. Writing is buffered; the first error is kept and reported by [`Transcript::finish`],
/// and nothing more is written after it.
pub struct Transcript {
    out: BufWriter<File>,
    path: PathBuf,
    calls: u64,
    clauses: u64,
    error: Option<io::Error>,
}

impl std::fmt::Debug for Transcript {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Transcript({}, {} clauses, {} calls)", self.path.display(), self.clauses, self.calls)
    }
}

impl Transcript {
    /// Starts a transcript at `path` (its directory made if missing), with `header` as its first comments.
    pub fn create(path: &Path, header: &[String]) -> io::Result<Transcript> {
        if let Some(dir) = path.parent().filter(|d| !d.as_os_str().is_empty()) {
            std::fs::create_dir_all(dir)?;
        }
        let mut out = BufWriter::with_capacity(1 << 16, File::create(path)?);
        for line in header {
            for part in line.lines() {
                writeln!(out, "c {part}")?;
            }
        }
        writeln!(out, "p inccnf")?;
        Ok(Transcript { out, path: path.to_path_buf(), calls: 0, clauses: 0, error: None })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    fn write(&mut self, body: impl FnOnce(&mut BufWriter<File>) -> io::Result<()>) {
        if self.error.is_none() {
            if let Err(e) = body(&mut self.out) {
                self.error = Some(e);
            }
        }
    }

    /// A clause, as given to the solver.
    pub fn clause(&mut self, lits: &[Lit]) {
        self.clauses += 1;
        self.write(|out| {
            for l in lits {
                write!(out, "{l} ")?;
            }
            writeln!(out, "0")
        });
    }

    /// A call under `assumptions`, with the per-call time `limit` and conflict limit it was given, what it answered
    /// and how long it took.
    pub fn call(&mut self, assumptions: &[Lit], limit: Option<f32>, conflicts: Option<u64>, answer: Option<bool>, took: Duration) {
        self.calls += 1;
        self.write(|out| {
            write!(out, "a ")?;
            for l in assumptions {
                write!(out, "{l} ")?;
            }
            writeln!(out, "0")?;
            write!(out, "c answer {} {:.6}", answer_name(answer), took.as_secs_f64())?;
            if let Some(limit) = limit {
                write!(out, " limit {limit:.3}")?;
            }
            if let Some(conflicts) = conflicts {
                write!(out, " conflicts {conflicts}")?;
            }
            writeln!(out)
        });
    }

    /// A comment line (each line of `text` its own).
    pub fn comment(&mut self, text: &str) {
        self.write(|out| {
            for part in text.lines() {
                writeln!(out, "c {part}")?;
            }
            Ok(())
        });
    }

    /// Ends the transcript with `last` as a comment, and says where it is, or what went wrong writing it.
    pub fn finish(mut self, last: &str) -> io::Result<PathBuf> {
        self.comment(&format!("end: {} clauses, {} calls; {last}", self.clauses, self.calls));
        if let Some(e) = self.error.take() {
            return Err(e);
        }
        self.out.flush()?;
        Ok(self.path)
    }
}

pub(crate) fn answer_name(answer: Option<bool>) -> &'static str {
    match answer {
        Some(true) => "sat",
        Some(false) => "unsat",
        None => "unknown",
    }
}

/// One call of a transcript, as recorded and as run again.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct Call {
    /// How many clauses the formula had when the call was made.
    pub clauses: u64,
    pub assumptions: usize,
    /// The answer recorded: `sat`, `unsat` or `unknown`.
    pub recorded: &'static str,
    pub recorded_seconds: f64,
    /// The per-call time limit recorded, which the replay gives the call too unless told otherwise.
    pub limit: Option<f64>,
    /// The conflict limit recorded, which the replay gives the call too.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub conflicts: Option<u64>,
    pub replayed: &'static str,
    pub replayed_seconds: f64,
}

/// A transcript run again.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct Replay {
    pub transcript: PathBuf,
    /// The solver the transcript was recorded with, from its header, and the one it was run on now.
    pub recorded_solver: Option<String>,
    pub solver: String,
    pub variables: i32,
    pub clauses: u64,
    pub calls: Vec<Call>,
    pub recorded_seconds: f64,
    pub replayed_seconds: f64,
    /// The whole replay: reading the transcript, adding the clauses and every call.
    pub seconds: f64,
    /// Calls answered `sat` one way and `unsat` the other: a solver that is wrong, or a transcript that is not what
    /// the engine asked. A call that is `unknown` on either side is not a contradiction.
    pub contradictions: usize,
    /// Calls the recording decided and the replay did not, and the other way round.
    pub undecided: usize,
    pub decided: usize,
    /// How the recorded check ended, from the transcript's last comment.
    pub ending: Option<String>,
}

impl Replay {
    /// One line on the replay, for a terminal.
    pub fn summary(&self) -> String {
        let s = |n: usize| if n == 1 { "" } else { "s" };
        format!(
            "{} calls over {} clauses and {} variables: {:.3} s solving on {} against {:.3} s recorded{}; {} contradiction{}, {} undecided now that were decided, {} decided now that were not",
            self.calls.len(),
            self.clauses,
            self.variables,
            self.replayed_seconds,
            self.solver,
            self.recorded_seconds,
            self.recorded_solver.as_deref().map(|r| format!(" on {r}")).unwrap_or_default(),
            self.contradictions,
            s(self.contradictions),
            self.undecided,
            self.decided,
        )
    }
}

/// What a line of a transcript is.
#[derive(Debug, PartialEq)]
enum Line {
    Clause(Vec<Lit>),
    Call(Vec<Lit>),
    /// The comment after a call: the answer, the seconds, the time limit and the conflict limit.
    Answer(Option<bool>, f64, Option<f64>, Option<u64>),
    Comment(String),
    Header,
}

fn parse_lits<'a>(words: impl Iterator<Item = &'a str>, n: usize) -> Result<Vec<Lit>, String> {
    let mut lits = Vec::new();
    let mut ended = false;
    for w in words {
        if ended {
            return Err(format!("line {n}: something after the closing 0"));
        }
        let l: Lit = w.parse().map_err(|_| format!("line {n}: {w:?} is not a literal"))?;
        if l == 0 {
            ended = true;
        } else if l == Lit::MIN {
            return Err(format!("line {n}: {l} is not a literal"));
        } else {
            lits.push(l);
        }
    }
    if !ended {
        return Err(format!("line {n}: no closing 0"));
    }
    Ok(lits)
}

fn parse_line(line: &str, n: usize) -> Result<Line, String> {
    let line = line.trim();
    if let Some(rest) = line.strip_prefix("c answer ") {
        let words: Vec<&str> = rest.split_whitespace().collect();
        let answer = match words.first() {
            Some(&"sat") => Some(true),
            Some(&"unsat") => Some(false),
            Some(&"unknown") => None,
            _ => return Err(format!("line {n}: an answer that is not sat, unsat or unknown")),
        };
        let seconds = words.get(1).and_then(|w| w.parse().ok()).ok_or_else(|| format!("line {n}: an answer with no seconds"))?;
        let mut rest = words.get(2..).unwrap_or(&[]);
        let mut limit = None;
        if let ["limit", l, more @ ..] = rest {
            limit = Some(l.parse().map_err(|_| format!("line {n}: a limit that is not a number"))?);
            rest = more;
        }
        let mut conflicts = None;
        if let ["conflicts", c, more @ ..] = rest {
            conflicts = Some(c.parse().map_err(|_| format!("line {n}: a conflict limit that is not a number"))?);
            rest = more;
        }
        if !rest.is_empty() {
            return Err(format!("line {n}: something after the answer's seconds that is not a limit"));
        }
        return Ok(Line::Answer(answer, seconds, limit, conflicts));
    }
    if line == "c" || line.starts_with("c ") {
        return Ok(Line::Comment(line.get(2..).unwrap_or("").to_string()));
    }
    if line == "p inccnf" {
        return Ok(Line::Header);
    }
    if let Some(rest) = line.strip_prefix("a ") {
        return Ok(Line::Call(parse_lits(rest.split_whitespace(), n)?));
    }
    Ok(Line::Clause(parse_lits(line.split_whitespace(), n)?))
}

/// Runs the transcript at `path` again on the bundled CaDiCaL, call by call, each with its recorded time limit, or
/// with `limit` seconds when one is given, and its recorded conflict limit if any, and compares the answers with the
/// recorded ones.
pub fn replay(path: &Path, limit: Option<f32>) -> Result<Replay, crate::Error> {
    replay_on(&mut super::sat::Cadical::new(), path, limit)
}

/// [`replay`] on `solver`, which must hold no clauses yet: any solver behind the engine's interface.
pub fn replay_on(solver: &mut dyn super::sat::Sat, path: &Path, limit: Option<f32>) -> Result<Replay, crate::Error> {
    let started = Instant::now();
    let file = File::open(path).map_err(|e| crate::Error::new(format!("cannot read {}: {e}", path.display())))?;
    let mut header = false;
    let mut recorded_solver = None;
    let mut ending = None;
    let mut clauses = 0u64;
    let mut calls: Vec<Call> = Vec::new();
    // The call made and not yet given its recorded answer.
    let mut open: Option<Vec<Lit>> = None;
    for (i, line) in io::BufReader::new(file).lines().enumerate() {
        let n = i + 1;
        let line = line.map_err(|e| crate::Error::new(format!("cannot read {}: {e}", path.display())))?;
        if line.trim().is_empty() {
            continue;
        }
        let parsed = parse_line(&line, n).map_err(|e| crate::Error::new(format!("{}: {e}", path.display())))?;
        if open.is_some() && !matches!(parsed, Line::Answer(..)) {
            return Err(crate::Error::new(format!("{}: line {n}: a call with no recorded answer after it", path.display())));
        }
        match parsed {
            Line::Comment(text) => {
                if let Some(s) = text.strip_prefix("solver: ") {
                    recorded_solver.get_or_insert_with(|| s.to_string());
                } else if text.starts_with("end: ") {
                    ending = Some(text);
                }
            }
            Line::Header => header = true,
            _ if !header => return Err(crate::Error::new(format!("{}: line {n}: no `p inccnf` line before the formula", path.display()))),
            Line::Clause(lits) => {
                solver.add_clause(&lits);
                clauses += 1;
            }
            Line::Call(assumptions) => {
                // The recorded limit is only known from the answer line, so the call is made there.
                calls.push(Call { clauses, assumptions: assumptions.len(), recorded: "", recorded_seconds: 0.0, limit: None, conflicts: None, replayed: "", replayed_seconds: 0.0 });
                open = Some(assumptions);
            }
            Line::Answer(answer, seconds, recorded_limit, conflicts) => {
                let Some(assumptions) = open.take() else {
                    return Err(crate::Error::new(format!("{}: line {n}: an answer with no call before it", path.display())));
                };
                solver.set_limit(limit.or(recorded_limit.map(|s| s as f32)));
                solver.set_work_limit(conflicts);
                let call_started = Instant::now();
                let replayed = solver.solve(&assumptions);
                let took = call_started.elapsed();
                let call = calls.last_mut().expect("the open call");
                call.recorded = answer_name(answer);
                call.recorded_seconds = seconds;
                call.limit = recorded_limit;
                call.conflicts = conflicts;
                call.replayed = answer_name(replayed);
                call.replayed_seconds = took.as_secs_f64();
            }
        }
    }
    if open.is_some() {
        return Err(crate::Error::new(format!("{}: the last call has no recorded answer", path.display())));
    }
    if !header {
        return Err(crate::Error::new(format!("{}: no `p inccnf` line", path.display())));
    }
    let both = |c: &Call| c.recorded != "unknown" && c.replayed != "unknown";
    Ok(Replay {
        transcript: path.to_path_buf(),
        recorded_solver,
        solver: solver.signature(),
        variables: solver.variables(),
        clauses,
        recorded_seconds: calls.iter().map(|c| c.recorded_seconds).sum(),
        replayed_seconds: calls.iter().map(|c| c.replayed_seconds).sum(),
        contradictions: calls.iter().filter(|c| both(c) && c.recorded != c.replayed).count(),
        undecided: calls.iter().filter(|c| c.recorded != "unknown" && c.replayed == "unknown").count(),
        decided: calls.iter().filter(|c| c.recorded == "unknown" && c.replayed != "unknown").count(),
        calls,
        seconds: started.elapsed().as_secs_f64(),
        ending,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_line_is_a_clause_a_call_an_answer_or_a_comment() {
        assert_eq!(parse_line("1 -2 0", 1), Ok(Line::Clause(vec![1, -2])));
        assert_eq!(parse_line("0", 1), Ok(Line::Clause(vec![])));
        assert_eq!(parse_line("a 3 -4 0", 1), Ok(Line::Call(vec![3, -4])));
        assert_eq!(parse_line("a 0", 1), Ok(Line::Call(vec![])));
        assert_eq!(parse_line("c answer sat 0.000412 limit 599.871", 1), Ok(Line::Answer(Some(true), 0.000412, Some(599.871), None)));
        assert_eq!(parse_line("c answer unknown 0.08125 limit 599.79 conflicts 2048", 1), Ok(Line::Answer(None, 0.08125, Some(599.79), Some(2048))));
        assert_eq!(parse_line("c answer unknown 1.5", 1), Ok(Line::Answer(None, 1.5, None, None)));
        assert_eq!(parse_line("c solver: CaDiCaL 1.9.5 (bundled)", 1), Ok(Line::Comment("solver: CaDiCaL 1.9.5 (bundled)".into())));
        assert_eq!(parse_line("p inccnf", 1), Ok(Line::Header));
        assert!(parse_line("1 2", 7).unwrap_err().contains("line 7: no closing 0"));
        assert!(parse_line("1 0 2", 7).is_err());
        assert!(parse_line("a x 0", 7).is_err());
        assert!(parse_line("c answer maybe 0.1", 7).is_err());
        assert!(parse_line("c answer sat 0.1 limit", 7).is_err());
        assert!(parse_line("c answer sat 0.1 limit 1.0 conflicts many", 7).is_err());
        assert!(parse_line("c answer sat 0.1 conflicts 5 limit 1.0", 7).is_err());
    }

    fn written(dir: &Path, body: impl FnOnce(&mut Transcript)) -> PathBuf {
        let path = dir.join("t.icnf");
        let mut t = Transcript::create(&path, &["solver: CaDiCaL 1.9.5 (bundled)".into()]).unwrap();
        body(&mut t);
        t.finish("Verified").unwrap()
    }

    #[test]
    fn a_transcript_replays_with_the_answers_it_recorded() {
        let dir = tempfile::tempdir().unwrap();
        // x1 or x2; not x1: sat under x2, unsat under not x2; then x2 is required, and asking for not x2 again is unsat.
        let path = written(dir.path(), |t| {
            t.clause(&[1, 2]);
            t.clause(&[-1]);
            t.call(&[2], Some(10.0), None, Some(true), Duration::from_micros(5));
            t.call(&[-2], Some(10.0), Some(64), Some(false), Duration::from_micros(5));
            t.clause(&[2, 3]);
            t.call(&[], None, None, Some(true), Duration::from_micros(5));
        });
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.starts_with("c solver: CaDiCaL 1.9.5 (bundled)\np inccnf\n1 2 0\n-1 0\na 2 0\nc answer sat 0.000005 limit 10.000\n"), "{text}");
        assert!(text.contains("a -2 0\nc answer unsat 0.000005 limit 10.000 conflicts 64\n"), "{text}");
        assert!(text.ends_with("c end: 3 clauses, 3 calls; Verified\n"), "{text}");
        let r = replay(&path, None).unwrap();
        assert_eq!((r.clauses, r.calls.len(), r.contradictions, r.undecided, r.decided), (3, 3, 0, 0, 0), "{r:?}");
        assert_eq!(r.calls.iter().map(|c| (c.clauses, c.recorded, c.replayed)).collect::<Vec<_>>(), [(2, "sat", "sat"), (2, "unsat", "unsat"), (3, "sat", "sat")]);
        assert_eq!(r.calls.iter().map(|c| c.conflicts).collect::<Vec<_>>(), [None, Some(64), None]);
        assert_eq!(r.recorded_solver.as_deref(), Some("CaDiCaL 1.9.5 (bundled)"));
        assert_eq!(r.ending.as_deref(), Some("end: 3 clauses, 3 calls; Verified"));
        assert_eq!(r.variables, 3);
    }

    #[test]
    fn an_answer_the_solver_does_not_give_again_is_a_contradiction() {
        let dir = tempfile::tempdir().unwrap();
        let path = written(dir.path(), |t| {
            t.clause(&[1]);
            t.call(&[-1], None, None, Some(true), Duration::ZERO);
            t.call(&[1], None, None, None, Duration::ZERO);
        });
        let r = replay(&path, None).unwrap();
        assert_eq!((r.contradictions, r.undecided, r.decided), (1, 0, 1), "{r:?}");
        assert!(r.summary().contains("1 contradiction,"), "{}", r.summary());
    }

    #[test]
    fn a_transcript_that_is_cut_short_or_out_of_order_is_refused() {
        let dir = tempfile::tempdir().unwrap();
        for (body, why) in [
            ("p inccnf\n1 0\na 0\n", "the last call has no recorded answer"),
            ("p inccnf\na 0\n1 0\n", "a call with no recorded answer after it"),
            ("p inccnf\nc answer sat 0.1\n", "an answer with no call before it"),
            ("1 0\n", "no `p inccnf` line before the formula"),
            ("c nothing\n", "no `p inccnf` line"),
        ] {
            let path = dir.path().join("bad.icnf");
            std::fs::write(&path, body).unwrap();
            let e = replay(&path, None).unwrap_err().to_string();
            assert!(e.contains(why), "{body:?}: {e}");
        }
    }

    #[test]
    fn a_check_without_a_file_named_writes_where_the_environment_says() {
        assert_eq!(destination(Some(Path::new("x.icnf"))), Some(PathBuf::from("x.icnf")));
        // The variable itself is not set here: tests run in parallel, and another check would write there too.
        if std::env::var_os(ENV).is_none() {
            assert_eq!(destination(None), None);
        }
    }
}
