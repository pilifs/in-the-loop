//! Bounded model checking of a harness in the tool itself, without JBMC: the harness bytecode is executed
//! symbolically over bit-vectors ([`bits`]), one path at a time, and a bundled SAT solver (CaDiCaL) decides at
//! every branch which sides are feasible and, when a path reaches the harness's `AssertionError`, what input takes
//! it there. Each path carries a model of its condition (the solver's answer when it was split off), so the side
//! of a branch that model takes is known feasible and the solver is asked once per branch, about the other side,
//! and not at all about a condition the path has taken before. That one question is given as long as the solver's
//! calls so far took together, and a side undecided by then waits until the decided paths are done, so a violation
//! is not held up by an infeasible side that is hard to refute. A division or multiplication is left to the solver
//! under what holds of every one and built as a circuit only where a model got it wrong
//! ([`bits::Blaster::sdivrem_lazy`], [`bits::Blaster::mul_lazy`]); a quotient times its divisor is the dividend
//! less the remainder, with no product.
//! Loops are unwound up to a bound, as JBMC's are, and a path that needs more is no verdict. Once more paths have
//! been explored than a small search has ([`Options::merge_after`]), paths are merged where they meet: one that
//! reaches an instruction with more than one way in (after an `if`, a loop header, a handler) waits there, and the
//! paths waiting at the earliest such point are made one path when nothing else can run, every value they differ
//! in a choice by the condition of each and its models all of theirs ([`Engine::merge`]), so that independent
//! branches add paths rather than multiply them and a branch each of whose sides some model takes costs no solver
//! call. A small search stays unmerged, each solver call being about one concrete path, which is cheaper.
//!
//! The fragment this engine handles is the one the proofs are mostly about: static methods over `int`, `long`,
//! `short`, `byte`, `char` and `boolean`, straight-line and branching arithmetic, calls into the application's own
//! static methods (inlined), the `Math`/`StrictMath` exact and floor operations with their overflow exceptions,
//! `Integer`/`Long` comparisons, exceptions thrown and caught by class, and strings only as opaque objects (a
//! message built for an exception). An array of those primitives is an object with a symbolic length and a cell
//! per index it may have ([`Array`]): an array parameter has every length up to [`Options::max_array_length`],
//! as JBMC's nondeterministic arrays do, a read is a choice among the cells by the index and a write a
//! conditional update of each, and an index out of bounds or a negative size is a branch to the exception, as a
//! division by zero is. Floating point, arrays of references, static state and the rest of the JDK are refused
//! with a reason, so that a caller can fall back to JBMC. A verdict it gives is on the same statement JBMC would
//! check, the generated harness class, so a counterexample is replayed and shrunk like JBMC's.
//!
//! Every instruction, and every call it can make, is implemented as the JVM does it, modelled (by a model whose
//! contract is written down), a named gap ([`gaps`]), or refused:
//!
//! | Instructions | Treatment |
//! |---|---|
//! | `nop`, `aconst_null`, `iconst`, `lconst`, `bipush`/`sipush`, `ldc` of an int or a long, `iload`/`lload`/`aload`, `istore`/`lstore`/`astore`, `pop`, `pop2`, `dup`, `dup_x1`, `dup_x2`, `dup2`, `dup2_x1`, `dup2_x2`, `swap`, `iinc` | implemented |
//! | `iadd` … `lxor` (arithmetic, shifts, bitwise), `i2l`, `l2i`, `i2b`, `i2c`, `i2s`, `lcmp` | implemented bit for bit; `idiv`, `irem`, `ldiv`, `lrem` throw `ArithmeticException` on zero |
//! | `ifeq` …, `if_icmpeq` …, `if_acmpeq`/`if_acmpne`, `ifnull`, `ifnonnull`, `goto`, `tableswitch`, `lookupswitch`, `ireturn` … `return` | implemented; a loop's back edge counts against the unwinding bound |
//! | `newarray`, `arraylength`, `iaload` … `saload`, `iastore` … `sastore` on arrays of primitives | implemented, up to [`Options::max_array_length`] cells; `ArrayIndexOutOfBoundsException`, `NegativeArraySizeException`, and `NullPointerException` on null |
//! | `new`, `getfield`, `putfield`, `invokestatic`, `invokespecial`, `invokevirtual`, `invokeinterface` of the application's own methods | implemented: objects with fields, calls inlined, a virtual call dispatched on its receiver's class, `NullPointerException` on a null receiver; a field resolved as the JVM resolves it (JVMS §5.4.3.2), so a field a subclass declares again is a second one |
//! | `athrow`, exception handlers, `checkcast`, `instanceof` | implemented, a handler matched by subclass |
//! | `monitorenter`, `monitorexit` | implemented: `NullPointerException` on null, and otherwise nothing, which is all a monitor does in a run of one thread |
//! | `getstatic` of a compile-time constant (an application field with a `ConstantValue`, `Integer`/`Long` `MAX_VALUE`/`MIN_VALUE`) | implemented |
//! | class initialization, at the first `new`, `getstatic` or `invokestatic` of an application class whose initialization runs a `<clinit>` ([`gaps::initializers`]) | gap: `class-initializer`, since the engine runs no initializer; a JDK class is taken to be initialized already |
//! | `invokestatic` of `Math`/`StrictMath`/`Integer`/`Long`/`Boolean` operations ([`models_jdk_static`]) | modelled in [`Engine::call_jdk_static`], each as its Javadoc specifies, exceptions included |
//! | `invokestatic` of any other JDK method over integers, booleans, arrays and objects ([`gaps::jdk_static_call`]) | gap: `jdk-static-method`, with no assume form |
//! | `invokestatic` of a class the tool's models (`lib/models`) provide | modelled: the model's bytecode runs, as in the interpreter |
//! | `invokespecial` of `Object.<init>()`, `Record.<init>()`, and a JDK exception's `()`, `(String)` or `(String, Throwable)` constructor ([`gaps::exact_jdk_call`]) | modelled exactly: they change nothing a proof observes |
//! | `invokespecial` of any other JDK constructor, `invokevirtual`/`invokeinterface` of a JDK method returning `void` or an object | gap: `jdk-constructor`, `jdk-void-method`, `jdk-reference-method` |
//! | `invokevirtual`/`invokeinterface` of a JDK method returning an integer, a `char` or a `boolean` | gap: `jdk-primitive-method`, with no assume form |
//! | `invokedynamic` string concatenation | implemented over strings and primitives (the result an opaque string); an object argument it would convert is a gap, `string-conversion` |
//! | `ldc` of a string or a class | implemented: one opaque object per distinct literal on a path, as the JVM interns strings and has one `Class` object per class |
//! | floating point (`fconst`, `dconst`, `fadd` …, `fcmpl` …, `f2i` …), `jsr`/`ret`, `putstatic`, any other `getstatic`, `anewarray`, `multianewarray`, `aaload`/`aastore`, any other `invokedynamic`, a JDK method with a floating-point parameter or result or an array result, a native method | refused: no verdict, so that `--engine auto` can ask JBMC |
//! | under JBMC, not this engine ([`crate::jbmc_gaps`]): a method with no bytecode on JBMC's class path, or an `invokedynamic` JBMC does not link, or a monitor instruction, which JBMC drops | JBMC's gaps: its stub of a JDK method is one of the JDK kinds above, any other is `missing-body`, an unlinked call site is `invokedynamic`, and a method that synchronizes is `monitor`; this engine refuses the first two and implements monitors |
//!
//! A gap is refused by name under [`gaps::GapMode::Strict`], the default: the path ends there, and a run that met
//! one has no verdict unless another path is a violation, which stands. Under [`gaps::GapMode::Assume`] the engine
//! goes on with the approximation [`gaps::GapKind::approximation`] states, and the outcome names every gap it
//! assumed ([`Outcome::gaps`]); a gap with no assume form ([`gaps::GapKind::assumable`]) is refused there too. Under [`gaps::GapMode::Advised`] it refuses a gap as under strict: the proof
//! drivers stop before the engine runs when the gap scan finds one with no contract ([`crate::advice`]), so the
//! engine meets one only where the scan did not see it. A gap a contract closes (`--contracts`,
//! [`crate::gap_contracts`], [`Options::contracts`]) is no gap: at a JDK call the engine runs the contract's method
//! of the generated class [`crate::gap_contracts::CLASS`] in place of the call, whose intrinsics open the gap again
//! on an input outside the contract's `assume:` (met at the call), give an array it modifies fresh elements, give
//! a primitive result a fresh value, and end a path the contract's assertion excludes; an initializer whose contract throws nothing is taken to have run.
//! The outcome names every gap a contract closed, with the contract (treatment `contract`).

pub mod bits;
pub mod gaps;

use std::collections::{BTreeMap, HashMap};
use std::rc::Rc;
use std::time::{Duration, Instant};

use crate::classfile::{ArithOp, ArrayKind, BootstrapArg, ClassFile, Cond, ExceptionHandler, Insn, Kind, MethodDescriptor, Narrow, Type};
use crate::classpath::ClassPath;
use crate::{Error, Verdict};
use bits::{Bits, Blaster, Lit, Model, FALSE, TRUE};
use gaps::{Closing, Closure, Gap, GapKind, GapMode, GapRecord, GapSetting, GapTreatment, JdkCall, Site};

/// What the engine is allowed.
#[derive(Debug, Clone)]
pub struct Options {
    /// How many times a loop's back edge may be taken on one path.
    pub unwind: u32,
    pub timeout: Duration,
    /// How many paths may be explored before the engine gives up.
    pub max_paths: u64,
    /// The longest an array parameter may be, as JBMC's `--max-nondet-array-length`.
    pub max_array_length: u32,
    /// How many paths are explored each on its own before the paths that meet are merged ([`Engine::merge`]): a
    /// small search is cheaper unmerged, every solver call being about one concrete path, and merging pays once
    /// the paths multiply. 0 merges from the start.
    pub merge_after: u64,
    /// What a gap does to the path that reaches it ([`gaps::GapMode`]): ends it (strict) or is assumed.
    pub gaps: GapMode,
    /// Under advised, the contracts that close gaps (`--contracts`, [`crate::gap_contracts`]): the engine applies
    /// each at its gap in place of refusing it.
    pub contracts: std::sync::Arc<BTreeMap<Gap, Closure>>,
}

