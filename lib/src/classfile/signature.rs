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
