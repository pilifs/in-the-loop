//! Copies a directory of compiled classes into a new package prefix, so that two versions of the same classes can
//! be loaded side by side: `net/example/Pricing` becomes `before/net/example/Pricing`, and every reference between
//! the copied classes follows.
//!
//! Class names only ever appear in a class file's constant pool, as UTF-8 entries: on their own (class entries),
//! inside field and method descriptors (`Lnet/example/Pricing;`), and inside generic signatures
//! (`Lnet/example/Pricing<...>;`). Rewriting those entries, and nothing else, relocates the class. Everything after
//! the constant pool refers to entries by index and is copied unchanged.

use std::collections::BTreeSet;
use std::path::Path;

use crate::classfile::{decode_modified_utf16, decode_modified_utf8, encode_modified_utf8, flags};
use crate::Error;

/// The previous version of a pair of versions held in one program: which of its classes the program holds, under
/// which names, and what its class path holds besides. A question the previous version's code asks by a name it
/// computes (a class by its name, a class's name) is answered from here, as on the previous version's own class
/// path, and not from the program's, which is the new version's with the copies beside it.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Previous {
    /// The package the copies are under, `before`.
    pub prefix: String,
    /// The classes copied, by their own internal names: the previous version's build and, with a dependency
    /// closure of its own, the classes of it that the copies name.
    pub relocated: BTreeSet<String>,
    /// Every class the previous version's class path holds, its build included, by internal name.
    pub classes: BTreeSet<String>,
    /// Whether the libraries are both versions' (no closure of its own): a class of them is the program's as it is.
    pub shared: bool,
    /// The previous version's class path: its build, then its libraries.
    pub classpath: Vec<std::path::PathBuf>,
}

/// A class by its name, as the previous version's code finds it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Found {
    /// The program's class of this internal name: a copy, or a library's class both versions share.
    Class(String),
    /// The previous version's class path has the class, and the program holds no copy of it (nothing the copies
    /// name in a constant pool reaches it).
    NotCopied,
    /// The previous version's class path has no such class: the JDK's, or none.
    Elsewhere,
}

impl Previous {
    /// The own name of a class the program holds as a copy (`before/x/Y` is `x/Y`), or `None` for any other.
    pub fn original<'a>(&self, name: &'a str) -> Option<&'a str> {
        name.strip_prefix(self.prefix.as_str())?.strip_prefix('/').filter(|n| self.relocated.contains(*n))
    }

    /// The class of the internal name `name`, as the previous version's code finds it by that name.
    pub fn find(&self, name: &str) -> Found {
        if self.relocated.contains(name) {
            Found::Class(format!("{}/{name}", self.prefix))
        } else if !self.classes.contains(name) {
            Found::Elsewhere
        } else if self.shared {
            Found::Class(name.to_string())
        } else {
            Found::NotCopied
        }
    }
}

/// Copies every class under `input` to `output/<prefix>/...`, renamed. Returns the relocated class names.
pub fn directory(input: &Path, output: &Path, prefix: &str) -> Result<BTreeSet<String>, Error> {
    let mut files = Vec::new();
    collect(input, input, &mut files)?;
    let own: BTreeSet<String> = files.iter().map(|(name, _)| name.clone()).collect();
    for (name, path) in &files {
        let target = output.join(prefix).join(format!("{name}.class"));
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let bytes = std::fs::read(path)?;
        std::fs::write(&target, class_file(&bytes, &own, prefix)?)?;
    }
    Ok(own)
}

