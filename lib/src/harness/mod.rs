//! The statement of a regression proof, as a class file JBMC can check: a harness that calls the old and the new
//! version of a method on the same symbolic arguments, catches what each throws, and asserts that the results and
//! the exception types agree. An array argument is copied first, so that each version writes into its own, and
//! what the two leave is compared element by element, as an array result is. With a scope expression
//! (`--unchanged-unless`), the harness returns early on the inputs the developer meant to change, so the proof
//! covers everything else.
//!
//! The harness is written as bytecode directly, with no Java compiler in the loop: the statement is generated,
//! not transcribed, and the tool needs only JBMC. A Java rendering of the same statement is produced alongside it
//! for readers.
//!
//! The second kind of harness states a *property* of one version ([`generate_property`]): on every input that
//! satisfies an assumption, the method returns without throwing and its result satisfies an assertion, which may
//! call the method again to state a law. Array parameters are symbolic arrays of bounded length, and a quantifier
//! in the assertion becomes a loop in the harness; `\old(a[i])` reads a copy of the array taken before the call.

pub mod expr;

use crate::classfile::writer::{ClassWriter, CodeBuilder, Label, MethodWriter};
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
/// Each array parameter is copied before the calls, exactly as long, so that the version before writes into the
/// copy and the version after into the array itself, and the two are compared element by element afterwards;
/// `max_array_length` bounds the copying and comparing loops. An array result is compared the same way.
pub fn generate(class_internal: &str, method: &str, params: &[Param], ret: &Type, unchanged_unless: Option<&str>, max_array_length: u32) -> Result<Harness, Error> {
    let descriptor = format!("({}){}", params.iter().map(|p| p.ty.descriptor()).collect::<String>(), ret.descriptor());
    let check_descriptor = format!("({})V", params.iter().map(|p| p.ty.descriptor()).collect::<String>());
    let arg_slots: u16 = params.iter().map(|p| p.ty.slots()).sum();

    // Locals after the parameters: a copy of each array parameter, then a, ea, b, eb, then the index of the
    // copying and comparing loops, which the scope's quantifiers reuse.
    let copies: Vec<(u16, u16, Type)> = params
        .iter()
        .filter_map(|p| match &p.ty {
            Type::Array(element) => Some((p.slot, (**element).clone())),
            _ => None,
        })
        .enumerate()
        .map(|(i, (slot, element))| (slot, arg_slots + i as u16, element))
        .collect();
    let is_void = *ret == Type::Void;
    let ret_kind = kind_of(ret);
    let a = arg_slots + copies.len() as u16;
    let ea = a + if is_void { 0 } else { ret.slots() };
    let b = ea + 1;
    let eb = b + if is_void { 0 } else { ret.slots() };
    let index = eb + 1;
    let scope = match unchanged_unless {
        Some(src) => Some(expr::parse_in(src, params, None, index)?),
        None => None,
    };
    let bound = i32::try_from(max_array_length).unwrap_or(i32::MAX);

    let mut writer = ClassWriter::new(CLASS);
    writer.source_file = Some(format!("{CLASS}.java"));
    writer.default_constructor();
    let mut code = CodeBuilder::new();
    code.max_locals = arg_slots;
    code.max_stack = 16 + 4 * arg_slots;

    // The scope: return early on the inputs the developer meant to change.
    if let Some(scope) = &scope {
        let proceed = code.label();
        expr::emit(scope, &mut code, &mut writer.pool);
        code.if_zero(Cond::Eq, proceed);
        code.return_(None);
        code.bind(proceed);
    }

    // The copies: as long as the array, filled by a loop of at most the bound's iterations.
    for (slot, copy, element) in &copies {
        code.load(Kind::Ref, *slot);
        code.op(0xbe); // arraylength
        code.op_u8(0xbc, newarray_code(element)); // newarray
        code.store(Kind::Ref, *copy);
        let loop_ = code.label();
        let done = code.label();
        code.iconst(0);
        code.store(Kind::Int, index);
        code.bind(loop_);
        code.load(Kind::Int, index);
        code.iconst(bound);
        code.if_icmp(Cond::Ge, done);
        code.load(Kind::Int, index);
        code.load(Kind::Ref, *slot);
        code.op(0xbe); // arraylength
        code.if_icmp(Cond::Ge, done);
        code.load(Kind::Ref, *copy);
        code.load(Kind::Int, index);
        code.load(Kind::Ref, *slot);
        code.load(Kind::Int, index);
        code.op(array_load(element));
        code.op(array_store(element));
        code.iinc(index, 1);
        code.goto(loop_);
        code.bind(done);
    }

    let before_owner = format!("before/{class_internal}");
    for (owner, value_slot, flag_slot, on_copies) in [(before_owner.as_str(), a, ea, true), (class_internal, b, eb, false)] {
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
            match copies.iter().find(|(slot, _, _)| *slot == p.slot) {
                Some((_, copy, _)) if on_copies => code.load(Kind::Ref, *copy),
                _ => code.load(kind_of(&p.ty), p.slot),
            }
        }
        let target = writer.pool.method_ref(owner, method, &descriptor);
        code.op_u16(0xb8, target); // invokestatic
        if !is_void {
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

    // The assertion: ea == eb && (ea != 0 || a == b) && each array parameter is left as its copy was.
    let fail = code.label();
    let ok = code.label();
    code.load(Kind::Int, ea);
    code.load(Kind::Int, eb);
    code.if_icmp(Cond::Ne, fail);
    if !is_void {
        let arrays = code.label();
        code.load(Kind::Int, ea);
        code.if_zero(Cond::Ne, arrays);
        match ret {
            Type::Array(element) => {
                let compare = code.label();
                code.load(Kind::Ref, a);
                code.if_nonnull(compare);
                code.load(Kind::Ref, b);
                code.if_null(arrays);
                code.goto(fail);
                code.bind(compare);
                code.load(Kind::Ref, b);
                code.if_null(fail);
                code.load(Kind::Ref, a);
                code.op(0xbe); // arraylength
                code.load(Kind::Ref, b);
                code.op(0xbe); // arraylength
                code.if_icmp(Cond::Ne, fail);
                compare_arrays(&mut code, a, b, element, None, index, fail);
            }
            Type::Object(_) => {
                let equals = writer.pool.method_ref("java/util/Objects", "equals", "(Ljava/lang/Object;Ljava/lang/Object;)Z");
                code.load(Kind::Ref, a);
                code.load(Kind::Ref, b);
                code.op_u16(0xb8, equals);
                code.if_zero(Cond::Eq, fail);
            }
            _ => compare_values(&mut code, ret, fail, &|code, side| code.load(ret_kind, if side == 0 { a } else { b })),
        }
        code.bind(arrays);
    }
    for (slot, copy, element) in &copies {
        compare_arrays(&mut code, *slot, *copy, element, Some(bound), index, fail);
    }
    code.goto(ok);
    code.bind(fail);
    let assertion_error = writer.pool.class("java/lang/AssertionError");
    let init = writer.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
    code.op_u16(0xbb, assertion_error); // new
    code.op(0x59); // dup
    code.op_u16(0xb7, init); // invokespecial
    code.op(0xbf); // athrow
    code.bind(ok);
    code.return_(None);
    code.max_locals = code.max_locals.max(index + 1);

    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: METHOD.into(), descriptor: check_descriptor, code: Some(code) });
    let source = source(class_internal, method, params, ret, unchanged_unless);
    Ok(Harness { bytes: writer.to_bytes(), source, scope, params: params.to_vec() })
}

