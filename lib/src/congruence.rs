//! Multiplication congruence lemmas for a formula JBMC wrote as SMT-LIB (`verification/findings.md`, VF-018).
//!
//! JBMC's SAT backend encodes every multiplication as a circuit of its own, in the order of its operands. Two
//! products whose operands are equal, or equal crosswise, are then equal only through those circuits, which a SAT
//! solver can take hours to see: `cents * quantity` in one version of a method and `quantity * cents` in the
//! other, or a product of a conditional and the conditional of two products. The tool's own checker ties such
//! products together when it builds them ([`crate::bmc::bits`]); JBMC does not.
//!
//! This module adds what is missing, to the formula and not to the claim. For every two products `p = a * b` and
//! `q = c * d` of one width in the formula, it asserts
//!
//! ```text
//! ((a = c and b = d) or (a = d and b = c)) => p = q
//! ```
//!
//! which holds of fixed-width multiplication whatever the operands are, overflow included: a function gives
//! equal results on equal arguments, and multiplication modulo a power of two commutes. So the formula with the
//! lemmas has exactly the models the formula has. Nothing else is touched: every line JBMC wrote is kept as it
//! is, and the lemmas go in before `(check-sat)`.
//!
//! It is cautious about what it reads. A product is taken only where its text means the same thing anywhere in
//! the file: not under a binder (`let`, a quantifier), not in a function with parameters. Its width has to be
//! read off its operands, or it is left out. A file with scopes (`push`, `pop`) or more than one `(check-sat)` is
//! left alone. Leaving a product out loses a lemma, never soundness.
//!
//! [`crate::jbmc::run`] is where it is used, and says when.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::time::Duration;

/// More products of one width than this are not paired: the lemmas grow with the square of their number.
pub const MAX_PRODUCTS: usize = 48;

/// The variable that names the Z3 to use, or turns the step off (`off`). Unset: the `z3` on `PATH`.
pub const ENV: &str = "JVMCONTRACT_Z3";

/// A formula with its lemmas.
#[derive(Debug, Clone, PartialEq)]
pub struct Prepared {
    /// The formula as JBMC wrote it, with the lemmas before its `(check-sat)`.
    pub text: String,
    /// The distinct products the lemmas are about.
    pub products: usize,
    pub lemmas: usize,
}

/// What a result records when this step, not JBMC's SAT solver, gave the proof.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Record {
    /// The solver's executable.
    pub solver: String,
    /// Its version, as `5.3.3`; none when it could not be read.
    pub version: Option<String>,
    pub products: usize,
    pub lemmas: usize,
    /// How long JBMC's own solver had run without a verdict when this step was tried.
    pub after_seconds: f64,
    /// The step's own time: writing the formula, the lemmas, and the proof.
    pub seconds: f64,
}

impl Record {
    /// The solver as a result's evidence names it.
    pub fn sat(&self, options: &[String]) -> crate::statement::Sat {
        crate::statement::Sat {
            solver: "Z3".into(),
            version: self.version.clone(),
            source: format!(
                "{}, given the formula JBMC wrote as SMT-LIB with {} multiplication congruence lemma(s) over {} product(s) added by jvmcontract, after JBMC's own solver had given no verdict in {:.0} s",
                self.solver, self.lemmas, self.products, self.after_seconds
            ),
            configuration: options.to_vec(),
        }
    }

    /// The checker's name with this step in it: `JBMC 6.11.0, its formula decided by Z3 5.3.3 with 6 multiplication
    /// congruence lemmas`.
    pub fn checker(&self, jbmc: &str) -> String {
        let version = self.version.as_deref().map(|v| format!(" {v}")).unwrap_or_default();
        format!("{jbmc}, its formula decided by Z3{version} with {} multiplication congruence lemma(s)", self.lemmas)
    }
}

