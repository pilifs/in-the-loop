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
    /// The same class with the calls replaced by the assertion's failure: an input that reaches the calls (one
    /// outside the scope, that every constructor accepts and the previous version's arguments are computed for)
    /// violates it. A proof of it is a proof that no input in the domain reaches the calls, and the statement's
    /// proof vacuous.
    pub probe: Vec<u8>,
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
///
/// A parameter may also be an object of an application class made by its constructor (step H2 of
/// `llm-dlc/loops/foundations-heap.md`): the constructor's parameters are primitives or objects made the same way
/// in turn (`Quote(Money amount, int quantity)` of a `Money(long cents)`), and [`RecordType::components`] are the
/// primitive leaves of that construction, named by their path (`amount.cents`, `quantity`), which the harness takes
/// as its symbolic parameters. Such an object may be changed by the method, so [`RecordType::fields`] says what of
/// it both versions' objects are compared on after the calls.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordType {
    /// The internal name (`net/example/Backoff`); the previous version's record is the same name under `before/`.
    pub class: String,
    /// The components in declaration order, each of a primitive type: for a class made by its constructor, the
    /// primitive leaves of its construction in order, each named by its path through it.
    pub components: Vec<(String, Type)>,
    /// The constructor's parameters, of primitive types or the classes of [`RecordType::inner`]; a record's are its
    /// components.
    pub params: Vec<(String, Type)>,
    /// How each parameter of a class type is made, in order.
    pub inner: Vec<RecordType>,
    /// What of the object is observed after the calls: none for a record, whose fields the method cannot change
    /// (its components are primitive); its instance fields, followed into the objects they refer to, for a class.
    pub fields: Option<Fields>,
    /// For the previous version's object only, where a correspondence relates it to the new one's (step H5 of
    /// `llm-dlc/loops/foundations-heap.md`): which of the new construction's leaves each of its leaves is made from,
    /// and the equations it is compared under in place of field-by-field equality.
    pub corresponds: Option<Corresponds>,
}

/// How the previous version's object is related to the new version's where a correspondence's input equations say
/// so (step H5): the two may have different shapes (`Quote(long cents, int quantity)` before, `Quote(Money amount,
/// int quantity)` now).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Corresponds {
    /// For each leaf of the previous version's construction, in order, what it is made from: the new
    /// construction's leaf the equation naming it gives, or the expression over the new construction's leaves it
    /// gives.
    pub leaves: Vec<Source>,
    /// The equations, each between a primitive field path of the previous version's object and one of the new
    /// one's, or an expression over the new one's. They are assumed of the two objects as made (an input on which
    /// one fails is outside the relation), and compared of them as the calls leave them, and of two results of the
    /// same pair of classes.
    pub equations: Vec<FieldEquation>,
    /// The correspondence's output relations for the parameter's fields as the calls leave them (H5's rest): each
    /// compared in place of the equations about the path it is for, which still make the previous object.
    pub relations: Vec<FieldRelation>,
}

impl Corresponds {
    /// The equations compared of the parameter as the calls leave it: those no output relation takes the place of.
    pub fn compared_equations(&self) -> Vec<FieldEquation> {
        self.equations.iter().filter(|e| !self.relations.iter().any(|r| r.covers(&e.old))).cloned().collect()
    }
}

/// An output relation of a correspondence for an object parameter's field as the calls leave it (H5's rest): a
/// boolean over primitive field paths of both versions' objects, `new.p.dollars * 100 + new.p.cents - old.p.cents <
/// 100`, compared in place of equality for the previous version's path `path` (`cents`; empty for the whole
/// object). A path through null makes it not hold.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FieldRelation {
    /// The previous version's field path it is for, under the parameter: `cents`, `amount.cents`, or empty.
    pub path: String,
    /// As the correspondence writes it.
    pub holds: String,
    pub pieces: Vec<Piece>,
    /// The paths read, each once, in order of first reading.
    pub reads: Vec<RelationRead>,
}

/// A field path a [`FieldRelation`] reads: of the previous version's object (`previous`) or the new one's.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RelationRead {
    pub previous: bool,
    pub path: String,
    pub ty: Type,
}

impl FieldRelation {
    /// Whether it takes the place of equality for the previous version's path `old`: its own path, or one under it.
    pub fn covers(&self, old: &str) -> bool {
        self.path.is_empty() || old == self.path || old.strip_prefix(self.path.as_str()).is_some_and(|rest| rest.starts_with('.'))
    }

    /// The observation id it is for, `field:p.cents`, for the parameter `name`.
    pub fn observation(&self, name: &str) -> String {
        if self.path.is_empty() {
            format!("field:{name}")
        } else {
            format!("field:{name}.{}", self.path)
        }
    }

    /// It written with each read as `name(previous, path)`.
    pub fn text(&self, name: &dyn Fn(bool, &str) -> String) -> String {
        self.pieces.iter().map(|p| match p {
            Piece::Text(t) => t.clone(),
            Piece::Read(i) => name(self.reads[*i].previous, &self.reads[*i].path),
        }).collect()
    }

    /// It compiled over locals, read `i` in the local `slots[i]`; `Err` unless it is a boolean.
    pub fn parse(&self, slots: &[u16]) -> Result<expr::Expr, Error> {
        let params: Vec<Param> = self.reads.iter().zip(slots).enumerate().map(|(i, (r, s))| Param { name: format!("read__{i}"), ty: r.ty.clone(), slot: *s }).collect();
        let text = self.text(&|previous, path| format!("read__{}", self.reads.iter().position(|r| r.previous == previous && r.path == path).unwrap_or(0)));
        let e = expr::parse_value(&text, &params, None, slots.iter().map(|s| s + 2).max().unwrap_or(0))?;
        if e.ty() != expr::Ty::Boolean {
            return Err(Error::new(format!("{} is not a boolean", self.holds.trim())));
        }
        Ok(e)
    }

    /// Whether it holds of the values of its reads, in order; `Err` where it can't be evaluated (a division by zero).
    pub fn eval(&self, values: &[crate::interp::Value]) -> Result<bool, Error> {
        let slots: Vec<u16> = (0..self.reads.len() as u16).map(|i| 2 * i).collect();
        let e = self.parse(&slots)?;
        let mut locals = vec![crate::interp::Value::Int(0); 2 * self.reads.len()];
        for (i, v) in values.iter().enumerate() {
            locals[2 * i] = *v;
        }
        Ok(expr::eval(&e, &locals)? == crate::interp::Value::Int(1))
    }
}

/// An output relation of a correspondence for an identity relation (H5's rest): a boolean over whether the relation
/// holds in each version, `old.result == old.q` and `new.result == new.q`, compared in place of "holds before iff it
/// holds now". `new.result != new.q` says the new version hands back another object, always.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IdentityRelation {
    /// The two references, as [`Layout::identity_pairs`] gives them: `("result", "q")`.
    pub pair: (String, String),
    /// As the correspondence writes it.
    pub holds: String,
    /// The text, each read of the relation in a version a [`Piece::Read`] of the index of `reads`.
    pub pieces: Vec<Piece>,
    /// Which version's relation each read is, `true` for the previous one's, each once.
    pub reads: Vec<bool>,
}

impl IdentityRelation {
    /// The observation id it is for, `identity:result==q`.
    pub fn observation(&self) -> String {
        format!("identity:{}=={}", self.pair.0, self.pair.1)
    }

    /// Whether it is for the pair `x`, `y`, either way round.
    pub fn is_for(&self, x: &str, y: &str) -> bool {
        (self.pair.0 == x && self.pair.1 == y) || (self.pair.0 == y && self.pair.1 == x)
    }

    /// It written with each read as `name(previous)`.
    pub fn text(&self, name: &dyn Fn(bool) -> String) -> String {
        self.pieces.iter().map(|p| match p {
            Piece::Text(t) => t.clone(),
            Piece::Read(i) => name(self.reads[*i]),
        }).collect()
    }

    /// It compiled over locals, read `i` a boolean in the local `slots[i]`; `Err` unless it is a boolean.
    pub fn parse(&self, slots: &[u16]) -> Result<expr::Expr, Error> {
        let params: Vec<Param> = slots.iter().enumerate().map(|(i, s)| Param { name: format!("read__{i}"), ty: Type::Boolean, slot: *s }).collect();
        let text = self.text(&|previous| format!("read__{}", self.reads.iter().position(|r| *r == previous).unwrap_or(0)));
        let e = expr::parse_value(&text, &params, None, slots.iter().map(|s| s + 2).max().unwrap_or(0))?;
        if e.ty() != expr::Ty::Boolean {
            return Err(Error::new(format!("{} is not a boolean", self.holds.trim())));
        }
        Ok(e)
    }

    /// Whether it holds where the identity relation holds before (`old`) and now (`new`).
    pub fn eval(&self, old: bool, new: bool) -> Result<bool, Error> {
        let slots: Vec<u16> = (0..self.reads.len() as u16).map(|i| 2 * i).collect();
        let e = self.parse(&slots)?;
        let mut locals = vec![crate::interp::Value::Int(0); 2 * self.reads.len()];
        for (i, previous) in self.reads.iter().enumerate() {
            locals[2 * i] = crate::interp::Value::Int(if *previous { old } else { new } as i32);
        }
        Ok(expr::eval(&e, &locals)? == crate::interp::Value::Int(1))
    }
}

/// What a leaf of the previous version's construction is made from, under a correspondence (step H5).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Source {
    /// The new construction's leaf of this index.
    Leaf(usize),
    /// An expression over the new construction's leaves, each read named by its index among them.
    Computed(Computed),
}

/// An expression over primitive field paths of the new version's object, giving a field of the previous
/// version's (H5's rest): `old.p.cents == new.p.dollars * 100 + new.p.cents` has `dollars * 100 + cents`. Kept as
/// pieces of text and reads, so that it can be written over any root, compiled over any locals and evaluated over
/// any values. Each path it reads is both a field path of the new object and a leaf of its construction, so that it
/// gives the previous leaf before the call and is compared after it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Computed {
    pub pieces: Vec<Piece>,
    /// The paths read, each once, in order of first reading.
    pub reads: Vec<Read>,
    /// The type it gives: the previous version's field's, `int`, `long` or `boolean`.
    pub ty: Type,
}

/// A piece of a [`Computed`] expression: text as written, or the read of this index.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Piece {
    Text(String),
    Read(usize),
}

/// What a [`Computed`] expression reads: a field path of the new object, `dollars`, of the type `ty`, which is the
/// new construction's leaf of index `leaf`; or, where `param` (H5's rest), the new version's primitive parameter
/// named `path`, `n`, which is the flat parameter of index `leaf` once [`Layout::new`] lays the parameters out.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Read {
    pub path: String,
    pub ty: Type,
    pub leaf: usize,
    pub param: bool,
}

impl Computed {
    /// The expression written with each read of a field path as `name(path)`: `q.dollars * 100 + q.cents` for `|p|
    /// format!("q.{p}")`; a parameter it reads is written by its name, `n`.
    pub fn text(&self, name: &dyn Fn(&str) -> String) -> String {
        self.text_with(name, &|n| n.to_string())
    }

    /// [`Computed::text`] with each parameter it reads written as `param(name)`, `new.n`.
    pub fn text_with(&self, name: &dyn Fn(&str) -> String, param: &dyn Fn(&str) -> String) -> String {
        self.pieces.iter().map(|p| match p {
            Piece::Text(t) => t.clone(),
            Piece::Read(i) if self.reads[*i].param => param(&self.reads[*i].path),
            Piece::Read(i) => name(&self.reads[*i].path),
        }).collect()
    }

    /// Whether it reads one of the new version's parameters, besides the object's paths.
    pub fn reads_parameters(&self) -> bool {
        self.reads.iter().any(|r| r.param)
    }

    /// The expression compiled over locals: read `i` in the local `slots[i]`, of its type. Its type promotes to the
    /// field's, as [`Computed::ty`] was checked to when the correspondence was read.
    pub fn parse(&self, slots: &[u16]) -> Result<expr::Expr, Error> {
        let params: Vec<Param> = self.reads.iter().zip(slots).enumerate().map(|(i, (r, s))| Param { name: format!("read__{i}"), ty: r.ty.clone(), slot: *s }).collect();
        let text = self.text_over_reads();
        let e = expr::parse_value(&text, &params, None, slots.iter().map(|s| s + 2).max().unwrap_or(0))?;
        let fits = match (expr::ty_of(&self.ty), e.ty()) {
            (Some(expr::Ty::Long), expr::Ty::Int | expr::Ty::Long) | (Some(expr::Ty::Int), expr::Ty::Int) | (Some(expr::Ty::Boolean), expr::Ty::Boolean) => true,
            _ => false,
        };
        if !fits || !matches!(self.ty, Type::Int | Type::Long | Type::Boolean) {
            return Err(Error::new(format!("{} is {}, and the field it gives is {}", self.text(&|p| p.to_string()), match e.ty() { expr::Ty::Int => "an int", expr::Ty::Long => "a long", expr::Ty::Boolean => "a boolean" }, self.ty.java_name())));
        }
        Ok(e)
    }

    fn text_over_reads(&self) -> String {
        self.pieces.iter().map(|p| match p {
            Piece::Text(t) => t.clone(),
            Piece::Read(i) => format!("read__{i}"),
        }).collect()
    }

    /// The value it gives over the values of its reads, in order, widened to [`Computed::ty`]; `Err` where it
    /// divides by zero.
    pub fn eval(&self, values: &[crate::interp::Value]) -> Result<crate::interp::Value, Error> {
        let slots: Vec<u16> = (0..self.reads.len() as u16).map(|i| 2 * i).collect();
        let e = self.parse(&slots)?;
        let mut locals = vec![crate::interp::Value::Int(0); 2 * self.reads.len()];
        for (i, v) in values.iter().enumerate() {
            locals[2 * i] = *v;
        }
        let v = expr::eval(&e, &locals)?;
        Ok(match (v, &self.ty) {
            (crate::interp::Value::Int(x), Type::Long) => crate::interp::Value::Long(i64::from(x)),
            (v, _) => v,
        })
    }
}

/// A leaf of a construction as the harness passes it: the flat parameter of this index, or an expression over
/// flat parameters (the previous version's object under a correspondence, H5's rest), each read the parameter of
/// the index `at` gives in turn.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Leaf {
    Flat(usize),
    Computed(Computed, Vec<usize>),
}

/// One equation of [`Corresponds`]: `old.q.cents == new.q.amount.cents` as the paths `cents` and `amount.cents`
/// from the two objects, of the primitive type `ty`; or, where the new side is an expression over the new object's
/// paths (`computed`), `new` is that expression over bare paths, `dollars * 100 + cents`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FieldEquation {
    pub old: String,
    pub new: String,
    pub ty: Type,
    pub computed: Option<Computed>,
}

impl FieldEquation {
    /// `old.q.cents == new.q.amount.cents`, for the objects named `old_root` and `new_root`; a parameter an
    /// expression reads is `new.n`.
    pub fn text(&self, old_root: &str, new_root: &str) -> String {
        let new_side = match &self.computed {
            Some(c) => c.text_with(&|p| format!("new.{new_root}.{p}"), &|n| format!("new.{n}")),
            None => self.new_side(&format!("new.{new_root}")),
        };
        format!("old.{old_root}.{} == {new_side}", self.old)
    }

    /// The new side over the object `root`: `root.amount.cents`, or `root.dollars * 100 + root.cents`; a parameter
    /// an expression reads is by its name, `root.price * n`.
    pub fn new_side(&self, root: &str) -> String {
        match &self.computed {
            Some(c) => c.text(&|p| format!("{root}.{p}")),
            None => format!("{root}.{}", self.new),
        }
    }

    /// Whether it reads one of the new version's parameters (H5's rest), and so is about the parameter it relates
    /// in this call, not about every object of its classes.
    pub fn reads_parameters(&self) -> bool {
        self.computed.as_ref().is_some_and(Computed::reads_parameters)
    }
}

/// The fields a primitive field path reads from an object laid out by `fields`, each as its declaring class
/// (unrelocated), name, and descriptor, and the type the last one has; none when the path is not one of them.
pub fn field_steps(fields: &Fields, path: &str) -> Option<(Vec<(String, String, String)>, Type)> {
    let (first, rest) = match path.split_once('.') {
        Some((f, rest)) => (f, Some(rest)),
        None => (path, None),
    };
    let (_, kind) = fields.fields.iter().find(|(n, _)| n == first)?;
    match (kind, rest) {
        (FieldKind::Value(t), None) => Some((vec![(fields.class.clone(), first.to_string(), t.descriptor())], t.clone())),
        (FieldKind::Object(inner), Some(rest)) => {
            let (mut steps, t) = field_steps(inner, rest)?;
            steps.insert(0, (fields.class.clone(), first.to_string(), format!("L{};", inner.class)));
            Some((steps, t))
        }
        _ => None,
    }
}

/// The instance fields of a class as the harness reads them back, in declaration order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fields {
    /// The internal name of the class declaring them.
    pub class: String,
    pub fields: Vec<(String, FieldKind)>,
}

/// One field of [`Fields`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FieldKind {
    /// A primitive, compared as the results are.
    Value(Type),
    /// An array of primitives (`Type::Array`): null in both, or the same length and elements.
    Array(Type),
    /// A reference to an object of an application class: null in both, or each of its fields as compared in turn.
    Object(Box<Fields>),
}

impl Fields {
    /// Each primitive or array field by its path (`amount.cents`), with its type, depth first.
    pub fn paths(&self) -> Vec<(String, Type)> {
        let mut out = Vec::new();
        for (name, kind) in &self.fields {
            match kind {
                FieldKind::Value(t) | FieldKind::Array(t) => out.push((name.clone(), t.clone())),
                FieldKind::Object(inner) => out.extend(inner.paths().into_iter().map(|(p, t)| (format!("{name}.{p}"), t))),
            }
        }
        out
    }

