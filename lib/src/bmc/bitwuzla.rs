//! [Bitwuzla](https://bitwuzla.github.io) behind the engine's [`Sat`] interface, for Phase 6 of the engine
//! priorities: the same checks and transcripts run on another solver, to tell the solver apart from the encoding.
//!
//! Here Bitwuzla is given the engine's own bit-blasted clauses, nothing word-level: a variable is a Boolean
//! constant, a clause the `or` of its literals, asserted, and a call `check_sat_assuming` the call's literals. So
//! the formula is the one CaDiCaL is given, and what differs is the solver: Bitwuzla's rewriting and preprocessing
//! of it, and the CaDiCaL inside Bitwuzla (2.1.2 in Bitwuzla 0.8.2) where the engine links 1.9.5.
//!
//! Nothing in `jvmcontract` links Bitwuzla. Its C API is loaded at run time from a build of it
//! (`lib/solvers/bitwuzla/build.sh`), which is found by the environment variable [`LIBRARY_ENV`], or else in
//! `~/tools/bitwuzla/current`. The enum values below are the C API's of version [`VERSION`], read from its headers,
//! so another version is refused rather than called with them.

use std::ffi::{c_char, c_int, c_void, CStr, CString};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::{Duration, Instant};

use super::bits::Lit;
use super::sat::Sat;
use crate::Error;

/// The environment variable naming Bitwuzla's library (`libbitwuzla.so`), or the directory it was installed in.
pub const LIBRARY_ENV: &str = "JVMCONTRACT_BITWUZLA";

/// The version whose C API this binding is written against.
pub const VERSION: &str = "0.8.2";

// The C API's enum values in Bitwuzla 0.8.2 (`include/bitwuzla/enums.h` and `option.h`, with
// `BITWUZLA_API_USE_C_ENUMS`), printed by a C program compiled against the installed headers.
const RESULT_SAT: c_int = 10;
const RESULT_UNSAT: c_int = 20;
const KIND_NOT: c_int = 9;
const KIND_OR: c_int = 10;
const OPT_PRODUCE_MODELS: c_int = 1;
const OPT_SAT_SOLVER: c_int = 11;

type Opts = c_void;
type Tm = c_void;
type Bzla = c_void;
type Sort = *const c_void;
type Term = *const c_void;

/// The C API's functions this binding calls, from the loaded library.
struct Api {
    library: PathBuf,
    version: unsafe extern "C" fn() -> *const c_char,
    options_new: unsafe extern "C" fn() -> *mut Opts,
    options_delete: unsafe extern "C" fn(*mut Opts),
    set_option: unsafe extern "C" fn(*mut Opts, c_int, u64),
    set_option_mode: unsafe extern "C" fn(*mut Opts, c_int, *const c_char),
    term_manager_new: unsafe extern "C" fn() -> *mut Tm,
    term_manager_delete: unsafe extern "C" fn(*mut Tm),
    new: unsafe extern "C" fn(*mut Tm, *const Opts) -> *mut Bzla,
    delete: unsafe extern "C" fn(*mut Bzla),
    set_termination_callback: unsafe extern "C" fn(*mut Bzla, Option<unsafe extern "C" fn(*mut c_void) -> i32>, *mut c_void),
    mk_bool_sort: unsafe extern "C" fn(*mut Tm) -> Sort,
    mk_false: unsafe extern "C" fn(*mut Tm) -> Term,
    mk_const: unsafe extern "C" fn(*mut Tm, Sort, *const c_char) -> Term,
    mk_term1: unsafe extern "C" fn(*mut Tm, c_int, Term) -> Term,
    mk_term: unsafe extern "C" fn(*mut Tm, c_int, u32, *const Term) -> Term,
    assert: unsafe extern "C" fn(*mut Bzla, Term),
    check_sat_assuming: unsafe extern "C" fn(*mut Bzla, u32, *const Term) -> c_int,
    get_value: unsafe extern "C" fn(*mut Bzla, Term) -> Term,
    term_value_get_bool: unsafe extern "C" fn(Term) -> bool,
}

// The loaded library's functions are plain C functions; the binding keeps no state of its own in `Api`.
unsafe impl Send for Api {}
unsafe impl Sync for Api {}

#[cfg(unix)]
mod dl {
    use std::ffi::{c_char, c_int, c_void};
    extern "C" {
        pub fn dlopen(filename: *const c_char, flag: c_int) -> *mut c_void;
        pub fn dlsym(handle: *mut c_void, symbol: *const c_char) -> *mut c_void;
        pub fn dlerror() -> *mut c_char;
    }
    pub const RTLD_NOW: c_int = 2;
}

