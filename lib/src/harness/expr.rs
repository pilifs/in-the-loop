//! The developer's declaration of a change's scope: a Java boolean expression over the method's parameters, such
//! as `seats >= 8 && priceCents > 0`. It is parsed and type-checked here with Java's rules (binary numeric
//! promotion, operator precedence), compiled to bytecode for the harness, and evaluated in Rust to check a
//! replayed counterexample against it.
//!
//! Supported: `int`/`long`/`short`/`byte`/`char`/`boolean` parameters, integer literals (decimal, hex, binary,
//! with `L` and `_`), `true`/`false`, parentheses, casts `(int)`/`(long)`, unary `- ! ~`, and the binary
//! operators `* / % + - << >> >>> < > <= >= == != & ^ | && ||` and `?:`.
//!
//! A property ([`crate::property`]) also sees the method's `result`, which is just another named value, and may
//! call the method under proof itself (`result == merge(b, a)`), which is how a law such as commutativity or
//! idempotence is stated. The call is compiled to an `invokestatic` in the harness; it cannot be evaluated here.
//!
//! An array parameter (or an array `result`) of an integral or boolean element type is used as `a.length` and
//! `a[index]`, and quantified over with JML's syntax: `(\forall int i; 0 <= i && i < a.length; a[i] != key)` and
//! `(\exists int i; 0 <= i && i < a.length; a[i] == key)`. The range must bound the variable below and above
//! (`lo <= i`, `i < hi`, `i <= hi`, and so on, with `&&`); any other conjunct of the range filters. A quantifier
//! is compiled to a loop in the harness, which bounded model checking unwinds, and evaluated as a loop here.

use crate::classfile::writer::{CodeBuilder, PoolBuilder};
use crate::classfile::{Cond, Kind, Type};
use crate::interp::Value;
use crate::Error;

/// The static types the expression language has.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ty {
    Int,
    Long,
    Boolean,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BinOp {
    Mul,
    Div,
    Rem,
    Add,
    Sub,
    Shl,
    Shr,
    Ushr,
    Lt,
    Gt,
    Le,
    Ge,
    Eq,
    Ne,
    And,
    Xor,
    Or,
    LogAnd,
    LogOr,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Int(i32),
    Long(i64),
    Bool(bool),
    /// A parameter: its name, type and local-variable slot.
    Var(String, Ty, u16),
    Neg(Box<Expr>),
    Not(Box<Expr>),
    BitNot(Box<Expr>),
    Cast(Ty, Box<Expr>),
    Binary(BinOp, Box<Expr>, Box<Expr>),
    Ternary(Box<Expr>, Box<Expr>, Box<Expr>),
    /// A call of the method under proof, with its arguments.
    Call(Callee, Vec<Expr>),
    /// `a.length` of an array parameter: its name and slot.
    Length(String, u16),
    /// `a[index]` of an array parameter: its name, slot, element type and the index.
    Index(String, u16, Type, Box<Expr>),
    /// `\forall int i; range; body` or `\exists ...`.
    Quantifier(Box<Quantifier>),
}

/// A bounded quantifier over an `int` variable.
#[derive(Debug, Clone, PartialEq)]
pub struct Quantifier {
    pub forall: bool,
    pub var: String,
    /// The slot of the variable, and of the accumulator next to it.
    pub slot: u16,
    /// The lower bound, inclusive; it does not mention the variable.
    pub lo: Expr,
    /// The upper bound, exclusive unless `inclusive`; it does not mention the variable.
    pub hi: Expr,
    pub inclusive: bool,
    /// The conjuncts of the range that are not bounds.
    pub filter: Option<Expr>,
    pub body: Expr,
}

/// A static method an expression may call: the method under proof, in a property.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Callee {
    pub name: String,
    /// The internal name of the class (`net/example/Clock`).
    pub owner: String,
    pub descriptor: String,
    pub params: Vec<Ty>,
    pub ret: Ty,
}

impl Callee {
    /// The callee for a static method, if its parameters and result are all integral or boolean.
    pub fn of(owner: &str, name: &str, descriptor: &str, params: &[Type], ret: &Type) -> Option<Callee> {
        let params = params.iter().map(ty_of).collect::<Option<Vec<Ty>>>()?;
        Some(Callee { name: name.to_string(), owner: owner.to_string(), descriptor: descriptor.to_string(), params, ret: ty_of(ret)? })
    }
}

impl Expr {
    /// The static type, by Java's promotion rules.
    pub fn ty(&self) -> Ty {
        match self {
            Expr::Int(_) => Ty::Int,
            Expr::Long(_) => Ty::Long,
            Expr::Bool(_) => Ty::Boolean,
            Expr::Var(_, t, _) => *t,
            Expr::Call(callee, _) => callee.ret,
            Expr::Length(..) => Ty::Int,
            Expr::Index(_, _, t, _) => ty_of(t).unwrap_or(Ty::Int),
            Expr::Quantifier(_) => Ty::Boolean,
            Expr::Neg(e) | Expr::BitNot(e) => e.ty(),
            Expr::Not(_) => Ty::Boolean,
            Expr::Cast(t, _) => *t,
            Expr::Binary(op, l, r) => match op {
                BinOp::Lt | BinOp::Gt | BinOp::Le | BinOp::Ge | BinOp::Eq | BinOp::Ne | BinOp::LogAnd | BinOp::LogOr => Ty::Boolean,
                BinOp::Shl | BinOp::Shr | BinOp::Ushr => l.ty(),
                BinOp::And | BinOp::Xor | BinOp::Or if l.ty() == Ty::Boolean => Ty::Boolean,
                _ => promote(l.ty(), r.ty()),
            },
            Expr::Ternary(_, t, e) => {
                if t.ty() == Ty::Boolean {
                    Ty::Boolean
                } else {
                    promote(t.ty(), e.ty())
                }
            }
        }
    }
}

fn promote(a: Ty, b: Ty) -> Ty {
    if a == Ty::Long || b == Ty::Long {
        Ty::Long
    } else {
        Ty::Int
    }
}

