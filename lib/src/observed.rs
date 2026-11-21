//! A class initializer observed on a JVM: the static state it left there, for the tool's own checker to start from.
//!
//! A library's initializer builds tables before anything else happens: Spring's `ClassUtils` fills maps of the
//! primitive and common classes through an `IdentityHashMap`, a `HashSet` and a map of soft references, which the
//! checker does not run (floating point, reference queues, an iteration order that follows identity hash codes).
//! Such an initializer has no input: what it leaves is a fact about the class path and the JDK, and a JVM says what
//! it is. `prove --observed-initializer CLASS` (and `equivalence`) asks for that: the class is initialized in a JVM
//! of its own, first thing, on the check's class path, its static fields are read by reflection, and the checker,
//! where a use initializes the class, takes that state instead of running the `<clinit>`
//! ([`crate::bmc::Options::observed`]). Its superclasses are initialized as any class's are, before it.
//!
//! **What is held** of a static field's value: null, an integral or boolean primitive, a String (its code units,
//! and whether it is the pooled one a literal of that content is), a `Class`, a `java.util.HashMap` itself (no
//! subclass) whose keys are Strings or null and whose values are held, an empty exact ConcurrentHashMap with
//! its single-threaded registry model selected, and an array of integral primitives or of
//! held references. A final application class with only final integral and String fields is held with every
//! superclass through Object. A final application enum can also hold its own constants, including their
//! inherited name and ordinal. The checker binds the bootstrap getters to their actual fields and refuses
//! other bootstrap field accesses. The observer binds each declaring class's bytes and field layout. Two fields
//! that hold one object hold one object here. Any other value (a `float` or an `IdentityHashMap`) is **not held**: the field has no value in the
//! check, and a read of it before the check writes it is refused by name ([`Observed::fields`]), so nothing is
//! made up for it.
//!
//! **What a result that used one rests on**, which each such result states ([`assumption`]): that the initializer
//! leaves the same state in every run, whatever ran before it (it reads nothing a run could have changed, and
//! nothing that differs from one JVM to the next shows in what is held), and that the objects it leaves are its
//! own (none is also held by another class's state, where the check would have a second object). The observation
//! is one run on one JDK, the check's; it is evidence of the tested kind, never a proof about the initializer. An
//! initializer that throws on the JVM is not observed: the check is refused, with what it threw.
//!
//! **What it is bound to** ([`On`]): the observer says what it observed on, and a run whose observation does not
//! say it, or says something the check does not hold, ends there by name; nothing falls back to a Java default.
//! - The class file: its sha256 as the JVM's class loader read it must be the class file the tool reads of the
//!   class on the same class path, in the same order (the JVM's `java.class.path` is the one it was given).
//! - The classes it initialized besides itself (as the JVM logged them, `-Xlog:class+init`), its superclasses and
//!   superinterfaces among them: each is, in the check, initialized as it is without the observed initializer (a
//!   supertype before the class, any other where the check first uses it), so its static state just after the
//!   observed initialization must be the state it has initialized first thing in a JVM of its own. An initializer
//!   that wrote another class's static (`A.<clinit> { B.x = 1; k = 7; }`, `lib/tests/observed_countermodels.rs`), a
//!   superclass's (`ob.Derived`) or a cell of a superinterface's array (`ob.Filled`, both
//!   `lib/tests/fixtures/rule-countermodels`) is refused, with the field, and so is one whose class file is not the
//!   tool's. A value such a class holds that the observation does not hold is compared by its description, which
//!   the observer reads in full (`Describe` in the observer): an object of the application by every field its
//!   classes declare, a lambda by the method it calls (from its class's constant pool, which the observer's JVM is
//!   given access to) and the values it captured, a JDK collection by its elements, a float by its bits. So a write
//!   into an object another class holds (`bc.Boxed`) and a lambda put in place of another of its class
//!   (`bc.Rehooked`, both `lib/tests/fixtures/binding-countermodels`) are refused, and a value the observer does
//!   not describe (an object of the JDK it has no reading of, one whose class extends a JDK class with state) is
//!   refused, with why. A lambda's hidden class is named by what it was defined from (`R$$Lambda`), without the
//!   address a JVM appends to its name, which differs from run to run (`claims.Hooked`, `lib/tests/claims.rs`).
//! - With `--observed-runtime '{"preinitializeTogether":true}'`, startup precedes the checked entry. The named
//!   roots are initialized in their specified order, and their transitive application classes share one object
//!   table. The checker binds every class file, installs the fields and all represented aliases, and refuses
//!   overlapping captures, absent application supertypes and operations that inspect opaque state. A reference
//!   can pass through an application constructor into a field until such an operation. This scope includes any
//!   cross-class registration the JVM made. It assumes that unrecorded external state and aliases do not affect
//!   the checked call. The ordinary first-use observation still compares each transitive class independently.
//! - The default locale: one whose language is Turkish, Azeri or Lithuanian is refused, since the check takes the
//!   JVM's default to be none of them ([`crate::bmc::strings::LOCALE_ASSUMPTION`]); any other is stated. The default
//!   time zone (which the JDK reads from `user.timezone` or the machine, as `ob.Zoned`'s `TimeZone.getDefault()`
//!   does) is stated too. The observer reads both again after the initialization, and the system properties: an
//!   initialization that changed one (`Locale.setDefault`, as `bc.Relocaled` does, `TimeZone.setDefault`,
//!   `System.setProperty`) is refused, with the setting, since the check runs what follows under the one before.
//! - The system properties the class path's code read during the initialization (through `System.getProperty`,
//!   `Integer.getInteger`, `Long.getLong` or `Boolean.getBoolean`, or by key through the map `System.getProperties()`
//!   gives, as `ob.Bypassed` does), each with the value it had or that it was not set: stated. One that read the
//!   properties as a whole (their keys, entries or values, a copy) is refused, since the observation lists only the
//!   ones read by name. The JDK's reads of its own configuration, as it opens a JAR or first uses one of its
//!   classes, are not listed: the check takes the JDK at its defaults throughout.
//! - `System.getenv` requires an empty process environment verified by the subject JVM. A caller can select
//!   it with `--observed-runtime '{"emptyEnvironment":true}'`. The observer records only emptiness.
//!   `ProcessBuilder.environment` and reads under an inherited nonempty environment remain unbound.
//! - `rootWorkingDirectory: true` launches the observation at Unix / and checks its JVM and File bases before
//!   and after startup. This binds lexical File.getAbsolutePath/getAbsoluteFile. Canonical paths and filesystem
//!   provider calls still need their own evidence.
//! - A read of `Runtime.availableProcessors()` requires a positive, immutable HotSpot
//!   `-XX:ActiveProcessorCount=N` matching the observed JVM. This count enters the statement and state digest.
//! - The JDK: its release must be the check's, and its vendor and home are stated.
//!
//! What is still assumed, and stated: that a write of the value a field already had is none; that the settings it
//! read (the locale, the time zone, the properties) are those of the run the result is about. Not seen: a read of
//! the environment by reflection or through a JDK method other than the two, a read of the properties through a
//! method the observer does not override (`equals`, `hashCode`), the JDK's own state other than those settings (a
//! logger registered with its logging, as spring-jcl's `LogFactory` may do), what a `ReferenceQueue` holds (said as
//! one: the collector's), the state of an object the observer describes through its public methods beyond what
//! they say, and identity: a class's object said alike after the initialization and alone may be one object shared
//! with the observed class, which the check holds apart.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

use crate::Error;

/// The program that observes one class, as Java: javac compiles it and a JVM runs it once for each class.
const SOURCE: &str = include_str!("observed/ObservedInitializer.java");
const CLASS: &str = "ObservedInitializer";
pub(crate) const ENUM: &str = "java/lang/Enum";
/// The line of its output that holds the observation.
const MARK: &str = "@observed ";
/// How long the JVM is given for one class.
const TIMEOUT: Duration = Duration::from_secs(60);

