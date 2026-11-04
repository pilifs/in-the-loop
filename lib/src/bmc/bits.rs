//! Bit-blasting: machine integers as vectors of propositional literals, and the JVM's arithmetic as circuits over
//! them, fed to a SAT solver clause by clause as they are built. A value is a `Vec<Lit>` of its bits, least
//! significant first; a bit that is known is one of two constant literals, so that arithmetic over constants
//! folds away and only what depends on an input reaches the solver.

use std::collections::HashMap;
use std::fmt;

/// A propositional literal: a positive or negative variable number, as a SAT solver numbers them.
pub type Lit = i32;

/// The constant true: variable 1, asserted by a unit clause when the solver is made.
pub const TRUE: Lit = 1;
pub const FALSE: Lit = -1;

/// A machine integer of some width, as bits, least significant first.
pub type Bits = Vec<Lit>;

/// What a variable is: an input, chosen freely (a parameter's bit), or a gate over earlier literals. Every
/// clause the solver holds defines a gate, so any choice of the inputs extends to exactly one model, and a model
/// is kept as the inputs' values alone ([`Model`]).
#[derive(Clone, Copy)]
enum Def {
    Input,
    And(Lit, Lit),
    Xor(Lit, Lit),
    Ite(Lit, Lit, Lit),
    /// An output bit of a division left to the solver ([`Lazy`]), by the division's index.
    Lazy(u32),
}

/// A division or multiplication whose circuit is not built unless it is needed: its result (quotient and
/// remainder, or product) is fresh bits that the solver chooses under the cheap facts of
/// [`Blaster::division_facts`] or [`Blaster::multiplication_facts`] (the remainder is smaller than the divisor and
/// takes the dividend's sign, a division by one is the dividend, a product by a power of two is a shift, and so
/// on), which every real operation satisfies. A proof that goes through under the facts alone holds; a model the
/// solver gives is checked against the real operation on the values it chose, and when they differ the circuit is
/// built and tied to the bits ([`Blaster::refine_operation`]), so that the solver is never believed on an
/// operation it got wrong. A 64-bit division or multiplication is a circuit of some ten thousand gates that a
/// proof seldom needs in full: both versions of a method mostly use the same remainder or product, or compare it
/// with something the facts decide.
struct Lazy {
    op: Op,
    a: Bits,
    b: Bits,
    /// The quotient, or the product.
    q: Bits,
    /// The remainder; empty for a product.
    r: Bits,
    refined: bool,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Op {
    DivRem,
    Mul,
}

/// The real result of an operation left to the solver on the values: the quotient and remainder, or the product
/// and zero.
fn real_operation(op: Op, width: usize, a: i64, b: i64) -> (i64, i64) {
    match op {
        Op::DivRem => real_division(width, a, b),
        Op::Mul => (real_product(width, a, b), 0),
    }
}

/// `imul`/`lmul`: the product modulo the width.
fn real_product(width: usize, a: i64, b: i64) -> i64 {
    if width == 32 { i64::from((a as i32).wrapping_mul(b as i32)) } else { a.wrapping_mul(b) }
}

/// `idiv`/`irem` and `ldiv`/`lrem` of two values of the width: the quotient truncates toward zero, the remainder
/// takes the dividend's sign, `MIN_VALUE / -1` wraps. A division by zero, which the JVM throws on, gives the
/// hardware's all-ones quotient and the dividend as remainder.
fn real_division(width: usize, a: i64, b: i64) -> (i64, i64) {
    if b == 0 {
        return (-1, a);
    }
    if width == 32 {
        let (a, b) = (a as i32, b as i32);
        (i64::from(a.wrapping_div(b)), i64::from(a.wrapping_rem(b)))
    } else {
        (a.wrapping_div(b), a.wrapping_rem(b))
    }
}

/// A value's bits in a model, sign-extended; `None` unless every bit has a value.
fn value_in(model: &Model, bits: &Bits) -> Option<i64> {
    let mut v: u64 = 0;
    for (i, &l) in bits.iter().enumerate() {
        if model.lit(l)? {
            v |= 1 << i;
        }
    }
    let width = bits.len();
    if width < 64 && v & (1 << (width - 1)) != 0 {
        v |= u64::MAX << width;
    }
    Some(v as i64)
}

/// A model of the circuits, kept by the path it satisfies: the inputs' values as the solver chose them, and the
/// values of the gates evaluated so far. A gate made after the model was taken is evaluated from its inputs when
/// it is asked for, and an input made after it is free, so the model stays a model of every clause.
#[derive(Clone, Default)]
pub struct Model {
    known: Vec<u64>,
    value: Vec<u64>,
}

impl Model {
    fn get(&self, v: usize) -> Option<bool> {
        let (word, bit) = (v / 64, v % 64);
        if self.known.get(word).is_some_and(|w| w >> bit & 1 == 1) {
            Some(self.value[word] >> bit & 1 == 1)
        } else {
            None
        }
    }

    fn set(&mut self, v: usize, b: bool) {
        let (word, bit) = (v / 64, v % 64);
        if word >= self.known.len() {
            self.known.resize(word + 1, 0);
            self.value.resize(word + 1, 0);
        }
        self.known[word] |= 1 << bit;
        if b {
            self.value[word] |= 1 << bit;
        } else {
            self.value[word] &= !(1 << bit);
        }
    }

    /// A literal's value, if its variable has one.
    fn lit(&self, l: Lit) -> Option<bool> {
        if is_const(l) {
            return Some(l == TRUE);
        }
        self.get(l.unsigned_abs() as usize).map(|b| b == (l > 0))
    }
}

/// The solver with the circuits built over it.
pub struct Blaster {
    solver: cadical::Solver,
    next: i32,
    /// What each variable is, by number (0 is no variable, 1 the constant true).
    defs: Vec<Def>,
    /// Gates already built, by operation and inputs, so that the same function of the same inputs is one
    /// variable: two copies of a circuit (the method's own multiplication and the harness's check of it, say)
    /// then fold to the same literals, and their comparison to a constant.
    gates: HashMap<(u8, Lit, Lit, Lit), Lit>,
    /// The divisions and multiplications left to the solver, and which one is of which operands, so that the
    /// same operation on the same values is the same bits (a product's operands in either order).
    lazy: Vec<Lazy>,
    divisions: HashMap<(Bits, Bits), usize>,
    products: HashMap<(Bits, Bits), usize>,
    /// How many clauses have been added, for reporting.
    pub clauses: u64,
    /// How many times the solver was asked, for reporting, and the time it took.
    pub solves: u64,
    pub solving: std::time::Duration,
    /// How many gates were evaluated in a path's model, and the time it took.
    pub evaluated: u64,
    pub evaluating: std::time::Duration,
}

impl fmt::Debug for Blaster {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Blaster({} variables, {} clauses)", self.next - 1, self.clauses)
    }
}

