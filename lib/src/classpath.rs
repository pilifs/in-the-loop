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
    /// multi-release JAR ([`versioned_classes`]).
    Jar(crate::zip::ZipArchive, PathBuf, BTreeMap<String, Vec<u32>>),
}

/// The classes a multi-release JAR holds a class file of for a release of Java of their own
/// (`META-INF/versions/N/x/Y.class`), each with those releases: none unless the manifest's main section says
/// `Multi-Release: true`, without which a JVM reads only the base class files.
fn versioned_classes(zip: &crate::zip::ZipArchive) -> Result<BTreeMap<String, Vec<u32>>, Error> {
    let mut out: BTreeMap<String, Vec<u32>> = BTreeMap::new();
    let Some(manifest) = zip.read("META-INF/MANIFEST.MF")? else { return Ok(out) };
    let text = String::from_utf8_lossy(&manifest);
    let main = text.split("\n").map(|l| l.trim_end_matches('\r')).take_while(|l| !l.is_empty());
    if !main.filter_map(|l| l.split_once(':')).any(|(k, v)| k.trim().eq_ignore_ascii_case("Multi-Release") && v.trim().eq_ignore_ascii_case("true")) {
        return Ok(out);
    }
    for name in zip.names() {
        let Some((release, class)) = name.strip_prefix("META-INF/versions/").and_then(|r| r.split_once('/')) else { continue };
        let (Ok(release), Some(class)) = (release.parse::<u32>(), class.strip_suffix(".class")) else { continue };
        out.entry(class.to_string()).or_default().push(release);
    }
    Ok(out)
}

impl Entry {
    fn read(&self, class_name: &str) -> Result<Option<Vec<u8>>, Error> {
        match self {
            Entry::Dir(dir) => {
                let file = dir.join(format!("{class_name}.class"));
                match std::fs::read(&file) {
                    Ok(bytes) => Ok(Some(bytes)),
                    Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
                    Err(e) => Err(Error::new(format!("cannot read {}: {e}", file.display()))),
                }
            }
            Entry::Jar(zip, _, _) => zip.read(&format!("{class_name}.class")),
        }
    }

    fn class_names(&self) -> Result<Vec<String>, Error> {
        match self {
            Entry::Dir(dir) => {
                let mut names = Vec::new();
                walk(dir, dir, &mut names)?;
                names.sort();
                Ok(names)
            }
            Entry::Jar(zip, _, _) => Ok(zip
                .names()
                .filter(|n| n.ends_with(".class") && !n.starts_with("META-INF/"))
                .map(|n| n.trim_end_matches(".class").to_string())
                .collect()),
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
    jdk: Option<JImage>,
    /// Whether the tool's models of JDK classes are part of this class path (they are, unless turned off).
    models: bool,
    cache: RefCell<HashMap<String, Option<Loaded>>>,
    /// Every application class, once read ([`ClassPath::application_classes_shared`]).
    classes: RefCell<Option<Rc<BTreeMap<String, Rc<ClassFile>>>>>,
    /// Whether the own checker runs each class initializer asked about ([`crate::bmc::gaps::runs_initializer`]): a
    /// function of the class path alone.
    pub(crate) initializer_runs: RefCell<HashMap<String, bool>>,
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
        ClassPath { entries: Vec::new(), jdk: None, models: true, cache: RefCell::new(HashMap::new()), classes: RefCell::new(None), initializer_runs: Default::default(), observed_initializers: Default::default(), requested_models: Default::default(), loading: Default::default(), refusals: Default::default(), jdk_packages: Default::default() }
    }

    /// With or without the tool's models of JDK classes ([`crate::models`]); on by default. Without them, a call
    /// into a modelled class is left to the interpreter's natives, as it was before the models existed.
    pub fn with_models(mut self, models: bool) -> ClassPath {
        self.models = models;
        self.cache.borrow_mut().clear();
        self.classes.replace(None);
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
            let versioned = versioned_classes(&zip)?;
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
        self.jdk = JImage::open_default();
        self.refusals.borrow_mut().clear();
        self.jdk_packages = Default::default();
        self.initializer_runs.borrow_mut().clear();
        self
    }

    pub fn with_jdk(mut self, jdk: JImage) -> ClassPath {
        self.jdk = Some(jdk);
        self.refusals.borrow_mut().clear();
        self.jdk_packages = Default::default();
        self.initializer_runs.borrow_mut().clear();
        self
    }

    pub fn jdk(&self) -> Option<&JImage> {
        self.jdk.as_ref()
    }

    pub fn has_jdk(&self) -> bool {
        self.jdk.is_some()
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
            let bytes = match entry {
                Entry::Dir(dir) => {
                    let file = dir.join(name);
                    if !file.is_file() {
                        continue;
                    }
                    std::fs::read(&file).map_err(|e| Error::new(format!("cannot read {}: {e}", file.display())))?
                }
                Entry::Jar(zip, _, _) => match zip.read(name)? {
                    Some(bytes) => bytes,
                    None => continue,
                },
            };
            out.push((entry.display(), bytes));
        }
        Ok(out)
    }

