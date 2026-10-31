//! A canonical text form of values, used on both sides of a contract. It depends only on the values' structure,
//! never on `toString` overrides or identity hash codes, so equal behaviour renders equally on every run.
//!
//! The numeric formats are Java's (`Integer.toString`, `Double.toString`), so that a contract written by this
//! tool matches one written by reflection on a JVM.

use crate::classfile::Type;

use super::{Exec, Fault, Machine, Native, Object, Ref, Value};

/// A primitive value as Java's `String.valueOf` prints it, given its static type.
pub fn primitive(v: Value, t: &Type) -> String {
    match (t, v) {
        (Type::Boolean, Value::Int(x)) => (x != 0).to_string(),
        (Type::Char, Value::Int(x)) => char_to_string(x),
        (_, Value::Int(x)) => x.to_string(),
        (_, Value::Long(x)) => x.to_string(),
        (_, Value::Float(x)) => float_to_string(x),
        (_, Value::Double(x)) => double_to_string(x),
        (_, Value::Null) => "null".into(),
        (_, Value::Ref(_)) => "<reference>".into(),
    }
}

pub fn char_to_string(unit: i32) -> String {
    String::from_utf16_lossy(&[unit as u16])
}

/// A primitive value as a witness is shown: as [`primitive`], except that a char is a Java literal (`'a'`,
/// `'\u0000'`), so that a control character or a surrogate is readable.
pub fn witness(v: Value, t: &Type) -> String {
    match (t, v) {
        (Type::Char, Value::Int(x)) => {
            let unit = x as u16;
            match char::from_u32(u32::from(unit)) {
                Some('\'') => "'\\''".into(),
                Some('\\') => "'\\\\'".into(),
                Some(c) if !c.is_control() => format!("'{c}'"),
                _ => format!("'\\u{unit:04x}'"),
            }
        }
        _ => primitive(v, t),
    }
}

/// `Double.toString`: the shortest decimal that round-trips, in Java's layout.
pub fn double_to_string(x: f64) -> String {
    if x.is_nan() {
        return "NaN".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "Infinity".into() } else { "-Infinity".into() };
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    java_number_layout(&format!("{x:e}"), x.abs())
}

/// `Float.toString`.
pub fn float_to_string(x: f32) -> String {
    if x.is_nan() {
        return "NaN".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "Infinity".into() } else { "-Infinity".into() };
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    java_number_layout(&format!("{x:e}"), f64::from(x.abs()))
}

/// Lays out shortest digits (`d.ddde±n` from Rust) the way Java does: plain between 1e-3 and 1e7, else `d.dddE±n`.
fn java_number_layout(scientific: &str, magnitude: f64) -> String {
    let (sign, rest) = match scientific.strip_prefix('-') {
        Some(r) => ("-", r),
        None => ("", scientific),
    };
    let (mantissa, exponent) = rest.split_once('e').expect("scientific form");
    let exponent: i32 = exponent.parse().expect("exponent");
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    if (1e-3..1e7).contains(&magnitude) {
        let body = if exponent >= 0 {
            let point = exponent as usize + 1;
            let mut int_part = digits.clone();
            while int_part.len() < point {
                int_part.push('0');
            }
            let (int_part, frac) = int_part.split_at(point);
            let frac = if frac.is_empty() { "0" } else { frac };
            format!("{int_part}.{frac}")
        } else {
            format!("0.{}{digits}", "0".repeat((-exponent - 1) as usize))
        };
        format!("{sign}{body}")
    } else {
        let (first, rest) = digits.split_at(1);
        let rest = if rest.is_empty() { "0" } else { rest };
        format!("{sign}{first}.{rest}E{exponent}")
    }
}

fn quote(s: &str) -> String {
    format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\"").replace('\n', "\\n"))
}

/// A value as the contract records it. For a reference, the structure decides: an enum by its name, a string
/// quoted, a boxed primitive as a number, a record as `Name[component=value, ...]`, a collection as `[...]`,
/// anything else as `<class name>`.
pub fn value(m: &mut Machine, v: Value, static_type: &Type) -> Exec<String> {
    if static_type.is_primitive() {
        return Ok(primitive(v, static_type));
    }
    match v {
        Value::Null => Ok("null".into()),
        Value::Ref(r) => reference(m, r),
        other => Ok(primitive(other, static_type)),
    }
}

