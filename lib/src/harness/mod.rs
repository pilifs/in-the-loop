//! The statement of a regression proof, as a class file JBMC can check: a harness that calls the old and the new
//! version of a method on the same symbolic arguments, catches what each throws, and asserts that the results and
//! the exception types agree. An array argument is copied first, so that each version writes into its own, and
//! what the two leave is compared element by element, as an array result is. With a scope expression
//! (`--unchanged-unless`), the harness returns early on the inputs the developer meant to change, so the proof
//! covers everything else. A receiver, parameter or result of record type is made of the record's components,
//! each a primitive: the components are the harness's symbolic parameters, the record is built from them through
//! its canonical constructor (an input a constructor of either version rejects is outside the statement), and a
//! record result is compared component by component ([`Layout`]).
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

pub use expr::{CallArg, Callee, Expr, Param};

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
    /// The previous version's arguments as expressions over the parameters, when they are not the parameters
    /// themselves, for computing them again on a replayed counterexample.
    pub before_args: Option<Vec<CallArg>>,
    /// The relation the two results must satisfy, when it is not equality, for checking it again on a replayed
    /// counterexample.
    pub relation: Option<Relation>,
}

/// A record class standing in for a value of it: the receiver, a parameter or the result of record type is made of
/// its components, each a primitive, which the harness takes as symbolic parameters and builds the record from
/// through its canonical constructor.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordType {
    /// The internal name (`net/example/Backoff`); the previous version's record is the same name under `before/`.
    pub class: String,
    /// The components in declaration order, each of a primitive type.
    pub components: Vec<(String, Type)>,
}

impl RecordType {
    /// The canonical constructor's descriptor: one parameter per component.
    pub fn constructor(&self) -> String {
        format!("({})V", self.components.iter().map(|(_, t)| t.descriptor()).collect::<String>())
    }

    pub fn java_name(&self) -> String {
        self.class.replace('/', ".")
    }

    pub fn simple_name(&self) -> String {
        crate::classfile::simple_name_of(&self.class)
    }

    /// `Backoff(baseMillis: long, capMillis: long)`, for the domain.
    pub fn describe(&self) -> String {
        format!("{}({})", self.simple_name(), self.components.iter().map(|(n, t)| format!("{n}: {}", t.java_name())).collect::<Vec<_>>().join(", "))
    }

    /// Whether the previous version's record can stand for this one: the same component types in the same order
    /// (a renamed component is the same value).
    pub fn same_shape(&self, other: &RecordType) -> bool {
        self.components.len() == other.components.len() && self.components.iter().zip(&other.components).all(|((_, a), (_, b))| a == b)
    }
}

/// One argument of the target, made from the harness's flat parameters.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Slot {
    /// A primitive or array parameter: its index among the flat parameters.
    Plain(usize),
    /// A record built from the flat parameters from `first` on, one per component: `record` in the new version
    /// and `before` in the previous one (the same components, under `before/`), or none when the previous version
    /// takes the components themselves (a static method the components are passed to by expressions).
    Record { name: String, record: RecordType, before: Option<RecordType>, first: usize },
}

/// How the target's receiver and arguments are made from the harness's flat parameters, which are the symbolic
/// inputs the checker chooses: a record's components under `name.component`, `this.component` for the receiver's.
#[derive(Debug, Clone)]
pub struct Layout {
    /// The receiver of an instance method, always a [`Slot::Record`] named `this`.
    pub receiver: Option<Slot>,
    pub args: Vec<Slot>,
    /// The flat parameters, in slot order.
    pub params: Vec<Param>,
    /// The result's record, in the new version and in the previous one, when the method returns a record.
    pub result: Option<(RecordType, RecordType)>,
}

impl Layout {
    /// The usual layout: every parameter a primitive or an array, passed through.
    pub fn plain(names: &[String], types: &[Type]) -> Layout {
        Layout { receiver: None, args: (0..types.len()).map(Slot::Plain).collect(), params: params(names, types), result: None }
    }

    /// Lays out the receiver (new record, and the previous one when the previous version has it) and the
    /// parameters, of which `records[i]` says which are records (new, and previous when it has one), flattening
    /// each record into its components.
    pub fn new(receiver: Option<(RecordType, Option<RecordType>)>, names: &[String], types: &[Type], records: &[Option<(RecordType, Option<RecordType>)>], result: Option<(RecordType, RecordType)>) -> Layout {
        let mut flat: Vec<(String, Type)> = Vec::new();
        let flatten = |flat: &mut Vec<(String, Type)>, name: &str, record: &RecordType| {
            for (c, t) in &record.components {
                flat.push((format!("{name}.{c}"), t.clone()));
            }
        };
        let receiver = receiver.map(|(record, before)| {
            flatten(&mut flat, "this", &record);
            Slot::Record { name: "this".into(), record, before, first: 0 }
        });
        let mut args = Vec::new();
        for ((name, t), record) in names.iter().zip(types).zip(records) {
            let first = flat.len();
            match record {
                Some((record, before)) => {
                    flatten(&mut flat, name, record);
                    args.push(Slot::Record { name: name.clone(), record: record.clone(), before: before.clone(), first });
                }
                None => {
                    flat.push((name.clone(), t.clone()));
                    args.push(Slot::Plain(first));
                }
            }
        }
        let (flat_names, flat_types): (Vec<String>, Vec<Type>) = flat.into_iter().unzip();
        Layout { receiver, args, params: params(&flat_names, &flat_types), result }
    }

    /// The flat parameters' types: the harness method's.
    pub fn types(&self) -> Vec<Type> {
        self.params.iter().map(|p| p.ty.clone()).collect()
    }

