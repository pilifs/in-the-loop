//! Generic signatures (JVMS 4.7.9.1), rendered as a reader of the source would see them: `List<Order>`,
//! `ResponseEntity<Map<String, Integer>>`, `T[]`. Only the `Signature` attribute keeps the type arguments the
//! descriptor erases, so the renderers take the signature when a class has one and fall back to the descriptor.

use super::descriptor::Type;

struct Parser<'a> {
    s: &'a [u8],
    pos: usize,
}

impl Parser<'_> {
    fn peek(&self) -> Option<u8> {
        self.s.get(self.pos).copied()
    }

    fn eat(&mut self, b: u8) -> bool {
        if self.peek() == Some(b) {
            self.pos += 1;
            true
        } else {
            false
        }
    }

    fn identifier(&mut self) -> Option<String> {
        let start = self.pos;
        while let Some(b) = self.peek() {
            if matches!(b, b';' | b'<' | b'>' | b'.' | b':' | b'/') {
                break;
            }
            self.pos += 1;
        }
        if self.pos == start {
            return None;
        }
        String::from_utf8(self.s[start..self.pos].to_vec()).ok()
    }

    /// Skips `<T:Ljava/lang/Object;U::Ljava/lang/Comparable<TU;>;>` at the start of a class or method signature.
    fn skip_type_parameters(&mut self) -> Option<()> {
        if !self.eat(b'<') {
            return Some(());
        }
        while !self.eat(b'>') {
            self.identifier()?;
            while self.eat(b':') {
                if matches!(self.peek(), Some(b'L' | b'T' | b'[')) {
                    self.reference()?;
                }
            }
        }
        Some(())
    }

    /// A `JavaTypeSignature`: a base type or a reference type, rendered.
    fn java_type(&mut self) -> Option<String> {
        match self.peek()? {
            b'L' | b'T' | b'[' => self.reference(),
            b => {
                self.pos += 1;
                Type::parse(std::str::from_utf8(&[b]).ok()?).ok().map(|t| t.java_name())
            }
        }
    }

    fn reference(&mut self) -> Option<String> {
        match self.peek()? {
            b'T' => {
                self.pos += 1;
                let name = self.identifier()?;
                self.eat(b';').then_some(name)
            }
            b'[' => {
                self.pos += 1;
                Some(format!("{}[]", self.java_type()?))
            }
            b'L' => {
                self.pos += 1;
                let mut rendered = String::new();
                loop {
                    let mut name = self.identifier()?;
                    while self.eat(b'/') {
                        name = self.identifier()?;
                    }
                    let simple = name.rsplit('$').next().unwrap_or(&name).to_string();
                    rendered.push_str(&simple);
                    if self.eat(b'<') {
                        let mut args = Vec::new();
                        while !self.eat(b'>') {
                            args.push(self.type_argument()?);
                        }
                        rendered.push_str(&format!("<{}>", args.join(", ")));
                    }
                    if self.eat(b'.') {
                        rendered.push('.');
                        continue;
                    }
                    break;
                }
                self.eat(b';').then_some(rendered)
            }
            _ => None,
        }
    }

    fn type_argument(&mut self) -> Option<String> {
        if self.eat(b'*') {
            return Some("?".into());
        }
        if self.eat(b'+') {
            return Some(format!("? extends {}", self.reference()?));
        }
        if self.eat(b'-') {
            return Some(format!("? super {}", self.reference()?));
        }
        self.reference()
    }
}

/// A type from a signature or descriptor, kept as a tree: what a type annotation's path (JVMS 4.7.20.2) walks
/// and what a validation constraint applies to.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Sig {
    /// A class by internal name (`java/util/List`, `net/x/Outer$Inner`) with its type arguments, those of an inner
    /// class after its outer's.
    Class { name: String, args: Vec<Sig> },
    Array(Box<Sig>),
    /// A base type by descriptor letter (`I`).
    Primitive(char),
    Variable(String),
    /// `?`, `? extends T` (`true`) or `? super T` (`false`).
    Wildcard(Option<(bool, Box<Sig>)>),
}

impl Sig {
    /// The type a type path leads to: into a type argument, an array's component or a wildcard's bound. `None`
    /// when the path does not fit the type.
    pub fn at(&self, path: &[(u8, u8)]) -> Option<&Sig> {
        let Some(&(kind, index)) = path.first() else { return Some(self) };
        let next = match (kind, self) {
            (0, Sig::Array(elem)) => elem.as_ref(),
            (2, Sig::Wildcard(Some((_, bound)))) => bound.as_ref(),
            (3, Sig::Class { args, .. }) => args.get(index as usize)?,
            // Kind 1 steps from an outer class to its inner; the inner's arguments are already here.
            (1, Sig::Class { .. }) => self,
            _ => return None,
        };
        next.at(&path[1..])
    }

    /// The class name when this is a class type.
    pub fn class_name(&self) -> Option<&str> {
        match self {
            Sig::Class { name, .. } => Some(name),
            _ => None,
        }
    }
}

