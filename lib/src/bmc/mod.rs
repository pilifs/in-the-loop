//! Bounded model checking of a harness in the tool itself, without JBMC: the harness bytecode is executed
//! symbolically over bit-vectors ([`bits`]), one path at a time, and a bundled SAT solver (CaDiCaL) decides at
//! every branch which sides are feasible and, when a path reaches the harness's `AssertionError`, what input takes
//! it there. Each path carries a model of its condition (the solver's answer when it was split off), so the side
//! of a branch that model takes is known feasible and the solver is asked once per branch, about the other side,
//! and not at all about a condition the path has taken before. That one question is given as long as the solver's
//! calls so far took together, and a side undecided by then waits until the decided paths are done, so a violation
//! is not held up by an infeasible side that is hard to refute. A division is left to the solver under what holds
//! of every division and built as a circuit only where a model got it wrong ([`bits::Blaster::sdivrem_lazy`]).
//! Loops are unwound up to a bound, as JBMC's are, and a path that needs more is no verdict.
//!
//! The fragment this engine handles is the one the proofs are mostly about: static methods over `int`, `long`,
//! `short`, `byte`, `char` and `boolean`, straight-line and branching arithmetic, calls into the application's own
//! static methods (inlined), the `Math`/`StrictMath` exact and floor operations with their overflow exceptions,
//! `Integer`/`Long` comparisons, exceptions thrown and caught by class, and strings only as opaque objects (a
//! message built for an exception). Floating point, arrays, fields with state and the rest of the JDK are refused
//! with a reason, so that a caller can fall back to JBMC. A verdict it gives is on the same statement JBMC would
//! check, the generated harness class, so a counterexample is replayed and shrunk like JBMC's.

pub mod bits;

use std::collections::{BTreeMap, HashMap};
use std::rc::Rc;
use std::time::{Duration, Instant};

use crate::classfile::{ArithOp, BootstrapArg, ClassFile, Cond, ExceptionHandler, Insn, Kind, MethodDescriptor, Narrow, Type};
use crate::classpath::ClassPath;
use crate::{Error, Verdict};
use bits::{Bits, Blaster, Lit, Model, FALSE, TRUE};

/// What the engine is allowed.
#[derive(Debug, Clone)]
pub struct Options {
    /// How many times a loop's back edge may be taken on one path.
    pub unwind: u32,
    pub timeout: Duration,
    /// How many paths may be explored before the engine gives up.
    pub max_paths: u64,
}

impl Default for Options {
    fn default() -> Self {
        Options { unwind: 16, timeout: Duration::from_secs(600), max_paths: 200_000 }
    }
}

/// The ranges a violating input is looked for in, smallest first, so that a counterexample is small enough to
/// read: the same stages as JBMC is run through (`[0:20]`, then `[-100000:100000]`, then everything). The engine
/// explores every path once; on a path that violates the property it asks the solver for an input in the first
/// stage that has one, and goes on to the next path only while no path has given one in the first stage.
pub const STAGES: &[(i64, i64)] = &[(0, 20), (-100_000, 100_000)];

/// The engine's answer about one harness.
#[derive(Debug, Clone)]
pub struct Outcome {
    pub verdict: Verdict,
    /// The violating input by parameter slot, as decimal numbers (a boolean as 0 or 1, a char by its code).
    pub raw_inputs: BTreeMap<u32, String>,
    /// The stage the violating input was found in, as JBMC's `--java-assume-inputs-interval` would spell it;
    /// `None` when only the whole range has one.
    pub stage: Option<String>,
    /// Why there is no verdict: something outside the fragment, a loop beyond the bound, or the budget.
    pub problem: Option<String>,
    pub paths: u64,
    pub solves: u64,
    pub solving: f64,
    pub evaluated: u64,
    pub evaluating: f64,
    pub clauses: u64,
    pub variables: i32,
    /// How many divisions were left to the solver under the cheap facts, and how many of them had their circuit
    /// built because the solver got one wrong ([`bits::Blaster::sdivrem_lazy`]).
    pub divisions: u64,
    pub refined: u64,
    pub seconds: f64,
    /// The solver, for the report.
    pub solver: String,
}

impl Outcome {
    /// The outcome in the shape of a JBMC result, so that the proof drivers treat it as one.
    pub fn into_jbmc_result(self, log: std::path::PathBuf) -> crate::jbmc::JbmcResult {
        crate::jbmc::JbmcResult {
            verdict: self.verdict,
            version: format!("jvmcontract's own checker ({})", self.solver),
            properties: 1,
            raw_inputs: self.raw_inputs,
            raw_arrays: BTreeMap::new(),
            stage: self.stage,
            problem: self.problem,
            log,
            seconds: self.seconds,
        }
    }

    /// One line on what the run did, for the log.
    pub fn summary(&self) -> String {
        format!("{:?}: {} paths, {} solver calls ({:.2} s), {} gates evaluated in path models ({:.2} s), {} of {} divisions built in full, {} variables, {} clauses, {:.2} s{}", self.verdict, self.paths, self.solves, self.solving, self.evaluated, self.evaluating, self.refined, self.divisions, self.variables, self.clauses, self.seconds, self.problem.as_deref().map(|p| format!("; {p}")).unwrap_or_default())
    }
}

/// Why a parameter type is outside the fragment, if it is.
pub fn unsupported_parameter(t: &Type) -> Option<String> {
    match t {
        Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long => None,
        other => Some(format!("a {} parameter", other.java_name())),
    }
}

/// A value on the operand stack or in a local: an int (32 bits, which boolean, byte, char and short are too), a
/// long, or a reference to an object this run made (an exception, a string) or `null`.
#[derive(Debug, Clone)]
enum Val {
    I(Bits),
    J(Bits),
    R(Option<usize>),
}

impl Val {
    fn category(&self) -> usize {
        match self {
            Val::J(_) => 2,
            _ => 1,
        }
    }
}

/// An object made during the run: its class, and the fields written so far (an application exception's, say).
#[derive(Debug, Clone)]
struct Obj {
    class: String,
    fields: BTreeMap<String, Val>,
}

/// A method's decoded code, shared by every frame that runs it.
struct Decoded {
    insns: Vec<Insn>,
    pcs: Vec<u32>,
    index: HashMap<u32, usize>,
    handlers: Vec<ExceptionHandler>,
    max_locals: usize,
}

#[derive(Clone)]
struct Frame {
    class: Rc<ClassFile>,
    method: String,
    code: Rc<Decoded>,
    /// The index (into `code.insns`) of the instruction being executed.
    at: usize,
    locals: Vec<Option<Val>>,
    stack: Vec<Val>,
}

impl Frame {
    fn pc(&self) -> u32 {
        self.code.pcs[self.at]
    }
}

/// One path through the harness: its frames, the condition that selects it (a conjunction of literals), a model
/// of that condition, its objects, and how often each back edge was taken.
#[derive(Clone)]
struct Path {
    frames: Vec<Frame>,
    cond: Vec<Lit>,
    /// An input that takes the path: the solver's answer when the path was split off, or every input zero for
    /// the first. The side of a branch it takes is feasible without asking the solver.
    model: Model,
    /// Whether the path is known feasible: a twin split off at a branch the solver did not decide within its
    /// probe's budget keeps its parent's model, which takes the other side, and waits in `Engine::deferred`
    /// until every decided path is done, when the solver is asked about it with all the time left.
    undecided: bool,
    objects: Vec<Obj>,
    back_edges: HashMap<(String, String, u32), u32>,
}

/// How a path ended.
enum End {
    /// The harness returned: the property holds on this path.
    Returned,
    /// The path condition cannot be satisfied.
    Infeasible,
    /// The harness's assertion failed on a path of this condition, which the solver found satisfiable.
    Violation(Vec<Lit>),
    /// A loop needed more iterations than the bound.
    Unwound(String),
}

/// Why the engine stops without a verdict.
enum Stop {
    Unsupported(String),
    Budget(String),
}

type Step = Result<Option<End>, Stop>;

/// Which sides of a branch are feasible under the path condition.
enum Sides {
    /// Both, the path's own model taking the then side or the else side, and `other` a model of the other.
    Both { model_takes_then: bool, other: Model },
    Then,
    Else,
    /// The side the path's model takes, the other undecided: the solver did not answer within the probe's budget.
    Undecided { model_takes_then: bool },
}

struct Engine<'a> {
    cp: &'a ClassPath,
    b: Blaster,
    codes: HashMap<(String, String, String), Rc<Decoded>>,
    pending: Vec<Path>,
    /// The paths the solver did not decide in time, taken up when `pending` is empty.
    deferred: Vec<Path>,
    unwind: u32,
    deadline: Instant,
    max_paths: u64,
    paths: u64,
    /// The harness's parameters: slot, type and bits, for reading the input off a model.
    params: Vec<(u32, Type, Bits)>,
    /// One literal per entry of [`STAGES`], true when every parameter is in the range; built at the first
    /// violation, so that a proof pays nothing for them.
    stage_lits: Vec<Option<Lit>>,
}

fn unsupported<T>(what: impl Into<String>) -> Result<T, Stop> {
    Err(Stop::Unsupported(what.into()))
}

