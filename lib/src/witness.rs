//! What is done with a counterexample once JBMC has found one: it is replayed in the interpreter to show what the
//! method does on it, shrunk by running the harness class JBMC checked on smaller inputs, and rendered as Java
//! would write it. Shared by the regression proofs ([`crate::equivalence`]) and the property proofs
//! ([`crate::property`]).

use std::collections::BTreeMap;
use std::path::Path;

use serde::Serialize;

use crate::classfile::{MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::harness::{self, Layout, Param, Slot};
use crate::interp::{render, Fault, Machine, Object, Ref, Value};
use crate::jbmc::Argument;
use crate::shrink::{self, Shrunk};
use crate::Error;

/// A witness argument as Java would write it: `17`, `'a'`, `[3, 5, 8]`, `"VI\u0000"`, `null`; the same object as
/// argument `i` is `@i` (by name in [`call`]).
pub fn argument(argument: &Argument, t: &Type) -> String {
    match (argument, t) {
        (Argument::Scalar(v), _) => render::witness(*v, t),
        (Argument::Array(data), Type::Array(element)) => array(data, element),
        (Argument::Array(_), _) => "<array>".into(),
        (Argument::String(units), _) => string_literal(units),
        (Argument::Null, _) => "null".into(),
        (Argument::Same(i), _) => format!("@{i}"),
    }
}

/// A String's code units as a Java literal: printable ASCII as itself, every other unit (an isolated surrogate
/// included) as its `\uXXXX` escape, so that the text names every unit exactly.
pub fn string_literal(units: &[u16]) -> String {
    let mut out = String::from("\"");
    for &u in units {
        match u {
            0x22 => out.push_str("\\\""),
            0x5c => out.push_str("\\\\"),
            0x20..=0x7e => out.push(char::from(u as u8)),
            _ => out.push_str(&format!("\\u{u:04x}")),
        }
    }
    out.push('"');
    out
}

/// An argument as [`call`] shows it among `names`: the same object as an earlier argument by that one's name.
fn shown(argument: &Argument, t: &Type, names: &[&str]) -> String {
    match argument {
        Argument::Same(i) => {
            let what = if crate::values::is_string(t) { "String" } else { "array" };
            names.get(*i).map(|n| format!("the same {what} as {n}")).unwrap_or_else(|| format!("@{i}"))
        }
        other => self::argument(other, t),
    }
}

/// The locals and the arrays by slot that an expression over `params` is evaluated on ([`harness::expr::eval_with`])
/// for `arguments`: each array a distinct reference in its local (the same one for an argument that is the same
/// array as an earlier one, and null for a null one), with its elements, `arrays_after` where the call left them.
pub fn locals_of(params: &[Param], arguments: &[Argument], arrays_after: &[(u16, Vec<Value>)]) -> (Vec<Value>, Vec<(u16, Vec<Value>)>) {
    let mut locals = Vec::new();
    let mut arrays = Vec::new();
    let mut refs: Vec<Value> = Vec::new();
    for (k, (a, p)) in arguments.iter().zip(params).enumerate() {
        let data = |slot: u16, data: &Vec<Value>| arrays_after.iter().find(|(s, _)| *s == slot).map(|(_, d)| d.clone()).unwrap_or_else(|| data.clone());
        let value = match a {
            Argument::Scalar(v) => *v,
            Argument::Array(d) => {
                arrays.push((p.slot, data(p.slot, d)));
                Value::Ref(k as Ref + 1)
            }
            // A String is a reference of its own, which no expression reads into.
            Argument::String(_) => Value::Ref(k as Ref + 1),
            Argument::Null => Value::Null,
            Argument::Same(i) => {
                if let Some((_, d)) = arrays.iter().find(|(s, _)| Some(*s) == params.get(*i).map(|q| q.slot)).cloned() {
                    arrays.push((p.slot, d));
                }
                refs.get(*i).copied().unwrap_or(Value::Null)
            }
        };
        refs.push(value);
        locals.push(value);
        if value.is_wide() {
            locals.push(Value::Int(0));
        }
    }
    (locals, arrays)
}

pub fn array(data: &[Value], element: &Type) -> String {
    format!("[{}]", data.iter().map(|v| render::witness(*v, element)).collect::<Vec<_>>().join(", "))
}

/// `method(a=[1, 2], n=3)`: the arguments by parameter name, and the rendering of each.
pub fn call(method: &str, params: &[Param], arguments: &[Argument]) -> (String, Vec<String>) {
    let names: Vec<&str> = params.iter().map(|p| p.name.as_str()).collect();
    let witnesses: Vec<String> = params.iter().zip(arguments).map(|(p, a)| shown(a, &p.ty, &names)).collect();
    let rendered = format!("{method}({})", params.iter().zip(&witnesses).map(|(p, w)| format!("{}={w}", p.name)).collect::<Vec<_>>().join(", "));
    (rendered, witnesses)
}

/// `method(this=Backoff[baseMillis=1, capMillis=1], attempt=63)`: the receiver and the arguments by name, a
/// record as Java prints it, and the rendering of each flat parameter.
pub fn call_in(method: &str, layout: &Layout, arguments: &[Argument]) -> (String, Vec<String>) {
    let names: Vec<&str> = layout.params.iter().map(|p| p.name.as_str()).collect();
    let witnesses: Vec<String> = layout.params.iter().zip(arguments).map(|(p, a)| shown(a, &p.ty, &names)).collect();
    let made = layout.made_on(arguments);
    let made_as = |name: &str| made.iter().find(|(n, _)| n == name).map(|(_, m)| m.clone()).unwrap_or(harness::Made::Own);
    let shown = |s: &Slot| match s {
        Slot::Plain(i) => format!("{}={}", layout.params[*i].name, witnesses[*i]),
        Slot::Record { name, record, first, .. } if record.is_made() => match made_as(name) {
            harness::Made::Null => format!("{name}=null"),
            harness::Made::Same(other) => format!("{name}=the same object as {other}"),
            harness::Made::Own => format!("{name}={}", recipe(record, &mut witnesses[*first..].iter())),
        },
        Slot::Record { name, record, first, .. } => {
            let components = record.components.iter().zip(&witnesses[*first..]).map(|((c, _), w)| format!("{c}={w}")).collect::<Vec<_>>().join(", ");
            format!("{name}={}[{components}]", record.simple_name())
        }
    };
    let mut rendered = format!("{method}({})", layout.receiver.iter().chain(layout.args.iter()).map(shown).collect::<Vec<_>>().join(", "));
    // The setup sequence (O3), which the call comes after.
    if !layout.setup.is_empty() {
        let calls = layout.setup_text(&|i| format!("{}={}", layout.params[i].name, witnesses[i]));
        rendered = format!("{rendered}, after the setup {}", calls.join(" then "));
    }
    (rendered, witnesses)
}

/// How an object made by its constructor is made, as Java writes it, from the renderings of its leaves in order:
/// `new Quote(new Money(5), 1)`.
fn recipe<'a>(record: &crate::harness::RecordType, leaves: &mut impl Iterator<Item = &'a String>) -> String {
    let mut nested = record.inner.iter();
    let args: Vec<String> = record
        .params
        .iter()
        .map(|(_, t)| match t {
            Type::Object(_) => nested.next().map(|r| recipe(r, leaves)).unwrap_or_default(),
            _ => leaves.next().cloned().unwrap_or_default(),
        })
        .collect();
    format!("new {}({})", record.simple_name(), args.join(", "))
}