    /// The classes the fields reach, this one first.
    pub fn classes(&self) -> Vec<String> {
        let mut out = vec![self.class.clone()];
        for (_, kind) in &self.fields {
            if let FieldKind::Object(inner) = kind {
                out.extend(inner.classes());
            }
        }
        out
    }

    /// The same fields with every class under `prefix` (`before/`), as the previous version's classes are in the
    /// harness.
    pub fn under(&self, prefix: &str) -> Fields {
        let kind = |k: &FieldKind| match k {
            FieldKind::Object(inner) => FieldKind::Object(Box::new(inner.under(prefix))),
            other => other.clone(),
        };
        Fields { class: format!("{prefix}{}", self.class), fields: self.fields.iter().map(|(n, k)| (n.clone(), kind(k))).collect() }
    }

    /// Whether `other` (the previous version's) has the same fields: the same names and kinds, in the same order.
    pub fn same_shape(&self, other: &Fields) -> bool {
        self.fields.len() == other.fields.len()
            && self.fields.iter().zip(&other.fields).all(|((n, a), (m, b))| {
                n == m
                    && match (a, b) {
                        (FieldKind::Value(x), FieldKind::Value(y)) | (FieldKind::Array(x), FieldKind::Array(y)) => x == y,
                        (FieldKind::Object(x), FieldKind::Object(y)) => x.same_shape(y),
                        _ => false,
                    }
            })
    }
}

impl RecordType {
    /// A record of primitive components, made by its canonical constructor.
    pub fn record(class: &str, components: Vec<(String, Type)>) -> RecordType {
        RecordType { class: class.to_string(), params: components.clone(), components, inner: Vec::new(), fields: None, corresponds: None }
    }

    /// An object of the application class `class` made by its constructor of `params`, each parameter of a class
    /// type made as `inner` says in order, and observed by `fields`.
    pub fn made(class: &str, params: Vec<(String, Type)>, inner: Vec<RecordType>, fields: Fields) -> RecordType {
        let mut components = Vec::new();
        let mut nested = inner.iter();
        for (name, t) in &params {
            if t.is_primitive() {
                components.push((name.clone(), t.clone()));
            } else if let Some(made) = nested.next() {
                components.extend(made.components.iter().map(|(c, t)| (format!("{name}.{c}"), t.clone())));
            }
        }
        RecordType { class: class.to_string(), components, params, inner, fields: Some(fields), corresponds: None }
    }

    /// Whether it is a class made by its constructor, rather than a record of primitive components.
    pub fn is_made(&self) -> bool {
        self.fields.is_some()
    }

    /// The flat parameters its leaves are taken from, in order, for an object whose leaves start at `first`: the
    /// next ones, or under a correspondence the new construction's leaves its equations name.
    pub fn leaf_indices(&self, first: usize) -> Vec<usize> {
        self.leaves(first).into_iter().map(|l| match l {
            Leaf::Flat(i) => i,
            // Only the previous version's object under a correspondence has computed leaves, and its callers ask
            // for `leaves`.
            Leaf::Computed(_, at) => at.first().copied().unwrap_or(first),
        }).collect()
    }

    /// As [`RecordType::leaf_indices`], with a leaf an expression gives (H5's rest) as that expression over the
    /// flat parameters it reads.
    pub fn leaves(&self, first: usize) -> Vec<Leaf> {
        match &self.corresponds {
            Some(c) => c.leaves.iter().map(|s| match s {
                Source::Leaf(i) => Leaf::Flat(first + i),
                Source::Computed(e) => Leaf::Computed(e.clone(), e.reads.iter().map(|r| if r.param { r.leaf } else { first + r.leaf }).collect()),
            }).collect(),
            None => (first..first + self.components.len()).map(Leaf::Flat).collect(),
        }
    }

    /// How many objects making it takes: this one and every inner one.
    pub fn objects(&self) -> u32 {
        1 + self.inner.iter().map(RecordType::objects).sum::<u32>()
    }

    /// The constructor's descriptor: one parameter per component for a record.
    pub fn constructor(&self) -> String {
        self.constructor_in(None)
    }

    /// [`RecordType::constructor`] for the class under the package `prefix` (`before`), whose parameters of a class
    /// type are under it too.
    pub fn constructor_in(&self, prefix: Option<&str>) -> String {
        let descriptor = |t: &Type| match (t, prefix) {
            (Type::Object(name), Some(p)) if self.inner.iter().any(|r| r.class == *name) => format!("L{p}/{name};"),
            _ => t.descriptor(),
        };
        format!("({})V", self.params.iter().map(|(_, t)| descriptor(t)).collect::<String>())
    }

    /// Every constructor the harness calls to make it, this one's first, by owner and descriptor.
    pub fn constructors(&self) -> Vec<(String, String)> {
        let mut out = vec![(self.class.clone(), self.constructor())];
        for r in &self.inner {
            out.extend(r.constructors());
        }
        out
    }

    pub fn java_name(&self) -> String {
        self.class.replace('/', ".")
    }

    pub fn simple_name(&self) -> String {
        crate::classfile::simple_name_of(&self.class)
    }

    /// `Backoff(baseMillis: long, capMillis: long)`, for the domain; a class made by its constructor shows the
    /// constructions of its parameters, `Quote(amount: Money(cents: long), quantity: int)`.
    pub fn describe(&self) -> String {
        let mut nested = self.inner.iter();
        let params = self
            .params
            .iter()
            .map(|(n, t)| match t {
                Type::Object(_) => format!("{n}: {}", nested.next().map(RecordType::describe).unwrap_or_else(|| t.java_name())),
                _ => format!("{n}: {}", t.java_name()),
            })
            .collect::<Vec<_>>()
            .join(", ");
        format!("{}({params})", self.simple_name())
    }

    /// The domain's words for a parameter `name` of it: `name: Backoff(baseMillis: long, capMillis: long)` for a
    /// record, and for a class made by its constructor `name: a Quote made by its constructor, Quote(amount:
    /// Money(cents: long), quantity: int), from any arguments it accepts`, which is all a result over it claims.
    pub fn domain_part(&self, name: &str) -> String {
        if self.is_made() {
            format!("{name}: a {} made by its constructor, {}, from any arguments it accepts", self.simple_name(), self.describe())
        } else {
            format!("{name}: {}", self.describe())
        }
    }

    /// For the previous version's object under a correspondence, the domain's words for how it is made: `a Quote
    /// made by its constructor, Quote(cents: long, quantity: int), from the new q's amount.cents and quantity as the
    /// correspondence's input equations say (old.q.cents == new.q.amount.cents, …), and satisfying them`.
    pub fn made_from(&self, name: &str) -> String {
        let Some(c) = &self.corresponds else { return self.domain_part(name) };
        let sources: Vec<String> = self.components.iter().map(|(leaf, _)| c.equations.iter().find(|e| e.old == *leaf).map(|e| e.new.clone()).unwrap_or_else(|| "?".into())).collect();
        let sources = match sources.split_last() {
            Some((last, rest)) if !rest.is_empty() => format!("{} and {last}", rest.join(", ")),
            _ => sources.join(""),
        };
        format!("a {} made by its constructor, {}, from the new {name}'s {sources} as the correspondence's input equations say ({}), and satisfying them", self.simple_name(), self.describe(), c.equations.iter().map(|e| e.text(name, name)).collect::<Vec<_>>().join(", "))
    }

    /// Whether the previous version's record can stand for this one: the same component types in the same order
    /// (a renamed component is the same value); for a class made by its constructor, the same construction
    /// (constructor parameter types, the inner constructions) and the same fields.
    pub fn same_shape(&self, other: &RecordType) -> bool {
        let leaves = self.components.len() == other.components.len() && self.components.iter().zip(&other.components).all(|((_, a), (_, b))| a == b);
        let made = match (&self.fields, &other.fields) {
            (None, None) => true,
            (Some(a), Some(b)) => {
                a.same_shape(b)
                    && self.params.len() == other.params.len()
                    && self.params.iter().zip(&other.params).all(|((_, a), (_, b))| a == b)
                    && self.inner.len() == other.inner.len()
                    && self.inner.iter().zip(&other.inner).all(|(a, b)| a.same_shape(b))
            }
            _ => false,
        };
        leaves && made
    }
}

/// Where a reference of [`RefPath`] starts: the result, or the target's argument `args[i]`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Root {
    Result,
    Arg(usize),
}

/// A reference that identity relations are observed over, in one version (step H3 of
/// `llm-dlc/loops/foundations-heap.md`): the result, an array parameter or an object parameter made by its
/// constructor, or a field of an object one of those reaches (`q.amount`), by its path.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RefPath {
    pub path: String,
    /// Its static type: a class's internal name as the new version has it (unrelocated), or an array's descriptor.
    pub ty: String,
    pub root: Root,
    /// The reference it is a field of, by index among the same version's paths (always an earlier one), and the
    /// field: its declaring class (unrelocated), name and descriptor. None for a root.
    pub field: Option<(usize, String, String, String)>,
}

impl RefPath {
    /// The field's reference for the version under `prefix` (`before`): its class, and a class in its descriptor,
    /// relocated there.
    pub fn field_in(&self, prefix: Option<&str>) -> Option<(usize, String, String, String)> {
        let (parent, owner, name, descriptor) = self.field.clone()?;
        Some(match prefix {
            Some(p) => {
                let descriptor = match descriptor.strip_prefix('L') {
                    Some(class) => format!("L{p}/{class}"),
                    None => descriptor,
                };
                (parent, format!("{p}/{owner}"), name, descriptor)
            }
            None => (parent, owner, name, descriptor),
        })
    }
}

/// Appends the references among the fields of an object at `path` (index `at` among `out`), depth first.
fn field_refs(out: &mut Vec<RefPath>, path: &str, at: usize, root: Root, fields: &Fields) {
    for (name, kind) in &fields.fields {
        let ty = match kind {
            FieldKind::Value(_) => continue,
            FieldKind::Array(t) => t.descriptor(),
            FieldKind::Object(inner) => inner.class.clone(),
        };
        let descriptor = if matches!(kind, FieldKind::Object(_)) { format!("L{ty};") } else { ty.clone() };
        let here = out.len();
        out.push(RefPath { path: format!("{path}.{name}"), ty, root, field: Some((at, fields.class.clone(), name.clone(), descriptor)) });
        if let FieldKind::Object(inner) = kind {
            field_refs(out, &format!("{path}.{name}"), here, root, inner);
        }
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
    /// The result's record in the new version and in the previous one, when the method returns a record of
    /// primitive components in that version. Without a relation between the results, both are of the same shape
    /// and compared component by component; under one, the relation names the components `result.c` and
    /// `previous.c`.
    pub result: (Option<RecordType>, Option<RecordType>),
    /// The fields of the result in the new version and in the previous one, when it is an object of an application
    /// class other than a record of primitive components (step H3): compared field by field, as an object
    /// parameter is, and followed for identity relations.
    pub result_fields: (Option<Fields>, Option<Fields>),
    /// Where the result's classes are related by a correspondence (step H5): the equations two results are compared
    /// under, in place of field-by-field equality, as the objects of a parameter of the same pair of classes are.
    pub result_equations: Option<Vec<FieldEquation>>,
    /// The object parameters that may be null or the same object as an earlier one (step H2), in slot order, each
    /// choice a boolean flat parameter after every leaf ([`Layout::choose`]).
    pub choices: Vec<Choice>,
    /// A correspondence's output relations for identity relations (H5's rest), each compared in place of "holds
    /// before iff it holds now" for its pair of [`Layout::identity_pairs`].
    pub identity_relations: Vec<IdentityRelation>,
}

/// How an object parameter made by its constructor may be made otherwise (step H2 of
/// `llm-dlc/loops/foundations-heap.md`): null, or the same object as an earlier parameter of its class, each when a
/// boolean flat parameter of the harness says so. Both versions are given the same choice, so that their identity
/// relations start alike. The first flag that holds decides, null first; a flag naming a parameter that is null
/// itself is passed over, so that a parameter that may not be null never is; with none, the object is its own.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Choice {
    /// The parameter's name (`b`, or `this` for the receiver).
    pub name: String,
    /// The flat parameter that makes it null (`b.null`), where it may be.
    pub null: Option<usize>,
    /// For each earlier parameter it may be the same object as, that one's name and the flat parameter that makes it
    /// so (`b.same.a`).
    pub same: Vec<(String, usize)>,
}

/// What a [`Choice`] made of a parameter on one input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Made {
    /// An object of its own, made by its constructor from its leaves.
    Own,
    Null,
    /// The same object as the parameter named, which has one of its own.
    Same(String),
}

/// The groups of names that may be one object, from pairs (`--may-alias a,b`), closed under chains: each group in
/// the order of `order`, the groups by their first member.
pub fn alias_groups(pairs: &[(String, String)], order: &[String]) -> Vec<Vec<String>> {
    let mut groups: Vec<Vec<String>> = Vec::new();
    for (a, b) in pairs {
        let mut group: Vec<String> = groups.iter().filter(|g| g.contains(a) || g.contains(b)).flatten().cloned().chain([a.clone(), b.clone()]).collect();
        groups.retain(|g| !g.contains(a) && !g.contains(b));
        group.sort_by_key(|n| order.iter().position(|o| o == n).unwrap_or(usize::MAX));
        group.dedup();
        groups.push(group);
    }
    groups.sort_by_key(|g| g.first().and_then(|n| order.iter().position(|o| o == n)).unwrap_or(usize::MAX));
    groups
}

impl Layout {
    /// The usual layout: every parameter a primitive or an array, passed through.
    pub fn plain(names: &[String], types: &[Type]) -> Layout {
        Layout { receiver: None, args: (0..types.len()).map(Slot::Plain).collect(), params: params(names, types), result: (None, None), result_fields: (None, None), result_equations: None, choices: Vec::new(), identity_relations: Vec::new() }
    }

    /// Lets the object parameters `nullable` be null and those of each group of `groups` be one object (step H2):
    /// each a parameter made by its constructor in both versions (the receiver among them as `this`, which is never
    /// null), the members of a group of one class. Each choice is a boolean flat parameter appended after every leaf,
    /// so that the leaves keep their places. An error names the flag and what is wrong.
    pub fn choose(&mut self, nullable: &[String], groups: &[Vec<String>]) -> Result<(), String> {
        self.choose_in(nullable, groups, false)
    }

    /// [`Layout::choose`] for a regression check, or for a property check (`property`), whose one version makes
    /// each object by its constructor and whose array parameters' choices are the own checker's, given apart.
    pub fn choose_in(&mut self, nullable: &[String], groups: &[Vec<String>], property: bool) -> Result<(), String> {
        let slots: Vec<&Slot> = self.receiver.iter().chain(self.args.iter()).collect();
        let names: Vec<String> = slots
            .iter()
            .map(|s| match s {
                Slot::Plain(i) => self.params[*i].name.clone(),
                Slot::Record { name, .. } => name.clone(),
            })
            .collect();
        let object = |name: &str, flag: &str| -> Result<(String, String), String> {
            let Some(at) = names.iter().position(|n| n == name) else {
                return Err(format!("{flag} {name}: no parameter is named {name}; the parameters are {}", names.join(", ")));
            };
            match slots[at] {
                Slot::Record { record, before: Some(previous), .. } if record.is_made() && previous.is_made() => Ok((record.class.clone(), previous.class.clone())),
                Slot::Record { record, before: None, .. } if property && record.is_made() => Ok((record.class.clone(), record.class.clone())),
                Slot::Record { record, before: None, .. } if record.is_made() => Err(format!("{flag} {name}: the previous version is given {name} by --before-arguments, which a choice of null or of the same object would not reach")),
                Slot::Record { record, .. } => Err(format!("{flag} {name}: {name} is a {}, a record of primitive components, which a regression check compares as a value; only an object made by its constructor may be null or the same as another here", record.simple_name())),
                Slot::Plain(i) if property => Err(format!("{flag} {name}: {name} is a {}, and only an array parameter or an object made by its constructor may be null or the same as another", self.params[*i].ty.java_name())),
                Slot::Plain(i) => {
                    let t = &self.params[*i].ty;
                    let arrays = if matches!(t, Type::Array(_)) { "; an array parameter may be, in a property check (jvmcontract prove)" } else { "" };
                    Err(format!("{flag} {name}: {name} is a {}, and in a regression check only an object parameter made by its constructor may be null or the same as another{arrays}", t.java_name()))
                }
            }
        };
        for name in nullable {
            object(name, "--nullable")?;
            if name == "this" {
                return Err("--nullable this: the receiver of an instance method is never null".into());
            }
        }
        for group in groups {
            let classes = group.iter().map(|n| object(n, "--may-alias").map(|c| (n, c))).collect::<Result<Vec<_>, _>>()?;
            if let Some(((a, ca), (b, cb))) = classes.iter().zip(classes.iter().skip(1)).find(|((_, x), (_, y))| x != y) {
                let what = if ca.0 != cb.0 { format!("a {} and a {}", crate::classfile::simple_name_of(&ca.0), crate::classfile::simple_name_of(&cb.0)) } else { format!("in the previous version a {} and a {}", crate::classfile::simple_name_of(&ca.1), crate::classfile::simple_name_of(&cb.1)) };
                return Err(format!("--may-alias {a},{b}: {what} are never one object"));
            }
        }
        let mut flat: Vec<(String, Type)> = self.params.iter().map(|p| (p.name.clone(), p.ty.clone())).collect();
        let add = |flat: &mut Vec<(String, Type)>, name: String| -> Result<usize, String> {
            if flat.iter().any(|(n, _)| *n == name) {
                return Err(format!("the choice's input {name} has the name of a leaf of the construction; rename the constructor's parameter"));
            }
            flat.push((name, Type::Boolean));
            Ok(flat.len() - 1)
        };
        let mut choices = Vec::new();
        for (at, name) in names.iter().enumerate() {
            let null = if nullable.contains(name) { Some(add(&mut flat, format!("{name}.null"))?) } else { None };
            let mut same = Vec::new();
            if let Some(group) = groups.iter().find(|g| g.contains(name)) {
                for other in group.iter().filter(|o| names.iter().position(|n| n == *o).is_some_and(|p| p < at)) {
                    same.push((other.clone(), add(&mut flat, format!("{name}.same.{other}"))?));
                }
            }
            if null.is_some() || !same.is_empty() {
                choices.push(Choice { name: name.clone(), null, same });
            }
        }
        let (flat_names, flat_types): (Vec<String>, Vec<Type>) = flat.into_iter().unzip();
        self.params = params(&flat_names, &flat_types);
        self.choices = choices;
        Ok(())
    }

