//! Field and method descriptors (JVMS 4.3).

use std::fmt;

use super::{err, Result};

/// A JVM type, as written in a descriptor.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Type {
    Boolean,
    Byte,
    Char,
    Short,
    Int,
    Long,
    Float,
    Double,
    Void,
    /// A class or interface, by internal name (`java/lang/String`).
    Object(String),
    Array(Box<Type>),
}

impl Type {
    /// Parses one field descriptor, such as `I` or `Ljava/lang/String;` or `[[J`.
    pub fn parse(descriptor: &str) -> Result<Type> {
        let mut chars = descriptor.chars().peekable();
        let t = parse_type(&mut chars, descriptor)?;
        if chars.next().is_some() {
            return err(format!("trailing characters in descriptor {descriptor:?}"));
        }
        Ok(t)
    }

    pub fn object(internal_name: &str) -> Type {
        Type::Object(internal_name.to_string())
    }

    pub fn is_primitive(&self) -> bool {
        !matches!(self, Type::Object(_) | Type::Array(_) | Type::Void)
    }

    pub fn is_reference(&self) -> bool {
        matches!(self, Type::Object(_) | Type::Array(_))
    }

    /// The number of local-variable or stack slots the type takes: two for `long` and `double`.
    pub fn slots(&self) -> u16 {
        match self {
            Type::Long | Type::Double => 2,
            Type::Void => 0,
            _ => 1,
        }
    }

    /// The internal name of a class type, if this is one.
    pub fn class_name(&self) -> Option<&str> {
        match self {
            Type::Object(name) => Some(name),
            _ => None,
        }
    }

    /// The descriptor string.
    pub fn descriptor(&self) -> String {
        let mut s = String::new();
        self.write_descriptor(&mut s);
        s
    }

    fn write_descriptor(&self, out: &mut String) {
        match self {
            Type::Boolean => out.push('Z'),
            Type::Byte => out.push('B'),
            Type::Char => out.push('C'),
            Type::Short => out.push('S'),
            Type::Int => out.push('I'),
            Type::Long => out.push('J'),
            Type::Float => out.push('F'),
            Type::Double => out.push('D'),
            Type::Void => out.push('V'),
            Type::Object(name) => {
                out.push('L');
                out.push_str(name);
                out.push(';');
            }
            Type::Array(inner) => {
                out.push('[');
                inner.write_descriptor(out);
            }
        }
    }

    /// The Java source spelling: `int`, `java.lang.String`, `long[]`.
    pub fn java_name(&self) -> String {
        match self {
            Type::Boolean => "boolean".into(),
            Type::Byte => "byte".into(),
            Type::Char => "char".into(),
            Type::Short => "short".into(),
            Type::Int => "int".into(),
            Type::Long => "long".into(),
            Type::Float => "float".into(),
            Type::Double => "double".into(),
            Type::Void => "void".into(),
            Type::Object(name) => name.replace('/', "."),
            Type::Array(inner) => format!("{}[]", inner.java_name()),
        }
    }

    /// The simple Java name: `int`, `String`, `Transition` (by the last `/` and `$`).
    pub fn simple_name(&self) -> String {
        match self {
            Type::Object(name) => super::simple_name_of(name),
            Type::Array(inner) => format!("{}[]", inner.simple_name()),
            other => other.java_name(),
        }
    }

    /// The name `Class.getName()` gives: `[J` for `long[]`, `java.lang.String`, `int`.
    pub fn class_get_name(&self) -> String {
        match self {
            Type::Object(name) => name.replace('/', "."),
            Type::Array(_) => self.descriptor().replace('/', "."),
            other => other.java_name(),
        }
    }
}

impl fmt::Display for Type {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.java_name())
    }
}

fn parse_type(chars: &mut std::iter::Peekable<std::str::Chars>, whole: &str) -> Result<Type> {
    match chars.next() {
        Some('Z') => Ok(Type::Boolean),
        Some('B') => Ok(Type::Byte),
        Some('C') => Ok(Type::Char),
        Some('S') => Ok(Type::Short),
        Some('I') => Ok(Type::Int),
        Some('J') => Ok(Type::Long),
        Some('F') => Ok(Type::Float),
        Some('D') => Ok(Type::Double),
        Some('V') => Ok(Type::Void),
        Some('L') => {
            let mut name = String::new();
            loop {
                match chars.next() {
                    Some(';') => break,
                    Some(c) => name.push(c),
                    None => return err(format!("unterminated class name in descriptor {whole:?}")),
                }
            }
            Ok(Type::Object(name))
        }
        Some('[') => Ok(Type::Array(Box::new(parse_type(chars, whole)?))),
        other => err(format!("unexpected {other:?} in descriptor {whole:?}")),
    }
}

/// A method descriptor: parameter types and return type.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct MethodDescriptor {
    pub params: Vec<Type>,
    pub ret: Type,
}

impl MethodDescriptor {
    pub fn parse(descriptor: &str) -> Result<MethodDescriptor> {
        let mut chars = descriptor.chars().peekable();
        if chars.next() != Some('(') {
            return err(format!("method descriptor {descriptor:?} does not start with ("));
        }
        let mut params = Vec::new();
        while chars.peek() != Some(&')') {
            if chars.peek().is_none() {
                return err(format!("unterminated parameter list in {descriptor:?}"));
            }
            params.push(parse_type(&mut chars, descriptor)?);
        }
        chars.next();
        let ret = parse_type(&mut chars, descriptor)?;
        if chars.next().is_some() {
            return err(format!("trailing characters in method descriptor {descriptor:?}"));
        }
        Ok(MethodDescriptor { params, ret })
    }

    pub fn new(params: Vec<Type>, ret: Type) -> MethodDescriptor {
        MethodDescriptor { params, ret }
    }

    pub fn descriptor(&self) -> String {
        let mut s = String::from("(");
        for p in &self.params {
            s.push_str(&p.descriptor());
        }
        s.push(')');
        s.push_str(&self.ret.descriptor());
        s
    }

    /// The number of argument slots, not counting a receiver.
    pub fn argument_slots(&self) -> u16 {
        self.params.iter().map(Type::slots).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_and_prints_descriptors() {
        let d = MethodDescriptor::parse("(JI[Ljava/lang/String;)Ljava/util/List;").unwrap();
        assert_eq!(d.params.len(), 3);
        assert_eq!(d.params[0], Type::Long);
        assert_eq!(d.params[2], Type::Array(Box::new(Type::object("java/lang/String"))));
        assert_eq!(d.ret, Type::object("java/util/List"));
        assert_eq!(d.descriptor(), "(JI[Ljava/lang/String;)Ljava/util/List;");
        assert_eq!(d.argument_slots(), 4);
        assert_eq!(d.params[2].java_name(), "java.lang.String[]");
        assert_eq!(d.params[2].class_get_name(), "[Ljava.lang.String;");
        assert!(MethodDescriptor::parse("(I").is_err());
        assert!(Type::parse("Ljava/lang/String").is_err());
    }
}
