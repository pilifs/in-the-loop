//! The narrow interface between the own checker and its SAT solver. The engine is three layers, and only the last
//! one knows which solver it is:
//!
//! - **scheduling** ([`super::Engine`]): which queries to ask, with what budget, and what to do with a model the
//!   lemmas show is not real (the probes, the deferred paths, the refinement loop in `solve_until`);
//! - **encoding** ([`super::bits::Blaster`]): word-level operations bit-blasted into clauses, and the inputs' values
//!   read back from a model;
//! - **solving** ([`Sat`]): clauses added, calls made under assumptions with a per-call time limit, and a model's
//!   values read.
//!
//! The encoding hands the solver nothing but clauses and calls, so a transcript of them ([`super::transcript`]) is
//! the whole of what the solver was asked, and another solver that implements [`Sat`] can be put behind the same
//! encoding, or behind a transcript's replay, without the engine changing. [`Cadical`] is the one the engine uses;
//! [`super::bitwuzla::Bitwuzla`], given the same clauses, is the one the solver comparison puts beside it, chosen by
//! the environment variable [`ENV`].
//!
//! A solver may also take the formula as terms ([`Terms`]), the word-level prototype of Phase 6c: the encoding then
//! defines each gate and each word-level operation's bits to it instead of bit-blasting them into clauses, and the
//! scheduling is unchanged. Only `bitwuzla-words` does ([`super::bitwuzla`]).

use super::bits::Lit;

/// An incremental SAT solver as the engine uses it. Literals are DIMACS numbers: a variable is a positive number,
/// its negation the negative one, and a variable is made by using it.
pub trait Sat {
    /// The solver by name and version, as results and transcripts record it: `CaDiCaL 1.9.5 (bundled)`.
    fn signature(&self) -> String;
    /// The solver as a result's evidence records it ([`crate::statement::native_sat`]): its name, version, where it
    /// comes from, and how it is configured.
    fn record(&self) -> crate::statement::Sat;
    /// Adds a clause, kept for every later call.
    fn add_clause(&mut self, lits: &[Lit]);
    /// Gives every later call at most this many seconds, or no limit.
    fn set_limit(&mut self, seconds: Option<f32>);
    /// Whether the clauses and the assumptions together are satisfiable, the assumptions holding for this call
    /// only; `None` when the solver stopped at its limit.
    fn solve(&mut self, assumptions: &[Lit]) -> Option<bool>;
    /// A literal's value in the model of the last call, when it was satisfiable; `None` when the model leaves it
    /// free.
    fn value(&self, lit: Lit) -> Option<bool>;
    /// The largest variable used so far.
    fn variables(&self) -> i32;
    /// The solver's terms, when it takes the formula as terms rather than as clauses: the encoding then defines
    /// every gate and word-level operation to it ([`Terms`]), and adds clauses only for what is asserted outright.
    /// `None` for a SAT solver, which is given clauses alone.
    fn terms(&mut self) -> Option<&mut dyn Terms> {
        None
    }
}

/// A gate over literals, as a solver that takes terms is given it: the output variable is that function of the
/// inputs, with no clause.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Gate {
    And(Lit, Lit),
    Xor(Lit, Lit),
    /// `if c then a else b`.
    Ite(Lit, Lit, Lit),
}

/// A word-level operation on machine integers, as the JVM does it (the shifts' amounts already masked to the width,
/// and given at the width of the value shifted). A division or remainder by zero, which the JVM throws on before its
/// value matters, is SMT-LIB's: the quotient is all ones for a dividend that isn't negative and one otherwise, and the
/// remainder the dividend.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum WordOp {
    Add,
    Sub,
    Mul,
    /// Signed division, truncating toward zero (`idiv`, `ldiv`).
    Div,
    /// Signed remainder, of the dividend's sign (`irem`, `lrem`).
    Rem,
    Shl,
    /// Arithmetic shift right (`ishr`).
    Shr,
    /// Logical shift right (`iushr`).
    Ushr,
    And,
    Or,
    Xor,
    /// `if c then a else b`, with `c` a single bit, the first operand.
    Ite,
    /// Unsigned `a < b`, one bit.
    Ult,
    /// Signed `a < b`, one bit.
    Slt,
    /// `a == b`, one bit.
    Eq,
}

impl WordOp {
    /// Whether the operands may be swapped.
    pub fn commutes(self) -> bool {
        matches!(self, WordOp::Add | WordOp::Mul | WordOp::And | WordOp::Or | WordOp::Xor | WordOp::Eq)
    }

    /// Whether the result is a single bit.
    pub fn compares(self) -> bool {
        matches!(self, WordOp::Ult | WordOp::Slt | WordOp::Eq)
    }
}