impl Default for Options {
    fn default() -> Self {
        Options { unwind: 16, timeout: Duration::from_secs(600), max_paths: 200_000, max_array_length: 8, merge_after: 512, gaps: GapMode::Strict, contracts: Default::default() }
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
    /// The violating input's array parameters by slot, their elements as `raw_inputs` spells values (never
    /// `None`: an array parameter is not null).
    pub raw_arrays: BTreeMap<u32, Option<Vec<String>>>,
    /// The stage the violating input was found in, as JBMC's `--java-assume-inputs-interval` would spell it;
    /// `None` when only the whole range has one.
    pub stage: Option<String>,
    /// Why there is no verdict: something outside the fragment, a loop beyond the bound, or the budget.
    pub problem: Option<String>,
    pub paths: u64,
    /// How many paths were absorbed into another at a join point ([`Engine::merge`]).
    pub merges: u64,
    pub solves: u64,
    pub solving: f64,
    pub evaluated: u64,
    pub evaluating: f64,
    pub clauses: u64,
    pub variables: i32,
    /// How many divisions and multiplications were left to the solver under the cheap facts, and how many of each
    /// had their circuit built because the solver got one wrong ([`bits::Blaster::sdivrem_lazy`],
    /// [`bits::Blaster::mul_lazy`]).
    pub divisions: u64,
    pub refined: u64,
    pub multiplications: u64,
    pub refined_multiplications: u64,
    pub seconds: f64,
    /// The solver, for the report.
    pub solver: String,
    /// The gaps the run met, each refused (strict: a path ended there) or assumed, with where.
    pub gaps: Vec<GapRecord>,
    pub gap_mode: GapMode,
}

impl Outcome {
    /// The outcome in the shape of a JBMC result, so that the proof drivers treat it as one.
    pub fn into_jbmc_result(self, log: std::path::PathBuf) -> crate::jbmc::JbmcResult {
        let stats = self.stats();
        let ending = crate::jbmc::Ending::of_native(self.verdict, self.problem.as_deref());
        crate::jbmc::JbmcResult {
            verdict: self.verdict,
            version: format!("jvmcontract's own checker ({})", self.solver),
            properties: 1,
            raw_inputs: self.raw_inputs,
            raw_arrays: self.raw_arrays,
            stage: self.stage,
            problem: self.problem,
            log,
            seconds: self.seconds,
            native: Some(stats),
            gaps: self.gaps,
            gap_mode: Some(self.gap_mode),
            ending,
        }
    }

    /// The numbers of [`Outcome::summary`], for a structured report.
    pub fn stats(&self) -> Stats {
        Stats {
            paths: self.paths,
            merges: self.merges,
            solver_calls: self.solves,
            solving_seconds: self.solving,
            gates_evaluated: self.evaluated,
            evaluating_seconds: self.evaluating,
            divisions: self.divisions,
            divisions_built: self.refined,
            multiplications: self.multiplications,
            multiplications_built: self.refined_multiplications,
            variables: self.variables,
            clauses: self.clauses,
            seconds: self.seconds,
        }
    }

    /// One line on what the run did, for the log.
    pub fn summary(&self) -> String {
        let gaps = match self.gaps.len() {
            0 => String::new(),
            n => {
                let refused = self.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Refused)).count();
                let what = match (refused, n - refused) {
                    (_, 0) => "refused".to_string(),
                    (0, _) => "assumed".to_string(),
                    (r, a) => format!("({r} refused, {a} assumed)"),
                };
                format!(", {n} gap{} {what} (--gaps {})", if n == 1 { "" } else { "s" }, self.gap_mode.name())
            }
        };
        format!("{:?}: {} paths, {} merged at joins, {} solver calls ({:.2} s), {} gates evaluated in path models ({:.2} s), {} of {} divisions and {} of {} multiplications built in full, {} variables, {} clauses, {:.2} s{gaps}{}", self.verdict, self.paths, self.merges, self.solves, self.solving, self.evaluated, self.evaluating, self.refined, self.divisions, self.refined_multiplications, self.multiplications, self.variables, self.clauses, self.seconds, self.problem.as_deref().map(|p| format!("; {p}")).unwrap_or_default())
    }
}

/// What the engine's search took, as [`Outcome::summary`] prints it: the paths it explored and merged, the solver's
/// calls and time, the gates evaluated in path models instead, the divisions and multiplications left to the solver
/// and those whose circuit had to be built, and the size of the last formula.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct Stats {
    pub paths: u64,
    pub merges: u64,
    pub solver_calls: u64,
    pub solving_seconds: f64,
    pub gates_evaluated: u64,
    pub evaluating_seconds: f64,
    pub divisions: u64,
    pub divisions_built: u64,
    pub multiplications: u64,
    pub multiplications_built: u64,
    pub variables: i32,
    pub clauses: u64,
    pub seconds: f64,
}

/// Why a parameter type is outside the fragment, if it is.
pub fn unsupported_parameter(t: &Type) -> Option<String> {
    match t {
        Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long => None,
        Type::Array(element) if matches!(**element, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long) => None,
        other => Some(format!("a {} parameter", other.java_name())),
    }
}

