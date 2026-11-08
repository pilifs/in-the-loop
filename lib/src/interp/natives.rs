//! Native models of the JDK classes the interpreter supports. Each model reproduces the observable behaviour of
//! the JDK method, including the exception type and message it throws, so that a contract derived here matches
//! one derived by running the method on a JVM. A method that is not modelled stops execution with
//! [`Fault::Unsupported`].

use crate::classfile::{BootstrapArg, ClassFile, MethodDescriptor, MethodHandle, Type};

use super::render::{double_to_string, float_to_string, primitive};
use super::{Base, Exec, Fault, JStr, Machine, Native, Object, Ref, Value};

/// A primitive value as `String.valueOf` gives it: a char is its one code unit, whatever it is, a surrogate
/// included, and every other primitive is ASCII text.
fn primitive_units(v: Value, t: &Type) -> JStr {
    match (t, v) {
        (Type::Char, Value::Int(x)) => JStr::from_units(vec![x as u16]),
        _ => JStr::from(primitive(v, t)),
    }
}

/// The code units of a `char[]`'s elements, or `None` for an object that is not an array.
fn char_array_units(m: &Machine, r: Ref) -> Option<JStr> {
    match m.heap.get(r) {
        Object::Array { data, .. } => Some(JStr::from_units(data.iter().map(|v| v.as_int() as u16).collect())),
        _ => None,
    }
}

/// The text of `s`, for an operation whose meaning comes from Unicode's tables (case, whitespace, number syntax):
/// refused for a String with an isolated surrogate, which those tables are not consulted on here, rather than
/// answered for the U+FFFD a Rust string would make of it.
fn text_of(s: &JStr, what: &str) -> Exec<String> {
    s.text().ok_or_else(|| Fault::Unsupported(format!("{what} of a String with an isolated surrogate ({})", s.display())))
}

/// Whether a code point is whitespace as `Character.isWhitespace` says: a space, line or paragraph separator other
/// than the non-breaking ones (U+00A0, U+2007, U+202F), or one of the controls U+0009–U+000D and U+001C–U+001F.
fn java_whitespace(c: u32) -> bool {
    matches!(c, 0x09..=0x0D | 0x1C..=0x20 | 0x1680 | 0x2000..=0x2006 | 0x2008..=0x200A | 0x2028 | 0x2029 | 0x205F | 0x3000)
}

/// The code points of `units`, an isolated surrogate as itself, as `String.codePoints` gives them, with the
/// index of the code unit each starts at.
fn code_points(units: &[u16]) -> Vec<(usize, u32)> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < units.len() {
        let u = units[i];
        if (0xD800..0xDC00).contains(&u) && i + 1 < units.len() && (0xDC00..0xE000).contains(&units[i + 1]) {
            out.push((i, 0x10000 + ((u32::from(u) - 0xD800) << 10) + (u32::from(units[i + 1]) - 0xDC00)));
            i += 2;
        } else {
            out.push((i, u32::from(u)));
            i += 1;
        }
    }
    out
}

/// `strip`, `stripLeading` and `stripTrailing`: the code units between the first and last code points that are not
/// `Character.isWhitespace`.
fn strip(units: &[u16], leading: bool, trailing: bool) -> JStr {
    let points = code_points(units);
    let start = if leading { points.iter().find(|(_, c)| !java_whitespace(*c)).map(|(i, _)| *i).unwrap_or(units.len()) } else { 0 };
    let end = if trailing {
        points.iter().rev().find(|(_, c)| !java_whitespace(*c)).map(|(i, c)| i + if *c >= 0x10000 { 2 } else { 1 }).unwrap_or(start)
    } else {
        units.len()
    };
    JStr::from_units(units[start..end.max(start)].to_vec())
}

fn unsupported<T>(what: impl Into<String>) -> Exec<T> {
    Err(Fault::Unsupported(what.into()))
}

fn index_message(index: i64, length: usize) -> String {
    format!("Index {index} out of bounds for length {length}")
}

/// `String.hashCode`.
pub fn string_hash(s: &str) -> i32 {
    s.encode_utf16().fold(0i32, |h, c| h.wrapping_mul(31).wrapping_add(i32::from(c)))
}

/// The message of a throwable object (native or an application instance), if any.
pub fn throwable_message(m: &Machine, r: Ref) -> Option<JStr> {
    let message = match m.heap.get(r) {
        Object::Native(Native::Throwable { message, .. }) => *message,
        Object::Instance { base: Base::Throwable { message, .. }, .. } => *message,
        _ => None,
    };
    message.and_then(|s| m.heap.string(s).cloned())
}

fn throwable_cause(m: &Machine, r: Ref) -> Option<Ref> {
    match m.heap.get(r) {
        Object::Native(Native::Throwable { cause, .. }) => *cause,
        Object::Instance { base: Base::Throwable { cause, .. }, .. } => *cause,
        _ => None,
    }
}

fn set_throwable(m: &mut Machine, r: Ref, message: Option<Ref>, cause: Option<Ref>, set_message: bool, set_cause: bool) {
    match m.heap.get_mut(r) {
        Object::Native(Native::Throwable { message: msg, cause: c, .. }) => {
            if set_message {
                *msg = message;
            }
            if set_cause {
                *c = cause;
            }
        }
        Object::Instance { base: Base::Throwable { message: msg, cause: c }, .. } => {
            if set_message {
                *msg = message;
            }
            if set_cause {
                *c = cause;
            }
        }
        _ => {}
    }
}

// Boxing

fn box_class_of(t: &Type) -> Option<&'static str> {
    Some(match t {
        Type::Boolean => "java/lang/Boolean",
        Type::Byte => "java/lang/Byte",
        Type::Char => "java/lang/Character",
        Type::Short => "java/lang/Short",
        Type::Int => "java/lang/Integer",
        Type::Long => "java/lang/Long",
        Type::Float => "java/lang/Float",
        Type::Double => "java/lang/Double",
        _ => return None,
    })
}

fn is_box_class(name: &str) -> bool {
    matches!(name, "java/lang/Boolean" | "java/lang/Byte" | "java/lang/Character" | "java/lang/Short" | "java/lang/Integer" | "java/lang/Long" | "java/lang/Float" | "java/lang/Double")
}

/// Boxes a primitive as the JDK's `valueOf` does, with the JDK's identity cache for small values.
pub fn box_value(m: &mut Machine, class: &str, v: Value) -> Value {
    let v = match (class, v) {
        ("java/lang/Boolean", Value::Int(x)) => Value::Int((x != 0) as i32),
        ("java/lang/Byte", Value::Int(x)) => Value::Int(x as i8 as i32),
        ("java/lang/Short", Value::Int(x)) => Value::Int(x as i16 as i32),
        ("java/lang/Character", Value::Int(x)) => Value::Int(x as u16 as i32),
        (_, v) => v,
    };
    let cached = match (class, v) {
        ("java/lang/Boolean", Value::Int(x)) => Some(i64::from(x)),
        ("java/lang/Byte", Value::Int(x)) => Some(i64::from(x)),
        ("java/lang/Short" | "java/lang/Integer", Value::Int(x)) if (-128..=127).contains(&x) => Some(i64::from(x)),
        ("java/lang/Character", Value::Int(x)) if (0..=127).contains(&x) => Some(i64::from(x)),
        ("java/lang/Long", Value::Long(x)) if (-128..=127).contains(&x) => Some(x),
        _ => None,
    };
    if let Some(key) = cached {
        if let Some(&r) = m.boxes.get(&(class.to_string(), key)) {
            return Value::Ref(r);
        }
        m.clinit_depth += 1; // cached boxes are global state
        let r = m.alloc_native(Native::Boxed { class: class.to_string(), value: v });
        m.clinit_depth -= 1;
        m.boxes.insert((class.to_string(), key), r);
        return Value::Ref(r);
    }
    Value::Ref(m.alloc_native(Native::Boxed { class: class.to_string(), value: v }))
}

/// Unboxes a boxed primitive; null throws `NullPointerException`.
pub fn unbox(m: &mut Machine, v: Value) -> Exec<Value> {
    match v {
        Value::Null => Err(m.npe()),
        Value::Ref(r) => match m.heap.get(r) {
            Object::Native(Native::Boxed { value, .. }) => Ok(*value),
            _ => unsupported(format!("unboxing a {}", m.class_of(r))),
        },
        primitive => Ok(primitive),
    }
}

fn boxed_type(class: &str) -> Type {
    match class {
        "java/lang/Boolean" => Type::Boolean,
        "java/lang/Byte" => Type::Byte,
        "java/lang/Character" => Type::Char,
        "java/lang/Short" => Type::Short,
        "java/lang/Long" => Type::Long,
        "java/lang/Float" => Type::Float,
        "java/lang/Double" => Type::Double,
        _ => Type::Int,
    }
}

// Strings and conversions

/// `String.valueOf(x)` for a value of the given static type.
pub fn to_java_string(m: &mut Machine, v: Value, t: &Type) -> Exec<JStr> {
    match v {
        Value::Null => Ok("null".into()),
        Value::Ref(r) => object_to_string(m, r),
        other => Ok(primitive_units(other, t)),
    }
}

/// `obj.toString()` with virtual dispatch: an application override, else the JDK's own.
pub fn object_to_string(m: &mut Machine, r: Ref) -> Exec<JStr> {
    let result = m.call_virtual(Value::Ref(r), "java/lang/Object", "toString", "()Ljava/lang/String;", Vec::new())?;
    match result {
        Some(Value::Ref(s)) => m.heap.string(s).cloned().ok_or_else(|| Fault::Unsupported("toString returned a non-string".into())),
        Some(Value::Null) => Ok("null".into()),
        _ => unsupported("toString returned nothing"),
    }
}

fn native_to_string(m: &mut Machine, r: Ref) -> Exec<JStr> {
    let native = match m.heap.get(r) {
        Object::Native(n) => n.clone(),
        _ => return unsupported("not a native object"),
    };
    Ok(match native {
        Native::String(s) => s,
        Native::Boxed { class, value } => primitive_units(value, &boxed_type(&class)),
        Native::StringBuilder(s) => s,
        Native::List { elements, .. } | Native::Set { elements, .. } => {
            let mut parts = Vec::new();
            for e in elements {
                parts.push(to_java_string(m, e, &Type::object("java/lang/Object"))?);
            }
            let mut out = JStr::from("[");
            out.push(&JStr::join(&parts, &JStr::from(", ")));
            out.push_str("]");
            out
        }
        Native::Map { entries, .. } => {
            let mut parts = Vec::new();
            for (k, v) in entries {
                let mut part = to_java_string(m, k, &Type::object("java/lang/Object"))?;
                part.push_str("=");
                part.push(&to_java_string(m, v, &Type::object("java/lang/Object"))?);
                parts.push(part);
            }
            let mut out = JStr::from("{");
            out.push(&JStr::join(&parts, &JStr::from(", ")));
            out.push_str("}");
            out
        }
        Native::Class(t) => match &t {
            Type::Object(name) => {
                let interface = m.cp.application(name).ok().flatten().is_some_and(|c| c.is_interface());
                format!("{} {}", if interface { "interface" } else { "class" }, name.replace('/', "."))
            }
            other => format!("class {}", other.class_get_name()),
        }
        .into(),
        Native::Throwable { class, message, .. } => match message.and_then(|s| m.heap.string(s).cloned()) {
            Some(msg) => {
                let mut out = JStr::from(format!("{}: ", class.replace('/', ".")));
                out.push(&msg);
                out
            }
            None => class.replace('/', ".").into(),
        },
        Native::Optional(None) => "Optional.empty".into(),
        Native::Optional(Some(v)) => {
            let mut out = JStr::from("Optional[");
            out.push(&to_java_string(m, v, &Type::object("java/lang/Object"))?);
            out.push_str("]");
            out
        }
        Native::Iterator { .. } => return unsupported("Iterator.toString is identity-based"),
        Native::Lambda { .. } => return unsupported("a lambda's toString is identity-based"),
    })
}

/// `Objects.equals(a, b)` with virtual dispatch of `equals`.
pub fn equals(m: &mut Machine, a: Value, b: Value) -> Exec<bool> {
    match (a, b) {
        (Value::Null, Value::Null) => Ok(true),
        (Value::Null, _) | (_, Value::Null) => Ok(false),
        (Value::Ref(x), Value::Ref(y)) if x == y => Ok(true),
        (Value::Ref(x), _) => {
            let result = m.call_virtual(Value::Ref(x), "java/lang/Object", "equals", "(Ljava/lang/Object;)Z", vec![b])?;
            Ok(result.map(|v| v.as_int() != 0).unwrap_or(false))
        }
        (x, y) => Ok(x == y),
    }
}

fn native_equals(m: &mut Machine, r: Ref, other: Value) -> Exec<bool> {
    let Value::Ref(o) = other else { return Ok(false) };
    if r == o {
        return Ok(true);
    }
    let (a, b) = match (m.heap.get(r), m.heap.get(o)) {
        (Object::Native(a), Object::Native(b)) => (a.clone(), b.clone()),
        _ => return Ok(false),
    };
    Ok(match (a, b) {
        (Native::String(x), Native::String(y)) => x == y,
        (Native::Boxed { class: c1, value: v1 }, Native::Boxed { class: c2, value: v2 }) => {
            c1 == c2
                && match (v1, v2) {
                    (Value::Float(x), Value::Float(y)) => x.to_bits() == y.to_bits() || (x.is_nan() && y.is_nan()),
                    (Value::Double(x), Value::Double(y)) => x.to_bits() == y.to_bits() || (x.is_nan() && y.is_nan()),
                    (x, y) => x == y,
                }
        }
        (Native::List { elements: x, .. }, Native::List { elements: y, .. }) => {
            if x.len() != y.len() {
                return Ok(false);
            }
            for (p, q) in x.into_iter().zip(y) {
                if !equals(m, p, q)? {
                    return Ok(false);
                }
            }
            true
        }
        (Native::Set { elements: x, .. }, Native::Set { elements: y, .. }) => {
            if x.len() != y.len() {
                return Ok(false);
            }
            for p in &x {
                let mut found = false;
                for q in &y {
                    if equals(m, *p, *q)? {
                        found = true;
                        break;
                    }
                }
                if !found {
                    return Ok(false);
                }
            }
            true
        }
        (Native::Map { entries: x, .. }, Native::Map { entries: y, .. }) => {
            if x.len() != y.len() {
                return Ok(false);
            }
            for (k, v) in &x {
                let mut found = false;
                for (k2, v2) in &y {
                    if equals(m, *k, *k2)? {
                        found = equals(m, *v, *v2)?;
                        break;
                    }
                }
                if !found {
                    return Ok(false);
                }
            }
            true
        }
        (Native::Class(x), Native::Class(y)) => x == y,
        (Native::Optional(x), Native::Optional(y)) => match (x, y) {
            (None, None) => true,
            (Some(p), Some(q)) => equals(m, p, q)?,
            _ => false,
        },
        _ => false,
    })
}