fn is_const(l: Lit) -> bool {
    l == TRUE || l == FALSE
}

impl Default for Blaster {
    fn default() -> Self {
        Self::new()
    }
}

impl Blaster {
    pub fn new() -> Blaster {
        let mut b = Blaster { solver: cadical::Solver::new(), next: 2, defs: vec![Def::Input, Def::Input], gates: HashMap::new(), lazy: Vec::new(), divisions: HashMap::new(), products: HashMap::new(), clauses: 0, solves: 0, solving: std::time::Duration::ZERO, evaluated: 0, evaluating: std::time::Duration::ZERO };
        b.clause(&[TRUE]);
        b
    }

    /// Stops the solver after this many seconds on any one call.
    pub fn set_timeout(&mut self, seconds: f32) {
        self.solver.set_callbacks(Some(cadical::Timeout::new(seconds)));
    }

    fn clause(&mut self, lits: &[Lit]) {
        self.solver.add_clause(lits.iter().copied());
        self.clauses += 1;
    }

    /// A fresh variable: an input.
    pub fn var(&mut self) -> Lit {
        let v = self.next;
        self.next += 1;
        self.defs.push(Def::Input);
        v
    }

    /// A fresh variable that is a gate.
    fn gate(&mut self, def: Def) -> Lit {
        let o = self.var();
        self.defs[o as usize] = def;
        o
    }

    pub fn variables(&self) -> i32 {
        self.next - 1
    }

    /// `width` fresh bits.
    pub fn fresh(&mut self, width: usize) -> Bits {
        (0..width).map(|_| self.var()).collect()
    }

    /// A constant of the width.
    pub fn constant(&self, value: i64, width: usize) -> Bits {
        (0..width).map(|i| if (value >> i.min(63)) & 1 == 1 { TRUE } else { FALSE }).collect()
    }

    /// The value of bits that are all constant, sign-extended; `None` when any bit is a variable.
    pub fn constant_value(&self, bits: &Bits) -> Option<i64> {
        if bits.iter().any(|&l| !is_const(l)) {
            return None;
        }
        let mut v: u64 = 0;
        for (i, &l) in bits.iter().enumerate() {
            if l == TRUE {
                v |= 1 << i;
            }
        }
        let width = bits.len();
        if width < 64 && v & (1 << (width - 1)) != 0 {
            v |= u64::MAX << width;
        }
        Some(v as i64)
    }

    // Gates, with constant folding.

    pub fn not(&self, a: Lit) -> Lit {
        -a
    }

    pub fn and(&mut self, a: Lit, b: Lit) -> Lit {
        if a == FALSE || b == FALSE || a == -b {
            return FALSE;
        }
        if a == TRUE || a == b {
            return b;
        }
        if b == TRUE {
            return a;
        }
        let key = (0, a.min(b), a.max(b), 0);
        if let Some(&o) = self.gates.get(&key) {
            return o;
        }
        let o = self.gate(Def::And(a, b));
        self.clause(&[-o, a]);
        self.clause(&[-o, b]);
        self.clause(&[o, -a, -b]);
        self.gates.insert(key, o);
        o
    }

    pub fn or(&mut self, a: Lit, b: Lit) -> Lit {
        -self.and(-a, -b)
    }

    pub fn xor(&mut self, a: Lit, b: Lit) -> Lit {
        if a == FALSE {
            return b;
        }
        if b == FALSE {
            return a;
        }
        if a == TRUE {
            return -b;
        }
        if b == TRUE {
            return -a;
        }
        if a == b {
            return FALSE;
        }
        if a == -b {
            return TRUE;
        }
        // xor(a, b) = xor(-a, -b) = -xor(-a, b): one gate over the two variables, signed by the inputs' signs.
        let (x, y) = if a.abs() <= b.abs() { (a, b) } else { (b, a) };
        let flip = (x < 0) != (y < 0);
        let key = (1, x.abs(), y.abs(), 0);
        let o = match self.gates.get(&key) {
            Some(&o) => o,
            None => {
                let (x, y) = (x.abs(), y.abs());
                let o = self.gate(Def::Xor(x, y));
                self.clause(&[-o, x, y]);
                self.clause(&[-o, -x, -y]);
                self.clause(&[o, -x, y]);
                self.clause(&[o, x, -y]);
                self.gates.insert(key, o);
                o
            }
        };
        if flip { -o } else { o }
    }

    /// `if c then a else b`.
    pub fn ite(&mut self, c: Lit, a: Lit, b: Lit) -> Lit {
        if c == TRUE || a == b {
            return a;
        }
        if c == FALSE {
            return b;
        }
        if a == TRUE && b == FALSE {
            return c;
        }
        if a == FALSE && b == TRUE {
            return -c;
        }
        let key = (2, c, a, b);
        if let Some(&o) = self.gates.get(&key) {
            return o;
        }
        let o = self.gate(Def::Ite(c, a, b));
        self.clause(&[-c, -a, o]);
        self.clause(&[-c, a, -o]);
        self.clause(&[c, -b, o]);
        self.clause(&[c, b, -o]);
        self.gates.insert(key, o);
        o
    }

    /// The conjunction of several literals.
    pub fn all(&mut self, lits: &[Lit]) -> Lit {
        lits.iter().fold(TRUE, |acc, &l| self.and(acc, l))
    }

    // Bit-vector operations. Every operand has the width of its result unless said otherwise.

    pub fn ite_bits(&mut self, c: Lit, a: &Bits, b: &Bits) -> Bits {
        a.iter().zip(b).map(|(&x, &y)| self.ite(c, x, y)).collect()
    }

    pub fn and_bits(&mut self, a: &Bits, b: &Bits) -> Bits {
        a.iter().zip(b).map(|(&x, &y)| self.and(x, y)).collect()
    }

    pub fn or_bits(&mut self, a: &Bits, b: &Bits) -> Bits {
        a.iter().zip(b).map(|(&x, &y)| self.or(x, y)).collect()
    }

