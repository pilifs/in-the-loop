//! Shrinking a counterexample: the input a model checker refutes a property with is whatever satisfied the solver,
//! an eight-element array of large numbers as often as not. Given an oracle that says whether an input still
//! violates the property, the shrinker makes the input smaller one step at a time, as a property-based testing
//! library does, until no single step keeps it a counterexample: an array loses an element, a number moves
//! towards zero (to zero, or by a power of two, the largest first; the values of a sign together, too, for an end
//! tied to a length), a `true` becomes `false`.
//!
//! The result is a local minimum, not the smallest counterexample there is, but it is small, and it is the same
//! one on every run, where the solver's is not. Every candidate is checked by the oracle, so the shrunk input is a
//! counterexample by the same standard as the original.

use crate::classfile::Type;
use crate::interp::Value;
use crate::jbmc::Argument;

/// The outcome of shrinking: the arguments reached, and the number of candidates the oracle was asked about.
#[derive(Debug, Clone, PartialEq)]
pub struct Shrunk {
    pub arguments: Vec<Argument>,
    pub runs: u32,
}

/// Shrinks `arguments` (of the parameter types `types`) while `fails` says they still violate the property;
/// `fails` answers `None` when it cannot tell, which rejects the candidate. At most `budget` candidates are tried.
pub fn shrink(types: &[Type], arguments: Vec<Argument>, budget: u32, mut fails: impl FnMut(&[Argument]) -> Option<bool>) -> Shrunk {
    let mut current = arguments;
    let mut runs = 0;
    'outer: loop {
        for candidate in candidates(types, &current) {
            if runs >= budget {
                break 'outer;
            }
            runs += 1;
            if fails(&candidate) == Some(true) {
                current = candidate;
                continue 'outer;
            }
        }
        break;
    }
    Shrunk { arguments: current, runs }
}

/// The inputs one step smaller than `current`: shorter arrays first (one array at a time), then shorter or plainer
/// Strings, then the same index dropped from every array (for parallel arrays whose lengths an assumption ties
/// together), then smaller scalars, then smaller elements.
fn candidates(types: &[Type], current: &[Argument]) -> Vec<Vec<Argument>> {
    let mut out = Vec::new();
    let with = |i: usize, a: Argument| {
        let mut c = current.to_vec();
        c[i] = a;
        c
    };
    let mut longest = 0;
    for (i, argument) in current.iter().enumerate() {
        if let Argument::Array(data) = argument {
            longest = longest.max(data.len());
            for j in 0..data.len() {
                let mut shorter = data.clone();
                shorter.remove(j);
                out.push(with(i, Argument::Array(shorter)));
            }
        }
    }
    // A String one unit shorter, then with a unit that isn't printable ASCII made `a`: each step shortens it or
    // leaves one unit fewer to escape, so a witness reads as text where the difference allows.
    for (i, argument) in current.iter().enumerate() {
        if let Argument::String(units) = argument {
            for j in 0..units.len() {
                let mut shorter = units.clone();
                shorter.remove(j);
                out.push(with(i, Argument::String(shorter)));
            }
            for (j, u) in units.iter().enumerate() {
                if !(0x20..=0x7e).contains(u) {
                    let mut plain = units.clone();
                    plain[j] = u16::from(b'a');
                    out.push(with(i, Argument::String(plain)));
                }
            }
        }
    }
    let arrays = current.iter().filter(|a| matches!(a, Argument::Array(_))).count();
    if arrays > 1 {
        for j in 0..longest {
            let mut c = current.to_vec();
            for a in &mut c {
                if let Argument::Array(data) = a {
                    if j < data.len() {
                        data.remove(j);
                    }
                }
            }
            out.push(c);
        }
    }
    for (i, (argument, t)) in current.iter().zip(types).enumerate() {
        if let Argument::Scalar(v) = argument {
            for smaller in smaller(*v, t) {
                out.push(with(i, Argument::Scalar(smaller)));
            }
        }
    }
    // Values a property ties together (an end equal to a length, a pc equal to an entry's end) shrink together:
    // every positive integral value, scalar or element, moves down by the same amount, the smallest to zero
    // first, and every negative one up.
    for sign in [1i128, -1] {
        let tied: Vec<(usize, Option<usize>, i128)> = current
            .iter()
            .zip(types)
            .enumerate()
            .flat_map(|(i, (a, t))| match (a, t) {
                (Argument::Scalar(v), t) => integral(*v, t).map(|x| (i, None, x)).into_iter().collect::<Vec<_>>(),
                (Argument::Array(data), Type::Array(element)) => data.iter().enumerate().filter_map(|(j, v)| integral(*v, element).map(|x| (i, Some(j), x))).collect(),
                _ => Vec::new(),
            })
            .filter(|(_, _, x)| x.signum() == sign)
            .collect();
        if tied.len() < 2 {
            continue;
        }
        let nearest = tied.iter().map(|(_, _, x)| x.abs()).min().unwrap_or(0);
        for value in towards_zero(nearest) {
            let delta = (nearest - value) * sign;
            let mut c = current.to_vec();
            for (i, j, x) in &tied {
                let moved = x - delta;
                match (&mut c[*i], j) {
                    (Argument::Scalar(v), None) => *v = narrowed(*v, moved),
                    (Argument::Array(data), Some(j)) => data[*j] = narrowed(data[*j], moved),
                    _ => {}
                }
            }
            out.push(c);
        }
    }
    for (i, (argument, t)) in current.iter().zip(types).enumerate() {
        if let (Argument::Array(data), Type::Array(element)) = (argument, t) {
            for (j, v) in data.iter().enumerate() {
                for smaller in smaller(*v, element) {
                    let mut d = data.clone();
                    d[j] = smaller;
                    out.push(with(i, Argument::Array(d)));
                }
            }
        }
    }
    out
}