/// `Objects.hashCode(v)` with virtual dispatch.
pub fn hash_code(m: &mut Machine, v: Value) -> Exec<i32> {
    match v {
        Value::Null => Ok(0),
        Value::Int(x) => Ok(x),
        Value::Long(x) => Ok((x ^ (x >> 32)) as i32),
        Value::Float(x) => Ok(x.to_bits() as i32),
        Value::Double(x) => {
            let bits = x.to_bits();
            Ok((bits ^ (bits >> 32)) as i32)
        }
        Value::Ref(r) => {
            let result = m.call_virtual(Value::Ref(r), "java/lang/Object", "hashCode", "()I", Vec::new())?;
            Ok(result.map(Value::as_int).unwrap_or(0))
        }
    }
}

fn native_hash(m: &mut Machine, r: Ref) -> Exec<i32> {
    let native = match m.heap.get(r) {
        Object::Native(n) => n.clone(),
        _ => return unsupported("not a native object"),
    };
    Ok(match native {
        Native::String(s) => s.hash_code(),
        Native::Boxed { value, class } => match (class.as_str(), value) {
            ("java/lang/Boolean", Value::Int(x)) => {
                if x != 0 {
                    1231
                } else {
                    1237
                }
            }
            (_, v) => hash_code(m, v)?,
        },
        Native::List { elements, .. } => {
            let mut h: i32 = 1;
            for e in elements {
                h = h.wrapping_mul(31).wrapping_add(hash_code(m, e)?);
            }
            h
        }
        Native::Set { elements, .. } => {
            let mut h: i32 = 0;
            for e in elements {
                h = h.wrapping_add(hash_code(m, e)?);
            }
            h
        }
        Native::Map { entries, .. } => {
            let mut h: i32 = 0;
            for (k, v) in entries {
                h = h.wrapping_add(hash_code(m, k)? ^ hash_code(m, v)?);
            }
            h
        }
        Native::Class(t) => string_hash(&t.class_get_name()),
        Native::Optional(None) => 0,
        Native::Optional(Some(v)) => hash_code(m, v)?,
        other => return unsupported(format!("{}.hashCode is identity-based", other.class_name().replace('/', "."))),
    })
}

// Static state of JDK classes

pub fn get_static_jdk(m: &mut Machine, class: &str, name: &str) -> Exec<Value> {
    match (class, name) {
        ("java/lang/Boolean", "TRUE") => Ok(box_value(m, "java/lang/Boolean", Value::Int(1))),
        ("java/lang/Boolean", "FALSE") => Ok(box_value(m, "java/lang/Boolean", Value::Int(0))),
        ("java/lang/Integer", "MAX_VALUE") => Ok(Value::Int(i32::MAX)),
        ("java/lang/Integer", "MIN_VALUE") => Ok(Value::Int(i32::MIN)),
        ("java/lang/Long", "MAX_VALUE") => Ok(Value::Long(i64::MAX)),
        ("java/lang/Long", "MIN_VALUE") => Ok(Value::Long(i64::MIN)),
        ("java/math/RoundingMode", _) | ("java/util/concurrent/TimeUnit", _) => unsupported(format!("static field {}.{name}", class.replace('/', "."))),
        _ => unsupported(format!("reads static field {}.{name}", class.replace('/', "."))),
    }
}

// Objects of JDK classes

pub fn new_jdk_object(m: &mut Machine, class: &str) -> Exec<Value> {
    let native = match class {
        "java/lang/StringBuilder" | "java/lang/StringBuffer" => Native::StringBuilder(JStr::new()),
        // A String the program constructs: `<init>` gives it its contents (`invoke_special_jdk`).
        "java/lang/String" => Native::String(JStr::new()),
        "java/util/ArrayList" | "java/util/LinkedList" => Native::List { elements: Vec::new(), mutable: true },
        "java/util/HashMap" | "java/util/LinkedHashMap" | "java/util/TreeMap" => Native::Map { entries: Vec::new(), mutable: true },
        "java/util/HashSet" | "java/util/LinkedHashSet" | "java/util/TreeSet" => Native::Set { elements: Vec::new(), mutable: true },
        "java/lang/Object" => return Ok(Value::Ref(m.alloc(Object::Instance { class: class.into(), fields: Default::default(), base: Base::Object }))),
        _ if m.cp.is_subtype(class, "java/lang/Throwable") => Native::Throwable { class: class.into(), message: None, cause: None },
        _ => return unsupported(format!("new {}", class.replace('/', "."))),
    };
    Ok(Value::Ref(m.alloc_native(native)))
}

/// `invokespecial` on a JDK owner: a constructor of a modelled class, or a `super.` call into the JDK.
pub fn invoke_special_jdk(m: &mut Machine, r: Ref, owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    if let Object::Instance { .. } = m.heap.get(r) {
        return invoke_inherited(m, r, owner, name, descriptor, args);
    }
    if name != "<init>" {
        return invoke_native_virtual(m, r, owner, name, descriptor, args);
    }
    let native = match m.heap.get(r) {
        Object::Native(n) => n.clone(),
        _ => return unsupported("constructor on a non-native"),
    };
    match native {
        Native::Throwable { .. } => {
            init_throwable(m, r, descriptor, &args)?;
        }
        Native::StringBuilder(_) => {
            let initial = match descriptor {
                "()V" => JStr::new(),
                // AbstractStringBuilder allocates the capacity: a negative one is a NegativeArraySizeException.
                "(I)V" if args[0].as_int() < 0 => return Err(m.throw("java/lang/NegativeArraySizeException", Some(&args[0].as_int().to_string()))),
                "(I)V" => JStr::new(),
                "(Ljava/lang/String;)V" | "(Ljava/lang/CharSequence;)V" => char_sequence(m, args[0])?,
                _ => return unsupported(format!("StringBuilder.<init>{descriptor}")),
            };
            *m.heap.get_mut(r) = Object::Native(Native::StringBuilder(initial));
        }
        Native::String(_) => {
            let contents = match descriptor {
                "()V" => JStr::new(),
                "(Ljava/lang/String;)V" => string_arg(m, args[0])?,
                "([C)V" => {
                    let Some(a) = args[0].as_ref() else { return Err(m.npe()) };
                    char_array_units(m, a).ok_or_else(|| Fault::Unsupported("new String of a non-array".into()))?
                }
                "([CII)V" => {
                    let Some(a) = args[0].as_ref() else { return Err(m.npe()) };
                    let units = char_array_units(m, a).ok_or_else(|| Fault::Unsupported("new String of a non-array".into()))?;
                    let (offset, count) = (args[1].as_int(), args[2].as_int());
                    if offset < 0 || count < 0 || offset as i64 + count as i64 > units.len() as i64 {
                        return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&format!("offset {offset}, count {count}, length {}", units.len()))));
                    }
                    JStr::from_units(units.units()[offset as usize..(offset + count) as usize].to_vec())
                }
                "(Ljava/lang/StringBuilder;)V" | "(Ljava/lang/StringBuffer;)V" => char_sequence(m, args[0])?,
                _ => return unsupported(format!("String.<init>{descriptor}")),
            };
            *m.heap.get_mut(r) = Object::Native(Native::String(contents));
        }
        Native::List { .. } => {
            let elements = match descriptor {
                "()V" => Vec::new(),
                "(I)V" if args[0].as_int() < 0 => return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("Illegal Capacity: {}", args[0].as_int())))),
                "(I)V" => Vec::new(),
                "(Ljava/util/Collection;)V" => collection_elements(m, args[0])?,
                _ => return unsupported(format!("ArrayList.<init>{descriptor}")),
            };
            *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable: true });
        }
        Native::Set { .. } => {
            let mut elements = Vec::new();
            hash_capacity(m, descriptor, &args)?;
            if descriptor == "(Ljava/util/Collection;)V" {
                for e in collection_elements(m, args[0])? {
                    if !contains(m, &elements, e)? {
                        elements.push(e);
                    }
                }
            } else if !matches!(descriptor, "()V" | "(I)V" | "(IF)V") {
                return unsupported(format!("HashSet.<init>{descriptor}"));
            }
            *m.heap.get_mut(r) = Object::Native(Native::Set { elements, mutable: true });
        }
        Native::Map { .. } => {
            hash_capacity(m, descriptor, &args)?;
            let entries = match descriptor {
                "()V" | "(I)V" | "(IF)V" => Vec::new(),
                "(Ljava/util/Map;)V" => map_entries(m, args[0])?,
                _ => return unsupported(format!("HashMap.<init>{descriptor}")),
            };
            *m.heap.get_mut(r) = Object::Native(Native::Map { entries, mutable: true });
        }
        other => return unsupported(format!("{}.<init>", other.class_name().replace('/', "."))),
    }
    Ok(None)
}

/// What `HashMap(int)` and `HashMap(int, float)` check, and the sets built on one: a negative capacity, or a load
/// factor that is not positive, is an IllegalArgumentException, as on the JVM.
fn hash_capacity(m: &mut Machine, descriptor: &str, args: &[Value]) -> Exec<()> {
    if matches!(descriptor, "(I)V" | "(IF)V") && args[0].as_int() < 0 {
        return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("Illegal initial capacity: {}", args[0].as_int()))));
    }
    if let ("(IF)V", Some(Value::Float(f))) = (descriptor, args.get(1)) {
        if f.is_nan() || *f <= 0.0 {
            return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("Illegal load factor: {}", super::render::float_to_string(*f)))));
        }
    }
    Ok(())
}

fn init_throwable(m: &mut Machine, r: Ref, descriptor: &str, args: &[Value]) -> Exec<()> {
    match descriptor {
        "()V" => {}
        "(Ljava/lang/String;)V" => set_throwable(m, r, args[0].as_ref(), None, true, false),
        "(Ljava/lang/String;Ljava/lang/Throwable;)V" | "(Ljava/lang/String;Ljava/lang/Throwable;ZZ)V" => {
            set_throwable(m, r, args[0].as_ref(), args[1].as_ref(), true, true)
        }
        "(Ljava/lang/Throwable;)V" => {
            let cause = args[0].as_ref();
            let message = match cause {
                Some(c) => {
                    let text = object_to_string(m, c)?;
                    m.new_string(text).as_ref()
                }
                None => None,
            };
            set_throwable(m, r, message, cause, true, true);
        }
        _ => return unsupported(format!("Throwable.<init>{descriptor}")),
    }
    Ok(())
}

/// A method inherited from a JDK superclass, called on an application instance: `Enum.ordinal`,
/// `Throwable.getMessage`, `Object.equals`, ...
pub fn invoke_inherited(m: &mut Machine, r: Ref, owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let (class, base) = match m.heap.get(r) {
        Object::Instance { class, base, .. } => (class.clone(), base.clone()),
        _ => return unsupported("inherited call on a non-instance"),
    };
    match (name, descriptor) {
        ("getClass", "()Ljava/lang/Class;") => return Ok(Some(m.class_object(&Type::Object(class)))),
        ("equals", "(Ljava/lang/Object;)Z") => return Ok(Some(Value::bool(args[0] == Value::Ref(r)))),
        _ => {}
    }
    match base {
        Base::Enum { name: constant, ordinal, text } => match (name, descriptor) {
            ("<init>", "(Ljava/lang/String;I)V") => {
                let constant = m.str_of(args[0]).unwrap_or_default();
                let ordinal = args[1].as_int();
                if let Object::Instance { base, .. } = m.heap.get_mut(r) {
                    *base = Base::Enum { name: constant, ordinal, text: args[0].as_ref() };
                }
                Ok(None)
            }
            // The very string the constructor was given, as on a JVM.
            ("name", _) | ("toString", _) => Ok(Some(match text {
                Some(t) => Value::Ref(t),
                None => m.new_string(constant),
            })),
            ("ordinal", _) => Ok(Some(Value::Int(ordinal))),
            // Enum.hashCode is identity-based on a JVM; here it is the name's hash, which is deterministic.
            ("hashCode", _) => Ok(Some(Value::Int(string_hash(&constant)))),
            ("compareTo", _) => {
                let Some(o) = args[0].as_ref() else { return Err(m.npe()) };
                match m.heap.get(o) {
                    Object::Instance { base: Base::Enum { ordinal: other, .. }, .. } => Ok(Some(Value::Int(ordinal - *other))),
                    _ => Err(m.throw("java/lang/ClassCastException", None)),
                }
            }
            ("getDeclaringClass", _) => {
                let declaring = match m.cp.application(&class).ok().flatten() {
                    Some(cf) if !cf.is_enum() => cf.super_class.clone().unwrap_or(class),
                    _ => class,
                };
                Ok(Some(m.class_object(&Type::Object(declaring))))
            }
            _ => unsupported(format!("Enum.{name}{descriptor}")),
        },
        Base::Throwable { .. } => match name {
            "<init>" => {
                init_throwable(m, r, descriptor, &args)?;
                Ok(None)
            }
            "getMessage" | "getLocalizedMessage" => {
                let message = match m.heap.get(r) {
                    Object::Instance { base: Base::Throwable { message, .. }, .. } => *message,
                    _ => None,
                };
                Ok(Some(message.map(Value::Ref).unwrap_or(Value::Null)))
            }
            "getCause" => Ok(Some(throwable_cause(m, r).map(Value::Ref).unwrap_or(Value::Null))),
            "toString" => {
                let text = match throwable_message(m, r) {
                    Some(msg) => {
                        let mut out = JStr::from(format!("{}: ", class.replace('/', ".")));
                        out.push(&msg);
                        out
                    }
                    None => class.replace('/', ".").into(),
                };
                Ok(Some(m.new_string(text)))
            }
            "initCause" => {
                set_throwable(m, r, None, args[0].as_ref(), false, true);
                Ok(Some(Value::Ref(r)))
            }
            "fillInStackTrace" => Ok(Some(Value::Ref(r))),
            "addSuppressed" => Ok(None),
            "hashCode" => unsupported("Throwable.hashCode is identity-based"),
            _ => unsupported(format!("Throwable.{name}{descriptor}")),
        },
        Base::Object => match (name, descriptor) {
            ("<init>", "()V") => Ok(None),
            ("hashCode", "()I") => unsupported(format!("{}.hashCode is Object's identity hash", class.replace('/', "."))),
            ("toString", _) => unsupported(format!("{}.toString is Object's identity-based default", class.replace('/', "."))),
            _ => unsupported(format!("{}.{name}{descriptor} (inherited from {})", class.replace('/', "."), owner.replace('/', "."))),
        },
    }
}

