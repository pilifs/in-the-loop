//! JVM comparisons over IEEE 754 interchange bits. The stack carries the raw word until an
//! opcode or a method descriptor supplies its interpretation. No host floating-point arithmetic
//! or solver-specific floating-point theory is involved.

use super::{unsupported, Bits, Blaster, Engine, Kind, Lit, Path, Step, Stop, Val, FALSE, TRUE};

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
        ("java/lang/Double", "isNaN", "(D)Z")
        | ("java/lang/Float", "isNaN", "(F)Z")
        | ("java/lang/Double", "doubleToRawLongBits" | "doubleToLongBits", "(D)J")
        | ("java/lang/Float", "floatToRawIntBits" | "floatToIntBits", "(F)I")
        | ("java/lang/Double", "longBitsToDouble", "(J)D")
        | ("java/lang/Float", "intBitsToFloat", "(I)F")
        | ("java/lang/Math" | "java/lang/StrictMath", "min" | "max", "(DD)D" | "(FF)F"))
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