/// The width of a cell of an array of `element`s: what a store keeps of the value, which a load extends to an
/// int (a boolean and a char without sign, a byte and a short with it) or leaves a long.
fn cell_width(element: &Type) -> usize {
    match element {
        Type::Boolean => 1,
        Type::Byte => 8,
        Type::Char | Type::Short => 16,
        Type::Long => 64,
        _ => 32,
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

/// An object made during the run: its class, and the fields written so far (an application exception's, say), or
/// the array it is.
#[derive(Debug, Clone)]
struct Obj {
    class: String,
    fields: BTreeMap<String, Val>,
    array: Option<Array>,
}

/// An array of primitives: its length, and a cell for every index it may have (as many as its length can be),
/// each as wide as [`cell_width`] says. A read at a symbolic index is a choice among the cells, and a write
/// updates each cell under the condition that the index is its own; an index at or beyond the length is out of
/// bounds whatever its cell holds.
#[derive(Debug, Clone)]
struct Array {
    element: Type,
    length: Bits,
    cells: Vec<Bits>,
}

/// A violating input: the scalar parameters' values and the array parameters' elements, by slot.
#[derive(Debug, Clone, Default)]
struct Input {
    scalars: BTreeMap<u32, String>,
    arrays: BTreeMap<u32, Option<Vec<String>>>,
}

/// A method's decoded code, shared by every frame that runs it.
struct Decoded {
    insns: Vec<Insn>,
    pcs: Vec<u32>,
    index: HashMap<u32, usize>,
    handlers: Vec<ExceptionHandler>,
    max_locals: usize,
    /// Per instruction, its source line, when the class has line numbers: where a gap is met.
    lines: Vec<Option<u16>>,
    /// Per instruction, whether control can reach it from more than one place (the instruction after an `if`'s
    /// scope, a loop header, a handler): where the paths that reach it are merged ([`Engine::merge`]).
    joins: Vec<bool>,
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

/// One path through the harness: its frames, the condition that selects it (a conjunction of literals), models
/// of that condition, its objects, and how often each back edge was taken.
#[derive(Clone)]
struct Path {
    frames: Vec<Frame>,
    cond: Vec<Lit>,
    /// Inputs that take the path, at least one: the solver's answer when the path was split off, or every input
    /// zero for the first, and after a merge the models of every path merged into it (up to [`MOST_MODELS`]). A
    /// side of a branch one of them takes is feasible without asking the solver, so a branch whose two sides are
    /// each taken by a model costs no solver call, and each side keeps the models that take it.
    models: Vec<Model>,
    /// Whether the path is known feasible: a twin split off at a branch the solver did not decide within its
    /// probe's budget keeps its parent's model, which takes the other side, and waits in `Engine::deferred`
    /// until every decided path is done, when the solver is asked about it with all the time left.
    undecided: bool,
    /// Whether the path was just taken from a join point, where it waited for the other paths to arrive, and is
    /// to run the join's instruction rather than wait there again.
    resumed: bool,
    objects: Vec<Obj>,
    back_edges: HashMap<(String, String, u32), u32>,
    /// The object each string or class literal loaded so far is, so that every load of one literal is the same
    /// reference, as the JVM's interned strings and `Class` objects are.
    literals: BTreeMap<Literal, usize>,
    /// The application classes whose initialization the path has reached ([`gaps::initializers`]), so that a
    /// `class-initializer` gap is met once per class, where the JVM would run the initializer.
    initialised: std::collections::BTreeSet<String>,
}

/// A string or class literal, the identity of what an `ldc` of it loads.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Literal {
    Str(String),
    Class(String),
}

/// Where a path waits at a join point: each frame's instruction index, class and method, outermost first, so that
/// the paths of one group are at the same instruction of the same calls, and the group earliest in the harness
/// (the smallest key) is resumed first, since what is still running can only arrive at a later one.
type JoinKey = Vec<(usize, String, String)>;

fn join_key(path: &Path) -> JoinKey {
    path.frames.iter().map(|f| (f.at, f.class.name.clone(), f.method.clone())).collect()
}

/// Whether two values can be one value under a condition: both ints, both longs, or the same reference.
fn mergeable(a: &Val, b: &Val) -> bool {
    match (a, b) {
        (Val::I(_), Val::I(_)) | (Val::J(_), Val::J(_)) => true,
        (Val::R(x), Val::R(y)) => x == y,
        _ => false,
    }
}

/// Whether two paths at the same join point have states of one shape, so that they can be merged: the same
/// slots and objects, with references to the same objects (the paths only differ in bits).
fn same_shape(a: &Path, b: &Path) -> bool {
    let slots = |x: &Option<Val>, y: &Option<Val>| match (x, y) {
        (None, None) => true,
        (Some(x), Some(y)) => mergeable(x, y),
        _ => false,
    };
    a.frames.len() == b.frames.len()
        && a.frames.iter().zip(&b.frames).all(|(f, g)| f.locals.len() == g.locals.len() && f.locals.iter().zip(&g.locals).all(|(x, y)| slots(x, y)) && f.stack.len() == g.stack.len() && f.stack.iter().zip(&g.stack).all(|(x, y)| mergeable(x, y)))
        && a.objects.len() == b.objects.len()
        && a.literals == b.literals
        && a.objects.iter().zip(&b.objects).all(|(o, q)| {
            o.class == q.class
                && o.fields.len() == q.fields.len()
                && o.fields.iter().zip(&q.fields).all(|((k, x), (l, y))| k == l && mergeable(x, y))
                && match (&o.array, &q.array) {
                    (None, None) => true,
                    (Some(x), Some(y)) => x.element == y.element && x.cells.len() == y.cells.len(),
                    _ => false,
                }
        })
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
    /// The path reached a gap under `--gaps strict`, which refuses it: what lies beyond it is not known.
    Gap,
    /// The path reached a join point and waits there for the paths that arrive after it.
    Parked,
}

/// Why the engine stops without a verdict.
enum Stop {
    Unsupported(String),
    Budget(String),
}

type Step = Result<Option<End>, Stop>;

/// Which sides of a branch are feasible under the path condition.
enum Sides {
    /// Both, with the path's models that take each side (the solver's answer where none of its own did).
    Both { then_models: Vec<Model>, else_models: Vec<Model> },
    Then,
    Else,
    /// The side the path's models take, the other undecided: the solver did not answer within the probe's budget.
    Undecided { model_takes_then: bool },
}

/// How many models a path keeps after a merge: the first ones, since every path has at least one.
const MOST_MODELS: usize = 16;

struct Engine<'a> {
    cp: &'a ClassPath,
    b: Blaster,
    codes: HashMap<(String, String, String), Rc<Decoded>>,
    pending: Vec<Path>,
    /// The paths the solver did not decide in time, taken up when `pending` is empty.
    deferred: Vec<Path>,
    /// The paths waiting at join points, by where they wait; a group is merged and resumed when `pending` is
    /// empty, the earliest first.
    waiting: BTreeMap<JoinKey, Vec<Path>>,
    merges: u64,
    merge_after: u64,
    unwind: u32,
    deadline: Instant,
    max_paths: u64,
    paths: u64,
    /// The harness's scalar parameters: slot, type and bits, for reading the input off a model.
    params: Vec<(u32, Type, Bits)>,
    /// The harness's array parameters: slot, element type, length and cells, for reading the input off a model
    /// (the cells as made; a path writes into its own copy of the object).
    arrays: Vec<(u32, Type, Bits, Vec<Bits>)>,
    max_array_length: u32,
    /// One literal per entry of [`STAGES`], true when every parameter is in the range; built at the first
    /// violation, so that a proof pays nothing for them.
    stage_lits: Vec<Option<Lit>>,
    gap_mode: GapMode,
    /// The gaps met so far, with where.
    met: BTreeMap<Gap, std::collections::BTreeSet<Site>>,
    /// The contracts that close gaps, and the gaps they closed so far, with where.
    contracts: std::sync::Arc<BTreeMap<Gap, Closure>>,
    applied: BTreeMap<Gap, std::collections::BTreeSet<Site>>,
    /// Whether an object of a class has a field that a subclass along its chain declares again, by class: only
    /// then does an access need the field's resolution to find its key ([`ClassPath::field_key`]).
    hides: HashMap<String, bool>,
    /// The application classes whose `<clinit>` initializing a class would run, by class ([`gaps::initializers`]).
    initializers: HashMap<String, Rc<Vec<String>>>,
}

fn unsupported<T>(what: impl Into<String>) -> Result<T, Stop> {
    Err(Stop::Unsupported(what.into()))
}

/// Whether a load or store instruction of `kind` fits an array of `element`s, as the verifier requires.
fn check_kind(kind: ArrayKind, element: &Type) -> Result<(), Stop> {
    let fits = match kind {
        ArrayKind::Int => *element == Type::Int,
        ArrayKind::Long => *element == Type::Long,
        ArrayKind::Byte => matches!(element, Type::Byte | Type::Boolean),
        ArrayKind::Char => *element == Type::Char,
        ArrayKind::Short => *element == Type::Short,
        ArrayKind::Float | ArrayKind::Double => return unsupported("floating point"),
        ArrayKind::Ref => return unsupported("arrays of references"),
    };
    if fits {
        Ok(())
    } else {
        unsupported(format!("a {kind:?} array instruction on a {}[]", element.java_name()))
    }
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
        waiting: BTreeMap::new(),
        merges: 0,
        merge_after: options.merge_after,
        unwind: options.unwind,
        deadline: started + options.timeout,
        max_paths: options.max_paths,
        paths: 0,
        params: Vec::new(),
        arrays: Vec::new(),
        max_array_length: options.max_array_length,
        stage_lits: vec![None; STAGES.len()],
        gap_mode: options.gaps,
        met: BTreeMap::new(),
        contracts: options.contracts.clone(),
        applied: BTreeMap::new(),
        hides: HashMap::new(),
        initializers: HashMap::new(),
    };
    let solver = engine.b.signature();
    let jdk = gaps::jdk_release();
    let outcome = |engine: &Engine, verdict: Verdict, input: Input, stage: Option<String>, problem: Option<String>| Outcome {
        verdict,
        raw_inputs: input.scalars,
        raw_arrays: input.arrays,
        stage,
        problem,
        paths: engine.paths,
        merges: engine.merges,
        solves: engine.b.solves,
        solving: engine.b.solving.as_secs_f64(),
        evaluated: engine.b.evaluated,
        evaluating: engine.b.evaluating.as_secs_f64(),
        clauses: engine.b.clauses,
        variables: engine.b.variables(),
        divisions: engine.b.divisions().0,
        refined: engine.b.divisions().1,
        multiplications: engine.b.multiplications().0,
        refined_multiplications: engine.b.multiplications().1,
        seconds: started.elapsed().as_secs_f64(),
        solver: solver.clone(),
        gaps: gaps::records(&engine.met, jdk.as_deref(), Some(if engine.gap_mode.refuses() { GapTreatment::Refused } else { GapTreatment::Assumed })).into_iter().chain(gaps::contract_records(&engine.applied, &engine.contracts, jdk.as_deref())).collect(),
        gap_mode: engine.gap_mode,
    };

    // The inputs: fresh bits per parameter, in its range; an array parameter is an object of a fresh length up to
    // the bound (the first path's condition) with fresh cells.
    let mut locals: Vec<Option<Val>> = Vec::new();
    let mut objects: Vec<Obj> = Vec::new();
    let mut cond: Vec<Lit> = Vec::new();
    let mut slot = 0u32;
    for t in &descriptor.params {
        if let Some(why) = unsupported_parameter(t) {
            return Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("outside the fragment: {why}"))));
        }
        if let Type::Array(element) = t {
            let length = engine.b.fresh(32);
            let zero = engine.b.constant(0, 32);
            let most = engine.b.constant(i64::from(options.max_array_length), 32);
            cond.push(engine.b.sle(&zero, &length));
            cond.push(engine.b.sle(&length, &most));
            let cells: Vec<Bits> = (0..options.max_array_length).map(|_| engine.b.fresh(cell_width(element))).collect();
            engine.arrays.push((slot, (**element).clone(), length.clone(), cells.clone()));
            objects.push(Obj { class: format!("{}[]", element.java_name()), fields: BTreeMap::new(), array: Some(Array { element: (**element).clone(), length, cells }) });
            locals.push(Some(Val::R(Some(objects.len() - 1))));
            slot += 1;
            continue;
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
    let first = Path { frames: vec![Frame { class: harness.clone(), method: m.name.clone(), code, at: 0, locals, stack: Vec::new() }], cond, models: vec![Model::default()], undecided: false, resumed: false, objects, back_edges: HashMap::new(), literals: BTreeMap::new(), initialised: Default::default() };
    engine.pending.push(first);

    // The smallest violating input so far, by stage: a path that only has one outside the stages does not end the
    // search, since another path may have one in the first stage, as it does when the first path to fail is an
    // overflow and the second a rounding. The search for a better one is given as long again as the first took,
    // within the deadline; the violation stands whatever the remaining paths do.
    let mut best: Option<(usize, Input)> = None;
    let violation = |engine: &Engine, best: Option<(usize, Input)>| {
        let (stage, input) = best.expect("a violation");
        let stage = STAGES.get(stage).map(|(lo, hi)| format!("[{lo}:{hi}]"));
        outcome(engine, Verdict::Violation, input, stage, None)
    };
    loop {
        let path = match engine.next_path() {
            Ok(Some(path)) => path,
            Ok(None) => break,
            Err(stop) => return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(stop_text(&stop))) }),
        };
        if engine.paths > engine.max_paths {
            return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("more than {} paths; the budget is spent", engine.max_paths))) });
        }
        match engine.run(path) {
            Ok(End::Returned) | Ok(End::Infeasible) | Ok(End::Parked) | Ok(End::Gap) => {}
            Ok(End::Violation(cond)) => {
                let (stage, input) = match engine.staged_input(&cond) {
                    Ok(found) => found,
                    Err(stop) if best.is_some() => {
                        let _ = stop;
                        return Ok(violation(&engine, best));
                    }
                    Err(stop) => return Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(stop_text(&stop)))),
                };
                if best.as_ref().is_none_or(|(s, _)| stage < *s) {
                    if best.is_none() {
                        let elapsed = started.elapsed();
                        engine.deadline = engine.deadline.min(Instant::now() + elapsed.max(Duration::from_secs(1)));
                    }
                    best = Some((stage, input));
                }
                if stage == 0 {
                    return Ok(violation(&engine, best));
                }
            }
            Ok(End::Unwound(what)) => {
                return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("a loop was not fully unwound with --unwind {} ({what})", options.unwind))) })
            }
            Err(Stop::Unsupported(what)) => {
                return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("outside the fragment: {what}"))) })
            }
            Err(Stop::Budget(what)) => return Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(what)) }),
        }
    }
    if best.is_some() {
        return Ok(violation(&engine, best));
    }
    if !engine.met.is_empty() && (engine.gap_mode.refuses() || engine.met.keys().any(|g| !g.kind.assumable())) {
        let refused: BTreeMap<Gap, std::collections::BTreeSet<Site>> = engine.met.iter().filter(|(g, _)| engine.gap_mode.refuses() || !g.kind.assumable()).map(|(g, s)| (g.clone(), s.clone())).collect();
        let problem = refused_gaps(&gaps::records(&refused, jdk.as_deref(), None), engine.gap_mode);
        return Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(problem)));
    }
    Ok(outcome(&engine, Verdict::Verified, Input::default(), None, None))
}

