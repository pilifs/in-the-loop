//! The annotations kept in class files (JVMS 4.7.16 to 4.7.19): `RuntimeVisibleAnnotations` on classes, fields and
//! methods, and `RuntimeVisibleParameterAnnotations`. A framework that acts on annotations at run time (Spring,
//! Jakarta Validation, Resilience4j, Micrometer) declares them with `RUNTIME` retention, so they are all in the
//! visible attributes; the invisible ones (`CLASS` retention) are compile-time facts and are not read. The type
//! annotations (`RuntimeVisibleTypeAnnotations`, JVMS 4.7.20) are read for fields and methods: a constraint on a
//! type argument (`List<@NotBlank String>`) is only there.

use super::{Constant, ConstantPool, ParseError, Result};

/// `@Type(name = value, ...)`, with the type as an internal name (`org/springframework/stereotype/Service`).
#[derive(Debug, Clone, PartialEq)]
pub struct Annotation {
    pub type_name: String,
    pub elements: Vec<(String, ElementValue)>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ElementValue {
    Int(i64),
    Boolean(bool),
    Char(char),
    Float(f64),
    String(String),
    /// An enum constant: the enum's internal name and the constant's name.
    Enum(String, String),
    /// A class literal, as a field descriptor (`Ljava/io/IOException;`, `V`).
    Class(String),
    Annotation(Annotation),
    Array(Vec<ElementValue>),
}

/// Where a type annotation sits (JVMS 4.7.20.1): on a field's type, a method's return type, a parameter's type,
/// or somewhere else (a type parameter, a supertype, a `throws` clause, a local variable, a cast).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TypeTarget {
    Field,
    Return,
    Parameter(u8),
    Other(u8),
}

/// An annotation on a type, with the path (JVMS 4.7.20.2) from the target's type to the annotated part: empty for
/// the type itself, `(3, i)` into the i-th type argument, `(0, 0)` into an array's component, `(2, 0)` into a
/// wildcard's bound, `(1, 0)` into an inner class.
#[derive(Debug, Clone, PartialEq)]
pub struct TypeAnnotation {
    pub target: TypeTarget,
    pub path: Vec<(u8, u8)>,
    pub annotation: Annotation,
}

impl Annotation {
    /// The element of this name, if given.
    pub fn element(&self, name: &str) -> Option<&ElementValue> {
        self.elements.iter().find(|(n, _)| n == name).map(|(_, v)| v)
    }

    /// The simple name of the annotation type, as written in source (`Service`, `Transactional`).
    pub fn simple_name(&self) -> String {
        super::simple_name_of(&self.type_name)
    }

    /// The dotted name of the annotation type.
    pub fn java_name(&self) -> String {
        self.type_name.replace('/', ".")
    }

    /// The element as a list of strings: a string, an array of strings, or nothing. `@GetMapping("/a")` and
    /// `@RequestMapping(path = {"/a", "/b"})` both read as their strings.
    pub fn strings(&self, name: &str) -> Vec<String> {
        match self.element(name) {
            Some(v) => v.strings(),
            None => Vec::new(),
        }
    }

    /// The element as class names (internal names) when it is a class or an array of classes.
    pub fn classes(&self, name: &str) -> Vec<String> {
        match self.element(name) {
            Some(v) => v.classes(),
            None => Vec::new(),
        }
    }

    /// The element as enum constant names.
    pub fn enum_names(&self, name: &str) -> Vec<String> {
        match self.element(name) {
            Some(v) => v.enum_names(),
            None => Vec::new(),
        }
    }

    /// The annotation as it is written in source: `@Transactional(readOnly = true)`, `@GetMapping("/{id}")`. A
    /// lone `value` element is written without its name, and a one-element array without braces, as Java allows.
    pub fn render(&self) -> String {
        let mut s = format!("@{}", self.simple_name());
        if self.elements.is_empty() {
            return s;
        }
        s.push('(');
        if self.elements.len() == 1 && self.elements[0].0 == "value" {
            s.push_str(&self.elements[0].1.render());
        } else {
            let parts: Vec<String> = self.elements.iter().map(|(n, v)| format!("{n} = {}", v.render())).collect();
            s.push_str(&parts.join(", "));
        }
        s.push(')');
        s
    }
}

