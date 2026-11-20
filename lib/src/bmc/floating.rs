//! JVM comparisons over IEEE 754 interchange bits. The stack carries the raw word until an
//! opcode or a method descriptor supplies its interpretation. Integer widening and comparisons are
//! bit-vector circuits. Arithmetic uses the JVM rounding rules on exhaustively covered operand tuples.

use super::{unsupported, ArithOp, Bits, Blaster, Engine, Kind, Lit, Narrow, Path, Step, Stop, Val, FALSE, TRUE};
use crate::interp::Value;

fn fraction_width(bits: &Bits) -> usize {
    match bits.len() {
        32 => 23,
        64 => 52,
        _ => unreachable!("a JVM floating-point word"),
    }
}

fn nan(b: &mut Blaster, bits: &Bits) -> Lit {
    let split = fraction_width(bits);
    let exponent_ones = b.all(&bits[split..bits.len() - 1]);
    let nonzero_fraction = -b.is_zero(&b.trunc(bits, split));
    b.and(exponent_ones, nonzero_fraction)
}

/// Signed magnitude order, including -0 before +0. The caller deals with NaNs.
fn ordered_less(b: &mut Blaster, x: &Bits, y: &Bits) -> Lit {
    let (sx, sy) = (b.negative(x), b.negative(y));
    let signs_differ = b.xor(sx, sy);
    let forward = b.ult(x, y);
    let backward = b.ult(y, x);
    let same_sign = b.ite(sx, backward, forward);
    b.ite(signs_differ, sx, same_sign)
}

fn cmp(b: &mut Blaster, x: &Bits, y: &Bits, unordered: i32) -> Bits {
    let x_nan = nan(b, x);
    let y_nan = nan(b, y);
    let either_nan = b.or(x_nan, y_nan);
    let magnitude = x.len() - 1;
    let x_zero = b.is_zero(&b.trunc(x, magnitude));
    let y_zero = b.is_zero(&b.trunc(y, magnitude));
    let both_zero = b.and(x_zero, y_zero);
    let same_bits = b.eq(x, y);
    let equal = b.or(both_zero, same_bits);
    let less = ordered_less(b, x, y);
    let sign = b.ite_bits(less, &b.constant(-1, 32), &b.constant(1, 32));
    let ordered = b.ite_bits(equal, &b.constant(0, 32), &sign);
    b.ite_bits(either_nan, &b.constant(i64::from(unordered), 32), &ordered)
}

pub(super) fn models_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!((owner, name, descriptor),
        ("java/lang/Double", "isNaN" | "isFinite" | "isInfinite", "(D)Z")
        | ("java/lang/Float", "isNaN" | "isFinite" | "isInfinite", "(F)Z")
        | ("java/lang/Double", "doubleToRawLongBits" | "doubleToLongBits", "(D)J")
        | ("java/lang/Float", "floatToRawIntBits" | "floatToIntBits", "(F)I")
        | ("java/lang/Double", "longBitsToDouble", "(J)D")
        | ("java/lang/Float", "intBitsToFloat", "(I)F")
        | ("java/lang/Math" | "java/lang/StrictMath", "min" | "max", "(DD)D" | "(FF)F")
        | ("java/lang/Math" | "java/lang/StrictMath", "abs", "(D)D" | "(F)F")
        | ("java/lang/Math" | "java/lang/StrictMath", "sqrt", "(D)D"))
}

