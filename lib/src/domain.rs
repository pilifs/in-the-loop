//! Enumerates every value of a type whose values are finite: booleans, enums, records of finite types, and sealed
//! hierarchies of those. Such a type is an algebraic data type, so a method whose parameters all have such types
//! has finitely many inputs, and running it on each of them decides its behaviour completely.
//!
//! The values are built in the interpreter: enum constants by initialising the enum class, records by calling
//! their canonical constructor (a compact constructor that rejects a combination means that value does not exist).

use std::collections::HashSet;

use crate::classfile::Type;
use crate::interp::{Fault, Machine, Value};

/// The most cases a domain may have; beyond this the domain counts as unbounded.
pub const MAX_CASES: usize = 100_000;

/// A parameter type with infinitely many values, such as `long` or `String`, or a domain too large to enumerate.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Unbounded(pub String);

/// Why a domain could not be enumerated.
#[derive(Debug, Clone, PartialEq)]
pub enum DomainError {
    Unbounded(String),
    Execution(Fault),
}

impl From<Fault> for DomainError {
    fn from(f: Fault) -> DomainError {
        DomainError::Execution(f)
    }
}

/// Options for enumeration.
#[derive(Debug, Clone, Copy, Default)]
pub struct Options {
    /// Whether record components of reference type also take `null`. The JVM allows it; the default follows the
    /// original tool and leaves it out.
    pub null_components: bool,
}

/// Every value of `t`. A top-level reference parameter also takes `null` when `nullable`, because callers can
/// pass it.
pub fn values(m: &mut Machine, t: &Type, nullable: bool, options: Options) -> Result<Vec<Value>, DomainError> {
    let mut out = enumerate(m, t, &mut HashSet::new(), options)?;
    if nullable && t.is_reference() {
        out.push(Value::Null);
    }
    Ok(out)
}

fn enumerate(m: &mut Machine, t: &Type, visiting: &mut HashSet<String>, options: Options) -> Result<Vec<Value>, DomainError> {
    match t {
        Type::Boolean => Ok(vec![Value::Int(0), Value::Int(1)]),
        Type::Object(name) if name == "java/lang/Boolean" => {
            let f = crate::interp::natives::box_value(m, name, Value::Int(0));
            let t = crate::interp::natives::box_value(m, name, Value::Int(1));
            Ok(vec![f, t])
        }
        Type::Object(name) => {
            if !visiting.insert(name.clone()) {
                return Err(DomainError::Unbounded(format!("{} is recursive", name.replace('/', "."))));
            }
            let result = enumerate_class(m, name, visiting, options);
            visiting.remove(name);
            result
        }
        other => Err(DomainError::Unbounded(format!("{} has unboundedly many values", other.java_name()))),
    }
}

fn enumerate_class(m: &mut Machine, name: &str, visiting: &mut HashSet<String>, options: Options) -> Result<Vec<Value>, DomainError> {
    let Some(class) = m.cp.application(name).map_err(|e| DomainError::Execution(Fault::Unsupported(e.to_string())))? else {
        return Err(DomainError::Unbounded(format!("{} has unboundedly many values", name.replace('/', "."))));
    };
    if class.is_enum() {
        return Ok(m.enum_constants(name)?);
    }
    if class.is_record() {
        return records(m, name, visiting, options);
    }
    if class.is_sealed() {
        let mut out = Vec::new();
        for sub in class.permitted_subclasses().map_err(|e| DomainError::Execution(Fault::Unsupported(e.to_string())))? {
            out.extend(enumerate(m, &Type::Object(sub), visiting, options)?);
        }
        return Ok(out);
    }
    Err(DomainError::Unbounded(format!("{} has unboundedly many values", name.replace('/', "."))))
}

fn records(m: &mut Machine, name: &str, visiting: &mut HashSet<String>, options: Options) -> Result<Vec<Value>, DomainError> {
    let class = m.cp.application(name).ok().flatten().expect("checked");
    let components = class.record_components().map_err(|e| DomainError::Execution(Fault::Unsupported(e.to_string())))?;
    let mut domains = Vec::new();
    let mut descriptor = String::from("(");
    for c in &components {
        let t = Type::parse(&c.descriptor).map_err(|e| DomainError::Execution(Fault::Unsupported(e.to_string())))?;
        let mut values = enumerate(m, &t, visiting, options)?;
        if options.null_components && t.is_reference() {
            values.push(Value::Null);
        }
        domains.push(values);
        descriptor.push_str(&c.descriptor);
    }
    descriptor.push_str(")V");
    let mut out = Vec::new();
    for args in product(&domains)? {
        match m.construct(name, &descriptor, args) {
            Ok(v) => out.push(v),
            Err(Fault::Throw(_)) => {} // a compact constructor that rejects these components: the value does not exist
            Err(other) => return Err(DomainError::Execution(other)),
        }
    }
    Ok(out)
}

/// The cartesian product, in order: the last list varies fastest.
pub fn product(domains: &[Vec<Value>]) -> Result<Vec<Vec<Value>>, DomainError> {
    let mut result: Vec<Vec<Value>> = vec![Vec::new()];
    for domain in domains {
        if result.len().saturating_mul(domain.len()) > MAX_CASES {
            return Err(DomainError::Unbounded(format!("more than {MAX_CASES} cases")));
        }
        let mut next = Vec::with_capacity(result.len() * domain.len());
        for prefix in &result {
            for value in domain {
                let mut extended = prefix.clone();
                extended.push(*value);
                next.push(extended);
            }
        }
        result = next;
    }
    Ok(result)
}

/// A description of a parameter's domain for the contract header: `OrderStatus (6)`.
pub fn describe(t: &Type, count: usize) -> String {
    format!("{} ({count})", t.simple_name())
}

/// The outcome of a dry enumeration without a machine: whether a type is finite by its shape alone.
pub fn is_finite_shape(cp: &crate::classpath::ClassPath, t: &Type, visiting: &mut HashSet<String>) -> bool {
    match t {
        Type::Boolean => true,
        Type::Object(name) if name == "java/lang/Boolean" => true,
        Type::Object(name) => {
            if !visiting.insert(name.clone()) {
                return false;
            }
            let finite = match cp.application(name).ok().flatten() {
                Some(class) if class.is_enum() => true,
                Some(class) if class.is_record() => class
                    .record_components()
                    .map(|cs| cs.iter().all(|c| Type::parse(&c.descriptor).map(|t| is_finite_shape(cp, &t, visiting)).unwrap_or(false)))
                    .unwrap_or(false),
                Some(class) if class.is_sealed() => class
                    .permitted_subclasses()
                    .map(|subs| subs.iter().all(|s| is_finite_shape(cp, &Type::Object(s.clone()), visiting)))
                    .unwrap_or(false),
                _ => false,
            };
            visiting.remove(name);
            finite
        }
        _ => false,
    }
}
