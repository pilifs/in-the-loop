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
//! An array parameter is passed to such a call by name (`offsetOf(offsetDelta, k - 1)`).
//!
//! An array parameter (or an array `result`) of an integral or boolean element type is used as `a.length` and
//! `a[index]`, and quantified over with JML's syntax: `(\forall int i; 0 <= i && i < a.length; a[i] != key)` and
//! `(\exists int i; 0 <= i && i < a.length; a[i] == key)`. The range must bound the variable below and above
//! (`lo <= i`, `i < hi`, `i <= hi`, and so on, with `&&`); any other conjunct of the range filters. A quantifier
//! is compiled to a loop in the harness, which bounded model checking unwinds, and evaluated as a loop here.
//!
//! JML's generalized quantifiers have the same shape and fold a value instead: `(\sum int i; 0 <= i && i < n;
//! a[i])` adds (an `int` or a `long`, wrapping as Java does), `\num_of` counts the values of `i` for which a boolean
//! body holds (an `int`), and `\max` and `\min` take the extreme of a numeric body; over an empty range they are
//! 0, 0, the smallest value of the body's type and the largest, as in JML.
//!
//! A property reads an array parameter after the call, so `\old(a[i])` and `\old(a.length)` (JML's `\old`) are
//! the element and the length before it, from a copy the harness takes before the call; `\old(a)` passes that
//! copy to a call. That is how a method that writes into an array is held to what it changed and what it left:
//! `(\forall int i; result <= i && i < out.length; out[i] == \old(out[i]))` is a frame condition, and
//! `(\exists int j; 0 <= j && j < keys.length; keys[j] == \old(keys[i]))` says an element is kept.

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
    Call(Callee, Vec<CallArg>),
    /// `a.length` of an array parameter: its name and slot.
    Length(String, u16),
    /// `a[index]` of an array parameter: its name, slot, element type and the index.
    Index(String, u16, Type, Box<Expr>),
    /// `\forall int i; range; body` or `\exists ...`.
    Quantifier(Box<Quantifier>),
}

/// The quantifiers: the two boolean ones, and JML's generalized ones, which fold a value over the range.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Quant {
    Forall,
    Exists,
    Sum,
    NumOf,
    Max,
    Min,
}

impl Quant {
    pub fn keyword(self) -> &'static str {
        match self {
            Quant::Forall => "\\forall",
            Quant::Exists => "\\exists",
            Quant::Sum => "\\sum",
            Quant::NumOf => "\\num_of",
            Quant::Max => "\\max",
            Quant::Min => "\\min",
        }
    }

    /// Whether the body is a boolean (and the result a truth value or a count) rather than a number to fold.
    fn boolean_body(self) -> bool {
        matches!(self, Quant::Forall | Quant::Exists | Quant::NumOf)
    }
}

/// A bounded quantifier over an `int` variable.
#[derive(Debug, Clone, PartialEq)]
pub struct Quantifier {
    pub kind: Quant,
    pub var: String,
    /// The slot of the variable; the accumulator takes the two slots after it.
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

impl Quantifier {
    /// The type of the quantified expression: a truth value, a count, or the body's type.
    pub fn ty(&self) -> Ty {
        match self.kind {
            Quant::Forall | Quant::Exists => Ty::Boolean,
            Quant::NumOf => Ty::Int,
            Quant::Sum | Quant::Max | Quant::Min => self.body.ty(),
        }
    }
}

/// An argument of a call: a value, or an array parameter passed through by name (its name and slot).
#[derive(Debug, Clone, PartialEq)]
pub enum CallArg {
    Value(Expr),
    Array(String, u16),
}

impl CallArg {
    fn slots_used(&self) -> u16 {
        match self {
            CallArg::Value(e) => e.slots_used(),
            CallArg::Array(_, slot) => slot + 1,
        }
    }

    fn mentions(&self, slot: u16) -> bool {
        match self {
            CallArg::Value(e) => e.mentions(slot),
            CallArg::Array(_, s) => *s == slot,
        }
    }
}

/// A static method an expression may call: the method under proof, in a property.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Callee {
    pub name: String,
    /// The internal name of the class (`net/example/Clock`).
    pub owner: String,
    pub descriptor: String,
    /// The parameter types: integral, boolean, or arrays of those.
    pub params: Vec<Type>,
    pub ret: Ty,
}

