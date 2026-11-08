//! The `jvmcontract` command line.

use std::path::PathBuf;
use std::process::ExitCode;

use clap::{Args, Parser, Subcommand};

use jvmcontract::{capabilities, classpath::ClassPath, equivalence, property, statemachine, tla, verifier, Error};

#[derive(Parser)]
#[command(name = "jvmcontract", version, about = "Formal verification of JVM bytecode as contracts: behavioural, regression, capability and API contracts, and TLA+ models generated from them.", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Check that the code still behaves exactly as the contracts in a directory say (exit 1 on any drift).
    Verify(ContractArgs),
    /// Rewrite the contracts in a directory from the code; --add creates new ones.
    Update(ContractArgs),
    /// Derive the contract of one method and print it, without touching any file.
    Derive {
        /// `pkg.Class#method`, or `pkg.Class#method(int, long[])` to name one of several overloads.
        target: String,
        #[command(flatten)]
        classes: ClassesArgs,
        /// Print the contract as JSON.
        #[arg(long)]
        json: bool,
        /// Report the execution cost (steps, allocations, call depth).
        #[arg(long)]
        cost: bool,
        /// Let record components of reference type also be null.
        #[arg(long)]
        null_components: bool,
    },
    /// Prove two compiled versions of a method equivalent with JBMC, or show an input on which they differ.
    Equivalence(EquivalenceArgs),
    /// List the gaps of the tool's own checker a method reaches: JDK calls, string conversions and class
    /// initializers it approximates rather than implements, found statically.
    Gaps {
        /// `pkg.Class#method` (repeatable), or `pkg.Class#method(int, long[])` to name one of several overloads.
        #[arg(long = "target", required = true)]
        targets: Vec<String>,
        #[command(flatten)]
        classes: ClassesArgs,
        /// Print JSON instead of the report.
        #[arg(long)]
        json: bool,
    },
    /// Say which claims a change from one build to another invalidates, and why: per claim, invalidated with the
    /// parts of its code that changed (a method's body, a class's declaration, a call's dispatch targets, a
    /// configuration file), unchanged, or unresolved when the first build has no such method.
    Impact {
        /// The first build's classes: a directory or jar (repeatable).
        #[arg(long = "before", required = true)]
        before: Vec<PathBuf>,
        /// The second build's classes: a directory or jar (repeatable).
        #[arg(long = "after", required = true)]
        after: Vec<PathBuf>,
        /// Further class path entries both builds refer to (repeatable, or PATH-separated).
        #[arg(long = "classpath")]
        classpath: Vec<String>,
        /// A JSON file of claims: an array of objects with a `target` (`pkg.Class#method`) and optionally a
        /// `beforeTarget` or `previousSymbol` and an `id`. build.py's claim.json and --plan output serve as they are.
        #[arg(long)]
        claims: Option<PathBuf>,
        /// A claim's target (repeatable), `pkg.Class#method`, beside or instead of --claims.
        #[arg(long = "target")]
        targets: Vec<String>,
        /// Print JSON instead of the report.
        #[arg(long)]
        json: bool,
    },
    /// Check the contract library on this JDK (exit 1 when a contract is refused, or has no record that holds):
    /// each contract for a gap of the tool's own checker is proved against the JDK's bytecode where it can be and
    /// tested on a real JVM, as a run under `--gaps advised` checks the agent's. With `--record`, the evidence is
    /// written to the library's checked.json, so runs apply each contract without checking it again.
    GapContracts {
        /// The library's directory: `lib/models/contracts`, or a project's own. Without it, the library built in.
        #[arg(long)]
        dir: Option<PathBuf>,
        /// Write the evidence of each accepted contract to DIR/checked.json, keeping the records on other JDKs.
        #[arg(long)]
        record: bool,
        /// The work directory for the proofs and the JVM test.
        #[arg(long)]
        work: Option<PathBuf>,
        /// Print JSON instead of the report.
        #[arg(long)]
        json: bool,
    },
    /// Prove a property of a method on every input with JBMC, or show an input that violates it.
    Prove(ProveArgs),
    /// Print the capability contract of a module (directories or jars), without touching any file.
    Capabilities {
        /// Directories of classes or jars. Each is analysed as one module unless --each is given.
        #[arg(required = true)]
        paths: Vec<PathBuf>,
        /// Analyse each path as a module of its own: a capability contract per dependency jar.
        #[arg(long)]
        each: bool,
        /// Print JSON instead of the contract text.
        #[arg(long)]
        json: bool,
        /// The module name for the contract header.
        #[arg(long, default_value = "module")]
        module: String,
    },
    /// Print the public API contract of a module.
    Api {
        #[arg(required = true)]
        paths: Vec<PathBuf>,
        #[arg(long, default_value = "module")]
        module: String,
    },
    /// Print the boundary contract of a module: where the framework enters it (routes, listeners, schedules, bean
    /// definitions), the advice on each bean (transactions, security, validation, caching, retries), the places
    /// where an annotation does not do what it says, the configuration keys, the wire types and the stored types, and under
    /// each entry point what it reaches (reads, writes, sends, calls, publishes, and which of those happen inside a
    /// transaction), what it throws and what each exception becomes (the handler that takes it, or a 500), and
    /// whether each handler's parameters can bind to the request, from the compiled classes and the application
    /// files.
    Boundaries {
        /// Directories of classes or jars of the module.
        #[arg(required = true)]
        paths: Vec<PathBuf>,
        /// Further class path entries (dependency jars, whose configuration metadata declares the framework's keys;
        /// repeatable, or PATH-separated).
        #[arg(long = "classpath")]
        classpath: Vec<String>,
        /// Resource roots with the application files (`application.yaml`, `application-prod.properties`).
        #[arg(long = "resources")]
        resources: Vec<PathBuf>,
        /// Print JSON instead of the contract text.
        #[arg(long)]
        json: bool,
        /// The module name for the contract header.
        #[arg(long, default_value = "module")]
        module: String,
    },
    /// Print the observation spec of each entry point of a module (routes, message listeners, schedules,
    /// application-event listeners): its external inputs and how each is bound, what a consumer observes (the
    /// result, the exception, a route's status for each outcome, each effect with the payload paths it snapshots
    /// and its place relative to transactions), which identity relations count, the environment model of its
    /// effects, and what the analysis can't see. Static: it says what a change must preserve and proves nothing.
    Observations {
        /// Directories of classes or jars of the module.
        #[arg(required = true)]
        paths: Vec<PathBuf>,
        /// Further class path entries (repeatable, or PATH-separated).
        #[arg(long = "classpath")]
        classpath: Vec<String>,
        /// The build's root directory: the class path entries under it are the module's sibling modules, whose
        /// classes the walk follows as it does the module's (as `verify --base` does for the boundary contract).
        #[arg(long)]
        base: Option<PathBuf>,
        /// Print JSON (the shared IR's `EntryPointSpec`s) instead of text.
        #[arg(long)]
        json: bool,
        /// Compare against an earlier build's specs, as this command printed them with `--json`, and print the
        /// obligations instead: each old observation preserved (to prove), changed, removed or unresolved, and
        /// what each would need. Exits 0; it proves nothing.
        #[arg(long, value_name = "SPECS.json")]
        against: Option<PathBuf>,
    },
    /// Check that each entry point of a build preserves, in a later build, what its observation spec observes: the
    /// ordered trace of modeled boundary-call attempts (each with its payload snapshotted at the call), the result,
    /// the exception and the status, under one environment model for both, by the tool's own checker. Recording
    /// stubs replace the modeled calls, every call returns normally, and a counterexample is replayed on a JVM under
    /// those stubs, not against real infrastructure. Exits 0 when every entry point checked is verified, else 1.
    Effects {
        /// The old build's classes (one directory).
        before: PathBuf,
        /// The new build's classes (one directory).
        after: PathBuf,
        /// Only this entry point of the old build, by its id (`POST /quotes`; repeatable). Default: every one.
        #[arg(long = "entry")]
        entries: Vec<String>,
        /// The most attempts a trace records; past it, the result is unresolved. Default: the spec's.
        #[arg(long)]
        trace_bound: Option<u32>,
        /// The unwinding bound of the proof.
        #[arg(long, default_value_t = 16)]
        unwind: u32,
        /// The longest array the proof considers.
        #[arg(long, default_value_t = 8)]
        max_array_length: u32,
        /// The proof cache's directory: each entry point's effect-trace proof is looked up under its claim key (the
        /// rewritten builds' closures, recording stubs included) and stored once decided. Local; never commit it.
        #[arg(long)]
        cache: Option<PathBuf>,
        /// The modelled calls a person declares, as JSON (a list of `ModeledCall`, each with its `model`): each
        /// replaces the spec's call of that method, and both builds are checked under it. A query or a per-call
        /// choice of primitive or String keys, answering a primitive, a nullable DTO made by a construction plan,
        /// or a declared exception (`lib/README.md`); a model the check can't enforce is refused by name.
        #[arg(long)]
        environment: Option<PathBuf>,
        /// Print JSON (one check per entry point, with its outcome, assumptions and traces) instead of text.
        #[arg(long)]
        json: bool,
        /// Write `effects.sarif` into this directory: an `effects-changed` finding per refuted entry point.
        #[arg(long)]
        report: Option<PathBuf>,
        /// The old build's source roots, which a finding is anchored in (repeatable).
        #[arg(long = "sources")]
        sources: Vec<PathBuf>,
        /// Make a finding's path relative to this directory.
        #[arg(long)]
        base: Option<PathBuf>,
    },
    /// Compare two builds of an application with nothing written by hand: each entry point's observations proved
    /// preserved, effects included (as `effects` does), and each changed kernel method checked under the
    /// correspondence alignment proposes (as `align` proposes it), with the proof cache when given one; then every
    /// obligation, what was reused, and every decision a person made or is asked to make.
    Compare {
        /// The old build's classes (one directory).
        before: PathBuf,
        /// The new build's classes (one directory).
        after: PathBuf,
        /// The proof cache's directory, for every proof of the run: an unchanged rerun reuses each result (the entry
        /// points' effect-trace proofs and the kernel's checks), and a changed pure helper is proved once and shared
        /// in its callers. Local; never commit it.
        #[arg(long)]
        cache: Option<PathBuf>,
        /// The unwinding bound of every proof.
        #[arg(long, default_value_t = 16)]
        unwind: u32,
        /// The longest array a proof considers.
        #[arg(long, default_value_t = 8)]
        max_array_length: u32,
        /// The modelled calls a person declares, as JSON (a list of `ModeledCall`, each with its `model`), for every
        /// entry point's effect check, as `effects --environment` takes them. Each counts in the effort report as
        /// an environment assumption a person made.
        #[arg(long)]
        environment: Option<PathBuf>,
        /// Print the report as JSON instead of text.
        #[arg(long)]
        json: bool,
        /// Write `compare.sarif` into this directory: an `effects-changed` finding per refuted entry point and a
        /// `behaviour-changed` one per refuted kernel pair.
        #[arg(long)]
        report: Option<PathBuf>,
        /// The new build's source roots, which a finding is anchored in (repeatable).
        #[arg(long = "sources")]
        sources: Vec<PathBuf>,
        /// Make a finding's path relative to this directory.
        #[arg(long)]
        base: Option<PathBuf>,
    },
    /// Turn a behavioural contract into a TLA+ operator, for a model checked by TLC.
    Tla {
        /// The contract file (`OrderLifecycle.decide.contract`).
        contract: PathBuf,
        /// The TLA+ module to write.
        output: PathBuf,
        /// The module name; defaults to the output file's stem.
        #[arg(long)]
        module: Option<String>,
        /// The operator name; defaults to the method name, capitalised.
        #[arg(long)]
        operator: Option<String>,
    },
    /// Run TLC on a TLA+ specification and report the verdict, the state count and any counterexample trace.
    Tlc {
        /// The specification file (`BoxOffice.tla`); its `.cfg` sits next to it.
        spec: PathBuf,
        /// Another configuration for the same specification (TLC's `-config`): other constants, a symmetry set,
        /// or an inductive check, where `INIT` is an invariant and a counterexample is one step from a state it
        /// admits.
        #[arg(long)]
        config: Option<PathBuf>,
        /// Print JSON.
        #[arg(long)]
        json: bool,
        /// Workers (`1` keeps the reported trace stable between runs).
        #[arg(long, default_value = "1")]
        workers: String,
        /// Seconds before giving up.
        #[arg(long, default_value_t = 1800)]
        timeout: u64,
        /// Where TLC finds the standard modules, if not in its jar (`-DTLA-Library`).
        #[arg(long)]
        library: Option<PathBuf>,
        /// Also report a reachable state in which no action is enabled, as a deadlock (off by default: a
        /// finished system is meant to stop).
        #[arg(long)]
        deadlock: bool,
        /// Also report, for each generated operator the specification uses, how many rows of its contract a step
        /// of the model takes, and which it never takes (TLC's `-coverage`): a change to a row no step takes is
        /// verified vacuously, whatever the verdict.
        #[arg(long)]
        coverage: bool,
    },
    /// Draw the state machine a behavioural contract describes, as Mermaid or DOT.
    Statemachine {
        contract: PathBuf,
        /// `mermaid` (default) or `dot`.
        #[arg(long, default_value = "mermaid")]
        format: String,
        /// The outcome field that names the next state.
        #[arg(long, default_value = "next")]
        next_field: String,
    },
    /// List the models of JDK classes the tool ships (shared by JBMC and the interpreter), or write them out as a
    /// class path entry.
    Models {
        /// Write every model's class file under this directory.
        #[arg(long)]
        write: Option<PathBuf>,
        /// Print JSON.
        #[arg(long)]
        json: bool,
    },
    /// Propose which method of a new build corresponds to each method of an old one that changed or is gone,
    /// statically, from names, descriptors, body shapes and callers: ranked candidates, each with what ties it to the
    /// old method. Then, for each pair, how its arguments, records and result relate, under the preservation
    /// contract: an input it fixes is mapped to itself and nothing else. Proves nothing unless --prove; --hints
    /// writes them to a hints file as proposed, their evidence unchecked or what --prove showed. Ends with the
    /// questions: each decision that is a person's, its candidates, and the line that approves one.
    Align {
        /// The old build's class files.
        #[arg(long)]
        before: PathBuf,
        /// The new build's class files.
        #[arg(long)]
        after: PathBuf,
        /// The hints file to update (made if missing): its method proposals are replaced, and every hint a person
        /// stated or approved is kept as it is. Keep it beside the build, not in the source tree.
        #[arg(long)]
        hints: Option<PathBuf>,
        /// The preservation contract (a JSON file, `jvmcontract::spec::PreservationContract`) of the comparison
        /// whose subject it names; every other pair is mapped under the contract its two signatures imply.
        #[arg(long)]
        contract: Option<PathBuf>,
        /// Check every complete mapping by the regression proof (`jvmcontract equivalence` with the flags it amounts
        /// to), collapse the proved ones that the contract can't tell apart, and settle each pair: one proved
        /// (evidence for its claim key, intent still proposed), several (a question), or none (each tried, with its
        /// counterexample). Runs proofs: queue it as a verification job.
        #[arg(long)]
        prove: bool,
        /// With --prove, only the pairs whose new method is this one (`pkg.Class#method`).
        #[arg(long)]
        subject: Option<String>,
        /// With --prove, the inputs the change is declared to affect, as `equivalence --unchanged-unless` takes them:
        /// a person's decision, part of every proof's claim.
        #[arg(long = "unchanged-unless")]
        unchanged_unless: Option<String>,
        /// With --prove: the checker (`jbmc`, `native` or `auto`), as for `equivalence`.
        #[arg(long, default_value = "jbmc")]
        engine: String,
        /// With --prove: the own checker's gap mode, `strict` or `assume`, as for `equivalence`.
        #[arg(long, default_value = "strict")]
        gaps: String,
        /// With --prove: the loop unwinding bound.
        #[arg(long, default_value_t = 16)]
        unwind: u32,
        /// With --prove: the longest array an array parameter is given.
        #[arg(long, default_value_t = 8)]
        max_array_length: u32,
        /// With --prove: the seconds each proof may take.
        #[arg(long, default_value_t = 600)]
        timeout: u64,
        /// With --prove: the `jbmc` executable.
        #[arg(long, default_value = "jbmc")]
        jbmc: String,
        /// With --prove: a working directory for the proofs, one subdirectory each (temporary ones by default).
        #[arg(long)]
        work: Option<PathBuf>,
        /// Print the report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Approve one of the tool's proposals in a hints file, as `align` lists them under its questions: the subject's
    /// other proposals of that kind are dropped, and later runs keep the approved one as it is. Sets the intent state
    /// only: the evidence stays what a proof under the current claim key showed, or unchecked.
    Approve {
        /// The hints file.
        #[arg(long)]
        hints: PathBuf,
        /// The kind of hint: `method`, `correspondence` or `observation-change`.
        #[arg(long)]
        kind: String,
        /// The hint's subject (`pkg.Class#method`, as the hints file writes it).
        #[arg(long)]
        subject: String,
        /// Which of the subject's ranked proposals; needed when it has more than one.
        #[arg(long)]
        rank: Option<u32>,
    },
    /// Print the structure of a class file: constant pool size, members, attributes and bytecode.
    Inspect {
        class_file: PathBuf,
        /// Also disassemble each method.
        #[arg(long)]
        code: bool,
    },
    /// Run a transcript of the own checker's solver calls again on the bundled CaDiCaL, or on another solver, call
    /// by call, and compare the answers with the recorded ones. A check writes one when the environment variable
    /// JVMCONTRACT_TRANSCRIPTS names a directory. Exits 1 when an answer contradicts the recorded one.
    Transcript {
        /// The transcript (`p inccnf`, with each call's recorded answer in a comment after it).
        file: PathBuf,
        /// Give every call this many seconds, instead of the limit recorded for it.
        #[arg(long)]
        limit: Option<f32>,
        /// The solver to run it on: `cadical` (bundled), or `bitwuzla`, loaded from JVMCONTRACT_BITWUZLA or
        /// ~/tools/bitwuzla/current, with Bitwuzla's options after a colon if any (`bitwuzla:preprocess=0`).
        #[arg(long, default_value = "cadical")]
        solver: String,
        /// Print JSON, with every call.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Args, Clone)]
struct ClassesArgs {
    /// The module's compiled classes: a directory or jar (repeatable).
    #[arg(long = "classes", required = true)]
    classes: Vec<PathBuf>,
    /// Further class path entries the classes refer to (repeatable, or PATH-separated).
    #[arg(long = "classpath")]
    classpath: Vec<String>,
}

impl ClassesArgs {
    fn classpath_entries(&self) -> Vec<PathBuf> {
        self.classpath.iter().flat_map(|s| std::env::split_paths(s).collect::<Vec<_>>()).collect()
    }
}

#[derive(Args)]
struct ContractArgs {
    /// The directory of `.contract` files.
    #[arg(long)]
    contracts: PathBuf,
    #[command(flatten)]
    classes: ClassesArgs,
    /// Source roots, to anchor findings to lines (repeatable).
    #[arg(long = "sources")]
    sources: Vec<PathBuf>,
    /// Resource roots with the application files (`application.yaml`) the boundary contract checks (repeatable).
    #[arg(long = "resources")]
    resources: Vec<PathBuf>,
    /// The directory SARIF paths are relative to.
    #[arg(long)]
    base: Option<PathBuf>,
    /// Write `contracts.sarif` into this directory.
    #[arg(long)]
    report: Option<PathBuf>,
    /// The module name, for the capability and API contract headers.
    #[arg(long, default_value = "module")]
    module: String,
    /// A target to add: `pkg.Class#method`, `capabilities`, `api`, or `boundaries` (repeatable).
    #[arg(long = "add")]
    add: Vec<String>,
    /// Report the execution cost of each derivation.
    #[arg(long)]
    cost: bool,
    /// Let record components of reference type also be null.
    #[arg(long)]
    null_components: bool,
}

#[derive(Args)]
struct EquivalenceArgs {
    /// The previous version's classes.
    #[arg(long)]
    before: PathBuf,
    /// The new version's classes.
    #[arg(long)]
    after: PathBuf,
    /// `pkg.Class#method`, a static method with primitive or array parameters; `pkg.Class#method(int, long[])`
    /// names one of several overloads.
    #[arg(long)]
    target: String,
    /// A Java boolean expression over the parameters naming the inputs the change is meant to affect; JML's
    /// quantifiers may range over an array parameter.
    #[arg(long = "unchanged-unless")]
    unchanged_unless: Option<String>,
    /// The previous version's method, `pkg.Class#method`, when it is not the target's: a method renamed or moved.
    #[arg(long = "before-target")]
    before_target: Option<String>,
    /// The previous version's arguments as expressions over the new parameters, separated by commas, when its
    /// parameters are not the new version's (reordered, added, removed or retyped): `tsA, nodeA, tsB, nodeB`, or
    /// `start, (int) (end - start), failed`. An array parameter is passed by name.
    #[arg(long = "before-arguments")]
    before_arguments: Option<String>,
    /// How the two results are related when they are not equal: a boolean expression over the new parameters,
    /// `previous` (the previous version's result) and `result` (the new one's), such as 'previous == (result <= 0)'
    /// for a boolean that became a remaining time; required when the return types differ.
    #[arg(long = "results-agree-when")]
    results_agree_when: Option<String>,
    /// How the two versions' internal states correspond where their classes differ: a JSON file in the form of the
    /// foundations IR's correspondence, `{"inputs": [{"old": "old.q.cents", "new": "new.q.amount.cents"}, ...],
    /// "outputs": [{"observation": "result", "holds": "old.result == new.result.cents"}]}`. The input equations
    /// say how the previous version's object for a parameter is made from the new one's, between field paths of
    /// the two; an output relation for the result takes the place of --results-agree-when, over old.result,
    /// new.result (an object by its field paths) and the new parameters. Not together with --before-arguments or
    /// --results-agree-when.
    #[arg(long)]
    correspondence: Option<PathBuf>,
    /// An object parameter made by its constructor that may be null; may be repeated. Both versions are given null
    /// together. Every other object parameter is an object.
    #[arg(long)]
    nullable: Vec<String>,
    /// Two object parameters of one class (the receiver as `this`) that may be the same object, `a,b`; may be
    /// repeated, and any two of a chain may be. Both versions are given one object together. Every other object
    /// parameter is an object of its own.
    #[arg(long = "may-alias")]
    may_alias: Vec<String>,
    /// A construction plan for each version, as JSON (`{"before": PLAN, "after": PLAN}`, `construction::Plans`):
    /// the receiver, parameters, shared objects, bounded arrays, adapted lists and setup calls the check makes its
    /// inputs by. What a check can't make by it (a factory, a cycle, an adapted value inside an object) is refused by
    /// name, never made otherwise (`lib/README.md`).
    #[arg(long)]
    plan: Option<PathBuf>,
    /// Further class path entries (PATH-separated or repeatable).
    #[arg(long = "classpath")]
    classpath: Vec<String>,
    /// A working directory for the harness, relocated classes and JBMC logs (a temporary one by default).
    #[arg(long)]
    work: Option<PathBuf>,
    /// Write `equivalence.sarif` into this directory.
    #[arg(long)]
    report: Option<PathBuf>,
    #[arg(long = "sources")]
    sources: Vec<PathBuf>,
    #[arg(long)]
    base: Option<PathBuf>,
    /// Loop unwinding bound for JBMC.
    #[arg(long, default_value_t = 16)]
    unwind: u32,
    /// The longest array an array parameter is given, the most code units a String parameter has, and the most
    /// elements a list parameter has (at most 10; each String or list checked by the tool's own checker only, a
    /// stated bound of the claim); the copying and comparing loops must fit the unwinding bound.
    #[arg(long, default_value_t = 8)]
    max_array_length: u32,
    /// Prove each callee as written, instead of taking a callee unchanged in both versions as one function in both,
    /// and prove a target whose bytecode is identical in both versions instead of taking it as unchanged.
    #[arg(long = "no-shared-callees")]
    no_shared_callees: bool,
    /// A local proof cache directory, never committed: a result stored there for the same prepared claim (both
    /// versions' code closures, the flags, the bounds, the models, the JDK and this binary's digest) is the result,
    /// marked as reused, and a verified or refuted result is stored. Used with `--engine native` only, for now.
    #[arg(long)]
    cache: Option<PathBuf>,
    /// Report the counterexample as JBMC found it, without shrinking it in the interpreter.
    #[arg(long)]
    no_shrink: bool,
    /// Seconds the whole check may take: the own checker, JBMC's search stages and its fallback, and the vacuity
    /// probe, each within a budget out of them (`--confirm` gets as long again).
    #[arg(long, default_value_t = 600)]
    timeout: u64,
    /// The `jbmc` executable.
    #[arg(long, default_value = "jbmc")]
    jbmc: String,
    /// Leave the tool's models of JDK classes (`jvmcontract models`) off JBMC's class path and out of the replay,
    /// to see what JBMC makes of its stubs.
    #[arg(long)]
    no_models: bool,
    /// Run JBMC with its string solver on. It is off by default: with it on, JBMC replaces calls of
    /// java.lang.Character by approximations of its own, ahead of the class on the class path.
    #[arg(long)]
    refine_strings: bool,
    /// The SAT solver JBMC is asked for: `cadical` (bundled with JBMC 6, and much the faster on array proofs with
    /// the string solver off), `minisat2`, or `default` for JBMC's own choice. A JBMC built without the solver
    /// named is run again with its default.
    #[arg(long, default_value = "cadical")]
    sat_solver: String,
    /// Which of JBMC's interval stages run before its run over every input: `full-range` (the default: that run
    /// alone, its counterexample shrunk in the interpreter), `staged` (`[0:20]`, then `[-100000:100000]`, each on at
    /// most an eighth of the check, where they leave out an input), or `tight` (`[0:20]` on at most a fortieth of
    /// the check, then that run). The own checker's stages and `--confirm` do not follow it.
    #[arg(long, default_value = "full-range")]
    jbmc_staging: String,
    /// Which checker proves the statement: `jbmc` (the default), `native` (the tool's own bounded model checker,
    /// for methods over integers, arrays of them and records, without floating point), or `auto` (the tool's own
    /// where it applies, JBMC elsewhere).
    #[arg(long, default_value = "jbmc")]
    engine: String,
    /// What the tool's own checker does at a gap, a construct it does not implement as the JVM does (a JDK
    /// constructor or method it has no model of, say): `strict` (the default) refuses it by name, so that the run
    /// has no verdict unless another path is a violation, and `--engine auto` does not ask JBMC; `assume` takes the
    /// approximation the gap states and names it in the verdict (a call whose value the proof reads has none, and
    /// is refused there too); `advised` scans the harness before solving and,
    /// when it reaches a gap with no contract, stops with each gap, what a contract for it must state and a
    /// template (`advice` in `--json`), and is otherwise strict. JBMC's own approximations (its stubs of methods
    /// it has no bytecode for, the call sites it does not link, the monitors it drops) are gaps in each mode too,
    /// found from its goto program before its proof; under advised JBMC applies a contract for a JDK call at its call
    /// sites, and what no contract closes (a monitor, an unlinked call site) is refused as under strict.
    #[arg(long, default_value = "strict")]
    gaps: String,
    /// Under `--gaps advised`, the contracts for the gaps, in the format of the template advised writes
    /// (`kind: gap-contracts`, a block per gap under its id): the tool's own checker applies each at its call in
    /// place of the gap, and refuses one it cannot apply, with the reason. Each is checked first: a contract for a
    /// static JDK method of primitives is proved against the JDK's own bytecode by the tool's own checker where it
    /// can be, and every contract is tested on a real JVM (the JDK's call on boundary and seeded random inputs, and
    /// on any input the proof refutes it on). One the JVM refutes is refused with its counterexamples; the others
    /// are proved, tested, or, where the JVM cannot test one, trusted. The verdict counts the contracts it rests on
    /// at each level. A gap the file has no contract for takes the contract library's, if it has one
    /// (`lib/models/contracts`, built in): checked once and recorded, so it is not checked again.
    #[arg(long)]
    contracts: Option<PathBuf>,
    /// Under `--gaps advised`, close gaps with the agent's `--contracts` only, not with the contract library's.
    #[arg(long)]
    no_contract_library: bool,
    /// Under `--gaps advised`, the most trusted contracts (ones neither proved nor tested) the proof may rest on.
    /// When more of the contracts for the gaps it reaches are trusted, each of those is refused, and its gap goes
    /// back to the agent: `--max-trust 0` accepts proved and tested contracts only.
    #[arg(long)]
    max_trust: Option<usize>,
    /// With `--engine auto`, have JBMC prove again, over every input, a statement the tool's own checker proved.
    /// JBMC agreeing is a second implementation of the JVM's semantics agreeing; JBMC refuting it is neither
    /// verdict (unverifiable, with JBMC's witness); JBMC giving none leaves the proof unconfirmed. The result says
    /// which. JBMC takes ten to a hundred times longer, so this is off unless asked for.
    #[arg(long)]
    confirm: bool,
    /// Print JSON.
    #[arg(long)]
    json: bool,
    /// Under the verdict, print the statement it is about (domain, assumptions with their basis, what is observed,
    /// bounds, models, checker, gap mode, confirmation, vacuity) and where its time went (the driver's steps, and
    /// each checker run's phases and formula): what `--json` holds as `stated` and `search`.
    #[arg(long)]
    details: bool,
}

#[derive(Args)]
struct ProveArgs {
    /// `pkg.Class#method`, a static method with primitive or array parameters; `pkg.Class#method(int, long[])`
    /// names one of several overloads. With --properties, only this target's properties are proved.
    target: Option<String>,
    #[command(flatten)]
    classes: ClassesArgs,
    /// A properties file (`properties.contract`): every property in it is proved, and the exit code is 1 if any
    /// is violated or cannot be verified.
    #[arg(long)]
    properties: Option<PathBuf>,
    /// The inputs the property is about: a Java boolean expression over the parameters (every input by default).
    #[arg(long)]
    assume: Option<String>,
    /// The property: a Java boolean expression over the parameters, `result`, and calls of the method itself,
    /// such as `result == merge(b, a)`. A boolean method's property is `result` by default.
    #[arg(long = "assert")]
    assert_: Option<String>,
    /// The exceptional behaviour, `<exception class> when <condition>`: the method throws that exception exactly on
    /// the inputs where the condition holds, such as `java.lang.ArithmeticException when divisor == 0`. May be
    /// repeated; the first clause whose condition holds is the one expected.
    #[arg(long = "throws")]
    throws: Vec<String>,
    /// An array parameter, or an object parameter made by its constructor, that may be null; may be repeated.
    /// Every other is an array or an object. Only the tool's own checker takes an array that may be null
    /// (`--engine native` or `auto`); an object's choice is the harness's, which either checker takes.
    #[arg(long)]
    nullable: Vec<String>,
    /// Two array parameters that may be one array, or two object parameters of one class that may be one object,
    /// `a,b`; may be repeated, and any two of a chain may be. Every other is its own. Only the tool's own checker
    /// takes arrays that may be one.
    #[arg(long = "may-alias")]
    may_alias: Vec<String>,
    /// A construction plan for each version, as JSON (`{"before": PLAN, "after": PLAN}`, `construction::Plans`):
    /// the receiver, parameters, shared objects, bounded arrays, adapted lists and setup calls the check makes its
    /// inputs by. What a check can't make by it (a factory, a cycle, an adapted value inside an object) is refused by
    /// name, never made otherwise (`lib/README.md`).
    #[arg(long)]
    plan: Option<PathBuf>,
    /// A local proof cache directory, never committed: a verified or refuted result is stored under the property
    /// claim's key (both versions' code closures, the assertion, the assumptions, the domain, the bounds, the models,
    /// the JDK and this binary's digest), and a later run of the same claim is that result, marked as reused, a
    /// refutation only once its witness fails the stored harness again. Not yet with `--plan`.
    #[arg(long)]
    cache: Option<PathBuf>,
    /// A working directory for the harness and JBMC logs (a temporary one by default).
    #[arg(long)]
    work: Option<PathBuf>,
    /// Write `property.sarif` into this directory.
    #[arg(long)]
    report: Option<PathBuf>,
    #[arg(long = "sources")]
    sources: Vec<PathBuf>,
    #[arg(long)]
    base: Option<PathBuf>,
    /// Loop unwinding bound for JBMC.
    #[arg(long, default_value_t = 16)]
    unwind: u32,
    /// The longest array an array parameter is given; a quantifier's loop must fit the unwinding bound.
    #[arg(long, default_value_t = 8)]
    max_array_length: u32,
    /// Report the counterexample as JBMC found it, without shrinking it in the interpreter.
    #[arg(long)]
    no_shrink: bool,
    /// Seconds the whole check may take: the own checker, JBMC's search stages and its fallback, and the vacuity
    /// probe, each within a budget out of them (`--confirm` gets as long again).
    #[arg(long, default_value_t = 600)]
    timeout: u64,
    /// The `jbmc` executable.
    #[arg(long, default_value = "jbmc")]
    jbmc: String,
    /// Leave the tool's models of JDK classes (`jvmcontract models`) off JBMC's class path and out of the replay,
    /// to see what JBMC makes of its stubs.
    #[arg(long)]
    no_models: bool,
    /// Run JBMC with its string solver on. It is off by default: with it on, JBMC replaces calls of
    /// java.lang.Character by approximations of its own, ahead of the class on the class path.
    #[arg(long)]
    refine_strings: bool,
    /// The SAT solver JBMC is asked for: `cadical` (bundled with JBMC 6, and much the faster on array proofs with
    /// the string solver off), `minisat2`, or `default` for JBMC's own choice. A JBMC built without the solver
    /// named is run again with its default.
    #[arg(long, default_value = "cadical")]
    sat_solver: String,
    /// Which of JBMC's interval stages run before its run over every input: `full-range` (the default: that run
    /// alone, its counterexample shrunk in the interpreter), `staged` (`[0:20]`, then `[-100000:100000]`, each on at
    /// most an eighth of the check, where they leave out an input), or `tight` (`[0:20]` on at most a fortieth of
    /// the check, then that run). The own checker's stages and `--confirm` do not follow it.
    #[arg(long, default_value = "full-range")]
    jbmc_staging: String,
    /// Which checker proves the statement: `jbmc` (the default), `native` (the tool's own bounded model checker,
    /// for methods over integers, arrays of them and records, without floating point), or `auto` (the tool's own
    /// where it applies, JBMC elsewhere).
    #[arg(long, default_value = "jbmc")]
    engine: String,
    /// What the tool's own checker does at a gap, a construct it does not implement as the JVM does (a JDK
    /// constructor or method it has no model of, say): `strict` (the default) refuses it by name, so that the run
    /// has no verdict unless another path is a violation, and `--engine auto` does not ask JBMC; `assume` takes the
    /// approximation the gap states and names it in the verdict (a call whose value the proof reads has none, and
    /// is refused there too); `advised` scans the harness before solving and,
    /// when it reaches a gap with no contract, stops with each gap, what a contract for it must state and a
    /// template (`advice` in `--json`), and is otherwise strict. JBMC's own approximations (its stubs of methods
    /// it has no bytecode for, the call sites it does not link, the monitors it drops) are gaps in each mode too,
    /// found from its goto program before its proof; under advised JBMC applies a contract for a JDK call at its call
    /// sites, and what no contract closes (a monitor, an unlinked call site) is refused as under strict.
    #[arg(long, default_value = "strict")]
    gaps: String,
    /// Under `--gaps advised`, the contracts for the gaps, in the format of the template advised writes
    /// (`kind: gap-contracts`, a block per gap under its id): the tool's own checker applies each at its call in
    /// place of the gap, and refuses one it cannot apply, with the reason. Each is checked first: a contract for a
    /// static JDK method of primitives is proved against the JDK's own bytecode by the tool's own checker where it
    /// can be, and every contract is tested on a real JVM (the JDK's call on boundary and seeded random inputs, and
    /// on any input the proof refutes it on). One the JVM refutes is refused with its counterexamples; the others
    /// are proved, tested, or, where the JVM cannot test one, trusted. The verdict counts the contracts it rests on
    /// at each level. A gap the file has no contract for takes the contract library's, if it has one
    /// (`lib/models/contracts`, built in): checked once and recorded, so it is not checked again.
    #[arg(long)]
    contracts: Option<PathBuf>,
    /// Under `--gaps advised`, close gaps with the agent's `--contracts` only, not with the contract library's.
    #[arg(long)]
    no_contract_library: bool,
    /// Under `--gaps advised`, the most trusted contracts (ones neither proved nor tested) the proof may rest on.
    /// When more of the contracts for the gaps it reaches are trusted, each of those is refused, and its gap goes
    /// back to the agent: `--max-trust 0` accepts proved and tested contracts only.
    #[arg(long)]
    max_trust: Option<usize>,
    /// With `--engine auto`, have JBMC prove again, over every input, a statement the tool's own checker proved.
    /// JBMC agreeing is a second implementation of the JVM's semantics agreeing; JBMC refuting it is neither
    /// verdict (unverifiable, with JBMC's witness); JBMC giving none leaves the proof unconfirmed. The result says
    /// which. JBMC takes ten to a hundred times longer, so this is off unless asked for.
    #[arg(long)]
    confirm: bool,
    /// Print JSON.
    #[arg(long)]
    json: bool,
    /// Under the verdict, print the statement it is about (domain, assumptions with their basis, what is observed,
    /// bounds, models, checker, gap mode, confirmation, vacuity) and where its time went (the driver's steps, and
    /// each checker run's phases and formula): what `--json` holds as `stated` and `search`.
    #[arg(long)]
    details: bool,
}

fn main() -> ExitCode {
    match run(Cli::parse()) {
        Ok(code) => ExitCode::from(code as u8),
        Err(e) => {
            eprintln!("jvmcontract: {e}");
            ExitCode::from(2)
        }
    }
}

fn run(cli: Cli) -> Result<i32, Error> {
    match cli.command {
        Command::Verify(args) | Command::Update(args) => {
            let update = matches!(std::env::args().nth(1).as_deref(), Some("update"));
            let mut run = verifier::ContractsRun::new(&args.contracts);
            run.classes = args.classes.classes.clone();
            run.classpath = args.classes.classpath_entries();
            run.sources = args.sources.iter().map(|s| std::fs::canonicalize(s).unwrap_or_else(|_| s.clone())).collect();
            run.resources = args.resources.clone();
            if let Some(base) = args.base {
                run.base = std::fs::canonicalize(&base).unwrap_or(base);
            }
            run.report = args.report;
            run.module = args.module;
            run.add = args.add;
            run.update = update;
            run.show_cost = args.cost;
            run.options.domain.null_components = args.null_components;
            let outcome = verifier::run(&run)?;
            print!("{}", outcome.output);
            Ok(outcome.exit_code)
        }
        Command::Derive { target, classes, json, cost, null_components } => {
            let cp = load_classpath(&classes)?;
            let mut v = verifier::Verifier::new(&cp);
            v.options.domain.null_components = null_components;
            let derivation = v.derive(&target);
            if json {
                println!("{}", serde_json::to_string_pretty(&derivation).expect("serializable"));
            } else if let Some(problem) = &derivation.problem {
                println!("✗ {target} cannot be verified: {problem}");
            } else {
                print!("{}", derivation.contract.as_ref().expect("derived").render());
                eprintln!("({})", derivation.stats());
                if cost {
                    eprintln!("(cost: {} steps, {} allocations, depth {})", derivation.cost.steps, derivation.cost.allocations, derivation.cost.max_depth);
                }
            }
            Ok(if derivation.problem.is_some() { 1 } else { 0 })
        }
        Command::Equivalence(args) => {
            let mut options = equivalence::Options::new(&args.before, &args.after, &args.target);
            options.unchanged_unless = args.unchanged_unless;
            options.classpath = args.classpath.iter().flat_map(|s| std::env::split_paths(s).collect::<Vec<_>>()).collect();
            options.work = args.work;
            options.report = args.report;
            options.sources = args.sources;
            if let Some(base) = args.base {
                options.base = base;
            }
            options.unwind = args.unwind;
            options.max_array_length = args.max_array_length;
            options.shrink = !args.no_shrink;
            options.timeout_seconds = args.timeout;
            options.jbmc = args.jbmc;
            options.models = !args.no_models;
            options.refine_strings = args.refine_strings;
            options.sat_solver = Some(args.sat_solver.clone()).filter(|s| s != "default");
            options.jbmc_staging = args.jbmc_staging.parse()?;
            options.engine = args.engine.parse()?;
            options.gaps = args.gaps.parse()?;
            options.contracts = args.contracts;
            options.contract_library = !args.no_contract_library;
            options.max_trust = args.max_trust;
            options.confirm = confirm_option(args.confirm, options.engine)?;
            options.shared_callees = !args.no_shared_callees;
            options.before_target = args.before_target;
            options.before_arguments = args.before_arguments;
            options.results_agree_when = args.results_agree_when;
            if let Some(file) = &args.correspondence {
                let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("--correspondence {}: {e}", file.display())))?;
                options.correspondence = Some(serde_json::from_str(&text).map_err(|e| Error::new(format!("--correspondence {}: not a correspondence ({{\"inputs\": [...], \"outputs\": [...]}}): {e}", file.display())))?);
            }
            options.nullable = args.nullable.clone();
            options.may_alias = args.may_alias.iter().map(|pair| pair.split_once(',').map(|(a, b)| (a.trim().to_string(), b.trim().to_string())).ok_or_else(|| Error::new(format!("--may-alias {pair}: give two parameters, `a,b`")))).collect::<Result<_, _>>()?;
            options.plan = args.plan.as_deref().map(jvmcontract::construction::load).transpose().map_err(|u| Error::new(u.to_string()))?;
            options.cache = args.cache;
            let outcome = equivalence::run(&options)?;
            if args.json {
                println!("{}", serde_json::to_string_pretty(&outcome).expect("serializable"));
            } else {
                print!("{}", outcome.output);
                if args.details {
                    print!("{}", jvmcontract::details::render(outcome.stated.as_ref(), outcome.search.as_ref()));
                }
            }
            Ok(outcome.verdict.exit_code())
        }
        Command::Prove(args) => {
            let declarations = match (&args.properties, &args.target) {
                (Some(file), only) => {
                    let all = property::read_declarations(file)?;
                    let selected: Vec<_> = all.into_iter().filter(|d| only.as_ref().is_none_or(|t| &d.target == t)).collect();
                    if selected.is_empty() {
                        return Err(Error::new(format!("no properties{} in {}", only.as_ref().map(|t| format!(" of {t}")).unwrap_or_default(), file.display())));
                    }
                    selected
                }
                (None, Some(target)) => vec![property::Declaration { target: target.clone(), assume: args.assume.clone(), assert: args.assert_.clone(), throws: args.throws.clone(), max_array_length: None, unwind: None }],
                (None, None) => return Err(Error::new("give a target `pkg.Class#method`, or --properties FILE")),
            };
            let mut outcomes = Vec::new();
            let mut findings = Vec::new();
            let mut exit = 0;
            for (i, declaration) in declarations.iter().enumerate() {
                let mut options = property::Options::new(&args.classes.classes, &declaration.target);
                options.classpath = args.classes.classpath_entries();
                options.assume = declaration.assume.clone();
                options.assert = declaration.assert.clone();
                options.throws = declaration.throws.clone();
                options.work = args.work.as_ref().map(|w| if declarations.len() > 1 { w.join(format!("property-{}", i + 1)) } else { w.clone() });
                options.report = if declarations.len() > 1 { None } else { args.report.clone() };
                options.sources = args.sources.clone();
                if let Some(base) = &args.base {
                    options.base = base.clone();
                }
                options.unwind = declaration.unwind.unwrap_or(args.unwind);
                options.max_array_length = declaration.max_array_length.unwrap_or(args.max_array_length);
                options.shrink = !args.no_shrink;
                options.timeout_seconds = args.timeout;
                options.jbmc = args.jbmc.clone();
                options.models = !args.no_models;
                options.refine_strings = args.refine_strings;
                options.sat_solver = Some(args.sat_solver.clone()).filter(|s| s != "default");
                options.jbmc_staging = args.jbmc_staging.parse()?;
                options.engine = args.engine.parse()?;
                options.gaps = args.gaps.parse()?;
                options.contracts = args.contracts.clone();
                options.contract_library = !args.no_contract_library;
                options.max_trust = args.max_trust;
                options.confirm = confirm_option(args.confirm, options.engine)?;
                options.nullable = args.nullable.clone();
                options.may_alias = args.may_alias.iter().map(|pair| pair.split_once(',').map(|(a, b)| (a.trim().to_string(), b.trim().to_string())).ok_or_else(|| Error::new(format!("--may-alias {pair}: give two parameters, `a,b`")))).collect::<Result<_, _>>()?;
                options.plan = args.plan.as_deref().map(jvmcontract::construction::load).transpose().map_err(|u| Error::new(u.to_string()))?;
                options.cache = args.cache.clone();
                let outcome = property::run(&options)?;
                exit = exit.max(outcome.verdict.exit_code());
                if !args.json {
                    print!("{}", outcome.output);
                    if args.details {
                        print!("{}", jvmcontract::details::render(outcome.stated.as_ref(), outcome.search.as_ref()));
                    }
                }
                findings.extend(outcome.findings.iter().cloned());
                outcomes.push(outcome);
            }
            if declarations.len() > 1 {
                if let Some(report) = &args.report {
                    jvmcontract::sarif::write(&report.join("property.sarif"), &findings)?;
                }
            }
            if args.json {
                println!("{}", serde_json::to_string_pretty(&outcomes).expect("serializable"));
            }
            Ok(exit)
        }
        Command::Capabilities { paths, each, json, module } => {
            if each {
                for path in &paths {
                    let report = capabilities::analyse(std::slice::from_ref(path))?;
                    let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| module.clone());
                    if json {
                        println!("{}", serde_json::to_string_pretty(&serde_json::json!({ "path": path, "report": report })).expect("serializable"));
                    } else {
                        println!("{}", report.render(&name));
                    }
                }
            } else {
                let report = capabilities::analyse(&paths)?;
                if json {
                    println!("{}", serde_json::to_string_pretty(&report).expect("serializable"));
                } else {
                    print!("{}", report.render(&module));
                }
            }
            Ok(0)
        }
        Command::Api { paths, module } => {
            let mut cp = ClassPath::new();
            for p in &paths {
                cp.add(p)?;
            }
            let surface = jvmcontract::api::analyse(&cp)?;
            print!("{}", surface.render(&module));
            Ok(0)
        }
        Command::Boundaries { paths, classpath, resources, json, module } => {
            let mut cp = ClassPath::new();
            for p in &paths {
                cp.add(p)?;
            }
            let mut module_cp = ClassPath::new();
            for p in &paths {
                module_cp.add(p)?;
            }
            let module_classes: std::collections::BTreeSet<String> = module_cp.application_class_names()?.into_iter().collect();
            for list in &classpath {
                cp.add_path_list(list)?;
            }
            let cp = cp.with_default_jdk();
            let boundaries = jvmcontract::boundaries::analyse_in(&cp, Some(&module_classes), Some(&module_classes), &resources)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&boundaries).expect("serializable"));
            } else {
                print!("{}", boundaries.render(&module));
            }
            Ok(0)
        }
        Command::Observations { paths, classpath, base, json, against } => {
            let mut cp = ClassPath::new();
            for p in &paths {
                cp.add(p)?;
            }
            let module_classes: std::collections::BTreeSet<String> = cp.application_class_names()?.into_iter().collect();
            let mut followed = module_classes.clone();
            // Compared canonically, as `verify` does: a relative `--base .` names the same siblings as an absolute one.
            let base = base.map(|b| std::fs::canonicalize(&b).unwrap_or(b));
            for list in &classpath {
                cp.add_path_list(list)?;
                if let Some(base) = &base {
                    for entry in std::env::split_paths(list).filter(|e| e.exists() && std::fs::canonicalize(e).unwrap_or_else(|_| e.clone()).starts_with(base)) {
                        let mut sibling = ClassPath::new();
                        sibling.add(&entry)?;
                        followed.extend(sibling.application_class_names()?);
                    }
                }
            }
            let cp = cp.with_default_jdk();
            let specs = jvmcontract::observations::analyse(&cp, Some(&module_classes), Some(&followed))?;
            if let Some(against) = against {
                let text = std::fs::read_to_string(&against).map_err(|e| jvmcontract::Error::new(format!("{}: {e}", against.display())))?;
                let before: Vec<jvmcontract::spec::observe::EntryPointSpec> = serde_json::from_str(&text).map_err(|e| jvmcontract::Error::new(format!("{}: not the JSON of `observations --json`: {e}", against.display())))?;
                let obligations = jvmcontract::observations::compare(&before, &specs);
                if json {
                    println!("{}", serde_json::to_string_pretty(&obligations).expect("serializable"));
                } else {
                    print!("{}", jvmcontract::observations::render_obligations(&before, &obligations));
                }
                return Ok(0);
            }
            if json {
                println!("{}", serde_json::to_string_pretty(&specs).expect("serializable"));
            } else {
                print!("{}", jvmcontract::observations::render(&specs));
            }
            Ok(0)
        }
        Command::Effects { before, after, entries, trace_bound, unwind, max_array_length, cache, environment, json, report, sources, base } => {
            let bounds = jvmcontract::spec::ClaimBounds { unwind, max_array_length };
            let environment = environment.as_deref().map(jvmcontract::environment::load).transpose().map_err(|u| Error::new(u.to_string()))?.unwrap_or_default();
            let checks = jvmcontract::effects::check_builds(&before, &after, &entries, trace_bound, bounds, cache.as_deref(), &environment).map_err(|u| Error::new(u.to_string()))?;
            if let Some(report) = &report {
                jvmcontract::sarif::write(&report.join("effects.sarif"), &jvmcontract::effects::findings(&checks, &sources, base.as_deref()))?;
            }
            if json {
                println!("{}", serde_json::to_string_pretty(&checks).expect("serializable"));
            } else {
                print!("{}", jvmcontract::effects::render_checks(&checks));
            }
            let all = checks.iter().all(|c| c.checked.as_ref().is_some_and(|k| k.outcome.verdict == jvmcontract::spec::Verdict::Verified));
            Ok(if all { 0 } else { 1 })
        }
        Command::Compare { before, after, cache, unwind, max_array_length, environment, json, report: report_dir, sources, base } => {
            let environment = environment.as_deref().map(jvmcontract::environment::load).transpose().map_err(|u| Error::new(u.to_string()))?.unwrap_or_default();
            let options = jvmcontract::compare::Options { before, after, cache, bounds: jvmcontract::spec::ClaimBounds { unwind, max_array_length }, environment };
            let report = jvmcontract::compare::run(&options).map_err(|u| Error::new(u.to_string()))?;
            if let Some(dir) = &report_dir {
                jvmcontract::sarif::write(&dir.join("compare.sarif"), &jvmcontract::compare::findings(&report, &sources, base.as_deref()))?;
            }
            if json {
                println!("{}", serde_json::to_string_pretty(&report).expect("serializable"));
            } else {
                print!("{}", jvmcontract::compare::render(&report));
            }
            Ok(if report.all_verified() { 0 } else { 1 })
        }
        Command::Tla { contract, output, module, operator } => {
            let contract = jvmcontract::contract::Contract::read(&contract)?;
            let module_name = module.unwrap_or_else(|| output.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "Contract".into()));
            let text = tla::operator_module(&contract, &module_name, operator.as_deref())?;
            std::fs::write(&output, &text)?;
            println!("wrote {}: {} cases", output.display(), text.lines().filter(|l| l.contains("->")).count());
            Ok(0)
        }
        Command::Tlc { spec, config, json, workers, timeout, library, deadlock, coverage } => {
            let mut options = tla::TlcOptions::new(&spec);
            options.config = config;
            options.workers = workers;
            options.timeout_seconds = timeout;
            options.library = library;
            options.deadlock = deadlock;
            options.coverage = coverage;
            let result = tla::run_tlc(&options)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&result).expect("serializable"));
            } else {
                print!("{}", result.summary());
            }
            Ok(result.verdict.exit_code())
        }
        Command::Statemachine { contract, format, next_field } => {
            let contract = jvmcontract::contract::Contract::read(&contract)?;
            let machine = statemachine::from_contract(&contract, &next_field)?;
            match format.as_str() {
                "dot" => print!("{}", machine.dot()),
                _ => print!("{}", machine.mermaid()),
            }
            Ok(0)
        }
        Command::Models { write, json } => {
            if let Some(dir) = &write {
                jvmcontract::models::write_to(dir)?;
            }
            if json {
                println!("{}", serde_json::to_string_pretty(jvmcontract::models::MODELS).expect("serializable"));
            } else {
                print!("{}", jvmcontract::models::listing());
                if let Some(dir) = &write {
                    println!("written under {}", dir.display());
                }
            }
            Ok(0)
        }
        Command::Gaps { targets, classes, json } => {
            let mut entries = classes.classes.clone();
            entries.extend(classes.classpath_entries());
            let cp = jvmcontract::witness::classpath(entries.iter().map(PathBuf::as_path))?.with_models(true);
            let roots = jvmcontract::bmc::gaps::roots(&cp, &targets)?;
            let scan = jvmcontract::bmc::gaps::scan(&cp, &roots)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&scan.record(&targets)).map_err(|e| Error::new(e.to_string()))?);
            } else {
                print!("{}", scan.report(&targets));
            }
            Ok(0)
        }
        Command::Impact { before, after, classpath, claims, targets, json } => {
            let mut list = Vec::new();
            if let Some(path) = &claims {
                let text = std::fs::read_to_string(path).map_err(|e| Error::new(format!("{}: {e}", path.display())))?;
                let value: serde_json::Value = serde_json::from_str(&text).map_err(|e| Error::new(format!("{}: {e}", path.display())))?;
                list.extend(jvmcontract::impact::claims_from_json(&value)?);
            }
            list.extend(targets.iter().map(|t| jvmcontract::impact::Claim::new(t)));
            if list.is_empty() {
                return Err(Error::new("name the claims with --claims FILE or --target"));
            }
            let shared: Vec<PathBuf> = classpath.iter().flat_map(|s| std::env::split_paths(s).collect::<Vec<_>>()).collect();
            let build = |entries: &[PathBuf]| -> Result<(ClassPath, jvmcontract::closure::Configuration), Error> {
                let all: Vec<&std::path::Path> = entries.iter().chain(shared.iter()).map(PathBuf::as_path).collect();
                let cp = jvmcontract::closure::build_class_path(&all)?;
                let configuration = jvmcontract::closure::Configuration::read(&cp, &[])?;
                Ok((cp, configuration))
            };
            let (before_cp, before_configuration) = build(&before)?;
            let (after_cp, after_configuration) = build(&after)?;
            let report = jvmcontract::impact::impact(&before_cp, &after_cp, &before_configuration, &after_configuration, &list);
            if json {
                println!("{}", serde_json::to_string_pretty(&report).map_err(|e| Error::new(e.to_string()))?);
            } else {
                print!("{}", report.render());
            }
            Ok(0)
        }
        Command::GapContracts { dir, record, work, json } => {
            let work = work.unwrap_or_else(|| std::env::temp_dir().join(format!("jvmcontract-gap-contracts-{}", std::process::id())));
            let checked = jvmcontract::contract_library::check(dir.as_deref(), &work, record)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&checked).map_err(|e| Error::new(e.to_string()))?);
            } else {
                print!("{}", checked.report());
            }
            Ok(if checked.ok() { 0 } else { 1 })
        }
        Command::Align { before, after, hints, contract, prove, subject, unchanged_unless, engine, gaps, unwind, max_array_length, timeout, jbmc, work, json } => {
            let contract: Option<jvmcontract::spec::PreservationContract> = match contract {
                Some(path) => Some(serde_json::from_str(&std::fs::read_to_string(&path)?).map_err(|e| Error::new(format!("{}: not a preservation contract: {e}", path.display())))?),
                None => None,
            };
            let (before_dir, after_dir) = (before, after);
            let (before, after) = (jvmcontract::alignment::Build::load(&before_dir)?, jvmcontract::alignment::Build::load(&after_dir)?);
            let mut alignment = jvmcontract::alignment::align(&before, &after, contract.as_ref());
            // The proof settings, part of every claim key: a static run with a hints file checks a decision's evidence
            // against the key these settings give.
            let gaps: jvmcontract::bmc::gaps::GapMode = gaps.parse()?;
            let settings = jvmcontract::alignment::proofs::Settings { engine: engine.parse()?, gaps, unwind, max_array_length, timeout_seconds: timeout, jbmc, unchanged_unless, work };
            if prove {
                if gaps == jvmcontract::bmc::gaps::GapMode::Advised {
                    return Err(Error::new("align --prove takes --gaps strict or assume: advised stops before solving, with contracts to write"));
                }
                let subject = subject.or_else(|| contract.as_ref().map(|c| c.subject.clone()));
                jvmcontract::alignment::prove(&mut alignment, &before_dir, &after_dir, subject.as_deref(), &settings)?;
            }
            if json {
                println!("{}", serde_json::to_string_pretty(&alignment).map_err(|e| Error::new(e.to_string()))?);
            } else {
                print!("{}", jvmcontract::alignment::render(&alignment.methods));
                print!("{}", jvmcontract::alignment::mappings::render(&alignment.mappings));
                print!("{}", jvmcontract::alignment::proofs::render(&alignment.proofs));
            }
            let proposed = jvmcontract::alignment::hints(&alignment);
            let (asked, file) = match hints {
                Some(path) => {
                    let merged = jvmcontract::alignment::merge_hints(jvmcontract::alignment::read_hints(&path)?, proposed);
                    let now = jvmcontract::alignment::evidence::current(&alignment, &jvmcontract::alignment::proofs::Keys::new(&before_dir, &after_dir)?, &settings);
                    let merged = jvmcontract::alignment::evidence::refresh(merged, &now);
                    jvmcontract::alignment::write_hints(&path, &merged)?;
                    eprintln!("({} hints in {})", merged.entries.len(), path.display());
                    (merged, Some(path))
                }
                None => (proposed, None),
            };
            if !json {
                print!("{}", jvmcontract::alignment::questions::render(&jvmcontract::alignment::questions::questions(&asked, file.as_deref()), &jvmcontract::alignment::questions::decisions(&asked)));
            }
            Ok(0)
        }
        Command::Approve { hints, kind, subject, rank } => {
            let (updated, approved) = jvmcontract::alignment::questions::approve(jvmcontract::alignment::read_hints(&hints)?, &kind, &subject, rank)?;
            jvmcontract::alignment::write_hints(&hints, &updated)?;
            println!("approved  {subject} ({kind}{}): intent approved; evidence {}", rank.map(|r| format!(", rank {r}")).unwrap_or_default(), jvmcontract::alignment::questions::describe(&approved.evidence));
            Ok(0)
        }
        Command::Inspect { class_file, code } => {
            let bytes = std::fs::read(&class_file)?;
            let class = jvmcontract::classfile::ClassFile::parse(&bytes)?;
            print!("{}", jvmcontract::classfile::describe(&class, code)?);
            Ok(0)
        }
        Command::Transcript { file, limit, solver, json } => {
            let make = jvmcontract::bmc::sat::named(&solver)?;
            let replay = jvmcontract::bmc::transcript::replay_on(&mut *make(), &file, limit)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&replay).map_err(|e| Error::new(e.to_string()))?);
            } else {
                println!("{}", replay.summary());
            }
            Ok(if replay.contradictions > 0 { 1 } else { 0 })
        }
    }
}

fn load_classpath(classes: &ClassesArgs) -> Result<ClassPath, Error> {
    let mut cp = ClassPath::new();
    for path in &classes.classes {
        cp.add(path)?;
    }
    for path in classes.classpath_entries() {
        if path.exists() {
            cp.add(&path)?;
        }
    }
    Ok(cp.with_default_jdk())
}

/// `--confirm`, which only `--engine auto` has: under `native` there is no JBMC to ask, and under `jbmc` no own
/// checker's proof to confirm.
fn confirm_option(confirm: bool, engine: jvmcontract::Engine) -> Result<bool, jvmcontract::Error> {
    if confirm && engine != jvmcontract::Engine::Auto {
        return Err(jvmcontract::Error::new("--confirm needs --engine auto: it has JBMC check a proof of the tool's own checker"));
    }
    Ok(confirm)
}