/// Emits a jump to `fail` unless the two values `push` loads (`push(code, 0)` the first, `push(code, 1)` the
/// second, of the primitive type `ty`) are equal, where two NaNs count as equal: the versions agree.
fn compare_values(code: &mut CodeBuilder, ty: &Type, fail: Label, push: &dyn Fn(&mut CodeBuilder, u8)) {
    push(code, 0);
    push(code, 1);
    match kind_of(ty) {
        Kind::Int => code.if_icmp(Cond::Ne, fail),
        Kind::Long => {
            code.op(0x94); // lcmp
            code.if_zero(Cond::Ne, fail);
        }
        Kind::Float | Kind::Double => {
            let cmp = if kind_of(ty) == Kind::Float { 0x95 } else { 0x97 }; // fcmpl, dcmpl
            let equal = code.label();
            code.op(cmp);
            code.if_zero(Cond::Eq, equal);
            push(code, 0);
            push(code, 0);
            code.op(cmp);
            code.if_zero(Cond::Eq, fail); // the first is a number, so they differ
            push(code, 1);
            push(code, 1);
            code.op(cmp);
            code.if_zero(Cond::Eq, fail); // the first is NaN and the second is not
            code.bind(equal);
        }
        Kind::Ref => unreachable!("compared by Objects.equals"),
    }
}

