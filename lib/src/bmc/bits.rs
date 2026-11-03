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

/// The solver with the circuits built over it.
pub struct Blaster {
    solver: cadical::Solver,
    next: i32,
    /// Gates already built, by operation and inputs, so that the same function of the same inputs is one
    /// variable: two copies of a circuit (the method's own multiplication and the harness's check of it, say)
    /// then fold to the same literals, and their comparison to a constant.
    gates: HashMap<(u8, Lit, Lit, Lit), Lit>,
    /// How many clauses have been added, for reporting.
    pub clauses: u64,
    /// How many times the solver was asked, for reporting.
    pub solves: u64,
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
        let mut b = Blaster { solver: cadical::Solver::new(), next: 2, gates: HashMap::new(), clauses: 0, solves: 0 };
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

    /// A fresh variable.
    pub fn var(&mut self) -> Lit {
        let v = self.next;
        self.next += 1;
        v
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
        let o = self.var();
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
                let o = self.var();
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
        let o = self.var();
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
        self.solver.solve_with(assumptions.into_iter())
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