impl Callee {
    /// The callee for a static method, if its parameters are integral, boolean or arrays of those, and its result
    /// is integral or boolean.
    pub fn of(owner: &str, name: &str, descriptor: &str, params: &[Type], ret: &Type) -> Option<Callee> {
        if !params.iter().all(|t| ty_of(t).is_some() || element_ty(t).is_some()) {
            return None;
        }
        Some(Callee { name: name.to_string(), owner: owner.to_string(), descriptor: descriptor.to_string(), params: params.to_vec(), ret: ty_of(ret)? })
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
            Expr::Quantifier(q) => q.ty(),
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
            Expr::Call(_, args) => args.iter().map(CallArg::slots_used).max().unwrap_or(0),
            Expr::Quantifier(q) => {
                let inner = q.lo.slots_used().max(q.hi.slots_used()).max(q.body.slots_used()).max(q.filter.as_ref().map(Expr::slots_used).unwrap_or(0));
                (q.slot + 3).max(inner)
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

    /// Whether the expression passes the array in `slot` to a call, which sees its whole length.
    pub fn passes(&self, slot: u16) -> bool {
        match self {
            Expr::Int(_) | Expr::Long(_) | Expr::Bool(_) | Expr::Var(..) | Expr::Length(..) => false,
            Expr::Index(_, _, _, index) => index.passes(slot),
            Expr::Neg(e) | Expr::Not(e) | Expr::BitNot(e) | Expr::Cast(_, e) => e.passes(slot),
            Expr::Binary(_, l, r) => l.passes(slot) || r.passes(slot),
            Expr::Ternary(c, t, e) => c.passes(slot) || t.passes(slot) || e.passes(slot),
            Expr::Call(_, args) => args.iter().any(|a| match a {
                CallArg::Value(e) => e.passes(slot),
                CallArg::Array(_, s) => *s == slot,
            }),
            Expr::Quantifier(q) => q.lo.passes(slot) || q.hi.passes(slot) || q.body.passes(slot) || q.filter.as_ref().is_some_and(|f| f.passes(slot)),
        }
    }

    /// Whether the expression reads the local in `slot`.
    pub fn mentions(&self, slot: u16) -> bool {
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
    /// `\forall`, `\exists`, `\sum`, `\num_of`, `\max` or `\min`.
    Quantifier(Quant),
    /// `\old`.
    Old,
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
            while i < chars.len() && (chars[i].is_ascii_alphabetic() || chars[i] == '_') {
                i += 1;
            }
            let word: String = chars[start..i].iter().collect();
            match word.as_str() {
                "forall" => tokens.push(Token::Quantifier(Quant::Forall)),
                "exists" => tokens.push(Token::Quantifier(Quant::Exists)),
                "sum" => tokens.push(Token::Quantifier(Quant::Sum)),
                "num_of" => tokens.push(Token::Quantifier(Quant::NumOf)),
                "max" => tokens.push(Token::Quantifier(Quant::Max)),
                "min" => tokens.push(Token::Quantifier(Quant::Min)),
                "old" => tokens.push(Token::Old),
                _ => return Err(Error::new(format!("unknown \\{word} in expression; the quantifiers are \\forall, \\exists, \\sum, \\num_of, \\max and \\min, and \\old(a[i]) is an element before the call"))),
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
    /// Where `\old` is allowed, the slot of the copy of each array parameter taken before the call, by the
    /// parameter's slot.
    old: Option<&'a [(u16, u16)]>,
    /// Whether the parser is inside `\old(...)`.
    in_old: bool,
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

    /// The name and slot an array parameter is read from: its own, or inside `\old`, its copy's, shown as
    /// `\old(a)`.
    fn array_state(&self, name: String, slot: u16) -> Result<(String, u16), Error> {
        if !self.in_old {
            return Ok((name, slot));
        }
        let copy = self.old.and_then(|old| old.iter().find(|(s, _)| *s == slot)).map(|(_, copy)| *copy).ok_or_else(|| Error::new(format!("no copy of {name} is taken before the call")))?;
        Ok((format!("\\old({name})"), copy))
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
        if let Token::Quantifier(kind) = self.peek().clone() {
            self.next();
            return self.quantifier(kind);
        }
        if self.peek() == &Token::Old {
            self.next();
            require(self.old.is_some(), "\\old is only meaningful in the assertion, which is checked after the call")?;
            require(!self.in_old, "\\old inside \\old")?;
            self.expect("(")?;
            self.in_old = true;
            let e = self.ternary();
            self.in_old = false;
            let e = e?;
            self.expect(")")?;
            return Ok(e);
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
                            // An array parameter is passed by name; anything else is a value.
                            let array = match (&self.tokens[self.pos], &self.tokens[self.pos + 1]) {
                                (Token::Ident(a), Token::Op(",") | Token::Op(")")) => self.params.iter().find(|p| p.name == *a && matches!(p.ty, Type::Array(_))).map(|p| (p.name.clone(), p.slot, p.ty.clone())),
                                _ => None,
                            };
                            let old = match (&self.tokens[self.pos], self.tokens.get(self.pos + 1), self.tokens.get(self.pos + 2), self.tokens.get(self.pos + 3)) {
                                (Token::Old, Some(Token::Op("(")), Some(Token::Ident(a)), Some(Token::Op(")"))) if !self.in_old => self.params.iter().find(|p| p.name == *a && matches!(p.ty, Type::Array(_))).map(|p| (p.name.clone(), p.slot, p.ty.clone())),
                                _ => None,
                            };
                            match (array, old) {
                                (Some((a, slot, ty)), _) => {
                                    self.next();
                                    let (a, slot) = self.array_state(a, slot)?;
                                    args.push((CallArg::Array(a, slot), Some(ty)));
                                }
                                (None, Some((a, slot, ty))) => {
                                    require(self.old.is_some(), "\\old is only meaningful in the assertion, which is checked after the call")?;
                                    self.pos += 4;
                                    self.in_old = true;
                                    let state = self.array_state(a, slot);
                                    self.in_old = false;
                                    let (a, slot) = state?;
                                    args.push((CallArg::Array(a, slot), Some(ty)));
                                }
                                (None, None) => args.push((CallArg::Value(self.ternary()?), None)),
                            }
                            if self.eat(")") {
                                break;
                            }
                            if !self.eat(",") {
                                return Err(Error::new(format!("expected \",\" or \")\" in the arguments of {name}, found {:?}", self.peek())));
                            }
                        }
                    }
                    require(args.len() == callee.params.len(), &format!("{name} takes {} arguments, {} given", callee.params.len(), args.len()))?;
                    for (i, ((arg, array_ty), param)) in args.iter().zip(&callee.params).enumerate() {
                        let ok = match (ty_of(param), arg) {
                            (Some(Ty::Boolean), CallArg::Value(e)) => e.ty() == Ty::Boolean,
                            (Some(Ty::Int), CallArg::Value(e)) => e.ty() == Ty::Int,
                            (Some(Ty::Long), CallArg::Value(e)) => e.ty() != Ty::Boolean,
                            (None, CallArg::Array(..)) => array_ty.as_ref() == Some(param),
                            _ => false,
                        };
                        require(ok, &format!("argument {} of {name} must be {}", i + 1, match ty_of(param) { Some(Ty::Boolean) => "boolean".to_string(), Some(Ty::Int) => "int".to_string(), Some(Ty::Long) => "a number".to_string(), None => format!("the {} parameter {}", param.java_name(), self.params.iter().find(|p| p.ty == *param).map(|p| p.name.as_str()).unwrap_or("itself")) }))?;
                    }
                    Ok(Expr::Call(callee.clone(), args.into_iter().map(|(a, _)| a).collect()))
                }
                _ => {
                    if let Some(bound) = self.scope.iter().rev().find(|p| p.name == name) {
                        return Ok(Expr::Var(name, Ty::Int, bound.slot));
                    }
                    let param = self.params.iter().find(|p| p.name == name).ok_or_else(|| Error::new(format!("unknown name {name:?}; the names are {}", self.params.iter().map(|p| p.name.as_str()).collect::<Vec<_>>().join(", "))))?;
                    if self.in_old && name == "result" {
                        return Err(Error::new("result has no value before the call; \\old applies to the parameters"));
                    }
                    if let Type::Array(element) = &param.ty {
                        let element = (**element).clone();
                        element_ty(&param.ty).ok_or_else(|| Error::new(format!("parameter {name} has type {}; only arrays of integral or boolean elements can appear in the expression", param.ty.java_name())))?;
                        let (shown, slot) = self.array_state(name.clone(), param.slot)?;
                        if self.eat(".") {
                            match self.next() {
                                // A length does not change, so \old(a.length) is a.length, read from the array itself.
                                Token::Ident(field) if field == "length" => return Ok(Expr::Length(name, param.slot)),
                                other => return Err(Error::new(format!("expected {name}.length, found {other:?}"))),
                            }
                        }
                        if self.eat("[") {
                            // The index is a value of the pre-state too, but every value it can name is unchanged
                            // by the call, so it is parsed as any other expression.
                            let index = self.ternary()?;
                            require(index.ty() == Ty::Int, &format!("the index of {name} must be an int"))?;
                            self.expect("]")?;
                            return Ok(Expr::Index(shown, slot, element, Box::new(index)));
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

    /// `int i; range; body`, after `\forall`, `\exists`, `\sum`, `\num_of`, `\max` or `\min`.
    fn quantifier(&mut self, kind: Quant) -> Result<Expr, Error> {
        let keyword = kind.keyword();
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
        self.next_slot += 3;
        self.scope.push(Param { name: var.clone(), ty: Type::Int, slot });
        let range = self.ternary();
        let body = range.as_ref().ok().map(|_| self.expect(";").and_then(|()| self.ternary()));
        self.scope.pop();
        let range = range?;
        let body = body.expect("parsed after the range")?;
        require(range.ty() == Ty::Boolean, &format!("the range of {var} must be boolean"))?;
        if kind.boolean_body() {
            require(body.ty() == Ty::Boolean, &format!("the body of {keyword} must be boolean"))?;
        } else {
            require(body.ty() != Ty::Boolean, &format!("the body of {keyword} must be a number"))?;
        }
        let (lo, hi, inclusive, filter) = bounds(range, &var, slot)?;
        Ok(Expr::Quantifier(Box::new(Quantifier { kind, var, slot, lo, hi, inclusive, filter, body })))
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
    let expr = parse_value(src, params, callee, first_free_slot)?;
    if expr.ty() != Ty::Boolean {
        return Err(Error::new("the expression must be boolean"));
    }
    Ok(expr)
}

/// As [`parse_in`], for an expression of any type.
pub fn parse_value(src: &str, params: &[Param], callee: Option<&Callee>, first_free_slot: u16) -> Result<Expr, Error> {
    parse_after(src, params, callee, first_free_slot, None)
}

/// As [`parse_value`], for an expression checked after a call: `old` gives, by an array parameter's slot, the
/// slot of the copy of it taken before the call, which `\old(a[i])` and `\old(a.length)` read; without it,
/// `\old` is an error.
pub fn parse_after(src: &str, params: &[Param], callee: Option<&Callee>, first_free_slot: u16, old: Option<&[(u16, u16)]>) -> Result<Expr, Error> {
    let tokens = lex(src)?;
    let mut parser = Parser { tokens, pos: 0, params, callee, scope: Vec::new(), next_slot: first_free_slot, old, in_old: false };
    let expr = parser.ternary()?;
    if parser.peek() != &Token::End {
        return Err(Error::new(format!("unexpected {:?} after the expression", parser.peek())));
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
            let wide = q.ty() == Ty::Long;
            let wrap = |v: i64| if wide { Value::Long(v) } else { Value::Int(v as i32) };
            let forall = q.kind == Quant::Forall;
            let mut acc: i64 = match q.kind {
                Quant::Forall => 1,
                Quant::Exists | Quant::Sum | Quant::NumOf => 0,
                Quant::Max => if wide { i64::MIN } else { i64::from(i32::MIN) },
                Quant::Min => if wide { i64::MAX } else { i64::from(i32::MAX) },
            };
            let mut i = i64::from(lo);
            while i < end {
                locals[usize::from(q.slot)] = Value::Int(i as i32);
                let selected = match &q.filter {
                    Some(f) => eval_in(f, locals, arrays)?.as_int() != 0,
                    None => true,
                };
                if selected {
                    let v = as_i64(eval_in(&q.body, locals, arrays)?);
                    match q.kind {
                        Quant::Forall | Quant::Exists => {
                            if (v != 0) != forall {
                                return Ok(Value::Int((!forall) as i32));
                            }
                        }
                        Quant::NumOf => acc += (v != 0) as i64,
                        Quant::Sum => acc = if wide { acc.wrapping_add(v) } else { i64::from((acc as i32).wrapping_add(v as i32)) },
                        Quant::Max => acc = acc.max(v),
                        Quant::Min => acc = acc.min(v),
                    }
                }
                i += 1;
            }
            wrap(acc)
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
            // The variable in q.slot, the accumulator after it: a loop from lo to hi that folds the body.
            let acc = q.slot + 1;
            let ty = q.ty();
            let acc_kind = if ty == Ty::Long { Kind::Long } else { Kind::Int };
            let loop_ = code.label();
            let next = code.label();
            let end = code.label();
            match (q.kind, ty) {
                (Quant::Forall, _) => code.iconst(1),
                (Quant::Exists | Quant::NumOf, _) => code.iconst(0),
                (Quant::Sum, Ty::Long) => emit_long(0, code, pool),
                (Quant::Sum, _) => code.iconst(0),
                (Quant::Max, Ty::Long) => emit_long(i64::MIN, code, pool),
                (Quant::Max, _) => emit_int(i32::MIN, code, pool),
                (Quant::Min, Ty::Long) => emit_long(i64::MAX, code, pool),
                (Quant::Min, _) => emit_int(i32::MAX, code, pool),
            }
            code.store(acc_kind, acc);
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
            match q.kind {
                Quant::Forall | Quant::Exists => {
                    let forall = q.kind == Quant::Forall;
                    emit(&q.body, code, pool);
                    code.if_zero(if forall { Cond::Ne } else { Cond::Eq }, next);
                    code.iconst((!forall) as i32);
                    code.store(Kind::Int, acc);
                    code.goto(end);
                }
                Quant::NumOf => {
                    emit(&q.body, code, pool);
                    code.if_zero(Cond::Eq, next);
                    code.iinc(acc, 1);
                }
                Quant::Sum => {
                    code.load(acc_kind, acc);
                    emit_promoted(&q.body, ty, code, pool);
                    code.op(if ty == Ty::Long { 0x61 } else { 0x60 }); // ladd / iadd
                    code.store(acc_kind, acc);
                }
                Quant::Max | Quant::Min => {
                    // Keep the body's value when it beats the accumulator, else drop it.
                    let keep = code.label();
                    let cond = if q.kind == Quant::Max { Cond::Gt } else { Cond::Lt };
                    emit_promoted(&q.body, ty, code, pool);
                    if ty == Ty::Long {
                        code.op(0x5c); // dup2
                        code.load(Kind::Long, acc);
                        code.op(0x94); // lcmp
                        code.if_zero(cond, keep);
                        code.op(0x58); // pop2
                    } else {
                        code.op(0x59); // dup
                        code.load(Kind::Int, acc);
                        code.if_icmp(cond, keep);
                        code.op(0x57); // pop
                    }
                    code.goto(next);
                    code.bind(keep);
                    code.store(acc_kind, acc);
                }
            }
            code.bind(next);
            code.iinc(q.slot, 1);
            code.goto(loop_);
            code.bind(end);
            code.load(acc_kind, acc);
        }
        Expr::Call(callee, args) => {
            for (arg, param) in args.iter().zip(&callee.params) {
                match arg {
                    CallArg::Value(e) => emit_promoted(e, ty_of(param).unwrap_or(Ty::Int), code, pool),
                    CallArg::Array(_, slot) => code.load(Kind::Ref, *slot),
                }
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

    const RESULT_NAME: &str = "result";

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
        assert_eq!(even.slots_used(), 5);
        let distinct = parse_in("\\forall int i; 0 <= i && i < a.length; \\forall int j; i < j && j < a.length; a[i] != a[j]", &params, None, 2).unwrap();
        assert_eq!(eval_with(&distinct, &locals(0), &arrays(&[1, 2, 3])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&distinct, &locals(0), &arrays(&[1, 2, 1])).unwrap(), Value::Int(0));
        assert_eq!(distinct.slots_used(), 8);
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
    fn reads_the_pre_state_under_old() {
        let params = vec![Param { name: "a".into(), ty: Type::Array(Box::new(Type::Int)), slot: 0 }, Param { name: "n".into(), ty: Type::Int, slot: 1 }, Param { name: RESULT_NAME.into(), ty: Type::Int, slot: 2 }];
        let copies = [(0u16, 4u16)];
        let locals = |n, r| vec![Value::Null, Value::Int(n), Value::Int(r), Value::Int(0), Value::Null];
        let arrays = |after: &[i32], before: &[i32]| vec![(0u16, after.iter().map(|v| Value::Int(*v)).collect::<Vec<_>>()), (4u16, before.iter().map(|v| Value::Int(*v)).collect::<Vec<_>>())];
        let reversed = parse_after("\\forall int i; 0 <= i && i < a.length; a[i] == \\old(a[a.length - 1 - i])", &params, None, 5, Some(&copies)).unwrap();
        assert!(reversed.mentions(4) && !reversed.mentions(3));
        assert_eq!(eval_with(&reversed, &locals(0, 0), &arrays(&[3, 2, 1], &[1, 2, 3])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&reversed, &locals(0, 0), &arrays(&[1, 2, 3], &[1, 2, 3])).unwrap(), Value::Int(0));
        let frame = parse_after("(\\forall int i; n <= i && i < \\old(a.length); a[i] == \\old(a[i])) && \\old(n) == n", &params, None, 5, Some(&copies)).unwrap();
        assert!(!parse_after("\\old(a.length) == n", &params, None, 5, Some(&copies)).unwrap().mentions(4), "a length is read from the array itself");
        assert_eq!(eval_with(&frame, &locals(1, 0), &arrays(&[0, 2], &[1, 2])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&frame, &locals(1, 0), &arrays(&[1, 0], &[1, 2])).unwrap(), Value::Int(0));
        let kept = parse_after("\\forall int i; 0 <= i && i < a.length; \\exists int j; 0 <= j && j < a.length; a[j] == \\old(a[i])", &params, None, 5, Some(&copies)).unwrap();
        assert_eq!(eval_with(&kept, &locals(0, 0), &arrays(&[2, 1], &[1, 2])).unwrap(), Value::Int(1));
        assert_eq!(eval_with(&kept, &locals(0, 0), &arrays(&[2, 2], &[1, 2])).unwrap(), Value::Int(0));
        let plain = parse_after("a[0] == 1", &params, None, 5, Some(&copies)).unwrap();
        assert!(!plain.mentions(4), "no copy is needed");
        assert!(parse_after("\\old(a[0]) == 1", &params, None, 5, None).unwrap_err().to_string().contains("after the call"), "not in an assumption");
        assert!(parse_after("\\old(\\old(a[0])) == 1", &params, None, 5, Some(&copies)).is_err(), "nested");
        assert!(parse_after("\\old(result) == 1", &params, None, 5, Some(&copies)).unwrap_err().to_string().contains("result has no value before the call"));
        assert!(parse_after("\\old a[0] == 1", &params, None, 5, Some(&copies)).is_err(), "parentheses");
        let callee = Callee::of("net/example/InPlace", "sum", "([I)I", &[Type::Array(Box::new(Type::Int))], &Type::Int).unwrap();
        let law = parse_after("sum(\\old(a)) == sum(a)", &params, Some(&callee), 5, Some(&copies)).unwrap();
        assert_eq!(law, Expr::Binary(BinOp::Eq, Box::new(Expr::Call(callee.clone(), vec![CallArg::Array("\\old(a)".into(), 4)])), Box::new(Expr::Call(callee, vec![CallArg::Array("a".into(), 0)]))));
        assert!(law.passes(4) && !reversed.passes(4));
    }

    #[test]
    fn folds_generalized_quantifiers() {
        let params = vec![Param { name: "a".into(), ty: Type::Array(Box::new(Type::Int)), slot: 0 }, Param { name: "n".into(), ty: Type::Int, slot: 1 }, Param { name: "w".into(), ty: Type::Array(Box::new(Type::Long)), slot: 2 }];
        let arrays = |data: &[i32]| vec![(0u16, data.iter().map(|v| Value::Int(*v)).collect::<Vec<_>>()), (2u16, data.iter().map(|v| Value::Long(i64::from(*v) * 3_000_000_000)).collect::<Vec<_>>())];
        let locals = |n| vec![Value::Null, Value::Int(n), Value::Null];
        let sum = parse_value("(\\sum int i; 0 <= i && i < n; a[i])", &params, None, 3).unwrap();
        assert_eq!(sum.ty(), Ty::Int);
        assert_eq!(eval_with(&sum, &locals(3), &arrays(&[1, 2, 4])).unwrap(), Value::Int(7));
        assert_eq!(eval_with(&sum, &locals(2), &arrays(&[1, 2, 4])).unwrap(), Value::Int(3));
        assert_eq!(eval_with(&sum, &locals(0), &arrays(&[1, 2, 4])).unwrap(), Value::Int(0), "an empty sum");
        let wide = parse_value("(\\sum int i; 0 <= i && i < w.length; w[i])", &params, None, 3).unwrap();
        assert_eq!(wide.ty(), Ty::Long);
        assert_eq!(eval_with(&wide, &locals(0), &arrays(&[1, 1])).unwrap(), Value::Long(6_000_000_000));
        let wrapped = parse_in("(\\sum int i; 0 <= i && i < a.length; a[i]) == 2147483647 + 1", &params, None, 3).unwrap();
        assert_eq!(eval_with(&wrapped, &locals(0), &arrays(&[2147483647, 1])).unwrap(), Value::Int(1), "wraps as Java does");
        let count = parse_value("(\\num_of int i; 0 <= i && i < a.length; a[i] % 2 == 0)", &params, None, 3).unwrap();
        assert_eq!(count.ty(), Ty::Int);
        assert_eq!(eval_with(&count, &locals(0), &arrays(&[1, 2, 4, 5])).unwrap(), Value::Int(2));
        let max = parse_value("(\\max int i; 0 <= i && i < a.length; a[i])", &params, None, 3).unwrap();
        assert_eq!(eval_with(&max, &locals(0), &arrays(&[3, 9, -2])).unwrap(), Value::Int(9));
        assert_eq!(eval_with(&max, &locals(0), &arrays(&[])).unwrap(), Value::Int(i32::MIN), "the smallest int over an empty range");
        let min = parse_value("(\\min int i; 0 <= i && i < w.length; w[i])", &params, None, 3).unwrap();
        assert_eq!(eval_with(&min, &locals(0), &arrays(&[3, -2, 9])).unwrap(), Value::Long(-6_000_000_000));
        assert_eq!(eval_with(&min, &locals(0), &arrays(&[])).unwrap(), Value::Long(i64::MAX));
        // The prefix-depth law of a stack machine: the deepest point is the largest prefix sum, 0 included.
        let depth = parse_value("(\\max int k; 0 <= k && k <= a.length; (\\sum int i; 0 <= i && i < k; a[i]))", &params, None, 3).unwrap();
        assert_eq!(eval_with(&depth, &locals(0), &arrays(&[2, -1, 3, -4])).unwrap(), Value::Int(4));
        assert_eq!(eval_with(&depth, &locals(0), &arrays(&[-1])).unwrap(), Value::Int(0));
        assert_eq!(depth.slots_used(), 9);
        assert!(parse_in("(\\sum int i; 0 <= i && i < n; a[i] > 0)", &params, None, 3).is_err(), "a sum of booleans");
        assert!(parse_in("(\\num_of int i; 0 <= i && i < n; a[i])", &params, None, 3).is_err(), "a count of numbers");
        assert!(parse_in("(\\sum int i; 0 <= i && i < n; a[i]) && true", &params, None, 3).is_err(), "a sum is not boolean");
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

        // An array parameter is passed through by name.
        let ints = Type::Array(Box::new(Type::Int));
        let callee = Callee::of("net/example/Table", "offsetOf", "([II)I", &[ints.clone(), Type::Int], &Type::Int).unwrap();
        let params = vec![Param { name: "deltas".into(), ty: ints.clone(), slot: 0 }, Param { name: "k".into(), ty: Type::Int, slot: 1 }, Param { name: "result".into(), ty: Type::Int, slot: 2 }];
        let law = parse_with("k == 0 || result > offsetOf(deltas, k - 1)", &params, Some(&callee)).unwrap();
        assert!(law.has_call());
        assert_eq!(law.slots_used(), 3);
        assert!(parse_with("result > offsetOf(k, k)", &params, Some(&callee)).is_err(), "a number for the array");
        assert!(parse_with("result > offsetOf(deltas, deltas)", &params, Some(&callee)).is_err(), "the array for a number");
        assert!(Callee::of("X", "f", "([F)I", &[Type::Array(Box::new(Type::Float))], &Type::Int).is_none(), "float arrays are not expressible");
    }
}