/// Checks `class.method` of the harness: every path either returns or is infeasible (verified), or one throws the
/// `AssertionError` on an input the solver names (violation).
pub fn check(cp: &ClassPath, class: &str, method: &str, options: &Options) -> Result<Outcome, Error> {
    let started = Instant::now();
    let Some(harness) = cp.bytecode(class)? else {
        return Err(Error::new(format!("harness class {class} not found")));
    };
    let m = harness.method_by_name(method).ok_or_else(|| Error::new(format!("no method {method} in {class}")))?.clone();
    let descriptor = MethodDescriptor::parse(&m.descriptor)?;
    let mut engine = Engine {
        cp,
        b: Blaster::new(),
        codes: HashMap::new(),
        pending: Vec::new(),
        deferred: Vec::new(),
        unwind: options.unwind,
        deadline: started + options.timeout,
        max_paths: options.max_paths,
        paths: 0,
        params: Vec::new(),
        stage_lits: vec![None; STAGES.len()],
    };
    let solver = engine.b.signature();
    let outcome = |engine: &Engine, verdict: Verdict, raw_inputs: BTreeMap<u32, String>, stage: Option<String>, problem: Option<String>| Outcome {
        verdict,
        raw_inputs,
        stage,
        problem,
        paths: engine.paths,
        solves: engine.b.solves,
        solving: engine.b.solving.as_secs_f64(),
        evaluated: engine.b.evaluated,
        evaluating: engine.b.evaluating.as_secs_f64(),
        clauses: engine.b.clauses,
        variables: engine.b.variables(),
        divisions: engine.b.divisions(),
        refined: engine.b.refined,
        seconds: started.elapsed().as_secs_f64(),
        solver: solver.clone(),
    };

    // The inputs: fresh bits per parameter, in its range.
    let mut locals: Vec<Option<Val>> = Vec::new();
    let mut slot = 0u32;
    for t in &descriptor.params {
        if let Some(why) = unsupported_parameter(t) {
            return Ok(outcome(&engine, Verdict::Unverifiable, BTreeMap::new(), None, Some(format!("outside the fragment: {why}"))));
        }
        let bits = match t {
            Type::Boolean => {
                let mut v = vec![FALSE; 32];
                v[0] = engine.b.var();
                v
            }
            Type::Byte => {
                let small = engine.b.fresh(8);
                engine.b.sext(&small, 32)
            }
            Type::Char => {
                let small = engine.b.fresh(16);
                engine.b.zext(&small, 32)
            }
            Type::Short => {
                let small = engine.b.fresh(16);
                engine.b.sext(&small, 32)
            }
            Type::Int => engine.b.fresh(32),
            Type::Long => engine.b.fresh(64),
            _ => unreachable!(),
        };
        engine.params.push((slot, t.clone(), bits.clone()));
        locals.push(Some(if *t == Type::Long { Val::J(bits) } else { Val::I(bits) }));
        if *t == Type::Long {
            locals.push(None);
        }
        slot += u32::from(t.slots());
    }
    let code = engine.code(&harness, &m.name, &m.descriptor).map_err(|e| Error::new(stop_text(&e)))?;
    locals.resize(code.max_locals.max(locals.len()), None);
    let first = Path { frames: vec![Frame { class: harness.clone(), method: m.name.clone(), code, at: 0, locals, stack: Vec::new() }], cond: Vec::new(), model: Model::default(), undecided: false, objects: Vec::new(), back_edges: HashMap::new() };
    engine.pending.push(first);

    // The smallest violating input so far, by stage: a path that only has one outside the stages does not end the
    // search, since another path may have one in the first stage, as it does when the first path to fail is an
    // overflow and the second a rounding. The search for a better one is given as long again as the first took,
    // within the deadline; the violation stands whatever the remaining paths do.
    let mut best: Option<(usize, BTreeMap<u32, String>)> = None;
    let violation = |engine: &Engine, best: Option<(usize, BTreeMap<u32, String>)>| {
        let (stage, raw_inputs) = best.expect("a violation");
        let stage = STAGES.get(stage).map(|(lo, hi)| format!("[{lo}:{hi}]"));
        outcome(engine, Verdict::Violation, raw_inputs, stage, None)
    };
    loop {
        let path = match engine.next_path() {
            Ok(Some(path)) => path,
            Ok(None) => break,
            Err(stop) => return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, BTreeMap::new(), None, Some(stop_text(&stop))) }),
        };
        engine.paths += 1;
        if engine.paths > engine.max_paths {
            return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, BTreeMap::new(), None, Some(format!("more than {} paths; the budget is spent", engine.max_paths))) });
        }
        match engine.run(path) {
            Ok(End::Returned) | Ok(End::Infeasible) => {}
            Ok(End::Violation(cond)) => {
                let (stage, raw_inputs) = match engine.staged_input(&cond) {
                    Ok(found) => found,
                    Err(stop) if best.is_some() => {
                        let _ = stop;
                        return Ok(violation(&engine, best));
                    }
                    Err(stop) => return Ok(outcome(&engine, Verdict::Unverifiable, BTreeMap::new(), None, Some(stop_text(&stop)))),
                };
                if best.as_ref().is_none_or(|(s, _)| stage < *s) {
                    if best.is_none() {
                        let elapsed = started.elapsed();
                        engine.deadline = engine.deadline.min(Instant::now() + elapsed.max(Duration::from_secs(1)));
                    }
                    best = Some((stage, raw_inputs));
                }
                if stage == 0 {
                    return Ok(violation(&engine, best));
                }
            }
            Ok(End::Unwound(what)) => {
                return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, BTreeMap::new(), None, Some(format!("a loop was not fully unwound with --unwind {} ({what})", options.unwind))) })
            }
            Err(Stop::Unsupported(what)) => {
                return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, BTreeMap::new(), None, Some(format!("outside the fragment: {what}"))) })
            }
            Err(Stop::Budget(what)) => return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, BTreeMap::new(), None, Some(what)) }),
        }
    }
    Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Verified, BTreeMap::new(), None, None) })
}

/// Runs the engine on a harness for the proof drivers: the class path is the harness, the application classes
/// and their class path (not the JDK classes extracted for JBMC: a JDK method is modelled here, never run), with
/// the tool's models; the result is in JBMC's shape, and a line goes to `work/bmc.log`.
pub fn run_for_proof(entries: &[std::path::PathBuf], models: bool, class: &str, method: &str, unwind: u32, timeout: Duration, work: &std::path::Path) -> Result<crate::jbmc::JbmcResult, Error> {
    let cp = crate::witness::classpath(entries.iter().map(std::path::PathBuf::as_path))?.with_models(models);
    let outcome = check(&cp, class, method, &Options { unwind, timeout, ..Options::default() })?;
    let log = work.join("bmc.log");
    let _ = std::fs::write(&log, format!("jvmcontract's own checker on {class}.{method}\n{}\n", outcome.summary()));
    Ok(outcome.into_jbmc_result(log))
}

fn stop_text(stop: &Stop) -> String {
    match stop {
        Stop::Unsupported(s) | Stop::Budget(s) => s.clone(),
    }
}

impl ClassFile {
    /// The one method of this name (the harness has one `check`).
    fn method_by_name(&self, name: &str) -> Option<&crate::classfile::Method> {
        self.methods.iter().find(|m| m.name == name)
    }
}

impl<'a> Engine<'a> {
    fn code(&mut self, class: &Rc<ClassFile>, name: &str, descriptor: &str) -> Result<Rc<Decoded>, Stop> {
        let key = (class.name.clone(), name.to_string(), descriptor.to_string());
        if let Some(c) = self.codes.get(&key) {
            return Ok(c.clone());
        }
        let method = class.method(name, descriptor).ok_or_else(|| Stop::Unsupported(format!("no method {}.{name}{descriptor}", class.name)))?;
        if method.is_native() {
            return unsupported(format!("{}.{name} is native", class.name.replace('/', ".")));
        }
        let code = method.code.as_ref().ok_or_else(|| Stop::Unsupported(format!("{}.{name} has no code", class.name.replace('/', "."))))?;
        let decoded = code.instructions().map_err(|e| Stop::Unsupported(e.to_string()))?;
        let mut index = HashMap::with_capacity(decoded.len());
        let mut insns = Vec::with_capacity(decoded.len());
        let mut pcs = Vec::with_capacity(decoded.len());
        for (i, (pc, insn)) in decoded.into_iter().enumerate() {
            index.insert(pc, i);
            insns.push(insn);
            pcs.push(pc);
        }
        let compiled = Rc::new(Decoded { insns, pcs, index, handlers: code.exception_table.clone(), max_locals: code.max_locals as usize });
        self.codes.insert(key, compiled.clone());
        Ok(compiled)
    }

    /// Runs one path to its end; twins of it go to `pending`.
    fn run(&mut self, mut path: Path) -> Result<End, Stop> {
        let mut steps: u64 = 0;
        loop {
            steps += 1;
            if steps % 256 == 0 && Instant::now() > self.deadline {
                return Err(Stop::Budget("the engine did not finish within the time limit".into()));
            }
            if let Some(end) = self.step(&mut path)? {
                return Ok(end);
            }
        }
    }