/// A solver given the formula as terms: each variable that is not an input is defined, once and before it is used, as
/// a gate over earlier literals or as a bit of a word-level operation over earlier bits. Literals are the ones of
/// [`Sat`].
pub trait Terms {
    /// Defines `out` as `gate`.
    fn gate(&mut self, out: Lit, gate: Gate);
    /// Defines `outs`, least significant first, as the bits of `op` over `operands` (each as bits, least
    /// significant first; [`WordOp::Ite`]'s condition as one bit). A comparison has one output.
    fn word(&mut self, outs: &[Lit], op: WordOp, operands: &[&[Lit]]);
}

/// The environment variable choosing the solver for checks whose options don't: `cadical` (the default), `bitwuzla`
/// ([`super::bitwuzla`]), given the engine's clauses, or `bitwuzla-words`, given its terms ([`Terms`]), each with
/// Bitwuzla's options after a colon if any (`bitwuzla:preprocess=0`). Like the
/// transcripts' variable, it reaches the checks that the proof drivers, the benchmark or a job run, and the results
/// name the solver it chose, with those options ([`super::solver_signature`]).
pub const ENV: &str = "JVMCONTRACT_SOLVER";

/// The solvers by the names [`ENV`] and `jvmcontract transcript --solver` take.
pub const NAMES: &[&str] = &["cadical", "bitwuzla", "bitwuzla-words"];

/// What makes a new, empty solver of one kind and configuration.
pub type Maker = std::sync::Arc<dyn Fn() -> Box<dyn Sat> + Send + Sync>;

/// The maker of the solver `name` names, `cadical`, `bitwuzla`, or `bitwuzla:` and Bitwuzla's options
/// (`bitwuzla:preprocess=0,rewrite-level=0`), once it is known to work here: Bitwuzla's library must load and take
/// the options.
pub fn named(name: &str) -> Result<Maker, crate::Error> {
    let (base, options) = match name.split_once(':') {
        Some((base, options)) => (base, Some(options)),
        None => (name, None),
    };
    match base {
        "cadical" if options.is_none() => Ok(std::sync::Arc::new(cadical)),
        "cadical" => Err(crate::Error::new(format!("{ENV}: the bundled CaDiCaL takes no options here ({name:?})"))),
        "bitwuzla" | "bitwuzla-words" => {
            let words = base == "bitwuzla-words";
            let settings = super::bitwuzla::settings(options.unwrap_or(""))?;
            super::bitwuzla::Bitwuzla::configured(&settings, words)?;
            Ok(std::sync::Arc::new(move || super::bitwuzla::boxed_configured(&settings, words)))
        }
        _ => Err(crate::Error::new(format!("{ENV}: no solver called {name:?} (the solvers are {})", NAMES.join(", ")))),
    }
}

static CONFIGURED: std::sync::OnceLock<Result<Maker, String>> = std::sync::OnceLock::new();

/// The solver [`ENV`] chooses, read once per process; CaDiCaL when it is unset or empty.
pub fn configuration() -> Result<Maker, crate::Error> {
    let chosen = CONFIGURED.get_or_init(|| match std::env::var(ENV) {
        Ok(name) if !name.is_empty() => named(&name).map_err(|e| e.0),
        _ => Ok(std::sync::Arc::new(cadical)),
    });
    chosen.clone().map_err(crate::Error::new)
}

/// A new, empty solver of the kind [`ENV`] chooses, as [`super::Options::solver`] makes one by default. A check
/// asks for [`configuration`] first, so a choice that doesn't work here is an error, not this panic.
pub fn configured() -> Box<dyn Sat> {
    match configuration() {
        Ok(make) => make(),
        Err(e) => panic!("{}", e.0),
    }
}

/// CaDiCaL as the `cadical` crate bundles it (1.9.5 in crate 0.1.16), with its time limit per call.
pub struct Cadical {
    solver: cadical::Solver<cadical::Timeout>,
}

impl Cadical {
    pub fn new() -> Cadical {
        Cadical { solver: cadical::Solver::new() }
    }
}

/// A new, empty [`Cadical`], as [`super::Options::solver`] makes one.
pub fn cadical() -> Box<dyn Sat> {
    Box::new(Cadical::new())
}

impl Default for Cadical {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Debug for Cadical {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Cadical({} variables)", self.solver.max_variable())
    }
}

impl Sat for Cadical {
    fn signature(&self) -> String {
        let signature = self.solver.signature();
        match signature.strip_prefix("cadical-") {
            Some(version) => format!("CaDiCaL {version} (bundled)"),
            None => format!("{signature} (bundled)"),
        }
    }

    fn record(&self) -> crate::statement::Sat {
        let signature = self.solver.signature();
        let version = signature.strip_prefix("cadical-").map(str::to_string);
        let source = match crate::statement::locked_version("cadical") {
            Some(v) => format!("bundled by the Rust crate cadical {v}"),
            None => "bundled by the Rust crate cadical".to_string(),
        };
        let configuration = [
            "CaDiCaL's default options",
            "incremental: one solver per run of the checker takes the clauses as they are encoded, each query solved under assumptions",
            "the run's deadline through CaDiCaL's terminate callback",
        ];
        crate::statement::Sat { solver: "CaDiCaL".into(), version: version.or(Some(signature.to_string())), source, configuration: configuration.map(String::from).into() }
    }