/// As [`directory`], where the previous version has a dependency closure of its own (`closure`: its libraries, in
/// class path order, as [`crate::classpath::ClassPath::application_bytes`] reads them): every class of the closure
/// that the classes under `input` name, directly or through the closure's classes they name in turn, is copied and
/// renamed with them. So the previous version runs on its own libraries (`before/io/micrometer/…/Tag`) beside the
/// new version on its own, in one program, and a class the two closures hold differently is each version's own.
/// A class is named wherever a constant pool entry holds its name: as a class, or inside a descriptor or a generic
/// signature, so a type only passed through is copied too. A JDK class is in no closure, and is both versions'.
///
/// `absent` are the classes the new version has that the previous version's build and closure do not: a name of
/// theirs in a copied class is renamed too, to a class that does not exist, so the previous version finds no such
/// class, as on its own class path, and never the new version's.
pub fn with_closure(input: &Path, closure: &crate::classpath::ClassPath, absent: &BTreeSet<String>, output: &Path, prefix: &str) -> Result<BTreeSet<String>, Error> {
    let mut files = Vec::new();
    collect(input, input, &mut files)?;
    let library: BTreeSet<String> = closure.application_class_names()?.into_iter().collect();
    let mut classes: Vec<(String, Vec<u8>)> = Vec::new();
    let mut own: BTreeSet<String> = BTreeSet::new();
    for (name, path) in files {
        own.insert(name.clone());
        classes.push((name, std::fs::read(path)?));
    }
    // The closure's classes reached so far, each read once: `classes[at..]` are still to be looked into.
    let mut at = 0;
    while at < classes.len() {
        let named = named_among(&classes[at].1, &library)?;
        at += 1;
        for name in named {
            if own.contains(&name) {
                continue;
            }
            if let Some(bytes) = closure.application_bytes(&name)? {
                own.insert(name.clone());
                classes.push((name, bytes));
            }
        }
    }
    let renamed: BTreeSet<String> = own.union(absent).cloned().collect();
    for (name, bytes) in &classes {
        let target = output.join(prefix).join(format!("{name}.class"));
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(&target, class_file(bytes, &renamed, prefix)?)?;
    }
    Ok(own)
}

/// The classes among `known` that a class file's constant pool names: an entry that is one's name, or holds it as
/// `L<name>;` or `L<name><` in a descriptor or a signature, which are the places [`rename`] renames.
fn named_among(bytes: &[u8], known: &BTreeSet<String>) -> Result<BTreeSet<String>, Error> {
    let mut out = BTreeSet::new();
    for text in pool(bytes)?.utf8.into_iter().flatten() {
        if known.contains(&text) {
            out.insert(text);
            continue;
        }
        let mut rest = text.as_str();
        while let Some(start) = rest.find('L') {
            rest = &rest[start + 1..];
            let end = rest.find([';', '<']).unwrap_or(rest.len());
            if known.contains(&rest[..end]) {
                out.insert(rest[..end].to_string());
                rest = &rest[end..];
            }
        }
    }
    Ok(out)
}

fn collect(root: &Path, dir: &Path, out: &mut Vec<(String, std::path::PathBuf)>) -> Result<(), Error> {
    for entry in std::fs::read_dir(dir)? {
        let path = entry?.path();
        if path.is_dir() {
            collect(root, &path, out)?;
        } else if path.extension().is_some_and(|e| e == "class") {
            let relative = path.strip_prefix(root).unwrap_or(&path).with_extension("");
            out.push((relative.to_string_lossy().replace('\\', "/"), path));
        }
    }
    Ok(())
}

/// Rewrites one class file's constant pool.
pub fn class_file(bytes: &[u8], own: &BTreeSet<String>, prefix: &str) -> Result<Vec<u8>, Error> {
    let mut out = Vec::with_capacity(bytes.len() + 256);
    let mut pos = 0usize;
    let mut take = |n: usize| -> Result<&[u8], Error> {
        let slice = bytes.get(pos..pos + n).ok_or_else(|| Error::new("truncated class file"))?;
        pos += n;
        Ok(slice)
    };
    out.extend_from_slice(take(8)?); // magic, minor, major
    let count_bytes = take(2)?;
    let count = u16::from_be_bytes([count_bytes[0], count_bytes[1]]);
    out.extend_from_slice(count_bytes);
    let mut i = 1;
    while i < count {
        let tag = take(1)?[0];
        out.push(tag);
        match tag {
            1 => {
                let len_bytes = take(2)?;
                let len = u16::from_be_bytes([len_bytes[0], len_bytes[1]]) as usize;
                let original = take(len)?;
                // Only a name changes, and a name is well-formed text. So an entry that isn't (a String constant
                // with an isolated surrogate, which the text reads as U+FFFD), or that renaming leaves as it was,
                // keeps its bytes.
                let renamed = match String::from_utf16(&decode_modified_utf16(original)) {
                    Ok(text) => match rename(&text, own, prefix) {
                        renamed if renamed == text => original.to_vec(),
                        renamed => encode_modified_utf8(&renamed),
                    },
                    Err(_) => original.to_vec(),
                };
                out.extend((renamed.len() as u16).to_be_bytes());
                out.extend(renamed);
            }
            3 | 4 => out.extend_from_slice(take(4)?),
            5 | 6 => {
                out.extend_from_slice(take(8)?);
                i += 1;
            }
            7 | 8 | 16 | 19 | 20 => out.extend_from_slice(take(2)?),
            9 | 10 | 11 | 12 | 17 | 18 => out.extend_from_slice(take(4)?),
            15 => out.extend_from_slice(take(3)?),
            other => return Err(Error::new(format!("unknown constant pool tag {other}"))),
        }
        i += 1;
    }
    out.extend_from_slice(&bytes[pos..]);
    Ok(out)
}