/// A witness value with its Java type, exact: enough to pass it to the method again without reading the text.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Typed {
    /// The parameter's or component's name: `attempt`, `this`, `baseMillis`; among a witness's inputs, the
    /// harness's own name for it (`this.baseMillis`).
    pub name: String,
    /// The Java type: `int`, `long[]`, `net.example.retry.Backoff`.
    #[serde(rename = "type")]
    pub ty: String,
    /// The value: a boolean; a number for `byte`, `short` and `int`, and for `char` its UTF-16 code unit; a string
    /// for `long` (in decimal, exact past 2^53) and for `float` and `double` (Java's `toString` of it, which reads
    /// back as the same value: `0.1`, `-0.0`, `NaN`, `Infinity`); an array of those; null; or `{"same": i}` for
    /// the same array as the `i`th input. Absent for a record, whose components give it. For an object parameter a
    /// choice made null or the same object as another (step H2), null or `{"same": "a"}` by that one's name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<serde_json::Value>,
    /// A record's components, in declaration order: the arguments of its canonical constructor; for an object
    /// made by its constructor, that constructor's arguments, an object among them typed so in turn.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub components: Option<Vec<Typed>>,
    /// Where a call's argument came from: the input it is (`this.baseMillis`), or for the previous version's
    /// arguments given by `--before-arguments`, the expression over the inputs that computed it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub from: Option<String>,
}

/// A call of the method under proof on a witness, as data: which method of which class, in which version, with
/// the receiver and the arguments typed and mapped back to the inputs.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Call {
    /// The class declaring the method, as Java names it, as it is in that version's classes (not relocated).
    pub class: String,
    /// The class file the method was read from, relative to the root of that version's classes.
    pub class_file: String,
    /// Which classes: `after` (the version proved) or `before` (the previous one).
    pub classes: String,
    pub method: String,
    /// The method's descriptor, as in the class file: `(Lnet/example/retry/Backoff;I)J`.
    pub descriptor: String,
    #[serde(rename = "static")]
    pub is_static: bool,
    /// The receiver of an instance method: a record built by its canonical constructor from its components.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub receiver: Option<Typed>,
    /// The arguments, in parameter order.
    pub arguments: Vec<Typed>,
}

/// The method a [`Call`] calls, and in which classes.
pub struct Target<'a> {
    pub class_internal: &'a str,
    pub method: &'a str,
    pub descriptor: &'a str,
    pub is_static: bool,
    /// `after` or `before`.
    pub classes: &'a str,
}

/// The exact value of a primitive, as [`Typed::value`] has it.
pub fn exact(v: Value, t: &Type) -> serde_json::Value {
    use serde_json::Value as J;
    match (t, v) {
        (_, Value::Null) => J::Null,
        (Type::Boolean, Value::Int(x)) => J::Bool(x != 0),
        (Type::Char, Value::Int(x)) => J::from(x as u16),
        (_, Value::Int(x)) => J::from(x),
        (_, Value::Long(x)) => J::String(x.to_string()),
        (_, Value::Float(x)) => J::String(render::float_to_string(x)),
        (_, Value::Double(x)) => J::String(render::double_to_string(x)),
        (_, Value::Ref(_)) => J::Null,
    }
}

/// The exact value of an argument: a primitive, an array of them, a String as the shared witness form holds it
/// (`{"kind": "string", "units": [86, 73]}`, `spec::plans::WitnessValue`), null, or `{"same": i}`.
pub fn exact_argument(argument: &Argument, t: &Type) -> serde_json::Value {
    match (argument, t) {
        (Argument::Same(i), _) => serde_json::json!({ "same": i }),
        (Argument::String(units), _) => serde_json::to_value(crate::spec::plans::WitnessValue::String { units: units.clone() }).unwrap_or_default(),
        (Argument::Scalar(v), _) => exact(*v, t),
        (Argument::Array(data), Type::Array(element)) => serde_json::Value::Array(data.iter().map(|v| exact(*v, element)).collect()),
        (Argument::Array(data), _) => serde_json::Value::Array(data.iter().map(|v| exact(*v, &Type::Int)).collect()),
        (Argument::Null, _) => serde_json::Value::Null,
    }
}

/// The inputs of a witness, typed, under the harness's names (a record's components as `this.c` or `p.c`).
pub fn typed_inputs(params: &[Param], arguments: &[Argument]) -> Vec<Typed> {
    params.iter().zip(arguments).map(|(p, a)| Typed { name: p.name.clone(), ty: p.ty.java_name(), value: Some(exact_argument(a, &p.ty)), components: None, from: None }).collect()
}

/// The call of `target` on the flat parameters `arguments` of `layout`: each record built from its components (the
/// previous version's record when `before`), each argument mapped to what it came from, `from[i]` for the flat
/// parameter `i` (its name when `from` is empty).
pub fn typed_call(target: &Target, layout: &Layout, arguments: &[Argument], before: bool, from: &[String]) -> Call {
    let source = |i: usize| from.get(i).cloned().unwrap_or_else(|| layout.params[i].name.clone());
    let made = layout.made_on(arguments);
    let typed = |s: &Slot| match s {
        Slot::Plain(i) => {
            let p = &layout.params[*i];
            Typed { name: p.name.clone(), ty: p.ty.java_name(), value: arguments.get(*i).map(|a| exact_argument(a, &p.ty)), components: None, from: Some(source(*i)) }
        }
        Slot::Record { name, record, before: previous, first } => {
            let record = if before { previous.as_ref().unwrap_or(record) } else { record };
            // A choice's object (step H2): null, or `{"same": "a"}` for the same object as the parameter `a`.
            match made.iter().find(|(n, _)| n == name).map(|(_, m)| m) {
                Some(harness::Made::Null) => Typed { name: name.clone(), ty: record.java_name(), value: Some(serde_json::Value::Null), components: None, from: None },
                Some(harness::Made::Same(other)) => Typed { name: name.clone(), ty: record.java_name(), value: Some(serde_json::json!({ "same": other })), components: None, from: None },
                _ => typed_made(name, record, arguments, &source, &mut record.leaves(*first).into_iter()),
            }
        }
    };
    Call {
        class: target.class_internal.replace('/', "."),
        class_file: format!("{}.class", target.class_internal),
        classes: target.classes.to_string(),
        method: target.method.to_string(),
        descriptor: target.descriptor.to_string(),
        is_static: target.is_static,
        receiver: layout.receiver.as_ref().map(typed),
        arguments: layout.args.iter().map(typed).collect(),
    }
}

