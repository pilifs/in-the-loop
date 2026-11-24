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

/// Class.getName takes internal names for objects and JVM descriptors for arrays.
fn class_name(m: &Machine, ty: &Type) -> String {
    match ty {
        Type::Object(name) => m.cp.binary_name(name),
        Type::Array(_) => m.cp.binary_name(&ty.descriptor()),
        primitive => primitive.java_name(),
    }
}

fn type_name(m: &Machine, ty: &Type) -> String {
    match ty {
        Type::Array(element) => format!("{}[]", type_name(m, element)),
        other => class_name(m, other),
    }
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
        Object::Instance { base: Base::Throwable { message: msg, cause: c, .. }, .. } => {
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
    Type::for_wrapper(class).unwrap_or(Type::Int)
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
                format!("{} {}", if interface { "interface" } else { "class" }, m.cp.binary_name(name))
            }
            other => format!("class {}", class_name(m, other)),
        }
        .into(),
        Native::Throwable { class, message, .. } => match message.and_then(|s| m.heap.string(s).cloned()) {
            Some(msg) => {
                let mut out = JStr::from(format!("{}: ", m.cp.binary_name(&class)));
                out.push(&msg);
                out
            }
            None => m.cp.binary_name(&class).into(),
        },
        Native::Optional(None) => "Optional.empty".into(),
        Native::Optional(Some(v)) => {
            let mut out = JStr::from("Optional[");
            out.push(&to_java_string(m, v, &Type::object("java/lang/Object"))?);
            out.push_str("]");
            out
        }
        Native::Iterator { .. } | Native::ArrayListIterator { .. } => return unsupported("Iterator.toString is identity-based"),
        Native::ArrayListSubList { .. } => return unsupported("rendering a live ArrayList sublist"),
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

/// The image-backed Arrays.asList and the interpreter's lists share the List
/// equality contract. Compare in receiver order, dispatching each element's equals.
pub(super) fn array_list_equality(m: &mut Machine, r: Ref, other: Value) -> Option<Exec<bool>> {
    let s = other.as_ref()?;
    let view = |v| matches!(m.heap.get(v), Object::Instance { class, .. } if class == "java/util/Arrays$ArrayList")
        || matches!(m.heap.get(v), Object::Native(Native::ArrayListSubList { .. }));
    let native = |v| matches!(m.heap.get(v), Object::Native(Native::List { .. }));
    if !((view(r) && (native(s) || view(s))) || (native(r) && view(s))) { return None; }
    if r == s { return Some(Ok(true)); }
    let version = match m.heap.get(r) {
        Object::Native(Native::ArrayListSubList { root, expected_mod_count, .. }) => Some((*root, *expected_mod_count)),
        _ => m.array_list_mod_count.get(&r).map(|count| (r, *count)),
    };
    Some((|| {
        let mut it = |v| m.call_virtual(Value::Ref(v), "java/util/List", "iterator", "()Ljava/util/Iterator;", vec![]);
        let left = it(r)?.expect("list iterator");
        let right = it(s)?.expect("list iterator");
        let equal = loop {
            let mut has = |v| m.call_virtual(v, "java/util/Iterator", "hasNext", "()Z", vec![]).map(|v| v.expect("boolean").as_int() != 0);
            let (a, b) = (has(left)?, has(right)?);
            if !a || !b { break a == b; }
            let mut next = |v| m.call_virtual(v, "java/util/Iterator", "next", "()Ljava/lang/Object;", vec![]).map(|v| v.expect("element"));
            let (a, b) = (next(left)?, next(right)?);
            if !equals(m, a, b)? { break false; }
        };
        if version.is_some_and(|(root, count)| m.array_list_mod_count.get(&root) != Some(&count)) {
            return Err(m.throw("java/util/ConcurrentModificationException", None));
        }
        Ok(equal)
    })())
}

fn native_equals(m: &mut Machine, r: Ref, other: Value) -> Exec<bool> {
    let Value::Ref(o) = other else { return Ok(false) };
    if r == o {
        return Ok(true);
    }
    if matches!(m.heap.get(r), Object::Native(Native::ArrayListSubList { .. })) && m.cp.is_subtype(&m.class_of(o), "java/util/List") {
        return unsupported("comparing a live sublist with this List implementation");
    }
    if let (Object::Native(Native::Map { entries, .. }), Object::Instance { class, .. }) = (m.heap.get(r), m.heap.get(o)) {
        if class == "java/util/HashMap" {
            let entries = entries.clone();
            let other = map_entries(m, other)?;
            return equal_map_entries(m, &entries, &other);
        }
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
        (Native::Map { entries: x, .. }, Native::Map { entries: y, .. }) => equal_map_entries(m, &x, &y)?,
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
        Native::Class(t) => string_hash(&class_name(m, &t)),
        Native::Optional(None) => 0,
        Native::Optional(Some(v)) => hash_code(m, v)?,
        other => return unsupported(format!("{}.hashCode is identity-based", other.class_name().replace('/', "."))),
    })
}

// Static state of JDK classes