/// The Z3 to use: [`ENV`]'s, or the one on `PATH`; none when there is none or the variable says `off`.
pub fn solver() -> Option<PathBuf> {
    match std::env::var(ENV).ok().map(|v| v.trim().to_string()).filter(|v| !v.is_empty()) {
        Some(v) if v.eq_ignore_ascii_case("off") => None,
        Some(v) => Some(PathBuf::from(v)).filter(|p| p.is_file()),
        None => std::env::var_os("PATH").and_then(|paths| std::env::split_paths(&paths).map(|d| d.join("z3")).find(|p| p.is_file())),
    }
}

/// The version `z3 --version` prints, as `5.3.3`.
pub fn version(solver: &Path) -> Option<String> {
    let out = std::process::Command::new(solver).arg("--version").output().ok()?;
    let text = String::from_utf8_lossy(&out.stdout);
    text.split_whitespace().find(|w| w.chars().next().is_some_and(|c| c.is_ascii_digit()) && w.contains('.')).map(str::to_string)
}

/// How long JBMC's own solver runs before the step is tried: a twentieth of the run's limit, 5 s at least and 30 s
/// at most. Runs that finish sooner, nearly all of them, never meet it, and neither does a run whose whole limit
/// is shorter, such as a preliminary stage over small inputs on its share of a short check.
pub fn patience(timeout: Duration) -> Duration {
    (timeout / 20).clamp(Duration::from_secs(5), Duration::from_secs(30))
}

/// How long the step may take: a tenth of the run's limit, 60 s at most, and never more than the run has left.
/// JBMC's own solver is paused meanwhile and goes on afterwards if the step proved nothing, with the time it had:
/// the step's time is not taken from it.
pub fn cap(timeout: Duration) -> Duration {
    (timeout / 10).min(Duration::from_secs(60))
}

#[derive(Debug, Clone, PartialEq)]
enum Sexp<'a> {
    Atom(&'a str),
    List(Vec<Sexp<'a>>),
}

impl<'a> Sexp<'a> {
    fn head(&self) -> Option<&'a str> {
        match self {
            Sexp::List(items) => match items.first() {
                Some(Sexp::Atom(a)) => Some(a),
                _ => None,
            },
            Sexp::Atom(_) => None,
        }
    }

    fn items(&self) -> &[Sexp<'a>] {
        match self {
            Sexp::List(items) => items,
            Sexp::Atom(_) => &[],
        }
    }

    fn atom(&self) -> Option<&'a str> {
        match self {
            Sexp::Atom(a) => Some(a),
            Sexp::List(_) => None,
        }
    }

    fn render(&self, out: &mut String) {
        match self {
            Sexp::Atom(a) => out.push_str(a),
            Sexp::List(items) => {
                out.push('(');
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        out.push(' ');
                    }
                    item.render(out);
                }
                out.push(')');
            }
        }
    }

    fn text(&self) -> String {
        let mut out = String::new();
        self.render(&mut out);
        out
    }
}

/// The file's commands, each with the offset of its opening parenthesis. None for text that is not a sequence of
/// balanced lists: nothing is guessed from a file that can't be read.
fn commands(text: &str) -> Option<Vec<(usize, Sexp<'_>)>> {
    let bytes = text.as_bytes();
    let (mut i, mut stack, mut out): (usize, Vec<(usize, Vec<Sexp>)>, Vec<(usize, Sexp)>) = (0, Vec::new(), Vec::new());
    while i < bytes.len() {
        match bytes[i] {
            b if b.is_ascii_whitespace() => i += 1,
            b';' => i = text[i..].find('\n').map_or(bytes.len(), |n| i + n),
            b'(' => {
                stack.push((i, Vec::new()));
                i += 1;
            }
            b')' => {
                let (start, items) = stack.pop()?;
                match stack.last_mut() {
                    Some((_, parent)) => parent.push(Sexp::List(items)),
                    None => out.push((start, Sexp::List(items))),
                }
                i += 1;
            }
            first => {
                let end = match first {
                    b'|' => i + 1 + text[i + 1..].find('|')? + 1,
                    b'"' => {
                        // A string ends at a quote that is not doubled.
                        let mut j = i + 1;
                        loop {
                            j += text[j..].find('"')?;
                            if bytes.get(j + 1) == Some(&b'"') {
                                j += 2;
                            } else {
                                break j + 1;
                            }
                        }
                    }
                    _ => i + bytes[i..].iter().position(|b| b.is_ascii_whitespace() || matches!(b, b'(' | b')' | b';' | b'|' | b'"')).unwrap_or(bytes.len() - i),
                };
                stack.last_mut()?.1.push(Sexp::Atom(&text[i..end]));
                i = end;
            }
        }
    }
    stack.is_empty().then_some(out)
}

