//! A readable dump of a class file, like a small `javap`.

use super::{flags, ClassFile, Insn, Result};

fn flag_names(access: u16, class: bool) -> String {
    let mut out = Vec::new();
    let table: &[(u16, &str)] = if class {
        &[(flags::PUBLIC, "public"), (flags::FINAL, "final"), (flags::INTERFACE, "interface"), (flags::ABSTRACT, "abstract"), (flags::SYNTHETIC, "synthetic"), (flags::ANNOTATION, "annotation"), (flags::ENUM, "enum")]
    } else {
        &[(flags::PUBLIC, "public"), (flags::PRIVATE, "private"), (flags::PROTECTED, "protected"), (flags::STATIC, "static"), (flags::FINAL, "final"), (flags::SYNCHRONIZED, "synchronized"), (flags::NATIVE, "native"), (flags::ABSTRACT, "abstract"), (flags::SYNTHETIC, "synthetic"), (flags::BRIDGE, "bridge"), (flags::VARARGS, "varargs")]
    };
    for (bit, name) in table {
        if access & bit != 0 {
            out.push(*name);
        }
    }
    out.join(" ")
}

/// Describes a class; with `code`, disassembles each method.
pub fn describe(class: &ClassFile, code: bool) -> Result<String> {
    let mut s = String::new();
    s.push_str(&format!("class {} (version {}.{}, {} constant pool entries)\n", class.name, class.major, class.minor, class.pool.len()));
    s.push_str(&format!("  flags: {}\n", flag_names(class.access, true)));
    if let Some(sup) = &class.super_class {
        s.push_str(&format!("  extends: {sup}\n"));
    }
    if !class.interfaces.is_empty() {
        s.push_str(&format!("  implements: {}\n", class.interfaces.join(", ")));
    }
    let permitted = class.permitted_subclasses()?;
    if !permitted.is_empty() {
        s.push_str(&format!("  permits: {}\n", permitted.join(", ")));
    }
    let components = class.record_components()?;
    if !components.is_empty() {
        s.push_str(&format!("  record components: {}\n", components.iter().map(|c| format!("{} {}", c.descriptor, c.name)).collect::<Vec<_>>().join(", ")));
    }
    s.push_str(&format!("  attributes: {}\n", class.attributes.iter().map(|a| a.name.as_str()).collect::<Vec<_>>().join(", ")));
    for field in &class.fields {
        s.push_str(&format!("  field {} {} {}\n", flag_names(field.access, false), field.descriptor, field.name));
    }
    for method in &class.methods {
        s.push_str(&format!("  method {} {}{}", flag_names(method.access, false), method.name, method.descriptor));
        if let Some(c) = &method.code {
            s.push_str(&format!(" (stack {}, locals {}, {} bytes, {} handlers)", c.max_stack, c.max_locals, c.bytes.len(), c.exception_table.len()));
        }
        s.push('\n');
        if code {
            if let Some(c) = &method.code {
                for (pc, insn) in c.instructions()? {
                    s.push_str(&format!("    {pc:5}: {}\n", describe_insn(class, &insn)));
                }
                for h in &c.exception_table {
                    s.push_str(&format!("    try [{}, {}) catch {} -> {}\n", h.start_pc, h.end_pc, h.catch_type.as_deref().unwrap_or("any"), h.handler_pc));
                }
            }
        }
    }
    Ok(s)
}

fn describe_insn(class: &ClassFile, insn: &Insn) -> String {
    let member = |i: u16| class.pool.member(i).map(|m| format!("{}.{}{}", m.owner, m.name, m.descriptor)).unwrap_or_else(|_| format!("#{i}"));
    let name = |i: u16| class.pool.class_name(i).map(str::to_string).unwrap_or_else(|_| format!("#{i}"));
    match insn {
        Insn::Ldc(i) => format!("ldc {:?}", class.pool.loadable(*i).map(|a| format!("{a:?}")).unwrap_or_else(|_| format!("#{i}"))),
        Insn::GetStatic(i) => format!("getstatic {}", member(*i)),
        Insn::PutStatic(i) => format!("putstatic {}", member(*i)),
        Insn::GetField(i) => format!("getfield {}", member(*i)),
        Insn::PutField(i) => format!("putfield {}", member(*i)),
        Insn::InvokeVirtual(i) => format!("invokevirtual {}", member(*i)),
        Insn::InvokeSpecial(i) => format!("invokespecial {}", member(*i)),
        Insn::InvokeStatic(i) => format!("invokestatic {}", member(*i)),
        Insn::InvokeInterface(i) => format!("invokeinterface {}", member(*i)),
        Insn::InvokeDynamic(i) => match class.pool.invoke_dynamic(*i) {
            Ok((b, n, d)) => format!("invokedynamic #{b} {n}{d}"),
            Err(_) => format!("invokedynamic #{i}"),
        },
        Insn::New(i) => format!("new {}", name(*i)),
        Insn::ANewArray(i) => format!("anewarray {}", name(*i)),
        Insn::CheckCast(i) => format!("checkcast {}", name(*i)),
        Insn::InstanceOf(i) => format!("instanceof {}", name(*i)),
        Insn::MultiANewArray(i, d) => format!("multianewarray {} dims {d}", name(*i)),
        other => format!("{other:?}").to_lowercase(),
    }
}