    pub fn xor_bits(&mut self, a: &Bits, b: &Bits) -> Bits {
        a.iter().zip(b).map(|(&x, &y)| self.xor(x, y)).collect()
    }

    pub fn not_bits(&self, a: &Bits) -> Bits {
        a.iter().map(|&x| -x).collect()
    }

    /// Ripple-carry addition with a carry in; returns the sum and the carry out.
    fn add_carry(&mut self, a: &Bits, b: &Bits, carry: Lit) -> (Bits, Lit) {
        let mut out = Vec::with_capacity(a.len());
        let mut c = carry;
        for (&x, &y) in a.iter().zip(b) {
            let xy = self.xor(x, y);
            out.push(self.xor(xy, c));
            let t = self.and(xy, c);
            let u = self.and(x, y);
            c = self.or(t, u);
        }
        (out, c)
    }

    pub fn add(&mut self, a: &Bits, b: &Bits) -> Bits {
        self.add_carry(a, b, FALSE).0
    }

    pub fn sub(&mut self, a: &Bits, b: &Bits) -> Bits {
        let nb = self.not_bits(b);
        self.add_carry(a, &nb, TRUE).0
    }

    pub fn neg(&mut self, a: &Bits) -> Bits {
        let zero = self.constant(0, a.len());
        self.sub(&zero, a)
    }

    /// Two's-complement multiplication, modulo the width (as `imul` and `lmul` are).
    pub fn mul(&mut self, a: &Bits, b: &Bits) -> Bits {
        let width = a.len();
        let mut acc = self.constant(0, width);
        for i in 0..width {
            if b[i] == FALSE {
                continue;
            }
            // a << i, gated by b[i].
            let mut partial = vec![FALSE; i];
            for &x in a.iter().take(width - i) {
                partial.push(self.and(x, b[i]));
            }
            acc = self.add(&acc, &partial);
        }
        acc
    }

    /// Unsigned `a < b`: the borrow of `a - b`.
    pub fn ult(&mut self, a: &Bits, b: &Bits) -> Lit {
        let nb = self.not_bits(b);
        let (_, carry) = self.add_carry(a, &nb, TRUE);
        -carry
    }

    /// Signed `a < b`: unsigned, with the sign bits flipped.
    pub fn slt(&mut self, a: &Bits, b: &Bits) -> Lit {
        let mut fa = a.clone();
        let mut fb = b.clone();
        let last = a.len() - 1;
        fa[last] = -fa[last];
        fb[last] = -fb[last];
        self.ult(&fa, &fb)
    }

    pub fn sle(&mut self, a: &Bits, b: &Bits) -> Lit {
        -self.slt(b, a)
    }

    pub fn eq(&mut self, a: &Bits, b: &Bits) -> Lit {
        let mut acc = TRUE;
        for (&x, &y) in a.iter().zip(b) {
            let d = self.xor(x, y);
            acc = self.and(acc, -d);
        }
        acc
    }

    pub fn is_zero(&mut self, a: &Bits) -> Lit {
        let zero = self.constant(0, a.len());
        self.eq(a, &zero)
    }

    /// The sign bit.
    pub fn negative(&self, a: &Bits) -> Lit {
        a[a.len() - 1]
    }

    /// The magnitude, as an unsigned value (`MIN_VALUE` stays itself, which as unsigned is its magnitude).
    fn magnitude(&mut self, a: &Bits) -> Bits {
        let n = self.neg(a);
        let s = self.negative(a);
        self.ite_bits(s, &n, a)
    }

    /// Signed division and remainder left to the solver (see [`Lazy`]): fresh bits under the facts of
    /// [`Blaster::division_facts`], the circuit built by [`Blaster::refine_division`] only when a model needs it.
    /// Constant operands fold as they do in [`Blaster::sdivrem`].
    pub fn sdivrem_lazy(&mut self, a: &Bits, b: &Bits) -> (Bits, Bits) {
        if a.iter().chain(b).all(|&l| is_const(l)) {
            return self.sdivrem(a, b);
        }
        if let Some(&i) = self.divisions.get(&(a.clone(), b.clone())) {
            return (self.lazy[i].q.clone(), self.lazy[i].r.clone());
        }
        let i = self.lazy.len();
        let width = a.len();
        let q: Bits = (0..width).map(|_| self.gate(Def::Lazy(i as u32))).collect();
        let r: Bits = (0..width).map(|_| self.gate(Def::Lazy(i as u32))).collect();
        self.lazy.push(Lazy { op: Op::DivRem, a: a.clone(), b: b.clone(), q: q.clone(), r: r.clone(), refined: false });
        self.divisions.insert((a.clone(), b.clone()), i);
        self.division_facts(a, b, &q, &r);
        (q, r)
    }

    /// Multiplication left to the solver (see [`Lazy`]): fresh bits under the facts of
    /// [`Blaster::multiplication_facts`], the circuit built by [`Blaster::refine_operation`] only when a model
    /// needs it. A product with a constant operand is built as [`Blaster::mul`] builds it, which is small (one
    /// adder per set bit). A quotient times its divisor is the dividend less the remainder, `a - a % b`, exactly:
    /// the identity `a == (a / b) * b + a % b` holds for every pair, the division by zero and `MIN_VALUE / -1`
    /// included, so `(a / b) * b` is that subtraction, with no product at all, and a method that aligns to a
    /// multiple either way computes the same bits.
    pub fn mul_lazy(&mut self, a: &Bits, b: &Bits) -> Bits {
        if a.iter().all(|&l| is_const(l)) || b.iter().all(|&l| is_const(l)) {
            return self.mul(a, b);
        }
        if let Some(l) = self.lazy.iter().find(|l| l.op == Op::DivRem && ((l.q == *a && l.b == *b) || (l.q == *b && l.b == *a))) {
            let (dividend, remainder) = (l.a.clone(), l.r.clone());
            return self.sub(&dividend, &remainder);
        }
        let key = if a <= b { (a.clone(), b.clone()) } else { (b.clone(), a.clone()) };
        if let Some(&i) = self.products.get(&key) {
            return self.lazy[i].q.clone();
        }
        let i = self.lazy.len();
        let width = a.len();
        let p: Bits = (0..width).map(|_| self.gate(Def::Lazy(i as u32))).collect();
        self.lazy.push(Lazy { op: Op::Mul, a: a.clone(), b: b.clone(), q: p.clone(), r: Vec::new(), refined: false });
        self.products.insert(key, i);
        self.multiplication_facts(a, b, &p);
        p
    }