/// A value as the observation has it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Slot {
    Null,
    /// An integral primitive, a `char` or a `boolean` (0 or 1).
    Number(i64),
    /// The object at this index of [`Observed::objects`].
    Object(usize),
    /// Not held, and what it was: `an object of java.util.IdentityHashMap`.
    Unheld(String),
}

/// An object the observation holds.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Object {
    /// A String: its code units, and whether it is the string pool's String of that content.
    Str { units: Vec<u16>, interned: bool },
    /// A `Class`, by the internal name of a class (`java/lang/Boolean`), the descriptor of an array's (`[I`) or
    /// the name of a primitive type (`int`).
    Class(String),
    /// A `java.util.HashMap`: its entries, in the order the JVM iterated them.
    Map(Vec<(Slot, Slot)>),
    /// An exact ConcurrentHashMap observed empty. Its references share the same object number.
    EmptyConcurrentMap,
    /// Final application value, with every inherited instance field and its defining bytes.
    Value(Vec<ValueClass>),
    /// An array: its element type's descriptor and its cells.
    Array { element: String, cells: Vec<Slot> },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValueClass {
    pub name: String,
    pub sha256: String,
    pub fields: BTreeMap<(String, String), Slot>,
}

/// The static state one class's initializer left on a JVM.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Observed {
    /// The JVM's `java.version`.
    pub jdk: String,
    /// Digest of the JVM's fields and object table before a previous version's class names are relocated.
    pub state_sha256: String,
    /// Each static field the class declares, by name.
    pub fields: BTreeMap<String, Slot>,
    pub objects: Vec<Object>,
    /// If requested, the other initialized application classes share the root's object table.
    pub(crate) joint_fields: Option<BTreeMap<String, BTreeMap<String, Slot>>>,
    /// Additional explicitly requested roots in actual initialization order, with their class digests.
    pub(crate) additional_roots: Vec<(String, String)>,
    /// For a class of the previous version of a pair ([`observe_previous`]): its own name, the one it was observed
    /// under on the previous version's class path. The check holds it under another.
    pub previous: Option<String>,
    /// What it was observed on.
    pub on: On,
}

/// What an observation was observed on, as the observer's JVM said it ([`observe`] checks it against the check's).
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct On {
    /// The sha256 of the class file the JVM's class loader read, and the location it came from.
    pub sha256: String,
    pub from: Option<String>,
    /// The JVM's class path, in order (the observer's own directory first).
    pub classpath: Vec<String>,
    /// The JDK's `java.vendor` and `java.home`.
    pub vendor: String,
    pub home: String,
    /// The default locale's language tag, and the defaults for formatting and display.
    pub locale: String,
    pub format: String,
    pub display: String,
    /// The default time zone's id (`Asia/Tokyo`).
    pub zone: String,
    /// Both standard calendar factories met the fixed-UTC Gregorian profile on the observed JVM.
    pub utc_gregorian: bool,
    /// Runtime.availableProcessors() on a JVM whose read-only ActiveProcessorCount pins it.
    pub fixed_processors: Option<i32>,
    pub empty_environment: bool,
    pub root_working_directory: bool,
    /// Each system property the initialization read, in the order it first did, and the value it had.
    pub properties: Vec<(String, Option<String>)>,
    /// The first class of the class path that read the system properties as a whole, if one did.
    pub all_properties: Option<String>,
    /// Each setting of the JDK the initialization changed, as the observer read it again after it: the default
    /// locale (each category), the default time zone, a system property set or removed.
    pub changed: Vec<String>,
    /// Each class of the class path the initialization initialized besides the class, its supertypes among them.
    pub initialized: Vec<Initialized>,
}

/// A class an observed initialization initialized: its class file's sha256 and its static state then, as the
/// observer prints a class's (`fields` and `objects`), to be compared with its state alone.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Initialized {
    pub name: String,
    pub sha256: String,
    pub state: serde_json::Value,
}

/// The observations a check was given, by the class's internal name.
pub type Observations = BTreeMap<String, Observed>;

/// Launch settings for a separately scoped initializer observation and its comparison JVMs.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, serde::Deserialize)]
#[serde(default, rename_all = "camelCase", deny_unknown_fields)]
pub struct Runtime {
    pub processors: Option<std::num::NonZeroI32>,
    pub empty_environment: bool,
    pub preinitialize_together: bool,
    pub root_working_directory: bool,
}

impl std::str::FromStr for Runtime {
    type Err = String;
    fn from_str(text: &str) -> Result<Self, Self::Err> {
        let r: Self = serde_json::from_str(text).map_err(|e| format!("invalid observed runtime: {e}"))?;
        if r == Self::default() || r.processors.is_some_and(|n| n.get() < 1) {
            return Err("provide a positive processor count or enable a supported startup setting".into());
        }
        Ok(r)
    }
}

/// What a result that took the observed state of `class`'s initializer rests on.
pub fn assumption(class: &str, observed: &Observed) -> String {
    let jdk = &observed.jdk;
    let on = match &observed.previous {
        Some(own) => format!("the previous version's class path, where it is {}", own.replace('/', ".")),
        None => "the check's class path".to_string(),
    };
    let bound = &observed.on;
    let processors = bound.fixed_processors.map(|n| format!("; Runtime.availableProcessors() was pinned to {n} (-XX:ActiveProcessorCount={n}) throughout initialization")).unwrap_or_default();
    let environment = if bound.empty_environment { ", with an empty process environment throughout initialization" } else { "" };
    let cwd = if bound.root_working_directory { ", with the process working directory and JVM absolute-path base both at the Unix root /" } else { "" };
    let short = |h: &str| h.chars().take(12).collect::<String>();
    let properties = if bound.properties.is_empty() {
        "it read no system property".to_string()
    } else {
        let each: Vec<String> = bound.properties.iter().map(|(k, v)| match v { Some(v) => format!("{k} = {v:?}"), None => format!("{k}, not set") }).collect();
        format!("it read the system properties {}, and the result holds where each is as it was", each.join("; "))
    };
    let initialized = if let Some(members) = &observed.joint_fields {
        let names: Vec<_> = members.keys().map(|name| name.replace('/', ".")).collect();
        format!("; before the checked entry, one JVM snapshot supplies this class and {} other initialized application classes [{}], including their cross-class static writes and shared object identities", members.len(), names.join(", "))
    } else if bound.initialized.is_empty() {
        String::new()
    } else {
        let names: Vec<String> = bound.initialized.iter().map(|i| i.name.replace('/', ".")).collect();
        format!("; it initialized {} besides, and left each in the state the class has initialized alone, every value of it compared (one the observation does not hold by what the observer read of it: an object's fields, a lambda's method and captured values, a collection's elements)", names.join(", "))
    };
    let ownership = if observed.joint_fields.is_some() { "its noncanonical objects have no aliases outside that snapshot and unrecorded external effects do not affect the checked call" } else { "the objects it leaves are held by no other class" };
    format!(
        "the class initializer of {} was not run by the checker: its static state is the one a JVM (JDK {jdk}, {}) left after initializing the selected roots on {on}, from the class file the check reads (sha256 {}), in a JVM whose default locale was {} (formatting {}, display {}) and default time zone {}; {properties}{processors}{environment}{cwd}{initialized}; and it is taken to leave that state in every run (it reads nothing a run could have changed before it, and {ownership})",
        class.replace('/', "."),
        bound.vendor,
        short(&bound.sha256),
        bound.locale,
        bound.format,
        bound.display,
        bound.zone,
    )
}

/// Observes each of `classes` (binary or internal names) on `classpath`, in a JVM of its own, with the working
/// files under `work`, and checks what each was observed on ([`On`]). An error where there is no JDK, the class is
/// not found, its initializer throws, or the observation is not bound to what the check holds.
pub fn observe(classes: &[String], classpath: &[PathBuf], work: &Path) -> Result<Observations, Error> {
    observe_on(classes, classpath, work, Runtime::default())
}