impl Engine<'_> {
    pub(super) fn floating_cmp(&mut self, path: &mut Path, kind: Kind, unordered: i32) -> Result<Bits, Stop> {
        let (y, x) = if kind == Kind::Double {
            (self.pop_long(path)?, self.pop_long(path)?)
        } else {
            (self.pop_int(path)?, self.pop_int(path)?)
        };
        Ok(cmp(&mut self.b, &x, &y, unordered))
    }

    /// NaN payloads returned by Math.min/max and a signaling NaN's raw bits after a
    /// Java value transfer are not portable. Refuse when that case is reachable.
    fn exclude_float_case(&mut self, path: &Path, condition: Lit, why: &str) -> Result<(), Stop> {
        if condition != FALSE {
            let mut assumptions = path.cond.clone();
            assumptions.push(condition);
            if condition == TRUE || self.solve(&assumptions)? { return unsupported(why); }
        }
        Ok(())
    }

    pub(super) fn floating_static(&mut self, path: &mut Path, name: &str, args: &[Val]) -> Step {
        let Some(Val::I(x) | Val::J(x)) = args.first() else { return unsupported("a floating-point call without its operand") };
        let x_nan = nan(&mut self.b, x);
        let result = match name {
            "isNaN" => self.b.zext(&vec![x_nan], 32),
            "isInfinite" | "isFinite" => {
                let special = self.b.all(&x[fraction_width(x)..x.len() - 1]);
                let truth = if name == "isFinite" { -special } else { self.b.and(special, -x_nan) };
                self.b.zext(&vec![truth], 32)
            }
            "abs" => {
                self.exclude_float_case(path, x_nan, "floating point absolute value with an unspecified NaN sign")?;
                let mut bits = x.clone();
                *bits.last_mut().expect("a sign bit") = FALSE;
                bits
            }
            "sqrt" => self.finite_operation(path, "double sqrt", [x], 64, |[value]| {
                result_bits(Value::Double(f64::from_bits(value as u64).sqrt()))
            })?,
            "doubleToLongBits" | "floatToIntBits" => {
                let value = if x.len() == 64 { 0x7ff8_0000_0000_0000 } else { 0x7fc0_0000 };
                self.b.ite_bits(x_nan, &self.b.constant(value, x.len()), x)
            }
            "doubleToRawLongBits" | "floatToRawIntBits" | "longBitsToDouble" | "intBitsToFloat" => {
                let signaling = self.b.and(x_nan, -x[fraction_width(x) - 1]);
                self.exclude_float_case(path, signaling, "raw floating-point conversion of a possible signaling NaN")?;
                x.clone()
            }
            "max" | "min" => {
                let Some(Val::I(y) | Val::J(y)) = args.get(1) else { return unsupported("floating-point extrema without the second operand") };
                let y_nan = nan(&mut self.b, y);
                let either_nan = self.b.or(x_nan, y_nan);
                self.exclude_float_case(path, either_nan, "floating-point extrema with a possible NaN payload")?;
                let less = ordered_less(&mut self.b, x, y);
                if name == "min" { self.b.ite_bits(less, x, y) } else { self.b.ite_bits(less, y, x) }
            }
            _ => unreachable!("a classified floating-point intrinsic"),
        };
        self.push(path, if result.len() == 64 { Val::J(result) } else { Val::I(result) });
        self.advance(path);
        Ok(None)
    }
}

/// An int's magnitude has at most 32 significant bits. Normalization into the 53-bit
/// binary64 significand is therefore exact even for Integer.MIN_VALUE.
fn int_to_double(b: &mut Blaster, x: &Bits) -> Bits {
    let sign = b.negative(x);
    let negated = b.neg(x);
    let magnitude = b.ite_bits(sign, &negated, x);
    let mut word = b.constant(0, 64);
    for lead in 0..32 {
        let mut normalized = b.constant(((1023 + lead) as i64) << 52, 64);
        normalized[52 - lead..52].copy_from_slice(&magnitude[..lead]);
        word = b.ite_bits(magnitude[lead], &normalized, &word);
    }
    word[63] = sign;
    word
}

fn value_of(kind: Kind, raw: i64) -> Value {
    match kind {
        Kind::Int => Value::Int(raw as i32),
        Kind::Long => Value::Long(raw),
        Kind::Float => Value::Float(f32::from_bits(raw as u32)),
        Kind::Double => Value::Double(f64::from_bits(raw as u64)),
        Kind::Ref => unreachable!("numeric operand"),
    }
}

fn result_bits(value: Value) -> Option<i64> {
    match value {
        Value::Int(x) => Some(i64::from(x)),
        Value::Long(x) => Some(x),
        Value::Float(x) if !x.is_nan() => Some(i64::from(x.to_bits())),
        Value::Double(x) if !x.is_nan() => Some(x.to_bits() as i64),
        Value::Float(_) | Value::Double(_) => None,
        _ => unreachable!("numeric result"),
    }
}

