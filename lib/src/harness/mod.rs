//! The statement of a regression proof, as a class file JBMC can check: a harness that calls the old and the new
//! version of a method on the same symbolic arguments, catches what each throws, and asserts that the results and
//! the exception types agree. With a scope expression (`--unchanged-unless`), the harness returns early on the
//! inputs the developer meant to change, so the proof covers everything else.
//!
//! The harness is written as bytecode directly, with no Java compiler in the loop: the statement is generated,
//! not transcribed, and the tool needs only JBMC. A Java rendering of the same statement is produced alongside it
//! for readers.
//!
//! The second kind of harness states a *property* of one version ([`generate_property`]): on every input that
//! satisfies an assumption, the method returns without throwing and its result satisfies an assertion, which may
//! call the method again to state a law.

pub mod expr;

use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::{flags, Cond, Kind, Type};
use crate::Error;

pub use expr::{Callee, Expr, Param};

/// The harness class name (default package), and its method.
pub const CLASS: &str = "EquivalenceHarness";
pub const METHOD: &str = "check";
/// The class of a property harness.
pub const PROPERTY_CLASS: &str = "PropertyHarness";
/// The name of the method's result in a property.
pub const RESULT: &str = "result";

/// The exceptions the harness tells apart, most specific first. Anything else is a RuntimeException or an Error.
pub const EXCEPTIONS: &[&str] = &[
    "java/lang/NumberFormatException",
    "java/lang/ArithmeticException",
    "java/lang/NullPointerException",
    "java/lang/ArrayIndexOutOfBoundsException",
    "java/lang/StringIndexOutOfBoundsException",
    "java/lang/IndexOutOfBoundsException",
    "java/lang/NegativeArraySizeException",
    "java/lang/ClassCastException",
    "java/lang/IllegalStateException",
    "java/lang/IllegalArgumentException",
    "java/lang/UnsupportedOperationException",
    "java/util/NoSuchElementException",
    "java/util/ConcurrentModificationException",
    "java/lang/RuntimeException",
    "java/lang/Error",
];

/// The generated harness.
#[derive(Debug, Clone)]
pub struct Harness {
    /// The class file bytes of `EquivalenceHarness`.
    pub bytes: Vec<u8>,
    /// The same statement as Java source, for readers; it is not compiled.
    pub source: String,
    /// The parsed scope expression, if any, for checking replayed counterexamples.
    pub scope: Option<Expr>,
    pub params: Vec<Param>,
}

/// Lays out the method's parameters in local-variable slots, as the static harness method receives them.
pub fn params(names: &[String], types: &[Type]) -> Vec<Param> {
    let mut slot = 0;
    names
        .iter()
        .zip(types)
        .map(|(name, ty)| {
            let p = Param { name: name.clone(), ty: ty.clone(), slot };
            slot += ty.slots();
            p
        })
        .collect()
}

fn kind_of(t: &Type) -> Kind {
    match t {
        Type::Long => Kind::Long,
        Type::Float => Kind::Float,
        Type::Double => Kind::Double,
        Type::Object(_) | Type::Array(_) => Kind::Ref,
        _ => Kind::Int,
    }
}

