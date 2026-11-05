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

/// A witness argument as Java would write it: `17`, `'a'`, `[3, 5, 8]`, `null`.
pub fn argument(argument: &Argument, t: &Type) -> String {
    match (argument, t) {
        (Argument::Scalar(v), _) => render::witness(*v, t),
        (Argument::Array(data), Type::Array(element)) => array(data, element),
        (Argument::Array(_), _) => "<array>".into(),
        (Argument::Null, _) => "null".into(),
    }
}

pub fn array(data: &[Value], element: &Type) -> String {
    format!("[{}]", data.iter().map(|v| render::witness(*v, element)).collect::<Vec<_>>().join(", "))
}

/// `method(a=[1, 2], n=3)`: the arguments by parameter name, and the rendering of each.
pub fn call(method: &str, params: &[Param], arguments: &[Argument]) -> (String, Vec<String>) {
    let witnesses: Vec<String> = params.iter().zip(arguments).map(|(p, a)| argument(a, &p.ty)).collect();
    let rendered = format!("{method}({})", params.iter().zip(&witnesses).map(|(p, w)| format!("{}={w}", p.name)).collect::<Vec<_>>().join(", "));
    (rendered, witnesses)
}

/// `method(this=Backoff[baseMillis=1, capMillis=1], attempt=63)`: the receiver and the arguments by name, a
/// record as Java prints it, and the rendering of each flat parameter.
pub fn call_in(method: &str, layout: &Layout, arguments: &[Argument]) -> (String, Vec<String>) {
    let witnesses: Vec<String> = layout.params.iter().zip(arguments).map(|(p, a)| argument(a, &p.ty)).collect();
    let shown = |s: &Slot| match s {
        Slot::Plain(i) => format!("{}={}", layout.params[*i].name, witnesses[*i]),
        Slot::Record { name, record, first, .. } => {
            let components = record.components.iter().zip(&witnesses[*first..]).map(|((c, _), w)| format!("{c}={w}")).collect::<Vec<_>>().join(", ");
            format!("{name}={}[{components}]", record.simple_name())
        }
    };
    let rendered = format!("{method}({})", layout.receiver.iter().chain(layout.args.iter()).map(shown).collect::<Vec<_>>().join(", "));
    (rendered, witnesses)
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
    /// back as the same value: `0.1`, `-0.0`, `NaN`, `Infinity`); an array of those; or null. Absent for a record,
    /// whose components give it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<serde_json::Value>,
    /// A record's components, in declaration order: the arguments of its canonical constructor.
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

/// The exact value of an argument: a primitive, an array of them, or null.
pub fn exact_argument(argument: &Argument, t: &Type) -> serde_json::Value {
    match (argument, t) {
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
    let typed = |s: &Slot| match s {
        Slot::Plain(i) => {
            let p = &layout.params[*i];
            Typed { name: p.name.clone(), ty: p.ty.java_name(), value: arguments.get(*i).map(|a| exact_argument(a, &p.ty)), components: None, from: Some(source(*i)) }
        }
        Slot::Record { name, record, before: previous, first } => {
            let record = if before { previous.as_ref().unwrap_or(record) } else { record };
            let components = record
                .components
                .iter()
                .enumerate()
                .map(|(k, (c, t))| Typed { name: c.clone(), ty: t.java_name(), value: arguments.get(first + k).map(|a| exact_argument(a, t)), components: None, from: Some(source(first + k)) })
                .collect();
            Typed { name: name.clone(), ty: record.java_name(), value: None, components: Some(components), from: None }
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

/// The method's behaviour on a counterexample, replayed in the interpreter.
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
    /// The class of the exception thrown, as an internal name.
    pub thrown: Option<String>,
}

impl Replayed {
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
        outcome
    }

    /// Whether the replay failed for a reason that is not the method's (a method the interpreter does not model).
    pub fn could_not_replay(&self) -> bool {
        self.outcome.starts_with("<could not replay")
    }
}

/// The argument values for a call in the interpreter, with each array allocated afresh.
fn values_for(m: &mut Machine, arguments: &[Argument], types: &[Type]) -> Vec<Value> {
    arguments
        .iter()
        .zip(types)
        .map(|(argument, t)| match argument {
            Argument::Scalar(v) => *v,
            Argument::Null => Value::Null,
            Argument::Array(data) => {
                let element = match t {
                    Type::Array(e) => (**e).clone(),
                    _ => Type::Int,
                };
                m.new_array_of(element, data.clone())
            }
        })
        .collect()
}

/// Runs the counterexample through `class_internal.method` in the interpreter, with the effect monitor off.
pub fn replay(cp: &ClassPath, class_internal: &str, method: &str, descriptor: &str, signature: &MethodDescriptor, arguments: &[Argument]) -> Replayed {
    let names: Vec<String> = (0..signature.params.len()).map(|i| format!("p{i}")).collect();
    replay_in(cp, &Layout::plain(&names, &signature.params), None, class_internal, method, descriptor, signature, arguments)
}

/// Runs the counterexample, given as the flat parameters of `layout`, through `class_internal.method` in the
/// interpreter: each record is built from its components through its constructor (the previous version's record,
/// under the package `prefix`, when one is given), and an instance method is called on the receiver. The arrays
/// left are keyed by flat parameter slot.
#[allow(clippy::too_many_arguments)]
pub fn replay_in(cp: &ClassPath, layout: &Layout, prefix: Option<&str>, class_internal: &str, method: &str, descriptor: &str, signature: &MethodDescriptor, arguments: &[Argument]) -> Replayed {
    let mut m = Machine::new(cp);
    m.monitor = false;
    let _ = m.begin_case();
    let ret = &signature.ret;
    let flat = values_for(&mut m, arguments, &layout.types());
    let build = |m: &mut Machine, slot: &Slot| -> Result<Value, Fault> {
        match slot {
            Slot::Plain(i) => Ok(flat[*i]),
            Slot::Record { record, before, first, .. } => {
                let owner = match (prefix, before) {
                    (Some(p), Some(before)) => format!("{p}/{}", before.class),
                    _ => record.class.clone(),
                };
                m.construct(&owner, &record.constructor(), flat[*first..*first + record.components.len()].to_vec())
            }
        }
    };
    let mut values = Vec::new();
    let mut receiver = None;
    let mut rejected = None;
    for slot in layout.receiver.iter().chain(layout.args.iter()) {
        match build(&mut m, slot) {
            Ok(v) if layout.receiver.as_ref() == Some(slot) => receiver = Some(v),
            Ok(v) => values.push(v),
            Err(f) => {
                rejected = Some(f);
                break;
            }
        }
    }
    let arrays: Vec<(u16, Ref)> = layout
        .args
        .iter()
        .zip(&values)
        .filter_map(|(slot, v)| match (slot, v) {
            (Slot::Plain(i), Value::Ref(r)) if matches!(m.heap.get(*r), Object::Array { .. }) => Some((layout.params[*i].slot, *r)),
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
    let outcome = match rejected {
        Some(Fault::Throw(r)) => return Replayed { outcome: format!("<the constructor {}>", render::thrown(&m, r)), returned: None, result_array: None, result_fields: None, arrays_after: left(&m), thrown: Some(m.class_of(r)) },
        Some(f) => Err(f),
        None => match receiver {
            Some(this) => m.call_virtual(this, class_internal, method, descriptor, values),
            None => m.call_static(class_internal, method, descriptor, values),
        },
    };
    let after = left(&m);
    match outcome {
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
                _ => render::value(&mut m, v, ret).unwrap_or_else(|f| render::fault(&m, &f)),
            };
            let returned = (ret.is_primitive() || array.is_some()).then_some(v);
            Replayed { outcome: text, returned, result_array: array, result_fields: fields, arrays_after: after, thrown: None }
        }
        Ok(None) => Replayed { outcome: "void".to_string(), returned: None, result_array: None, result_fields: None, arrays_after: after, thrown: None },
        Err(Fault::Throw(r)) => Replayed { outcome: render::thrown(&m, r), returned: None, result_array: None, result_fields: None, arrays_after: after, thrown: Some(m.class_of(r)) },
        Err(f) => Replayed { outcome: format!("<could not replay: {}>", render::fault(&m, &f)), returned: None, result_array: None, result_fields: None, arrays_after: after, thrown: None },
    }
}

/// How many smaller inputs the shrinker may try.
pub const SHRINK_BUDGET: u32 = 4000;

/// Shrinks a counterexample with the harness as the oracle: the generated class `harness_class` on `cp`, run in
/// the interpreter, refutes the statement on an input exactly when it throws `AssertionError` on it (the scope or
/// assumption is part of the harness, so an input outside it passes). An input the interpreter cannot run is not
/// accepted.
pub fn shrink_in_harness(cp: &ClassPath, harness_class: &str, types: &[Type], found: Vec<Argument>) -> Shrunk {
    let mut m = Machine::new(cp);
    m.monitor = false;
    let check_descriptor = format!("({})V", types.iter().map(Type::descriptor).collect::<String>());
    let mut fails = |arguments: &[Argument]| -> Option<bool> {
        let mark = m.begin_case();
        let values = values_for(&mut m, arguments, types);
        let verdict = match m.call_static(harness_class, harness::METHOD, &check_descriptor, values) {
            Ok(_) => Some(false),
            Err(Fault::Throw(r)) if m.class_of(r) == "java/lang/AssertionError" => Some(true),
            Err(_) => None,
        };
        m.end_case(mark);
        verdict
    };
    // The interpreter must agree that the input found is a counterexample before it is trusted on smaller ones.
    if fails(&found) != Some(true) {
        return Shrunk { arguments: found, runs: 0 };
    }
    shrink::shrink(types, found, SHRINK_BUDGET, fails)
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
        let backoff = RecordType { class: "net/example/Backoff".into(), components: vec![("baseMillis".into(), Type::Long), ("capMillis".into(), Type::Long)] };
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