/// Emits a loop over the arrays in `x` and `y` (of `element`s, as long as each other) that jumps to `fail` at the
/// first index where they differ: up to `bound` indices when given, else up to the length of `x`.
fn compare_arrays(code: &mut CodeBuilder, x: u16, y: u16, element: &Type, bound: Option<i32>, index: u16, fail: Label) {
    let loop_ = code.label();
    let done = code.label();
    code.iconst(0);
    code.store(Kind::Int, index);
    code.bind(loop_);
    if let Some(bound) = bound {
        code.load(Kind::Int, index);
        code.iconst(bound);
        code.if_icmp(Cond::Ge, done);
    }
    code.load(Kind::Int, index);
    code.load(Kind::Ref, x);
    code.op(0xbe); // arraylength
    code.if_icmp(Cond::Ge, done);
    compare_values(code, element, fail, &|code, side| {
        code.load(Kind::Ref, if side == 0 { x } else { y });
        code.load(Kind::Int, index);
        code.op(array_load(element));
    });
    code.iinc(index, 1);
    code.goto(loop_);
    code.bind(done);
}

/// The statement as Java source, for readers.
pub fn source(class_internal: &str, method: &str, params: &[Param], ret: &Type, unchanged_unless: Option<&str>) -> String {
    let class = class_internal.replace('/', ".");
    let param_list = params.iter().map(|p| format!("{} {}", p.ty.java_name(), p.name)).collect::<Vec<_>>().join(", ");
    let is_array = |p: &Param| matches!(p.ty, Type::Array(_));
    let args = params.iter().map(|p| p.name.clone()).collect::<Vec<_>>().join(", ");
    let args_before = params.iter().map(|p| if is_array(p) { format!("{}_before", p.name) } else { p.name.clone() }).collect::<Vec<_>>().join(", ");
    let is_void = *ret == Type::Void;
    let type_name = if ret.is_primitive() || matches!(ret, Type::Array(_)) { ret.java_name() } else { "Object".to_string() };
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
    for p in params.iter().filter(|p| is_array(p)) {
        s.push_str(&format!("        {} {}_before = java.util.Arrays.copyOf({}, {}.length); // the version before writes into its own copy\n", p.ty.java_name(), p.name, p.name, p.name));
    }
    for (side, owner, args) in [("before", format!("before.{class}"), &args_before), ("after", class.clone(), &args)] {
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
        let equal = match ret {
            Type::Float | Type::Double => "a == b || (a != a && b != b)",
            Type::Array(_) => "java.util.Arrays.equals(a, b)",
            t if t.is_primitive() => "a == b",
            _ => "java.util.Objects.equals(a, b)",
        };
        s.push_str(&format!(" && (ea != 0 || {equal})"));
    }
    for p in params.iter().filter(|p| is_array(p)) {
        s.push_str(&format!(" && java.util.Arrays.equals({}, {}_before)", p.name, p.name));
    }
    s.push_str(";\n    }\n}\n");
    s
}

/// An exceptional behaviour clause of a property: the method throws `class` (an internal name, an instance of it
/// counts) exactly when `when`, a boolean expression over the parameters, holds; JML's `signals`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Signal {
    pub class: String,
    pub when: String,
}

impl Signal {
    /// `java.lang.ArithmeticException when divisor == 0`.
    pub fn parse(text: &str) -> Result<Signal, Error> {
        let (class, when) = text.trim().split_once(" when ").ok_or_else(|| Error::new(format!("a throws clause is `<exception class> when <condition>`, found {text:?}")))?;
        let class = class.trim();
        if class.is_empty() || when.trim().is_empty() || class.contains(char::is_whitespace) {
            return Err(Error::new(format!("a throws clause is `<exception class> when <condition>`, found {text:?}")));
        }
        Ok(Signal { class: class.replace('.', "/"), when: when.trim().to_string() })
    }

