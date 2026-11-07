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
//! call. A reference they differ in becomes a symbolic one, one of their objects or null under the condition of
//! each ([`Choice`]); a reference every path agrees on stays a known object, the fast path. A small search stays unmerged, each solver call being about one concrete path, which is cheaper.
//!
//! The fragment this engine handles is the one the proofs are mostly about: static methods over `int`, `long`,
//! `short`, `byte`, `char` and `boolean`, straight-line and branching arithmetic, calls into the application's own
//! static methods (inlined), the `Math`/`StrictMath` exact and floor operations with their overflow exceptions,
//! `Integer`/`Long` comparisons, exceptions thrown and caught by class, and strings only as opaque objects (a
//! message built for an exception). An array of those primitives is an object with a symbolic length and a cell
//! per index it may have ([`Array`]): an array parameter has every length up to [`Options::max_array_length`],
//! as JBMC's nondeterministic arrays do (and is never null nor another parameter's array, unless
//! [`Options::parameters`] lets it be, a symbolic reference then), a read is a choice among the cells by the index and a write a
//! conditional update of each, and an index out of bounds or a negative size is a branch to the exception, as a
//! division by zero is. An array of references holds an object or null per cell, and an index into one that is not
//! a constant splits the path per cell. An application class's static fields are path state, and its initializer
//! runs where the JVM runs it (JVMS §5.5); an enum's is one, its constants made through `java.lang.Enum`'s model
//! and its `$VALUES` an array of references. Floating point, the JDK's static state and the rest of the
//! JDK are refused with a reason, so that a caller can fall back to JBMC. A verdict it gives is on the same statement JBMC would
//! check, the generated harness class, so a counterexample is replayed and shrunk like JBMC's.
//!
//! Every instruction, and every call it can make, is implemented as the JVM does it, modelled (by a model whose
//! contract is written down), a named gap ([`gaps`]), or refused:
//!
//! | Instructions | Treatment |
//! |---|---|
//! | `nop`, `aconst_null`, `iconst`, `lconst`, `bipush`/`sipush`, `ldc` of an int or a long, `iload`/`lload`/`aload`, `istore`/`lstore`/`astore`, `pop`, `pop2`, `dup`, `dup_x1`, `dup_x2`, `dup2`, `dup2_x1`, `dup2_x2`, `swap`, `iinc` | implemented |
//! | `iadd` … `lxor` (arithmetic, shifts, bitwise), `i2l`, `l2i`, `i2b`, `i2c`, `i2s`, `lcmp` | implemented bit for bit; `idiv`, `irem`, `ldiv`, `lrem` throw `ArithmeticException` on zero |
//! | `ifeq` …, `if_icmpeq` …, `if_acmpeq`/`if_acmpne`, `ifnull`, `ifnonnull`, `goto`, `tableswitch`, `lookupswitch`, `ireturn` … `return` | implemented; a loop's back edge counts against the unwinding bound; `if_acmp`, `ifnull` and `ifnonnull` on a symbolic reference are formulas over its guards |
//! | `newarray`, `arraylength`, `iaload` … `saload`, `iastore` … `sastore` on arrays of primitives | implemented, up to [`Options::max_array_length`] cells; `ArrayIndexOutOfBoundsException`, `NegativeArraySizeException`, and `NullPointerException` on null |
//! | `anewarray`, `aaload`/`aastore` on arrays of references, and an array's `clone()` | implemented as for primitives, a cell holding an object or null; an index that is not a constant splits the path per cell ([`Engine::concrete_index`]); `clone()` a new array of the same class and elements; an `aastore` of an object not of the element type (`ArrayStoreException`) is refused |
//! | `new`, `getfield`, `putfield`, `invokestatic`, `invokespecial`, `invokevirtual`, `invokeinterface` of the application's own methods | implemented: objects with fields, calls inlined, a virtual call dispatched on its receiver's class, `NullPointerException` on a null receiver; a field resolved as the JVM resolves it (JVMS §5.4.3.2), so a field a subclass declares again is a second one. Through a symbolic reference, `getfield` chooses among its objects' fields by the guards and `putfield` writes each under its guard, `NullPointerException` where it is null; a call on one, or any other instruction that needs its object (`checkcast`, `athrow`, a monitor, an array instruction, a JDK call's argument), splits the path per object first ([`Engine::concrete_ref`]) |
//! | `athrow`, exception handlers, `checkcast`, `instanceof` | implemented, a handler matched by subclass; `instanceof` on a symbolic reference a formula over its guards |
//! | `monitorenter`, `monitorexit` | implemented: `NullPointerException` on null, and otherwise nothing, which is all a monitor does in a run of one thread |
//! | `getstatic`, `putstatic` of an application class's field; `getstatic` of a JDK compile-time constant (`Integer`/`Long` `MAX_VALUE`/`MIN_VALUE`, or a field with a `ConstantValue`) | implemented: a field is resolved as the JVM resolves it, and holds what the path wrote, else its `ConstantValue`, else zero or null |
//! | class initialization (JVMS §5.5), at the first `new`, `getstatic`, `putstatic` or `invokestatic` of an application class | implemented ([`Engine::initialise`]): the class's superclass, then the superinterfaces that declare a default method ([`gaps::initialization_supers`]), then its `<clinit>`, run as bytecode; a use from inside its own initialization goes on; an exception that leaves a `<clinit>` is thrown as an `ExceptionInInitializerError` (an `Error` as it is), and a later use of the class, or of one that waited on it, throws `NoClassDefFoundError`. A JDK class is taken to be initialized already |
//! | a `<clinit>` outside the fragment ([`gaps::runs_initializer`]: one that reaches what the engine refuses, or reads or writes a static of a class whose `<clinit>` is outside; a gap inside one it runs is met there) | gap: `class-initializer`, met where the JVM would run it; under assume, or closed by a contract that it throws nothing, taken to have run, its static fields then known only as constants |
//! | `invokestatic` of `Math`/`StrictMath`/`Integer`/`Long`/`Boolean` operations ([`models_jdk_static`]) | modelled in [`Engine::call_jdk_static`], each as its Javadoc specifies, exceptions included |
//! | `invokestatic` of any other JDK method over integers, booleans, arrays and objects ([`gaps::jdk_static_call`]) | gap: `jdk-static-method`, with no assume form |
//! | `invokestatic` of a class the tool's models (`lib/models`) provide | modelled: the model's bytecode runs, as in the interpreter |
//! | `invokespecial`/`invokevirtual` of `java.lang.Enum`'s constructor, `name()`, `ordinal()`, `toString()` and `equals` ([`ClassPath::checker_runs`]) | modelled: the model's bytecode (`lib/models/java/lang/Enum.java`, which JBMC runs too) sets and reads the enum's `name` and `ordinal` fields; the interpreter's natives do the same. `Enum`'s other methods (`compareTo`, `hashCode`, `valueOf` …) stay JDK gaps |
//! | `invokespecial` of `Object.<init>()`, `Record.<init>()`, and a JDK exception's `()`, `(String)` or `(String, Throwable)` constructor ([`gaps::exact_jdk_call`]) | modelled exactly: they change nothing a proof observes |
//! | `invokespecial` of any other JDK constructor, `invokevirtual`/`invokeinterface` of a JDK method returning `void` or an object | gap: `jdk-constructor`, `jdk-void-method`, `jdk-reference-method` |
//! | `invokevirtual`/`invokeinterface` of a JDK method returning an integer, a `char` or a `boolean` | gap: `jdk-primitive-method`, with no assume form |
//! | `invokedynamic` string concatenation | implemented over strings and primitives (the result an opaque string); an object argument it would convert is a gap, `string-conversion` |
//! | `ldc` of a string or a class | implemented: one opaque object per distinct literal on a path, as the JVM interns strings and has one `Class` object per class |
//! | floating point (`fconst`, `dconst`, `fadd` …, `fcmpl` …, `f2i` …), `jsr`/`ret`, `putstatic` of a JDK field, any other `getstatic` of one, a static field of a class taken to be initialized other than a constant, `multianewarray`, any other `invokedynamic`, a JDK method with a floating-point parameter or result or an array result, a native method | refused: no verdict, so that `--engine auto` can ask JBMC |
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

pub mod bitwuzla;
pub mod bits;
pub mod gaps;
pub mod sat;
pub mod transcript;

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
    /// The file to write the run's solver calls to ([`transcript`]); when `None`, the directory the environment
    /// variable [`transcript::ENV`] names, if it is set.
    pub transcript: Option<std::path::PathBuf>,
    /// Makes the SAT solver the check is run on, empty ([`sat`]): by default the one the environment variable
    /// [`sat::ENV`] chooses, CaDiCaL unless it names another, and otherwise what a test puts behind the same
    /// interface. Results name the solver by [`solver_signature`], the default's.
    pub solver: fn() -> Box<dyn sat::Sat>,
    /// Which array parameters may be null and which may be one array ([`Parameters`]); by default each is an
    /// array of its own, never null.
    pub parameters: Parameters,
}

impl Default for Options {
    fn default() -> Self {
        Options { unwind: 16, timeout: Duration::from_secs(600), max_paths: 200_000, max_array_length: 8, merge_after: 512, gaps: GapMode::Strict, contracts: Default::default(), transcript: None, solver: sat::configured, parameters: Parameters::default() }
    }
}

/// The harness's array parameters beyond the default domain, by local-variable slot. Each array parameter has an
/// array of its own, of a fresh length up to the bound with fresh cells; a parameter that may be null, or may be
/// one array with another, is a symbolic reference ([`Choice`]) among null and the arrays it may be: its own, and
/// the own array of each parameter before it in its group. Any partition of a group into arrays is so reachable,
/// each array named by the first parameter holding it, and a witness says which parameters hold one array
/// ([`Outcome::raw_same`]).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Parameters {
    pub nullable: Vec<u32>,
    /// Groups of parameters any two of which may be one array, each group in slot order.
    pub may_alias: Vec<Vec<u32>>,
}