/// `(_ BitVec N)`'s N.
fn bit_vector(sort: &Sexp) -> Option<u32> {
    match sort.items() {
        [Sexp::Atom("_"), Sexp::Atom("BitVec"), Sexp::Atom(n)] => n.parse().ok(),
        _ => None,
    }
}

/// The width of a term, read off its shape; none for a shape not listed here.
fn width(term: &Sexp, sorts: &BTreeMap<&str, u32>) -> Option<u32> {
    const SAME: [&str; 15] = ["bvmul", "bvadd", "bvsub", "bvneg", "bvnot", "bvand", "bvor", "bvxor", "bvshl", "bvlshr", "bvashr", "bvsdiv", "bvudiv", "bvsrem", "bvurem"];
    match term {
        Sexp::Atom(a) => match a.as_bytes() {
            [b'#', b'x', digits @ ..] => Some(digits.len() as u32 * 4),
            [b'#', b'b', digits @ ..] => Some(digits.len() as u32),
            _ => sorts.get(a).copied(),
        },
        Sexp::List(items) => match items.as_slice() {
            [Sexp::Atom("_"), Sexp::Atom(literal), Sexp::Atom(n)] if literal.starts_with("bv") => n.parse().ok(),
            [Sexp::Atom("ite"), _, then, _] => width(then, sorts),
            [Sexp::Atom("concat"), parts @ ..] => parts.iter().map(|p| width(p, sorts)).sum(),
            [Sexp::Atom(op), first, ..] if SAME.contains(op) => width(first, sorts),
            [indexed @ Sexp::List(_), operand] => match indexed.items() {
                [Sexp::Atom("_"), Sexp::Atom("sign_extend" | "zero_extend"), Sexp::Atom(n)] => Some(width(operand, sorts)? + n.parse::<u32>().ok()?),
                [Sexp::Atom("_"), Sexp::Atom("extract"), Sexp::Atom(high), Sexp::Atom(low)] => Some(high.parse::<u32>().ok()?.checked_sub(low.parse().ok()?)? + 1),
                _ => None,
            },
            _ => None,
        },
    }
}

/// The products in a term that mean the same anywhere in the file: none under a binder, whose variables they
/// may name.
fn products<'a, 'b>(term: &'b Sexp<'a>, out: &mut Vec<&'b Sexp<'a>>) {
    if matches!(term.head(), Some("let" | "forall" | "exists" | "lambda" | "match" | "!")) {
        return;
    }
    if let [Sexp::Atom("bvmul"), _, _] = term.items() {
        out.push(term);
    }
    for item in term.items() {
        products(item, out);
    }
}