pub fn invoke_on_array(m: &mut Machine, r: Ref, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    match (name, descriptor) {
        ("clone", _) => {
            let (element, data) = match m.heap.get(r) {
                Object::Array { element, data } => (element.clone(), data.clone()),
                _ => unreachable!(),
            };
            Ok(Some(m.new_array_of(element, data)))
        }
        ("equals", _) => Ok(Some(Value::bool(args[0] == Value::Ref(r)))),
        ("getClass", _) => {
            let t = Type::parse(&m.class_of(r)).map_err(|e| Fault::Unsupported(e.to_string()))?;
            Ok(Some(m.class_object(&t)))
        }
        ("hashCode", _) | ("toString", _) => unsupported(format!("array {name} is identity-based")),
        _ => unsupported(format!("array.{name}{descriptor}")),
    }
}

// Helpers over collections

fn collection_elements(m: &mut Machine, v: Value) -> Exec<Vec<Value>> {
    let Some(r) = v.as_ref() else { return Err(m.npe()) };
    match m.heap.get(r) {
        Object::Native(Native::List { elements, .. }) | Object::Native(Native::Set { elements, .. }) => Ok(elements.clone()),
        Object::Array { data, .. } => Ok(data.clone()),
        _ => unsupported(format!("iterating a {}", m.class_of(r).replace('/', "."))),
    }
}

fn map_entries(m: &mut Machine, v: Value) -> Exec<Vec<(Value, Value)>> {
    let Some(r) = v.as_ref() else { return Err(m.npe()) };
    match m.heap.get(r) {
        Object::Native(Native::Map { entries, .. }) => Ok(entries.clone()),
        _ => unsupported(format!("{} is not a modelled Map", m.class_of(r).replace('/', "."))),
    }
}

fn contains(m: &mut Machine, elements: &[Value], v: Value) -> Exec<bool> {
    for e in elements {
        if equals(m, *e, v)? {
            return Ok(true);
        }
    }
    Ok(false)
}

fn index_of(m: &mut Machine, elements: &[Value], v: Value) -> Exec<i32> {
    for (i, e) in elements.iter().enumerate() {
        if equals(m, *e, v)? {
            return Ok(i as i32);
        }
    }
    Ok(-1)
}

fn char_sequence(m: &mut Machine, v: Value) -> Exec<JStr> {
    let Some(r) = v.as_ref() else { return Err(m.npe()) };
    match m.heap.get(r) {
        Object::Native(Native::String(s)) | Object::Native(Native::StringBuilder(s)) => Ok(s.clone()),
        _ => object_to_string(m, r),
    }
}

fn string_arg(m: &mut Machine, v: Value) -> Exec<JStr> {
    let Some(r) = v.as_ref() else { return Err(m.npe()) };
    m.heap.string(r).cloned().ok_or_else(|| Fault::Unsupported("expected a String".into()))
}

fn immutable(m: &mut Machine) -> Fault {
    m.throw("java/lang/UnsupportedOperationException", None)
}

fn new_list(m: &mut Machine, elements: Vec<Value>, mutable: bool) -> Value {
    Value::Ref(m.alloc_native(Native::List { elements, mutable }))
}

fn require_non_null_elements(m: &mut Machine, elements: &[Value]) -> Exec<()> {
    if elements.contains(&Value::Null) {
        return Err(m.npe());
    }
    Ok(())
}

// Virtual calls on native objects

pub fn invoke_native_virtual(m: &mut Machine, r: Ref, _owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let native = match m.heap.get(r) {
        Object::Native(n) => n.clone(),
        _ => return unsupported("native call on a non-native"),
    };
    // Methods every object has.
    match (name, descriptor) {
        ("getClass", "()Ljava/lang/Class;") => {
            let t = match &native {
                Native::Boxed { class, .. } => Type::Object(class.clone()),
                other => Type::Object(other.class_name().to_string()),
            };
            return Ok(Some(m.class_object(&t)));
        }
        ("equals", "(Ljava/lang/Object;)Z") => return Ok(Some(Value::bool(native_equals(m, r, args[0])?))),
        ("hashCode", "()I") => return Ok(Some(Value::Int(native_hash(m, r)?))),
        ("toString", "()Ljava/lang/String;") => {
            let s = native_to_string(m, r)?;
            return Ok(Some(m.new_string(s)));
        }
        _ => {}
    }
    match native {
        Native::String(s) => string_method(m, &s, name, descriptor, &args).map(Some),
        Native::StringBuilder(s) => string_builder_method(m, r, s, name, descriptor, &args),
        Native::Boxed { class, value } => boxed_method(m, r, &class, value, name, descriptor, &args).map(Some),
        Native::List { elements, mutable } => list_method(m, r, elements, mutable, name, descriptor, &args),
        Native::Set { elements, mutable } => set_method(m, r, elements, mutable, name, descriptor, &args),
        Native::Map { entries, mutable } => map_method(m, r, entries, mutable, name, descriptor, &args),
        Native::Iterator { elements, position, immutable: of_immutable } => match name {
            "hasNext" => Ok(Some(Value::bool(position < elements.len()))),
            "next" => {
                if position >= elements.len() {
                    return Err(m.throw("java/util/NoSuchElementException", None));
                }
                *m.heap.get_mut(r) = Object::Native(Native::Iterator { elements: elements.clone(), position: position + 1, immutable: of_immutable });
                Ok(Some(elements[position]))
            }
            // The immutable collections' iterators refuse `remove` whatever their position, as `Iterator.remove`'s
            // default does; a mutable collection's would change the collection, which a snapshot can't.
            "remove" if of_immutable => Err(immutable(m)),
            _ => unsupported(format!("Iterator.{name}")),
        },
        Native::Class(t) => match name {
            "getName" | "getTypeName" => Ok(Some(m.new_string(t.class_get_name()))),
            "getSimpleName" => {
                let simple = match &t {
                    Type::Object(n) => m.cp.application(n).ok().flatten().map(|c| c.simple_name()).unwrap_or_else(|| crate::classfile::simple_name_of(n)),
                    other => other.simple_name(),
                };
                Ok(Some(m.new_string(simple)))
            }
            "getCanonicalName" => Ok(Some(m.new_string(t.class_get_name().replace('$', ".")))),
            "isInstance" => Ok(Some(Value::bool(match (args[0], &t) {
                (Value::Ref(o), Type::Object(n)) => m.is_instance(o, n),
                (Value::Ref(o), Type::Array(_)) => m.is_instance(o, &t.descriptor()),
                _ => false,
            }))),
            "isEnum" => Ok(Some(Value::bool(t.class_name().and_then(|n| m.cp.application(n).ok().flatten()).is_some_and(|c| c.is_enum())))),
            "isRecord" => Ok(Some(Value::bool(t.class_name().and_then(|n| m.cp.application(n).ok().flatten()).is_some_and(|c| c.is_record())))),
            "isInterface" => Ok(Some(Value::bool(t.class_name().and_then(|n| m.cp.application(n).ok().flatten()).is_some_and(|c| c.is_interface())))),
            "isPrimitive" => Ok(Some(Value::bool(t.is_primitive()))),
            "isArray" => Ok(Some(Value::bool(matches!(t, Type::Array(_))))),
            "desiredAssertionStatus" => Ok(Some(Value::Int(0))),
            _ => unsupported(format!("Class.{name}: reflection is outside the model")),
        },
        Native::Throwable { class, message, cause } => match name {
            "getMessage" | "getLocalizedMessage" => Ok(Some(message.map(Value::Ref).unwrap_or(Value::Null))),
            "getCause" => Ok(Some(cause.map(Value::Ref).unwrap_or(Value::Null))),
            "initCause" => {
                set_throwable(m, r, None, args[0].as_ref(), false, true);
                Ok(Some(Value::Ref(r)))
            }
            "fillInStackTrace" => Ok(Some(Value::Ref(r))),
            "addSuppressed" => Ok(None),
            _ => unsupported(format!("{}.{name}", class.replace('/', "."))),
        },
        Native::Lambda { sam_name, implementation, captured, instantiated, interface } => {
            if name == sam_name {
                call_lambda(m, &implementation, captured, &instantiated, args)
            } else {
                unsupported(format!("{}.{name} on a lambda (only its functional method {sam_name} is modelled)", interface.replace('/', ".")))
            }
        }
        Native::Optional(value) => optional_method(m, value, name, descriptor, &args),
    }
}

fn string_method(m: &mut Machine, s: &JStr, name: &str, descriptor: &str, args: &[Value]) -> Exec<Value> {
    let units = s.units();
    let len = units.len() as i32;
    Ok(match (name, descriptor) {
        ("length", _) => Value::Int(len),
        ("isEmpty", _) => Value::bool(units.is_empty()),
        ("isBlank", _) => Value::bool(code_points(units).iter().all(|(_, c)| java_whitespace(*c))),
        ("charAt", _) => {
            let i = args[0].as_int();
            if i < 0 || i >= len {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&index_message(i.into(), units.len()))));
            }
            Value::Int(i32::from(units[i as usize]))
        }
        ("codePointAt", _) => {
            let i = args[0].as_int();
            if i < 0 || i >= len {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&index_message(i.into(), units.len()))));
            }
            Value::Int(code_points(&units[i as usize..]).first().map(|(_, c)| *c as i32).unwrap_or(0))
        }
        ("equals", _) => Value::bool(matches!(args[0], Value::Ref(o) if m.heap.string(o) == Some(s))),
        ("equalsIgnoreCase", _) => match args[0] {
            Value::Ref(o) => match m.heap.string(o).cloned() {
                Some(t) => Value::bool(text_of(&t, "String.equalsIgnoreCase")?.to_lowercase() == text_of(s, "String.equalsIgnoreCase")?.to_lowercase()),
                None => Value::bool(false),
            },
            _ => Value::bool(false),
        },
        ("hashCode", _) => Value::Int(s.hash_code()),
        ("compareTo", _) => {
            let other = string_arg(m, args[0])?;
            let o = other.units();
            let mut result = 0;
            for (a, b) in units.iter().zip(o.iter()) {
                if a != b {
                    result = i32::from(*a) - i32::from(*b);
                    break;
                }
            }
            if result == 0 {
                result = len - o.len() as i32;
            }
            Value::Int(result)
        }
        ("compareToIgnoreCase", _) => {
            let other = string_arg(m, args[0])?;
            let a = utf16_of(&text_of(s, "String.compareToIgnoreCase")?.to_lowercase());
            let b = utf16_of(&text_of(&other, "String.compareToIgnoreCase")?.to_lowercase());
            let mut result = 0;
            for (x, y) in a.iter().zip(b.iter()) {
                if x != y {
                    result = i32::from(*x) - i32::from(*y);
                    break;
                }
            }
            if result == 0 {
                result = a.len() as i32 - b.len() as i32;
            }
            Value::Int(result)
        }
        ("concat", _) => {
            let other = string_arg(m, args[0])?;
            let mut out = s.clone();
            out.push(&other);
            m.new_string(out)
        }
        ("contains", _) => {
            let other = char_sequence(m, args[0])?;
            Value::bool(s.find(&other, 0) >= 0)
        }
        ("startsWith", "(Ljava/lang/String;)Z") => {
            let other = string_arg(m, args[0])?;
            Value::bool(units.starts_with(other.units()))
        }
        ("startsWith", "(Ljava/lang/String;I)Z") => {
            let other = string_arg(m, args[0])?;
            let offset = args[1].as_int();
            Value::bool(offset >= 0 && (offset as usize) <= units.len() && units[offset as usize..].starts_with(other.units()))
        }
        ("endsWith", _) => {
            let other = string_arg(m, args[0])?;
            Value::bool(units.ends_with(other.units()))
        }
        ("indexOf", "(I)I") | ("indexOf", "(II)I") => {
            let from = if descriptor == "(II)I" { args[1].as_int().max(0) as usize } else { 0 };
            match code_point_units(args[0].as_int()) {
                Some(_) if from >= units.len() => Value::Int(-1),
                Some(needle) => Value::Int(s.find(&needle, from)),
                None => Value::Int(-1),
            }
        }
        ("indexOf", "(Ljava/lang/String;)I") | ("indexOf", "(Ljava/lang/String;I)I") => {
            let needle = string_arg(m, args[0])?;
            let from = if descriptor.ends_with("I)I") && args.len() > 1 { args[1].as_int().max(0) as usize } else { 0 };
            Value::Int(s.find(&needle, from))
        }
        ("lastIndexOf", "(I)I") => match code_point_units(args[0].as_int()) {
            Some(needle) => Value::Int((0..=units.len().saturating_sub(needle.len())).rev().find(|&i| units.len() >= needle.len() && units[i..].starts_with(needle.units())).map(|i| i as i32).unwrap_or(-1)),
            None => Value::Int(-1),
        },
        ("lastIndexOf", "(Ljava/lang/String;)I") => {
            let needle = string_arg(m, args[0])?;
            let mut result = -1;
            let mut from = 0;
            loop {
                let i = s.find(&needle, from);
                if i < 0 {
                    break;
                }
                result = i;
                from = i as usize + 1;
                if from > units.len() {
                    break;
                }
            }
            Value::Int(result)
        }
        ("substring", "(I)Ljava/lang/String;") => {
            let begin = args[0].as_int();
            if begin < 0 || begin > len {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&format!("begin {begin}, end {len}, length {len}"))));
            }
            m.new_string(JStr::from_units(units[begin as usize..].to_vec()))
        }
        ("substring", "(II)Ljava/lang/String;") | ("subSequence", _) => {
            let begin = args[0].as_int();
            let end = args[1].as_int();
            if begin < 0 || end > len || begin > end {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&format!("begin {begin}, end {end}, length {len}"))));
            }
            m.new_string(JStr::from_units(units[begin as usize..end as usize].to_vec()))
        }
        ("toUpperCase", "()Ljava/lang/String;") => {
            let text = text_of(s, "String.toUpperCase")?;
            m.new_string(text.to_uppercase())
        }
        ("toLowerCase", "()Ljava/lang/String;") => {
            let text = text_of(s, "String.toLowerCase")?;
            m.new_string(text.to_lowercase())
        }
        ("trim", _) => {
            let start = units.iter().position(|&u| u > 0x20).unwrap_or(units.len());
            let end = units.iter().rposition(|&u| u > 0x20).map(|i| i + 1).unwrap_or(start);
            m.new_string(JStr::from_units(units[start..end.max(start)].to_vec()))
        }
        ("strip", _) => m.new_string(strip(units, true, true)),
        ("stripLeading", _) => m.new_string(strip(units, true, false)),
        ("stripTrailing", _) => m.new_string(strip(units, false, true)),
        ("replace", "(CC)Ljava/lang/String;") => {
            let from = args[0].as_int() as u16;
            let to = args[1].as_int() as u16;
            m.new_string(JStr::from_units(units.iter().map(|u| if *u == from { to } else { *u }).collect()))
        }
        ("replace", "(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;") => {
            let from = char_sequence(m, args[0])?;
            let to = char_sequence(m, args[1])?;
            let mut out = JStr::new();
            if from.is_empty() {
                // Java puts the replacement before every code unit and at the end.
                for &u in units {
                    out.push(&to);
                    out.push_unit(u);
                }
                out.push(&to);
            } else {
                let mut at = 0;
                loop {
                    let i = s.find(&from, at);
                    if i < 0 {
                        break;
                    }
                    out.push(&JStr::from_units(units[at..i as usize].to_vec()));
                    out.push(&to);
                    at = i as usize + from.len();
                }
                out.push(&JStr::from_units(units[at..].to_vec()));
            }
            m.new_string(out)
        }
        ("repeat", _) => {
            let n = args[0].as_int();
            if n < 0 {
                return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("count is negative: {n}"))));
            }
            m.new_string(JStr::from_units(units.repeat(n as usize)))
        }
        ("toString", _) | ("intern", _) => m.new_string(s.clone()),
        ("toCharArray", _) => {
            let data = units.iter().map(|u| Value::Int(i32::from(*u))).collect();
            m.new_array_of(Type::Char, data)
        }
        ("isLatin1", _) => Value::bool(units.iter().all(|u| *u < 256)),
        ("format" | "formatted", _) => return unsupported("String.format depends on the default locale"),
        ("split" | "matches" | "replaceAll" | "replaceFirst", _) => return unsupported(format!("String.{name} uses regular expressions, which are not modelled")),
        _ => return unsupported(format!("String.{name}{descriptor}")),
    })
}