/// A record or an object made by its constructor, typed: its constructor's arguments in order, each primitive the
/// flat parameter `leaves` gives next, each object typed so in turn.
fn typed_made(name: &str, record: &crate::harness::RecordType, arguments: &[Argument], source: &dyn Fn(usize) -> String, leaves: &mut dyn Iterator<Item = crate::harness::Leaf>) -> Typed {
    let mut nested = record.inner.iter();
    let components = record
        .params
        .iter()
        .map(|(c, t)| match t {
            Type::Object(_) => match nested.next() {
                Some(inner) => typed_made(c, inner, arguments, source, leaves),
                None => Typed { name: c.clone(), ty: t.java_name(), value: None, components: None, from: None },
            },
            _ => match leaves.next().expect("a leaf for each primitive argument") {
                crate::harness::Leaf::Flat(k) => Typed { name: c.clone(), ty: t.java_name(), value: arguments.get(k).map(|a| exact_argument(a, t)), components: None, from: Some(source(k)) },
                // The previous version's argument an expression gives (H5's rest): its value, from the expression
                // over what its reads came from.
                crate::harness::Leaf::Computed(e, at) => {
                    let values: Option<Vec<Value>> = at.iter().map(|k| match arguments.get(*k) { Some(Argument::Scalar(v)) => Some(*v), _ => None }).collect();
                    let value = values.and_then(|v| e.eval(&v).ok()).map(|v| exact(v, t));
                    let names: Vec<(bool, String, String)> = e.reads.iter().zip(&at).map(|(r, k)| (r.param, r.path.clone(), source(*k))).collect();
                    let named = |param: bool, p: &str| names.iter().find(|(x, q, _)| *x == param && q == p).map(|(_, _, n)| n.clone()).unwrap_or_default();
                    let from = e.text_with(&|p| named(false, p), &|p| named(true, p));
                    Typed { name: c.clone(), ty: t.java_name(), value, components: None, from: Some(from.trim().to_string()) }
                }
            },
        })
        .collect();
    Typed { name: name.to_string(), ty: record.java_name(), value: None, components: Some(components), from: None }
}

/// The method's behaviour on a counterexample, replayed in the interpreter (or run on a JVM, [`crate::jvm_witness`]).
#[derive(Debug, Clone)]
pub struct Replayed {
    /// The outcome as text: the result, or the exception thrown.
    pub outcome: String,
    /// The value returned, if the method returned a primitive or an array.
    pub returned: Option<Value>,
    /// The elements of a returned array.
    pub result_array: Option<Vec<Value>>,
    /// The fields of a returned object (a record's components by name), when one was returned and not null.
    pub result_fields: Option<BTreeMap<String, Value>>,
    /// The elements of the array arguments after the call, by parameter slot.
    pub arrays_after: Vec<(u16, Vec<Value>)>,
    /// Each object argument made by its constructor that the call changed, by name, with its fields as the call
    /// left them: `("q", "Quote{amount=Money{cents=5}, quantity=3}")`.
    pub objects_after: Vec<(String, String)>,
    /// The class of the exception thrown, as an internal name.
    pub thrown: Option<String>,
    /// Each reference identity relations are over ([`crate::harness::Layout::references`]), by path, as the call
    /// left it: the result null where the method threw, a field of null null.
    pub references: Vec<(String, Value)>,
    /// Under a correspondence (step H5), each object it relates (a parameter as the call left it, by name, and the
    /// result, as `result`) read through its equations and labelled by the previous version's paths,
    /// `Quote{cents=5, quantity=3}`: two versions' views read alike exactly when the harness has the objects agree.
    pub views: Vec<(String, String)>,
    /// The harness's category of the exception thrown: its index among the classes the harness tells apart
    /// ([`crate::harness::Layout::exceptions`]), the first it is an instance of, or their number for any other.
    pub category: Option<usize>,
    /// Each primitive field path of a returned object the layout reads by its fields, as the call left it
    /// (`amount.cents`), for a relation between the results (step H5); a path through null is absent.
    pub result_paths: BTreeMap<String, Value>,
    /// Under output relations for an object parameter's fields (H5's rest), each such parameter's primitive field
    /// paths as the call left it, by name, for evaluating them over both replays, and those of each object
    /// parameter of the same shape in both versions compared without a correspondence, for naming the paths two
    /// replays differ in; a path through null is absent.
    pub object_paths: Vec<(String, BTreeMap<String, Value>)>,
}

impl Replayed {
    /// The identity relations among `pairs` (from [`crate::harness::Layout::identity_pairs`]) that hold in this
    /// replay, as `, with result == q`; empty when none does. Two replays agree on the relations exactly when these
    /// read the same.
    pub fn identities(&self, pairs: &[(String, String)]) -> String {
        let value = |path: &str| self.references.iter().find(|(p, _)| p == path).map(|(_, v)| *v);
        let holding: Vec<String> = pairs
            .iter()
            .filter(|(x, y)| matches!((value(x), value(y)), (Some(a), Some(b)) if a == b))
            .map(|(x, y)| format!("{x} == {y}"))
            .collect();
        if holding.is_empty() {
            String::new()
        } else {
            format!(", with {}", holding.join(" and "))
        }
    }

    /// Whether the identity relation `x == y` holds in this replay: both references there and the same object.
    pub fn identity_holds(&self, x: &str, y: &str) -> bool {
        let value = |path: &str| self.references.iter().find(|(p, _)| p == path).map(|(_, v)| *v);
        matches!((value(x), value(y)), (Some(a), Some(b)) if a == b)
    }

    /// The outcome, followed by what the method left in each array argument it changed: `3, leaving a=[0, 0]`.
    pub fn with_leftovers(&self, params: &[Param], arguments: &[Argument]) -> String {
        let mut outcome = self.outcome.clone();
        for (p, a) in params.iter().zip(arguments) {
            if let (Argument::Array(before), Type::Array(element)) = (a, &p.ty) {
                if let Some((_, after)) = self.arrays_after.iter().find(|(slot, after)| *slot == p.slot && after != before) {
                    outcome = format!("{outcome}, leaving {}={}", p.name, array(after, element));
                }
            }
        }
        for (name, fields) in &self.objects_after {
            outcome = format!("{outcome}, leaving {name}={fields}");
        }
        outcome
    }

