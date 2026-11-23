//! JVM comparisons over IEEE 754 interchange bits. The stack carries the raw word until an
//! opcode or a method descriptor supplies its interpretation. Integer widening and comparisons are
//! bit-vector circuits. Arithmetic uses the JVM rounding rules on exhaustively covered operand tuples.

use super::{unsupported, ArithOp, Bits, Blaster, Engine, Kind, Lit, Model, Narrow, Path, Step, Stop, Val, FALSE, TRUE};
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
        | ("java/lang/Float", "parseFloat", "(Ljava/lang/String;)F")
        | ("java/lang/Double", "parseDouble", "(Ljava/lang/String;)D")
        | ("java/lang/Float", "isNaN" | "isFinite" | "isInfinite", "(F)Z")
        | ("java/lang/Double", "doubleToRawLongBits" | "doubleToLongBits", "(D)J")
        | ("java/lang/Float", "floatToRawIntBits" | "floatToIntBits", "(F)I")
        | ("java/lang/Double", "longBitsToDouble", "(J)D")
        | ("java/lang/Float", "intBitsToFloat", "(I)F")
        | ("java/lang/Math" | "java/lang/StrictMath", "min" | "max", "(DD)D" | "(FF)F")
        | ("java/lang/Math" | "java/lang/StrictMath", "abs", "(D)D" | "(F)F")
        | ("java/lang/Math" | "java/lang/StrictMath", "sqrt" | "floor" | "ceil" | "sin" | "cos", "(D)D")
        | ("java/lang/Math" | "java/lang/StrictMath", "atan2", "(DD)D"))
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

    /// A raw conversion of a signaling NaN or an unspecified NaN sign may have
    /// platform-specific bits. Refuse when such an observation is reachable.
    fn exclude_float_case(&mut self, path: &Path, condition: Lit, why: &str) -> Result<(), Stop> {
        if condition != FALSE {
            let mut assumptions = path.cond.clone();
            assumptions.push(condition);
            if condition == TRUE || self.solve(&assumptions)? { return unsupported(why); }
        }
        Ok(())
    }

    pub(super) fn floating_static(&mut self, path: &mut Path, owner: &str, name: &str, args: &[Val]) -> Step {
        if let [Val::R(text)] = args {
            let Some(text) = text else { return self.throw_class_only(path, "java/lang/NullPointerException") };
            let value = self.constant_units(path, *text)
                .and_then(|u| String::from_utf16(&u).ok())
                .and_then(|s| crate::interp::value::decimal_float(&s, name == "parseDouble"));
            let word = match value {
                Some(Value::Float(x)) => Val::I(self.b.constant(i64::from(x.to_bits()), 32)),
                Some(Value::Double(x)) => Val::J(self.b.constant(x.to_bits() as i64, 64)),
                _ => return unsupported(format!("{}.{name} needs a concrete decimal floating-point literal", owner.replace('/', "."))),
            };
            self.push(path, word);
            self.advance(path);
            return Ok(None);
        }
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
            "sqrt" | "floor" | "ceil" => self.finite_operation(path, name, [x], 64, |[raw]| {
                let value = f64::from_bits(raw as u64);
                let result = match name { "floor" => value.floor(), "ceil" => value.ceil(), _ => value.sqrt() };
                result_bits(Value::Double(result))
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
            "sin" | "cos" => {
                let function = if name == "sin" { super::trig::Function::Sin } else { super::trig::Function::Cos };
                let mut rounded = false;
                let bits = self.finite_words(path, name, [x], 64, |engine, [raw]| {
                    let key = (function, raw as u64);
                    let pair = match engine.trig_brackets.get(&key) {
                        Some(&cached) => cached,
                        None => {
                            let Some(bracket) = function.bracket(f64::from_bits(key.1)) else {
                                return unsupported(format!("{}.{name}(D)D without a certified rounding bracket at 0x{:016x}", owner.replace('/', "."), key.1));
                            };
                            engine.trig_brackets.insert(key, bracket);
                            bracket
                        }
                    };
                    let lower = engine.b.constant(pair.0 as i64, 64);
                    if pair.0 == pair.1 { return Ok(lower); }
                    rounded = true;
                    let choice = engine.b.var();
                    Ok(engine.b.ite_bits(choice, &lower, &engine.b.constant(pair.1 as i64, 64)))
                })?;
                if rounded { path.unbound_platform_value = Some("a permitted trigonometric rounding"); }
                bits
            }
            "atan2" => {
                // Java fixes the angle exactly on each nonzero axis. Math.atan2 can be a
                // VM intrinsic off the axes, with an implementation-dependent rounding.
                let Some(Val::J(abscissa)) = args.get(1) else { return unsupported("atan2 without the abscissa") };
                let y_zero = self.b.is_zero(&self.b.trunc(x, 63));
                let x_zero = self.b.is_zero(&self.b.trunc(abscissa, 63));
                let one_zero = self.b.xor(x_zero, y_zero);
                let abscissa_nan = nan(&mut self.b, abscissa);
                let either_nan = self.b.or(x_nan, abscissa_nan);
                let outside = self.b.or(-one_zero, either_nan);
                self.exclude_float_case(path, outside, "Math.atan2 outside its exact nonzero-axis cases")?;
                let pi = self.b.constant(std::f64::consts::PI.to_bits() as i64, 64);
                let half_pi = self.b.constant(std::f64::consts::FRAC_PI_2.to_bits() as i64, 64);
                let horizontal = self.b.ite_bits(self.b.negative(abscissa), &pi, &self.b.constant(0, 64));
                let mut bits = self.b.ite_bits(x_zero, &half_pi, &horizontal);
                bits[63] = self.b.negative(x);
                bits
            }
            "max" | "min" => {
                let Some(Val::I(y) | Val::J(y)) = args.get(1) else { return unsupported("floating-point extrema without the second operand") };
                let y_nan = nan(&mut self.b, y);
                let either_nan = self.b.or(x_nan, y_nan);
                let less = ordered_less(&mut self.b, x, y);
                let ordered = if name == "min" { self.b.ite_bits(less, x, y) } else { self.b.ite_bits(less, y, x) };
                if either_nan == FALSE { ordered } else {
                    // Math specifies NaN without specifying a raw payload. Cover both
                    // signs and every nonzero fraction, including signaling encodings.
                    let width = fraction_width(x);
                    let mut word = self.b.fresh(width);
                    let empty = self.b.is_zero(&word);
                    word[0] = self.b.or(word[0], empty);
                    word.resize(x.len() - 1, TRUE);
                    word.push(self.b.var());
                    path.unbound_platform_value = Some("an unspecified NaN payload");
                    self.b.ite_bits(either_nan, &word, &ordered)
                }
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

/// Normalize the unsigned magnitude, including abs(MIN_VALUE). The guard bit is exactly
/// half a unit in the last place. Sticky bits or an odd retained significand round it up.
fn int_to_float(b: &mut Blaster, x: &Bits) -> Bits {
    let sign = b.negative(x);
    let negated = b.neg(x);
    let magnitude = b.ite_bits(sign, &negated, x);
    let mut result = b.constant(0, 32);
    for lead in 0..32 {
        let mut word = b.constant(((127 + lead) as i64) << 23, 32);
        if lead <= 23 {
            word[23 - lead..23].copy_from_slice(&magnitude[..lead]);
        } else {
            let discard = lead - 23;
            word[..23].copy_from_slice(&magnitude[discard..lead]);
            let sticky = magnitude[..discard-1].iter().fold(FALSE, |seen, &bit| b.or(seen, bit));
            let above_or_odd = b.or(sticky, magnitude[discard]);
            let round = b.and(magnitude[discard-1], above_or_odd);
            // A carry from an all-ones significand advances the exponent too.
            word = b.add(&word, &b.zext(&vec![round], 32));
        }
        result = b.ite_bits(magnitude[lead], &word, &result);
    }
    result[31] = sign;
    result
}

/// JVM f2i/f2l/d2i/d2l. Align the implicit leading one with the sign position, shift
/// toward zero, then apply sign and saturation. NaN always converts to integer zero.
fn float_to_integral(b: &mut Blaster, x: &Bits, width: usize) -> Bits {
    let fraction = fraction_width(x);
    let bias = if fraction == 23 { 127 } else { 1023 };
    let exp = b.zext(&x[fraction..x.len()-1].to_vec(), 32);
    let cutoff = b.constant(bias + width as i64 - 1, 32);
    let shift = b.sub(&cutoff, &exp);
    let mut aligned = b.constant(0, width);
    let copied = fraction.min(width-1);
    aligned[width-1-copied..width-1].copy_from_slice(&x[fraction-copied..fraction]);
    aligned[width-1] = TRUE;
    let magnitude = b.ushr(&aligned, &shift);
    let minus = b.neg(&magnitude);
    let sign = b.negative(x);
    let signed = b.ite_bits(sign, &minus, &magnitude);
    let minimum = b.constant(1i64.wrapping_shl((width-1) as u32), width);
    let maximum = minimum.iter().map(|v| -*v).collect();
    let clamped = b.ite_bits(sign, &minimum, &maximum);
    let fits = b.ult(&exp, &cutoff);
    let integer = b.ite_bits(fits, &signed, &clamped);
    let tiny = b.ult(&exp, &b.constant(bias,32));
    let is_nan = nan(b, x);
    let zero = b.or(tiny, is_nan);
    b.ite_bits(zero, &b.constant(0,width), &integer)
}

/// Exact widening for all non-NaN binary32 inputs, including signed zero,
/// subnormals and infinity. A NaN's binary64 payload is not specified by Java.
fn float_to_double(b: &mut Blaster, x: &Bits) -> Bits {
    let exp = x[23..31].to_vec();
    let wide_exp = b.add(&b.zext(&exp, 11), &b.constant(1023-127,11));
    let mut normal = b.constant(0,64);
    normal[29..52].copy_from_slice(&x[..23]);
    normal[52..63].copy_from_slice(&wide_exp);
    let mut subnormal = b.constant(0,64);
    for lead in 0..23 {
        let mut word = b.constant(((1023-149+lead) as i64) << 52,64);
        word[52-lead..52].copy_from_slice(&x[..lead]);
        subnormal = b.ite_bits(x[lead], &word, &subnormal);
    }
    let zero_exp = b.is_zero(&exp);
    let finite = b.ite_bits(zero_exp, &subnormal, &normal);
    let infinite = b.all(&exp);
    let mut word = b.ite_bits(infinite, &b.constant(0x7ff0_0000_0000_0000,64), &finite);
    word[63] = x[31];
    word
}

fn raw_in_model(b: &mut Blaster, model: &mut Model, word: &Bits) -> i64 {
    let mut raw = 0u64;
    for (bit, &literal) in word.iter().enumerate() {
        raw |= u64::from(b.holds(model, literal)) << bit;
    }
    raw as i64
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
        self.finite_words(path, operation, operands, width, |engine, values| {
            let value = evaluate(values).ok_or_else(|| Stop::Unsupported(format!("{operation} with an unspecified NaN result encoding")))?;
            Ok(engine.b.constant(value, width))
        })
    }

    pub(super) fn finite_words<const N: usize>(&mut self, path: &Path, operation: &str, operands: [&Bits; N], width: usize,
        mut evaluate: impl FnMut(&mut Self, [i64; N]) -> Result<Bits, Stop>) -> Result<Bits, Stop> {
        const MAX_TUPLES: usize = 64;
        if operands.iter().all(|word| self.b.constant_value(word).is_some()) {
            let raw = operands.map(|word| self.b.constant_value(word).expect("constant"));
            return evaluate(self, raw);
        }
        let mut remaining = path.cond.clone();
        let mut result = self.b.constant(0, width);
        let mut count = 0;
        while self.solve(&remaining)? {
            if count == MAX_TUPLES {
                return unsupported(format!("{operation} with more than {MAX_TUPLES} reachable operand tuples"));
            }
            let mut model = self.b.snapshot();
            let values = operands.map(|word| raw_in_model(&mut self.b, &mut model, word));
            let mut selected = TRUE;
            for (word, value) in operands.iter().zip(values) {
                let equal = self.b.eq(word, &self.b.constant(value, word.len()));
                selected = self.b.and(selected, equal);
            }
            let value = evaluate(self, values)?;
            result = if count == 0 { value } else { self.b.ite_bits(selected, &value, &result) };
            remaining.push(-selected);
            count += 1;
        }
        Ok(result)
    }

    pub(super) fn floating_convert(&mut self, path: &mut Path, from: Kind, to: Kind) -> Result<Val, Stop> {
        let x = self.pop_word(path, from)?;
        if from == Kind::Int && to == Kind::Double { return Ok(Val::J(int_to_double(&mut self.b, &x))); }
        if from == Kind::Int && to == Kind::Float { return Ok(Val::I(int_to_float(&mut self.b, &x))); }
        if from == Kind::Float && to == Kind::Double {
            let is_nan = nan(&mut self.b, &x);
            self.exclude_float_case(path, is_nan, "Float to Double with an unspecified NaN result encoding")?;
            return Ok(Val::J(float_to_double(&mut self.b, &x)));
        }
        if matches!(from, Kind::Float | Kind::Double) && matches!(to, Kind::Int | Kind::Long) {
            return Ok(if to == Kind::Long { Val::J(float_to_integral(&mut self.b, &x, 64)) }
                      else { Val::I(float_to_integral(&mut self.b, &x, 32)) });
        }
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
            // A normal value divided by two stays exact while its exponent remains normal.
            if op == ArithOp::Div && self.b.constant_value(&y) == Some(if kind == Kind::Float { 0x4000_0000 } else { 0x4000_0000_0000_0000 }) {
                let fraction = fraction_width(&x);
                let exp = x[fraction..x.len()-1].to_vec();
                let small = self.b.ult(&exp, &self.b.constant(2, exp.len()));
                let special = self.b.all(&exp);
                let outside = self.b.or(small, special);
                let mut conditions = path.cond.clone();
                conditions.push(outside);
                if outside == FALSE || (outside != TRUE && !self.solve(&conditions)?) {
                    let lower = self.b.sub(&exp, &self.b.constant(1,exp.len()));
                    let mut half = x;
                    let end = half.len()-1;
                    half[fraction..end].copy_from_slice(&lower);
                    self.push(path, if kind == Kind::Double { Val::J(half) } else { Val::I(half) });
                    self.advance(path);
                    return Ok(None);
                }
            }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn conversion_circuits_cover_ties_subnormals_and_both_saturation_limits() {
        let mut b = Blaster::new();
        for lead in 0..32 {
            let center = 1_i32.wrapping_shl(lead);
            for delta in [-129, -3, -2, -1, 0, 1, 2, 3, 129] {
                let n = center.wrapping_add(delta);
                for i in [n, n.wrapping_neg()] {
                    let input = b.constant(i64::from(i), 32);
                    let result = int_to_float(&mut b, &input);
                    assert_eq!(b.constant_value(&result).unwrap() as u32, (i as f32).to_bits());
                }
            }
        }
        for exponent in [0_u64, 1, 126, 127, 157, 158, 190, 254, 255] {
            for mantissa in [0, 1, 0x3fffff, 0x400000, 0x7fffff] {
                for sign in [0, 1] {
                    let bits = (sign << 31 | exponent << 23 | mantissa) as u32;
                    let value = f32::from_bits(bits);
                    let word = b.constant(i64::from(bits), 32);
                    if !value.is_nan() {
                        let wide = float_to_double(&mut b, &word);
                        assert_eq!(b.constant_value(&wide).unwrap() as u64, f64::from(value).to_bits());
                    }
                    let int = float_to_integral(&mut b, &word, 32);
                    let long = float_to_integral(&mut b, &word, 64);
                    assert_eq!(b.constant_value(&int).unwrap() as i32, value as i32);
                    assert_eq!(b.constant_value(&long).unwrap(), value as i64);
                }
            }
        }
        for exponent in [0_u64, 1, 1022, 1023, 1053, 1054, 1085, 1086, 2046, 2047] {
            for mantissa in [0, 1, (1_u64 << 51), (1_u64 << 52) - 1] {
                for sign in [0, 1] {
                    let bits = sign << 63 | exponent << 52 | mantissa;
                    let value = f64::from_bits(bits);
                    let word = b.constant(bits as i64, 64);
                    let int = float_to_integral(&mut b, &word, 32);
                    let long = float_to_integral(&mut b, &word, 64);
                    assert_eq!(b.constant_value(&int).unwrap() as i32, value as i32);
                    assert_eq!(b.constant_value(&long).unwrap(), value as i64);
                }
            }
        }
    }
}