    /// Which sides of a branch on `c` are feasible on the path. A condition the path has already taken (the
    /// same comparison of the same values, which the gate hashing makes the same literal: a loop bound both
    /// versions test) is decided without the solver; otherwise the side the path's model takes is feasible, and
    /// the solver is asked once, about the other side.
    fn sides(&mut self, path: &mut Path, c: Lit) -> Result<Sides, Stop> {
        if c == TRUE || path.cond.contains(&c) {
            return Ok(Sides::Then);
        }
        if c == FALSE || path.cond.contains(&-c) {
            return Ok(Sides::Else);
        }
        let model_takes_then = self.b.holds(&mut path.model, c);
        let mut assumptions = path.cond.clone();
        assumptions.push(if model_takes_then { -c } else { c });
        match self.probe(&assumptions)? {
            Some(true) => Ok(Sides::Both { model_takes_then, other: self.b.snapshot() }),
            None => Ok(Sides::Undecided { model_takes_then }),
            Some(false) if model_takes_then => Ok(Sides::Then),
            Some(false) => Ok(Sides::Else),
        }
    }

    /// Splits the path on `c` when both sides are feasible: the twin returned takes the then side when
    /// `twin_takes_then`, else the else side, and the path the other; each keeps the model of its side.
    fn split(&self, path: &mut Path, c: Lit, model_takes_then: bool, other: Model, twin_takes_then: bool) -> Path {
        let mut twin = path.clone();
        if model_takes_then == twin_takes_then {
            path.model = other;
        } else {
            twin.model = other;
        }
        twin.cond.push(if twin_takes_then { c } else { -c });
        path.cond.push(if twin_takes_then { -c } else { c });
        twin
    }

    /// Splits the path on `c` when the side its model does not take is undecided: the path goes on with its
    /// side, and the twin returned takes the other, undecided, with the path's model (see `Path::undecided`).
    fn split_undecided(&self, path: &mut Path, c: Lit, model_takes_then: bool) -> Path {
        let mut twin = path.clone();
        twin.undecided = true;
        twin.cond.push(if model_takes_then { -c } else { c });
        path.cond.push(if model_takes_then { c } else { -c });
        twin
    }

    /// Decides an undecided twin now, with all the time left, where it cannot wait: `None` when it is infeasible.
    fn settle(&mut self, mut twin: Path) -> Result<Option<Path>, Stop> {
        if !self.solve(&twin.cond)? {
            return Ok(None);
        }
        twin.model = self.b.snapshot();
        twin.undecided = false;
        Ok(Some(twin))
    }

    /// The literal of stage `i`: every parameter within its range (a boolean is in every range).
    fn stage_literal(&mut self, i: usize) -> Lit {
        if let Some(l) = self.stage_lits[i] {
            return l;
        }
        let (lo, hi) = STAGES[i];
        let mut lits = Vec::new();
        for (_, t, bits) in self.params.clone() {
            if t == Type::Boolean {
                continue;
            }
            let width = bits.len();
            let low = self.b.constant(lo, width);
            let high = self.b.constant(hi, width);
            let above = self.b.sle(&low, &bits);
            let below = self.b.sle(&bits, &high);
            lits.push(self.b.and(above, below));
        }
        let l = self.b.all(&lits);
        self.stage_lits[i] = Some(l);
        l
    }

    /// An input that takes the violating path of condition `cond`, from the first stage of [`STAGES`] that has
    /// one, or from the whole range (stage `STAGES.len()`) when none does.
    fn staged_input(&mut self, cond: &[Lit]) -> Result<(usize, BTreeMap<u32, String>), Stop> {
        let mut assumptions = cond.to_vec();
        for i in 0..STAGES.len() {
            let l = self.stage_literal(i);
            assumptions.push(l);
            if self.solve(&assumptions)? {
                return Ok((i, self.input()));
            }
            assumptions.pop();
        }
        if !self.solve(cond)? {
            return Err(Stop::Budget("the solver changed its mind about a violating path".into()));
        }
        Ok((STAGES.len(), self.input()))
    }

    /// The parameters' values in the solver's last model.
    fn input(&self) -> BTreeMap<u32, String> {
        let mut raw_inputs = BTreeMap::new();
        for (slot, t, bits) in &self.params {
            let v = self.b.eval(bits);
            let v = match t {
                Type::Char => v & 0xFFFF,
                _ => v,
            };
            raw_inputs.insert(*slot, v.to_string());
        }
        raw_inputs
    }

    /// Asks the solver, which is given the time left until the deadline (the search for a smaller witness after
    /// a violation shortens it, and one call must not run past it). A model is only taken when it is a real one:
    /// while the solver's choice for a division left to it is not the real division of the operands it chose, the
    /// circuit of that division is built and the solver asked again, so a `true` means an execution exists and
    /// its model (the parameters' values, the sides of later branches) is one.
    fn solve(&mut self, assumptions: &[Lit]) -> Result<bool, Stop> {
        let deadline = self.deadline;
        self.solve_until(assumptions, deadline)?.ok_or_else(|| Stop::Budget("the solver did not finish within the time limit".into()))
    }

    /// Asks the solver about the other side of a branch, for as long as all the solver calls so far took
    /// together, at least a second: `None` when it did not answer, and the side is left undecided rather than
    /// waited for, since an infeasible side can be as hard to refute as the whole proof (that a value is not a
    /// multiple of another, say) while the violation on the feasible side is found at once, as JBMC finds it
    /// without ever deciding the side. What is undecided is decided once the decided paths are done, with all the
    /// time left, so a proof loses at most the probes' time.
    fn probe(&mut self, assumptions: &[Lit]) -> Result<Option<bool>, Stop> {
        let budget = self.b.solving.max(Duration::from_secs(1));
        let until = self.deadline.min(Instant::now() + budget);
        self.solve_until(assumptions, until)
    }

    fn solve_until(&mut self, assumptions: &[Lit], until: Instant) -> Result<Option<bool>, Stop> {
        loop {
            let now = Instant::now();
            if now > self.deadline {
                return Err(Stop::Budget("the engine did not finish within the time limit".into()));
            }
            if now > until {
                return Ok(None);
            }
            self.b.set_timeout((until - now).as_secs_f32());
            match self.b.solve_with(assumptions) {
                None => return Ok(None),
                Some(false) => return Ok(false).map(Some),
                Some(true) => match self.b.wrong_division() {
                    None => return Ok(Some(true)),
                    Some(i) => self.b.refine_division(i),
                },
            }
        }
    }

    /// The next path to run: a decided one from `pending`, or, when there is none, a deferred one the solver now
    /// decides with all the time left (an infeasible one is dropped). `None` when every path is done.
    fn next_path(&mut self) -> Result<Option<Path>, Stop> {
        loop {
            if let Some(path) = self.pending.pop() {
                if path.undecided {
                    self.deferred.push(path);
                    continue;
                }
                return Ok(Some(path));
            }
            let Some(mut path) = self.deferred.pop() else {
                return Ok(None);
            };
            if self.solve(&path.cond)? {
                path.model = self.b.snapshot();
                path.undecided = false;
                return Ok(Some(path));
            }
        }
    }

    /// Takes the branch on `c`: the path goes on with `c` and jumps to `then`, or with `¬c` and jumps to `else_`,
    /// or both, the twin for the else side joining `pending`. `None` if neither side is feasible.
    fn branch(&mut self, path: &mut Path, c: Lit, then: usize, else_: usize) -> Result<Option<End>, Stop> {
        match self.sides(path, c)? {
            Sides::Both { model_takes_then, other } => {
                let mut twin = self.split(path, c, model_takes_then, other, false);
                twin.frames.last_mut().expect("a frame").at = else_;
                self.pending.push(twin);
                path.frames.last_mut().expect("a frame").at = then;
            }
            Sides::Then => {
                path.cond.push(c);
                path.frames.last_mut().expect("a frame").at = then;
            }
            Sides::Else => {
                path.cond.push(-c);
                path.frames.last_mut().expect("a frame").at = else_;
            }
            Sides::Undecided { model_takes_then } => {
                let mut twin = self.split_undecided(path, c, model_takes_then);
                twin.frames.last_mut().expect("a frame").at = if model_takes_then { else_ } else { then };
                self.pending.push(twin);
                path.frames.last_mut().expect("a frame").at = if model_takes_then { then } else { else_ };
            }
        }
        Ok(None)
    }

    /// Splits the path on `c` where the then side throws `exception` and the else side pushes `value` and goes
    /// on: a division by zero, an overflow.
    fn branch_throw(&mut self, path: &mut Path, c: Lit, exception: &str, value: Val) -> Step {
        match self.sides(path, c)? {
            Sides::Both { model_takes_then, other } => {
                let mut twin = self.split(path, c, model_takes_then, other, false);
                self.push(&mut twin, value);
                self.advance(&mut twin);
                self.pending.push(twin);
                self.raise(path, exception)
            }
            Sides::Then => {
                path.cond.push(c);
                self.raise(path, exception)
            }
            Sides::Else => {
                path.cond.push(-c);
                self.push(path, value);
                self.advance(path);
                Ok(None)
            }
            Sides::Undecided { model_takes_then: true } => {
                let mut twin = self.split_undecided(path, c, true);
                self.push(&mut twin, value);
                self.advance(&mut twin);
                self.pending.push(twin);
                self.raise(path, exception)
            }
            Sides::Undecided { model_takes_then: false } => {
                // The throwing side cannot wait undecided: whether the exception leaves the harness is judged as
                // it is thrown.
                let twin = self.split_undecided(path, c, false);
                if let Some(mut twin) = self.settle(twin)? {
                    self.raise(&mut twin, exception)?;
                    self.pending.push(twin);
                }
                self.push(path, value);
                self.advance(path);
                Ok(None)
            }
        }
    }