/// Generates the harness for `class_internal.method(params) -> ret`, comparing it with `before/class_internal`.
pub fn generate(class_internal: &str, method: &str, params: &[Param], ret: &Type, unchanged_unless: Option<&str>) -> Result<Harness, Error> {
    let scope = match unchanged_unless {
        Some(src) => Some(expr::parse(src, params)?),
        None => None,
    };
    let descriptor = format!("({}){}", params.iter().map(|p| p.ty.descriptor()).collect::<String>(), ret.descriptor());
    let check_descriptor = format!("({})V", params.iter().map(|p| p.ty.descriptor()).collect::<String>());
    let arg_slots: u16 = params.iter().map(|p| p.ty.slots()).sum();

    let mut writer = ClassWriter::new(CLASS);
    writer.source_file = Some(format!("{CLASS}.java"));
    writer.default_constructor();
    let mut code = CodeBuilder::new();
    code.max_locals = arg_slots;
    code.max_stack = arg_slots.max(4) + 2;

    // The scope: return early on the inputs the developer meant to change.
    if let Some(scope) = &scope {
        let proceed = code.label();
        expr::emit(scope, &mut code, &mut writer.pool);
        code.if_zero(Cond::Eq, proceed);
        code.return_(None);
        code.bind(proceed);
    }

    // Locals after the parameters: a, ea, b, eb.
    let is_void = *ret == Type::Void;
    let ret_kind = kind_of(ret);
    let a = arg_slots;
    let ea = a + if is_void { 0 } else { ret.slots() };
    let b = ea + 1;
    let eb = b + if is_void { 0 } else { ret.slots() };
    let before_owner = format!("before/{class_internal}");
    for (owner, value_slot, flag_slot) in [(before_owner.as_str(), a, ea), (class_internal, b, eb)] {
        if !is_void {
            match ret_kind {
                Kind::Int => code.iconst(0),
                Kind::Long => code.op(0x09),
                Kind::Float => code.op(0x0b),
                Kind::Double => code.op(0x0e),
                Kind::Ref => code.op(0x01),
            }
            code.store(ret_kind, value_slot);
        }
        code.iconst(0);
        code.store(Kind::Int, flag_slot);
        let try_start = code.label();
        let try_end = code.label();
        let join = code.label();
        code.bind(try_start);
        for p in params {
            code.load(kind_of(&p.ty), p.slot);
        }
        let target = writer.pool.method_ref(owner, method, &descriptor);
        code.op_u16(0xb8, target); // invokestatic
        if is_void {
            // nothing to store
        } else {
            code.store(ret_kind, value_slot);
        }
        code.bind(try_end);
        code.goto(join);
        for (i, exception) in EXCEPTIONS.iter().enumerate() {
            let handler = code.label();
            code.bind(handler);
            code.op(0x57); // pop the exception
            code.iconst(i as i32 + 1);
            code.store(Kind::Int, flag_slot);
            code.goto(join);
            let catch_type = writer.pool.class(exception);
            code.handler(try_start, try_end, handler, Some(catch_type));
        }
        code.bind(join);
    }

    // The assertion: ea == eb && (ea != 0 || a == b).
    let fail = code.label();
    let ok = code.label();
    code.load(Kind::Int, ea);
    code.load(Kind::Int, eb);
    code.if_icmp(Cond::Ne, fail);
    if !is_void {
        code.load(Kind::Int, ea);
        code.if_zero(Cond::Ne, ok);
        code.load(ret_kind, a);
        code.load(ret_kind, b);
        match ret_kind {
            Kind::Int => code.if_icmp(Cond::Eq, ok),
            Kind::Long => {
                code.op(0x94); // lcmp
                code.if_zero(Cond::Eq, ok);
            }
            Kind::Float => {
                code.op(0x95); // fcmpl
                code.if_zero(Cond::Eq, ok);
            }
            Kind::Double => {
                code.op(0x97); // dcmpl
                code.if_zero(Cond::Eq, ok);
            }
            Kind::Ref => {
                let equals = writer.pool.method_ref("java/util/Objects", "equals", "(Ljava/lang/Object;Ljava/lang/Object;)Z");
                code.op_u16(0xb8, equals);
                code.if_zero(Cond::Ne, ok);
            }
        }
    } else {
        code.goto(ok);
    }
    code.bind(fail);
    let assertion_error = writer.pool.class("java/lang/AssertionError");
    let init = writer.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
    code.op_u16(0xbb, assertion_error); // new
    code.op(0x59); // dup
    code.op_u16(0xb7, init); // invokespecial
    code.op(0xbf); // athrow
    code.bind(ok);
    code.return_(None);
    code.max_locals = code.max_locals.max(eb + 1);

    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: METHOD.into(), descriptor: check_descriptor, code: Some(code) });
    let source = source(class_internal, method, params, ret, unchanged_unless);
    Ok(Harness { bytes: writer.to_bytes(), source, scope, params: params.to_vec() })
}