impl Parameters {
    pub fn is_default(&self) -> bool {
        self.nullable.is_empty() && self.may_alias.is_empty()
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
    /// The violating input's array parameters by slot, their elements as `raw_inputs` spells values, or `None`
    /// for a null one ([`Parameters::nullable`]).
    pub raw_arrays: BTreeMap<u32, Option<Vec<String>>>,
    /// The violating input's array parameters that are the same array as an earlier one, by slot: the slot of the
    /// first parameter holding it ([`Parameters::may_alias`]).
    pub raw_same: BTreeMap<u32, u32>,
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
    /// How many word-level operations the solver was given as terms, when it takes terms ([`sat::Terms`]); zero
    /// when it is given clauses.
    pub word_operations: u64,
    pub seconds: f64,
    /// The phases the solving and evaluating above are not: reading and parsing class files, decoding methods,
    /// building circuits (the encoding, as the paths are explored), and reading a witness out of a model; the
    /// rest of `seconds` is the symbolic execution ([`Outcome::profile`]).
    pub loading: f64,
    pub decoding: f64,
    pub encoding: f64,
    pub witness: f64,
    /// The solver, for the report.
    pub solver: String,
    /// The gaps the run met, each refused (strict: a path ended there) or assumed, with where.
    pub gaps: Vec<GapRecord>,
    pub gap_mode: GapMode,
    /// Where the run's solver calls were written, when they were ([`Options::transcript`]).
    pub transcript: Option<std::path::PathBuf>,
}

impl Outcome {
    /// The outcome in the shape of a JBMC result, so that the proof drivers treat it as one.
    pub fn into_jbmc_result(self, log: std::path::PathBuf) -> crate::jbmc::JbmcResult {
        let stats = self.stats();
        let profile = self.profile();
        let ending = crate::jbmc::Ending::of_native(self.verdict, self.problem.as_deref());
        crate::jbmc::JbmcResult {
            verdict: self.verdict,
            version: format!("jvmcontract's own checker ({})", self.solver),
            properties: 1,
            raw_inputs: self.raw_inputs,
            raw_arrays: self.raw_arrays,
            raw_same: self.raw_same,
            stage: self.stage,
            problem: self.problem,
            log,
            seconds: self.seconds,
            native: Some(stats),
            gaps: self.gaps,
            gap_mode: Some(self.gap_mode),
            ending,
            profile,
        }
    }

    /// The run's phases as [`crate::phases`] names them for both checkers: the symbolic execution is what the
    /// other phases leave of the run, gates evaluated in path models included, and nothing is `other`.
    pub fn profile(&self) -> crate::phases::Profile {
        let symbolic = (self.seconds - self.loading - self.decoding - self.encoding - self.solving - self.witness).max(0.0);
        let phases = crate::phases::Phases { loading: self.loading, lowering: self.decoding, symbolic, encoding: self.encoding, solving: self.solving, trace: self.witness, other: 0.0 }.completed(self.seconds);
        crate::phases::Profile { phases: Some(phases), formula: crate::phases::Formula { steps: None, conditions: None, variables: Some(self.variables.max(0) as u64), clauses: Some(self.clauses) } }
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
            word_operations: self.word_operations,
            variables: self.variables,
            clauses: self.clauses,
            seconds: self.seconds,
            loading_seconds: self.loading,
            decoding_seconds: self.decoding,
            encoding_seconds: self.encoding,
            witness_seconds: self.witness,
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
        format!("{:?}: {} paths, {} merged at joins, {} solver calls ({:.2} s), {} gates evaluated in path models ({:.2} s), {} of {} divisions and {} of {} multiplications built in full, {}{} variables, {} clauses, {:.2} s{gaps}{}", self.verdict, self.paths, self.merges, self.solves, self.solving, self.evaluated, self.evaluating, self.refined, self.divisions, self.refined_multiplications, self.multiplications, if self.word_operations > 0 { format!("{} word-level operations given as terms, ", self.word_operations) } else { String::new() }, self.variables, self.clauses, self.seconds, self.problem.as_deref().map(|p| format!("; {p}")).unwrap_or_default())
            + &self.transcript.as_ref().map(|t| format!("; solver calls written to {}", t.display())).unwrap_or_default()
    }
}

/// What the engine's search took, as [`Outcome::summary`] prints it: the paths it explored and merged, the solver's
/// calls and time, the gates evaluated in path models instead, the divisions and multiplications left to the solver
/// and those whose circuit had to be built, and the size of the last formula.
fn is_zero(n: &u64) -> bool {
    *n == 0
}

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
    /// Absent for a solver given clauses.
    #[serde(skip_serializing_if = "is_zero")]
    pub word_operations: u64,
    pub variables: i32,
    pub clauses: u64,
    pub seconds: f64,
    /// Reading and parsing class files, decoding methods, building circuits, and reading a witness out of a
    /// model: with the solving and evaluating above, the phases of [`crate::phases`].
    pub loading_seconds: f64,
    pub decoding_seconds: f64,
    pub encoding_seconds: f64,
    pub witness_seconds: f64,
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
/// long, a reference to an object of the path's (one this run made, an exception, a string) or `null`, or a
/// symbolic reference ([`Choice`]).
///
/// A reference whose target is known is `R`, the fast path every reference took before symbolic ones: nothing
/// about it is a formula. A `C` is made only where paths that differ in a reference merge ([`Engine::absorb`]),
/// or where a read through a `C` gives references ([`Engine::get_field`]).
#[derive(Debug, Clone)]
enum Val {
    I(Bits),
    J(Bits),
    R(Option<usize>),
    C(Rc<Choice>),
}

impl Val {
    fn category(&self) -> usize {
        match self {
            Val::J(_) => 2,
            _ => 1,
        }
    }

