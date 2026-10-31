//! API contracts: the public surface of a module (its public and protected types and members, with their exact
//! signatures), derived from the compiled classes and checked in. The same lockfile-and-diff workflow as the other
//! contracts, for compatibility: a pull request that removes a public method, changes a parameter type or makes a
//! class final changes this file, and the diff is the API change a reviewer approves.

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use serde::Serialize;

use crate::classfile::{flags, ClassFile, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::Error;

pub const FILE_NAME: &str = "api.contract";

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TypeSurface {
    /// `public final class extends a.B implements c.D, e.F`.
    pub declaration: String,
    /// Member lines, sorted: `public static long totalCents(long, int)`.
    pub members: BTreeSet<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize)]
pub struct Surface {
    /// By binary name with dots (`pkg.Outer$Inner`).
    pub types: BTreeMap<String, TypeSurface>,
}

fn modifiers(access: u16, class_level: bool) -> String {
    let mut out = Vec::new();
    if access & flags::PUBLIC != 0 {
        out.push("public");
    }
    if access & flags::PROTECTED != 0 {
        out.push("protected");
    }
    if access & flags::STATIC != 0 {
        out.push("static");
    }
    if access & flags::ABSTRACT != 0 && !class_level {
        out.push("abstract");
    }
    if access & flags::FINAL != 0 {
        out.push("final");
    }
    if class_level && access & flags::ABSTRACT != 0 && access & flags::INTERFACE == 0 {
        out.push("abstract");
    }
    out.join(" ")
}

fn kind(class: &ClassFile) -> &'static str {
    if class.access & flags::ANNOTATION != 0 {
        "@interface"
    } else if class.is_interface() {
        "interface"
    } else if class.is_enum() {
        "enum"
    } else if class.is_record() {
        "record"
    } else {
        "class"
    }
}

fn declaration(class: &ClassFile) -> String {
    let mut s = modifiers(class.access & !flags::SUPER, true);
    if class.is_sealed() {
        s.push_str(" sealed");
    }
    s.push(' ');
    s.push_str(kind(class));
    if let Some(sup) = &class.super_class {
        if sup != "java/lang/Object" && !class.is_interface() && !class.is_enum() && !class.is_record() {
            s.push_str(&format!(" extends {}", sup.replace('/', ".")));
        }
    }
    if !class.interfaces.is_empty() {
        let word = if class.is_interface() { "extends" } else { "implements" };
        s.push_str(&format!(" {word} {}", class.interfaces.iter().map(|i| i.replace('/', ".")).collect::<Vec<_>>().join(", ")));
    }
    if let Ok(permitted) = class.permitted_subclasses() {
        if !permitted.is_empty() {
            s.push_str(&format!(" permits {}", permitted.iter().map(|i| i.replace('/', ".")).collect::<Vec<_>>().join(", ")));
        }
    }
    s.trim().to_string()
}

/// The public surface of every application class on the class path.
pub fn analyse(cp: &ClassPath) -> Result<Surface, Error> {
    let mut surface = Surface::default();
    let classes = cp.application_classes()?;
    for (name, class) in &classes {
        if class.access & (flags::PUBLIC | flags::PROTECTED) == 0 {
            continue;
        }
        // A nested class is API only if every enclosing class is.
        let mut outer = class.outer_class();
        let mut exported = true;
        while let Some(o) = outer {
            match classes.get(&o) {
                Some(oc) if oc.access & (flags::PUBLIC | flags::PROTECTED) != 0 => outer = oc.outer_class(),
                _ => {
                    exported = false;
                    break;
                }
            }
        }
        if !exported {
            continue;
        }
        let mut members = BTreeSet::new();
        for field in &class.fields {
            if field.access & (flags::PUBLIC | flags::PROTECTED) == 0 || field.access & flags::SYNTHETIC != 0 {
                continue;
            }
            let t = Type::parse(&field.descriptor).map(|t| t.java_name()).unwrap_or_else(|_| field.descriptor.clone());
            members.insert(format!("{} {}: {t}", modifiers(field.access, false), field.name).trim().to_string());
        }
        for method in &class.methods {
            if method.access & (flags::PUBLIC | flags::PROTECTED) == 0 || method.is_synthetic() || method.is_bridge() || method.is_class_initializer() {
                continue;
            }
            let Ok(d) = MethodDescriptor::parse(&method.descriptor) else { continue };
            let params = d.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", ");
            let line = if method.is_constructor() {
                format!("{} {}({params})", modifiers(method.access, false), crate::classfile::simple_name_of(name))
            } else {
                format!("{} {} {}({params})", modifiers(method.access, false), d.ret.java_name(), method.name)
            };
            members.insert(line.trim().to_string());
        }
        surface.types.insert(name.replace('/', "."), TypeSurface { declaration: declaration(class), members });
    }
    Ok(surface)
}

impl Surface {
    pub fn member_count(&self) -> usize {
        self.types.values().map(|t| t.members.len()).sum()
    }

    /// Comparable entries: `type: decl` and `type: member` lines.
    pub fn entries(&self) -> BTreeSet<String> {
        let mut out = BTreeSet::new();
        for (name, t) in &self.types {
            out.insert(format!("{name}: {}", t.declaration));
            for m in &t.members {
                out.insert(format!("{name}: {m}"));
            }
        }
        out
    }

    pub fn render(&self, module: &str) -> String {
        let mut lines = vec![
            "# API contract, generated by jvmcontract. Do not edit: regenerate it with `jvmcontract update`.".to_string(),
            "# It lists every public and protected type and member of this module, from the compiled classes.".to_string(),
            "# A change here is a change in what the module's users can call: review it like an API change.".to_string(),
            "kind: api".to_string(),
            format!("module: {module}, {} public types, {} members", self.types.len(), self.member_count()),
            String::new(),
        ];
        for (name, t) in &self.types {
            lines.push(format!("{name}: {}", t.declaration));
            for m in &t.members {
                lines.push(format!("  {m}"));
            }
            lines.push(String::new());
        }
        let mut text = lines.join("\n");
        text.push('\n');
        text
    }

    pub fn write(&self, file: &Path, module: &str) -> Result<(), Error> {
        if let Some(parent) = file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(file, self.render(module))?;
        Ok(())
    }
}

/// The entries of a checked-in API contract, comparable with [`Surface::entries`].
pub fn read(file: &Path) -> Result<BTreeSet<String>, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("cannot read {}: {e}", file.display())))?;
    parse(&text)
}

pub fn parse(text: &str) -> Result<BTreeSet<String>, Error> {
    let mut out = BTreeSet::new();
    let mut current: Option<String> = None;
    for line in text.lines() {
        if line.trim().is_empty() || line.starts_with('#') || line.starts_with("kind:") || line.starts_with("module:") {
            continue;
        }
        if let Some(member) = line.strip_prefix("  ") {
            let t = current.as_deref().ok_or_else(|| Error::new(format!("api contract: member before any type: {line:?}")))?;
            out.insert(format!("{t}: {member}"));
        } else {
            let (name, _) = line.split_once(": ").ok_or_else(|| Error::new(format!("api contract: bad type line {line:?}")))?;
            current = Some(name.to_string());
            out.insert(line.to_string());
        }
    }
    Ok(out)
}

pub fn diff(contract: &BTreeSet<String>, actual: &BTreeSet<String>) -> Vec<String> {
    let mut lines: Vec<String> = actual.difference(contract).map(|e| format!("  added {e}")).collect();
    lines.extend(contract.difference(actual).map(|e| format!("  removed {e}")));
    lines
}