fn utf16_of(s: &str) -> Vec<u16> {
    s.encode_utf16().collect()
}

/// The code units of a code point `indexOf(int)` searches for: one for a BMP code point, a surrogate included,
/// two for a supplementary one, and `None` for a value that is no code point, which no String contains.
fn code_point_units(c: i32) -> Option<JStr> {
    match c {
        0..=0xFFFF => Some(JStr::from_units(vec![c as u16])),
        0x10000..=0x10FFFF => {
            let v = (c - 0x10000) as u32;
            Some(JStr::from_units(vec![0xD800 + (v >> 10) as u16, 0xDC00 + (v & 0x3FF) as u16]))
        }
        _ => None,
    }
}

fn string_builder_method(m: &mut Machine, r: Ref, s: JStr, name: &str, descriptor: &str, args: &[Value]) -> Exec<Option<Value>> {
    let mut text = s;
    let result = match (name, descriptor) {
        ("append", d) => {
            let params = MethodDescriptor::parse(d).map_err(|e| Fault::Unsupported(e.to_string()))?.params;
            if params.len() != 1 {
                return unsupported(format!("StringBuilder.append{descriptor}"));
            }
            let param = &params[0];
            let piece = match (param, args[0]) {
                (Type::Array(_), Value::Ref(a)) => char_array_units(m, a).ok_or_else(|| Fault::Unsupported("append of a non-array".into()))?,
                (Type::Array(_), _) => return Err(m.npe()),
                (Type::Object(_), v) => to_java_string(m, v, param)?,
                (t, v) => primitive_units(v, t),
            };
            text.push(&piece);
            Some(Value::Ref(r))
        }
        ("toString", _) => Some(m.new_string(text.clone())),
        ("length", _) => Some(Value::Int(text.len() as i32)),
        ("isEmpty", _) => Some(Value::bool(text.is_empty())),
        ("charAt", _) => {
            let i = args[0].as_int();
            if i < 0 || i as usize >= text.len() {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&index_message(i.into(), text.len()))));
            }
            Some(Value::Int(i32::from(text.units()[i as usize])))
        }
        ("reverse", _) => {
            // AbstractStringBuilder.reverse: the code units reversed, then every surrogate pair that was one put
            // back in order, so that a supplementary character stays one; an isolated surrogate stays as it is.
            let mut units = text.into_units();
            units.reverse();
            let mut i = 0;
            while i + 1 < units.len() {
                if (0xDC00..0xE000).contains(&units[i]) && (0xD800..0xDC00).contains(&units[i + 1]) {
                    units.swap(i, i + 1);
                    i += 2;
                } else {
                    i += 1;
                }
            }
            text = JStr::from_units(units);
            Some(Value::Ref(r))
        }
        ("setLength", _) => {
            let n = args[0].as_int();
            if n < 0 {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&format!("String index out of range: {n}"))));
            }
            let mut units = text.into_units();
            units.resize(n as usize, 0);
            text = JStr::from_units(units);
            None
        }
        ("deleteCharAt", _) => {
            let mut units = text.into_units();
            let i = args[0].as_int();
            if i < 0 || i as usize >= units.len() {
                let n = units.len();
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&index_message(i.into(), n))));
            }
            units.remove(i as usize);
            text = JStr::from_units(units);
            Some(Value::Ref(r))
        }
        ("insert", d) => {
            let params = MethodDescriptor::parse(d).map_err(|e| Fault::Unsupported(e.to_string()))?.params;
            if params.len() != 2 {
                return unsupported(format!("StringBuilder.insert{descriptor}"));
            }
            let offset = args[0].as_int();
            let piece = match (&params[1], args[1]) {
                (Type::Array(_), Value::Ref(a)) => char_array_units(m, a).ok_or_else(|| Fault::Unsupported("insert of a non-array".into()))?,
                (Type::Array(_), _) => return Err(m.npe()),
                (Type::Object(_), v) => to_java_string(m, v, &params[1])?,
                (t, v) => primitive_units(v, t),
            };
            let mut units = text.into_units();
            if offset < 0 || offset as usize > units.len() {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", Some(&format!("offset {offset}, length {}", units.len()))));
            }
            let tail = units.split_off(offset as usize);
            units.extend_from_slice(piece.units());
            units.extend(tail);
            text = JStr::from_units(units);
            Some(Value::Ref(r))
        }
        _ => return unsupported(format!("StringBuilder.{name}{descriptor}")),
    };
    m.check_write(r, "a StringBuilder")?;
    *m.heap.get_mut(r) = Object::Native(Native::StringBuilder(text));
    Ok(result)
}


fn boxed_method(m: &mut Machine, _r: Ref, class: &str, value: Value, name: &str, descriptor: &str, args: &[Value]) -> Exec<Value> {
    let t = boxed_type(class);
    Ok(match name {
        "intValue" => Value::Int(as_i64(value) as i32),
        "longValue" => Value::Long(as_i64(value)),
        "shortValue" => Value::Int(as_i64(value) as i16 as i32),
        "byteValue" => Value::Int(as_i64(value) as i8 as i32),
        "doubleValue" => Value::Double(as_f64(value)),
        "floatValue" => Value::Float(as_f64(value) as f32),
        "booleanValue" | "charValue" => value,
        "compareTo" | "compare" => {
            let other = unbox(m, args[0])?;
            Value::Int(compare_values(value, other, &t))
        }
        "isNaN" => Value::bool(as_f64(value).is_nan()),
        "isInfinite" => Value::bool(as_f64(value).is_infinite()),
        "describeConstable" => return unsupported("describeConstable"),
        _ => return unsupported(format!("{}.{name}{descriptor}", class.replace('/', "."))),
    })
}

fn as_i64(v: Value) -> i64 {
    match v {
        Value::Int(x) => i64::from(x),
        Value::Long(x) => x,
        Value::Float(x) => x as i64,
        Value::Double(x) => x as i64,
        _ => 0,
    }
}

fn as_f64(v: Value) -> f64 {
    match v {
        Value::Int(x) => f64::from(x),
        Value::Long(x) => x as f64,
        Value::Float(x) => f64::from(x),
        Value::Double(x) => x,
        _ => 0.0,
    }
}

/// `Integer.compare`, `Double.compare` (total order with NaN greatest), `Boolean.compare`.
fn compare_values(a: Value, b: Value, t: &Type) -> i32 {
    match t {
        Type::Float | Type::Double => {
            let (x, y) = (as_f64(a), as_f64(b));
            if x < y {
                -1
            } else if x > y {
                1
            } else {
                let (bx, by) = (if x.is_nan() { i64::MAX } else { x.to_bits() as i64 }, if y.is_nan() { i64::MAX } else { y.to_bits() as i64 });
                bx.cmp(&by) as i32
            }
        }
        _ => as_i64(a).cmp(&as_i64(b)) as i32,
    }
}

fn list_method(m: &mut Machine, r: Ref, mut elements: Vec<Value>, mutable: bool, name: &str, descriptor: &str, args: &[Value]) -> Exec<Option<Value>> {
    let len = elements.len();
    let made = m.immutable_list_kind(r);
    let out_of_bounds = |m: &mut Machine, i: i32| m.throw("java/lang/IndexOutOfBoundsException", Some(&index_message(i.into(), len)));
    // A list List.of or copyOf made holds no null, and its searches refuse one, as the JDK's do.
    if made.is_some() && matches!(name, "contains" | "indexOf" | "lastIndexOf") && args.first() == Some(&Value::Null) {
        return Err(m.npe());
    }
    let write = |m: &mut Machine| -> Exec<()> {
        if !mutable {
            return Err(immutable(m));
        }
        m.check_write(r, "a List")
    };
    Ok(match (name, descriptor) {
        ("size", _) => Some(Value::Int(len as i32)),
        ("isEmpty", _) => Some(Value::bool(len == 0)),
        ("get", _) => {
            let i = args[0].as_int();
            if i < 0 || i as usize >= len {
                // The JDK's List12 throws IndexOutOfBoundsException; its ListN indexes its array.
                return Err(match made {
                    Some(crate::interp::ImmutableList::List12) => m.throw("java/lang/IndexOutOfBoundsException", Some(&format!("Index: {i} Size: {len}"))),
                    Some(crate::interp::ImmutableList::ListN) => m.throw("java/lang/ArrayIndexOutOfBoundsException", Some(&index_message(i.into(), len))),
                    None => out_of_bounds(m, i),
                });
            }
            Some(elements[i as usize])
        }
        ("getFirst", _) | ("getLast", _) => {
            if len == 0 {
                return Err(m.throw("java/util/NoSuchElementException", None));
            }
            Some(if name == "getFirst" { elements[0] } else { elements[len - 1] })
        }
        ("contains", _) => Some(Value::bool(contains(m, &elements, args[0])?)),
        ("containsAll", _) => {
            let others = collection_elements(m, args[0])?;
            for o in others {
                if !contains(m, &elements, o)? {
                    return Ok(Some(Value::Int(0)));
                }
            }
            Some(Value::Int(1))
        }
        ("indexOf", _) => Some(Value::Int(index_of(m, &elements, args[0])?)),
        ("lastIndexOf", _) => {
            let mut result = -1;
            for (i, e) in elements.iter().enumerate() {
                if equals(m, *e, args[0])? {
                    result = i as i32;
                }
            }
            Some(Value::Int(result))
        }
        ("iterator", _) => Some(Value::Ref(m.alloc_native(Native::Iterator { elements, position: 0, immutable: !mutable }))),
        ("forEach", _) => {
            for e in elements {
                m.call_virtual(args[0], "java/util/function/Consumer", "accept", "(Ljava/lang/Object;)V", vec![e])?;
            }
            None
        }
        ("toArray", "()[Ljava/lang/Object;") => Some(m.new_array_of(Type::object("java/lang/Object"), elements)),
        ("toArray", _) => {
            let element = match args[0].as_ref().map(|a| m.heap.get(a).clone()) {
                Some(Object::Array { element, .. }) => element,
                _ => Type::object("java/lang/Object"),
            };
            Some(m.new_array_of(element, elements))
        }
        ("subList", _) => {
            let (from, to) = (args[0].as_int(), args[1].as_int());
            if from < 0 || to as usize > len || from > to {
                return Err(m.throw("java/lang/IndexOutOfBoundsException", Some(&format!("fromIndex: {from}, toIndex: {to}, size: {len}"))));
            }
            Some(new_list(m, elements[from as usize..to as usize].to_vec(), false))
        }
        ("reversed", _) => {
            elements.reverse();
            Some(new_list(m, elements, false))
        }
        ("stream", _) => return unsupported("streams are not modelled"),
        ("add", "(Ljava/lang/Object;)Z") => {
            write(m)?;
            elements.push(args[0]);
            *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable });
            Some(Value::Int(1))
        }
        ("add", "(ILjava/lang/Object;)V") => {
            write(m)?;
            let i = args[0].as_int();
            if i < 0 || i as usize > len {
                return Err(out_of_bounds(m, i));
            }
            elements.insert(i as usize, args[1]);
            *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable });
            None
        }
        ("addAll", "(Ljava/util/Collection;)Z") => {
            write(m)?;
            let others = collection_elements(m, args[0])?;
            let changed = !others.is_empty();
            elements.extend(others);
            *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable });
            Some(Value::bool(changed))
        }
        ("set", _) => {
            write(m)?;
            let i = args[0].as_int();
            if i < 0 || i as usize >= len {
                return Err(out_of_bounds(m, i));
            }
            let old = elements[i as usize];
            elements[i as usize] = args[1];
            *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable });
            Some(old)
        }
        ("remove", "(I)Ljava/lang/Object;") => {
            write(m)?;
            let i = args[0].as_int();
            if i < 0 || i as usize >= len {
                return Err(out_of_bounds(m, i));
            }
            let old = elements.remove(i as usize);
            *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable });
            Some(old)
        }
        ("remove", "(Ljava/lang/Object;)Z") => {
            write(m)?;
            let i = index_of(m, &elements, args[0])?;
            if i >= 0 {
                elements.remove(i as usize);
            }
            *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable });
            Some(Value::bool(i >= 0))
        }
        ("clear", _) => {
            write(m)?;
            *m.heap.get_mut(r) = Object::Native(Native::List { elements: Vec::new(), mutable });
            None
        }
        _ => return unsupported(format!("List.{name}{descriptor}")),
    })
}