/// What [`referenced_classes`] and [`opened`] read of a class file's constant pool: each UTF-8 entry by index, the
/// name index of each class entry, and where the pool ends.
struct Pool {
    utf8: Vec<Option<String>>,
    classes: Vec<u16>,
    end: usize,
}

fn pool(bytes: &[u8]) -> Result<Pool, Error> {
    let short = || Error::new("truncated class file");
    let u2 = |at: usize| -> Result<u16, Error> { bytes.get(at..at + 2).map(|b| u16::from_be_bytes([b[0], b[1]])).ok_or_else(short) };
    let count = u2(8)?;
    let mut utf8 = vec![None; count as usize];
    let mut classes = Vec::new();
    let mut pos = 10usize;
    let mut i = 1u16;
    while i < count {
        let tag = *bytes.get(pos).ok_or_else(short)?;
        pos += 1;
        match tag {
            1 => {
                let len = u2(pos)? as usize;
                let text = bytes.get(pos + 2..pos + 2 + len).ok_or_else(short)?;
                utf8[i as usize] = Some(decode_modified_utf8(text));
                pos += 2 + len;
            }
            7 => {
                classes.push(u2(pos)?);
                pos += 2;
            }
            3 | 4 => pos += 4,
            5 | 6 => {
                pos += 8;
                i += 1;
            }
            8 | 16 | 19 | 20 => pos += 2,
            9 | 10 | 11 | 12 | 17 | 18 => pos += 4,
            15 => pos += 3,
            other => return Err(Error::new(format!("unknown constant pool tag {other}"))),
        }
        i += 1;
    }
    Ok(Pool { utf8, classes, end: pos })
}

/// The classes a class file's constant pool names in its class entries, array classes left out: those its code
/// makes, casts to, calls into or reads a field of.
pub fn referenced_classes(bytes: &[u8]) -> Result<Vec<String>, Error> {
    let pool = pool(bytes)?;
    Ok(pool.classes.iter().filter_map(|&n| pool.utf8.get(n as usize).cloned().flatten()).filter(|n| !n.starts_with('[')).collect())
}

/// A copy of a class file that another package's class can use as a harness does (step H4 of
/// `llm-dlc/loops/foundations-heap.md`): the class, each of its fields, its constructors and its static methods
/// made public. Nothing else changes. Field resolution, constructor calls and static calls don't depend on access
/// (JVMS 5.4.3.2, 5.4.3.3), so a program that ran without an access error runs as it did; only reflection on the
/// modifiers would tell. Instance methods keep their access, since it decides which methods override which (JVMS
/// 5.4.5); [`opened_with`] opens those it may.
pub fn opened(bytes: &[u8]) -> Result<Vec<u8>, Error> {
    open(bytes, None)
}

/// [`opened`], with also each protected instance method made public, and each package-private one for which
/// `may_open(name, descriptor)` holds, which the caller says where no class of another package that extends this
/// one declares a method of that name and descriptor: then making it public changes no override (JVMS 5.4.5: a
/// subclass of the same package overrides a package-private method already, and a protected one is overridden from
/// any package), so dispatch runs as it did. A harness in the unnamed package calls a package-private target so
/// (`QuoteService.fee`, a helper of the quote family).
pub fn opened_with(bytes: &[u8], may_open: &dyn Fn(&str, &str) -> bool) -> Result<Vec<u8>, Error> {
    open(bytes, Some(may_open))
}