    /// What two replays are compared on: [`Replayed::with_leftovers`] and [`Replayed::identities`], with each object
    /// a correspondence relates in its [`Replayed::views`] instead (the result's in place of the outcome), so that
    /// two versions of different shapes read alike when they agree under it. Without one it is the text shown.
    pub fn compared(&self, params: &[Param], arguments: &[Argument], pairs: &[(String, String)]) -> String {
        if self.views.is_empty() {
            return format!("{}{}", self.with_leftovers(params, arguments), self.identities(pairs));
        }
        let view = |name: &str| self.views.iter().find(|(n, _)| n == name).map(|(_, v)| v.clone());
        let mut text = if self.thrown.is_none() { view("result").unwrap_or_else(|| self.outcome.clone()) } else { self.outcome.clone() };
        for (p, a) in params.iter().zip(arguments) {
            if let (Argument::Array(before), Type::Array(element)) = (a, &p.ty) {
                if let Some((_, after)) = self.arrays_after.iter().find(|(slot, after)| *slot == p.slot && after != before) {
                    text = format!("{text}, leaving {}={}", p.name, array(after, element));
                }
            }
        }
        for (name, fields) in self.objects_after.iter().filter(|(n, _)| view(n).is_none()) {
            text = format!("{text}, leaving {name}={fields}");
        }
        for (name, v) in self.views.iter().filter(|(n, _)| n != "result") {
            text = format!("{text}, {name} as left {v}");
        }
        format!("{text}{}", self.identities(pairs))
    }

    /// Whether the replay failed for a reason that is not the method's (a method the interpreter does not model).
    pub fn could_not_replay(&self) -> bool {
        self.outcome.starts_with("<could not replay")
    }
}

/// The argument values for a call in the interpreter, with each array allocated afresh, once: an argument that is
/// the same array as an earlier one is passed that one.
fn values_for(m: &mut Machine, arguments: &[Argument], types: &[Type]) -> Vec<Value> {
    let mut values: Vec<Value> = Vec::with_capacity(arguments.len());
    for (argument, t) in arguments.iter().zip(types) {
        let v = match argument {
            Argument::Scalar(v) => *v,
            Argument::Null => Value::Null,
            Argument::Same(i) => values.get(*i).copied().unwrap_or(Value::Null),
            Argument::String(units) => crate::values::new_string(m, units),
            Argument::Array(data) => {
                let element = match t {
                    Type::Array(e) => (**e).clone(),
                    _ => Type::Int,
                };
                m.new_array_of(element, data.clone())
            }
        };
        values.push(v);
    }
    values
}

/// Runs the counterexample through `class_internal.method` in the interpreter, with the effect monitor off.
pub fn replay(cp: &ClassPath, class_internal: &str, method: &str, descriptor: &str, signature: &MethodDescriptor, arguments: &[Argument]) -> Replayed {
    crate::phases::timed(crate::phases::Step::Replay, || replay_untimed(cp, class_internal, method, descriptor, signature, arguments))
}

fn replay_untimed(cp: &ClassPath, class_internal: &str, method: &str, descriptor: &str, signature: &MethodDescriptor, arguments: &[Argument]) -> Replayed {
    let names: Vec<String> = (0..signature.params.len()).map(|i| format!("p{i}")).collect();
    replay_in(cp, &Layout::plain(&names, &signature.params), None, class_internal, method, descriptor, signature, arguments)
}

/// Runs the counterexample, given as the flat parameters of `layout`, through `class_internal.method` in the
/// interpreter: each record is built from its components through its constructor (the previous version's record,
/// under the package `prefix`, when one is given), and an instance method is called on the receiver. The arrays
/// left are keyed by flat parameter slot.
#[allow(clippy::too_many_arguments)]
pub fn replay_in(cp: &ClassPath, layout: &Layout, prefix: Option<&str>, class_internal: &str, method: &str, descriptor: &str, signature: &MethodDescriptor, arguments: &[Argument]) -> Replayed {
    crate::phases::timed(crate::phases::Step::Replay, || replay_in_untimed(cp, layout, prefix, class_internal, method, descriptor, signature, arguments))
}

