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
//! subclass) whose keys are Strings or null and whose values are held, and an array of integral primitives or of
//! held references. Two fields that hold one object hold one object here. Any other value (a `float`, an
//! `IdentityHashMap`, an object of a class of the application) is **not held**: the field has no value in the
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
//!   observed initialization must be the state it has initialized first thing in a JVM of its own, as far as the
//!   observation holds it. An initializer that wrote another class's static (`A.<clinit> { B.x = 1; k = 7; }`,
//!   `lib/tests/observed_countermodels.rs`), a superclass's (`ob.Derived`) or a cell of a superinterface's array
//!   (`ob.Filled`, both `lib/tests/fixtures/rule-countermodels`) is refused, with the field, and so is
//!   one whose class file is not the tool's. A value not held is compared by what it is said to be, and a lambda's
//!   hidden class is said by what it was defined from (`R$$Lambda`), without the address a JVM appends to its name,
//!   which differs from run to run (`claims.Hooked`, `lib/tests/claims.rs`).
//! - The default locale: one whose language is Turkish, Azeri or Lithuanian is refused, since the check takes the
//!   JVM's default to be none of them ([`crate::bmc::strings::LOCALE_ASSUMPTION`]); any other is stated. The default
//!   time zone (which the JDK reads from `user.timezone` or the machine, as `ob.Zoned`'s `TimeZone.getDefault()`
//!   does) is stated too.
//! - The system properties the class path's code read during the initialization (through `System.getProperty`,
//!   `Integer.getInteger`, `Long.getLong` or `Boolean.getBoolean`, or by key through the map `System.getProperties()`
//!   gives, as `ob.Bypassed` does), each with the value it had or that it was not set: stated. One that read the
//!   properties as a whole (their keys, entries or values, a copy) is refused, since the observation lists only the
//!   ones read by name. The JDK's reads of its own configuration, as it opens a JAR or first uses one of its
//!   classes, are not listed: the check takes the JDK at its defaults throughout.
//! - The environment: an observation does not record it, so one whose initialization initialized a class whose code
//!   reads it (`System.getenv`, `ProcessBuilder.environment`, as `ob.Environ` does) is refused, by the class.
//! - The JDK: its release must be the check's, and its vendor and home are stated.
//!
//! What is still assumed, and stated: that a class it initialized holds, where the observation holds nothing of a
//! field (an object of the application), what it would hold alone, and that a write of the value a field already
//! had is none; that the settings it read (the locale, the time zone, the properties) are those of the run the
//! result is about. Not seen: a read of the environment by reflection or through a JDK method other than the two,
//! and a read of the properties through a method the observer does not override (`equals`, `hashCode`).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

use crate::Error;

/// The program that observes one class, as Java: javac compiles it and a JVM runs it once for each class.
const SOURCE: &str = include_str!("observed/ObservedInitializer.java");
const CLASS: &str = "ObservedInitializer";
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
    /// An array: its element type's descriptor and its cells.
    Array { element: String, cells: Vec<Slot> },
}

/// The static state one class's initializer left on a JVM.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Observed {
    /// The JVM's `java.version`.
    pub jdk: String,
    /// Each static field the class declares, by name.
    pub fields: BTreeMap<String, Slot>,
    pub objects: Vec<Object>,
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
    /// Each system property the initialization read, in the order it first did, and the value it had.
    pub properties: Vec<(String, Option<String>)>,
    /// The first class of the class path that read the system properties as a whole, if one did.
    pub all_properties: Option<String>,
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