    /// Every application class name, in entry order and sorted within an entry.
    pub fn application_class_names(&self) -> Result<Vec<String>, Error> {
        let mut names = Vec::new();
        for entry in &self.entries {
            names.extend(entry.class_names()?);
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
            if let Some(bytes) = entry.read(name)? {
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
    ///   tool reads only the base;
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
        let refused = self.versioned(name).or_else(|| self.shadows_the_jdk(name));
        self.refusals.borrow_mut().insert(name.to_string(), refused.clone());
        refused
    }

    /// [`ClassPath::refused`]'s first case.
    fn versioned(&self, name: &str) -> Option<String> {
        if !self.entries.iter().any(|e| matches!(e, Entry::Jar(_, _, versioned) if versioned.contains_key(name))) {
            return None;
        }
        for entry in &self.entries {
            match entry {
                Entry::Jar(zip, path, versioned) if zip.contains(&format!("{name}.class")) || versioned.contains_key(name) => {
                    let releases = versioned.get(name)?;
                    let releases: Vec<String> = releases.iter().map(u32::to_string).collect();
                    return Some(format!(
                        "{} is a class of a multi-release JAR ({}) that holds a class file of it for Java {} (META-INF/versions/), which a JVM of that release or later loads in place of the base class file; the tool reads only the base, so the class is refused (lib/src/classpath.rs)",
                        name.replace('/', "."),
                        path.display(),
                        releases.join(", ")
                    ));
                }
                Entry::Jar(..) => {}
                Entry::Dir(dir) => {
                    if dir.join(format!("{name}.class")).is_file() {
                        return None;
                    }
                }
            }
        }
        None
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
        let (entry, bytes) = self.entries.iter().find_map(|e| e.read(name).ok().flatten().map(|b| (e, b)))?;
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
            if let Some(bytes) = entry.read(name)? {
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

    /// Reference-array comparison and hashing call the actual elements' methods.
    pub(crate) fn collection_static(&self, owner: &str, name: &str, descriptor: &str) -> bool {
        matches!((owner, name, descriptor),
            ("java/util/Arrays", "fill", "([CC)V")
            | ("java/util/Collections", "unmodifiableSet", "(Ljava/util/Set;)Ljava/util/Set;")
            | ("java/util/Objects", "equals", "(Ljava/lang/Object;Ljava/lang/Object;)Z")
            | ("java/util/Objects", "toString", "(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/String;")
            | ("java/util/Objects", "hash", "([Ljava/lang/Object;)I")
            | ("java/util/Objects", "hashCode", "(Ljava/lang/Object;)I")
            | ("java/util/Objects", "checkFromIndexSize", "(III)I")
            | ("jdk/internal/util/Preconditions", "checkFromIndexSize", "(IIILjava/util/function/BiFunction;)I")
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

    /// Selected collection and text bytecode. Callers qualify the actual receivers and helper arguments.
    pub(crate) fn library_image_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        let sublist = matches!(owner, "java/util/ArrayList$SubList" | "java/util/ArrayList$SubList$1");
        if !sublist && !self.collection_static(owner, name, descriptor) && !matches!((owner, name, descriptor),
            ("java/lang/String", "concat", "(Ljava/lang/String;)Ljava/lang/String;")
            | ("java/util/ArrayList", "<init>", "()V" | "(I)V")
            | ("java/util/ArrayList", "size", "()I") | ("java/util/ArrayList", "isEmpty", "()Z")
            | ("java/util/ArrayList", "get" | "elementData", "(I)Ljava/lang/Object;")
            | ("java/util/ArrayList", "clear", "()V")
            | ("java/util/ArrayList", "iterator", "()Ljava/util/Iterator;")
            | ("java/util/ArrayList", "subList", "(II)Ljava/util/List;")
            | ("java/util/AbstractList", "subListRangeCheck", "(III)V")
            | ("java/util/AbstractList", "clear", "()V")
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
            | ("java/util/ArrayList", "grow", "()[Ljava/lang/Object;" | "(I)[Ljava/lang/Object;")
            | ("java/util/ArrayList", "toArray", "()[Ljava/lang/Object;" | "([Ljava/lang/Object;)[Ljava/lang/Object;")
            | ("java/util/Arrays", "copyOf", "([Ljava/lang/Object;ILjava/lang/Class;)[Ljava/lang/Object;")
            | ("jdk/internal/util/ArraysSupport", "newLength", "(III)I")
            | ("jdk/internal/util/ArraysSupport", "hugeLength", "(II)I")) { return None; }
        let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
        if (sublist || owner == "java/util/ArrayList$Itr") && class.method("<clinit>", "()V").is_some() { return None; }
        let method = class.method(name, descriptor)?.clone();
        method.code.as_ref()?;
        Some((class, method))
    }

    /// Numeric code executed from the selected JDK image. Factories follow their actual
    /// allocation and cache branches. The hypot implementation includes the FdLibm helpers
    /// the selected image calls. An additional helper can produce a named refusal.
    pub(crate) fn numeric_image_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        if !matches!((owner, name, descriptor),
            ("java/lang/Math" | "java/lang/StrictMath", "hypot", "(DD)D")
            | ("java/lang/FdLibm$Hypot", "compute", "(DD)D")
            | ("java/lang/FdLibm", "__HI" | "__LO", "(D)I" | "(DI)D")
            | ("java/lang/Math", "powerOfTwoD" | "primPowerOfTwoD", "(I)D")
            | ("java/math/BigInteger", "valueOf", "(J)Ljava/math/BigInteger;")
            | ("java/math/BigInteger", "<init>", "(J)V")
            | ("java/math/BigInteger", "toMagArray", "(J)[I")
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
            | ("java/lang/Byte", "<init>", "(B)V") | ("java/lang/Short", "<init>", "(S)V")
            | ("java/lang/Long", "<init>", "(J)V") | ("java/lang/Float", "<init>", "(F)V")
            | ("java/lang/Double", "<init>", "(D)V") | ("java/lang/Number", "<init>", "()V"))
        {
            return None;
        }
        let Loaded { class, origin: Origin::Jdk } = self.load(owner).ok()?? else { return None };
        let method = class.method(name, descriptor)?.clone();
        method.code.as_ref()?;
        if matches!(owner, "java/lang/Math" | "java/lang/StrictMath" | "java/lang/FdLibm" | "java/lang/FdLibm$Hypot")
            && method.annotations(&class.pool).ok()?.iter().any(|a| matches!(a.type_name.rsplit('/').next(), Some("IntrinsicCandidate" | "HotSpotIntrinsicCandidate"))) {
            return None;
        }
        Some((class, method))
    }

    /// The compiler-generated assertion switch read by these image methods. Both possible values
    /// can be checked without relying on the JVM launcher having enabled or disabled assertions.
    pub(crate) fn numeric_assertion_flag(&self, owner: &str, name: &str, descriptor: &str) -> bool {
        if name != "$assertionsDisabled" || descriptor != "Z" || !matches!(owner, "java/lang/Math" | "java/lang/FdLibm$Hypot") {
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
        let interface = match (name, descriptor) {
            ("putIfAbsent", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;") if class == "java/util/EnumMap" => "java/util/Map",
            ("end", "()V") if class.starts_with("java/util/stream/ReduceOps$") => "java/util/stream/Sink",
            ("forEachRemaining", "(Ljava/util/function/Consumer;)V") if self.is_application(class) => "java/util/Iterator",
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
        if !matches!(name, "java/io/Reader" | "java/io/StringReader" | "java/io/Reader$2" | "java/io/BufferedReader" | "java/io/ObjectStreamField"
            | "java/util/Collections$EmptyList" | "java/util/Spliterators" | "java/util/Spliterators$IteratorSpliterator"
            | "java/util/Spliterators$EmptySpliterator" | "java/util/Spliterators$EmptySpliterator$OfRef" | "java/util/Spliterators$EmptySpliterator$OfInt"
            | "java/util/Spliterators$EmptySpliterator$OfLong" | "java/util/Spliterators$EmptySpliterator$OfDouble"
            | "java/util/Collections$EmptySet" | "java/util/Collections$UnmodifiableSet" | "java/util/Collections$UnmodifiableCollection"
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

    pub(crate) fn map_image_method(&self, owner: &str, name: &str, descriptor: &str) -> Option<(Rc<ClassFile>, Method)> {
        let (cf, m) = self.method_in(owner, name, descriptor, &|c| self.map_image_class(c))?;
        (m.code.is_some() && (name != "<init>" || cf.name == owner)).then_some((cf, m))
    }

    pub(crate) fn is_map_image(&self, cf: &Rc<ClassFile>) -> bool {
        self.map_image_class(&cf.name).is_some_and(|image| Rc::ptr_eq(cf, &image))
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
        for iface in self.all_interfaces(owner) {
            if let Some(class) = bytecode(&iface) {
                if let Some(m) = class.method(name, descriptor) {
                    return Some((class.clone(), m.clone()));
                }
            }
        }
        None
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
        // Interfaces, for default methods and abstract declarations.
        for iface in self.all_interfaces(owner) {
            if let Ok(Some(loaded)) = self.load(&iface) {
                if let Some(m) = loaded.class.method(name, descriptor) {
                    return Some((loaded.class.clone(), m.clone()));
                }
            }
        }
        None
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
