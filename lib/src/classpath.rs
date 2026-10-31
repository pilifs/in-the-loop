//! The closed world an analysis runs in: the application classes (directories and jars), and the JDK.
//!
//! Application classes are the code under verification. JDK classes are consulted for their *shape* only (their
//! superclasses, interfaces and member declarations), from the JDK image when one is found and from a built-in
//! table of `java.base` facts otherwise; their behaviour is never executed from bytecode but modelled by
//! [`crate::interp`].

use std::cell::RefCell;
use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::rc::Rc;

use crate::classfile::{ClassFile, Method};
use crate::jimage::JImage;
use crate::Error;

enum Entry {
    Dir(PathBuf),
    Jar(crate::zip::ZipArchive, PathBuf),
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
            Entry::Jar(zip, _) => zip.read(&format!("{class_name}.class")),
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
            Entry::Jar(zip, _) => Ok(zip
                .names()
                .filter(|n| n.ends_with(".class") && !n.starts_with("META-INF/"))
                .map(|n| n.trim_end_matches(".class").to_string())
                .collect()),
        }
    }

    fn display(&self) -> String {
        match self {
            Entry::Dir(d) => d.display().to_string(),
            Entry::Jar(_, p) => p.display().to_string(),
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
    cache: RefCell<HashMap<String, Option<Loaded>>>,
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
        ClassPath { entries: Vec::new(), jdk: None, cache: RefCell::new(HashMap::new()) }
    }

    /// Adds a directory of classes or a jar, by the path's kind.
    pub fn add(&mut self, path: &Path) -> Result<&mut Self, Error> {
        if path.is_dir() {
            self.entries.push(Entry::Dir(path.to_path_buf()));
        } else if path.is_file() {
            self.entries.push(Entry::Jar(crate::zip::ZipArchive::open(path)?, path.to_path_buf()));
        } else {
            return Err(Error::new(format!("{} is neither a directory nor a jar", path.display())));
        }
        self.cache.borrow_mut().clear();
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
        self
    }

    pub fn with_jdk(mut self, jdk: JImage) -> ClassPath {
        self.jdk = Some(jdk);
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

    /// Every application class name, in entry order and sorted within an entry.
    pub fn application_class_names(&self) -> Result<Vec<String>, Error> {
        let mut names = Vec::new();
        for entry in &self.entries {
            names.extend(entry.class_names()?);
        }
        Ok(names)
    }

    /// Every application class, parsed, keyed by name. Classes found in an earlier entry shadow later ones.
    pub fn application_classes(&self) -> Result<BTreeMap<String, Rc<ClassFile>>, Error> {
        let mut out = BTreeMap::new();
        for name in self.application_class_names()? {
            if out.contains_key(&name) {
                continue;
            }
            if let Some(loaded) = self.load(&name)? {
                out.insert(name, loaded.class);
            }
        }
        Ok(out)
    }

    /// Loads a class by internal name: the application entries first, then the JDK. `None` if nowhere.
    pub fn load(&self, name: &str) -> Result<Option<Loaded>, Error> {
        if let Some(cached) = self.cache.borrow().get(name) {
            return Ok(cached.clone());
        }
        let loaded = self.load_uncached(name)?;
        self.cache.borrow_mut().insert(name.to_string(), loaded.clone());
        Ok(loaded)
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
        Ok(None)
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
                return match (sub_elem.strip_prefix('L').and_then(|s| s.strip_suffix(';')), sup_elem.strip_prefix('L').and_then(|s| s.strip_suffix(';'))) {
                    (Some(a), Some(b)) => self.is_subtype(a, b),
                    _ => sub_elem == sup_elem || (sub_elem.starts_with('[') && sup_elem.starts_with('[') && self.is_subtype(sub_elem, sup_elem)),
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