/// What a result that took the observed state of `class`'s initializer rests on.
pub fn assumption(class: &str, observed: &Observed) -> String {
    let jdk = &observed.jdk;
    let on = match &observed.previous {
        Some(own) => format!("the previous version's class path, where it is {}", own.replace('/', ".")),
        None => "the check's class path".to_string(),
    };
    let bound = &observed.on;
    let short = |h: &str| h.chars().take(12).collect::<String>();
    let properties = if bound.properties.is_empty() {
        "it read no system property".to_string()
    } else {
        let each: Vec<String> = bound.properties.iter().map(|(k, v)| match v { Some(v) => format!("{k} = {v:?}"), None => format!("{k}, not set") }).collect();
        format!("it read the system properties {}, and the result holds where each is as it was", each.join("; "))
    };
    let initialized = if bound.initialized.is_empty() {
        String::new()
    } else {
        let names: Vec<String> = bound.initialized.iter().map(|i| i.name.replace('/', ".")).collect();
        format!("; it initialized {} besides, and left each in the state the class has initialized alone, as far as the observation holds its fields (what it holds nothing of is taken to be the same too)", names.join(", "))
    };
    format!(
        "the class initializer of {} was not run by the checker: its static state is the one a JVM (JDK {jdk}, {}) left after initializing the class first thing on {on}, from the class file the check reads (sha256 {}), in a JVM whose default locale was {} (formatting {}, display {}) and default time zone {}; {properties}{initialized}; and it is taken to leave that state in every run (it reads nothing a run could have changed before it, and the objects it leaves are held by no other class)",
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
    let mut out = Observations::new();
    if classes.is_empty() {
        return Ok(out);
    }
    let home = crate::jimage::JImage::find_java_home().ok_or_else(|| Error::new("--observed-initializer: no JDK to observe a class initializer on (set JAVA_HOME)"))?;
    let dir = work.join("observed");
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
    let mut tool = crate::classpath::ClassPath::new();
    for entry in &entries[1..] {
        tool.add(entry)?;
    }
    let jvm = Jvm { java: home.join("bin").join("java"), class_path, dir: dir.clone() };
    let mut alone: BTreeMap<String, serde_json::Value> = BTreeMap::new();
    for class in classes {
        let internal = class.replace('.', "/");
        let binary = internal.replace('/', ".");
        let log = dir.join(format!("{binary}.init.log"));
        let line = jvm.run(&binary, Some(&log))?;
        let observed = parse(&binary, &line)?;
        bind(&binary, &internal, &observed.on, &entries, &tool)?;
        for ran in std::iter::once(internal.as_str()).chain(observed.on.initialized.iter().map(|i| i.name.as_str())) {
            if let Some(call) = reads_environment(&tool, ran)? {
                let whose = if ran == internal { "its code".to_string() } else { format!("its initialization initialized {}, whose code", ran.replace('/', ".")) };
                return Err(Error::new(format!(
                    "--observed-initializer {binary}: {whose} reads the environment ({call}), and an observation does not record the environment, so the check cannot take it (the environment is not the class path's, and it differs from one machine to the next)"
                )));
            }
        }
        for other in &observed.on.initialized {
            let name = other.name.replace('/', ".");
            if tool_sha256(&tool, &other.name)?.as_deref() != Some(other.sha256.as_str()) {
                return Err(Error::new(format!("--observed-initializer {binary}: its initialization initialized {name}, whose class file the JVM read is not the one the tool reads of it on this class path")));
            }
            if !alone.contains_key(&other.name) {
                let line = jvm.run(&name, None)?;
                alone.insert(other.name.clone(), state(&name, &line)?);
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
}

impl Jvm {
    /// Runs the observer on `binary`, with its class initializations logged to `log` where given, and returns the
    /// line of the observation.
    fn run(&self, binary: &str, log: Option<&Path>) -> Result<String, Error> {
        let suffix = if log.is_some() { "" } else { ".alone" };
        let stdout = self.dir.join(format!("{binary}{suffix}.stdout"));
        let stderr = self.dir.join(format!("{binary}{suffix}.stderr"));
        let mut command = Command::new(&self.java);
        command.args(["-Xmx256m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData"]);
        if let Some(log) = log {
            let _ = std::fs::remove_file(log);
            command.arg(format!("-Xlog:class+init=info:file={}::filecount=0", log.display()));
        }
        command.arg("-cp").arg(&self.class_path).arg(CLASS).arg(binary);
        if let Some(log) = log {
            command.arg(log);
        }
        let mut child = command
            .current_dir(&self.dir)
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

/// The JDK method by which the class file the tool reads of `internal` reads the environment, if it has one: a call
/// or a method handle of `System.getenv` or `ProcessBuilder.environment` anywhere in it, run or not.
fn reads_environment(tool: &crate::classpath::ClassPath, internal: &str) -> Result<Option<String>, Error> {
    let Some(bytes) = tool.application_bytes(internal)? else { return Ok(None) };
    let class = crate::classfile::ClassFile::parse(&bytes).map_err(|e| Error::new(format!("--observed-initializer: the class file of {} does not parse: {e}", internal.replace('/', "."))))?;
    for (index, constant) in class.pool.entries().iter().enumerate() {
        if !matches!(constant, crate::classfile::Constant::MethodRef { .. }) {
            continue;
        }
        let Ok(member) = class.pool.member(index as u16) else { continue };
        if matches!((member.owner.as_str(), member.name.as_str()), ("java/lang/System", "getenv") | ("java/lang/ProcessBuilder", "environment")) {
            return Ok(Some(member.display()));
        }
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
    if let Some(reader) = &on.all_properties {
        return Err(Error::new(format!(
            "--observed-initializer {binary}: {reader} read the system properties as a whole (their keys, entries or values, through System.getProperties()), and an observation lists only the properties read by name, so the check cannot take it"
        )));
    }
    Ok(())
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
            return u.to_string();
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
fn state(binary: &str, line: &str) -> Result<serde_json::Value, Error> {
    let json: serde_json::Value = serde_json::from_str(line).map_err(|e| Error::new(format!("--observed-initializer {binary}: the observation is not one the tool reads ({e})")))?;
    if let Some(threw) = json.get("threw").and_then(|t| t.as_str()) {
        return Err(Error::new(format!("--observed-initializer {binary}: initialized alone on the JVM, the class threw {threw}")));
    }
    Ok(serde_json::json!({ "fields": json.get("fields"), "objects": json.get("objects") }))
}

/// [`observe`] for a check: the observations must be of the JDK the check's facts about the JDK are of.
pub fn observe_for(classes: &[String], classpath: &[PathBuf], work: &Path) -> Result<Observations, Error> {
    let observed = observe(classes, classpath, work)?;
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
    use crate::relocate::Found;
    let mut out = Observations::new();
    for (class, mut observed) in observe_for(classes, &previous.classpath, &work.join("previous"))? {
        let binary = class.replace('/', ".");
        if !previous.relocated.contains(&class) {
            return Err(Error::new(format!("--observed-initializer {binary}: the check holds no copy of the previous version's class")));
        }
        let held = format!("{}/{class}", previous.prefix);
        for object in &mut observed.objects {
            let Object::Class(name) = object else { continue };
            // A class by its internal name, or an array of one by its descriptor (`[Lx/Y;`).
            let (open, element, close) = match name.rfind("[L") {
                Some(at) if name.ends_with(';') => (&name[..at + 2], &name[at + 2..name.len() - 1], ";"),
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
            Some("map") => {
                let flat = slots(o.get("entries"))?;
                if flat.len() % 2 != 0 {
                    return Err(bad("a map's entries"));
                }
                Object::Map(flat.chunks(2).map(|kv| (kv[0].clone(), kv[1].clone())).collect())
            }
            Some("array") => Object::Array { element: o.get("element").and_then(|e| e.as_str()).ok_or_else(|| bad("an array"))?.to_string(), cells: slots(o.get("cells"))? },
            _ => return Err(bad("an object")),
        });
    }
    let mut fields = BTreeMap::new();
    for f in json.get("fields").and_then(|f| f.as_array()).ok_or_else(|| bad("fields"))? {
        let name = f.get("name").and_then(|n| n.as_str()).ok_or_else(|| bad("a field"))?;
        fields.insert(name.to_string(), slot(f.get("value").ok_or_else(|| bad("a field"))?)?);
    }
    let on = json.get("on").ok_or_else(|| Error::new(format!("--observed-initializer {binary}: the observation does not say what it was observed on (the class file, the class path, the locale, the properties it read, the classes it initialized), and an observation that does not is not taken")))?;
    let text = |v: &serde_json::Value, key: &str| -> Result<String, Error> { v.get(key).and_then(|t| t.as_str()).map(String::from).ok_or_else(|| bad(key)) };
    let list = |key: &str| -> Result<&Vec<serde_json::Value>, Error> { on.get(key).and_then(|l| l.as_array()).ok_or_else(|| bad(key)) };
    let locale = on.get("locale").ok_or_else(|| bad("the locale"))?;
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
        properties: list("properties")?.iter().map(|p| Ok((text(p, "name")?, p.get("value").and_then(|v| v.as_str()).map(String::from)))).collect::<Result<_, Error>>()?,
        all_properties: match on.get("allProperties") {
            Some(serde_json::Value::Null) => None,
            Some(serde_json::Value::String(reader)) => Some(reader.clone()),
            _ => return Err(bad("allProperties")),
        },
        initialized: list("initialized")?
            .iter()
            .map(|i| Ok(Initialized { name: text(i, "name")?, sha256: text(i, "sha256")?, state: serde_json::json!({ "fields": i.get("fields"), "objects": i.get("objects") }) }))
            .collect::<Result<_, Error>>()?,
    };
    let observed = Observed { jdk: json.get("jdk").and_then(|j| j.as_str()).ok_or_else(|| bad("the JDK"))?.to_string(), fields, objects, previous: None, on };
    let within = |s: &Slot| !matches!(s, Slot::Object(i) if *i >= observed.objects.len());
    let all = observed.fields.values().chain(observed.objects.iter().flat_map(|o| match o {
        Object::Map(entries) => entries.iter().flat_map(|(k, v)| [k, v]).collect::<Vec<_>>(),
        Object::Array { cells, .. } => cells.iter().collect(),
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
    const ON: &str = r#""on":{"sha256":"ab12","from":"file:/app/","classpath":["/w/observed","/app"],"vendor":"Eclipse Adoptium","home":"/jdk","locale":{"default":"en-US","format":"de-DE","display":"en-US"},"zone":"Asia/Tokyo","properties":[{"name":"p.value","value":"xyz"},{"name":"p.unset","value":null}],"allProperties":null,"initialized":[{"name":"p/B","sha256":"cd34","fields":[{"name":"x","value":{"n":1}}],"objects":[]}]}"#;

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
