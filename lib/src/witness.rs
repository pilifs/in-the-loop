//! What is done with a counterexample once JBMC has found one: it is replayed in the interpreter to show what the
//! method does on it, shrunk by running the harness class JBMC checked on smaller inputs, and rendered as Java
//! would write it. Shared by the regression proofs ([`crate::equivalence`]) and the property proofs
//! ([`crate::property`]).

use std::path::Path;

use crate::classfile::{MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::harness::{self, Param};
use crate::interp::{render, Fault, Machine, Object, Value};
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

/// The elements of the arrays among `values`, by parameter slot, as they are now.
fn arrays_of(m: &Machine, values: &[Value], signature: &MethodDescriptor) -> Vec<(u16, Vec<Value>)> {
    let mut out = Vec::new();
    let mut slot = 0;
    for (v, t) in values.iter().zip(&signature.params) {
        if let Value::Ref(r) = v {
            if let Object::Array { data, .. } = m.heap.get(*r) {
                out.push((slot, data.clone()));
            }
        }
        slot += t.slots();
    }
    out
}

/// The method's behaviour on a counterexample, replayed in the interpreter.
pub struct Replayed {
    /// The outcome as text: the result, or the exception thrown.
    pub outcome: String,
    /// The value returned, if the method returned a primitive or an array.
    pub returned: Option<Value>,
    /// The elements of a returned array.
    pub result_array: Option<Vec<Value>>,
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
    let mut m = Machine::new(cp);
    m.monitor = false;
    let _ = m.begin_case();
    let ret = &signature.ret;
    let values = values_for(&mut m, arguments, &signature.params);
    let outcome = m.call_static(class_internal, method, descriptor, values.clone());
    let after = arrays_of(&m, &values, signature);
    match outcome {
        Ok(Some(v)) => {
            let array = match v {
                Value::Ref(r) => match m.heap.get(r) {
                    Object::Array { data, .. } => Some(data.clone()),
                    _ => None,
                },
                _ => None,
            };
            let text = match (&array, ret) {
                (Some(data), Type::Array(element)) => self::array(data, element),
                _ => render::value(&mut m, v, ret).unwrap_or_else(|f| render::fault(&m, &f)),
            };
            let returned = (ret.is_primitive() || array.is_some()).then_some(v);
            Replayed { outcome: text, returned, result_array: array, arrays_after: after, thrown: None }
        }
        Ok(None) => Replayed { outcome: "void".to_string(), returned: None, result_array: None, arrays_after: after, thrown: None },
        Err(Fault::Throw(r)) => Replayed { outcome: render::thrown(&m, r), returned: None, result_array: None, arrays_after: after, thrown: Some(m.class_of(r)) },
        Err(f) => Replayed { outcome: format!("<could not replay: {}>", render::fault(&m, &f)), returned: None, result_array: None, arrays_after: after, thrown: None },
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
