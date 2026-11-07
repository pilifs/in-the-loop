//! Code closure digests (`llm-dlc/loops/foundations-summaries.md`, S1): for a target in a build, a digest of everything
//! its proof reads, kept as parts so that two builds' closures say *which* parts differ.
//!
//! A closure is a map from part ids to the SHA-256 of each part's content:
//!
//! | Part | Content | Why it is read |
//! |---|---|---|
//! | `method pkg/C.m(D)` | access flags, the body's [`shape`](crate::shared) (each instruction with its constant-pool references resolved, the exception table with catch types resolved), the method's and its parameters' annotations, its declared exceptions | every method the target reaches, application classes only |
//! | `class pkg/C` | access flags, superclass chain, every superinterface, the record components, the permitted subclasses, every field with its access, type, `ConstantValue` and annotations, the class's annotations | every application class whose method is reached, whose field is read or written, that is made, cast to or tested, and every application supertype of one |
//! | `dispatch pkg/O.m(D)` | the classes whose method a virtual or interface call of `m(D)` on `O` may run: for each application class that is `O` or a subtype of it, the class that declares the method it resolves to | every `invokevirtual` and `invokeinterface`, on an application owner or a JDK one (an application class can override `Object.equals` or implement `Comparable`) |
//! | `config FILE` | the file's bytes | the application files (`application*.properties`, `application*.yml`, `application*.yaml`, at a resource root or under `config/`), for a closure that touches Spring |
//! | `missing NAME` | nothing | a class or method the closure names that the class path doesn't have: adding it later changes the closure |
//!
//! Following: from the target, every method a call may run (static and special calls by resolution, virtual and
//! interface calls by every dispatch target, lambda bodies through `LambdaMetafactory`'s handle), and the class
//! initializer of every application class in the closure, since a first use may run it. JDK classes are not
//! followed: the JDK's identity, the tool's models of it and the tool's own binary are their own part of the
//! canonical claim ([`crate::spec::ToolIdentity`]), so a closure only names the JDK methods its bodies call.
//!
//! A closure *touches Spring* when one of its classes, methods, fields or parameters carries an annotation of an
//! `org/springframework/` type, or a body calls or reads a member of an `org/springframework/` class. Configuration
//! reaches code only through Spring's binding (injected values, `Environment` lookups), so a closure that doesn't
//! touch Spring doesn't depend on the application files, and a change to them names only the closures that do.
//!
//! Differences that change no behaviour (a reordered constant pool, a recompile) leave a closure as it was. Some that
//! change none can still change it (an `ldc` that became an `ldc_w` moves every later offset): those are misses,
//! never wrong reuse.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::path::{Path, PathBuf};
use std::rc::Rc;

use serde::{Deserialize, Serialize};

use crate::classfile::{BootstrapArg, ClassFile, Insn, MemberRef, Method};
use crate::classpath::ClassPath;
use crate::digest::sha256_hex;
use crate::Error;

const SPRING: &str = "org/springframework/";

/// A target's closure in one build: each part's digest, by part id.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Closure {
    /// The target, `pkg/C.m(D)`.
    pub root: String,
    pub parts: BTreeMap<String, String>,
}

/// What kind of part an id names.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PartKind {
    Method,
    Class,
    Dispatch,
    Config,
    Missing,
}

impl PartKind {
    pub fn of(id: &str) -> PartKind {
        match id.split_once(' ').map(|(k, _)| k) {
            Some("method") => PartKind::Method,
            Some("class") => PartKind::Class,
            Some("dispatch") => PartKind::Dispatch,
            Some("config") => PartKind::Config,
            _ => PartKind::Missing,
        }
    }
}

/// How a part differs between two closures.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "change")]
pub enum PartChange {
    /// In the second closure only.
    Added { part: String },
    /// In the first closure only.
    Removed { part: String },
    Changed { part: String },
}

impl PartChange {
    pub fn part(&self) -> &str {
        match self {
            PartChange::Added { part } | PartChange::Removed { part } | PartChange::Changed { part } => part,
        }
    }
}

impl Closure {
    /// The digest of the whole closure: equal exactly when every part is.
    pub fn digest(&self) -> String {
        let mut text = format!("closure {}\n", self.root);
        for (id, digest) in &self.parts {
            text.push_str(&format!("{id}\t{digest}\n"));
        }
        sha256_hex(text.as_bytes())
    }

