//! Enclose sin and cos of an exact binary64 argument. The host library suggests where
//! to look. Only an alternating Taylor bound, compared to adjacent doubles as exact
//! rationals, can certify the bracket. Java permits either endpoint of a one-ulp
//! bracket (java.lang.Math, "Quality of implementation specifications").

use num_rational::BigRational;
use num_traits::One;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(super) enum Function { Sin, Cos }

fn neighbor(x: f64, up: bool) -> f64 {
    if x == 0.0 { return f64::from_bits(if up { 1 } else { (1 << 63) | 1 }); }
    let raw = x.to_bits();
    f64::from_bits(if up == x.is_sign_positive() { raw + 1 } else { raw - 1 })
}

impl Function {
    pub(super) fn bracket(self, x: f64) -> Option<(u64, u64)> {
        if x == 0.0 {
            let exact = if self == Self::Sin { x } else { 1.0 };
            return Some((exact.to_bits(), exact.to_bits()));
        }
        // Direct Taylor expansion has a bounded cost on this interval. Leave
        // underflowing sine, where even the sign of a zero matters, outside it.
        if !x.is_finite() || x.abs() > 8.0 || (self == Self::Sin && x.abs() < f64::MIN_POSITIVE) {
            return None;
        }
        let guess = match self { Self::Sin => x.sin(), Self::Cos => x.cos() };
        if !guess.is_finite() || guess == 0.0 { return None; }
        let prev = neighbor(guess, false);
        let next = neighbor(guess, true);
        let endpoints = [neighbor(prev, false), prev, guess, next, neighbor(next, true)];
        let exact = endpoints.map(|v| BigRational::from_float(v).expect("finite endpoint"));
        let arg = BigRational::from_float(x)?;
        let square = &arg * &arg;
        let mut degree = if self == Self::Sin { 1 } else { 0 };
        let mut term = if self == Self::Sin { arg } else { BigRational::one() };
        let mut sum = term.clone();
        while degree < 96 {
            let divisor = BigRational::from_integer(((degree + 1) * (degree + 2)).into());
            term = -term * &square / &divisor;
            let following = &sum + &term;
            // Once term magnitudes decrease, every subsequent ratio is smaller.
            // The true value lies strictly between these partial sums for x != 0.
            if divisor > square {
                let (lo, hi) = if sum < following { (&sum, &following) } else { (&following, &sum) };
                if let Some(i) = exact.windows(2).position(|pair| &pair[0] <= lo && hi <= &pair[1]) {
                    return Some((endpoints[i].to_bits(), endpoints[i + 1].to_bits()));
                }
            }
            sum = following;
            degree += 2;
        }
        None
    }
}