fn set_method(m: &mut Machine, r: Ref, mut elements: Vec<Value>, mutable: bool, name: &str, descriptor: &str, args: &[Value]) -> Exec<Option<Value>> {
    let write = |m: &mut Machine| -> Exec<()> {
        if !mutable {
            return Err(immutable(m));
        }
        m.check_write(r, "a Set")
    };
    Ok(match name {
        "size" => Some(Value::Int(elements.len() as i32)),
        "isEmpty" => Some(Value::bool(elements.is_empty())),
        "contains" => Some(Value::bool(contains(m, &elements, args[0])?)),
        "containsAll" => {
            let others = collection_elements(m, args[0])?;
            for o in others {
                if !contains(m, &elements, o)? {
                    return Ok(Some(Value::Int(0)));
                }
            }
            Some(Value::Int(1))
        }
        "iterator" => Some(Value::Ref(m.alloc_native(Native::Iterator { elements, position: 0, immutable: !mutable }))),
        "forEach" => {
            for e in elements {
                m.call_virtual(args[0], "java/util/function/Consumer", "accept", "(Ljava/lang/Object;)V", vec![e])?;
            }
            None
        }
        "toArray" => Some(m.new_array_of(Type::object("java/lang/Object"), elements)),
        "add" => {
            write(m)?;
            let added = !contains(m, &elements, args[0])?;
            if added {
                elements.push(args[0]);
            }
            *m.heap.get_mut(r) = Object::Native(Native::Set { elements, mutable });
            Some(Value::bool(added))
        }
        "addAll" => {
            write(m)?;
            let mut changed = false;
            for o in collection_elements(m, args[0])? {
                if !contains(m, &elements, o)? {
                    elements.push(o);
                    changed = true;
                }
            }
            *m.heap.get_mut(r) = Object::Native(Native::Set { elements, mutable });
            Some(Value::bool(changed))
        }
        "remove" => {
            write(m)?;
            let i = index_of(m, &elements, args[0])?;
            if i >= 0 {
                elements.remove(i as usize);
            }
            *m.heap.get_mut(r) = Object::Native(Native::Set { elements, mutable });
            Some(Value::bool(i >= 0))
        }
        "clear" => {
            write(m)?;
            *m.heap.get_mut(r) = Object::Native(Native::Set { elements: Vec::new(), mutable });
            None
        }
        "stream" => return unsupported("streams are not modelled"),
        _ => return unsupported(format!("Set.{name}{descriptor}")),
    })
}

fn map_method(m: &mut Machine, r: Ref, mut entries: Vec<(Value, Value)>, mutable: bool, name: &str, descriptor: &str, args: &[Value]) -> Exec<Option<Value>> {
    let write = |m: &mut Machine| -> Exec<()> {
        if !mutable {
            return Err(immutable(m));
        }
        m.check_write(r, "a Map")
    };
    let find = |m: &mut Machine, entries: &[(Value, Value)], key: Value| -> Exec<Option<usize>> {
        for (i, (k, _)) in entries.iter().enumerate() {
            if equals(m, *k, key)? {
                return Ok(Some(i));
            }
        }
        Ok(None)
    };
    Ok(match name {
        "size" => Some(Value::Int(entries.len() as i32)),
        "isEmpty" => Some(Value::bool(entries.is_empty())),
        "get" => Some(match find(m, &entries, args[0])? {
            Some(i) => entries[i].1,
            None => Value::Null,
        }),
        "getOrDefault" => Some(match find(m, &entries, args[0])? {
            Some(i) => entries[i].1,
            None => args[1],
        }),
        "containsKey" => Some(Value::bool(find(m, &entries, args[0])?.is_some())),
        "containsValue" => {
            let values: Vec<Value> = entries.iter().map(|(_, v)| *v).collect();
            Some(Value::bool(contains(m, &values, args[0])?))
        }
        "keySet" => {
            let keys = entries.iter().map(|(k, _)| *k).collect();
            Some(Value::Ref(m.alloc_native(Native::Set { elements: keys, mutable: false })))
        }
        "values" => {
            let values = entries.iter().map(|(_, v)| *v).collect();
            Some(new_list(m, values, false))
        }
        "forEach" => {
            for (k, v) in entries {
                m.call_virtual(args[0], "java/util/function/BiConsumer", "accept", "(Ljava/lang/Object;Ljava/lang/Object;)V", vec![k, v])?;
            }
            None
        }
        "put" => {
            write(m)?;
            let old = match find(m, &entries, args[0])? {
                Some(i) => {
                    let old = entries[i].1;
                    entries[i].1 = args[1];
                    old
                }
                None => {
                    entries.push((args[0], args[1]));
                    Value::Null
                }
            };
            *m.heap.get_mut(r) = Object::Native(Native::Map { entries, mutable });
            Some(old)
        }
        "putIfAbsent" => {
            write(m)?;
            let old = match find(m, &entries, args[0])? {
                Some(i) => entries[i].1,
                None => {
                    entries.push((args[0], args[1]));
                    Value::Null
                }
            };
            *m.heap.get_mut(r) = Object::Native(Native::Map { entries, mutable });
            Some(old)
        }
        "remove" => {
            write(m)?;
            let old = match find(m, &entries, args[0])? {
                Some(i) => entries.remove(i).1,
                None => Value::Null,
            };
            *m.heap.get_mut(r) = Object::Native(Native::Map { entries, mutable });
            Some(old)
        }
        "clear" => {
            write(m)?;
            *m.heap.get_mut(r) = Object::Native(Native::Map { entries: Vec::new(), mutable });
            None
        }
        "entrySet" | "stream" | "compute" | "computeIfAbsent" | "merge" => return unsupported(format!("Map.{name} is not modelled")),
        _ => return unsupported(format!("Map.{name}{descriptor}")),
    })
}

fn optional_method(m: &mut Machine, value: Option<Value>, name: &str, descriptor: &str, args: &[Value]) -> Exec<Option<Value>> {
    Ok(match name {
        "isPresent" => Some(Value::bool(value.is_some())),
        "isEmpty" => Some(Value::bool(value.is_none())),
        "get" | "orElseThrow" if descriptor.starts_with("()") => match value {
            Some(v) => Some(v),
            None => return Err(m.throw("java/util/NoSuchElementException", Some("No value present"))),
        },
        "orElse" => Some(value.unwrap_or(args[0])),
        "orElseGet" => Some(match value {
            Some(v) => v,
            None => m.call_virtual(args[0], "java/util/function/Supplier", "get", "()Ljava/lang/Object;", Vec::new())?.unwrap_or(Value::Null),
        }),
        "ifPresent" => {
            if let Some(v) = value {
                m.call_virtual(args[0], "java/util/function/Consumer", "accept", "(Ljava/lang/Object;)V", vec![v])?;
            }
            None
        }
        "map" => Some(match value {
            None => Value::Ref(m.alloc_native(Native::Optional(None))),
            Some(v) => {
                let mapped = m.call_virtual(args[0], "java/util/function/Function", "apply", "(Ljava/lang/Object;)Ljava/lang/Object;", vec![v])?.unwrap_or(Value::Null);
                let inner = if mapped == Value::Null { None } else { Some(mapped) };
                Value::Ref(m.alloc_native(Native::Optional(inner)))
            }
        }),
        "filter" => Some(match value {
            Some(v) => {
                let keep = m.call_virtual(args[0], "java/util/function/Predicate", "test", "(Ljava/lang/Object;)Z", vec![v])?.map(|b| b.as_int() != 0).unwrap_or(false);
                Value::Ref(m.alloc_native(Native::Optional(if keep { Some(v) } else { None })))
            }
            None => Value::Ref(m.alloc_native(Native::Optional(None))),
        }),
        _ => return unsupported(format!("Optional.{name}{descriptor}")),
    })
}

// Lambdas

