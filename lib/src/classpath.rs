//! The closed world an analysis runs in: the application classes (directories and jars), the JDK, and the tool's
//! own models of a few JDK classes.
//!
//! Application classes are the code under verification. JDK classes are consulted for their *shape* only (their
//! superclasses, interfaces and member declarations), from the JDK image when one is found and from a built-in
//! table of `java.base` facts otherwise; their behaviour is never executed from bytecode but modelled by
//! [`crate::interp`]. The exception is the [`crate::models`]: class files the tool ships for JDK classes JBMC has
//! no bytecode for, which the interpreter executes too, so that both engines compute the same function. A model's
//! shape is used only where neither the application nor the JDK image has the class.

use std::cell::RefCell;
use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::rc::Rc;

use crate::classfile::{ClassFile, Method};
use crate::jimage::JImage;
use crate::Error;

enum Entry {
    Dir(PathBuf),
    /// A jar, and the class files it holds for a release of Java of their own where its manifest says it is a
    /// multi-release JAR ([`versioned_entries`]).
    Jar(crate::zip::ZipArchive, PathBuf, JarVersions),
}

fn lookup_directory(path: &Path, ancestors: &mut Vec<PathBuf>) -> Result<String, Error> {
    let resolved = path.canonicalize()?;
    if ancestors.contains(&resolved) {
        return Err(Error::new("cycle in a class path directory"));
    }
    ancestors.push(resolved);
    let mut entries = std::fs::read_dir(path)?.collect::<Result<Vec<_>, _>>()?;
    entries.sort_by_key(|e| e.file_name());
    let mut contents = Vec::new();
    for entry in entries {
        let child = entry.path();
        let metadata = std::fs::metadata(&child)?;
        let (kind, digest) = if metadata.is_dir() {
            (b'D', lookup_directory(&child, ancestors)?)
        } else if metadata.is_file() {
            (b'F', crate::digest::sha256_reader(std::fs::File::open(&child)?)?)
        } else {
            return Err(Error::new(format!("non-file class path entry {}", child.display())));
        };
        contents.push(kind);
        contents.extend(entry.file_name().as_encoded_bytes());
        contents.push(0);
        contents.extend(digest.bytes());
    }
    ancestors.pop();
    Ok(crate::digest::sha256_hex(&contents))
}

/// How a JAR's main manifest enables multi-release lookup, read as the JDK's own reader reads it
/// (`java.util.jar.JarFile`). Measured on Temurin 17.0.21, 21.0.13 and 25.0.5 with fifteen spellings
/// (`lib/tests/class_bindings.rs`): a JAR is multi-release there when its manifest's bytes hold `Multi-Release: true`
/// literally (letters in either case, one space) and the main section's attribute, with continuation lines joined
/// and the last value taken, is `true` on a line that is ended. The JAR specification's reading, joining
/// continuation lines first, calls a value folded over two lines `true` as well; those runtimes load the base
/// entries of such a JAR.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum MultiRelease {
    /// The main section has no `Multi-Release: true`: versioned entries are never consulted.
    Disabled,
    /// Enabled, in a spelling every reader agrees on.
    Enabled,
    /// The attribute reads `true` once continuation lines are joined, but the bytes hold no literal
    /// `Multi-Release: true`: the runtimes measured load the base entries, and a reader that joins lines first the
    /// versioned ones. A class with a versioned entry in such a JAR is refused unless a JVM said which it loaded
    /// ([`ClassPath::refused`]).
    Ambiguous,
}

/// What a JAR says of multi-release lookup, and the versioned entries it then holds: each logical name with the
/// releases it has an entry for. Empty when the manifest does not enable the lookup.
pub struct JarVersions {
    mode: MultiRelease,
    entries: BTreeMap<String, Vec<u32>>,
}

impl JarVersions {
    /// The entry that stands for `name` on a JVM of `feature`: the highest versioned one not above it where the
    /// manifest enables the lookup in a spelling every reader agrees on, else the base entry.
    fn entry_for(&self, name: &str, feature: Option<u32>) -> String {
        if let (MultiRelease::Enabled, Some(feature), Some(available)) = (self.mode, feature, self.entries.get(name)) {
            if let Some(selected) = available.iter().copied().filter(|&v| v <= feature).max() {
                return format!("META-INF/versions/{selected}/{name}");
            }
        }
        name.to_string()
    }
}

/// [`MultiRelease`] of a manifest's bytes.
pub fn multi_release(manifest: &[u8]) -> MultiRelease {
    const LITERAL: &[u8] = b"multi-release: true";
    let literal = manifest.windows(LITERAL.len()).any(|w| w.eq_ignore_ascii_case(LITERAL));
    let text = String::from_utf8_lossy(manifest).replace("\r\n", "\n").replace('\r', "\n");
    // The main section ends at the first empty line; a last line with no line break is not read.
    let main = match text.split_once("\n\n") {
        Some((main, _)) => main.to_string(),
        None => text.rsplit_once('\n').map(|(ended, _)| ended.to_string()).unwrap_or_default(),
    };
    let main = main.replace("\n ", "");
    let attribute = main.lines().filter_map(|line| line.split_once(": "))
        .filter(|(key, _)| key.eq_ignore_ascii_case("Multi-Release")).next_back()
        .is_some_and(|(_, value)| value.eq_ignore_ascii_case("true"));
    match (attribute, literal) {
        (false, _) => MultiRelease::Disabled,
        (true, true) => MultiRelease::Enabled,
        (true, false) => MultiRelease::Ambiguous,
    }
}

/// The versioned entries of a JAR whose main manifest enables multi-release lookup (JAR specification).
fn versioned_entries(zip: &crate::zip::ZipArchive) -> Result<JarVersions, Error> {
    let mut out: BTreeMap<String, Vec<u32>> = BTreeMap::new();
    let mode = match zip.read("META-INF/MANIFEST.MF")? {
        Some(manifest) => multi_release(&manifest),
        None => MultiRelease::Disabled,
    };
    if mode == MultiRelease::Disabled { return Ok(JarVersions { mode, entries: out }) }
    for name in zip.names() {
        let Some((release, entry)) = name.strip_prefix("META-INF/versions/").and_then(|rest| rest.split_once('/')) else { continue };
        if release.starts_with('0') || !release.bytes().all(|b| b.is_ascii_digit()) || entry.starts_with("META-INF/") { continue }
        if let Ok(release @ 9..) = release.parse::<u32>() {
            out.entry(entry.to_owned()).or_default().push(release);
        }
    }
    Ok(JarVersions { mode, entries: out })
}

fn legacy_boot_archive(home: &Path) -> Option<PathBuf> {
    if home.join("lib/modules").is_file() { return None }
    [home.join("jre/lib/rt.jar"), home.join("lib/rt.jar")].into_iter().find(|path| path.is_file())
}

/// The installation whose boot classes the checker will actually read, including an explicitly selected JDK 8.
pub(crate) fn binding_java_home() -> Option<PathBuf> {
    let legacy = std::env::var_os("JAVA_HOME").map(PathBuf::from).filter(|home| legacy_boot_archive(home).is_some());
    legacy.or_else(JImage::find_java_home)
}

/// An explicitly bound release for a native check, checked against the actual JDK installation.
/// A launcher override or an unavailable runtime leaves multi-release classes subject to the conservative refusal.
pub(crate) fn configured_jar_release() -> Option<u32> {
    let requested: u32 = std::env::var("JVMCONTRACT_JAR_RELEASE").ok()?.parse().ok()?;
    for name in ["JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS"] {
        if std::env::var(name).is_ok_and(|s| s.contains("jdk.util.jar.") || s.split_whitespace().any(|s| s.starts_with('@'))) {
            return None;
        }
    }
    let release = std::fs::read_to_string(binding_java_home()?.join("release")).ok()?;
    let version = release.lines().find_map(|l| l.strip_prefix("JAVA_VERSION="))?.trim_matches('"');
    let feature: u32 = version.strip_prefix("1.").unwrap_or(version).split(|ch: char| !ch.is_ascii_digit()).next()?.parse().ok()?;
    (requested == feature).then_some(requested)
}

/// What a JVM was seen to load, for the classes whose selection a rule alone does not settle: `JVMCONTRACT_CLASS_OBSERVATIONS`
/// names a JSON file `{"feature": 21, "classes": {"fixture.Gate": "<sha256>"}}`, written by whoever ran the JVM (the
/// target workflow's `LoadedClasses` probe). It counts only for the release it was made on, and only while that
/// release is the bound one.
#[derive(Default)]
struct ClassObservations {
    feature: Option<u32>,
    /// By internal name: the SHA-256 of the class file the JVM loaded.
    classes: HashMap<String, String>,
    /// Why the file named could not be used. Then no application class is read: an observation that was meant to
    /// bind a class and silently did not would be the disagreement this exists to catch.
    problem: Option<String>,
}

fn configured_observations() -> ClassObservations {
    let Some(path) = std::env::var_os("JVMCONTRACT_CLASS_OBSERVATIONS").filter(|p| !p.is_empty()) else { return ClassObservations::default() };
    let read = || -> Result<ClassObservations, String> {
        let text = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let value: serde_json::Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;
        let feature = value["feature"].as_u64().and_then(|f| u32::try_from(f).ok()).ok_or("it names no feature release")?;
        let mut classes = HashMap::new();
        for (name, digest) in value["classes"].as_object().ok_or("it lists no classes")? {
            let digest = digest.as_str().filter(|d| d.len() == 64 && d.bytes().all(|b| b.is_ascii_hexdigit())).ok_or_else(|| format!("{name} has no SHA-256"))?;
            classes.insert(name.replace('.', "/"), digest.to_ascii_lowercase());
        }
        Ok(ClassObservations { feature: Some(feature), classes, problem: None })
    };
    read().unwrap_or_else(|why| ClassObservations { problem: Some(format!("the class observations in {} cannot be used: {why}", PathBuf::from(&path).display())), ..Default::default() })
}

/// One class file an entry holds for a name: where it is, and its digest.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct Candidate {
    /// The class path entry, as it was given.
    pub provider: String,
    /// The entry inside a JAR (`fixture/Gate.class`, `META-INF/versions/17/fixture/Gate.class`), or the file under
    /// a directory.
    pub entry: String,
    pub sha256: String,
    /// The release a versioned entry is for; none for a base entry.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub release: Option<u32>,
}

/// How a binding's class file was chosen.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum SelectedBy {
    /// By the class path's order and the bound release alone.
    Rule,
    /// By the rule, and a JVM was seen to load the same bytes.
    RuleAndObservation,
    /// By what a JVM was seen to load, where the manifest's spelling leaves the rule without an answer.
    Observation,
}

/// The exact class file the checker inspects for a binary class name, on this ordered class path and bound runtime:
/// the one answer every reader of the class takes ([`ClassPath::bind`]).
#[derive(Debug, Clone, serde::Serialize)]
pub struct ClassBinding {
    /// The class, dotted.
    pub class: String,
    /// The provider's position among the class path's entries, from 0.
    pub index: usize,
    #[serde(flatten)]
    pub selected: Candidate,
    pub selected_by: SelectedBy,
    /// The release multi-release lookup is bound to (`JVMCONTRACT_JAR_RELEASE`, checked against the JDK); none
    /// when no runtime is bound.
    pub bound_release: Option<u32>,
    /// What the provider's manifest says of multi-release lookup; none for a directory.
    pub manifest: Option<MultiRelease>,
    /// Every class file the provider holds for the name, the selected one among them.
    pub candidates: Vec<Candidate>,
    /// Later entries that hold the class too, shadowed here. Whether a shadowed class is acceptable is the caller's
    /// policy; this only says so.
    pub shadowed: Vec<Candidate>,
}

/// Why no class file stands for a name: the two digests where two readers would differ, and where each is from.
#[derive(Debug, Clone, serde::Serialize)]
pub struct BindingRefusal {
    pub code: RefusalCode,
    /// The class, dotted.
    pub class: String,
    pub reason: String,
    /// What the rule selects, when it selects.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub selected: Option<Candidate>,
    /// The SHA-256 a JVM was seen to load, when one was given.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observed: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub candidates: Vec<Candidate>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum RefusalCode {
    /// No entry holds the class.
    MissingClass,
    /// The provider is a multi-release JAR with a versioned class file of it, and no runtime release is bound.
    UnboundRelease,
    /// The provider's manifest spells `Multi-Release` so that readers differ ([`MultiRelease::Ambiguous`]), it
    /// holds a versioned class file of the class, and no JVM said which it loads.
    AmbiguousManifest,
    /// A JVM was seen to load other bytes than the rule selects.
    ObservationDiffers,
    /// A JVM was seen to load bytes that no class file of the provider has.
    ObservationUnmatched,
    /// The class is on the class path in a package of a JDK module, which a JVM loads from the module.
    ShadowsJdk,
    /// The observations file named could not be used, or an entry could not be read.
    Unreadable,
}

impl Entry {
    /// Every class file this entry holds for `file`, the base one first and then the versioned ones by release,
    /// whatever its manifest says: the physical inventory, apart from which of them is selected.
    fn candidates(&self, file: &str) -> Result<Vec<Candidate>, Error> {
        let provider = self.display();
        let candidate = |entry: String, bytes: &[u8], release| Candidate { provider: provider.clone(), entry, sha256: crate::digest::sha256_hex(bytes), release };
        match self {
            Entry::Dir(_) => Ok(self.resource(file, None)?.map(|bytes| candidate(file.to_string(), &bytes, None)).into_iter().collect()),
            Entry::Jar(zip, _, _) => {
                let mut out = Vec::new();
                if let Some(bytes) = zip.read(file)? {
                    out.push(candidate(file.to_string(), &bytes, None));
                }
                let mut versioned: Vec<(u32, &str)> = zip.names().filter_map(|name| {
                    let (release, entry) = name.strip_prefix("META-INF/versions/")?.split_once('/')?;
                    (entry == file && !release.starts_with('0') && release.bytes().all(|b| b.is_ascii_digit())).then(|| release.parse::<u32>().ok().map(|r| (r, name)))?
                }).collect();
                versioned.sort();
                for (release, name) in versioned {
                    if let Some(bytes) = zip.read(name)? {
                        out.push(candidate(name.to_string(), &bytes, Some(release)));
                    }
                }
                Ok(out)
            }
        }
    }

    /// Whether a JVM could load `file` from this entry: its base entry, or a versioned one where the manifest
    /// enables the lookup.
    fn holds(&self, file: &str) -> bool {
        match self {
            Entry::Dir(dir) => dir.join(file).is_file(),
            Entry::Jar(zip, _, versions) => zip.contains(file) || versions.entries.contains_key(file),
        }
    }

    fn resource(&self, name: &str, feature: Option<u32>) -> Result<Option<Vec<u8>>, Error> {
        match self {
            Entry::Dir(dir) => {
                let file = dir.join(name);
                if file.is_dir() { return Ok(None) }
                match std::fs::read(&file) {
                    Ok(bytes) => Ok(Some(bytes)),
                    Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
                    Err(e) => Err(Error::new(format!("cannot read {}: {e}", file.display()))),
                }
            }
            Entry::Jar(zip, _, versions) => zip.read(&versions.entry_for(name, feature)),
        }
    }

    fn read(&self, class_name: &str, feature: Option<u32>) -> Result<Option<Vec<u8>>, Error> {
        self.resource(&format!("{class_name}.class"), feature)
    }

    fn class_names(&self, feature: Option<u32>) -> Result<Vec<String>, Error> {
        match self {
            Entry::Dir(dir) => {
                let mut names = Vec::new();
                walk(dir, dir, &mut names)?;
                names.sort();
                Ok(names)
            }
            Entry::Jar(zip, _, versions) => {
                let mut names: std::collections::BTreeSet<_> = zip.names()
                    .filter(|n| !n.starts_with("META-INF/")).filter_map(|n| n.strip_suffix(".class")).collect();
                if let (MultiRelease::Enabled, Some(feature)) = (versions.mode, feature) {
                    names.extend(versions.entries.iter().filter(|(_, v)| v.iter().any(|&n| n <= feature))
                        .filter_map(|(name, _)| name.strip_suffix(".class")));
                }
                Ok(names.into_iter().map(str::to_owned).collect())
            }
        }
    }

    fn display(&self) -> String {
        match self {
            Entry::Dir(d) => d.display().to_string(),
            Entry::Jar(_, p, _) => p.display().to_string(),
        }
    }
}

fn walk(root: &Path, dir: &Path, names: &mut Vec<String>) -> Result<(), Error> {
    let entries = std::fs::read_dir(dir).map_err(|e| Error::new(format!("cannot list {}: {e}", dir.display())))?;
    for entry in entries {
        let entry = entry.map_err(|e| Error::new(format!("cannot list {}: {e}", dir.display())))?;
        let path = entry.path();
        if path.is_dir() {
            if dir == root && entry.file_name() == "META-INF" { continue }
            walk(root, &path, names)?;
        } else if path.extension().is_some_and(|e| e == "class") {
            // Multi-release and module descriptors are not classes of the module.
            if path.file_name().is_some_and(|f| f == "module-info.class" || f == "package-info.class") {
                continue;
            }
            let relative = path.strip_prefix(root).unwrap_or(&path);
            let name = relative.with_extension("");
            names.push(name.to_string_lossy().replace('\\', "/"));
        }
    }
    Ok(())
}

/// Whether an internal class name belongs to the JDK, by package.
pub fn is_jdk_name(internal_name: &str) -> bool {
    ["java/", "javax/", "jdk/", "sun/", "com/sun/"].iter().any(|p| internal_name.starts_with(p))
}

/// Where a class was found.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Origin {
    Application,
    Jdk,
    /// One of the tool's own [`crate::models`].
    Model,
}

/// A class with where it came from.
#[derive(Clone)]
pub struct Loaded {
    pub class: Rc<ClassFile>,
    pub origin: Origin,
}

/// The application classes and the JDK, with lazy loading and a cache.
pub struct ClassPath {
    entries: Vec<Entry>,
    /// Original namespace of the previous release for observable class names and lookups.
    pub(crate) previous: Option<std::sync::Arc<crate::relocate::Previous>>,
    jar_release: Option<u32>,
    /// What a JVM was seen to load ([`ClassObservations`]).
    observations: ClassObservations,
    jdk: Option<JImage>,
    /// Bootstrap bytecode for String range checks on a selected pre-module JDK.
    legacy_boot: Option<crate::zip::ZipArchive>,
    /// Whether the tool's models of JDK classes are part of this class path (they are, unless turned off).
    models: bool,
    cache: RefCell<HashMap<String, Option<Loaded>>>,
    /// Every application class, once read ([`ClassPath::application_classes_shared`]).
    classes: RefCell<Option<Rc<BTreeMap<String, Rc<ClassFile>>>>>,
    /// Whether the own checker runs each class initializer asked about ([`crate::bmc::gaps::runs_initializer`]): a
    /// function of the class path alone.
    pub(crate) initializer_runs: RefCell<HashMap<String, bool>>,
    plain_buffer_formatter: std::cell::OnceCell<bool>,
    string_unit_replacement: std::cell::OnceCell<bool>,
    reflection_copies: std::cell::OnceCell<bool>,
    thread_local_keys: std::cell::OnceCell<bool>,
    class_table_image: std::cell::OnceCell<bool>,
    jar_resource_image: std::cell::OnceCell<bool>,
    properties_reader_image: std::cell::OnceCell<bool>,
    system_properties_image: std::cell::OnceCell<bool>,
    linked_map_image: std::cell::OnceCell<bool>,
    soft_queue_image: std::cell::OnceCell<bool>,
    generic_interface_image: std::cell::OnceCell<bool>,
    byte_array_view_image: std::cell::OnceCell<bool>,
    wildcard_type_image: std::cell::OnceCell<bool>,
    method_return_image: std::cell::OnceCell<bool>,
    explicit_utc: std::cell::OnceCell<bool>,
    string_buffer_layout: std::cell::OnceCell<Option<bool>>,
    basic_base64: std::cell::OnceCell<bool>,
    heap_buffer_copy: std::cell::OnceCell<bool>,
    concurrent_table_layout: std::cell::OnceCell<bool>,
    decimal_tables_image: std::cell::OnceCell<bool>,
    /// The classes whose initializer a check has the observed state of ([`crate::observed`]), set by the check: the
    /// own checker neither runs such an initializer nor meets it as a gap, and the scan does not walk it.
    pub(crate) observed_initializers: RefCell<std::collections::BTreeSet<String>>,
    /// The models on request a check asked for ([`crate::models::ON_REQUEST`]), by internal name, set by the check.
    pub(crate) requested_models: RefCell<std::collections::BTreeSet<String>>,
    /// The time spent reading and parsing class files, for a checker's phases ([`crate::phases`]).
    loading: std::cell::Cell<std::time::Duration>,
    /// Each class asked about, and why it is refused if it is ([`ClassPath::refused`]).
    refusals: RefCell<HashMap<String, Option<String>>>,
    /// The packages of the JDK's image, once asked.
    jdk_packages: std::cell::OnceCell<std::collections::HashSet<String>>,
}

impl Default for ClassPath {
    fn default() -> Self {
        Self::new()
    }
}