/// The statement as Java source, for readers.
pub fn source(class_internal: &str, method: &str, params: &[Param], ret: &Type, unchanged_unless: Option<&str>) -> String {
    let class = class_internal.replace('/', ".");
    let param_list = params.iter().map(|p| format!("{} {}", p.ty.java_name(), p.name)).collect::<Vec<_>>().join(", ");
    let args = params.iter().map(|p| p.name.clone()).collect::<Vec<_>>().join(", ");
    let is_void = *ret == Type::Void;
    let type_name = if ret.is_primitive() { ret.java_name() } else { "Object".to_string() };
    let zero = match ret {
        Type::Boolean => "false",
        t if t.is_primitive() => "0",
        _ => "null",
    };
    let mut s = String::new();
    s.push_str("/** Generated by jvmcontract: asserts that two versions of a method agree. The class file JBMC checks is generated directly; this is the same statement, for readers. */\n");
    s.push_str(&format!("public final class {CLASS} {{\n"));
    s.push_str(&format!("    public static void {METHOD}({param_list}) {{\n"));
    if let Some(scope) = unchanged_unless {
        s.push_str(&format!("        if ({scope}) {{ return; }} // the inputs the developer meant to change\n"));
    }
    for (side, owner) in [("before", format!("before.{class}")), ("after", class.clone())] {
        let var = if side == "before" { "a" } else { "b" };
        if !is_void {
            s.push_str(&format!("        {type_name} {var} = {zero};\n"));
        }
        s.push_str(&format!("        int e{var} = 0;\n"));
        s.push_str(&format!("        try {{ {}{owner}.{method}({args}); }}", if is_void { String::new() } else { format!("{var} = ") }));
        for (i, exception) in EXCEPTIONS.iter().enumerate() {
            s.push_str(&format!(" catch ({} t) {{ e{var} = {}; }}", exception.replace('/', "."), i + 1));
        }
        s.push('\n');
    }
    s.push_str("        assert ea == eb");
    if !is_void {
        s.push_str(&format!(" && (ea != 0 || {})", if ret.is_primitive() { "a == b" } else { "java.util.Objects.equals(a, b)" }));
    }
    s.push_str(";\n    }\n}\n");
    s
}

/// The generated property harness.
#[derive(Debug, Clone)]
pub struct PropertyHarness {
    /// The class file bytes of `PropertyHarness`.
    pub bytes: Vec<u8>,
    /// The same statement as Java source, for readers; it is not compiled.
    pub source: String,
    pub assume: Option<Expr>,
    pub assertion: Expr,
    /// The assertion as text: as given, or `result` for a boolean method with no assertion given.
    pub assertion_text: String,
    pub params: Vec<Param>,
}