#[allow(clippy::too_many_arguments)]
fn replay_in_untimed(cp: &ClassPath, layout: &Layout, prefix: Option<&str>, class_internal: &str, method: &str, descriptor: &str, signature: &MethodDescriptor, arguments: &[Argument]) -> Replayed {
    let mut m = Machine::new(cp);
    m.monitor = false;
    let _ = m.begin_case();
    let ret = &signature.ret;
    let flat = values_for(&mut m, arguments, &layout.types());
    // What the choices make of each object parameter (step H2), as the harness does: null, the same object as an
    // earlier one, or its own.
    let chosen = layout.made_on(arguments);
    let mut built: Vec<(String, Value)> = Vec::new();
    let build = |m: &mut Machine, slot: &Slot, built: &[(String, Value)]| -> Result<Value, Fault> {
        match slot {
            Slot::Plain(i) => Ok(flat[*i]),
            Slot::Record { name, record, before, first } => {
                match chosen.iter().find(|(n, _)| n == name).map(|(_, c)| c) {
                    Some(harness::Made::Null) => return Ok(Value::Null),
                    Some(harness::Made::Same(other)) => return Ok(built.iter().find(|(n, _)| n == other).map(|(_, v)| *v).unwrap_or(Value::Null)),
                    _ => {}
                }
                let (made, prefix) = match (prefix, before) {
                    (Some(p), Some(before)) => (before, Some(p)),
                    _ => (record, None),
                };
                construct(m, made, prefix, &flat, &mut made.leaves(*first).into_iter())
            }
        }
    };
    let mut values = Vec::new();
    let mut receiver = None;
    let mut rejected = None;
    // Each object made by its constructor, with its fields as made, to tell what the call changed.
    let mut objects: Vec<(String, Value, crate::harness::Fields, String)> = Vec::new();
    for slot in layout.receiver.iter().chain(layout.args.iter()) {
        match build(&mut m, slot, &built) {
            Ok(v) => {
                if let Slot::Record { name, .. } = slot {
                    built.push((name.clone(), v));
                }
                if let Slot::Record { name, record, before, .. } = slot {
                    let made = if prefix.is_some() { before.as_ref().unwrap_or(record) } else { record };
                    if let Some(fields) = &made.fields {
                        let shown = object_fields(&m, v, fields);
                        objects.push((name.clone(), v, fields.clone(), shown));
                    }
                }
                if layout.receiver.as_ref() == Some(slot) {
                    receiver = Some(v);
                } else {
                    values.push(v);
                }
            }
            Err(f) => {
                rejected = Some(f);
                break;
            }
        }
    }
    let changed = |m: &Machine| -> Vec<(String, String)> {
        objects
            .iter()
            .filter_map(|(name, v, fields, made)| {
                let now = object_fields(m, *v, fields);
                (now != *made).then(|| (name.clone(), now))
            })
            .collect()
    };
    // Every array among the flat parameters: an array argument, or an array leaf of an object's construction (O1),
    // which the caller still holds.
    let arrays: Vec<(u16, Ref)> = layout
        .params
        .iter()
        .zip(&flat)
        .filter_map(|(p, v)| match v {
            Value::Ref(r) if matches!(p.ty, Type::Array(_)) && matches!(m.heap.get(*r), Object::Array { .. }) => Some((p.slot, *r)),
            _ => None,
        })
        .collect();
    // The arrays as the call leaves them.
    let left = |m: &Machine| -> Vec<(u16, Vec<Value>)> {
        arrays
            .iter()
            .filter_map(|(slot, r)| match m.heap.get(*r) {
                Object::Array { data, .. } => Some((*slot, data.clone())),
                _ => None,
            })
            .collect()
    };
    let arg_values = values.clone();
    // The setup sequence (O3), on the receiver as made: a call that throws ends the history, and its exception,
    // under the step's own category, is the outcome.
    let mut setup_ended = None;
    let outcome = match rejected {
        None if receiver.is_some() && !layout.setup.is_empty() => {
            let this = receiver.expect("checked");
            let mut ended = None;
            for (k, step) in layout.setup.iter().enumerate() {
                let args: Vec<Value> = step.args.iter().map(|i| flat[*i]).collect();
                if let Err(f) = m.call_virtual(this, class_internal, &step.method, &step.descriptor, args) {
                    setup_ended = Some(k);
                    ended = Some(f);
                    break;
                }
            }
            match ended {
                Some(f) => Err(f),
                None => m.call_virtual(this, class_internal, method, descriptor, values),
            }
        }
        Some(Fault::Throw(r)) => return Replayed { outcome: format!("<the constructor {}>", render::thrown(&m, r)), returned: None, result_array: None, result_fields: None, arrays_after: left(&m), objects_after: Vec::new(), thrown: Some(m.class_of(r)), references: Vec::new(), views: Vec::new(), category: None, result_paths: BTreeMap::new(), object_paths: Vec::new() },
        Some(f) => Err(f),
        None => match receiver {
            Some(this) => m.call_virtual(this, class_internal, method, descriptor, values),
            None => m.call_static(class_internal, method, descriptor, values),
        },
    };
    let after = left(&m);
    let objects_after = changed(&m);
    // The references the identity relations are over, as the call left them.
    let result_value = match &outcome {
        Ok(Some(v)) => *v,
        _ => Value::Null,
    };
    let mut references: Vec<(String, Value)> = Vec::new();
    for r in layout.references(prefix.is_some(), ret, true) {
        let v = match &r.field {
            None => match r.root {
                crate::harness::Root::Result => result_value,
                crate::harness::Root::Receiver => receiver.unwrap_or(Value::Null),
                crate::harness::Root::Arg(i) => arg_values.get(i).copied().unwrap_or(Value::Null),
            },
            Some((parent, _, name, _)) => match references[*parent].1 {
                Value::Ref(p) => match m.heap.get(p) {
                    Object::Instance { fields, .. } => fields.get(name).copied().unwrap_or(Value::Null),
                    _ => Value::Null,
                },
                _ => Value::Null,
            },
        };
        references.push((r.path.clone(), v));
    }
    // Under a correspondence, the objects it relates as the call left them, read through its equations; those an
    // output relation takes the place of are left to it, which reads the object's paths (H5's rest).
    let mut views = Vec::new();
    let mut object_paths = Vec::new();
    for (slot, v) in layout.args.iter().zip(&arg_values) {
        if let Slot::Record { name, record, before: Some(previous), .. } = slot {
            if let (Some(c), Some(old)) = (&previous.corresponds, &previous.fields) {
                views.push((name.clone(), corresponding_view(&m, *v, &old.class, &c.compared_equations(), prefix.is_some(), &flat)));
                let fields = if prefix.is_some() { Some(old) } else { record.fields.as_ref() };
                // A parameter its choice made null is null in both versions, and has nothing to relate. Its paths
                // are kept for the output relations for its fields and for a result relation that reads them.
                if let (Some(fields), Value::Ref(_)) = (fields, v) {
                    object_paths.push((name.clone(), primitive_paths(&m, *v, fields)));
                }
            } else if let (None, Some(old), Some(new), Value::Ref(_)) = (&previous.corresponds, &previous.fields, &record.fields, v) {
                // Of the same shape without a correspondence, compared field by field: its paths too, so that a
                // difference names each path it is in (H5's rest).
                object_paths.push((name.clone(), primitive_paths(&m, *v, if prefix.is_some() { old } else { new })));
            }
        }
    }
    if let (Some(equations), Some(old), Ok(Some(v))) = (&layout.result_equations, &layout.result_fields.1, &outcome) {
        views.push(("result".to_string(), corresponding_view(&m, *v, &old.class, equations, prefix.is_some(), &flat)));
    }
    let category = match &outcome {
        Err(Fault::Throw(r)) => {
            let exceptions = layout.exceptions(prefix);
            let index = exceptions.iter().position(|e| m.is_instance(*r, e)).unwrap_or(exceptions.len());
            Some(match setup_ended {
                Some(k) => crate::harness::setup_category(k, index) as usize,
                None => index,
            })
        }
        _ => None,
    };
    let result_fields_of = if prefix.is_some() { &layout.result_fields.1 } else { &layout.result_fields.0 };
    let result_value = match &outcome {
        Ok(Some(v)) => Some(*v),
        _ => None,
    };
    let mut replayed = match outcome {
        Ok(Some(v)) => {
            let (array, fields) = match v {
                Value::Ref(r) => match m.heap.get(r) {
                    Object::Array { data, .. } => (Some(data.clone()), None),
                    Object::Instance { fields, .. } => (None, Some(fields.clone())),
                    _ => (None, None),
                },
                _ => (None, None),
            };
            let text = match (&array, ret) {
                (Some(data), Type::Array(element)) => self::array(data, element),
                (_, Type::Object(_)) if result_fields_of.is_some() => object_fields(&m, v, result_fields_of.as_ref().expect("checked")),
                _ => render::value(&mut m, v, ret).unwrap_or_else(|f| render::fault(&m, &f)),
            };
            let returned = (ret.is_primitive() || array.is_some()).then_some(v);
            Replayed { outcome: text, returned, result_array: array, result_fields: fields, arrays_after: after, objects_after: Vec::new(), thrown: None, references: Vec::new(), views: Vec::new(), category: None, result_paths: BTreeMap::new(), object_paths: Vec::new() }
        }
        Ok(None) => Replayed { outcome: "void".to_string(), returned: None, result_array: None, result_fields: None, arrays_after: after, objects_after: Vec::new(), thrown: None, references: Vec::new(), views: Vec::new(), category: None, result_paths: BTreeMap::new(), object_paths: Vec::new() },
        Err(Fault::Throw(r)) => Replayed { outcome: match setup_ended { Some(k) => format!("{} in the setup call this.{}", render::thrown(&m, r), layout.setup[k].method), None => render::thrown(&m, r) }, returned: None, result_array: None, result_fields: None, arrays_after: after, objects_after: Vec::new(), thrown: Some(m.class_of(r)), references: Vec::new(), views: Vec::new(), category: None, result_paths: BTreeMap::new(), object_paths: Vec::new() },
        Err(f) => Replayed { outcome: format!("<could not replay: {}>", render::fault(&m, &f)), returned: None, result_array: None, result_fields: None, arrays_after: after, objects_after: Vec::new(), thrown: None, references: Vec::new(), views: Vec::new(), category: None, result_paths: BTreeMap::new(), object_paths: Vec::new() },
    };
    if let (Some(v), Some(fields)) = (result_value, result_fields_of) {
        replayed.result_paths = primitive_paths(&m, v, fields);
    }
    replayed.objects_after = objects_after;
    replayed.references = references;
    replayed.views = views;
    replayed.object_paths = object_paths;
    replayed.category = category;
    replayed
}