impl ElementValue {
    pub fn strings(&self) -> Vec<String> {
        match self {
            ElementValue::String(s) => vec![s.clone()],
            ElementValue::Array(items) => items.iter().flat_map(ElementValue::strings).collect(),
            _ => Vec::new(),
        }
    }

    pub fn classes(&self) -> Vec<String> {
        match self {
            ElementValue::Class(d) => d.strip_prefix('L').and_then(|d| d.strip_suffix(';')).map(|c| vec![c.to_string()]).unwrap_or_default(),
            ElementValue::Array(items) => items.iter().flat_map(ElementValue::classes).collect(),
            _ => Vec::new(),
        }
    }

    pub fn enum_names(&self) -> Vec<String> {
        match self {
            ElementValue::Enum(_, n) => vec![n.clone()],
            ElementValue::Array(items) => items.iter().flat_map(ElementValue::enum_names).collect(),
            _ => Vec::new(),
        }
    }

    pub fn render(&self) -> String {
        match self {
            ElementValue::Int(i) => i.to_string(),
            ElementValue::Boolean(b) => b.to_string(),
            ElementValue::Char(c) => format!("{:?}", c),
            ElementValue::Float(f) => f.to_string(),
            ElementValue::String(s) => format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\"")),
            ElementValue::Enum(t, n) => format!("{}.{n}", super::simple_name_of(t)),
            ElementValue::Class(d) => match super::Type::parse(d) {
                Ok(t) => format!("{}.class", t.java_name()),
                Err(_) => format!("{d}.class"),
            },
            ElementValue::Annotation(a) => a.render(),
            ElementValue::Array(items) if items.len() == 1 => items[0].render(),
            ElementValue::Array(items) => format!("{{{}}}", items.iter().map(ElementValue::render).collect::<Vec<_>>().join(", ")),
        }
    }
}

struct Reader<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl Reader<'_> {
    fn u8(&mut self) -> Result<u8> {
        let b = *self.bytes.get(self.pos).ok_or_else(|| ParseError("annotation attribute ends early".into()))?;
        self.pos += 1;
        Ok(b)
    }

    fn u16(&mut self) -> Result<u16> {
        Ok(u16::from_be_bytes([self.u8()?, self.u8()?]))
    }
}

fn read_annotation(r: &mut Reader, pool: &ConstantPool) -> Result<Annotation> {
    let type_descriptor = pool.utf8(r.u16()?)?;
    let type_name = type_descriptor.strip_prefix('L').and_then(|d| d.strip_suffix(';')).unwrap_or(type_descriptor).to_string();
    let count = r.u16()?;
    let mut elements = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let name = pool.utf8(r.u16()?)?.to_string();
        let value = read_value(r, pool)?;
        elements.push((name, value));
    }
    Ok(Annotation { type_name, elements })
}

fn read_value(r: &mut Reader, pool: &ConstantPool) -> Result<ElementValue> {
    let tag = r.u8()?;
    Ok(match tag {
        b'B' | b'S' | b'I' => match pool.get(r.u16()?)? {
            Constant::Integer(i) => ElementValue::Int(*i as i64),
            other => return Err(ParseError(format!("annotation element: expected an integer, found {other:?}"))),
        },
        b'C' => match pool.get(r.u16()?)? {
            Constant::Integer(i) => ElementValue::Char(char::from_u32(*i as u32).unwrap_or('\u{fffd}')),
            other => return Err(ParseError(format!("annotation element: expected a char, found {other:?}"))),
        },
        b'Z' => match pool.get(r.u16()?)? {
            Constant::Integer(i) => ElementValue::Boolean(*i != 0),
            other => return Err(ParseError(format!("annotation element: expected a boolean, found {other:?}"))),
        },
        b'J' => match pool.get(r.u16()?)? {
            Constant::Long(l) => ElementValue::Int(*l),
            other => return Err(ParseError(format!("annotation element: expected a long, found {other:?}"))),
        },
        b'F' => match pool.get(r.u16()?)? {
            Constant::Float(f) => ElementValue::Float(*f as f64),
            other => return Err(ParseError(format!("annotation element: expected a float, found {other:?}"))),
        },
        b'D' => match pool.get(r.u16()?)? {
            Constant::Double(d) => ElementValue::Float(*d),
            other => return Err(ParseError(format!("annotation element: expected a double, found {other:?}"))),
        },
        b's' => ElementValue::String(pool.utf8(r.u16()?)?.to_string()),
        b'e' => {
            let type_descriptor = pool.utf8(r.u16()?)?;
            let type_name = type_descriptor.strip_prefix('L').and_then(|d| d.strip_suffix(';')).unwrap_or(type_descriptor).to_string();
            let name = pool.utf8(r.u16()?)?.to_string();
            ElementValue::Enum(type_name, name)
        }
        b'c' => ElementValue::Class(pool.utf8(r.u16()?)?.to_string()),
        b'@' => ElementValue::Annotation(read_annotation(r, pool)?),
        b'[' => {
            let count = r.u16()?;
            let mut items = Vec::with_capacity(count as usize);
            for _ in 0..count {
                items.push(read_value(r, pool)?);
            }
            ElementValue::Array(items)
        }
        other => return Err(ParseError(format!("annotation element: unknown tag {other:?}"))),
    })
}