    /// What holds of every product `p = a * b` modulo the width, in circuits of a few hundred gates each, with
    /// one barrel shifter per operand: a factor of zero gives zero, of one the other factor, of minus one its
    /// negation; a factor that is a power of two (`MIN_VALUE` included) shifts the other by its exponent; and the
    /// low eight bits of the product are the low eight bits of the factors multiplied, which a small multiplier
    /// gives exactly. Nothing is said of the sign, which overflow can flip.
    fn multiplication_facts(&mut self, a: &Bits, b: &Bits, p: &Bits) {
        let width = a.len();
        let zero = self.constant(0, width);
        let one = self.constant(1, width);
        let minus_one = self.constant(-1, width);
        let p_zero = self.eq(p, &zero);
        let mut facts = Vec::new();
        for (x, y) in [(a, b), (b, a)] {
            let x_zero = self.eq(x, &zero);
            facts.push(self.or(-x_zero, p_zero));
            let x_one = self.eq(x, &one);
            let p_is_y = self.eq(p, y);
            facts.push(self.or(-x_one, p_is_y));
            let x_minus_one = self.eq(x, &minus_one);
            let ny = self.neg(y);
            let p_is_minus_y = self.eq(p, &ny);
            facts.push(self.or(-x_minus_one, p_is_minus_y));
            let x_less = self.sub(x, &one);
            let x_masked = self.and_bits(x, &x_less);
            let single_bit = self.is_zero(&x_masked);
            let power_of_two = self.and(single_bit, -x_zero);
            let steps = width.trailing_zeros() as usize;
            let exponent: Bits = (0..steps).map(|j| {
                let mut acc = FALSE;
                for (i, &bit) in x.iter().enumerate() {
                    if (i >> j) & 1 == 1 {
                        acc = self.or(acc, bit);
                    }
                }
                acc
            }).collect();
            let shifted = self.shl(y, &exponent);
            let p_shifted = self.eq(p, &shifted);
            facts.push(self.or(-power_of_two, p_shifted));
        }
        let k = width.min(8);
        let low = self.mul(&a[..k].to_vec(), &b[..k].to_vec());
        for (&chosen, &real) in p[..k].iter().zip(&low) {
            facts.push(-self.xor(chosen, real));
        }
        for f in facts {
            self.clause(&[f]);
        }
    }

    /// What holds of every division `a / b = q` with remainder `r` when `b` is not zero, in circuits of a few
    /// hundred gates each (comparisons, negations, equalities: no division and no multiplication): `|r| < |b|`,
    /// `|r| <= |a|`, `|q| <= |a|`; `r` is zero or of `a`'s sign; `q` is zero exactly when `|a| < |b|`, and `r` is
    /// `a` exactly then; `q` is zero or of the sign of `a` times `b`, unless `b` is minus one; a division by one
    /// is `a` with no remainder, by minus one its negation, of `a` by itself one; and a power of two divides a
    /// non-negative `a` with the remainder `a & (b - 1)`. All of them hold for `MIN_VALUE` too, which the
    /// magnitudes being unsigned makes so.
    fn division_facts(&mut self, a: &Bits, b: &Bits, q: &Bits, r: &Bits) {
        let width = a.len();
        let nz = -self.is_zero(b);
        let (sa, sb, sq, sr) = (self.negative(a), self.negative(b), self.negative(q), self.negative(r));
        let abs_a = self.magnitude(a);
        let abs_b = self.magnitude(b);
        let abs_q = self.magnitude(q);
        let abs_r = self.magnitude(r);
        let one = self.constant(1, width);
        let minus_one = self.constant(-1, width);
        let r_zero = self.is_zero(r);
        let q_zero = self.is_zero(q);
        let mut facts = vec![self.ult(&abs_r, &abs_b), -self.ult(&abs_a, &abs_r), -self.ult(&abs_a, &abs_q)];
        let r_sign = -self.xor(sr, sa);
        facts.push(self.or(r_zero, r_sign));
        let small = self.ult(&abs_a, &abs_b);
        facts.push(-self.xor(small, q_zero));
        let r_is_a = self.eq(r, a);
        facts.push(-self.xor(r_is_a, q_zero));
        let b_minus_one = self.eq(b, &minus_one);
        let product_sign = self.xor(sa, sb);
        let q_sign = -self.xor(sq, product_sign);
        let q_sign_or_zero = self.or(q_zero, q_sign);
        facts.push(self.or(b_minus_one, q_sign_or_zero));
        let b_one = self.eq(b, &one);
        let q_is_a = self.eq(q, a);
        let by_one = self.and(q_is_a, r_zero);
        facts.push(self.or(-b_one, by_one));
        let na = self.neg(a);
        let q_is_minus_a = self.eq(q, &na);
        let by_minus_one = self.and(q_is_minus_a, r_zero);
        facts.push(self.or(-b_minus_one, by_minus_one));
        let same = self.eq(a, b);
        let q_one = self.eq(q, &one);
        let by_itself = self.and(q_one, r_zero);
        facts.push(self.or(-same, by_itself));
        let b_less = self.sub(b, &one);
        let b_masked = self.and_bits(b, &b_less);
        let power_of_two = self.is_zero(&b_masked);
        let a_masked = self.and_bits(a, &b_less);
        let r_masked = self.eq(r, &a_masked);
        let masking = self.and(power_of_two, -sa);
        facts.push(self.or(-masking, r_masked));
        for f in facts {
            let guarded = self.or(-nz, f);
            self.clause(&[guarded]);
        }
    }

    /// The first operation left to the solver whose result in the solver's last model is not the real operation
    /// on the operands' values there (a division by zero is never wrong: the JVM throws before the values
    /// matter). `None` when the model is a real one, as a model of the circuits alone always is: the first wrong
    /// operation decides, since the operands of a later one may come from it.
    pub fn wrong_operation(&self) -> Option<usize> {
        self.lazy.iter().enumerate().find(|(_, l)| {
            if l.refined {
                return false;
            }
            let (a, b) = (self.eval(&l.a), self.eval(&l.b));
            if l.op == Op::DivRem && b == 0 {
                return false;
            }
            let r = if l.r.is_empty() { 0 } else { self.eval(&l.r) };
            real_operation(l.op, l.a.len(), a, b) != (self.eval(&l.q), r)
        }).map(|(i, _)| i)
    }