/// The observations two replays of the same input differ in, by id ([`crate::spec::Observation::id`]), as the
/// harness compares them: `exception` for the category, `result` (when both returned; through the correspondence's
/// view under one), `array:a` for an array parameter as left, `field:q` for an object parameter as left (its view
/// under a correspondence, with `field:q.cents` for each previous version's path the views read differently, or
/// each primitive path read differently of an object of the same shape compared without one), and `identity:x==y` for each relation of `pairs` that holds in one and not the other.
///
/// None where either replay could not run its version ([`Replayed::could_not_replay`]): an outcome the interpreter
/// could not produce is unknown, and differs from nothing (O2, after VF-015's step 4). The caller runs such a
/// witness on a JVM, whose outcomes it compares in its place.
pub fn differences(before: &Replayed, after: &Replayed, params: &[Param], arguments: &[Argument], pairs: &[(String, String)]) -> Vec<String> {
    let mut out = Vec::new();
    if before.could_not_replay() || after.could_not_replay() {
        return out;
    }
    let view = |r: &Replayed, name: &str| r.views.iter().find(|(n, _)| n == name).map(|(_, v)| v.clone());
    if before.category != after.category || before.thrown.is_some() != after.thrown.is_some() {
        out.push("exception".to_string());
    } else if before.thrown.is_none() {
        let result = |r: &Replayed| view(r, "result").unwrap_or_else(|| r.outcome.clone());
        if result(before) != result(after) {
            out.push("result".to_string());
        }
    }
    for (p, a) in params.iter().zip(arguments) {
        if let Argument::Array(_) = a {
            let left = |r: &Replayed| r.arrays_after.iter().find(|(slot, _)| *slot == p.slot).map(|(_, data)| data.clone());
            if left(before) != left(after) {
                out.push(format!("array:{}", p.name));
            }
        }
    }
    let mut objects: Vec<&String> = before.views.iter().chain(&after.views).map(|(n, _)| n).chain(before.objects_after.iter().chain(&after.objects_after).map(|(n, _)| n)).filter(|n| *n != "result").collect();
    objects.sort();
    objects.dedup();
    for name in objects {
        let left = |r: &Replayed| view(r, name).or_else(|| r.objects_after.iter().find(|(n, _)| n == name).map(|(_, t)| t.clone()));
        if left(before) != left(after) {
            out.push(format!("field:{name}"));
            // Of the same shape without a correspondence, each primitive path read differently, `field:l.quantity`.
            let paths = |r: &Replayed| r.object_paths.iter().find(|(n, _)| n == name).map(|(_, p)| p.clone());
            if let (None, None, Some(x), Some(y)) = (view(before, name), view(after, name), paths(before), paths(after)) {
                let mut names: Vec<&String> = x.keys().chain(y.keys()).collect();
                names.sort();
                names.dedup();
                for path in names {
                    if format!("{:?}", x.get(path)) != format!("{:?}", y.get(path)) {
                        out.push(format!("field:{name}.{path}"));
                    }
                }
            }
            // Through a correspondence's views, each previous version's path read differently too, `field:q.cents`.
            if let (Some(x), Some(y)) = (view(before, name), view(after, name)) {
                let parts = |v: &str| -> Vec<(String, String)> {
                    let inner = v.split_once('{').map(|(_, rest)| rest.trim_end_matches('}')).unwrap_or_default();
                    inner.split(", ").filter_map(|p| p.split_once('=')).map(|(k, v)| (k.to_string(), v.to_string())).collect()
                };
                let (xs, ys) = (parts(&x), parts(&y));
                for (path, value) in &xs {
                    if ys.iter().find(|(p, _)| p == path).map(|(_, v)| v) != Some(value) {
                        out.push(format!("field:{name}.{path}"));
                    }
                }
            }
        }
    }
    let holds = |r: &Replayed, x: &str, y: &str| {
        let value = |path: &str| r.references.iter().find(|(p, _)| p == path).map(|(_, v)| *v);
        matches!((value(x), value(y)), (Some(a), Some(b)) if a == b)
    };
    for (x, y) in pairs {
        if holds(before, x, y) != holds(after, x, y) {
            out.push(format!("identity:{x}=={y}"));
        }
    }
    out
}

/// The object `v` read through a correspondence's `equations` (step H5): each equation's path in this version (the
/// previous one's when `previous`), labelled by the previous version's path, `Quote{cents=5, quantity=3}` under the
/// previous version's simple class name `class`; a path through null reads `absent`. A parameter an expression reads
/// (H5's rest) is its flat value in `flat`.
fn corresponding_view(m: &Machine, v: Value, class: &str, equations: &[crate::harness::FieldEquation], previous: bool, flat: &[Value]) -> String {
    if !matches!(v, Value::Ref(_)) {
        return "null".into();
    }
    let read = |path: &str| -> Option<Value> {
        let mut current = v;
        for name in path.split('.') {
            current = match current {
                Value::Ref(r) => match m.heap.get(r) {
                    Object::Instance { fields, .. } => fields.get(name).copied().unwrap_or(Value::Null),
                    _ => Value::Null,
                },
                _ => return None,
            };
        }
        Some(current)
    };
    let parts: Vec<String> = equations
        .iter()
        .map(|e| {
            // The new side an expression over the new object's paths gives (H5's rest), absent where one is.
            let value = match (&e.computed, previous) {
                (Some(c), false) => c.reads.iter().map(|r| if r.param { flat.get(r.leaf).copied() } else { read(&r.path) }).collect::<Option<Vec<_>>>().map(|values| c.eval(&values).unwrap_or(Value::Null)),
                (_, true) => read(&e.old),
                (None, false) => read(&e.new),
            };
            match value {
                Some(current) => format!("{}={}", e.old, render::witness(current, &e.ty)),
                None => format!("{}=absent", e.old),
            }
        })
        .collect();
    format!("{}{{{}}}", crate::classfile::simple_name_of(class), parts.join(", "))
}