    /// The choice of the parameter `name`, if it has one.
    pub fn choice(&self, name: &str) -> Option<&Choice> {
        self.choices.iter().find(|c| c.name == name)
    }

    /// What the choices make of each object parameter on an input whose flat parameter `i` is `flag(i)`, by name, as
    /// the harness decides it: the parameters without a choice are their own objects.
    pub fn made(&self, flag: &dyn Fn(usize) -> bool) -> Vec<(String, Made)> {
        let mut out: Vec<(String, Made)> = Vec::new();
        for slot in self.receiver.iter().chain(self.args.iter()) {
            let Slot::Record { name, .. } = slot else { continue };
            let made = match self.choice(name) {
                Some(c) if c.null.is_some_and(flag) => Made::Null,
                Some(c) => c
                    .same
                    .iter()
                    .filter(|(_, i)| flag(*i))
                    .find_map(|(other, _)| match out.iter().find(|(n, _)| n == other).map(|(_, m)| m) {
                        Some(Made::Own) => Some(Made::Same(other.clone())),
                        Some(Made::Same(root)) => Some(Made::Same(root.clone())),
                        _ => None,
                    })
                    .unwrap_or(Made::Own),
                None => Made::Own,
            };
            out.push((name.clone(), made));
        }
        out
    }

    /// [`Layout::made`] on a witness's flat arguments.
    pub fn made_on(&self, arguments: &[crate::jbmc::Argument]) -> Vec<(String, Made)> {
        self.made(&|i| matches!(arguments.get(i), Some(crate::jbmc::Argument::Scalar(crate::interp::Value::Int(x))) if *x != 0))
    }

    /// The flat parameters that are choices' flags: a shrinker keeps them, so that it never merges or splits objects.
    pub fn flags(&self) -> Vec<usize> {
        self.choices.iter().flat_map(|c| c.null.into_iter().chain(c.same.iter().map(|(_, i)| *i))).collect()
    }

    /// The references a version's identity relations are over (step H3): the result when it is an array or an object
    /// with [`Layout::result_fields`] (`ret` the version's return type), each array parameter, each object parameter
    /// made by its constructor, and every reference field those reach. `previous` picks the previous version's
    /// objects; `with_args` leaves the parameters out when false (the previous version's arguments are expressions).
    pub fn references(&self, previous: bool, ret: &Type, with_args: bool) -> Vec<RefPath> {
        let mut out = Vec::new();
        let result_fields = if previous { &self.result_fields.1 } else { &self.result_fields.0 };
        match (result_fields, ret) {
            (Some(fields), _) => {
                out.push(RefPath { path: "result".into(), ty: fields.class.clone(), root: Root::Result, field: None });
                field_refs(&mut out, "result", 0, Root::Result, fields);
            }
            (None, Type::Array(_)) => out.push(RefPath { path: "result".into(), ty: ret.descriptor(), root: Root::Result, field: None }),
            _ => {}
        }
        if !with_args {
            return out;
        }
        for (i, slot) in self.args.iter().enumerate() {
            match slot {
                Slot::Plain(p) if matches!(self.params[*p].ty, Type::Array(_)) => {
                    out.push(RefPath { path: self.params[*p].name.clone(), ty: self.params[*p].ty.descriptor(), root: Root::Arg(i), field: None });
                }
                Slot::Record { name, record, before, .. } => {
                    let made = if previous { before.as_ref() } else { Some(record) };
                    if let Some(fields) = made.and_then(|r| r.fields.as_ref()) {
                        let at = out.len();
                        out.push(RefPath { path: name.clone(), ty: fields.class.clone(), root: Root::Arg(i), field: None });
                        field_refs(&mut out, name, at, Root::Arg(i), fields);
                    }
                }
                Slot::Plain(_) => {}
            }
        }
        out
    }

    /// The identity relations compared, each as "holds in the previous version iff in the new one" (step H3), as
    /// pairs of paths: every two references both versions have under the same paths, of the same static type in
    /// one of them. References of different static types are never the same object, since a class an input or a
    /// result is followed into extends `Object` directly, so those pairs are left out. Physical identities are
    /// never compared across versions.
    pub fn identity_pairs(&self, ret: &Type, before_ret: &Type, with_args: bool) -> Vec<(String, String)> {
        let new = self.references(false, ret, with_args);
        let old = self.references(true, before_ret, with_args);
        let ty_in = |refs: &[RefPath], path: &str| refs.iter().find(|r| r.path == path).map(|r| r.ty.clone());
        let mut pairs = Vec::new();
        for (i, x) in new.iter().enumerate() {
            for y in &new[i + 1..] {
                let (Some(ox), Some(oy)) = (ty_in(&old, &x.path), ty_in(&old, &y.path)) else { continue };
                if x.ty == y.ty || ox == oy {
                    pairs.push((x.path.clone(), y.path.clone()));
                }
            }
        }
        pairs
    }

    /// The correspondence's output relation compared for the identity relation `x == y` in place of "holds before
    /// iff it holds now", if it has one.
    pub fn identity_relation(&self, x: &str, y: &str) -> Option<&IdentityRelation> {
        self.identity_relations.iter().find(|r| r.is_for(x, y))
    }

    /// Lays out the receiver (new record, and the previous one when the previous version has it) and the
    /// parameters, of which `records[i]` says which are records (new, and previous when it has one), flattening
    /// each record into its components.
    pub fn new(receiver: Option<(RecordType, Option<RecordType>)>, names: &[String], types: &[Type], records: &[Option<(RecordType, Option<RecordType>)>], result: (Option<RecordType>, Option<RecordType>)) -> Layout {
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
        // A parameter an input equation's expression reads (H5's rest) is the flat parameter of its name.
        for slot in &mut args {
            let Slot::Record { before: Some(previous), .. } = slot else { continue };
            let Some(c) = &mut previous.corresponds else { continue };
            for source in &mut c.leaves {
                let Source::Computed(e) = source else { continue };
                for r in e.reads.iter_mut().filter(|r| r.param) {
                    r.leaf = flat.iter().position(|(n, _)| *n == r.path).unwrap_or(usize::MAX);
                }
            }
            for equation in &mut c.equations {
                let Some(e) = &mut equation.computed else { continue };
                for r in e.reads.iter_mut().filter(|r| r.param) {
                    r.leaf = flat.iter().position(|(n, _)| *n == r.path).unwrap_or(usize::MAX);
                }
            }
        }
        let (flat_names, flat_types): (Vec<String>, Vec<Type>) = flat.into_iter().unzip();
        Layout { receiver, args, params: params(&flat_names, &flat_types), result, result_fields: (None, None), result_equations: None, choices: Vec::new(), identity_relations: Vec::new() }
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
        self.before_descriptor_with(params, ret, &[])
    }

    /// As [`Layout::before_descriptor`], with the records the previous version takes that this layout has no
    /// counterpart of (built from expressions) relocated too.
    pub fn before_descriptor_with(&self, params: &[Type], ret: &Type, also: &[Option<RecordType>]) -> String {
        let relocated = |t: &Type| match t {
            Type::Object(name) => {
                let known = self.args.iter().any(|s| matches!(s, Slot::Record { before: Some(b), .. } if b.class == *name))
                    || self.result.1.as_ref().is_some_and(|previous| previous.class == *name)
                    || self.result_fields.1.as_ref().is_some_and(|previous| previous.class == *name)
                    || also.iter().flatten().any(|r| r.class == *name);
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
        self.receiver.is_some() || self.result.0.is_some() || self.result.1.is_some() || self.args.iter().any(|s| matches!(s, Slot::Record { .. }))
    }

    /// `this: Backoff(baseMillis: long, capMillis: long) × attempt: int`; an array parameter is `a: int[] of
    /// length ≤ 8, not null`, as [`domain`] says.
    pub fn domain(&self, max_array_length: u32) -> String {
        let parts: Vec<(String, bool)> = self
            .receiver
            .iter()
            .chain(self.args.iter())
            .map(|s| match s {
                Slot::Plain(i) => {
                    let p = &self.params[*i];
                    (format!("{}: {}", p.name, p.ty.java_name()), matches!(p.ty, Type::Array(_)))
                }
                Slot::Record { name, record, before: Some(previous), .. } if previous.corresponds.is_some() => (format!("{}{}; in the previous version, {}", record.domain_part(name), self.or_null(name), previous.made_from(name)), false),
                Slot::Record { name, record, .. } => (format!("{}{}", record.domain_part(name), self.or_null(name)), false),
            })
            .collect();
        let text = domain(parts, max_array_length);
        let groups = self.alias_groups();
        if groups.is_empty() {
            return text;
        }
        let listed = |names: &[String]| match names {
            [init @ .., last] if !init.is_empty() => format!("{} and {last}", init.join(", ")),
            _ => names.join(""),
        };
        let shared: Vec<String> = groups.iter().map(|g| format!("{} may be the same object", listed(g))).collect();
        format!("{text}; {}", shared.join("; "))
    }

    /// `, or null` for a parameter its choice lets be null.
    fn or_null(&self, name: &str) -> &'static str {
        if self.choice(name).is_some_and(|c| c.null.is_some()) {
            ", or null"
        } else {
            ""
        }
    }

    /// The groups of object parameters that may be one object, by name in slot order.
    pub fn alias_groups(&self) -> Vec<Vec<String>> {
        let pairs: Vec<(String, String)> = self.choices.iter().flat_map(|c| c.same.iter().map(|(o, _)| (o.clone(), c.name.clone()))).collect();
        let order: Vec<String> = self.receiver.iter().chain(self.args.iter()).filter_map(|s| if let Slot::Record { name, .. } = s { Some(name.clone()) } else { None }).collect();
        alias_groups(&pairs, &order)
    }
}

/// The domain of a proof, from each parameter's `name: type` and whether it is an array: the parts joined by
/// ` × `. An array parameter is `of length ≤ N, not null`, and with two or more of them the domain ends `; no two
/// the same array`, since both engines give each array parameter an array of its own (JBMC under
/// `--java-assume-inputs-non-null`). A claim the JVM refutes only with a null or a shared array is outside the
/// domain, and the domain says so (step 1d of `llm-dlc/loops/sound-verdicts.md`).
pub fn domain(parts: Vec<(String, bool)>, max_array_length: u32) -> String {
    let arrays = parts.iter().filter(|(_, array)| *array).count();
    let joined = parts
        .into_iter()
        .map(|(part, array)| if array { format!("{part} of length ≤ {max_array_length}, not null") } else { part })
        .collect::<Vec<_>>()
        .join(" × ");
    if arrays > 1 {
        format!("{joined}; no two the same array")
    } else {
        joined
    }
}

/// [`domain`] for plain parameters, some arrays among them null perhaps (`nullable`, by name: `a: int[] of length
/// ≤ 8, or null`) or one array with others (`groups`, by name: `; a and b may be the same array`), the rest of
/// them no two the same array. With neither, it is [`domain`]'s text.
pub fn domain_of(params: &[Param], max_array_length: u32, nullable: &[String], groups: &[Vec<String>]) -> String {
    let is_array = |p: &Param| matches!(p.ty, Type::Array(_));
    if nullable.is_empty() && groups.is_empty() {
        return domain(params.iter().map(|p| (format!("{}: {}", p.name, p.ty.java_name()), is_array(p))).collect(), max_array_length);
    }
    let joined = params
        .iter()
        .map(|p| match (is_array(p), nullable.contains(&p.name)) {
            (true, true) => format!("{}: {} of length ≤ {max_array_length}, or null", p.name, p.ty.java_name()),
            (true, false) => format!("{}: {} of length ≤ {max_array_length}, not null", p.name, p.ty.java_name()),
            (false, _) => format!("{}: {}", p.name, p.ty.java_name()),
        })
        .collect::<Vec<_>>()
        .join(" × ");
    let listed = |names: &[String]| match names {
        [one] => one.clone(),
        [init @ .., last] => format!("{} and {last}", init.join(", ")),
        [] => String::new(),
    };
    let mut tail: Vec<String> = groups.iter().map(|g| format!("{} may be the same array", listed(g))).collect();
    let arrays: Vec<&Param> = params.iter().filter(|p| is_array(p)).collect();
    let together = |a: &str, b: &str| groups.iter().any(|g| g.iter().any(|n| n == a) && g.iter().any(|n| n == b));
    let others = arrays.iter().enumerate().any(|(i, a)| arrays[i + 1..].iter().any(|b| !together(&a.name, &b.name)));
    if others {
        tail.push(if groups.is_empty() { "no two the same array" } else { "no other two the same array" }.to_string());
    }
    if tail.is_empty() {
        joined
    } else {
        format!("{joined}; {}", tail.join("; "))
    }
}

/// The relation between the previous version's result and the new one's (`--results-agree-when`): a boolean
/// expression over the new parameters, `previous` (the previous version's result, in the slot `previous`) and
/// `result` (the new version's, in the slot `result`), which must hold whenever both versions return. A result
/// that is a record of primitive components is in the expression as its components, `previous.c` and `result.c`,
/// each read from the record into a slot of its own; two record results that are both null agree, and one null
/// alone does not. A result that is an object of an application class (step H5 of
/// `llm-dlc/loops/foundations-heap.md`) is in it by its field paths, `previous.cents` and `result.amount.cents`,
/// read through the object where the harness evaluates it; two null objects agree, one alone does not, and a path
/// through a null field does not hold.
#[derive(Debug, Clone)]
pub struct Relation {
    pub expr: Expr,
    pub previous: u16,
    pub result: u16,
    /// The previous version's result record and the slots its components are read into, when it is a record.
    pub previous_components: Option<(RecordType, Vec<u16>)>,
    /// The new version's, likewise.
    pub result_components: Option<(RecordType, Vec<u16>)>,
    /// The first slot after those the components take, or 0 when neither result is a record.
    pub slots_end: u16,
    /// The previous version's result, when it is an object read by its field paths: its fields (under `before/`).
    pub previous_object: Option<Fields>,
    /// The new version's, likewise.
    pub result_object: Option<Fields>,
}

impl Relation {
    /// Whether the previous version's result is a reference the relation reads (a record or an object), so that a
    /// null one agrees only with a null one.
    pub fn previous_read(&self) -> bool {
        self.previous_components.is_some() || self.previous_object.is_some()
    }

    /// Likewise for the new version's result.
    pub fn result_read(&self) -> bool {
        self.result_components.is_some() || self.result_object.is_some()
    }
}

/// The name of the previous version's result in a result relation.
pub const PREVIOUS: &str = "previous";

/// The previous version of the method, when it is not the target under the same name with the same parameters:
/// a method renamed or moved, or whose parameters were reordered, added, removed or retyped. The arguments it
/// is called with are expressions over the new version's parameters (`--before-arguments`); without them, the
/// parameters must be the same and are passed through. A record the previous version takes, as its receiver or
/// a parameter, that the new version has no record of the same shape for is built from the new parameters by a
/// constructor call among the arguments, `new Window(this.lo, this.hi)`, the receiver's first.
#[derive(Debug, Clone)]
pub struct BeforeMethod {
    /// The internal name of the class as it was, before relocation (`net/example/Clock`).
    pub owner: String,
    pub method: String,
    pub descriptor: String,
    pub params: Vec<Type>,
    /// The parameter names, for the report.
    pub names: Vec<String>,
    /// The arguments as written, one per parameter (one more, first, for a receiver built by an expression),
    /// separated by commas.
    pub arguments: Option<String>,
    /// The record the previous version is a method of, when its receiver is built by an expression among the
    /// arguments: the new version is static, or a method of a record of other components.
    pub receiver: Option<RecordType>,
    /// By parameter, the record of primitive components it is, built by an expression among the arguments.
    pub records: Vec<Option<RecordType>>,
    /// The previous version's return type.
    pub ret: Type,
    /// The relation its result and the new one's must satisfy, as written, when it is not equality: a boolean
    /// expression over the new parameters, `previous` and `result`.
    pub relation: Option<String>,
}

impl BeforeMethod {
    /// `pkg.Class#method(args)`, or `method(args)` when the class is `class_internal`; with a receiver built by an
    /// expression, `method(args) on new Rec(...)`.
    pub fn display(&self, class_internal: &str) -> String {
        let name = if self.owner == class_internal { self.method.clone() } else { format!("{}#{}", self.owner.replace('/', "."), self.method) };
        match &self.arguments {
            Some(a) if self.receiver.is_some() => {
                let pieces = split_arguments(a);
                match pieces.split_first() {
                    Some((receiver, rest)) => format!("{name}({}) on {receiver}", rest.join(", ")),
                    None => format!("{name}({a})"),
                }
            }
            Some(a) => format!("{name}({a})"),
            None => format!("{name}({})", self.names.join(", ")),
        }
    }