    /// The reference as a choice: a known one is the only option, under `TRUE`. `None` for a primitive.
    fn options(&self) -> Option<Vec<(Lit, Option<usize>)>> {
        match self {
            Val::R(r) => Some(vec![(TRUE, *r)]),
            Val::C(c) => Some(c.0.clone()),
            _ => None,
        }
    }
}

/// A symbolic reference: one of a finite set of the path's objects, or null, each under a guard. The guards are
/// pairwise exclusive, and under the path's condition one of them holds, so the reference is the target of the
/// guard that holds. Options are sorted by target, each target once, at least two of them ([`choice`]), so that two
/// choices of the same guards and targets are equal.
///
/// `if_acmp`, `ifnull`, `ifnonnull` and `instanceof` on one are formulas over the guards, `getfield` reads each
/// candidate's field and chooses among the values by the guards, and `putfield` writes each candidate's field
/// under its guard ([`Engine::put_field`]). Every other instruction that needs to know the object (a call on it,
/// an array instruction, `checkcast`, `athrow`, a monitor) splits the path per option first
/// ([`Engine::concrete_ref`]), the reference then known on each.
#[derive(Debug, Clone, PartialEq, Eq)]
struct Choice(Vec<(Lit, Option<usize>)>);

/// The reference that is each target under its guard: options under `FALSE` dropped, the guards of one target
/// joined, sorted by target; a known reference when one target is left.
fn choice(b: &mut Blaster, options: Vec<(Lit, Option<usize>)>) -> Val {
    let mut by_target: BTreeMap<Option<usize>, Lit> = BTreeMap::new();
    for (g, t) in options {
        if g == FALSE {
            continue;
        }
        let joined = match by_target.get(&t) {
            Some(&h) => b.or(h, g),
            None => g,
        };
        by_target.insert(t, joined);
    }
    if let Some((&t, _)) = by_target.iter().find(|(_, &g)| g == TRUE) {
        return Val::R(t);
    }
    if by_target.len() <= 1 {
        return Val::R(by_target.into_keys().next().flatten());
    }
    Val::C(Rc::new(Choice(by_target.into_iter().map(|(t, g)| (g, t)).collect())))
}

/// An object made during the run: its class, and the fields written so far (an application exception's, say), or
/// the array it is.
#[derive(Debug, Clone)]
struct Obj {
    class: String,
    fields: BTreeMap<String, Val>,
    array: Option<Array>,
}

/// An array: its length, and a cell for every index it may have (as many as its length can be). An array of
/// primitives has `cells`, each as wide as [`cell_width`] says: a read at a symbolic index is a choice among them,
/// and a write updates each under the condition that the index is its own. An array of references has `refs`,
/// the object in each cell or null, and no `cells`: a reference is not a choice among bits, so an index into one
/// is made a constant first, the path split per cell ([`Engine::concrete_index`]). An index at or beyond the
/// length is out of bounds whatever its cell holds.
#[derive(Debug, Clone)]
struct Array {
    element: Type,
    length: Bits,
    cells: Vec<Bits>,
    refs: Vec<Option<usize>>,
}

/// Whether an array of `element`s holds references.
fn holds_references(element: &Type) -> bool {
    matches!(element, Type::Object(_) | Type::Array(_))
}

/// The class an object of type `t` has, as [`ClassPath::is_subtype`] names classes: an internal name, or an
/// array's descriptor (`[I`, `[Lcom/example/Color;`).
fn class_of(t: &Type) -> String {
    match t {
        Type::Object(name) => name.clone(),
        other => other.descriptor(),
    }
}

/// A violating input: the scalar parameters' values and the array parameters' elements, by slot.
#[derive(Debug, Clone, Default)]
struct Input {
    scalars: BTreeMap<u32, String>,
    arrays: BTreeMap<u32, Option<Vec<String>>>,
    same: BTreeMap<u32, u32>,
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
    /// The class whose `<clinit>` the frame runs: when it returns the class is initialized, and when an exception
    /// leaves it the class is erroneous (JVMS §5.5, steps 10 and 11).
    initializes: Option<String>,
    /// The classes the instruction being executed began to initialize and that wait for their superclasses' and
    /// superinterfaces' initializers to finish (JVMS §5.5, step 7), outermost first: the instruction runs again
    /// each time one of those returns, and an exception that leaves it makes them erroneous.
    entered: Vec<String>,
}

impl Frame {
    fn new(class: Rc<ClassFile>, method: String, code: Rc<Decoded>, locals: Vec<Option<Val>>) -> Frame {
        Frame { class, method, code, at: 0, locals, stack: Vec::new(), initializes: None, entered: Vec::new() }
    }

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
    /// The state of initialization of each application class the path has used (JVMS §5.5); a class absent is not
    /// initialized yet.
    classes: BTreeMap<String, ClassState>,
    /// The static fields of application classes the path has written, by declaring class and name; one it has not
    /// is its `ConstantValue`, or zero or null.
    statics: BTreeMap<(String, String), Val>,
}

/// Where a class is in its initialization (JVMS §5.5).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ClassState {
    /// Begun and not finished: a use of the class from its own initialization goes on as if it were initialized.
    InProgress,
    /// Its `<clinit>` ran and returned, or it has none.
    Done,
    /// Taken to be initialized, its `<clinit>` not run: a `class-initializer` gap assumed, or closed by a contract.
    /// Only its constants are known.
    Assumed,
    /// Its initialization threw: a later use throws `NoClassDefFoundError`.
    Erroneous,
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

/// The value that is `x` where `g` holds and `y` where it doesn't: bits chosen bit by bit, references a
/// [`Choice`] of both's options. `None` when the two are not of one kind ([`mergeable`]).
fn choose(b: &mut Blaster, g: Lit, x: &Val, y: &Val) -> Option<Val> {
    match (x, y) {
        (Val::I(p), Val::I(q)) => Some(Val::I(if p == q { p.clone() } else { b.ite_bits(g, p, q) })),
        (Val::J(p), Val::J(q)) => Some(Val::J(if p == q { p.clone() } else { b.ite_bits(g, p, q) })),
        (Val::R(p), Val::R(q)) if p == q => Some(x.clone()),
        (Val::C(p), Val::C(q)) if p == q => Some(x.clone()),
        _ => {
            let (xs, ys) = (x.options()?, y.options()?);
            let mut options = Vec::with_capacity(xs.len() + ys.len());
            for (h, t) in xs {
                options.push((b.and(g, h), t));
            }
            for (h, t) in ys {
                options.push((b.and(-g, h), t));
            }
            Some(choice(b, options))
        }
    }
}

/// Makes every copy of `choice` in the path's state (locals, stacks, static fields, objects' fields) the known
/// reference `target`, once the path has taken the option of `target`.
fn substitute(path: &mut Path, choice: &Rc<Choice>, target: Option<usize>) {
    let fix = |v: &mut Val| {
        if matches!(v, Val::C(c) if Rc::ptr_eq(c, choice) || **c == **choice) {
            *v = Val::R(target);
        }
    };
    for frame in &mut path.frames {
        frame.locals.iter_mut().flatten().for_each(fix);
        frame.stack.iter_mut().for_each(fix);
    }
    path.statics.values_mut().for_each(fix);
    for o in &mut path.objects {
        o.fields.values_mut().for_each(fix);
    }
}

/// Whether two values can be one value under a condition: both ints, both longs, or both references, which
/// are a [`Choice`] by the condition where they differ.
fn mergeable(a: &Val, b: &Val) -> bool {
    matches!((a, b), (Val::I(_), Val::I(_)) | (Val::J(_), Val::J(_)) | (Val::R(_) | Val::C(_), Val::R(_) | Val::C(_)))
}

/// Whether two paths at the same join point have states of one shape, so that they can be merged: the same
/// slots and objects, each object of the same class with the same fields (the paths differ only in bits and in
/// which objects references denote). The cells of arrays of references must be the same objects.
fn same_shape(a: &Path, b: &Path) -> bool {
    let slots = |x: &Option<Val>, y: &Option<Val>| match (x, y) {
        (None, None) => true,
        (Some(x), Some(y)) => mergeable(x, y),
        _ => false,
    };
    a.frames.len() == b.frames.len()
        && a.frames.iter().zip(&b.frames).all(|(f, g)| f.locals.len() == g.locals.len() && f.locals.iter().zip(&g.locals).all(|(x, y)| slots(x, y)) && f.stack.len() == g.stack.len() && f.stack.iter().zip(&g.stack).all(|(x, y)| mergeable(x, y)))
        && a.frames.iter().zip(&b.frames).all(|(f, g)| f.initializes == g.initializes && f.entered == g.entered)
        && a.objects.len() == b.objects.len()
        && a.literals == b.literals
        && a.classes == b.classes
        && a.statics.len() == b.statics.len()
        && a.statics.iter().zip(&b.statics).all(|((k, x), (l, y))| k == l && mergeable(x, y))
        && a.objects.iter().zip(&b.objects).all(|(o, q)| {
            o.class == q.class
                && o.fields.len() == q.fields.len()
                && o.fields.iter().zip(&q.fields).all(|((k, x), (l, y))| k == l && mergeable(x, y))
                && match (&o.array, &q.array) {
                    (None, None) => true,
                    (Some(x), Some(y)) => x.element == y.element && x.cells.len() == y.cells.len() && x.refs == y.refs,
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

/// Where a use of a class leaves its initialization ([`Engine::initialise_class`]).
enum Initialising {
    /// Initialized, or being initialized by an enclosing use: the instruction goes on.
    Ready,
    /// A `<clinit>` was pushed to run first.
    Running,
    /// The class, or one it needs first, is erroneous: `NoClassDefFoundError`.
    Erroneous,
    /// A gap ended the path.
    End(End),
}

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
    /// The array parameters that are a choice ([`Parameters`]): slot, and each option's guard with the slot whose
    /// own array it is, or null.
    choices: Vec<(u32, Vec<(Lit, Option<u32>)>)>,
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
    /// What the JVM initializes before a class, by class ([`gaps::initialization_supers`]).
    supers: HashMap<String, Rc<Vec<String>>>,
    /// Whether the engine runs a class's `<clinit>`, by class ([`gaps::runs_initializer`]).
    runs: HashMap<String, bool>,
    /// The time spent decoding methods, and reading witnesses out of models (their solving and encoding apart).
    decoding: Duration,
    witness: Duration,
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
    sat::configuration()?;
    let mut solver = (options.solver)();
    let transcript = match transcript::destination(options.transcript.as_deref()) {
        None => None,
        Some(path) if solver.terms().is_some() => {
            return Err(Error::new(format!("cannot write the transcript {}: it records clauses, and {} is given the engine's terms", path.display(), solver.signature())));
        }
        Some(path) => {
            let header = [
                format!("jvmcontract {}: the own checker's solver calls, in order ({})", env!("CARGO_PKG_VERSION"), "lib/src/bmc/transcript.rs"),
                format!("solver: {}", solver.signature()),
                format!("check: {class}.{method}{}", m.descriptor),
                format!("options: unwind {}, max array length {}, max paths {}, merge after {}, timeout {:.3} s, gaps {}", options.unwind, options.max_array_length, options.max_paths, options.merge_after, options.timeout.as_secs_f64(), options.gaps.name()),
            ];
            Some(transcript::Transcript::create(&path, &header).map_err(|e| Error::new(format!("cannot write the transcript {}: {e}", path.display())))?)
        }
    };
    let mut engine = Engine {
        cp,
        b: Blaster::over(solver, transcript),
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
        choices: Vec::new(),
        max_array_length: options.max_array_length,
        stage_lits: vec![None; STAGES.len()],
        gap_mode: options.gaps,
        met: BTreeMap::new(),
        contracts: options.contracts.clone(),
        applied: BTreeMap::new(),
        hides: HashMap::new(),
        supers: HashMap::new(),
        runs: HashMap::new(),
        decoding: Duration::ZERO,
        witness: Duration::ZERO,
    };
    let loading_before = cp.loading();
    let solver = engine.b.signature();
    let jdk = gaps::jdk_release();
    let outcome = |engine: &Engine, verdict: Verdict, input: Input, stage: Option<String>, problem: Option<String>| Outcome {
        verdict,
        raw_inputs: input.scalars,
        raw_arrays: input.arrays,
        raw_same: input.same,
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
        word_operations: engine.b.word_operations() as u64,
        seconds: started.elapsed().as_secs_f64(),
        loading: (cp.loading() - loading_before).as_secs_f64(),
        decoding: engine.decoding.as_secs_f64(),
        encoding: engine.b.encoding.as_secs_f64(),
        witness: engine.witness.as_secs_f64(),
        solver: solver.clone(),
        gaps: gaps::records(&engine.met, jdk.as_deref(), Some(if engine.gap_mode.refuses() { GapTreatment::Refused } else { GapTreatment::Assumed })).into_iter().chain(gaps::contract_records(&engine.applied, &engine.contracts, jdk.as_deref())).collect(),
        gap_mode: engine.gap_mode,
        transcript: engine.b.transcript_path().map(std::path::Path::to_path_buf),
    };

    let result = 'search: {
        // The inputs: fresh bits per parameter, in its range; an array parameter is an object of a fresh length up to
        // the bound (the first path's condition) with fresh cells.
        let mut locals: Vec<Option<Val>> = Vec::new();
        let mut objects: Vec<Obj> = Vec::new();
        let mut cond: Vec<Lit> = Vec::new();
        let mut slot = 0u32;
        // Each array parameter's own array: slot, type and object.
        let mut own: Vec<(u32, Type, usize)> = Vec::new();
        let options_in = &options.parameters;
        for t in &descriptor.params {
            if let Some(why) = unsupported_parameter(t) {
                break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("outside the fragment: {why}"))));
            }
            if let Type::Array(element) = t {
                let length = engine.b.fresh(32);
                let zero = engine.b.constant(0, 32);
                let most = engine.b.constant(i64::from(options.max_array_length), 32);
                cond.push(engine.b.sle(&zero, &length));
                cond.push(engine.b.sle(&length, &most));
                let cells: Vec<Bits> = (0..options.max_array_length).map(|_| engine.b.fresh(cell_width(element))).collect();
                engine.arrays.push((slot, (**element).clone(), length.clone(), cells.clone()));
                objects.push(Obj { class: t.descriptor(), fields: BTreeMap::new(), array: Some(Array { element: (**element).clone(), length, cells, refs: Vec::new() }) });
                own.push((slot, t.clone(), objects.len() - 1));
                // Null, the own arrays of the parameters before it in its group of the same type, and its own,
                // one of them under exclusive guards that cover every input.
                let mut options: Vec<Option<u32>> = Vec::new();
                if options_in.nullable.contains(&slot) {
                    options.push(None);
                }
                if let Some(group) = options_in.may_alias.iter().find(|g| g.contains(&slot)) {
                    options.extend(own.iter().filter(|(s, ty, _)| *s != slot && ty == t && group.contains(s)).map(|(s, _, _)| Some(*s)));
                }
                options.push(Some(slot));
                let mut guarded = Vec::new();
                let mut none_before = TRUE;
                for (i, option) in options.iter().enumerate() {
                    let g = if i + 1 == options.len() {
                        none_before
                    } else {
                        let pick = engine.b.var();
                        let g = engine.b.and(none_before, pick);
                        none_before = engine.b.and(none_before, -pick);
                        g
                    };
                    guarded.push((g, *option));
                }
                let object_of = |s: Option<u32>| s.map(|s| own.iter().find(|(o, _, _)| *o == s).expect("an own array").2);
                let value = choice(&mut engine.b, guarded.iter().map(|(g, s)| (*g, object_of(*s))).collect());
                if guarded.len() > 1 {
                    engine.choices.push((slot, guarded));
                }
                locals.push(Some(value));
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
        let first = Path { frames: vec![Frame::new(harness.clone(), m.name.clone(), code, locals)], cond, models: vec![Model::default()], undecided: false, resumed: false, objects, back_edges: HashMap::new(), literals: BTreeMap::new(), classes: BTreeMap::new(), statics: BTreeMap::new() };
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
                Err(stop) => break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(stop_text(&stop))) }),
            };
            if engine.paths > engine.max_paths {
                break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("more than {} paths; the budget is spent", engine.max_paths))) });
            }
            match engine.run(path) {
                Ok(End::Returned) | Ok(End::Infeasible) | Ok(End::Parked) | Ok(End::Gap) => {}
                Ok(End::Violation(cond)) => {
                    let (stage, input) = match engine.staged_input(&cond) {
                        Ok(found) => found,
                        Err(stop) if best.is_some() => {
                            let _ = stop;
                            break 'search Ok(violation(&engine, best));
                        }
                        Err(stop) => break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(stop_text(&stop)))),
                    };
                    if best.as_ref().is_none_or(|(s, _)| stage < *s) {
                        if best.is_none() {
                            let elapsed = started.elapsed();
                            engine.deadline = engine.deadline.min(Instant::now() + elapsed.max(Duration::from_secs(1)));
                        }
                        best = Some((stage, input));
                    }
                    if stage == 0 {
                        break 'search Ok(violation(&engine, best));
                    }
                }
                Ok(End::Unwound(what)) => {
                    break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("a loop was not fully unwound with --unwind {} ({what})", options.unwind))) })
                }
                Err(Stop::Unsupported(what)) => {
                    break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("outside the fragment: {what}"))) })
                }
                Err(Stop::Budget(what)) => break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(what)) }),
            }
        }
        if best.is_some() {
            break 'search Ok(violation(&engine, best));
        }
        if !engine.met.is_empty() && (engine.gap_mode.refuses() || engine.met.keys().any(|g| !g.kind.assumable())) {
            let refused: BTreeMap<Gap, std::collections::BTreeSet<Site>> = engine.met.iter().filter(|(g, _)| engine.gap_mode.refuses() || !g.kind.assumable()).map(|(g, s)| (g.clone(), s.clone())).collect();
            let problem = refused_gaps(&gaps::records(&refused, jdk.as_deref(), None), engine.gap_mode);
            break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(problem)));
        }
        Ok(outcome(&engine, Verdict::Verified, Input::default(), None, None))
    };
    // The transcript ends with how the run ended; one that could not be written fails the run, which was asked for it.
    let mut result = result;
    if let Ok(out) = &mut result {
        let last = format!("{:?}{}", out.verdict, out.problem.as_deref().map(|p| format!(": {p}")).unwrap_or_default());
        if let Some(written) = engine.b.finish_transcript(&last.replace('\n', " ")) {
            let path = out.transcript.clone().unwrap_or_default();
            written.map_err(|e| Error::new(format!("cannot write the transcript {}: {e}", path.display())))?;
        }
    }
    result
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