    /// A jump within the top frame, counting back edges against the bound.
    fn jump(&mut self, path: &mut Path, target: u32) -> Step {
        let frame = path.frames.last_mut().expect("a frame");
        let to = *frame.code.index.get(&target).ok_or_else(|| Stop::Unsupported(format!("jump to no instruction at pc {target}")))?;
        if to <= frame.at {
            let key = (frame.class.name.clone(), frame.method.clone(), target);
            let count = path.back_edges.entry(key).or_insert(0);
            *count += 1;
            if *count > self.unwind {
                let frame = path.frames.last().expect("a frame");
                return Ok(Some(End::Unwound(format!("{}.{} at pc {target}", frame.class.name.replace('/', "."), frame.method))));
            }
        }
        path.frames.last_mut().expect("a frame").at = to;
        Ok(None)
    }

    fn advance(&self, path: &mut Path) {
        path.frames.last_mut().expect("a frame").at += 1;
    }

    fn push(&self, path: &mut Path, v: Val) {
        path.frames.last_mut().expect("a frame").stack.push(v);
    }

    fn pop(&self, path: &mut Path) -> Result<Val, Stop> {
        path.frames.last_mut().expect("a frame").stack.pop().ok_or_else(|| Stop::Unsupported("operand stack underflow".into()))
    }

    fn pop_int(&self, path: &mut Path) -> Result<Bits, Stop> {
        match self.pop(path)? {
            Val::I(b) => Ok(b),
            other => unsupported(format!("expected an int on the stack, found {other:?}")),
        }
    }

    fn pop_long(&self, path: &mut Path) -> Result<Bits, Stop> {
        match self.pop(path)? {
            Val::J(b) => Ok(b),
            other => unsupported(format!("expected a long on the stack, found {other:?}")),
        }
    }

    fn pop_ref(&self, path: &mut Path) -> Result<Option<usize>, Stop> {
        match self.pop(path)? {
            Val::R(r) => Ok(r),
            other => unsupported(format!("expected a reference on the stack, found {other:?}")),
        }
    }

    fn alloc(&self, path: &mut Path, class: &str) -> usize {
        path.objects.push(Obj { class: class.to_string(), fields: BTreeMap::new() });
        path.objects.len() - 1
    }

    /// Throws a new exception of the class from the current instruction.
    fn raise(&mut self, path: &mut Path, class: &str) -> Step {
        let obj = self.alloc(path, class);
        self.throw(path, obj)
    }

    /// Unwinds to the nearest handler of the object's class; a path the harness's `AssertionError` leaves is a
    /// violation, and any other uncaught exception is outside what the engine can judge.
    fn throw(&mut self, path: &mut Path, obj: usize) -> Step {
        let class = path.objects[obj].class.clone();
        while let Some(frame) = path.frames.last_mut() {
            let pc = frame.pc();
            let handler = frame.code.handlers.iter().find(|h| u32::from(h.start_pc) <= pc && pc < u32::from(h.end_pc) && h.catch_type.as_deref().is_none_or(|t| self.cp.is_subtype(&class, t))).cloned();
            if let Some(h) = handler {
                let to = *frame.code.index.get(&u32::from(h.handler_pc)).ok_or_else(|| Stop::Unsupported("handler at no instruction".into()))?;
                frame.stack.clear();
                frame.stack.push(Val::R(Some(obj)));
                frame.at = to;
                return Ok(None);
            }
            path.frames.pop();
        }
        if self.cp.is_subtype(&class, "java/lang/AssertionError") {
            let feasible = self.solve(&path.cond.clone())?;
            return Ok(Some(if feasible { End::Violation(std::mem::take(&mut path.cond)) } else { End::Infeasible }));
        }
        unsupported(format!("an uncaught {} leaves the harness", class.replace('/', ".")))
    }

    fn null_check(&mut self, path: &mut Path, r: Option<usize>) -> Result<Option<usize>, Step> {
        match r {
            Some(o) => Ok(Some(o)),
            None => Err(self.raise(path, "java/lang/NullPointerException")),
        }
    }

