//! [Bitwuzla](https://bitwuzla.github.io) behind the engine's [`Sat`] interface, for Phase 6 of the engine
//! priorities: the same checks and transcripts run on another solver, to tell the solver apart from the encoding.
//!
//! As `bitwuzla`, Bitwuzla is given the engine's own bit-blasted clauses, nothing word-level: a variable is a Boolean
//! constant, a clause the `or` of its literals, asserted, and a call `check_sat_assuming` the call's literals. So
//! the formula is the one CaDiCaL is given, and what differs is the solver: Bitwuzla's rewriting and preprocessing
//! of it, and the CaDiCaL inside Bitwuzla (2.1.2 in Bitwuzla 0.8.2) where the engine links 1.9.5.
//!
//! As `bitwuzla-words`, the word-level prototype, it takes the engine's terms ([`Terms`]): an input is a Boolean
//! constant as before, a gate the Boolean term of its function, and a word-level operation one bit-vector term
//! (`bvadd`, `bvsdiv`, `ite`, `bvult`, ...) over its operands, whose bits are `extract`s of it. Operand bits that are
//! a run of one such term's bits are that term or an `extract` of it, so the arithmetic of a method reaches Bitwuzla
//! as a word-level term over its inputs, and Bitwuzla bit-blasts what it has not rewritten away. Arrays stay the
//! engine's bounded cells, read and written through `ite`s over the index: no array theory.
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
use super::sat::{Gate, Sat, Terms, WordOp};
use crate::Error;

/// The environment variable naming Bitwuzla's library (`libbitwuzla.so`), or the directory it was installed in.
pub const LIBRARY_ENV: &str = "JVMCONTRACT_BITWUZLA";

/// The version whose C API this binding is written against.
pub const VERSION: &str = "0.8.2";

// The C API's enum values in Bitwuzla 0.8.2 (`include/bitwuzla/enums.h` and `option.h`, with
// `BITWUZLA_API_USE_C_ENUMS`), printed by a C program compiled against the installed headers.
const RESULT_SAT: c_int = 10;
const RESULT_UNSAT: c_int = 20;
const KIND_AND: c_int = 4;
const KIND_EQUAL: c_int = 6;
const KIND_NOT: c_int = 9;
const KIND_OR: c_int = 10;
const KIND_XOR: c_int = 11;
const KIND_ITE: c_int = 12;
const KIND_BV_ADD: c_int = 19;
const KIND_BV_AND: c_int = 20;
const KIND_BV_ASHR: c_int = 21;
const KIND_BV_CONCAT: c_int = 23;
const KIND_BV_MUL: c_int = 26;
const KIND_BV_OR: c_int = 32;
const KIND_BV_SDIV: c_int = 40;
const KIND_BV_SHL: c_int = 43;
const KIND_BV_SHR: c_int = 44;
const KIND_BV_SLT: c_int = 46;
const KIND_BV_SREM: c_int = 49;
const KIND_BV_SUB: c_int = 51;
const KIND_BV_ULT: c_int = 57;
const KIND_BV_XOR: c_int = 62;
const KIND_BV_EXTRACT: c_int = 63;
const OPT_PRODUCE_MODELS: c_int = 1;
const OPT_SAT_SOLVER: c_int = 11;
const NUM_OPTS: c_int = 54;

/// `BitwuzlaOptionInfo` in 0.8.2's `bitwuzla.h`: 120 bytes, with the offsets the C program printed (`lng` at 16,
/// the flags at 32, `numeric` at 40, `mode` at 72), which [`tests::the_option_info_has_the_c_layout`] checks.
#[repr(C)]
struct OptionInfo {
    opt: c_int,
    shrt: *const c_char,
    lng: *const c_char,
    description: *const c_char,
    is_numeric: bool,
    is_mode: bool,
    is_string: bool,
    numeric: [u64; 4],
    mode_cur: *const c_char,
    mode_dflt: *const c_char,
    num_modes: usize,
    modes: *const *const c_char,
    string: [*const c_char; 2],
}