/// Where the library is: [`LIBRARY_ENV`] (a file, or an install directory), else `~/tools/bitwuzla/current`.
pub fn library_path() -> Result<PathBuf, Error> {
    let named = std::env::var_os(LIBRARY_ENV).map(PathBuf::from);
    let root = match named {
        Some(p) if p.is_file() => return Ok(p),
        Some(p) => p,
        None => match std::env::var_os("HOME") {
            Some(home) => Path::new(&home).join("tools/bitwuzla/current"),
            None => return Err(Error::new(format!("Bitwuzla's library not found: {LIBRARY_ENV} is not set, and neither is HOME"))),
        },
    };
    let lib = root.join("lib");
    let mut candidates = vec![lib.join("libbitwuzla.so"), lib.join("libbitwuzla.dylib")];
    if let Ok(entries) = std::fs::read_dir(&lib) {
        let mut dirs: Vec<PathBuf> = entries.flatten().map(|e| e.path()).filter(|p| p.is_dir()).collect();
        dirs.sort();
        candidates.extend(dirs.into_iter().map(|d| d.join("libbitwuzla.so")));
    }
    candidates.into_iter().find(|p| p.is_file()).ok_or_else(|| Error::new(format!("Bitwuzla's library not found under {} (set {LIBRARY_ENV} to the library or its install directory; lib/solvers/bitwuzla/build.sh builds one)", root.display())))
}

static API: OnceLock<Result<Api, String>> = OnceLock::new();

/// The C API, loaded once per process; an error says why it can't be.
fn api() -> Result<&'static Api, Error> {
    API.get_or_init(|| load().map_err(|e| e.0)).as_ref().map_err(|e| Error::new(e.clone()))
}

/// Whether Bitwuzla can be loaded here, and if not, why: for tests and the solver's selection.
pub fn available() -> Result<(), Error> {
    api().map(|_| ())
}

#[cfg(not(unix))]
fn load() -> Result<Api, Error> {
    Err(Error::new("loading Bitwuzla is implemented for Unix only"))
}

#[cfg(unix)]
fn load() -> Result<Api, Error> {
    let library = library_path()?;
    let name = CString::new(library.as_os_str().as_encoded_bytes()).map_err(|_| Error::new("the library's path has a NUL in it"))?;
    // SAFETY: dlopen and dlsym are called with NUL-terminated strings; each symbol is cast to its declared C
    // signature in Bitwuzla 0.8.2's `bitwuzla.h`, and the version is checked before anything else is called.
    unsafe {
        let handle = dl::dlopen(name.as_ptr(), dl::RTLD_NOW);
        if handle.is_null() {
            let why = dl::dlerror();
            let why = if why.is_null() { "unknown".to_string() } else { CStr::from_ptr(why).to_string_lossy().into_owned() };
            return Err(Error::new(format!("cannot load Bitwuzla from {}: {why}", library.display())));
        }
        macro_rules! sym {
            ($name:literal) => {{
                let s = dl::dlsym(handle, concat!($name, "\0").as_ptr().cast());
                if s.is_null() {
                    return Err(Error::new(format!("{} has no {}", library.display(), $name)));
                }
                std::mem::transmute::<*mut c_void, _>(s)
            }};
        }
        let api = Api {
            library: library.clone(),
            version: sym!("bitwuzla_version"),
            options_new: sym!("bitwuzla_options_new"),
            options_delete: sym!("bitwuzla_options_delete"),
            set_option: sym!("bitwuzla_set_option"),
            set_option_mode: sym!("bitwuzla_set_option_mode"),
            term_manager_new: sym!("bitwuzla_term_manager_new"),
            term_manager_delete: sym!("bitwuzla_term_manager_delete"),
            new: sym!("bitwuzla_new"),
            delete: sym!("bitwuzla_delete"),
            set_termination_callback: sym!("bitwuzla_set_termination_callback"),
            mk_bool_sort: sym!("bitwuzla_mk_bool_sort"),
            mk_false: sym!("bitwuzla_mk_false"),
            mk_const: sym!("bitwuzla_mk_const"),
            mk_term1: sym!("bitwuzla_mk_term1"),
            mk_term: sym!("bitwuzla_mk_term"),
            assert: sym!("bitwuzla_assert"),
            check_sat_assuming: sym!("bitwuzla_check_sat_assuming"),
            get_value: sym!("bitwuzla_get_value"),
            term_value_get_bool: sym!("bitwuzla_term_value_get_bool"),
        };
        let version = CStr::from_ptr((api.version)()).to_string_lossy().into_owned();
        if version != VERSION {
            return Err(Error::new(format!("{} is Bitwuzla {version}; this binding is written against {VERSION}'s C API", library.display())));
        }
        Ok(api)
    }
}