/// An integral value as a number, for the values that move together; a boolean is not one.
fn integral(v: Value, t: &Type) -> Option<i128> {
    match v {
        Value::Int(x) if *t != Type::Boolean => Some(i128::from(x)),
        Value::Long(x) => Some(i128::from(x)),
        _ => None,
    }
}

/// `x` in the width of `like`.
fn narrowed(like: Value, x: i128) -> Value {
    match like {
        Value::Long(_) => Value::Long(x as i64),
        _ => Value::Int(x as i32),
    }
}

/// The values one step closer to zero than `v`, nearest zero first.
fn smaller(v: Value, t: &Type) -> Vec<Value> {
    let mut out: Vec<Value> = match v {
        Value::Int(0) | Value::Long(0) => Vec::new(),
        Value::Int(_) if *t == Type::Boolean => vec![Value::Int(0)],
        Value::Int(x) => towards_zero(i128::from(x)).into_iter().map(|c| Value::Int(c as i32)).collect(),
        Value::Long(x) => towards_zero(i128::from(x)).into_iter().map(|c| Value::Long(c as i64)).collect(),
        Value::Float(x) => vec![Value::Float(0.0), Value::Float(x.trunc()), Value::Float(x / 2.0)],
        Value::Double(x) => vec![Value::Double(0.0), Value::Double(x.trunc()), Value::Double(x / 2.0)],
        Value::Null | Value::Ref(_) => Vec::new(),
    };
    // A NaN or an infinity is not made smaller by arithmetic; only zero is tried for it.
    out.retain(|c| match c {
        Value::Float(f) => f.is_finite(),
        Value::Double(f) => f.is_finite(),
        _ => true,
    });
    let same = |a: &Value, b: &Value| match (a, b) {
        (Value::Float(x), Value::Float(y)) => x.to_bits() == y.to_bits(),
        (Value::Double(x), Value::Double(y)) => x.to_bits() == y.to_bits(),
        _ => a == b,
    };
    let mut distinct: Vec<Value> = Vec::new();
    for c in out {
        if !same(&c, &v) && !distinct.iter().any(|d| same(d, &c)) {
            distinct.push(c);
        }
    }
    distinct
}