/// An option set by its long name, as Bitwuzla's command line takes it (`preprocess=0`), on top of the binding's own
/// (`produce-models`, `sat-solver cadical`). [`settings`] reads a list of them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Setting {
    pub name: String,
    pub value: String,
}

/// The settings in `name=value,name=value` (an empty text is none). Whether Bitwuzla has each option and takes the
/// value is checked when an instance is made with them ([`Bitwuzla::with`]).
pub fn settings(text: &str) -> Result<Vec<Setting>, Error> {
    text.split(',').filter(|s| !s.trim().is_empty()).map(|item| match item.split_once('=') {
        Some((name, value)) if !name.trim().is_empty() && !value.trim().is_empty() => Ok(Setting { name: name.trim().to_string(), value: value.trim().to_string() }),
        _ => Err(Error::new(format!("Bitwuzla setting {item:?} is not name=value (as in preprocess=0)"))),
    }).collect()
}

/// The options the binding sets itself, which a setting may not change: models are read after every satisfiable
/// call, the limit is the termination callback's, and the solver must be an incremental one.
const OWN: &[&str] = &["produce-models", "time-limit-per", "sat-solver"];

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
    get_option_info: unsafe extern "C" fn(*mut Opts, c_int, *mut OptionInfo),
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
    mk_term2: unsafe extern "C" fn(*mut Tm, c_int, Term, Term) -> Term,
    mk_term3: unsafe extern "C" fn(*mut Tm, c_int, Term, Term, Term) -> Term,
    mk_term1_indexed2: unsafe extern "C" fn(*mut Tm, c_int, Term, u64, u64) -> Term,
    mk_bv_sort: unsafe extern "C" fn(*mut Tm, u64) -> Sort,
    mk_bv_value_uint64: unsafe extern "C" fn(*mut Tm, Sort, u64) -> Term,
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

/// The repository's record of its Bitwuzla build from source (`lib/solvers/bitwuzla/build.sh`).
const BUILD: &str = include_str!("../../solvers/bitwuzla/build.json");

/// Where a loaded library of `version` comes from, as a result records it: the library by file name and its
/// digest (none when it can't be read), and the build that `build` (a `build.json`) records, when it is of the same
/// version, with its commit and the CaDiCaL it links.
fn source(library: &Path, digest: Option<&str>, version: &str, build: &str) -> String {
    let name = library.canonicalize().ok().and_then(|p| p.file_name().map(|n| n.to_string_lossy().into_owned())).or_else(|| library.file_name().map(|n| n.to_string_lossy().into_owned())).unwrap_or_default();
    let loaded = match digest {
        Some(d) => format!("the shared library {name} (sha256:{d}), loaded at run time"),
        None => format!("the shared library {name}, loaded at run time (unreadable, so not hashed)"),
    };
    let record: Option<serde_json::Value> = serde_json::from_str(build).ok();
    let field = |key: &str| record.as_ref().and_then(|r| r.get(key)).and_then(|v| v.as_str()).map(str::to_string);
    match field("version") {
        Some(built) if built == version => {
            let commit = field("commit").map(|c| format!(" at commit {}", &c[..c.len().min(8)])).unwrap_or_default();
            let cadical = record.as_ref().and_then(|r| r.get("subprojectsFetched")).and_then(|v| v.as_array()).into_iter().flatten().filter_map(|v| v.as_str()).find_map(|s| s.strip_prefix("cadical-rel-")).map(|v| format!(", linking CaDiCaL {v} static")).unwrap_or_default();
            format!("{loaded}; lib/solvers/bitwuzla/build.json records version {built} built from source{commit}{cadical}")
        }
        Some(built) => format!("{loaded}; not the version lib/solvers/bitwuzla/build.json records ({built})"),
        None => format!("{loaded}; lib/solvers/bitwuzla/build.json records no version"),
    }
}