    pub fn java_name(&self) -> String {
        self.class.replace('/', ".")
    }

    /// `throws java.lang.ArithmeticException when divisor == 0`, the clause as the report prints it.
    pub fn render(&self) -> String {
        format!("throws {} when {}", self.java_name(), self.when)
    }
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
    /// The assertion as text: as given, `result` for a boolean method with no assertion given, or `true` for a
    /// method whose property is its throws clauses alone.
    pub assertion_text: String,
    /// The throws clauses, with their conditions parsed; the first whose condition holds is the one expected.
    pub signals: Vec<(Signal, Expr)>,
    pub params: Vec<Param>,
    /// By the slot of each array parameter the assertion reads under `\old`, the slot of the copy the harness
    /// takes before the call.
    pub old: Vec<(u16, u16)>,
}

/// Generates the harness of a property of `class_internal.method(params) -> ret`: on every input where `assume`
/// holds (every input, when `None`), the method returns without throwing and `assertion` holds; where the
/// condition of one of the `signals` holds instead, it throws that clause's exception. The assertion may name the
/// parameters, `result`, and the method itself; when it is `None`, the method must return `boolean` and the
/// property is that it returns `true`, or have throws clauses, and the property is that it returns at all.
/// `max_array_length` bounds the array parameters, and sizes the copies the harness takes for `\old`.
#[allow(clippy::too_many_arguments)] // the parts of a property, as the command line takes them
pub fn generate_property(class_internal: &str, method: &str, params: &[Param], ret: &Type, assume: Option<&str>, assertion: Option<&str>, signals: &[Signal], max_array_length: u32) -> Result<PropertyHarness, Error> {
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
        None if !signals.is_empty() => "true".to_string(),
        None => return Err(Error::new(format!("the method returns {}, so the property needs an assertion (--assert) over the parameters and `result`", ret.java_name()))),
    };
    // Locals after the parameters: result, e, expected, a copy of each array parameter for \old (taken only when
    // the assertion reads it); quantifiers take their variables after those.
    let ret_kind = kind_of(ret);
    let result = arg_slots;
    let e = result + if is_void { 0 } else { ret.slots() };
    let expected = e + 1;
    let copies: Vec<(u16, u16)> = params.iter().filter(|p| matches!(p.ty, Type::Array(_))).enumerate().map(|(i, p)| (p.slot, expected + 1 + i as u16)).collect();
    let first_free = expected + 1 + copies.len() as u16;
    let assume_expr = match assume {
        Some(src) => Some(expr::parse_in(src, params, callee.as_ref(), first_free).map_err(|e| Error::new(format!("in the assumption: {e}")))?),
        None => None,
    };
    let assertion_expr = expr::parse_after(&assertion_text, &names, callee.as_ref(), first_free, Some(&copies)).map_err(|e| Error::new(format!("in the assertion: {e}")))?;
    if assertion_expr.ty() != expr::Ty::Boolean {
        return Err(Error::new("in the assertion: the expression must be boolean"));
    }
    let old: Vec<(u16, u16)> = copies.iter().copied().filter(|(_, copy)| assertion_expr.mentions(*copy)).collect();
    let mut signal_exprs = Vec::new();
    for signal in signals {
        if signal.class.is_empty() || signal.class.contains(|c: char| c.is_whitespace() || c == ';' || c == '[') {
            return Err(Error::new(format!("in the throws clause: {:?} is not a class name", signal.java_name())));
        }
        let when = expr::parse_in(&signal.when, params, callee.as_ref(), first_free).map_err(|e| Error::new(format!("in the throws clause `{}`: {e}", signal.render())))?;
        signal_exprs.push((signal.clone(), when));
    }

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
    // Which throws clause applies: the first whose condition holds, numbered from 1; 0 for none.
    code.iconst(0);
    code.store(Kind::Int, expected);
    if !signal_exprs.is_empty() {
        let decided = code.label();
        for (i, (_, when)) in signal_exprs.iter().enumerate() {
            let next = code.label();
            expr::emit(when, &mut code, &mut writer.pool);
            code.if_zero(Cond::Eq, next);
            code.iconst(i as i32 + 1);
            code.store(Kind::Int, expected);
            code.goto(decided);
            code.bind(next);
        }
        code.bind(decided);
    }
    // The copies for \old: as long as the bound on the arrays (a copy of the array's own, symbolic, length costs
    // the solver far more), copied element by element in a loop of that many iterations; exactly as long as the
    // array only when the assertion passes the copy to a call, which would see the padding. The index is the
    // first quantifier slot, which is free until the assertion.
    for (slot, copy) in &old {
        let element = match &params.iter().find(|p| p.slot == *slot).expect("an array parameter").ty {
            Type::Array(element) => (**element).clone(),
            _ => unreachable!(),
        };
        let index = first_free;
        let loop_ = code.label();
        let skip = code.label();
        let done = code.label();
        let bound = i32::try_from(max_array_length).unwrap_or(i32::MAX);
        if assertion_expr.passes(*copy) {
            code.load(Kind::Ref, *slot);
            code.op(0xbe); // arraylength
        } else {
            code.iconst(bound);
        }
        code.op_u8(0xbc, newarray_code(&element)); // newarray
        code.store(Kind::Ref, *copy);
        code.iconst(0);
        code.store(Kind::Int, index);
        code.bind(loop_);
        code.load(Kind::Int, index);
        code.iconst(bound);
        code.if_icmp(Cond::Ge, done);
        code.load(Kind::Int, index);
        code.load(Kind::Ref, *slot);
        code.op(0xbe); // arraylength
        code.if_icmp(Cond::Ge, skip);
        code.load(Kind::Ref, *copy);
        code.load(Kind::Int, index);
        code.load(Kind::Ref, *slot);
        code.load(Kind::Int, index);
        code.op(array_load(&element));
        code.op(array_store(&element));
        code.bind(skip);
        code.iinc(index, 1);
        code.goto(loop_);
        code.bind(done);
    }
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
    // The declared exceptions are caught first, each as -(its number), so that a declared supertype of a listed
    // exception takes its subclasses.
    for (i, (signal, _)) in signal_exprs.iter().enumerate() {
        let handler = code.label();
        code.bind(handler);
        code.op(0x57); // pop the exception
        code.iconst(-(i as i32 + 1));
        code.store(Kind::Int, e);
        code.goto(join);
        let catch_type = writer.pool.class(&signal.class);
        code.handler(try_start, try_end, handler, Some(catch_type));
    }
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

    // The assertion: e == 0 && (assertion), or e == -expected when a throws clause applies. An exception while
    // evaluating the assertion (an index out of bounds, say) fails it.
    let fail = code.label();
    let ok = code.label();
    if !signal_exprs.is_empty() {
        let normal = code.label();
        code.load(Kind::Int, expected);
        code.if_zero(Cond::Eq, normal);
        code.load(Kind::Int, e);
        code.load(Kind::Int, expected);
        code.op(0x60); // iadd
        code.if_zero(Cond::Eq, ok);
        code.goto(fail);
        code.bind(normal);
    }
    code.load(Kind::Int, e);
    code.if_zero(Cond::Ne, fail);
    let assertion_start = code.label();
    let assertion_end = code.label();
    code.bind(assertion_start);
    expr::emit(&assertion_expr, &mut code, &mut writer.pool);
    code.bind(assertion_end);
    code.if_zero(Cond::Ne, ok);
    code.goto(fail);
    let assertion_threw = code.label();
    code.bind(assertion_threw);
    code.op(0x57); // pop the exception
    for exception in EXCEPTIONS {
        let catch_type = writer.pool.class(exception);
        code.handler(assertion_start, assertion_end, assertion_threw, Some(catch_type));
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
    code.max_locals = code.max_locals.max(first_free + 1);

    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: METHOD.into(), descriptor: check_descriptor, code: Some(code) });
    let source = property_source(class_internal, method, params, ret, assume, &assertion_text, signals);
    Ok(PropertyHarness { bytes: writer.to_bytes(), source, assume: assume_expr, assertion: assertion_expr, assertion_text, signals: signal_exprs, params: params.to_vec(), old })
}