/// [`opened`], and with `instances` [`opened_with`].
fn open(bytes: &[u8], instances: Option<&dyn Fn(&str, &str) -> bool>) -> Result<Vec<u8>, Error> {
    let pool = pool(bytes)?;
    let mut out = bytes.to_vec();
    let short = || Error::new("truncated class file");
    let u2 = |out: &[u8], at: usize| -> Result<u16, Error> { out.get(at..at + 2).map(|b| u16::from_be_bytes([b[0], b[1]])).ok_or_else(short) };
    let public = |f: u16| (f & !(flags::PRIVATE | flags::PROTECTED)) | flags::PUBLIC;
    let mut pos = pool.end;
    let class_flags = u2(&out, pos)?;
    out[pos..pos + 2].copy_from_slice(&public(class_flags).to_be_bytes());
    pos += 6; // access, this, super
    let interfaces = u2(&out, pos)? as usize;
    pos += 2 + 2 * interfaces;
    for members in 0..2 {
        let count = u2(&out, pos)?;
        pos += 2;
        for _ in 0..count {
            let access = u2(&out, pos)?;
            let name = pool.utf8.get(u2(&out, pos + 2)? as usize).cloned().flatten().unwrap_or_default();
            let instance = access & (flags::STATIC | flags::PRIVATE) == 0 && name != "<init>" && name != "<clinit>";
            let package_private = access & (flags::PUBLIC | flags::PROTECTED) == 0;
            let descriptor = || pool.utf8.get(u2(&out, pos + 4).unwrap_or(0) as usize).cloned().flatten().unwrap_or_default();
            let open = members == 0
                || name == "<init>"
                || (access & flags::STATIC != 0 && name != "<clinit>")
                || (members == 1 && instance && instances.is_some_and(|may_open| !package_private || may_open(&name, &descriptor())));
            if open {
                out[pos..pos + 2].copy_from_slice(&public(access).to_be_bytes());
            }
            let attributes = u2(&out, pos + 6)?;
            pos += 8;
            for _ in 0..attributes {
                let len = out.get(pos + 2..pos + 6).map(|b| u32::from_be_bytes([b[0], b[1], b[2], b[3]])).ok_or_else(short)? as usize;
                pos += 6 + len;
            }
        }
    }
    Ok(out)
}

