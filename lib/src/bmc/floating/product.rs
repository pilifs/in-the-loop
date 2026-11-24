//! Exact multiplication of two normal binary32 or binary64 operands with fixed exponents.
//! A SAT model suggests exponents. An UNSAT query is required before the circuit uses them.
use super::*;

fn significand(b: &Blaster, raw: &Bits, precision: usize) -> Bits {
    let mut significand = raw[..precision].to_vec();
    significand.push(TRUE);
    b.zext(&significand, 2 * (precision + 1))
}

/// Round the exact integer significand product once, under Java's nearest-even rule.
fn product_word(b: &mut Blaster, x: &Bits, y: &Bits, ex: i32, ey: i32) -> Bits {
    let width = x.len();
    let p = fraction_width(x);
    let bias = if width == 32 { 127 } else { 1023 };
    let e = ex + ey - 2 * bias;
    let min_subnormal = 1 - bias - p as i32;
    let sign = b.xor(x[width - 1], y[width - 1]);
    let mut word = b.constant(0, width);
    if e > bias {
        word[p..width - 1].fill(TRUE);
    } else if e >= min_subnormal - 2 {
        // (2^p + X)(2^p + Y) is in [2^(2p), (2^(p+1)-1)^2]. No bit is discarded here.
        let full = b.mul(&significand(b, x, p), &significand(b, y, p));
        if e == min_subnormal - 1 {
            // In units of the least subnormal the exact result is in [1/2, 2).
            // The lower tie occurs exactly when BOTH fractions are zero. At the upper
            // tie, 3/2, the even neighbour is two (the two leading product bits are 11).
            let x_min = b.is_zero(&x[..p].to_vec());
            let y_min = b.is_zero(&y[..p].to_vec());
            let tie = b.and(x_min, y_min);
            let at_least_three_halves = b.and(full[2 * p + 1], full[2 * p]);
            word[0] = b.and(-tie, -at_least_three_halves);
            word[1] = b.and(-tie, at_least_three_halves);
        } else if e < 1 - bias {
            // The unrounded product has units of 2^(e-2p). Shift to the least
            // subnormal's unit. A carry into the least normal is the same encoding.
            let discard = (min_subnormal - e + 2 * p as i32) as usize;
            let keep = b.zext(&full[discard..].to_vec(), width);
            let up = round_up(b, &full, discard);
            word = b.add(&keep, &b.zext(&vec![up], width));
        } else {
            let high = full[2 * p + 1];
            let lo_up = round_up(b, &full, p);
            let hi_up = round_up(b, &full, p + 1);
            let lo = full[p..2*p].to_vec();
            let hi = full[p+1..2*p+1].to_vec();
            let all_ones = b.all(&lo);
            let carry = b.and(all_ones, lo_up);
            let next_exponent = b.or(high, carry);
            let exponent_width = width - 1 - p;
            let exponent = b.ite_bits(next_exponent,
                &b.constant(i64::from(e + bias + 1), exponent_width),
                &b.constant(i64::from(e + bias), exponent_width));
            word[p..width-1].copy_from_slice(&exponent);
            let retained = b.ite_bits(high, &hi, &lo);
            let up = b.ite(high, hi_up, lo_up);
            // In the high binade the exact upper bound divided by 2^(p+1) is
            // 2^(p+1)-2 + 2^(-p-1), so rounding cannot overflow that binade.
            let mut fraction = b.add(&retained, &b.zext(&vec![up], p));
            if e == bias {
                // Any result that enters the next binade overflows to signed infinity.
                fraction = b.ite_bits(next_exponent, &b.constant(0, p), &fraction);
            }
            word[..p].copy_from_slice(&fraction);
        }
    }
    word[width - 1] = sign;
    word
}

impl Engine<'_> {
    pub(super) fn fixed_exponent_product(&mut self, path: &Path, x: &Bits, y: &Bits) -> Result<Option<Bits>, Stop> {
        if self.b.constant_value(x).is_some() && self.b.constant_value(y).is_some() {
            return Ok(None);
        }
        let p = fraction_width(x);
        let end = x.len() - 1;
        let ex = x[p..end].to_vec();
        let ey = y[p..end].to_vec();
        // Zero times any finite operand is signed zero; infinity and NaN stay with the fallback.
        for (raw, other_exponent) in [(x, &ey), (y, &ex)] {
            if raw[..end].iter().all(|&bit| bit == FALSE) {
                let special = self.b.all(other_exponent);
                let mut conditions = path.cond.clone();
                conditions.push(special);
                if special == FALSE || !self.solve(&conditions)? {
                    let mut zero = self.b.constant(0, x.len());
                    zero[end] = self.b.xor(x[end], y[end]);
                    return Ok(Some(zero));
                }
                return Ok(None);
            }
        }
        if !self.solve(&path.cond)? { return Ok(None); }
        let sampled = |e: &Bits| e.iter().enumerate().fold(0i32, |v, (i, &bit)| v | (i32::from(self.b.value(bit)) << i));
        let (a, c) = (sampled(&ex), sampled(&ey));
        let special = (1 << ex.len()) - 1;
        if a == 0 || c == 0 || a == special || c == special {
            return Ok(None);
        }
        let first = self.b.eq(&ex, &self.b.constant(i64::from(a), ex.len()));
        let second = self.b.eq(&ey, &self.b.constant(i64::from(c), ey.len()));
        let both = self.b.and(first, second);
        let mut different = path.cond.clone();
        different.push(-both);
        if both != TRUE && self.solve(&different)? { return Ok(None); }
        Ok(Some(product_word(&mut self.b, x, y, a, c)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn products_round_once_at_normal_subnormal_and_overflow_boundaries() {
        let mut b = Blaster::new();
        for width in [32, 64] {
            let (p, bias) = if width == 32 { (23,127) } else { (52,1023) };
            let tail = (1u64 << p) - 1;
            let tiny = 1 - bias - p as i32;
            for (a, c) in [(0,1), (0,0), (1-bias,0), (1-bias,-1), (tiny/2, tiny-tiny/2),
                           (-75,-75), (tiny/2,tiny-1-tiny/2), (tiny/2,tiny-2-tiny/2),
                           (tiny/2,tiny-3-tiny/2), (bias,0), (bias,1)] {
                for (fx, fy) in [(0,0), (1,1), (tail,tail), (tail,0), ((tail+1)/2,0),
                                 ((tail+1)/2,1), ((tail+1)/2,tail-1), (tail,1)] {
                    let x = (1u64 << (width-1)) | (((a+bias) as u64) << p) | fx;
                    let y = (((c+bias) as u64) << p) | fy;
                    let xb = b.constant(x as i64, width);
                    let yb = b.constant(y as i64, width);
                    let result = product_word(&mut b, &xb, &yb, a+bias, c+bias);
                    let actual = b.constant_value(&result).unwrap() as u64;
                    if width == 32 {
                        assert_eq!(actual as u32, (f32::from_bits(x as u32)*f32::from_bits(y as u32)).to_bits());
                    } else {
                        assert_eq!(actual, (f64::from_bits(x)*f64::from_bits(y)).to_bits());
                    }
                }
            }
        }
    }
}