    fn add_clause(&mut self, lits: &[Lit]) {
        self.solver.add_clause(lits.iter().copied());
    }

    fn set_limit(&mut self, seconds: Option<f32>) {
        self.solver.set_callbacks(seconds.map(cadical::Timeout::new));
    }

    fn solve(&mut self, assumptions: &[Lit]) -> Option<bool> {
        self.solver.solve_with(assumptions.iter().copied())
    }

    fn value(&self, lit: Lit) -> Option<bool> {
        self.solver.value(lit)
    }

    fn variables(&self) -> i32 {
        self.solver.max_variable()
    }
}

/// A solver for tests: CaDiCaL behind the interface, with every clause, limit and call written down in this thread's
/// [`Logged::take`], to show what crosses the interface and that nothing else does.
#[cfg(test)]
pub struct Logged {
    inner: Cadical,
}

/// What a [`Logged`] solver was given, in order.
#[cfg(test)]
#[derive(Debug, Clone, PartialEq)]
pub enum Event {
    Clause(Vec<Lit>),
    Limit(Option<f32>),
    Solve(Vec<Lit>, Option<bool>),
}

#[cfg(test)]
thread_local! {
    static LOG: std::cell::RefCell<Vec<Event>> = const { std::cell::RefCell::new(Vec::new()) };
}

#[cfg(test)]
impl Logged {
    /// A new, empty one, as [`super::Options::solver`] makes one; its events go to this thread's log.
    pub fn boxed() -> Box<dyn Sat> {
        Box::new(Logged { inner: Cadical::new() })
    }

    /// This thread's log so far, emptied.
    pub fn take() -> Vec<Event> {
        LOG.with(|l| std::mem::take(&mut *l.borrow_mut()))
    }

    fn log(event: Event) {
        LOG.with(|l| l.borrow_mut().push(event));
    }
}

#[cfg(test)]
impl Sat for Logged {
    fn signature(&self) -> String {
        format!("logged {}", self.inner.signature())
    }

    fn record(&self) -> crate::statement::Sat {
        self.inner.record()
    }

    fn add_clause(&mut self, lits: &[Lit]) {
        Self::log(Event::Clause(lits.to_vec()));
        self.inner.add_clause(lits);
    }

    fn set_limit(&mut self, seconds: Option<f32>) {
        Self::log(Event::Limit(seconds));
        self.inner.set_limit(seconds);
    }

    fn solve(&mut self, assumptions: &[Lit]) -> Option<bool> {
        let answer = self.inner.solve(assumptions);
        Self::log(Event::Solve(assumptions.to_vec(), answer));
        answer
    }

    fn value(&self, lit: Lit) -> Option<bool> {
        self.inner.value(lit)
    }

    fn variables(&self) -> i32 {
        self.inner.variables()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cadical_names_itself_and_answers_incrementally_under_assumptions() {
        let mut s = Cadical::new();
        assert!(s.signature().starts_with("CaDiCaL 1.9.5"), "{}", s.signature());
        s.add_clause(&[1, 2]);
        s.add_clause(&[-1, 2]);
        assert_eq!(s.solve(&[]), Some(true));
        assert_eq!(s.value(2), Some(true));
        // An assumption holds for its call only.
        assert_eq!(s.solve(&[-2]), Some(false));
        assert_eq!(s.solve(&[1]), Some(true));
        assert_eq!(s.value(1), Some(true));
        s.add_clause(&[-2]);
        assert_eq!(s.solve(&[]), Some(false));
        assert_eq!(s.variables(), 2);
        s.set_limit(Some(10.0));
        assert_eq!(s.solve(&[]), Some(false));
        s.set_limit(None);
        assert_eq!(s.solve(&[]), Some(false));
    }

    #[test]
    fn a_solver_is_named_with_its_options() {
        assert!(named("cadical").unwrap()().signature().starts_with("CaDiCaL 1.9.5"));
        assert!(named("cadical:x=1").err().unwrap().0.contains("takes no options"));
        assert!(named("minisat").err().unwrap().0.contains("the solvers are cadical, bitwuzla"));
        if super::super::bitwuzla::available().is_err() {
            eprintln!("skipped: Bitwuzla isn't installed");
            return;
        }
        assert!(named("bitwuzla").unwrap()().signature().contains("produce-models, otherwise defaults"));
        let make = named("bitwuzla:preprocess=0").unwrap();
        assert!(make().signature().contains("produce-models, preprocess=0, otherwise defaults"), "{}", make().signature());
        assert!(named("bitwuzla:preprocess=7").err().unwrap().0.contains("from 0 to 1"));
        let mut words = named("bitwuzla-words:preprocess=0").unwrap()();
        assert!(words.signature().contains("the engine's terms") && words.signature().contains("preprocess=0"), "{}", words.signature());
        assert!(words.terms().is_some());
        assert!(named("bitwuzla").unwrap()().terms().is_none());
        assert!(cadical().terms().is_none());
    }
}