/// The formula with a congruence lemma for every two of its products of one width. None when there is nothing to
/// add (fewer than two products of a width), or the file is not one this reads: unbalanced, with scopes, or
/// without exactly one `(check-sat)`.
pub fn prepare(formula: &str) -> Option<Prepared> {
    let commands = commands(formula)?;
    if commands.iter().any(|(_, c)| matches!(c.head(), Some("push" | "pop" | "reset" | "check-sat-assuming"))) {
        return None;
    }
    let mut checks = commands.iter().filter(|(_, c)| c.head() == Some("check-sat"));
    let (at, _) = checks.next()?;
    if checks.next().is_some() {
        return None;
    }
    // The sort of every name without parameters. A name declared twice with different sorts is no name to trust.
    let mut sorts: BTreeMap<&str, u32> = BTreeMap::new();
    let mut unsure: Vec<&str> = Vec::new();
    for (_, c) in &commands {
        let (name, sort) = match c.items() {
            [Sexp::Atom("declare-fun"), name, Sexp::List(params), sort] | [Sexp::Atom("define-fun"), name, Sexp::List(params), sort, _] if params.is_empty() => (name, sort),
            [Sexp::Atom("declare-const"), name, sort] => (name, sort),
            _ => continue,
        };
        if let (Some(name), Some(bits)) = (name.atom(), bit_vector(sort)) {
            if sorts.insert(name, bits).is_some_and(|before| before != bits) {
                unsure.push(name);
            }
        }
    }
    for name in unsure {
        sorts.remove(name);
    }
    let mut found = Vec::new();
    for (_, c) in &commands {
        match c.items() {
            [Sexp::Atom("assert"), body] => products(body, &mut found),
            [Sexp::Atom("define-fun"), _, Sexp::List(params), _, body] if params.is_empty() => products(body, &mut found),
            _ => {}
        }
    }
    // By width, each product once, in the order the file has them.
    let mut by_width: BTreeMap<u32, Vec<(String, String, String)>> = BTreeMap::new();
    for p in found {
        let [_, a, b] = p.items() else { continue };
        let (Some(wa), Some(wb)) = (width(a, &sorts), width(b, &sorts)) else { continue };
        if wa != wb || wa == 0 {
            continue;
        }
        let entry = (p.text(), a.text(), b.text());
        let group = by_width.entry(wa).or_default();
        if !group.contains(&entry) {
            group.push(entry);
        }
    }
    let mut lemmas = String::new();
    let (mut count, mut paired) = (0, 0);
    for group in by_width.values().filter(|g| (2..=MAX_PRODUCTS).contains(&g.len())) {
        paired += group.len();
        for (i, (p, a, b)) in group.iter().enumerate() {
            for (q, c, d) in &group[i + 1..] {
                lemmas.push_str(&format!("(assert (=> (or (and (= {a} {c}) (= {b} {d})) (and (= {a} {d}) (= {b} {c}))) (= {p} {q})))\n"));
                count += 1;
            }
        }
    }
    if count == 0 {
        return None;
    }
    let header = format!("; {count} multiplication congruence lemma(s) over {paired} product(s), added by jvmcontract: each holds of any fixed-width multiplication\n");
    Some(Prepared { text: format!("{}{header}{lemmas}{}", &formula[..*at], &formula[*at..]), products: paired, lemmas: count })
}

