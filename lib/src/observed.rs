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
//! The observation is of the named class alone. A class the initializer happened to initialize on the JVM is, in
//! the check, initialized where the check first uses it, as it would be had the observed initializer not run.

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
}

/// The observations a check was given, by the class's internal name.
pub type Observations = BTreeMap<String, Observed>;

/// What a result that took the observed state of `class`'s initializer rests on.
pub fn assumption(class: &str, jdk: &str) -> String {
    format!(
        "the class initializer of {} was not run by the checker: its static state is the one a JVM (JDK {jdk}) left after initializing the class first thing on the check's class path, and it is taken to leave that state in every run (it reads nothing a run could have changed before it, and the objects it leaves are held by no other class)",
        class.replace('/', ".")
    )
}

/// Observes each of `classes` (binary or internal names) on `classpath`, in a JVM of its own, with the working
/// files under `work`. An error where there is no JDK, the class is not found, or its initializer throws.
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
    for class in classes {
        let internal = class.replace('.', "/");
        let binary = internal.replace('/', ".");
        let stdout = dir.join(format!("{binary}.stdout"));
        let stderr = dir.join(format!("{binary}.stderr"));
        let mut child = Command::new(home.join("bin").join("java"))
            .args(["-Xmx256m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData", "-cp"])
            .arg(&class_path)
            .arg(CLASS)
            .arg(&binary)
            .current_dir(&dir)
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
        let Some(line) = text.lines().find_map(|l| l.strip_prefix(MARK)) else {
            let said = std::fs::read_to_string(&stderr).unwrap_or_default();
            let tail: Vec<&str> = said.lines().rev().take(3).collect();
            return Err(Error::new(format!("--observed-initializer {binary}: the JVM gave no observation{}", if tail.is_empty() { String::new() } else { format!(": {}", tail.into_iter().rev().collect::<Vec<_>>().join(" / ")) })));
        };
        out.insert(internal, parse(&binary, line)?);
    }
    Ok(out)
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
    let observed = Observed { jdk: json.get("jdk").and_then(|j| j.as_str()).ok_or_else(|| bad("the JDK"))?.to_string(), fields, objects };
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

    #[test]
    fn an_observation_is_read_as_the_observer_writes_it() {
        let line = r#"{"jdk":"25.0.5","fields":[{"name":"A","value":{"o":2}},{"name":"N","value":{"n":-3}},{"name":"Z","value":null},{"name":"W","value":{"u":"an object of java.util.IdentityHashMap"}},{"name":"T","value":{"o":3}}],"objects":[{"k":"string","units":[105,110,116],"interned":true},{"k":"class","name":"int"},{"k":"map","entries":[{"o":0},{"o":1}]},{"k":"array","element":"Ljava/lang/Object;","cells":[{"o":2},{"u":"a float"}]}]}"#;
        let o = parse("p.C", line).unwrap();
        assert_eq!(o.jdk, "25.0.5");
        assert_eq!(o.fields["N"], Slot::Number(-3));
        assert_eq!(o.fields["Z"], Slot::Null);
        assert_eq!(o.objects[2], Object::Map(vec![(Slot::Object(0), Slot::Object(1))]));
        assert_eq!(o.unheld(&o.fields["A"]), None);
        assert_eq!(o.unheld(&o.fields["W"]).as_deref(), Some("an object of java.util.IdentityHashMap"));
        assert_eq!(o.unheld(&o.fields["T"]).as_deref(), Some("a float"), "an array with a cell that is not held is not held");
    }

    #[test]
    fn an_initializer_that_threw_and_a_malformed_line_are_refused() {
        let threw = parse("p.C", r#"{"threw":"java.lang.IllegalStateException"}"#).unwrap_err().to_string();
        assert!(threw.contains("threw java.lang.IllegalStateException") && threw.contains("p.C"), "{threw}");
        assert!(parse("p.C", r#"{"jdk":"25","fields":[{"name":"A","value":{"o":4}}],"objects":[]}"#).is_err(), "an object's number past the objects");
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