/// The SAT solver checks run on by default, by name and version: `CaDiCaL 1.9.5 (bundled)`, unless the environment
/// variable [`sat::ENV`] chooses another.
pub fn solver_signature() -> String {
    match sat::configuration() {
        Ok(make) => make().signature(),
        Err(e) => format!("none: {}", e.0),
    }
}

/// Runs the engine on a harness for the proof drivers: the class path is the harness, the application classes
/// and their class path (not the JDK classes extracted for JBMC: a JDK method is modelled here, never run), with
/// the tool's models; the result is in JBMC's shape, and a line goes to `work/bmc.log`.
#[allow(clippy::too_many_arguments)] // the settings a proof driver passes on
#[allow(clippy::too_many_arguments)]
pub fn run_for_proof(entries: &[std::path::PathBuf], models: bool, class: &str, method: &str, unwind: u32, max_array_length: u32, timeout: Duration, gaps: &GapSetting, parameters: &Parameters, work: &std::path::Path) -> Result<crate::jbmc::JbmcResult, Error> {
    let cp = crate::witness::classpath(entries.iter().chain(&gaps.class_dir).map(std::path::PathBuf::as_path))?.with_models(models);
    let outcome = check(&cp, class, method, &Options { unwind, timeout, max_array_length, gaps: gaps.mode, contracts: gaps.contracts.clone(), parameters: parameters.clone(), ..Options::default() })?;
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
        let started = Instant::now();
        let compiled = self.decode(class, name, descriptor);
        self.decoding += started.elapsed();
        let compiled = compiled?;
        self.codes.insert(key, compiled.clone());
        Ok(compiled)
    }

    /// [`Engine::code`] for a method not decoded yet.
    fn decode(&mut self, class: &Rc<ClassFile>, name: &str, descriptor: &str) -> Result<Rc<Decoded>, Stop> {
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
        Ok(Rc::new(Decoded { insns, pcs, index, handlers: code.exception_table.clone(), max_locals: code.max_locals as usize, lines, joins }))
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
        // Its solving and encoding are counted as such; the rest is reading the witness.
        let (started, solving, encoding) = (Instant::now(), self.b.solving, self.b.encoding);
        let found = self.staged_input_solved(cond);
        let elsewhere = (self.b.solving - solving) + (self.b.encoding - encoding);
        self.witness += started.elapsed().saturating_sub(elsewhere);
        found
    }

    fn staged_input_solved(&mut self, cond: &[Lit]) -> Result<(usize, Input), Stop> {
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
        let contents = |own: u32| -> Option<Vec<String>> {
            let (_, element, length, cells) = self.arrays.iter().find(|(s, ..)| *s == own)?;
            let n = usize::try_from(self.b.eval(length)).unwrap_or(0).min(cells.len());
            Some(cells[..n].iter().map(|c| unsigned(element, self.b.eval(c)).to_string()).collect())
        };
        // Which array each parameter holds (its own, unless it is a choice), and the first parameter to hold each.
        let mut first: BTreeMap<u32, u32> = BTreeMap::new();
        for (slot, ..) in &self.arrays {
            let held = match self.choices.iter().find(|(s, _)| s == slot) {
                Some((_, options)) => options.iter().find(|(g, _)| self.b.value(*g)).and_then(|(_, s)| *s),
                None => Some(*slot),
            };
            match held {
                None => {
                    input.arrays.insert(*slot, None);
                }
                Some(own) => {
                    input.arrays.insert(*slot, contents(own));
                    match first.get(&own) {
                        Some(&earlier) => {
                            input.same.insert(*slot, earlier);
                        }
                        None => {
                            first.insert(own, *slot);
                        }
                    }
                }
            }
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
                // A model that gives one function of equal operands two values is ruled out by a lemma first, so a
                // proof that two versions compute one remainder differently builds no divider.
                Some(true) => match (self.b.inconsistent_pair(), self.b.wrong_operation()) {
                    (Some((i, j, swapped)), _) => self.b.add_congruence(i, j, swapped),
                    (None, None) => return Ok(Some(true)),
                    (None, Some(i)) => self.b.refine_operation(i),
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
        if either != TRUE {
            into.cond.push(either);
        }
        let choose = |b: &mut Blaster, x: &mut Val, y: &Val| {
            if let Some(v) = choose(b, takes_into, x, y) {
                *x = v;
            }
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
        for (x, y) in into.statics.values_mut().zip(other.statics.values()) {
            choose(&mut self.b, x, y);
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
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let length = path.objects[o].array.as_ref().expect("an array").length.clone();
                self.push(path, Val::I(length));
                self.advance(path);
                Ok(None)
            }
            Insn::ArrayLoad(ArrayKind::Ref) => {
                if let Some(step) = self.concrete_ref(path, 1) {
                    return step;
                }
                if let Some(step) = self.concrete_index(path, 0) {
                    return step;
                }
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let array = path.objects[o].array.clone().expect("an array");
                if !holds_references(&array.element) {
                    return unsupported(format!("an aaload from a {}[]", array.element.java_name()));
                }
                let Some(value) = self.b.constant_value(&index).and_then(|k| usize::try_from(k).ok()).and_then(|k| array.refs.get(k).copied()) else {
                    // No cell there: out of bounds whatever the length.
                    return self.raise(path, "java/lang/ArrayIndexOutOfBoundsException");
                };
                let in_bounds = self.b.ult(&index, &array.length);
                self.branch_throw(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", Val::R(value))
            }
            Insn::ArrayStore(ArrayKind::Ref) => {
                if let Some(step) = self.concrete_ref(path, 2).or_else(|| self.concrete_ref(path, 0)) {
                    return step;
                }
                if let Some(step) = self.concrete_index(path, 1) {
                    return step;
                }
                let value = self.pop_ref(path)?;
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let array = path.objects[o].array.as_ref().expect("an array");
                if !holds_references(&array.element) {
                    return unsupported(format!("an aastore into a {}[]", array.element.java_name()));
                }
                let Some(cell) = self.b.constant_value(&index).and_then(|k| usize::try_from(k).ok()).filter(|&k| k < array.refs.len()) else {
                    return self.raise(path, "java/lang/ArrayIndexOutOfBoundsException");
                };
                if value.is_some_and(|v| !self.cp.is_subtype(&path.objects[v].class, &class_of(&array.element))) {
                    return unsupported(format!("an aastore of a {} into a {}[] (ArrayStoreException)", path.objects[value.expect("an object")].class.replace('/', "."), array.element.java_name()));
                }
                let in_bounds = self.b.ult(&index, &array.length);
                self.branch_throw_or(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", move |engine, path| {
                    path.objects[o].array.as_mut().expect("an array").refs[cell] = value;
                    engine.advance(path);
                })
            }
            Insn::ArrayLoad(kind) => {
                if let Some(step) = self.concrete_ref(path, 1) {
                    return step;
                }
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
                if let Some(step) = self.concrete_ref(path, 2) {
                    return step;
                }
                let value = match self.pop(path)? {
                    Val::I(b) | Val::J(b) => b,
                    Val::R(_) | Val::C(_) => return unsupported("arrays of references"),
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
                let cells = self.new_array_cells(path, &count)?;
                let negative = self.b.negative(&count);
                let width = cell_width(&element);
                self.branch_throw_or(path, negative, "java/lang/NegativeArraySizeException", move |engine, path| {
                    let zero = engine.b.constant(0, width);
                    let class = Type::Array(Box::new(element.clone())).descriptor();
                    path.objects.push(Obj { class, fields: BTreeMap::new(), array: Some(Array { element, length: count, cells: vec![zero; cells], refs: Vec::new() }) });
                    let o = path.objects.len() - 1;
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                })
            }
            // Every cell null; the element class is not initialized (JVMS §6.5 anewarray).
            Insn::ANewArray(index) => {
                let frame = path.frames.last().expect("a frame");
                let name = frame.class.pool.class_name(*index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                let element = if name.starts_with('[') { Type::parse(&name).map_err(|e| Stop::Unsupported(e.to_string()))? } else { Type::Object(name) };
                let count = self.pop_int(path)?;
                let cells = self.new_array_cells(path, &count)?;
                let negative = self.b.negative(&count);
                self.branch_throw_or(path, negative, "java/lang/NegativeArraySizeException", move |engine, path| {
                    let class = Type::Array(Box::new(element.clone())).descriptor();
                    path.objects.push(Obj { class, fields: BTreeMap::new(), array: Some(Array { element, length: count, cells: Vec::new(), refs: vec![None; cells] }) });
                    let o = path.objects.len() - 1;
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                })
            }
            _ => unsupported("a multi-dimensional array"),
        }
    }

    /// How many cells a new array of `count` elements has: its size when that is a constant (none when it is
    /// negative, which throws), and otherwise the bound, once the solver shows the size is within it on the path.
    fn new_array_cells(&mut self, path: &Path, count: &Bits) -> Result<usize, Stop> {
        Ok(match self.b.constant_value(count) {
            Some(n) if n < 0 => 0,
            Some(n) if n <= 1 << 16 => n as usize,
            Some(n) => return unsupported(format!("an array of {n} elements")),
            None => {
                // A computed size: within the bound, as a copy of a parameter is, or beyond the engine.
                let most = self.b.constant(i64::from(self.max_array_length), 32);
                let beyond = self.b.slt(&most, count);
                let mut assumptions = path.cond.clone();
                assumptions.push(beyond);
                if self.solve(&assumptions)? {
                    return unsupported(format!("an array of computed size, not known to be within {} elements", self.max_array_length));
                }
                self.max_array_length as usize
            }
        })
    }

    /// Makes the index of an `aaload` (`depth` 0) or an `aastore` (`depth` 1, under the value) a constant, when
    /// it is not one and the array below it is an array: a reference is not a choice among bits, as an int is, so
    /// the path is split on `index == i` for each cell `i` in turn, as a switch is. Each side that takes a cell
    /// runs the instruction again with `i` in place of the index, and the path on which the index is none of
    /// them throws `ArrayIndexOutOfBoundsException`, since the array's length is at most its cells. `None` when
    /// there is nothing to split, and the instruction goes on (or throws, on a null array).
    fn concrete_index(&mut self, path: &mut Path, depth: usize) -> Option<Step> {
        let stack = &path.frames.last().expect("a frame").stack;
        let n = stack.len();
        if n < depth + 2 {
            return None;
        }
        let at = n - 1 - depth;
        let (Val::I(index), Val::R(Some(o))) = (&stack[at], &stack[at - 1]) else { return None };
        if self.b.constant_value(index).is_some() {
            return None;
        }
        let array = path.objects[*o].array.as_ref().filter(|a| holds_references(&a.element))?;
        let cells = array.refs.len();
        let index = index.clone();
        Some(self.split_index(path, index, at, cells))
    }

    /// [`Engine::concrete_index`]'s split. A path that runs the instruction again does so rather than wait at it,
    /// as one taken from a join point does (`Path::resumed`): merged with the others there, its constant would
    /// be a choice again.
    fn split_index(&mut self, path: &mut Path, index: Bits, at: usize, cells: usize) -> Step {
        let fix = |path: &mut Path, k: &Bits| {
            path.frames.last_mut().expect("a frame").stack[at] = Val::I(k.clone());
            path.resumed = true;
        };
        for i in 0..cells {
            let k = self.b.constant(i as i64, 32);
            let c = self.b.eq(&index, &k);
            match self.sides(path, c)? {
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, true);
                    fix(&mut twin, &k);
                    // Counted here, since it does not come back from `next_path` as a new path.
                    self.paths += 1;
                    self.pending.push(twin);
                }
                Sides::Then => {
                    path.cond.push(c);
                    fix(path, &k);
                    return Ok(None);
                }
                Sides::Else => path.cond.push(-c),
                Sides::Undecided { model_takes_then: true } => {
                    // The twin takes the other cells: it runs the instruction again, this cell decided against.
                    let mut twin = self.split_undecided(path, c, true);
                    twin.resumed = true;
                    self.pending.push(twin);
                    fix(path, &k);
                    return Ok(None);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    fix(&mut twin, &k);
                    self.pending.push(twin);
                }
            }
        }
        self.raise(path, "java/lang/ArrayIndexOutOfBoundsException")
    }

    /// Splits the path per option of the symbolic reference `depth` values below the top of the stack, if it is one
    /// ([`Choice`]): the instruction, which needs to know the object, runs again on each part with the reference
    /// known, as [`Engine::concrete_index`] makes an index known. `None` when it is known already.
    fn concrete_ref(&mut self, path: &mut Path, depth: usize) -> Option<Step> {
        let stack = &path.frames.last().expect("a frame").stack;
        let at = stack.len().checked_sub(depth + 1)?;
        let Val::C(choice) = &stack[at] else { return None };
        let choice = choice.clone();
        Some(self.split_choice(path, &choice))
    }

    /// Splits the path per option of `choice`, every option but the last asked of the solver, the last taking what
    /// is left; on each part, every copy of the choice in the path's state is the option's target.
    fn split_choice(&mut self, path: &mut Path, choice: &Rc<Choice>) -> Step {
        let fix = |path: &mut Path, target: Option<usize>| {
            substitute(path, choice, target);
            path.resumed = true;
        };
        let (last, rest) = choice.0.split_last().expect("a choice has options");
        for &(c, target) in rest {
            match self.sides(path, c)? {
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, true);
                    fix(&mut twin, target);
                    self.paths += 1;
                    self.pending.push(twin);
                }
                Sides::Then => {
                    path.cond.push(c);
                    fix(path, target);
                    return Ok(None);
                }
                Sides::Else => path.cond.push(-c),
                Sides::Undecided { model_takes_then: true } => {
                    // The twin takes the other options: it runs the instruction again, this one decided against.
                    let mut twin = self.split_undecided(path, c, true);
                    twin.resumed = true;
                    self.pending.push(twin);
                    fix(path, target);
                    return Ok(None);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    fix(&mut twin, target);
                    self.pending.push(twin);
                }
            }
        }
        // Every other option excluded: the last one's guard holds under the path's condition.
        if !path.cond.contains(&last.0) {
            path.cond.push(last.0);
        }
        fix(path, last.1);
        Ok(None)
    }

    /// Whether the reference is null, as a literal: a formula over a [`Choice`]'s guards.
    fn null_lit(&mut self, v: &Val) -> Result<Lit, Stop> {
        let Some(options) = v.options() else { return unsupported(format!("expected a reference on the stack, found {v:?}")) };
        let guards: Vec<Lit> = options.iter().filter(|(_, t)| t.is_none()).map(|(g, _)| *g).collect();
        Ok(self.any(&guards))
    }

    /// Whether two references are the same object (or both null), as a literal: some pair of their options with
    /// one target, both guards holding.
    fn same_lit(&mut self, x: &Val, y: &Val) -> Result<Lit, Stop> {
        let (Some(xs), Some(ys)) = (x.options(), y.options()) else { return unsupported(format!("expected two references on the stack, found {x:?} and {y:?}")) };
        let mut pairs = Vec::new();
        for (g, t) in &xs {
            for (h, u) in &ys {
                if t == u {
                    pairs.push(self.b.and(*g, *h));
                }
            }
        }
        Ok(self.any(&pairs))
    }

    /// The disjunction of `lits`, `FALSE` when there are none.
    fn any(&mut self, lits: &[Lit]) -> Lit {
        let mut c = FALSE;
        for &l in lits {
            c = self.b.or(c, l);
        }
        c
    }

    /// `getfield` through a symbolic reference: the field of each object it may be, chosen among by the guards, and
    /// `NullPointerException` where it is null.
    fn get_field(&mut self, path: &mut Path, choice: &Choice, owner: &str, name: &str, descriptor: &str) -> Step {
        let mut values: Vec<(Lit, Val)> = Vec::new();
        let mut null = Vec::new();
        for &(g, t) in &choice.0 {
            match t {
                None => null.push(g),
                Some(o) => {
                    let key = self.field_key(path, o, owner, name, descriptor)?;
                    let v = match path.objects[o].fields.get(&key) {
                        Some(v) => v.clone(),
                        None => self.default_value(descriptor)?,
                    };
                    values.push((g, v));
                }
            }
        }
        // Where no object is the target the reference is null, which throws; there the value is any of them.
        let (_, mut value) = values.pop().expect("a choice has an object or two options");
        while let Some((g, v)) = values.pop() {
            value = choose(&mut self.b, g, &v, &value).ok_or_else(|| Stop::Unsupported(format!("fields {name} of different kinds")))?;
        }
        let null = self.any(&null);
        self.branch_throw(path, null, "java/lang/NullPointerException", value)
    }

    /// `putfield` through a symbolic reference: each object it may be gets the value where its guard holds and keeps
    /// its own elsewhere, and where it is null, `NullPointerException`.
    fn put_field(&mut self, path: &mut Path, choice: &Choice, value: Val, owner: &str, name: &str, descriptor: &str) -> Step {
        let mut writes: Vec<(usize, String, Val)> = Vec::new();
        let mut null = Vec::new();
        for &(g, t) in &choice.0 {
            match t {
                None => null.push(g),
                Some(o) => {
                    let key = self.field_key(path, o, owner, name, descriptor)?;
                    let old = match path.objects[o].fields.get(&key) {
                        Some(v) => v.clone(),
                        None => self.default_value(descriptor)?,
                    };
                    let new = choose(&mut self.b, g, &value, &old).ok_or_else(|| Stop::Unsupported(format!("a putfield of {value:?} into {name}")))?;
                    writes.push((o, key, new));
                }
            }
        }
        let null = self.any(&null);
        self.branch_throw_or(path, null, "java/lang/NullPointerException", move |engine, path| {
            for (o, key, v) in writes {
                path.objects[o].fields.insert(key, v);
            }
            engine.advance(path);
        })
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
    ///
    /// An exception that leaves a `<clinit>` makes its class erroneous and, unless it is an `Error`, is replaced by
    /// an `ExceptionInInitializerError`; the classes the instruction that ran it was initializing are erroneous
    /// too (JVMS §5.5, steps 7 and 11).
    fn throw(&mut self, path: &mut Path, mut obj: usize) -> Step {
        let mut class = path.objects[obj].class.clone();
        while let Some(frame) = path.frames.last_mut() {
            for c in std::mem::take(&mut frame.entered) {
                path.classes.insert(c, ClassState::Erroneous);
            }
            let pc = frame.pc();
            let handler = frame.code.handlers.iter().find(|h| u32::from(h.start_pc) <= pc && pc < u32::from(h.end_pc) && h.catch_type.as_deref().is_none_or(|t| self.cp.is_subtype(&class, t))).cloned();
            if let Some(h) = handler {
                let to = *frame.code.index.get(&u32::from(h.handler_pc)).ok_or_else(|| Stop::Unsupported("handler at no instruction".into()))?;
                frame.stack.clear();
                frame.stack.push(Val::R(Some(obj)));
                frame.at = to;
                return Ok(None);
            }
            if let Some(c) = path.frames.pop().and_then(|f| f.initializes) {
                path.classes.insert(c, ClassState::Erroneous);
                if !self.cp.is_subtype(&class, "java/lang/Error") {
                    class = "java/lang/ExceptionInInitializerError".to_string();
                    obj = self.alloc(path, &class);
                }
            }
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
            // Over known references these are constants; over a symbolic one, formulas of its guards.
            Insn::IfACmp(equal, target) => {
                let y = self.pop(path)?;
                let x = self.pop(path)?;
                let same = self.same_lit(&x, &y)?;
                return self.conditional(path, if equal { same } else { -same }, target);
            }
            Insn::IfNull(target) => {
                let x = self.pop(path)?;
                let null = self.null_lit(&x)?;
                return self.conditional(path, null, target);
            }
            Insn::IfNonNull(target) => {
                let x = self.pop(path)?;
                let null = self.null_lit(&x)?;
                return self.conditional(path, -null, target);
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
                let returned = path.frames.pop().expect("a frame");
                if path.frames.is_empty() {
                    return Ok(Some(End::Returned));
                }
                // A `<clinit>` returned: its class is initialized, and the instruction that ran it runs again.
                if let Some(c) = returned.initializes {
                    path.classes.insert(c, ClassState::Done);
                    return Ok(None);
                }
                if let Some(v) = value {
                    self.push(path, v);
                }
                self.advance(path);
                return Ok(None);
            }
            // The class that declares the resolved field is initialized first (JVMS §5.5).
            Insn::GetStatic(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let declaring = self.cp.resolve_field(&member.owner, &member.name, &member.descriptor).unwrap_or_else(|| member.owner.clone());
                if let Some(step) = self.initialise(path, &declaring) {
                    return step;
                }
                let v = match self.application_static(path, &declaring, &member.name, &member.descriptor) {
                    Some(v) => v?,
                    None => self.get_static(&member.owner, &member.name, &member.descriptor)?,
                };
                self.push(path, v);
            }
            Insn::PutStatic(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let declaring = self.cp.resolve_field(&member.owner, &member.name, &member.descriptor).unwrap_or_else(|| member.owner.clone());
                if crate::classpath::is_jdk_name(&declaring) || !self.cp.is_application(&declaring) {
                    return unsupported(format!("writes static field {}.{} of the JDK", declaring.replace('/', "."), member.name));
                }
                if let Some(step) = self.initialise(path, &declaring) {
                    return step;
                }
                if path.classes.get(&declaring) == Some(&ClassState::Assumed) {
                    return unsupported(format!("writes static field {}.{} of a class whose initializer was not run", declaring.replace('/', "."), member.name));
                }
                let v = self.pop(path)?;
                path.statics.insert((declaring, member.name.clone()), v);
            }
            Insn::GetField(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                if let Some(Val::C(choice)) = path.frames.last().expect("a frame").stack.last().cloned() {
                    self.pop(path)?;
                    return self.get_field(path, &choice, &member.owner, &member.name, &member.descriptor);
                }
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
                if let Some(Val::C(choice)) = path.frames.last().expect("a frame").stack.last().cloned() {
                    self.pop(path)?;
                    return self.put_field(path, &choice, v, &member.owner, &member.name, &member.descriptor);
                }
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
                if self.cp.is_application(&member.owner) && member.owner != crate::gap_contracts::INTRINSICS {
                    // The class that declares the method is initialized first (JVMS §5.5), the arguments still on
                    // the stack, so that the instruction can run again once its initializer returns.
                    let declaring = self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).map(|(cf, _)| cf.name.clone()).unwrap_or_else(|| member.owner.clone());
                    if let Some(step) = self.initialise(path, &declaring) {
                        return step;
                    }
                    let args = self.pop_args(path, descriptor.params.len())?;
                    return self.call(path, &member.owner, &member.name, &member.descriptor, args);
                }
                // The JDK's methods and the intrinsics take known references.
                for depth in 0..descriptor.params.len() {
                    if let Some(step) = self.concrete_ref(path, depth) {
                        return step;
                    }
                }
                let args = self.pop_args(path, descriptor.params.len())?;
                if member.owner == crate::gap_contracts::INTRINSICS {
                    return self.intrinsic(path, &member.name, args);
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
                // The receiver is dispatched on, so it is known first; so are the arguments of a call that is not
                // into the application, whose models and contracts take known references.
                if let Some(step) = self.concrete_ref(path, descriptor.params.len()) {
                    return step;
                }
                let receiver_at = path.frames.last().expect("a frame").stack.len() - 1 - descriptor.params.len();
                if let Val::R(Some(o)) = path.frames.last().expect("a frame").stack[receiver_at] {
                    let owner = if matches!(insn, Insn::InvokeSpecial(_)) { member.owner.clone() } else { path.objects[o].class.clone() };
                    let application = self.cp.checker_method(&owner, &member.name, &member.descriptor).is_some_and(|(cf, m)| self.cp.checker_runs(&cf.name) && m.code.is_some());
                    if !application {
                        for depth in 0..descriptor.params.len() {
                            if let Some(step) = self.concrete_ref(path, depth) {
                                return step;
                            }
                        }
                    }
                }
                let args = self.pop_args(path, descriptor.params.len())?;
                let receiver = self.pop_ref(path)?;
                let o = match self.null_check(path, receiver) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                let special = matches!(insn, Insn::InvokeSpecial(_));
                // An array's `clone`: a new array of the same class, length and elements (JLS §10.7).
                if !special && member.name == "clone" && member.descriptor == "()Ljava/lang/Object;" && path.objects[o].array.is_some() {
                    let copy = Obj { class: path.objects[o].class.clone(), fields: BTreeMap::new(), array: path.objects[o].array.clone() };
                    path.objects.push(copy);
                    let r = path.objects.len() - 1;
                    self.push(path, Val::R(Some(r)));
                    self.advance(path);
                    return Ok(None);
                }
                let owner = if special { member.owner.clone() } else { path.objects[o].class.clone() };
                // An application method, or one of `java.lang.Enum`'s, which its model runs ([`ClassPath::checker_runs`]).
                if let Some((cf, m)) = self.cp.checker_method(&owner, &member.name, &member.descriptor).filter(|(cf, _)| self.cp.checker_runs(&cf.name)) {
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
                if let Some(step) = self.initialise(path, &name) {
                    return step;
                }
                let r = self.alloc(path, &name);
                self.push(path, Val::R(Some(r)));
            }
            Insn::AThrow => {
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
                let r = self.pop_ref(path)?;
                let o = match self.null_check(path, r) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                return self.throw(path, o);
            }
            Insn::CheckCast(index) => {
                let target = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
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
                let r = self.pop(path)?;
                let Some(options) = r.options() else { return unsupported(format!("expected a reference on the stack, found {r:?}")) };
                let guards: Vec<Lit> = options.iter().filter(|(_, t)| t.is_some_and(|o| self.cp.is_subtype(&path.objects[o].class, &target))).map(|(g, _)| *g).collect();
                let is = self.any(&guards);
                let (one, zero) = (self.b.constant(1, 32), self.b.constant(0, 32));
                let c = self.b.ite_bits(is, &one, &zero);
                self.push(path, Val::I(c));
            }
            // In a run of one thread a monitor is always free and always held by it: only a null one does anything.
            Insn::MonitorEnter | Insn::MonitorExit => {
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
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

    /// The path uses `class` in a way that initializes it (JVMS §5.5: `new`, `getstatic`, `putstatic`,
    /// `invokestatic`), from the instruction at the top frame: `None` when the class is initialized, or being
    /// initialized by an enclosing use, and the instruction goes on; otherwise what the instruction does instead,
    /// having pushed a `<clinit>` to run first (the instruction runs again when it returns), thrown
    /// `NoClassDefFoundError` for an erroneous class, or ended at a gap. The engine runs an application class's
    /// `<clinit>` when it is in the fragment ([`gaps::runs_initializer`]); any other is a `class-initializer` gap,
    /// which under assume, or closed by a contract that it throws nothing, is taken to have run. A JDK class is
    /// taken to be initialized already.
    fn initialise(&mut self, path: &mut Path, class: &str) -> Option<Step> {
        if crate::classpath::is_jdk_name(class) || !self.cp.is_application(class) {
            return None;
        }
        match self.initialise_class(path, class) {
            Ok(Initialising::Ready) => {
                debug_assert!(path.frames.last().expect("a frame").entered.is_empty());
                None
            }
            Ok(Initialising::Running) => Some(Ok(None)),
            Ok(Initialising::Erroneous) => Some(self.raise(path, "java/lang/NoClassDefFoundError")),
            Ok(Initialising::End(end)) => Some(Ok(Some(end))),
            Err(stop) => Some(Err(stop)),
        }
    }

    /// The procedure of JVMS §5.5 for `class`, from the top frame's instruction, resumed where it stopped each
    /// time a `<clinit>` it pushed returns.
    fn initialise_class(&mut self, path: &mut Path, class: &str) -> Result<Initialising, Stop> {
        let top = path.frames.len() - 1;
        match path.classes.get(class) {
            Some(ClassState::Done | ClassState::Assumed) => return Ok(Initialising::Ready),
            Some(ClassState::Erroneous) => return Ok(Initialising::Erroneous),
            // Being initialized by this thread, from an enclosing use: go on (step 3).
            Some(ClassState::InProgress) if !path.frames[top].entered.iter().any(|c| c == class) => return Ok(Initialising::Ready),
            // Begun by this instruction, which runs again: resume.
            Some(ClassState::InProgress) => {}
            None => {
                if !self.cp.is_application(class) {
                    return Ok(Initialising::Ready);
                }
                path.classes.insert(class.to_string(), ClassState::InProgress);
                path.frames[top].entered.push(class.to_string());
            }
        }
        let supers = match self.supers.get(class) {
            Some(s) => s.clone(),
            None => {
                let s = Rc::new(gaps::initialization_supers(self.cp, class));
                self.supers.insert(class.to_string(), s.clone());
                s
            }
        };
        for s in supers.iter() {
            match self.initialise_class(path, s)? {
                Initialising::Ready => {}
                other => return Ok(other),
            }
        }
        path.frames[top].entered.retain(|c| c != class);
        let Some(cf) = self.cp.application(class).ok().flatten() else {
            path.classes.insert(class.to_string(), ClassState::Done);
            return Ok(Initialising::Ready);
        };
        if cf.method("<clinit>", "()V").is_none() {
            path.classes.insert(class.to_string(), ClassState::Done);
            return Ok(Initialising::Ready);
        }
        let runs = match self.runs.get(class) {
            Some(&r) => r,
            None => {
                let r = gaps::runs_initializer(self.cp, class);
                self.runs.insert(class.to_string(), r);
                r
            }
        };
        if runs {
            self.call(path, class, "<clinit>", "()V", Vec::new())?;
            path.frames.last_mut().expect("a frame").initializes = Some(class.to_string());
            return Ok(Initialising::Running);
        }
        let gap = Gap { kind: GapKind::ClassInitializer, owner: class.to_string(), name: "<clinit>".into(), descriptor: "()V".into() };
        if self.contracts.get(&gap).is_some_and(|k| k.how == Closing::Initialised) {
            self.apply(path, gap);
        } else if let Some(end) = self.meet(path, GapKind::ClassInitializer, class, "<clinit>", "()V") {
            return Ok(Initialising::End(end));
        }
        path.classes.insert(class.to_string(), ClassState::Assumed);
        Ok(Initialising::Ready)
    }

    /// The value of the static field `name` that `declaring`, an application class, declares, once the class is
    /// initialized: what the path wrote, else its `ConstantValue`, else zero or null. `None` for a JDK class, read
    /// by [`Engine::get_static`]. A class taken to be initialized has only its constants.
    fn application_static(&mut self, path: &mut Path, declaring: &str, name: &str, descriptor: &str) -> Option<Result<Val, Stop>> {
        if crate::classpath::is_jdk_name(declaring) || !self.cp.is_application(declaring) {
            return None;
        }
        if path.classes.get(declaring) == Some(&ClassState::Assumed) {
            return Some(self.get_static(declaring, name, descriptor));
        }
        if let Some(v) = path.statics.get(&(declaring.to_string(), name.to_string())) {
            return Some(Ok(v.clone()));
        }
        let constant = self.cp.application(declaring).ok().flatten().and_then(|cf| {
            let field = cf.field(name).filter(|f| f.is_static())?;
            let attr = field.attributes.iter().find(|a| a.name == "ConstantValue").filter(|a| a.data.len() == 2)?;
            cf.pool.loadable(u16::from_be_bytes([attr.data[0], attr.data[1]])).ok()
        });
        Some(match constant {
            Some(BootstrapArg::Int(v)) => Ok(Val::I(self.b.constant(i64::from(v), 32))),
            Some(BootstrapArg::Long(v)) => Ok(Val::J(self.b.constant(v, 64))),
            Some(BootstrapArg::Str(text)) => {
                let o = self.literal(path, Literal::Str(text), "java/lang/String");
                Ok(Val::R(Some(o)))
            }
            Some(_) => unsupported("floating point"),
            None => self.default_value(descriptor),
        })
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
        let (cf, m) = self.cp.checker_method(owner, name, descriptor).ok_or_else(|| Stop::Unsupported(format!("method not found: {}.{name}{descriptor}", owner.replace('/', "."))))?;
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
        path.frames.push(Frame::new(cf.clone(), name.to_string(), code, locals));
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

    /// The JDK's static methods the engine models: the exact and floor arithmetic of `Math`, the comparisons
    /// of the integer wrappers, and their `numberOfLeadingZeros`. [`models_jdk_static`] lists the same arms, for the gap scan.
    fn call_jdk_static(&mut self, path: &mut Path, owner: &str, name: &str, descriptor: &str, parsed: &MethodDescriptor, args: Vec<Val>) -> Step {
        let bits = |v: &Val| match v {
            Val::I(b) | Val::J(b) => Some(b.clone()),
            Val::R(_) | Val::C(_) => None,
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
            ("java/lang/Integer" | "java/lang/Long", "numberOfLeadingZeros") => {
                // A priority encoder: the zeros above the highest one bit, the width for zero. Each bit, from the
                // lowest up, overrides the count the bits below it gave.
                let width = a[0].len();
                let mut count = self.b.constant(width as i64, 32);
                for (i, &bit) in a[0].iter().enumerate() {
                    let here = self.b.constant((width - 1 - i) as i64, 32);
                    count = self.b.ite_bits(bit, &here, &count);
                }
                Val::I(count)
            }
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
            | ("java/lang/Integer" | "java/lang/Long", "numberOfLeadingZeros")
            | ("java/lang/Boolean", "logicalAnd" | "logicalOr" | "logicalXor")
    )
}

impl Blaster {
    /// The solver by name alone, as [`Outcome::solver`] gives it: the first word of its signature (`CaDiCaL`).
    fn signature(&self) -> String {
        self.solver_signature().split_whitespace().next().unwrap_or_default().to_string()
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
                Insn::GetStatic(_) => "`getstatic`",
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

    /// `a[0] = 1; b[0] = 2; a[0] == 1`, which holds unless `a` and `b` are one array, over arrays of length 1 at
    /// least: a parameter that may be the same array as another is a choice between its own and the other's.
    #[test]
    fn array_parameters_that_may_be_one_array_are_a_choice_and_the_witness_says_which() {
        let cp = harness("([I[I)V", |code, _, fail| {
            let skip = code.label();
            for a in [0, 1] {
                code.load(Kind::Ref, a);
                code.op(0xbe); // arraylength
                code.if_zero(Cond::Eq, skip);
            }
            for (a, v) in [(0, 1), (1, 2)] {
                code.load(Kind::Ref, a);
                code.iconst(0);
                code.iconst(v);
                code.op(0x4f); // iastore
            }
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.op(0x2e); // iaload
            code.iconst(1);
            code.if_icmp(Cond::Ne, fail);
            code.bind(skip);
        });
        let distinct = run(&cp);
        assert_eq!(distinct.verdict, Verdict::Verified, "{:?}", distinct.problem);
        for merge_after in [0, u64::MAX] {
            let parameters = Parameters { nullable: Vec::new(), may_alias: vec![vec![0, 1]] };
            let out = check(&cp, "Check", "check", &Options { parameters, merge_after, ..Options::default() }).unwrap();
            assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
            assert_eq!(out.raw_same, BTreeMap::from([(1, 0)]), "b is a's array");
            assert_eq!(out.raw_arrays[&1], out.raw_arrays[&0], "and has its elements");
        }
    }

    /// `a.length >= 0`, which an array parameter that may be null refutes with a `NullPointerException` the
    /// harness doesn't catch: the engine says so, and with the null checked first, the claim holds.
    #[test]
    fn an_array_parameter_that_may_be_null_is_null_on_some_path() {
        let length = |guarded: bool| {
            harness("([I)V", move |code, _, fail| {
                let done = code.label();
                if guarded {
                    code.load(Kind::Ref, 0);
                    code.if_null(done);
                }
                code.load(Kind::Ref, 0);
                code.op(0xbe); // arraylength
                code.if_zero(Cond::Lt, fail);
                code.bind(done);
            })
        };
        let nullable = |cp: &ClassPath| check(cp, "Check", "check", &Options { parameters: Parameters { nullable: vec![0], may_alias: Vec::new() }, ..Options::default() }).unwrap();
        assert_eq!(run(&length(false)).verdict, Verdict::Verified, "never null by default");
        let unguarded = nullable(&length(false));
        assert_eq!(unguarded.verdict, Verdict::Unverifiable);
        assert!(unguarded.problem.as_deref().unwrap_or("").contains("NullPointerException"), "{:?}", unguarded.problem);
        assert_eq!(nullable(&length(true)).verdict, Verdict::Verified);
        // A null that fails the claim is the witness's.
        let fails_on_null = harness("([I)V", |code, _, fail| {
            code.load(Kind::Ref, 0);
            code.if_null(fail);
        });
        let out = nullable(&fails_on_null);
        assert_eq!(out.verdict, Verdict::Violation);
        assert_eq!(out.raw_arrays[&0], None);
        assert!(out.raw_same.is_empty());
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

    /// A run that writes its solver calls is the same run, and the transcript holds every clause and call it made,
    /// which give the same answers when run again ([`transcript`]).
    #[test]
    fn a_transcript_holds_every_clause_and_call_and_replays_with_the_same_answers() {
        // x / y == 3 claimed impossible, behind two branches: refuted, after calls on both branches and the
        // division's facts, perhaps its circuit too.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("deeper/check.icnf");
        let plain = run(&cp);
        let recorded = check(&cp, "Check", "check", &Options { transcript: Some(path.clone()), ..Options::default() }).unwrap();
        let same = |o: &Outcome| (o.verdict, o.paths, o.solves, o.clauses, o.variables, o.raw_inputs.clone(), o.refined);
        assert_eq!(same(&recorded), same(&plain));
        assert_eq!((plain.transcript.as_ref(), recorded.transcript.as_ref()), (None, Some(&path)));
        assert!(recorded.summary().ends_with(&format!("; solver calls written to {}", path.display())), "{}", recorded.summary());

        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.starts_with(&format!("c jvmcontract {}: the own checker's solver calls, in order", env!("CARGO_PKG_VERSION"))), "{text}");
        assert!(text.contains(&format!("\nc solver: {}\n", solver_signature())), "{text}");
        assert!(text.contains("\nc check: Check.check(II)V\nc options: unwind 16, max array length 8, max paths 200000, merge after 512, timeout 600.000 s, gaps strict\np inccnf\n1 0\n"), "{text}");
        let replay = transcript::replay(&path, None).unwrap();
        assert!(replay.calls.len() >= 2 && replay.calls.len() as u64 <= recorded.solves, "{} calls of {}", replay.calls.len(), recorded.solves);
        assert_eq!(replay.clauses, recorded.clauses);
        assert_eq!(replay.variables, recorded.variables);
        assert_eq!((replay.contradictions, replay.undecided, replay.decided), (0, 0, 0), "{}", replay.summary());
        assert!(replay.calls.iter().all(|c| c.limit.is_some_and(|l| l > 0.0 && l <= 600.0)), "{:?}", replay.calls);
        assert_eq!(replay.calls.last().map(|c| c.recorded), Some("sat"), "the violation's input is the last model asked for");
        assert_eq!(replay.ending, Some(format!("end: {} clauses, {} calls; Violation", recorded.clauses, replay.calls.len())));

        // One that cannot be written stops the run before it starts, since it was asked for.
        let blocked = dir.path().join("file");
        std::fs::write(&blocked, "").unwrap();
        let e = check(&cp, "Check", "check", &Options { transcript: Some(blocked.join("x.icnf")), ..Options::default() }).unwrap_err();
        assert!(e.to_string().starts_with("cannot write the transcript"), "{e}");
    }


    #[test]
    fn the_engine_gives_its_solver_nothing_but_clauses_limits_and_calls() {
        // The same refuted division as the transcript's test, on a solver behind the interface that logs what it is
        // given: the outcome is the plain run's, and the clauses and calls it saw are the outcome's and the
        // transcript's, in the same order.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let plain = run(&cp);
        sat::Logged::take();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("logged.icnf");
        let logged = check(&cp, "Check", "check", &Options { solver: sat::Logged::boxed, transcript: Some(path.clone()), ..Options::default() }).unwrap();
        let events = sat::Logged::take();
        let same = |o: &Outcome| (o.verdict, o.paths, o.solves, o.clauses, o.variables, o.raw_inputs.clone(), o.refined);
        assert_eq!(same(&logged), same(&plain));

        let clauses: Vec<&Vec<Lit>> = events.iter().filter_map(|e| if let sat::Event::Clause(c) = e { Some(c) } else { None }).collect();
        let calls: Vec<(&Vec<Lit>, Option<bool>)> = events.iter().filter_map(|e| if let sat::Event::Solve(a, r) = e { Some((a, *r)) } else { None }).collect();
        assert_eq!(clauses.len() as u64, logged.clauses);
        assert_eq!(clauses.first().map(|c| c.as_slice()), Some(&[TRUE][..]), "the constant first");
        assert!(calls.len() >= 2 && calls.len() as u64 <= logged.solves, "{} calls of {}", calls.len(), logged.solves);
        // Every call is made under the limit last set, and the limit is within the check's budget.
        let mut limit = None;
        for e in &events {
            match e {
                sat::Event::Limit(l) => limit = *l,
                sat::Event::Solve(..) => assert!(limit.is_some_and(|l| l > 0.0 && l <= 600.0), "{events:?}"),
                sat::Event::Clause(_) => {}
            }
        }

        // The transcript names the solver the check ran on, and holds what that solver was given.
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.contains(&format!("\nc solver: logged {}\n", solver_signature())), "{text}");
        let replay = transcript::replay_on(&mut sat::Cadical::new(), &path, None).unwrap();
        assert_eq!(replay.clauses, logged.clauses);
        assert_eq!(replay.calls.iter().map(|c| c.recorded).collect::<Vec<_>>(), calls.iter().map(|(_, r)| transcript::answer_name(*r)).collect::<Vec<_>>());
        assert_eq!(replay.calls.iter().map(|c| c.assumptions).collect::<Vec<_>>(), calls.iter().map(|(a, _)| a.len()).collect::<Vec<_>>());
        assert_eq!(replay.contradictions, 0, "{}", replay.summary());

        // A replay goes through the interface too: on the logged solver it gives the same clauses and calls again.
        let again = transcript::replay_on(&mut *sat::Logged::boxed(), &path, None).unwrap();
        assert_eq!(again.solver, format!("logged {}", solver_signature()));
        let replayed = sat::Logged::take();
        assert_eq!(replayed.iter().filter(|e| matches!(e, sat::Event::Clause(_))).cloned().collect::<Vec<_>>(), events.iter().filter(|e| matches!(e, sat::Event::Clause(_))).cloned().collect::<Vec<_>>());
        assert_eq!(replayed.iter().filter_map(|e| if let sat::Event::Solve(a, r) = e { Some((a.clone(), *r)) } else { None }).collect::<Vec<_>>(), calls.iter().map(|(a, r)| ((*a).clone(), *r)).collect::<Vec<_>>());
    }

    #[test]
    fn a_check_on_bitwuzla_decides_as_on_cadical_and_replays_cadicals_calls() {
        // Bitwuzla given the engine's clauses (Phase 6c's SAT-only comparison), and given its terms (the word-level
        // prototype), when it is installed here. Its models may differ from CaDiCaL's, and so the lemmas and the
        // input found, but not the verdicts.
        if let Err(e) = bitwuzla::available() {
            eprintln!("skipped: {}", e.0);
            return;
        }
        let division = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let product = harness("(II)V", |code, _, fail| {
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
        let dir = tempfile::tempdir().unwrap();
        for (name, cp, expected) in [("division", &division, Verdict::Violation), ("product", &product, Verdict::Verified)] {
            let cadical_path = dir.path().join(format!("{name}-cadical.icnf"));
            let bitwuzla_path = dir.path().join(format!("{name}-bitwuzla.icnf"));
            let on_cadical = check(cp, "Check", "check", &Options { solver: sat::cadical, transcript: Some(cadical_path.clone()), ..Options::default() }).unwrap();
            let on_bitwuzla = check(cp, "Check", "check", &Options { solver: bitwuzla::boxed, transcript: Some(bitwuzla_path.clone()), ..Options::default() }).unwrap();
            assert_eq!(on_cadical.verdict, expected, "{name}: {}", on_cadical.summary());
            assert_eq!(on_bitwuzla.verdict, expected, "{name}: {}", on_bitwuzla.summary());
            assert_eq!((on_cadical.solver.as_str(), on_bitwuzla.solver.as_str()), ("CaDiCaL", "Bitwuzla"));
            if expected == Verdict::Violation {
                // The input Bitwuzla's model gives is a violation too: x >= 0, y != 0 and x / y == 3.
                let (x, y): (i32, i32) = (on_bitwuzla.raw_inputs[&0].parse().unwrap(), on_bitwuzla.raw_inputs[&1].parse().unwrap());
                assert!(x >= 0 && y != 0 && x.wrapping_div(y) == 3, "{x} / {y}");
            }
            // Each transcript names its solver, and CaDiCaL's calls, replayed on Bitwuzla, get CaDiCaL's answers.
            let text = std::fs::read_to_string(&bitwuzla_path).unwrap();
            assert!(text.contains("\nc solver: Bitwuzla 0.8.2 "), "{text}");
            let replay = transcript::replay_on(&mut bitwuzla::Bitwuzla::new().unwrap(), &cadical_path, None).unwrap();
            assert_eq!(replay.clauses, on_cadical.clauses);
            assert_eq!(replay.contradictions, 0, "{name}: {}", replay.summary());
            assert!(replay.solver.starts_with("Bitwuzla 0.8.2 "), "{}", replay.solver);
            // Given terms: the same verdict, a real input, the operations as terms and no lemma, and no transcript,
            // since there are no clauses to record.
            let on_terms = check(cp, "Check", "check", &Options { solver: bitwuzla::boxed_words, ..Options::default() }).unwrap();
            assert_eq!(on_terms.verdict, expected, "{name}: {}", on_terms.summary());
            assert_eq!(on_terms.clauses, 1, "{name}: only the constant's unit clause");
            assert_eq!((on_terms.divisions, on_terms.multiplications), (0, 0), "{name}: {}", on_terms.summary());
            if expected == Verdict::Violation {
                let (x, y): (i32, i32) = (on_terms.raw_inputs[&0].parse().unwrap(), on_terms.raw_inputs[&1].parse().unwrap());
                assert!(x >= 0 && y != 0 && x.wrapping_div(y) == 3, "{x} / {y}");
            }
            let refused = check(cp, "Check", "check", &Options { solver: bitwuzla::boxed_words, transcript: Some(dir.path().join("terms.icnf")), ..Options::default() }).unwrap_err();
            assert!(refused.0.contains("it records clauses"), "{}", refused.0);
        }
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

    /// Phase 5 of `llm-dlc/loops/engine-priorities.md`, enums: an array of references holds an object or null per
    /// cell, an index that is an input splits the path per cell, at a join too and with the paths merged there, and
    /// `clone()` is another array with the same cells.
    #[test]
    fn an_array_of_references_holds_its_objects_and_an_input_index_splits_the_path() {
        // For 0 <= n <= 2: a = new Object[3]; a[0] = "x"; a[1] = a; r = a[n > 0 ? n : 0], the index chosen at a join.
        // r is null exactly when n == 2; b = a.clone() has r at n, and b[0] = b leaves a[0] the literal.
        // `violate` adds `assert r != a`, which n == 1 refutes.
        let build = |violate: bool| {
            harness("(I)V", move |code, w, fail| {
                let (done, zero, index, some, next) = (code.label(), code.label(), code.label(), code.label(), code.label());
                let object = w.pool.class("java/lang/Object");
                let objects = w.pool.class("[Ljava/lang/Object;");
                let x = w.pool.string("x");
                let clone = w.pool.method_ref("[Ljava/lang/Object;", "clone", "()Ljava/lang/Object;");
                code.load(Kind::Int, 0);
                code.if_zero(Cond::Lt, done);
                code.load(Kind::Int, 0);
                code.iconst(2);
                code.if_icmp(Cond::Gt, done);
                code.iconst(3);
                code.op_u16(0xbd, object); // anewarray
                code.store(Kind::Ref, 1);
                code.load(Kind::Ref, 1);
                code.iconst(0);
                code.ldc(x);
                code.op(0x53); // aastore
                code.load(Kind::Ref, 1);
                code.iconst(1);
                code.load(Kind::Ref, 1);
                code.op(0x53);
                code.load(Kind::Ref, 1);
                code.load(Kind::Int, 0);
                code.if_zero(Cond::Le, zero);
                code.load(Kind::Int, 0);
                code.goto(index);
                code.bind(zero);
                code.iconst(0);
                code.bind(index);
                code.op(0x32); // aaload
                code.store(Kind::Ref, 2);
                code.load(Kind::Ref, 2);
                code.if_nonnull(some);
                code.load(Kind::Int, 0);
                code.iconst(2);
                code.if_icmp(Cond::Ne, fail);
                code.goto(next);
                code.bind(some);
                code.load(Kind::Int, 0);
                code.iconst(2);
                code.if_icmp(Cond::Eq, fail);
                code.bind(next);
                code.load(Kind::Ref, 1);
                code.op_u16(0xb6, clone);
                code.op_u16(0xc0, objects); // checkcast
                code.store(Kind::Ref, 3);
                code.load(Kind::Ref, 3);
                code.load(Kind::Int, 0);
                code.op(0x32);
                code.load(Kind::Ref, 2);
                code.if_acmpne(fail);
                code.load(Kind::Ref, 3);
                code.iconst(0);
                code.load(Kind::Ref, 3);
                code.op(0x53);
                code.load(Kind::Ref, 1);
                code.iconst(0);
                code.op(0x32);
                code.ldc(x);
                code.if_acmpne(fail);
                if violate {
                    let fine = code.label();
                    code.load(Kind::Ref, 2);
                    code.load(Kind::Ref, 1);
                    code.if_acmpne(fine);
                    code.goto(fail);
                    code.bind(fine);
                }
                code.bind(done);
            })
        };
        let merged = Options { merge_after: 0, ..Options::default() };
        for options in [Options::default(), merged.clone()] {
            let out = check(&build(false), "Check", "check", &options).unwrap();
            assert_eq!(out.verdict, Verdict::Verified, "merge after {}: {:?} {}", options.merge_after, out.problem, out.summary());
            let out = check(&build(true), "Check", "check", &options).unwrap();
            assert_eq!(out.verdict, Verdict::Violation, "merge after {}: {:?} {}", options.merge_after, out.problem, out.summary());
            assert_eq!(out.raw_inputs.get(&0).map(String::as_str), Some("1"), "{:?}", out.raw_inputs);
        }
        let out = check(&build(false), "Check", "check", &merged).unwrap();
        assert!(out.merges > 0, "the paths met at the index's join and were merged: {}", out.summary());

        // An object stored into an array of another element type (ArrayStoreException) is refused.
        let cp = harness("(I)V", |code, w, _| {
            let strings = w.pool.class("java/lang/String");
            let object = w.pool.class("java/lang/Object");
            let init = w.pool.method_ref("java/lang/Object", "<init>", "()V");
            code.iconst(1);
            code.op_u16(0xbd, strings);
            code.iconst(0);
            code.op_u16(0xbb, object);
            code.op(0x59);
            code.op_u16(0xb7, init);
            code.op(0x53);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.as_deref().unwrap_or("").contains("ArrayStoreException"), "{:?}", out.problem);
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