fn call_lambda(m: &mut Machine, handle: &MethodHandle, captured: Vec<Value>, instantiated: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let mut full = captured;
    full.extend(args);
    let target = MethodDescriptor::parse(&handle.member.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
    let instantiated = MethodDescriptor::parse(instantiated).map_err(|e| Fault::Unsupported(e.to_string()))?;
    let owner = handle.member.owner.clone();
    let name = handle.member.name.clone();
    let descriptor = handle.member.descriptor.clone();
    let result = match handle.kind {
        6 => {
            let adapted = adapt_args(m, full, &target.params)?;
            if m.cp.is_application(&owner) {
                m.call_static(&owner, &name, &descriptor, adapted)?
            } else {
                invoke_static_jdk(m, &owner, &name, &descriptor, adapted)?
            }
        }
        5 | 9 | 7 => {
            let receiver = *full.first().ok_or_else(|| Fault::Unsupported("lambda without a receiver".into()))?;
            let rest = adapt_args(m, full[1..].to_vec(), &target.params)?;
            if handle.kind == 7 && m.cp.is_application(&owner) {
                let (cf, method) = m.cp.find_method(&owner, &name, &descriptor).ok_or_else(|| Fault::Unsupported(format!("method not found: {owner}.{name}")))?;
                let mut all = vec![receiver];
                all.extend(rest);
                m.invoke(&cf, &method, all)?
            } else {
                m.call_virtual(receiver, &owner, &name, &descriptor, rest)?
            }
        }
        8 => {
            let adapted = adapt_args(m, full, &target.params)?;
            if m.cp.is_application(&owner) {
                Some(m.construct(&owner, &descriptor, adapted)?)
            } else {
                let object = new_jdk_object(m, &owner)?;
                let r = object.as_ref().expect("allocated");
                invoke_special_jdk(m, r, &owner, "<init>", &descriptor, adapted)?;
                Some(object)
            }
        }
        other => return unsupported(format!("method handle kind {other}")),
    };
    // Adapt the return value to the functional interface's type.
    let returned_type = if handle.kind == 8 { Type::Object(owner) } else { target.ret };
    Ok(match (result, &returned_type, &instantiated.ret) {
        (Some(v), t, Type::Object(_)) if t.is_primitive() => Some(box_value(m, box_class_of(t).unwrap_or("java/lang/Integer"), v)),
        (Some(v), Type::Object(_), t) if t.is_primitive() => Some(unbox(m, v)?),
        (None, _, Type::Void) => None,
        (None, _, _) => Some(Value::Null),
        (v, _, Type::Void) => {
            let _ = v;
            None
        }
        (v, _, _) => v,
    })
}

fn adapt_args(m: &mut Machine, values: Vec<Value>, params: &[Type]) -> Exec<Vec<Value>> {
    let mut out = Vec::with_capacity(values.len());
    for (i, v) in values.into_iter().enumerate() {
        let Some(param) = params.get(i) else {
            out.push(v);
            continue;
        };
        out.push(match (param.is_primitive(), v) {
            (true, Value::Ref(_)) | (true, Value::Null) => unbox(m, v)?,
            (false, Value::Int(_)) | (false, Value::Long(_)) | (false, Value::Float(_)) | (false, Value::Double(_)) => {
                let class = match param {
                    Type::Object(n) if is_box_class(n) => n.clone(),
                    _ => match v {
                        Value::Long(_) => "java/lang/Long".into(),
                        Value::Float(_) => "java/lang/Float".into(),
                        Value::Double(_) => "java/lang/Double".into(),
                        _ => "java/lang/Integer".into(),
                    },
                };
                box_value(m, &class, v)
            }
            _ => v,
        });
    }
    Ok(out)
}

// invokedynamic

pub fn invoke_dynamic(m: &mut Machine, class: &ClassFile, bootstrap_index: u16, name: &str, descriptor: &MethodDescriptor, args: Vec<Value>) -> Exec<Option<Value>> {
    let bootstraps = class.bootstrap_methods().map_err(|e| Fault::Unsupported(e.to_string()))?;
    let bootstrap = bootstraps.get(bootstrap_index as usize).ok_or_else(|| Fault::Unsupported("missing bootstrap method".into()))?;
    let owner = bootstrap.method.member.owner.as_str();
    let method = bootstrap.method.member.name.as_str();
    match (owner, method) {
        ("java/lang/invoke/StringConcatFactory", "makeConcatWithConstants") => {
            let Some(recipe) = bootstrap.args.first().and_then(BootstrapArg::string_units) else { return unsupported("concat recipe") };
            let mut constants = bootstrap.args[1..].iter();
            let mut args = args.into_iter().zip(descriptor.params.iter());
            let mut out = JStr::new();
            for &c in recipe.iter() {
                match c {
                    1 => {
                        let (v, t) = args.next().ok_or_else(|| Fault::Unsupported("concat arity".into()))?;
                        out.push(&to_java_string(m, v, t)?);
                    }
                    2 => match constants.next() {
                        Some(BootstrapArg::Str(s)) => out.push_str(s),
                        Some(BootstrapArg::Units(units)) => units.iter().for_each(|&u| out.push_unit(u)),
                        Some(BootstrapArg::Int(v)) => out.push_str(&v.to_string()),
                        Some(BootstrapArg::Long(v)) => out.push_str(&v.to_string()),
                        Some(BootstrapArg::Float(v)) => out.push_str(&float_to_string(*v)),
                        Some(BootstrapArg::Double(v)) => out.push_str(&double_to_string(*v)),
                        _ => return unsupported("concat constant"),
                    },
                    other => out.push_unit(other),
                }
            }
            Ok(Some(m.new_string(out)))
        }
        ("java/lang/invoke/StringConcatFactory", "makeConcat") => {
            let mut out = JStr::new();
            for (v, t) in args.into_iter().zip(descriptor.params.iter()) {
                out.push(&to_java_string(m, v, t)?);
            }
            Ok(Some(m.new_string(out)))
        }
        ("java/lang/runtime/ObjectMethods", "bootstrap") => record_method(m, class, &bootstrap.args, name, args),
        ("java/lang/runtime/SwitchBootstraps", "typeSwitch") | ("java/lang/runtime/SwitchBootstraps", "enumSwitch") => {
            let selector = args[0];
            let restart = args[1].as_int().max(0) as usize;
            let Some(selector) = selector.as_ref() else { return Ok(Some(Value::Int(-1))) };
            for (i, label) in bootstrap.args.iter().enumerate().skip(restart) {
                let matched = match label {
                    BootstrapArg::Class(target) => m.is_instance(selector, target),
                    BootstrapArg::Str(s) => {
                        if method == "enumSwitch" {
                            matches!(m.heap.get(selector), Object::Instance { base: Base::Enum { name, .. }, .. } if name == s)
                        } else {
                            m.heap.string(selector) == Some(&JStr::from(s))
                        }
                    }
                    BootstrapArg::Units(units) if method == "typeSwitch" => m.heap.string(selector).is_some_and(|s| s.units() == &units[..]),
                    BootstrapArg::Int(v) => matches!(m.heap.get(selector), Object::Native(Native::Boxed { value: Value::Int(x), .. }) if x == v),
                    BootstrapArg::Dynamic { bootstrap_method_attr_index, .. } => {
                        let (enum_class, constant) = resolve_enum_label(&bootstraps, *bootstrap_method_attr_index)?;
                        matches!(m.heap.get(selector), Object::Instance { class, base: Base::Enum { name, .. }, .. }
                            if *name == constant && m.cp.is_subtype(class, &enum_class))
                    }
                    other => return unsupported(format!("switch label {other:?}")),
                };
                if matched {
                    return Ok(Some(Value::Int(i as i32)));
                }
            }
            Ok(Some(Value::Int(bootstrap.args.len() as i32)))
        }
        ("java/lang/invoke/LambdaMetafactory", "metafactory") | ("java/lang/invoke/LambdaMetafactory", "altMetafactory") => {
            let implementation = match bootstrap.args.get(1) {
                Some(BootstrapArg::MethodHandle(h)) => h.clone(),
                _ => return unsupported("lambda without an implementation handle"),
            };
            let instantiated = match bootstrap.args.get(2) {
                Some(BootstrapArg::MethodType(t)) => t.clone(),
                _ => implementation.member.descriptor.clone(),
            };
            let interface = descriptor.ret.class_name().unwrap_or("java/lang/Object").to_string();
            let lambda = Native::Lambda { interface, sam_name: name.to_string(), implementation, captured: args, instantiated };
            Ok(Some(Value::Ref(m.alloc_native(lambda))))
        }
        _ => unsupported(format!("invokedynamic with bootstrap {}.{method}", owner.replace('/', "."))),
    }
}

/// The enum class and constant an `EnumDesc` dynamic constant denotes, as javac emits it for `case E.X` labels:
/// `ConstantBootstraps.invoke(EnumDesc.of, ClassDesc, "X")` with the `ClassDesc` another `invoke(ClassDesc.of, "pkg.E")`.
fn resolve_enum_label(bootstraps: &[crate::classfile::BootstrapMethod], index: u16) -> Exec<(String, String)> {
    let bootstrap = bootstraps.get(index as usize).ok_or_else(|| Fault::Unsupported("missing bootstrap for an enum label".into()))?;
    let mut class = None;
    let mut constant = None;
    for arg in &bootstrap.args {
        match arg {
            BootstrapArg::Str(s) => constant = Some(s.clone()),
            BootstrapArg::Class(c) => class = Some(c.clone()),
            BootstrapArg::Dynamic { bootstrap_method_attr_index, .. } => {
                let inner = bootstraps.get(*bootstrap_method_attr_index as usize).ok_or_else(|| Fault::Unsupported("missing bootstrap for a class label".into()))?;
                for a in &inner.args {
                    match a {
                        BootstrapArg::Str(s) => class = Some(s.replace('.', "/")),
                        BootstrapArg::Class(c) => class = Some(c.clone()),
                        _ => {}
                    }
                }
            }
            _ => {}
        }
    }
    match (class, constant) {
        (Some(c), Some(n)) => Ok((c, n)),
        _ => unsupported("an enum case label the interpreter cannot resolve"),
    }
}

fn record_method(m: &mut Machine, class: &ClassFile, bootstrap_args: &[BootstrapArg], name: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let getters: Vec<&MethodHandle> = bootstrap_args.iter().filter_map(|a| if let BootstrapArg::MethodHandle(h) = a { Some(h) } else { None }).collect();
    let names: Vec<String> = match bootstrap_args.get(1) {
        Some(BootstrapArg::Str(s)) if !s.is_empty() => s.split(';').map(str::to_string).collect(),
        _ => Vec::new(),
    };
    let this = args[0];
    let Some(this_ref) = this.as_ref() else { return Err(m.npe()) };
    let mut components = Vec::new();
    for (i, getter) in getters.iter().enumerate() {
        let t = Type::parse(&getter.member.descriptor).map_err(|e| Fault::Unsupported(e.to_string()))?;
        let field = getter.member.name.clone();
        let label = names.get(i).cloned().unwrap_or_else(|| field.clone());
        components.push((label, field, t));
    }
    match name {
        "toString" => {
            let mut parts = Vec::new();
            for (label, field, t) in &components {
                let v = m.get_field(this, field)?;
                let mut part = JStr::from(format!("{label}="));
                part.push(&to_java_string(m, v, t)?);
                parts.push(part);
            }
            let mut text = JStr::from(format!("{}[", class.simple_name()));
            text.push(&JStr::join(&parts, &JStr::from(", ")));
            text.push_str("]");
            Ok(Some(m.new_string(text)))
        }
        "hashCode" => {
            let mut h: i32 = 0;
            for (_, field, t) in &components {
                let v = m.get_field(this, field)?;
                let component_hash = match t {
                    Type::Boolean => {
                        if v.as_int() != 0 {
                            1231
                        } else {
                            1237
                        }
                    }
                    _ => hash_code(m, v)?,
                };
                h = h.wrapping_mul(31).wrapping_add(component_hash);
            }
            Ok(Some(Value::Int(h)))
        }
        "equals" => {
            let other = args[1];
            let Some(o) = other.as_ref() else { return Ok(Some(Value::Int(0))) };
            if o == this_ref {
                return Ok(Some(Value::Int(1)));
            }
            if m.class_of(o) != m.class_of(this_ref) {
                return Ok(Some(Value::Int(0)));
            }
            for (_, field, t) in &components {
                let a = m.get_field(this, field)?;
                let b = m.get_field(other, field)?;
                let same = match t {
                    Type::Float | Type::Double => compare_values(a, b, t) == 0,
                    t if t.is_primitive() => a == b,
                    _ => equals(m, a, b)?,
                };
                if !same {
                    return Ok(Some(Value::Int(0)));
                }
            }
            Ok(Some(Value::Int(1)))
        }
        _ => unsupported(format!("ObjectMethods.{name}")),
    }
}

// Static methods of the JDK

pub fn invoke_static_jdk(m: &mut Machine, owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let a = &args;
    let result: Value = match owner {
        "java/lang/Math" | "java/lang/StrictMath" => math(m, name, descriptor, a)?,
        "java/lang/Integer" | "java/lang/Long" | "java/lang/Short" | "java/lang/Byte" => integral(m, owner, name, descriptor, a)?,
        "java/lang/Boolean" => match (name, descriptor) {
            ("valueOf", "(Z)Ljava/lang/Boolean;") => box_value(m, owner, a[0]),
            ("valueOf", _) => {
                let s = m.units_of(a[0]).and_then(|s| s.text()).is_some_and(|s| s.eq_ignore_ascii_case("true"));
                box_value(m, owner, Value::bool(s))
            }
            ("parseBoolean", _) => Value::bool(m.units_of(a[0]).and_then(|s| s.text()).is_some_and(|s| s.eq_ignore_ascii_case("true"))),
            ("toString", _) => m.new_string((a[0].as_int() != 0).to_string()),
            ("compare", _) => Value::Int(a[0].as_int().cmp(&a[1].as_int()) as i32),
            ("hashCode", _) => Value::Int(if a[0].as_int() != 0 { 1231 } else { 1237 }),
            ("logicalAnd", _) => Value::bool(a[0].as_int() != 0 && a[1].as_int() != 0),
            ("logicalOr", _) => Value::bool(a[0].as_int() != 0 || a[1].as_int() != 0),
            ("logicalXor", _) => Value::bool((a[0].as_int() != 0) != (a[1].as_int() != 0)),
            _ => return unsupported(format!("Boolean.{name}{descriptor}")),
        },
        "java/lang/Character" => character(m, name, descriptor, a)?,
        "java/lang/Double" | "java/lang/Float" => floating(m, owner, name, descriptor, a)?,
        "java/lang/String" => match (name, descriptor) {
            ("valueOf", "(Ljava/lang/Object;)Ljava/lang/String;") => {
                let s = to_java_string(m, a[0], &Type::object("java/lang/Object"))?;
                m.new_string(s)
            }
            ("valueOf", "([C)Ljava/lang/String;") | ("copyValueOf", "([C)Ljava/lang/String;") => {
                let Some(r) = a[0].as_ref() else { return Err(m.npe()) };
                let s = char_array_units(m, r).ok_or_else(|| Fault::Unsupported("String.valueOf of a non-array".into()))?;
                m.new_string(s)
            }
            ("valueOf", d) => {
                let t = MethodDescriptor::parse(d).map_err(|e| Fault::Unsupported(e.to_string()))?.params[0].clone();
                m.new_string(primitive_units(a[0], &t))
            }
            ("join", "(Ljava/lang/CharSequence;[Ljava/lang/CharSequence;)Ljava/lang/String;") => {
                let delimiter = char_sequence(m, a[0])?;
                let elements = collection_elements(m, a[1])?;
                let mut parts = Vec::new();
                for e in elements {
                    parts.push(to_java_string(m, e, &Type::object("java/lang/CharSequence"))?);
                }
                m.new_string(JStr::join(&parts, &delimiter))
            }
            ("join", "(Ljava/lang/CharSequence;Ljava/lang/Iterable;)Ljava/lang/String;") => {
                let delimiter = char_sequence(m, a[0])?;
                let elements = collection_elements(m, a[1])?;
                let mut parts = Vec::new();
                for e in elements {
                    parts.push(to_java_string(m, e, &Type::object("java/lang/CharSequence"))?);
                }
                m.new_string(JStr::join(&parts, &delimiter))
            }
            ("format", _) => return unsupported("String.format depends on the default locale"),
            _ => return unsupported(format!("String.{name}{descriptor}")),
        },
        "java/util/Objects" => match (name, descriptor) {
            ("requireNonNull", "(Ljava/lang/Object;)Ljava/lang/Object;") => {
                if a[0] == Value::Null {
                    return Err(m.npe());
                }
                a[0]
            }
            ("requireNonNull", "(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;") => {
                if a[0] == Value::Null {
                    return Err(m.throw_with("java/lang/NullPointerException", a[1].as_ref()));
                }
                a[0]
            }
            ("requireNonNull", "(Ljava/lang/Object;Ljava/util/function/Supplier;)Ljava/lang/Object;") => {
                if a[0] == Value::Null {
                    let message = m.call_virtual(a[1], "java/util/function/Supplier", "get", "()Ljava/lang/Object;", Vec::new())?.and_then(|v| v.as_ref());
                    return Err(m.throw_with("java/lang/NullPointerException", message));
                }
                a[0]
            }
            ("requireNonNullElse", _) => {
                if a[0] != Value::Null {
                    a[0]
                } else if a[1] != Value::Null {
                    a[1]
                } else {
                    return Err(m.throw("java/lang/NullPointerException", Some("defaultObj")));
                }
            }
            ("equals", _) => Value::bool(equals(m, a[0], a[1])?),
            ("hashCode", _) => Value::Int(hash_code(m, a[0])?),
            ("hash", _) => {
                let elements = match a[0] {
                    Value::Null => return Ok(Some(Value::Int(0))),
                    v => collection_elements(m, v)?,
                };
                let mut h: i32 = 1;
                for e in elements {
                    h = h.wrapping_mul(31).wrapping_add(hash_code(m, e)?);
                }
                Value::Int(h)
            }
            ("toString", "(Ljava/lang/Object;)Ljava/lang/String;") => {
                let s = to_java_string(m, a[0], &Type::object("java/lang/Object"))?;
                m.new_string(s)
            }
            ("toString", _) => {
                if a[0] == Value::Null {
                    a[1]
                } else {
                    let s = to_java_string(m, a[0], &Type::object("java/lang/Object"))?;
                    m.new_string(s)
                }
            }
            ("isNull", _) => Value::bool(a[0] == Value::Null),
            ("nonNull", _) => Value::bool(a[0] != Value::Null),
            ("checkIndex", "(II)I") => {
                let (i, n) = (a[0].as_int(), a[1].as_int());
                if i < 0 || i >= n {
                    return Err(m.throw("java/lang/IndexOutOfBoundsException", Some(&index_message(i.into(), n.max(0) as usize))));
                }
                Value::Int(i)
            }
            ("compare", _) => {
                if a[0] == a[1] {
                    Value::Int(0)
                } else {
                    m.call_virtual(a[2], "java/util/Comparator", "compare", "(Ljava/lang/Object;Ljava/lang/Object;)I", vec![a[0], a[1]])?.unwrap_or(Value::Int(0))
                }
            }
            _ => return unsupported(format!("Objects.{name}{descriptor}")),
        },
        "java/util/List" | "java/util/Set" => match name {
            "of" => {
                let elements = if descriptor.starts_with("([") { collection_elements(m, a[0])? } else { args.clone() };
                require_non_null_elements(m, &elements)?;
                if owner == "java/util/List" {
                    m.immutable_list(elements)
                } else {
                    let mut unique = Vec::new();
                    for e in elements {
                        if contains(m, &unique, e)? {
                            let text = to_java_string(m, e, &Type::object("java/lang/Object"))?;
                            return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("duplicate element: {text}"))));
                        }
                        unique.push(e);
                    }
                    Value::Ref(m.alloc_native(Native::Set { elements: unique, mutable: false }))
                }
            }
            "copyOf" => {
                let elements = collection_elements(m, a[0])?;
                require_non_null_elements(m, &elements)?;
                if owner == "java/util/List" {
                    // The list itself when List.of or copyOf made it (not a view such as subList's), as the JDK's.
                    if a[0].as_ref().is_some_and(|r| m.immutable_list_kind(r).is_some()) {
                        return Ok(Some(a[0]));
                    }
                    m.immutable_list(elements)
                } else {
                    let mut unique = Vec::new();
                    for e in elements {
                        if !contains(m, &unique, e)? {
                            unique.push(e);
                        }
                    }
                    Value::Ref(m.alloc_native(Native::Set { elements: unique, mutable: false }))
                }
            }
            _ => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
        },
        "java/util/Map" => match name {
            "of" => {
                let mut entries = Vec::new();
                for pair in args.chunks(2) {
                    if pair.len() != 2 || pair[0] == Value::Null || pair[1] == Value::Null {
                        return Err(m.npe());
                    }
                    let mut dup = false;
                    for (k, _) in &entries {
                        if equals(m, *k, pair[0])? {
                            dup = true;
                        }
                    }
                    if dup {
                        let text = to_java_string(m, pair[0], &Type::object("java/lang/Object"))?;
                        return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("duplicate key: {text}"))));
                    }
                    entries.push((pair[0], pair[1]));
                }
                Value::Ref(m.alloc_native(Native::Map { entries, mutable: false }))
            }
            "copyOf" => {
                let entries = map_entries(m, a[0])?;
                Value::Ref(m.alloc_native(Native::Map { entries, mutable: false }))
            }
            _ => return unsupported(format!("Map.{name}{descriptor}")),
        },
        "java/util/Optional" => match name {
            "empty" => Value::Ref(m.alloc_native(Native::Optional(None))),
            "of" => {
                if a[0] == Value::Null {
                    return Err(m.npe());
                }
                Value::Ref(m.alloc_native(Native::Optional(Some(a[0]))))
            }
            "ofNullable" => Value::Ref(m.alloc_native(Native::Optional(if a[0] == Value::Null { None } else { Some(a[0]) }))),
            _ => return unsupported(format!("Optional.{name}{descriptor}")),
        },
        "java/lang/Enum" => match name {
            "valueOf" => {
                let Some(class_ref) = a[0].as_ref() else { return Err(m.npe()) };
                let class_name = match m.heap.get(class_ref) {
                    Object::Native(Native::Class(Type::Object(n))) => n.clone(),
                    _ => return unsupported("Enum.valueOf of a non-class"),
                };
                let Some(wanted) = m.units_of(a[1]) else { return Err(m.throw("java/lang/NullPointerException", Some("Name is null"))) };
                for constant in m.enum_constants(&class_name)? {
                    if let Some(r) = constant.as_ref() {
                        if matches!(m.heap.get(r), Object::Instance { base: Base::Enum { name, .. }, .. } if JStr::from(name) == wanted) {
                            return Ok(Some(constant));
                        }
                    }
                }
                let message = format!("No enum constant {}.{wanted}", class_name.replace(['/', '$'], "."));
                return Err(m.throw("java/lang/IllegalArgumentException", Some(&message)));
            }
            _ => return unsupported(format!("Enum.{name}{descriptor}")),
        },
        "java/util/Arrays" => arrays(m, name, descriptor, a)?,
        "java/lang/System" => match name {
            "arraycopy" => {
                let (Some(src), Some(dst)) = (a[0].as_ref(), a[2].as_ref()) else { return Err(m.npe()) };
                let (src_pos, dst_pos, length) = (a[1].as_int(), a[3].as_int(), a[4].as_int());
                let data = match m.heap.get(src) {
                    Object::Array { data, .. } => data.clone(),
                    _ => return Err(m.throw("java/lang/ArrayStoreException", Some("arraycopy: source type is not an array"))),
                };
                m.check_write(dst, "an array element")?;
                let dst_len = match m.heap.get(dst) {
                    Object::Array { data, .. } => data.len() as i32,
                    _ => return Err(m.throw("java/lang/ArrayStoreException", Some("arraycopy: destination type is not an array"))),
                };
                if src_pos < 0 || dst_pos < 0 || length < 0 || src_pos + length > data.len() as i32 || dst_pos + length > dst_len {
                    return Err(m.throw("java/lang/ArrayIndexOutOfBoundsException", Some("arraycopy: last source index out of bounds")));
                }
                let slice = data[src_pos as usize..(src_pos + length) as usize].to_vec();
                if let Object::Array { data, .. } = m.heap.get_mut(dst) {
                    data[dst_pos as usize..(dst_pos + length) as usize].copy_from_slice(&slice);
                }
                return Ok(None);
            }
            "identityHashCode" => return unsupported("System.identityHashCode is nondeterministic"),
            _ => return unsupported(format!("System.{name} is a capability, not a computation")),
        },
        _ => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
    };
    Ok(Some(result))
}