/// Makes `record` in the interpreter (its classes under `prefix/` when given) from its leaves, the values of `flat`
/// at the indices `leaves` gives in turn, each inner object made first.
fn construct(m: &mut Machine, record: &crate::harness::RecordType, prefix: Option<&str>, flat: &[Value], leaves: &mut dyn Iterator<Item = crate::harness::Leaf>) -> Result<Value, Fault> {
    let owner = match prefix {
        Some(p) => format!("{p}/{}", record.class),
        None => record.class.clone(),
    };
    let mut nested = record.inner.iter();
    let mut args = Vec::new();
    for (_, t) in &record.params {
        if crate::harness::is_leaf(t) {
            args.push(match leaves.next().expect("a leaf for each primitive argument") {
                crate::harness::Leaf::Flat(i) => flat[i],
                // An expression over the new version's leaves (H5's rest), as the harness computes it; one that
                // divides by zero throws, and the input is skipped as one a constructor rejects.
                crate::harness::Leaf::Computed(e, at) => {
                    let values: Vec<Value> = at.iter().map(|i| flat[*i]).collect();
                    e.eval(&values).map_err(|_| m.throw("java/lang/ArithmeticException", Some("/ by zero")))?
                }
            });
        } else if let Some(inner) = nested.next() {
            args.push(construct(m, inner, prefix, flat, leaves)?);
        }
    }
    m.construct(&owner, &record.constructor_in(prefix), args)
}

/// The fields of the object `v` as `fields` lays them out, followed into the objects they refer to:
/// `Quote{amount=Money{cents=5}, quantity=3}`, by simple class name, so that both versions' objects read alike.
pub fn object_fields(m: &Machine, v: Value, fields: &crate::harness::Fields) -> String {
    let Value::Ref(r) = v else { return "null".into() };
    let Object::Instance { fields: values, .. } = m.heap.get(r) else { return "<not an object>".into() };
    let shown: Vec<String> = fields
        .fields
        .iter()
        .map(|(name, kind)| {
            let value = values.get(name).copied().unwrap_or(Value::Null);
            let text = match kind {
                crate::harness::FieldKind::Value(t) => render::witness(value, t),
                crate::harness::FieldKind::Array(t) => match (value, t) {
                    (Value::Ref(a), Type::Array(element)) => match m.heap.get(a) {
                        Object::Array { data, .. } => array(data, element),
                        _ => "<not an array>".into(),
                    },
                    _ => "null".into(),
                },
                crate::harness::FieldKind::Object(inner) => object_fields(m, value, inner),
            };
            format!("{name}={text}")
        })
        .collect();
    format!("{}{{{}}}", crate::classfile::simple_name_of(&fields.class), shown.join(", "))
}

/// Each primitive field path of the object `v` by `fields`, as it reads now, `amount.cents`; a path through null is
/// absent.
fn primitive_paths(m: &Machine, v: Value, fields: &crate::harness::Fields) -> BTreeMap<String, Value> {
    let mut out = BTreeMap::new();
    let Value::Ref(r) = v else { return out };
    let Object::Instance { fields: values, .. } = m.heap.get(r) else { return out };
    for (name, kind) in &fields.fields {
        let value = values.get(name).copied().unwrap_or(Value::Null);
        match kind {
            crate::harness::FieldKind::Value(_) => {
                out.insert(name.clone(), value);
            }
            crate::harness::FieldKind::Object(inner) => out.extend(primitive_paths(m, value, inner).into_iter().map(|(p, v)| (format!("{name}.{p}"), v))),
            crate::harness::FieldKind::Array(_) => {}
        }
    }
    out
}

/// How many smaller inputs the shrinker may try.
pub const SHRINK_BUDGET: u32 = 4000;

/// Shrinks a counterexample with the harness as the oracle: the generated class `harness_class` on `cp`, run in
/// the interpreter, refutes the statement on an input exactly when it throws `AssertionError` on it (the scope or
/// assumption is part of the harness, so an input outside it passes). An input the interpreter cannot run is not
/// accepted.
///
/// It keeps the flat parameters `kept` as found, a choice's flags (step H2, [`crate::harness::Layout::flags`]),
/// so that shrinking never makes two objects one or one object two. A
/// candidate the harness refutes is accepted only where `same` says it is the same failure as the input found
/// (O2 of `llm-dlc/loops/application-core-objects.md`): the regression check's replay differs in the same
/// observations, the property check's fails in the same way. The harness alone would take any failure, and a
/// witness of one difference could shrink into a witness of another, a constructor's narrower admission say,
/// reported as the input found shrunk.
///
/// So a shrunk recipe is legal and reproduces the failure: every candidate is the harness's own input, with the
/// harness's domain (its scope, its assumptions, its constructors' admission) and the plan's choices as found, no
/// longer array than found and no null where there was none, and it is accepted only after it is replayed.
pub fn shrink_in_harness_keeping(cp: &ClassPath, harness_class: &str, types: &[Type], found: Vec<Argument>, kept: &[usize], same: impl FnMut(&[Argument]) -> bool) -> Shrunk {
    crate::phases::timed(crate::phases::Step::Replay, || shrink_in_harness_untimed(cp, harness_class, types, found, kept, same))
}

fn shrink_in_harness_untimed(cp: &ClassPath, harness_class: &str, types: &[Type], found: Vec<Argument>, kept: &[usize], mut same: impl FnMut(&[Argument]) -> bool) -> Shrunk {
    let mut m = Machine::new(cp);
    m.monitor = false;
    let original = found.clone();
    let mut fails = |arguments: &[Argument]| {
        if kept.iter().any(|&i| arguments.get(i) != original.get(i)) {
            return Some(false);
        }
        match fails_in(&mut m, harness_class, types, arguments) {
            Some(true) => Some(same(arguments)),
            other => other,
        }
    };
    // The interpreter must agree that the input found is a counterexample before it is trusted on smaller ones.
    if fails(&found) != Some(true) {
        return Shrunk { arguments: found, runs: 0 };
    }
    shrink::shrink(types, found, SHRINK_BUDGET, fails)
}

/// Whether the harness `harness_class` on `cp`, run in the interpreter, refutes the statement on `arguments`
/// (throws `AssertionError`); `None` when the interpreter cannot run it.
pub fn fails_in_harness(cp: &ClassPath, harness_class: &str, types: &[Type], arguments: &[Argument]) -> Option<bool> {
    let mut m = Machine::new(cp);
    m.monitor = false;
    fails_in(&mut m, harness_class, types, arguments)
}