/// Generates the harness of a property of `class_internal.method(params) -> ret`: on every input where `assume`
/// holds (every input, when `None`), the method returns without throwing and `assertion` holds. The assertion
/// may name the parameters, `result`, and the method itself; when it is `None`, the method must return `boolean`
/// and the property is that it returns `true`.
pub fn generate_property(class_internal: &str, method: &str, params: &[Param], ret: &Type, assume: Option<&str>, assertion: Option<&str>) -> Result<PropertyHarness, Error> {
    let descriptor = format!("({}){}", params.iter().map(|p| p.ty.descriptor()).collect::<String>(), ret.descriptor());
    let check_descriptor = format!("({})V", params.iter().map(|p| p.ty.descriptor()).collect::<String>());
    let arg_slots: u16 = params.iter().map(|p| p.ty.slots()).sum();
    let is_void = *ret == Type::Void;
    let callee = Callee::of(class_internal, method, &descriptor, &params.iter().map(|p| p.ty.clone()).collect::<Vec<_>>(), ret);

    // The names the assertion sees: the parameters, then the result.
    let mut names = params.to_vec();
    if !is_void {
        names.push(Param { name: RESULT.into(), ty: ret.clone(), slot: arg_slots });
    }
    let assertion_text = match assertion {
        Some(a) => a.to_string(),
        None if *ret == Type::Boolean => RESULT.to_string(),
        None => return Err(Error::new(format!("the method returns {}, so the property needs an assertion (--assert) over the parameters and `result`", ret.java_name()))),
    };
    let assume_expr = match assume {
        Some(src) => Some(expr::parse_with(src, params, callee.as_ref()).map_err(|e| Error::new(format!("in the assumption: {e}")))?),
        None => None,
    };
    let assertion_expr = expr::parse_with(&assertion_text, &names, callee.as_ref()).map_err(|e| Error::new(format!("in the assertion: {e}")))?;

    let mut writer = ClassWriter::new(PROPERTY_CLASS);
    writer.source_file = Some(format!("{PROPERTY_CLASS}.java"));
    writer.default_constructor();
    let mut code = CodeBuilder::new();
    code.max_locals = arg_slots;
    code.max_stack = 16 + 4 * arg_slots;

    // The assumption: return on the inputs the property is not about.
    if let Some(assume) = &assume_expr {
        let proceed = code.label();
        expr::emit(assume, &mut code, &mut writer.pool);
        code.if_zero(Cond::Ne, proceed);
        code.return_(None);
        code.bind(proceed);
    }

    // Locals after the parameters: result, e.
    let ret_kind = kind_of(ret);
    let result = arg_slots;
    let e = result + if is_void { 0 } else { ret.slots() };
    if !is_void {
        match ret_kind {
            Kind::Int => code.iconst(0),
            Kind::Long => code.op(0x09),
            Kind::Float => code.op(0x0b),
            Kind::Double => code.op(0x0e),
            Kind::Ref => code.op(0x01),
        }
        code.store(ret_kind, result);
    }
    code.iconst(0);
    code.store(Kind::Int, e);
    let try_start = code.label();
    let try_end = code.label();
    let join = code.label();
    code.bind(try_start);
    for p in params {
        code.load(kind_of(&p.ty), p.slot);
    }
    let target = writer.pool.method_ref(class_internal, method, &descriptor);
    code.op_u16(0xb8, target); // invokestatic
    if !is_void {
        code.store(ret_kind, result);
    }
    code.bind(try_end);
    code.goto(join);
    for (i, exception) in EXCEPTIONS.iter().enumerate() {
        let handler = code.label();
        code.bind(handler);
        code.op(0x57); // pop the exception
        code.iconst(i as i32 + 1);
        code.store(Kind::Int, e);
        code.goto(join);
        let catch_type = writer.pool.class(exception);
        code.handler(try_start, try_end, handler, Some(catch_type));
    }
    code.bind(join);

    // The assertion: e == 0 && (assertion).
    let fail = code.label();
    let ok = code.label();
    code.load(Kind::Int, e);
    code.if_zero(Cond::Ne, fail);
    expr::emit(&assertion_expr, &mut code, &mut writer.pool);
    code.if_zero(Cond::Ne, ok);
    code.bind(fail);
    let assertion_error = writer.pool.class("java/lang/AssertionError");
    let init = writer.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
    code.op_u16(0xbb, assertion_error); // new
    code.op(0x59); // dup
    code.op_u16(0xb7, init); // invokespecial
    code.op(0xbf); // athrow
    code.bind(ok);
    code.return_(None);
    code.max_locals = code.max_locals.max(e + 1);

    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: METHOD.into(), descriptor: check_descriptor, code: Some(code) });
    let source = property_source(class_internal, method, params, ret, assume, &assertion_text);
    Ok(PropertyHarness { bytes: writer.to_bytes(), source, assume: assume_expr, assertion: assertion_expr, assertion_text, params: params.to_vec() })
}

/// The property as Java source, for readers.
pub fn property_source(class_internal: &str, method: &str, params: &[Param], ret: &Type, assume: Option<&str>, assertion: &str) -> String {
    let class = class_internal.replace('/', ".");
    let param_list = params.iter().map(|p| format!("{} {}", p.ty.java_name(), p.name)).collect::<Vec<_>>().join(", ");
    let args = params.iter().map(|p| p.name.clone()).collect::<Vec<_>>().join(", ");
    let is_void = *ret == Type::Void;
    let type_name = if ret.is_primitive() { ret.java_name() } else { "Object".to_string() };
    let zero = match ret {
        Type::Boolean => "false",
        t if t.is_primitive() => "0",
        _ => "null",
    };
    let qualify = |text: &str| qualify_calls(text, method, &class);
    let mut s = String::new();
    s.push_str("/** Generated by jvmcontract: asserts a property of a method on every input. The class file JBMC checks is generated directly; this is the same statement, for readers. */\n");
    s.push_str(&format!("public final class {PROPERTY_CLASS} {{\n"));
    s.push_str(&format!("    public static void {METHOD}({param_list}) {{\n"));
    if let Some(assume) = assume {
        s.push_str(&format!("        if (!({})) {{ return; }} // the inputs the property is about\n", qualify(assume)));
    }
    if !is_void {
        s.push_str(&format!("        {type_name} {RESULT} = {zero};\n"));
    }
    s.push_str("        int e = 0;\n");
    s.push_str(&format!("        try {{ {}{class}.{method}({args}); }}", if is_void { String::new() } else { format!("{RESULT} = ") }));
    for (i, exception) in EXCEPTIONS.iter().enumerate() {
        s.push_str(&format!(" catch ({} t) {{ e = {}; }}", exception.replace('/', "."), i + 1));
    }
    s.push('\n');
    s.push_str(&format!("        assert e == 0 && ({}); // no exception, and the property\n", qualify(assertion)));
    s.push_str("    }\n}\n");
    s
}