pub fn get_static_jdk(m: &mut Machine, class: &str, name: &str) -> Exec<Value> {
    if name == "TYPE" {
        if let Some(ty) = Type::for_wrapper(class) { return Ok(m.class_object(&ty)); }
    }
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
        _ if crate::classpath::ClassPath::big_number(class) => return m.new_instance(class),
        "java/util/ArrayDeque" | "java/util/ArrayDeque$DeqIterator" => return m.new_instance(class),
        "java/util/Properties" if m.cp.properties_method(class, class, "<init>", "()V", true).is_some() => return m.new_instance(class),
        crate::models::CONCURRENT_MAP if m.cp.concurrent_map_method("<init>", "()V").is_some() => return m.new_instance(class),
        "java/lang/StringBuilder" | "java/lang/StringBuffer" => Native::StringBuilder(JStr::new()),
        // A String the program constructs: `<init>` gives it its contents (`invoke_special_jdk`).
        "java/lang/String" => Native::String(JStr::new()),
        "java/util/ArrayList" | "java/util/LinkedList" => Native::List { elements: Vec::new(), mutable: true },
        "java/util/HashMap" | "java/util/LinkedHashMap" | "java/util/TreeMap" => Native::Map { entries: Vec::new(), mutable: true },
        "java/util/HashSet" | "java/util/LinkedHashSet" | "java/util/TreeSet" => Native::Set { elements: Vec::new(), mutable: true },
        "java/lang/Object" | "java/util/concurrent/ConcurrentLinkedQueue" | crate::bmc::runtime::REENTRANT_LOCK => return Ok(Value::Ref(m.alloc(Object::Instance { class: class.into(), fields: Default::default(), base: Base::Object }))),
        _ if m.cp.is_subtype(class, "java/lang/Throwable") => Native::Throwable { class: class.into(), message: None, cause: None, suppressed: None },
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
            if owner == "java/lang/StringIndexOutOfBoundsException" && m.class_of(r) == owner {
                if let Some((class, method)) = m.cp.string_range_constructor(owner, descriptor) {
                    let mut full = vec![Value::Ref(r)];
                    full.extend(args);
                    return m.invoke(&class, &method, full);
                }
            }
            init_throwable(m, r, owner, descriptor, &args)?;
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
                "([BLjava/nio/charset/Charset;)V" | "([BIILjava/nio/charset/Charset;)V" => {
                    if m.get_static("java/nio/charset/StandardCharsets", "UTF_8")? != *args.last().unwrap() {
                        return unsupported("String byte slice requires the exact UTF-8 charset");
                    }
                    let Some(array) = args[0].as_ref() else { return unsupported("String byte slice of null"); };
                    let Object::Array { element: Type::Byte, data } = m.heap.get(array) else { return unsupported("String byte slice needs a byte array"); };
                    let (offset, count) = if args.len() == 2 { (0, data.len() as i32) } else { (args[1].as_int(), args[2].as_int()) };
                    let (Ok(first), Ok(n)) = (usize::try_from(offset), usize::try_from(count)) else { return unsupported("invalid String byte range"); };
                    let Some(slice) = data.get(first..first.saturating_add(n)) else { return unsupported("invalid String byte range"); };
                    let bytes: Vec<u8> = slice.iter().map(|v| v.as_int() as u8).collect();
                    let Some(units) = crate::bmc::bytes::utf8_slice_units(&bytes) else { return unsupported("interior malformed UTF-8 sequence"); };
                    JStr::from_units(units)
                }
                "()V" => JStr::new(),
                "(Ljava/lang/String;)V" => string_arg(m, args[0])?,
                "([BIII)V" => {
                    let (high, offset, count) = (args[1].as_int(), args[2].as_int(), args[3].as_int());
                    let data = args[0].as_ref().and_then(|a| match m.heap.get(a) {
                        Object::Array { element: Type::Byte, data } => Some(data), _ => None,
                    });
                    match data {
                        Some(bytes) if offset >= 0 && count >= 0 && i64::from(offset) + i64::from(count) <= bytes.len() as i64 =>
                            JStr::from_units(bytes[offset as usize..][..count as usize].iter()
                                .map(|v| ((high as u16) << 8) | u16::from(v.as_int() as u8)).collect()),
                        _ => {
                            let Some((class, method)) = m.cp.string_range_constructor(owner, descriptor) else {
                                return unsupported("String byte range exception needs the selected JDK constructor");
                            };
                            let mut full = vec![Value::Ref(r)];
                            full.extend(args);
                            return m.invoke(&class, &method, full);
                        }
                    }
                }
                "([C)V" => {
                    let Some(a) = args[0].as_ref() else { return Err(m.npe()) };
                    char_array_units(m, a).ok_or_else(|| Fault::Unsupported("new String of a non-array".into()))?
                }
                "([CII)V" => {
                    let (offset, count) = (args[1].as_int(), args[2].as_int());
                    let Some(a) = args[0].as_ref() else {
                        if offset >= 0 && count >= 0 { return Err(m.npe()) }
                        let Some((class, method)) = m.cp.string_range_constructor(owner, descriptor) else {
                            return unsupported("String(char[], int, int) exception order needs the selected JDK constructor");
                        };
                        return m.invoke(&class, &method, vec![Value::Ref(r), Value::Null, args[1], args[2]]);
                    };
                    let units = char_array_units(m, a).ok_or_else(|| Fault::Unsupported("new String of a non-array".into()))?;
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
            if owner == "java/util/ArrayList" { m.array_list_mod_count.insert(r, 0); }
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

fn init_throwable(m: &mut Machine, r: Ref, owner: &str, descriptor: &str, args: &[Value]) -> Exec<()> {
    use crate::bmc::throwables::{plain_constructor, SUPPRESSED, THROWABLE};
    if plain_constructor(m.cp, owner, descriptor) || (owner == THROWABLE && descriptor == "(Ljava/lang/Throwable;)V") {
        let fills_stack = args.get(3).is_none_or(|flag| flag.as_int() != 0);
        if fills_stack && m.cp.bytecode_method(&m.class_of(r), "fillInStackTrace", "()Ljava/lang/Throwable;").is_some() {
            return unsupported("Throwable constructor with an application fillInStackTrace override");
        }
        let state = if args.get(2).is_some_and(|flag| flag.as_int() == 0) {
            Value::Null
        } else {
            m.get_static(THROWABLE, "SUPPRESSED_SENTINEL")?
        };
        m.put_field(Value::Ref(r), SUPPRESSED, state)?;
    }
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

/// Execute the same final methods as the checker, on the ordinary interpreter heap.
fn invoke_suppression(m: &mut Machine, r: Ref, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let (class, method) = m.cp.throwable_image_method(crate::bmc::throwables::THROWABLE, name, descriptor)
        .ok_or_else(|| Fault::Unsupported(format!("no selected JDK bytecode for Throwable.{name}{descriptor}")))?;
    let mut full = vec![Value::Ref(r)];
    full.extend(args);
    m.invoke(&class, &method, full)
}

/// A method inherited from a JDK superclass, called on an application instance: `Enum.ordinal`,
/// `Throwable.getMessage`, `Object.equals`, ...
pub fn invoke_inherited(m: &mut Machine, r: Ref, owner: &str, name: &str, descriptor: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let (class, base) = match m.heap.get(r) {
        Object::Instance { class, base, .. } => (class.clone(), base.clone()),
        _ => return unsupported("inherited call on a non-instance"),
    };
    if class == crate::bmc::runtime::REENTRANT_LOCK && crate::bmc::runtime::sequential_lock_call(owner, name, descriptor) {
        let field = crate::bmc::runtime::HOLD_COUNT;
        let count = if name == "<init>" { 0 } else { m.get_field(Value::Ref(r), field)?.as_int() };
        let Some((write, returned)) = crate::bmc::runtime::sequential_lock_transition(name, count) else {
            return unsupported("an unbalanced unlock or excessive recursion on a reentrant lock");
        };
        if let Some(next) = write { m.put_field(Value::Ref(r), field, Value::Int(next))?; }
        return Ok(returned.map(Value::Int));
    }
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
            ("compareTo", "(Ljava/lang/Enum;)I" | "(Ljava/lang/Object;)I") => {
                let Some(o) = args[0].as_ref() else { return Err(m.npe()) };
                match m.heap.get(o) {
                    Object::Instance { class: other_class, base: Base::Enum { ordinal: other, .. }, .. }
                        if class == *other_class || declaring_enum(m, &class)? == declaring_enum(m, other_class)? =>
                        Ok(Some(Value::Int(ordinal.wrapping_sub(*other)))),
                    _ => Err(m.throw("java/lang/ClassCastException", None)),
                }
            }
            ("getDeclaringClass", _) => {
                let declaring = declaring_enum(m, &class)?;
                Ok(Some(m.class_object(&Type::Object(declaring))))
            }
            _ => unsupported(format!("Enum.{name}{descriptor}")),
        },
        Base::Throwable { .. } => match name {
            "<init>" => {
                init_throwable(m, r, owner, descriptor, &args)?;
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
                        let mut out = JStr::from(format!("{}: ", m.cp.binary_name(&class)));
                        out.push(&msg);
                        out
                    }
                    None => m.cp.binary_name(&class).into(),
                };
                Ok(Some(m.new_string(text)))
            }
            "initCause" => {
                set_throwable(m, r, None, args[0].as_ref(), false, true);
                Ok(Some(Value::Ref(r)))
            }
            "fillInStackTrace" => Ok(Some(Value::Ref(r))),
            "addSuppressed" | "getSuppressed" => invoke_suppression(m, r, name, descriptor, args),
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

/// Enum.getDeclaringClass uses the runtime class's direct superclass, including for a constant-specific body.
fn declaring_enum(m: &Machine, class: &str) -> Exec<String> {
    match m.cp.superclass(class) {
        Some(parent) if parent == "java/lang/Enum" => Ok(class.to_string()),
        Some(parent) => Ok(parent),
        None => unsupported(format!("unknown superclass of enum {class}")),
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
        Object::Native(Native::ArrayListSubList { root, offset, length, expected_mod_count, .. }) => {
            if m.array_list_mod_count.get(root) != Some(expected_mod_count) { return Err(m.throw("java/util/ConcurrentModificationException", None)); }
            let Object::Native(Native::List { elements, .. }) = m.heap.get(*root) else { return unsupported("sublist without its root"); };
            Ok(elements[*offset..*offset + *length].to_vec())
        }
        Object::Instance { class, .. } if matches!(class.as_str(), "java/util/HashMap$KeySet" | "java/util/HashMap$EntrySet" | "java/util/Arrays$ArrayList") => {
            let it = m.call_virtual(v, "java/lang/Iterable", "iterator", "()Ljava/util/Iterator;", vec![])?.expect("iterator reference");
            let mut elements = Vec::new();
            while m.call_virtual(it, "java/util/Iterator", "hasNext", "()Z", vec![])?.expect("hasNext result").as_int() != 0 {
                elements.push(m.call_virtual(it, "java/util/Iterator", "next", "()Ljava/lang/Object;", vec![])?.expect("next reference"));
            }
            Ok(elements)
        }
        Object::Array { data, .. } => Ok(data.clone()),
        _ => unsupported(format!("iterating a {}", m.class_of(r).replace('/', "."))),
    }
}

fn map_entries(m: &mut Machine, v: Value) -> Exec<Vec<(Value, Value)>> {
    let Some(r) = v.as_ref() else { return Err(m.npe()) };
    match m.heap.get(r) {
        Object::Native(Native::Map { entries, .. }) => Ok(entries.clone()),
        Object::Instance { class, .. } if class == "java/util/HashMap" => {
            let set = m.call_virtual(v, "java/util/Map", "entrySet", "()Ljava/util/Set;", vec![])?.expect("entry set");
            collection_elements(m, set)?.into_iter().map(|node| {
                let key = m.call_virtual(node, "java/util/Map$Entry", "getKey", "()Ljava/lang/Object;", vec![])?.expect("entry key");
                let value = m.call_virtual(node, "java/util/Map$Entry", "getValue", "()Ljava/lang/Object;", vec![])?.expect("entry value");
                Ok((key, value))
            }).collect()
        }
        _ => unsupported(format!("{} is not a modelled Map", m.class_of(r).replace('/', "."))),
    }
}

fn equal_map_entries(m: &mut Machine, left: &[(Value, Value)], right: &[(Value, Value)]) -> Exec<bool> {
    if left.len() != right.len() { return Ok(false); }
    for &(key, value) in left {
        let mut found = false;
        for &(other_key, other_value) in right {
            if equals(m, key, other_key)? {
                found = equals(m, value, other_value)?;
                break;
            }
        }
        if !found { return Ok(false); }
    }
    Ok(true)
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
        ("intern", "()Ljava/lang/String;") if matches!(native, Native::String(_)) => {
            if m.interned.values().any(|&known| known == r) {
                return Ok(Some(Value::Ref(r)));
            }
            return unsupported("String.intern on a receiver not established as a canonical literal");
        }
        // A String's toString is the String itself, which `==` sees.
        ("toString", "()Ljava/lang/String;") if matches!(native, Native::String(_)) => return Ok(Some(Value::Ref(r))),
        ("toString", "()Ljava/lang/String;") => {
            if let Native::Boxed { class, value } = &native {
                if m.cp.floating_formatter(class) {
                    let desc = if class == "java/lang/Float" { "(F)Ljava/lang/String;" } else { "(D)Ljava/lang/String;" };
                    return m.call_static_jdk(class, "toString", desc, vec![*value]);
                }
            }
            let s = native_to_string(m, r)?;
            return Ok(Some(m.new_string(s)));
        }
        _ => {}
    }
    match native {
        Native::String(s) => {
            if (name, descriptor) == ("getChars", "(II[CI)V") {
                let (begin, end, offset) = (args[0].as_int(), args[1].as_int(), args[3].as_int());
                if begin < 0 || end < begin || end as usize > s.units().len() { return unsupported("String.getChars source range is not proven valid"); }
                let Some(dst) = args[2].as_ref() else { return Err(m.npe()) };
                let Object::Array { element: Type::Char, data } = m.heap.get(dst) else { return unsupported("String.getChars needs a known char array") };
                let count = (end - begin) as usize;
                if offset < 0 || offset as usize + count > data.len() { return unsupported("String.getChars destination range is not proven valid"); }
                if count > 0 {
                    m.check_write(dst, "String.getChars writes a char array")?;
                    let Object::Array { data, .. } = m.heap.get_mut(dst) else { unreachable!() };
                    for (cell, unit) in data[offset as usize..][..count].iter_mut().zip(&s.units()[begin as usize..end as usize]) {
                        *cell = Value::Int(i32::from(*unit));
                    }
                }
                return Ok(None);
            }
            let value = string_method(m, &s, name, descriptor, &args)?;
            // The JDK returns the String itself where a substring is its whole range or nothing is lowered, and
            // the literal "" for any other empty substring: `==` sees which.
            if let (true, Value::Ref(made)) = (matches!(name, "substring" | "toLowerCase" | "concat" | "trim"), value) {
                let content = match m.heap.get(made) {
                    Object::Native(Native::String(t)) => Some(t.units().to_vec()),
                    _ => None,
                };
                match content {
                    Some(units) if units == s.units() => return Ok(Some(Value::Ref(r))),
                    Some(units) if units.is_empty() && name == "substring" => return Ok(Some(m.intern_units(&[]))),
                    Some(_) if name == "trim" => { m.trimmed.insert(made); }
                    _ => {}
                }
            }
            Ok(Some(value))
        }
        Native::StringBuilder(s) => string_builder_method(m, r, s, name, descriptor, &args),
        Native::Boxed { class, value } => boxed_method(m, r, &class, value, name, descriptor, &args).map(Some),
        Native::List { elements, mutable } => list_method(m, r, elements, mutable, name, descriptor, &args),
        Native::Set { elements, mutable } => set_method(m, r, elements, mutable, name, descriptor, &args),
        Native::Map { entries, mutable } => map_method(m, r, entries, mutable, name, descriptor, &args),
        Native::ArrayListSubList { root, offset, length, expected_mod_count, .. } => {
            if (name, descriptor) == ("subList", "(II)Ljava/util/List;") {
                return array_sublist(m, root, Some(r), offset, length, expected_mod_count, &args).map(Some);
            }
            let indexed = matches!((name, descriptor), ("get" | "remove", "(I)Ljava/lang/Object;") | ("set", "(ILjava/lang/Object;)Ljava/lang/Object;"));
            let mut actual = args;
            if indexed {
                let i = actual[0].as_int();
                if i < 0 || i as usize >= length { return Err(m.throw("java/lang/IndexOutOfBoundsException", Some(&index_message(i.into(), length)))); }
                actual[0] = Value::Int(offset as i32 + i);
            }
            if m.array_list_mod_count.get(&root) != Some(&expected_mod_count) { return Err(m.throw("java/util/ConcurrentModificationException", None)); }
            if indexed {
                let value = m.call_virtual(Value::Ref(root), "java/util/ArrayList", name, descriptor, actual)?;
                if name == "remove" {
                    let mut ancestor = Some(r);
                    while let Some(a) = ancestor {
                        if let Object::Native(Native::ArrayListSubList { parent, length, expected_mod_count, .. }) = m.heap.get_mut(a) {
                            *length -= 1;
                            *expected_mod_count = m.array_list_mod_count[&root];
                            ancestor = *parent;
                        } else { return unsupported("sublist without its parent view"); }
                    }
                }
                return Ok(value);
            }
            match (name, descriptor) {
                ("iterator", "()Ljava/util/Iterator;") => Ok(Some(Value::Ref(m.alloc_native(Native::ArrayListIterator {
                    list: r, view: true, cursor: 0, last: None, expected_mod_count,
                })))),
                ("size", "()I") => Ok(Some(Value::Int(length as i32))),
                ("isEmpty", "()Z") => Ok(Some(Value::bool(length == 0))),
                ("toArray", "()[Ljava/lang/Object;" | "([Ljava/lang/Object;)[Ljava/lang/Object;") => {
                    let elements = collection_elements(m, Value::Ref(r))?;
                    list_method(m, r, elements, false, name, descriptor, &actual)
                }
                _ => unsupported(format!("ArrayList sublist.{name}{descriptor}")),
            }
        }
        Native::ArrayListIterator { list, view, cursor, last, expected_mod_count } => {
            let (root, offset, length) = match m.heap.get(list) {
                Object::Native(Native::ArrayListSubList { root, offset, length, .. }) => (*root, *offset, *length),
                Object::Native(Native::List { elements, .. }) => (list, 0, elements.len()),
                _ => return unsupported("ArrayList iterator without a list"),
            };
            let Some(&current) = m.array_list_mod_count.get(&root) else { return unsupported("ArrayList iterator lost its list"); };
            let Object::Native(Native::List { elements, .. }) = m.heap.get(root) else { return unsupported("ArrayList iterator without list storage"); };
            match (name, descriptor) {
                ("hasNext", "()Z") => Ok(Some(Value::bool(cursor != length))),
                ("remove", "()V") if last.is_none() => Err(m.throw("java/lang/IllegalStateException", None)),
                ("next", "()Ljava/lang/Object;") | ("remove", "()V") if current != expected_mod_count =>
                    Err(m.throw("java/util/ConcurrentModificationException", None)),
                ("next", "()Ljava/lang/Object;") => {
                    let Some(&element) = elements.get(offset + cursor).filter(|_| cursor < length) else { return Err(m.throw("java/util/NoSuchElementException", None)); };
                    m.check_write(r, "an iterator cursor")?;
                    *m.heap.get_mut(r) = Object::Native(Native::ArrayListIterator { list, view, cursor: cursor + 1, last: Some(cursor), expected_mod_count });
                    Ok(Some(element))
                }
                ("remove", "()V") => {
                    m.check_write(r, "an iterator cursor")?;
                    let i = last.expect("remove checked the last returned index");
                    m.call_virtual(Value::Ref(list), "java/util/List", "remove", "(I)Ljava/lang/Object;", vec![Value::Int(i as i32)])?;
                    *m.heap.get_mut(r) = Object::Native(Native::ArrayListIterator { list, view, cursor: i, last: None, expected_mod_count: m.array_list_mod_count[&root] });
                    Ok(None)
                }
                _ => unsupported(format!("ArrayList iterator.{name}{descriptor}")),
            }
        }
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
            "cast" | "cannotCastMsg" => {
                let Some((cf, method)) = m.cp.library_image_method("java/lang/Class", name, descriptor) else {
                    return unsupported("Class.cast requires its selected JDK bytecode");
                };
                m.invoke(&cf, &method, vec![Value::Ref(r), args[0]])
            }
            "getTypeName" if matches!(t, Type::Array(_)) => Ok(Some(m.new_string(type_name(m, &t)))),
            "getName" | "getTypeName" => Ok(Some(m.intern(&class_name(m, &t)))),
            "getSimpleName" => {
                let simple = match &t {
                    Type::Object(n) => m.cp.application(n).ok().flatten().map(|c| c.simple_name()).unwrap_or_else(|| crate::classfile::simple_name_of(n)),
                    other => other.simple_name(),
                };
                Ok(Some(m.new_string(simple)))
            }
            "getCanonicalName" => Ok(Some(m.new_string(type_name(m, &t).replace('$', ".")))),
            "getComponentType" => Ok(Some(match &t { Type::Array(element) => m.class_object(element), _ => Value::Null })),
            "getClassLoader" if !t.is_reference() => Ok(Some(Value::Null)),
            "isAssignableFrom" => {
                let Some(r) = args[0].as_ref() else { return Err(m.npe()) };
                let Object::Native(Native::Class(sub)) = m.heap.get(r) else { return unsupported("isAssignableFrom needs a Class argument"); };
                let class_name = |ty: &Type| match ty { Type::Object(name) => name.clone(), _ => ty.descriptor() };
                let yes = sub == &t || (sub.is_reference() && t.is_reference() && m.cp.is_subtype(&class_name(sub), &class_name(&t)));
                Ok(Some(Value::bool(yes)))
            }
            // Null of `Object`, of an interface and of a primitive type, `Object` of an array, as the JVM has it.
            "getSuperclass" => {
                let above = match &t {
                    Type::Array(_) => Some("java/lang/Object".to_string()),
                    Type::Object(n) => {
                        let interface = matches!(m.cp.load(n), Ok(Some(l)) if l.class.is_interface());
                        if interface { None } else { m.cp.superclass(n) }
                    }
                    _ => None,
                };
                Ok(Some(match above {
                    Some(c) => m.class_object(&Type::Object(c)),
                    None => Value::Null,
                }))
            }
            "isInstance" => Ok(Some(Value::bool(match (args[0], &t) {
                (Value::Ref(o), Type::Object(n)) => m.is_instance(o, n),
                (Value::Ref(o), Type::Array(_)) => m.is_instance(o, &t.descriptor()),
                _ => false,
            }))),
            "isEnum" => Ok(Some(Value::bool(t.class_name().and_then(|n| m.cp.application(n).ok().flatten()).is_some_and(|c| c.is_enum())))),
            "isRecord" => Ok(Some(Value::bool(t.class_name().and_then(|n| m.cp.application(n).ok().flatten()).is_some_and(|c| c.is_record())))),
            "isInterface" => Ok(Some(Value::bool(t.class_name().and_then(|n| m.cp.application(n).ok().flatten()).is_some_and(|c| c.is_interface())))),
            "isPrimitive" => Ok(Some(Value::bool(!t.is_reference()))),
            "isArray" => Ok(Some(Value::bool(matches!(t, Type::Array(_))))),
            "desiredAssertionStatus" => Ok(Some(Value::Int(0))),
            _ => unsupported(format!("Class.{name}: reflection is outside the model")),
        },
        Native::Throwable { class, message, cause, .. } => match name {
            "getMessage" | "getLocalizedMessage" => Ok(Some(message.map(Value::Ref).unwrap_or(Value::Null))),
            "getCause" => Ok(Some(cause.map(Value::Ref).unwrap_or(Value::Null))),
            "initCause" => {
                set_throwable(m, r, None, args[0].as_ref(), false, true);
                Ok(Some(Value::Ref(r)))
            }
            "fillInStackTrace" => Ok(Some(Value::Ref(r))),
            "addSuppressed" | "getSuppressed" => invoke_suppression(m, r, name, descriptor, args),
            _ => unsupported(format!("{}.{name}", class.replace('/', "."))),
        },
        Native::Lambda { sam_name, sam_descriptor, implementation, captured, instantiated, interface, .. } => {
            if name == sam_name && sam_descriptor.as_deref().is_none_or(|d| d == descriptor) {
                call_lambda(m, &implementation, captured, &instantiated, descriptor, args)
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
        ("compareTo", "(Ljava/lang/String;)I" | "(Ljava/lang/Object;)I") => {
            if let Value::Ref(r) = args[0] {
                if m.heap.string(r).is_none() { return Err(m.throw("java/lang/ClassCastException", None)); }
            }
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
            let offset = args[1].as_int();
            if offset < 0 {
                if args[0] == Value::Null && !m.cp.prefix_checks_negative_first() {
                    return unsupported("String.startsWith(null, negative offset) on an unqualified JDK");
                }
                Value::bool(false)
            } else {
                let other = string_arg(m, args[0])?;
                Value::bool(units.get(offset as usize..).is_some_and(|tail| tail.starts_with(other.units())))
            }
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
        ("lastIndexOf", "(I)I" | "(II)I") => {
            let from = args.get(1).map(|v| v.as_int()).unwrap_or(i32::MAX);
            let at = code_point_units(args[0].as_int()).and_then(|needle| {
                let end = usize::try_from(from).ok()?.min(units.len().checked_sub(needle.len())?);
                (0..=end).rev().find(|&i| units[i..].starts_with(needle.units()))
            });
            Value::Int(at.map_or(-1, |index| index as i32))
        }
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

fn checked_code_point(m: &mut Machine, point: i32) -> Exec<JStr> {
    code_point_units(point).ok_or_else(|| m.throw("java/lang/IllegalArgumentException", Some(&format!("Not a valid Unicode code point: 0x{point:X}"))))
}

fn string_builder_method(m: &mut Machine, r: Ref, s: JStr, name: &str, descriptor: &str, args: &[Value]) -> Exec<Option<Value>> {
    let mut text = s;
    let result = match (name, descriptor) {
        ("appendCodePoint", "(I)Ljava/lang/StringBuilder;" | "(I)Ljava/lang/StringBuffer;") => {
            text.push(&checked_code_point(m, args[0].as_int())?);
            Some(Value::Ref(r))
        }
        ("append", "(Ljava/lang/CharSequence;II)Ljava/lang/StringBuilder;") => {
            let source = if args[0] == Value::Null { JStr::from("null") } else {
                m.units_of(args[0]).ok_or_else(|| Fault::Unsupported("append slice of an unqualified CharSequence".into()))?
            };
            let (begin,end) = (args[1].as_int(),args[2].as_int());
            if begin < 0 || begin > end || end as usize > source.len() {
                return Err(m.throw("java/lang/IndexOutOfBoundsException", Some(&format!("Range [{begin}, {end}) out of bounds for length {}",source.len()))));
            }
            for &unit in &source.units()[begin as usize..end as usize] { text.push_unit(unit); }
            Some(Value::Ref(r))
        }
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
        ("setCharAt", "(IC)V") => {
            let index = args[0].as_int();
            if index < 0 || index as usize >= text.len() {
                return Err(m.throw("java/lang/StringIndexOutOfBoundsException", None));
            }
            let mut units = text.into_units();
            units[index as usize] = args[1].as_int() as u16;
            text = JStr::from_units(units);
            None
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
        "floatValue" => super::convert(value, crate::classfile::Narrow::To(crate::classfile::Kind::Float)),
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

fn array_sublist(m: &mut Machine, root: Ref, parent: Option<Ref>, offset: usize, length: usize, expected_mod_count: i32, args: &[Value]) -> Exec<Value> {
    let (from, to) = (args[0].as_int(), args[1].as_int());
    if from < 0 { return Err(m.throw("java/lang/IndexOutOfBoundsException", Some(&format!("fromIndex = {from}")))); }
    if i64::from(to) > length as i64 { return Err(m.throw("java/lang/IndexOutOfBoundsException", Some(&format!("toIndex = {to}")))); }
    if from > to { return Err(m.throw("java/lang/IllegalArgumentException", Some(&format!("fromIndex({from}) > toIndex({to})")))); }
    Ok(Value::Ref(m.alloc_native(Native::ArrayListSubList { root, parent, offset: offset + from as usize, length: (to - from) as usize, expected_mod_count })))
}

fn list_method(m: &mut Machine, r: Ref, mut elements: Vec<Value>, mutable: bool, name: &str, descriptor: &str, args: &[Value]) -> Exec<Option<Value>> {
    let len = elements.len();
    let made = m.immutable_list_kind(r);
    let out_of_bounds = |m: &mut Machine, i: i32| m.throw("java/lang/IndexOutOfBoundsException", Some(&index_message(i.into(), len)));
    // A list List.of or copyOf made holds no null, and its searches refuse one, as the JDK's do.
    if made.is_some() && matches!(name, "contains" | "indexOf" | "lastIndexOf") && args.first() == Some(&Value::Null) {
        return Err(m.npe());
    }
    if let Some(kind) = made {
        if matches!(name, "contains" | "indexOf" | "lastIndexOf") {
            let query = args[0];
            let mut found = -1;
            for step in 0..len {
                let i = if name == "lastIndexOf" { len - 1 - step } else { step };
                // ListN uses Objects.equals(query, element). List12 calls query.equals
                // even on the identical reference, so an observable override still runs.
                let same = if matches!(kind, crate::interp::ImmutableList::ListN) && query == elements[i] {
                    true
                } else {
                    m.call_virtual(query, "java/lang/Object", "equals", "(Ljava/lang/Object;)Z", vec![elements[i]])?
                        .expect("equals returns boolean").as_int() != 0
                };
                if same { found = i as i32; break; }
            }
            return Ok(Some(if name == "contains" { Value::bool(found >= 0) } else { Value::Int(found) }));
        }
    }
    let write = |m: &mut Machine| -> Exec<()> {
        if !mutable {
            return Err(immutable(m));
        }
        m.check_write(r, "a List")
    };
    let store = |m: &mut Machine, elements, structural: bool| {
        if structural {
            if let Some(count) = m.array_list_mod_count.get_mut(&r) { *count = count.wrapping_add(1); }
        }
        *m.heap.get_mut(r) = Object::Native(Native::List { elements, mutable });
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
        ("iterator", _) => {
            let iterator = match m.array_list_mod_count.get(&r) {
                Some(&expected_mod_count) => Native::ArrayListIterator { list: r, view: false, cursor: 0, last: None, expected_mod_count },
                None => Native::Iterator { elements, position: 0, immutable: !mutable },
            };
            Some(Value::Ref(m.alloc_native(iterator)))
        }
        ("forEach", "(Ljava/util/function/Consumer;)V") if m.array_list_mod_count.contains_key(&r) => {
            if args[0] == Value::Null { return Err(m.npe()); }
            let version = m.array_list_mod_count[&r];
            for index in 0..len {
                let Object::Native(Native::List { elements: live, .. }) = m.heap.get(r) else { return unsupported("ArrayList.forEach receiver lost its storage") };
                let Some(&element) = live.get(index) else { return unsupported("ArrayList.forEach lost an element without a structural change") };
                m.call_virtual(args[0], "java/util/function/Consumer", "accept", "(Ljava/lang/Object;)V", vec![element])?;
                if m.array_list_mod_count.get(&r) != Some(&version) { return Err(m.throw("java/util/ConcurrentModificationException", None)); }
            }
            None
        }
        ("forEach", _) => {
            for e in elements {
                m.call_virtual(args[0], "java/util/function/Consumer", "accept", "(Ljava/lang/Object;)V", vec![e])?;
            }
            None
        }
        ("toArray", "()[Ljava/lang/Object;") => Some(m.new_array_of(Type::object("java/lang/Object"), elements)),
        ("toArray", "([Ljava/lang/Object;)[Ljava/lang/Object;") => {
            let Some(target) = args[0].as_ref() else { return Err(m.npe()) };
            let Object::Array { element, data } = m.heap.get(target) else { return unsupported("List.toArray requires an array") };
            let capacity = data.len();
            let destination = if capacity < len { m.new_array(element.clone(), len as i32)? } else { args[0] };
            let source = m.new_array_of(Type::object("java/lang/Object"), elements);
            invoke_static_jdk(m, "java/lang/System", "arraycopy", "(Ljava/lang/Object;ILjava/lang/Object;II)V",
                vec![source, Value::Int(0), destination, Value::Int(0), Value::Int(len as i32)])?;
            if capacity > len {
                m.check_write(target, "an array element")?;
                if let Object::Array { data, .. } = m.heap.get_mut(target) { data[len] = Value::Null; }
            }
            Some(destination)
        }
        ("subList", _) => {
            if let Some(&count) = m.array_list_mod_count.get(&r) {
                return array_sublist(m, r, None, 0, len, count, args).map(Some);
            }
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
            store(m, elements, true);
            Some(Value::Int(1))
        }
        ("add", "(ILjava/lang/Object;)V") => {
            write(m)?;
            let i = args[0].as_int();
            if i < 0 || i as usize > len {
                return Err(out_of_bounds(m, i));
            }
            elements.insert(i as usize, args[1]);
            store(m, elements, true);
            None
        }
        ("addAll", "(Ljava/util/Collection;)Z") if m.array_list_mod_count.contains_key(&r) => {
            // The source's virtual toArray can throw, return a typed array, or mutate this list.
            // ArrayList increments modCount after the callback, even for an empty or null result.
            let array = m.call_virtual(args[0], "java/util/Collection", "toArray", "()[Ljava/lang/Object;", Vec::new())?;
            write(m)?;
            let count = m.array_list_mod_count.get_mut(&r).expect("an exact ArrayList");
            *count = count.wrapping_add(1);
            let Some(array) = array.and_then(Value::as_ref) else { return Err(m.npe()) };
            let Object::Array { data, .. } = m.heap.get(array) else { return unsupported("Collection.toArray returned a non-array") };
            let snapshot = data.clone();
            let changed = !snapshot.is_empty();
            let Object::Native(Native::List { elements, .. }) = m.heap.get_mut(r) else { return unsupported("ArrayList lost its backing elements") };
            elements.extend(snapshot);
            Some(Value::bool(changed))
        }
        ("addAll", "(Ljava/util/Collection;)Z") => {
            write(m)?;
            let others = collection_elements(m, args[0])?;
            let changed = !others.is_empty();
            elements.extend(others);
            store(m, elements, true);
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
            store(m, elements, false);
            Some(old)
        }
        ("remove", "(I)Ljava/lang/Object;") => {
            write(m)?;
            let i = args[0].as_int();
            if i < 0 || i as usize >= len {
                return Err(out_of_bounds(m, i));
            }
            let old = elements.remove(i as usize);
            store(m, elements, true);
            Some(old)
        }
        ("remove", "(Ljava/lang/Object;)Z") => {
            write(m)?;
            let i = index_of(m, &elements, args[0])?;
            if i >= 0 {
                elements.remove(i as usize);
            }
            store(m, elements, i >= 0);
            Some(Value::bool(i >= 0))
        }
        ("clear", _) => {
            write(m)?;
            store(m, Vec::new(), true);
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

/// Check a reference cast at the adapter, before the implementation is invoked.
fn lambda_cast(m: &mut Machine, value: Value, to: &Type) -> Exec<Value> {
    match value {
        Value::Null => Ok(value),
        Value::Ref(r) => {
            let name = match to { Type::Object(c) => c.clone(), Type::Array(_) => to.descriptor(),
                _ => return unsupported("reference adapter without a reference descriptor") };
            if m.is_instance(r, &name) { Ok(value) } else { Err(m.throw("java/lang/ClassCastException", None)) }
        }
        _ => unsupported("a primitive in a reference adapter slot"),
    }
}

fn widen_lambda_value(value: Value, from: &Type, to: &Type) -> Exec<Value> {
    use crate::classfile::{Kind, Narrow};
    let compatible = matches!((value, from),
        (Value::Int(_), Type::Boolean | Type::Byte | Type::Short | Type::Char | Type::Int)
        | (Value::Long(_), Type::Long) | (Value::Float(_), Type::Float) | (Value::Double(_), Type::Double));
    if !compatible || !from.widens_to(to) {
        return unsupported(format!("lambda conversion from {} to {}", from.java_name(), to.java_name()));
    }
    Ok(match to {
        Type::Long => super::convert(value, Narrow::To(Kind::Long)),
        Type::Float => super::convert(value, Narrow::To(Kind::Float)),
        Type::Double => super::convert(value, Narrow::To(Kind::Double)),
        _ => value, // byte, short, char and int occupy an int on the operand stack.
    })
}

fn adapt_lambda_value(m: &mut Machine, value: Value, from: &Type, to: &Type) -> Exec<Value> {
    if from.is_primitive() {
        if to.is_primitive() { return widen_lambda_value(value, from, to); }
        let box_type = to.class_name().and_then(Type::for_wrapper).unwrap_or_else(|| from.clone());
        let primitive = widen_lambda_value(value, from, &box_type)?;
        let class = box_class_of(&box_type).ok_or_else(|| Fault::Unsupported("boxing void".into()))?;
        let boxed = box_value(m, class, primitive);
        return lambda_cast(m, boxed, to);
    }
    let value = lambda_cast(m, value, from)?;
    if to.is_reference() { return lambda_cast(m, value, to); }
    let Some(r) = value.as_ref() else { return Err(m.npe()); };
    // A wrapper-typed argument unboxes that exact wrapper, then widens. A
    // reference-typed result may require virtual Number.xxxValue on a subclass.
    if let Some(source) = from.class_name().and_then(Type::for_wrapper) {
        return widen_lambda_value(unbox(m, value)?, &source, to);
    }
    let (owner, method) = match to {
        Type::Byte => ("java/lang/Number", "byteValue"), Type::Short => ("java/lang/Number", "shortValue"),
        Type::Int => ("java/lang/Number", "intValue"), Type::Long => ("java/lang/Number", "longValue"),
        Type::Float => ("java/lang/Number", "floatValue"), Type::Double => ("java/lang/Number", "doubleValue"),
        Type::Char => ("java/lang/Character", "charValue"), Type::Boolean => ("java/lang/Boolean", "booleanValue"),
        _ => return unsupported("invalid lambda unboxing destination"),
    };
    if !m.is_instance(r, owner) { return Err(m.throw("java/lang/ClassCastException", None)); }
    m.call_virtual(value, owner, method, &format!("(){}", to.descriptor()), Vec::new())?
        .ok_or_else(|| Fault::Unsupported("unboxing returned void".into()))
}

fn call_lambda(m: &mut Machine, handle: &MethodHandle, mut full: Vec<Value>, instantiated: &str, called: &str, args: Vec<Value>) -> Exec<Option<Value>> {
    let parse = |d: &str| MethodDescriptor::parse(d).map_err(|e| Fault::Unsupported(e.to_string()));
    let target = parse(&handle.member.descriptor)?;
    let instantiated = parse(instantiated)?;
    let called = parse(called)?;
    let owner = &handle.member.owner;
    let name = &handle.member.name;
    let descriptor = &handle.member.descriptor;
    let mut takes = target.params;
    if matches!(handle.kind, 5 | 7 | 9) { takes.insert(0, Type::object(owner)); }
    if args.len() != instantiated.params.len() || args.len() + full.len() != takes.len() {
        return unsupported("a lambda called through an incompatible argument descriptor");
    }
    let captured = full.len();
    for ((arg, src), dst) in args.into_iter().zip(&instantiated.params).zip(&takes[captured..]) {
        full.push(adapt_lambda_value(m, arg, src, dst)?);
    }
    let result = match handle.kind {
        6 if m.cp.is_application(owner) => m.call_static(owner, name, descriptor, full)?,
        6 => invoke_static_jdk(m, owner, name, descriptor, full)?,
        5 | 7 | 9 => {
            let receiver = full.remove(0);
            if handle.kind == 7 && m.cp.is_application(owner) {
                let (cf, method) = m.cp.find_method(owner, name, descriptor)
                    .ok_or_else(|| Fault::Unsupported(format!("method not found: {owner}.{name}")))?;
                full.insert(0, receiver);
                m.invoke(&cf, &method, full)?
            } else {
                m.call_virtual(receiver, owner, name, descriptor, full)?
            }
        }
        8 if m.cp.is_application(owner) => Some(m.construct(owner, descriptor, full)?),
        8 => {
            let object = new_jdk_object(m, owner)?;
            invoke_special_jdk(m, object.as_ref().expect("allocated"), owner, "<init>", descriptor, full)?;
            Some(object)
        }
        other => return unsupported(format!("method handle kind {other}")),
    };
    if called.ret == Type::Void { return Ok(None); }
    let returned = if handle.kind == 8 { Type::object(owner) } else { target.ret };
    let value = result.ok_or_else(|| Fault::Unsupported("lambda implementation returned void for a value call".into()))?;
    let adapted = adapt_lambda_value(m, value, &returned, &instantiated.ret)?;
    adapt_lambda_value(m, adapted, &instantiated.ret, &called.ret).map(Some)
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
            let sam_descriptor = match (method, bootstrap.args.first()) {
                ("metafactory", Some(BootstrapArg::MethodType(d))) => Some(d.clone()),
                _ => None,
            };
            let serializable = method == "altMetafactory" && matches!(bootstrap.args.get(3), Some(BootstrapArg::Int(flags)) if flags & 1 != 0);
            let lambda = Native::Lambda { interface, serializable, sam_name: name.to_string(), sam_descriptor, implementation, captured: args, instantiated };
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
        "java/lang/reflect/Array" if (name, descriptor) == ("getLength", "(Ljava/lang/Object;)I") => {
            let Some(r) = a[0].as_ref() else { return Err(m.npe()) };
            match m.heap.get(r) {
                Object::Array { data, .. } => Value::Int(data.len() as i32),
                _ => return Err(m.throw("java/lang/IllegalArgumentException", Some("Argument is not an array"))),
            }
        }
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
        // Recognize the same constant grammar as strict checking. Methods that need
        // the matcher's state still require their own implementation.
        "java/util/regex/Pattern" => match (name, descriptor) {
            ("compile", "(Ljava/lang/String;)Ljava/util/regex/Pattern;") => {
                if a[0] == Value::Null {
                    return Err(m.npe());
                }
                let regex = char_sequence(m, a[0])?;
                if !crate::jdk_facts::plain_regex(regex.units()) && !crate::bmc::compiles_constant(regex.units()) {
                    return unsupported("Pattern.compile outside the supported constant grammar");
                }
                Value::Ref(m.alloc(Object::Instance { class: owner.into(), fields: Default::default(), base: Base::Object }))
            }
            _ => return unsupported(format!("Pattern.{name}{descriptor}")),
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
                let (source_type, source_len) = match m.heap.get(src) {
                    Object::Array { element, data } => (element.clone(), data.len()),
                    _ => return Err(m.throw("java/lang/ArrayStoreException", Some("arraycopy: source type is not an array"))),
                };
                let (dest_type, dest_len) = match m.heap.get(dst) {
                    Object::Array { element, data } => (element.clone(), data.len()),
                    _ => return Err(m.throw("java/lang/ArrayStoreException", Some("arraycopy: destination type is not an array"))),
                };
                if source_type != dest_type && !(source_type.is_reference() && dest_type.is_reference()) {
                    return Err(m.throw("java/lang/ArrayStoreException", None));
                }
                if src_pos < 0 || dst_pos < 0 || length < 0 || i64::from(src_pos) + i64::from(length) > source_len as i64
                    || i64::from(dst_pos) + i64::from(length) > dest_len as i64 {
                    return Err(m.throw("java/lang/ArrayIndexOutOfBoundsException", Some("arraycopy: last source index out of bounds")));
                }
                let Object::Array { data, .. } = m.heap.get(src) else { unreachable!() };
                let slice = data[src_pos as usize..src_pos as usize + length as usize].to_vec();
                let dest_class = match &dest_type { Type::Object(name) => name.clone(), other => other.descriptor() };
                let copied = if source_type == dest_type { slice.len() } else {
                    slice.iter().position(|v| v.as_ref().is_some_and(|r| !m.is_instance(r, &dest_class))).unwrap_or(slice.len())
                };
                if copied != 0 { m.check_write(dst, "an array element")?; }
                if let Object::Array { data, .. } = m.heap.get_mut(dst) {
                    data[dst_pos as usize..dst_pos as usize + copied].copy_from_slice(&slice[..copied]);
                }
                if copied != slice.len() {
                    return Err(m.throw("java/lang/ArrayStoreException", None));
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
        "toChars" if descriptor == "(I)[C" => {
            let units = checked_code_point(m, a[0].as_int())?;
            m.new_array_of(Type::Char, units.units().iter().map(|u| Value::Int(i32::from(*u))).collect())
        }
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
        "valueOf" | "parseFloat" | "parseDouble" if descriptor.starts_with("(Ljava/lang/String;") => {
            let Some(units) = m.units_of(a[0]) else { return Err(m.throw("java/lang/NullPointerException", None)) };
            let raw = units.units();
            let Some(first) = raw.iter().position(|u| *u > 32) else { return Err(m.throw("java/lang/NumberFormatException", Some("empty String"))); };
            let last = raw.iter().rposition(|u| *u > 32).unwrap();
            let units = JStr::from_units(raw[first..=last].to_vec());
            let value = match units.text() {
                Some(text) => {
                    let unsigned = text.strip_prefix(['+', '-']).unwrap_or(&text);
                    match unsigned {
                        "NaN" => wrap(f64::NAN),
                        "Infinity" => wrap(if text.starts_with('-') { f64::NEG_INFINITY } else { f64::INFINITY }),
                        _ if unsigned.starts_with("0x") || unsigned.starts_with("0X") => return unsupported("hexadecimal floating-point text"),
                        _ if unsigned.bytes().take_while(|b| b.is_ascii_digit() || *b == b'.').filter(|b| *b == b'.').count() > 1 =>
                            return Err(m.throw("java/lang/NumberFormatException", Some("multiple points"))),
                        _ => super::value::decimal_float(&text, is_double).ok_or_else(|| number_format(m, Some(&units), 10))?,
                    }
                }
                None => return Err(number_format(m, Some(&units), 10)),
            };
            if name == "valueOf" { box_value(m, owner, value) } else { value }
        }
        "valueOf" => box_value(m, owner, a[0]),
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