/// When a call is to stop, for the termination callback; `None` for no limit.
struct Deadline {
    at: Option<Instant>,
}

unsafe extern "C" fn past_deadline(state: *mut c_void) -> i32 {
    // SAFETY: the state is the `Deadline` boxed in the `Bitwuzla` that set the callback, which outlives it.
    let deadline = unsafe { &*(state as *const Deadline) };
    deadline.at.is_some_and(|at| Instant::now() >= at) as i32
}

/// One Bitwuzla instance, given the engine's clauses as Boolean terms (SAT only), with a time limit per call.
pub struct Bitwuzla {
    api: &'static Api,
    tm: *mut Tm,
    options: *mut Opts,
    solver: *mut Bzla,
    boolean: Sort,
    /// The Boolean constant of each variable, by number less one; made when the variable is first used.
    variables: Vec<Term>,
    limit: Option<Duration>,
    deadline: Box<Deadline>,
    /// Whether the last call was satisfiable, so that a model may be read.
    model: bool,
}

impl std::fmt::Debug for Bitwuzla {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Bitwuzla({} variables)", self.variables.len())
    }
}

impl Bitwuzla {
    /// A new, empty instance, with models on and CaDiCaL as its SAT solver (Bitwuzla's default, set so that the
    /// signature can say it).
    pub fn new() -> Result<Bitwuzla, Error> {
        let api = api()?;
        // SAFETY: the C API is used as `bitwuzla.h` documents: options made and set before the instance, which is
        // made over a term manager that outlives it (both are deleted in `drop`, the instance first).
        unsafe {
            let options = (api.options_new)();
            (api.set_option)(options, OPT_PRODUCE_MODELS, 1);
            (api.set_option_mode)(options, OPT_SAT_SOLVER, c"cadical".as_ptr());
            let tm = (api.term_manager_new)();
            let solver = (api.new)(tm, options);
            let mut deadline = Box::new(Deadline { at: None });
            (api.set_termination_callback)(solver, Some(past_deadline), (&mut *deadline as *mut Deadline).cast());
            let boolean = (api.mk_bool_sort)(tm);
            Ok(Bitwuzla { api, tm, options, solver, boolean, variables: Vec::new(), limit: None, deadline, model: false })
        }
    }

    /// The library this instance was loaded from.
    pub fn library(&self) -> &Path {
        &self.api.library
    }

    fn variable(&mut self, var: i32) -> Term {
        let index = var as usize - 1;
        while self.variables.len() <= index {
            // SAFETY: a fresh constant of the Boolean sort, unnamed (the symbol may be NULL).
            let t = unsafe { (self.api.mk_const)(self.tm, self.boolean, std::ptr::null()) };
            self.variables.push(t);
        }
        self.variables[index]
    }

    fn literal(&mut self, lit: Lit) -> Term {
        let t = self.variable(lit.abs());
        // SAFETY: the negation of a Boolean term of this term manager.
        if lit < 0 { unsafe { (self.api.mk_term1)(self.tm, KIND_NOT, t) } } else { t }
    }
}

/// A new, empty [`Bitwuzla`], as [`super::Options::solver`] makes one. The library must load: the selection
/// ([`super::sat::configured`]) checks that first.
pub fn boxed() -> Box<dyn Sat> {
    match Bitwuzla::new() {
        Ok(b) => Box::new(b),
        Err(e) => panic!("{}", e.0),
    }
}

impl Drop for Bitwuzla {
    fn drop(&mut self) {
        // SAFETY: each was made in `new` and is deleted once, the instance before its term manager.
        unsafe {
            (self.api.delete)(self.solver);
            (self.api.term_manager_delete)(self.tm);
            (self.api.options_delete)(self.options);
        }
    }
}

impl Sat for Bitwuzla {
    fn signature(&self) -> String {
        // SAFETY: the version is a static NUL-terminated string.
        let version = unsafe { CStr::from_ptr((self.api.version)()) }.to_string_lossy().into_owned();
        format!("Bitwuzla {version} (the engine's clauses as Boolean terms; sat-solver cadical, produce-models, otherwise defaults)")
    }