impl Engine<'_> {
    fn pop_word(&self, path: &mut Path, kind: Kind) -> Result<Bits, Stop> {
        if matches!(kind, Kind::Long | Kind::Double) { self.pop_long(path) } else { self.pop_int(path) }
    }

    /// Compute the operation on every reachable operand tuple and prove their complement
    /// unsatisfiable before using the result. The limit bounds cost and never truncates the domain.
    fn finite_operation<const N: usize>(&mut self, path: &Path, operation: &str, operands: [&Bits; N], width: usize,
        evaluate: impl Fn([i64; N]) -> Option<i64>) -> Result<Bits, Stop> {
        const MAX_TUPLES: usize = 64;
        let checked = |values| evaluate(values).ok_or_else(|| Stop::Unsupported(format!("{operation} with an unspecified NaN result encoding")));
        if operands.iter().all(|word| self.b.constant_value(word).is_some()) {
            let raw = operands.map(|word| self.b.constant_value(word).expect("constant"));
            return Ok(self.b.constant(checked(raw)?, width));
        }
        let mut remaining = path.cond.clone();
        let mut result = self.b.constant(0, width);
        let mut count = 0;
        while self.solve(&remaining)? {
            if count == MAX_TUPLES {
                return unsupported(format!("{operation} with more than {MAX_TUPLES} reachable operand tuples"));
            }
            let mut model = self.b.snapshot();
            let values = operands.map(|word| {
                let mut raw = 0u64;
                for (bit, &literal) in word.iter().enumerate() {
                    raw |= u64::from(self.b.holds(&mut model, literal)) << bit;
                }
                raw as i64
            });
            let mut selected = TRUE;
            for (word, value) in operands.iter().zip(values) {
                let equal = self.b.eq(word, &self.b.constant(value, word.len()));
                selected = self.b.and(selected, equal);
            }
            let value = self.b.constant(checked(values)?, width);
            result = if count == 0 { value } else { self.b.ite_bits(selected, &value, &result) };
            remaining.push(-selected);
            count += 1;
        }
        Ok(result)
    }

    pub(super) fn floating_convert(&mut self, path: &mut Path, from: Kind, to: Kind) -> Result<Val, Stop> {
        let x = self.pop_word(path, from)?;
        if from == Kind::Int && to == Kind::Double { return Ok(Val::J(int_to_double(&mut self.b, &x))); }
        let wide = matches!(to, Kind::Long | Kind::Double);
        let result = self.finite_operation(path, &format!("{from:?} to {to:?}"), [&x], if wide { 64 } else { 32 }, |[raw]| {
            result_bits(crate::interp::convert(value_of(from, raw), Narrow::To(to)))
        })?;
        Ok(if wide { Val::J(result) } else { Val::I(result) })
    }

    pub(super) fn floating_arithmetic(&mut self, path: &mut Path, op: ArithOp, kind: Kind) -> Step {
        let y = self.pop_word(path, kind)?;
        let result = if op == ArithOp::Neg {
            let is_nan = nan(&mut self.b, &y);
            self.exclude_float_case(path, is_nan, "floating point negation with an unspecified NaN sign")?;
            let mut bits = y;
            let sign = bits.last_mut().expect("a floating-point word");
            *sign = -*sign;
            bits
        } else {
            let x = self.pop_word(path, kind)?;
            self.finite_operation(path, &format!("{kind:?} {op:?}"), [&x, &y], x.len(), |[left, right]| {
                let value = match kind {
                    Kind::Float => Value::Float(crate::interp::ieee_binary(op, f32::from_bits(left as u32), f32::from_bits(right as u32))),
                    Kind::Double => Value::Double(crate::interp::ieee_binary(op, f64::from_bits(left as u64), f64::from_bits(right as u64))),
                    _ => unreachable!("a floating-point opcode"),
                };
                result_bits(value)
            })?
        };
        self.push(path, if kind == Kind::Double { Val::J(result) } else { Val::I(result) });
        self.advance(path);
        Ok(None)
    }
}