    /// Executes the instruction at the top frame's `at`.
    fn step(&mut self, path: &mut Path) -> Step {
        let frame = path.frames.last().expect("a frame");
        let insn = frame.code.insns[frame.at].clone();
        let class = frame.class.clone();
        match insn {
            Insn::Nop => {}
            Insn::AConstNull => self.push(path, Val::R(None)),
            Insn::IConst(v) => {
                let c = self.b.constant(i64::from(v), 32);
                self.push(path, Val::I(c));
            }
            Insn::LConst(v) => {
                let c = self.b.constant(v, 64);
                self.push(path, Val::J(c));
            }
            Insn::FConst(_) | Insn::DConst(_) => return unsupported("floating point"),
            Insn::Ldc(index) => match class.pool.loadable(index).map_err(|e| Stop::Unsupported(e.to_string()))? {
                BootstrapArg::Int(v) => {
                    let c = self.b.constant(i64::from(v), 32);
                    self.push(path, Val::I(c));
                }
                BootstrapArg::Long(v) => {
                    let c = self.b.constant(v, 64);
                    self.push(path, Val::J(c));
                }
                BootstrapArg::Str(_) => {
                    let o = self.alloc(path, "java/lang/String");
                    self.push(path, Val::R(Some(o)));
                }
                BootstrapArg::Class(_) => {
                    let o = self.alloc(path, "java/lang/Class");
                    self.push(path, Val::R(Some(o)));
                }
                BootstrapArg::Float(_) | BootstrapArg::Double(_) => return unsupported("floating point"),
                other => return unsupported(format!("ldc of {other:?}")),
            },
            Insn::Load(_, slot) => {
                let frame = path.frames.last().expect("a frame");
                let v = frame.locals.get(slot as usize).cloned().flatten().ok_or_else(|| Stop::Unsupported(format!("load of an unset local {slot}")))?;
                self.push(path, v);
            }
            Insn::Store(_, slot) => {
                let v = self.pop(path)?;
                let frame = path.frames.last_mut().expect("a frame");
                let slot = slot as usize;
                if frame.locals.len() <= slot + 1 {
                    frame.locals.resize(slot + 2, None);
                }
                if v.category() == 2 {
                    frame.locals[slot + 1] = None;
                }
                frame.locals[slot] = Some(v);
            }
            Insn::ArrayLoad(_) | Insn::ArrayStore(_) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::ArrayLength | Insn::MultiANewArray(..) => return unsupported("arrays"),
            Insn::Pop => {
                self.pop(path)?;
            }
            Insn::Pop2 => {
                if self.pop(path)?.category() == 1 {
                    self.pop(path)?;
                }
            }
            Insn::Dup => {
                let v = self.pop(path)?;
                self.push(path, v.clone());
                self.push(path, v);
            }
            Insn::DupX1 => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                self.push(path, v1.clone());
                self.push(path, v2);
                self.push(path, v1);
            }
            Insn::DupX2 => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                if v2.category() == 2 {
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                } else {
                    let v3 = self.pop(path)?;
                    self.push(path, v1.clone());
                    self.push(path, v3);
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Dup2 => {
                let v1 = self.pop(path)?;
                if v1.category() == 2 {
                    self.push(path, v1.clone());
                    self.push(path, v1);
                } else {
                    let v2 = self.pop(path)?;
                    self.push(path, v2.clone());
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Dup2X1 => {
                let v1 = self.pop(path)?;
                if v1.category() == 2 {
                    let v2 = self.pop(path)?;
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                } else {
                    let v2 = self.pop(path)?;
                    let v3 = self.pop(path)?;
                    self.push(path, v2.clone());
                    self.push(path, v1.clone());
                    self.push(path, v3);
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Dup2X2 => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                if v1.category() == 2 && v2.category() == 2 {
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                } else if v1.category() == 1 && v2.category() == 1 {
                    let v3 = self.pop(path)?;
                    if v3.category() == 2 {
                        self.push(path, v2.clone());
                        self.push(path, v1.clone());
                        self.push(path, v3);
                        self.push(path, v2);
                        self.push(path, v1);
                    } else {
                        let v4 = self.pop(path)?;
                        self.push(path, v2.clone());
                        self.push(path, v1.clone());
                        self.push(path, v4);
                        self.push(path, v3);
                        self.push(path, v2);
                        self.push(path, v1);
                    }
                } else {
                    // v1 wide over v2, v3 narrow.
                    let v3 = self.pop(path)?;
                    self.push(path, v1.clone());
                    self.push(path, v3);
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Swap => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                self.push(path, v1);
                self.push(path, v2);
            }
            Insn::Arith(op, kind) => return self.arith(path, op, kind),
            Insn::IInc(slot, delta) => {
                let frame = path.frames.last_mut().expect("a frame");
                let Some(Some(Val::I(v))) = frame.locals.get(slot as usize).cloned() else { return unsupported(format!("iinc of an unset local {slot}")) };
                let d = self.b.constant(i64::from(delta), 32);
                let sum = self.b.add(&v, &d);
                path.frames.last_mut().expect("a frame").locals[slot as usize] = Some(Val::I(sum));
            }
            Insn::Convert(from, to) => {
                let v = match (from, to) {
                    (Kind::Int, Narrow::To(Kind::Long)) => {
                        let x = self.pop_int(path)?;
                        Val::J(self.b.sext(&x, 64))
                    }
                    (Kind::Long, Narrow::To(Kind::Int)) => {
                        let x = self.pop_long(path)?;
                        Val::I(self.b.trunc(&x, 32))
                    }
                    (Kind::Int, Narrow::Byte) => {
                        let x = self.pop_int(path)?;
                        let t = self.b.trunc(&x, 8);
                        Val::I(self.b.sext(&t, 32))
                    }
                    (Kind::Int, Narrow::Char) => {
                        let x = self.pop_int(path)?;
                        let t = self.b.trunc(&x, 16);
                        Val::I(self.b.zext(&t, 32))
                    }
                    (Kind::Int, Narrow::Short) => {
                        let x = self.pop_int(path)?;
                        let t = self.b.trunc(&x, 16);
                        Val::I(self.b.sext(&t, 32))
                    }
                    _ => return unsupported("floating point"),
                };
                self.push(path, v);
            }
            Insn::Cmp(op) => {
                if op.kind != Kind::Long {
                    return unsupported("floating point");
                }
                let y = self.pop_long(path)?;
                let x = self.pop_long(path)?;
                let lt = self.b.slt(&x, &y);
                let eq = self.b.eq(&x, &y);
                let minus_one = self.b.constant(-1, 32);
                let zero = self.b.constant(0, 32);
                let one = self.b.constant(1, 32);
                let tail = self.b.ite_bits(eq, &zero, &one);
                let r = self.b.ite_bits(lt, &minus_one, &tail);
                self.push(path, Val::I(r));
            }
            Insn::If(cond, target) => {
                let x = self.pop_int(path)?;
                let zero = self.b.constant(0, 32);
                let c = self.compare(cond, &x, &zero);
                return self.conditional(path, c, target);
            }
            Insn::IfICmp(cond, target) => {
                let y = self.pop_int(path)?;
                let x = self.pop_int(path)?;
                let c = self.compare(cond, &x, &y);
                return self.conditional(path, c, target);
            }
            Insn::IfACmp(equal, target) => {
                let y = self.pop_ref(path)?;
                let x = self.pop_ref(path)?;
                let c = if (x == y) == equal { TRUE } else { FALSE };
                return self.conditional(path, c, target);
            }
            Insn::IfNull(target) => {
                let x = self.pop_ref(path)?;
                return self.conditional(path, if x.is_none() { TRUE } else { FALSE }, target);
            }
            Insn::IfNonNull(target) => {
                let x = self.pop_ref(path)?;
                return self.conditional(path, if x.is_some() { TRUE } else { FALSE }, target);
            }
            Insn::Goto(target) => return self.jump(path, target),
            Insn::Jsr(_) | Insn::Ret(_) => return unsupported("jsr/ret"),
            Insn::TableSwitch { default, low, high, targets } => {
                let key = self.pop_int(path)?;
                let cases: Vec<(i32, u32)> = targets.iter().enumerate().map(|(i, &t)| (low + i as i32, t)).collect();
                debug_assert_eq!(cases.len() as i32, high - low + 1);
                return self.switch(path, key, &cases, default);
            }
            Insn::LookupSwitch { default, pairs } => {
                let key = self.pop_int(path)?;
                return self.switch(path, key, &pairs, default);
            }
            Insn::Return(kind) => {
                let value = match kind {
                    Some(_) => Some(self.pop(path)?),
                    None => None,
                };
                path.frames.pop();
                if path.frames.is_empty() {
                    return Ok(Some(End::Returned));
                }
                if let Some(v) = value {
                    self.push(path, v);
                }
                self.advance(path);
                return Ok(None);
            }
            Insn::GetStatic(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let v = self.get_static(&member.owner, &member.name, &member.descriptor)?;
                self.push(path, v);
            }
            Insn::PutStatic(_) => return unsupported("writes a static field"),
            Insn::GetField(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let r = self.pop_ref(path)?;
                let o = match self.null_check(path, r) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                let v = match path.objects[o].fields.get(&member.name) {
                    Some(v) => v.clone(),
                    None => self.default_value(&member.descriptor)?,
                };
                self.push(path, v);
            }
            Insn::PutField(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let v = self.pop(path)?;
                let r = self.pop_ref(path)?;
                let o = match self.null_check(path, r) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                path.objects[o].fields.insert(member.name.clone(), v);
            }
            Insn::InvokeStatic(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let descriptor = MethodDescriptor::parse(&member.descriptor).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let args = self.pop_args(path, descriptor.params.len())?;
                if self.cp.is_application(&member.owner) {
                    return self.call(path, &member.owner, &member.name, &member.descriptor, args);
                }
                // A JDK class the tool models (Character.digit, say) runs as bytecode here too, so that the
                // engine and the interpreter that replays its witnesses agree on it.
                if self.cp.model(&member.owner).is_some() && self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).is_some_and(|(_, m)| m.code.is_some()) {
                    return self.call(path, &member.owner, &member.name, &member.descriptor, args);
                }
                return self.call_jdk_static(path, &member.owner, &member.name, &member.descriptor, &descriptor, args);
            }
            Insn::InvokeSpecial(index) | Insn::InvokeVirtual(index) | Insn::InvokeInterface(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let descriptor = MethodDescriptor::parse(&member.descriptor).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let args = self.pop_args(path, descriptor.params.len())?;
                let receiver = self.pop_ref(path)?;
                let o = match self.null_check(path, receiver) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                let special = matches!(insn, Insn::InvokeSpecial(_));
                let owner = if special { member.owner.clone() } else { path.objects[o].class.clone() };
                if let Some((cf, m)) = self.cp.bytecode_method(&owner, &member.name, &member.descriptor).filter(|(cf, _)| self.cp.is_application(&cf.name)) {
                    if m.code.is_some() {
                        let mut full = vec![Val::R(Some(o))];
                        full.extend(args);
                        return self.call(path, &cf.name, &member.name, &member.descriptor, full);
                    }
                }
                // A JDK method on an opaque object: a constructor does nothing the proof can see, a method that
                // returns a reference returns another opaque object, and a primitive result is beyond the engine.
                if member.name == "<init>" {
                    self.advance(path);
                    return Ok(None);
                }
                match &descriptor.ret {
                    Type::Void => {}
                    Type::Object(name) => {
                        let r = self.alloc(path, name);
                        self.push(path, Val::R(Some(r)));
                    }
                    _ => return unsupported(format!("{}.{} on an object the engine does not model", member.owner.replace('/', "."), member.name)),
                }
            }
            Insn::InvokeDynamic(index) => {
                let (_, _, descriptor_text) = class.pool.invoke_dynamic(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let descriptor = MethodDescriptor::parse(descriptor_text).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let _ = self.pop_args(path, descriptor.params.len())?;
                match &descriptor.ret {
                    Type::Object(name) if name == "java/lang/String" => {
                        let r = self.alloc(path, "java/lang/String");
                        self.push(path, Val::R(Some(r)));
                    }
                    _ => return unsupported("invokedynamic other than string concatenation"),
                }
            }
            Insn::New(index) => {
                let name = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                let r = self.alloc(path, &name);
                self.push(path, Val::R(Some(r)));
            }
            Insn::AThrow => {
                let r = self.pop_ref(path)?;
                let o = match self.null_check(path, r) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                return self.throw(path, o);
            }
            Insn::CheckCast(index) => {
                let target = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                let r = self.pop_ref(path)?;
                if let Some(o) = r {
                    if !self.cp.is_subtype(&path.objects[o].class, &target) {
                        return self.raise(path, "java/lang/ClassCastException");
                    }
                }
                self.push(path, Val::R(r));
            }
            Insn::InstanceOf(index) => {
                let target = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                let r = self.pop_ref(path)?;
                let is = r.is_some_and(|o| self.cp.is_subtype(&path.objects[o].class, &target));
                let c = self.b.constant(i64::from(is), 32);
                self.push(path, Val::I(c));
            }
            Insn::MonitorEnter | Insn::MonitorExit => {
                self.pop(path)?;
            }
        }
        self.advance(path);
        Ok(None)
    }

    fn default_value(&self, descriptor: &str) -> Result<Val, Stop> {
        Ok(match Type::parse(descriptor).map_err(|e| Stop::Unsupported(e.to_string()))? {
            Type::Long => Val::J(self.b.constant(0, 64)),
            Type::Float | Type::Double => return unsupported("floating point"),
            Type::Object(_) | Type::Array(_) => Val::R(None),
            _ => Val::I(self.b.constant(0, 32)),
        })
    }

    fn get_static(&mut self, owner: &str, name: &str, descriptor: &str) -> Result<Val, Stop> {
        // A JDK constant javac did not inline (none in practice: these are compile-time constants).
        let known: Option<Val> = match (owner, name) {
            ("java/lang/Integer", "MAX_VALUE") => Some(Val::I(self.b.constant(i64::from(i32::MAX), 32))),
            ("java/lang/Integer", "MIN_VALUE") => Some(Val::I(self.b.constant(i64::from(i32::MIN), 32))),
            ("java/lang/Long", "MAX_VALUE") => Some(Val::J(self.b.constant(i64::MAX, 64))),
            ("java/lang/Long", "MIN_VALUE") => Some(Val::J(self.b.constant(i64::MIN, 64))),
            _ => None,
        };
        if let Some(v) = known {
            return Ok(v);
        }
        // An application constant with a ConstantValue attribute (a static final primitive initialised by a
        // literal); any other static is state the engine does not model.
        let Ok(Some(class)) = self.cp.bytecode(owner) else { return unsupported(format!("reads static field {}.{name}", owner.replace('/', "."))) };
        let Some(field) = class.field(name).filter(|f| f.is_static()) else { return unsupported(format!("reads static field {}.{name}", owner.replace('/', "."))) };
        let Some(attr) = field.attributes.iter().find(|a| a.name == "ConstantValue").filter(|a| a.data.len() == 2) else {
            return unsupported(format!("reads static field {}.{name}, which is not a compile-time constant", owner.replace('/', ".")));
        };
        let index = u16::from_be_bytes([attr.data[0], attr.data[1]]);
        Ok(match (class.pool.loadable(index), Type::parse(descriptor)) {
            (Ok(BootstrapArg::Int(v)), _) => Val::I(self.b.constant(i64::from(v), 32)),
            (Ok(BootstrapArg::Long(v)), _) => Val::J(self.b.constant(v, 64)),
            _ => return unsupported(format!("reads static field {}.{name}", owner.replace('/', "."))),
        })
    }

    fn pop_args(&self, path: &mut Path, count: usize) -> Result<Vec<Val>, Stop> {
        let mut args = Vec::with_capacity(count);
        for _ in 0..count {
            args.push(self.pop(path)?);
        }
        args.reverse();
        Ok(args)
    }

    /// Calls an application method: a new frame with the arguments in its locals.
    fn call(&mut self, path: &mut Path, owner: &str, name: &str, descriptor: &str, args: Vec<Val>) -> Step {
        let (cf, m) = self.cp.bytecode_method(owner, name, descriptor).ok_or_else(|| Stop::Unsupported(format!("method not found: {}.{name}{descriptor}", owner.replace('/', "."))))?;
        if m.is_abstract() {
            return unsupported(format!("{}.{name} is abstract", cf.name.replace('/', ".")));
        }
        if path.frames.len() >= 64 {
            return unsupported("calls nested deeper than 64 (unbounded recursion?)");
        }
        let code = self.code(&cf, name, descriptor)?;
        let mut locals: Vec<Option<Val>> = Vec::with_capacity(code.max_locals);
        for a in args {
            let wide = a.category() == 2;
            locals.push(Some(a));
            if wide {
                locals.push(None);
            }
        }
        locals.resize(code.max_locals.max(locals.len()), None);
        path.frames.push(Frame { class: cf.clone(), method: name.to_string(), code, at: 0, locals, stack: Vec::new() });
        Ok(None)
    }

    fn compare(&mut self, cond: Cond, x: &Bits, y: &Bits) -> Lit {
        match cond {
            Cond::Eq => self.b.eq(x, y),
            Cond::Ne => -self.b.eq(x, y),
            Cond::Lt => self.b.slt(x, y),
            Cond::Ge => -self.b.slt(x, y),
            Cond::Gt => self.b.slt(y, x),
            Cond::Le => -self.b.slt(y, x),
        }
    }

    /// A conditional jump to `target`, else fall through.
    fn conditional(&mut self, path: &mut Path, c: Lit, target: u32) -> Step {
        let frame = path.frames.last().expect("a frame");
        let then = *frame.code.index.get(&target).ok_or_else(|| Stop::Unsupported(format!("jump to no instruction at pc {target}")))?;
        let fall = frame.at + 1;
        let backward = then <= frame.at;
        if backward {
            // Count the back edge on the side that takes it; `jump` does the counting once the side is chosen.
            match self.sides(path, c)? {
                Sides::Both { model_takes_then, other } => {
                    let mut twin = self.split(path, c, model_takes_then, other, false);
                    twin.frames.last_mut().expect("a frame").at = fall;
                    self.pending.push(twin);
                    return self.jump(path, target);
                }
                Sides::Then => {
                    path.cond.push(c);
                    return self.jump(path, target);
                }
                Sides::Else => {
                    path.cond.push(-c);
                    path.frames.last_mut().expect("a frame").at = fall;
                    return Ok(None);
                }
                Sides::Undecided { model_takes_then: true } => {
                    let mut twin = self.split_undecided(path, c, true);
                    twin.frames.last_mut().expect("a frame").at = fall;
                    self.pending.push(twin);
                    return self.jump(path, target);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    if let Some(end) = self.jump(&mut twin, target)? {
                        // The twin hit the unwinding bound, which counts only if it is feasible.
                        if !matches!(end, End::Infeasible) {
                            if let Some(twin) = self.settle(twin)? {
                                *path = twin;
                                return Ok(Some(end));
                            }
                        }
                    } else {
                        self.pending.push(twin);
                    }
                    path.frames.last_mut().expect("a frame").at = fall;
                    return Ok(None);
                }
            }
        }
        self.branch(path, c, then, fall)
    }

    /// A switch: each case in turn is a branch on `key == case`, the matching twin jumping to its target and the
    /// path going on to the next case; the last falls to the default.
    fn switch(&mut self, path: &mut Path, key: Bits, cases: &[(i32, u32)], default: u32) -> Step {
        for &(value, target) in cases {
            let k = self.b.constant(i64::from(value), 32);
            let c = self.b.eq(&key, &k);
            match self.sides(path, c)? {
                Sides::Both { model_takes_then, other } => {
                    let mut twin = self.split(path, c, model_takes_then, other, true);
                    if let Some(end) = self.jump(&mut twin, target)? {
                        if !matches!(end, End::Infeasible) {
                            // The twin hit the unwinding bound: report it as the path's own end.
                            *path = twin;
                            return Ok(Some(end));
                        }
                    } else {
                        self.pending.push(twin);
                    }
                }
                Sides::Then => {
                    path.cond.push(c);
                    return self.jump(path, target);
                }
                Sides::Else => path.cond.push(-c),
                Sides::Undecided { model_takes_then: true } => {
                    // The twin takes the other cases: it runs the switch again, with this case decided against.
                    let mut twin = self.split_undecided(path, c, true);
                    twin.frames.last_mut().expect("a frame").stack.push(Val::I(key.clone()));
                    self.pending.push(twin);
                    return self.jump(path, target);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    if let Some(end) = self.jump(&mut twin, target)? {
                        if !matches!(end, End::Infeasible) {
                            if let Some(twin) = self.settle(twin)? {
                                *path = twin;
                                return Ok(Some(end));
                            }
                        }
                    } else {
                        self.pending.push(twin);
                    }
                }
            }
        }
        self.jump(path, default)
    }

    fn arith(&mut self, path: &mut Path, op: ArithOp, kind: Kind) -> Step {
        let width = match kind {
            Kind::Int => 32,
            Kind::Long => 64,
            _ => return unsupported("floating point"),
        };
        let wrap = |b: Bits| if width == 64 { Val::J(b) } else { Val::I(b) };
        if op == ArithOp::Neg {
            let x = if width == 64 { self.pop_long(path)? } else { self.pop_int(path)? };
            let r = self.b.neg(&x);
            self.push(path, wrap(r));
            self.advance(path);
            return Ok(None);
        }
        // Shift amounts are ints whatever the shifted value's width.
        let y = if width == 64 && !matches!(op, ArithOp::Shl | ArithOp::Shr | ArithOp::Ushr) { self.pop_long(path)? } else { self.pop_int(path)? };
        let x = if width == 64 { self.pop_long(path)? } else { self.pop_int(path)? };
        let r = match op {
            ArithOp::Add => self.b.add(&x, &y),
            ArithOp::Sub => self.b.sub(&x, &y),
            ArithOp::Mul => self.b.mul(&x, &y),
            ArithOp::Div | ArithOp::Rem => {
                let zero = self.b.is_zero(&y);
                let (q, r) = self.b.sdivrem_lazy(&x, &y);
                let value = wrap(if op == ArithOp::Div { q } else { r });
                return self.branch_throw(path, zero, "java/lang/ArithmeticException", value);
            }
            ArithOp::Shl => self.b.shl(&x, &y),
            ArithOp::Shr => self.b.shr(&x, &y),
            ArithOp::Ushr => self.b.ushr(&x, &y),
            ArithOp::And => self.b.and_bits(&x, &y),
            ArithOp::Or => self.b.or_bits(&x, &y),
            ArithOp::Xor => self.b.xor_bits(&x, &y),
            ArithOp::Neg => unreachable!(),
        };
        self.push(path, wrap(r));
        self.advance(path);
        Ok(None)
    }

    /// The JDK's static methods the engine models: the exact and floor arithmetic of `Math`, and the comparisons
    /// of the integer wrappers.
    fn call_jdk_static(&mut self, path: &mut Path, owner: &str, name: &str, descriptor: &str, parsed: &MethodDescriptor, args: Vec<Val>) -> Step {
        let bits = |v: &Val| match v {
            Val::I(b) | Val::J(b) => Some(b.clone()),
            Val::R(_) => None,
        };
        let a: Vec<Bits> = match args.iter().map(bits).collect::<Option<Vec<_>>>() {
            Some(a) => a,
            None => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
        };
        let wrap = |b: Bits| if b.len() == 64 { Val::J(b) } else { Val::I(b) };
        let result = match (owner, name) {
            ("java/lang/Math" | "java/lang/StrictMath", "addExact" | "subtractExact" | "multiplyExact" | "negateExact" | "incrementExact" | "decrementExact" | "toIntExact" | "absExact") => {
                let (value, overflow) = match name {
                    "addExact" => {
                        let r = self.b.add(&a[0], &a[1]);
                        // Overflow if the operands agree in sign and the result does not.
                        let same = -self.b.xor(self.b.negative(&a[0]), self.b.negative(&a[1]));
                        let differs = self.b.xor(self.b.negative(&a[0]), self.b.negative(&r));
                        let o = self.b.and(same, differs);
                        (r, o)
                    }
                    "subtractExact" => {
                        let r = self.b.sub(&a[0], &a[1]);
                        let differ = self.b.xor(self.b.negative(&a[0]), self.b.negative(&a[1]));
                        let changed = self.b.xor(self.b.negative(&a[0]), self.b.negative(&r));
                        let o = self.b.and(differ, changed);
                        (r, o)
                    }
                    "multiplyExact" => {
                        // (JI)J widens the int; the product is exact iff it fits in the width, checked on the
                        // double-width product.
                        let width = a[0].len();
                        let x = self.b.sext(&a[0], 2 * width);
                        let y = if a[1].len() == width { self.b.sext(&a[1], 2 * width) } else { self.b.sext(&a[1], 2 * width) };
                        let wide = self.b.mul(&x, &y);
                        let r = self.b.trunc(&wide, width);
                        let back = self.b.sext(&r, 2 * width);
                        let o = -self.b.eq(&wide, &back);
                        (r, o)
                    }
                    "negateExact" => {
                        let r = self.b.neg(&a[0]);
                        let min = self.b.constant(if a[0].len() == 64 { i64::MIN } else { i64::from(i32::MIN) }, a[0].len());
                        let o = self.b.eq(&a[0], &min);
                        (r, o)
                    }
                    "incrementExact" | "decrementExact" => {
                        let one = self.b.constant(1, a[0].len());
                        let r = if name == "incrementExact" { self.b.add(&a[0], &one) } else { self.b.sub(&a[0], &one) };
                        let limit = self.b.constant(if name == "incrementExact" { if a[0].len() == 64 { i64::MAX } else { i64::from(i32::MAX) } } else if a[0].len() == 64 { i64::MIN } else { i64::from(i32::MIN) }, a[0].len());
                        let o = self.b.eq(&a[0], &limit);
                        (r, o)
                    }
                    "toIntExact" => {
                        let r = self.b.trunc(&a[0], 32);
                        let back = self.b.sext(&r, 64);
                        let o = -self.b.eq(&a[0], &back);
                        (r, o)
                    }
                    "absExact" => {
                        let neg = self.b.neg(&a[0]);
                        let r = self.b.ite_bits(self.b.negative(&a[0]), &neg, &a[0]);
                        let min = self.b.constant(if a[0].len() == 64 { i64::MIN } else { i64::from(i32::MIN) }, a[0].len());
                        let o = self.b.eq(&a[0], &min);
                        (r, o)
                    }
                    _ => unreachable!(),
                };
                return self.branch_throw(path, overflow, "java/lang/ArithmeticException", wrap(value));
            }
            ("java/lang/Math" | "java/lang/StrictMath", "abs") => {
                let neg = self.b.neg(&a[0]);
                wrap(self.b.ite_bits(self.b.negative(&a[0]), &neg, &a[0]))
            }
            ("java/lang/Math" | "java/lang/StrictMath" | "java/lang/Integer" | "java/lang/Long", "max" | "min") => {
                let lt = self.b.slt(&a[0], &a[1]);
                let (x, y) = if name == "max" { (&a[1], &a[0]) } else { (&a[0], &a[1]) };
                wrap(self.b.ite_bits(lt, x, y))
            }
            ("java/lang/Integer" | "java/lang/Long", "sum") => wrap(self.b.add(&a[0], &a[1])),
            ("java/lang/Math" | "java/lang/StrictMath", "floorDiv" | "floorMod") => {
                // floorDiv(x, y) = x / y, less one when the signs differ and the division is inexact;
                // floorMod(x, y) = x - floorDiv(x, y) * y. A second operand narrower than the first is widened.
                let width = a[0].len();
                let y = if a[1].len() == width { a[1].clone() } else { self.b.sext(&a[1], width) };
                let zero = self.b.is_zero(&y);
                let (q, r) = self.b.sdivrem_lazy(&a[0], &y);
                let inexact = -self.b.is_zero(&r);
                let differ = self.b.xor(self.b.negative(&a[0]), self.b.negative(&y));
                let adjust = self.b.and(inexact, differ);
                let one = self.b.constant(1, width);
                let q_less = self.b.sub(&q, &one);
                let fq = self.b.ite_bits(adjust, &q_less, &q);
                let value = if name == "floorDiv" {
                    fq
                } else {
                    let r_plus = self.b.add(&r, &y);
                    let fm = self.b.ite_bits(adjust, &r_plus, &r);
                    if parsed.ret == Type::Int && width == 64 { self.b.trunc(&fm, 32) } else { fm }
                };
                return self.branch_throw(path, zero, "java/lang/ArithmeticException", wrap(value));
            }
            ("java/lang/Integer" | "java/lang/Long", "compare") => {
                let lt = self.b.slt(&a[0], &a[1]);
                let eq = self.b.eq(&a[0], &a[1]);
                let minus_one = self.b.constant(-1, 32);
                let zero = self.b.constant(0, 32);
                let one = self.b.constant(1, 32);
                let tail = self.b.ite_bits(eq, &zero, &one);
                Val::I(self.b.ite_bits(lt, &minus_one, &tail))
            }
            ("java/lang/Integer" | "java/lang/Long", "signum") => {
                let zero = self.b.constant(0, a[0].len());
                let lt = self.b.slt(&a[0], &zero);
                let eq = self.b.eq(&a[0], &zero);
                let minus_one = self.b.constant(-1, 32);
                let z = self.b.constant(0, 32);
                let one = self.b.constant(1, 32);
                let tail = self.b.ite_bits(eq, &z, &one);
                Val::I(self.b.ite_bits(lt, &minus_one, &tail))
            }
            ("java/lang/Integer", "toUnsignedLong") => Val::J(self.b.zext(&a[0], 64)),
            ("java/lang/Boolean", "logicalAnd") => Val::I(self.b.and_bits(&a[0], &a[1])),
            ("java/lang/Boolean", "logicalOr") => Val::I(self.b.or_bits(&a[0], &a[1])),
            ("java/lang/Boolean", "logicalXor") => Val::I(self.b.xor_bits(&a[0], &a[1])),
            _ => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
        };
        self.push(path, result);
        self.advance(path);
        Ok(None)
    }
}

impl Blaster {
    fn signature(&self) -> String {
        "CaDiCaL".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::flags;
    use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};

    /// A harness-shaped class: `static void check(int a, int b)` whose body `build` writes, failing by throwing an
    /// `AssertionError` at the label `fail`.
    fn harness(descriptor: &str, build: impl FnOnce(&mut CodeBuilder, &mut ClassWriter, crate::classfile::writer::Label)) -> ClassPath {
        let mut writer = ClassWriter::new("Check");
        writer.default_constructor();
        let mut code = CodeBuilder::new();
        code.max_locals = 8;
        code.max_stack = 8;
        let fail = code.label();
        build(&mut code, &mut writer, fail);
        code.return_(None);
        code.bind(fail);
        let error = writer.pool.class("java/lang/AssertionError");
        let init = writer.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
        code.op_u16(0xbb, error);
        code.op(0x59);
        code.op_u16(0xb7, init);
        code.op(0xbf);
        writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "check".into(), descriptor: descriptor.into(), code: Some(code) });
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("Check.class"), writer.to_bytes()).unwrap();
        let mut cp = ClassPath::new();
        cp.add(dir.path()).unwrap();
        std::mem::forget(dir);
        cp
    }

    fn run(cp: &ClassPath) -> Outcome {
        check(cp, "Check", "check", &Options::default()).unwrap()
    }

    #[test]
    fn a_tautology_is_verified_and_a_falsifiable_claim_refuted_with_its_input() {
        // a + b == b + a
        let cp = harness("(II)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x60); // iadd
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 0);
            code.op(0x60);
            code.if_icmp(Cond::Ne, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!(out.solves, 0, "both sides are the same gates, so the comparison folds to a constant and no solver call is needed");

        // a * 2 == a + a holds; a * a >= 0 does not (overflow), and the input that breaks it is reported.
        let cp = harness("(I)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.op(0x68); // imul
            code.if_zero(Cond::Lt, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let a: i32 = out.raw_inputs[&0].parse().unwrap();
        assert!(a.wrapping_mul(a) < 0, "{a}");
    }

    #[test]
    fn a_branch_costs_one_solver_call_and_a_condition_taken_before_none() {
        // `if (a >= b) return; if (a >= b) fail; return`: the first branch asks the solver about the one side
        // the path's model does not take, and the second is on the literal the path already took.
        let cp = harness("(II)V", |code, _, fail| {
            let done = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, done);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, fail);
            code.bind(done);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.solves), (2, 1));

        // Two independent branches: four paths, and three solver calls (one per branch point explored), where
        // asking about both sides of each would take six.
        let cp = harness("(II)V", |code, _, _| {
            let second = code.label();
            let done = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Lt, second);
            code.bind(second);
            code.load(Kind::Int, 0);
            code.iconst(5);
            code.if_icmp(Cond::Lt, done);
            code.bind(done);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.solves), (4, 3));
    }

    #[test]
    fn division_by_zero_is_an_exception_path_and_handlers_catch_by_class() {
        // a / b throws ArithmeticException exactly when b == 0 (the handler asserts b == 0, the normal path
        // b != 0), and on a concrete input the quotient is what it should be.
        let cp = harness("(II)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let not_seven = code.label();
            code.bind(try_start);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.store(Kind::Int, 2);
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, fail); // returned although b == 0: impossible
            code.load(Kind::Int, 0);
            code.iconst(7);
            code.if_icmp(Cond::Ne, not_seven);
            code.load(Kind::Int, 1);
            code.iconst(2);
            code.if_icmp(Cond::Ne, not_seven);
            code.load(Kind::Int, 2);
            code.iconst(3);
            code.if_icmp(Cond::Ne, fail); // 7 / 2 != 3: impossible
            code.bind(not_seven);
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57); // pop
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Ne, fail); // thrown although b != 0: impossible
            code.bind(ok);
            let arithmetic = writer.pool.class("java/lang/ArithmeticException");
            code.handler(try_start, try_end, handler, Some(arithmetic));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // The quotient of 7 / 2 claimed to be 4: refuted, and the input named is 7 and 2.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 0);
            code.iconst(7);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Int, 1);
            code.iconst(2);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c);
            code.iconst(4);
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!((out.raw_inputs[&0].as_str(), out.raw_inputs[&1].as_str()), ("7", "2"));

        // Without a handler the exception leaves the harness, which the engine does not judge.
        let cp = harness("(II)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c);
            code.op(0x57);
            code.iconst(1);
            code.if_zero(Cond::Eq, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Unverifiable);
        assert!(out.problem.unwrap().contains("uncaught java.lang.ArithmeticException"));
    }

    #[test]
    fn a_violating_input_is_taken_from_the_first_stage_that_has_one() {
        // a * a >= 0 fails only from 46341 up: nothing in [0:20], the second stage has it.
        let cp = harness("(I)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.op(0x68); // imul
            code.if_zero(Cond::Lt, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage.as_deref(), Some("[-100000:100000]"));
        let a: i32 = out.raw_inputs[&0].parse().unwrap();
        assert!(a.wrapping_mul(a) < 0 && a.abs() <= 100_000, "{a}");

        // a != 5000000 fails on one input only, outside every stage.
        let cp = harness("(I)V", |code, writer, fail| {
            code.load(Kind::Int, 0);
            let big = writer.pool.integer(5_000_000);
            code.ldc(big);
            code.if_icmp(Cond::Eq, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage, None);
        assert_eq!(out.raw_inputs[&0], "5000000");

        // The path explored first (the jump, a < 0) fails only at -7000000; the other fails at 3. The search
        // goes on past the first violating path and reports the small input, from the first stage.
        let cp = harness("(I)V", |code, writer, fail| {
            let negative = code.label();
            let done = code.label();
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, negative);
            code.load(Kind::Int, 0);
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.goto(done);
            code.bind(negative);
            code.load(Kind::Int, 0);
            let big = writer.pool.integer(-7_000_000);
            code.ldc(big);
            code.if_icmp(Cond::Eq, fail);
            code.bind(done);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));
        assert_eq!(out.raw_inputs[&0], "3");
        assert!(out.paths >= 2, "{}", out.paths);

        // A long parameter is staged too, and a boolean is in every stage.
        let cp = harness("(JZ)V", |code, _, fail| {
            code.load(Kind::Int, 2);
            code.if_zero(Cond::Eq, fail);
            code.load(Kind::Long, 0);
            code.op(0x09); // lconst_0
            code.op(0x94); // lcmp
            code.if_zero(Cond::Le, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));
        let a: i64 = out.raw_inputs[&0].parse().unwrap();
        assert!((0..=20).contains(&a), "{a}");
    }

    #[test]
    fn the_stages_are_jbmcs() {
        let spelled: Vec<Option<String>> = STAGES.iter().map(|(lo, hi)| Some(format!("[{lo}:{hi}]"))).chain(std::iter::once(None)).collect();
        let jbmc: Vec<Option<String>> = crate::equivalence::STAGES.iter().map(|s| s.map(str::to_string)).collect();
        assert_eq!(spelled, jbmc);
    }

    #[test]
    fn loops_are_unwound_up_to_the_bound() {
        // for (i = 0; i < n; i++) {}  then assert i == n: fine within the bound, beyond it no verdict.
        let cp = harness("(I)V", |code, _, fail| {
            let top = code.label();
            let done = code.label();
            code.iconst(0);
            code.store(Kind::Int, 1);
            code.bind(top);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Ge, done);
            code.iinc(1, 1);
            code.goto(top);
            code.bind(done);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Lt, fail);
        });
        let out = check(&cp, "Check", "check", &Options { unwind: 4, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.unwrap().contains("not fully unwound"));
    }

    #[test]
    fn a_division_is_built_in_full_only_when_the_solver_gets_it_wrong() {
        // x % y < y for x >= 0 and y > 0: what holds of every remainder proves it, with no division circuit.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Le, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x70); // irem
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.divisions, out.refined), (1, 0), "{}", out.summary());

        // x / y == 3 claimed impossible: refuted with an input whose real quotient is 3, the circuit built if the
        // solver's first guess was not a real division.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let (x, y): (i32, i32) = (out.raw_inputs[&0].parse().unwrap(), out.raw_inputs[&1].parse().unwrap());
        assert_eq!(x.wrapping_div(y), 3, "{x} / {y}");
        assert!(out.refined <= 1, "{}", out.summary());
        assert!(out.summary().contains(&format!("{} of 1 divisions built in full", out.refined)));
    }

    #[test]
    fn an_overflow_check_calls_into_math() {
        // Math.multiplyExact(a, b) throws exactly when (long) a * b does not fit an int, and returns a * b
        // otherwise: both sides are the engine's own circuits, which fold together.
        let cp = harness("(II)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let exact = writer.pool.method_ref("java/lang/Math", "multiplyExact", "(II)I");
            let fits = |code: &mut CodeBuilder, target| {
                // (long) a * (long) b == (long) (a * b)  ->  jump to target
                code.load(Kind::Int, 0);
                code.op(0x85); // i2l
                code.load(Kind::Int, 1);
                code.op(0x85);
                code.op(0x69); // lmul
                code.load(Kind::Int, 0);
                code.load(Kind::Int, 1);
                code.op(0x68); // imul
                code.op(0x85);
                code.op(0x94); // lcmp
                code.if_zero(Cond::Eq, target);
            };
            code.bind(try_start);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op_u16(0xb8, exact);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x68);
            code.if_icmp(Cond::Ne, fail); // the exact product is the product
            let fine = code.label();
            fits(code, fine);
            code.goto(fail); // returned although the product does not fit
            code.bind(fine);
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57);
            fits(code, fail); // threw although the product fits
            code.bind(ok);
            let arithmetic = writer.pool.class("java/lang/ArithmeticException");
            code.handler(try_start, try_end, handler, Some(arithmetic));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // addExact on longs: a claim that it never throws is refuted with inputs that overflow.
        let cp = harness("(JJ)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let exact = writer.pool.method_ref("java/lang/Math", "addExact", "(JJ)J");
            code.bind(try_start);
            code.load(Kind::Long, 0);
            code.load(Kind::Long, 2);
            code.op_u16(0xb8, exact);
            code.op(0x58); // pop2
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57);
            code.goto(fail);
            code.bind(ok);
            let arithmetic = writer.pool.class("java/lang/ArithmeticException");
            code.handler(try_start, try_end, handler, Some(arithmetic));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let a: i64 = out.raw_inputs[&0].parse().unwrap();
        let b: i64 = out.raw_inputs[&2].parse().unwrap();
        assert!(a.checked_add(b).is_none(), "{a} + {b}");
    }
}