/// Renames a constant pool string if it is a relocated class name or contains one as a descriptor.
pub fn rename(s: &str, own: &BTreeSet<String>, prefix: &str) -> String {
    if own.contains(s) {
        return format!("{prefix}/{s}");
    }
    if !s.contains('L') {
        return s.to_string();
    }
    let chars: Vec<char> = s.chars().collect();
    let mut result = String::with_capacity(s.len() + 16);
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == 'L' {
            let mut end = i + 1;
            while end < chars.len() && chars[end] != ';' && chars[end] != '<' {
                end += 1;
            }
            let name: String = chars[i + 1..end].iter().collect();
            if own.contains(&name) {
                result.push('L');
                result.push_str(prefix);
                result.push('/');
                result.push_str(&name);
                i = end;
                continue;
            }
        }
        result.push(chars[i]);
        i += 1;
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A previous version with a closure of its own takes with it the closure's classes it names, in a class entry,
    /// a descriptor or a signature, and those they name in turn; a class it doesn't reach stays behind, and a name
    /// only the new version has is renamed to a class that isn't there.
    #[test]
    fn a_closure_of_its_own_is_relocated_as_far_as_the_build_names_it() {
        use crate::classfile::writer::{ClassWriter, FieldWriter, MethodWriter};
        use crate::classfile::ClassFile;
        let root = crate::tla::tempfile_path("jvmcontract-relocate-closure");
        let class = |dir: &str, name: &str, fields: &[&str], methods: &[&str]| {
            let mut w = ClassWriter::new(name);
            w.access = flags::PUBLIC | flags::ABSTRACT;
            w.fields = fields.iter().enumerate().map(|(i, d)| FieldWriter { access: flags::PUBLIC, name: format!("f{i}"), descriptor: d.to_string() }).collect();
            w.methods = methods.iter().enumerate().map(|(i, d)| MethodWriter { access: flags::PUBLIC | flags::ABSTRACT, name: format!("m{i}"), descriptor: d.to_string(), code: None }).collect();
            let path = root.join(dir).join(format!("{name}.class"));
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, w.to_bytes()).unwrap();
        };
        class("build", "app/Tags", &["Llib/Money;"], &["(Llib/Request;)[Llib/Tag;", "()Lnext/Verb;"]);
        class("closure", "lib/Money", &[], &[]);
        class("closure", "lib/Request", &[], &["()Llib/Session;"]);
        class("closure", "lib/Session", &[], &[]);
        class("closure", "lib/Tag", &[], &[]);
        class("closure", "lib/Unused", &[], &[]);
        let mut closure = crate::classpath::ClassPath::new();
        closure.add(&root.join("closure")).unwrap();
        let absent: BTreeSet<String> = ["next/Verb".to_string()].into();
        let own = with_closure(&root.join("build"), &closure, &absent, &root.join("out"), "before").unwrap();
        assert_eq!(own.iter().map(String::as_str).collect::<Vec<_>>(), ["app/Tags", "lib/Money", "lib/Request", "lib/Session", "lib/Tag"]);
        assert!(!root.join("out/before/lib/Unused.class").exists() && !root.join("out/before/next/Verb.class").exists());
        let tags = ClassFile::parse(&std::fs::read(root.join("out/before/app/Tags.class")).unwrap()).unwrap();
        assert_eq!(tags.name, "before/app/Tags");
        assert_eq!(tags.fields[0].descriptor, "Lbefore/lib/Money;");
        assert_eq!(tags.methods.iter().map(|m| m.descriptor.as_str()).collect::<Vec<_>>(), ["(Lbefore/lib/Request;)[Lbefore/lib/Tag;", "()Lbefore/next/Verb;"]);
        let request = ClassFile::parse(&std::fs::read(root.join("out/before/lib/Request.class")).unwrap()).unwrap();
        assert_eq!(request.methods[0].descriptor, "()Lbefore/lib/Session;");
        std::fs::remove_dir_all(&root).ok();
    }

    #[test]
    fn an_opened_class_is_public_with_its_fields_constructors_and_static_methods_and_nothing_else_changes() {
        use crate::classfile::writer::{ClassWriter, CodeBuilder, FieldWriter, MethodWriter};
        use crate::classfile::ClassFile;
        let mut w = ClassWriter::new("shop/Money");
        w.access = flags::FINAL | flags::SUPER;
        w.fields.push(FieldWriter { access: flags::PRIVATE | flags::FINAL, name: "cents".into(), descriptor: "J".into() });
        w.fields.push(FieldWriter { access: flags::PROTECTED, name: "note".into(), descriptor: "I".into() });
        let body = |access: u16, name: &str| {
            let mut code = CodeBuilder::new();
            code.max_locals = 1;
            code.return_(None);
            MethodWriter { access, name: name.into(), descriptor: "()V".into(), code: Some(code) }
        };
        w.methods.push(body(flags::PRIVATE, "<init>"));
        w.methods.push(body(flags::STATIC, "helper"));
        w.methods.push(body(flags::PRIVATE, "own"));
        w.methods.push(body(flags::STATIC, "<clinit>"));
        let bytes = w.to_bytes();
        let opened = ClassFile::parse(&opened(&bytes).unwrap()).unwrap();
        let original = ClassFile::parse(&bytes).unwrap();
        assert_eq!(opened.access, flags::PUBLIC | flags::FINAL | flags::SUPER);
        assert_eq!(opened.fields.iter().map(|f| f.access).collect::<Vec<_>>(), [flags::PUBLIC | flags::FINAL, flags::PUBLIC]);
        let access: Vec<(&str, u16)> = opened.methods.iter().map(|m| (m.name.as_str(), m.access)).collect();
        assert_eq!(access, [("<init>", flags::PUBLIC), ("helper", flags::PUBLIC | flags::STATIC), ("own", flags::PRIVATE), ("<clinit>", flags::STATIC)]);
        assert_eq!(opened.pool.len(), original.pool.len());
        assert_eq!(opened.methods.iter().map(|m| m.code.as_ref().map(|c| c.bytes.clone())).collect::<Vec<_>>(), original.methods.iter().map(|m| m.code.as_ref().map(|c| c.bytes.clone())).collect::<Vec<_>>());
        assert!(referenced_classes(&bytes).unwrap().contains(&"shop/Money".to_string()));
    }

    /// `opened_with` opens a protected instance method always, a package-private one only where its caller says no
    /// override changes (`may_open`), and never a private one, a constructor's access aside.
    #[test]
    fn an_instance_method_is_opened_only_where_no_override_changes() {
        use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
        use crate::classfile::ClassFile;
        let mut w = ClassWriter::new("quotes/QuoteService");
        w.access = flags::SUPER;
        let body = |access: u16, name: &str, descriptor: &str| {
            let mut code = CodeBuilder::new();
            code.max_locals = 2;
            code.return_(None);
            MethodWriter { access, name: name.into(), descriptor: descriptor.into(), code: Some(code) }
        };
        w.methods.push(body(0, "fee", "(I)V"));
        w.methods.push(body(0, "kept", "(I)V"));
        w.methods.push(body(flags::PROTECTED, "shown", "()V"));
        w.methods.push(body(flags::PRIVATE, "own", "()V"));
        let bytes = w.to_bytes();
        let asked = std::cell::RefCell::new(Vec::new());
        let opened = ClassFile::parse(&opened_with(&bytes, &|m, d| {
            asked.borrow_mut().push(format!("{m}{d}"));
            m == "fee"
        }).unwrap()).unwrap();
        let access: Vec<(&str, u16)> = opened.methods.iter().map(|m| (m.name.as_str(), m.access)).collect();
        assert_eq!(access, [("fee", flags::PUBLIC), ("kept", 0), ("shown", flags::PUBLIC), ("own", flags::PRIVATE)]);
        assert_eq!(*asked.borrow(), ["fee(I)V", "kept(I)V"], "only package-private methods are asked about, by descriptor");
        let plain = ClassFile::parse(&super::opened(&bytes).unwrap()).unwrap();
        assert_eq!(plain.methods.iter().map(|m| m.access).collect::<Vec<_>>(), [0, 0, flags::PROTECTED, flags::PRIVATE], "opened keeps every instance method's access");
    }

    /// A String constant with an isolated surrogate keeps its code units through the copy, as the JVM and JBMC then
    /// read them: decoded as text and encoded again, `"\uDBFF"` would become `"\uFFFD"` in both versions.
    #[test]
    fn a_string_constant_that_is_not_well_formed_keeps_its_bytes() {
        use crate::classfile::writer::ClassWriter;
        use crate::classfile::{BootstrapArg, ClassFile, Constant};
        let mut w = ClassWriter::new("a/B");
        w.pool.string_units(&[0xDBFF]);
        w.pool.string("a/B");
        let own: BTreeSet<String> = ["a/B".to_string()].into_iter().collect();
        let copied = ClassFile::parse(&class_file(&w.to_bytes(), &own, "before").unwrap()).unwrap();
        assert_eq!(copied.name, "before/a/B");
        let strings: Vec<BootstrapArg> = (1..copied.pool.len() as u16)
            .filter(|&i| matches!(copied.pool.get(i), Ok(Constant::String { .. })))
            .map(|i| copied.pool.loadable(i).unwrap())
            .collect();
        assert_eq!(strings, [BootstrapArg::Units(vec![0xDBFF]), BootstrapArg::Str("before/a/B".into())]);
    }

    #[test]
    fn renames_names_and_descriptors() {
        let own: BTreeSet<String> = ["a/B".to_string()].into_iter().collect();
        assert_eq!(rename("La/B;", &own, "before"), "Lbefore/a/B;");
        assert_eq!(rename("(JLa/B<La/C;>;)V", &own, "before"), "(JLbefore/a/B<La/C;>;)V");
        assert_eq!(rename("a/B", &own, "before"), "before/a/B");
        assert_eq!(rename("a/BC", &own, "before"), "a/BC");
        assert_eq!(rename("hello", &own, "before"), "hello");
    }
}