/// The digest of the library the API was loaded from, read once per process (there is one such library).
fn library_digest(library: &Path) -> Option<&'static str> {
    static DIGEST: OnceLock<Option<String>> = OnceLock::new();
    DIGEST.get_or_init(|| std::fs::read(library).ok().map(|bytes| crate::digest::sha256_hex(&bytes))).as_deref()
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
            get_option_info: sym!("bitwuzla_get_option_info"),
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
            mk_term2: sym!("bitwuzla_mk_term2"),
            mk_term3: sym!("bitwuzla_mk_term3"),
            mk_term1_indexed2: sym!("bitwuzla_mk_term1_indexed2"),
            mk_bv_sort: sym!("bitwuzla_mk_bv_sort"),
            mk_bv_value_uint64: sym!("bitwuzla_mk_bv_value_uint64"),
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

/// Sets one option on `options`, by its long name, once Bitwuzla's own description of it says the value is good.
///
/// # Safety
/// `options` is a live `BitwuzlaOptions` of `api`'s library.
unsafe fn set(api: &Api, options: *mut Opts, setting: &Setting) -> Result<(), Error> {
    let Setting { name, value } = setting;
    if OWN.contains(&name.as_str()) {
        return Err(Error::new(format!("Bitwuzla setting {name}: the binding sets it itself ({})", OWN.join(", "))));
    }
    for opt in 0..NUM_OPTS {
        let mut info = std::mem::MaybeUninit::<OptionInfo>::zeroed();
        // SAFETY: an option number below the count, and a struct of the C layout to fill.
        let info = unsafe {
            (api.get_option_info)(options, opt, info.as_mut_ptr());
            info.assume_init()
        };
        // SAFETY: the info's names and modes are static NUL-terminated strings of the library.
        let text = |p: *const c_char| if p.is_null() { String::new() } else { unsafe { CStr::from_ptr(p) }.to_string_lossy().into_owned() };
        if info.opt != opt || text(info.lng) != *name {
            continue;
        }
        if info.is_numeric {
            let [_, _, min, max] = info.numeric;
            let n: u64 = value.parse().map_err(|_| Error::new(format!("Bitwuzla setting {name}={value}: the value is a number, from {min} to {max}")))?;
            if n < min || n > max {
                return Err(Error::new(format!("Bitwuzla setting {name}={value}: the value is from {min} to {max}")));
            }
            // SAFETY: a numeric option, with a value in its range.
            unsafe { (api.set_option)(options, opt, n) };
            return Ok(());
        }
        if info.is_mode {
            // SAFETY: `num_modes` strings at `modes`, as the info describes them.
            let modes: Vec<String> = (0..info.num_modes).map(|i| text(unsafe { *info.modes.add(i) })).collect();
            if !modes.contains(value) {
                return Err(Error::new(format!("Bitwuzla setting {name}={value}: the modes are {}", modes.join(", "))));
            }
            let mode = CString::new(value.as_str()).map_err(|_| Error::new("a NUL in a Bitwuzla setting"))?;
            // SAFETY: a mode option, with one of its modes.
            unsafe { (api.set_option_mode)(options, opt, mode.as_ptr()) };
            return Ok(());
        }
        return Err(Error::new(format!("Bitwuzla setting {name}: only numeric and mode options can be set here")));
    }
    Err(Error::new(format!("Bitwuzla setting {name}: Bitwuzla {VERSION} has no option called that")))
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

/// One Bitwuzla instance, given the engine's clauses as Boolean terms (SAT only), or its terms as well ([`Terms`]),
/// with a time limit per call.
pub struct Bitwuzla {
    api: &'static Api,
    tm: *mut Tm,
    options: *mut Opts,
    solver: *mut Bzla,
    boolean: Sort,
    /// The Boolean term of each variable, by number less one: a constant made when an input is first used, or the
    /// term a gate or a word-level operation's bit is defined as.
    variables: Vec<Term>,
    /// Whether it takes the engine's terms (`bitwuzla-words`), not only its clauses.
    words: bool,
    /// For a variable that is bit `k` of a word-level term, the term and `k`, so that a run of its bits is read back
    /// as the term.
    bit_of: std::collections::HashMap<i32, (Term, u32, u32)>,
    /// The bit-vector term each operand was read as, by its bits.
    read: std::collections::HashMap<Vec<Lit>, Term>,
    /// The bit-vector sorts, by width.
    sorts: std::collections::HashMap<u64, Sort>,
    limit: Option<Duration>,
    deadline: Box<Deadline>,
    /// Whether the last call was satisfiable, so that a model may be read.
    model: bool,
    /// The settings it was made with, beyond the binding's own.
    settings: Vec<Setting>,
}

impl std::fmt::Debug for Bitwuzla {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Bitwuzla({} variables)", self.variables.len())
    }
}