impl Expr {
    /// One past the highest local-variable slot the expression uses, including its quantifiers' variables.
    pub fn slots_used(&self) -> u16 {
        match self {
            Expr::Int(_) | Expr::Long(_) | Expr::Bool(_) => 0,
            Expr::Var(_, Ty::Long, slot) => slot + 2,
            Expr::Var(_, _, slot) | Expr::Length(_, slot) => slot + 1,
            Expr::Index(_, slot, _, index) => (slot + 1).max(index.slots_used()),
            Expr::Neg(e) | Expr::Not(e) | Expr::BitNot(e) | Expr::Cast(_, e) => e.slots_used(),
            Expr::Binary(_, l, r) => l.slots_used().max(r.slots_used()),
            Expr::Ternary(c, t, e) => c.slots_used().max(t.slots_used()).max(e.slots_used()),
            Expr::Call(_, args) => args.iter().map(Expr::slots_used).max().unwrap_or(0),
            Expr::Quantifier(q) => {
                let inner = q.lo.slots_used().max(q.hi.slots_used()).max(q.body.slots_used()).max(q.filter.as_ref().map(Expr::slots_used).unwrap_or(0));
                (q.slot + 2).max(inner)
            }
        }
    }

    /// Whether the expression calls the method under proof, which only the harness can evaluate.
    pub fn has_call(&self) -> bool {
        match self {
            Expr::Int(_) | Expr::Long(_) | Expr::Bool(_) | Expr::Var(..) | Expr::Length(..) => false,
            Expr::Call(..) => true,
            Expr::Index(_, _, _, index) => index.has_call(),
            Expr::Neg(e) | Expr::Not(e) | Expr::BitNot(e) | Expr::Cast(_, e) => e.has_call(),
            Expr::Binary(_, l, r) => l.has_call() || r.has_call(),
            Expr::Ternary(c, t, e) => c.has_call() || t.has_call() || e.has_call(),
            Expr::Quantifier(q) => q.lo.has_call() || q.hi.has_call() || q.body.has_call() || q.filter.as_ref().is_some_and(Expr::has_call),
        }
    }

    /// Whether the expression reads the local in `slot`.
    fn mentions(&self, slot: u16) -> bool {
        match self {
            Expr::Int(_) | Expr::Long(_) | Expr::Bool(_) => false,
            Expr::Var(_, _, s) | Expr::Length(_, s) => *s == slot,
            Expr::Index(_, s, _, index) => *s == slot || index.mentions(slot),
            Expr::Neg(e) | Expr::Not(e) | Expr::BitNot(e) | Expr::Cast(_, e) => e.mentions(slot),
            Expr::Binary(_, l, r) => l.mentions(slot) || r.mentions(slot),
            Expr::Ternary(c, t, e) => c.mentions(slot) || t.mentions(slot) || e.mentions(slot),
            Expr::Call(_, args) => args.iter().any(|a| a.mentions(slot)),
            Expr::Quantifier(q) => q.lo.mentions(slot) || q.hi.mentions(slot) || q.body.mentions(slot) || q.filter.as_ref().is_some_and(|f| f.mentions(slot)),
        }
    }
}

/// The element type of an array parameter, if the expression language can read it.
pub fn element_ty(t: &Type) -> Option<Ty> {
    match t {
        Type::Array(inner) => ty_of(inner),
        _ => None,
    }
}

/// A parameter available to the expression.
#[derive(Debug, Clone)]
pub struct Param {
    pub name: String,
    pub ty: Type,
    pub slot: u16,
}

fn ty_of(t: &Type) -> Option<Ty> {
    match t {
        Type::Boolean => Some(Ty::Boolean),
        Type::Byte | Type::Char | Type::Short | Type::Int => Some(Ty::Int),
        Type::Long => Some(Ty::Long),
        _ => None,
    }
}

// Lexer

#[derive(Debug, Clone, PartialEq)]
enum Token {
    Int(i64, bool), // value, is_long
    Ident(String),
    Op(&'static str),
    /// `\forall` or `\exists`.
    Quantifier(bool),
    End,
}

const OPS: &[&str] = &[">>>=", ">>>", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "(", ")", "[", "]", ",", ";", ".", "+", "-", "*", "/", "%", "<", ">", "!", "~", "&", "^", "|", "?", ":"];

fn lex(src: &str) -> Result<Vec<Token>, Error> {
    let chars: Vec<char> = src.chars().collect();
    let mut tokens = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c.is_whitespace() {
            i += 1;
            continue;
        }
        if c.is_ascii_digit() {
            let start = i;
            let mut radix = 10;
            if c == '0' && i + 1 < chars.len() && (chars[i + 1] == 'x' || chars[i + 1] == 'X') {
                radix = 16;
                i += 2;
            } else if c == '0' && i + 1 < chars.len() && (chars[i + 1] == 'b' || chars[i + 1] == 'B') {
                radix = 2;
                i += 2;
            }
            let digits_start = i;
            while i < chars.len() && (chars[i].is_ascii_alphanumeric() && chars[i] != 'L' && chars[i] != 'l' || chars[i] == '_') {
                i += 1;
            }
            let digits: String = chars[digits_start..i].iter().filter(|c| **c != '_').collect();
            let is_long = i < chars.len() && (chars[i] == 'L' || chars[i] == 'l');
            if is_long {
                i += 1;
            }
            let text: String = chars[start..i].iter().collect();
            let value = u64::from_str_radix(&digits, radix).map_err(|_| Error::new(format!("bad number literal {text:?}")))?;
            if !is_long && radix == 10 && value > i32::MAX as u64 + 1 {
                return Err(Error::new(format!("integer literal {text} is too large; add L for a long")));
            }
            tokens.push(Token::Int(value as i64, is_long));
            continue;
        }
        if c.is_alphabetic() || c == '_' || c == '$' {
            let start = i;
            while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_' || chars[i] == '$') {
                i += 1;
            }
            tokens.push(Token::Ident(chars[start..i].iter().collect()));
            continue;
        }
        if c == '\\' {
            let start = i + 1;
            i += 1;
            while i < chars.len() && chars[i].is_ascii_alphabetic() {
                i += 1;
            }
            let word: String = chars[start..i].iter().collect();
            match word.as_str() {
                "forall" => tokens.push(Token::Quantifier(true)),
                "exists" => tokens.push(Token::Quantifier(false)),
                _ => return Err(Error::new(format!("unknown \\{word} in expression; the quantifiers are \\forall and \\exists"))),
            }
            continue;
        }
        let rest: String = chars[i..].iter().take(4).collect();
        match OPS.iter().find(|op| rest.starts_with(**op)) {
            Some(op) => {
                tokens.push(Token::Op(op));
                i += op.len();
            }
            None => return Err(Error::new(format!("unexpected character {c:?} in expression"))),
        }
    }
    tokens.push(Token::End);
    Ok(tokens)
}

