//! The developer's declaration of a change's scope: a Java boolean expression over the method's parameters, such
//! as `seats >= 8 && priceCents > 0`. It is parsed and type-checked here with Java's rules (binary numeric
//! promotion, operator precedence), compiled to bytecode for the harness, and evaluated in Rust to check a
//! replayed counterexample against it.
//!
//! Supported: `int`/`long`/`short`/`byte`/`char`/`boolean` parameters, integer literals (decimal, hex, binary,
//! with `L` and `_`), `true`/`false`, parentheses, casts `(int)`/`(long)`, unary `- ! ~`, and the binary
//! operators `* / % + - << >> >>> < > <= >= == != & ^ | && ||` and `?:`.

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
}

impl Expr {
    /// The static type, by Java's promotion rules.
    pub fn ty(&self) -> Ty {
        match self {
            Expr::Int(_) => Ty::Int,
            Expr::Long(_) => Ty::Long,
            Expr::Bool(_) => Ty::Boolean,
            Expr::Var(_, t, _) => *t,
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
    End,
}

const OPS: &[&str] = &[">>>=", ">>>", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "(", ")", "+", "-", "*", "/", "%", "<", ">", "!", "~", "&", "^", "|", "?", ":"];

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
                _ => {
                    let param = self.params.iter().find(|p| p.name == name).ok_or_else(|| Error::new(format!("unknown name {name:?}; the parameters are {}", self.params.iter().map(|p| p.name.as_str()).collect::<Vec<_>>().join(", "))))?;
                    let t = ty_of(&param.ty).ok_or_else(|| Error::new(format!("parameter {name} has type {}; only integral and boolean parameters can appear in the expression", param.ty.java_name())))?;
                    Ok(Expr::Var(name, t, param.slot))
                }
            },
            other => Err(Error::new(format!("unexpected {other:?} in expression"))),
        }
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
    let tokens = lex(src)?;
    let mut parser = Parser { tokens, pos: 0, params };
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
    Ok(match expr {
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
        Expr::Neg(e) => match eval(e, locals)? {
            Value::Int(x) => Value::Int(x.wrapping_neg()),
            Value::Long(x) => Value::Long(x.wrapping_neg()),
            v => v,
        },
        Expr::Not(e) => Value::Int((eval(e, locals)?.as_int() == 0) as i32),
        Expr::BitNot(e) => match eval(e, locals)? {
            Value::Int(x) => Value::Int(!x),
            Value::Long(x) => Value::Long(!x),
            v => v,
        },
        Expr::Cast(Ty::Int, e) => Value::Int(as_i64(eval(e, locals)?) as i32),
        Expr::Cast(_, e) => Value::Long(as_i64(eval(e, locals)?)),
        Expr::Ternary(c, t, e) => {
            if eval(c, locals)?.as_int() != 0 {
                eval(t, locals)?
            } else {
                eval(e, locals)?
            }
        }
        Expr::Binary(op, l, r) => {
            if *op == BinOp::LogAnd {
                return Ok(Value::Int((eval(l, locals)?.as_int() != 0 && eval(r, locals)?.as_int() != 0) as i32));
            }
            if *op == BinOp::LogOr {
                return Ok(Value::Int((eval(l, locals)?.as_int() != 0 || eval(r, locals)?.as_int() != 0) as i32));
            }
            let (a, b) = (eval(l, locals)?, eval(r, locals)?);
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
    }
}