fn fails_in(m: &mut Machine, harness_class: &str, types: &[Type], arguments: &[Argument]) -> Option<bool> {
    let check_descriptor = format!("({})V", types.iter().map(Type::descriptor).collect::<String>());
    let mark = m.begin_case();
    let values = values_for(m, arguments, types);
    let verdict = match m.call_static(harness_class, harness::METHOD, &check_descriptor, values) {
        Ok(_) => Some(false),
        Err(Fault::Throw(r)) if m.class_of(r) == "java/lang/AssertionError" => Some(true),
        Err(_) => None,
    };
    m.end_case(mark);
    verdict
}

/// A class path over the directories that exist among `entries`, with the JDK.
pub fn classpath<'a>(entries: impl IntoIterator<Item = &'a Path>) -> Result<ClassPath, Error> {
    let mut cp = ClassPath::new();
    for entry in entries {
        if entry.exists() {
            cp.add(entry)?;
        }
    }
    Ok(cp.with_default_jdk())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::harness::RecordType;
    use serde_json::json;

    /// A replay of `outcome` alone, as a call that returned (`returned`) or could not be run.
    fn replayed(outcome: &str, returned: Option<Value>) -> Replayed {
        Replayed { outcome: outcome.into(), returned, result_array: None, result_fields: None, arrays_after: Vec::new(), objects_after: Vec::new(), thrown: None, references: Vec::new(), views: Vec::new(), category: None, result_paths: BTreeMap::new(), object_paths: Vec::new() }
    }

    /// VF-015's step 4: the previous version returned 7 and the new one could not be replayed. Its outcome is
    /// unknown, so the two differ in nothing the replay knows, never in `result`.
    #[test]
    fn a_replay_that_could_not_run_one_version_differs_in_nothing() {
        let params = [crate::harness::expr::Param { name: "ch".into(), ty: Type::Char, slot: 0 }];
        let arguments = [Argument::Scalar(Value::Int(0x667))];
        let seven = replayed("7", Some(Value::Int(7)));
        let unknown = replayed("<could not replay: <unsupported: String.format depends on the default locale>>", None);
        assert_eq!(differences(&seven, &replayed("8", Some(Value::Int(8))), &params, &arguments, &[]), vec!["result".to_string()], "the premise: two outcomes that ran differ in the result");
        assert!(differences(&seven, &unknown, &params, &arguments, &[]).is_empty());
        assert!(differences(&unknown, &seven, &params, &arguments, &[]).is_empty());
    }

    #[test]
    fn values_are_exact_for_their_type() {
        assert_eq!(exact(Value::Int(1), &Type::Boolean), json!(true));
        assert_eq!(exact(Value::Int(0), &Type::Boolean), json!(false));
        assert_eq!(exact(Value::Int(-128), &Type::Byte), json!(-128));
        assert_eq!(exact(Value::Int(0xff10), &Type::Char), json!(0xff10));
        assert_eq!(exact(Value::Int(i32::MIN), &Type::Int), json!(i32::MIN));
        // Past 2^53 a JSON number is not exact in every reader; the decimal string is.
        assert_eq!(exact(Value::Long(i64::MAX), &Type::Long), json!("9223372036854775807"));
        assert_eq!(exact(Value::Long((1 << 53) + 1), &Type::Long), json!("9007199254740993"));
        assert_eq!(exact(Value::Double(0.1), &Type::Double), json!("0.1"));
        assert_eq!(exact(Value::Double(-0.0), &Type::Double), json!("-0.0"));
        assert_eq!(exact(Value::Double(f64::NAN), &Type::Double), json!("NaN"));
        assert_eq!(exact(Value::Double(f64::NEG_INFINITY), &Type::Double), json!("-Infinity"));
        // The smallest float reads as "1.0E-45" (Java writes 1.4E-45): either reads back as the same float.
        for x in [1.0e-45f32, 0.1, f32::MAX, -3.5] {
            let text = exact(Value::Float(x), &Type::Float);
            assert_eq!(text.as_str().unwrap().parse::<f32>().unwrap().to_bits(), x.to_bits(), "{x}");
        }
        for x in [0.1f64, 1.0 / 3.0, 5e-324, f64::MAX, 123456789.0123] {
            let text = exact(Value::Double(x), &Type::Double);
            assert_eq!(text.as_str().unwrap().parse::<f64>().unwrap().to_bits(), x.to_bits(), "{x}");
        }
        assert_eq!(exact_argument(&Argument::Array(vec![Value::Long(-1), Value::Long(2)]), &Type::Array(Box::new(Type::Long))), json!(["-1", "2"]));
        assert_eq!(exact_argument(&Argument::Null, &Type::Array(Box::new(Type::Int))), json!(null));
    }

    #[test]
    fn a_call_maps_a_records_components_to_the_inputs_they_are() {
        let backoff = RecordType::record("net/example/Backoff", vec![("baseMillis".into(), Type::Long), ("capMillis".into(), Type::Long)]);
        let layout = Layout::new(Some((backoff.clone(), Some(backoff))), &["attempt".into()], &[Type::Int], &[None], (None, None));
        let arguments = [Argument::Scalar(Value::Long(1)), Argument::Scalar(Value::Long(1)), Argument::Scalar(Value::Int(-1))];
        let target = Target { class_internal: "net/example/Backoff", method: "delayMillis", descriptor: "(I)J", is_static: false, classes: "after" };
        let call = typed_call(&target, &layout, &arguments, false, &[]);
        assert_eq!(
            serde_json::to_value(&call).unwrap(),
            json!({
                "class": "net.example.Backoff", "class_file": "net/example/Backoff.class", "classes": "after",
                "method": "delayMillis", "descriptor": "(I)J", "static": false,
                "receiver": {"name": "this", "type": "net.example.Backoff", "components": [
                    {"name": "baseMillis", "type": "long", "value": "1", "from": "this.baseMillis"},
                    {"name": "capMillis", "type": "long", "value": "1", "from": "this.capMillis"}]},
                "arguments": [{"name": "attempt", "type": "int", "value": -1, "from": "attempt"}]
            })
        );
        let inputs = typed_inputs(&layout.params, &arguments);
        assert_eq!(inputs.iter().map(|t| t.name.as_str()).collect::<Vec<_>>(), ["this.baseMillis", "this.capMillis", "attempt"]);
        // The previous version's arguments computed by expressions name them.
        let flat = Layout::plain(&["base".into(), "n".into()], &[Type::Long, Type::Int]);
        let previous = Target { class_internal: "net/example/Delays", method: "delay", descriptor: "(JI)J", is_static: true, classes: "before" };
        let call = typed_call(&previous, &flat, &[Argument::Scalar(Value::Long(1)), Argument::Scalar(Value::Int(-1))], true, &["this.baseMillis".into(), "attempt".into()]);
        assert!(call.receiver.is_none() && call.is_static);
        assert_eq!(call.arguments[0].from.as_deref(), Some("this.baseMillis"));
        assert_eq!(call.arguments[1].value, Some(json!(-1)));
    }
}
