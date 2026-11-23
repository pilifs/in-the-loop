//! Exact addition and subtraction when the path bounds both normal exponents.

use super::*;

// Signed fixed-point sum in units of the lowest admitted operand's ulp. The
// domain check guarantees every nonzero result is normal, with room for rounding.
fn binade_sum(b: &mut Blaster, x: &Bits, y: &Bits, low: u32, high: u32, subtract: bool) -> Bits {
    let frac = fraction_width(x);
    let width = x.len();
    let span = (high - low) as usize;
    let fixed_width = frac + span + 3;
    let mut aligned = |raw: &Bits, negate: bool| {
        let exponent = raw[frac..width - 1].to_vec();
        let candidate = |shift: usize| {
            let mut word = vec![FALSE; fixed_width];
            word[shift..shift + frac].copy_from_slice(&raw[..frac]);
            word[shift + frac] = TRUE;
            word
        };
        let mut magnitude = candidate(0);
        for shift in 1..=span {
            let guard = b.eq(
                &exponent,
                &b.constant(i64::from(low) + shift as i64, exponent.len()),
            );
            magnitude = b.ite_bits(guard, &candidate(shift), &magnitude);
        }
        let sign = if negate {
            -raw[width - 1]
        } else {
            raw[width - 1]
        };
        let negative = b.neg(&magnitude);
        b.ite_bits(sign, &negative, &magnitude)
    };
    let left = aligned(x, false);
    let right = aligned(y, subtract);
    let sum = b.add(&left, &right);
    let bias = if width == 32 { 127 } else { 1023 };
    scaled_integer_to_floating(b, &sum, width, i64::from(low) - bias - frac as i64)
}

impl Engine<'_> {
    /// Use the fixed-point circuit only after a solver query excludes every
    /// exponent outside a small normal band for *both* independent operands.
    pub(super) fn bounded_binade_sum(
        &mut self,
        path: &Path,
        x: &Bits,
        y: &Bits,
        subtract: bool,
    ) -> Result<Option<Bits>, Stop> {
        if self.b.constant_value(x).is_some() && self.b.constant_value(y).is_some() {
            return Ok(None);
        }
        let frac = fraction_width(x);
        let ex = x[frac..x.len() - 1].to_vec();
        let ey = y[frac..y.len() - 1].to_vec();
        if !self.solve(&path.cond)? {
            return Ok(None);
        }
        // A model proposes the band. Only the independent UNSAT test below authorizes it.
        let sampled = |w: &Bits| {
            w.iter()
                .enumerate()
                .fold(0u32, |n, (i, &bit)| n | (u32::from(self.b.value(bit)) << i))
        };
        let (a, b) = (sampled(&ex), sampled(&ey));
        let (lo, hi) = (a.min(b), a.max(b));
        for (low, high) in [
            (lo, hi),
            (lo, hi + 1),
            (lo.saturating_sub(1), hi),
            (lo.saturating_sub(1), hi + 1),
        ] {
            if high - low > 2 || low <= frac as u32 || high + 2 >= (1 << ex.len()) - 1 {
                continue;
            }
            let l = self.b.constant(i64::from(low), ex.len());
            let h = self.b.constant(i64::from(high), ex.len());
            let mut outside = FALSE;
            for e in [&ex, &ey] {
                let below = self.b.ult(e, &l);
                let above = self.b.ult(&h, e);
                let invalid = self.b.or(below, above);
                outside = self.b.or(outside, invalid);
            }
            let mut conditions = path.cond.clone();
            conditions.push(outside);
            if outside == FALSE || !self.solve(&conditions)? {
                return Ok(Some(binade_sum(&mut self.b, x, y, low, high, subtract)));
            }
        }
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_point_float_sums_cover_signs_ties_cancellation_and_adjacent_exponents() {
        let mut b = Blaster::new();
        for width in [32, 64] {
            let (fraction, bias) = if width == 32 { (23, 127) } else { (52, 1023) };
            for sign in [0u64, 1] {
                for shift in 0..=2 {
                    let left = sign << (width - 1) | (bias + shift) << fraction | 1;
                    for tail in [0, 1, 2, (1 << fraction) - 1] {
                        for right_sign in [0u64, 1] {
                            let right = right_sign << (width - 1) | bias << fraction | tail;
                            let x = b.constant(left as i64, width);
                            let y = b.constant(right as i64, width);
                            for subtract in [false, true] {
                                let result = binade_sum(
                                    &mut b,
                                    &x,
                                    &y,
                                    bias as u32,
                                    (bias + shift) as u32,
                                    subtract,
                                );
                                let actual = b.constant_value(&result).unwrap() as u64;
                                if width == 32 {
                                    let (a, c) =
                                        (f32::from_bits(left as u32), f32::from_bits(right as u32));
                                    assert_eq!(
                                        actual as u32,
                                        (if subtract { a - c } else { a + c }).to_bits()
                                    );
                                } else {
                                    let (a, c) = (f64::from_bits(left), f64::from_bits(right));
                                    assert_eq!(
                                        actual,
                                        (if subtract { a - c } else { a + c }).to_bits()
                                    );
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