fn observe_on(classes: &[String], classpath: &[PathBuf], work: &Path, runtime: Runtime) -> Result<Observations, Error> {
    if runtime.processors.is_some_and(|n| n.get() < 1) { return Err(Error::new("--observed-runtime requires a positive processor count")); }
    let mut out = Observations::new();
    if classes.is_empty() {
        return Ok(out);
    }
    let home = crate::jimage::JImage::find_java_home().ok_or_else(|| Error::new("--observed-initializer: no JDK to observe a class initializer on (set JAVA_HOME)"))?;
    // Absolute: the JVM runs in this folder, and is given the log's path in it (an option and an argument).
    let dir = std::path::absolute(work.join("observed"))?;
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir)?;
    let source = dir.join(format!("{CLASS}.java"));
    std::fs::write(&source, SOURCE)?;
    let javac = home.join("bin").join("javac");
    let compiled = Command::new(&javac).args(["-proc:none", "-Xlint:none", "-nowarn", "-d"]).arg(&dir).arg(&source).output().map_err(|e| Error::new(format!("{}: {e}", javac.display())))?;
    if !compiled.status.success() {
        return Err(Error::new(format!("--observed-initializer: javac did not compile the observer: {}", String::from_utf8_lossy(&compiled.stderr).trim())));
    }
    let absolute = |p: &Path| std::path::absolute(p).unwrap_or_else(|_| p.to_path_buf());
    let entries: Vec<PathBuf> = std::iter::once(absolute(&dir)).chain(classpath.iter().map(|e| absolute(e))).collect();
    let class_path = std::env::join_paths(&entries).map_err(|e| Error::new(format!("a class path entry cannot be joined: {e}")))?;
    let mut tool = crate::classpath::ClassPath::new().with_jdk(crate::jimage::JImage::open(&home)?);
    for entry in &entries[1..] {
        tool.add(entry)?;
    }
    let additional: Vec<String> = if runtime.preinitialize_together { classes.iter().skip(1).map(|c| c.replace('/', ".")).collect() } else { vec![] };
    let jvm = Jvm { java: home.join("bin").join("java"), class_path, dir: dir.clone(), runtime, additional };
    let mut alone: BTreeMap<String, serde_json::Value> = BTreeMap::new();
    for class in classes.iter().take(if runtime.preinitialize_together { 1 } else { classes.len() }) {
        let internal = class.replace('.', "/");
        let binary = internal.replace('/', ".");
        let log = dir.join(format!("{binary}.init.log"));
        let line = jvm.run(&binary, Some(&log))?;
        let observed = parse(&binary, &line)?;
        if runtime.preinitialize_together != observed.joint_fields.is_some()
            || !observed.additional_roots.iter().map(|(name, _)| name.replace('/', ".")).eq(jvm.additional.iter().cloned())
            || runtime.root_working_directory && !observed.on.root_working_directory
            || runtime.empty_environment && !observed.on.empty_environment
            || runtime.processors.is_some_and(|n| observed.on.fixed_processors != Some(n.get())) {
            return Err(Error::new(format!("--observed-initializer {binary}: the observing JVM did not confirm its requested process settings")));
        }
        bind(&binary, &internal, &observed.on, &entries, &tool)?;
        bind_values(&binary, &observed, &tool)?;
        for ran in std::iter::once(internal.as_str()).chain(observed.on.initialized.iter().map(|i| i.name.as_str())) {
            if let Some((setting, call)) = unbound_setting(&tool, ran, &observed.on)? {
                let whose = if ran == internal { "its code".to_string() } else { format!("its initialization initialized {}, whose code", ran.replace('/', ".")) };
                return Err(Error::new(format!(
                    "--observed-initializer {binary}: {whose} reads {setting} ({call}), which the observation cannot bind"
                )));
            }
        }
        for other in &observed.on.initialized {
            let name = other.name.replace('/', ".");
            if tool_sha256(&tool, &other.name)?.as_deref() != Some(other.sha256.as_str()) {
                return Err(Error::new(format!("--observed-initializer {binary}: its initialization initialized {name}, whose class file the JVM read is not the one the tool reads of it on this class path")));
            }
            if observed.joint_fields.is_some() { continue; }
            if !alone.contains_key(&other.name) {
                let line = jvm.run(&name, None)?;
                alone.insert(other.name.clone(), state(&name, &line, &observed.on)?);
            }
            if let Some(value) = undescribed(&other.state).or_else(|| undescribed(&alone[&other.name])) {
                return Err(Error::new(format!(
                    "--observed-initializer {binary}: its initialization initialized {name}, {value}, so whether the initialization wrote into it is not known, and the check cannot take it"
                )));
            }
            if let Some(field) = changed(&other.state, &alone[&other.name]) {
                return Err(Error::new(format!(
                    "--observed-initializer {binary}: its initialization initialized {name} and left it other than it is initialized alone ({field}): it wrote another class's static state, which an observation does not carry (it holds only {binary}'s own fields), so the check cannot take it"
                )));
            }
        }
        out.insert(internal, observed);
    }
    Ok(out)
}

/// The JVM an observation runs on: the observer first on the check's class path.
struct Jvm {
    java: PathBuf,
    class_path: std::ffi::OsString,
    dir: PathBuf,
    runtime: Runtime,
    additional: Vec<String>,
}