/// The `newarray` type code of a primitive element type.
fn newarray_code(element: &Type) -> u8 {
    match element {
        Type::Boolean => 4,
        Type::Char => 5,
        Type::Float => 6,
        Type::Double => 7,
        Type::Byte => 8,
        Type::Short => 9,
        Type::Long => 11,
        _ => 10, // int
    }
}

fn array_load(element: &Type) -> u8 {
    match element {
        Type::Long => 0x2f,                 // laload
        Type::Byte | Type::Boolean => 0x33, // baload
        Type::Char => 0x34,                 // caload
        Type::Short => 0x35,                // saload
        _ => 0x2e,                          // iaload
    }
}

fn array_store(element: &Type) -> u8 {
    match element {
        Type::Long => 0x50,                 // lastore
        Type::Byte | Type::Boolean => 0x54, // bastore
        Type::Char => 0x55,                 // castore
        Type::Short => 0x56,                // sastore
        _ => 0x4f,                          // iastore
    }
}

/// The property as Java source, for readers.
pub fn property_source(class_internal: &str, method: &str, params: &[Param], ret: &Type, assume: Option<&str>, assertion: &str, signals: &[Signal]) -> String {
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
    if assertion.contains('\\') || assume.is_some_and(|a| a.contains('\\')) || signals.iter().any(|s| s.when.contains('\\')) {
        s.push_str("/* \\forall, \\exists, \\sum, \\num_of, \\max and \\min are JML's quantifiers; the class file evaluates each as a loop over its range. */\n");
    }
    if assertion.contains("\\old") {
        s.push_str("/* \\old(a) is the array a as it was before the call: the class file copies it first. */\n");
    }
    s.push_str(&format!("public final class {PROPERTY_CLASS} {{\n"));
    s.push_str(&format!("    public static void {METHOD}({param_list}) {{\n"));
    if let Some(assume) = assume {
        s.push_str(&format!("        if (!({})) {{ return; }} // the inputs the property is about\n", qualify(assume)));
    }
    if !is_void {
        s.push_str(&format!("        {type_name} {RESULT} = {zero};\n"));
    }
    s.push_str("        int e = 0;\n");
    if !signals.is_empty() {
        s.push_str("        int expected = 0; // the throws clause that applies: the first whose condition holds\n");
        for (i, signal) in signals.iter().enumerate() {
            s.push_str(&format!("        {}if ({}) {{ expected = {}; }} // {}\n", if i == 0 { "" } else { "else " }, qualify(&signal.when), i + 1, signal.java_name()));
        }
    }
    s.push_str(&format!("        try {{ {}{class}.{method}({args}); }}", if is_void { String::new() } else { format!("{RESULT} = ") }));
    for (i, signal) in signals.iter().enumerate() {
        s.push_str(&format!(" catch ({} t) {{ e = -{}; }}", signal.java_name(), i + 1));
    }
    for (i, exception) in EXCEPTIONS.iter().enumerate() {
        s.push_str(&format!(" catch ({} t) {{ e = {}; }}", exception.replace('/', "."), i + 1));
    }
    s.push('\n');
    if signals.is_empty() {
        s.push_str(&format!("        assert e == 0 && ({}); // no exception, and the property\n", qualify(assertion)));
    } else {
        s.push_str(&format!("        assert expected != 0 ? e == -expected : e == 0 && ({}); // the declared exception where its condition holds; elsewhere no exception, and the property\n", qualify(assertion)));
    }
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
        let harness = generate_property("net/example/Clock", "receive", &params, &Type::Long, Some("now >= 0"), Some("result > last && result == receive(now, message, last)"), &[], 8).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        assert_eq!(class.name, PROPERTY_CLASS);
        let check = class.method(METHOD, "(JJJ)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        assert_eq!(code.exception_table.len(), 2 * EXCEPTIONS.len(), "the call's handlers, and the assertion's");
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

        let boolean = generate_property("net/example/Laws", "holds", &params, &Type::Boolean, None, None, &[], 8).unwrap();
        assert_eq!(boolean.assertion_text, "result");
        assert!(generate_property("net/example/Clock", "receive", &params, &Type::Long, None, None, &[], 8).is_err(), "a long result needs an assertion");
        assert!(generate_property("net/example/Clock", "receive", &params, &Type::Long, Some("result > 0"), Some("true"), &[], 8).is_err(), "no result in the assumption");
    }

    #[test]
    fn generates_a_property_harness_with_throws_clauses() {
        let params = params(&["dividend".into(), "divisor".into()], &[Type::Int, Type::Int]);
        let signals = vec![Signal::parse("java.lang.ArithmeticException when divisor == 0").unwrap()];
        assert_eq!(signals[0], Signal { class: "java/lang/ArithmeticException".into(), when: "divisor == 0".into() });
        let harness = generate_property("net/example/Arithmetic", "idiv", &params, &Type::Int, None, Some("divisor != -1 || result == -dividend"), &signals, 8).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(II)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        assert_eq!(code.exception_table.len(), 2 * EXCEPTIONS.len() + 1, "the declared exception's handler comes first");
        assert_eq!(code.exception_table[0].catch_type.as_deref(), Some("java/lang/ArithmeticException"));
        let insns = code.instructions().unwrap();
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        assert!(harness.source.contains("if (divisor == 0) { expected = 1; } // java.lang.ArithmeticException"), "{}", harness.source);
        assert!(harness.source.contains("catch (java.lang.ArithmeticException t) { e = -1; }"), "{}", harness.source);
        assert!(harness.source.contains("assert expected != 0 ? e == -expected : e == 0 && (divisor != -1 || result == -dividend);"), "{}", harness.source);
        assert_eq!(harness.signals.len(), 1);

        // A void method's property can be its throws clauses alone.
        let void = generate_property("net/example/Table", "check", &params, &Type::Void, None, None, &signals, 8).unwrap();
        assert_eq!(void.assertion_text, "true");
        assert!(generate_property("net/example/Table", "check", &params, &Type::Void, None, None, &[], 8).is_err(), "a void method with no throws clause has no property");
        let bad = generate_property("net/example/Arithmetic", "idiv", &params, &Type::Int, None, Some("true"), &[Signal::parse("java.lang.ArithmeticException when result == 0").unwrap()], 8);
        assert!(bad.unwrap_err().to_string().contains("in the throws clause"), "no result before the call");
        assert!(Signal::parse("ArithmeticException").is_err());
    }

    #[test]
    fn generates_a_property_harness_with_old() {
        let params = params(&["a".into(), "n".into()], &[Type::Array(Box::new(Type::Byte)), Type::Int]);
        let harness = generate_property("net/example/InPlace", "zeroFrom", &params, &Type::Void, Some("0 <= n && n <= a.length"), Some("\\forall int i; 0 <= i && i < n; a[i] == \\old(a[i])"), &[], 8).unwrap();
        // Slots: a, n, e, expected, the copy of a; then the index of the copying loop, which the quantifier's
        // variable reuses, and the accumulator.
        assert_eq!(harness.old, vec![(0, 4)]);
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "([BI)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        assert_eq!(code.max_locals, 7);
        let insns = code.instructions().unwrap();
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        assert!(code.bytes.windows(3).any(|w| w == [0x10, 8, 0xbc]), "newarray as long as the bound");
        assert!(code.bytes.windows(2).any(|w| w == [0xbc, 8]), "newarray byte");
        assert!(code.bytes.contains(&0x54), "bastore");
        assert!(harness.source.contains("\\old(a) is the array a as it was before the call"), "{}", harness.source);

        let plain = generate_property("net/example/InPlace", "zeroFrom", &params, &Type::Void, None, Some("a.length >= n"), &[], 8).unwrap();
        assert!(plain.old.is_empty(), "no copy unless the assertion reads it");
        assert!(!plain.source.contains("\\old"));
        let err = generate_property("net/example/InPlace", "zeroFrom", &params, &Type::Void, Some("\\old(a.length) > 0"), Some("true"), &[], 8).unwrap_err();
        assert!(err.to_string().contains("in the assumption: \\old is only meaningful in the assertion"), "{err}");
        // A copy passed to a call is exactly as long as the array.
        let one = super::params(&["a".into()], &[Type::Array(Box::new(Type::Int))]);
        let passed = generate_property("net/example/InPlace", "sum", &one, &Type::Int, None, Some("sum(\\old(a)) == result"), &[], 8).unwrap();
        assert_eq!(passed.old, vec![(0, 4)]);
        let class = ClassFile::parse(&passed.bytes).unwrap();
        let code = class.method(METHOD, "([I)V").unwrap().code.as_ref().unwrap();
        assert!(code.bytes.windows(3).any(|w| w == [0xbe, 0xbc, 10]), "newarray int of the array's length");
    }

    #[test]
    fn generates_a_property_harness_over_arrays() {
        let params = params(&["matches".into(), "key".into()], &[Type::Array(Box::new(Type::Int)), Type::Int]);
        let harness = generate_property("net/example/Search", "find", &params, &Type::Int, Some("\\forall int i; 0 < i && i < matches.length; matches[i - 1] < matches[i]"), Some("result == -1 || matches[result] == key"), &[], 8).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "([II)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        // Slots: matches, key, result, e, then the quantifier's variable and accumulator.
        assert!(code.max_locals >= 6, "{}", code.max_locals);
        let insns = code.instructions().unwrap();
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        assert!(harness.source.contains("int[] matches, int key"), "{}", harness.source);
        assert!(harness.source.contains("JML"), "{}", harness.source);
    }

    #[test]
    fn generates_a_well_formed_harness() {
        let params = params(&["priceCents".into(), "seats".into()], &[Type::Long, Type::Int]);
        let harness = generate("net/example/Pricing", "total", &params, &Type::Long, Some("seats >= 8"), 8).unwrap();
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

    #[test]
    fn generates_an_equivalence_harness_over_arrays() {
        let params = params(&["chars".into(), "out".into()], &[Type::Array(Box::new(Type::Char)), Type::Array(Box::new(Type::Byte))]);
        let harness = generate("net/example/Utf8", "encodeInto", &params, &Type::Int, None, 6).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "([C[B)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        // Slots: chars, out, their copies, a, ea, b, eb, the loop index.
        assert_eq!(code.max_locals, 9);
        let insns = code.instructions().unwrap();
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        // Each copy is as long as its array (arraylength, newarray) and the loops stop at the bound.
        assert!(code.bytes.windows(3).any(|w| w == [0xbe, 0xbc, 5]), "newarray char of the array's length");
        assert!(code.bytes.windows(3).any(|w| w == [0xbe, 0xbc, 8]), "newarray byte of the array's length");
        assert_eq!(code.bytes.windows(2).filter(|w| *w == [0x10, 6]).count(), 6, "bipush 6 in two copying and two comparing loops, and in the sixth exception handler of each version");
        assert!(code.bytes.contains(&0x55) && code.bytes.contains(&0x54), "castore and bastore");
        assert!(harness.source.contains("byte[] out_before = java.util.Arrays.copyOf(out, out.length);"), "{}", harness.source);
        assert!(harness.source.contains("a = before.net.example.Utf8.encodeInto(chars_before, out_before);"), "{}", harness.source);
        assert!(harness.source.contains("assert ea == eb && (ea != 0 || a == b) && java.util.Arrays.equals(chars, chars_before) && java.util.Arrays.equals(out, out_before);"), "{}", harness.source);

        // An array result is compared element by element; a float result allows two NaNs.
        let one = super::params(&["a".into()], &[Type::Array(Box::new(Type::Int))]);
        let returning = generate("net/example/Copies", "prefix", &one, &Type::Array(Box::new(Type::Int)), Some("\\exists int i; 0 <= i && i < a.length; a[i] < 0"), 8).unwrap();
        assert!(returning.source.contains("(ea != 0 || java.util.Arrays.equals(a, b))"), "{}", returning.source);
        assert!(returning.source.contains("if (\\exists int i; 0 <= i && i < a.length; a[i] < 0) { return; }"), "{}", returning.source);
        let class = ClassFile::parse(&returning.bytes).unwrap();
        assert!(class.method(METHOD, "([I)V").unwrap().code.as_ref().unwrap().bytes.contains(&0xc6), "ifnull on the results");
        let scalar = super::params(&["x".into()], &[Type::Float]);
        let floating = generate("net/example/Maths", "f", &scalar, &Type::Float, None, 8).unwrap();
        assert!(floating.source.contains("(ea != 0 || a == b || (a != a && b != b))"), "{}", floating.source);
        assert_eq!(ClassFile::parse(&floating.bytes).unwrap().method(METHOD, "(F)V").unwrap().code.as_ref().unwrap().bytes.iter().filter(|b| **b == 0x95).count(), 3, "three fcmpl");
        assert!(generate("net/example/Utf8", "encodeInto", &params, &Type::Int, Some("chars.length"), 6).unwrap_err().to_string().contains("boolean"));
    }
}