    /// What the arguments stand for, in order: the receiver when it is built by an expression, then each
    /// parameter, with its name, type and the record it is when it is one.
    pub fn expected(&self) -> Vec<(String, Type, Option<&RecordType>)> {
        let receiver = self.receiver.as_ref().map(|r| ("this".to_string(), Type::Object(r.class.clone()), Some(r)));
        let records = self.records.iter().map(Option::as_ref).chain(std::iter::repeat(None));
        receiver.into_iter().chain(self.names.iter().zip(&self.params).zip(records).map(|((n, t), r)| (n.clone(), t.clone(), r))).collect()
    }

    /// The types of the arguments as given: the receiver's, when it is built by an expression, then the parameters'.
    pub fn argument_types(&self) -> Vec<Type> {
        self.expected().into_iter().map(|(_, t, _)| t).collect()
    }

    /// The previous version's descriptor as relocated under `before/`: every record it takes or returns is there.
    pub fn relocated_descriptor(&self, layout: &Layout) -> String {
        layout.before_descriptor_with(&self.params, &self.ret, &self.records)
    }

    /// The expressions of `--before-arguments` as written, one per flat parameter of the previous version (a record
    /// built by `new R(a, b)` as one per component, `a` and `b`), in the order [`Self::parse_arguments`] computes
    /// them; empty without expressions.
    pub fn argument_sources(&self) -> Vec<String> {
        let Some(text) = &self.arguments else { return Vec::new() };
        let mut out = Vec::new();
        for piece in split_arguments(text) {
            let inner = piece
                .strip_prefix("new")
                .filter(|rest| rest.starts_with(char::is_whitespace))
                .and_then(|rest| rest.trim_end().strip_suffix(')'))
                .and_then(|rest| rest.split_once('('))
                .map(|(_, inner)| inner);
            match inner {
                Some(inner) => out.extend(split_arguments(inner)),
                None => out.push(piece),
            }
        }
        out
    }

    /// Parses the arguments against the new version's parameters: each must have the type of the parameter it is
    /// passed as (an `int` expression for a `byte`, `short` or `char` parameter is narrowed as a cast is), and an
    /// array parameter is passed by name. `first_free_slot` is for a quantifier's variable.
    pub fn parse_arguments(&self, params: &[Param], args: &[Slot], first_free_slot: u16) -> Result<Option<Vec<CallArg>>, Error> {
        let Some(text) = &self.arguments else {
            // Passed through as the new version's are: each plain parameter, and each object the layout makes in
            // both versions as the previous version's class.
            let new: Vec<Type> = args
                .iter()
                .map(|a| match a {
                    Slot::Plain(i) => params[*i].ty.clone(),
                    Slot::Record { record, before, .. } => Type::Object(before.as_ref().unwrap_or(record).class.clone()),
                })
                .collect();
            if new != self.params {
                return Err(Error::new(format!(
                    "the previous version takes ({}) and the new one ({}); give the previous version's arguments as expressions over the new parameters with --before-arguments",
                    self.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", "),
                    new.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")
                )));
            }
            return Ok(None);
        };
        let expected = self.expected();
        for (name, t, record) in &expected {
            if record.is_none() && expr::ty_of(t).is_none() && expr::element_ty(t).is_none() {
                return Err(Error::new(format!("the previous version's parameter {name} has type {}; an argument can be given for integral and boolean parameters, for arrays of those, and for records whose components are primitive", t.java_name())));
            }
        }
        let pieces = split_arguments(text);
        // A receiver to build comes first, whatever follows.
        if let (Some(r), Some(first)) = (&self.receiver, pieces.first()) {
            if !first.starts_with("new") {
                self.parse_record(r, "this", first, params, first_free_slot)?;
            }
        }
        if pieces.len() != expected.len() {
            let plural = |n: usize| if n == 1 { "argument".to_string() } else { format!("{n} arguments") };
            let what = match &self.receiver {
                Some(r) => format!("{} takes {} after its receiver, a {} to build first", self.method, plural(self.params.len()), r.simple_name()),
                None => format!("{} takes {}", self.method, plural(self.params.len())),
            };
            return Err(Error::new(format!("{what}, {} given", pieces.len())));
        }
        let mut args = Vec::new();
        for (i, ((name, t, record), piece)) in expected.iter().zip(&pieces).enumerate() {
            let position = match &self.receiver {
                Some(_) if i == 0 => "the receiver".to_string(),
                Some(_) => format!("argument {i}"),
                None => format!("argument {}", i + 1),
            };
            args.push(match record {
                Some(record) => self.parse_record(record, name, piece, params, first_free_slot)?,
                None => parse_argument(&self.method, &position, t, piece, params, first_free_slot)?,
            });
        }
        Ok(Some(args))
    }

    /// `new Window(lo, hi)`: the previous version's record `record`, built from one expression per component.
    fn parse_record(&self, record: &RecordType, name: &str, piece: &str, params: &[Param], first_free_slot: u16) -> Result<CallArg, Error> {
        let simple = record.simple_name();
        let hint = || format!("new {simple}({})", record.components.iter().map(|(c, _)| c.clone()).collect::<Vec<_>>().join(", "));
        let inner = piece
            .strip_prefix("new")
            .filter(|rest| rest.starts_with(char::is_whitespace))
            .map(str::trim_start)
            .and_then(|rest| rest.strip_suffix(')'))
            .and_then(|rest| rest.split_once('('))
            .filter(|(class, _)| class.trim() == simple || class.trim() == record.java_name())
            .map(|(_, inner)| inner);
        let Some(inner) = inner else {
            let what = if name == "this" { format!("the previous version is a method of the record {simple}; build its receiver") } else { format!("the previous version's parameter {name} is the record {simple}; build it") };
            return Err(Error::new(format!("{what} from the new parameters as the first argument, {}", hint())));
        };
        let values = split_arguments(inner);
        if values.len() != record.components.len() {
            return Err(Error::new(format!("{simple} has {} components, {} given; build it as {}", record.components.len(), values.len(), hint())));
        }
        let mut components = Vec::new();
        for ((c, t), value) in record.components.iter().zip(&values) {
            match parse_argument(&format!("new {simple}"), &format!("the component {c}"), t, value, params, first_free_slot)? {
                CallArg::Value(e) => components.push(e),
                _ => return Err(Error::new(format!("the component {c} of {simple} must be a value"))),
            }
        }
        Ok(CallArg::Record(record.clone(), components))
    }