impl ClassPath {
    /// An empty class path with no JDK. Add entries with [`add`](Self::add) and a JDK with
    /// [`with_default_jdk`](Self::with_default_jdk).
    pub fn new() -> ClassPath {
        ClassPath { entries: Vec::new(), previous: None, jar_release: configured_jar_release(), observations: configured_observations(), jdk: None, legacy_boot: None, models: true, cache: RefCell::new(HashMap::new()), classes: RefCell::new(None), initializer_runs: Default::default(), plain_buffer_formatter: Default::default(), string_unit_replacement: Default::default(), reflection_copies: Default::default(), thread_local_keys: Default::default(), class_table_image: Default::default(), jar_resource_image: Default::default(), properties_reader_image: Default::default(), system_properties_image: Default::default(), linked_map_image: Default::default(), soft_queue_image: Default::default(), generic_interface_image: Default::default(), byte_array_view_image: Default::default(), wildcard_type_image: Default::default(), method_return_image: Default::default(), explicit_utc: Default::default(), string_buffer_layout: Default::default(), basic_base64: Default::default(), heap_buffer_copy: Default::default(), concurrent_table_layout: Default::default(), decimal_tables_image: Default::default(), observed_initializers: Default::default(), requested_models: Default::default(), loading: Default::default(), refusals: Default::default(), jdk_packages: Default::default() }
    }

    pub(crate) fn with_previous(mut self, previous: Option<std::sync::Arc<crate::relocate::Previous>>) -> Self {
        self.previous = previous;
        self
    }

    pub(crate) fn binary_name(&self, name: &str) -> String {
        crate::relocate::binary_name(name, self.previous.as_deref())
    }

    /// Resolve the binary name as seen by the calling release. A missing definition
    /// is a Java outcome. An array or a definition outside the prepared copy needs the JVM.
    pub(crate) fn named_class(&self, caller: &str, binary: &str, previous: Option<&crate::relocate::Previous>) -> Option<(String, bool)> {
        self.named_class_for_loader(binary, previous, previous.is_some_and(|p| p.original(caller).is_some()))
    }

    pub(crate) fn named_class_for_loader(&self, binary: &str, previous: Option<&crate::relocate::Previous>, older: bool) -> Option<(String, bool)> {
        if binary.starts_with('[') {
            return None;
        }
        let mut name = binary.replace('.', "/");
        if binary.contains('/') {
            return Some((name, false));
        }
        if let Some(old) = previous {
            if older {
                match old.find(&name) {
                    crate::relocate::Found::Class(copy) => name = copy,
                    crate::relocate::Found::NotCopied => return None,
                    crate::relocate::Found::Elsewhere if self.is_application(&name) => return Some((name, false)),
                    crate::relocate::Found::Elsewhere => {}
                }
            } else if old.original(&name).is_some() {
                return Some((name, false));
            }
        }
        if self.refused(&name).is_some() {
            return None;
        }
        let found = self.exists(&name);
        Some((name, found))
    }

    /// Class.forName can select and initialize an application class by a computed name.
    /// Bind its ordered providers, including resources an initializer can read.
    pub(crate) fn lookup_digest(&self) -> Result<String, Error> {
        if let Some(problem) = &self.observations.problem {
            return Err(Error::new(problem.clone()));
        }
        let observed: BTreeMap<_, _> = self.observations.classes.iter().collect();
        let mut providers = serde_json::to_vec(&(self.jar_release, self.observations.feature, observed))
            .map_err(|e| Error::new(e.to_string()))?;
        for entry in &self.entries {
            let (path, kind, digest) = match entry {
                Entry::Jar(jar, path, _) => (path, b'J', jar.sha256()),
                Entry::Dir(path) => (path, b'D', lookup_directory(path, &mut Vec::new())?),
            };
            providers.push(kind);
            providers.extend(path.canonicalize()?.as_os_str().as_encoded_bytes());
            providers.push(0);
            providers.extend(digest.bytes());
        }
        Ok(crate::digest::sha256_hex(&providers))
    }

    /// With or without the tool's models of JDK classes ([`crate::models`]); on by default. Without them, a call
    /// into a modelled class is left to the interpreter's natives, as it was before the models existed.
    pub fn with_models(mut self, models: bool) -> ClassPath {
        self.models = models;
        self.cache.borrow_mut().clear();
        self.classes.replace(None);
        self.byte_array_view_image.take();
        self.wildcard_type_image.take();
        self.method_return_image.take();
        self.initializer_runs.borrow_mut().clear();
        self
    }

    pub fn has_models(&self) -> bool {
        self.models
    }

    /// Adds a directory of classes or a jar, by the path's kind.
    pub fn add(&mut self, path: &Path) -> Result<&mut Self, Error> {
        if path.is_dir() {
            self.entries.push(Entry::Dir(path.to_path_buf()));
        } else if path.is_file() {
            let zip = crate::zip::ZipArchive::open(path)?;
            let versioned = versioned_entries(&zip)?;
            self.entries.push(Entry::Jar(zip, path.to_path_buf(), versioned));
        } else {
            return Err(Error::new(format!("{} is neither a directory nor a jar", path.display())));
        }
        self.cache.borrow_mut().clear();
        self.classes.replace(None);
        self.initializer_runs.borrow_mut().clear();
        self.refusals.borrow_mut().clear();
        Ok(self)
    }

    /// Adds every entry of a `PATH`-style list (`a/classes:lib/b.jar`), skipping entries that do not exist.
    pub fn add_path_list(&mut self, list: &str) -> Result<&mut Self, Error> {
        for part in std::env::split_paths(list) {
            if part.as_os_str().is_empty() || !part.exists() {
                continue;
            }
            self.add(&part)?;
        }
        Ok(self)
    }

    /// Uses the JDK found through `JAVA_HOME` or `PATH` for JDK class shapes, if there is one.
    pub fn with_default_jdk(mut self) -> ClassPath {
        let legacy = std::env::var_os("JAVA_HOME").map(PathBuf::from).and_then(|home| legacy_boot_archive(&home));
        self.legacy_boot = None;
        if let Some(archive) = legacy {
            self.legacy_boot = crate::zip::ZipArchive::open(&archive).ok();
        } else if let Some(jdk) = JImage::open_default() {
            return self.with_jdk(jdk);
        }
        self.jdk = None;
        let major = self.legacy_boot.as_ref().and_then(|boot| boot.read("java/lang/Object.class").ok().flatten())
            .and_then(|bytes| Some(u16::from_be_bytes(bytes.get(6..8)?.try_into().ok()?)));
        self.jar_release = self.jar_release.filter(|&feature| feature <= 8 && major.map(u32::from) == feature.checked_add(44));
        self.reset_runtime_caches();
        self
    }

    pub fn with_jdk(mut self, jdk: JImage) -> ClassPath {
        if let Some(feature) = self.jar_release {
            let major = jdk.read_class("java/lang/Object").ok().flatten()
                .and_then(|bytes| Some(u16::from_be_bytes(bytes.get(6..8)?.try_into().ok()?)));
            if major.map(u32::from) != feature.checked_add(44) {
                self.jar_release = None;
            }
        }
        self.jdk = Some(jdk);
        self.legacy_boot = None;
        self.reset_runtime_caches();
        self
    }

    fn reset_runtime_caches(&mut self) {
        self.plain_buffer_formatter.take();
        self.string_unit_replacement.take();
        self.reflection_copies.take();
        self.thread_local_keys.take();
        self.class_table_image.take();
        self.byte_array_view_image.take();
        self.wildcard_type_image.take();
        self.method_return_image.take();
        self.jar_resource_image.take();
        self.properties_reader_image.take();
        self.system_properties_image.take();
        self.linked_map_image.take();
        self.soft_queue_image.take();
        self.explicit_utc.take();
        self.string_buffer_layout.take();
        self.basic_base64.take();
        self.heap_buffer_copy.take();
        self.concurrent_table_layout.take();
        self.cache.borrow_mut().clear();
        self.classes.replace(None);
        self.refusals.borrow_mut().clear();
        self.jdk_packages = Default::default();
        self.initializer_runs.borrow_mut().clear();
    }

    pub fn jdk(&self) -> Option<&JImage> {
        self.jdk.as_ref()
    }

    pub fn has_jdk(&self) -> bool {
        self.jdk.is_some()
    }

    /// The public constructor itself chooses which exception wins when the array is null and a bound is negative.
    pub(crate) fn string_range_constructor(&self, owner: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        if !matches!((owner, descriptor), ("java/lang/String", "([CII)V" | "([BIII)V") | ("java/lang/StringIndexOutOfBoundsException", "(I)V")) { return None }
        self.bootstrap_method(owner, "<init>", descriptor)
    }