fn math(m: &mut Machine, name: &str, descriptor: &str, a: &[Value]) -> Exec<Value> {
    let overflow = |m: &mut Machine, what: &str| m.throw("java/lang/ArithmeticException", Some(what));
    Ok(match (name, descriptor) {
        ("abs", "(I)I") => Value::Int(a[0].as_int().wrapping_abs()),
        ("abs", "(J)J") => Value::Long(a[0].as_long().wrapping_abs()),
        ("abs", "(F)F") => Value::Float(a[0].as_float().abs()),
        ("abs", "(D)D") => Value::Double(a[0].as_double().abs()),
        ("absExact", "(I)I") => Value::Int(a[0].as_int().checked_abs().ok_or_else(|| overflow(m, "Overflow to represent absolute value of Integer.MIN_VALUE"))?),
        ("absExact", "(J)J") => Value::Long(a[0].as_long().checked_abs().ok_or_else(|| overflow(m, "Overflow to represent absolute value of Long.MIN_VALUE"))?),
        ("max", "(II)I") => Value::Int(a[0].as_int().max(a[1].as_int())),
        ("max", "(JJ)J") => Value::Long(a[0].as_long().max(a[1].as_long())),
        ("max", "(FF)F") => Value::Float(java_max_f64(f64::from(a[0].as_float()), f64::from(a[1].as_float())) as f32),
        ("max", "(DD)D") => Value::Double(java_max_f64(a[0].as_double(), a[1].as_double())),
        ("min", "(II)I") => Value::Int(a[0].as_int().min(a[1].as_int())),
        ("min", "(JJ)J") => Value::Long(a[0].as_long().min(a[1].as_long())),
        ("min", "(FF)F") => Value::Float(java_min_f64(f64::from(a[0].as_float()), f64::from(a[1].as_float())) as f32),
        ("min", "(DD)D") => Value::Double(java_min_f64(a[0].as_double(), a[1].as_double())),
        ("addExact", "(II)I") => Value::Int(a[0].as_int().checked_add(a[1].as_int()).ok_or_else(|| overflow(m, "integer overflow"))?),
        ("addExact", "(JJ)J") => Value::Long(a[0].as_long().checked_add(a[1].as_long()).ok_or_else(|| overflow(m, "long overflow"))?),
        ("subtractExact", "(II)I") => Value::Int(a[0].as_int().checked_sub(a[1].as_int()).ok_or_else(|| overflow(m, "integer overflow"))?),
        ("subtractExact", "(JJ)J") => Value::Long(a[0].as_long().checked_sub(a[1].as_long()).ok_or_else(|| overflow(m, "long overflow"))?),
        ("multiplyExact", "(II)I") => Value::Int(a[0].as_int().checked_mul(a[1].as_int()).ok_or_else(|| overflow(m, "integer overflow"))?),
        ("multiplyExact", "(JJ)J") => Value::Long(a[0].as_long().checked_mul(a[1].as_long()).ok_or_else(|| overflow(m, "long overflow"))?),
        ("multiplyExact", "(JI)J") => Value::Long(a[0].as_long().checked_mul(i64::from(a[1].as_int())).ok_or_else(|| overflow(m, "long overflow"))?),
        ("negateExact", "(I)I") => Value::Int(a[0].as_int().checked_neg().ok_or_else(|| overflow(m, "integer overflow"))?),
        ("negateExact", "(J)J") => Value::Long(a[0].as_long().checked_neg().ok_or_else(|| overflow(m, "long overflow"))?),
        ("incrementExact", "(I)I") => Value::Int(a[0].as_int().checked_add(1).ok_or_else(|| overflow(m, "integer overflow"))?),
        ("incrementExact", "(J)J") => Value::Long(a[0].as_long().checked_add(1).ok_or_else(|| overflow(m, "long overflow"))?),
        ("decrementExact", "(I)I") => Value::Int(a[0].as_int().checked_sub(1).ok_or_else(|| overflow(m, "integer overflow"))?),
        ("decrementExact", "(J)J") => Value::Long(a[0].as_long().checked_sub(1).ok_or_else(|| overflow(m, "long overflow"))?),
        ("toIntExact", "(J)I") => Value::Int(i32::try_from(a[0].as_long()).map_err(|_| overflow(m, "integer overflow"))?),
        ("multiplyFull", _) => Value::Long(i64::from(a[0].as_int()) * i64::from(a[1].as_int())),
        ("multiplyHigh", _) => Value::Long(((i128::from(a[0].as_long()) * i128::from(a[1].as_long())) >> 64) as i64),
        ("floorDiv", "(II)I") => {
            let (x, y) = (a[0].as_int(), a[1].as_int());
            if y == 0 {
                return Err(overflow(m, "/ by zero"));
            }
            Value::Int(x.wrapping_div(y) - if (x % y != 0) && ((x < 0) != (y < 0)) { 1 } else { 0 })
        }
        ("floorDiv", "(JJ)J") | ("floorDiv", "(JI)J") => {
            let x = a[0].as_long();
            let y = if descriptor == "(JI)J" { i64::from(a[1].as_int()) } else { a[1].as_long() };
            if y == 0 {
                return Err(overflow(m, "/ by zero"));
            }
            Value::Long(x.wrapping_div(y) - if (x % y != 0) && ((x < 0) != (y < 0)) { 1 } else { 0 })
        }
        ("floorMod", "(II)I") => {
            let (x, y) = (a[0].as_int(), a[1].as_int());
            if y == 0 {
                return Err(overflow(m, "/ by zero"));
            }
            Value::Int(x.wrapping_rem(y).wrapping_add(y).wrapping_rem(y))
        }
        ("floorMod", "(JJ)J") | ("floorMod", "(JI)I") | ("floorMod", "(JI)J") => {
            let x = a[0].as_long();
            let y = if descriptor.starts_with("(JI") { i64::from(a[1].as_int()) } else { a[1].as_long() };
            if y == 0 {
                return Err(overflow(m, "/ by zero"));
            }
            let r = x.wrapping_rem(y).wrapping_add(y).wrapping_rem(y);
            if descriptor == "(JI)I" {
                Value::Int(r as i32)
            } else {
                Value::Long(r)
            }
        }
        ("ceilDiv", "(II)I") => {
            let (x, y) = (a[0].as_int(), a[1].as_int());
            if y == 0 {
                return Err(overflow(m, "/ by zero"));
            }
            Value::Int(x.wrapping_div(y) + if (x % y != 0) && ((x < 0) == (y < 0)) { 1 } else { 0 })
        }
        ("ceilDiv", "(JJ)J") => {
            let (x, y) = (a[0].as_long(), a[1].as_long());
            if y == 0 {
                return Err(overflow(m, "/ by zero"));
            }
            Value::Long(x.wrapping_div(y) + if (x % y != 0) && ((x < 0) == (y < 0)) { 1 } else { 0 })
        }
        ("clamp", "(JII)I") => Value::Int(a[0].as_long().clamp(i64::from(a[1].as_int()), i64::from(a[2].as_int())) as i32),
        ("clamp", "(JJJ)J") => Value::Long(a[0].as_long().clamp(a[1].as_long(), a[2].as_long())),
        ("clamp", "(DDD)D") => Value::Double(a[0].as_double().clamp(a[1].as_double(), a[2].as_double())),
        ("clamp", "(FFF)F") => Value::Float(a[0].as_float().clamp(a[1].as_float(), a[2].as_float())),
        ("sqrt", _) => Value::Double(a[0].as_double().sqrt()),
        ("cbrt", _) => Value::Double(a[0].as_double().cbrt()),
        ("pow", _) => Value::Double(a[0].as_double().powf(a[1].as_double())),
        ("exp", _) => Value::Double(a[0].as_double().exp()),
        ("log", _) => Value::Double(a[0].as_double().ln()),
        ("log10", _) => Value::Double(a[0].as_double().log10()),
        ("floor", _) => Value::Double(a[0].as_double().floor()),
        ("ceil", _) => Value::Double(a[0].as_double().ceil()),
        ("rint", _) => {
            let x = a[0].as_double();
            let r = x.round();
            Value::Double(if (x - x.trunc()).abs() == 0.5 && r % 2.0 != 0.0 { r - x.signum() } else { r })
        }
        ("round", "(D)J") => Value::Long((a[0].as_double() + 0.5).floor() as i64),
        ("round", "(F)I") => Value::Int((a[0].as_float() + 0.5).floor() as i32),
        ("signum", "(D)D") => Value::Double(if a[0].as_double() == 0.0 || a[0].as_double().is_nan() { a[0].as_double() } else { a[0].as_double().signum() }),
        ("signum", "(F)F") => Value::Float(if a[0].as_float() == 0.0 || a[0].as_float().is_nan() { a[0].as_float() } else { a[0].as_float().signum() }),
        ("hypot", _) => Value::Double(a[0].as_double().hypot(a[1].as_double())),
        ("sin", _) => Value::Double(a[0].as_double().sin()),
        ("cos", _) => Value::Double(a[0].as_double().cos()),
        ("tan", _) => Value::Double(a[0].as_double().tan()),
        ("atan", _) => Value::Double(a[0].as_double().atan()),
        ("atan2", _) => Value::Double(a[0].as_double().atan2(a[1].as_double())),
        ("toRadians", _) => Value::Double(a[0].as_double().to_radians()),
        ("toDegrees", _) => Value::Double(a[0].as_double().to_degrees()),
        ("random", _) => return unsupported("Math.random is nondeterministic"),
        _ => return unsupported(format!("Math.{name}{descriptor}")),
    })
}

fn java_max_f64(x: f64, y: f64) -> f64 {
    if x.is_nan() || y.is_nan() {
        f64::NAN
    } else if x == 0.0 && y == 0.0 {
        if x.is_sign_negative() && y.is_sign_negative() {
            -0.0
        } else {
            0.0
        }
    } else {
        x.max(y)
    }
}

fn java_min_f64(x: f64, y: f64) -> f64 {
    if x.is_nan() || y.is_nan() {
        f64::NAN
    } else if x == 0.0 && y == 0.0 {
        if x.is_sign_negative() || y.is_sign_negative() {
            -0.0
        } else {
            0.0
        }
    } else {
        x.min(y)
    }
}

/// `NumberFormatException` for the String `s`, quoted in its message as it is.
fn number_format(m: &mut Machine, s: Option<&JStr>, radix: u32) -> Fault {
    let Some(s) = s else { return m.throw("java/lang/NumberFormatException", Some("Cannot parse null string: null")) };
    let mut message = JStr::from("For input string: \"");
    message.push(s);
    message.push_str(if radix == 10 { "\"".to_string() } else { format!("\" under radix {radix}") }.as_str());
    m.throw_units("java/lang/NumberFormatException", message)
}

fn parse_integral(m: &mut Machine, v: Value, radix: u32, min: i64, max: i64) -> Exec<i64> {
    let Some(s) = m.units_of(v) else { return Err(number_format(m, None, radix)) };
    // Java takes any Unicode digit (`Character.digit`), whose tables aren't modelled: a String with a code unit
    // outside ASCII is refused, not parsed as Rust's ASCII digits would parse it.
    if s.units().iter().any(|&u| u > 0x7F) {
        return unsupported(format!("parsing {} (Character.digit's Unicode digits are not modelled)", s.display()));
    }
    let text_owned = s.text().unwrap_or_default();
    let text = text_owned.as_str();
    let trimmed = text.strip_prefix('+').unwrap_or(text);
    let parsed = if text.is_empty() || trimmed.is_empty() || (text.starts_with('+') && text[1..].starts_with(['+', '-'])) {
        None
    } else {
        i64::from_str_radix(trimmed, radix).ok()
    };
    match parsed {
        Some(v) if v >= min && v <= max => Ok(v),
        _ => Err(number_format(m, Some(&s), radix)),
    }
}