/// Why a run that refused gaps has no verdict: each gap by its id, with the call and where.
pub fn refused_gaps(gaps: &[GapRecord], mode: GapMode) -> String {
    let n = gaps.len();
    let list = gaps.iter().map(|g| format!("{} ({} at {})", g.id, g.call, g.sites.join(", "))).collect::<Vec<_>>().join("; ");
    let assumable: Vec<&GapRecord> = gaps.iter().filter(|g| g.kind.assumable()).collect();
    let after = if assumable.is_empty() {
        if n == 1 { "It has no approximation under --gaps assume, since its value could only be made up: only a contract closes it (--gaps advised)".to_string() } else { "They have no approximation under --gaps assume, since their values could only be made up: only contracts close them (--gaps advised)".to_string() }
    } else {
        let instead = match (gaps, assumable.as_slice()) {
            ([_], [g]) => format!("that {} {}", g.call, g.approximation),
            _ => "what each gap's approximation states".to_string(),
        };
        let rest = if assumable.len() < n { ", except where a gap has no approximation" } else { "" };
        format!("With --gaps assume it assumes instead {instead}, and the verdict names the assumption{rest}")
    };
    format!("the tool's own checker met {n} gap{s}, a construct it does not implement as the JVM does, and refused {it} (--gaps {mode}): {list}. {after}", s = if n == 1 { "" } else { "s" }, it = if n == 1 { "it" } else { "them" }, mode = mode.name())
}

/// The SAT solver the engine is built with, by name and version: `CaDiCaL 1.9.5 (bundled)`.
pub fn solver_signature() -> String {
    let signature = cadical::Solver::<cadical::Timeout>::new().signature().to_string();
    match signature.strip_prefix("cadical-") {
        Some(version) => format!("CaDiCaL {version} (bundled)"),
        None => format!("{signature} (bundled)"),
    }
}

/// Runs the engine on a harness for the proof drivers: the class path is the harness, the application classes
/// and their class path (not the JDK classes extracted for JBMC: a JDK method is modelled here, never run), with
/// the tool's models; the result is in JBMC's shape, and a line goes to `work/bmc.log`.
#[allow(clippy::too_many_arguments)] // the settings a proof driver passes on
pub fn run_for_proof(entries: &[std::path::PathBuf], models: bool, class: &str, method: &str, unwind: u32, max_array_length: u32, timeout: Duration, gaps: &GapSetting, work: &std::path::Path) -> Result<crate::jbmc::JbmcResult, Error> {
    let cp = crate::witness::classpath(entries.iter().chain(&gaps.class_dir).map(std::path::PathBuf::as_path))?.with_models(models);
    let outcome = check(&cp, class, method, &Options { unwind, timeout, max_array_length, gaps: gaps.mode, contracts: gaps.contracts.clone(), ..Options::default() })?;
    let log = work.join("bmc.log");
    let _ = std::fs::write(&log, format!("jvmcontract's own checker on {class}.{method}\n{}\n", outcome.summary()));
    Ok(outcome.into_jbmc_result(log))
}