impl Parser<'_> {
    fn sig(&mut self) -> Option<Sig> {
        match self.peek()? {
            b'T' => {
                self.pos += 1;
                let name = self.identifier()?;
                self.eat(b';').then_some(Sig::Variable(name))
            }
            b'[' => {
                self.pos += 1;
                Some(Sig::Array(Box::new(self.sig()?)))
            }
            b'L' => {
                self.pos += 1;
                let mut name = String::new();
                let mut args = Vec::new();
                loop {
                    let mut part = self.identifier()?;
                    while self.eat(b'/') {
                        name.push_str(&part);
                        name.push('/');
                        part = self.identifier()?;
                    }
                    name.push_str(&part);
                    if self.eat(b'<') {
                        while !self.eat(b'>') {
                            args.push(self.sig_argument()?);
                        }
                    }
                    if self.eat(b'.') {
                        name.push('$');
                        continue;
                    }
                    break;
                }
                self.eat(b';').then_some(Sig::Class { name, args })
            }
            b'*' => {
                self.pos += 1;
                Some(Sig::Wildcard(None))
            }
            b => {
                self.pos += 1;
                Some(Sig::Primitive(b as char))
            }
        }
    }

    fn sig_argument(&mut self) -> Option<Sig> {
        if self.eat(b'+') {
            return Some(Sig::Wildcard(Some((true, Box::new(self.sig()?)))));
        }
        if self.eat(b'-') {
            return Some(Sig::Wildcard(Some((false, Box::new(self.sig()?)))));
        }
        self.sig()
    }
}

/// A field type, from its generic signature or its descriptor, as a tree.
pub fn parse_type(signature: &str) -> Option<Sig> {
    let mut p = Parser { s: signature.as_bytes(), pos: 0 };
    let t = p.sig()?;
    (p.pos == signature.len()).then_some(t)
}

/// The parameter types and the return type of a method signature, rendered with simple names, or `None` when the
/// signature is not one this renderer understands.
pub fn method_types(signature: &str) -> Option<(Vec<String>, String)> {
    let mut p = Parser { s: signature.as_bytes(), pos: 0 };
    p.skip_type_parameters()?;
    if !p.eat(b'(') {
        return None;
    }
    let mut params = Vec::new();
    while !p.eat(b')') {
        params.push(p.java_type()?);
    }
    let ret = if p.eat(b'V') { "void".to_string() } else { p.java_type()? };
    Some((params, ret))
}

/// The raw parameter and return parts of a method signature or descriptor, unrendered, for a caller that wants
/// the class names in each: `(Ljava/util/List<Lnet/x/Order;>;I)V` is `["Ljava/util/List<Lnet/x/Order;>;", "I"]`
/// and `V`.
pub fn method_parts(signature: &str) -> Option<(Vec<String>, String)> {
    let mut p = Parser { s: signature.as_bytes(), pos: 0 };
    p.skip_type_parameters()?;
    if !p.eat(b'(') {
        return None;
    }
    let mut params = Vec::new();
    while !p.eat(b')') {
        let start = p.pos;
        p.java_type()?;
        params.push(signature[start..p.pos].to_string());
    }
    let start = p.pos;
    if !p.eat(b'V') {
        p.java_type()?;
    }
    Some((params, signature[start..p.pos].to_string()))
}

/// A field's type from its signature, rendered with simple names.
pub fn field_type(signature: &str) -> Option<String> {
    let mut p = Parser { s: signature.as_bytes(), pos: 0 };
    let t = p.java_type()?;
    (p.pos == signature.len()).then_some(t)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn types_parse_as_trees() {
        let t = parse_type("Ljava/util/Map<Ljava/lang/String;Ljava/util/List<[I>;>;").unwrap();
        assert_eq!(t.at(&[(3, 1), (3, 0), (0, 0)]), Some(&Sig::Primitive('I')));
        assert_eq!(t.at(&[(3, 0)]).and_then(Sig::class_name), Some("java/lang/String"));
        assert_eq!(t.at(&[(3, 2)]), None);
        assert_eq!(parse_type("Lnet/example/Outer<TT;>.Inner<+Ljava/lang/Number;>;").unwrap().at(&[(1, 0), (3, 1), (2, 0)]).and_then(Sig::class_name), Some("java/lang/Number"));
        assert_eq!(parse_type("I"), Some(Sig::Primitive('I')));
        assert_eq!(parse_type("Ljava/lang/String;I"), None);
    }

    #[test]
    fn signatures_render_as_source_does() {
        assert_eq!(method_types("(Ljava/util/List<Ljava/lang/String;>;I)Lorg/springframework/http/ResponseEntity<Lnet/example/Order;>;").unwrap(), (vec!["List<String>".to_string(), "int".to_string()], "ResponseEntity<Order>".to_string()));
        assert_eq!(method_types("<T:Ljava/lang/Object;>([TT;Ljava/util/Map<Ljava/lang/String;+Ljava/lang/Number;>;)V").unwrap(), (vec!["T[]".to_string(), "Map<String, ? extends Number>".to_string()], "void".to_string()));
        assert_eq!(method_types("()Ljava/util/Map$Entry<Ljava/lang/String;*>;").unwrap().1, "Entry<String, ?>");
        assert_eq!(method_types("()Lnet/example/Outer<TT;>.Inner;").unwrap().1, "Outer<T>.Inner");
        assert_eq!(field_type("Ljava/util/Optional<Ljava/time/Duration;>;").unwrap(), "Optional<Duration>");
        assert!(method_types("garbage").is_none());
        assert_eq!(method_parts("(Ljava/util/List<Lnet/x/Order;>;I)V").unwrap(), (vec!["Ljava/util/List<Lnet/x/Order;>;".to_string(), "I".to_string()], "V".to_string()));
        assert_eq!(method_parts("<T:Ljava/lang/Object;>([TT;)Lnet/x/Result;").unwrap(), (vec!["[TT;".to_string()], "Lnet/x/Result;".to_string()));
    }
}