    /// Builds the circuit of operation `i` and ties its bits to the ones the solver chooses.
    pub fn refine_operation(&mut self, i: usize) {
        let (a, b) = (self.lazy[i].a.clone(), self.lazy[i].b.clone());
        let (q, r) = match self.lazy[i].op {
            Op::DivRem => self.sdivrem(&a, &b),
            Op::Mul => (self.mul(&a, &b), Vec::new()),
        };
        for (&chosen, &real) in self.lazy[i].q.iter().zip(&q).chain(self.lazy[i].r.iter().zip(&r)) {
            self.solver.add_clause([-chosen, real]);
            self.solver.add_clause([chosen, -real]);
            self.clauses += 2;
        }
        self.lazy[i].refined = true;
    }

    /// How many divisions were left to the solver, and how many of them had their circuit built.
    pub fn divisions(&self) -> (u64, u64) {
        self.counted(Op::DivRem)
    }

    /// How many multiplications were left to the solver, and how many of them had their circuit built.
    pub fn multiplications(&self) -> (u64, u64) {
        self.counted(Op::Mul)
    }

    fn counted(&self, op: Op) -> (u64, u64) {
        let of = self.lazy.iter().filter(|l| l.op == op);
        (of.clone().count() as u64, of.filter(|l| l.refined).count() as u64)
    }

    /// Unsigned division and remainder by restoring division; the quotient of a division by zero is all ones and
    /// the remainder the dividend, as hardware does, but the JVM throws before it gets here.
    pub fn udivrem(&mut self, a: &Bits, b: &Bits) -> (Bits, Bits) {
        let width = a.len();
        let mut rem = self.constant(0, width);
        let mut quot = vec![FALSE; width];
        for i in (0..width).rev() {
            // rem = (rem << 1) | a[i]
            let mut shifted = vec![a[i]];
            shifted.extend_from_slice(&rem[..width - 1]);
            let fits = -self.ult(&shifted, b); // shifted >= b
            let diff = self.sub(&shifted, b);
            rem = self.ite_bits(fits, &diff, &shifted);
            quot[i] = fits;
        }
        (quot, rem)
    }

    /// Signed division and remainder as `idiv`/`irem` define them: the quotient truncates toward zero, the
    /// remainder takes the dividend's sign, and `MIN_VALUE / -1` wraps to `MIN_VALUE`.
    pub fn sdivrem(&mut self, a: &Bits, b: &Bits) -> (Bits, Bits) {
        let sa = self.negative(a);
        let sb = self.negative(b);
        let na = self.neg(a);
        let nb = self.neg(b);
        let abs_a = self.ite_bits(sa, &na, a);
        let abs_b = self.ite_bits(sb, &nb, b);
        let (q, r) = self.udivrem(&abs_a, &abs_b);
        let sq = self.xor(sa, sb);
        let nq = self.neg(&q);
        let nr = self.neg(&r);
        let quot = self.ite_bits(sq, &nq, &q);
        let rem = self.ite_bits(sa, &nr, &r);
        (quot, rem)
    }

    /// A shift by a symbolic amount, masked to the width as the JVM masks it (`& 31`, `& 63`). `arith` keeps the
    /// sign for right shifts.
    fn shift(&mut self, a: &Bits, amount: &Bits, left: bool, arith: bool) -> Bits {
        let width = a.len();
        let steps = width.trailing_zeros() as usize; // 5 for 32, 6 for 64
        let fill = if arith { self.negative(a) } else { FALSE };
        let mut cur = a.clone();
        for s in 0..steps {
            let k = 1usize << s;
            let shifted: Bits = if left {
                (0..width).map(|i| if i < k { FALSE } else { cur[i - k] }).collect()
            } else {
                (0..width).map(|i| if i + k < width { cur[i + k] } else { fill }).collect()
            };
            cur = self.ite_bits(amount[s], &shifted, &cur);
        }
        cur
    }

    pub fn shl(&mut self, a: &Bits, amount: &Bits) -> Bits {
        self.shift(a, amount, true, false)
    }

    pub fn shr(&mut self, a: &Bits, amount: &Bits) -> Bits {
        self.shift(a, amount, false, true)
    }

    pub fn ushr(&mut self, a: &Bits, amount: &Bits) -> Bits {
        self.shift(a, amount, false, false)
    }

    pub fn sext(&self, a: &Bits, width: usize) -> Bits {
        let sign = self.negative(a);
        let mut out = a.clone();
        out.resize(width, sign);
        out
    }

    pub fn zext(&self, a: &Bits, width: usize) -> Bits {
        let mut out = a.clone();
        out.resize(width, FALSE);
        out
    }

    pub fn trunc(&self, a: &Bits, width: usize) -> Bits {
        a[..width].to_vec()
    }

    // Solving.

    /// Whether the clauses together with the assumptions are satisfiable; `None` when the solver gave up (a
    /// timeout).
    pub fn solve_with(&mut self, assumptions: &[Lit]) -> Option<bool> {
        self.solves += 1;
        let assumptions: Vec<Lit> = assumptions.iter().copied().filter(|&l| l != TRUE).collect();
        if assumptions.contains(&FALSE) {
            return Some(false);
        }
        let started = std::time::Instant::now();
        let answer = self.solver.solve_with(assumptions.into_iter());
        self.solving += started.elapsed();
        answer
    }

    /// The solver's last model, as the inputs' values.
    pub fn snapshot(&self) -> Model {
        let mut model = Model::default();
        for (v, def) in self.defs.iter().enumerate().skip(2) {
            if matches!(def, Def::Input) {
                model.set(v, self.solver.value(v as Lit).unwrap_or(false));
            }
        }
        model
    }