fn integral(m: &mut Machine, owner: &str, name: &str, descriptor: &str, a: &[Value]) -> Exec<Value> {
    let (min, max, is_long) = match owner {
        "java/lang/Long" => (i64::MIN, i64::MAX, true),
        "java/lang/Short" => (i64::from(i16::MIN), i64::from(i16::MAX), false),
        "java/lang/Byte" => (i64::from(i8::MIN), i64::from(i8::MAX), false),
        _ => (i64::from(i32::MIN), i64::from(i32::MAX), false),
    };
    let wrap = |v: i64| if is_long { Value::Long(v) } else { Value::Int(v as i32) };
    Ok(match name {
        "valueOf" if descriptor.starts_with("(Ljava/lang/String;") => {
            let radix = if descriptor.contains("I)") { a[1].as_int() as u32 } else { 10 };
            let v = parse_integral(m, a[0], radix, min, max)?;
            box_value(m, owner, wrap(v))
        }
        "valueOf" => box_value(m, owner, a[0]),
        "parseInt" | "parseLong" | "parseShort" | "parseByte" => {
            let radix = if descriptor.contains("I)") { a[1].as_int() as u32 } else { 10 };
            wrap(parse_integral(m, a[0], radix, min, max)?)
        }
        "toString" if descriptor.ends_with("I)Ljava/lang/String;") && a.len() == 2 => {
            let radix = a[1].as_int() as u32;
            let v = as_i64(a[0]);
            let s = if (2..=36).contains(&radix) { to_radix(v, radix) } else { v.to_string() };
            m.new_string(s)
        }
        "toString" => m.new_string(as_i64(a[0]).to_string()),
        "toHexString" => m.new_string(if is_long { format!("{:x}", a[0].as_long()) } else { format!("{:x}", a[0].as_int()) }),
        "toBinaryString" => m.new_string(if is_long { format!("{:b}", a[0].as_long()) } else { format!("{:b}", a[0].as_int()) }),
        "toOctalString" => m.new_string(if is_long { format!("{:o}", a[0].as_long()) } else { format!("{:o}", a[0].as_int()) }),
        "compare" => Value::Int(as_i64(a[0]).cmp(&as_i64(a[1])) as i32),
        "compareUnsigned" => Value::Int(if is_long { (a[0].as_long() as u64).cmp(&(a[1].as_long() as u64)) as i32 } else { (a[0].as_int() as u32).cmp(&(a[1].as_int() as u32)) as i32 }),
        "max" => wrap(as_i64(a[0]).max(as_i64(a[1]))),
        "min" => wrap(as_i64(a[0]).min(as_i64(a[1]))),
        "sum" => wrap(if is_long { a[0].as_long().wrapping_add(a[1].as_long()) } else { i64::from(a[0].as_int().wrapping_add(a[1].as_int())) }),
        "signum" => Value::Int(as_i64(a[0]).signum() as i32),
        "hashCode" => Value::Int(hash_code(m, a[0])?),
        "bitCount" => Value::Int(if is_long { a[0].as_long().count_ones() } else { a[0].as_int().count_ones() } as i32),
        "numberOfLeadingZeros" => Value::Int(if is_long { a[0].as_long().leading_zeros() } else { a[0].as_int().leading_zeros() } as i32),
        "numberOfTrailingZeros" => Value::Int(if is_long { a[0].as_long().trailing_zeros() } else { a[0].as_int().trailing_zeros() } as i32),
        "highestOneBit" => wrap(if is_long {
            let x = a[0].as_long();
            if x == 0 { 0 } else { (1u64 << (63 - x.leading_zeros())) as i64 }
        } else {
            let x = a[0].as_int();
            i64::from(if x == 0 { 0 } else { (1u32 << (31 - x.leading_zeros())) as i32 })
        }),
        "lowestOneBit" => wrap(if is_long { a[0].as_long() & a[0].as_long().wrapping_neg() } else { i64::from(a[0].as_int() & a[0].as_int().wrapping_neg()) }),
        "reverse" => wrap(if is_long { a[0].as_long().reverse_bits() } else { i64::from(a[0].as_int().reverse_bits()) }),
        "reverseBytes" => wrap(if is_long { a[0].as_long().swap_bytes() } else { i64::from(a[0].as_int().swap_bytes()) }),
        "rotateLeft" => wrap(if is_long { a[0].as_long().rotate_left(a[1].as_int() as u32 & 63) } else { i64::from(a[0].as_int().rotate_left(a[1].as_int() as u32 & 31)) }),
        "rotateRight" => wrap(if is_long { a[0].as_long().rotate_right(a[1].as_int() as u32 & 63) } else { i64::from(a[0].as_int().rotate_right(a[1].as_int() as u32 & 31)) }),
        "divideUnsigned" => {
            if as_i64(a[1]) == 0 {
                return Err(m.throw("java/lang/ArithmeticException", Some("/ by zero")));
            }
            wrap(if is_long { ((a[0].as_long() as u64) / (a[1].as_long() as u64)) as i64 } else { i64::from(((a[0].as_int() as u32) / (a[1].as_int() as u32)) as i32) })
        }
        "remainderUnsigned" => {
            if as_i64(a[1]) == 0 {
                return Err(m.throw("java/lang/ArithmeticException", Some("/ by zero")));
            }
            wrap(if is_long { ((a[0].as_long() as u64) % (a[1].as_long() as u64)) as i64 } else { i64::from(((a[0].as_int() as u32) % (a[1].as_int() as u32)) as i32) })
        }
        "toUnsignedLong" => Value::Long(i64::from(a[0].as_int() as u32)),
        "toUnsignedInt" => Value::Int(as_i64(a[0]) as i32 & if owner == "java/lang/Byte" { 0xff } else { 0xffff }),
        "toUnsignedString" => m.new_string(if is_long { (a[0].as_long() as u64).to_string() } else { (a[0].as_int() as u32).to_string() }),
        _ => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
    })
}

fn to_radix(v: i64, radix: u32) -> String {
    if v == 0 {
        return "0".into();
    }
    let negative = v < 0;
    let mut n = (v as i128).unsigned_abs();
    let mut digits = Vec::new();
    while n > 0 {
        digits.push(std::char::from_digit((n % u128::from(radix)) as u32, radix).unwrap_or('?'));
        n /= u128::from(radix);
    }
    let mut s: String = digits.iter().rev().collect();
    if negative {
        s.insert(0, '-');
    }
    s
}

fn character(m: &mut Machine, name: &str, descriptor: &str, a: &[Value]) -> Exec<Value> {
    let c = |v: Value| char::from_u32(v.as_int() as u32).unwrap_or('\u{FFFD}');
    Ok(match name {
        "valueOf" => box_value(m, "java/lang/Character", a[0]),
        "toString" => m.new_string(JStr::from_units(vec![a[0].as_int() as u16])),
        "isDigit" => Value::bool(c(a[0]).is_numeric()),
        "isLetter" => Value::bool(c(a[0]).is_alphabetic()),
        "isLetterOrDigit" => Value::bool(c(a[0]).is_alphanumeric()),
        "isAlphabetic" => Value::bool(c(a[0]).is_alphabetic()),
        "isWhitespace" | "isSpaceChar" => Value::bool(c(a[0]).is_whitespace()),
        "isUpperCase" => Value::bool(c(a[0]).is_uppercase()),
        "isLowerCase" => Value::bool(c(a[0]).is_lowercase()),
        "toUpperCase" => Value::Int(c(a[0]).to_uppercase().next().map(|x| x as i32).unwrap_or(a[0].as_int())),
        "toLowerCase" => Value::Int(c(a[0]).to_lowercase().next().map(|x| x as i32).unwrap_or(a[0].as_int())),
        "getNumericValue" => Value::Int(c(a[0]).to_digit(36).map(|d| d as i32).unwrap_or(-1)),
        "digit" => Value::Int(c(a[0]).to_digit(a[1].as_int() as u32).map(|d| d as i32).unwrap_or(-1)),
        "forDigit" => Value::Int(std::char::from_digit(a[0].as_int() as u32, a[1].as_int() as u32).map(|x| x as i32).unwrap_or(0)),
        "compare" => Value::Int(a[0].as_int() - a[1].as_int()),
        "hashCode" => Value::Int(a[0].as_int()),
        "isSurrogate" => Value::bool((0xD800..=0xDFFF).contains(&a[0].as_int())),
        _ => return unsupported(format!("Character.{name}{descriptor}")),
    })
}

fn floating(m: &mut Machine, owner: &str, name: &str, descriptor: &str, a: &[Value]) -> Exec<Value> {
    let is_double = owner == "java/lang/Double";
    let wrap = |x: f64| if is_double { Value::Double(x) } else { Value::Float(x as f32) };
    Ok(match name {
        "valueOf" if descriptor.starts_with("(Ljava/lang/String;") => {
            let Some(units) = m.units_of(a[0]) else { return Err(m.throw("java/lang/NullPointerException", None)) };
            // A String with an isolated surrogate is no number: the exception quotes it as it is.
            match units.text().and_then(|text| text.trim().parse::<f64>().ok()) {
                Some(x) => box_value(m, owner, wrap(x)),
                None => return Err(number_format(m, Some(&units), 10)),
            }
        }
        "valueOf" => box_value(m, owner, a[0]),
        "parseDouble" | "parseFloat" => {
            let Some(units) = m.units_of(a[0]) else { return Err(m.throw("java/lang/NullPointerException", None)) };
            match units.text().and_then(|text| text.trim().trim_end_matches(['d', 'D', 'f', 'F']).parse::<f64>().ok()) {
                Some(x) => wrap(x),
                None => return Err(number_format(m, Some(&units), 10)),
            }
        }
        "toString" => m.new_string(if is_double { double_to_string(a[0].as_double()) } else { float_to_string(a[0].as_float()) }),
        "compare" => Value::Int(compare_values(a[0], a[1], &Type::Double)),
        "isNaN" => Value::bool(as_f64(a[0]).is_nan()),
        "isInfinite" => Value::bool(as_f64(a[0]).is_infinite()),
        "isFinite" => Value::bool(as_f64(a[0]).is_finite()),
        "max" => wrap(java_max_f64(as_f64(a[0]), as_f64(a[1]))),
        "min" => wrap(java_min_f64(as_f64(a[0]), as_f64(a[1]))),
        "sum" => wrap(as_f64(a[0]) + as_f64(a[1])),
        "hashCode" => Value::Int(hash_code(m, a[0])?),
        "doubleToLongBits" => Value::Long(if a[0].as_double().is_nan() { 0x7ff8000000000000 } else { a[0].as_double().to_bits() as i64 }),
        "doubleToRawLongBits" => Value::Long(a[0].as_double().to_bits() as i64),
        "longBitsToDouble" => Value::Double(f64::from_bits(a[0].as_long() as u64)),
        "floatToIntBits" => Value::Int(if a[0].as_float().is_nan() { 0x7fc00000 } else { a[0].as_float().to_bits() as i32 }),
        "floatToRawIntBits" => Value::Int(a[0].as_float().to_bits() as i32),
        "intBitsToFloat" => Value::Float(f32::from_bits(a[0].as_int() as u32)),
        _ => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
    })
}

fn arrays(m: &mut Machine, name: &str, descriptor: &str, a: &[Value]) -> Exec<Value> {
    Ok(match name {
        "asList" => {
            let elements = collection_elements(m, a[0])?;
            new_list(m, elements, false)
        }
        "toString" => {
            let Some(r) = a[0].as_ref() else { return Ok(m.new_string("null")) };
            let (element, data) = match m.heap.get(r) {
                Object::Array { element, data } => (element.clone(), data.clone()),
                _ => return unsupported("Arrays.toString of a non-array"),
            };
            let mut parts = Vec::new();
            for v in data {
                parts.push(to_java_string(m, v, &element)?);
            }
            let mut out = JStr::from("[");
            out.push(&JStr::join(&parts, &JStr::from(", ")));
            out.push_str("]");
            m.new_string(out)
        }
        "equals" => {
            let (Some(x), Some(y)) = (a[0].as_ref(), a[1].as_ref()) else { return Ok(Value::bool(a[0] == a[1])) };
            let (dx, dy) = match (m.heap.get(x), m.heap.get(y)) {
                (Object::Array { data: dx, .. }, Object::Array { data: dy, .. }) => (dx.clone(), dy.clone()),
                _ => return unsupported("Arrays.equals of non-arrays"),
            };
            if dx.len() != dy.len() {
                return Ok(Value::Int(0));
            }
            for (p, q) in dx.into_iter().zip(dy) {
                if !equals(m, p, q)? {
                    return Ok(Value::Int(0));
                }
            }
            Value::Int(1)
        }
        "hashCode" => {
            let Some(r) = a[0].as_ref() else { return Ok(Value::Int(0)) };
            let data = match m.heap.get(r) {
                Object::Array { data, .. } => data.clone(),
                _ => return unsupported("Arrays.hashCode of a non-array"),
            };
            let mut h: i32 = 1;
            for v in data {
                h = h.wrapping_mul(31).wrapping_add(hash_code(m, v)?);
            }
            Value::Int(h)
        }
        "copyOf" => {
            let Some(r) = a[0].as_ref() else { return Err(m.npe()) };
            let n = a[1].as_int();
            if n < 0 {
                return Err(m.throw("java/lang/NegativeArraySizeException", Some(&n.to_string())));
            }
            let (element, mut data) = match m.heap.get(r) {
                Object::Array { element, data } => (element.clone(), data.clone()),
                _ => return unsupported("Arrays.copyOf of a non-array"),
            };
            data.resize(n as usize, Value::default_for(&element));
            m.new_array_of(element, data)
        }
        "copyOfRange" => {
            let Some(r) = a[0].as_ref() else { return Err(m.npe()) };
            let (from, to) = (a[1].as_int(), a[2].as_int());
            let (element, data) = match m.heap.get(r) {
                Object::Array { element, data } => (element.clone(), data.clone()),
                _ => return unsupported("Arrays.copyOfRange of a non-array"),
            };
            if from > to {
                return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("{from} > {to}"))));
            }
            if from < 0 || from as usize > data.len() {
                return Err(m.throw("java/lang/ArrayIndexOutOfBoundsException", Some(&index_message(from.into(), data.len()))));
            }
            let mut out: Vec<Value> = data[from as usize..(to as usize).min(data.len())].to_vec();
            out.resize((to - from) as usize, Value::default_for(&element));
            m.new_array_of(element, out)
        }
        "fill" if a.len() == 2 => {
            let Some(r) = a[0].as_ref() else { return Err(m.npe()) };
            m.check_write(r, "an array element")?;
            if let Object::Array { data, .. } = m.heap.get_mut(r) {
                for v in data.iter_mut() {
                    *v = a[1];
                }
            }
            return Ok(Value::Null);
        }
        _ => return unsupported(format!("Arrays.{name}{descriptor}")),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn string_hash_matches_java() {
        assert_eq!(string_hash(""), 0);
        assert_eq!(string_hash("a"), 97);
        assert_eq!(string_hash("hello"), 99162322);
        assert_eq!(string_hash("Hello, World!"), 1498789909);
    }

    #[test]
    fn radix_and_find() {
        assert_eq!(to_radix(255, 16), "ff");
        assert_eq!(to_radix(-8, 2), "-1000");
        assert_eq!(JStr::from("hello").find(&JStr::from("ll"), 0), 2);
        assert_eq!(JStr::from("hello").find(&JStr::from("ll"), 3), -1);
        assert_eq!(JStr::from("hello").find(&JStr::from(""), 2), 2);
        assert_eq!(JStr::from("hello").hash_code(), string_hash("hello"));
    }
}