/// Parses a `RuntimeVisibleAnnotations` (or `RuntimeInvisibleAnnotations`) attribute.
pub fn parse_annotations(data: &[u8], pool: &ConstantPool) -> Result<Vec<Annotation>> {
    let mut r = Reader { bytes: data, pos: 0 };
    let count = r.u16()?;
    let mut out = Vec::with_capacity(count as usize);
    for _ in 0..count {
        out.push(read_annotation(&mut r, pool)?);
    }
    Ok(out)
}

/// Parses a `RuntimeVisibleTypeAnnotations` attribute.
pub fn parse_type_annotations(data: &[u8], pool: &ConstantPool) -> Result<Vec<TypeAnnotation>> {
    let mut r = Reader { bytes: data, pos: 0 };
    let count = r.u16()?;
    let mut out = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let target_type = r.u8()?;
        let target = match target_type {
            0x00 | 0x01 => {
                r.u8()?;
                TypeTarget::Other(target_type)
            }
            0x10 => {
                r.u16()?;
                TypeTarget::Other(target_type)
            }
            0x11 | 0x12 => {
                r.u8()?;
                r.u8()?;
                TypeTarget::Other(target_type)
            }
            0x13 => TypeTarget::Field,
            0x14 => TypeTarget::Return,
            0x15 => TypeTarget::Other(target_type),
            0x16 => TypeTarget::Parameter(r.u8()?),
            0x17 => {
                r.u16()?;
                TypeTarget::Other(target_type)
            }
            0x40 | 0x41 => {
                let entries = r.u16()?;
                for _ in 0..entries {
                    r.u16()?;
                    r.u16()?;
                    r.u16()?;
                }
                TypeTarget::Other(target_type)
            }
            0x42..=0x46 => {
                r.u16()?;
                TypeTarget::Other(target_type)
            }
            0x47..=0x4B => {
                r.u16()?;
                r.u8()?;
                TypeTarget::Other(target_type)
            }
            other => return Err(ParseError(format!("type annotation: unknown target type {other:#x}"))),
        };
        let steps = r.u8()?;
        let mut path = Vec::with_capacity(steps as usize);
        for _ in 0..steps {
            path.push((r.u8()?, r.u8()?));
        }
        out.push(TypeAnnotation { target, path, annotation: read_annotation(&mut r, pool)? });
    }
    Ok(out)
}

/// Parses a `RuntimeVisibleParameterAnnotations` attribute: one list per parameter the compiler counted.
pub fn parse_parameter_annotations(data: &[u8], pool: &ConstantPool) -> Result<Vec<Vec<Annotation>>> {
    let mut r = Reader { bytes: data, pos: 0 };
    let params = r.u8()?;
    let mut out = Vec::with_capacity(params as usize);
    for _ in 0..params {
        let count = r.u16()?;
        let mut list = Vec::with_capacity(count as usize);
        for _ in 0..count {
            list.push(read_annotation(&mut r, pool)?);
        }
        out.push(list);
    }
    Ok(out)
}