/// `merge(a, b)` becomes `net.example.Clock.merge(a, b)` in the Java rendering.
fn qualify_calls(text: &str, method: &str, class: &str) -> String {
    let bytes = text.as_bytes();
    let mut out = String::new();
    let mut i = 0;
    while i < text.len() {
        let rest = &text[i..];
        let starts_identifier = i == 0 || !(bytes[i - 1].is_ascii_alphanumeric() || bytes[i - 1] == b'_' || bytes[i - 1] == b'$' || bytes[i - 1] == b'.');
        if starts_identifier && rest.starts_with(method) && rest[method.len()..].trim_start().starts_with('(') {
            out.push_str(class);
            out.push('.');
            out.push_str(method);
            i += method.len();
            continue;
        }
        let c = rest.chars().next().expect("in range");
        out.push(c);
        i += c.len_utf8();
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::ClassFile;

    #[test]
    fn generates_a_well_formed_property_harness() {
        let params = params(&["now".into(), "last".into(), "message".into()], &[Type::Long, Type::Long, Type::Long]);
        let harness = generate_property("net/example/Clock", "receive", &params, &Type::Long, Some("now >= 0"), Some("result > last && result == receive(now, message, last)")).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        assert_eq!(class.name, PROPERTY_CLASS);
        let check = class.method(METHOD, "(JJJ)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        assert_eq!(code.exception_table.len(), EXCEPTIONS.len());
        let insns = code.instructions().unwrap();
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, crate::classfile::Insn::InvokeStatic(_))).count(), 2, "the call under test and the call in the law");
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        assert!(harness.source.contains("if (!(now >= 0)) { return; }"), "{}", harness.source);
        assert!(harness.source.contains("assert e == 0 && (result > last && result == net.example.Clock.receive(now, message, last));"), "{}", harness.source);

        let boolean = generate_property("net/example/Laws", "holds", &params, &Type::Boolean, None, None).unwrap();
        assert_eq!(boolean.assertion_text, "result");
        assert!(generate_property("net/example/Clock", "receive", &params, &Type::Long, None, None).is_err(), "a long result needs an assertion");
        assert!(generate_property("net/example/Clock", "receive", &params, &Type::Long, Some("result > 0"), Some("true")).is_err(), "no result in the assumption");
    }

    #[test]
    fn generates_a_well_formed_harness() {
        let params = params(&["priceCents".into(), "seats".into()], &[Type::Long, Type::Int]);
        let harness = generate("net/example/Pricing", "total", &params, &Type::Long, Some("seats >= 8")).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        assert_eq!(class.name, CLASS);
        let check = class.method(METHOD, "(JI)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        assert_eq!(code.exception_table.len(), 2 * EXCEPTIONS.len());
        let insns = code.instructions().unwrap();
        assert!(insns.iter().any(|(_, i)| matches!(i, crate::classfile::Insn::InvokeStatic(_))));
        assert!(insns.iter().any(|(_, i)| matches!(i, crate::classfile::Insn::AThrow)));
        assert!(harness.source.contains("if (seats >= 8) { return; }"), "{}", harness.source);
        assert!(harness.source.contains("a = before.net.example.Pricing.total(priceCents, seats);"));
        assert!(harness.source.contains("assert ea == eb && (ea != 0 || a == b);"));
        // Every branch target is an instruction boundary.
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
    }
}