impl Bitwuzla {
    /// A new, empty instance, with models on and CaDiCaL as its SAT solver (Bitwuzla's default, set so that the
    /// signature can say it), and otherwise Bitwuzla's defaults.
    pub fn new() -> Result<Bitwuzla, Error> {
        Bitwuzla::with(&[])
    }

    /// A new, empty instance as [`Bitwuzla::new`] makes one, with these options set as well. Each must be one of
    /// Bitwuzla's, numeric or a mode, not one the binding sets itself ([`OWN`]), and its value in range or one of
    /// its modes: the C API aborts the process on a value it refuses, so the binding checks first.
    pub fn with(settings: &[Setting]) -> Result<Bitwuzla, Error> {
        Bitwuzla::configured(settings, false)
    }

    /// A new, empty instance with these settings, as [`Bitwuzla::with`] makes one, that takes the engine's terms as
    /// well when `words` is set (`bitwuzla-words`).
    pub fn configured(settings: &[Setting], words: bool) -> Result<Bitwuzla, Error> {
        let api = api()?;
        // SAFETY: the C API is used as `bitwuzla.h` documents: options made and set before the instance, which is
        // made over a term manager that outlives it (both are deleted in `drop`, the instance first). An option's
        // info is read into a struct of the C layout, and its strings are static.
        unsafe {
            let options = (api.options_new)();
            (api.set_option)(options, OPT_PRODUCE_MODELS, 1);
            (api.set_option_mode)(options, OPT_SAT_SOLVER, c"cadical".as_ptr());
            for setting in settings {
                if let Err(e) = set(api, options, setting) {
                    (api.options_delete)(options);
                    return Err(e);
                }
            }
            let tm = (api.term_manager_new)();
            let solver = (api.new)(tm, options);
            let mut deadline = Box::new(Deadline { at: None });
            (api.set_termination_callback)(solver, Some(past_deadline), (&mut *deadline as *mut Deadline).cast());
            let boolean = (api.mk_bool_sort)(tm);
            Ok(Bitwuzla { api, tm, options, solver, boolean, variables: Vec::new(), words, bit_of: Default::default(), read: Default::default(), sorts: Default::default(), limit: None, deadline, model: false, settings: settings.to_vec() })
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

    /// Defines variable `var`, which no term has used yet, as the Boolean term `t`.
    fn define(&mut self, var: Lit, t: Term) {
        let index = var as usize - 1;
        assert!(index >= self.variables.len(), "variable {var} is defined after it was used");
        if index > 0 {
            self.variable(var - 1);
        }
        self.variables.push(t);
    }

    fn sort(&mut self, width: u64) -> Sort {
        let (api, tm) = (self.api, self.tm);
        // SAFETY: a bit-vector sort of a positive width.
        *self.sorts.entry(width).or_insert_with(|| unsafe { (api.mk_bv_sort)(tm, width) })
    }

    fn value_of(&mut self, value: u64, width: u64) -> Term {
        let sort = self.sort(width);
        // SAFETY: a value of the sort's width (at most 64 bits, the value masked to it).
        unsafe { (self.api.mk_bv_value_uint64)(self.tm, sort, if width >= 64 { value } else { value & ((1 << width) - 1) }) }
    }

    /// `bits` as one bit-vector term, most significant piece first: a run of a word-level term's bits is that term or
    /// an `extract` of it, a run of constants a value, and any other bit its literal as one bit.
    fn word_of(&mut self, bits: &[Lit]) -> Term {
        if let Some(&t) = self.read.get(bits) {
            return t;
        }
        let (api, tm) = (self.api, self.tm);
        let mut pieces: Vec<Term> = Vec::new();
        let mut i = 0;
        while i < bits.len() {
            let l = bits[i];
            if l == super::bits::TRUE || l == super::bits::FALSE {
                let mut j = i;
                let mut value = 0u64;
                while j < bits.len() && (bits[j] == super::bits::TRUE || bits[j] == super::bits::FALSE) {
                    if bits[j] == super::bits::TRUE {
                        value |= 1 << (j - i);
                    }
                    j += 1;
                }
                pieces.push(self.value_of(value, (j - i) as u64));
                i = j;
                continue;
            }
            if let Some(&(t, k, width)) = self.bit_of.get(&l) {
                let mut j = i + 1;
                while j < bits.len() && self.bit_of.get(&bits[j]).is_some_and(|&(u, m, _)| u == t && m == k + (j - i) as u32) {
                    j += 1;
                }
                let hi = k + (j - i) as u32 - 1;
                // SAFETY: an extract within the term's width.
                pieces.push(if k == 0 && hi + 1 == width { t } else { unsafe { (api.mk_term1_indexed2)(tm, KIND_BV_EXTRACT, t, u64::from(hi), u64::from(k)) } });
                i = j;
                continue;
            }
            let b = self.literal(l);
            let (one, zero) = (self.value_of(1, 1), self.value_of(0, 1));
            // SAFETY: an `ite` over a Boolean term with two bit-vector values of one sort.
            pieces.push(unsafe { (api.mk_term3)(tm, KIND_ITE, b, one, zero) });
            i += 1;
        }
        pieces.reverse();
        // SAFETY: a concatenation of two or more bit-vector terms.
        let t = if pieces.len() == 1 { pieces[0] } else { unsafe { (api.mk_term)(tm, KIND_BV_CONCAT, pieces.len() as u32, pieces.as_ptr()) } };
        self.read.insert(bits.to_vec(), t);
        t
    }
}

impl Terms for Bitwuzla {
    fn gate(&mut self, out: Lit, gate: Gate) {
        let (api, tm) = (self.api, self.tm);
        // SAFETY: Boolean operations over Boolean terms of this term manager.
        let t = unsafe {
            match gate {
                Gate::And(a, b) => (api.mk_term2)(tm, KIND_AND, self.literal(a), self.literal(b)),
                Gate::Xor(a, b) => (api.mk_term2)(tm, KIND_XOR, self.literal(a), self.literal(b)),
                Gate::Ite(c, a, b) => (api.mk_term3)(tm, KIND_ITE, self.literal(c), self.literal(a), self.literal(b)),
            }
        };
        self.define(out, t);
    }

    fn word(&mut self, outs: &[Lit], op: WordOp, operands: &[&[Lit]]) {
        let (api, tm) = (self.api, self.tm);
        let kind = match op {
            WordOp::Add => KIND_BV_ADD,
            WordOp::Sub => KIND_BV_SUB,
            WordOp::Mul => KIND_BV_MUL,
            WordOp::Div => KIND_BV_SDIV,
            WordOp::Rem => KIND_BV_SREM,
            WordOp::Shl => KIND_BV_SHL,
            WordOp::Shr => KIND_BV_ASHR,
            WordOp::Ushr => KIND_BV_SHR,
            WordOp::And => KIND_BV_AND,
            WordOp::Or => KIND_BV_OR,
            WordOp::Xor => KIND_BV_XOR,
            WordOp::Ite => KIND_ITE,
            WordOp::Ult => KIND_BV_ULT,
            WordOp::Slt => KIND_BV_SLT,
            WordOp::Eq => KIND_EQUAL,
        };
        let result = if op == WordOp::Ite {
            let c = self.literal(operands[0][0]);
            let (a, b) = (self.word_of(operands[1]), self.word_of(operands[2]));
            // SAFETY: an `ite` over a Boolean term and two bit-vector terms of one width.
            unsafe { (api.mk_term3)(tm, KIND_ITE, c, a, b) }
        } else {
            let (a, b) = (self.word_of(operands[0]), self.word_of(operands[1]));
            // SAFETY: a binary bit-vector operation over two terms of one width.
            unsafe { (api.mk_term2)(tm, kind, a, b) }
        };
        if op.compares() {
            self.define(outs[0], result);
            return;
        }
        let width = outs.len() as u32;
        let one = self.value_of(1, 1);
        for (k, &out) in outs.iter().enumerate() {
            // SAFETY: bit `k` of a bit-vector term of `width` bits, compared with the one-bit value one.
            let bit = unsafe { (api.mk_term2)(tm, KIND_EQUAL, (api.mk_term1_indexed2)(tm, KIND_BV_EXTRACT, result, k as u64, k as u64), one) };
            self.define(out, bit);
            self.bit_of.insert(out, (result, k as u32, width));
        }
        self.read.insert(outs.to_vec(), result);
    }
}

/// A new, empty [`Bitwuzla`] with Bitwuzla's defaults, as [`super::Options::solver`] makes one. The library must
/// load: the selection ([`super::sat::configured`]) checks that first.
pub fn boxed() -> Box<dyn Sat> {
    boxed_with(&[])
}

/// A new, empty [`Bitwuzla`] that takes the engine's terms (`bitwuzla-words`), with Bitwuzla's defaults.
pub fn boxed_words() -> Box<dyn Sat> {
    boxed_configured(&[], true)
}

/// A new, empty [`Bitwuzla`] with these settings, which [`Bitwuzla::with`] has already accepted once.
pub fn boxed_with(settings: &[Setting]) -> Box<dyn Sat> {
    boxed_configured(settings, false)
}

/// A new, empty [`Bitwuzla`] with these settings that takes the engine's terms when `words` is set, once
/// [`Bitwuzla::configured`] has accepted them.
pub fn boxed_configured(settings: &[Setting], words: bool) -> Box<dyn Sat> {
    match Bitwuzla::configured(settings, words) {
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
        let set: String = self.settings.iter().map(|s| format!(", {}={}", s.name, s.value)).collect();
        let given = if self.words { "the engine's terms: word-level operations as bit-vector terms, gates as Boolean terms" } else { "the engine's clauses as Boolean terms" };
        format!("Bitwuzla {version} ({given}; sat-solver cadical, produce-models{set}, otherwise defaults)")
    }

    fn record(&self) -> crate::statement::Sat {
        // SAFETY: as in `signature`.
        let version = unsafe { CStr::from_ptr((self.api.version)()) }.to_string_lossy().trim().to_string();
        let mut configuration = vec![
            if self.words { "given the engine's terms: word-level operations as bit-vector terms, gates as Boolean terms" } else { "given the engine's clauses as Boolean terms" }.to_string(),
            "sat-solver cadical".to_string(),
            "produce-models".to_string(),
        ];
        configuration.extend(self.settings.iter().map(|s| format!("{}={}", s.name, s.value)));
        configuration.push("otherwise Bitwuzla's default options".to_string());
        configuration.push("incremental: one solver per run of the checker, each query solved under assumptions (check_sat_assuming)".to_string());
        configuration.push("the run's deadline through Bitwuzla's termination callback".to_string());
        crate::statement::Sat { solver: "Bitwuzla".into(), version: Some(version.clone()), source: source(&self.api.library, library_digest(&self.api.library), &version, BUILD), configuration }
    }

    fn terms(&mut self) -> Option<&mut dyn Terms> {
        if self.words { Some(self) } else { None }
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
    fn bitwuzla_records_its_version_its_build_and_its_options_as_a_results_evidence() {
        let build = r#"{"version": "0.8.2", "commit": "61bdc637a291c27597fc04263328ecd29d36cc12", "subprojectsFetched": ["cadical-rel-2.1.2", "symfpu"]}"#;
        let missing = Path::new("/nonexistent/libbitwuzla.so.0");
        assert_eq!(source(missing, None, "0.8.2", build), "the shared library libbitwuzla.so.0, loaded at run time (unreadable, so not hashed); lib/solvers/bitwuzla/build.json records version 0.8.2 built from source at commit 61bdc637, linking CaDiCaL 2.1.2 static");
        assert!(source(missing, None, "0.9.0", build).ends_with("; not the version lib/solvers/bitwuzla/build.json records (0.8.2)"));
        assert!(source(missing, None, "0.8.2", "{}").ends_with("; lib/solvers/bitwuzla/build.json records no version"));
        let recorded: serde_json::Value = serde_json::from_str(BUILD).unwrap();
        assert_eq!(recorded["version"].as_str(), Some(VERSION), "the repository's build is of the version the binding is written against");
        let Some(_) = installed() else { return };
        for (words, given) in [(false, "given the engine's clauses as Boolean terms"), (true, "given the engine's terms: word-level operations as bit-vector terms, gates as Boolean terms")] {
            let s = Bitwuzla::configured(&settings("preprocess=0").unwrap(), words).unwrap();
            let r = s.record();
            assert_eq!((r.solver.as_str(), r.version.as_deref()), ("Bitwuzla", Some(VERSION)));
            assert!(r.source.starts_with("the shared library libbitwuzla.so"), "{}", r.source);
            assert!(r.source.contains(" (sha256:") && r.source.ends_with("built from source at commit 61bdc637, linking CaDiCaL 2.1.2 static"), "{}", r.source);
            assert_eq!(r.configuration[..4], [given, "sat-solver cadical", "produce-models", "preprocess=0"]);
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
    fn the_option_info_has_the_c_layout() {
        assert_eq!(std::mem::size_of::<OptionInfo>(), 120);
        assert_eq!(std::mem::offset_of!(OptionInfo, lng), 16);
        assert_eq!(std::mem::offset_of!(OptionInfo, is_numeric), 32);
        assert_eq!(std::mem::offset_of!(OptionInfo, numeric), 40);
        assert_eq!(std::mem::offset_of!(OptionInfo, mode_cur), 72);
        assert_eq!(std::mem::offset_of!(OptionInfo, string), 104);
    }

    #[test]
    fn settings_are_read_checked_against_bitwuzla_and_named_in_the_signature() {
        let off = |text: &str| settings(text).unwrap();
        assert_eq!(off(""), vec![]);
        assert_eq!(off("preprocess=0, rewrite-level=1"), vec![Setting { name: "preprocess".into(), value: "0".into() }, Setting { name: "rewrite-level".into(), value: "1".into() }]);
        assert!(settings("preprocess").is_err());
        assert!(settings("=0").is_err());
        let Some(_) = installed() else { return };
        let mut s = Bitwuzla::with(&off("preprocess=0,rewrite-level=0")).unwrap();
        assert!(s.signature().ends_with("(the engine's clauses as Boolean terms; sat-solver cadical, produce-models, preprocess=0, rewrite-level=0, otherwise defaults)"), "{}", s.signature());
        s.add_clause(&[1, 2]);
        s.add_clause(&[-1, 2]);
        assert_eq!(s.solve(&[-2]), Some(false));
        assert_eq!(s.solve(&[1]), Some(true));
        assert_eq!(s.value(2), Some(true));
        let refused = |text: &str| Bitwuzla::with(&off(text)).unwrap_err().0;
        assert!(refused("preprocess=2").contains("from 0 to 1"), "{}", refused("preprocess=2"));
        assert!(refused("preprocess=no").contains("is a number"));
        assert!(refused("bv-solver=fast").contains("the modes are preprop, prop, bitblast"), "{}", refused("bv-solver=fast"));
        assert!(refused("no-such-option=1").contains("has no option called that"));
        assert!(refused("produce-models=0").contains("sets it itself"));
        assert!(refused("write-cnf=/tmp/x").contains("only numeric and mode"));
        // A mode, set.
        assert!(Bitwuzla::with(&off("bv-solver=prop")).is_ok());
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