// Parser

struct Parser<'a> {
    tokens: Vec<Token>,
    pos: usize,
    params: &'a [Param],
    callee: Option<&'a Callee>,
    /// The variables of the enclosing quantifiers.
    scope: Vec<Param>,
    /// The first local-variable slot free for a quantifier's variable.
    next_slot: u16,
}

impl Parser<'_> {
    fn peek(&self) -> &Token {
        &self.tokens[self.pos]
    }

    fn next(&mut self) -> Token {
        let t = self.tokens[self.pos].clone();
        self.pos += 1;
        t
    }

    fn eat(&mut self, op: &str) -> bool {
        if self.peek() == &Token::Op(op_static(op)) {
            self.pos += 1;
            true
        } else {
            false
        }
    }

    fn expect(&mut self, op: &str) -> Result<(), Error> {
        if self.eat(op) {
            Ok(())
        } else {
            Err(Error::new(format!("expected {op:?} in expression, found {:?}", self.peek())))
        }
    }

    fn ternary(&mut self) -> Result<Expr, Error> {
        let cond = self.binary(2)?;
        if self.eat("?") {
            let then = self.ternary()?;
            self.expect(":")?;
            let otherwise = self.ternary()?;
            require(cond.ty() == Ty::Boolean, "the condition of ?: must be boolean")?;
            require((then.ty() == Ty::Boolean) == (otherwise.ty() == Ty::Boolean), "the branches of ?: must both be numeric or both boolean")?;
            return Ok(Expr::Ternary(Box::new(cond), Box::new(then), Box::new(otherwise)));
        }
        Ok(cond)
    }

    fn binary(&mut self, min_level: u8) -> Result<Expr, Error> {
        let mut left = self.unary()?;
        loop {
            let (op, level) = match self.peek() {
                Token::Op("||") => (BinOp::LogOr, 2),
                Token::Op("&&") => (BinOp::LogAnd, 3),
                Token::Op("|") => (BinOp::Or, 4),
                Token::Op("^") => (BinOp::Xor, 5),
                Token::Op("&") => (BinOp::And, 6),
                Token::Op("==") => (BinOp::Eq, 7),
                Token::Op("!=") => (BinOp::Ne, 7),
                Token::Op("<") => (BinOp::Lt, 8),
                Token::Op(">") => (BinOp::Gt, 8),
                Token::Op("<=") => (BinOp::Le, 8),
                Token::Op(">=") => (BinOp::Ge, 8),
                Token::Op("<<") => (BinOp::Shl, 9),
                Token::Op(">>") => (BinOp::Shr, 9),
                Token::Op(">>>") => (BinOp::Ushr, 9),
                Token::Op("+") => (BinOp::Add, 10),
                Token::Op("-") => (BinOp::Sub, 10),
                Token::Op("*") => (BinOp::Mul, 11),
                Token::Op("/") => (BinOp::Div, 11),
                Token::Op("%") => (BinOp::Rem, 11),
                _ => break,
            };
            if level < min_level {
                break;
            }
            self.next();
            let right = self.binary(level + 1)?;
            check_binary(op, &left, &right)?;
            left = Expr::Binary(op, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn unary(&mut self) -> Result<Expr, Error> {
        if self.eat("-") {
            let e = self.unary()?;
            require(e.ty() != Ty::Boolean, "unary - needs a number")?;
            return Ok(match e {
                Expr::Int(v) => Expr::Int(v.wrapping_neg()),
                Expr::Long(v) => Expr::Long(v.wrapping_neg()),
                e => Expr::Neg(Box::new(e)),
            });
        }
        if self.eat("!") {
            let e = self.unary()?;
            require(e.ty() == Ty::Boolean, "! needs a boolean")?;
            return Ok(Expr::Not(Box::new(e)));
        }
        if self.eat("~") {
            let e = self.unary()?;
            require(e.ty() != Ty::Boolean, "~ needs a number")?;
            return Ok(Expr::BitNot(Box::new(e)));
        }
        if self.eat("+") {
            return self.unary();
        }
        if let Token::Quantifier(forall) = self.peek().clone() {
            self.next();
            return self.quantifier(forall);
        }
        if self.peek() == &Token::Op("(") {
            // A cast, or a parenthesised expression.
            if let Token::Ident(name) = &self.tokens[self.pos + 1] {
                let cast = match name.as_str() {
                    "int" => Some(Ty::Int),
                    "long" => Some(Ty::Long),
                    "short" | "byte" | "char" => Some(Ty::Int),
                    _ => None,
                };
                if let Some(t) = cast {
                    if self.tokens[self.pos + 2] == Token::Op(")") {
                        self.pos += 3;
                        let e = self.unary()?;
                        require(e.ty() != Ty::Boolean, "cannot cast a boolean to a number")?;
                        return Ok(Expr::Cast(t, Box::new(e)));
                    }
                }
            }
            self.next();
            let e = self.ternary()?;
            self.expect(")")?;
            return Ok(e);
        }
        match self.next() {
            Token::Int(v, true) => Ok(Expr::Long(v)),
            Token::Int(v, false) => {
                if v == i32::MAX as i64 + 1 {
                    return Err(Error::new("2147483648 needs a leading - or an L suffix"));
                }
                Ok(Expr::Int(v as i32))
            }
            Token::Ident(name) => match name.as_str() {
                "true" => Ok(Expr::Bool(true)),
                "false" => Ok(Expr::Bool(false)),
                _ if self.callee.is_some_and(|c| c.name == name) && self.peek() == &Token::Op("(") => {
                    let callee = self.callee.expect("checked");
                    self.next();
                    let mut args = Vec::new();
                    if !self.eat(")") {
                        loop {
                            args.push(self.ternary()?);
                            if self.eat(")") {
                                break;
                            }
                            if !self.eat(",") {
                                return Err(Error::new(format!("expected \",\" or \")\" in the arguments of {name}, found {:?}", self.peek())));
                            }
                        }
                    }
                    require(args.len() == callee.params.len(), &format!("{name} takes {} arguments, {} given", callee.params.len(), args.len()))?;
                    for (i, (arg, param)) in args.iter().zip(&callee.params).enumerate() {
                        let ok = match param {
                            Ty::Boolean => arg.ty() == Ty::Boolean,
                            Ty::Int => arg.ty() == Ty::Int,
                            Ty::Long => arg.ty() != Ty::Boolean,
                        };
                        require(ok, &format!("argument {} of {name} must be {}", i + 1, match param { Ty::Boolean => "boolean", Ty::Int => "int", Ty::Long => "a number" }))?;
                    }
                    Ok(Expr::Call(callee.clone(), args))
                }
                _ => {
                    if let Some(bound) = self.scope.iter().rev().find(|p| p.name == name) {
                        return Ok(Expr::Var(name, Ty::Int, bound.slot));
                    }
                    let param = self.params.iter().find(|p| p.name == name).ok_or_else(|| Error::new(format!("unknown name {name:?}; the names are {}", self.params.iter().map(|p| p.name.as_str()).collect::<Vec<_>>().join(", "))))?;
                    if let Type::Array(element) = &param.ty {
                        let element = (**element).clone();
                        element_ty(&param.ty).ok_or_else(|| Error::new(format!("parameter {name} has type {}; only arrays of integral or boolean elements can appear in the expression", param.ty.java_name())))?;
                        if self.eat(".") {
                            match self.next() {
                                Token::Ident(field) if field == "length" => return Ok(Expr::Length(name, param.slot)),
                                other => return Err(Error::new(format!("expected {name}.length, found {other:?}"))),
                            }
                        }
                        if self.eat("[") {
                            let index = self.ternary()?;
                            require(index.ty() == Ty::Int, &format!("the index of {name} must be an int"))?;
                            self.expect("]")?;
                            return Ok(Expr::Index(name, param.slot, element, Box::new(index)));
                        }
                        return Err(Error::new(format!("{name} is an array; use {name}.length, {name}[index], or a quantifier over it")));
                    }
                    let t = ty_of(&param.ty).ok_or_else(|| Error::new(format!("parameter {name} has type {}; only integral and boolean parameters can appear in the expression", param.ty.java_name())))?;
                    Ok(Expr::Var(name, t, param.slot))
                }
            },
            other => Err(Error::new(format!("unexpected {other:?} in expression"))),
        }
    }

    /// `int i; range; body`, after `\forall` or `\exists`.
    fn quantifier(&mut self, forall: bool) -> Result<Expr, Error> {
        let keyword = if forall { "\\forall" } else { "\\exists" };
        match self.next() {
            Token::Ident(t) if t == "int" => {}
            other => return Err(Error::new(format!("expected `int` after {keyword}, found {other:?}"))),
        }
        let var = match self.next() {
            Token::Ident(name) => name,
            other => return Err(Error::new(format!("expected the variable of {keyword}, found {other:?}"))),
        };
        if self.scope.iter().any(|p| p.name == var) || self.params.iter().any(|p| p.name == var) {
            return Err(Error::new(format!("the variable {var} of {keyword} is already a name")));
        }
        self.expect(";")?;
        let slot = self.next_slot;
        self.next_slot += 2;
        self.scope.push(Param { name: var.clone(), ty: Type::Int, slot });
        let range = self.ternary();
        let body = range.as_ref().ok().map(|_| self.expect(";").and_then(|()| self.ternary()));
        self.scope.pop();
        let range = range?;
        let body = body.expect("parsed after the range")?;
        require(range.ty() == Ty::Boolean, &format!("the range of {var} must be boolean"))?;
        require(body.ty() == Ty::Boolean, &format!("the body of {keyword} must be boolean"))?;
        let (lo, hi, inclusive, filter) = bounds(range, &var, slot)?;
        Ok(Expr::Quantifier(Box::new(Quantifier { forall, var, slot, lo, hi, inclusive, filter, body })))
    }
}

/// Splits the range of a quantifier into a lower bound, an upper bound and a filter.
fn bounds(range: Expr, var: &str, slot: u16) -> Result<(Expr, Expr, bool, Option<Expr>), Error> {
    let mut conjuncts = Vec::new();
    flatten_and(range, &mut conjuncts);
    let mut lo = None;
    let mut hi: Option<(Expr, bool)> = None;
    let mut filter: Option<Expr> = None;
    for conjunct in conjuncts {
        let bound = match &conjunct {
            Expr::Binary(op, l, r) if matches!(op, BinOp::Lt | BinOp::Le | BinOp::Gt | BinOp::Ge) => {
                let is_var = |e: &Expr| matches!(e, Expr::Var(_, _, s) if *s == slot);
                if is_var(l) && !r.mentions(slot) && r.ty() == Ty::Int {
                    Some((*op, (**r).clone()))
                } else if is_var(r) && !l.mentions(slot) && l.ty() == Ty::Int {
                    let flipped = match op {
                        BinOp::Lt => BinOp::Gt,
                        BinOp::Le => BinOp::Ge,
                        BinOp::Gt => BinOp::Lt,
                        _ => BinOp::Le,
                    };
                    Some((flipped, (**l).clone()))
                } else {
                    None
                }
            }
            _ => None,
        };
        // The bound is now `var <op> e`.
        match bound {
            Some((BinOp::Ge, e)) if lo.is_none() => lo = Some(e),
            Some((BinOp::Gt, e)) if lo.is_none() => lo = Some(Expr::Binary(BinOp::Add, Box::new(e), Box::new(Expr::Int(1)))),
            Some((BinOp::Lt, e)) if hi.is_none() => hi = Some((e, false)),
            Some((BinOp::Le, e)) if hi.is_none() => hi = Some((e, true)),
            _ => {
                filter = Some(match filter {
                    Some(f) => Expr::Binary(BinOp::LogAnd, Box::new(f), Box::new(conjunct)),
                    None => conjunct,
                })
            }
        }
    }
    match (lo, hi) {
        (Some(lo), Some((hi, inclusive))) => Ok((lo, hi, inclusive, filter)),
        _ => Err(Error::new(format!("the range of {var} must bound it below and above, as in `0 <= {var} && {var} < a.length`"))),
    }
}

fn flatten_and(e: Expr, out: &mut Vec<Expr>) {
    match e {
        Expr::Binary(BinOp::LogAnd, l, r) => {
            flatten_and(*l, out);
            flatten_and(*r, out);
        }
        other => out.push(other),
    }
}

fn op_static(op: &str) -> &'static str {
    OPS.iter().copied().find(|o| *o == op).unwrap_or("")
}

fn require(condition: bool, message: &str) -> Result<(), Error> {
    if condition {
        Ok(())
    } else {
        Err(Error::new(message.to_string()))
    }
}

fn check_binary(op: BinOp, l: &Expr, r: &Expr) -> Result<(), Error> {
    let (lb, rb) = (l.ty() == Ty::Boolean, r.ty() == Ty::Boolean);
    match op {
        BinOp::LogAnd | BinOp::LogOr => require(lb && rb, "&& and || need booleans"),
        BinOp::And | BinOp::Or | BinOp::Xor => require(lb == rb, "& | ^ need two numbers or two booleans"),
        BinOp::Eq | BinOp::Ne => require(lb == rb, "== and != need two numbers or two booleans"),
        _ => require(!lb && !rb, &format!("{op:?} needs numbers")),
    }
}

/// Parses and type-checks an expression; it must be boolean.
pub fn parse(src: &str, params: &[Param]) -> Result<Expr, Error> {
    parse_with(src, params, None)
}

/// As [`parse`], with a method the expression may call.
pub fn parse_with(src: &str, params: &[Param], callee: Option<&Callee>) -> Result<Expr, Error> {
    parse_in(src, params, callee, params.iter().map(|p| p.slot + p.ty.slots()).max().unwrap_or(0))
}

/// As [`parse_with`], with the first local-variable slot a quantifier may use for its variable.
pub fn parse_in(src: &str, params: &[Param], callee: Option<&Callee>, first_free_slot: u16) -> Result<Expr, Error> {
    let tokens = lex(src)?;
    let mut parser = Parser { tokens, pos: 0, params, callee, scope: Vec::new(), next_slot: first_free_slot };
    let expr = parser.ternary()?;
    if parser.peek() != &Token::End {
        return Err(Error::new(format!("unexpected {:?} after the expression", parser.peek())));
    }
    if expr.ty() != Ty::Boolean {
        return Err(Error::new("the expression must be boolean"));
    }
    Ok(expr)
}

// Evaluation, for checking a replayed counterexample

/// Evaluates the expression over parameter values (by slot). Division by zero is an error.
pub fn eval(expr: &Expr, locals: &[Value]) -> Result<Value, Error> {
    eval_with(expr, locals, &[])
}

/// As [`eval`], with the elements of the array parameters by slot. A quantifier's variable is written into its
/// slot, so the locals are extended as needed.
pub fn eval_with(expr: &Expr, locals: &[Value], arrays: &[(u16, Vec<Value>)]) -> Result<Value, Error> {
    let mut locals = locals.to_vec();
    locals.resize(locals.len().max(usize::from(expr.slots_used())), Value::Int(0));
    eval_in(expr, &mut locals, arrays)
}

fn eval_in(expr: &Expr, locals: &mut Vec<Value>, arrays: &[(u16, Vec<Value>)]) -> Result<Value, Error> {
    let array = |name: &str, slot: u16| arrays.iter().find(|(s, _)| *s == slot).map(|(_, data)| data).ok_or_else(|| Error::new(format!("no elements for the array {name}")));
    Ok(match expr {
        Expr::Length(name, slot) => Value::Int(array(name, *slot)?.len() as i32),
        Expr::Index(name, slot, t, index) => {
            let i = eval_in(index, locals, arrays)?.as_int();
            let data = array(name, *slot)?;
            let v = *usize::try_from(i).ok().and_then(|i| data.get(i)).ok_or_else(|| Error::new(format!("{name}[{i}] is out of bounds for length {}", data.len())))?;
            match (t, v) {
                (Type::Long, Value::Int(x)) => Value::Long(i64::from(x)),
                _ => v,
            }
        }
        Expr::Quantifier(q) => {
            let lo = eval_in(&q.lo, locals, arrays)?.as_int();
            let hi = eval_in(&q.hi, locals, arrays)?.as_int();
            let end = if q.inclusive { i64::from(hi) + 1 } else { i64::from(hi) };
            let mut i = i64::from(lo);
            while i < end {
                locals[usize::from(q.slot)] = Value::Int(i as i32);
                let selected = match &q.filter {
                    Some(f) => eval_in(f, locals, arrays)?.as_int() != 0,
                    None => true,
                };
                if selected && (eval_in(&q.body, locals, arrays)?.as_int() != 0) != q.forall {
                    return Ok(Value::Int((!q.forall) as i32));
                }
                i += 1;
            }
            Value::Int(q.forall as i32)
        }
        Expr::Int(v) => Value::Int(*v),
        Expr::Long(v) => Value::Long(*v),
        Expr::Bool(b) => Value::Int(*b as i32),
        Expr::Var(name, t, slot) => {
            let v = *locals.get(*slot as usize).ok_or_else(|| Error::new(format!("no value for {name}")))?;
            match (t, v) {
                (Ty::Long, Value::Int(x)) => Value::Long(i64::from(x)),
                _ => v,
            }
        }
        Expr::Neg(e) => match eval_in(e, locals, arrays)? {
            Value::Int(x) => Value::Int(x.wrapping_neg()),
            Value::Long(x) => Value::Long(x.wrapping_neg()),
            v => v,
        },
        Expr::Not(e) => Value::Int((eval_in(e, locals, arrays)?.as_int() == 0) as i32),
        Expr::Call(callee, _) => return Err(Error::new(format!("a call of {} can only be evaluated in the harness", callee.name))),
        Expr::BitNot(e) => match eval_in(e, locals, arrays)? {
            Value::Int(x) => Value::Int(!x),
            Value::Long(x) => Value::Long(!x),
            v => v,
        },
        Expr::Cast(Ty::Int, e) => Value::Int(as_i64(eval_in(e, locals, arrays)?) as i32),
        Expr::Cast(_, e) => Value::Long(as_i64(eval_in(e, locals, arrays)?)),
        Expr::Ternary(c, t, e) => {
            if eval_in(c, locals, arrays)?.as_int() != 0 {
                eval_in(t, locals, arrays)?
            } else {
                eval_in(e, locals, arrays)?
            }
        }
        Expr::Binary(op, l, r) => {
            if *op == BinOp::LogAnd {
                return Ok(Value::Int((eval_in(l, locals, arrays)?.as_int() != 0 && eval_in(r, locals, arrays)?.as_int() != 0) as i32));
            }
            if *op == BinOp::LogOr {
                return Ok(Value::Int((eval_in(l, locals, arrays)?.as_int() != 0 || eval_in(r, locals, arrays)?.as_int() != 0) as i32));
            }
            let (a, b) = (eval_in(l, locals, arrays)?, eval_in(r, locals, arrays)?);
            let wide = expr.ty() == Ty::Long || (matches!(op, BinOp::Lt | BinOp::Gt | BinOp::Le | BinOp::Ge | BinOp::Eq | BinOp::Ne) && promote(l.ty(), r.ty()) == Ty::Long);
            let (x, y) = (as_i64(a), as_i64(b));
            let wrap = |v: i64| if wide { Value::Long(v) } else { Value::Int(v as i32) };
            let shift_x = if l.ty() == Ty::Long { x } else { i64::from(x as i32) };
            match op {
                BinOp::Add => wrap(if wide { x.wrapping_add(y) } else { i64::from((x as i32).wrapping_add(y as i32)) }),
                BinOp::Sub => wrap(if wide { x.wrapping_sub(y) } else { i64::from((x as i32).wrapping_sub(y as i32)) }),
                BinOp::Mul => wrap(if wide { x.wrapping_mul(y) } else { i64::from((x as i32).wrapping_mul(y as i32)) }),
                BinOp::Div | BinOp::Rem => {
                    if y == 0 {
                        return Err(Error::new("division by zero in the expression"));
                    }
                    if *op == BinOp::Div {
                        wrap(if wide { x.wrapping_div(y) } else { i64::from((x as i32).wrapping_div(y as i32)) })
                    } else {
                        wrap(if wide { x.wrapping_rem(y) } else { i64::from((x as i32).wrapping_rem(y as i32)) })
                    }
                }
                BinOp::Shl => {
                    if l.ty() == Ty::Long {
                        Value::Long(shift_x.wrapping_shl(y as u32 & 63))
                    } else {
                        Value::Int((shift_x as i32).wrapping_shl(y as u32 & 31))
                    }
                }
                BinOp::Shr => {
                    if l.ty() == Ty::Long {
                        Value::Long(shift_x.wrapping_shr(y as u32 & 63))
                    } else {
                        Value::Int((shift_x as i32).wrapping_shr(y as u32 & 31))
                    }
                }
                BinOp::Ushr => {
                    if l.ty() == Ty::Long {
                        Value::Long(((shift_x as u64) >> (y as u32 & 63)) as i64)
                    } else {
                        Value::Int(((shift_x as i32 as u32) >> (y as u32 & 31)) as i32)
                    }
                }
                BinOp::And => wrap(x & y),
                BinOp::Or => wrap(x | y),
                BinOp::Xor => wrap(x ^ y),
                BinOp::Lt => Value::Int((x < y) as i32),
                BinOp::Gt => Value::Int((x > y) as i32),
                BinOp::Le => Value::Int((x <= y) as i32),
                BinOp::Ge => Value::Int((x >= y) as i32),
                BinOp::Eq => Value::Int((x == y) as i32),
                BinOp::Ne => Value::Int((x != y) as i32),
                BinOp::LogAnd | BinOp::LogOr => unreachable!(),
            }
        }
    })
}

fn as_i64(v: Value) -> i64 {
    match v {
        Value::Int(x) => i64::from(x),
        Value::Long(x) => x,
        _ => 0,
    }
}

// Bytecode

/// Emits the expression, leaving its value on the stack (booleans as 0/1 ints).
pub fn emit(expr: &Expr, code: &mut CodeBuilder, pool: &mut PoolBuilder) {
    match expr {
        Expr::Int(v) => emit_int(*v, code, pool),
        Expr::Long(v) => emit_long(*v, code, pool),
        Expr::Bool(b) => code.iconst(*b as i32),
        Expr::Var(_, Ty::Long, slot) => code.load(Kind::Long, *slot),
        Expr::Var(_, _, slot) => code.load(Kind::Int, *slot),
        Expr::Length(_, slot) => {
            code.load(Kind::Ref, *slot);
            code.op(0xbe); // arraylength
        }
        Expr::Index(_, slot, t, index) => {
            code.load(Kind::Ref, *slot);
            emit_promoted(index, Ty::Int, code, pool);
            code.op(match t {
                Type::Long => 0x2f,                 // laload
                Type::Byte | Type::Boolean => 0x33, // baload
                Type::Char => 0x34,                 // caload
                Type::Short => 0x35,                // saload
                _ => 0x2e,                          // iaload
            });
        }
        Expr::Quantifier(q) => {
            let acc = q.slot + 1;
            let loop_ = code.label();
            let next = code.label();
            let end = code.label();
            code.iconst(q.forall as i32);
            code.store(Kind::Int, acc);
            emit_promoted(&q.lo, Ty::Int, code, pool);
            code.store(Kind::Int, q.slot);
            code.bind(loop_);
            code.load(Kind::Int, q.slot);
            emit_promoted(&q.hi, Ty::Int, code, pool);
            code.if_icmp(if q.inclusive { Cond::Gt } else { Cond::Ge }, end);
            if let Some(filter) = &q.filter {
                emit(filter, code, pool);
                code.if_zero(Cond::Eq, next);
            }
            emit(&q.body, code, pool);
            code.if_zero(if q.forall { Cond::Ne } else { Cond::Eq }, next);
            code.iconst((!q.forall) as i32);
            code.store(Kind::Int, acc);
            code.goto(end);
            code.bind(next);
            code.iinc(q.slot, 1);
            code.goto(loop_);
            code.bind(end);
            code.load(Kind::Int, acc);
        }
        Expr::Call(callee, args) => {
            for (arg, param) in args.iter().zip(&callee.params) {
                emit_promoted(arg, *param, code, pool);
            }
            let index = pool.method_ref(&callee.owner, &callee.name, &callee.descriptor);
            code.op_u16(0xb8, index); // invokestatic
        }
        Expr::Neg(e) => {
            emit(e, code, pool);
            code.op(if e.ty() == Ty::Long { 0x75 } else { 0x74 });
        }
        Expr::BitNot(e) => {
            emit(e, code, pool);
            if e.ty() == Ty::Long {
                emit_long(-1, code, pool);
                code.op(0x83); // lxor
            } else {
                code.iconst(-1);
                code.op(0x82); // ixor
            }
        }
        Expr::Not(e) => {
            emit(e, code, pool);
            code.iconst(1);
            code.op(0x82); // ixor: flips 0/1
        }
        Expr::Cast(t, e) => {
            emit(e, code, pool);
            match (e.ty(), t) {
                (Ty::Int, Ty::Long) => code.op(0x85),
                (Ty::Long, Ty::Int) => code.op(0x88),
                _ => {}
            }
        }
        Expr::Ternary(c, t, e) => {
            let target = expr.ty();
            let otherwise = code.label();
            let end = code.label();
            emit(c, code, pool);
            code.if_zero(Cond::Eq, otherwise);
            emit_promoted(t, target, code, pool);
            code.goto(end);
            code.bind(otherwise);
            emit_promoted(e, target, code, pool);
            code.bind(end);
        }
        Expr::Binary(op, l, r) => match op {
            BinOp::LogAnd | BinOp::LogOr => {
                let short = code.label();
                let end = code.label();
                let short_cond = if *op == BinOp::LogAnd { Cond::Eq } else { Cond::Ne };
                emit(l, code, pool);
                code.if_zero(short_cond, short);
                emit(r, code, pool);
                code.if_zero(short_cond, short);
                code.iconst((*op == BinOp::LogAnd) as i32);
                code.goto(end);
                code.bind(short);
                code.iconst((*op == BinOp::LogOr) as i32);
                code.bind(end);
            }
            BinOp::Lt | BinOp::Gt | BinOp::Le | BinOp::Ge | BinOp::Eq | BinOp::Ne => {
                let target = promote(l.ty(), r.ty());
                let cond = match op {
                    BinOp::Lt => Cond::Lt,
                    BinOp::Gt => Cond::Gt,
                    BinOp::Le => Cond::Le,
                    BinOp::Ge => Cond::Ge,
                    BinOp::Eq => Cond::Eq,
                    _ => Cond::Ne,
                };
                let yes = code.label();
                let end = code.label();
                if l.ty() == Ty::Boolean {
                    emit(l, code, pool);
                    emit(r, code, pool);
                    code.if_icmp(cond, yes);
                } else {
                    emit_promoted(l, target, code, pool);
                    emit_promoted(r, target, code, pool);
                    if target == Ty::Long {
                        code.op(0x94); // lcmp
                        code.if_zero(cond, yes);
                    } else {
                        code.if_icmp(cond, yes);
                    }
                }
                code.iconst(0);
                code.goto(end);
                code.bind(yes);
                code.iconst(1);
                code.bind(end);
            }
            BinOp::Shl | BinOp::Shr | BinOp::Ushr => {
                emit(l, code, pool);
                emit_promoted(r, Ty::Int, code, pool);
                let long = l.ty() == Ty::Long;
                code.op(match (op, long) {
                    (BinOp::Shl, false) => 0x78,
                    (BinOp::Shl, true) => 0x79,
                    (BinOp::Shr, false) => 0x7a,
                    (BinOp::Shr, true) => 0x7b,
                    (BinOp::Ushr, false) => 0x7c,
                    _ => 0x7d,
                });
            }
            _ => {
                let target = expr.ty();
                let long = target == Ty::Long;
                emit_promoted(l, target, code, pool);
                emit_promoted(r, target, code, pool);
                code.op(match (op, long) {
                    (BinOp::Add, false) => 0x60,
                    (BinOp::Add, true) => 0x61,
                    (BinOp::Sub, false) => 0x64,
                    (BinOp::Sub, true) => 0x65,
                    (BinOp::Mul, false) => 0x68,
                    (BinOp::Mul, true) => 0x69,
                    (BinOp::Div, false) => 0x6c,
                    (BinOp::Div, true) => 0x6d,
                    (BinOp::Rem, false) => 0x70,
                    (BinOp::Rem, true) => 0x71,
                    (BinOp::And, false) => 0x7e,
                    (BinOp::And, true) => 0x7f,
                    (BinOp::Or, false) => 0x80,
                    (BinOp::Or, true) => 0x81,
                    (BinOp::Xor, false) => 0x82,
                    _ => 0x83,
                });
            }
        },
    }
}

fn emit_promoted(e: &Expr, target: Ty, code: &mut CodeBuilder, pool: &mut PoolBuilder) {
    emit(e, code, pool);
    if target == Ty::Long && e.ty() == Ty::Int {
        code.op(0x85); // i2l
    }
}

fn emit_int(v: i32, code: &mut CodeBuilder, pool: &mut PoolBuilder) {
    if (-32768..=32767).contains(&v) {
        code.iconst(v);
    } else {
        let index = pool.integer(v);
        code.ldc(index);
    }
}

fn emit_long(v: i64, code: &mut CodeBuilder, pool: &mut PoolBuilder) {
    match v {
        0 => code.op(0x09),
        1 => code.op(0x0a),
        _ => {
            let index = pool.long(v);
            code.ldc2(index);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params() -> Vec<Param> {
        vec![
            Param { name: "priceCents".into(), ty: Type::Long, slot: 0 },
            Param { name: "seats".into(), ty: Type::Int, slot: 2 },
            Param { name: "vip".into(), ty: Type::Boolean, slot: 3 },
        ]
    }

    fn locals(price: i64, seats: i32, vip: bool) -> Vec<Value> {
        vec![Value::Long(price), Value::Int(0), Value::Int(seats), Value::Int(vip as i32)]
    }

    #[test]
    fn parses_types_and_evaluates() {
        let e = parse("seats >= 8 && priceCents > 0L || vip", &params()).unwrap();
        assert_eq!(eval(&e, &locals(5, 8, false)).unwrap(), Value::Int(1));
        assert_eq!(eval(&e, &locals(0, 8, false)).unwrap(), Value::Int(0));
        assert_eq!(eval(&e, &locals(0, 1, true)).unwrap(), Value::Int(1));
        let e = parse("(priceCents * seats) % 10 == 0", &params()).unwrap();
        assert_eq!(eval(&e, &locals(5, 2, false)).unwrap(), Value::Int(1));
        assert_eq!(eval(&e, &locals(5, 3, false)).unwrap(), Value::Int(0));
        let e = parse("seats > 6 ? priceCents < 100 : !vip", &params()).unwrap();
        assert_eq!(eval(&e, &locals(50, 7, true)).unwrap(), Value::Int(1));
        let e = parse("(int) priceCents == seats", &params()).unwrap();
        assert_eq!(eval(&e, &locals(3, 3, false)).unwrap(), Value::Int(1));
        let e = parse("-seats < 0x10 && ~seats != 0 && seats << 2 == 8", &params()).unwrap();
        assert_eq!(eval(&e, &locals(0, 2, false)).unwrap(), Value::Int(1));
        assert_eq!(parse("seats >= 8 && priceCents > 0L || vip", &params()).unwrap().ty(), Ty::Boolean);
    }

    #[test]
    fn rejects_bad_expressions() {
        assert!(parse("seats + 1", &params()).is_err(), "not boolean");
        assert!(parse("seat >= 8", &params()).is_err(), "unknown name");
        assert!(parse("vip > 1", &params()).is_err(), "boolean compared with number");
        assert!(parse("seats && vip", &params()).is_err(), "&& on a number");
        assert!(parse("seats >= 8)", &params()).is_err(), "trailing token");
        assert!(parse("total(priceCents, seats) > 0", &params()).is_err(), "no callee");
    }

    #[test]
    fn parses_arrays_and_quantifiers() {
        let params = vec![Param { name: "a".into(), ty: Type::Array(Box::new(Type::Int)), slot: 0 }, Param { name: "key".into(), ty: Type::Int, slot: 1 }];
        let arrays = |data: &[i32]| vec![(0u16, data.iter().map(|v| Value::Int(*v)).collect::<Vec<_>>())];
        let locals = |key| vec![Value::Null, Value::Int(key)];
        let absent = parse_in("(\\forall int i; 0 <= i && i < a.length; a[i] != key)", &params, None, 2).unwrap();
        assert_eq!(eval_with(&absent, &locals(5), &arrays(&[1, 2, 3])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&absent, &locals(2), &arrays(&[1, 2, 3])).unwrap(), Value::Int(0));
        assert_eq!(eval_with(&absent, &locals(2), &arrays(&[])).unwrap(), Value::Int(1), "vacuous");
        let sorted = parse_in("\\forall int i; 0 < i && i < a.length; a[i - 1] < a[i]", &params, None, 2).unwrap();
        assert_eq!(eval_with(&sorted, &locals(0), &arrays(&[1, 2, 3])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&sorted, &locals(0), &arrays(&[1, 3, 2])).unwrap(), Value::Int(0));
        // An inclusive upper bound, a filter, and the bound written with the variable on the right.
        let even = parse_in("(\\exists int i; 0 <= i && a.length - 1 >= i && i % 2 == 0; a[i] == key)", &params, None, 2).unwrap();
        assert_eq!(eval_with(&even, &locals(3), &arrays(&[1, 2, 3])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&even, &locals(2), &arrays(&[1, 2, 3])).unwrap(), Value::Int(0), "index 1 is filtered out");
        assert_eq!(even.slots_used(), 4);
        let distinct = parse_in("\\forall int i; 0 <= i && i < a.length; \\forall int j; i < j && j < a.length; a[i] != a[j]", &params, None, 2).unwrap();
        assert_eq!(eval_with(&distinct, &locals(0), &arrays(&[1, 2, 3])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&distinct, &locals(0), &arrays(&[1, 2, 1])).unwrap(), Value::Int(0));
        assert_eq!(distinct.slots_used(), 6);
        assert!(eval_with(&parse_in("a[key] == 0", &params, None, 2).unwrap(), &locals(7), &arrays(&[1])).is_err(), "out of bounds");

        assert!(parse_in("a == 0", &params, None, 2).is_err(), "an array is not a value");
        assert!(parse_in("\\forall int i; i < a.length; a[i] != key", &params, None, 2).is_err(), "no lower bound");
        assert!(parse_in("\\forall int key; 0 <= key && key < 3; true", &params, None, 2).is_err(), "shadows a parameter");
        assert!(parse_in("\\forall long i; 0 <= i && i < 3; true", &params, None, 2).is_err(), "int variables only");
        assert!(parse_in("\\some int i; 0 <= i && i < 3; true", &params, None, 2).is_err(), "unknown quantifier");
        assert!(parse_in("a[1L] == 0", &params, None, 2).is_err(), "a long index");
        let floats = vec![Param { name: "f".into(), ty: Type::Array(Box::new(Type::Float)), slot: 0 }];
        assert!(parse_in("f.length > 0", &floats, None, 1).is_err(), "float elements are not expressible");
    }

    #[test]
    fn parses_and_types_calls_of_the_method_under_proof() {
        let callee = Callee::of("net/example/Pricing", "total", "(JIZ)J", &[Type::Long, Type::Int, Type::Boolean], &Type::Long).unwrap();
        let mut params = params();
        params.push(Param { name: "result".into(), ty: Type::Long, slot: 4 });
        let e = parse_with("result == total(priceCents, seats, vip) && total(seats, 1, !vip) >= 0", &params, Some(&callee)).unwrap();
        assert!(matches!(&e, Expr::Binary(BinOp::LogAnd, _, _)));
        assert!(eval(&e, &[]).is_err(), "calls are not evaluated outside the harness");
        assert!(parse_with("total(priceCents, seats) == 0", &params, Some(&callee)).is_err(), "arity");
        assert!(parse_with("total(priceCents, priceCents, vip) == 0", &params, Some(&callee)).is_err(), "long for int");
        assert!(parse_with("total(1, 2, 3) == 0", &params, Some(&callee)).is_err(), "number for boolean");
        assert!(Callee::of("X", "f", "(D)J", &[Type::Double], &Type::Long).is_none(), "a double parameter is not expressible");
    }
}