    /// Whether the literal holds in the model, evaluating the gates it depends on that the model has not been
    /// asked about yet (an input the model does not fix is false).
    pub fn holds(&mut self, model: &mut Model, lit: Lit) -> bool {
        if let Some(b) = model.lit(lit) {
            return b;
        }
        let started = std::time::Instant::now();
        let mut stack = vec![lit.unsigned_abs() as usize];
        let mut done = 0u64;
        while let Some(&v) = stack.last() {
            if model.get(v).is_some() {
                stack.pop();
                continue;
            }
            let need = |model: &Model, stack: &mut Vec<usize>, l: Lit| -> Option<bool> {
                let value = model.lit(l);
                if value.is_none() {
                    stack.push(l.unsigned_abs() as usize);
                }
                value
            };
            match self.defs[v] {
                Def::Input => {
                    model.set(v, false);
                    stack.pop();
                    done += 1;
                }
                Def::And(a, b) => {
                    let (x, y) = (model.lit(a), model.lit(b));
                    if x == Some(false) || y == Some(false) {
                        model.set(v, false);
                        stack.pop();
                        done += 1;
                    } else if let (Some(x), Some(y)) = (need(model, &mut stack, a), need(model, &mut stack, b)) {
                        model.set(v, x && y);
                        stack.pop();
                        done += 1;
                    }
                }
                Def::Xor(a, b) => {
                    if let (Some(x), Some(y)) = (need(model, &mut stack, a), need(model, &mut stack, b)) {
                        model.set(v, x != y);
                        stack.pop();
                        done += 1;
                    }
                }
                Def::Ite(c, a, b) => {
                    if let Some(cv) = need(model, &mut stack, c) {
                        if let Some(x) = need(model, &mut stack, if cv { a } else { b }) {
                            model.set(v, x);
                            stack.pop();
                            done += 1;
                        }
                    }
                }
                Def::Lazy(i) => {
                    // The real operation on the operands' values, every bit of the result at once.
                    let l = &self.lazy[i as usize];
                    let mut ready = true;
                    for &x in l.a.iter().chain(&l.b) {
                        ready &= need(model, &mut stack, x).is_some();
                    }
                    if ready {
                        let (a, b) = (value_in(model, &l.a).expect("ready"), value_in(model, &l.b).expect("ready"));
                        let (q, r) = real_operation(l.op, l.a.len(), a, b);
                        for (k, &bit) in l.q.iter().enumerate() {
                            model.set(bit as usize, (q >> k) & 1 == 1);
                        }
                        for (k, &bit) in l.r.iter().enumerate() {
                            model.set(bit as usize, (r >> k) & 1 == 1);
                        }
                        stack.pop();
                        done += 1;
                    }
                }
            }
        }
        self.evaluating += started.elapsed();
        self.evaluated += done;
        model.lit(lit).expect("evaluated")
    }

    /// A literal's value in the last model.
    pub fn value(&self, lit: Lit) -> bool {
        if is_const(lit) {
            return lit == TRUE;
        }
        self.solver.value(lit).unwrap_or(false)
    }