    /// The parts that differ from `self` to `other`, in part order. Empty exactly when the digests agree and the roots
    /// are the same.
    pub fn changes(&self, other: &Closure) -> Vec<PartChange> {
        let mut out = Vec::new();
        for (id, digest) in &self.parts {
            match other.parts.get(id) {
                None => out.push(PartChange::Removed { part: id.clone() }),
                Some(d) if d != digest => out.push(PartChange::Changed { part: id.clone() }),
                Some(_) => {}
            }
        }
        for id in other.parts.keys() {
            if !self.parts.contains_key(id) {
                out.push(PartChange::Added { part: id.clone() });
            }
        }
        out.sort();
        out
    }
}

/// The application files a closure that touches Spring depends on, read once per build.
#[derive(Debug, Clone, Default)]
pub struct Configuration {
    /// Each file as the contract names it (`application.yaml`, `config/application-prod.properties`), with its digest.
    files: BTreeMap<String, String>,
}

impl Configuration {
    /// The application files under the resource roots, as [`crate::config::read_files`] finds them, and those at
    /// the root of the class path (`application.properties` in a build's output, say).
    pub fn read(cp: &ClassPath, resource_dirs: &[PathBuf]) -> Result<Configuration, Error> {
        let mut files = BTreeMap::new();
        for dir in resource_dirs {
            for sub in ["", "config"] {
                let folder = if sub.is_empty() { dir.clone() } else { dir.join(sub) };
                let Ok(entries) = std::fs::read_dir(&folder) else { continue };
                for entry in entries.filter_map(|e| e.ok()) {
                    let name = entry.file_name().to_string_lossy().into_owned();
                    if !is_application_file(&name) {
                        continue;
                    }
                    let path = folder.join(&name);
                    let bytes = std::fs::read(&path).map_err(|e| Error::new(format!("cannot read {}: {e}", path.display())))?;
                    let display = if sub.is_empty() { name } else { format!("{sub}/{name}") };
                    files.insert(format!("{}:{display}", dir.display()), sha256_hex(&bytes));
                }
            }
        }
        for sub in ["", "config/"] {
            for ext in ["properties", "yml", "yaml"] {
                let name = format!("{sub}application.{ext}");
                for (entry, bytes) in cp.resources(&name)? {
                    files.insert(format!("{entry}:{name}"), sha256_hex(&bytes));
                }
            }
        }
        Ok(Configuration { files })
    }

    /// No application files: for a build that has none, or a check that reads none.
    pub fn none() -> Configuration {
        Configuration::default()
    }

    /// A configuration of named files with their contents, for tests and for callers that read the files themselves.
    pub fn of(files: &[(&str, &[u8])]) -> Configuration {
        Configuration { files: files.iter().map(|(n, b)| (n.to_string(), sha256_hex(b))).collect() }
    }
}

fn is_application_file(name: &str) -> bool {
    let Some((stem, ext)) = name.rsplit_once('.') else { return false };
    matches!(ext, "yaml" | "yml" | "properties") && (stem == "application" || stem.starts_with("application-"))
}

/// The closure of `root` (`pkg/C`, `m`, its descriptor) in the build `cp` is, with the build's application files.
pub fn closure(cp: &ClassPath, root: &MemberRef, configuration: &Configuration) -> Closure {
    Walk::new(cp).run(root, configuration)
}

/// The closures of several targets in one build, sharing the work of enumerating its classes.
pub fn closures(cp: &ClassPath, roots: &[MemberRef], configuration: &Configuration) -> Vec<Closure> {
    let mut walk = Walk::new(cp);
    roots.iter().map(|r| walk.run(r, configuration)).collect()
}

/// `pkg/C.m(D)`, the id a closure gives a method.
pub fn method_id(m: &MemberRef) -> String {
    format!("{}.{}{}", m.owner, m.name, m.descriptor)
}

struct Walk<'a> {
    cp: &'a ClassPath,
    /// Every application class of the build, by name: dispatch targets are looked for among them.
    classes: Option<BTreeMap<String, Rc<ClassFile>>>,
}