impl Jvm {
    /// Runs the observer on `binary`, with its class initializations logged to `log` where given, and returns the
    /// line of the observation.
    fn run(&self, binary: &str, log: Option<&Path>) -> Result<String, Error> {
        let suffix = if log.is_some() { "" } else { ".alone" };
        let stdout = self.dir.join(format!("{binary}{suffix}.stdout"));
        let stderr = self.dir.join(format!("{binary}{suffix}.stderr"));
        let mut command = Command::new(&self.java);
        if self.runtime.empty_environment { command.env_clear(); }
        if let Some(n) = self.runtime.processors { command.arg(format!("-XX:ActiveProcessorCount={n}")); }
        command.args(["-Xmx256m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData"]);
        // The observer reads a lambda's constant pool to say which method it calls (its Describe and Pool).
        command.args(["--add-exports", "java.base/jdk.internal.access=ALL-UNNAMED", "--add-exports", "java.base/jdk.internal.reflect=ALL-UNNAMED"]);
        if let Some(log) = log {
            let _ = std::fs::remove_file(log);
            command.arg(format!("-Xlog:class+init=info:file={}::filecount=0", log.display()));
        }
        command.arg("-cp").arg(&self.class_path).arg(CLASS).arg(binary);
        if let Some(log) = log {
            command.arg(log);
            if self.runtime.preinitialize_together { command.arg("together").args(&self.additional); }
        }
        let mut child = command
            .current_dir(if self.runtime.root_working_directory { Path::new("/") } else { &self.dir })
            .stdout(std::fs::File::create(&stdout)?)
            .stderr(std::fs::File::create(&stderr)?)
            .spawn()
            .map_err(|e| Error::new(format!("cannot run the JVM: {e}")))?;
        let started = Instant::now();
        while child.try_wait()?.is_none() {
            if started.elapsed() > TIMEOUT {
                let _ = child.kill();
                let _ = child.wait();
                return Err(Error::new(format!("--observed-initializer {binary}: the JVM did not finish within {} s", TIMEOUT.as_secs())));
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        let text = std::fs::read_to_string(&stdout).unwrap_or_default();
        match text.lines().find_map(|l| l.strip_prefix(MARK)) {
            Some(line) => Ok(line.to_string()),
            None => {
                let said = std::fs::read_to_string(&stderr).unwrap_or_default();
                let tail: Vec<&str> = said.lines().rev().take(3).collect();
                Err(Error::new(format!("--observed-initializer {binary}: the JVM gave no observation{}", if tail.is_empty() { String::new() } else { format!(": {}", tail.into_iter().rev().collect::<Vec<_>>().join(" / ")) })))
            }
        }
    }
}

/// The sha256 of the class file the tool reads of `internal` on its class path, or none.
fn tool_sha256(tool: &crate::classpath::ClassPath, internal: &str) -> Result<Option<String>, Error> {
    Ok(tool.application_bytes(internal)?.map(|b| crate::digest::sha256_hex(&b)))
}

/// Bind the two final public getters read by the observer to the fields used by this JDK.
/// In particular, no value is supplied for JDKs that also cache an identity hash in Enum.
fn bind_enum_base(observed: &Observed, base: &ValueClass, tool: &crate::classpath::ClassPath) -> Result<bool, Error> {
    use crate::classfile::{Insn, Kind};
    let Some(image) = tool.jdk() else { return Ok(false) };
    let Some(bytes) = image.read_class(ENUM)? else { return Ok(false) };
    let Some(loaded) = tool.load(ENUM)? else { return Ok(false) };
    if loaded.origin != crate::classpath::Origin::Jdk || crate::digest::sha256_hex(&bytes) != base.sha256 || base.fields.len() != 2 {
        return Ok(false);
    }
    for (name, descriptor, kind) in [("name", "Ljava/lang/String;", Kind::Ref), ("ordinal", "I", Kind::Int)] {
        let Some(method) = loaded.class.method(name, &format!("(){descriptor}")).filter(|m| m.is_final()) else { return Ok(false) };
        let Some(insns) = method.code.as_ref().filter(|c| c.exception_table.is_empty()).and_then(|c| c.instructions().ok()) else { return Ok(false) };
        let [(_, Insn::Load(Kind::Ref, 0)), (_, Insn::GetField(index)), (_, Insn::Return(Some(result)))] = insns.as_slice() else { return Ok(false) };
        let member = loaded.class.pool.member(*index)?;
        if *result != kind || member.owner != ENUM || member.name != name || member.descriptor != descriptor { return Ok(false); }
        match base.fields.get(&(name.into(), descriptor.into())) {
            Some(Slot::Object(id)) if kind == Kind::Ref && matches!(observed.objects.get(*id), Some(Object::Str { .. })) => {}
            Some(Slot::Number(n)) if kind == Kind::Int && i32::try_from(*n).is_ok() => {}
            _ => return Ok(false),
        }
    }
    Ok(true)
}

/// Check every declaring class independently. The JVM's class-loader resource and
/// the verifier's selected bytes must agree, and no inherited field may be omitted.
fn bind_values(binary: &str, observed: &Observed, tool: &crate::classpath::ClassPath) -> Result<(), Error> {
    for object in &observed.objects {
        let Object::Value(chain) = object else { continue };
        for (i, part) in chain.iter().enumerate() {
            let mismatch = || Error::new(format!("--observed-initializer {binary}: immutable value {} does not match its selected application class bytes or complete field layout", part.name));
            if part.name == ENUM {
                let owner = &chain[0].name;
                if i != 1 || chain.len() != 2 || (*owner != binary.replace('.', "/") && !observed.joint_fields.as_ref().is_some_and(|m| m.contains_key(owner)))
                    || !tool.application(&chain[0].name)?.is_some_and(|cf| cf.is_enum()) || !bind_enum_base(observed, part, tool)? {
                    return Err(mismatch());
                }
                continue;
            }
            let cf = tool.application(&part.name)?.ok_or_else(mismatch)?;
            let parent = chain.get(i + 1).map_or("java/lang/Object", |c| &c.name);
            if tool_sha256(tool, &part.name)?.as_deref() != Some(part.sha256.as_str()) || (i == 0 && !cf.is_final())
                || cf.super_class.as_deref() != Some(parent) { return Err(mismatch()); }
            let fields: Vec<_> = cf.fields.iter().filter(|f| !f.is_static()).collect();
            let names: std::collections::BTreeSet<_> = fields.iter().map(|f| &f.name).collect();
            if fields.len() != part.fields.len() || names.len() != fields.len() { return Err(mismatch()); }
            for f in fields {
                let Some(slot) = part.fields.get(&(f.name.clone(), f.descriptor.clone())) else { return Err(mismatch()); };
                let fits = match (f.descriptor.as_str(), slot) {
                    ("Ljava/lang/String;", Slot::Null) | ("J", Slot::Number(_)) => true,
                    ("Ljava/lang/String;", Slot::Object(n)) => matches!(observed.objects.get(*n), Some(Object::Str { .. })),
                    ("Z", Slot::Number(n)) => matches!(n, 0 | 1),
                    ("B", Slot::Number(n)) => i8::try_from(*n).is_ok(),
                    ("S", Slot::Number(n)) => i16::try_from(*n).is_ok(),
                    ("C", Slot::Number(n)) => u16::try_from(*n).is_ok(),
                    ("I", Slot::Number(n)) => i32::try_from(*n).is_ok(),
                    _ => false,
                };
                if !f.is_final() || !fits { return Err(mismatch()); }
            }
        }
    }
    Ok(())
}

/// Settings outside the observation's dynamic recorder. Scan the observed class and the application classes
/// initialized with it. A reference in an unexecuted method can conservatively refuse an observation.
fn unbound_setting(tool: &crate::classpath::ClassPath, internal: &str, on: &On) -> Result<Option<(&'static str, String)>, Error> {
    let Some(bytes) = tool.application_bytes(internal)? else { return Ok(None) };
    let class = crate::classfile::ClassFile::parse(&bytes).map_err(|e| Error::new(format!("--observed-initializer: the class file of {} does not parse: {e}", internal.replace('/', "."))))?;
    for (index, constant) in class.pool.entries().iter().enumerate() {
        use crate::classfile::Constant;
        let (index, handle) = match constant {
            Constant::MethodRef { .. } | Constant::InterfaceMethodRef { .. } => (index as u16, false),
            Constant::MethodHandle { reference_index, .. } => (*reference_index, true),
            _ => continue,
        };
        let Ok(member) = class.pool.member(index) else { continue };
        let setting = match (member.owner.as_str(), member.name.as_str()) {
            ("java/lang/System", "getenv") if on.empty_environment && matches!(member.descriptor.as_str(), "()Ljava/util/Map;" | "(Ljava/lang/String;)Ljava/lang/String;") => continue,
            ("java/lang/System", "getenv") | ("java/lang/ProcessBuilder", "environment") => "the environment",
            ("java/lang/System", "getProperty" | "getProperties") if handle => "a system property through a method handle",
            ("java/util/Properties" | "java/util/Hashtable", "putIfAbsent" | "replace" | "replaceAll" | "merge" | "compute" | "computeIfAbsent" | "computeIfPresent") => "a possible system property through a map update",
            ("java/lang/invoke/MethodHandles$Lookup", name) if name.starts_with("find") || name.starts_with("unreflect") => "a dynamically looked-up member",
            ("java/lang/Runtime", "availableProcessors") if member.descriptor == "()I" && on.fixed_processors.is_some() => continue,
            ("java/lang/Runtime", "availableProcessors" | "maxMemory" | "totalMemory" | "freeMemory") => "the JVM resource configuration",
            ("java/io/File", "getAbsolutePath") if member.descriptor == "()Ljava/lang/String;" && on.root_working_directory => continue,
            ("java/io/File", "getAbsoluteFile") if member.descriptor == "()Ljava/io/File;" && on.root_working_directory => continue,
            ("java/io/File", "getAbsolutePath" | "getAbsoluteFile" | "getCanonicalPath" | "getCanonicalFile")
            | ("java/nio/file/Path", "toAbsolutePath" | "toRealPath") => "the JVM working directory",
            ("java/nio/charset/Charset", "defaultCharset") => "the default charset",
            ("java/lang/String", "getBytes") if member.descriptor == "()[B" => "the default charset",
            ("java/lang/String", "<init>") if matches!(member.descriptor.as_str(), "([B)V" | "([BII)V") => "the default charset",
            _ => continue,
        };
        return Ok(Some((setting, member.display())));
    }
    Ok(None)
}

/// Checks that an observation was made on what the check holds: the class path in its order, the class file, and the
/// settings it read ([`settings`]).
fn bind(binary: &str, internal: &str, on: &On, entries: &[PathBuf], tool: &crate::classpath::ClassPath) -> Result<(), Error> {
    let given: Vec<String> = entries.iter().map(|e| e.display().to_string()).collect();
    if on.classpath != given {
        return Err(Error::new(format!("--observed-initializer {binary}: the JVM that observed it ran on the class path {}, not the check's {}", on.classpath.join(":"), given.join(":"))));
    }
    match tool_sha256(tool, internal)? {
        Some(sha) if sha == on.sha256 => {}
        Some(_) => return Err(Error::new(format!("--observed-initializer {binary}: the class file the JVM initialized (from {}) is not the one the tool reads of the class on the same class path", on.from.as_deref().unwrap_or("an unnamed location")))),
        None => return Err(Error::new(format!("--observed-initializer {binary}: the tool reads no class file of it on the check's class path, where the JVM read one (from {})", on.from.as_deref().unwrap_or("an unnamed location")))),
    }
    settings(binary, on)
}

/// Checks the settings an observation was made under: a default locale the check's lowering of a String agrees
/// with, and system properties read one by one.
fn settings(binary: &str, on: &On) -> Result<(), Error> {
    let language = on.locale.split(['-', '_']).next().unwrap_or("");
    if matches!(language, "tr" | "az" | "lt") {
        return Err(Error::new(format!(
            "--observed-initializer {binary}: it was observed in a JVM whose default locale is {}, and the check takes the default locale to be none of Turkish, Azeri or Lithuanian, under which String.toLowerCase() differs: the observation is not of the run the check is about (observe it under another default locale, as the JVM's settings, JAVA_TOOL_OPTIONS among them, give it)",
            on.locale
        )));
    }
    if !on.changed.is_empty() {
        return Err(Error::new(format!(
            "--observed-initializer {binary}: its initialization changed the JDK's settings ({}), which an observation does not carry: the check would run what follows under the settings before it, so it cannot take it",
            on.changed.join("; ")
        )));
    }
    if let Some(reader) = &on.all_properties {
        return Err(Error::new(format!(
            "--observed-initializer {binary}: {reader} read the system properties as a whole (their keys, entries or values, through System.getProperties()), and an observation lists only the properties read by name, so the check cannot take it"
        )));
    }
    Ok(())
}

/// The first value of a class's state (a field, or a cell or entry of an object a field holds) that the observation
/// neither holds nor describes, said with why ([`changed`] compares what is described).
fn undescribed(state: &serde_json::Value) -> Option<String> {
    let lacks = |v: &serde_json::Value| -> Option<String> {
        let what = v.get("u")?.as_str()?;
        if v.get("d").is_some_and(|d| d.is_string()) {
            return None;
        }
        Some(format!("{what}, which the observation neither holds nor describes ({})", v.get("why").and_then(|w| w.as_str()).unwrap_or("the observer said nothing of it")))
    };
    for f in state.get("fields").and_then(|f| f.as_array()).into_iter().flatten() {
        if let Some(said) = f.get("value").and_then(lacks) {
            return Some(format!("whose field {} holds {said}", f.get("name").and_then(|n| n.as_str()).unwrap_or("")));
        }
    }
    for o in state.get("objects").and_then(|o| o.as_array()).into_iter().flatten() {
        let held = o.get("cells").or_else(|| o.get("entries")).and_then(|c| c.as_array());
        if let Some(said) = held.into_iter().flatten().find_map(lacks) {
            return Some(format!("whose fields hold an object that holds {said}"));
        }
    }
    None
}

/// The first field whose value differs between two states of one class, said as the field and its two values.
fn changed(after: &serde_json::Value, alone: &serde_json::Value) -> Option<String> {
    let fields = |s: &serde_json::Value| -> Vec<(String, serde_json::Value)> {
        s.get("fields").and_then(|f| f.as_array()).map(|f| f.iter().map(|f| (f.get("name").and_then(|n| n.as_str()).unwrap_or("").to_string(), f.get("value").cloned().unwrap_or_default())).collect()).unwrap_or_default()
    };
    let say = |v: &serde_json::Value| -> String {
        if v.is_null() {
            return "null".into();
        }
        if let Some(n) = v.get("n") {
            return n.to_string();
        }
        if let Some(u) = v.get("u").and_then(|u| u.as_str()) {
            return match v.get("d").and_then(|d| d.as_str()) {
                Some(d) if d.chars().count() > 200 => format!("{u} ({}…)", d.chars().take(200).collect::<String>()),
                Some(d) => format!("{u} ({d})"),
                None => u.to_string(),
            };
        }
        "an object the observation holds".into()
    };
    let (a, b) = (fields(after), fields(alone));
    for (name, value) in &a {
        match b.iter().find(|(n, _)| n == name) {
            Some((_, other)) if other != value => return Some(format!("its field {name} was {} after it and is {} alone", say(value), say(other))),
            None => return Some(format!("its field {name}, which it does not have alone")),
            _ => {}
        }
    }
    if after.get("objects") != alone.get("objects") {
        return Some("an object its fields hold".into());
    }
    None
}

/// A class's static state alone, from the observer's line without a log: `fields` and `objects`.
fn state(binary: &str, line: &str, on: &On) -> Result<serde_json::Value, Error> {
    let json: serde_json::Value = serde_json::from_str(line).map_err(|e| Error::new(format!("--observed-initializer {binary}: the observation is not one the tool reads ({e})")))?;
    if let Some(threw) = json.get("threw").and_then(|t| t.as_str()) {
        return Err(Error::new(format!("--observed-initializer {binary}: initialized alone on the JVM, the class threw {threw}")));
    }
    if fixed_processors(&json)? != on.fixed_processors || empty_environment(&json)? != on.empty_environment
        || root_directory(&json)? != on.root_working_directory {
        return Err(Error::new(format!("--observed-initializer {binary}: initialized alone under different process settings")));
    }
    Ok(serde_json::json!({ "fields": json.get("fields"), "objects": json.get("objects") }))
}

fn empty_environment(settings: &serde_json::Value) -> Result<bool, Error> {
    settings.get("emptyEnvironment").map(|v| v.as_bool().ok_or_else(|| Error::new("--observed-initializer: invalid process environment observation")))
        .unwrap_or(Ok(false))
}

fn root_directory(settings: &serde_json::Value) -> Result<bool, Error> {
    settings.get("rootWorkingDirectory").map(|v| v.as_bool().ok_or_else(|| Error::new("--observed-initializer: invalid JVM working directory observation")))
        .unwrap_or(Ok(false))
}

fn fixed_processors(settings: &serde_json::Value) -> Result<Option<i32>, Error> {
    match settings.get("fixedProcessors") {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(n) => n.as_i64().and_then(|v| i32::try_from(v).ok()).filter(|v| *v > 0).map(Some)
            .ok_or_else(|| Error::new("--observed-initializer: invalid fixed JVM processor count")),
    }
}

/// [`observe`] for a check: the observations must be of the JDK the check's facts about the JDK are of.
pub fn observe_for(classes: &[String], classpath: &[PathBuf], work: &Path) -> Result<Observations, Error> {
    observe_for_runtime(classes, classpath, work, Runtime::default())
}

pub(crate) fn observe_for_runtime(classes: &[String], classpath: &[PathBuf], work: &Path, runtime: Runtime) -> Result<Observations, Error> {
    let observed = observe_on(classes, classpath, work, runtime)?;
    if let (Some(release), Some((class, o))) = (crate::bmc::gaps::jdk_release(), observed.iter().next()) {
        if o.jdk != release {
            return Err(Error::new(format!("--observed-initializer {}: the JVM that observed it is JDK {}, and the check's JDK is {release}", class.replace('/', "."), o.jdk)));
        }
    }
    Ok(observed)
}

/// [`observe_for`] for classes of the previous version of a pair: each is observed under its own name on the
/// previous version's class path, and the observation is then of the copy the check holds (`before/x/Y`), a
/// `Class` it holds being the copy's where the check holds a copy of that class. An error where it holds the
/// `Class` of a class of the previous version that the check has no copy of.
pub fn observe_previous(classes: &[String], previous: &crate::relocate::Previous, work: &Path) -> Result<Observations, Error> {
    observe_previous_on(classes, previous, work, Runtime::default())
}

pub(crate) fn observe_previous_on(classes: &[String], previous: &crate::relocate::Previous, work: &Path, runtime: Runtime) -> Result<Observations, Error> {
    use crate::relocate::Found;
    let mut out = Observations::new();
    for (class, mut observed) in observe_for_runtime(classes, &previous.classpath, &work.join("previous"), runtime)? {
        let binary = class.replace('/', ".");
        if !previous.relocated.contains(&class) {
            return Err(Error::new(format!("--observed-initializer {binary}: the check holds no copy of the previous version's class")));
        }
        let held = format!("{}/{class}", previous.prefix);
        for (name, _) in &mut observed.additional_roots {
            let Found::Class(copy) = previous.find(name) else { return Err(Error::new(format!("no copy of previous initialized root {name}"))); };
            *name = copy;
        }
        if let Some(fields) = observed.joint_fields.take() {
            let mut relocated = BTreeMap::new();
            for (name, state) in fields {
                let Found::Class(copy) = previous.find(&name) else {
                    return Err(Error::new(format!("--observed-initializer {binary}: the check holds no copy of the jointly initialized previous class {name}")));
                };
                relocated.insert(copy, state);
            }
            observed.joint_fields = Some(relocated);
        }
        for object in &mut observed.objects {
            if let Object::Value(chain) = object {
                for part in chain.iter_mut().filter(|p| p.name != ENUM) {
                    let Found::Class(held) = previous.find(&part.name) else {
                        return Err(Error::new(format!("--observed-initializer {binary}: the check holds no copy of the previous version's immutable value class {}", part.name)));
                    };
                    part.name = held;
                }
                continue;
            }
            let name = match object {
                Object::Class(name) => name,
                Object::Array { element, .. } => element,
                _ => continue,
            };
            // Class literals use internal names; an array element is a descriptor, possibly another array.
            let (open, element, close) = match name.rfind("[L") {
                Some(at) if name.ends_with(';') => (&name[..at + 2], &name[at + 2..name.len() - 1], ";"),
                None if name.starts_with('L') && name.ends_with(';') => ("L", &name[1..name.len() - 1], ";"),
                _ if name.starts_with('[') => continue,
                _ => ("", name.as_str(), ""),
            };
            match previous.find(element) {
                Found::Class(now) => *name = format!("{open}{now}{close}"),
                Found::Elsewhere => {}
                Found::NotCopied => return Err(Error::new(format!("--observed-initializer {binary}: the previous version's initializer left the Class of {}, a class of its class path that the check holds no copy of", element.replace('/', ".")))),
            }
        }
        observed.previous = Some(class);
        out.insert(held, observed);
    }
    Ok(out)
}

/// One observation, from the observer's line.
pub fn parse(binary: &str, line: &str) -> Result<Observed, Error> {
    let bad = |what: &str| Error::new(format!("--observed-initializer {binary}: the observation is not one the tool reads ({what})"));
    let json: serde_json::Value = serde_json::from_str(line).map_err(|e| bad(&e.to_string()))?;
    if let Some(threw) = json.get("threw").and_then(|t| t.as_str()) {
        return Err(Error::new(format!("--observed-initializer {binary}: on the JVM the class's initialization threw {threw}, and an observation is of an initializer that completes: the check has to run this one, or meet it as the gap it is")));
    }
    let slot = |v: &serde_json::Value| -> Result<Slot, Error> {
        if v.is_null() {
            return Ok(Slot::Null);
        }
        if let Some(n) = v.get("n").and_then(|n| n.as_i64()) {
            return Ok(Slot::Number(n));
        }
        if let Some(o) = v.get("o").and_then(|o| o.as_u64()) {
            return Ok(Slot::Object(o as usize));
        }
        match v.get("u").and_then(|u| u.as_str()) {
            Some(u) => Ok(Slot::Unheld(u.to_string())),
            None => Err(bad("a value")),
        }
    };
    let slots = |v: Option<&serde_json::Value>| -> Result<Vec<Slot>, Error> { v.and_then(|c| c.as_array()).ok_or_else(|| bad("a list"))?.iter().map(&slot).collect() };
    let mut objects = Vec::new();
    for o in json.get("objects").and_then(|o| o.as_array()).ok_or_else(|| bad("objects"))? {
        objects.push(match o.get("k").and_then(|k| k.as_str()) {
            Some("string") => {
                let units = o.get("units").and_then(|u| u.as_array()).ok_or_else(|| bad("a string"))?.iter().map(|u| u.as_u64().and_then(|u| u16::try_from(u).ok()).ok_or_else(|| bad("a code unit"))).collect::<Result<_, _>>()?;
                Object::Str { units, interned: o.get("interned").and_then(|i| i.as_bool()).ok_or_else(|| bad("a string"))? }
            }
            Some("class") => Object::Class(o.get("name").and_then(|n| n.as_str()).ok_or_else(|| bad("a class"))?.to_string()),
            Some("concurrentMap") if o.get("entries").and_then(|v| v.as_array()).is_some_and(Vec::is_empty) => Object::EmptyConcurrentMap,
            Some("map") => {
                let flat = slots(o.get("entries"))?;
                if flat.len() % 2 != 0 {
                    return Err(bad("a map's entries"));
                }
                Object::Map(flat.chunks(2).map(|kv| (kv[0].clone(), kv[1].clone())).collect())
            }
            Some("array") => Object::Array { element: o.get("element").and_then(|e| e.as_str()).ok_or_else(|| bad("an array"))?.to_string(), cells: slots(o.get("cells"))? },
            Some("value") => {
                let string = |v: &serde_json::Value, k: &str| v.get(k).and_then(|t| t.as_str()).map(str::to_owned).ok_or_else(|| bad("an immutable value field or class"));
                let classes = o["classes"].as_array().filter(|v| !v.is_empty()).ok_or_else(|| bad("an immutable value hierarchy"))?;
                let mut hierarchy = Vec::new();
                for class in classes {
                    let mut fields = BTreeMap::new();
                    for field in class["fields"].as_array().ok_or_else(|| bad("immutable value fields"))? {
                        let key = (string(field, "name")?, string(field, "type")?);
                        let value = slot(field.get("value").ok_or_else(|| bad("a missing immutable field value"))?)?;
                        if fields.insert(key, value).is_some() { return Err(bad("a repeated immutable field")); }
                    }
                    hierarchy.push(ValueClass { name: string(class, "name")?, sha256: string(class, "sha256")?, fields });
                }
                Object::Value(hierarchy)
            }
            _ => return Err(bad("an object")),
        });
    }
    let fields_of = |state: &serde_json::Value| -> Result<BTreeMap<String, Slot>, Error> {
        let mut fields = BTreeMap::new();
        for f in state.get("fields").and_then(|f| f.as_array()).ok_or_else(|| bad("fields"))? {
            let name = f.get("name").and_then(|n| n.as_str()).ok_or_else(|| bad("a field"))?;
            let value = slot(f.get("value").ok_or_else(|| bad("a field"))?)?;
            if fields.insert(name.to_string(), value).is_some() { return Err(bad("a repeated static field")); }
        }
        Ok(fields)
    };
    let fields = fields_of(&json)?;
    let on = json.get("on").ok_or_else(|| Error::new(format!("--observed-initializer {binary}: the observation does not say what it was observed on (the class file, the class path, the locale, the properties it read, the classes it initialized), and an observation that does not is not taken")))?;
    let text = |v: &serde_json::Value, key: &str| -> Result<String, Error> { v.get(key).and_then(|t| t.as_str()).map(String::from).ok_or_else(|| bad(key)) };
    let list = |key: &str| -> Result<&Vec<serde_json::Value>, Error> { on.get(key).and_then(|l| l.as_array()).ok_or_else(|| bad(key)) };
    let locale = on.get("locale").ok_or_else(|| bad("the locale"))?;
    let mut state = serde_json::json!({"fields": json.get("fields"), "objects": json.get("objects")});
    let joint_fields = if on.get("preinitializeTogether").map(|v| v.as_bool().ok_or_else(|| bad("preinitializeTogether"))).transpose()?.unwrap_or(false) {
        let mut members = BTreeMap::new();
        for member in list("initialized")? {
            let name = text(member, "name")?;
            if member.get("objects").is_some() || name == binary.replace('.', "/") || members.insert(name, fields_of(member)?).is_some() {
                return Err(bad("the jointly initialized classes or their shared object table"));
            }
        }
        state["jointlyInitialized"] = on["initialized"].clone();
        Some(members)
    } else { None };
    let mut additional_roots = vec![];
    if let Some(roots) = on.get("additionalRoots") {
        for value in roots.as_array().ok_or_else(|| bad("additional startup roots"))? {
            let name = value.as_str().ok_or_else(|| bad("additional startup root name"))?;
            let member = list("initialized")?.iter().find(|v| v["name"].as_str() == Some(name)).ok_or_else(|| bad("an unbound additional root"))?;
            if joint_fields.is_none() || additional_roots.iter().any(|(n, _)| n == name) { return Err(bad("additional startup roots")); }
            additional_roots.push((name.to_owned(), text(member, "sha256")?));
        }
        if !additional_roots.is_empty() { state["additionalRoots"] = roots.clone(); }
    }
    let on = On {
        sha256: text(on, "sha256")?,
        from: on.get("from").and_then(|f| f.as_str()).map(String::from),
        classpath: list("classpath")?.iter().map(|e| e.as_str().map(String::from).ok_or_else(|| bad("the class path"))).collect::<Result<_, _>>()?,
        vendor: text(on, "vendor")?,
        home: text(on, "home")?,
        locale: text(locale, "default")?,
        format: text(locale, "format")?,
        display: text(locale, "display")?,
        zone: text(on, "zone")?,
        utc_gregorian: on.get("utcGregorian").and_then(|v| v.as_bool()).unwrap_or(false),
        fixed_processors: fixed_processors(on)?,
        empty_environment: empty_environment(on)?,
        root_working_directory: root_directory(on)?,
        properties: list("properties")?.iter().map(|p| Ok((text(p, "name")?, p.get("value").and_then(|v| v.as_str()).map(String::from)))).collect::<Result<_, Error>>()?,
        all_properties: match on.get("allProperties") {
            Some(serde_json::Value::Null) => None,
            Some(serde_json::Value::String(reader)) => Some(reader.clone()),
            _ => return Err(bad("allProperties")),
        },
        changed: list("changed")?.iter().map(|c| c.as_str().map(String::from).ok_or_else(|| bad("changed"))).collect::<Result<_, _>>()?,
        initialized: list("initialized")?
            .iter()
            .map(|i| Ok(Initialized { name: text(i, "name")?, sha256: text(i, "sha256")?, state: serde_json::json!({ "fields": i.get("fields"), "objects": i.get("objects") }) }))
            .collect::<Result<_, Error>>()?,
    };
    if let Some(n) = on.fixed_processors { state["fixedProcessors"] = n.into(); }
    if on.empty_environment { state["emptyEnvironment"] = true.into(); }
    if on.root_working_directory { state["rootWorkingDirectory"] = true.into(); }
    let state_sha256 = crate::digest::sha256_hex(state.to_string().as_bytes());
    let observed = Observed { jdk: json.get("jdk").and_then(|j| j.as_str()).ok_or_else(|| bad("the JDK"))?.to_string(), state_sha256, fields, objects, joint_fields, additional_roots, previous: None, on };
    let within = |s: &Slot| !matches!(s, Slot::Object(i) if *i >= observed.objects.len());
    let joint_slots = observed.joint_fields.iter().flat_map(|m| m.values()).flat_map(|fields| fields.values());
    let all = observed.fields.values().chain(joint_slots).chain(observed.objects.iter().flat_map(|o| match o {
        Object::Map(entries) => entries.iter().flat_map(|(k, v)| [k, v]).collect::<Vec<_>>(),
        Object::Array { cells, .. } => cells.iter().collect(),
        Object::Value(chain) => chain.iter().flat_map(|c| c.fields.values()).collect(),
        _ => Vec::new(),
    }));
    if !all.into_iter().all(within) {
        return Err(bad("an object's number"));
    }
    Ok(observed)
}

impl Observed {
    /// Why the value is not held, if it is not: what it, or the first value under it that is not, was.
    pub fn unheld(&self, slot: &Slot) -> Option<String> {
        fn walk(o: &Observed, slot: &Slot, seen: &mut Vec<usize>) -> Option<String> {
            match slot {
                Slot::Unheld(what) => Some(what.clone()),
                Slot::Object(i) if !seen.contains(i) => {
                    seen.push(*i);
                    match &o.objects[*i] {
                        Object::Map(entries) => entries.iter().find_map(|(k, v)| walk(o, k, seen).or_else(|| walk(o, v, seen))),
                        Object::Array { cells, .. } => cells.iter().find_map(|c| walk(o, c, seen)),
                        _ => None,
                    }
                }
                _ => None,
            }
        }
        walk(self, slot, &mut Vec::new())
    }
}

/// `String.hashCode()` of these code units.
pub fn string_hash(units: &[u16]) -> i32 {
    units.iter().fold(0i32, |h, &u| h.wrapping_mul(31).wrapping_add(i32::from(u)))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// What an observer says it observed on, as it writes it: one property read, one class initialized besides.
    const ON: &str = r#""on":{"sha256":"ab12","from":"file:/app/","classpath":["/w/observed","/app"],"vendor":"Eclipse Adoptium","home":"/jdk","locale":{"default":"en-US","format":"de-DE","display":"en-US"},"zone":"Asia/Tokyo","properties":[{"name":"p.value","value":"xyz"},{"name":"p.unset","value":null}],"allProperties":null,"changed":[],"initialized":[{"name":"p/B","sha256":"cd34","fields":[{"name":"x","value":{"n":1}}],"objects":[]}]}"#;

    fn on(fields: &str) -> String {
        format!("{{{fields},{ON}}}")
    }

    #[test]
    fn an_observation_is_read_as_the_observer_writes_it() {
        let line = on(r#""jdk":"25.0.5","fields":[{"name":"A","value":{"o":2}},{"name":"N","value":{"n":-3}},{"name":"Z","value":null},{"name":"W","value":{"u":"an object of java.util.IdentityHashMap"}},{"name":"T","value":{"o":3}}],"objects":[{"k":"string","units":[105,110,116],"interned":true},{"k":"class","name":"int"},{"k":"map","entries":[{"o":0},{"o":1}]},{"k":"array","element":"Ljava/lang/Object;","cells":[{"o":2},{"u":"a float"}]}]"#);
        let o = parse("p.C", &line).unwrap();
        assert_eq!(o.jdk, "25.0.5");
        assert_eq!(o.fields["N"], Slot::Number(-3));
        assert_eq!(o.fields["Z"], Slot::Null);
        assert_eq!(o.objects[2], Object::Map(vec![(Slot::Object(0), Slot::Object(1))]));
        assert_eq!(o.unheld(&o.fields["A"]), None);
        assert_eq!(o.unheld(&o.fields["W"]).as_deref(), Some("an object of java.util.IdentityHashMap"));
        assert_eq!(o.unheld(&o.fields["T"]).as_deref(), Some("a float"), "an array with a cell that is not held is not held");
        assert_eq!((o.on.sha256.as_str(), o.on.locale.as_str(), o.on.format.as_str()), ("ab12", "en-US", "de-DE"));
        assert_eq!(o.on.properties, vec![("p.value".to_string(), Some("xyz".to_string())), ("p.unset".to_string(), None)]);
        assert_eq!(o.on.initialized[0].name, "p/B");
        let with_count = |count: &str| line.replace("\"zone\":", &format!("\"fixedProcessors\":{count},\"zone\":"));
        let three = parse("p.C", &with_count("3")).unwrap();
        let five = parse("p.C", &with_count("5")).unwrap();
        assert_eq!(three.objects, five.objects);
        assert_ne!(three.state_sha256, five.state_sha256);
        assert_eq!(o.state_sha256, parse("p.C", &with_count("null")).unwrap().state_sha256);
        let empty = parse("p.C", &line.replace("\"zone\":", "\"emptyEnvironment\":true,\"zone\":")).unwrap();
        assert_ne!(empty.state_sha256, o.state_sha256);
        assert!(state("p.C", r#"{"fields":[],"objects":[]}"#, &empty.on).is_err());
        let mut joint: serde_json::Value = serde_json::from_str(&line).unwrap();
        joint["on"]["preinitializeTogether"] = true.into();
        let captured = |j: &serde_json::Value| parse("p.C", &j.to_string());
        assert!(captured(&joint).is_err(), "member-local object numbers cannot enter the shared table");
        joint["on"]["initialized"][0].as_object_mut().unwrap().remove("objects");
        let first = captured(&joint).unwrap();
        assert_ne!(first.state_sha256, o.state_sha256);
        joint["on"]["initialized"][0]["fields"][0]["value"] = serde_json::json!({"o": 2});
        assert_ne!(first.state_sha256, captured(&joint).unwrap().state_sha256);
        joint["on"]["initialized"][0]["fields"][0]["value"] = serde_json::json!({"o": 99});
        assert!(captured(&joint).is_err());
        for invalid in ["0", "-1", "\"3\"", "2147483648"] {
            assert!(parse("p.C", &with_count(invalid)).is_err());
        }
        let said = assumption("p/C", &o);
        for part in ["JDK 25.0.5, Eclipse Adoptium", "sha256 ab12", "default locale was en-US (formatting de-DE", "default time zone Asia/Tokyo", "p.value = \"xyz\"", "p.unset, not set", "it initialized p.B besides"] {
            assert!(said.contains(part), "{part}: {said}");
        }
    }

    #[test]
    fn an_observation_that_does_not_say_what_it_was_observed_on_is_not_taken() {
        let said = parse("p.C", r#"{"jdk":"25","fields":[],"objects":[]}"#).unwrap_err().to_string();
        assert!(said.contains("does not say what it was observed on"), "{said}");
    }

    #[test]
    fn a_class_left_other_than_it_is_alone_is_named_with_its_field() {
        let state = |x: i64| serde_json::json!({"fields": [{"name": "x", "value": {"n": x}}], "objects": []});
        assert_eq!(changed(&state(1), &state(0)).as_deref(), Some("its field x was 1 after it and is 0 alone"));
        assert_eq!(changed(&state(0), &state(0)), None);
        let string = |u: u64| serde_json::json!({"fields": [{"name": "s", "value": {"o": 0}}], "objects": [{"k": "string", "units": [u], "interned": false}]});
        assert_eq!(changed(&string(105), &string(305)).as_deref(), Some("an object its fields hold"));
    }

    #[test]
    fn an_observation_on_another_class_path_or_of_a_class_file_the_tool_does_not_read_is_not_bound() {
        let o = parse("p.C", &on(r#""jdk":"25","fields":[],"objects":[]"#)).unwrap();
        let tool = crate::classpath::ClassPath::new();
        let other = bind("p.C", "p/C", &o.on, &[PathBuf::from("/w/observed"), PathBuf::from("/elsewhere")], &tool).unwrap_err().to_string();
        assert!(other.contains("not the check's"), "{other}");
        let mut alone = o.on.clone();
        alone.classpath = vec!["/w/observed".into()];
        let none = bind("p.C", "p/C", &alone, &[PathBuf::from("/w/observed")], &tool).unwrap_err().to_string();
        assert!(none.contains("reads no class file"), "{none}");
    }

    #[test]
    fn an_observation_that_read_the_properties_as_a_whole_or_does_not_say_its_settings_is_not_bound() {
        let line = on(r#""jdk":"25","fields":[],"objects":[]"#);
        assert!(settings("p.C", &parse("p.C", &line).unwrap().on).is_ok());
        let o = parse("p.C", &line.replace(r#""allProperties":null"#, r#""allProperties":"p.Lister""#)).unwrap();
        assert_eq!(o.on.all_properties.as_deref(), Some("p.Lister"));
        let said = settings("p.C", &o.on).unwrap_err().to_string();
        assert!(said.contains("p.Lister read the system properties as a whole"), "{said}");
        let unsaid = parse("p.C", &line.replace(r#""allProperties":null,"#, "")).unwrap_err().to_string();
        assert!(unsaid.contains("allProperties"), "{unsaid}");
        let unzoned = parse("p.C", &line.replace(r#""zone":"Asia/Tokyo","#, "")).unwrap_err().to_string();
        assert!(unzoned.contains("zone"), "{unzoned}");
    }

    /// A value the observation does not hold is compared by its description (`bc.Boxed`'s Box, `bc.Rehooked`'s
    /// lambda), one with none is refused with why, and an initialization that changed the JDK's settings
    /// (`bc.Relocaled`) is refused with the setting.
    #[test]
    fn a_value_not_held_is_compared_by_its_description_and_a_changed_setting_is_refused() {
        let boxed = |d: &str| serde_json::json!({"fields": [{"name": "BOX", "value": {"u": "an object of bc.Box", "d": d}}], "objects": []});
        assert_eq!(changed(&boxed("bc.Box{value=Integer 5}"), &boxed("bc.Box{value=Integer 0}")).as_deref(), Some("its field BOX was an object of bc.Box (bc.Box{value=Integer 5}) after it and is an object of bc.Box (bc.Box{value=Integer 0}) alone"));
        assert_eq!(changed(&boxed("bc.Box{value=Integer 0}"), &boxed("bc.Box{value=Integer 0}")), None);
        assert_eq!(undescribed(&boxed("bc.Box{value=Integer 0}")), None);
        let logger = serde_json::json!({"fields": [{"name": "LOG", "value": {"u": "an object of java.util.logging.Logger", "why": "an object of java.util.logging.Logger, a class of the JDK the observer does not describe"}}], "objects": []});
        let said = undescribed(&logger).unwrap();
        assert!(said.starts_with("whose field LOG holds an object of java.util.logging.Logger, which the observation neither holds nor describes (an object of"), "{said}");
        let cell = serde_json::json!({"fields": [{"name": "A", "value": {"o": 0}}], "objects": [{"k": "array", "element": "Ljava/lang/Object;", "cells": [{"u": "an object of p.X"}]}]});
        assert!(undescribed(&cell).unwrap().contains("whose fields hold an object that holds an object of p.X"), "{:?}", undescribed(&cell));
        let line = on(r#""jdk":"25","fields":[],"objects":[]"#).replace(r#""changed":[]"#, r#""changed":["the default locale, from en-US to tr"]"#);
        let o = parse("p.C", &line).unwrap();
        let said = settings("p.C", &o.on).unwrap_err().to_string();
        assert!(said.contains("its initialization changed the JDK's settings (the default locale, from en-US to tr)"), "{said}");
        let unsaid = parse("p.C", &on(r#""jdk":"25","fields":[],"objects":[]"#).replace(r#""changed":[],"#, "")).unwrap_err().to_string();
        assert!(unsaid.contains("changed"), "{unsaid}");
    }

    #[test]
    fn an_initializer_that_threw_and_a_malformed_line_are_refused() {
        let threw = parse("p.C", r#"{"threw":"java.lang.IllegalStateException"}"#).unwrap_err().to_string();
        assert!(threw.contains("threw java.lang.IllegalStateException") && threw.contains("p.C"), "{threw}");
        assert!(parse("p.C", &on(r#""jdk":"25","fields":[{"name":"A","value":{"o":4}}],"objects":[]"#)).is_err(), "an object's number past the objects");
        assert!(parse("p.C", "not json").is_err());
    }

    #[test]
    fn a_strings_hash_is_the_jdks() {
        let units = |s: &str| s.encode_utf16().collect::<Vec<u16>>();
        assert_eq!(string_hash(&units("")), 0);
        assert_eq!(string_hash(&units("int")), 104431);
        assert_eq!(string_hash(&units("java.lang.String")), 1195259493);
        assert_eq!(string_hash(&units("org.springframework.web.servlet.DispatcherServlet")), "org.springframework.web.servlet.DispatcherServlet".chars().fold(0i32, |h, c| h.wrapping_mul(31).wrapping_add(c as i32)));
    }
}