    /// The target's parameter types.
    pub fn target_types(&self) -> Vec<Type> {
        self.args
            .iter()
            .map(|s| match s {
                Slot::Plain(i) => self.params[*i].ty.clone(),
                Slot::Record { record, .. } => Type::Object(record.class.clone()),
            })
            .collect()
    }

    /// The previous version's descriptor as relocated: its parameters and result, with every record of this layout
    /// under `before/`, since the previous version's classes are.
    pub fn before_descriptor(&self, params: &[Type], ret: &Type) -> String {
        let relocated = |t: &Type| match t {
            Type::Object(name) => {
                let known = self.args.iter().any(|s| matches!(s, Slot::Record { before: Some(b), .. } if b.class == *name)) || self.result.as_ref().is_some_and(|(_, previous)| previous.class == *name);
                if known {
                    format!("Lbefore/{name};")
                } else {
                    t.descriptor()
                }
            }
            _ => t.descriptor(),
        };
        format!("({}){}", params.iter().map(relocated).collect::<String>(), relocated(ret))
    }

    /// Whether the previous version is called on a receiver: the new version's receiver has a previous record.
    pub fn before_receiver(&self) -> bool {
        matches!(&self.receiver, Some(Slot::Record { before: Some(_), .. }))
    }

    /// The receiver and the arguments that are records, the receiver first.
    pub fn records(&self) -> Vec<&Slot> {
        self.receiver.iter().chain(self.args.iter()).filter(|s| matches!(s, Slot::Record { .. })).collect()
    }

    pub fn has_records(&self) -> bool {
        self.receiver.is_some() || self.result.is_some() || self.args.iter().any(|s| matches!(s, Slot::Record { .. }))
    }

    /// `this: Backoff(baseMillis: long, capMillis: long) × attempt: int`.
    pub fn domain(&self, max_array_length: u32) -> String {
        self.receiver
            .iter()
            .chain(self.args.iter())
            .map(|s| match s {
                Slot::Plain(i) => {
                    let p = &self.params[*i];
                    match p.ty {
                        Type::Array(_) => format!("{}: {} of length ≤ {max_array_length}", p.name, p.ty.java_name()),
                        _ => format!("{}: {}", p.name, p.ty.java_name()),
                    }
                }
                Slot::Record { name, record, .. } => format!("{name}: {}", record.describe()),
            })
            .collect::<Vec<_>>()
            .join(" × ")
    }
}

/// The relation between the previous version's result and the new one's (`--results-agree-when`): a boolean
/// expression over the new parameters, `previous` (the previous version's result, in the slot `previous`) and
/// `result` (the new version's, in the slot `result`), which must hold whenever both versions return.
#[derive(Debug, Clone)]
pub struct Relation {
    pub expr: Expr,
    pub previous: u16,
    pub result: u16,
}

/// The name of the previous version's result in a result relation.
pub const PREVIOUS: &str = "previous";

/// The previous version of the method, when it is not the target under the same name with the same parameters:
/// a method renamed or moved, or whose parameters were reordered, added, removed or retyped. The arguments it
/// is called with are expressions over the new version's parameters (`--before-arguments`); without them, the
/// parameters must be the same and are passed through.
#[derive(Debug, Clone)]
pub struct BeforeMethod {
    /// The internal name of the class as it was, before relocation (`net/example/Clock`).
    pub owner: String,
    pub method: String,
    pub descriptor: String,
    pub params: Vec<Type>,
    /// The parameter names, for the report.
    pub names: Vec<String>,
    /// The arguments as written, one per parameter, separated by commas.
    pub arguments: Option<String>,
    /// The previous version's return type.
    pub ret: Type,
    /// The relation its result and the new one's must satisfy, as written, when it is not equality: a boolean
    /// expression over the new parameters, `previous` and `result`.
    pub relation: Option<String>,
}

impl BeforeMethod {
    /// `pkg.Class#method(args)`, or `method(args)` when the class is `class_internal`.
    pub fn display(&self, class_internal: &str) -> String {
        let name = if self.owner == class_internal { self.method.clone() } else { format!("{}#{}", self.owner.replace('/', "."), self.method) };
        match &self.arguments {
            Some(a) => format!("{name}({a})"),
            None => format!("{name}({})", self.names.join(", ")),
        }
    }

    /// Parses the arguments against the new version's parameters: each must have the type of the parameter it is
    /// passed as (an `int` expression for a `byte`, `short` or `char` parameter is narrowed as a cast is), and an
    /// array parameter is passed by name. `first_free_slot` is for a quantifier's variable.
    pub fn parse_arguments(&self, params: &[Param], first_free_slot: u16) -> Result<Option<Vec<CallArg>>, Error> {
        let Some(text) = &self.arguments else {
            let new: Vec<Type> = params.iter().map(|p| p.ty.clone()).collect();
            if new != self.params {
                return Err(Error::new(format!(
                    "the previous version takes ({}) and the new one ({}); give the previous version's arguments as expressions over the new parameters with --before-arguments",
                    self.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", "),
                    new.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")
                )));
            }
            return Ok(None);
        };
        for (name, t) in self.names.iter().zip(&self.params) {
            if expr::ty_of(t).is_none() && expr::element_ty(t).is_none() {
                return Err(Error::new(format!("the previous version's parameter {name} has type {}; an argument can be given for integral and boolean parameters, and for arrays of those", t.java_name())));
            }
        }
        let callee = Callee { name: self.method.clone(), owner: self.owner.clone(), descriptor: self.descriptor.clone(), params: self.params.clone(), ret: expr::Ty::Int };
        match expr::parse_value(&format!("{}({text})", self.method), params, Some(&callee), first_free_slot)? {
            Expr::Call(_, args) => Ok(Some(args)),
            _ => Err(Error::new("the arguments must be a list of expressions separated by commas")),
        }
    }

    /// Parses the result relation, if one was given, over the new parameters, `previous` (the previous version's
    /// result of type `self.ret`, in slot `previous`) and `result` (the new version's of type `ret`, in slot
    /// `result`). Without one, the return types must be the same, and the results are compared for equality.
    pub fn parse_relation(&self, params: &[Param], ret: &Type, previous: u16, result: u16, first_free_slot: u16) -> Result<Option<Relation>, Error> {
        let Some(text) = &self.relation else {
            if self.ret != *ret {
                return Err(Error::new(format!(
                    "the previous version returns {} and the new one {}; say how the results are related with --results-agree-when, a boolean expression over the new parameters, previous and result",
                    self.ret.java_name(),
                    ret.java_name()
                )));
            }
            return Ok(None);
        };
        for (side, t) in [("previous", &self.ret), ("new", ret)] {
            if expr::ty_of(t).is_none() && expr::element_ty(t).is_none() {
                return Err(Error::new(format!("the {side} version returns {}; a relation can be given between integral, boolean and array results", t.java_name())));
            }
        }
        for p in params {
            if p.name == PREVIOUS || p.name == RESULT {
                return Err(Error::new(format!("the parameter {} has the name the relation uses for a result", p.name)));
            }
        }
        let mut names = params.to_vec();
        names.push(Param { name: PREVIOUS.into(), ty: self.ret.clone(), slot: previous });
        names.push(Param { name: RESULT.into(), ty: ret.clone(), slot: result });
        let expr = expr::parse_in(text, &names, None, first_free_slot).map_err(|e| Error::new(format!("in the result relation: {e}")))?;
        Ok(Some(Relation { expr, previous, result }))
    }
}