    /// A value's bits in the last model, sign-extended.
    pub fn eval(&self, bits: &Bits) -> i64 {
        let mut v: u64 = 0;
        for (i, &l) in bits.iter().enumerate() {
            if self.value(l) {
                v |= 1 << i;
            }
        }
        let width = bits.len();
        if width < 64 && v & (1 << (width - 1)) != 0 {
            v |= u64::MAX << width;
        }
        v as i64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Runs `op` on fresh inputs pinned to `x` and `y` by assumptions, so that the circuits are exercised rather
    /// than folded away, and reads the result back from the model.
    fn circuit(width: usize, x: i64, y: i64, op: impl Fn(&mut Blaster, &Bits, &Bits) -> Bits) -> i64 {
        let mut b = Blaster::new();
        let a = b.fresh(width);
        let c = b.fresh(width);
        let out = op(&mut b, &a, &c);
        let mut assumptions = Vec::new();
        for i in 0..width {
            assumptions.push(if (x >> i) & 1 == 1 { a[i] } else { -a[i] });
            assumptions.push(if (y >> i) & 1 == 1 { c[i] } else { -c[i] });
        }
        assert_eq!(b.solve_with(&assumptions), Some(true));
        b.eval(&out)
    }

    fn bit(width: usize, x: i64, y: i64, op: impl Fn(&mut Blaster, &Bits, &Bits) -> Lit) -> bool {
        circuit(width, x, y, |b, a, c| vec![op(b, a, c)]) & 1 == 1
    }

    const INTS: &[i32] = &[0, 1, -1, 2, 3, 7, -7, 10, 100, 1000, 65535, 65536, -65536, 1 << 30, i32::MAX, i32::MIN, i32::MIN + 1, 0x5555_5555, -0x1234_5678];
    const LONGS: &[i64] = &[0, 1, -1, 3, -3, 1000, i32::MAX as i64, i32::MIN as i64, 1 << 40, -(1 << 40), i64::MAX, i64::MIN, i64::MIN + 1, 0x0123_4567_89AB_CDEF];

    #[test]
    fn int_arithmetic_is_the_jvms() {
        for &x in INTS {
            for &y in INTS {
                let (x64, y64) = (i64::from(x), i64::from(y));
                assert_eq!(circuit(32, x64, y64, |b, a, c| b.add(a, c)) as i32, x.wrapping_add(y), "{x} + {y}");
                assert_eq!(circuit(32, x64, y64, |b, a, c| b.sub(a, c)) as i32, x.wrapping_sub(y), "{x} - {y}");
                assert_eq!(circuit(32, x64, y64, |b, a, c| b.mul(a, c)) as i32, x.wrapping_mul(y), "{x} * {y}");
                if y != 0 {
                    assert_eq!(circuit(32, x64, y64, |b, a, c| b.sdivrem(a, c).0) as i32, x.wrapping_div(y), "{x} / {y}");
                    assert_eq!(circuit(32, x64, y64, |b, a, c| b.sdivrem(a, c).1) as i32, x.wrapping_rem(y), "{x} % {y}");
                }
                assert_eq!(circuit(32, x64, y64, |b, a, c| b.shl(a, c)) as i32, x.wrapping_shl(y as u32), "{x} << {y}");
                assert_eq!(circuit(32, x64, y64, |b, a, c| b.shr(a, c)) as i32, x.wrapping_shr(y as u32), "{x} >> {y}");
                assert_eq!(circuit(32, x64, y64, |b, a, c| b.ushr(a, c)) as i32, ((x as u32).wrapping_shr(y as u32)) as i32, "{x} >>> {y}");
                assert_eq!(bit(32, x64, y64, |b, a, c| b.slt(a, c)), x < y, "{x} < {y}");
                assert_eq!(bit(32, x64, y64, |b, a, c| b.sle(a, c)), x <= y, "{x} <= {y}");
                assert_eq!(bit(32, x64, y64, |b, a, c| b.eq(a, c)), x == y, "{x} == {y}");
                assert_eq!(bit(32, x64, y64, |b, a, c| b.ult(a, c)), (x as u32) < (y as u32), "{x} <u {y}");
            }
            assert_eq!(circuit(32, i64::from(x), 0, |b, a, _| b.neg(a)) as i32, x.wrapping_neg());
            assert_eq!(circuit(32, i64::from(x), 0, |b, a, _| b.sext(&b.trunc(a, 8), 32)) as i32, x as i8 as i32, "i2b");
            assert_eq!(circuit(32, i64::from(x), 0, |b, a, _| b.zext(&b.trunc(a, 16), 32)) as i32, x as u16 as i32, "i2c");
            assert_eq!(circuit(32, i64::from(x), 0, |b, a, _| b.sext(&b.trunc(a, 16), 32)) as i32, x as i16 as i32, "i2s");
        }
    }

    #[test]
    fn long_arithmetic_is_the_jvms() {
        for &x in LONGS {
            for &y in LONGS {
                assert_eq!(circuit(64, x, y, |b, a, c| b.add(a, c)), x.wrapping_add(y), "{x} + {y}");
                assert_eq!(circuit(64, x, y, |b, a, c| b.mul(a, c)), x.wrapping_mul(y), "{x} * {y}");
                if y != 0 {
                    assert_eq!(circuit(64, x, y, |b, a, c| b.sdivrem(a, c).0), x.wrapping_div(y), "{x} / {y}");
                    assert_eq!(circuit(64, x, y, |b, a, c| b.sdivrem(a, c).1), x.wrapping_rem(y), "{x} % {y}");
                }
                assert_eq!(bit(64, x, y, |b, a, c| b.slt(a, c)), x < y, "{x} < {y}");
            }
            for &s in &[0i64, 1, 31, 32, 63, 64, 100, -1] {
                assert_eq!(circuit(64, x, s, |b, a, c| b.shl(a, &b.trunc(c, 32))), x.wrapping_shl(s as u32), "{x} << {s}");
                assert_eq!(circuit(64, x, s, |b, a, c| b.shr(a, &b.trunc(c, 32))), x.wrapping_shr(s as u32), "{x} >> {s}");
                assert_eq!(circuit(64, x, s, |b, a, c| b.ushr(a, &b.trunc(c, 32))), ((x as u64).wrapping_shr(s as u32)) as i64, "{x} >>> {s}");
            }
            assert_eq!(circuit(64, x, 0, |b, a, _| b.sext(&b.trunc(a, 32), 64)), x as i32 as i64, "l2i then i2l");
        }
    }

    #[test]
    fn the_same_circuit_twice_is_one_circuit() {
        let mut b = Blaster::new();
        let x = b.fresh(32);
        let y = b.fresh(32);
        let p = b.mul(&x, &y);
        let before = b.variables();
        let q = b.mul(&x, &y);
        assert_eq!(b.variables(), before, "no new gate");
        assert_eq!(b.eq(&p, &q), TRUE, "equal by construction");
        let xy = b.xor(x[0], y[0]);
        assert_eq!(b.xor(-x[0], y[0]), -xy, "xor with a negated input is the negated gate");
        assert_eq!(b.xor(-y[0], -x[0]), xy);
    }

    #[test]
    fn a_division_left_to_the_solver_is_built_when_its_model_is_wrong_and_not_before() {
        let mut b = Blaster::new();
        let x = b.fresh(32);
        let y = b.fresh(32);
        let (q, r) = b.sdivrem_lazy(&x, &y);
        let (q2, r2) = b.sdivrem_lazy(&x, &y);
        assert_eq!((&q2, &r2), (&q, &r), "the same division of the same values is the same bits");
        assert_eq!(b.divisions(), (1, 0));
        // What the facts decide needs no circuit: a remainder is smaller than a positive divisor, a division by
        // one is exact, a power of two masks a non-negative dividend.
        let zero = b.constant(0, 32);
        let one = b.constant(1, 32);
        let eight = b.constant(8, 32);
        let seven = b.constant(7, 32);
        let y_pos = b.slt(&zero, &y);
        let r_big = b.sle(&y, &r);
        assert_eq!(b.solve_with(&[y_pos, r_big]), Some(false), "r < y when y > 0");
        let y_one = b.eq(&y, &one);
        let r_nz = -b.is_zero(&r);
        assert_eq!(b.solve_with(&[y_one, r_nz]), Some(false), "x % 1 == 0");
        let y_eight = b.eq(&y, &eight);
        let x_nonneg = -b.negative(&x);
        let low = b.and_bits(&x, &seven);
        let r_masked = b.eq(&r, &low);
        assert_eq!(b.solve_with(&[y_eight, x_nonneg, -r_masked]), Some(false), "x % 8 == x & 7 for x >= 0");
        assert_eq!(b.divisions(), (1, 0), "no circuit was built");
        // A quotient the facts do not pin: the solver's guess is checked against the real division, and the
        // circuit built when it is wrong, after which the solver cannot be wrong again.
        let x_23 = b.eq(&x, &b.constant(23, 32).clone());
        let y_7 = b.eq(&y, &seven);
        let r_2 = b.eq(&r, &b.constant(2, 32).clone());
        assert_eq!(b.solve_with(&[x_23, y_7, -r_2]), Some(true), "the facts allow a wrong remainder");
        let mut rounds = 0;
        while let Some(i) = b.wrong_operation() {
            b.refine_operation(i);
            rounds += 1;
            assert_eq!(b.solve_with(&[x_23, y_7]), Some(true));
        }
        assert!(rounds <= 1, "one division, built at most once");
        assert_eq!((b.eval(&q), b.eval(&r)), (3, 2));
        assert_eq!(b.solve_with(&[x_23, y_7, -r_2]), Some(false), "23 % 7 is 2 once the circuit is there");
        assert_eq!(b.divisions(), (1, 1));
        // A division by zero is never wrong: the JVM throws before its value matters.
        let y_zero = b.is_zero(&y);
        assert_eq!(b.solve_with(&[y_zero]), Some(true));
        assert_eq!(b.wrong_operation(), None);
    }

    #[test]
    fn a_multiplication_left_to_the_solver_is_built_when_its_model_is_wrong_and_not_before() {
        let mut b = Blaster::new();
        let x = b.fresh(32);
        let y = b.fresh(32);
        let p = b.mul_lazy(&x, &y);
        let p2 = b.mul_lazy(&y, &x);
        assert_eq!(p2, p, "a product of the same values in either order is the same bits");
        assert_eq!(b.multiplications(), (1, 0));
        // What the facts decide needs no circuit: a factor of zero or one, a power of two as a shift, the low
        // bits of the product.
        let zero = b.constant(0, 32);
        let one = b.constant(1, 32);
        let eight = b.constant(8, 32);
        let y_zero = b.eq(&y, &zero);
        let p_nz = -b.is_zero(&p);
        assert_eq!(b.solve_with(&[y_zero, p_nz]), Some(false), "x * 0 == 0");
        let x_one = b.eq(&x, &one);
        let p_is_y = b.eq(&p, &y);
        assert_eq!(b.solve_with(&[x_one, -p_is_y]), Some(false), "1 * y == y");
        let y_eight = b.eq(&y, &eight);
        let three = b.constant(3, 32);
        let x_shifted = b.shl(&x, &three);
        let p_shifted = b.eq(&p, &x_shifted);
        assert_eq!(b.solve_with(&[y_eight, -p_shifted]), Some(false), "x * 8 == x << 3");
        let p_odd = p[0];
        let x_even = -x[0];
        assert_eq!(b.solve_with(&[x_even, p_odd]), Some(false), "an even factor gives an even product");
        assert_eq!(b.multiplications(), (1, 0), "no circuit was built");
        // A product the facts do not pin: the solver's guess is checked against the real product, and the
        // circuit built when it is wrong, after which the solver cannot be wrong again.
        let x_300 = b.eq(&x, &b.constant(300, 32).clone());
        let y_500 = b.eq(&y, &b.constant(500, 32).clone());
        let p_right = b.eq(&p, &b.constant(150_000, 32).clone());
        let p_wrong = b.eq(&p, &b.constant(150_000 + 256, 32).clone());
        assert_eq!(b.solve_with(&[x_300, y_500, p_wrong]), Some(true), "the facts allow a wrong product of the same low bits");
        assert_eq!(b.wrong_operation(), Some(0));
        b.refine_operation(0);
        assert_eq!(b.solve_with(&[x_300, y_500, p_wrong]), Some(false), "300 * 500 is 150000 once the circuit is there");
        assert_eq!(b.solve_with(&[x_300, y_500]), Some(true));
        assert!(b.value(p_right));
        assert_eq!(b.wrong_operation(), None);
        assert_eq!(b.multiplications(), (1, 1));
        // A product with a constant factor is built as it is, small.
        let p3 = b.mul_lazy(&x, &three);
        assert_eq!(b.multiplications(), (1, 1));
        let p3_is = b.eq(&p3, &b.constant(900, 32).clone());
        assert_eq!(b.solve_with(&[x_300, -p3_is]), Some(false));
    }

    #[test]
    fn a_quotient_times_its_divisor_is_the_dividend_less_the_remainder() {
        let mut b = Blaster::new();
        let x = b.fresh(64);
        let y = b.fresh(64);
        let (q, r) = b.sdivrem_lazy(&x, &y);
        let aligned = b.mul_lazy(&q, &y);
        let aligned_too = b.mul_lazy(&y, &q);
        let by_remainder = b.sub(&x, &r);
        assert_eq!(aligned, by_remainder, "(x / y) * y is x - x % y, the same bits");
        assert_eq!(aligned_too, by_remainder);
        assert_eq!(b.multiplications(), (0, 0), "no product was left to the solver");
        // The identity holds where the circuits are built too: a division by zero, MIN_VALUE / -1.
        let min = b.constant(i64::MIN, 64);
        let minus_one = b.constant(-1, 64);
        let x_min = b.eq(&x, &min);
        let y_minus_one = b.eq(&y, &minus_one);
        assert_eq!(b.solve_with(&[x_min, y_minus_one]), Some(true));
        while let Some(i) = b.wrong_operation() {
            b.refine_operation(i);
            assert_eq!(b.solve_with(&[x_min, y_minus_one]), Some(true));
        }
        assert_eq!((b.eval(&q), b.eval(&r), b.eval(&aligned)), (i64::MIN, 0, i64::MIN));
        assert_eq!(real_product(64, i64::MIN, -1), i64::MIN);
        assert_eq!(real_product(32, 65_536, 65_536), 0);
        assert_eq!(real_product(64, 65_536, 65_536), 1 << 32);
    }

    #[test]
    fn a_path_model_evaluates_a_division_left_to_the_solver_for_real() {
        let mut b = Blaster::new();
        let x = b.fresh(64);
        let y = b.fresh(64);
        let (q, r) = b.sdivrem_lazy(&x, &y);
        let x_is = b.eq(&x, &b.constant(-23, 64).clone());
        let y_is = b.eq(&y, &b.constant(7, 64).clone());
        assert_eq!(b.solve_with(&[x_is, y_is]), Some(true));
        // The model keeps the inputs alone; the quotient and remainder are the real -23 / 7, whatever the solver
        // chose for them.
        let mut model = b.snapshot();
        let q_is = b.eq(&q, &b.constant(-3, 64).clone());
        let r_is = b.eq(&r, &b.constant(-2, 64).clone());
        assert!(b.holds(&mut model, q_is));
        assert!(b.holds(&mut model, r_is));
        assert_eq!(b.divisions(), (1, 0));
        // A product likewise: the real -23 * 7, with no circuit.
        let p = b.mul_lazy(&x, &y);
        let p_is = b.eq(&p, &b.constant(-161, 64).clone());
        assert!(b.holds(&mut model, p_is));
        assert_eq!(b.multiplications(), (1, 0));
        assert_eq!(real_division(32, i64::from(i32::MIN), -1), (i64::from(i32::MIN), 0));
        assert_eq!(real_division(64, i64::MIN, -1), (i64::MIN, 0));
        assert_eq!(real_division(64, 5, 0), (-1, 5));
    }

    #[test]
    fn constants_fold_without_reaching_the_solver() {
        let mut b = Blaster::new();
        let x = b.constant(6, 32);
        let y = b.constant(7, 32);
        let p = b.mul(&x, &y);
        assert_eq!(p, b.constant(42, 32));
        assert_eq!(b.variables(), 1, "no variable was needed");
        let (q, r) = b.sdivrem(&b.constant(-7, 32).clone(), &b.constant(2, 32).clone());
        assert_eq!(b.eval(&q), -3);
        assert_eq!(b.eval(&r), -1);
        assert_eq!(b.solve_with(&[FALSE]), Some(false));
    }
}