/// The script JBMC is given as its SMT solver (`--external-smt2-solver`). It answers one question only: the
/// formula the lemmas were made for, byte for byte, which it hands to Z3 with them. Anything else gets an error,
/// and JBMC then has no verdict.
pub fn solver_script(z3: &Path, formula: &Path, with_lemmas: &Path, seconds: u64) -> String {
    let quote = |p: &Path| format!("'{}'", p.display().to_string().replace('\'', r"'\''"));
    format!(
        "#!/bin/sh\n# JBMC's SMT solver for one run (jvmcontract, lib/src/congruence.rs). JBMC passes Z3's arguments, the problem last.\nfor problem; do :; done\ncmp -s \"$problem\" {} || {{ echo '(error \"not the formula the lemmas were made for\")'; exit 1; }}\nexec {} -T:{seconds} -smt2 {}\n",
        quote(formula),
        quote(z3),
        quote(with_lemmas)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    const HEAD: &str = "(set-option :produce-models true)\n(declare-fun |a b| () (_ BitVec 64))\n(declare-fun y () (_ BitVec 64))\n(declare-fun n () (_ BitVec 32))\n(declare-fun c () Bool)\n(define-fun t () (_ BitVec 64) (bvmul |a b| ((_ sign_extend 32) n)))\n";

    fn lemmas_of(prepared: &Prepared) -> Vec<&str> {
        prepared.text.lines().filter(|l| l.starts_with("(assert (=> (or ")).collect()
    }

    #[test]
    fn two_products_of_one_width_get_the_lemma_before_check_sat_and_the_formula_is_kept() {
        let formula = format!("{HEAD}(assert (= y (bvmul ((_ sign_extend 32) n) (ite c |a b| y)))) ; the other order\n(check-sat)\n(get-value (y))\n");
        let prepared = prepare(&formula).expect("two products");
        assert_eq!((prepared.products, prepared.lemmas), (2, 1));
        let (p, q) = ("(bvmul |a b| ((_ sign_extend 32) n))", "(bvmul ((_ sign_extend 32) n) (ite c |a b| y))");
        let (a, b, c, d) = ("|a b|", "((_ sign_extend 32) n)", "((_ sign_extend 32) n)", "(ite c |a b| y)");
        assert_eq!(lemmas_of(&prepared), [format!("(assert (=> (or (and (= {a} {c}) (= {b} {d})) (and (= {a} {d}) (= {b} {c}))) (= {p} {q})))")]);
        // Every line JBMC wrote is still there, in order, and the lemmas sit right before (check-sat).
        let kept: String = prepared.text.lines().filter(|l| !l.starts_with("(assert (=> (or ") && !l.starts_with("; 1 multiplication")).map(|l| format!("{l}\n")).collect();
        assert_eq!(kept, formula);
        let at = prepared.text.find("(check-sat)").unwrap();
        assert!(prepared.text[..at].ends_with(")))\n") && prepared.text[at..].starts_with("(check-sat)\n(get-value (y))"), "{}", prepared.text);
    }

    #[test]
    fn products_are_paired_within_a_width_only_and_each_once() {
        let formula = format!(
            "{HEAD}(declare-fun m () (_ BitVec 32))\n(assert (= y (bvmul y |a b|)))\n(assert (= y (bvmul y |a b|)))\n(assert (= n (bvmul n m)))\n(assert (= n (bvmul m #x00000002)))\n(check-sat)\n"
        );
        let prepared = prepare(&formula).unwrap();
        // Two distinct 64-bit products and two 32-bit ones: one lemma each, none across the widths.
        assert_eq!((prepared.products, prepared.lemmas), (4, 2));
        assert!(lemmas_of(&prepared).iter().all(|l| l.contains("|a b|") != l.contains(" m")), "{:?}", lemmas_of(&prepared));
    }

    #[test]
    fn a_product_whose_text_may_mean_something_else_elsewhere_is_left_out() {
        // Under a binder the operand x is the binder's; in a function with parameters it is the parameter.
        let bound = format!("{HEAD}(assert (let ((x y)) (= x (bvmul x y))))\n(define-fun f ((x (_ BitVec 64))) (_ BitVec 64) (bvmul x y))\n(check-sat)\n");
        assert_eq!(prepare(&bound), None, "one product is left: nothing to pair");
        // A width that can't be read off the operands (an array read) leaves the product out.
        let unread = format!("{HEAD}(declare-fun h () (Array (_ BitVec 64) (_ BitVec 64)))\n(assert (= y (bvmul (select h y) y)))\n(check-sat)\n");
        assert_eq!(prepare(&unread), None);
        // Operands of two widths are not a product this understands.
        let mixed = format!("{HEAD}(assert (= y (bvmul y n)))\n(check-sat)\n");
        assert_eq!(prepare(&mixed), None);
    }

    #[test]
    fn a_file_it_cant_read_or_with_scopes_is_left_alone() {
        let two = format!("{HEAD}(assert (= y (bvmul y |a b|)))\n");
        assert!(prepare(&format!("{two}(check-sat)\n")).is_some());
        assert_eq!(prepare(&two), None, "no (check-sat)");
        assert_eq!(prepare(&format!("{two}(check-sat)\n(check-sat)\n")), None);
        assert_eq!(prepare(&format!("{two}(push 1)\n(check-sat)\n(pop 1)\n")), None);
        assert_eq!(prepare(&format!("{two}(check-sat)\n(assert (= y y)")), None, "unbalanced");
        assert_eq!(prepare(&format!("{two}(check-sat))\n")), None, "unbalanced");
        assert_eq!(prepare(&format!("{two}(assert (= |a b y))\n(check-sat)\n")), None, "an unclosed quoted name");
    }

    #[test]
    fn names_and_strings_are_read_whole() {
        // A parenthesis, a semicolon or a quote inside a quoted name or a string is part of it.
        let formula = "(declare-fun |f(x); \"y| () (_ BitVec 8))\n(declare-fun z () (_ BitVec 8))\n(set-info :source \"a ) \"\" ; b\")\n(assert (= z (bvmul |f(x); \"y| z)))\n(assert (= z (bvmul z |f(x); \"y|)))\n(check-sat)\n";
        let prepared = prepare(formula).unwrap();
        assert_eq!((prepared.products, prepared.lemmas), (2, 1));
        assert!(lemmas_of(&prepared)[0].contains("(= (bvmul |f(x); \"y| z) (bvmul z |f(x); \"y|))"));
    }

    #[test]
    fn too_many_products_of_a_width_are_not_paired() {
        let products: String = (0..=MAX_PRODUCTS).map(|i| format!("(assert (= y (bvmul y (_ bv{i} 64))))\n")).collect();
        assert_eq!(prepare(&format!("{HEAD}{products}(check-sat)\n")), None, "{} products with t", MAX_PRODUCTS + 2);
        let fewer: String = (0..MAX_PRODUCTS - 1).map(|i| format!("(assert (= y (bvmul y (_ bv{i} 64))))\n")).collect();
        let prepared = prepare(&format!("{HEAD}{fewer}(check-sat)\n")).unwrap();
        assert_eq!((prepared.products, prepared.lemmas), (MAX_PRODUCTS, MAX_PRODUCTS * (MAX_PRODUCTS - 1) / 2));
    }

    #[test]
    fn the_solver_script_answers_only_the_formula_the_lemmas_were_made_for() {
        crate::tool_tier!();
        let script = solver_script(Path::new("/opt/z 3/bin/z3"), Path::new("/w/it's/formula.smt2"), Path::new("/w/with.smt2"), 60);
        assert!(script.starts_with("#!/bin/sh\n"));
        assert!(script.contains(r#"cmp -s "$problem" '/w/it'\''s/formula.smt2' || {"#), "{script}");
        assert!(script.ends_with("exec '/opt/z 3/bin/z3' -T:60 -smt2 '/w/with.smt2'\n"), "{script}");
    }

    #[test]
    fn the_step_waits_a_twentieth_of_the_limit_but_five_seconds_at_least_and_has_a_tenth_to_run() {
        assert_eq!((patience(Duration::from_secs(600)), cap(Duration::from_secs(600))), (Duration::from_secs(30), Duration::from_secs(60)));
        assert_eq!((patience(Duration::from_secs(1800)), cap(Duration::from_secs(1800))), (Duration::from_secs(30), Duration::from_secs(60)));
        assert_eq!((patience(Duration::from_secs(200)), cap(Duration::from_secs(200))), (Duration::from_secs(10), Duration::from_secs(20)));
        assert_eq!((patience(Duration::from_secs(40)), cap(Duration::from_secs(40))), (Duration::from_secs(5), Duration::from_secs(4)));
        assert!(patience(Duration::from_secs(1)) > Duration::from_secs(1), "a run that short ends first");
    }

    #[test]
    fn a_proof_by_this_step_is_named_with_its_solver_and_lemmas() {
        let record = Record { solver: "/usr/bin/z3".into(), version: Some("5.3.3".into()), products: 4, lemmas: 6, after_seconds: 30.2, seconds: 0.4 };
        assert_eq!(record.checker("JBMC 6.11.0"), "JBMC 6.11.0, its formula decided by Z3 5.3.3 with 6 multiplication congruence lemma(s)");
        let sat = record.sat(&["--z3".to_string()]);
        assert_eq!((sat.solver.as_str(), sat.version.as_deref(), sat.configuration.as_slice()), ("Z3", Some("5.3.3"), ["--z3".to_string()].as_slice()));
        assert!(sat.source.contains("6 multiplication congruence lemma(s) over 4 product(s)") && sat.source.contains("no verdict in 30 s"), "{}", sat.source);
    }
}