    fn add_clause(&mut self, lits: &[Lit]) {
        let terms: Vec<Term> = lits.iter().map(|&l| self.literal(l)).collect();
        // SAFETY: Boolean terms of this term manager; `or` takes two or more.
        let clause = unsafe {
            match terms.len() {
                0 => (self.api.mk_false)(self.tm),
                1 => terms[0],
                n => (self.api.mk_term)(self.tm, KIND_OR, n as u32, terms.as_ptr()),
            }
        };
        // SAFETY: a Boolean term asserted on the instance of its term manager.
        unsafe { (self.api.assert)(self.solver, clause) };
        self.model = false;
    }

    fn set_limit(&mut self, seconds: Option<f32>) {
        self.limit = seconds.map(|s| Duration::from_secs_f32(s.max(0.0)));
    }

    fn solve(&mut self, assumptions: &[Lit]) -> Option<bool> {
        let terms: Vec<Term> = assumptions.iter().map(|&l| self.literal(l)).collect();
        self.deadline.at = self.limit.map(|l| Instant::now() + l);
        // SAFETY: Boolean terms of this term manager, as assumptions for this call only.
        let result = unsafe { (self.api.check_sat_assuming)(self.solver, terms.len() as u32, terms.as_ptr()) };
        self.deadline.at = None;
        let answer = match result {
            RESULT_SAT => Some(true),
            RESULT_UNSAT => Some(false),
            _ => None,
        };
        self.model = answer == Some(true);
        answer
    }

    fn value(&self, lit: Lit) -> Option<bool> {
        if !self.model {
            return None;
        }
        let t = *self.variables.get(lit.unsigned_abs() as usize - 1)?;
        // SAFETY: the model's value of a constant of this instance, read after a satisfiable call.
        let v = unsafe { (self.api.term_value_get_bool)((self.api.get_value)(self.solver, t)) };
        Some(if lit < 0 { !v } else { v })
    }

    fn variables(&self) -> i32 {
        self.variables.len() as i32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Bitwuzla if it is installed here; otherwise the test says why it was skipped.
    pub(crate) fn installed() -> Option<Bitwuzla> {
        match Bitwuzla::new() {
            Ok(b) => Some(b),
            Err(e) => {
                eprintln!("skipped: {}", e.0);
                None
            }
        }
    }

    #[test]
    fn bitwuzla_names_itself_and_answers_incrementally_under_assumptions() {
        let Some(mut s) = installed() else { return };
        assert!(s.signature().starts_with("Bitwuzla 0.8.2 "), "{}", s.signature());
        s.add_clause(&[1, 2]);
        s.add_clause(&[-1, 2]);
        assert_eq!(s.solve(&[]), Some(true));
        assert_eq!(s.value(2), Some(true));
        assert_eq!(s.value(-2), Some(false));
        // An assumption holds for its call only.
        assert_eq!(s.solve(&[-2]), Some(false));
        assert_eq!(s.value(2), None, "no model after an unsatisfiable call");
        assert_eq!(s.solve(&[1]), Some(true));
        assert_eq!(s.value(1), Some(true));
        s.add_clause(&[-2]);
        assert_eq!(s.solve(&[]), Some(false));
        assert_eq!(s.variables(), 2);
        s.set_limit(Some(10.0));
        assert_eq!(s.solve(&[]), Some(false));
        s.set_limit(None);
        assert_eq!(s.solve(&[]), Some(false));
        // The empty clause, and a variable first used in an assumption.
        let mut t = installed().unwrap();
        assert_eq!(t.solve(&[5]), Some(true));
        assert_eq!(t.value(5), Some(true));
        assert_eq!(t.variables(), 5);
        t.add_clause(&[]);
        assert_eq!(t.solve(&[]), Some(false));
    }

    #[test]
    fn a_call_past_its_limit_stops_with_no_answer() {
        let Some(mut s) = installed() else { return };
        // The pigeonhole principle for 10 pigeons in 9 holes: unsatisfiable, and hard for resolution.
        let (pigeons, holes) = (10, 9);
        let var = |p: i32, h: i32| p * holes + h + 1;
        for p in 0..pigeons {
            s.add_clause(&(0..holes).map(|h| var(p, h)).collect::<Vec<_>>());
        }
        for h in 0..holes {
            for p in 0..pigeons {
                for q in p + 1..pigeons {
                    s.add_clause(&[-var(p, h), -var(q, h)]);
                }
            }
        }
        s.set_limit(Some(0.05));
        let started = Instant::now();
        assert_eq!(s.solve(&[]), None);
        assert!(started.elapsed() < Duration::from_secs(5), "{:?}", started.elapsed());
    }
}