    /// The selected bootstrap class and executable body, including rt.jar on JDK 8.
    pub(crate) fn bootstrap_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        let class = if let Some(boot) = &self.legacy_boot {
            let bytes = boot.read(&format!("{owner}.class")).ok()??;
            let class = ClassFile::parse(&bytes).ok()?;
            if class.name != owner { return None }
            Rc::new(class)
        } else {
            let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
            class
        };
        let method = class.method(name, descriptor)?.clone();
        method.code.as_ref()?;
        Some((class, method))
    }

    /// The entries, for messages.
    pub fn describe(&self) -> Vec<String> {
        self.entries.iter().map(Entry::display).collect()
    }

    /// Every copy of a resource across the entries (`META-INF/spring-configuration-metadata.json` is in many
    /// jars), each with the entry it came from.
    pub fn resources(&self, name: &str) -> Result<Vec<(String, Vec<u8>)>, Error> {
        let mut out = Vec::new();
        for entry in &self.entries {
            let Some(bytes) = entry.resource(name, self.jar_release)? else { continue };
            out.push((entry.display(), bytes));
        }
        Ok(out)
    }

    /// The ordinary built-in loader's base META-INF resources. Decline other providers,
    /// manifest class paths, signed or indexed archives, duplicate URLs and mutable
    /// directory resources. The proof states the clean launch and fixed classpath.
    pub(crate) fn local_jar_resources(&self, name: &str, deployment: Option<&[PathBuf]>) -> Option<Vec<(usize, Vec<u8>, Option<String>)>> {
        let tail = name.strip_prefix("META-INF/")?;
        if tail.len() > 128 || tail.split('/').any(|part| part.is_empty() || part.starts_with('.') || part.contains("..")
            || !part.bytes().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'_' | b'$')))
            || self.jdk()?.contains_resource(name).ok()? { return None; }
        if let Some(files) = deployment {
            let mut original = Self::new().bound_to(self.jar_release);
            for path in files {
                original.add(path).ok()?;
            }
            return original.jar_resource_entries(name);
        }
        self.jar_resource_entries(name)
    }

    fn jar_resource_entries(&self, name: &str) -> Option<Vec<(usize, Vec<u8>, Option<String>)>> {
        let mut seen = std::collections::BTreeSet::new();
        let mut urls = Vec::new();
        for (i, entry) in self.entries.iter().enumerate() {
            let path = match entry { Entry::Dir(dir) => dir, Entry::Jar(_, jar, _) => jar };
            let real = path.canonicalize().ok()?;
            if !seen.insert(real) { return None; }
            match entry {
                Entry::Dir(dir) => match std::fs::symlink_metadata(dir.join(name)) {
                    Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                    _ => return None,
                },
                Entry::Jar(zip, jar, versions) => {
                    if zip.duplicate_names || versions.entries.contains_key(name) || !jar.to_str()?.bytes()
                        .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'_' | b'+' | b'/')) { return None; }
                    if zip.names().any(|n| {
                        let upper = n.to_ascii_uppercase();
                        upper.starts_with("META-INF/") && (upper == "META-INF/INDEX.LIST" || upper.starts_with("META-INF/SIG-")
                            || [".SF", ".RSA", ".DSA", ".EC"].iter().any(|suffix| upper.ends_with(suffix))
                            || upper == "META-INF/MANIFEST.MF" && n != upper)
                    }) { return None; }
                    if zip.contains("META-INF/MANIFEST.MF") {
                        let manifest = zip.checked_resource("META-INF/MANIFEST.MF", 65536)?;
                        if manifest.windows(11).any(|w| w.eq_ignore_ascii_case(b"class-path:")) { return None; }
                    }
                    if zip.contains(name) {
                        if urls.len() == 32 { return None; }
                        urls.push((i, zip.checked_resource(name, 16384)?, self.local_jar_url_path(i, name)));
                    }
                }
            }
        }
        Some(urls)
    }

    /// URLClassPath canonicalizes an input JAR before constructing its file URL.
    /// These ASCII characters survive ParseUtil.encodePath on the selected Unix image.
    /// A relative entry depends on the launching JVM's user.dir. Its bytes can still
    /// be enumerated, but the checker cannot supply the lexical path.
    pub(crate) fn local_jar_url_path(&self, index: usize, resource: &str) -> Option<String> {
        let Entry::Jar(_, jar, _) = self.entries.get(index)? else { return None };
        if !cfg!(unix) || !jar.is_absolute() { return None; }
        let canonical = jar.canonicalize().ok()?;
        let path = canonical.to_str()?;
        if !path.starts_with('/') || !path.bytes().all(|b| b.is_ascii_alphanumeric()
            || matches!(b, b'.' | b'-' | b'_' | b'+' | b'/')) { return None; }
        Some(format!("file:{path}!/{resource}"))
    }

    /// Every application class name, in entry order and sorted within an entry.
    pub fn application_class_names(&self) -> Result<Vec<String>, Error> {
        let mut names = Vec::new();
        for entry in &self.entries {
            names.extend(entry.class_names(self.jar_release)?);
        }
        Ok(names)
    }

    /// An application class's file as its first entry holds it, unparsed, or none: for a copy of it
    /// ([`crate::relocate::with_closure`]).
    pub fn application_bytes(&self, name: &str) -> Result<Option<Vec<u8>>, Error> {
        if let Some(refused) = self.refused(name) {
            return Err(Error::new(refused));
        }
        for entry in &self.entries {
            if let Some(bytes) = self.read_class(entry, name)? {
                return Ok(Some(bytes));
            }
        }
        Ok(None)
    }

    /// Every application class, parsed, keyed by name. Classes found in an earlier entry shadow later ones.
    pub fn application_classes(&self) -> Result<BTreeMap<String, Rc<ClassFile>>, Error> {
        let mut out = BTreeMap::new();
        for name in self.application_class_names()? {
            if out.contains_key(&name) {
                continue;
            }
            if let Some(loaded) = self.load_base(&name)? {
                out.insert(name, loaded.class);
            }
        }
        Ok(out)
    }

    /// [`ClassPath::application_classes`], read once and shared: for a walk that asks at every call site which
    /// classes override a method, over a class path of whole libraries (thousands of classes), where reading the
    /// entries again each time took the gap scan of a Spring Boot method minutes.
    pub fn application_classes_shared(&self) -> Result<Rc<BTreeMap<String, Rc<ClassFile>>>, Error> {
        if let Some(classes) = self.classes.borrow().as_ref() {
            return Ok(classes.clone());
        }
        let classes = Rc::new(self.application_classes()?);
        self.classes.replace(Some(classes.clone()));
        Ok(classes)
    }

    /// Loads a class by internal name: the application entries first, then the JDK, then the tool's models. `None`
    /// if nowhere. An error for a class the tool would read another class file of than a JVM
    /// ([`ClassPath::refused`]).
    pub fn load(&self, name: &str) -> Result<Option<Loaded>, Error> {
        if let Some(refused) = self.refused(name) {
            return Err(Error::new(refused));
        }
        self.load_base(name)
    }

    /// Why a class is refused by name, where the class file the tool would read of it is not the one a JVM loads
    /// (`lib/tests/observed_countermodels.rs`, where each was a false proof):
    /// - the first entry that holds it is a multi-release JAR with a class file of it for a release of Java of its
    ///   own (`META-INF/versions/N/`), which a JVM of that release or later loads in place of the base one, and the
    ///   native check has no pinned runtime release for choosing the correct bytes;
    /// - an entry holds it in a package of the JDK's image (`org.xml.sax.helpers`, `javax.xml.parsers`): a JVM
    ///   loads a class of a package of a module of the boot layer from that module, never from the class path,
    ///   where the tool reads the entries first. Not where the entry's class file is the image's own, byte for
    ///   byte, or one of the tool's models: the tool puts those on a class path itself.
    ///
    /// Refused, not read, until the class file taken is the JVM's.
    pub fn refused(&self, name: &str) -> Option<String> {
        if let Some(known) = self.refusals.borrow().get(name) {
            return known.clone();
        }
        let refused = self.binding_refusal(name).map(|r| r.reason);
        self.refusals.borrow_mut().insert(name.to_string(), refused.clone());
        refused
    }

    /// A class whose effective multi-release member stock JBMC is not qualified to read. The ordinary JAR
    /// passed to JBMC still contains its base member. This applies to helpers as well as to the named subject.
    pub fn jbmc_multi_release_gap(&self) -> Option<String> {
        for (index, root) in self.entries.iter().enumerate() {
            let Entry::Jar(_, path, versions) = root else { continue };
            for (file, releases) in &versions.entries {
                if !file.ends_with(".class") || file == "module-info.class" { continue; }
                let Some(version) = releases.iter().copied().filter(|v| self.jar_release.is_none_or(|feature| *v <= feature)).max() else { continue };
                // An earlier base class wins in both readers. A version-only earlier class is not sufficient
                // evidence of that, since its release may be ineligible or its manifest ambiguous.
                if self.entries[..index].iter().any(|earlier| match earlier {
                    Entry::Dir(dir) => dir.join(file).is_file(),
                    Entry::Jar(zip, _, _) => zip.contains(file),
                }) { continue; }
                let profile = self.jar_release.map_or_else(|| "unbound JDK".to_string(), |v| format!("JDK {v}"));
                return Some(format!("stock JBMC has no qualified multi-release class binding for {file} in provider {index} ({}, {profile}): the deployed class may be META-INF/versions/{version}/{file} while the stock command can inspect the base member", path.display()));
            }
        }
        None
    }

    /// The SHA-256 a JVM of the bound release was seen to load for `name`, when one was given.
    fn observation(&self, name: &str) -> Option<&str> {
        (self.jar_release.is_some() && self.observations.feature == self.jar_release).then(|| self.observations.classes.get(name).map(String::as_str)).flatten()
    }

    /// [`ClassPath::refused`], as data. A class with one class file in its provider and no observation takes the
    /// short way: nothing about it can differ between readers but the JDK's own packages.
    fn binding_refusal(&self, name: &str) -> Option<BindingRefusal> {
        let file = format!("{name}.class");
        let first = self.entries.iter().find(|e| e.holds(&file));
        let versioned = matches!(first, Some(Entry::Jar(_, _, versions)) if versions.entries.contains_key(&file));
        if first.is_some() && (versioned || self.observation(name).is_some() || self.observations.problem.is_some()) {
            return self.bind(name).err().filter(|r| r.code != RefusalCode::MissingClass);
        }
        self.shadows_the_jdk(name).map(|reason| BindingRefusal { code: RefusalCode::ShadowsJdk, class: name.replace('/', "."), reason, selected: None, observed: None, candidates: Vec::new() })
    }

    /// The class file that stands for `name` (internal form) on this class path and bound runtime, or why none
    /// does. The first entry that holds the class provides it. In a multi-release JAR the bound release selects
    /// among its class files; with no release bound, or a manifest whose spelling readers differ on, nothing
    /// selects and the class is refused. Where a JVM was seen to load the class
    /// ([`ClassObservations`]), its bytes must be the rule's, and they settle a manifest the rule cannot.
    pub fn bind(&self, name: &str) -> Result<ClassBinding, BindingRefusal> {
        let class = name.replace('/', ".");
        let file = format!("{name}.class");
        let refusal = |code, reason: String, selected: Option<Candidate>, observed: Option<&str>, candidates: &[Candidate]| BindingRefusal { code, class: class.clone(), reason, selected, observed: observed.map(str::to_string), candidates: candidates.to_vec() };
        if let Some(problem) = &self.observations.problem {
            return Err(refusal(RefusalCode::Unreadable, problem.clone(), None, None, &[]));
        }
        let unreadable = |e: Error| refusal(RefusalCode::Unreadable, e.to_string(), None, None, &[]);
        let Some((index, first)) = self.entries.iter().enumerate().find(|(_, e)| e.holds(&file)) else {
            return Err(refusal(RefusalCode::MissingClass, format!("no entry of the class path holds {class}"), None, None, &[]));
        };
        let candidates = first.candidates(&file).map_err(unreadable)?;
        let observed = self.observation(name);
        let (manifest, releases) = match first {
            Entry::Jar(_, _, versions) => (Some(versions.mode), versions.entries.get(&file)),
            Entry::Dir(_) => (None, None),
        };
        let by_entry = |entry: &str| candidates.iter().find(|c| c.entry == entry).cloned();
        let rule = match (first, releases, self.jar_release) {
            (Entry::Jar(_, path, _), Some(releases), None) => {
                let releases: Vec<String> = releases.iter().map(u32::to_string).collect();
                return Err(refusal(RefusalCode::UnboundRelease, format!(
                    "{class} is a class of a multi-release JAR ({}) that holds a class file of it for Java {} (META-INF/versions/), which a JVM of that release or later loads in place of the base class file; the tool reads only the base, so the class is refused (lib/src/classpath.rs)",
                    path.display(), releases.join(", ")), by_entry(&file), None, &candidates));
            }
            (Entry::Jar(_, _, versions), Some(_), Some(_)) if versions.mode == MultiRelease::Ambiguous => None,
            (Entry::Jar(_, _, versions), _, release) => by_entry(&versions.entry_for(&file, release)),
            (Entry::Dir(_), _, _) => by_entry(&file),
        };
        let listed = || candidates.iter().map(|c| format!("{} ({})", c.entry, &c.sha256[..12])).collect::<Vec<_>>().join(", ");
        let (selected, selected_by) = match (rule, observed) {
            (Some(selected), None) => (selected, SelectedBy::Rule),
            (Some(selected), Some(seen)) if selected.sha256 == seen => (selected, SelectedBy::RuleAndObservation),
            (Some(selected), Some(seen)) => {
                return Err(refusal(RefusalCode::ObservationDiffers, format!(
                    "{class}: the class path and the bound release select {} of {} (sha256 {}), and a JVM of that release was seen to load other bytes (sha256 {seen}); the class is refused until both are the same bytes (lib/src/classpath.rs)",
                    selected.entry, selected.provider, selected.sha256), Some(selected), Some(seen), &candidates));
            }
            (None, Some(seen)) => match candidates.iter().find(|c| c.sha256 == seen) {
                Some(selected) => (selected.clone(), SelectedBy::Observation),
                None => return Err(refusal(RefusalCode::ObservationUnmatched, format!(
                    "{class}: a JVM was seen to load bytes (sha256 {seen}) that no class file of {} has: {}; the class is refused (lib/src/classpath.rs)",
                    first.display(), listed()), None, Some(seen), &candidates)),
            },
            (None, None) if manifest == Some(MultiRelease::Ambiguous) => {
                return Err(refusal(RefusalCode::AmbiguousManifest, format!(
                    "{class} is a class of a JAR ({}) whose manifest spells Multi-Release so that readers differ: the attribute reads true once its continuation lines are joined, and the bytes hold no literal `Multi-Release: true`, which is what the JDK's own reader looks for. The JAR holds {}; which a JVM loads was not observed, so the class is refused (lib/src/classpath.rs)",
                    first.display(), listed()), None, None, &candidates));
            }
            (None, None) => return Err(refusal(RefusalCode::MissingClass, format!("{} holds no class file of {class} for the bound release", first.display()), None, None, &candidates)),
        };
        if let Some(reason) = self.shadows_the_jdk(name) {
            return Err(refusal(RefusalCode::ShadowsJdk, reason, Some(selected), observed, &candidates));
        }
        let mut shadowed = Vec::new();
        for later in self.entries.iter().skip(index + 1).filter(|e| e.holds(&file)) {
            shadowed.extend(later.candidates(&file).map_err(unreadable)?);
        }
        Ok(ClassBinding { class, index, selected, selected_by, bound_release: self.jar_release, manifest, candidates, shadowed })
    }

    /// The bytes of `name` in `entry`: the selected class file's ([`ClassPath::bind`]). Where the manifest leaves
    /// the rule without an answer and a JVM was seen to load one of the entry's class files, that one.
    fn read_class(&self, entry: &Entry, name: &str) -> Result<Option<Vec<u8>>, Error> {
        if let (Entry::Jar(zip, _, versions), Some(seen)) = (entry, self.observation(name)) {
            let file = format!("{name}.class");
            if versions.mode == MultiRelease::Ambiguous && versions.entries.contains_key(&file) {
                if let Some(selected) = entry.candidates(&file)?.into_iter().find(|c| c.sha256 == seen) {
                    return zip.read(&selected.entry);
                }
            }
        }
        entry.read(name, self.jar_release)
    }

    /// For each logical name of the JAR at `index`, the entry that stands for it under the bound release: what a
    /// copy of the JAR as a JVM of that release sees it is made of. `META-INF/versions/` itself is left out.
    pub fn logical_entries(&self, index: usize) -> Option<(MultiRelease, BTreeMap<String, String>)> {
        let Some(Entry::Jar(zip, _, versions)) = self.entries.get(index) else { return None };
        let mut out: BTreeMap<String, String> = zip.names().filter(|n| !n.starts_with("META-INF/versions/") && !n.ends_with('/'))
            .map(|n| (n.to_string(), versions.entry_for(n, self.jar_release))).collect();
        if versions.mode == MultiRelease::Enabled {
            for name in versions.entries.keys() {
                let entry = versions.entry_for(name, self.jar_release);
                if entry != *name {
                    out.insert(name.clone(), entry);
                }
            }
        }
        Some((versions.mode, out))
    }

    /// The bytes a binding names, read from where it says they are.
    pub fn bound_bytes(&self, binding: &ClassBinding) -> Result<Vec<u8>, Error> {
        let missing = || Error::new(format!("{} is no longer in {}", binding.selected.entry, binding.selected.provider));
        match self.entries.get(binding.index).ok_or_else(missing)? {
            Entry::Dir(dir) => std::fs::read(dir.join(&binding.selected.entry)).map_err(|e| Error::new(format!("cannot read {}: {e}", dir.join(&binding.selected.entry).display()))),
            Entry::Jar(zip, _, _) => zip.read(&binding.selected.entry)?.ok_or_else(missing),
        }
    }

    /// This class path with multi-release lookup bound to `release`, as given: for a caller that has checked the
    /// runtime itself. The command line binds through `JVMCONTRACT_JAR_RELEASE`, which is checked against the JDK
    /// ([`configured_jar_release`]); adding a JDK afterwards ([`ClassPath::with_jdk`]) checks it again.
    pub fn bound_to(mut self, release: Option<u32>) -> ClassPath {
        self.jar_release = release;
        self.reset_runtime_caches();
        self
    }

    /// The release multi-release lookup is bound to, when a runtime is bound.
    pub fn bound_release(&self) -> Option<u32> {
        self.jar_release
    }

    /// [`ClassPath::refused`]'s second case.
    fn shadows_the_jdk(&self, name: &str) -> Option<String> {
        // The tool's own models are put on a class path as an entry (`models::write_to`, JBMC's): each is a stand-in
        // for the JDK's class by design, and none is the application's.
        if crate::models::find(name).is_some() {
            return None;
        }
        let jdk = self.jdk.as_ref()?;
        let package = name.rsplit_once('/').map_or("", |(p, _)| p);
        let packages = self.jdk_packages.get_or_init(|| jdk.class_names().filter_map(|c| c.rsplit_once('/').map(|(p, _)| p.to_string())).collect());
        if !packages.contains(package) {
            return None;
        }
        let (entry, bytes) = self.entries.iter().find_map(|e| self.read_class(e, name).ok().flatten().map(|b| (e, b)))?;
        // The JDK's own class file, put on a class path so that its bytecode is run (`contract_proving`, JBMC's
        // class path), is the class a JVM loads.
        if jdk.read_class(name).ok().flatten().is_some_and(|own| own == bytes) {
            return None;
        }
        let module = jdk.module_of(name).or_else(|| jdk.class_names().find(|c| c.rsplit_once('/').is_some_and(|(p, _)| p == package)).and_then(|c| jdk.module_of(c)));
        Some(format!(
            "{} is on the class path ({}) in the package {} of the JDK's module {}, which a JVM loads from the module and never from the class path; the tool would read the class path's class file, so the class is refused (lib/src/classpath.rs)",
            name.replace('/', "."),
            entry.display(),
            package.replace('/', "."),
            module.as_deref().unwrap_or("of the boot layer")
        ))
    }

    /// [`ClassPath::load`] of the class file the entries hold first, which the enumeration of every class reads: a
    /// class refused by name is still one of the application's, for the walks that ask which classes there are.
    fn load_base(&self, name: &str) -> Result<Option<Loaded>, Error> {
        if let Some(cached) = self.cache.borrow().get(name) {
            return Ok(cached.clone());
        }
        // A model loaded on the way times itself; this counts the whole load once.
        let (before, started) = (self.loading.get(), std::time::Instant::now());
        let loaded = self.load_uncached(name);
        self.loading.set(before + started.elapsed());
        let loaded = loaded?;
        self.cache.borrow_mut().insert(name.to_string(), loaded.clone());
        Ok(loaded)
    }

    /// How long reading and parsing class files has taken so far, models included.
    pub fn loading(&self) -> std::time::Duration {
        self.loading.get()
    }

    fn load_uncached(&self, name: &str) -> Result<Option<Loaded>, Error> {
        for entry in &self.entries {
            if let Some(bytes) = self.read_class(entry, name)? {
                let class = ClassFile::parse(&bytes).map_err(|e| Error::new(format!("{name} in {}: {e}", entry.display())))?;
                return Ok(Some(Loaded { class: Rc::new(class), origin: Origin::Application }));
            }
        }
        if let Some(jdk) = &self.jdk {
            if let Some(bytes) = jdk.read_class(name)? {
                let class = ClassFile::parse(&bytes).map_err(|e| Error::new(format!("{name} in the JDK image: {e}")))?;
                return Ok(Some(Loaded { class: Rc::new(class), origin: Origin::Jdk }));
            }
        }
        // A model that is no class of the JDK (the stream models' own classes) has its shape from the model.
        if let Some(class) = self.model(name).or_else(|| self.checker_model(name).filter(|_| crate::models::find(name).is_some_and(|m| m.checker_only))) {
            return Ok(Some(Loaded { class, origin: Origin::Model }));
        }
        Ok(None)
    }

    /// The tool's model of a JDK class, if it has one and models are on. This is the class to *execute* for the
    /// name; for its shape, [`load`](Self::load) prefers the application and the JDK image. A model that is only
    /// for JBMC's class path ([`Model::jbmc_only`](crate::models::Model::jbmc_only)) is not given: the interpreter
    /// and the tool's own checker keep their own handling of the class.
    pub fn model(&self, name: &str) -> Option<Rc<ClassFile>> {
        if crate::models::find(name).is_some_and(|m| m.jbmc_only) {
            return None;
        }
        self.any_model(name)
    }

    /// The model the tool's own checker runs for a JDK class: [`model`](Self::model)'s, and also the models only
    /// for JBMC's class path that the checker runs as bytecode ([`crate::models::CHECKER_RUNS`], `java.lang.Enum`),
    /// where the interpreter keeps its natives.
    pub fn checker_model(&self, name: &str) -> Option<Rc<ClassFile>> {
        if crate::models::find(name).is_some_and(|m| m.jbmc_only && !self.runs_model(name)) {
            return None;
        }
        self.any_model(name)
    }

    /// Whether the own checker runs the model of the class as bytecode: one of [`crate::models::CHECKER_RUNS`], or
    /// a class of a model on request that the check asked for ([`crate::models::ON_REQUEST`]).
    pub fn runs_model(&self, name: &str) -> bool {
        crate::models::CHECKER_RUNS.contains(&name) || crate::models::on_request(name).is_some_and(|r| self.requested_models.borrow().contains(r))
    }

    fn any_model(&self, name: &str) -> Option<Rc<ClassFile>> {
        if !self.models {
            return None;
        }
        let key = format!("model:{name}");
        if let Some(cached) = self.cache.borrow().get(&key) {
            return cached.as_ref().map(|l| l.class.clone());
        }
        let started = std::time::Instant::now();
        let loaded = crate::models::class(name).ok().flatten().map(|class| Loaded { class: Rc::new(class), origin: Origin::Model });
        self.loading.set(self.loading.get() + started.elapsed());
        let class = loaded.as_ref().map(|l| l.class.clone());
        self.cache.borrow_mut().insert(key, loaded);
        class
    }

    /// Classes the interpreter executes as bytecode: application classes, selected JDK
    /// collection classes and registered models. Other JDK calls use its natives.
    pub fn bytecode(&self, name: &str) -> Result<Option<Rc<ClassFile>>, Error> {
        if let Some(class) = self.application(name)? {
            return Ok(Some(class));
        }
        if name == "java/util/AbstractList" {
            if let Some(Loaded { class, origin: Origin::Jdk }) = self.load(name)? { return Ok(Some(class)); }
        }
        Ok(self.state_image_class(name).or_else(|| self.map_image_class(name)).or_else(|| self.model(name)))
    }

    /// Whether [`bytecode`](Self::bytecode) has a class for the name.
    pub fn has_bytecode(&self, name: &str) -> bool {
        matches!(self.bytecode(name), Ok(Some(_)))
    }

    /// The method the interpreter runs for `owner.name(descriptor)`: declared by the class or inherited from a
    /// superclass or interface that has bytecode here (an application class or a model). The search stops at the
    /// first JDK class in the chain: what is inherited from the JDK is the natives' business.
    pub fn bytecode_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        self.method_in(owner, name, descriptor, &|c| self.bytecode(c).ok().flatten())
    }

    /// [`bytecode_method`](Self::bytecode_method) as the tool's own checker finds a method: through its models
    /// too ([`checker_model`](Self::checker_model)), so that an enum's `ordinal()` is `java.lang.Enum`'s model.
    pub fn checker_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        self.method_in(owner, name, descriptor, &|c| match self.application(c) {
            Ok(Some(class)) => Some(class),
            _ => {
                if let Some(class) = self.checked_image_class(c) { return Some(class); }
                let model = self.checker_model(c)?;
                // Enum's model constructs the JDK's name and ordinal fields. For ordering, execute the
                // selected image's own comparison, bridge cast and declaring-class check on those fields.
                if c == "java/lang/Enum" && matches!((name, descriptor),
                    ("compareTo", "(Ljava/lang/Enum;)I" | "(Ljava/lang/Object;)I")
                    | ("hashCode", "()I") | ("getDeclaringClass", "()Ljava/lang/Class;")) {
                    if let Ok(Some(Loaded { class, origin: Origin::Jdk })) = self.load(c) {
                        return Some(class);
                    }
                }
                Some(model)
            }
        })
    }

    /// The final suppression methods and the exception handling they reach, from the selected runtime.
    /// Both engines execute these bodies on the state of a constructor they observed.
    pub(crate) fn throwable_image_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        if !matches!((owner, name, descriptor),
            ("java/lang/Throwable", "addSuppressed", "(Ljava/lang/Throwable;)V")
            | ("java/lang/Throwable", "getSuppressed", "()[Ljava/lang/Throwable;")
            | ("java/lang/NullPointerException", "getMessage", "()Ljava/lang/String;")
            | ("java/util/Objects", "requireNonNull", "(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;")) {
            return None;
        }
        let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
        let method = class.method(name, descriptor)?.clone();
        method.code.as_ref()?;
        Some((class, method))
    }

    /// The text of these factories is specified. Its identity is fresh only when every
    /// normal return in the selected image constructs a String from its encoded bytes.
    pub(crate) fn fresh_string_factory(&self, owner: &str, name: &str, descriptor: &str) -> bool {
        use crate::classfile::{Insn, Kind};
        let Ok(Some(Loaded { class, origin: Origin::Jdk })) = self.load(owner) else { return false };
        let Some(code) = class.method(name, descriptor).and_then(|m| m.code.as_ref()) else { return false };
        let Ok(insns) = code.instructions() else { return false };
        let mut returns = 0;
        for (i, (_, insn)) in insns.iter().enumerate() {
            if !matches!(insn, Insn::Return(Some(Kind::Ref))) { continue; }
            let (start, c, m) = match &insns[..i] {
                [.., (start, Insn::New(c)), (_, Insn::Dup), (_, Insn::Load(Kind::Ref, _)), (_, Insn::IConst(_)), (_, Insn::InvokeSpecial(m))]
                    if owner == "java/lang/Long" => (start, c, m),
                [.., (start, Insn::New(c)), (_, Insn::Dup), (_, Insn::Load(Kind::Int, 0)), (_, Insn::InvokeStatic(bytes)), (_, Insn::IConst(_)), (_, Insn::InvokeSpecial(m))]
                    if owner == "java/lang/String" && class.pool.member(*bytes).is_ok_and(|b| matches!(b.owner.as_str(), "java/lang/StringLatin1" | "java/lang/StringUTF16")
                        && b.name == "toBytes" && b.descriptor == "(C)[B") => (start, c, m),
                _ => return false,
            };
            if class.pool.class_name(*c).ok() != Some("java/lang/String")
                || !class.pool.member(*m).is_ok_and(|m| m.owner == "java/lang/String" && m.name == "<init>" && m.descriptor == "([BB)V") { return false; }
            // No branch can jump into the construction sequence and return another reference.
            let end = insns[i].0;
            if !code.exception_table.is_empty() || insns.iter().any(|(_, op)| matches!(op, Insn::Jsr(_) | Insn::Ret(_))
                || op.targets().iter().any(|pc| pc > start && *pc <= end)) { return false; }
            returns += 1;
        }
        returns > 0
    }

    /// Follow the selected standard charset to the literal stored in Charset.name.
    /// A different constructor or getter leaves the identity of the returned String open.
    pub(crate) fn charset_name_literal(&self, field: &str) -> Option<Vec<u16>> {
        use crate::classfile::{Insn, Kind};
        use Insn::*;
        let image = |name: &str| match self.load(name).ok()?? {
            Loaded { class, origin: Origin::Jdk } => Some(class), _ => None,
        };
        let code = |cf: &ClassFile, name: &str, desc: &str| {
            let body = cf.method(name, desc)?.code.as_ref()?;
            if !body.exception_table.is_empty() { return None; }
            body.instructions().ok()
        };
        // A factory assignment in these straight-line initializers must be the
        // unique write of the static final field on every normal return.
        let factory_write = |cf: &ClassFile, ops: &[(u32, Insn)], field: &str, desc: &str| {
            let declaration = cf.field(field)?;
            if !declaration.is_final() || !declaration.is_static() || declaration.descriptor != desc
                || !matches!(ops.last(), Some((_, Return(None))))
                || ops[..ops.len() - 1].iter().any(|(_, op)| !op.targets().is_empty() || matches!(op, Return(_) | Ret(_))) {
                return None;
            }
            let mut writes = ops.iter().enumerate().filter(|(_, (_, op))| matches!(op, PutStatic(i) if cf.pool.member(*i)
                .is_ok_and(|m| m.owner == cf.name && m.name == field && m.descriptor == desc)));
            let (write, _) = writes.next()?;
            writes.next().is_none().then_some(write)
        };
        let charset = "java/nio/charset/Charset";
        let provider = format!("sun/nio/cs/{field}");
        let std = image("java/nio/charset/StandardCharsets")?;
        let init = code(&std, "<clinit>", "()V")?;
        let write = factory_write(&std, &init, field, "Ljava/nio/charset/Charset;")?;
        let allocates = |cf: &ClassFile, ops: &[(u32, Insn)], at: usize| {
            matches!(ops.get(at.saturating_sub(3)..at), Some([(_,New(n)),(_,Dup),(_,InvokeSpecial(i))])
                if cf.pool.class_name(*n).ok() == Some(provider.as_str()) && cf.pool.member(*i).is_ok_and(|m|
                    m.owner == provider && m.name == "<init>" && m.descriptor == "()V"))
        };
        let implementation = image(&provider)?;
        if !allocates(&std, &init, write) {
            let GetStatic(i) = init.get(write.checked_sub(1)?)?.1 else { return None };
            let m = std.pool.member(i).ok()?;
            if m.owner != provider || m.name != "INSTANCE" || m.descriptor != format!("L{provider};") { return None; }
            let init = code(&implementation, "<clinit>", "()V")?;
            let idx = factory_write(&implementation, &init, &m.name, &m.descriptor)?;
            if !allocates(&implementation, &init, idx) { return None; }
        }
        let body = code(&implementation, "<init>", "()V")?;
        let [(_,Load(Kind::Ref,0)),(_,Ldc(name)),(_,InvokeStatic(aliases)),(_,InvokeSpecial(call)),(_,Return(None))] = body.as_slice() else { return None };
        let aliases = implementation.pool.member(*aliases).ok()?;
        let call = implementation.pool.member(*call).ok()?;
        let desc = "(Ljava/lang/String;[Ljava/lang/String;)V";
        if aliases.descriptor != "()[Ljava/lang/String;" || call.name != "<init>" || call.descriptor != desc
            || implementation.super_class.as_deref() != Some(&call.owner) { return None; }
        if call.owner != charset {
            let parent = image(&call.owner)?;
            let body = code(&parent, "<init>", desc)?;
            let [(_,Load(Kind::Ref,0)),(_,Load(Kind::Ref,1)),(_,Load(Kind::Ref,2)),(_,InvokeSpecial(i)),(_,Return(None))] = body.as_slice() else { return None };
            let c = parent.pool.member(*i).ok()?;
            if c.owner != charset || c.name != "<init>" || c.descriptor != desc || parent.super_class.as_deref() != Some(charset) { return None; }
        }
        let cf = image(charset)?;
        let canonical = cf.field("name")?;
        if !canonical.is_final() || canonical.descriptor != "Ljava/lang/String;" { return None; }
        let body = code(&cf, "<init>", desc)?;
        let writes: Vec<_> = body.iter().enumerate().filter(|(_, (_, i))| matches!(i, PutField(f) if cf.pool.member(*f).is_ok_and(|m| m.owner==charset && m.name=="name"))).collect();
        let [(i,(at,_))] = writes.as_slice() else { return None };
        let start = i.checked_sub(2)?;
        if !matches!(body.get(start..*i), Some([(_,Load(Kind::Ref,0)),(_,Load(Kind::Ref,1))]))
            || body.iter().any(|(pc,op)| matches!(op, Store(_,0 | 1)) || (*pc < *at && matches!(op, Return(_)))
                || op.targets().iter().any(|target| *target > body[start].0 && *target <= *at || (*pc < *at && *target > *at))) { return None; }
        let getter = code(&cf, "name", "()Ljava/lang/String;")?;
        let [(_,Load(Kind::Ref,0)),(_,GetField(i)),(_,Return(Some(Kind::Ref)))] = getter.as_slice() else { return None };
        let read = cf.pool.member(*i).ok()?;
        if read.owner != charset || read.name != "name" || read.descriptor != canonical.descriptor { return None; }
        Some(implementation.pool.loadable(*name).ok()?.string_units()?.into_owned())
    }

    /// The PrintWriter access registration in this image stores its one argument in
    /// a bootstrap field. Qualify that write without taking over other SharedSecrets state.
    pub(crate) fn print_writer_access_field(&self, setter: &crate::classfile::MemberRef) -> Option<String> {
        use crate::classfile::{Insn::*, Kind};
        let desc = "Ljdk/internal/access/JavaIOPrintWriterAccess;";
        if (setter.owner.as_str(), setter.name.as_str(), setter.descriptor.as_str()) !=
            ("jdk/internal/access/SharedSecrets", "setJavaIOCPrintWriterAccess", "(Ljdk/internal/access/JavaIOPrintWriterAccess;)V") { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(&setter.owner).ok()?? else { return None };
        let method = class.method(&setter.name, &setter.descriptor)?;
        let code = method.code.as_ref()?;
        let ops = code.instructions().ok()?;
        let [(_, Load(Kind::Ref, 0)), (_, PutStatic(i)), (_, Return(None))] = ops.as_slice() else { return None };
        let f = class.pool.member(*i).ok()?;
        let field = class.field(&f.name)?;
        (method.is_static() && code.exception_table.is_empty() && f.owner == class.name && f.descriptor == desc
            && field.is_static() && field.descriptor == desc).then_some(f.name)
    }

    /// Check that the JDK holder's final JLA field receives the fieldless provider
    /// installed by System during bootstrap, through the actual SharedSecrets getter.
    pub(crate) fn language_access_provider(&self, holder: &str) -> Option<String> {
        use crate::classfile::{Insn::*, Kind};
        let image = |owner: &str| match self.load(owner).ok()?? {
            Loaded { class, origin: Origin::Jdk } => Some(class), _ => None,
        };
        let code = |cf: &ClassFile, name: &str, desc: &str| {
            let body = cf.method(name, desc)?.code.as_ref()?;
            body.exception_table.is_empty().then(|| body.instructions().ok()).flatten()
        };
        let access = "jdk/internal/access/JavaLangAccess";
        let shared = image("jdk/internal/access/SharedSecrets")?;
        let getter = code(&shared, "getJavaLangAccess", "()Ljdk/internal/access/JavaLangAccess;")?;
        let setter = code(&shared, "setJavaLangAccess", "(Ljdk/internal/access/JavaLangAccess;)V")?;
        let [(_,GetStatic(read)),(_,Return(Some(Kind::Ref)))] = getter.as_slice() else { return None };
        let [(_,Load(Kind::Ref,0)),(_,PutStatic(write)),(_,Return(None))] = setter.as_slice() else { return None };
        let field = shared.pool.member(*read).ok()?;
        if field.owner != shared.name || field.descriptor != "Ljdk/internal/access/JavaLangAccess;"
            || shared.pool.member(*write).ok()? != field { return None; }
        let system = image("java/lang/System")?;
        let install = code(&system, "setJavaLangAccess", "()V")?;
        let [(_, New(c)), (_, Dup), (_, InvokeSpecial(init)), (_, InvokeStatic(set)), (_, Return(None))] = install.as_slice() else { return None };
        let provider = system.pool.class_name(*c).ok()?;
        let ctor = system.pool.member(*init).ok()?;
        let assign = system.pool.member(*set).ok()?;
        if ctor.owner != provider || ctor.name != "<init>" || ctor.descriptor != "()V"
            || assign.owner != shared.name || assign.name != "setJavaLangAccess" || assign.descriptor != "(Ljdk/internal/access/JavaLangAccess;)V" { return None; }
        let implementation = image(provider)?;
        if implementation.super_class.as_deref() != Some("java/lang/Object") || !implementation.interfaces.iter().any(|i| i == access)
            || implementation.fields.iter().any(|f| !f.is_static()) { return None; }
        let bootstrap = system.method("initPhase1", "()V")?.code.as_ref()?.instructions().ok()?;
        if !matches!(bootstrap.first(), Some((_,InvokeStatic(i))) if system.pool.member(*i)
            .is_ok_and(|m| m.owner == system.name && m.name == "setJavaLangAccess" && m.descriptor == "()V")) { return None; }
        let holder = image(holder)?;
        let init = code(&holder, "<clinit>", "()V")?;
        let final_field = holder.field("JLA")?;
        if !final_field.is_static() || !final_field.is_final() || final_field.descriptor != field.descriptor
            || !matches!(init.last(), Some((_, Return(None)))) || init[..init.len()-1].iter().any(|(_, op)| !op.targets().is_empty() || matches!(op, Return(_) | Ret(_))) { return None; }
        let mut writes = init.iter().enumerate().filter(|(_,(_,op))| matches!(op, PutStatic(i) if holder.pool.member(*i)
            .is_ok_and(|m| m.owner == holder.name && m.name == "JLA" && m.descriptor == field.descriptor)));
        let (at, _) = writes.next()?;
        let InvokeStatic(index) = init[at.checked_sub(1)?].1 else { return None };
        let get = holder.pool.member(index).ok()?;
        (writes.next().is_none() && get.owner == shared.name && get.name == "getJavaLangAccess"
            && get.descriptor == "()Ljdk/internal/access/JavaLangAccess;").then(|| provider.to_owned())
    }

    /// The Java 25 DataInputStream initializer caches the VM's existing provider for readUTF.
    pub(crate) fn data_input_access(&self, caller: &str, method: &str, member: &crate::classfile::MemberRef) -> Option<String> {
        if caller != "java/io/DataInputStream" || method != "<clinit>" || member.owner != "jdk/internal/access/SharedSecrets"
            || member.name != "getJavaLangAccess" || member.descriptor != "()Ljdk/internal/access/JavaLangAccess;" { return None; }
        self.language_access_provider(caller)
    }

    /// JDK array operations and the character and collection methods used by their callers.
    pub(crate) fn collection_static(&self, owner: &str, name: &str, descriptor: &str) -> bool {
        matches!((owner, name, descriptor),
            ("java/util/Arrays", "fill", "([BB)V" | "([CC)V" | "([II)V" | "([IIII)V" | "([Ljava/lang/Object;Ljava/lang/Object;)V")
            | ("java/lang/StringUTF16", "newBytesFor", "(I)[B")
            | ("java/lang/StringUTF16", "newBytesLength", "(I)I")
            | ("java/lang/Character", "toLowerCase", "(C)C" | "(I)I")
            | ("java/lang/reflect/Modifier", "isStatic", "(I)Z")
            | ("java/net/URLDecoder", "decode", "(Ljava/lang/String;Ljava/nio/charset/Charset;)Ljava/lang/String;")
            | ("java/util/Set", "of", "([Ljava/lang/Object;)Ljava/util/Set;")
            | ("java/lang/Character", "isJavaIdentifierPart" | "isUpperCase", "(C)Z" | "(I)Z")
            | ("java/util/Arrays", "rangeCheck", "(III)V")
            | ("jdk/internal/util/ArraysSupport", "newLength", "(III)I")
            | ("jdk/internal/util/ArraysSupport", "hugeLength", "(II)I")
            | ("java/util/Arrays", "copyOfRange" | "copyOfRangeByte", "([BII)[B")
            | ("java/util/Arrays", "checkLength", "(II)V")
            | ("java/util/ArrayDeque", "inc" | "dec", "(II)I")
            | ("java/util/ArrayDeque", "sub", "(III)I")
            | ("java/util/ArrayDeque", "elementAt" | "nonNullElementAt", "([Ljava/lang/Object;I)Ljava/lang/Object;")
            | ("java/nio/ByteBuffer", "allocate", "(I)Ljava/nio/ByteBuffer;")
            | ("java/nio/ByteBuffer", "wrap", "([B)Ljava/nio/ByteBuffer;" | "([BII)Ljava/nio/ByteBuffer;")
            | ("java/nio/channels/Channels", "newChannel", "(Ljava/io/OutputStream;)Ljava/nio/channels/WritableByteChannel;")
            | ("java/nio/CharBuffer", "wrap", "([CII)Ljava/nio/CharBuffer;" | "([C)Ljava/nio/CharBuffer;")
            | ("java/lang/String", "decodeASCII", "([BI[CII)I")
            | ("java/lang/String", "rangeCheck", "([CII)Ljava/lang/Void;")
            | ("java/lang/StringCoding", "countPositives", "([BII)I")
            | ("java/lang/StringLatin1", "inflate", "([BI[CII)V")
            | ("sun/nio/cs/UTF_8", "updatePositions", "(Ljava/nio/Buffer;ILjava/nio/Buffer;I)V")
            | ("java/util/Arrays", "sort" | "legacyMergeSort", "([Ljava/lang/Object;Ljava/util/Comparator;)V" | "([Ljava/lang/Object;)V")
            | ("java/util/Arrays", "mergeSort", "([Ljava/lang/Object;[Ljava/lang/Object;III)V" | "([Ljava/lang/Object;[Ljava/lang/Object;IIILjava/util/Comparator;)V")
            | ("java/util/Collections", "reverseOrder", "(Ljava/util/Comparator;)Ljava/util/Comparator;")
            | ("java/util/Collections", "emptyIterator", "()Ljava/util/Iterator;")
            | ("java/util/Arrays", "asList", "([Ljava/lang/Object;)Ljava/util/List;")
            | ("java/util/stream/Stream", "of", "([Ljava/lang/Object;)Ljava/util/stream/Stream;")
            | ("java/util/Arrays", "stream", "([Ljava/lang/Object;)Ljava/util/stream/Stream;" | "([Ljava/lang/Object;II)Ljava/util/stream/Stream;")
            | ("java/util/Arrays", "spliterator", "([Ljava/lang/Object;II)Ljava/util/Spliterator;")
            | ("java/util/Collections", "unmodifiableSet", "(Ljava/util/Set;)Ljava/util/Set;")
            | ("java/util/Collections", "unmodifiableMap", "(Ljava/util/Map;)Ljava/util/Map;")
            | ("java/util/Collections", "synchronizedMap", "(Ljava/util/Map;)Ljava/util/Map;")
            | ("java/util/Collections", "newSetFromMap", "(Ljava/util/Map;)Ljava/util/Set;")
            | ("java/util/Collections", "synchronizedSet", "(Ljava/util/Set;Ljava/lang/Object;)Ljava/util/Set;")
            | ("java/util/concurrent/ConcurrentHashMap", "spread" | "tableSizeFor", "(I)I")
            | ("java/util/Collections", "unmodifiableList", "(Ljava/util/List;)Ljava/util/List;")
            | ("java/util/Collections", "singletonList", "(Ljava/lang/Object;)Ljava/util/List;")
            | ("java/util/Collections", "singleton", "(Ljava/lang/Object;)Ljava/util/Set;")
            | ("java/util/Collections", "singletonIterator", "(Ljava/lang/Object;)Ljava/util/Iterator;")
            | ("java/util/Objects", "equals", "(Ljava/lang/Object;Ljava/lang/Object;)Z")
            | ("java/util/Objects", "toString", "(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/String;")
            | ("java/util/Objects", "hash", "([Ljava/lang/Object;)I")
            | ("java/util/Objects", "hashCode", "(Ljava/lang/Object;)I")
            | ("java/util/Objects", "checkFromIndexSize" | "checkFromToIndex", "(III)I")
            | ("jdk/internal/util/Preconditions", "checkIndex", "(IILjava/util/function/BiFunction;)I")
            | ("jdk/internal/util/Preconditions", "checkFromIndexSize" | "checkFromToIndex", "(IIILjava/util/function/BiFunction;)I")
            | ("jdk/internal/util/ArraysSupport", "hashCode", "([Ljava/lang/Object;III)I")
            | ("java/util/Arrays", "equals", "([Ljava/lang/Object;[Ljava/lang/Object;)Z")
            | ("java/util/Arrays", "hashCode", "([Ljava/lang/Object;)I"))
    }

    /// The public empty-list factory and field share the one EmptyList allocated in
    /// Collections' straight-line initializer. This is also Throwable's suppression sentinel.
    pub(crate) fn collections_empty_singleton(&self, factory_name: &str) -> bool {
        use crate::classfile::{Insn, Kind};
        const C: &str = "java/util/Collections";
        let (field, desc, class_name) = match factory_name {
            "emptyList" => ("EMPTY_LIST", "Ljava/util/List;", "java/util/Collections$EmptyList"),
            "emptySet" => ("EMPTY_SET", "Ljava/util/Set;", "java/util/Collections$EmptySet"),
            _ => return false,
        };
        let Ok(Some(Loaded { class, origin: Origin::Jdk })) = self.load(C) else { return false };
        let list = |i| class.pool.member(i).is_ok_and(|f| (f.owner.as_str(), f.name.as_str(), f.descriptor.as_str()) == (C, field, desc));
        let Some(factory) = class.method(factory_name, &format!("(){desc}")).and_then(|m| m.code.as_ref()) else { return false };
        if !factory.instructions().is_ok_and(|ops| matches!(ops.as_slice(), [(_, Insn::GetStatic(i)), (_, Insn::Return(Some(Kind::Ref)))] if list(*i))) { return false; }
        let Some(init) = class.method("<clinit>", "()V").and_then(|m| m.code.as_ref()) else { return false };
        let Ok(ops) = init.instructions() else { return false };
        if !init.exception_table.is_empty() || ops.iter().any(|(_, i)| !i.targets().is_empty()) { return false; }
        let writes = ops.iter().filter(|(_, i)| matches!(i, Insn::PutStatic(f) if list(*f))).count();
        writes == 1 && ops.windows(4).any(|four| matches!(four,
            [(_, Insn::New(c)), (_, Insn::Dup), (_, Insn::InvokeSpecial(m)), (_, Insn::PutStatic(f))] if list(*f)
                && class.pool.class_name(*c).ok() == Some(class_name)
                && class.pool.member(*m).is_ok_and(|ctor| (ctor.owner.as_str(), ctor.name.as_str(), ctor.descriptor.as_str()) == (class_name, "<init>", "()V"))))
    }

    /// Fingerprint the complete bootstrap class files in order for a qualified JDK operation.
    fn matches_jdk_classes(&self, names: &[&str], digests: &[&str]) -> bool {
        let mut bytes = Vec::new();
        for &name in names {
            let body = if let Some(image) = self.jdk() { image.read_class(name).ok().flatten() }
                else { self.legacy_boot.as_ref().and_then(|archive| archive.read(&format!("{name}.class")).ok().flatten()) };
            let Some(body) = body else { return false };
            bytes.extend(body);
        }
        digests.contains(&crate::digest::sha256_hex(&bytes).as_str())
    }

    /// The five arithmetic tables are read-only after initialization on this image. Decode
    /// their literal array initializers from the selected class, including every cell.
    pub(crate) fn decimal_table(&self, owner: &str, field: &str) -> Option<(crate::classfile::Type, Vec<i64>)> {
        use crate::classfile::{ArrayKind, BootstrapArg, Insn, Type};
        let (kind, element, descriptor) = match (owner, field) {
            ("java/math/BigInteger", "digitsPerInt" | "intRadix") => (ArrayKind::Int, Type::Int, "[I"),
            ("java/math/BigInteger", "bitsPerDigit") | ("java/math/BigDecimal", "LONG_TEN_POWERS_TABLE" | "THRESHOLDS_TABLE") =>
                (ArrayKind::Long, Type::Long, "[J"),
            _ => return None,
        };
        if !*self.decimal_tables_image.get_or_init(|| self.matches_jdk_classes(&["java/math/BigInteger", "java/math/BigDecimal"],
                    &["174944a78445d7e38620917a7b3e4567b5b080f32dc10518d7550cd8ac5b4658"])) { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
        let code = class.method("<clinit>", "()V")?.code.as_ref()?.instructions().ok()?;
        let end = code.iter().position(|(_, op)| matches!(op, Insn::PutStatic(i) if class.pool.member(*i).is_ok_and(|m|
            m.owner == owner && m.name == field && m.descriptor == descriptor)))?;
        let alloc = code[..end].iter().rposition(|(_, op)| matches!(op, Insn::NewArray(k) if *k == kind))?;
        let Insn::IConst(length) = code.get(alloc.checked_sub(1)?)?.1 else { return None };
        let entries = &code[alloc + 1..end];
        if entries.len() != usize::try_from(length).ok()?.checked_mul(4)? { return None; }
        let cells = entries.chunks_exact(4).enumerate().map(|(index, ops)| {
            let [(_, Insn::Dup), (_, Insn::IConst(i)), (_, value), (_, Insn::ArrayStore(store))] = ops else { return None };
            if *i != index as i32 || *store != kind { return None; }
            match value {
                Insn::IConst(n) if kind == ArrayKind::Int => Some(i64::from(*n)),
                Insn::LConst(n) if kind == ArrayKind::Long => Some(*n),
                Insn::Ldc(i) => match class.pool.loadable(*i).ok()? {
                    BootstrapArg::Int(n) if kind == ArrayKind::Int => Some(i64::from(n)),
                    BootstrapArg::Long(n) if kind == ArrayKind::Long => Some(n),
                    _ => None,
                },
                _ => None,
            }
        }).collect::<Option<Vec<_>>>()?;
        Some((element, cells))
    }

    /// Fresh keys on one platform thread. Bind the key constructor, identity-based map, get/set/remove
    /// and default initialValue to the selected implementation. Internal hash and table reads stay opaque.
    pub(crate) fn thread_local_keys(&self) -> bool {
        *self.thread_local_keys.get_or_init(|| self.matches_jdk_classes(
            &["java/lang/ThreadLocal", "java/lang/InheritableThreadLocal", "java/lang/ThreadLocal$ThreadLocalMap",
              "java/lang/ThreadLocal$ThreadLocalMap$Entry", "java/lang/Thread", "java/util/concurrent/atomic/AtomicInteger"],
            &["3c3c4c6a6b22ae5d97b167d5dae2c9a812bd66a6af51b2320c1d51218f490cc8"])) // Temurin 21.0.13
    }

    /// Selected image for class-mirror identity, map folds and immutable-set construction.
    pub(crate) fn class_table_image(&self) -> bool {
        *self.class_table_image.get_or_init(|| self.matches_jdk_classes(
            &["java/util/IdentityHashMap", "java/util/IdentityHashMap$IdentityHashMapIterator", "java/util/IdentityHashMap$EntrySet",
              "java/util/IdentityHashMap$EntryIterator", "java/util/IdentityHashMap$EntryIterator$Entry", "java/util/IdentityHashMap$Values",
              "java/util/IdentityHashMap$ValueIterator", "java/util/HashMap", "java/util/HashMap$Node",
              "java/util/HashSet", "java/util/AbstractCollection", "java/util/Collections",
              "java/util/ImmutableCollections$SetN", "java/lang/Class", "java/lang/Object",
              "java/lang/String"],
            &["6cf0ee476e559857d5d5703d8fea3ca2a46299cfd6c6c2071fdea3001f33f348"])) // Temurin 21.0.13
    }

    /// OpenJDK's byte-array view factory, order singletons, unaligned access and range checks.
    pub(crate) fn byte_array_view_image(&self) -> bool {
        let names = ["java/lang/invoke/MethodHandles", "java/lang/invoke/VarHandles", "java/lang/invoke/VarHandle",
              "java/nio/ByteOrder", "jdk/internal/misc/Unsafe", "jdk/internal/util/Preconditions",
              "java/lang/invoke/VarHandleByteArrayAsShorts", "java/lang/invoke/VarHandleByteArrayAsShorts$ArrayHandle",
              "java/lang/invoke/VarHandleByteArrayAsChars", "java/lang/invoke/VarHandleByteArrayAsChars$ArrayHandle",
              "java/lang/invoke/VarHandleByteArrayAsInts", "java/lang/invoke/VarHandleByteArrayAsInts$ArrayHandle",
              "java/lang/invoke/VarHandleByteArrayAsLongs", "java/lang/invoke/VarHandleByteArrayAsLongs$ArrayHandle",
              "java/lang/invoke/VarHandleByteArrayAsFloats", "java/lang/invoke/VarHandleByteArrayAsFloats$ArrayHandle",
              "java/lang/invoke/VarHandleByteArrayAsDoubles", "java/lang/invoke/VarHandleByteArrayAsDoubles$ArrayHandle",
            ];
        *self.byte_array_view_image.get_or_init(|| names.iter().all(|name| !self.is_application(name))
            && self.matches_jdk_classes(&names, &["c3e8ff6b32aa29978abfaefd40f227bfbe05c5060014744eed6d7fc1f6482ef9"])) // Temurin 21.0.13
    }

    /// OpenJDK's wildcard objects expose clones of their reified upper and lower bounds.
    pub(crate) fn wildcard_type_image(&self) -> bool {
        let names = ["java/lang/Enum", "java/lang/reflect/WildcardType", "sun/reflect/generics/reflectiveObjects/WildcardTypeImpl",
            "sun/reflect/generics/reflectiveObjects/LazyReflectiveObjectGenerator", "sun/reflect/generics/tree/Wildcard",
            "sun/reflect/generics/tree/BottomSignature", "sun/reflect/generics/tree/FieldTypeSignature"];
        *self.wildcard_type_image.get_or_init(|| names.iter().all(|name| !self.is_application(name))
            && self.matches_jdk_classes(&names, &["38a096cf9c1cc8cd19b9e65912b447d7a04e0bad4db2fec770d4045e5b793c2e"])) // Temurin 21.0.13
    }

    /// Method repositories cache their return Type on the reflective copy. Class-scoped
    /// variables come from the declaring class's repository on this image.
    pub(crate) fn method_return_image(&self) -> bool {
        let names = ["java/lang/Class", "java/lang/reflect/Method", "java/lang/reflect/TypeVariable", "java/util/List",
            "sun/reflect/generics/repository/MethodRepository", "sun/reflect/generics/repository/ConstructorRepository",
            "sun/reflect/generics/repository/ClassRepository", "sun/reflect/generics/reflectiveObjects/TypeVariableImpl",
            "sun/reflect/generics/scope/MethodScope", "sun/reflect/generics/scope/ClassScope",
            "sun/reflect/generics/visitor/Reifier", "sun/reflect/generics/factory/CoreReflectionFactory",
            "java/util/SequencedCollection", "java/util/Collection", "java/lang/Iterable"];
        *self.method_return_image.get_or_init(|| names.iter().all(|name| !self.is_application(name))
            && self.matches_jdk_classes(&names, &["c5392bc22b8b3208ef6b7acdc25d12af8722dc48db3c04291ae78196ae5f32bf"]))
    }

    /// ClassRepository clones its interfaces array, retaining the reified Type objects on the mirror.
    pub(crate) fn generic_interface_image(&self) -> bool {
        *self.generic_interface_image.get_or_init(|| self.matches_jdk_classes(
            &["java/lang/Class", "java/lang/reflect/ParameterizedType", "sun/reflect/generics/parser/SignatureParser",
              "sun/reflect/generics/repository/AbstractRepository", "sun/reflect/generics/repository/GenericDeclRepository",
              "sun/reflect/generics/repository/ClassRepository", "sun/reflect/generics/tree/ClassTypeSignature",
              "sun/reflect/generics/visitor/Reifier", "sun/reflect/generics/factory/CoreReflectionFactory",
              "sun/reflect/generics/reflectiveObjects/ParameterizedTypeImpl"],
            &["2a3e1317a03c92f25c934d15f147c3131377073096b550db598de8a053912063"])) // Temurin 21.0.13
    }

    pub(crate) fn jar_resource_image(&self) -> bool {
        *self.jar_resource_image.get_or_init(|| self.matches_jdk_classes(
            &["java/lang/ClassLoader", "java/lang/CompoundEnumeration", "jdk/internal/loader/BuiltinClassLoader",
              "jdk/internal/loader/BuiltinClassLoader$1", "jdk/internal/loader/ClassLoaders$AppClassLoader", "jdk/internal/loader/URLClassPath",
              "jdk/internal/loader/URLClassPath$JarLoader", "jdk/internal/loader/URLClassPath$JarLoader$2", "java/net/URL",
              "java/net/JarURLConnection", "sun/net/www/protocol/jar/Handler", "sun/net/www/protocol/jar/JarURLConnection",
              "sun/net/www/protocol/jar/JarURLConnection$JarURLInputStream", "java/io/InputStream", "java/io/FilterInputStream"],
            &["eece9c2f142cba64068daceb85c70c2e8e426132f588ca4a402c53448e758ef0"])) // Temurin 21.0.13
    }

    pub(crate) fn properties_reader_image(&self) -> bool {
        *self.properties_reader_image.get_or_init(|| self.matches_jdk_classes(
            &["java/util/Properties", "java/util/Properties$LineReader"],
            &["5557162135c0a12b872b1c44af1171fe8e91a104ef7495da7777c47ea6a614fa"]))
    }

    /// The getters of this System image return its installed Properties object and delegate
    /// to that exact receiver. Its non-null setter replaces the reference after permission checks.
    pub(crate) fn system_properties_image(&self) -> bool {
        *self.system_properties_image.get_or_init(|| self.matches_jdk_classes(
            &["java/lang/System", "java/util/Properties"],
            &["9febf1a065577810a10eb907d79a2ab8fde138615693bb5507337db7bd59a395", // Temurin 21.0.13
              "27e7d13f69f2156f51aaa168af3d88d267217c7e0a2932bece82852dfed1b51f"])) // Temurin 25.0.5
    }

    pub(crate) fn linked_map_image(&self) -> bool {
        *self.linked_map_image.get_or_init(|| self.matches_jdk_classes(&["java/util/HashMap", "java/util/LinkedHashMap"],
            &["b26ef44090b682e76fe299447ad1189e4321f62f343f0c4f633568024b7fb754"]))
    }

    pub(crate) fn soft_queue_image(&self) -> bool {
        *self.soft_queue_image.get_or_init(|| self.matches_jdk_classes(
            &["java/lang/ref/Reference", "java/lang/ref/SoftReference", "java/lang/ref/ReferenceQueue"],
            &["ab6102d8fb7c8cfc1945a9186c510bff4e994618c3224b4a5ca0aac9d5bdb1eb"]))
    }

    /// The bounded StringBuffer copy uses this image's growth rule and its actual UTF-16 byte order.
    pub(crate) fn string_buffer_byte_order(&self) -> Option<bool> {
        *self.string_buffer_layout.get_or_init(|| {
            let matches = self.matches_jdk_classes(&["java/lang/AbstractStringBuilder", "java/lang/StringBuffer",
                "java/lang/String", "java/lang/StringUTF16", "java/lang/StringLatin1", "jdk/internal/util/ArraysSupport"],
                &["b4f23eff462728cd8564aff1ac1eab77f4be441c1a418aa9f1e2ee06d183155f"]);
            if matches { self.jdk()?.hot_spot_big_endian() } else { None }
        })
    }

    /// This Temurin 21 image and tzdb resolve UTC to a fixed zero-offset ZoneInfo.
    /// The public factory clones its cached prototype and sets the caller's actual ID on the clone.
    pub(crate) fn explicit_utc(&self) -> bool {
        *self.explicit_utc.get_or_init(|| self.matches_jdk_classes(
            &["java/util/TimeZone", "sun/util/calendar/ZoneInfo", "sun/util/calendar/ZoneInfoFile",
              "sun/util/calendar/ZoneInfoFile$1", "sun/util/calendar/ZoneInfoFile$ZoneOffsetTransitionRule"],
            &["36b2b18547c61bf0bd54a9d78ce40a09538626ada9c2c61b8fa8fd71a239bb60"])
            && self.jdk().and_then(JImage::tzdb_sha256).as_deref() ==
                Some("a02e3a23d67255782b11ab81070902235ab564080f0f65ffe2a989cdaa86fe89"))
    }

    /// Class.getMethod and getDeclaredField return copies on this image. Their scalar metadata
    /// accessors read the declaring class, interned name, descriptor and JVM modifiers of the member.
    pub(crate) fn reflection_copies(&self) -> bool {
        *self.reflection_copies.get_or_init(|| self.matches_jdk_classes(
            &["java/lang/Class", "java/lang/reflect/Method", "java/lang/reflect/Field",
              "java/lang/reflect/Executable", "jdk/internal/reflect/ReflectionFactory"],
            &["38fa5f59e2a40c91e2d2ace8a9068f9d2e9378b887a05a184442e8f7f3379858"])) // Temurin 21.0.13
    }

    /// Both factories load the cached object for -128..=high and allocate a distinct Integer otherwise.
    /// The cache initializer fixes high at startup and fills each slot with its corresponding value.
    pub(crate) fn known_integer_cache(&self) -> bool {
        self.matches_jdk_classes(&["java/lang/Integer", "java/lang/Integer$IntegerCache"], &[
            "72bfbbe1f2885dbd5565cf63195e776a2ca3fc3807a8d8292f50bc8a06a927aa",
            "b9dd4690cd66026e282baa47deb2d5f60e9cffd843b34027cda4898da3d1141b",
        ])
    }

    pub(crate) fn integer_text_image(&self) -> bool {
        self.matches_jdk_classes(&["java/lang/Integer","java/lang/StringLatin1","java/lang/StringUTF16"],
            &["a8e237e5d730b5afba88e8995b5bfc171d3a437731ba31295e36a6f31acc9b83",
              "eeef00c7da113b3b61cd916103a56f733fb327a6a459d8ba02f982f3d6462cf3"])
    }

    pub(crate) fn enum_lookup_image(&self) -> bool {
        self.matches_jdk_classes(&["java/lang/Enum","java/lang/Class","java/util/HashMap"],
            &["0406d74eaffee4294188f377a0a8ed29ae8031b33fcbb6f0ec4b4d89157009a1",
              "d9dab35be2671bc870ef08b57cb2b66b971307fd48a5421331b82a995ce9fa68"])
    }

    /// These images install Buffer$1 through Preconditions$4. The fixed checkIndex formatter
    /// converts two plain Integers with "%s". Buffer$1.apply(String) ignores both the message
    /// and its receiver and constructs a fresh, no-argument IndexOutOfBoundsException.
    /// Bind the complete classes for the skipped formatting path. Other images run as written.
    pub(crate) fn plain_buffer_formatter(&self) -> bool {
        *self.plain_buffer_formatter.get_or_init(|| self.matches_jdk_classes(
            &["java/nio/Buffer", "java/nio/Buffer$1", "jdk/internal/util/Preconditions", "jdk/internal/util/Preconditions$4"],
            &["42e15de022f96d5073fabe25d5528a97bade2de31a6ff39681e0665ba67bfebe", // Temurin 21.0.13
              "50d5a86221a41a6b52d2bb0e43cf79432d32d8c4855c11c5969f8b38751cc2a0"])) // Temurin 25.0.5
    }

    /// The basic decoder singleton and its standard alphabet on the subject JVM.
    pub(crate) fn basic_base64(&self) -> bool {
        *self.basic_base64.get_or_init(|| self.matches_jdk_classes(
            &["java/util/Base64", "java/util/Base64$Decoder", "java/util/Base64$Encoder", "java/lang/String"],
            &["df41fe30f3d956b4ac136e8ffba2efb4acfc22d5ada1c697b008050a6e14a988", // Temurin 8u512
              "01f87d4df37d231720d9366da567b2433b06e5d8f0cd882030e148b57fbee6df", // Temurin 21.0.13
              "31a8fdd027846b8e8cd5f7437707e581c34953dd609eced4d6b3b616ec06b08d"])) // Temurin 25.0.5
    }

    /// On these images ByteBuffer.putBuffer copies bytes between base + address + index,
    /// with reachability fences. Ordinary heap buffers have a byte array base and a null session.
    pub(crate) fn heap_buffer_copy(&self) -> bool {
        *self.heap_buffer_copy.get_or_init(|| self.matches_jdk_classes(
            &["java/nio/Buffer", "java/nio/ByteBuffer", "java/nio/HeapByteBuffer", "java/nio/HeapByteBufferR",
              "jdk/internal/misc/ScopedMemoryAccess", "jdk/internal/misc/Unsafe", "java/lang/ref/Reference"],
            &["d522b4c7f2635ce9ab76083fee6c98a92c47d9943ad6bd3c10b92d1ecc3ea897", // Temurin 21.0.13
              "73b5d438d5329a71d1e3c835d847bdc88e6c8a44d0d424ce18dcc598471a9940"])) // Temurin 25.0.5
    }

    /// Both compact-string paths return the receiver on a miss, the canonical empty
    /// string on complete deletion, and a fresh string for a nonempty change.
    pub(crate) fn string_unit_replacement(&self) -> bool {
        *self.string_unit_replacement.get_or_init(|| self.matches_jdk_classes(
            &["java/lang/String", "java/lang/StringLatin1", "java/lang/StringUTF16"],
            &["256709b88a51b3c338f471ab3824c9f9ead1f8af43a873fc32acb2583a0f810c", // Temurin 21.0.13
              "962641c5f9fcb9933ccdd3c5c45e88d7361a57022ecda0771c54c6be87981fe3"])) // Temurin 25.0.5
    }

    pub(crate) fn heap_buffer_owner(name: &str) -> bool {
        matches!(name, "java/nio/Buffer" | "java/nio/ByteBuffer" | "java/nio/CharBuffer"
            | "java/nio/HeapByteBuffer" | "java/nio/HeapByteBufferR" | "java/nio/HeapCharBuffer")
    }

    pub(crate) fn platform_native(&self, member: &crate::classfile::MemberRef) -> bool {
        if member.owner != "java/lang/System" || !matches!((member.name.as_str(), member.descriptor.as_str()),
            ("currentTimeMillis", "()J") | ("identityHashCode", "(Ljava/lang/Object;)I")) { return false; }
        let Ok(Some(Loaded { class, origin: Origin::Jdk })) = self.load(&member.owner) else { return false };
        class.method(&member.name, &member.descriptor).is_some_and(|m| m.is_public() && m.is_static() && m.is_native())
    }

    /// In these JDKs WeakHashMap.get and put hash the supplied key, and compare with
    /// suppliedKey.equals(storedKey). Queue draining, growth and reference processing
    /// call no user code. The checker separately checks dispatch of both key methods.
    pub(crate) fn weak_map_null_operations(&self) -> bool {
        self.matches_jdk_classes(
            &["java/util/WeakHashMap", "java/util/WeakHashMap$Entry", "java/lang/ref/WeakReference",
              "java/lang/ref/Reference", "java/lang/ref/ReferenceQueue", "java/lang/Object"],
            &["e02eeefdfde93353bae13bfd1312d063c3248c1ff9af97772cdbe50b36c03bcd",
              "f9bdfff0be7df1a7633155c47b51ff4e0c02b9288c6755529512c6b2ffbaff55"])
    }

    /// Bind the public atomic accessors to the same volatile field that the subject JVM observed.
    pub(crate) fn atomic_reference_accessor(&self, name: &str, desc: &str) -> Option<(Rc<ClassFile>, Method)> {
        use crate::classfile::{Insn, Kind};
        const CLASS: &str = "java/util/concurrent/atomic/AtomicReference";
        let Loaded { class, origin: Origin::Jdk } = self.load(CLASS).ok()?? else { return None };
        let method = class.method(name, desc)?.clone();
        let code = method.code.as_ref()?;
        if !method.is_final() || !method.is_public() || method.is_static() || !code.exception_table.is_empty() { return None; }
        let ops = code.instructions().ok()?;
        let index = match (name, desc, ops.as_slice()) {
            ("get", "()Ljava/lang/Object;", [(_, Insn::Load(Kind::Ref, 0)), (_, Insn::GetField(i)), (_, Insn::Return(Some(Kind::Ref)))]) => *i,
            ("set", "(Ljava/lang/Object;)V", [(_, Insn::Load(Kind::Ref, 0)), (_, Insn::Load(Kind::Ref, 1)), (_, Insn::PutField(i)), (_, Insn::Return(None))]) => *i,
            _ => return None,
        };
        let f = class.pool.member(index).ok()?;
        let field = class.field("value")?;
        (f.owner == CLASS && f.name == field.name && f.descriptor == "Ljava/lang/Object;" && f.descriptor == field.descriptor
            && !field.is_static() && field.access & crate::classfile::flags::VOLATILE != 0).then_some((class, method))
    }

    /// Execute the selected image's constructor on a fresh, exact AtomicReference.
    /// Its get and set accessors use the same volatile field as a captured reference.
    pub(crate) fn fresh_atomic_method(&self, name: &str, desc: &str, special: bool) -> Option<(Rc<ClassFile>, Method)> {
        if !special { return self.atomic_reference_accessor(name, desc); }
        if name != "<init>" || !matches!(desc, "()V" | "(Ljava/lang/Object;)V") { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load("java/util/concurrent/atomic/AtomicReference").ok()?? else { return None };
        let method = class.method(name, desc)?.clone();
        (method.is_public() && !method.is_static() && method.code.is_some()).then_some((class, method))
    }

    /// VALUE is the offset of the int field 'value' and incrementAndGet is getAndAddInt(1) + 1.
    pub(crate) fn atomic_integer_increment(&self) -> bool {
        self.matches_jdk_classes(&["java/util/concurrent/atomic/AtomicInteger"],
            &["9195c151584c60db712f4de7684f7d92ec5018e9a94621dd94d9512197172295"])
    }

    /// Methods of an image-backed byte or char buffer with an ordinary Java heap array.
    /// Foreign segments and native memory operations keep their separate call boundaries.
    pub(crate) fn heap_buffer_method(&self, owner: &str, name: &str, desc: &str) -> Option<(Rc<ClassFile>, Method)> {
        if !Self::heap_buffer_owner(owner) || !matches!(name, "<init>" | "position" | "limit" | "capacity" | "remaining"
            | "hasRemaining" | "flip" | "rewind" | "clear" | "compact" | "discardMark" | "checkScope"
            | "duplicate" | "slice" | "asReadOnlyBuffer" | "markValue" | "checkSession" | "session"
            | "array" | "hasArray" | "arrayOffset" | "ix" | "isReadOnly" | "isDirect" | "nextGetIndex" | "nextPutIndex"
            | "get" | "put" | "checkIndex" | "createLimitException" | "createPositionException" | "mark" | "reset") { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
        let method = class.method(name, desc)?.clone();
        if method.is_static() || method.code.is_none() { return None; }
        Some((class, method))
    }

    /// Ordinary instance bytecode on an exact, freshly constructed queue. A path reaching a
    /// VarHandle still needs the JDK's actual atomic operation; the empty path reads neither handle.
    pub(crate) fn linked_queue_method(&self, receiver: &str, owner: &str, name: &str, desc: &str, special: bool) -> Option<(Rc<ClassFile>, Method)> {
        const QUEUE: &str = "java/util/concurrent/ConcurrentLinkedQueue";
        if receiver != QUEUE || special && owner != QUEUE { return None; }
        if !matches!((name, desc), ("<init>", "()V") | ("peek", "()Ljava/lang/Object;") | ("isEmpty", "()Z")
            | ("first", "()Ljava/util/concurrent/ConcurrentLinkedQueue$Node;")
            | ("updateHead", "(Ljava/util/concurrent/ConcurrentLinkedQueue$Node;Ljava/util/concurrent/ConcurrentLinkedQueue$Node;)V")) {
            return None;
        }
        let Loaded { class, origin: Origin::Jdk } = self.load(QUEUE).ok()?? else { return None };
        let method = class.method(name, desc)?.clone();
        (!method.is_static() && method.code.is_some()).then_some((class, method))
    }

    /// Fresh deques, sets, reference queues and string buffers construct their backing storage on the selected JDK.
    /// Fresh linked blocking queues build two distinct locks, conditions, an atomic
    /// count and a sentinel node. Only construction and the empty-state observers
    /// execute here. Waiting, signaling and atomic updates retain their own boundaries.
    pub(crate) fn fresh_state_method(&self, receiver: &str, owner: &str, name: &str, desc: &str, special: bool) -> Option<(Rc<ClassFile>, Method)> {
        // An explicitly modeled receiver has the model's fields throughout its lifetime.
        if self.runs_model(receiver) { return None; }
        const QUEUE: &str = "java/util/concurrent/LinkedBlockingQueue";
        const COUNT: &str = "java/util/concurrent/atomic/AtomicInteger";
        const LOCK: &str = "java/util/concurrent/locks/ReentrantLock";
        const SYNC: &str = "java/util/concurrent/locks/ReentrantLock$NonfairSync";
        const CONDITION: &str = "java/util/concurrent/locks/AbstractQueuedSynchronizer$ConditionObject";
        let supported = match receiver {
            "java/util/ImmutableCollections$Set12" => matches!((owner, name, desc),
                ("java/util/ImmutableCollections$Set12", "<init>", "(Ljava/lang/Object;)V" | "(Ljava/lang/Object;Ljava/lang/Object;)V")
                | ("java/util/ImmutableCollections$Set12" | "java/util/Set" | "java/util/Collection", "contains", "(Ljava/lang/Object;)Z")
                | ("java/util/ImmutableCollections$Set12" | "java/util/Set" | "java/util/Collection", "size", "()I")
                | ("java/util/ImmutableCollections$Set12" | "java/util/Set" | "java/util/Collection" | "java/lang/Iterable", "iterator", "()Ljava/util/Iterator;")
                | ("java/util/ImmutableCollections$AbstractImmutableSet" | "java/util/ImmutableCollections$AbstractImmutableCollection"
                   | "java/util/AbstractCollection", "<init>", "()V")),
            "java/util/ImmutableCollections$Set12$1" => matches!((owner, name, desc),
                ("java/util/ImmutableCollections$Set12$1", "<init>", "(Ljava/util/ImmutableCollections$Set12;)V")
                | ("java/util/ImmutableCollections$Set12$1" | "java/util/Iterator", "hasNext", "()Z")
                | ("java/util/ImmutableCollections$Set12$1" | "java/util/Iterator", "next", "()Ljava/lang/Object;")),
            "java/util/HashSet" => matches!((owner, name, desc),
                ("java/util/HashSet" | "java/util/AbstractSet" | "java/util/AbstractCollection", "<init>", "()V")
                | ("java/util/HashSet" | "java/util/Set" | "java/util/Collection", "isEmpty", "()Z")),
            "java/util/ArrayDeque" => matches!((owner, name, desc),
                ("java/util/ArrayDeque" | "java/util/AbstractCollection", "<init>", "()V")
                | ("java/util/ArrayDeque", "<init>", "(I)V")
                | ("java/util/ArrayDeque" | "java/util/Deque" | "java/util/Collection", "isEmpty", "()Z")
                | ("java/util/ArrayDeque" | "java/util/Deque" | "java/util/Collection", "size", "()I")
                | ("java/util/ArrayDeque" | "java/util/Deque", "addFirst" | "addLast", "(Ljava/lang/Object;)V")
                | ("java/util/ArrayDeque" | "java/util/Collection" | "java/util/Deque", "add", "(Ljava/lang/Object;)Z")
                | ("java/util/ArrayDeque", "delete", "(I)Z")
                | ("java/util/ArrayDeque" | "java/util/Deque", "pollLast" | "peekFirst" | "peekLast", "()Ljava/lang/Object;")
                | ("java/util/ArrayDeque" | "java/util/Deque" | "java/util/Collection" | "java/lang/Iterable", "iterator", "()Ljava/util/Iterator;")),
            "java/util/ArrayDeque$DeqIterator" => matches!((owner, name, desc),
                ("java/util/ArrayDeque$DeqIterator", "<init>", "(Ljava/util/ArrayDeque;)V")
                | ("java/util/ArrayDeque$DeqIterator" | "java/util/Iterator", "hasNext", "()Z")
                | ("java/util/ArrayDeque$DeqIterator" | "java/util/Iterator", "next", "()Ljava/lang/Object;")
                | ("java/util/ArrayDeque$DeqIterator" | "java/util/Iterator", "remove", "()V")
                | ("java/util/ArrayDeque$DeqIterator", "postDelete", "(Z)V")),
            "java/util/LinkedList" => matches!((owner, name, desc),
                ("java/util/LinkedList" | "java/util/AbstractSequentialList" | "java/util/AbstractList" | "java/util/AbstractCollection", "<init>", "()V")
                | ("java/util/LinkedList" | "java/util/Deque", "addFirst", "(Ljava/lang/Object;)V")
                | ("java/util/LinkedList", "linkFirst" | "linkLast", "(Ljava/lang/Object;)V")
                | ("java/util/LinkedList" | "java/util/List" | "java/util/Collection", "add", "(Ljava/lang/Object;)Z")
                | ("java/util/LinkedList" | "java/util/List" | "java/util/Collection", "addAll", "(Ljava/util/Collection;)Z")
                | ("java/util/LinkedList" | "java/util/List" | "java/util/AbstractCollection" | "java/util/Collection", "isEmpty", "()Z")
                | ("java/util/LinkedList" | "java/util/List" | "java/util/AbstractCollection" | "java/util/Collection", "size", "()I")
                | ("java/util/LinkedList" | "java/util/List", "remove", "(I)Ljava/lang/Object;")
                | ("java/util/LinkedList", "addAll", "(ILjava/util/Collection;)Z")
                | ("java/util/LinkedList", "checkElementIndex" | "checkPositionIndex", "(I)V")
                | ("java/util/LinkedList", "isElementIndex" | "isPositionIndex", "(I)Z")
                | ("java/util/LinkedList", "outOfBoundsMsg", "(I)Ljava/lang/String;")
                | ("java/util/LinkedList", "node", "(I)Ljava/util/LinkedList$Node;")
                | ("java/util/LinkedList", "unlink", "(Ljava/util/LinkedList$Node;)Ljava/lang/Object;")),
            "java/util/LinkedList$Node" => owner == receiver && name == "<init>"
                && desc == "(Ljava/util/LinkedList$Node;Ljava/lang/Object;Ljava/util/LinkedList$Node;)V",
            "java/util/concurrent/CopyOnWriteArrayList" => matches!((owner,name,desc),
                ("java/util/concurrent/CopyOnWriteArrayList","<init>","()V")
                | ("java/util/concurrent/CopyOnWriteArrayList","getArray","()[Ljava/lang/Object;")
                | ("java/util/concurrent/CopyOnWriteArrayList","setArray","([Ljava/lang/Object;)V")
                | ("java/util/concurrent/CopyOnWriteArrayList" | "java/util/List" | "java/util/Collection","size","()I")
                | ("java/util/concurrent/CopyOnWriteArrayList" | "java/util/List" | "java/util/Collection","isEmpty","()Z")
                | ("java/util/concurrent/CopyOnWriteArrayList" | "java/util/List" | "java/lang/Iterable" | "java/util/Collection","iterator","()Ljava/util/Iterator;")
                | ("java/util/concurrent/CopyOnWriteArrayList" | "java/util/List" | "java/util/Collection","add","(Ljava/lang/Object;)Z")),
            "java/util/concurrent/CopyOnWriteArrayList$COWIterator" => matches!((owner,name,desc),
                ("java/util/concurrent/CopyOnWriteArrayList$COWIterator","<init>","([Ljava/lang/Object;I)V")
                | ("java/util/concurrent/CopyOnWriteArrayList$COWIterator" | "java/util/Iterator","hasNext","()Z")
                | ("java/util/concurrent/CopyOnWriteArrayList$COWIterator" | "java/util/Iterator","next","()Ljava/lang/Object;")),
            QUEUE => matches!((owner, name, desc),
                (QUEUE, "<init>", "()V" | "(I)V") | (QUEUE, "size" | "remainingCapacity", "()I") | ("java/util/AbstractCollection", "size", "()I")
                | ("java/util/AbstractCollection" | QUEUE, "isEmpty", "()Z")),
            "java/util/concurrent/LinkedBlockingQueue$Node" => owner == receiver && name == "<init>" && desc == "(Ljava/lang/Object;)V",
            COUNT => matches!((owner, name, desc), (COUNT, "<init>", "()V" | "(I)V")
                | ("java/lang/Number", "<init>", "()V") | (COUNT, "get", "()I") | (COUNT, "set", "(I)V")),
            LOCK => owner == LOCK && matches!((name, desc), ("<init>", "()V") | ("newCondition", "()Ljava/util/concurrent/locks/Condition;")),
            // invokespecial selects the named superclass constructor even on a user-defined segment.
            _ if special && owner == LOCK && self.is_subtype(receiver, LOCK) => name == "<init>" && desc == "()V",
            _ if special && matches!(owner, "java/lang/ref/Reference" | "java/lang/ref/SoftReference")
                && self.is_subtype(receiver, "java/lang/ref/SoftReference") =>
                name == "<init>" && desc == "(Ljava/lang/Object;Ljava/lang/ref/ReferenceQueue;)V",
            "java/lang/ref/ReferenceQueue" => owner == receiver && name == "<init>" && desc == "()V",
            "java/util/Properties$LineReader" => owner == receiver && matches!((name, desc),
                ("<init>", "(Ljava/io/InputStream;)V") | ("readLine", "()I")),
            "java/lang/StringBuffer" => owner == "java/lang/AbstractStringBuilder" && name == "<init>" && desc == "(I)V",
            SYNC => matches!((owner,name,desc), (SYNC | "java/util/concurrent/locks/ReentrantLock$Sync"
                | "java/util/concurrent/locks/AbstractQueuedSynchronizer" | "java/util/concurrent/locks/AbstractOwnableSynchronizer", "<init>","()V")
                | ("java/util/concurrent/locks/ReentrantLock$Sync","newCondition","()Ljava/util/concurrent/locks/AbstractQueuedSynchronizer$ConditionObject;")),
            CONDITION => owner == CONDITION && name == "<init>" && desc == "(Ljava/util/concurrent/locks/AbstractQueuedSynchronizer;)V",
            _ => false,
        };
        if !supported || special != (name == "<init>") { return None; }
        let (class, method) = if special {
            let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
            let method = class.method(name, desc)?.clone();
            (class, method)
        } else {
            let (class,method) = self.find_method(receiver,name,desc)?;
            if !matches!(self.load(&class.name).ok()??.origin,Origin::Jdk) { return None; }
            (class,method)
        };
        (!method.is_static() && method.code.is_some()).then_some((class,method))
    }

    /// The count and cached key view of a freshly constructed, single-threaded concurrent map.
    /// These paths use ordinary instance fields. A call reaching an atomic update needs its own semantics.
    pub(crate) fn concurrent_map_method(&self, name: &str, desc: &str) -> Option<(Rc<ClassFile>, Method)> {
        if self.runs_model(crate::models::CONCURRENT_MAP) || !matches!((name, desc),
            ("<init>", "()V" | "(I)V" | "(IFI)V") | ("isEmpty", "()Z") | ("size", "()I") | ("sumCount", "()J")
            | ("get" | "remove", "(Ljava/lang/Object;)Ljava/lang/Object;") | ("containsKey", "(Ljava/lang/Object;)Z")
            | ("put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")
            | ("putVal", "(Ljava/lang/Object;Ljava/lang/Object;Z)Ljava/lang/Object;")
            | ("replaceNode", "(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")
            | ("initTable", "()[Ljava/util/concurrent/ConcurrentHashMap$Node;")
            | ("forEach", "(Ljava/util/function/BiConsumer;)V")
            | ("putAll", "(Ljava/util/Map;)V") | ("tryPresize", "(I)V") | ("entrySet", "()Ljava/util/Set;")
            | ("keySet", "()Ljava/util/Set;" | "()Ljava/util/concurrent/ConcurrentHashMap$KeySetView;")) { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(crate::models::CONCURRENT_MAP).ok()?? else { return None };
        let method = class.method(name, desc)?.clone();
        (!method.is_static() && method.code.is_some()).then_some((class, method))
    }

    /// Run the selected JDK's methods on an exact, freshly constructed Properties object.
    pub(crate) fn properties_method(&self, receiver: &str, owner: &str, name: &str, desc: &str, special: bool) -> Option<(Rc<ClassFile>, Method)> {
        const PROPS: &str = "java/util/Properties";
        if receiver != PROPS || !self.is_subtype(receiver, owner) { return None; }
        let declaring = if special { owner } else { PROPS };
        if !matches!((declaring, name, desc),
            (PROPS, "<init>", "()V" | "(I)V" | "(Ljava/util/Properties;)V" | "(Ljava/util/Properties;I)V")
            | (PROPS, "load", "(Ljava/io/InputStream;)V")
            | (PROPS, "load0", "(Ljava/util/Properties$LineReader;)V")
            | (PROPS, "loadConvert", "([CIILjava/lang/StringBuilder;)Ljava/lang/String;")
            | ("java/util/Hashtable", "<init>", "(Ljava/lang/Void;)V") | ("java/util/Dictionary", "<init>", "()V")
            | (PROPS, "size", "()I") | (PROPS, "isEmpty", "()Z") | (PROPS, "containsKey", "(Ljava/lang/Object;)Z")
            | (PROPS, "get" | "remove", "(Ljava/lang/Object;)Ljava/lang/Object;")
            | (PROPS, "setProperty", "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/Object;")
            | (PROPS, "put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")
            | (PROPS, "forEach", "(Ljava/util/function/BiConsumer;)V")
            | (PROPS, "putAll", "(Ljava/util/Map;)V") | (PROPS, "entrySet", "()Ljava/util/Set;")
            | (PROPS, "getProperty", "(Ljava/lang/String;)Ljava/lang/String;" | "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;")) {
            return None;
        }
        let Loaded { class, origin: Origin::Jdk } = self.load(declaring).ok()?? else { return None };
        let method = class.method(name, desc)?.clone();
        (!method.is_static() && method.code.is_some()).then_some((class, method))
    }

    /// In these images Properties initializes its private singleton from the bootstrap Unsafe.
    /// Its constructor reads it solely to issue a store fence. The adjacent pair has no
    /// operand, result or heap change in the checker's single thread.
    pub(crate) fn properties_store_fence(&self, class: &Rc<ClassFile>, field: &crate::classfile::MemberRef, next: Option<&crate::classfile::Insn>) -> bool {
        if class.name != "java/util/Properties" || (field.owner.as_str(), field.name.as_str(), field.descriptor.as_str())
            != ("java/util/Properties", "UNSAFE", "Ljdk/internal/misc/Unsafe;") { return false; }
        let Some(crate::classfile::Insn::InvokeVirtual(i)) = next else { return false };
        if !class.pool.member(*i).is_ok_and(|m| (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == ("jdk/internal/misc/Unsafe", "storeFence", "()V"))
            || !self.load(&class.name).ok().flatten().is_some_and(|l| l.origin == Origin::Jdk && Rc::ptr_eq(&l.class, class)) { return false; }
        self.matches_jdk_classes(&["java/util/Properties", "jdk/internal/misc/Unsafe"],
            &["034ae59c97dba913ad400bc75dbe8c4fbd8e85ecea8bb825c1cc07be56723ae0",
              "a9688ab678f030bee22af212985e0382b273f74667a0035aa62b456fce6467e1"])
    }

    /// These images initialize SIZECTL from their own sizeCtl field and calculate ABASE
    /// and ASHIFT from Node[]. Only the typed operations below use these layout facts.
    pub(crate) fn known_concurrent_table(&self) -> bool {
        *self.concurrent_table_layout.get_or_init(|| self.matches_jdk_classes(&[crate::models::CONCURRENT_MAP, "jdk/internal/misc/Unsafe"],
            &["fa36342584f8299066a80758c30abd00754753468be0fb36e921303dca9031d8",
              "01af927c892eb74ad558ef33d7b2d79b7bf0f67bce07b8a12c9fd3926204a361"]))
    }

    pub(crate) fn concurrent_table_read(&self, owner: &str, name: &str, desc: &str) -> bool {
        owner == crate::models::CONCURRENT_MAP && name == "tabAt"
            && desc == "([Ljava/util/concurrent/ConcurrentHashMap$Node;I)Ljava/util/concurrent/ConcurrentHashMap$Node;"
            && !self.runs_model(owner) && self.known_concurrent_table()
    }

    /// The presizing loop compares and sets this.sizeCtl to -1. Check the entire six-
    /// instruction expression before returning the local holding its expected value.
    pub(crate) fn concurrent_size_cas(&self, class: &Rc<ClassFile>, method: &str, code: &[crate::classfile::Insn]) -> Option<usize> {
        use crate::classfile::{Insn, Kind};
        if class.name != crate::models::CONCURRENT_MAP || !matches!(method, "tryPresize" | "initTable") { return None; }
        let [Insn::GetStatic(u), Insn::Load(Kind::Ref, 0), Insn::GetStatic(offset), Insn::Load(Kind::Int, expected),
            Insn::IConst(-1), Insn::InvokeVirtual(cas), ..] = code else { return None };
        let is = |i, owner: &str, name: &str, desc: &str| class.pool.member(i).is_ok_and(|m|
            (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == (owner, name, desc));
        (is(*u, &class.name, "U", "Ljdk/internal/misc/Unsafe;") && is(*offset, &class.name, "SIZECTL", "J")
            && is(*cas, "jdk/internal/misc/Unsafe", "compareAndSetInt", "(Ljava/lang/Object;JII)Z")
            && self.load(&class.name).ok().flatten().is_some_and(|l| l.origin == Origin::Jdk && Rc::ptr_eq(&l.class, class))
            && self.known_concurrent_table()).then_some(usize::from(*expected))
    }

    /// Some JDKs reject a negative offset before dereferencing a null prefix. Qualify that
    /// observable exception ordering against the actual branch and its false-return target.
    pub(crate) fn prefix_checks_negative_first(&self) -> bool {
        use crate::classfile::{Cond, Insn, Kind};
        let Ok(Some(Loaded {class, origin: Origin::Jdk})) = self.load("java/lang/String") else { return false };
        let Some(code) = class.method("startsWith", "(Ljava/lang/String;I)Z").and_then(|m| m.code.as_ref()) else { return false };
        let Ok(insns) = code.instructions() else { return false };
        let [(_, Insn::Load(Kind::Int, 2)), (_, Insn::If(Cond::Lt, target)), ..] = &insns[..] else { return false };
        insns.windows(2).any(|pair| matches!(pair,
            [(at, Insn::IConst(0)), (_, Insn::Return(Some(Kind::Int)))] if at == target))
    }

    /// Selected collection and text bytecode. Callers qualify the actual receivers and helper arguments.
    pub(crate) fn library_image_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        let sublist = matches!(owner, "java/util/ArrayList$SubList" | "java/util/ArrayList$SubList$1");
        if !sublist && !self.collection_static(owner, name, descriptor) && !matches!((owner, name, descriptor),
            ("java/lang/String", "concat", "(Ljava/lang/String;)Ljava/lang/String;")
            | ("java/lang/String", "contains", "(Ljava/lang/CharSequence;)Z")
            | ("java/lang/Object", "equals", "(Ljava/lang/Object;)Z")
            | ("java/lang/String", "valueOf", "(Ljava/lang/Object;)Ljava/lang/String;")
            | ("java/lang/StringBuilder", "append", "(Ljava/lang/Object;)Ljava/lang/StringBuilder;")
            | ("java/lang/Class", "cast", "(Ljava/lang/Object;)Ljava/lang/Object;")
            | ("java/lang/Class", "cannotCastMsg", "(Ljava/lang/Object;)Ljava/lang/String;")
            | ("java/util/ArrayList", "<init>", "()V" | "(I)V" | "(Ljava/util/Collection;)V")
            | ("java/util/ArrayList", "size", "()I") | ("java/util/ArrayList", "isEmpty", "()Z")
            | ("java/util/ArrayList", "spliterator", "()Ljava/util/Spliterator;")
            | ("java/util/ArrayList", "get" | "elementData", "(I)Ljava/lang/Object;")
            | ("java/util/ArrayList", "clear", "()V")
            | ("java/util/ArrayList", "iterator", "()Ljava/util/Iterator;")
            | ("java/util/ArrayList", "listIterator", "(I)Ljava/util/ListIterator;")
            | ("java/util/ArrayList", "rangeCheckForAdd", "(I)V")
            | ("java/util/ArrayList$ListItr", "<init>", "(Ljava/util/ArrayList;I)V")
            | ("java/util/ArrayList$ListItr", "hasPrevious", "()Z")
            | ("java/util/ArrayList$ListItr", "previous", "()Ljava/lang/Object;")
            | ("java/util/ArrayList", "forEach", "(Ljava/util/function/Consumer;)V")
            | ("java/util/ArrayList", "subList", "(II)Ljava/util/List;")
            | ("java/util/AbstractList", "subListRangeCheck", "(III)V")
            | ("java/util/AbstractList", "clear", "()V")
            | ("java/util/AbstractList", "add", "(Ljava/lang/Object;)Z")
            | ("java/util/ArrayList", "removeRange", "(II)V")
            | ("java/util/ArrayList", "shiftTailOverGap", "([Ljava/lang/Object;II)V")
            | ("java/util/ArrayList", "remove", "(I)Ljava/lang/Object;" | "(Ljava/lang/Object;)Z")
            | ("java/util/ArrayList", "fastRemove", "([Ljava/lang/Object;I)V")
            | ("java/util/ArrayList", "elementAt", "([Ljava/lang/Object;I)Ljava/lang/Object;")
            | ("java/util/ArrayList$Itr", "<init>", "(Ljava/util/ArrayList;)V")
            | ("java/util/ArrayList$Itr", "next", "()Ljava/lang/Object;")
            | ("java/util/ArrayList$Itr", "hasNext", "()Z")
            | ("java/util/ArrayList$Itr", "remove" | "checkForComodification", "()V")
            | ("java/util/ArrayList$Itr", "forEachRemaining", "(Ljava/util/function/Consumer;)V")
            | ("java/util/ArrayList", "set", "(ILjava/lang/Object;)Ljava/lang/Object;")
            | ("java/util/ArrayList", "contains", "(Ljava/lang/Object;)Z") | ("java/util/ArrayList", "indexOf", "(Ljava/lang/Object;)I")
            | ("java/util/ArrayList", "indexOfRange", "(Ljava/lang/Object;II)I")
            | ("java/util/ArrayList", "add", "(Ljava/lang/Object;)Z" | "(Ljava/lang/Object;[Ljava/lang/Object;I)V")
            | ("java/util/ArrayList", "addAll", "(Ljava/util/Collection;)Z")
            | ("java/util/ArrayList", "grow", "()[Ljava/lang/Object;" | "(I)[Ljava/lang/Object;")
            | ("java/util/ArrayList", "toArray", "()[Ljava/lang/Object;" | "([Ljava/lang/Object;)[Ljava/lang/Object;")
            | ("java/util/Arrays", "copyOf", "([Ljava/lang/Object;ILjava/lang/Class;)[Ljava/lang/Object;")) { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
        if (sublist || owner == "java/util/ArrayList$Itr") && class.method("<clinit>", "()V").is_some() { return None; }
        let method = class.method(name, descriptor)?.clone();
        method.code.as_ref()?;
        Some((class, method))
    }

    /// The builder stores UTF-16 content in the checker. This forwarding overload
    /// can run on that representation only when it touches no private JDK fields.
    pub(crate) fn builder_append_object(&self) -> Option<(Rc<ClassFile>, Method)> {
        use crate::classfile::{Insn::*, Kind::Ref};
        let owner = "java/lang/StringBuilder";
        let (cf, m) = self.library_image_method(owner, "append", "(Ljava/lang/Object;)Ljava/lang/StringBuilder;")?;
        let code = m.code.as_ref()?;
        let ops = code.instructions().ok()?;
        let [(_, Load(Ref, 0)), (_, Load(Ref, 1)), (_, InvokeStatic(value)), (_, InvokeVirtual(append)), (_, Return(Some(Ref)))] = ops.as_slice() else { return None };
        let value = cf.pool.member(*value).ok()?;
        let append = cf.pool.member(*append).ok()?;
        (code.exception_table.is_empty() && (value.owner.as_str(), value.name.as_str(), value.descriptor.as_str())
            == ("java/lang/String", "valueOf", "(Ljava/lang/Object;)Ljava/lang/String;")
            && (append.owner.as_str(), append.name.as_str(), append.descriptor.as_str()) == (owner, "append", "(Ljava/lang/String;)Ljava/lang/StringBuilder;"))
            .then_some((cf, m))
    }

    pub(crate) fn surrogate_arithmetic(owner: &str, name: &str, descriptor: &str) -> bool {
        owner == "java/lang/Character" && matches!((name, descriptor),
            ("isSurrogate" | "isHighSurrogate" | "isLowSurrogate", "(C)Z") | ("isSupplementaryCodePoint", "(I)Z")
            | ("charCount", "(I)I")
            | ("toCodePoint", "(CC)I")
            | ("highSurrogate" | "lowSurrogate", "(I)C"))
    }

    pub(crate) fn big_number(owner: &str) -> bool {
        matches!(owner, "java/math/BigDecimal" | "java/math/BigInteger")
    }

    /// The JDK 21 formatters construct their result from a byte range. Other image
    /// layouts keep the interpreter's existing rendering path.
    pub(crate) fn floating_formatter(&self, owner: &str) -> bool {
        let implementation = match owner {
            "java/lang/Float" => "jdk/internal/math/FloatToDecimal",
            "java/lang/Double" => "jdk/internal/math/DoubleToDecimal",
            _ => return false,
        };
        self.state_image_class(implementation).is_some_and(|c| c.method("charsToString", "()Ljava/lang/String;").is_some())
    }

    /// Numeric code executed from the selected JDK image. Factories follow their actual
    /// allocation and cache branches. The hypot implementation includes the FdLibm helpers
    /// the selected image calls. An additional helper can produce a named refusal.
    pub(crate) fn numeric_image_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        if !Self::surrogate_arithmetic(owner, name, descriptor) && !matches!((owner, name, descriptor),
            ("java/lang/Math" | "java/lang/StrictMath", "hypot", "(DD)D")
            | ("java/lang/String", "valueOf", "(J)Ljava/lang/String;")
            | ("java/lang/Byte" | "java/lang/Short" | "java/lang/Integer" | "java/lang/Long" | "java/lang/Float" | "java/lang/Double",
               "doubleValue", "()D")
            | ("java/lang/Byte" | "java/lang/Short" | "java/lang/Integer" | "java/lang/Long" | "java/lang/Float" | "java/lang/Double",
               "floatValue", "()F")
            | ("java/lang/FdLibm$Hypot", "compute", "(DD)D")
            | ("java/lang/FdLibm", "__HI" | "__LO", "(D)I" | "(DI)D")
            | ("java/lang/Math", "powerOfTwoD" | "primPowerOfTwoD", "(I)D")
            | ("java/lang/Integer", "bitCount" | "lowestOneBit", "(I)I")
            | ("java/lang/Integer", "equals", "(Ljava/lang/Object;)Z")
            | ("java/lang/Integer", "hashCode", "()I" | "(I)I")
            | ("java/lang/Integer", "toString", "()Ljava/lang/String;")
            | ("java/lang/Short", "reverseBytes", "(S)S")
            | ("java/lang/Integer", "reverseBytes", "(I)I")
            | ("java/lang/Long", "reverseBytes", "(J)J")
            | ("java/lang/Integer", "compareUnsigned" | "compare", "(II)I")
            | ("java/lang/Character", "codePointAt" | "codePointBefore", "(Ljava/lang/CharSequence;I)I")
            | ("java/math/BigInteger", "valueOf", "(J)Ljava/math/BigInteger;")
            | ("java/math/BigInteger", "<init>", "(J)V" | "([B)V" | "([BII)V")
            | ("java/math/BigInteger", "<init>", "([CII)V")
            | ("java/math/BigInteger", "parseInt", "([CII)I")
            | ("java/math/BigInteger", "destructiveMulAdd", "([III)V")
            | ("java/math/BigInteger", "trustedStripLeadingZeroInts", "([I)[I")
            | ("java/math/BigInteger", "equals", "(Ljava/lang/Object;)Z")
            | ("java/math/BigInteger", "toMagArray", "(J)[I")
            | ("java/math/BigInteger", "makePositive" | "stripLeadingZeroBytes", "(I[BII)[I" | "([BII)[I")
            | ("java/math/BigInteger", "bitLengthForInt" | "getInt", "(I)I")
            | ("java/math/BigInteger", "bitLength" | "magBitLength" | "intValue" | "intValueExact" | "signInt" | "firstNonzeroIntNum" | "numberOfTrailingZeroInts", "()I")
            | ("java/math/BigDecimal", "<init>", "(Ljava/math/BigInteger;I)V")
            | ("java/math/BigDecimal", "<init>", "(Ljava/lang/String;)V" | "([CII)V" | "([CIILjava/math/MathContext;)V")
            | ("java/math/BigDecimal", "valueOf", "(D)Ljava/math/BigDecimal;")
            | ("java/math/BigDecimal", "compareTo" | "compareMagnitude", "(Ljava/math/BigDecimal;)I")
            | ("java/math/BigDecimal", "precision" | "signum", "()I")
            | ("java/math/BigDecimal", "longMultiplyPowerTen", "(JI)J")
            | ("java/math/BigDecimal", "longCompareMagnitude", "(JJ)I")
            | ("java/math/BigDecimal", "compactValFor", "(Ljava/math/BigInteger;)J")
            | ("java/math/BigDecimal", "toStrictBigInteger", "(Ljava/math/BigInteger;)Ljava/math/BigInteger;")
            | ("java/math/BigDecimal", "scale", "()I")
            | ("java/math/BigDecimal", "unscaledValue" | "inflated", "()Ljava/math/BigInteger;")
            | ("java/lang/Byte", "valueOf", "(B)Ljava/lang/Byte;")
            | ("java/lang/Short", "valueOf", "(S)Ljava/lang/Short;")
            | ("java/lang/Character", "valueOf", "(C)Ljava/lang/Character;")
            | ("java/lang/Character", "<init>", "(C)V")
            | ("java/lang/Character", "charValue", "()C")
            | ("java/lang/Character", "toString", "()Ljava/lang/String;" | "(C)Ljava/lang/String;")
            | ("java/lang/Character", "hashCode", "()I" | "(C)I")
            | ("java/lang/Boolean", "hashCode", "()I" | "(Z)I")
            | ("java/lang/Long", "hashCode", "()I" | "(J)I")
            | ("java/lang/Character", "equals", "(Ljava/lang/Object;)Z")
            | ("java/lang/Long", "valueOf", "(J)Ljava/lang/Long;")
            | ("java/lang/Float", "valueOf", "(F)Ljava/lang/Float;")
            | ("java/lang/Double", "valueOf", "(D)Ljava/lang/Double;")
            | ("java/lang/Float", "valueOf", "(Ljava/lang/String;)Ljava/lang/Float;")
            | ("java/lang/Double", "valueOf", "(Ljava/lang/String;)Ljava/lang/Double;")
            | ("java/lang/Float" | "java/lang/Double", "isInfinite", "()Z")
            | ("java/lang/Float" | "java/lang/Double", "toString", "()Ljava/lang/String;")
            | ("java/lang/Float", "toString", "(F)Ljava/lang/String;")
            | ("java/lang/Double", "toString", "(D)Ljava/lang/String;")
            | ("java/lang/Math", "multiplyHigh", "(JJ)J")
            | ("java/lang/Integer", "decode", "(Ljava/lang/String;)Ljava/lang/Integer;")
            | ("java/lang/Integer", "parseInt", "(Ljava/lang/CharSequence;III)I")
            | ("java/lang/Long" | "java/lang/Integer", "intValue", "()I")
            | ("java/lang/Long" | "java/lang/Integer", "longValue", "()J")
            | ("java/lang/Byte", "<init>", "(B)V") | ("java/lang/Short", "<init>", "(S)V")
            | ("java/lang/Long", "<init>", "(J)V") | ("java/lang/Float", "<init>", "(F)V")
            | ("java/lang/Double", "<init>", "(D)V") | ("java/lang/Number", "<init>", "()V"))
        {
            return None;
        }
        let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
        let method = class.method(name, descriptor)?.clone();
        method.code.as_ref()?;
        // multiplyHigh specifies the exact high word of the signed 128-bit product.
        if name != "multiplyHigh" && matches!(owner, "java/lang/Math" | "java/lang/StrictMath" | "java/lang/FdLibm" | "java/lang/FdLibm$Hypot")
            && method.annotations(&class.pool).ok()?.iter().any(|a| matches!(a.type_name.rsplit('/').next(), Some("IntrinsicCandidate" | "HotSpotIntrinsicCandidate"))) {
            return None;
        }
        Some((class, method))
    }

    /// The compiler-generated assertion switch read by these image methods. Both possible values
    /// can be checked without relying on the JVM launcher having enabled or disabled assertions.
    pub(crate) fn numeric_assertion_flag(&self, owner: &str, name: &str, descriptor: &str) -> bool {
        if name != "$assertionsDisabled" || descriptor != "Z" || !(Self::heap_buffer_owner(owner) || matches!(owner, "java/lang/Math" | "java/lang/FdLibm$Hypot")) {
            return false;
        }
        let Ok(Some(Loaded { class, origin: Origin::Jdk })) = self.load(owner) else { return false };
        class.field(name).is_some_and(|f| f.descriptor == "Z" && f.is_static() && f.is_final() && f.access & crate::classfile::flags::SYNTHETIC != 0)
    }

    /// Whether the tool's own checker runs the instance methods of the class as bytecode: an application class's,
    /// and those of the models it runs although they are only for JBMC's class path ([`crate::models::CHECKER_RUNS`],
    /// `java.lang.Enum`). The other models it runs for static calls alone.
    pub fn checker_runs(&self, name: &str) -> bool {
        self.is_application(name) || self.checked_image_class(name).is_some() || (self.runs_model(name) && self.checker_model(name).is_some())
    }

    /// This class uses ordinary instance and static fields. The selected image supplies its
    /// initializer, empty singleton, branches, and actual Supplier dispatch.
    pub(crate) fn checked_image_class(&self, name: &str) -> Option<Rc<ClassFile>> {
        if name != "java/util/Optional" { return self.state_image_class(name); }
        let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
        Some(class)
    }

    /// Concrete receivers can inherit these default methods. Resolve the actual target
    /// first so an application override still supplies all its effects.
    pub(crate) fn image_default_method(&self, class: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        if (name, descriptor) == ("computeIfAbsent", "(Ljava/lang/Object;Ljava/util/function/Function;)Ljava/lang/Object;") {
            let receiver = self.application(class).ok()??;
            let [direct] = receiver.interfaces.as_slice() else { return None };
            if !matches!(direct.as_str(), "java/util/Map" | "java/util/concurrent/ConcurrentMap")
                || !matches!(receiver.super_class.as_deref(), Some("java/lang/Object" | "java/util/AbstractMap"))
                || !self.find_method(class, name, descriptor)?.0.is_interface() { return None; }
            // With these superclasses, the one direct map interface supplies the most specific default.
            // ConcurrentMap must run its putIfAbsent path even if a search encounters Map first.
            let Loaded { class: interface, origin: Origin::Jdk } = self.load(direct).ok()?? else { return None };
            let method = interface.method(name, descriptor)?.clone();
            return (method.is_public() && !method.is_static() && method.code.is_some()).then_some((interface, method));
        }
        let interface = match (name, descriptor) {
            ("putIfAbsent", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;") if class == "java/util/EnumMap" => "java/util/Map",
            ("end", "()V") if class.starts_with("java/util/stream/ReduceOps$") => "java/util/stream/Sink",
            ("stream", "()Ljava/util/stream/Stream;") if matches!(class, "java/util/Arrays$ArrayList" | "java/util/Collections$EmptySet")
                || class == "java/util/ArrayList" && !self.runs_model(class) => "java/util/Collection",
            ("begin", "(J)V") | ("end", "()V") if class.starts_with("java/util/stream/FindOps$FindSink") => "java/util/stream/Sink",
            ("getExactSizeIfKnown", "()J") if matches!(class, "java/util/Spliterators$ArraySpliterator" | "java/util/Spliterators$EmptySpliterator$OfRef") => "java/util/Spliterator",
            ("forEachRemaining", "(Ljava/util/function/Consumer;)V") if self.is_application(class) => "java/util/Iterator",
            ("forEach", "(Ljava/util/function/Consumer;)V") if self.is_application(class) => "java/lang/Iterable",
            ("getExactSizeIfKnown", "()J") | ("hasCharacteristics", "(I)Z") if class == "java/util/Spliterators$IteratorSpliterator" => "java/util/Spliterator",
            _ => return None,
        };
        let (cf, m) = self.find_method(class, name, descriptor)?;
        (cf.name == interface && cf.is_interface() && m.code.is_some()).then_some((cf, m))
    }

    /// The JVM's enum universe for these two JDK helpers comes directly from JavaLangAccess.
    pub(crate) fn enum_universe_lookup(&self, owner: &str, name: &str, descriptor: &str) -> bool {
        use crate::classfile::{Insn, Kind};
        if descriptor != "(Ljava/lang/Class;)[Ljava/lang/Enum;" || !matches!((owner, name), ("java/util/EnumMap", "getKeyUniverse") | ("java/util/EnumSet", "getUniverse")) { return false; }
        let Ok(Some(Loaded { class, origin: Origin::Jdk })) = self.load(owner) else { return false };
        let Some(code) = class.method(name, descriptor).and_then(|m| m.code.as_ref()) else { return false };
        let Ok(ops) = code.instructions() else { return false };
        let [(_, Insn::InvokeStatic(a)), (_, Insn::Load(Kind::Ref, 0)), (_, Insn::InvokeInterface(b)), (_, Insn::Return(Some(Kind::Ref)))] = ops.as_slice() else { return false };
        code.exception_table.is_empty() && class.pool.member(*a).is_ok_and(|m| (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == ("jdk/internal/access/SharedSecrets", "getJavaLangAccess", "()Ljdk/internal/access/JavaLangAccess;"))
            && class.pool.member(*b).is_ok_and(|m| (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == ("jdk/internal/access/JavaLangAccess", "getEnumConstantsShared", descriptor))
    }

    /// Accept the javac values() body only when it clones this enum's own synthetic final
    /// array. A hand-authored method with different behavior remains observable.
    pub(crate) fn enum_values_field(&self, name: &str) -> Option<String> {
        use crate::classfile::{flags, Insn, Kind};
        let cf = self.checker_class(name)?;
        if !cf.is_enum() || cf.super_class.as_deref() != Some("java/lang/Enum") { return None; }
        let array = format!("[L{name};");
        let m = cf.method("values", &format!("(){array}"))?;
        let code = m.code.as_ref()?;
        let ops = code.instructions().ok()?;
        let [(_, Insn::GetStatic(f)), (_, Insn::InvokeVirtual(copy)), (_, Insn::CheckCast(c)), (_, Insn::Return(Some(Kind::Ref)))] = ops.as_slice() else { return None };
        let f = cf.pool.member(*f).ok()?;
        let copy = cf.pool.member(*copy).ok()?;
        let field = cf.field(&f.name)?;
        (m.is_public() && m.is_static() && code.exception_table.is_empty() && f.owner == name && f.descriptor == array
            && field.descriptor == array && field.is_static() && field.is_final() && field.access & flags::SYNTHETIC != 0
            && copy.owner == array && copy.name == "clone" && copy.descriptor == "()Ljava/lang/Object;" && cf.pool.class_name(*c).ok()? == array).then_some(f.name)
    }

    /// Ordinary single-threaded JDK objects whose instance and static fields both engines
    /// execute from the image. Reader$2 is the CharSequence reader used by newer runtimes.
    pub(crate) fn state_image_class(&self, name: &str) -> Option<Rc<ClassFile>> {
        if matches!(name, "java/nio/channels/Channels$WritableByteChannelImpl" | "java/nio/channels/spi/AbstractInterruptibleChannel"
            | "java/nio/channels/spi/AbstractInterruptibleChannel$1") {
            let base = "java/nio/channels/spi/AbstractInterruptibleChannel";
            let Loaded { class: parent, origin: Origin::Jdk } = self.load(base).ok()?? else { return None };
            if parent.method("<clinit>", "()V").is_some() { return None; }
            let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
            return class.method("<clinit>", "()V").is_none().then_some(class);
        }
        if matches!(name, "java/util/StringTokenizer" | "java/io/PrintWriter$1" | "java/util/Collections$UnmodifiableMap" | "java/util/AbstractQueue" | "java/util/concurrent/ConcurrentLinkedQueue$Node"
            | "java/util/Collections$SetFromMap" | "java/util/concurrent/ConcurrentHashMap$Node" | "java/util/concurrent/ConcurrentHashMap$KeySetView"
            | "java/util/concurrent/ConcurrentHashMap$CollectionView" | "java/util/concurrent/ConcurrentHashMap$EntrySetView"
            | "java/util/concurrent/ConcurrentHashMap$EntryIterator" | "java/util/concurrent/ConcurrentHashMap$BaseIterator"
            | "java/util/concurrent/ConcurrentHashMap$Traverser" | "java/util/Properties$EntrySet"
            | "java/util/Collections$SynchronizedMap" | "java/util/Collections$SynchronizedSet" | "java/util/Collections$SynchronizedCollection") {
            let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
            return class.method("<clinit>", "()V").is_none().then_some(class);
        }
        if name == "java/util/EventObject" {
            if self.runs_model(name) { return None; }
            let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
            return Some(class);
        }
        if !matches!(name, "java/math/MathContext" | "java/math/RoundingMode"
            | "jdk/internal/math/FloatToDecimal" | "jdk/internal/math/DoubleToDecimal" | "jdk/internal/math/MathUtils"
            | "java/io/Reader" | "java/io/StringReader" | "java/io/Reader$2" | "java/io/BufferedReader" | "java/io/ObjectStreamField"
            | "java/io/Writer" | "java/io/StringWriter" | "java/io/PrintWriter" | "java/lang/StringBuffer"
            | "java/lang/CharacterData" | "java/lang/CharacterDataLatin1"
            | "java/io/InputStream" | "java/io/ByteArrayInputStream" | "java/io/FilterInputStream" | "java/io/DataInputStream"
            | "java/io/OutputStream" | "java/io/ByteArrayOutputStream" | "java/io/FilterOutputStream"
            | "java/io/InputStreamReader" | "sun/nio/cs/StreamDecoder" | "jdk/internal/misc/InternalLock" | "java/nio/charset/CodingErrorAction" | "java/nio/ByteOrder"
            | "java/nio/charset/CharsetDecoder" | "java/nio/charset/CoderResult" | "sun/nio/cs/UTF_8$Decoder"
            | "java/util/Comparator" | "java/util/Comparators$NaturalOrderComparator"
            | "java/util/TimSort" | "java/util/ComparableTimSort" | "java/util/BitSet"
            | "java/util/Stack" | "java/util/Vector" | "java/util/Collections$SingletonList" | "java/util/Collections$SingletonSet" | "java/util/Collections$1"
            | "java/util/Collections$UnmodifiableList" | "java/util/Collections$UnmodifiableRandomAccessList"
            | "java/util/Collections$UnmodifiableCollection$1"
            | "java/util/Collections$ReverseComparator" | "java/util/Collections$ReverseComparator2"
            | "java/util/Collections$EmptyList" | "java/util/Collections$EmptyIterator" | "java/util/Arrays$ArrayList" | "java/util/Arrays$ArrayItr"
            | "java/util/Spliterators" | "java/util/Spliterators$IteratorSpliterator"
            | "java/util/Spliterators$ArraySpliterator" | "java/util/ArrayList$ArrayListSpliterator"
            | "java/util/stream/DistinctOps" | "java/util/stream/DistinctOps$1" | "java/util/stream/ReferencePipeline$StatefulOp"
            | "java/util/stream/ReferencePipeline$2" | "java/util/stream/ReferencePipeline$2$1"
            | "java/util/stream/ReferencePipeline$3" | "java/util/stream/ReferencePipeline$3$1"
            | "java/util/stream/ReferencePipeline$StatelessOp" | "java/util/stream/Sink$ChainedReference"
            | "java/util/stream/FindOps" | "java/util/stream/FindOps$FindOp" | "java/util/stream/FindOps$FindSink" | "java/util/stream/FindOps$FindSink$OfRef"
            | "java/util/Spliterators$EmptySpliterator" | "java/util/Spliterators$EmptySpliterator$OfRef" | "java/util/Spliterators$EmptySpliterator$OfInt"
            | "java/util/Spliterators$EmptySpliterator$OfLong" | "java/util/Spliterators$EmptySpliterator$OfDouble"
            | "java/util/Collections$EmptyMap" | "java/util/Collections$EmptySet" | "java/util/Collections$UnmodifiableSet" | "java/util/Collections$UnmodifiableCollection"
            | "java/util/stream/Collectors" | "java/util/stream/Collectors$CollectorImpl" | "java/util/stream/Collector$Characteristics"
            | "java/util/stream/ReduceOps" | "java/util/stream/StreamShape"
            | "java/util/EnumMap" | "java/util/EnumMap$1" | "java/util/EnumSet" | "java/util/RegularEnumSet"
            | "java/util/stream/StreamSupport" | "java/util/stream/StreamOpFlag" | "java/util/stream/StreamOpFlag$Type" | "java/util/stream/StreamOpFlag$MaskBuilder"
            | "java/util/stream/PipelineHelper" | "java/util/stream/AbstractPipeline" | "java/util/stream/ReferencePipeline" | "java/util/stream/ReferencePipeline$Head"
            | "java/nio/file/StandardOpenOption" | "java/nio/file/LinkOption"
            | "javax/swing/event/EventListenerList" | "java/beans/PropertyChangeSupport" | "java/beans/VetoableChangeSupport"
            | "java/beans/ChangeListenerMap" | "java/beans/PropertyChangeSupport$PropertyChangeListenerMap" | "java/beans/VetoableChangeSupport$VetoableChangeListenerMap") && !name.starts_with("java/util/stream/ReduceOps$") { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
        Some(class)
    }

    /// HashMap and the ordinary JDK classes that implement its live entry and key views.
    /// A future runtime that adds a static initializer needs its state qualified first.
    pub(crate) fn map_image_class(&self, name: &str) -> Option<Rc<ClassFile>> {
        if !matches!(name, "java/util/HashMap" | "java/util/HashMap$Node" | "java/util/HashMap$EntrySet" | "java/util/HashMap$KeySet"
            | "java/util/HashMap$HashIterator" | "java/util/HashMap$EntryIterator" | "java/util/HashMap$KeyIterator"
            | "java/util/AbstractMap" | "java/util/AbstractSet" | "java/util/AbstractCollection") { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
        class.method("<clinit>", "()V").is_none().then_some(class)
    }

    /// HashSet's copy constructor and methods share the image map layout. Its only
    /// static initialization must create one fresh sentinel, used by every set.
    /// An explicitly selected model keeps its own field layout and dispatch.
    fn native_map_image_class(&self, name: &str) -> Option<Rc<ClassFile>> {
        // These classes are used only on objects marked by the native engine. Standalone
        // LinkedHashMap model objects and explicitly selected set models keep their layouts.
        if matches!(name, "java/util/LinkedHashSet" | "java/util/LinkedHashMap" | "java/util/LinkedHashMap$Entry"
            | "java/util/LinkedHashMap$LinkedKeySet" | "java/util/LinkedHashMap$LinkedHashIterator"
            | "java/util/LinkedHashMap$LinkedKeyIterator" | "java/util/LinkedHashMap$LinkedValues"
            | "java/util/LinkedHashMap$LinkedValueIterator" | "java/util/LinkedHashMap$LinkedEntrySet"
            | "java/util/LinkedHashMap$LinkedEntryIterator") {
            if name == "java/util/LinkedHashSet" && (self.runs_model(name) || self.runs_model("java/util/HashSet")
                || self.observed_initializers.borrow().contains(name) || self.native_map_image_class("java/util/HashSet").is_none()) {
                return None;
            }
            let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
            return class.method("<clinit>", "()V").is_none().then_some(class);
        }
        if name != "java/util/HashSet" { return self.map_image_class(name); }
        if self.runs_model(name) || self.observed_initializers.borrow().contains(name) { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(name).ok()?? else { return None };
        let code = class.method("<clinit>", "()V")?.code.as_ref()?;
        let ops = code.instructions().ok()?;
        use crate::classfile::Insn::*;
        let [(_, New(object)), (_, Dup), (_, InvokeSpecial(init)), (_, PutStatic(write)), (_, Return(None))] = ops.as_slice() else { return None };
        let ctor = class.pool.member(*init).ok()?;
        let field = class.pool.member(*write).ok()?;
        let declared = class.field("PRESENT")?;
        (code.exception_table.is_empty() && class.pool.class_name(*object).ok()? == "java/lang/Object"
            && (ctor.owner.as_str(), ctor.name.as_str(), ctor.descriptor.as_str()) == ("java/lang/Object", "<init>", "()V")
            && (field.owner.as_str(), field.name.as_str(), field.descriptor.as_str()) == (name, "PRESENT", "Ljava/lang/Object;")
            && declared.is_static() && declared.is_final() && declared.descriptor == field.descriptor).then_some(class)
    }

    pub(crate) fn map_image_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        let (cf, m) = self.method_in(owner, name, descriptor, &|c| self.native_map_image_class(c))?;
        (m.code.is_some() && (name != "<init>" || cf.name == owner)).then_some((cf, m))
    }

    pub(crate) fn is_map_image(&self, cf: &Rc<ClassFile>) -> bool {
        self.native_map_image_class(&cf.name).is_some_and(|image| Rc::ptr_eq(cf, &image))
    }

    /// The class whose static fields and initializer the tool's own checker holds and runs (JVMS §5.5): an
    /// application class, or a model it runs as bytecode ([`crate::models::CHECKER_RUNS`]: `ImmutableCollections`,
    /// whose initializer makes the one empty list and the sentinel of a list of one). Any other JDK class is taken to
    /// be initialized already, and only its constants are read.
    pub fn checker_class(&self, name: &str) -> Option<Rc<ClassFile>> {
        if let Some(class) = self.checked_image_class(name) { return Some(class); }
        if self.runs_model(name) {
            return self.checker_model(name);
        }
        // A class of a JDK package is the JDK's, initialized already, whichever entry holds it (`javax.servlet`'s are
        // a library's): unless the check has the observed state of its initializer, which is then the class's.
        if is_jdk_name(name) && !self.observed_initializers.borrow().contains(name) {
            return None;
        }
        self.application(name).ok().flatten()
    }

    /// Whether [`checker_class`](Self::checker_class) has the class.
    pub fn checker_statics(&self, name: &str) -> bool {
        self.checker_class(name).is_some()
    }

    fn method_in(&self, owner: &str, name: &str, descriptor: &str, bytecode: &dyn Fn(&str) -> Option<Rc<ClassFile>>) -> Option<(Rc<ClassFile>, Method)> {
        let mut current = Some(owner.to_string());
        let mut hops = 0;
        while let Some(c) = current {
            let Some(class) = bytecode(&c) else { break };
            if let Some(m) = class.method(name, descriptor) {
                return Some((class.clone(), m.clone()));
            }
            current = class.super_class.clone();
            hops += 1;
            if hops > 64 {
                break;
            }
        }
        self.interface_method_in(owner, name, descriptor, bytecode)
    }

    /// JVMS 5.4.3.3 and 5.4.6: a subinterface's declaration shadows its ancestors,
    /// including when it redeclares a default abstract. Among the maximally specific
    /// declarations only a unique concrete default supplies executable code.
    fn interface_method_in(&self, owner: &str, name: &str, descriptor: &str,
        bytecode: &dyn Fn(&str) -> Option<Rc<ClassFile>>) -> Option<(Rc<ClassFile>, Method)> {
        let declared: Vec<_> = self.all_interfaces(owner).into_iter().filter_map(|iface| {
            let class = bytecode(&iface).or_else(|| self.load(&iface).ok().flatten().map(|loaded| loaded.class))?;
            let method = class.method(name, descriptor)?;
            (!method.is_static() && !method.is_private()).then(|| (iface, method.is_abstract()))
        }).collect();
        let maximal: Vec<_> = declared.iter().filter(|(iface, _)|
            !declared.iter().any(|(other, _)| other != iface && self.is_subtype(other, iface))).collect();
        let mut defaults = maximal.iter().copied().filter(|(_, abstract_)| !abstract_);
        let selected = defaults.next().or_else(|| maximal.first().copied())?;
        if defaults.next().is_some() { return None; }
        let class = bytecode(&selected.0)?;
        let method = class.method(name, descriptor)?.clone();
        Some((class, method))
    }

    /// The class that declares the field a reference `owner.name:descriptor` resolves to, by the JVM's field
    /// lookup (JVMS §5.4.3.2): `owner` if it declares a field of that name and descriptor, else the first of its
    /// direct superinterfaces, each searched the same way, that leads to one, else its superclass, searched the
    /// same way. `None` when no class on the way declares it, or one on the way cannot be read.
    pub fn resolve_field(&self, owner: &str, name: &str, descriptor: &str) -> Option<String> {
        let mut budget = 256;
        self.lookup_field(owner, name, descriptor, &mut budget)
    }

    fn lookup_field(&self, class: &str, name: &str, descriptor: &str, budget: &mut u32) -> Option<String> {
        *budget = budget.checked_sub(1)?;
        let Ok(Some(loaded)) = self.load(class) else { return None };
        let cf = loaded.class;
        if cf.fields.iter().any(|f| f.name == name && f.descriptor == descriptor) {
            return Some(class.to_string());
        }
        for iface in &cf.interfaces {
            if let Some(found) = self.lookup_field(iface, name, descriptor, budget) {
                return Some(found);
            }
        }
        cf.super_class.as_deref().and_then(|s| self.lookup_field(s, name, descriptor, budget))
    }

    /// Whether two classes along `class`'s superclass chain declare an instance field of one name, so that one
    /// hides the other in an object of `class`.
    pub fn hides_fields(&self, class: &str) -> bool {
        let mut names = std::collections::HashSet::new();
        let mut current = Some(class.to_string());
        let mut hops = 0;
        while let Some(c) = current {
            let Ok(Some(loaded)) = self.load(&c) else { break };
            for f in loaded.class.fields.iter().filter(|f| !f.is_static()) {
                if !names.insert(f.name.clone()) {
                    return true;
                }
            }
            current = loaded.class.super_class.clone();
            hops += 1;
            if hops > 64 {
                break;
            }
        }
        false
    }

    /// The key under which an object of class `object_class` keeps its instance field `name` declared by
    /// `declaring`: the name alone for the field of that name nearest the object's class, the one a subclass
    /// sees, and `declaring.name` (internal name) for one it hides, so that a field declared again by a subclass
    /// is a second field and the usual one keeps its plain name. Both the interpreter and the tool's own checker
    /// key fields this way.
    pub fn field_key(&self, object_class: &str, declaring: &str, name: &str) -> String {
        let mut current = Some(object_class.to_string());
        let mut hops = 0;
        while let Some(c) = current {
            if c == declaring {
                return name.to_string();
            }
            let Ok(Some(loaded)) = self.load(&c) else { break };
            if loaded.class.fields.iter().any(|f| f.name == name && !f.is_static()) || hops > 64 {
                break;
            }
            current = loaded.class.super_class.clone();
            hops += 1;
        }
        format!("{declaring}.{name}")
    }

    /// Loads an application class, or `None` if it is a JDK class or missing.
    pub fn application(&self, name: &str) -> Result<Option<Rc<ClassFile>>, Error> {
        Ok(match self.load(name)? {
            Some(Loaded { class, origin: Origin::Application }) => Some(class),
            _ => None,
        })
    }

    /// Whether the class is one of the application's (on the entries, not in the JDK).
    pub fn is_application(&self, name: &str) -> bool {
        matches!(self.load(name), Ok(Some(Loaded { origin: Origin::Application, .. })))
    }

    /// Whether the class exists, in the application or the JDK (the JDK by image, or by the built-in facts).
    pub fn exists(&self, name: &str) -> bool {
        if name.starts_with('[') {
            return true;
        }
        matches!(self.load(name), Ok(Some(_))) || crate::jdk_facts::superclass(name).is_some() || name == "java/lang/Object"
    }

    /// Whether the class can be loaded (JVMS §5.3.5): it exists, and so does each class and interface above it. A
    /// JDK class is taken to have what is above it. An application class that names a superclass or an interface
    /// neither the entries nor the JDK have cannot: the JVM throws `NoClassDefFoundError` where it is loaded.
    pub fn loads(&self, name: &str) -> bool {
        let mut seen = std::collections::BTreeSet::new();
        let mut todo = vec![name.to_string()];
        while let Some(class) = todo.pop() {
            if !seen.insert(class.clone()) {
                continue;
            }
            match self.load(&class) {
                Ok(Some(Loaded { class: cf, origin: Origin::Application })) => todo.extend(cf.super_class.iter().chain(&cf.interfaces).cloned()),
                Ok(Some(_)) => {}
                _ if self.exists(&class) => {}
                _ => return false,
            }
        }
        true
    }

    /// The direct superclass, from the class file or the built-in JDK facts.
    pub fn superclass(&self, name: &str) -> Option<String> {
        if let Ok(Some(loaded)) = self.load(name) {
            return loaded.class.super_class.clone();
        }
        crate::jdk_facts::superclass(name).map(str::to_string)
    }

    /// The direct superinterfaces.
    pub fn interfaces(&self, name: &str) -> Vec<String> {
        if let Ok(Some(loaded)) = self.load(name) {
            return loaded.class.interfaces.clone();
        }
        crate::jdk_facts::interfaces(name).iter().map(|s| s.to_string()).collect()
    }

    /// The superclass chain, nearest first, not including `name` itself.
    pub fn superclasses(&self, name: &str) -> Vec<String> {
        let mut out = Vec::new();
        let mut current = self.superclass(name);
        while let Some(c) = current {
            if out.contains(&c) || out.len() > 64 {
                break;
            }
            current = self.superclass(&c);
            out.push(c);
        }
        out
    }

    /// Every instance field, including inherited fields, belongs to a class the
    /// checker executes. A native base such as Throwable may carry additional state.
    pub(crate) fn application_object(&self, name: &str) -> bool {
        if !self.is_application(name) { return false; }
        let chain = self.superclasses(name);
        chain.split_last().is_some_and(|(base, rest)| base == "java/lang/Object" && rest.iter().all(|c| self.is_application(c)))
    }

    /// Whether `sub` is `sup`, extends it, or implements it (transitively). Arrays are subtypes of `Object`,
    /// `Cloneable` and `Serializable`, and of arrays of their element's supertypes.
    pub fn is_subtype(&self, sub: &str, sup: &str) -> bool {
        if sub == sup || sup == "java/lang/Object" {
            return true;
        }
        if let Some(sub_elem) = sub.strip_prefix('[') {
            if sup == "java/lang/Cloneable" || sup == "java/io/Serializable" {
                return true;
            }
            if let Some(sup_elem) = sup.strip_prefix('[') {
                // A component can itself be an array, hence an Object, Cloneable and
                // Serializable. Primitive components are covariant only with themselves.
                fn reference_component(desc: &str) -> Option<&str> {
                    if desc.starts_with('[') { Some(desc) } else { desc.strip_prefix('L')?.strip_suffix(';') }
                }
                return match (reference_component(sub_elem), reference_component(sup_elem)) {
                    (Some(a), Some(b)) => self.is_subtype(a, b),
                    _ => sub_elem == sup_elem,
                };
            }
            return false;
        }
        let mut seen = std::collections::HashSet::new();
        let mut work = vec![sub.to_string()];
        while let Some(current) = work.pop() {
            if current == sup {
                return true;
            }
            if !seen.insert(current.clone()) {
                continue;
            }
            if let Some(s) = self.superclass(&current) {
                work.push(s);
            }
            work.extend(self.interfaces(&current));
        }
        false
    }

    /// Whether a class is final in the sense that matters for dispatch: `final`, a record, or an enum without
    /// constant bodies (an enum with bodies is sealed over them).
    pub fn is_effectively_final(&self, name: &str) -> bool {
        match self.load(name) {
            Ok(Some(loaded)) => loaded.class.is_final() || loaded.class.is_record() || (loaded.class.is_enum() && !loaded.class.is_sealed()),
            _ => crate::jdk_facts::is_final(name),
        }
    }

    /// The method a class declares with this name and descriptor, searching superclasses; returns the declaring
    /// class too. Abstract and interface methods count as declarations.
    pub fn find_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        let mut current = Some(owner.to_string());
        let mut hops = 0;
        while let Some(c) = current {
            let Ok(Some(loaded)) = self.load(&c) else { break };
            if let Some(m) = loaded.class.method(name, descriptor) {
                return Some((loaded.class.clone(), m.clone()));
            }
            current = loaded.class.super_class.clone();
            hops += 1;
            if hops > 64 {
                break;
            }
        }
        self.interface_method_in(owner, name, descriptor, &|c| self.load(c).ok().flatten().map(|loaded| loaded.class))
    }

    /// Every interface a class implements, transitively, through superclasses and superinterfaces.
    pub fn all_interfaces(&self, name: &str) -> Vec<String> {
        let mut out = Vec::new();
        let mut seen = std::collections::HashSet::new();
        let mut work = vec![name.to_string()];
        while let Some(current) = work.pop() {
            if !seen.insert(current.clone()) {
                continue;
            }
            for i in self.interfaces(&current) {
                if !out.contains(&i) {
                    out.push(i.clone());
                }
                work.push(i);
            }
            if let Some(s) = self.superclass(&current) {
                work.push(s);
            }
        }
        out
    }

    /// Whether a field (searched up the superclass chain) is `final`.
    pub fn is_final_field(&self, owner: &str, field: &str) -> Option<bool> {
        let mut current = Some(owner.to_string());
        while let Some(c) = current {
            let Ok(Some(loaded)) = self.load(&c) else { return None };
            if let Some(f) = loaded.class.field(field) {
                return Some(f.is_final());
            }
            current = loaded.class.super_class.clone();
        }
        None
    }

    /// Whether the JDK declares a method of this name on `owner` or one of its superclasses, and on which class.
    /// Uses the image when present, else the built-in facts.
    pub fn jdk_declaring_class(&self, owner: &str, method: &str) -> Option<String> {
        let mut current = Some(owner.to_string());
        let mut hops = 0;
        while let Some(c) = current {
            if let Ok(Some(loaded)) = self.load(&c) {
                if loaded.class.methods.iter().any(|m| m.name == method) {
                    return Some(c);
                }
                if method == "<init>" {
                    return Some(c);
                }
                current = loaded.class.super_class.clone();
            } else {
                if crate::jdk_facts::declares(&c, method) || method == "<init>" {
                    return Some(c);
                }
                current = crate::jdk_facts::superclass(&c).map(str::to_string);
            }
            hops += 1;
            if hops > 64 {
                break;
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn jdk_hierarchy_from_builtin_facts() {
        let cp = ClassPath::new();
        assert!(cp.is_subtype("java/lang/IllegalArgumentException", "java/lang/RuntimeException"));
        assert!(cp.is_subtype("java/lang/NumberFormatException", "java/lang/Exception"));
        assert!(!cp.is_subtype("java/lang/Error", "java/lang/Exception"));
        assert!(cp.is_subtype("java/lang/Integer", "java/lang/Comparable"));
        assert!(cp.is_subtype("[I", "java/lang/Object"));
        assert!(cp.is_subtype("[Ljava/lang/Integer;", "[Ljava/lang/Number;"));
        assert_eq!(cp.jdk_declaring_class("java/lang/Enum", "ordinal").as_deref(), Some("java/lang/Enum"));
        assert_eq!(cp.jdk_declaring_class("java/lang/Enum", "hashCode").as_deref(), Some("java/lang/Enum"));
    }
}

#[cfg(test)]
mod model_tests {
    use super::*;

    #[test]
    fn models_are_executed_but_shadow_neither_the_application_nor_the_jdk() {
        let cp = ClassPath::new();
        assert!(cp.model("java/nio/charset/Charset").is_some());
        assert!(cp.bytecode("java/nio/charset/StandardCharsets").unwrap().is_some());
        assert!(!cp.is_application("java/nio/charset/Charset"), "a model is not the code under analysis");
        assert!(cp.is_subtype("java/nio/charset/StandardCharsets$Standard", "java/nio/charset/Charset"), "shape from the model where nothing else has the class");
        let (class, method) = cp.bytecode_method("java/nio/charset/StandardCharsets$Standard", "name", "()Ljava/lang/String;").unwrap();
        assert_eq!(class.name, "java/nio/charset/Charset");
        assert_eq!(method.descriptor, "()Ljava/lang/String;");
        assert!(cp.bytecode_method("java/nio/charset/Charset", "hashCode", "()I").is_some());
        assert!(cp.bytecode_method("java/nio/charset/Charset", "getClass", "()Ljava/lang/Class;").is_none(), "inherited from Object: the natives' business");
        // The models only for JBMC's class path are neither executed nor a shape here.
        for name in ["java/lang/Enum", "java/util/List", "java/util/ImmutableCollections$ListN"] {
            assert!(crate::models::find(name).is_some_and(|m| m.jbmc_only), "{name}");
            assert!(cp.model(name).is_none() && !cp.has_bytecode(name), "{name}");
        }
        let off = ClassPath::new().with_models(false);
        assert!(off.model("java/nio/charset/Charset").is_none());
        assert!(!off.has_bytecode("java/lang/Character"));
        let with_jdk = ClassPath::new().with_default_jdk();
        if with_jdk.has_jdk() {
            let loaded = with_jdk.load("java/lang/Character").unwrap().unwrap();
            assert_eq!(loaded.origin, Origin::Jdk, "the shape of a modelled class comes from the JDK image");
            assert!(with_jdk.model("java/lang/Character").is_some());
        }
    }
}

#[cfg(test)]
mod jdk_tests {
    use super::*;

    #[test]
    fn jdk_classes_exist_through_the_image() {
        let cp = ClassPath::new().with_default_jdk();
        if !cp.has_jdk() {
            eprintln!("no JDK image; skipping");
            return;
        }
        for name in ["java/util/List", "java/lang/System", "java/util/Objects", "java/lang/Math"] {
            assert!(cp.exists(name), "{name} should exist");
            assert!(!cp.is_application(name));
        }
        assert!(cp.is_subtype("java/util/ArrayList", "java/util/List"));
        assert_eq!(cp.jdk_declaring_class("java/lang/Enum", "ordinal").as_deref(), Some("java/lang/Enum"));
    }
}