/// Where a frame is: its method and the source line of its instruction.
fn site(frame: &Frame) -> Site {
    Site { class: frame.class.name.clone(), method: frame.method.clone(), line: frame.code.lines[frame.at] }
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
        // A join is an instruction with more than one way in: the fall-through from the one before it, a branch
        // to it, or, for a handler, any instruction its range covers.
        let mut ways_in = vec![0u32; insns.len()];
        ways_in[0] += 1;
        for (i, insn) in insns.iter().enumerate() {
            let falls_through = !matches!(insn, Insn::Goto(_) | Insn::Jsr(_) | Insn::Ret(_) | Insn::TableSwitch { .. } | Insn::LookupSwitch { .. } | Insn::Return(_) | Insn::AThrow);
            if falls_through && i + 1 < insns.len() {
                ways_in[i + 1] += 1;
            }
            for target in insn.targets() {
                if let Some(&j) = index.get(&target) {
                    ways_in[j] += 1;
                }
            }
        }
        for h in &code.exception_table {
            if let Some(&j) = index.get(&u32::from(h.handler_pc)) {
                ways_in[j] += 2;
            }
        }
        let joins = ways_in.iter().map(|&n| n >= 2).collect();
        let lines = pcs.iter().map(|&pc| code.line_at(pc)).collect();
        let compiled = Rc::new(Decoded { insns, pcs, index, handlers: code.exception_table.clone(), max_locals: code.max_locals as usize, lines, joins });
        self.codes.insert(key, compiled.clone());
        Ok(compiled)
    }

    /// Runs one path to its end, or, once `Options::merge_after` paths have been explored, to a join point, where
    /// it waits (`End::Parked`) for the paths that arrive after it to be merged with it; twins of it go to `pending`.
    fn run(&mut self, mut path: Path) -> Result<End, Stop> {
        let mut steps: u64 = 0;
        loop {
            if !path.resumed && self.paths > self.merge_after {
                let frame = path.frames.last().expect("a frame");
                if frame.code.joins[frame.at] {
                    self.waiting.entry(join_key(&path)).or_default().push(path);
                    return Ok(End::Parked);
                }
            }
            path.resumed = false;
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
    /// versions test) is decided without the solver; otherwise a side one of the path's models takes is feasible,
    /// and the solver is asked once, about a side no model takes.
    fn sides(&mut self, path: &mut Path, c: Lit) -> Result<Sides, Stop> {
        if c == TRUE || path.cond.contains(&c) {
            return Ok(Sides::Then);
        }
        if c == FALSE || path.cond.contains(&-c) {
            return Ok(Sides::Else);
        }
        let (mut then_models, mut else_models): (Vec<Model>, Vec<Model>) = (Vec::new(), Vec::new());
        for mut model in path.models.drain(..) {
            if self.b.holds(&mut model, c) {
                then_models.push(model);
            } else {
                else_models.push(model);
            }
        }
        if !then_models.is_empty() && !else_models.is_empty() {
            return Ok(Sides::Both { then_models, else_models });
        }
        let model_takes_then = !then_models.is_empty();
        let mut assumptions = path.cond.clone();
        assumptions.push(if model_takes_then { -c } else { c });
        let answer = self.probe(&assumptions);
        if let Ok(Some(true)) = answer {
            if model_takes_then {
                else_models.push(self.b.snapshot());
            } else {
                then_models.push(self.b.snapshot());
            }
            return Ok(Sides::Both { then_models, else_models });
        }
        // The path keeps its models, which all take one side.
        path.models = if model_takes_then { then_models } else { else_models };
        match answer? {
            None => Ok(Sides::Undecided { model_takes_then }),
            Some(false) if model_takes_then => Ok(Sides::Then),
            _ => Ok(Sides::Else),
        }
    }

    /// Splits the path on `c` when both sides are feasible: the twin returned takes the then side when
    /// `twin_takes_then`, else the else side, and the path the other; each keeps the models of its side.
    fn split(&self, path: &mut Path, c: Lit, then_models: Vec<Model>, else_models: Vec<Model>, twin_takes_then: bool) -> Path {
        let mut twin = path.clone();
        twin.resumed = false;
        if twin_takes_then {
            twin.models = then_models;
            path.models = else_models;
        } else {
            twin.models = else_models;
            path.models = then_models;
        }
        twin.cond.push(if twin_takes_then { c } else { -c });
        path.cond.push(if twin_takes_then { -c } else { c });
        twin
    }

    /// Splits the path on `c` when the side its models do not take is undecided: the path goes on with its
    /// side, and the twin returned takes the other, undecided, with the path's models (see `Path::undecided`).
    fn split_undecided(&self, path: &mut Path, c: Lit, model_takes_then: bool) -> Path {
        let mut twin = path.clone();
        twin.resumed = false;
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
        twin.models = vec![self.b.snapshot()];
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
        let mut values: Vec<(Type, Bits)> = self.params.iter().map(|(_, t, bits)| (t.clone(), bits.clone())).collect();
        for (_, element, _, cells) in &self.arrays {
            values.extend(cells.iter().map(|c| (element.clone(), self.b.extend_cell(element, c))));
        }
        for (t, bits) in values {
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
    fn staged_input(&mut self, cond: &[Lit]) -> Result<(usize, Input), Stop> {
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

    /// The parameters' values in the solver's last model: an array's elements are its cells up to its length.
    fn input(&self) -> Input {
        let unsigned = |t: &Type, v: i64| match t {
            Type::Char => v & 0xFFFF,
            Type::Boolean => v & 1,
            _ => v,
        };
        let mut input = Input::default();
        for (slot, t, bits) in &self.params {
            input.scalars.insert(*slot, unsigned(t, self.b.eval(bits)).to_string());
        }
        for (slot, element, length, cells) in &self.arrays {
            let n = usize::try_from(self.b.eval(length)).unwrap_or(0).min(cells.len());
            input.arrays.insert(*slot, Some(cells[..n].iter().map(|c| unsigned(element, self.b.eval(c)).to_string()).collect()));
        }
        input
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
                Some(true) => match self.b.wrong_operation() {
                    None => return Ok(Some(true)),
                    Some(i) => self.b.refine_operation(i),
                },
            }
        }
    }

    /// The next path to run: a decided one from `pending`; when there is none, the group waiting at the earliest
    /// join point, merged; when nothing waits, a deferred one the solver now decides with all the time left (an
    /// infeasible one is dropped). `None` when every path is done.
    fn next_path(&mut self) -> Result<Option<Path>, Stop> {
        loop {
            if let Some(path) = self.pending.pop() {
                if path.undecided {
                    self.deferred.push(path);
                    continue;
                }
                if !path.resumed {
                    self.paths += 1;
                }
                return Ok(Some(path));
            }
            if let Some(key) = self.waiting.keys().next().cloned() {
                let group = self.waiting.remove(&key).expect("a group");
                let mut merged = self.merge(group);
                let first = merged.pop().expect("a path");
                self.pending.extend(merged);
                return Ok(Some(first));
            }
            let Some(mut path) = self.deferred.pop() else {
                return Ok(None);
            };
            if self.solve(&path.cond)? {
                path.models = vec![self.b.snapshot()];
                path.undecided = false;
                self.paths += 1;
                return Ok(Some(path));
            }
        }
    }

    /// Merges the paths waiting at one join point into as few as have one shape ([`same_shape`]): each path
    /// absorbed into another makes every value they differ in a choice by the absorbed path's condition, and the
    /// condition of the merged path the disjunction of theirs. The paths through an `if` are one path after it,
    /// and the paths through a loop body one path at the header, so that a method of `n` independent branches is
    /// explored in `n` paths and not `2^n`. The merged path keeps the models of both, which take it; its
    /// condition is the common prefix of the two, then the literals both took after it, then one literal for
    /// either rest.
    fn merge(&mut self, group: Vec<Path>) -> Vec<Path> {
        let mut merged: Vec<Path> = Vec::new();
        for mut path in group {
            path.resumed = true;
            match merged.iter_mut().find(|m| same_shape(m, &path)) {
                Some(into) => {
                    self.absorb(into, &path);
                    self.merges += 1;
                }
                None => merged.push(path),
            }
        }
        merged
    }

    fn absorb(&mut self, into: &mut Path, other: &Path) {
        let prefix = into.cond.iter().zip(&other.cond).take_while(|(x, y)| x == y).count();
        let common: Vec<Lit> = into.cond[prefix..].iter().copied().filter(|l| other.cond[prefix..].contains(l)).collect();
        let rest_into: Vec<Lit> = into.cond[prefix..].iter().copied().filter(|l| !common.contains(l)).collect();
        let rest_other: Vec<Lit> = other.cond[prefix..].iter().copied().filter(|l| !common.contains(l)).collect();
        let takes_into = self.b.all(&rest_into);
        let takes_other = self.b.all(&rest_other);
        let either = self.b.or(takes_into, takes_other);
        into.cond.truncate(prefix);
        into.cond.extend(common);
        into.initialised.extend(other.initialised.iter().cloned());
        if either != TRUE {
            into.cond.push(either);
        }
        let choose = |b: &mut Blaster, x: &mut Val, y: &Val| match (x, y) {
            (Val::I(p), Val::I(q)) | (Val::J(p), Val::J(q)) if p != q => *p = b.ite_bits(takes_into, p, q),
            _ => {}
        };
        for (f, g) in into.frames.iter_mut().zip(&other.frames) {
            for (x, y) in f.locals.iter_mut().zip(&g.locals) {
                if let (Some(x), Some(y)) = (x, y) {
                    choose(&mut self.b, x, y);
                }
            }
            for (x, y) in f.stack.iter_mut().zip(&g.stack) {
                choose(&mut self.b, x, y);
            }
        }
        for (o, q) in into.objects.iter_mut().zip(&other.objects) {
            for (name, x) in o.fields.iter_mut() {
                choose(&mut self.b, x, &q.fields[name]);
            }
            if let (Some(x), Some(y)) = (&mut o.array, &q.array) {
                if x.length != y.length {
                    x.length = self.b.ite_bits(takes_into, &x.length, &y.length);
                }
                for (c, d) in x.cells.iter_mut().zip(&y.cells) {
                    if c != d {
                        *c = self.b.ite_bits(takes_into, c, d);
                    }
                }
            }
        }
        // The paths may be at different iterations of a loop (one left an earlier loop sooner); the merged path
        // counts the fewer, so that the iterations the other has left are not counted twice, which would report
        // the loop as beyond the bound when no path is. A path needing more than the bound is still stopped, at
        // most as many iterations later as the counts differed: nothing is cut short, only reported later.
        into.back_edges.retain(|key, taken| {
            *taken = (*taken).min(other.back_edges.get(key).copied().unwrap_or(0));
            *taken > 0
        });
        into.models.extend(other.models.iter().take(MOST_MODELS.saturating_sub(into.models.len())).cloned());
    }

    /// Takes the branch on `c`: the path goes on with `c` and jumps to `then`, or with `¬c` and jumps to `else_`,
    /// or both, the twin for the else side joining `pending`. `None` if neither side is feasible.
    fn branch(&mut self, path: &mut Path, c: Lit, then: usize, else_: usize) -> Result<Option<End>, Stop> {
        match self.sides(path, c)? {
            Sides::Both { then_models, else_models } => {
                let mut twin = self.split(path, c, then_models, else_models, false);
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
        self.branch_throw_or(path, c, exception, move |engine, path| {
            engine.push(path, value);
            engine.advance(path);
        })
    }

    /// Splits the path on `c` where the then side throws `exception` and the else side does `go_on` (which moves
    /// past the instruction): an index out of bounds, a negative array size.
    fn branch_throw_or(&mut self, path: &mut Path, c: Lit, exception: &str, go_on: impl FnOnce(&mut Self, &mut Path)) -> Step {
        match self.sides(path, c)? {
            Sides::Both { then_models, else_models } => {
                let mut twin = self.split(path, c, then_models, else_models, false);
                go_on(self, &mut twin);
                self.pending.push(twin);
                self.raise(path, exception)
            }
            Sides::Then => {
                path.cond.push(c);
                self.raise(path, exception)
            }
            Sides::Else => {
                path.cond.push(-c);
                go_on(self, path);
                Ok(None)
            }
            Sides::Undecided { model_takes_then: true } => {
                let mut twin = self.split_undecided(path, c, true);
                go_on(self, &mut twin);
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
                go_on(self, path);
                Ok(None)
            }
        }
    }

    /// `arraylength`, `newarray`, and a load or store at an index: the index must be below the length (an int
    /// compared unsigned, so that a negative one is out of bounds too), else `ArrayIndexOutOfBoundsException`;
    /// a new array's size must not be negative, and must be known to be within the bound, since a cell is made
    /// per index.
    fn array_insn(&mut self, path: &mut Path, insn: &Insn) -> Step {
        match insn {
            Insn::ArrayLength => {
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let length = path.objects[o].array.as_ref().expect("an array").length.clone();
                self.push(path, Val::I(length));
                self.advance(path);
                Ok(None)
            }
            Insn::ArrayLoad(kind) => {
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let array = path.objects[o].array.clone().expect("an array");
                check_kind(*kind, &array.element)?;
                let width = cell_width(&array.element);
                let mut value = array.cells.last().cloned().unwrap_or_else(|| self.b.constant(0, width));
                for (i, cell) in array.cells.iter().enumerate().rev().skip(1) {
                    let here = self.b.constant(i as i64, 32);
                    let is = self.b.eq(&index, &here);
                    value = self.b.ite_bits(is, cell, &value);
                }
                let value = self.b.extend_cell(&array.element, &value);
                let value = if array.element == Type::Long { Val::J(value) } else { Val::I(value) };
                let in_bounds = self.b.ult(&index, &array.length);
                self.branch_throw(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", value)
            }
            Insn::ArrayStore(kind) => {
                let value = match self.pop(path)? {
                    Val::I(b) | Val::J(b) => b,
                    Val::R(_) => return unsupported("arrays of references"),
                };
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let array = path.objects[o].array.as_ref().expect("an array");
                check_kind(*kind, &array.element)?;
                let width = cell_width(&array.element);
                if value.len() < width {
                    return unsupported("a store of a narrower value into an array");
                }
                let stored = self.b.trunc(&value, width);
                let length = array.length.clone();
                let in_bounds = self.b.ult(&index, &length);
                self.branch_throw_or(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", move |engine, path| {
                    let cells = &mut path.objects[o].array.as_mut().expect("an array").cells;
                    for (i, cell) in cells.iter_mut().enumerate() {
                        let here = engine.b.constant(i as i64, 32);
                        let is = engine.b.eq(&index, &here);
                        *cell = engine.b.ite_bits(is, &stored, cell);
                    }
                    engine.advance(path);
                })
            }
            Insn::NewArray(kind) => {
                let element = match kind {
                    ArrayKind::Int => Type::Int,
                    ArrayKind::Long => Type::Long,
                    ArrayKind::Byte => Type::Byte,
                    ArrayKind::Char => Type::Char,
                    ArrayKind::Short => Type::Short,
                    ArrayKind::Float | ArrayKind::Double => return unsupported("floating point"),
                    ArrayKind::Ref => return unsupported("arrays of references"),
                };
                let count = self.pop_int(path)?;
                let cells = match self.b.constant_value(&count) {
                    Some(n) if n < 0 => 0,
                    Some(n) if n <= 1 << 16 => n as usize,
                    Some(n) => return unsupported(format!("an array of {n} elements")),
                    None => {
                        // A computed size: within the bound, as a copy of a parameter is, or beyond the engine.
                        let most = self.b.constant(i64::from(self.max_array_length), 32);
                        let beyond = self.b.slt(&most, &count);
                        let mut assumptions = path.cond.clone();
                        assumptions.push(beyond);
                        if self.solve(&assumptions)? {
                            return unsupported(format!("an array of computed size, not known to be within {} elements", self.max_array_length));
                        }
                        self.max_array_length as usize
                    }
                };
                let negative = self.b.negative(&count);
                let width = cell_width(&element);
                self.branch_throw_or(path, negative, "java/lang/NegativeArraySizeException", move |engine, path| {
                    let zero = engine.b.constant(0, width);
                    path.objects.push(Obj { class: format!("{}[]", element.java_name()), fields: BTreeMap::new(), array: Some(Array { element, length: count, cells: vec![zero; cells] }) });
                    let o = path.objects.len() - 1;
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                })
            }
            _ => unsupported("arrays of references"),
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
        path.objects.push(Obj { class: class.to_string(), fields: BTreeMap::new(), array: None });
        path.objects.len() - 1
    }

    /// The array the reference on the stack is, after the null check.
    fn pop_array(&mut self, path: &mut Path) -> Result<usize, Step> {
        let r = self.pop_ref(path).map_err(Err)?;
        let o = self.null_check(path, r)?.expect("checked");
        if path.objects[o].array.is_none() {
            return Err(unsupported("an array operation on an object that is not an array"));
        }
        Ok(o)
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
                // One object per distinct literal, as the JVM interns strings (JLS §3.10.5) and has one `Class`
                // object per class.
                BootstrapArg::Str(text) => {
                    let o = self.literal(path, Literal::Str(text), "java/lang/String");
                    self.push(path, Val::R(Some(o)));
                }
                BootstrapArg::Class(name) => {
                    let o = self.literal(path, Literal::Class(name), "java/lang/Class");
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
            Insn::ArrayLoad(_) | Insn::ArrayStore(_) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::ArrayLength | Insn::MultiANewArray(..) => return self.array_insn(path, &insn),
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
                let declaring = self.cp.resolve_field(&member.owner, &member.name, &member.descriptor).unwrap_or_else(|| member.owner.clone());
                if let Some(end) = self.initialise(path, &declaring) {
                    return Ok(Some(end));
                }
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
                let key = self.field_key(path, o, &member.owner, &member.name, &member.descriptor)?;
                let v = match path.objects[o].fields.get(&key) {
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
                let key = self.field_key(path, o, &member.owner, &member.name, &member.descriptor)?;
                path.objects[o].fields.insert(key, v);
            }
            Insn::InvokeStatic(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let descriptor = MethodDescriptor::parse(&member.descriptor).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let args = self.pop_args(path, descriptor.params.len())?;
                if member.owner == crate::gap_contracts::INTRINSICS {
                    return self.intrinsic(path, &member.name, args);
                }
                if self.cp.is_application(&member.owner) {
                    // The class that declares the method is initialized first (JVMS §5.5).
                    let declaring = self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).map(|(cf, _)| cf.name.clone()).unwrap_or_else(|| member.owner.clone());
                    if let Some(end) = self.initialise(path, &declaring) {
                        return Ok(Some(end));
                    }
                    return self.call(path, &member.owner, &member.name, &member.descriptor, args);
                }
                // A JDK class the tool models (Character.digit, say) runs as bytecode here too, so that the
                // engine and the interpreter that replays its witnesses agree on it.
                if self.cp.model(&member.owner).is_some() && self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).is_some_and(|(_, m)| m.code.is_some()) {
                    return self.call(path, &member.owner, &member.name, &member.descriptor, args);
                }
                match gaps::jdk_static_call(&member.owner, &member.name, &member.descriptor) {
                    JdkCall::Exact => return self.call_jdk_static(path, &member.owner, &member.name, &member.descriptor, &descriptor, args),
                    JdkCall::Refused => return unsupported(format!("{}.{}{}", member.owner.replace('/', "."), member.name, member.descriptor)),
                    JdkCall::Gap(kind) => {
                        let gap = Gap { kind, owner: member.owner.clone(), name: member.name.clone(), descriptor: member.descriptor.clone() };
                        if let Some(Closure { how: Closing::Stub { method, descriptor: stub, .. }, .. }) = self.contracts.get(&gap).cloned() {
                            self.apply(path, gap);
                            return self.call(path, crate::gap_contracts::CLASS, &method, &stub, args);
                        }
                        // No approximation: the path ends here in every mode.
                        return Ok(self.meet(path, kind, &member.owner, &member.name, &member.descriptor));
                    }
                }
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
                // A JDK method on an opaque object: reproduced exactly (an exception's constructor), a gap, or, with
                // a floating-point or array result, refused. Under assume, a constructor does nothing, a void method
                // nothing, and a method that returns an object returns a new one; one that returns a primitive has
                // no approximation, and is refused there too.
                match gaps::jdk_instance_call(self.cp, &member.owner, &member.name, &member.descriptor) {
                    JdkCall::Exact => {}
                    JdkCall::Gap(kind) => {
                        let gap = Gap { kind, owner: member.owner.clone(), name: member.name.clone(), descriptor: member.descriptor.clone() };
                        if let Some(Closure { how: Closing::Stub { method, descriptor: stub, receiver }, .. }) = self.contracts.get(&gap).cloned() {
                            // A contract closes the gap: its method of the generated class runs in place of the call.
                            self.apply(path, gap);
                            let mut full = Vec::new();
                            if receiver {
                                full.push(Val::R(Some(o)));
                            }
                            full.extend(args);
                            return self.call(path, crate::gap_contracts::CLASS, &method, &stub, full);
                        }
                        if let Some(end) = self.meet(path, kind, &member.owner, &member.name, &member.descriptor) {
                            return Ok(Some(end));
                        }
                        if let Type::Object(name) = &descriptor.ret {
                            let r = self.alloc(path, name);
                            self.push(path, Val::R(Some(r)));
                        }
                    }
                    JdkCall::Refused => return unsupported(format!("{}.{} on an object the engine does not model", member.owner.replace('/', "."), member.name)),
                }
            }
            Insn::InvokeDynamic(index) => {
                let (_, _, descriptor_text) = class.pool.invoke_dynamic(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let descriptor = MethodDescriptor::parse(descriptor_text).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let _ = self.pop_args(path, descriptor.params.len())?;
                match &descriptor.ret {
                    Type::Object(name) if name == "java/lang/String" => {
                        // An object argument is converted by its toString, which the engine does not run.
                        for class in gaps::converted_arguments(&descriptor) {
                            if let Some(end) = self.meet(path, GapKind::StringConversion, &class, "toString", "()Ljava/lang/String;") {
                                return Ok(Some(end));
                            }
                        }
                        let r = self.alloc(path, "java/lang/String");
                        self.push(path, Val::R(Some(r)));
                    }
                    _ => return unsupported("invokedynamic other than string concatenation"),
                }
            }
            Insn::New(index) => {
                let name = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                if let Some(end) = self.initialise(path, &name) {
                    return Ok(Some(end));
                }
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
            // In a run of one thread a monitor is always free and always held by it: only a null one does anything.
            Insn::MonitorEnter | Insn::MonitorExit => {
                let r = self.pop_ref(path)?;
                if let Err(step) = self.null_check(path, r) {
                    return step;
                }
            }
        }
        self.advance(path);
        Ok(None)
    }

    /// The path reaches a gap: it is recorded with where, and under strict the path ends there (`Some(End::Gap)`);
    /// under assume the caller goes on with the approximation (`None`).
    fn meet(&mut self, path: &Path, kind: GapKind, owner: &str, name: &str, descriptor: &str) -> Option<End> {
        let site = site(path.frames.last().expect("a frame"));
        self.met.entry(Gap { kind, owner: owner.to_string(), name: name.to_string(), descriptor: descriptor.to_string() }).or_default().insert(site);
        (self.gap_mode.refuses() || !kind.assumable()).then_some(End::Gap)
    }

    /// The path reaches a gap a contract closes: recorded with where, for the verdict to say what it rests on.
    fn apply(&mut self, path: &Path, gap: Gap) {
        let site = site(path.frames.last().expect("a frame"));
        self.applied.entry(gap).or_default().insert(site);
    }

    /// A call of [`crate::gap_contracts::INTRINSICS`] from a contract's method: what bytecode cannot say.
    fn intrinsic(&mut self, path: &mut Path, name: &str, args: Vec<Val>) -> Step {
        match (name, args.as_slice()) {
            // The input is outside the contract's `assume:`: the gap is open, and met at the call the contract is
            // for, in the frame below the contract's method.
            ("open", [Val::I(index)]) => {
                let index = self.b.constant_value(index).ok_or_else(|| Stop::Unsupported("a contract's number is not a constant".into()))? as usize;
                let gap = self.contracts.iter().find(|(_, c)| c.contract.index == index).map(|(g, _)| g.clone()).ok_or_else(|| Stop::Unsupported(format!("no contract {index}")))?;
                let caller = path.frames.len().checked_sub(2).map(|i| path.frames[i].clone()).ok_or_else(|| Stop::Unsupported("a contract's method called from nowhere".into()))?;
                let assumable = gap.kind.assumable();
                self.met.entry(gap).or_default().insert(site(&caller));
                if self.gap_mode.refuses() || !assumable {
                    return Ok(Some(End::Gap));
                }
            }
            // The array's elements become any values: what the call wrote, which the assertion that follows
            // narrows. Its length is the length it had.
            ("havoc", [Val::R(Some(o))]) => {
                let Some(array) = path.objects[*o].array.as_ref() else { return unsupported("a contract modifies an object that is not an array") };
                let width = cell_width(&array.element);
                let cells: Vec<Bits> = (0..array.cells.len()).map(|_| self.b.fresh(width)).collect();
                path.objects[*o].array.as_mut().expect("an array").cells = cells;
            }
            ("havoc", [Val::R(None)]) => return self.raise(path, "java/lang/NullPointerException"),
            // A primitive result: any value of the width, which the contract's method narrows to its type and its
            // assertion to what the contract states.
            ("anyInt", []) => {
                let v = self.b.fresh(32);
                self.push(path, Val::I(v));
            }
            ("anyLong", []) => {
                let v = self.b.fresh(64);
                self.push(path, Val::J(v));
            }
            // No run of the call takes the path: what it returned does not satisfy the contract's assertion.
            ("infeasible", []) => return Ok(Some(End::Infeasible)),
            // Whether two objects are of one class, as `a.getClass() == b.getClass()` is on the JVM: a proof of a
            // contract against the JDK's bytecode ([`crate::contract_proving`]) checks the exception's exact class.
            ("sameClass", [Val::R(Some(a)), Val::R(Some(b))]) => {
                let same = path.objects[*a].class == path.objects[*b].class;
                let v = self.b.constant(i64::from(same), 32);
                self.push(path, Val::I(v));
            }
            ("sameClass", [_, _]) => return self.raise(path, "java/lang/NullPointerException"),
            _ => return unsupported(format!("unknown intrinsic {name} of a contract")),
        }
        self.advance(path);
        Ok(None)
    }

    /// The path uses `class` in a way that initializes it (JVMS §5.5: `new`, `getstatic`, `invokestatic`): each
    /// application class whose `<clinit>` that would run, and the path has not reached before, is a
    /// `class-initializer` gap, since the engine runs no initializer. Under assume it is taken to have run already.
    fn initialise(&mut self, path: &mut Path, class: &str) -> Option<End> {
        if path.initialised.contains(class) || crate::classpath::is_jdk_name(class) {
            return None;
        }
        let classes = match self.initializers.get(class) {
            Some(c) => c.clone(),
            None => {
                let c = Rc::new(gaps::initializers(self.cp, class));
                self.initializers.insert(class.to_string(), c.clone());
                c
            }
        };
        let fresh: Vec<String> = classes.iter().filter(|c| !path.initialised.contains(*c)).cloned().collect();
        path.initialised.insert(class.to_string());
        path.initialised.extend(classes.iter().cloned());
        for c in &fresh {
            let gap = Gap { kind: GapKind::ClassInitializer, owner: c.clone(), name: "<clinit>".into(), descriptor: "()V".into() };
            if self.contracts.get(&gap).is_some_and(|k| k.how == Closing::Initialised) {
                self.apply(path, gap);
                continue;
            }
            if let Some(end) = self.meet(path, GapKind::ClassInitializer, c, "<clinit>", "()V") {
                return Some(end);
            }
        }
        None
    }

    /// The object a string or class literal is on this path: made at its first load.
    fn literal(&self, path: &mut Path, literal: Literal, class: &str) -> usize {
        if let Some(&o) = path.literals.get(&literal) {
            return o;
        }
        let o = self.alloc(path, class);
        path.literals.insert(literal, o);
        o
    }

    /// The key the instance field `owner.name:descriptor` has in object `o`: its name, unless a subclass along the
    /// object's class declares the name again ([`ClassPath::field_key`]), as the interpreter keys it.
    fn field_key(&mut self, path: &Path, o: usize, owner: &str, name: &str, descriptor: &str) -> Result<String, Stop> {
        let class = &path.objects[o].class;
        let hides = match self.hides.get(class) {
            Some(&h) => h,
            None => {
                let h = self.cp.hides_fields(class);
                self.hides.insert(class.clone(), h);
                h
            }
        };
        if !hides {
            return Ok(name.to_string());
        }
        let declaring = self.cp.resolve_field(owner, name, descriptor).ok_or_else(|| Stop::Unsupported(format!("no field {}.{name}", owner.replace('/', "."))))?;
        Ok(self.cp.field_key(class, &declaring, name))
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
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, false);
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
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, true);
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
            ArithOp::Mul => self.b.mul_lazy(&x, &y),
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
    /// of the integer wrappers. [`models_jdk_static`] lists the same arms, for the gap scan.
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

/// Whether [`Engine::call_jdk_static`] models `owner.name`: the arms of its match, for [`gaps::scan`], which counts
/// such a call as reproduced exactly rather than a gap.
pub fn models_jdk_static(owner: &str, name: &str) -> bool {
    matches!(
        (owner, name),
        ("java/lang/Math" | "java/lang/StrictMath", "addExact" | "subtractExact" | "multiplyExact" | "negateExact" | "incrementExact" | "decrementExact" | "toIntExact" | "absExact" | "abs" | "max" | "min" | "floorDiv" | "floorMod")
            | ("java/lang/Integer" | "java/lang/Long", "max" | "min" | "sum" | "compare" | "signum")
            | ("java/lang/Integer", "toUnsignedLong")
            | ("java/lang/Boolean", "logicalAnd" | "logicalOr" | "logicalXor")
    )
}

impl Blaster {
    fn signature(&self) -> String {
        "CaDiCaL".to_string()
    }

    /// A cell of an array of `element`s as the value a load pushes: extended to an int, without sign for a
    /// boolean or a char and with it for a byte or a short, or left a long.
    fn extend_cell(&self, element: &Type, cell: &Bits) -> Bits {
        match element {
            Type::Boolean | Type::Char => self.zext(cell, 32),
            Type::Byte | Type::Short => self.sext(cell, 32),
            _ => cell.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::flags;
    use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};

    /// The module's table says what the engine does with every instruction the decoder gives (each opcode decoded
    /// on its own, its operands zero), and the gap table of [`gaps`] has a row for every kind of gap: a new
    /// instruction or kind fails here until the tables say how it is treated.
    #[test]
    fn the_module_docs_say_what_the_engine_does_with_every_instruction() {
        let docs = |source: &str| source.lines().take_while(|l| l.starts_with("//!")).collect::<Vec<_>>().join("\n");
        let engine = docs(include_str!("mod.rs"));
        let table = engine.split("| Instructions | Treatment |").nth(1).expect("the table of instructions");
        let row = |insn: &Insn| -> &'static str {
            let float = |k: &Kind| matches!(k, Kind::Float | Kind::Double);
            match insn {
                Insn::Nop => "`nop`",
                Insn::AConstNull => "`aconst_null`",
                Insn::IConst(_) => "`iconst`",
                Insn::LConst(_) => "`lconst`",
                Insn::FConst(_) => "`fconst`",
                Insn::DConst(_) => "`dconst`",
                Insn::Ldc(_) => "`ldc` of an int or a long",
                Insn::Load(k, _) | Insn::Store(k, _) | Insn::Return(Some(k)) | Insn::Arith(_, k) if float(k) => "floating point",
                Insn::Convert(k, n) if float(k) || matches!(n, Narrow::To(t) if float(t)) => "floating point",
                Insn::Load(..) => "`iload`",
                Insn::Store(..) => "`istore`",
                Insn::ArrayLoad(ArrayKind::Ref) | Insn::ArrayStore(ArrayKind::Ref) => "`aaload`/`aastore`",
                Insn::ArrayLoad(ArrayKind::Float | ArrayKind::Double) | Insn::ArrayStore(ArrayKind::Float | ArrayKind::Double) => "floating point",
                Insn::ArrayLoad(_) => "`iaload` … `saload`",
                Insn::ArrayStore(_) => "`iastore` … `sastore`",
                Insn::Pop => "`pop`",
                Insn::Pop2 => "`pop2`",
                Insn::Dup => "`dup`",
                Insn::DupX1 => "`dup_x1`",
                Insn::DupX2 => "`dup_x2`",
                Insn::Dup2 => "`dup2`",
                Insn::Dup2X1 => "`dup2_x1`",
                Insn::Dup2X2 => "`dup2_x2`",
                Insn::Swap => "`swap`",
                Insn::Arith(..) => "`iadd` … `lxor`",
                Insn::IInc(..) => "`iinc`",
                Insn::Convert(..) => "`i2l`",
                Insn::Cmp(c) if c.kind == Kind::Long => "`lcmp`",
                Insn::Cmp(_) => "`fcmpl`",
                Insn::If(..) => "`ifeq`",
                Insn::IfICmp(..) => "`if_icmpeq`",
                Insn::IfACmp(..) => "`if_acmpeq`/`if_acmpne`",
                Insn::IfNull(_) => "`ifnull`",
                Insn::IfNonNull(_) => "`ifnonnull`",
                Insn::Goto(_) => "`goto`",
                Insn::Jsr(_) | Insn::Ret(_) => "`jsr`/`ret`",
                Insn::TableSwitch { .. } => "`tableswitch`",
                Insn::LookupSwitch { .. } => "`lookupswitch`",
                Insn::Return(_) => "`ireturn` … `return`",
                Insn::GetStatic(_) => "`getstatic` of a compile-time constant",
                Insn::PutStatic(_) => "`putstatic`",
                Insn::GetField(_) => "`getfield`",
                Insn::PutField(_) => "`putfield`",
                Insn::InvokeVirtual(_) => "`invokevirtual`",
                Insn::InvokeSpecial(_) => "`invokespecial`",
                Insn::InvokeStatic(_) => "`invokestatic`",
                Insn::InvokeInterface(_) => "`invokeinterface`",
                Insn::InvokeDynamic(_) => "`invokedynamic` string concatenation",
                Insn::New(_) => "`new`",
                Insn::NewArray(_) => "`newarray`",
                Insn::ANewArray(_) => "`anewarray`",
                Insn::ArrayLength => "`arraylength`",
                Insn::AThrow => "`athrow`",
                Insn::CheckCast(_) => "`checkcast`",
                Insn::InstanceOf(_) => "`instanceof`",
                Insn::MonitorEnter => "`monitorenter`",
                Insn::MonitorExit => "`monitorexit`",
                Insn::MultiANewArray(..) => "`multianewarray`",
            }
        };
        let mut decoded = 0;
        for op in 0u8..=255 {
            let mut bytes = vec![op];
            bytes.resize(32, 0);
            let Ok(insns) = crate::classfile::bytecode::decode(&bytes) else { continue };
            let insn = &insns[0].1;
            decoded += 1;
            assert!(table.contains(row(insn)), "opcode {op:#04x} ({insn:?}): the module's table has no row with {}", row(insn));
        }
        assert!(decoded >= 200, "every opcode of the JVM decodes, {decoded} did");
        for row in ["implemented", "modelled", "gap", "refused"] {
            assert!(table.contains(&format!("| {row}")), "a row of what is {row}");
        }
        let kinds = docs(include_str!("gaps.rs"));
        for kind in GapKind::ALL {
            assert!(kinds.contains(&format!("| `{}` |", kind.name())), "the gap table has a row for {}", kind.name());
            assert!(table.contains(&format!("`{}`", kind.name())), "the instruction table says where a {} gap is met", kind.name());
        }
    }

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
        assert_eq!((out.paths, out.merges, out.solves), (4, 0, 3));

        // Merged from the start, the two paths through the first branch are one again at the join after it, so
        // the second is explored once, on the merged path, and its two paths are one at the end: three paths, two
        // merges and two solver calls.
        let out = check(&cp, "Check", "check", &Options { merge_after: 0, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.merges, out.solves), (3, 2, 2));
    }

    #[test]
    fn paths_are_merged_at_a_join_and_a_violation_through_one_is_found_with_its_input() {
        // `x = a < b ? a : b; if (x != a) fail`: the two assignments meet at the comparison, which runs once on the
        // merged path; the violation on it needs the else side of the first branch, and the solver names an input
        // that takes it. The merged path goes to the failure itself, so its twin (the return) is never run.
        let cp = harness("(II)V", |code, _, fail| {
            let else_ = code.label();
            let join = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, else_);
            code.load(Kind::Int, 0);
            code.store(Kind::Int, 2);
            code.goto(join);
            code.bind(else_);
            code.load(Kind::Int, 1);
            code.store(Kind::Int, 2);
            code.bind(join);
            code.load(Kind::Int, 2);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Ne, fail);
        });
        let merged = Options { merge_after: 0, ..Options::default() };
        let out = check(&cp, "Check", "check", &merged).unwrap();
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!((out.paths, out.merges), (2, 1), "{}", out.summary());
        let (a, b): (i64, i64) = (out.raw_inputs[&0].parse().unwrap(), out.raw_inputs[&1].parse().unwrap());
        assert!(a > b, "{a} {b}");
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));

        // Eight independent branches in a row (`if ((a >>> i & 1) != 0) b += 1` for each bit i): nine paths
        // merged, not 256, and the claim after them still holds.
        let cp = harness("(II)V", |code, _, fail| {
            for i in 0..8u8 {
                let join = code.label();
                code.load(Kind::Int, 0);
                code.iconst(i as i32);
                code.op(0x7c);
                code.iconst(1);
                code.op(0x7e);
                code.if_zero(Cond::Eq, join);
                code.load(Kind::Int, 1);
                code.iconst(1);
                code.op(0x60);
                code.store(Kind::Int, 1);
                code.bind(join);
            }
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Ne, fail);
        });
        let out = check(&cp, "Check", "check", &merged).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.merges), (9, 8), "{}", out.summary());
        // Unmerged until the budget: every path on its own.
        let out = check(&cp, "Check", "check", &Options { merge_after: 1000, ..Options::default() }).unwrap();
        assert_eq!((out.verdict, out.paths, out.merges), (Verdict::Verified, 256, 0), "{}", out.summary());
        // With the budget inside the search, the paths explored after it are merged: fewer than 256, more than 9.
        let out = check(&cp, "Check", "check", &Options { merge_after: 16, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert!(out.paths > 9 && out.paths < 256 && out.merges > 0, "{}", out.summary());
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
        assert!(out.summary().contains(&format!("{} of 1 divisions and 0 of 0 multiplications built in full", out.refined)));
    }

    #[test]
    fn a_multiplication_is_built_in_full_only_when_the_solver_gets_it_wrong() {
        // x * y == x << 3 for y == 8: what holds of every product proves it, with no multiplier.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.iconst(8);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x68); // imul
            code.load(Kind::Int, 0);
            code.iconst(3);
            code.op(0x78); // ishl
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.multiplications, out.refined_multiplications), (1, 0), "{}", out.summary());

        // (x / y) * y == x - x % y: the identity, the same bits on both sides, no product and no circuit.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.load(Kind::Int, 1);
            code.op(0x68); // imul
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x70); // irem
            code.op(0x64); // isub
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.divisions, out.refined, out.multiplications), (1, 0, 0), "{}", out.summary());

        // x * y == 150000 claimed impossible: refuted with factors whose real product is that, the circuit built
        // if the solver's first guess was not a real product.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x68); // imul
            code.iconst(30_000);
            code.iconst(5);
            code.op(0x68); // imul of constants, folded: 150000
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let (x, y): (i32, i32) = (out.raw_inputs[&0].parse().unwrap(), out.raw_inputs[&1].parse().unwrap());
        assert_eq!(x.wrapping_mul(y), 150_000, "{x} * {y}");
        assert!(out.refined_multiplications <= 1, "{}", out.summary());
    }

    #[test]
    fn an_array_parameter_has_every_length_up_to_the_bound_and_its_elements_are_inputs() {
        // a.length <= 8 (the default bound) holds; a.length < 8 does not, and the array named is 8 long.
        let cp = harness("([I)V", |code, _, fail| {
            code.load(Kind::Ref, 0);
            code.op(0xbe); // arraylength
            code.iconst(8);
            code.if_icmp(Cond::Gt, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        let cp = harness("([I)V", |code, _, fail| {
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.iconst(8);
            code.if_icmp(Cond::Ge, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.raw_arrays[&0].as_ref().unwrap().len(), 8);

        // a.length == 2 && a[0] + a[1] == 10 is claimed impossible: refuted, with the two elements named, from
        // the first stage.
        let cp = harness("([I)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.iconst(2);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.op(0x2e); // iaload
            code.load(Kind::Ref, 0);
            code.iconst(1);
            code.op(0x2e);
            code.op(0x60); // iadd
            code.iconst(10);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let a: Vec<i32> = out.raw_arrays[&0].as_ref().unwrap().iter().map(|v| v.parse().unwrap()).collect();
        assert_eq!(a.len(), 2, "{a:?}");
        assert_eq!(a[0] + a[1], 10, "{a:?}");
        assert!(a.iter().all(|v| (0..=20).contains(v)), "{a:?}");
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));
        assert!(out.raw_inputs.is_empty());
    }

    #[test]
    fn an_index_out_of_bounds_is_an_exception_path_and_a_store_is_read_back() {
        // a[i] throws ArrayIndexOutOfBoundsException exactly when i < 0 || i >= a.length.
        let cp = harness("([II)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let out_of_bounds = code.label();
            code.bind(try_start);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 1);
            code.op(0x2e); // iaload
            code.op(0x57); // pop
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Lt, fail); // read although i < 0: impossible
            code.load(Kind::Int, 1);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, fail); // read although i >= a.length: impossible
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57);
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Lt, out_of_bounds);
            code.load(Kind::Int, 1);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, out_of_bounds);
            code.goto(fail); // thrown although 0 <= i < a.length: impossible
            code.bind(out_of_bounds);
            code.bind(ok);
            let exception = writer.pool.class("java/lang/ArrayIndexOutOfBoundsException");
            code.handler(try_start, try_end, handler, Some(exception));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // With 0 <= i, j < a.length and i != j: after a[i] = v, a[i] == v and a[j] is what it was.
        let cp = harness("([IIII)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 2);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 1);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, ok);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, ok);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 2);
            code.if_icmp(Cond::Eq, ok);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.store(Kind::Int, 4); // b = a[j]
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 3);
            code.op(0x4f); // a[i] = v
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 1);
            code.op(0x2e);
            code.load(Kind::Int, 3);
            code.if_icmp(Cond::Ne, fail); // a[i] != v: impossible
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.load(Kind::Int, 4);
            code.if_icmp(Cond::Ne, fail); // a[j] != b: impossible
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
    }

    #[test]
    fn a_new_array_is_within_the_bound_or_beyond_the_engine_and_cells_are_as_wide_as_their_elements() {
        // A copy as long as the parameter, filled by the harness's loop, reads back the same: the size is the
        // parameter's length, which the first path's condition bounds.
        let cp = harness("([I)V", |code, _, fail| {
            let loop_ = code.label();
            let done = code.label();
            let check = code.label();
            let checked = code.label();
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.op_u8(0xbc, 10); // newarray int
            code.store(Kind::Ref, 1);
            code.iconst(0);
            code.store(Kind::Int, 2);
            code.bind(loop_);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, done);
            code.load(Kind::Ref, 1);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.op(0x4f);
            code.iinc(2, 1);
            code.goto(loop_);
            code.bind(done);
            code.iconst(0);
            code.store(Kind::Int, 2);
            code.bind(check);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, checked);
            code.load(Kind::Ref, 1);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.if_icmp(Cond::Ne, fail);
            code.iinc(2, 1);
            code.goto(check);
            code.bind(checked);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?} {:?} {}", out.problem, out.raw_arrays, out.paths);

        // An array of a size the engine cannot bound is beyond it.
        let cp = harness("(I)V", |code, _, _| {
            code.load(Kind::Int, 0);
            code.op_u8(0xbc, 10);
            code.op(0x57);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.as_deref().unwrap_or("").contains("computed size"), "{:?}", out.problem);

        // A byte array's cell keeps eight bits: 200 stored reads back as -56; a char's sixteen, without sign.
        let cp = harness("([B[C)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Ref, 1);
            code.op(0xbe);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.iconst(20);
            code.iconst(10);
            code.op(0x68); // imul: 200 folded, since iconst takes a byte
            code.op(0x54); // bastore
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.op(0x33); // baload
            code.iconst(-56);
            code.if_icmp(Cond::Ne, fail);
            code.load(Kind::Ref, 1);
            code.iconst(0);
            code.op(0x34); // caload
            code.if_zero(Cond::Lt, fail);
            code.load(Kind::Ref, 1);
            code.iconst(0);
            code.iconst(-1);
            code.op(0x55); // castore
            code.load(Kind::Ref, 1);
            code.iconst(0);
            code.op(0x34);
            code.iconst(16);
            code.iconst(16);
            code.op(0x68);
            code.op(0x59); // dup
            code.op(0x68); // imul: 65536 folded
            code.iconst(1);
            code.op(0x64); // isub
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
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