/// Splits an argument list at the commas outside parentheses and brackets.
fn split_arguments(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut depth = 0i32;
    let mut current = String::new();
    for c in text.chars() {
        match c {
            '(' | '[' => depth += 1,
            ')' | ']' => depth -= 1,
            ',' if depth == 0 => {
                out.push(current.trim().to_string());
                current.clear();
                continue;
            }
            _ => {}
        }
        current.push(c);
    }
    if !current.trim().is_empty() || !out.is_empty() {
        out.push(current.trim().to_string());
    }
    out
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
/// `max_array_length` bounds the copying and comparing loops. An array result is compared the same way. A record
/// among the receiver and the arguments (`layout`) is built from its components in both versions before the calls,
/// and the input is skipped when a constructor throws; a record result is compared component by component.
pub fn generate(class_internal: &str, method: &str, layout: &Layout, ret: &Type, unchanged_unless: Option<&str>, max_array_length: u32, before: Option<&BeforeMethod>) -> Result<Harness, Error> {
    let params = &layout.params;
    let descriptor = format!("({}){}", layout.target_types().iter().map(Type::descriptor).collect::<String>(), ret.descriptor());
    let check_descriptor = format!("({})V", params.iter().map(|p| p.ty.descriptor()).collect::<String>());
    let arg_slots: u16 = params.iter().map(|p| p.ty.slots()).sum();
    let records = layout.records();
    // A record the previous version has no counterpart of is passed to it as its components, by expressions.
    if before.is_none_or(|b| b.arguments.is_none()) && records.iter().any(|s| matches!(s, Slot::Record { before: None, .. })) {
        return Err(Error::new("the previous version takes the record's components; give its arguments as expressions over them with --before-arguments"));
    }

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
    // The previous version's result has its own type when a relation between the results is given.
    let before_ret = before.map(|b| &b.ret).unwrap_or(ret);
    let before_ret_kind = kind_of(before_ret);
    let a = arg_slots + copies.len() as u16;
    let ea = a + if is_void { 0 } else { before_ret.slots() };
    let b = ea + 1;
    let eb = b + if is_void { 0 } else { ret.slots() };
    let index = eb + 1;
    let scope = match unchanged_unless {
        Some(src) => Some(expr::parse_in(src, params, None, index)?),
        None => None,
    };
    // Each record among the receiver and the arguments, built in both versions: the new one's object, then the
    // previous one's.
    let objects = index + 1;
    let object_slots = |i: usize| (objects + 2 * i as u16, objects + 2 * i as u16 + 1);
    // The previous version's arguments, when they are expressions: computed into locals after the objects, with a
    // quantifier's variable after those.
    let temps = objects + 2 * records.len() as u16;
    let before_args = match before {
        Some(b) => b.parse_arguments(params, temps + b.params.iter().map(Type::slots).sum::<u16>())?,
        None => None,
    };
    let relation = match before {
        Some(b) if is_void || b.ret == Type::Void => {
            if b.relation.is_some() || b.ret != *ret {
                return Err(Error::new(format!("the previous version returns {} and the new one {}; a regression proof relates the results of two methods that return", b.ret.java_name(), ret.java_name())));
            }
            None
        }
        Some(bm) => bm.parse_relation(params, ret, a, b, temps + bm.params.iter().map(Type::slots).sum::<u16>())?,
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

    // The records, from their components, in both versions; an input a constructor rejects is outside the
    // statement, and skipped as the scope skips an input.
    if !records.is_empty() {
        let build_start = code.label();
        let build_end = code.label();
        let built = code.label();
        code.bind(build_start);
        for (i, slot) in records.iter().enumerate() {
            let Slot::Record { record, before: previous, first, .. } = slot else { unreachable!("records() returns records") };
            let (new_local, old_local) = object_slots(i);
            let in_previous = previous.as_ref().map(|p| (format!("before/{}", p.class), old_local));
            for (owner, local) in std::iter::once((record.class.clone(), new_local)).chain(in_previous) {
                let class = writer.pool.class(&owner);
                code.op_u16(0xbb, class); // new
                code.op(0x59); // dup
                for (j, (_, t)) in record.components.iter().enumerate() {
                    code.load(kind_of(t), params[first + j].slot);
                }
                let init = writer.pool.method_ref(&owner, "<init>", &record.constructor());
                code.op_u16(0xb7, init); // invokespecial
                code.store(Kind::Ref, local);
            }
        }
        code.bind(build_end);
        code.goto(built);
        let handler = code.label();
        code.bind(handler);
        code.op(0x57); // pop the exception
        code.return_(None);
        // JBMC matches a handler by the exception's own class, not a superclass it has no model of: each class the
        // harness tells apart has a handler, and Throwable last.
        for exception in EXCEPTIONS.iter().chain(["java/lang/Throwable"].iter()) {
            let catch_type = writer.pool.class(exception);
            code.handler(build_start, build_end, handler, Some(catch_type));
        }
        code.bind(built);
        code.max_locals = code.max_locals.max(temps);
    }

    // The previous version's arguments, from the new parameters; an input for which one cannot be computed (a
    // division by zero in the expression) is outside the relation, and skipped as the scope skips an input.
    let before_types: Vec<Type> = match before {
        Some(b) => b.params.clone(),
        None => params.iter().map(|p| p.ty.clone()).collect(),
    };
    if let Some(args) = &before_args {
        let map_start = code.label();
        let map_end = code.label();
        let mapped = code.label();
        code.bind(map_start);
        let mut slot = temps;
        for (arg, t) in args.iter().zip(&before_types) {
            match arg {
                CallArg::Value(e) => {
                    expr::emit_promoted(e, expr::ty_of(t).unwrap_or(expr::Ty::Int), &mut code, &mut writer.pool);
                    match t {
                        Type::Byte => code.op(0x91),  // i2b
                        Type::Char => code.op(0x92),  // i2c
                        Type::Short => code.op(0x93), // i2s
                        _ => {}
                    }
                    code.store(kind_of(t), slot);
                }
                CallArg::Array(_, from) => {
                    let copy = copies.iter().find(|(s, _, _)| s == from).map(|(_, copy, _)| *copy).unwrap_or(*from);
                    code.load(Kind::Ref, copy);
                    code.store(Kind::Ref, slot);
                }
            }
            slot += t.slots();
        }
        code.bind(map_end);
        code.goto(mapped);
        let handler = code.label();
        code.bind(handler);
        code.op(0x57); // pop the exception
        code.return_(None);
        let throwable = writer.pool.class("java/lang/Throwable");
        code.handler(map_start, map_end, handler, Some(throwable));
        code.bind(mapped);
        code.max_locals = code.max_locals.max(slot);
        for arg in args {
            if let CallArg::Value(e) = arg {
                code.max_locals = code.max_locals.max(e.slots_used());
            }
        }
    }

    let (before_class, before_method, before_descriptor) = match before {
        Some(b) => (b.owner.as_str(), b.method.as_str(), layout.before_descriptor(&b.params, &b.ret)),
        None => (class_internal, method, layout.before_descriptor(&layout.target_types(), ret)),
    };
    let before_owner = format!("before/{before_class}");
    for (owner, value_slot, flag_slot, on_copies) in [(before_owner.as_str(), a, ea, true), (class_internal, b, eb, false)] {
        let value_kind = if on_copies { before_ret_kind } else { ret_kind };
        if !is_void {
            match value_kind {
                Kind::Int => code.iconst(0),
                Kind::Long => code.op(0x09),
                Kind::Float => code.op(0x0b),
                Kind::Double => code.op(0x0e),
                Kind::Ref => code.op(0x01),
            }
            code.store(value_kind, value_slot);
        }
        code.iconst(0);
        code.store(Kind::Int, flag_slot);
        let try_start = code.label();
        let try_end = code.label();
        let join = code.label();
        code.bind(try_start);
        // The object of this version standing for a record: the previous version's for the calls on the copies.
        let object_of = |slot: &Slot| -> Option<u16> {
            let i = records.iter().position(|r| *r == slot)?;
            let (new_local, old_local) = object_slots(i);
            Some(if on_copies { old_local } else { new_local })
        };
        // The previous version is called on a receiver only when it has one; a static one gets the components.
        let on_receiver = if on_copies { layout.before_receiver() } else { layout.receiver.is_some() };
        if let (Some(receiver), true) = (&layout.receiver, on_receiver) {
            code.load(Kind::Ref, object_of(receiver).expect("the receiver is a record"));
        }
        if on_copies && before_args.is_some() {
            let mut slot = temps;
            for t in &before_types {
                code.load(kind_of(t), slot);
                slot += t.slots();
            }
        } else {
            for arg in &layout.args {
                match arg {
                    Slot::Plain(i) => {
                        let p = &params[*i];
                        match copies.iter().find(|(slot, _, _)| *slot == p.slot) {
                            Some((_, copy, _)) if on_copies => code.load(Kind::Ref, *copy),
                            _ => code.load(kind_of(&p.ty), p.slot),
                        }
                    }
                    Slot::Record { .. } => code.load(Kind::Ref, object_of(arg).expect("an argument record")),
                }
            }
        }
        let target = if on_copies { writer.pool.method_ref(owner, before_method, &before_descriptor) } else { writer.pool.method_ref(owner, method, &descriptor) };
        code.op_u16(if on_receiver { 0xb6 } else { 0xb8 }, target); // invokevirtual, invokestatic
        if !is_void {
            code.store(value_kind, value_slot);
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

    // The assertion: ea == eb && (ea != 0 || a == b) && each array parameter is left as its copy was; with a
    // relation between the results, it takes the place of a == b, and a relation that throws (a division by zero)
    // does not hold.
    let fail = code.label();
    let ok = code.label();
    code.load(Kind::Int, ea);
    code.load(Kind::Int, eb);
    code.if_icmp(Cond::Ne, fail);
    if !is_void {
        let arrays = code.label();
        code.load(Kind::Int, ea);
        code.if_zero(Cond::Ne, arrays);
        if let Some(r) = &relation {
            let relate_start = code.label();
            let relate_end = code.label();
            code.bind(relate_start);
            expr::emit(&r.expr, &mut code, &mut writer.pool);
            code.bind(relate_end);
            code.if_zero(Cond::Eq, fail);
            code.goto(arrays);
            let handler = code.label();
            code.bind(handler);
            code.op(0x57); // pop the exception
            code.goto(fail);
            let throwable = writer.pool.class("java/lang/Throwable");
            code.handler(relate_start, relate_end, handler, Some(throwable));
            code.max_locals = code.max_locals.max(r.expr.slots_used());
        }
        match ret {
            _ if relation.is_some() => {}
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
            Type::Object(_) if layout.result.is_some() => {
                // Two records agree when both are null or every component agrees, read from the fields.
                let (record, previous) = layout.result.as_ref().expect("checked");
                let compare = code.label();
                code.load(Kind::Ref, a);
                code.if_nonnull(compare);
                code.load(Kind::Ref, b);
                code.if_null(arrays);
                code.goto(fail);
                code.bind(compare);
                code.load(Kind::Ref, b);
                code.if_null(fail);
                for ((name, t), (old_name, _)) in record.components.iter().zip(&previous.components) {
                    let old_field = writer.pool.field_ref(&format!("before/{}", previous.class), old_name, &t.descriptor());
                    let new_field = writer.pool.field_ref(&record.class, name, &t.descriptor());
                    compare_values(&mut code, t, fail, &|code, side| {
                        code.load(Kind::Ref, if side == 0 { a } else { b });
                        code.op_u16(0xb4, if side == 0 { old_field } else { new_field }); // getfield
                    });
                }
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
    let source = source(class_internal, method, layout, ret, unchanged_unless, before);
    Ok(Harness { bytes: writer.to_bytes(), source, scope, params: params.to_vec(), before_args, relation })
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

/// The statement as Java source, for readers. A record's components are parameters named `this_component` or
/// `other_component`, and the record is built from them in both versions.
pub fn source(class_internal: &str, method: &str, layout: &Layout, ret: &Type, unchanged_unless: Option<&str>, before: Option<&BeforeMethod>) -> String {
    let class = class_internal.replace('/', ".");
    let params: Vec<Param> = layout.params.iter().map(|p| Param { name: p.name.replace('.', "_"), ty: p.ty.clone(), slot: p.slot }).collect();
    let params = params.as_slice();
    let param_list = params.iter().map(|p| format!("{} {}", p.ty.java_name(), p.name)).collect::<Vec<_>>().join(", ");
    let is_array = |p: &Param| matches!(p.ty, Type::Array(_));
    let argument = |s: &Slot, side: &str| match s {
        Slot::Plain(i) => {
            let p = &params[*i];
            if is_array(p) && side == "before" {
                format!("{}_before", p.name)
            } else {
                p.name.clone()
            }
        }
        Slot::Record { name, .. } => format!("{name}_{side}"),
    };
    let args = layout.args.iter().map(|s| argument(s, "after")).collect::<Vec<_>>().join(", ");
    let pass_through = layout.args.iter().map(|s| argument(s, "before")).collect::<Vec<_>>().join(", ");
    // The previous version's arguments: computed into locals named after its parameters, from the expressions
    // given, with an array parameter's copy where it is passed by name.
    let mut mapping = Vec::new();
    let records = layout.records();
    let args_before = match before.and_then(|b| b.arguments.as_deref().map(|a| (b, a))) {
        Some((b, text)) => {
            let names: Vec<String> = b.names.iter().map(|n| format!("{n}_")).collect();
            for ((name, t), given) in names.iter().zip(&b.params).zip(split_arguments(text)) {
                // A record's components are named as the parameters are, `this_component` for `this.component`.
                let given = records.iter().fold(given, |e, slot| match slot {
                    Slot::Record { name, .. } => e.replace(&format!("{name}."), &format!("{name}_")),
                    Slot::Plain(_) => e,
                });
                let value = match params.iter().find(|p| p.name == given && is_array(p)) {
                    Some(p) => format!("{}_before", p.name),
                    None => given,
                };
                mapping.push(format!("{} {name} = {value};", t.java_name()));
            }
            names.join(", ")
        }
        None => pass_through,
    };
    let (before_class, before_method) = match before {
        Some(b) => (b.owner.replace('/', "."), b.method.as_str()),
        None => (class.clone(), method),
    };
    let is_void = *ret == Type::Void;
    let type_name = |t: &Type| if t.is_primitive() || matches!(t, Type::Array(_)) { t.java_name() } else { "Object".to_string() };
    let zero = |t: &Type| match t {
        Type::Boolean => "false",
        t if t.is_primitive() => "0",
        _ => "null",
    };
    let before_ret = before.map(|b| &b.ret).unwrap_or(ret);
    let relation = before.and_then(|b| b.relation.as_deref());
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
    if !records.is_empty() {
        s.push_str("        // The records, from their components, in both versions; an input a constructor rejects is outside the statement.\n");
        for slot in &records {
            let Slot::Record { name, record, before: previous, first } = slot else { continue };
            let components = params[*first..*first + record.components.len()].iter().map(|p| p.name.clone()).collect::<Vec<_>>().join(", ");
            match previous {
                Some(previous) => {
                    let old = format!("before.{}", previous.java_name());
                    s.push_str(&format!("        {old} {name}_before; {} {name}_after;\n", record.java_name()));
                    s.push_str(&format!("        try {{ {name}_before = new {old}({components}); {name}_after = new {}({components}); }} catch (Throwable t) {{ return; }}\n", record.java_name()));
                }
                None => {
                    s.push_str(&format!("        {} {name}_after; // the previous version takes the components\n", record.java_name()));
                    s.push_str(&format!("        try {{ {name}_after = new {}({components}); }} catch (Throwable t) {{ return; }}\n", record.java_name()));
                }
            }
        }
    }
    if !mapping.is_empty() {
        s.push_str("        // The previous version's arguments, from the new parameters; an input for which one throws is outside the relation.\n");
        s.push_str(&format!("        {}\n", mapping.join(" ")));
    }
    for (side, owner, callee, args) in [("before", format!("before.{before_class}"), before_method, &args_before), ("after", class.clone(), method, &args)] {
        let (var, t) = if side == "before" { ("a", before_ret) } else { ("b", ret) };
        let on_receiver = if side == "before" { layout.before_receiver() } else { layout.receiver.is_some() };
        let owner = if on_receiver { format!("this_{side}") } else { owner };
        let type_name = |t: &Type| match (&layout.result, t) {
            (Some((record, previous)), Type::Object(_)) => format!("{}{}", if side == "before" { "before." } else { "" }, if side == "before" { previous.java_name() } else { record.java_name() }),
            _ => type_name(t),
        };
        if !is_void {
            s.push_str(&format!("        {} {var} = {};\n", type_name(t), zero(t)));
        }
        s.push_str(&format!("        int e{var} = 0;\n"));
        s.push_str(&format!("        try {{ {}{owner}.{callee}({args}); }}", if is_void { String::new() } else { format!("{var} = ") }));
        for (i, exception) in EXCEPTIONS.iter().enumerate() {
            s.push_str(&format!(" catch ({} t) {{ e{var} = {}; }}", exception.replace('/', "."), i + 1));
        }
        s.push('\n');
    }
    if let Some(r) = relation {
        s.push_str(&format!("        // The results agree when the stated relation holds: previous is the previous version's, result the new one's.\n        {} previous = a; {} result = b;\n", type_name(before_ret), type_name(ret)));
        s.push_str(&format!("        assert ea == eb && (ea != 0 || ({r}))"));
    } else {
        s.push_str("        assert ea == eb");
        if !is_void {
            let equal = match ret {
                Type::Float | Type::Double => "a == b || (a != a && b != b)".to_string(),
                Type::Array(_) => "java.util.Arrays.equals(a, b)".to_string(),
                t if t.is_primitive() => "a == b".to_string(),
                Type::Object(_) if layout.result.is_some() => {
                    let (record, previous) = layout.result.as_ref().expect("checked");
                    let components = record.components.iter().zip(&previous.components).map(|((n, _), (o, _))| format!("a.{o} == b.{n}")).collect::<Vec<_>>().join(" && ");
                    format!("(a == null ? b == null : b != null && {components})")
                }
                _ => "java.util.Objects.equals(a, b)".to_string(),
            };
            s.push_str(&format!(" && (ea != 0 || {equal})"));
        }
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

    /// The usual layout: the parameters as they are.
    fn flat(params: &[Param]) -> Layout {
        Layout { receiver: None, args: (0..params.len()).map(Slot::Plain).collect(), params: params.to_vec(), result: None }
    }

    #[test]
    fn lays_out_a_record_receiver_argument_and_result_as_their_components() {
        let backoff = RecordType { class: "net/example/Backoff".into(), components: vec![("baseMillis".into(), Type::Long), ("capMillis".into(), Type::Long)] };
        let window = RecordType { class: "net/example/Window".into(), components: vec![("from".into(), Type::Int), ("open".into(), Type::Boolean)] };
        let names = ["attempt".to_string(), "window".to_string()];
        let types = [Type::Int, Type::Object("net/example/Window".into())];
        let layout = Layout::new(Some((backoff.clone(), Some(backoff.clone()))), &names, &types, &[None, Some((window.clone(), Some(window.clone())))], Some((window.clone(), window.clone())));
        assert_eq!(layout.params.iter().map(|p| (p.name.as_str(), p.slot)).collect::<Vec<_>>(), vec![("this.baseMillis", 0), ("this.capMillis", 2), ("attempt", 4), ("window.from", 5), ("window.open", 6)]);
        assert_eq!(layout.types(), vec![Type::Long, Type::Long, Type::Int, Type::Int, Type::Boolean]);
        assert_eq!(layout.target_types(), vec![Type::Int, Type::Object("net/example/Window".into())]);
        assert_eq!(layout.domain(8), "this: Backoff(baseMillis: long, capMillis: long) × attempt: int × window: Window(from: int, open: boolean)");
        assert_eq!(layout.records().len(), 2);
        assert_eq!(backoff.constructor(), "(JJ)V");
        assert!(backoff.same_shape(&RecordType { class: "x/Y".into(), components: vec![("a".into(), Type::Long), ("b".into(), Type::Long)] }), "renamed components are the same value");
        assert!(!backoff.same_shape(&window));

        let harness = generate("net/example/Backoff", "next", &layout, &Type::Object("net/example/Window".into()), Some("attempt < 0 || baseMillis > window.from"), 8, None).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(JJIIZ)V").expect("check method over the components");
        let code = check.code.as_ref().unwrap();
        let insns = code.instructions().unwrap();
        use crate::classfile::Insn;
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::New(_))).count(), 5, "two records in two versions, and the AssertionError");
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::InvokeVirtual(_))).count(), 2, "the method on each version's receiver");
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::InvokeStatic(_))).count(), 0);
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::GetField(_))).count(), 4, "the result's two components in each version");
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        assert!(harness.source.contains("public static void check(long this_baseMillis, long this_capMillis, int attempt, int window_from, boolean window_open)"), "{}", harness.source);
        assert!(harness.source.contains("try { this_before = new before.net.example.Backoff(this_baseMillis, this_capMillis); this_after = new net.example.Backoff(this_baseMillis, this_capMillis); } catch (Throwable t) { return; }"), "{}", harness.source);
        assert!(harness.source.contains("try { a = this_before.next(attempt, window_before); }"), "{}", harness.source);
        assert!(harness.source.contains("try { b = this_after.next(attempt, window_after); }"), "{}", harness.source);
        assert!(harness.source.contains("(ea != 0 || (a == null ? b == null : b != null && a.from == b.from && a.open == b.open))"), "{}", harness.source);

        let plain = Layout::plain(&["a".into(), "b".into()], &[Type::Long, Type::Int]);
        assert_eq!(plain.args, vec![Slot::Plain(0), Slot::Plain(1)]);
        assert!(!plain.has_records());
    }

    /// A static method that became the record's method: the receiver has no previous record, the previous version
    /// is called statically with the components, by the expressions given.
    #[test]
    fn calls_a_static_previous_version_with_the_records_components() {
        let batch = RecordType { class: "net/example/Batch".into(), components: vec![("start".into(), Type::Long), ("size".into(), Type::Int)] };
        let names = ["failedIndex".to_string()];
        let layout = Layout::new(Some((batch.clone(), None)), &names, &[Type::Int], &[None], None);
        assert!(!layout.before_receiver());
        assert_eq!(layout.before_descriptor(&[Type::Long, Type::Int, Type::Int], &Type::Long), "(JII)J");
        let previous = BeforeMethod {
            owner: "net/example/BatchCommit".into(),
            method: "offsetToCommit".into(),
            descriptor: "(JII)J".into(),
            params: vec![Type::Long, Type::Int, Type::Int],
            names: vec!["batchStart".into(), "batchSize".into(), "failedIndex".into()],
            arguments: Some("this.start, this.size, failedIndex".into()),
            ret: Type::Long,
            relation: None,
        };
        let harness = generate("net/example/Batch", "offsetToCommit", &layout, &Type::Long, None, 8, Some(&previous)).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(JII)V").expect("check method over the components");
        let insns = check.code.as_ref().unwrap().instructions().unwrap();
        use crate::classfile::Insn;
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::New(_))).count(), 2, "the record in the new version, and the AssertionError");
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::InvokeVirtual(_))).count(), 1, "the new version on its receiver");
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::InvokeStatic(_))).count(), 1, "the previous version with the components");
        assert!(harness.source.contains("net.example.Batch this_after; // the previous version takes the components"), "{}", harness.source);
        assert!(harness.source.contains("long batchStart_ = this_start; int batchSize_ = this_size; int failedIndex_ = failedIndex;"), "{}", harness.source);
        assert!(harness.source.contains("try { a = before.net.example.BatchCommit.offsetToCommit(batchStart_, batchSize_, failedIndex_); }"), "{}", harness.source);
        assert!(harness.source.contains("try { b = this_after.offsetToCommit(failedIndex); }"), "{}", harness.source);
        // Without the expressions there is no way to pass the record to a previous version that has none.
        let same = BeforeMethod { arguments: None, ..previous };
        assert!(generate("net/example/Batch", "offsetToCommit", &layout, &Type::Long, None, 8, Some(&same)).unwrap_err().to_string().contains("takes the record's components"));
    }

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
        let harness = generate("net/example/Pricing", "total", &flat(&params), &Type::Long, Some("seats >= 8"), 8, None).unwrap();
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
    fn generates_a_harness_against_a_previous_version_with_other_parameters() {
        // The new version takes (tsA, tsB, nodeA, nodeB); the previous one took them interleaved, as a short node id.
        let params = params(&["tsA".into(), "tsB".into(), "nodeA".into(), "nodeB".into()], &[Type::Long, Type::Long, Type::Int, Type::Int]);
        let before = BeforeMethod {
            owner: "net/example/Writes".into(),
            method: "pick".into(),
            descriptor: "(JSJS)I".into(),
            params: vec![Type::Long, Type::Short, Type::Long, Type::Short],
            names: vec!["a".into(), "na".into(), "b".into(), "nb".into()],
            arguments: Some("tsA, nodeA, tsB, nodeB + 1".into()),
            ret: Type::Int,
            relation: None,
        };
        let harness = generate("net/example/Writers", "winner", &flat(&params), &Type::Int, None, 8, Some(&before)).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(JJII)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        // The handler around the arguments' computation, and the two versions' handlers.
        assert_eq!(code.exception_table.len(), 1 + 2 * EXCEPTIONS.len());
        let insns = code.instructions().unwrap();
        let calls: Vec<String> = insns
            .iter()
            .filter_map(|(_, i)| match i {
                crate::classfile::Insn::InvokeStatic(index) => class.pool.member(*index).ok().map(|m| format!("{}.{}{}", m.owner, m.name, m.descriptor)),
                _ => None,
            })
            .collect();
        assert_eq!(calls, vec!["before/net/example/Writes.pick(JSJS)I".to_string(), "net/example/Writers.winner(JJII)I".to_string()]);
        // The short parameters are narrowed as a cast narrows.
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, crate::classfile::Insn::Convert(_, crate::classfile::Narrow::Short))).count(), 2, "{insns:?}");
        assert_eq!(harness.before_args.as_ref().map(Vec::len), Some(4));
        assert_eq!(before.display("net/example/Writers"), "net.example.Writes#pick(tsA, nodeA, tsB, nodeB + 1)");
        assert!(harness.source.contains("long a_ = tsA; short na_ = nodeA; long b_ = tsB; short nb_ = nodeB + 1;"), "{}", harness.source);
        assert!(harness.source.contains("a = before.net.example.Writes.pick(a_, na_, b_, nb_);"), "{}", harness.source);
        assert!(harness.source.contains("b = net.example.Writers.winner(tsA, tsB, nodeA, nodeB);"), "{}", harness.source);
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        // Without arguments, the parameters must be the previous version's.
        let same = BeforeMethod { arguments: None, ..before.clone() };
        let problem = generate("net/example/Writers", "winner", &flat(&params), &Type::Int, None, 8, Some(&same)).unwrap_err().to_string();
        assert!(problem.contains("takes (long, short, long, short) and the new one (long, long, int, int)"), "{problem}");
        let wrong = BeforeMethod { arguments: Some("tsA, nodeA, tsB".into()), ..before.clone() };
        assert!(generate("net/example/Writers", "winner", &flat(&params), &Type::Int, None, 8, Some(&wrong)).unwrap_err().to_string().contains("takes 4 arguments, 3 given"));
    }

    #[test]
    fn generates_a_harness_relating_results_of_two_types() {
        // The new version returns how long is left; the previous one returned whether it had expired.
        let params = params(&["writtenAt".into(), "ttl".into(), "now".into()], &[Type::Long, Type::Long, Type::Long]);
        let before = BeforeMethod {
            owner: "net/example/Expiry".into(),
            method: "isExpired".into(),
            descriptor: "(JJJ)Z".into(),
            params: vec![Type::Long, Type::Long, Type::Long],
            names: vec!["writtenAt".into(), "ttl".into(), "now".into()],
            arguments: None,
            ret: Type::Boolean,
            relation: Some("previous == (result <= 0)".into()),
        };
        let harness = generate("net/example/Expiry", "remainingNanos", &flat(&params), &Type::Long, None, 8, Some(&before)).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(JJJ)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        // The two versions' handlers, and the one around the relation.
        assert_eq!(code.exception_table.len(), 2 * EXCEPTIONS.len() + 1);
        // Slots: the three longs, a (a boolean, one slot), ea, b (a long, two), eb, the index.
        let relation = harness.relation.as_ref().expect("relation");
        assert_eq!((relation.previous, relation.result), (6, 8));
        assert_eq!(code.max_locals, 12);
        let insns = code.instructions().unwrap();
        let calls: Vec<String> = insns
            .iter()
            .filter_map(|(_, i)| match i {
                crate::classfile::Insn::InvokeStatic(index) => class.pool.member(*index).ok().map(|m| format!("{}.{}{}", m.owner, m.name, m.descriptor)),
                _ => None,
            })
            .collect();
        assert_eq!(calls, vec!["before/net/example/Expiry.isExpired(JJJ)Z".to_string(), "net/example/Expiry.remainingNanos(JJJ)J".to_string()]);
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        assert!(harness.source.contains("boolean a = false;"), "{}", harness.source);
        assert!(harness.source.contains("long b = 0;"), "{}", harness.source);
        assert!(harness.source.contains("boolean previous = a; long result = b;"), "{}", harness.source);
        assert!(harness.source.contains("assert ea == eb && (ea != 0 || (previous == (result <= 0)));"), "{}", harness.source);
        // Without a relation, the return types must be the same.
        let unrelated = BeforeMethod { relation: None, ..before.clone() };
        let problem = generate("net/example/Expiry", "remainingNanos", &flat(&params), &Type::Long, None, 8, Some(&unrelated)).unwrap_err().to_string();
        assert!(problem.contains("returns boolean and the new one long; say how the results are related with --results-agree-when"), "{problem}");
        // The relation is type-checked, and must be boolean.
        let not_boolean = BeforeMethod { relation: Some("result + 1".into()), ..before.clone() };
        assert!(generate("net/example/Expiry", "remainingNanos", &flat(&params), &Type::Long, None, 8, Some(&not_boolean)).unwrap_err().to_string().contains("in the result relation: the expression must be boolean"));
        let mistyped = BeforeMethod { relation: Some("previous == result".into()), ..before.clone() };
        assert!(generate("net/example/Expiry", "remainingNanos", &flat(&params), &Type::Long, None, 8, Some(&mistyped)).is_err());
    }

    #[test]
    fn generates_an_equivalence_harness_over_arrays() {
        let params = params(&["chars".into(), "out".into()], &[Type::Array(Box::new(Type::Char)), Type::Array(Box::new(Type::Byte))]);
        let harness = generate("net/example/Utf8", "encodeInto", &flat(&params), &Type::Int, None, 6, None).unwrap();
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
        let returning = generate("net/example/Copies", "prefix", &flat(&one), &Type::Array(Box::new(Type::Int)), Some("\\exists int i; 0 <= i && i < a.length; a[i] < 0"), 8, None).unwrap();
        assert!(returning.source.contains("(ea != 0 || java.util.Arrays.equals(a, b))"), "{}", returning.source);
        assert!(returning.source.contains("if (\\exists int i; 0 <= i && i < a.length; a[i] < 0) { return; }"), "{}", returning.source);
        let class = ClassFile::parse(&returning.bytes).unwrap();
        assert!(class.method(METHOD, "([I)V").unwrap().code.as_ref().unwrap().bytes.contains(&0xc6), "ifnull on the results");
        let scalar = super::params(&["x".into()], &[Type::Float]);
        let floating = generate("net/example/Maths", "f", &flat(&scalar), &Type::Float, None, 8, None).unwrap();
        assert!(floating.source.contains("(ea != 0 || a == b || (a != a && b != b))"), "{}", floating.source);
        assert_eq!(ClassFile::parse(&floating.bytes).unwrap().method(METHOD, "(F)V").unwrap().code.as_ref().unwrap().bytes.iter().filter(|b| **b == 0x95).count(), 3, "three fcmpl");
        assert!(generate("net/example/Utf8", "encodeInto", &flat(&params), &Type::Int, Some("chars.length"), 6, None).unwrap_err().to_string().contains("boolean"));
    }
}