impl<'a> Walk<'a> {
    fn new(cp: &'a ClassPath) -> Walk<'a> {
        Walk { cp, classes: None }
    }

    fn application_classes(&mut self) -> &BTreeMap<String, Rc<ClassFile>> {
        let cp = self.cp;
        self.classes.get_or_insert_with(|| cp.application_classes().unwrap_or_default())
    }

    fn run(&mut self, root: &MemberRef, configuration: &Configuration) -> Closure {
        let cp = self.cp;
        let mut parts: BTreeMap<String, String> = BTreeMap::new();
        let mut spring = false;
        let mut seen_methods: BTreeSet<MemberRef> = BTreeSet::new();
        let mut seen_classes: BTreeSet<String> = BTreeSet::new();
        let mut work: VecDeque<MemberRef> = VecDeque::from([root.clone()]);
        let mut class_work: VecDeque<String> = VecDeque::new();
        loop {
            // Classes first: each brings its supertypes and its initializer.
            while let Some(name) = class_work.pop_front() {
                if !seen_classes.insert(name.clone()) {
                    continue;
                }
                let Ok(Some(class)) = cp.application(&name) else {
                    parts.insert(format!("missing {name}"), sha256_hex(b"missing"));
                    continue;
                };
                let (text, touches) = class_content(cp, &class);
                spring |= touches;
                parts.insert(format!("class {name}"), sha256_hex(text.as_bytes()));
                for sup in class.super_class.iter().chain(class.interfaces.iter()) {
                    if cp.is_application(sup) {
                        class_work.push_back(sup.clone());
                    }
                }
                if class.method("<clinit>", "()V").is_some() {
                    work.push_back(MemberRef::new(&name, "<clinit>", "()V"));
                }
            }
            let Some(reference) = work.pop_front() else { break };
            if !seen_methods.insert(reference.clone()) {
                continue;
            }
            let Some((class, method)) = cp.find_method(&reference.owner, &reference.name, &reference.descriptor) else {
                if cp.is_application(&reference.owner) || reference == *root {
                    parts.insert(format!("missing {}", method_id(&reference)), sha256_hex(b"missing"));
                }
                continue;
            };
            if !cp.is_application(&class.name) {
                continue; // the JDK and the tool's models are the canonical claim's tools
            }
            class_work.push_back(class.name.clone());
            let declared = MemberRef::new(&class.name, &reference.name, &reference.descriptor);
            if declared != reference {
                // Resolved through a superclass: the resolution is part of the closure, as the method it found.
                seen_methods.insert(declared.clone());
            }
            let (text, touches) = method_content(&class, &method);
            spring |= touches;
            parts.insert(format!("method {}", method_id(&declared)), sha256_hex(text.as_bytes()));
            let Some(code) = &method.code else { continue };
            let Ok(insns) = code.instructions() else { continue };
            for (_, insn) in insns {
                match insn {
                    Insn::GetStatic(i) | Insn::PutStatic(i) | Insn::GetField(i) | Insn::PutField(i) => {
                        if let Ok(field) = class.pool.member(i) {
                            spring |= field.owner.starts_with(SPRING);
                            if cp.is_application(&field.owner) {
                                class_work.push_back(field.owner);
                            }
                        }
                    }
                    Insn::InvokeStatic(i) | Insn::InvokeSpecial(i) => {
                        let Ok(callee) = class.pool.member(i) else { continue };
                        spring |= callee.owner.starts_with(SPRING);
                        if cp.is_application(&callee.owner) {
                            class_work.push_back(callee.owner.clone());
                            work.push_back(callee);
                        }
                    }
                    Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => {
                        let Ok(callee) = class.pool.member(i) else { continue };
                        spring |= callee.owner.starts_with(SPRING);
                        if callee.owner.starts_with('[') {
                            continue; // an array's clone(): the JDK's
                        }
                        if cp.is_application(&callee.owner) {
                            class_work.push_back(callee.owner.clone());
                        }
                        let targets = self.dispatch_targets(&callee);
                        let text = targets.iter().map(|t| format!("{t}\n")).collect::<String>();
                        parts.insert(format!("dispatch {}", method_id(&callee)), sha256_hex(text.as_bytes()));
                        for t in targets {
                            work.push_back(MemberRef::new(&t, &callee.name, &callee.descriptor));
                        }
                    }
                    Insn::InvokeDynamic(i) => {
                        let Ok((bootstrap_index, _, _)) = class.pool.invoke_dynamic(i) else { continue };
                        let bootstraps = class.bootstrap_methods().unwrap_or_default();
                        let Some(bootstrap) = bootstraps.get(bootstrap_index as usize) else { continue };
                        for arg in &bootstrap.args {
                            if let BootstrapArg::MethodHandle(handle) = arg {
                                spring |= handle.member.owner.starts_with(SPRING);
                                if cp.is_application(&handle.member.owner) {
                                    class_work.push_back(handle.member.owner.clone());
                                    work.push_back(handle.member.clone());
                                }
                            }
                        }
                    }
                    Insn::New(i) | Insn::ANewArray(i) | Insn::CheckCast(i) | Insn::InstanceOf(i) | Insn::MultiANewArray(i, _) => {
                        if let Ok(name) = class.pool.class_name(i) {
                            let element = name.trim_start_matches('[');
                            let element = element.strip_prefix('L').and_then(|e| e.strip_suffix(';')).unwrap_or(element);
                            spring |= element.starts_with(SPRING);
                            if cp.is_application(element) {
                                class_work.push_back(element.to_string());
                            }
                        }
                    }
                    Insn::Ldc(i) => {
                        if let Ok(BootstrapArg::Class(name)) = class.pool.loadable(i) {
                            if cp.is_application(&name) {
                                class_work.push_back(name);
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
        if spring {
            for (file, digest) in &configuration.files {
                parts.insert(format!("config {file}"), digest.clone());
            }
        }
        Closure { root: method_id(root), parts }
    }

    /// The classes declaring the method a virtual or interface call of `callee` may run: for the owner and each
    /// application subtype of it, the declaration it resolves to, when that declaration has code or is native.
    fn dispatch_targets(&mut self, callee: &MemberRef) -> BTreeSet<String> {
        let cp = self.cp;
        let mut owners: Vec<String> = vec![callee.owner.clone()];
        owners.extend(self.application_classes().iter().filter(|(_, c)| !c.is_interface() && !c.is_abstract()).map(|(n, _)| n.clone()));
        let mut targets = BTreeSet::new();
        for owner in owners {
            if owner != callee.owner && !cp.is_subtype(&owner, &callee.owner) {
                continue;
            }
            if let Some((declaring, m)) = cp.find_method(&owner, &callee.name, &callee.descriptor) {
                if !m.is_abstract() && cp.is_application(&declaring.name) {
                    targets.insert(declaring.name.clone());
                }
            }
        }
        targets
    }
}

fn class_content(cp: &ClassPath, class: &ClassFile) -> (String, bool) {
    let mut text = format!("access {:#06x}\n", class.access);
    let mut spring = false;
    text.push_str(&format!("super {:?}\n", cp.superclasses(&class.name)));
    let mut interfaces = cp.all_interfaces(&class.name);
    interfaces.sort();
    text.push_str(&format!("interfaces {interfaces:?}\n"));
    if let Ok(components) = class.record_components() {
        for c in components {
            text.push_str(&format!("component {} {}\n", c.name, c.descriptor));
        }
    }
    if let Ok(permitted) = class.permitted_subclasses() {
        text.push_str(&format!("permits {permitted:?}\n"));
    }
    if let Ok(annotations) = class.annotations() {
        spring |= annotations.iter().any(|a| a.type_name.starts_with(SPRING));
        text.push_str(&format!("annotations {annotations:?}\n"));
    }
    for field in &class.fields {
        let constant = field.attributes.iter().find(|a| a.name == "ConstantValue").and_then(|a| {
            let index = u16::from_be_bytes([*a.data.first()?, *a.data.get(1)?]);
            class.pool.loadable(index).ok()
        });
        let annotations = field.annotations(&class.pool).unwrap_or_default();
        spring |= annotations.iter().any(|a| a.type_name.starts_with(SPRING)) || field.descriptor.contains("Lorg/springframework/");
        text.push_str(&format!("field {:#06x} {} {} {constant:?} {annotations:?}\n", field.access, field.name, field.descriptor));
    }
    (text, spring)
}

fn method_content(class: &ClassFile, method: &Method) -> (String, bool) {
    let mut text = format!("access {:#06x}\n", method.access);
    let annotations = method.annotations(&class.pool).unwrap_or_default();
    let parameters = method.parameter_annotations(&class.pool).unwrap_or_default();
    let spring = annotations.iter().chain(parameters.iter().flatten()).any(|a| a.type_name.starts_with(SPRING));
    text.push_str(&format!("annotations {annotations:?}\nparameters {parameters:?}\n"));
    text.push_str(&format!("throws {:?}\n", method.declared_exceptions(&class.pool).unwrap_or_default()));
    match &method.code {
        None => text.push_str(if method.is_native() { "native\n" } else { "abstract\n" }),
        Some(_) => match crate::shared::shape(class, method) {
            Some(lines) => {
                for line in lines {
                    text.push_str(&line);
                    text.push('\n');
                }
            }
            // Undecodable code: its bytes, so that any change to it is a change.
            None => text.push_str(&format!("raw {:?}\n", method.code.as_ref().map(|c| sha256_hex(&c.bytes)))),
        },
    }
    (text, spring)
}

/// The class path of one build for closures: its directories or jars, with the JDK and the tool's models.
pub fn build_class_path(entries: &[&Path]) -> Result<ClassPath, Error> {
    let mut cp = ClassPath::new().with_default_jdk();
    for e in entries {
        cp.add(e)?;
    }
    Ok(cp)
}