    /// Parses the result relation, if one was given, over the new parameters, `previous` (the previous version's
    /// result of type `self.ret`, in slot `previous`) and `result` (the new version's of type `ret`, in slot
    /// `result`). A result that is a record (`records`: the new version's, the previous one's) is in the
    /// expression as its components, `result.c` and `previous.c`, in slots from `first_free_slot` on, and one that
    /// is an object of an application class (`objects`: the new version's fields, the previous one's) by its field
    /// paths. Without a relation, the return types must be the same, and the results are compared for equality.
    pub fn parse_relation(&self, params: &[Param], ret: &Type, records: &(Option<RecordType>, Option<RecordType>), objects: &(Option<Fields>, Option<Fields>), previous: u16, result: u16, first_free_slot: u16) -> Result<Option<Relation>, Error> {
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
        for (side, t, record, object) in [("previous", &self.ret, &records.1, &objects.1), ("new", ret, &records.0, &objects.0)] {
            if expr::ty_of(t).is_none() && expr::element_ty(t).is_none() && record.is_none() && object.is_none() {
                return Err(Error::new(format!("the {side} version returns {}; a relation can be given between integral, boolean and array results, records of primitive components, and objects of application classes", t.java_name())));
            }
        }
        for p in params {
            if p.name == PREVIOUS || p.name == RESULT {
                return Err(Error::new(format!("the parameter {} has the name the relation uses for a result", p.name)));
            }
        }
        let mut names = params.to_vec();
        let mut next = first_free_slot;
        let mut components = |name: &str, t: &Type, slot: u16, record: &Option<RecordType>| -> Option<(RecordType, Vec<u16>)> {
            match record {
                Some(record) => {
                    let mut slots = Vec::new();
                    for (c, t) in &record.components {
                        names.push(Param { name: format!("{name}.{c}"), ty: t.clone(), slot: next });
                        slots.push(next);
                        next += t.slots();
                    }
                    Some((record.clone(), slots))
                }
                None => {
                    names.push(Param { name: name.into(), ty: t.clone(), slot });
                    None
                }
            }
        };
        let previous_components = components(PREVIOUS, &self.ret, previous, &records.1);
        let result_components = components(RESULT, ret, result, &records.0);
        // An object result is read by its field paths, the previous version's through its classes under before/.
        let previous_object = records.1.is_none().then(|| objects.1.as_ref().map(|f| f.under("before/"))).flatten();
        let result_object = records.0.is_none().then(|| objects.0.clone()).flatten();
        let read: Vec<(String, Fields)> = [(PREVIOUS, &previous_object), (RESULT, &result_object)].into_iter().filter_map(|(n, f)| f.clone().map(|f| (n.to_string(), f))).collect();
        let expr = expr::parse_over_objects(text, &names, None, next, None, &read).map_err(|e| Error::new(format!("in the result relation: {e}")))?;
        if expr.ty() != expr::Ty::Boolean {
            return Err(Error::new("in the result relation: the expression must be boolean"));
        }
        let slots_end = if previous_components.is_some() || result_components.is_some() { next } else { 0 };
        Ok(Some(Relation { expr, previous, result, previous_components, result_components, slots_end, previous_object, result_object }))
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

/// One argument of the previous version: an array parameter passed by name, or a value of the parameter's type
/// (an `int` expression for a `byte`, `short` or `char` parameter is narrowed as a cast is).
fn parse_argument(method: &str, position: &str, t: &Type, piece: &str, params: &[Param], first_free_slot: u16) -> Result<CallArg, Error> {
    if let Some(p) = params.iter().find(|p| p.name == piece && matches!(p.ty, Type::Array(_))) {
        if p.ty != *t {
            return Err(Error::new(format!("{position} of {method} must be {}, {} is {}", t.java_name(), p.name, p.ty.java_name())));
        }
        return Ok(CallArg::Array(p.name.clone(), p.slot));
    }
    let e = expr::parse_value(piece, params, None, first_free_slot)?;
    let ok = match expr::ty_of(t) {
        Some(expr::Ty::Boolean) => e.ty() == expr::Ty::Boolean,
        Some(expr::Ty::Int) => e.ty() == expr::Ty::Int,
        Some(expr::Ty::Long) => e.ty() != expr::Ty::Boolean,
        _ => false,
    };
    if !ok {
        let wanted = match expr::ty_of(t) {
            Some(expr::Ty::Boolean) => "boolean".to_string(),
            Some(expr::Ty::Int) => "int".to_string(),
            Some(expr::Ty::Long) => "a number".to_string(),
            None => format!("the {} parameter {}", t.java_name(), params.iter().find(|p| p.ty == *t).map(|p| p.name.as_str()).unwrap_or("itself")),
        };
        return Err(Error::new(format!("{position} of {method} must be {wanted}")));
    }
    Ok(CallArg::Value(e))
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
    crate::phases::timed(crate::phases::Step::Harness, || generate_untimed(class_internal, method, layout, ret, unchanged_unless, max_array_length, before))
}

fn generate_untimed(class_internal: &str, method: &str, layout: &Layout, ret: &Type, unchanged_unless: Option<&str>, max_array_length: u32, before: Option<&BeforeMethod>) -> Result<Harness, Error> {
    let mut harness = generate_in(class_internal, method, layout, ret, unchanged_unless, max_array_length, before, false)?;
    harness.probe = generate_in(class_internal, method, layout, ret, unchanged_unless, max_array_length, before, true)?.bytes;
    Ok(harness)
}

/// Whether a harness skips some inputs before the calls: the probe is only worth running when it does.
pub fn skips_inputs(layout: &Layout, unchanged_unless: Option<&str>, before: Option<&BeforeMethod>) -> bool {
    unchanged_unless.is_some() || !layout.records().is_empty() || before.is_some_and(|b| b.arguments.is_some())
}

/// Emits the harness's failure: `throw new AssertionError()`.
fn emit_failure(code: &mut CodeBuilder, pool: &mut crate::classfile::writer::PoolBuilder) {
    let assertion_error = pool.class("java/lang/AssertionError");
    let init = pool.method_ref("java/lang/AssertionError", "<init>", "()V");
    code.op_u16(0xbb, assertion_error); // new
    code.op(0x59); // dup
    code.op_u16(0xb7, init); // invokespecial
    code.op(0xbf); // athrow
}

#[allow(clippy::too_many_arguments)]
fn generate_in(class_internal: &str, method: &str, layout: &Layout, ret: &Type, unchanged_unless: Option<&str>, max_array_length: u32, before: Option<&BeforeMethod>, probe: bool) -> Result<Harness, Error> {
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
        Some(b) => b.parse_arguments(params, &layout.args, temps + b.argument_types().iter().map(Type::slots).sum::<u16>())?,
        None => None,
    };
    let relation = match before {
        Some(b) if is_void || b.ret == Type::Void => {
            if b.relation.is_some() || b.ret != *ret {
                return Err(Error::new(format!("the previous version returns {} and the new one {}; a regression proof relates the results of two methods that return", b.ret.java_name(), ret.java_name())));
            }
            None
        }
        Some(bm) => bm.parse_relation(params, ret, &layout.result, &layout.result_fields, a, b, temps + bm.argument_types().iter().map(Type::slots).sum::<u16>())?,
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
            let Slot::Record { name, record, before: previous, first } = slot else { unreachable!("records() returns records") };
            let (new_local, old_local) = object_slots(i);
            let in_previous = previous.as_ref().map(|p| (p, Some("before"), old_local));
            for (made, prefix, local) in std::iter::once((record, None, new_local)).chain(in_previous) {
                // A choice (step H2): null where its flag says so, or the same object as an earlier parameter that
                // is not null, in both versions alike; otherwise an object of its own.
                let done = code.label();
                if let Some(c) = layout.choice(name) {
                    if let Some(flag) = c.null {
                        let own = code.label();
                        code.load(Kind::Int, params[flag].slot);
                        code.if_zero(Cond::Eq, own);
                        code.op(0x01); // aconst_null
                        code.store(Kind::Ref, local);
                        code.goto(done);
                        code.bind(own);
                    }
                    for (other, flag) in &c.same {
                        let next = code.label();
                        let at = records.iter().position(|s| matches!(s, Slot::Record { name: n, .. } if n == other)).expect("a parameter of the group");
                        let (other_new, other_old) = object_slots(at);
                        let other_local = if prefix.is_some() { other_old } else { other_new };
                        code.load(Kind::Int, params[*flag].slot);
                        code.if_zero(Cond::Eq, next);
                        code.load(Kind::Ref, other_local);
                        code.if_null(next);
                        code.load(Kind::Ref, other_local);
                        code.store(Kind::Ref, local);
                        code.goto(done);
                        code.bind(next);
                    }
                }
                emit_construct(&mut code, &mut writer.pool, made, prefix, params, &mut made.leaves(*first).into_iter());
                code.store(Kind::Ref, local);
                code.bind(done);
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
        // Under a correspondence (step H5), the two objects as made must satisfy its equations: an input on which
        // they do not is outside the relation, and skipped.
        let outside = code.label();
        let inside = code.label();
        let mut related = false;
        for (i, slot) in records.iter().enumerate() {
            let Slot::Record { record, before: Some(previous), .. } = slot else { continue };
            let (Some(c), Some(fields), Some(old_fields)) = (&previous.corresponds, &record.fields, &previous.fields) else { continue };
            let (new_local, old_local) = object_slots(i);
            let scratch = code.max_locals;
            let used = compare_corresponding(&mut code, &mut writer.pool, old_local, new_local, old_fields, fields, &c.equations, &[], params, scratch, outside);
            code.max_locals = code.max_locals.max(used);
            related = true;
        }
        if related {
            code.goto(inside);
            code.bind(outside);
            code.return_(None);
            code.bind(inside);
        }
    }

    // The previous version's arguments, from the new parameters; an input for which one cannot be computed (a
    // division by zero in the expression, a record its constructor rejects) is outside the relation, and skipped
    // as the scope skips an input.
    let before_types: Vec<Type> = match before {
        Some(b) => b.argument_types(),
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
                CallArg::Record(record, components) => {
                    expr::emit_record(record, &format!("before/{}", record.class), components, &mut code, &mut writer.pool);
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
        // As for the records built from the components: JBMC matches a handler by the exception's own class.
        for exception in EXCEPTIONS.iter().chain(["java/lang/Throwable"].iter()) {
            let catch_type = writer.pool.class(exception);
            code.handler(map_start, map_end, handler, Some(catch_type));
        }
        code.bind(mapped);
        code.max_locals = code.max_locals.max(slot);
        for arg in args {
            code.max_locals = code.max_locals.max(arg.slots_used());
        }
    }

    let (before_class, before_method, before_descriptor) = match before {
        Some(b) => (b.owner.as_str(), b.method.as_str(), b.relocated_descriptor(layout)),
        None => (class_internal, method, layout.before_descriptor(&layout.target_types(), ret)),
    };
    let before_owner = format!("before/{before_class}");
    // The probe: every input that gets this far fails it, and the calls below are never reached.
    if probe {
        emit_failure(&mut code, &mut writer.pool);
    }
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
        // The previous version is called on a receiver only when it has one: the same record as the new version's,
        // or one built by an expression, first among its arguments; a static one gets the components.
        let built_receiver = on_copies && before.is_some_and(|b| b.receiver.is_some());
        let on_receiver = if on_copies { layout.before_receiver() || built_receiver } else { layout.receiver.is_some() };
        if let (Some(receiver), true, false) = (&layout.receiver, on_receiver, built_receiver) {
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
            // A record or object result: two null ones agree, a null beside one or a primitive does not, and
            // otherwise a record's components are read into the relation's slots.
            match (r.previous_read(), r.result_read()) {
                (true, true) => {
                    let both = code.label();
                    code.load(Kind::Ref, a);
                    code.if_nonnull(both);
                    code.load(Kind::Ref, b);
                    code.if_null(arrays);
                    code.goto(fail);
                    code.bind(both);
                    code.load(Kind::Ref, b);
                    code.if_null(fail);
                }
                (true, false) => {
                    code.load(Kind::Ref, a);
                    code.if_null(fail);
                }
                (false, true) => {
                    code.load(Kind::Ref, b);
                    code.if_null(fail);
                }
                (false, false) => {}
            }
            for (side, components) in [(0, &r.previous_components), (1, &r.result_components)] {
                let Some((record, slots)) = components else { continue };
                let owner = if side == 0 { format!("before/{}", record.class) } else { record.class.clone() };
                for ((name, t), slot) in record.components.iter().zip(slots) {
                    let field = writer.pool.field_ref(&owner, name, &t.descriptor());
                    code.load(Kind::Ref, if side == 0 { a } else { b });
                    code.op_u16(0xb4, field); // getfield
                    code.store(kind_of(t), *slot);
                }
            }
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
            code.max_locals = code.max_locals.max(r.expr.slots_used()).max(r.slots_end);
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
            Type::Object(_) if layout.result.0.is_some() && layout.result.1.is_some() => {
                // Two records agree when both are null or every component agrees, read from the fields.
                let (Some(record), Some(previous)) = (&layout.result.0, &layout.result.1) else { unreachable!("checked") };
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
            Type::Object(_) if layout.result_fields.0.is_some() && layout.result_fields.1.is_some() && layout.result_equations.is_some() => {
                // Under a correspondence (step H5), two results agree when both are null or its equations hold of
                // them, as of a parameter's objects of the same classes.
                let (Some(fields), Some(old_fields), Some(equations)) = (&layout.result_fields.0, &layout.result_fields.1, &layout.result_equations) else { unreachable!("checked") };
                let scratch = code.max_locals.max(index + 1);
                let used = compare_corresponding(&mut code, &mut writer.pool, a, b, old_fields, fields, equations, &[], params, scratch, fail);
                code.max_locals = code.max_locals.max(used);
            }
            Type::Object(_) if layout.result_fields.0.is_some() && layout.result_fields.1.is_some() => {
                // Two objects of an application class agree when both are null or their fields do, followed into
                // the objects they refer to, as an object parameter's are.
                let (Some(fields), Some(old_fields)) = (&layout.result_fields.0, &layout.result_fields.1) else { unreachable!("checked") };
                let compare = code.label();
                code.load(Kind::Ref, a);
                code.if_nonnull(compare);
                code.load(Kind::Ref, b);
                code.if_null(arrays);
                code.goto(fail);
                code.bind(compare);
                code.load(Kind::Ref, b);
                code.if_null(fail);
                let scratch = code.max_locals.max(index + 1);
                let used = compare_fields(&mut code, &mut writer.pool, a, b, old_fields, fields, scratch, index, fail);
                code.max_locals = code.max_locals.max(used);
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
    // Each object made by its constructor, as both versions leave it: its fields compared, followed into the
    // objects they refer to, two locals a level for the pair being compared.
    let mut scratch = code.max_locals.max(index + 1);
    for (i, slot) in records.iter().enumerate() {
        let Slot::Record { name, record, before: Some(previous), .. } = slot else { continue };
        let (Some(fields), Some(old_fields)) = (&record.fields, &previous.fields) else { continue };
        let (new_local, old_local) = object_slots(i);
        // A parameter its choice made null is null in both versions, and has no fields to compare.
        let compared = code.label();
        if layout.choice(name).is_some_and(|c| c.null.is_some()) {
            code.load(Kind::Ref, new_local);
            code.if_null(compared);
        }
        let used = match &previous.corresponds {
            // Under output relations for its fields (H5's rest), each in place of the equations about its path.
            Some(c) => compare_corresponding(&mut code, &mut writer.pool, old_local, new_local, old_fields, fields, &c.compared_equations(), &c.relations, params, scratch, fail),
            None => compare_fields(&mut code, &mut writer.pool, old_local, new_local, old_fields, fields, scratch, index, fail),
        };
        code.bind(compared);
        scratch = scratch.max(used);
    }
    code.max_locals = code.max_locals.max(scratch);
    // The identity relations within each version, compared as "holds before iff it holds now" (step H3): each
    // version's references into locals, a field of a null reference null, then each pair compared by `if_acmp`.
    // A version that threw has a null result in both, so the relations over it agree there.
    let with_args = before.is_none_or(|b| b.arguments.is_none());
    let pairs = layout.identity_pairs(ret, before_ret, with_args);
    if !pairs.is_empty() {
        let mut base = scratch;
        let mut locals: Vec<Vec<(String, u16)>> = Vec::new();
        for (previous, version_ret) in [(true, before_ret), (false, ret)] {
            let refs = layout.references(previous, version_ret, with_args);
            let prefix = previous.then_some("before");
            let mut placed = Vec::new();
            for (k, r) in refs.iter().enumerate() {
                let local = base + k as u16;
                match r.field_in(prefix) {
                    None => {
                        let from = match r.root {
                            Root::Result => if previous { a } else { b },
                            Root::Arg(i) => match &layout.args[i] {
                                Slot::Plain(p) => {
                                    let p = &params[*p];
                                    match copies.iter().find(|(slot, _, _)| *slot == p.slot) {
                                        Some((_, copy, _)) if previous => *copy,
                                        _ => p.slot,
                                    }
                                }
                                slot => {
                                    let at = records.iter().position(|r| *r == slot).expect("an argument record");
                                    let (new_local, old_local) = object_slots(at);
                                    if previous { old_local } else { new_local }
                                }
                            },
                        };
                        code.load(Kind::Ref, from);
                        code.store(Kind::Ref, local);
                    }
                    Some((parent, owner, name, descriptor)) => {
                        let read = code.label();
                        let done = code.label();
                        code.load(Kind::Ref, base + parent as u16);
                        code.if_nonnull(read);
                        code.op(0x01); // aconst_null
                        code.store(Kind::Ref, local);
                        code.goto(done);
                        code.bind(read);
                        let field = writer.pool.field_ref(&owner, &name, &descriptor);
                        code.load(Kind::Ref, base + parent as u16);
                        code.op_u16(0xb4, field); // getfield
                        code.store(Kind::Ref, local);
                        code.bind(done);
                    }
                }
                placed.push((r.path.clone(), local));
            }
            base += refs.len() as u16;
            locals.push(placed);
        }
        let at = |version: usize, path: &str| locals[version].iter().find(|(p, _)| p == path).map(|(_, l)| *l).expect("a path of both versions");
        for (x, y) in &pairs {
            // Under an output relation for it (H5's rest): whether it holds in each version, a boolean each, then
            // the relation over them.
            if let Some(relation) = layout.identity_relation(x, y) {
                let slots: Vec<u16> = (0..relation.reads.len() as u16).map(|j| base + 2 * j).collect();
                let Ok(compiled) = relation.parse(&slots) else {
                    // Refused when the correspondence was read; never agree on one.
                    code.goto(fail);
                    continue;
                };
                for (previous, slot) in relation.reads.iter().zip(&slots) {
                    let version = if *previous { 0 } else { 1 };
                    let apart = code.label();
                    code.iconst(0);
                    code.store(Kind::Int, *slot);
                    code.load(Kind::Ref, at(version, x));
                    code.load(Kind::Ref, at(version, y));
                    code.if_acmpne(apart);
                    code.iconst(1);
                    code.store(Kind::Int, *slot);
                    code.bind(apart);
                }
                expr::emit(&compiled, &mut code, &mut writer.pool);
                code.if_zero(Cond::Eq, fail);
                code.max_locals = code.max_locals.max(base + 2 * relation.reads.len() as u16 + 2);
                continue;
            }
            let apart_before = code.label();
            let next = code.label();
            code.load(Kind::Ref, at(0, x));
            code.load(Kind::Ref, at(0, y));
            code.if_acmpne(apart_before);
            code.load(Kind::Ref, at(1, x));
            code.load(Kind::Ref, at(1, y));
            code.if_acmpne(fail);
            code.goto(next);
            code.bind(apart_before);
            code.load(Kind::Ref, at(1, x));
            code.load(Kind::Ref, at(1, y));
            code.if_acmpne(next);
            code.goto(fail);
            code.bind(next);
        }
        code.max_locals = code.max_locals.max(base);
    }
    code.goto(ok);
    code.bind(fail);
    emit_failure(&mut code, &mut writer.pool);
    code.bind(ok);
    code.return_(None);
    code.max_locals = code.max_locals.max(index + 1);

    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: METHOD.into(), descriptor: check_descriptor, code: Some(code) });
    let source = source(class_internal, method, layout, ret, unchanged_unless, before);
    Ok(Harness { bytes: writer.to_bytes(), probe: Vec::new(), source, scope, params: params.to_vec(), before_args, relation })
}

/// Emits a jump to `fail` unless the objects in the locals `old` (of the previous version's class, under `before/`,
/// laid out as `old_fields`) and `new` (as `fields`) have the same fields: each primitive equal, each array null in
/// both or of the same length and elements, each object null in both or compared so in turn, through the locals from
/// `scratch` on. `index` is the loops' counter. Returns the first local it left unused.
#[allow(clippy::too_many_arguments)]
fn compare_fields(code: &mut CodeBuilder, pool: &mut crate::classfile::writer::PoolBuilder, old: u16, new: u16, old_fields: &Fields, fields: &Fields, scratch: u16, index: u16, fail: Label) -> u16 {
    let mut used = scratch;
    for ((name, kind), (old_name, old_kind)) in fields.fields.iter().zip(&old_fields.fields) {
        let descriptor = |k: &FieldKind, prefix: &str| match k {
            FieldKind::Value(t) | FieldKind::Array(t) => t.descriptor(),
            FieldKind::Object(f) => format!("L{prefix}{};", f.class),
        };
        let old_field = pool.field_ref(&format!("before/{}", old_fields.class), old_name, &descriptor(old_kind, "before/"));
        let new_field = pool.field_ref(&fields.class, name, &descriptor(kind, ""));
        match (kind, old_kind) {
            (FieldKind::Value(t), _) => compare_values(code, t, fail, &|code, side| {
                code.load(Kind::Ref, if side == 0 { old } else { new });
                code.op_u16(0xb4, if side == 0 { old_field } else { new_field }); // getfield
            }),
            (FieldKind::Array(t), _) => {
                let (x, y) = (scratch, scratch + 1);
                for (local, object, field) in [(x, old, old_field), (y, new, new_field)] {
                    code.load(Kind::Ref, object);
                    code.op_u16(0xb4, field); // getfield
                    code.store(Kind::Ref, local);
                }
                let element = match t {
                    Type::Array(e) => (**e).clone(),
                    other => other.clone(),
                };
                let compare = code.label();
                let done = code.label();
                code.load(Kind::Ref, x);
                code.if_nonnull(compare);
                code.load(Kind::Ref, y);
                code.if_null(done);
                code.goto(fail);
                code.bind(compare);
                code.load(Kind::Ref, y);
                code.if_null(fail);
                code.load(Kind::Ref, x);
                code.op(0xbe); // arraylength
                code.load(Kind::Ref, y);
                code.op(0xbe); // arraylength
                code.if_icmp(Cond::Ne, fail);
                compare_arrays(code, x, y, &element, None, index, fail);
                code.bind(done);
                used = used.max(scratch + 2);
            }
            (FieldKind::Object(inner), FieldKind::Object(old_inner)) => {
                let (x, y) = (scratch, scratch + 1);
                for (local, object, field) in [(x, old, old_field), (y, new, new_field)] {
                    code.load(Kind::Ref, object);
                    code.op_u16(0xb4, field); // getfield
                    code.store(Kind::Ref, local);
                }
                let compare = code.label();
                let done = code.label();
                code.load(Kind::Ref, x);
                code.if_nonnull(compare);
                code.load(Kind::Ref, y);
                code.if_null(done);
                code.goto(fail);
                code.bind(compare);
                code.load(Kind::Ref, y);
                code.if_null(fail);
                let deeper = compare_fields(code, pool, x, y, old_inner, inner, scratch + 2, index, fail);
                code.bind(done);
                used = used.max(deeper).max(scratch + 2);
            }
            (FieldKind::Object(_), _) => code.goto(fail),
        }
    }
    used
}

/// Emits a jump to `fail` unless the previous version's object in the local `old` and the new version's in `new`
/// agree under `equations` (step H5): both null, or neither, and each equation's two field paths reading the same,
/// where a path through a null reads as absent and two absent agree, and each of `relations` holding of the two,
/// where a path through null makes it fail. Uses the locals from `scratch` on and returns the first it leaves free.
#[allow(clippy::too_many_arguments)]
fn compare_corresponding(code: &mut CodeBuilder, pool: &mut crate::classfile::writer::PoolBuilder, old: u16, new: u16, old_fields: &Fields, fields: &Fields, equations: &[FieldEquation], relations: &[FieldRelation], params: &[Param], scratch: u16, fail: Label) -> u16 {
    let (link, old_value, new_value, old_present, new_present, read_present, reads) = (scratch, scratch + 1, scratch + 3, scratch + 5, scratch + 6, scratch + 7, scratch + 8);
    let mut used = scratch + 8;
    let compare = code.label();
    let done = code.label();
    code.load(Kind::Ref, old);
    code.if_nonnull(compare);
    code.load(Kind::Ref, new);
    code.if_null(done);
    code.goto(fail);
    code.bind(compare);
    code.load(Kind::Ref, new);
    code.if_null(fail);
    for equation in equations {
        let Some((old_steps, ty)) = field_steps(old_fields, &equation.old) else {
            // A path the layout doesn't have was refused when the correspondence was read; never agree on one.
            code.goto(fail);
            continue;
        };
        emit_read_path(code, pool, old, &old_steps, Some("before"), &ty, old_value, old_present, link);
        match &equation.computed {
            None => {
                let Some((new_steps, _)) = field_steps(fields, &equation.new) else {
                    code.goto(fail);
                    continue;
                };
                emit_read_path(code, pool, new, &new_steps, None, &ty, new_value, new_present, link);
            }
            // An expression over the new object's paths (H5's rest): absent where one of them is, else its value.
            Some(c) => {
                let slots: Vec<u16> = (0..c.reads.len() as u16).map(|j| reads + 2 * j).collect();
                used = used.max(reads + 2 * c.reads.len() as u16);
                // A parameter it reads is never absent: no steps, and its flat parameter's local.
                let steps = c.reads.iter().map(|r| if r.param { params.get(r.leaf).map(|_| Vec::new()) } else { field_steps(fields, &r.path).map(|(s, _)| s) }).collect::<Option<Vec<_>>>();
                let (Ok(compiled), Some(steps)) = (c.parse(&slots), steps) else {
                    code.goto(fail);
                    continue;
                };
                let absent = code.label();
                let read = code.label();
                for ((r, steps), slot) in c.reads.iter().zip(&steps).zip(&slots) {
                    if r.param {
                        code.load(kind_of(&r.ty), params[r.leaf].slot);
                        code.store(kind_of(&r.ty), *slot);
                        continue;
                    }
                    emit_read_path(code, pool, new, steps, None, &r.ty, *slot, read_present, link);
                    code.load(Kind::Int, read_present);
                    code.if_zero(Cond::Eq, absent);
                }
                expr::emit_promoted(&compiled, expr::ty_of(&ty).unwrap_or(expr::Ty::Int), code, pool);
                code.store(kind_of(&ty), new_value);
                code.iconst(1);
                code.store(Kind::Int, new_present);
                code.goto(read);
                code.bind(absent);
                zero_of(code, &ty);
                code.store(kind_of(&ty), new_value);
                code.iconst(0);
                code.store(Kind::Int, new_present);
                code.bind(read);
            }
        }
        let next = code.label();
        code.load(Kind::Int, old_present);
        code.load(Kind::Int, new_present);
        code.if_icmp(Cond::Ne, fail);
        code.load(Kind::Int, old_present);
        code.if_zero(Cond::Eq, next);
        compare_values(code, &ty, fail, &|code, side| code.load(kind_of(&ty), if side == 0 { old_value } else { new_value }));
        code.bind(next);
    }
    // Each output relation for a field (H5's rest): its paths read from both objects, failing where one goes
    // through null, then the boolean.
    for relation in relations {
        let slots: Vec<u16> = (0..relation.reads.len() as u16).map(|j| reads + 2 * j).collect();
        used = used.max(reads + 2 * relation.reads.len() as u16);
        let steps = relation.reads.iter().map(|r| field_steps(if r.previous { old_fields } else { fields }, &r.path).map(|(s, _)| s)).collect::<Option<Vec<_>>>();
        let (Ok(compiled), Some(steps)) = (relation.parse(&slots), steps) else {
            // Refused when the correspondence was read; never agree on one.
            code.goto(fail);
            continue;
        };
        for ((r, steps), slot) in relation.reads.iter().zip(&steps).zip(&slots) {
            let (root, prefix) = if r.previous { (old, Some("before")) } else { (new, None) };
            emit_read_path(code, pool, root, steps, prefix, &r.ty, *slot, read_present, link);
            code.load(Kind::Int, read_present);
            code.if_zero(Cond::Eq, fail);
        }
        expr::emit(&compiled, code, pool);
        code.if_zero(Cond::Eq, fail);
    }
    code.bind(done);
    used
}

/// Pushes the zero of the primitive type `ty`.
fn zero_of(code: &mut CodeBuilder, ty: &Type) {
    match kind_of(ty) {
        Kind::Int => code.iconst(0),
        Kind::Long => code.op(0x09),
        Kind::Float => code.op(0x0b),
        Kind::Double => code.op(0x0e),
        Kind::Ref => code.op(0x01),
    }
}

/// Emits the read of the primitive field path `steps` of type `ty` from the object in the local `root` (its classes
/// under `prefix/` when given) into the local `value`, with 1 in the local `present`, or 0 there (and the type's
/// zero in `value`) where the path goes through null; `link` holds each object on the way.
#[allow(clippy::too_many_arguments)]
fn emit_read_path(code: &mut CodeBuilder, pool: &mut crate::classfile::writer::PoolBuilder, root: u16, steps: &[(String, String, String)], prefix: Option<&str>, ty: &Type, value: u16, present: u16, link: u16) {
    let absent = code.label();
    let read = code.label();
    // A zero first, so that the value's local has its type on every path, as the JVM's verifier wants.
    zero_of(code, ty);
    code.store(kind_of(ty), value);
    code.load(Kind::Ref, root);
    for (k, (owner, name, descriptor)) in steps.iter().enumerate() {
        let (owner, descriptor) = match prefix {
            Some(p) => (format!("{p}/{owner}"), descriptor.strip_prefix('L').map(|c| format!("L{p}/{c}")).unwrap_or_else(|| descriptor.clone())),
            None => (owner.clone(), descriptor.clone()),
        };
        let field = pool.field_ref(&owner, name, &descriptor);
        code.op_u16(0xb4, field); // getfield
        if k + 1 < steps.len() {
            code.store(Kind::Ref, link);
            code.load(Kind::Ref, link);
            code.if_null(absent);
            code.load(Kind::Ref, link);
        }
    }
    code.store(kind_of(ty), value);
    code.iconst(1);
    code.store(Kind::Int, present);
    code.goto(read);
    code.bind(absent);
    code.iconst(0);
    code.store(Kind::Int, present);
    code.bind(read);
}

/// Emits the making of `record` (its class under `prefix/` when given, the previous version's) from its leaves, the
/// flat parameters `leaves` gives in turn, leaving the object on the stack: `new`, the arguments with each inner
/// construction made in its place, and the constructor's call.
fn emit_construct(code: &mut CodeBuilder, pool: &mut crate::classfile::writer::PoolBuilder, record: &RecordType, prefix: Option<&str>, params: &[Param], leaves: &mut dyn Iterator<Item = Leaf>) {
    let owner = match prefix {
        Some(p) => format!("{p}/{}", record.class),
        None => record.class.clone(),
    };
    let class = pool.class(&owner);
    code.op_u16(0xbb, class); // new
    code.op(0x59); // dup
    let mut nested = record.inner.iter();
    for (_, t) in &record.params {
        if t.is_primitive() {
            match leaves.next().expect("a leaf for each primitive argument") {
                Leaf::Flat(leaf) => code.load(kind_of(t), params[leaf].slot),
                // An expression over the new version's leaves (H5's rest), compiled over their locals; one that
                // divides by zero throws here, and the input is skipped as one a constructor rejects.
                Leaf::Computed(e, at) => {
                    let slots: Vec<u16> = at.iter().map(|i| params[*i].slot).collect();
                    let compiled = e.parse(&slots).expect("checked when the correspondence was read");
                    expr::emit_promoted(&compiled, expr::ty_of(t).unwrap_or(expr::Ty::Int), code, pool);
                }
            }
        } else if let Some(inner) = nested.next() {
            emit_construct(code, pool, inner, prefix, params, leaves);
        }
    }
    let init = pool.method_ref(&owner, "<init>", &record.constructor_in(prefix));
    code.op_u16(0xb7, init); // invokespecial
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
            for ((name, t, record), given) in b.expected().into_iter().zip(split_arguments(text)) {
                // A record's components are named as the parameters are, `this_component` for `this.component`.
                let given = records.iter().fold(given, |e, slot| match slot {
                    Slot::Record { name, .. } => e.replace(&format!("{name}."), &format!("{name}_")),
                    Slot::Plain(_) => e,
                });
                let value = match params.iter().find(|p| p.name == given && is_array(p)) {
                    Some(p) => format!("{}_before", p.name),
                    None => given,
                };
                // The previous version's record is its class under before/.
                let (t, value) = match record {
                    Some(r) => (format!("before.{}", r.java_name()), value.replacen("new ", &format!("new before.{}.", r.java_name().rsplit_once('.').map(|(pkg, _)| pkg).unwrap_or_default()), 1).replace("..", ".")),
                    None => (t.java_name(), value),
                };
                mapping.push(format!("{t} {name}_ = {value};"));
            }
            b.names.iter().map(|n| format!("{n}_")).collect::<Vec<_>>().join(", ")
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
        s.push_str("        // The records and objects, from their components, in both versions; an input a constructor rejects is outside the statement.\n");
        for slot in &records {
            let Slot::Record { name, record, before: previous, first } = slot else { continue };
            let leaves = &params[*first..*first + record.components.len()];
            match previous {
                Some(previous) => {
                    let old = format!("before.{}", previous.java_name());
                    // A leaf an expression gives (H5's rest) is that expression over the parameters it reads.
                    let old_leaves: Vec<String> = previous.leaves(*first).into_iter().map(|l| match l {
                        Leaf::Flat(i) => params[i].name.clone(),
                        Leaf::Computed(e, at) => {
                            let names: Vec<(bool, String, String)> = e.reads.iter().zip(&at).map(|(r, i)| (r.param, r.path.clone(), params[*i].name.clone())).collect();
                            let named = |param: bool, p: &str| names.iter().find(|(x, q, _)| *x == param && q == p).map(|(_, _, n)| n.clone()).unwrap_or_default();
                            let text = e.text_with(&|p| named(false, p), &|p| named(true, p));
                            match e.ty { Type::Long => format!("(long) ({})", text.trim()), _ => format!("({})", text.trim()) }
                        }
                    }).collect();
                    s.push_str(&format!("        {old} {name}_before; {} {name}_after;\n", record.java_name()));
                    let (old_made, new_made) = (construction_source_of(previous, "before.", &mut old_leaves.into_iter()), construction_source(record, "", &mut leaves.iter()));
                    // A choice (step H2): null, or the same object as an earlier parameter that is not null.
                    let chosen = |side: &str, made: String| -> String {
                        let Some(c) = layout.choice(name) else { return made };
                        let mut text = made;
                        for (other, flag) in c.same.iter().rev() {
                            text = format!("{} && {other}_{side} != null ? {other}_{side} : {text}", params[*flag].name);
                        }
                        if let Some(flag) = c.null {
                            text = format!("{} ? null : {text}", params[flag].name);
                        }
                        text
                    };
                    s.push_str(&format!("        try {{ {name}_before = {}; {name}_after = {}; }} catch (Throwable t) {{ return; }}\n", chosen("before", old_made), chosen("after", new_made)));
                    if let Some(c) = &previous.corresponds {
                        s.push_str(&format!("        if (!{}) {{ return; }} // the correspondence's input equations, of the objects as made\n", equations_source(&format!("{name}_before"), &format!("{name}_after"), &c.equations)));
                    }
                }
                None => {
                    s.push_str(&format!("        {} {name}_after; // the previous version takes the components\n", record.java_name()));
                    s.push_str(&format!("        try {{ {name}_after = {}; }} catch (Throwable t) {{ return; }}\n", construction_source(record, "", &mut leaves.iter())));
                }
            }
        }
    }
    if !mapping.is_empty() {
        s.push_str("        // The previous version's arguments, from the new parameters; an input for which one throws (a record its constructor rejects) is outside the relation.\n");
        s.push_str(&format!("        {}\n", mapping.join(" ")));
    }
    for (side, owner, callee, args) in [("before", format!("before.{before_class}"), before_method, &args_before), ("after", class.clone(), method, &args)] {
        let (var, t) = if side == "before" { ("a", before_ret) } else { ("b", ret) };
        let built_receiver = side == "before" && before.is_some_and(|b| b.receiver.is_some());
        let on_receiver = if side == "before" { layout.before_receiver() || built_receiver } else { layout.receiver.is_some() };
        let owner = if built_receiver { "this_".to_string() } else if on_receiver { format!("this_{side}") } else { owner };
        let type_name = |t: &Type| match (if side == "before" { &layout.result.1 } else { &layout.result.0 }, if side == "before" { &layout.result_fields.1 } else { &layout.result_fields.0 }, t) {
            (Some(record), _, Type::Object(_)) => format!("{}{}", if side == "before" { "before." } else { "" }, record.java_name()),
            (None, Some(fields), Type::Object(_)) => format!("{}{}", if side == "before" { "before." } else { "" }, fields.class.replace('/', ".")),
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
        // A record result's type, and its components as accessor calls, `previous.c()`.
        let typed = |t: &Type, record: &Option<RecordType>, fields: &Option<Fields>, prefix: &str| match (record, fields, t) {
            (Some(record), _, Type::Object(_)) => format!("{prefix}{}", record.java_name()),
            (None, Some(fields), Type::Object(_)) => format!("{prefix}{}", fields.class.replace('/', ".")),
            _ => type_name(t),
        };
        let r = [(PREVIOUS, &layout.result.1), (RESULT, &layout.result.0)].into_iter().fold(r.to_string(), |text, (name, record)| match record {
            Some(record) => accessor_calls(&text, name, record),
            None => text,
        });
        let read = |record: &Option<RecordType>, fields: &Option<Fields>| record.is_some() || fields.is_some();
        let null_note = match (read(&layout.result.1, &layout.result_fields.1), read(&layout.result.0, &layout.result_fields.0)) {
            _ if layout.result_fields.0.is_some() || layout.result_fields.1.is_some() => match (read(&layout.result.1, &layout.result_fields.1), read(&layout.result.0, &layout.result_fields.0)) {
                (true, true) => " (two null results agree, one alone does not)",
                _ => " (a null result does not)",
            },
            (true, true) => " (two null records agree, one alone does not)",
            (true, false) | (false, true) => " (a null record does not)",
            (false, false) => "",
        };
        s.push_str(&format!("        // The results agree when the stated relation holds: previous is the previous version's, result the new one's{null_note}.\n        {} previous = a; {} result = b;\n", typed(before_ret, &layout.result.1, &layout.result_fields.1, "before."), typed(ret, &layout.result.0, &layout.result_fields.0, "")));
        s.push_str(&format!("        assert ea == eb && (ea != 0 || ({r}))"));
    } else {
        s.push_str("        assert ea == eb");
        if !is_void {
            let equal = match ret {
                Type::Float | Type::Double => "a == b || (a != a && b != b)".to_string(),
                Type::Array(_) => "java.util.Arrays.equals(a, b)".to_string(),
                t if t.is_primitive() => "a == b".to_string(),
                Type::Object(_) if layout.result.0.is_some() && layout.result.1.is_some() => {
                    let (Some(record), Some(previous)) = (&layout.result.0, &layout.result.1) else { unreachable!("checked") };
                    let components = record.components.iter().zip(&previous.components).map(|((n, _), (o, _))| format!("a.{o} == b.{n}")).collect::<Vec<_>>().join(" && ");
                    format!("(a == null ? b == null : b != null && {components})")
                }
                Type::Object(_) if layout.result_equations.is_some() => format!("(a == null ? b == null : b != null && {})", equations_source("a", "b", layout.result_equations.as_deref().unwrap_or_default())),
                Type::Object(_) if layout.result_fields.0.is_some() && layout.result_fields.1.is_some() => {
                    let (Some(fields), Some(old_fields)) = (&layout.result_fields.0, &layout.result_fields.1) else { unreachable!("checked") };
                    format!("(a == null ? b == null : b != null && {})", fields_source("a", "b", old_fields, fields))
                }
                _ => "java.util.Objects.equals(a, b)".to_string(),
            };
            s.push_str(&format!(" && (ea != 0 || {equal})"));
        }
    }
    for p in params.iter().filter(|p| is_array(p)) {
        s.push_str(&format!(" && java.util.Arrays.equals({}, {}_before)", p.name, p.name));
    }
    // Each object made by its constructor, as both versions leave it.
    for slot in &records {
        if let Slot::Record { name, record, before: Some(previous), .. } = slot {
            let compared = match (&record.fields, &previous.fields, &previous.corresponds) {
                (Some(_), Some(_), Some(c)) => {
                    let (old, new) = (format!("{name}_before"), format!("{name}_after"));
                    let mut compared = equations_source(&old, &new, &c.compared_equations());
                    // An output relation for a field in place of the equations about it (H5's rest).
                    for r in &c.relations {
                        compared = format!("{compared} && ({})", r.text(&|previous, path| format!("{}.{path}", if previous { &old } else { &new })).trim());
                    }
                    compared
                }
                (Some(fields), Some(old_fields), None) => fields_source(&format!("{name}_before"), &format!("{name}_after"), old_fields, fields),
                _ => continue,
            };
            // A parameter its choice made null is null in both versions.
            if layout.choice(name).is_some_and(|c| c.null.is_some()) {
                s.push_str(&format!(" && ({name}_after == null || {compared})"));
            } else {
                s.push_str(&format!(" && {compared}"));
            }
        }
    }
    // The identity relations within each version, "holds before iff it holds now"; a field of null reads as null.
    let with_args = before.is_none_or(|b| b.arguments.is_none());
    let in_version = |path: &str, previous: bool| -> String {
        let (root, rest) = path.split_once('.').map(|(r, rest)| (r, format!(".{rest}"))).unwrap_or((path, String::new()));
        let root = match (root, previous) {
            ("result", true) => "a".to_string(),
            ("result", false) => "b".to_string(),
            (name, _) => {
                let record = records.iter().any(|slot| matches!(slot, Slot::Record { name: n, .. } if n == name));
                match (record, previous) {
                    (true, true) => format!("{name}_before"),
                    (true, false) => format!("{name}_after"),
                    (false, true) => format!("{name}_before"),
                    (false, false) => name.to_string(),
                }
            }
        };
        format!("{root}{rest}")
    };
    for (x, y) in layout.identity_pairs(ret, before_ret, with_args) {
        match layout.identity_relation(&x, &y) {
            // Under an output relation for it (H5's rest), the relation over whether it holds in each version.
            Some(r) => s.push_str(&format!(" && ({})", r.text(&|previous| format!("({} == {})", in_version(&r.pair.0, previous), in_version(&r.pair.1, previous))).trim())),
            None => s.push_str(&format!(" && (({} == {}) == ({} == {}))", in_version(&x, true), in_version(&y, true), in_version(&x, false), in_version(&y, false))),
        }
    }
    s.push_str(";\n    }\n}\n");
    s
}

/// The Java for making `record` (its classes under `prefix`, `before.` for the previous version's) from the next of
/// `leaves`: `new before.shop.Quote(new before.shop.Money(q_amount_cents), q_quantity)`.
fn construction_source<'a>(record: &RecordType, prefix: &str, leaves: &mut impl Iterator<Item = &'a Param>) -> String {
    construction_source_of(record, prefix, &mut leaves.map(|p| p.name.clone()))
}

/// As [`construction_source`], with each leaf's Java given: a parameter's name, or an expression over them.
fn construction_source_of(record: &RecordType, prefix: &str, leaves: &mut dyn Iterator<Item = String>) -> String {
    let mut nested = record.inner.iter();
    let args: Vec<String> = record
        .params
        .iter()
        .map(|(_, t)| match t {
            Type::Object(_) => nested.next().map(|r| construction_source_of(r, prefix, leaves)).unwrap_or_default(),
            _ => leaves.next().unwrap_or_default(),
        })
        .collect();
    format!("new {prefix}{}({})", record.java_name(), args.join(", "))
}

/// The Java for two objects satisfying a correspondence's equations, as [`compare_corresponding`] compares them
/// (a path through null reading as absent is left out, for brevity): `(q_before.cents == q_after.amount.cents)`.
fn equations_source(old: &str, new: &str, equations: &[FieldEquation]) -> String {
    let parts: Vec<String> = equations.iter().map(|e| format!("{old}.{} == {}", e.old, e.computed.as_ref().map(|_| format!("({})", e.new_side(new).trim())).unwrap_or_else(|| e.new_side(new)))).collect();
    format!("({})", if parts.is_empty() { "true".to_string() } else { parts.join(" && ") })
}

/// The Java for two objects having the same fields, as [`compare_fields`] compares them.
fn fields_source(old: &str, new: &str, old_fields: &Fields, fields: &Fields) -> String {
    let parts: Vec<String> = fields
        .fields
        .iter()
        .zip(&old_fields.fields)
        .map(|((name, kind), (old_name, old_kind))| {
            let (x, y) = (format!("{old}.{old_name}"), format!("{new}.{name}"));
            match (kind, old_kind) {
                (FieldKind::Value(Type::Float | Type::Double), _) => format!("({x} == {y} || ({x} != {x} && {y} != {y}))"),
                (FieldKind::Value(_), _) => format!("{x} == {y}"),
                (FieldKind::Array(_), _) => format!("java.util.Arrays.equals({x}, {y})"),
                (FieldKind::Object(inner), FieldKind::Object(old_inner)) => format!("({x} == null ? {y} == null : {y} != null && {})", fields_source(&x, &y, old_inner, inner)),
                (FieldKind::Object(_), _) => "false".to_string(),
            }
        })
        .collect();
    if parts.is_empty() {
        "true".to_string()
    } else {
        parts.join(" && ")
    }
}

/// `text` with each component of `record` read from `name` as an accessor call, `previous.tokens` as
/// `previous.tokens()`, for the statement as Java.
fn accessor_calls(text: &str, name: &str, record: &RecordType) -> String {
    let mut out = String::new();
    let mut rest = text;
    while let Some(i) = rest.find(&format!("{name}.")) {
        let after = i + name.len() + 1;
        let end = after + rest[after..].find(|c: char| !(c.is_alphanumeric() || c == '_' || c == '$')).unwrap_or(rest.len() - after);
        let preceded = rest[..i].chars().next_back().is_some_and(|c| c.is_alphanumeric() || c == '_' || c == '$' || c == '.');
        let component = &rest[after..end];
        out.push_str(&rest[..end]);
        if !preceded && record.components.iter().any(|(c, _)| c == component) && !rest[end..].starts_with('(') {
            out.push_str("()");
        }
        rest = &rest[end..];
    }
    out.push_str(rest);
    out
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
    /// The same class with the call replaced by the assertion's failure: an input the assumption admits violates
    /// it, and a proof of it is a proof that the assumption admits no input in the domain (see `Harness::probe`).
    pub probe: Vec<u8>,
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
    let layout = Layout { receiver: None, args: (0..params.len()).map(Slot::Plain).collect(), params: params.to_vec(), result: (None, None), result_fields: (None, None), result_equations: None, choices: Vec::new(), identity_relations: Vec::new() };
    generate_property_over(class_internal, method, &layout, ret, assume, assertion, signals, max_array_length)
}

/// [`generate_property`] for a static method whose arguments are laid out as `layout` (step H2 of
/// `llm-dlc/loops/foundations-heap.md`): an object parameter made by its constructor from the harness's flat
/// parameters, its leaves, and null or the same object as an earlier one where the layout's choices say so; an
/// input a constructor rejects is outside the property, and skipped. The expressions see each argument by its name,
/// an object's fields by their paths (`l.price.cents`, `\old(l.quantity)`), and an object `result`'s, whose fields
/// are `layout.result_fields.0`; an input on which the assumption throws (a path through null) is outside it too.
#[allow(clippy::too_many_arguments)] // the parts of a property, as the command line takes them
pub fn generate_property_over(class_internal: &str, method: &str, layout: &Layout, ret: &Type, assume: Option<&str>, assertion: Option<&str>, signals: &[Signal], max_array_length: u32) -> Result<PropertyHarness, Error> {
    crate::phases::timed(crate::phases::Step::Harness, || generate_property_untimed(class_internal, method, layout, ret, assume, assertion, signals, max_array_length))
}

#[allow(clippy::too_many_arguments)]
fn generate_property_untimed(class_internal: &str, method: &str, layout: &Layout, ret: &Type, assume: Option<&str>, assertion: Option<&str>, signals: &[Signal], max_array_length: u32) -> Result<PropertyHarness, Error> {
    let mut harness = generate_property_in(class_internal, method, layout, ret, assume, assertion, signals, max_array_length, false)?;
    if assume.is_some() {
        harness.probe = generate_property_in(class_internal, method, layout, ret, assume, assertion, signals, max_array_length, true)?.bytes;
    }
    Ok(harness)
}

#[allow(clippy::too_many_arguments)]
fn generate_property_in(class_internal: &str, method: &str, layout: &Layout, ret: &Type, assume: Option<&str>, assertion: Option<&str>, signals: &[Signal], max_array_length: u32, probe: bool) -> Result<PropertyHarness, Error> {
    let params = &layout.params;
    let target_types = layout.target_types();
    let descriptor = format!("({}){}", target_types.iter().map(Type::descriptor).collect::<String>(), ret.descriptor());
    let check_descriptor = format!("({})V", params.iter().map(|p| p.ty.descriptor()).collect::<String>());
    let arg_slots: u16 = params.iter().map(|p| p.ty.slots()).sum();
    let is_void = *ret == Type::Void;
    let callee = Callee::of(class_internal, method, &descriptor, &target_types, ret);
    // Each object argument, made from its leaves before anything else, in a local of its own after the flat
    // parameters (step H2).
    let records = layout.records();
    let object_slot = |i: usize| arg_slots + i as u16;
    let base = arg_slots + records.len() as u16;

    // The names the expressions see: the arguments (an object by its local), then the result.
    let mut arg_names: Vec<Param> = Vec::new();
    let mut objects: Vec<(String, Fields)> = Vec::new();
    for slot in &layout.args {
        match slot {
            Slot::Plain(i) => arg_names.push(params[*i].clone()),
            Slot::Record { name, record, .. } => {
                let at = records.iter().position(|r| *r == slot).expect("a record");
                arg_names.push(Param { name: name.clone(), ty: Type::Object(record.class.clone()), slot: object_slot(at) });
                if let Some(fields) = &record.fields {
                    objects.push((name.clone(), fields.clone()));
                }
            }
        }
    }
    let mut names = arg_names.clone();
    if !is_void {
        names.push(Param { name: RESULT.into(), ty: ret.clone(), slot: base });
        if let Some(fields) = &layout.result_fields.0 {
            objects.push((RESULT.into(), fields.clone()));
        }
    }
    let assertion_text = match assertion {
        Some(a) => a.to_string(),
        None if *ret == Type::Boolean => RESULT.to_string(),
        None if !signals.is_empty() => "true".to_string(),
        None => return Err(Error::new(format!("the method returns {}, so the property needs an assertion (--assert) over the parameters and `result`", ret.java_name()))),
    };
    // Locals after the parameters (and the objects): result, e, expected, a copy of each array parameter for \old
    // (taken only when the assertion reads it); quantifiers, and the fields read under \old, take theirs after those.
    let ret_kind = kind_of(ret);
    let result = base;
    let e = result + if is_void { 0 } else { ret.slots() };
    let expected = e + 1;
    let copies: Vec<(u16, u16)> = arg_names.iter().filter(|p| matches!(p.ty, Type::Array(_))).enumerate().map(|(i, p)| (p.slot, expected + 1 + i as u16)).collect();
    let first_free = expected + 1 + copies.len() as u16;
    let assume_expr = match assume {
        Some(src) => Some(expr::parse_over_objects(src, &arg_names, callee.as_ref(), first_free, None, &objects).and_then(|e| if e.ty() == expr::Ty::Boolean { Ok(e) } else { Err(Error::new("the expression must be boolean")) }).map_err(|e| Error::new(format!("in the assumption: {e}")))?),
        None => None,
    };
    let assertion_expr = expr::parse_over_objects(&assertion_text, &names, callee.as_ref(), first_free, Some(&copies), &objects).map_err(|e| Error::new(format!("in the assertion: {e}")))?;
    if assertion_expr.ty() != expr::Ty::Boolean {
        return Err(Error::new("in the assertion: the expression must be boolean"));
    }
    let old: Vec<(u16, u16)> = copies.iter().copied().filter(|(_, copy)| assertion_expr.mentions(*copy)).collect();
    let mut signal_exprs = Vec::new();
    for signal in signals {
        if signal.class.is_empty() || signal.class.contains(|c: char| c.is_whitespace() || c == ';' || c == '[') {
            return Err(Error::new(format!("in the throws clause: {:?} is not a class name", signal.java_name())));
        }
        let when = expr::parse_over_objects(&signal.when, &arg_names, callee.as_ref(), first_free, None, &objects).and_then(|e| if e.ty() == expr::Ty::Boolean { Ok(e) } else { Err(Error::new("the expression must be boolean")) }).map_err(|e| Error::new(format!("in the throws clause `{}`: {e}", signal.render())))?;
        signal_exprs.push((signal.clone(), when));
    }

    let mut writer = ClassWriter::new(PROPERTY_CLASS);
    writer.source_file = Some(format!("{PROPERTY_CLASS}.java"));
    writer.default_constructor();
    let mut code = CodeBuilder::new();
    code.max_locals = arg_slots;
    code.max_stack = 16 + 4 * arg_slots;

    // The objects (step H2), from their leaves: null, or the same object as an earlier one that is not null, where
    // a choice says so, and otherwise each its own; an input a constructor rejects is outside the property.
    if !records.is_empty() {
        let (build_start, build_end, built) = (code.label(), code.label(), code.label());
        code.bind(build_start);
        for (i, slot) in records.iter().enumerate() {
            let Slot::Record { name, record, first, .. } = slot else { unreachable!("records() returns records") };
            let local = object_slot(i);
            let done = code.label();
            if let Some(c) = layout.choice(name) {
                if let Some(flag) = c.null {
                    let own = code.label();
                    code.load(Kind::Int, params[flag].slot);
                    code.if_zero(Cond::Eq, own);
                    code.op(0x01); // aconst_null
                    code.store(Kind::Ref, local);
                    code.goto(done);
                    code.bind(own);
                }
                for (other, flag) in &c.same {
                    let next = code.label();
                    let at = records.iter().position(|s| matches!(s, Slot::Record { name: n, .. } if n == other)).expect("a parameter of the group");
                    code.load(Kind::Int, params[*flag].slot);
                    code.if_zero(Cond::Eq, next);
                    code.load(Kind::Ref, object_slot(at));
                    code.if_null(next);
                    code.load(Kind::Ref, object_slot(at));
                    code.store(Kind::Ref, local);
                    code.goto(done);
                    code.bind(next);
                }
            }
            emit_construct(&mut code, &mut writer.pool, record, None, params, &mut record.leaves(*first).into_iter());
            code.store(Kind::Ref, local);
            code.bind(done);
        }
        code.bind(build_end);
        code.goto(built);
        let handler = code.label();
        code.bind(handler);
        code.op(0x57); // pop the exception
        code.return_(None);
        for exception in EXCEPTIONS.iter().chain(["java/lang/Throwable"].iter()) {
            let catch_type = writer.pool.class(exception);
            code.handler(build_start, build_end, handler, Some(catch_type));
        }
        code.bind(built);
    }

    // The assumption: return on the inputs the property is not about. Over objects, an input on which it throws
    // (a field path through null) is not among them either.
    if let Some(assume) = &assume_expr {
        let proceed = code.label();
        let (start, end) = (code.label(), code.label());
        code.bind(start);
        expr::emit(assume, &mut code, &mut writer.pool);
        code.bind(end);
        code.if_zero(Cond::Ne, proceed);
        let skip = code.label();
        code.bind(skip);
        if !records.is_empty() {
            // The handler's stack holds the exception; the normal way out has nothing on it.
            let threw = code.label();
            code.return_(None);
            code.bind(threw);
            code.op(0x57); // pop the exception
            for exception in EXCEPTIONS {
                let catch_type = writer.pool.class(exception);
                code.handler(start, end, threw, Some(catch_type));
            }
        }
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
        // A null array has no copy: the copy is null too, where a domain lets the array be null.
        code.op(0x01); // aconst_null
        code.store(Kind::Ref, *copy);
        code.load(Kind::Ref, *slot);
        code.if_null(done);
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
    // The field paths the assertion reads under \old (step H2), each read before the call into its local, with
    // whether it could be: a path through null leaves 0 there, and reading it in the assertion throws.
    for (path, value) in assertion_expr.old_fields() {
        let kind = if path.ty == Type::Long { Kind::Long } else { Kind::Int };
        if kind == Kind::Long {
            code.op(0x09); // lconst_0
        } else {
            code.iconst(0);
        }
        code.store(kind, value);
        code.iconst(0);
        code.store(Kind::Int, value + 2);
        let (start, end, read, threw) = (code.label(), code.label(), code.label(), code.label());
        code.bind(start);
        path.emit(&mut code, &mut writer.pool);
        code.bind(end);
        code.store(kind, value);
        code.iconst(1);
        code.store(Kind::Int, value + 2);
        code.goto(read);
        code.bind(threw);
        code.op(0x57); // pop the exception
        let npe = writer.pool.class("java/lang/NullPointerException");
        code.handler(start, end, threw, Some(npe));
        code.bind(read);
    }
    let try_start = code.label();
    let try_end = code.label();
    let join = code.label();
    // The probe: every input the assumption admits fails it, and the call below is never reached.
    if probe {
        emit_failure(&mut code, &mut writer.pool);
    }
    code.bind(try_start);
    for p in &arg_names {
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
    let source = if records.is_empty() { property_source(class_internal, method, params, ret, assume, &assertion_text, signals) } else { property_source_over(class_internal, method, layout, ret, assume, &assertion_text, signals) };
    Ok(PropertyHarness { bytes: writer.to_bytes(), probe: Vec::new(), source, assume: assume_expr, assertion: assertion_expr, assertion_text, signals: signal_exprs, params: arg_names, old })
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

/// [`property_source`] for a method whose arguments are laid out as `layout` (step H2): the harness's parameters are
/// the leaves of each object's construction and the choices' flags (`l_price_cents`, `l_null`), and each object is
/// made from them before the property is checked.
pub fn property_source_over(class_internal: &str, method: &str, layout: &Layout, ret: &Type, assume: Option<&str>, assertion: &str, signals: &[Signal]) -> String {
    let flat: Vec<Param> = layout.params.iter().map(|p| Param { name: p.name.replace('.', "_"), ty: p.ty.clone(), slot: p.slot }).collect();
    let param_list = flat.iter().map(|p| format!("{} {}", p.ty.java_name(), p.name)).collect::<Vec<_>>().join(", ");
    let args: Vec<String> = layout
        .args
        .iter()
        .map(|s| match s {
            Slot::Plain(i) => flat[*i].name.clone(),
            Slot::Record { name, .. } => name.clone(),
        })
        .collect();
    let plain: Vec<Param> = args.iter().map(|a| Param { name: a.clone(), ty: Type::Int, slot: 0 }).collect();
    let mut s = property_source(class_internal, method, &plain, ret, assume, assertion, signals);
    let mut objects = String::from("        // The objects, from their leaves; an input a constructor rejects is outside the property.\n");
    for slot in layout.records() {
        let Slot::Record { name, record, first, .. } = slot else { continue };
        let mut made = construction_source(record, "", &mut record.leaf_indices(*first).into_iter().map(|i| &flat[i]));
        if let Some(c) = layout.choice(name) {
            for (other, flag) in c.same.iter().rev() {
                made = format!("{} && {other} != null ? {other} : {made}", flat[*flag].name);
            }
            if let Some(flag) = c.null {
                made = format!("{} ? null : {made}", flat[flag].name);
            }
        }
        objects.push_str(&format!("        {} {name};\n        try {{ {name} = {made}; }} catch (Throwable t) {{ return; }}\n", record.java_name()));
    }
    // The plain rendering's parameter list gives way to the leaves', and the objects are made first.
    let header = format!("    public static void {METHOD}({}) {{\n", plain.iter().map(|p| format!("int {}", p.name)).collect::<Vec<_>>().join(", "));
    s = s.replacen(&header, &format!("    public static void {METHOD}({param_list}) {{\n{objects}"), 1);
    if assume.is_some() {
        s = s.replacen("{ return; } // the inputs the property is about", "{ return; } // the inputs the property is about (one on which it throws is not among them)", 1);
    }
    s.replacen("/* \\old(a) is the array a as it was before the call: the class file copies it first. */", "/* \\old(a) is the array a, and \\old(l.f) the field l.f, as it was before the call: the class file copies it first. */", 1)
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
        Layout { receiver: None, args: (0..params.len()).map(Slot::Plain).collect(), params: params.to_vec(), result: (None, None), result_fields: (None, None), result_equations: None, choices: Vec::new(), identity_relations: Vec::new() }
    }

    #[test]
    fn a_choice_of_null_or_the_same_object_is_a_flag_after_the_leaves_and_never_makes_a_non_nullable_parameter_null() {
        let money = RecordType::made("m/Money", vec![("cents".into(), Type::Long)], Vec::new(), Fields { class: "m/Money".into(), fields: vec![("cents".into(), FieldKind::Value(Type::Long))] });
        let names = ["a".to_string(), "b".to_string(), "n".to_string(), "c".to_string()];
        let types = [Type::Object("m/Money".into()), Type::Object("m/Money".into()), Type::Int, Type::Object("m/Money".into())];
        let both = Some((money.clone(), Some(money.clone())));
        let mut layout = Layout::new(None, &names, &types, &[both.clone(), both.clone(), None, both], (None, None));
        let groups = alias_groups(&[("c".into(), "b".into()), ("a".into(), "b".into())], &names);
        assert_eq!(groups, vec![vec!["a".to_string(), "b".into(), "c".into()]], "closed under the chain, in parameter order");
        layout.choose(&["a".into()], &groups).unwrap();
        let flat: Vec<&str> = layout.params.iter().map(|p| p.name.as_str()).collect();
        assert_eq!(flat, vec!["a.cents", "b.cents", "n", "c.cents", "a.null", "b.same.a", "c.same.a", "c.same.b"], "the leaves keep their places");
        assert_eq!(layout.flags(), vec![4, 5, 6, 7]);
        assert_eq!(layout.domain(8), "a: a Money made by its constructor, Money(cents: long), from any arguments it accepts, or null × b: a Money made by its constructor, Money(cents: long), from any arguments it accepts × n: int × c: a Money made by its constructor, Money(cents: long), from any arguments it accepts; a, b and c may be the same object");
        let made = |set: &[usize]| layout.made(&|i| set.contains(&i)).into_iter().map(|(_, m)| m).collect::<Vec<_>>();
        assert_eq!(made(&[]), vec![Made::Own, Made::Own, Made::Own]);
        assert_eq!(made(&[4, 5]), vec![Made::Null, Made::Own, Made::Own], "b may not be null, so a null a is passed over");
        assert_eq!(made(&[5, 7]), vec![Made::Own, Made::Same("a".into()), Made::Same("a".into())], "the same as b is the same as the a it is");
        assert_eq!(made(&[4, 5, 7]), vec![Made::Null, Made::Own, Made::Same("b".into())]);
        assert!(layout.choose(&["n".into()], &[]).unwrap_err().contains("--nullable n: n is a int"));
        let mut other = Layout::new(None, &names[..2], &types[..2], &[Some((money.clone(), None)), Some((money.clone(), Some(money.clone())))], (None, None));
        assert!(other.choose(&["a".into()], &[]).unwrap_err().contains("by --before-arguments"));

        let harness = generate("m/Kernel", "f", &layout, &Type::Void, None, 8, None).unwrap();
        assert!(harness.source.contains("public static void check(long a_cents, long b_cents, int n, long c_cents, boolean a_null, boolean b_same_a, boolean c_same_a, boolean c_same_b)"), "{}", harness.source);
        assert!(harness.source.contains("c_after = c_same_a && a_after != null ? a_after : c_same_b && b_after != null ? b_after : new m.Money(c_cents);"), "{}", harness.source);
        assert!(harness.source.contains("a_before = a_null ? null : new before.m.Money(a_cents);"), "{}", harness.source);
        assert!(harness.source.contains(" && (a_after == null || a_before.cents == a_after.cents)"), "{}", harness.source);
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let code = class.method(METHOD, "(JJIJZZZZ)V").expect("check method with the flags last").code.as_ref().unwrap();
        let insns = code.instructions().unwrap();
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
    }

    #[test]
    fn a_property_over_objects_makes_them_from_their_leaves_and_reads_their_fields_now_and_before_the_call() {
        let money_fields = Fields { class: "m/Money".into(), fields: vec![("cents".into(), FieldKind::Value(Type::Long))] };
        let money = RecordType::made("m/Money", vec![("cents".into(), Type::Long)], Vec::new(), money_fields.clone());
        let line_fields = Fields { class: "m/Line".into(), fields: vec![("price".into(), FieldKind::Object(Box::new(money_fields))), ("quantity".into(), FieldKind::Value(Type::Int))] };
        let line = RecordType::made("m/Line", vec![("price".into(), Type::Object("m/Money".into())), ("quantity".into(), Type::Int)], vec![money], line_fields.clone());
        let names = ["l".to_string(), "k".to_string(), "n".to_string()];
        let types = [Type::Object("m/Line".into()), Type::Object("m/Line".into()), Type::Int];
        let mut layout = Layout::new(None, &names, &types, &[Some((line.clone(), None)), Some((line, None)), None], (None, None));
        assert!(layout.choose(&["l".into()], &[]).unwrap_err().contains("by --before-arguments"), "a regression check's rule");
        assert!(layout.choose_in(&["n".into()], &[], true).unwrap_err().contains("only an array parameter or an object made by its constructor may be null"));
        layout.choose_in(&["l".into()], &[vec!["l".into(), "k".into()]], true).unwrap();
        layout.result_fields.0 = Some(line_fields);
        let law = "result == k && result.quantity == \\old(l.quantity) + n && l.price != null";
        let harness = generate_property_over("m/Kernel", "f", &layout, &Type::Object("m/Line".into()), Some("l.price.cents > 0"), Some(law), &[], 8).unwrap();
        assert!(harness.source.contains("public static void check(long l_price_cents, int l_quantity, long k_price_cents, int k_quantity, int n, boolean l_null, boolean k_same_l)"), "{}", harness.source);
        assert!(harness.source.contains("try { k = k_same_l && l != null ? l : new m.Line(new m.Money(k_price_cents), k_quantity); } catch (Throwable t) { return; }"), "{}", harness.source);
        assert!(harness.source.contains("try { l = l_null ? null : new m.Line(new m.Money(l_price_cents), l_quantity); }"), "{}", harness.source);
        assert!(harness.source.contains("result = m.Kernel.f(l, k, n);"), "{}", harness.source);
        assert!(harness.source.contains("(one on which it throws is not among them)"), "{}", harness.source);
        let olds = harness.assertion.old_fields();
        assert_eq!(olds.len(), 1);
        assert_eq!((olds[0].0.shown.as_str(), olds[0].0.steps.len()), ("l.quantity", 1));
        assert!(harness.assertion.reads_objects() && harness.assume.as_ref().unwrap().reads_objects());
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let code = class.method(METHOD, "(JIJIIZZ)V").expect("the leaves, n, then the flags").code.as_ref().unwrap();
        let insns = code.instructions().unwrap();
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        // The plain harness is as it was: no objects, no handlers of theirs.
        let params = params(&["a".to_string()], &[Type::Int]);
        let plain = generate_property("m/Kernel", "g", &params, &Type::Int, Some("a > 0"), Some("result > 0"), &[], 8).unwrap();
        let plain_class = ClassFile::parse(&plain.bytes).unwrap();
        assert_eq!(plain_class.method(METHOD, "(I)V").unwrap().code.as_ref().unwrap().exception_table.len(), 2 * EXCEPTIONS.len(), "the call's and the assertion's");
    }

    #[test]
    fn lays_out_a_record_receiver_argument_and_result_as_their_components() {
        let backoff = RecordType::record("net/example/Backoff", vec![("baseMillis".into(), Type::Long), ("capMillis".into(), Type::Long)]);
        let window = RecordType::record("net/example/Window", vec![("from".into(), Type::Int), ("open".into(), Type::Boolean)]);
        let names = ["attempt".to_string(), "window".to_string()];
        let types = [Type::Int, Type::Object("net/example/Window".into())];
        let layout = Layout::new(Some((backoff.clone(), Some(backoff.clone()))), &names, &types, &[None, Some((window.clone(), Some(window.clone())))], (Some(window.clone()), Some(window.clone())));
        assert_eq!(layout.params.iter().map(|p| (p.name.as_str(), p.slot)).collect::<Vec<_>>(), vec![("this.baseMillis", 0), ("this.capMillis", 2), ("attempt", 4), ("window.from", 5), ("window.open", 6)]);
        assert_eq!(layout.types(), vec![Type::Long, Type::Long, Type::Int, Type::Int, Type::Boolean]);
        assert_eq!(layout.target_types(), vec![Type::Int, Type::Object("net/example/Window".into())]);
        assert_eq!(layout.domain(8), "this: Backoff(baseMillis: long, capMillis: long) × attempt: int × window: Window(from: int, open: boolean)");
        assert_eq!(layout.records().len(), 2);
        assert_eq!(backoff.constructor(), "(JJ)V");
        assert!(backoff.same_shape(&RecordType::record("x/Y", vec![("a".into(), Type::Long), ("b".into(), Type::Long)])), "renamed components are the same value");
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
        let batch = RecordType::record("net/example/Batch", vec![("start".into(), Type::Long), ("size".into(), Type::Int)]);
        let names = ["failedIndex".to_string()];
        let layout = Layout::new(Some((batch.clone(), None)), &names, &[Type::Int], &[None], (None, None));
        assert!(!layout.before_receiver());
        assert_eq!(layout.before_descriptor(&[Type::Long, Type::Int, Type::Int], &Type::Long), "(JII)J");
        let previous = BeforeMethod {
            owner: "net/example/BatchCommit".into(),
            method: "offsetToCommit".into(),
            descriptor: "(JII)J".into(),
            params: vec![Type::Long, Type::Int, Type::Int],
            names: vec!["batchStart".into(), "batchSize".into(), "failedIndex".into()],
            arguments: Some("this.start, this.size, failedIndex".into()),
            receiver: None,
            records: Vec::new(),
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

    /// A record's method made static: the previous version's receiver is built by a constructor call among the
    /// expressions, under before/, inside the handler that skips an input a constructor rejects.
    #[test]
    fn builds_the_previous_versions_receiver_from_the_new_parameters() {
        let window = RecordType::record("net/example/Window", vec![("lo".into(), Type::Int), ("hi".into(), Type::Int)]);
        let params = params(&["lo".into(), "hi".into(), "x".into()], &[Type::Int, Type::Int, Type::Int]);
        let layout = flat(&params);
        let previous = BeforeMethod {
            owner: "net/example/Window".into(),
            method: "clamp".into(),
            descriptor: "(I)I".into(),
            params: vec![Type::Int],
            names: vec!["x".into()],
            arguments: Some("new Window(lo, hi), x".into()),
            receiver: Some(window.clone()),
            records: Vec::new(),
            ret: Type::Int,
            relation: None,
        };
        assert_eq!(previous.display("net/example/Windows"), "net.example.Window#clamp(x) on new Window(lo, hi)");
        // What each flat argument of the previous version is computed from, the receiver's components first.
        assert_eq!(previous.argument_sources(), ["lo", "hi", "x"]);
        let nested = BeforeMethod { arguments: Some("new Window(Math.min(lo, hi), hi + 1), x * 2".into()), ..previous.clone() };
        assert_eq!(nested.argument_sources(), ["Math.min(lo, hi)", "hi + 1", "x * 2"]);
        assert!(BeforeMethod { arguments: None, ..previous.clone() }.argument_sources().is_empty());
        assert_eq!(previous.argument_types(), vec![Type::Object("net/example/Window".into()), Type::Int]);
        let harness = generate("net/example/Windows", "clamp", &layout, &Type::Int, None, 8, Some(&previous)).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(III)V").expect("check method over the parameters");
        let insns = check.code.as_ref().unwrap().instructions().unwrap();
        use crate::classfile::Insn;
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::New(_))).count(), 2, "the previous version's record, and the AssertionError");
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::InvokeVirtual(_))).count(), 1, "the previous version on its receiver");
        assert_eq!(insns.iter().filter(|(_, i)| matches!(i, Insn::InvokeStatic(_))).count(), 1, "the new version");
        assert!(harness.source.contains("before.net.example.Window this_ = new before.net.example.Window(lo, hi); int x_ = x;"), "{}", harness.source);
        assert!(harness.source.contains("try { a = this_.clamp(x_); }"), "{}", harness.source);
        assert!(harness.source.contains("try { b = net.example.Windows.clamp(lo, hi, x); }"), "{}", harness.source);
        // The receiver must be built, and from as many values as the record has components.
        let flat_args = BeforeMethod { arguments: Some("lo, hi, x".into()), ..previous.clone() };
        assert!(generate("net/example/Windows", "clamp", &layout, &Type::Int, None, 8, Some(&flat_args)).unwrap_err().to_string().contains("build its receiver from the new parameters as the first argument, new Window(lo, hi)"));
        let short = BeforeMethod { arguments: Some("new Window(lo), x".into()), ..previous.clone() };
        assert!(generate("net/example/Windows", "clamp", &layout, &Type::Int, None, 8, Some(&short)).unwrap_err().to_string().contains("Window has 2 components, 1 given"));
        let other = BeforeMethod { arguments: Some("new Range(lo, hi), x".into()), ..previous.clone() };
        assert!(generate("net/example/Windows", "clamp", &layout, &Type::Int, None, 8, Some(&other)).unwrap_err().to_string().contains("build its receiver"));
        let mistyped = BeforeMethod { arguments: Some("new Window(lo, hi), x > 0".into()), ..previous.clone() };
        assert!(generate("net/example/Windows", "clamp", &layout, &Type::Int, None, 8, Some(&mistyped)).unwrap_err().to_string().contains("argument 1 of clamp must be int"));
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
        // The probe is the same class up to the calls, which it never reaches: it throws first.
        let probe = ClassFile::parse(&harness.probe).unwrap();
        let probe_insns = probe.method(METHOD, "(JI)V").unwrap().code.as_ref().unwrap().instructions().unwrap();
        let first_throw = probe_insns.iter().position(|(_, i)| matches!(i, crate::classfile::Insn::AThrow)).unwrap();
        let first_call = probe_insns.iter().position(|(_, i)| matches!(i, crate::classfile::Insn::InvokeStatic(_))).unwrap();
        assert!(first_throw < first_call, "the probe throws at {first_throw}, before the call at {first_call}");
        assert!(skips_inputs(&flat(&params), Some("seats >= 8"), None) && !skips_inputs(&flat(&params), None, None));
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
            receiver: None,
            records: Vec::new(),
            ret: Type::Int,
            relation: None,
        };
        let harness = generate("net/example/Writers", "winner", &flat(&params), &Type::Int, None, 8, Some(&before)).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(JJII)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        // The handlers around the arguments' computation (one per class JBMC tells apart, and Throwable), and the
        // two versions' handlers.
        assert_eq!(code.exception_table.len(), EXCEPTIONS.len() + 1 + 2 * EXCEPTIONS.len());
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
            receiver: None,
            records: Vec::new(),
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
    fn generates_a_harness_relating_record_results_by_their_components() {
        // The record result gained a component: the relation names the components of both records.
        let old = RecordType::record("fixtures/Bucket", vec![("tokens".into(), Type::Long), ("lastNanos".into(), Type::Long)]);
        let new = RecordType::record("fixtures/Bucket", vec![("tokens".into(), Type::Long), ("lastNanos".into(), Type::Long), ("refills".into(), Type::Int)]);
        let params = params(&["tokens".into(), "earned".into()], &[Type::Long, Type::Long]);
        let layout = Layout { result: (Some(new.clone()), Some(old.clone())), ..flat(&params) };
        let before = BeforeMethod {
            owner: "fixtures/Bucket".into(),
            method: "credited".into(),
            descriptor: "(JJ)Lfixtures/Bucket;".into(),
            params: vec![Type::Long, Type::Long],
            names: vec!["tokens".into(), "earned".into()],
            arguments: None,
            receiver: None,
            records: Vec::new(),
            ret: Type::Object("fixtures/Bucket".into()),
            relation: Some("previous.tokens == result.tokens && previous.lastNanos == result.lastNanos && result.refills >= 0".into()),
        };
        let harness = generate("fixtures/Bucket", "credited", &layout, &Type::Object("fixtures/Bucket".into()), None, 8, Some(&before)).unwrap();
        let class = ClassFile::parse(&harness.bytes).unwrap();
        let check = class.method(METHOD, "(JJ)V").expect("check method");
        let code = check.code.as_ref().unwrap();
        let relation = harness.relation.as_ref().expect("relation");
        // Slots: the two longs, a, ea, b, eb, the index, the previous version's arguments (four slots); the
        // components after: two longs of the previous record, two longs and an int of the new one.
        assert_eq!((relation.previous, relation.result), (4, 6));
        let (previous_slots, result_slots) = (&relation.previous_components.as_ref().unwrap().1, &relation.result_components.as_ref().unwrap().1);
        assert_eq!(previous_slots, &vec![13, 15]);
        assert_eq!(result_slots, &vec![17, 19, 21]);
        assert_eq!(relation.slots_end, 22);
        assert_eq!(code.max_locals, 22);
        let insns = code.instructions().unwrap();
        let reads: Vec<String> = insns
            .iter()
            .filter_map(|(_, i)| match i {
                crate::classfile::Insn::GetField(index) => class.pool.member(*index).ok().map(|m| format!("{}.{}", m.owner, m.name)),
                _ => None,
            })
            .collect();
        assert_eq!(reads, vec!["before/fixtures/Bucket.tokens", "before/fixtures/Bucket.lastNanos", "fixtures/Bucket.tokens", "fixtures/Bucket.lastNanos", "fixtures/Bucket.refills"]);
        let pcs: std::collections::HashSet<u32> = insns.iter().map(|(pc, _)| *pc).collect();
        for (_, insn) in &insns {
            for t in insn.targets() {
                assert!(pcs.contains(&t), "target {t} is not an instruction");
            }
        }
        assert!(harness.source.contains("before.fixtures.Bucket previous = a; fixtures.Bucket result = b;"), "{}", harness.source);
        assert!(harness.source.contains("(two null records agree, one alone does not)"), "{}", harness.source);
        assert!(harness.source.contains("assert ea == eb && (ea != 0 || (previous.tokens() == result.tokens() && previous.lastNanos() == result.lastNanos() && result.refills() >= 0));"), "{}", harness.source);
        // A result that became a record is related to the value it was.
        let was_long = BeforeMethod { descriptor: "(JJ)J".into(), ret: Type::Long, relation: Some("previous == result.tokens".into()), ..before.clone() };
        let layout = Layout { result: (Some(new.clone()), None), ..flat(&params) };
        let harness = generate("fixtures/Bucket", "credited", &layout, &Type::Object("fixtures/Bucket".into()), None, 8, Some(&was_long)).unwrap();
        assert!(harness.source.contains("long previous = a; fixtures.Bucket result = b;"), "{}", harness.source);
        assert!(harness.source.contains("(a null record does not)"), "{}", harness.source);
        assert!(harness.source.contains("(ea != 0 || (previous == result.tokens()));"), "{}", harness.source);
        let relation = harness.relation.as_ref().expect("relation");
        assert!(relation.previous_components.is_none());
        assert_eq!(relation.result_components.as_ref().unwrap().1, vec![14, 16, 18], "a is a long now, two slots");
        // A component neither record has is unknown.
        let unknown = BeforeMethod { relation: Some("previous.refills == result.refills".into()), ..before.clone() };
        let problem = generate("fixtures/Bucket", "credited", &Layout { result: (Some(new.clone()), Some(old.clone())), ..flat(&params) }, &Type::Object("fixtures/Bucket".into()), None, 8, Some(&unknown)).unwrap_err().to_string();
        assert!(problem.contains("in the result relation: unknown name \"previous\""), "{problem}");
        // The accessor rewriting leaves other names alone.
        assert_eq!(accessor_calls("previous.tokens + previousTokens.x - result.tokens()", "previous", &old), "previous.tokens() + previousTokens.x - result.tokens()");
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