fn reference(m: &mut Machine, r: Ref) -> Exec<String> {
    match m.heap.get(r).clone() {
        Object::Instance { class, base: super::Base::Enum { name, .. }, .. } => {
            let _ = class;
            Ok(name)
        }
        Object::Instance { class, .. } => {
            let cf = m.cp.application(&class).ok().flatten();
            match cf {
                Some(cf) if cf.is_record() => {
                    let components = cf.record_components().map_err(|e| Fault::Unsupported(e.to_string()))?;
                    let mut parts = Vec::new();
                    for c in components {
                        let t = Type::parse(&c.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
                        let accessor = format!("(){}", c.descriptor);
                        let got = m.call_virtual(Value::Ref(r), &class, &c.name, &accessor, Vec::new())?.unwrap_or(Value::Null);
                        parts.push(format!("{}={}", c.name, value(m, got, &t)?));
                    }
                    Ok(format!("{}[{}]", cf.simple_name(), parts.join(", ")))
                }
                _ => Ok(format!("<{}>", class.replace('/', "."))),
            }
        }
        Object::Array { .. } => Ok(format!("<{}>", m.class_of(r).replace('/', "."))),
        Object::Native(native) => match native {
            Native::String(s) => Ok(quote(&s)),
            Native::Boxed { class, value: boxed } => {
                let t = match class.as_str() {
                    "java/lang/Boolean" => Type::Boolean,
                    "java/lang/Character" => Type::Char,
                    "java/lang/Long" => Type::Long,
                    "java/lang/Float" => Type::Float,
                    "java/lang/Double" => Type::Double,
                    _ => Type::Int,
                };
                Ok(primitive(boxed, &t))
            }
            Native::List { elements, .. } | Native::Set { elements, .. } => {
                let mut parts = Vec::new();
                for e in elements {
                    parts.push(value(m, e, &Type::object("java/lang/Object"))?);
                }
                Ok(format!("[{}]", parts.join(", ")))
            }
            other => Ok(format!("<{}>", other.class_name().replace('/', "."))),
        },
    }
}

/// An exception as an outcome: `throws Name` or `throws Name("message")`. A `NullPointerException`'s message is
/// left out: the JVM writes it, and its wording changes between versions.
pub fn thrown(m: &Machine, exception: Ref) -> String {
    let class = m.class_of(exception);
    let simple = match m.cp.application(&class).ok().flatten() {
        Some(cf) => cf.simple_name(),
        None => crate::classfile::simple_name_of(&class),
    };
    let message = super::natives::throwable_message(m, exception);
    match message {
        Some(msg) if class != "java/lang/NullPointerException" => format!("throws {simple}({})", quote(&msg)),
        _ => format!("throws {simple}"),
    }
}

/// An execution fault as an outcome, for the parts of the tool that report rather than refuse.
pub fn fault(m: &Machine, fault: &Fault) -> String {
    match fault {
        Fault::Throw(r) => thrown(m, *r),
        Fault::Unsupported(s) => format!("<unsupported: {s}>"),
        Fault::Impure(s) => format!("<impure: {s}>"),
        Fault::Budget(s) => format!("<budget: {s}>"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn numbers_print_as_java_prints_them() {
        assert_eq!(double_to_string(1.0), "1.0");
        assert_eq!(double_to_string(0.1), "0.1");
        assert_eq!(double_to_string(100.0), "100.0");
        assert_eq!(double_to_string(1234567.0), "1234567.0");
        assert_eq!(double_to_string(1e7), "1.0E7");
        assert_eq!(double_to_string(12345678.9), "1.23456789E7");
        assert_eq!(double_to_string(0.001), "0.001");
        assert_eq!(double_to_string(0.0001), "1.0E-4");
        assert_eq!(double_to_string(-2.5e-5), "-2.5E-5");
        assert_eq!(double_to_string(f64::NAN), "NaN");
        assert_eq!(double_to_string(-0.0), "-0.0");
        assert_eq!(double_to_string(f64::MAX), "1.7976931348623157E308");
        // Java prints Double.MIN_VALUE with two digits (4.9E-324), where the shortest round-trip is one (5E-324).
        // Subnormals are the one place the two algorithms differ, and no contract depends on them.
        assert_eq!(double_to_string(5e-324), "5.0E-324");
        assert_eq!(float_to_string(1.5), "1.5");
        assert_eq!(float_to_string(0.1), "0.1");
        assert_eq!(float_to_string(3.4028235e38), "3.4028235E38");
        assert_eq!(primitive(Value::Int(1), &Type::Boolean), "true");
        assert_eq!(primitive(Value::Int(65), &Type::Char), "A");
    }
}