/// Zero, then `x` less each power of two up to its magnitude, the largest first: big steps, so that a value which
/// must stay large settles in logarithmically many rounds, and even steps, so that a value which must stay odd
/// can take them.
fn towards_zero(x: i128) -> Vec<i128> {
    let mut out = vec![0];
    let magnitude = x.abs();
    let mut delta = 1i128 << (127 - magnitude.leading_zeros());
    while delta >= 1 {
        let candidate = x - x.signum() * delta;
        if candidate != 0 && !out.contains(&candidate) {
            out.push(candidate);
        }
        delta /= 2;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ints(data: &[i32]) -> Argument {
        Argument::Array(data.iter().map(|v| Value::Int(*v)).collect())
    }

    #[test]
    fn shrinks_to_a_local_minimum_the_oracle_still_rejects() {
        // "Some element is at least 10, and key is positive": the smallest counterexample is [10] with key 1.
        let types = [Type::Array(Box::new(Type::Int)), Type::Int];
        let fails = |args: &[Argument]| match (&args[0], &args[1]) {
            (Argument::Array(d), Argument::Scalar(Value::Int(k))) => Some(d.iter().any(|v| v.as_int() >= 10) && *k > 0),
            _ => None,
        };
        let shrunk = shrink(&types, vec![ints(&[536870912, 0, 7, 0, 99, 0, 0, 0]), Argument::Scalar(Value::Int(1_000_001))], 10_000, fails);
        assert_eq!(shrunk.arguments, vec![ints(&[10]), Argument::Scalar(Value::Int(1))]);
        assert!(shrunk.runs > 0 && shrunk.runs < 300, "{} runs", shrunk.runs);
        // The same input shrinks to the same minimum, and a minimum stays put.
        let again = shrink(&types, shrunk.arguments.clone(), 10_000, fails);
        assert_eq!(again.arguments, shrunk.arguments);
    }

    #[test]
    fn drops_the_same_index_from_parallel_arrays() {
        // Two columns of equal length, and a property that fails when some row has start == end.
        let types = [Type::Array(Box::new(Type::Int)), Type::Array(Box::new(Type::Int))];
        let fails = |args: &[Argument]| match (&args[0], &args[1]) {
            (Argument::Array(s), Argument::Array(e)) => Some(s.len() == e.len() && s.iter().zip(e).any(|(a, b)| a == b)),
            _ => None,
        };
        let shrunk = shrink(&types, vec![ints(&[4, 7, 7, 1]), ints(&[5, 7, 9, 1])], 10_000, fails);
        // One row is left, and its two equal values move down to zero together.
        assert_eq!(shrunk.arguments, vec![ints(&[0]), ints(&[0])]);
    }

    #[test]
    fn moves_tied_scalars_together() {
        // "end == length, and the range is not empty": each alone cannot move, so they move together.
        let types = [Type::Int, Type::Int, Type::Int];
        let fails = |args: &[Argument]| match (&args[0], &args[1], &args[2]) {
            (Argument::Scalar(Value::Int(start)), Argument::Scalar(Value::Int(end)), Argument::Scalar(Value::Int(length))) => Some(end == length && start < end),
            _ => None,
        };
        let shrunk = shrink(&types, vec![Argument::Scalar(Value::Int(12)), Argument::Scalar(Value::Int(15)), Argument::Scalar(Value::Int(15))], 1000, fails);
        assert_eq!(shrunk.arguments, vec![Argument::Scalar(Value::Int(0)), Argument::Scalar(Value::Int(1)), Argument::Scalar(Value::Int(1))]);
        let negative = shrink(&[Type::Long, Type::Long], vec![Argument::Scalar(Value::Long(-40)), Argument::Scalar(Value::Long(-40))], 1000, |args| Some(args[0] == args[1] && args[0] != Argument::Scalar(Value::Long(0))));
        assert_eq!(negative.arguments, vec![Argument::Scalar(Value::Long(-1)), Argument::Scalar(Value::Long(-1))]);
        // An element and a scalar: "pc equals the entry's end", which moves to zero together.
        let types = [Type::Array(Box::new(Type::Int)), Type::Int];
        let tied = shrink(&types, vec![ints(&[2]), Argument::Scalar(Value::Int(2))], 1000, |args| match (&args[0], &args[1]) {
            (Argument::Array(d), Argument::Scalar(Value::Int(pc))) => Some(d.len() == 1 && d[0].as_int() == *pc),
            _ => None,
        });
        assert_eq!(tied.arguments, vec![ints(&[0]), Argument::Scalar(Value::Int(0))]);
    }

    #[test]
    fn stops_at_the_budget_and_on_an_oracle_that_cannot_tell() {
        let types = [Type::Long];
        let shrunk = shrink(&types, vec![Argument::Scalar(Value::Long(1 << 40))], 100, |_| Some(true));
        assert_eq!(shrunk.runs, 1, "the first candidate is zero, and zero has no candidates");
        assert_eq!(shrunk.arguments, vec![Argument::Scalar(Value::Long(0))]);
        let budgeted = shrink(&types, vec![Argument::Scalar(Value::Long(1 << 40))], 2, |args| Some(args[0] != Argument::Scalar(Value::Long(0))));
        assert_eq!(budgeted.runs, 2, "zero is rejected, halving is accepted, and the budget is spent");
        assert_eq!(budgeted.arguments, vec![Argument::Scalar(Value::Long(1 << 39))]);
        let stuck = shrink(&types, vec![Argument::Scalar(Value::Long(5))], 100, |_| None);
        assert_eq!(stuck.arguments, vec![Argument::Scalar(Value::Long(5))]);
        assert_eq!(stuck.runs, 4, "0, 1, 3 and 4 were offered");
    }

    #[test]
    fn steps_towards_zero_by_type() {
        assert_eq!(smaller(Value::Int(9), &Type::Int), vec![Value::Int(0), Value::Int(1), Value::Int(5), Value::Int(7), Value::Int(8)]);
        assert_eq!(smaller(Value::Int(-1), &Type::Int), vec![Value::Int(0)]);
        assert_eq!(smaller(Value::Int(-6), &Type::Int), vec![Value::Int(0), Value::Int(-2), Value::Int(-4), Value::Int(-5)]);
        let min = smaller(Value::Int(i32::MIN), &Type::Int);
        assert_eq!(min.len(), 32);
        assert_eq!((min[0], min[1], min[31]), (Value::Int(0), Value::Int(i32::MIN / 2), Value::Int(i32::MIN + 1)));
        assert_eq!(smaller(Value::Long(i64::MIN), &Type::Long).len(), 64);
        assert_eq!(smaller(Value::Int(1), &Type::Boolean), vec![Value::Int(0)]);
        assert_eq!(smaller(Value::Int(0), &Type::Char), Vec::new());
        assert_eq!(smaller(Value::Float(f32::NAN), &Type::Float), vec![Value::Float(0.0)]);
        assert_eq!(smaller(Value::Double(2.5), &Type::Double), vec![Value::Double(0.0), Value::Double(2.0), Value::Double(1.25)]);
        assert_eq!(smaller(Value::Double(-0.0), &Type::Double), vec![Value::Double(0.0)], "negative zero steps to zero");
    }
}
