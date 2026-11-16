//! Bit-blasting: machine integers as vectors of propositional literals, and the JVM's arithmetic as circuits over
//! them, fed to a SAT solver clause by clause as they are built. A value is a `Vec<Lit>` of its bits, least
//! significant first; a bit that is known is one of two constant literals, so that arithmetic over constants
//! folds away and only what depends on an input reaches the solver.
//!
//! Over a solver that takes terms ([`super::sat::Terms`], the word-level prototype of Phase 6c), the same operations
//! build no circuits: each gate is defined to the solver as a Boolean term, and each arithmetic operation, comparison,
//! shift by a symbolic amount and `ite` of two values as one word-level term, whose result bits the engine handles as
//! it handles any others. Constants fold as before, and a model is evaluated the same way, a word-level operation by
//! its real result on its operands' values.

use std::collections::HashMap;
use std::fmt;

use super::sat::{Gate, WordOp};

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
    /// An output bit of a word-level operation given to a solver that takes terms ([`Word`]), by its index.
    Word(u32),
}

/// A word-level operation as a solver that takes terms was given it: its operands' bits and its result's.
struct Word {
    op: WordOp,
    operands: Vec<Bits>,
    out: Bits,
}

/// What `op` gives on operands of `width` bits with these values (sign-extended, a condition nonzero when set), as
/// the JVM computes it, and a division by zero as SMT-LIB does ([`WordOp`]); the low bits of the result are the
/// operation's.
fn word_value(op: WordOp, width: usize, v: &[i64]) -> i64 {
    let mask = if width >= 64 { u64::MAX } else { (1u64 << width) - 1 };
    let u = |x: i64| (x as u64) & mask;
    let s = |x: i64| {
        let x = u(x);
        if width < 64 && x >> (width - 1) & 1 == 1 { (x | !mask) as i64 } else { x as i64 }
    };
    let (a, b) = (v[0], v.get(1).copied().unwrap_or(0));
    match op {
        WordOp::Add => a.wrapping_add(b),
        WordOp::Sub => a.wrapping_sub(b),
        WordOp::Mul => a.wrapping_mul(b),
        WordOp::Div | WordOp::Rem if s(b) == 0 => match op {
            WordOp::Div => if s(a) < 0 { 1 } else { -1 },
            _ => a,
        },
        WordOp::Div => real_division(width, s(a), s(b)).0,
        WordOp::Rem => real_division(width, s(a), s(b)).1,
        WordOp::Shl => (u(a) << u(b).min(63)) as i64,
        WordOp::Shr => s(a) >> u(b).min(63),
        WordOp::Ushr => (u(a) >> u(b).min(63)) as i64,
        WordOp::And => a & b,
        WordOp::Or => a | b,
        WordOp::Xor => a ^ b,
        WordOp::Ite => if a != 0 { b } else { v[2] },
        WordOp::Ult => i64::from(u(a) < u(b)),
        WordOp::Slt => i64::from(s(a) < s(b)),
        WordOp::Eq => i64::from(u(a) == u(b)),
    }
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
    /// Whether the facts were given to the solver: at once, or, once clauses are deferred ([`Blaster::defer`]),
    /// when a call first depends on the operation.
    facts: bool,
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
///
/// The values are kept in pages of [`PAGE_WORDS`] words that a copy shares until one of the two writes there: the
/// models of the paths that split off one path are the same but for what each evaluated since, and a run of some
/// million gates keeps some hundred models.
#[derive(Clone, Default)]
pub struct Model {
    /// For each page, which of its variables have a value (the first [`PAGE_WORDS`] words) and the values.
    pages: Vec<Option<std::rc::Rc<[u64; 2 * PAGE_WORDS]>>>,
    /// What an input the model does not fix is when it is first asked for: false, or, where this is not zero, a
    /// bit drawn from it and the input's number ([`Model::salted`]).
    salt: u64,
}

/// The words of a [`Model`]'s page: 4096 variables.
const PAGE_WORDS: usize = 64;

impl Model {
    /// The model with the inputs it does not fix yet drawn by `salt`, not false: as much a model, since an input
    /// it does not fix is one nothing it was asked about depends on, and one of other values of what a loop reads
    /// from tables and computes, where every such input false is one state among many ([`super::loops`]).
    pub fn salted(&self, salt: u64) -> Model {
        Model { salt: salt | 1, ..self.clone() }
    }

    /// The value of an input the model does not fix.
    fn free(&self, v: usize) -> bool {
        if self.salt == 0 {
            return false;
        }
        // splitmix64 of the input's number and the salt.
        let mut z = (v as u64).wrapping_add(self.salt).wrapping_add(0x9E37_79B9_7F4A_7C15);
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        (z ^ (z >> 31)) & 1 == 1
    }

    fn get(&self, v: usize) -> Option<bool> {
        let (word, bit) = (v / 64, v % 64);
        let page = self.pages.get(word / PAGE_WORDS)?.as_ref()?;
        let word = word % PAGE_WORDS;
        if page[word] >> bit & 1 == 1 {
            Some(page[PAGE_WORDS + word] >> bit & 1 == 1)
        } else {
            None
        }
    }

    fn set(&mut self, v: usize, b: bool) {
        let (word, bit) = (v / 64, v % 64);
        let (page, word) = (word / PAGE_WORDS, word % PAGE_WORDS);
        if page >= self.pages.len() {
            self.pages.resize(page + 1, None);
        }
        let page = std::rc::Rc::make_mut(self.pages[page].get_or_insert_with(|| std::rc::Rc::new([0; 2 * PAGE_WORDS])));
        page[word] |= 1 << bit;
        if b {
            page[PAGE_WORDS + word] |= 1 << bit;
        } else {
            page[PAGE_WORDS + word] &= !(1 << bit);
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

/// The circuits, built over a solver ([`super::sat::Sat`]) that is given nothing but their clauses and the calls.
pub struct Blaster {
    solver: Box<dyn super::sat::Sat>,
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
    /// How many functional-consistency lemmas have been added ([`Blaster::inconsistent_pair`]).
    pub congruences: u64,
    /// How many clauses have been added, for reporting.
    pub clauses: u64,
    /// How many times the solver was asked, for reporting, and the time it took.
    pub solves: u64,
    pub solving: std::time::Duration,
    /// How many gates were evaluated in a path's model, and the time it took.
    pub evaluated: u64,
    pub evaluating: std::time::Duration,
    /// The time spent building circuits and handing their clauses to the solver: the encoding, which happens as
    /// the paths are explored, estimated from a sample of the operations ([`Blaster::encoding`]).
    pub encoding: std::time::Duration,
    /// Whether an operation is being built, so that one built inside another counts as part of it.
    timing: bool,
    /// The state of the generator that picks which operations are timed.
    sampling: u64,
    /// Where every clause and call goes as well, when the check is recorded ([`super::transcript`]).
    transcript: Option<super::transcript::Transcript>,
    /// Whether the solver takes terms ([`super::sat::Terms`]): gates and word-level operations are then defined to
    /// it, not bit-blasted.
    words: bool,
    /// The word-level operations given to it, and which one is of which operands.
    word_ops: Vec<Word>,
    word_keys: HashMap<(WordOp, Vec<Bits>), usize>,
    /// The per-call time limit last given to the solver, for the transcript.
    limit: Option<f32>,
    /// The per-call conflict limit last given to the solver, when it took one, for the transcript.
    work_limit: Option<u64>,
    /// What reading the clock around nothing takes, which each timed operation's time includes once.
    clock: std::time::Duration,
    /// Once clauses are deferred ([`Blaster::defer`]): the first variable whose gate was not given to the solver
    /// as it was made, for each variable from there whether its gate has been given since, and the variables
    /// whose gates a clause or a call has come to depend on and that are still to be given.
    deferred: Option<usize>,
    given: Vec<bool>,
    needed: Vec<usize>,
    /// The solver's variable for each variable from the first deferred one (0: none yet), numbered in the order
    /// the solver comes to hold them, so that what it holds is as dense as what it is asked; and the inputs among
    /// them, which a model is read off.
    numbered: Vec<Lit>,
    numbers: Lit,
    numbered_inputs: Vec<usize>,
}

/// What timing nothing takes: the median of a few empty timed regions.
fn clock_cost() -> std::time::Duration {
    let mut spans: Vec<std::time::Duration> = (0..15).map(|_| {
        let started = std::time::Instant::now();
        started.elapsed()
    }).collect();
    spans.sort();
    spans[spans.len() / 2]
}

/// One in this many single gates built on their own (an `and`, `xor` or `ite` of two bits) is timed, and its time
/// counted this many times over: a clock read costs about 0.3 µs on the WSL2 machine the benchmark runs on
/// (measured 2026-11-06), as much as a gate takes, so timing every one doubled the encoding it measured. The gates
/// timed are picked at random, so the estimate is unbiased whatever the order gates come in. Every word-level
/// operation (a circuit of at least a word's width of gates) is timed whole instead: sampled together with the
/// gates, one multiplier picked among cheap gates was counted this many times over, so a short run's encoding
/// could pass the run's own time. The clock's own cost is taken off each timing ([`clock_cost`]).
const ENCODING_SAMPLE: u32 = 64;

impl fmt::Debug for Blaster {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Blaster({} variables, {} clauses)", self.next - 1, self.clauses)
    }
}

fn is_const(l: Lit) -> bool {
    l == TRUE || l == FALSE
}

/// Whether the bits are the constant zero.
fn is_zero_const(bits: &Bits) -> bool {
    bits.iter().all(|&l| l == FALSE)
}

impl Default for Blaster {
    fn default() -> Self {
        Self::new()
    }
}

impl Blaster {
    pub fn new() -> Blaster {
        Self::recorded(None)
    }

    /// A blaster over CaDiCaL whose clauses and calls also go to `transcript`, from the first: the unit clause of the
    /// constant.
    pub fn recorded(transcript: Option<super::transcript::Transcript>) -> Blaster {
        Self::over(Box::new(super::sat::Cadical::new()), transcript)
    }

    /// A blaster over `solver`, which must hold no clauses yet, and whose clauses and calls also go to `transcript`.
    /// A solver that takes terms is given the gates and word-level operations as terms, and no transcript can be
    /// kept of them: `transcript` must then be `None`.
    pub fn over(mut solver: Box<dyn super::sat::Sat>, transcript: Option<super::transcript::Transcript>) -> Blaster {
        let words = solver.terms().is_some();
        assert!(!(words && transcript.is_some()), "a transcript records clauses, and this solver is given terms");
        let mut b = Blaster { words, word_ops: Vec::new(), word_keys: HashMap::new(), solver, next: 2, defs: vec![Def::Input, Def::Input], gates: HashMap::new(), lazy: Vec::new(), divisions: HashMap::new(), products: HashMap::new(), congruences: 0, clauses: 0, solves: 0, solving: std::time::Duration::ZERO, evaluated: 0, evaluating: std::time::Duration::ZERO, encoding: std::time::Duration::ZERO, timing: false, sampling: 0x9E37_79B9_7F4A_7C15, clock: clock_cost(), transcript, limit: None, work_limit: None, deferred: None, given: Vec::new(), needed: Vec::new(), numbered: Vec::new(), numbers: 0, numbered_inputs: Vec::new() };
        b.clause(&[TRUE]);
        b
    }

    /// Ends the transcript, if there is one, with `last` as its closing comment: where it is, or why it could not be
    /// written.
    pub fn finish_transcript(&mut self, last: &str) -> Option<std::io::Result<std::path::PathBuf>> {
        self.transcript.take().map(|t| t.finish(last))
    }

    /// Where the transcript is being written, if there is one.
    pub fn transcript_path(&self) -> Option<&std::path::Path> {
        self.transcript.as_ref().map(|t| t.path())
    }

    /// The solver the circuits are built over, by name and version.
    pub fn solver_signature(&self) -> String {
        self.solver.signature()
    }

    /// Whether the solver is given terms, not clauses ([`super::sat::Terms`]).
    pub fn takes_terms(&self) -> bool {
        self.words
    }

    /// How many word-level operations the solver was given as terms.
    pub fn word_operations(&self) -> usize {
        self.word_ops.len()
    }

    /// Defines a gate to a solver that takes terms.
    fn define(&mut self, out: Lit, gate: Gate) {
        self.solver.terms().expect("a solver that takes terms").gate(out, gate);
    }

    /// `op` over `operands` as one word-level operation for a solver that takes terms: its result's bits (one for a
    /// comparison), the operands' width otherwise. Constant operands fold, and the same operation on the same
    /// operands (in either order, where they commute) is the same bits.
    fn word(&mut self, op: WordOp, operands: &[&Bits]) -> Bits {
        let width = operands[operands.len() - 1].len();
        let out_width = if op.compares() { 1 } else { width };
        if operands.iter().all(|o| o.iter().all(|&l| is_const(l))) {
            let values: Vec<i64> = operands.iter().map(|o| self.constant_value(o).expect("constant")).collect();
            return self.constant(word_value(op, width, &values), out_width);
        }
        let mut key: Vec<Bits> = operands.iter().map(|&o| o.clone()).collect();
        if op.commutes() && key[1] < key[0] {
            key.swap(0, 1);
        }
        let key = (op, key);
        if let Some(&i) = self.word_keys.get(&key) {
            return self.word_ops[i].out.clone();
        }
        let i = self.word_ops.len();
        let out: Bits = (0..out_width).map(|_| self.gate(Def::Word(i as u32))).collect();
        let operands: Vec<&[Lit]> = key.1.iter().map(|b| b.as_slice()).collect();
        self.solver.terms().expect("a solver that takes terms").word(&out, op, &operands);
        self.word_ops.push(Word { op, operands: key.1.clone(), out: out.clone() });
        self.word_keys.insert(key, i);
        out
    }

    fn word_bit(&mut self, op: WordOp, a: &Bits, b: &Bits) -> Lit {
        self.word(op, &[a, b])[0]
    }

    /// Stops the solver after this many seconds on any one call.
    pub fn set_timeout(&mut self, seconds: f32) {
        self.limit = Some(seconds);
        self.solver.set_limit(Some(seconds));
    }

    /// Stops the solver after this many conflicts on any one call as well, or not by conflicts: `false` when the
    /// solver has no such limit ([`super::sat::Sat::set_work_limit`]).
    pub fn set_work_limit(&mut self, conflicts: Option<u64>) -> bool {
        let taken = self.solver.set_work_limit(conflicts);
        self.work_limit = if taken { conflicts } else { None };
        taken
    }

    /// The solver's conflicts in all its calls so far, the work [`Blaster::set_work_limit`] limits: the same on
    /// every machine, unlike [`Blaster::solving`].
    pub fn work(&self) -> u64 {
        self.solver.work()
    }

    /// Runs `build`, a word-level operation that builds circuits: when it is not built inside another, it is timed,
    /// and counted as encoding.
    #[inline]
    fn encoding<T>(&mut self, build: impl FnOnce(&mut Self) -> T) -> T {
        if self.timing {
            return build(self);
        }
        self.timing = true;
        let started = std::time::Instant::now();
        let out = build(self);
        self.encoding += started.elapsed().saturating_sub(self.clock);
        self.timing = false;
        out
    }

    /// Runs `build`, a single gate: one in [`ENCODING_SAMPLE`] of those not built inside another operation is
    /// timed, and counted that many times over as encoding.
    #[inline]
    fn gate_encoding<T>(&mut self, build: impl FnOnce(&mut Self) -> T) -> T {
        if self.timing {
            return build(self);
        }
        // xorshift64: which gates are timed does not follow their order.
        self.sampling ^= self.sampling << 13;
        self.sampling ^= self.sampling >> 7;
        self.sampling ^= self.sampling << 17;
        if self.sampling % u64::from(ENCODING_SAMPLE) != 0 {
            return build(self);
        }
        self.timing = true;
        let started = std::time::Instant::now();
        let out = build(self);
        self.encoding += started.elapsed().saturating_sub(self.clock) * ENCODING_SAMPLE;
        self.timing = false;
        out
    }

    fn clause(&mut self, lits: &[Lit]) {
        if self.deferred.is_some() {
            self.needed.extend(lits.iter().map(|l| l.unsigned_abs() as usize));
            let numbered: Vec<Lit> = lits.iter().map(|&l| self.number(l)).collect();
            return self.clause_given(&numbered);
        }
        self.clause_given(lits)
    }

    fn clause_given(&mut self, lits: &[Lit]) {
        self.solver.add_clause(lits);
        self.clauses += 1;
        if let Some(t) = &mut self.transcript {
            t.clause(lits);
        }
    }

    /// The solver's literal for `l`: itself until clauses are deferred and for a variable made before, and the
    /// next number the solver has not seen for a later one, the first time it is given.
    fn number(&mut self, l: Lit) -> Lit {
        let Some(first) = self.deferred else { return l };
        let v = l.unsigned_abs() as usize;
        if v < first {
            return l;
        }
        if self.numbered.len() <= v - first {
            self.numbered.resize(self.next as usize - first, 0);
        }
        if self.numbered[v - first] == 0 {
            self.numbers += 1;
            self.numbered[v - first] = self.numbers;
            if matches!(self.defs[v], Def::Input) {
                self.numbered_inputs.push(v);
            }
        }
        let n = self.numbered[v - first];
        if l < 0 { -n } else { n }
    }

    /// The solver's literal for `l`, if the solver holds its variable.
    fn numbered(&self, l: Lit) -> Option<Lit> {
        let Some(first) = self.deferred else { return Some(l) };
        let v = l.unsigned_abs() as usize;
        if v < first {
            return Some(l);
        }
        let n = self.numbered.get(v - first).copied().filter(|&n| n != 0)?;
        Some(if l < 0 { -n } else { n })
    }

    /// From here on a gate's clauses are given to the solver only when a clause or a call comes to depend on the
    /// gate, and an operation's facts ([`Lazy`]) when one comes to depend on the operation. What the solver is
    /// asked is the same, since a gate nothing asked depends on constrains nothing asked; what it holds is less,
    /// where much of what is built is never asked about (the values a loop computes, when only its bounds are:
    /// [`super::loops`]). Everything built before stays as it was given. A solver that takes terms is given
    /// every definition as before.
    pub fn defer(&mut self) {
        if self.deferred.is_none() && !self.words {
            self.deferred = Some(self.next as usize);
            self.numbers = self.next - 1;
        }
    }

    /// Gives the solver the gates the variables in `needed` depend on that it does not hold yet.
    fn give_needed(&mut self) {
        let Some(first) = self.deferred else { return };
        while let Some(v) = self.needed.pop() {
            if v < first {
                continue;
            }
            if self.given.len() <= v - first {
                self.given.resize(self.next as usize - first, false);
            }
            if std::mem::replace(&mut self.given[v - first], true) {
                continue;
            }
            let o = v as Lit;
            match self.defs[v] {
                Def::Input | Def::Word(_) => {}
                Def::And(a, b) => self.and_clauses(o, a, b),
                Def::Xor(x, y) => self.xor_clauses(o, x, y),
                Def::Ite(c, a, b) => self.ite_clauses(o, c, a, b),
                Def::Lazy(i) => {
                    let l = &mut self.lazy[i as usize];
                    if !std::mem::replace(&mut l.facts, true) {
                        let (op, a, b, q, r) = (l.op, l.a.clone(), l.b.clone(), l.q.clone(), l.r.clone());
                        match op {
                            Op::DivRem => self.remainder_facts(&a, &b, &q, &r),
                            Op::Mul => self.multiplication_facts(&a, &b, &q),
                        }
                    }
                }
            }
        }
    }

    fn and_clauses(&mut self, o: Lit, a: Lit, b: Lit) {
        self.clause(&[-o, a]);
        self.clause(&[-o, b]);
        self.clause(&[o, -a, -b]);
    }

    fn xor_clauses(&mut self, o: Lit, x: Lit, y: Lit) {
        self.clause(&[-o, x, y]);
        self.clause(&[-o, -x, -y]);
        self.clause(&[o, -x, y]);
        self.clause(&[o, x, -y]);
    }

    fn ite_clauses(&mut self, o: Lit, c: Lit, a: Lit, b: Lit) {
        self.clause(&[-c, -a, o]);
        self.clause(&[-c, a, -o]);
        self.clause(&[c, -b, o]);
        self.clause(&[c, b, -o]);
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
        self.gate_encoding(|s| s.and_gate(a, b))
    }

    fn and_gate(&mut self, a: Lit, b: Lit) -> Lit {
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
        if self.words {
            self.define(o, Gate::And(a, b));
        } else if self.deferred.is_none() {
            self.and_clauses(o, a, b);
        }
        self.gates.insert(key, o);
        o
    }

    pub fn or(&mut self, a: Lit, b: Lit) -> Lit {
        -self.and(-a, -b)
    }

    pub fn xor(&mut self, a: Lit, b: Lit) -> Lit {
        self.gate_encoding(|s| s.xor_gate(a, b))
    }

    fn xor_gate(&mut self, a: Lit, b: Lit) -> Lit {
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
                if self.words {
                    self.define(o, Gate::Xor(x, y));
                } else if self.deferred.is_none() {
                    self.xor_clauses(o, x, y);
                }
                self.gates.insert(key, o);
                o
            }
        };
        if flip { -o } else { o }
    }

    /// `if c then a else b`.
    pub fn ite(&mut self, c: Lit, a: Lit, b: Lit) -> Lit {
        self.gate_encoding(|s| s.ite_gate(c, a, b))
    }

    fn ite_gate(&mut self, c: Lit, a: Lit, b: Lit) -> Lit {
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
        if self.words {
            self.define(o, Gate::Ite(c, a, b));
        } else if self.deferred.is_none() {
            self.ite_clauses(o, c, a, b);
        }
        self.gates.insert(key, o);
        o
    }

    /// The conjunction of several literals.
    pub fn all(&mut self, lits: &[Lit]) -> Lit {
        self.encoding(|s| lits.iter().fold(TRUE, |acc, &l| s.and(acc, l)))
    }

    // Bit-vector operations. Every operand has the width of its result unless said otherwise.

    pub fn ite_bits(&mut self, c: Lit, a: &Bits, b: &Bits) -> Bits {
        if self.words && !is_const(c) && a != b {
            let c = vec![c];
            return self.encoding(|s| s.word(WordOp::Ite, &[&c, a, b]));
        }
        self.encoding(|s| a.iter().zip(b).map(|(&x, &y)| s.ite(c, x, y)).collect())
    }

    /// Whether a bitwise operation goes to a solver that takes terms as one word-level operation: when neither operand
    /// is a constant, which folds bit by bit into wiring and negations.
    fn bitwise_word(&self, a: &Bits, b: &Bits) -> bool {
        self.words && !a.iter().all(|&l| is_const(l)) && !b.iter().all(|&l| is_const(l))
    }

    pub fn and_bits(&mut self, a: &Bits, b: &Bits) -> Bits {
        if self.bitwise_word(a, b) {
            return self.encoding(|s| s.word(WordOp::And, &[a, b]));
        }
        self.encoding(|s| a.iter().zip(b).map(|(&x, &y)| s.and(x, y)).collect())
    }

    pub fn or_bits(&mut self, a: &Bits, b: &Bits) -> Bits {
        if self.bitwise_word(a, b) {
            return self.encoding(|s| s.word(WordOp::Or, &[a, b]));
        }
        self.encoding(|s| a.iter().zip(b).map(|(&x, &y)| s.or(x, y)).collect())
    }

    pub fn xor_bits(&mut self, a: &Bits, b: &Bits) -> Bits {
        if self.bitwise_word(a, b) {
            return self.encoding(|s| s.word(WordOp::Xor, &[a, b]));
        }
        self.encoding(|s| a.iter().zip(b).map(|(&x, &y)| s.xor(x, y)).collect())
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
        if self.words {
            return if is_zero_const(b) { a.clone() } else if is_zero_const(a) { b.clone() } else { self.encoding(|s| s.word(WordOp::Add, &[a, b])) };
        }
        self.encoding(|s| s.add_carry(a, b, FALSE).0)
    }

    pub fn sub(&mut self, a: &Bits, b: &Bits) -> Bits {
        if self.words {
            return if is_zero_const(b) { a.clone() } else { self.encoding(|s| s.word(WordOp::Sub, &[a, b])) };
        }
        let nb = self.not_bits(b);
        self.encoding(|s| s.add_carry(a, &nb, TRUE).0)
    }

    pub fn neg(&mut self, a: &Bits) -> Bits {
        let zero = self.constant(0, a.len());
        self.sub(&zero, a)
    }

    /// Two's-complement multiplication, modulo the width (as `imul` and `lmul` are).
    pub fn mul(&mut self, a: &Bits, b: &Bits) -> Bits {
        if self.words {
            return self.mul_word(a, b);
        }
        self.encoding(|s| s.mul_built(a, b))
    }

    /// A product for a solver that takes terms: a factor of zero or one folds, any other is one word-level operation.
    fn mul_word(&mut self, a: &Bits, b: &Bits) -> Bits {
        match (self.constant_value(a), self.constant_value(b)) {
            (Some(0), _) | (_, Some(1)) => a.clone(),
            (_, Some(0)) | (Some(1), _) => b.clone(),
            _ => self.encoding(|s| s.word(WordOp::Mul, &[a, b])),
        }
    }

    fn mul_built(&mut self, a: &Bits, b: &Bits) -> Bits {
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
        if self.words {
            return if a == b { FALSE } else { self.encoding(|s| s.word_bit(WordOp::Ult, a, b)) };
        }
        self.encoding(|s| s.ult_built(a, b))
    }

    fn ult_built(&mut self, a: &Bits, b: &Bits) -> Lit {
        let nb = self.not_bits(b);
        let (_, carry) = self.add_carry(a, &nb, TRUE);
        -carry
    }

    /// Signed `a < b`: unsigned, with the sign bits flipped.
    pub fn slt(&mut self, a: &Bits, b: &Bits) -> Lit {
        if self.words {
            return if a == b { FALSE } else { self.encoding(|s| s.word_bit(WordOp::Slt, a, b)) };
        }
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
        if self.words {
            if a == b {
                return TRUE;
            }
            if a.iter().zip(b).any(|(&x, &y)| x == -y) {
                return FALSE;
            }
            return self.encoding(|s| s.word_bit(WordOp::Eq, a, b));
        }
        self.encoding(|s| s.eq_built(a, b))
    }

    fn eq_built(&mut self, a: &Bits, b: &Bits) -> Lit {
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
        self.encoding(|s| s.sdivrem_lazy_built(a, b))
    }

    fn sdivrem_lazy_built(&mut self, a: &Bits, b: &Bits) -> (Bits, Bits) {
        if a.iter().chain(b).all(|&l| is_const(l)) || self.words {
            return self.sdivrem(a, b);
        }
        // By a constant power of two, once clauses are deferred: shifts, as a compiler divides by one. The
        // quotient is `(a + bias) >> k`, the bias `2^k - 1` for a negative `a` (the JVM rounds toward zero), and the
        // remainder `a` less the quotient shifted back.
        if self.deferred.is_some() {
            if let Some(k) = self.constant_value(b).filter(|&v| v > 0 && v & (v - 1) == 0).map(|v| v.trailing_zeros() as usize) {
                let width = a.len();
                let sa = self.negative(a);
                let bias: Bits = (0..width).map(|i| if i < k { sa } else { FALSE }).collect();
                let sum = self.add(a, &bias);
                let q: Bits = (0..width).map(|i| sum[(i + k).min(width - 1)]).collect();
                let back: Bits = (0..width).map(|i| if i < k { FALSE } else { q[i - k] }).collect();
                let r = self.sub(a, &back);
                return (q, r);
            }
        }
        if let Some(&i) = self.divisions.get(&(a.clone(), b.clone())) {
            return (self.lazy[i].q.clone(), self.lazy[i].r.clone());
        }
        let i = self.lazy.len();
        let width = a.len();
        let q: Bits = (0..width).map(|_| self.gate(Def::Lazy(i as u32))).collect();
        let r: Bits = (0..width).map(|_| self.gate(Def::Lazy(i as u32))).collect();
        let facts = self.deferred.is_none();
        self.lazy.push(Lazy { op: Op::DivRem, a: a.clone(), b: b.clone(), q: q.clone(), r: r.clone(), refined: false, facts });
        self.divisions.insert((a.clone(), b.clone()), i);
        if facts {
            self.division_facts(a, b, &q, &r);
        }
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
        self.encoding(|s| s.mul_lazy_built(a, b))
    }

    fn mul_lazy_built(&mut self, a: &Bits, b: &Bits) -> Bits {
        if self.words {
            return self.mul_word(a, b);
        }
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
        let facts = self.deferred.is_none();
        self.lazy.push(Lazy { op: Op::Mul, a: a.clone(), b: b.clone(), q: p.clone(), r: Vec::new(), refined: false, facts });
        self.products.insert(key, i);
        if facts {
            self.multiplication_facts(a, b, &p);
        }
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
    /// The facts of a division an index computed with `%` is in bounds by, and an index that goes round an array
    /// (`(i + 1) % length`) is exact by, given once clauses are deferred ([`Blaster::defer`]) in place of all of
    /// [`Blaster::division_facts`], which are some thousand gates a division: when `b` is not zero, `|r| < |b|`,
    /// `r` is zero or of `a`'s sign, a dividend smaller than the divisor is the remainder with the quotient zero,
    /// and `a` by itself is one with no remainder. Anything else the solver gets wrong of the division builds its
    /// circuit, as ever ([`Blaster::refine_operation`]).
    fn remainder_facts(&mut self, a: &Bits, b: &Bits, q: &Bits, r: &Bits) {
        let nz = -self.is_zero(b);
        let (sa, sr) = (self.negative(a), self.negative(r));
        let abs_a = self.magnitude(a);
        let abs_b = self.magnitude(b);
        let abs_r = self.magnitude(r);
        let within = self.ult(&abs_r, &abs_b);
        let r_zero = self.is_zero(r);
        let r_sign = -self.xor(sr, sa);
        let signed = self.or(r_zero, r_sign);
        let small = self.ult(&abs_a, &abs_b);
        let q_zero = self.is_zero(q);
        let r_is_a = self.eq(r, a);
        let itself = self.and(q_zero, r_is_a);
        let smaller = self.or(-small, itself);
        let same = self.eq(a, b);
        let one = self.constant(1, a.len());
        let q_one = self.eq(q, &one);
        let once = self.and(q_one, r_zero);
        let by_itself = self.or(-same, once);
        for f in [within, signed, smaller, by_itself] {
            let guarded = self.or(-nz, f);
            self.clause(&[guarded]);
        }
    }

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

    /// The operations left to the solver that the literals depend on, in the order they were made: an operation
    /// none of them depends on decides nothing of them, whatever the solver chose for it, and a model kept for
    /// later is the inputs' values alone ([`Blaster::snapshot`]), from which every operation is computed anew.
    pub fn operations_under(&self, lits: &[Lit]) -> Vec<usize> {
        let mut seen = vec![false; self.defs.len()];
        let mut found = vec![false; self.lazy.len()];
        let mut stack: Vec<usize> = lits.iter().map(|l| l.unsigned_abs() as usize).collect();
        while let Some(v) = stack.pop() {
            if std::mem::replace(&mut seen[v], true) {
                continue;
            }
            match self.defs[v] {
                Def::Input => {}
                Def::And(a, b) | Def::Xor(a, b) => stack.extend([a.unsigned_abs() as usize, b.unsigned_abs() as usize]),
                Def::Ite(c, a, b) => stack.extend([c.unsigned_abs() as usize, a.unsigned_abs() as usize, b.unsigned_abs() as usize]),
                Def::Lazy(i) => {
                    let l = &self.lazy[i as usize];
                    if !std::mem::replace(&mut found[i as usize], true) {
                        stack.extend(l.a.iter().chain(&l.b).map(|x| x.unsigned_abs() as usize));
                    }
                }
                Def::Word(i) => stack.extend(self.word_ops[i as usize].operands.iter().flatten().map(|x| x.unsigned_abs() as usize)),
            }
        }
        found.iter().enumerate().filter(|(_, &f)| f).map(|(i, _)| i).collect()
    }

    /// Every operation left to the solver.
    pub fn every_operation(&self) -> Vec<usize> {
        (0..self.lazy.len()).collect()
    }

    /// The first operation left to the solver, among `among`, whose result in the solver's last model is not the
    /// real operation on the operands' values there (a division by zero is never wrong: the JVM throws before
    /// the values matter). `None` when the model is a real one of what depends on those operations alone, as a
    /// model of the circuits alone always is: the first wrong operation decides, since the operands of a later
    /// one may come from it.
    pub fn wrong_operation(&self, among: &[usize]) -> Option<usize> {
        among.iter().copied().find(|&i| {
            let l = &self.lazy[i];
            if l.refined {
                return false;
            }
            let (a, b) = (self.eval(&l.a), self.eval(&l.b));
            if l.op == Op::DivRem && b == 0 {
                return false;
            }
            let r = if l.r.is_empty() { 0 } else { self.eval(&l.r) };
            real_operation(l.op, l.a.len(), a, b) != (self.eval(&l.q), r)
        })
    }

    /// Two operations left to the solver, among `among`, that the last model gives the same operands but
    /// different results: a division and a division, or a product and a product (its operands in either order),
    /// of one width. Each is a function of its operands, but they are separate bits unless their operand *terms*
    /// are the same, so the solver may answer `hash % b` and `(hash & 0x7fffffff) % b` differently where `hash`
    /// is not negative. Such a model is not real whichever of the two is right; [`Blaster::add_congruence`] rules
    /// it out with a clause, which is cheaper than building both circuits and having the solver prove two
    /// dividers equivalent.
    pub fn inconsistent_pair(&self, among: &[usize]) -> Option<(usize, usize, bool)> {
        let values: Vec<(i64, i64, i64, i64)> = among.iter().map(|&i| {
            let l = &self.lazy[i];
            let r = if l.r.is_empty() { 0 } else { self.eval(&l.r) };
            (self.eval(&l.a), self.eval(&l.b), self.eval(&l.q), r)
        }).collect();
        for (jj, &j) in among.iter().enumerate() {
            for (ii, &i) in among[..jj].iter().enumerate() {
                let (x, y) = (&self.lazy[i], &self.lazy[j]);
                if x.op != y.op || x.a.len() != y.a.len() || (x.refined && y.refined) {
                    continue;
                }
                let (vx, vy) = (values[ii], values[jj]);
                if (vx.2, vx.3) == (vy.2, vy.3) {
                    continue;
                }
                if (vx.0, vx.1) == (vy.0, vy.1) {
                    return Some((i, j, false));
                }
                if x.op == Op::Mul && (vx.0, vx.1) == (vy.1, vy.0) {
                    return Some((i, j, true));
                }
            }
        }
        None
    }

    /// The lemma for a pair [`Blaster::inconsistent_pair`] found: equal operands give equal results, for every
    /// value, not only the model's (`swapped`: a product's operands compared crosswise). It holds of the real
    /// operations, so it rules out no real execution; for a division by zero, whose bits nothing observes since
    /// the JVM throws first, it only picks equal values for both.
    pub fn add_congruence(&mut self, i: usize, j: usize, swapped: bool) {
        self.encoding(|s| {
            let (x, y) = (&s.lazy[i], &s.lazy[j]);
            let (xa, xb, ya, yb) = (x.a.clone(), x.b.clone(), y.a.clone(), y.b.clone());
            let (xq, xr, yq, yr) = (x.q.clone(), x.r.clone(), y.q.clone(), y.r.clone());
            let (ea, eb) = if swapped { (s.eq_built(&xa, &yb), s.eq_built(&xb, &ya)) } else { (s.eq_built(&xa, &ya), s.eq_built(&xb, &yb)) };
            let same_operands = s.and(ea, eb);
            let eq = s.eq_built(&xq, &yq);
            let er = s.eq_built(&xr, &yr);
            let same_results = s.and(eq, er);
            s.clause(&[-same_operands, same_results]);
        });
        self.congruences += 1;
    }

    /// Builds the circuit of operation `i` and ties its bits to the ones the solver chooses.
    pub fn refine_operation(&mut self, i: usize) {
        self.encoding(|s| s.refine_operation_built(i))
    }

    fn refine_operation_built(&mut self, i: usize) {
        let (a, b) = (self.lazy[i].a.clone(), self.lazy[i].b.clone());
        let (q, r) = match self.lazy[i].op {
            Op::DivRem => self.sdivrem(&a, &b),
            Op::Mul => (self.mul(&a, &b), Vec::new()),
        };
        let ties: Vec<(Lit, Lit)> = self.lazy[i].q.iter().zip(&q).chain(self.lazy[i].r.iter().zip(&r)).map(|(&c, &r)| (c, r)).collect();
        for (chosen, real) in ties {
            self.clause(&[-chosen, real]);
            self.clause(&[chosen, -real]);
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
        self.encoding(|s| s.udivrem_built(a, b))
    }

    fn udivrem_built(&mut self, a: &Bits, b: &Bits) -> (Bits, Bits) {
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
        self.encoding(|s| s.sdivrem_built(a, b))
    }

    fn sdivrem_built(&mut self, a: &Bits, b: &Bits) -> (Bits, Bits) {
        if self.words {
            return (self.word(WordOp::Div, &[a, b]), self.word(WordOp::Rem, &[a, b]));
        }
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
        self.encoding(|s| s.shift_built(a, amount, left, arith))
    }

    fn shift_built(&mut self, a: &Bits, amount: &Bits, left: bool, arith: bool) -> Bits {
        let width = a.len();
        let steps = width.trailing_zeros() as usize; // 5 for 32, 6 for 64
        if self.words && !amount[..steps].iter().all(|&l| is_const(l)) {
            // The amount masked to the width, at the width.
            let mut masked = amount[..steps].to_vec();
            masked.resize(width, FALSE);
            let op = if left { WordOp::Shl } else if arith { WordOp::Shr } else { WordOp::Ushr };
            return self.word(op, &[a, &masked]);
        }
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
        let assumptions: Vec<Lit> = if self.deferred.is_some() {
            self.needed.extend(assumptions.iter().map(|l| l.unsigned_abs() as usize));
            self.encoding(|s| s.give_needed());
            assumptions.iter().map(|&l| self.number(l)).collect()
        } else {
            assumptions
        };
        let started = std::time::Instant::now();
        let answer = self.solver.solve(&assumptions);
        let took = started.elapsed();
        self.solving += took;
        if let Some(t) = &mut self.transcript {
            t.call(&assumptions, self.limit, self.work_limit, answer, took);
        }
        answer
    }

    /// The solver's last model, as the inputs' values.
    pub fn snapshot(&self) -> Model {
        let mut model = Model::default();
        // An input the solver does not hold is free, and false when it is asked for ([`Blaster::holds`]).
        let before = self.deferred.unwrap_or(self.defs.len());
        for (v, def) in self.defs.iter().enumerate().take(before).skip(2) {
            if matches!(def, Def::Input) {
                model.set(v, self.solver.value(v as Lit).unwrap_or(false));
            }
        }
        for &v in &self.numbered_inputs {
            model.set(v, self.value(v as Lit));
        }
        model
    }

    /// The solver's last model with the inputs among `free` given other values, by `seed`, and the inputs it does
    /// not fix drawn by it too ([`Model::salted`]): a model of everything that does not depend on those inputs.
    pub fn snapshot_with(&self, free: &[Bits], seed: u64) -> Model {
        let mut model = self.snapshot().salted(seed);
        let mut state = seed | 1;
        for &l in free.iter().flatten() {
            let v = l.unsigned_abs() as usize;
            if v < 2 || !matches!(self.defs[v], Def::Input) {
                continue;
            }
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            model.set(v, state & 1 == 1);
        }
        model
    }

    /// Gives the inputs among `to`, in `model`, the values `from` has there, bit by bit: a state's new, free
    /// values set to the ones they replace.
    pub fn carry(&mut self, model: &mut Model, from: &Bits, to: &Bits) {
        for (&old, &new) in from.iter().zip(to) {
            let v = new.unsigned_abs() as usize;
            if v >= 2 && matches!(self.defs[v], Def::Input) {
                let value = self.holds(model, old);
                model.set(v, value == (new > 0));
            }
        }
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
                    model.set(v, model.free(v));
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
                Def::Word(i) => {
                    // The real operation on the operands' values, every bit of the result at once.
                    let w = &self.word_ops[i as usize];
                    let mut ready = true;
                    for &x in w.operands.iter().flatten() {
                        ready &= need(model, &mut stack, x).is_some();
                    }
                    if ready {
                        let values: Vec<i64> = w.operands.iter().map(|o| value_in(model, o).expect("ready")).collect();
                        let v = word_value(w.op, w.operands[w.operands.len() - 1].len(), &values);
                        for (k, &bit) in w.out.iter().enumerate() {
                            model.set(bit as usize, (v >> k.min(63)) & 1 == 1);
                        }
                        stack.pop();
                        done += 1;
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
        self.numbered(lit).and_then(|l| self.solver.value(l)).unwrap_or(false)
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

    /// Runs `op` on a blaster `new` makes, on fresh inputs pinned to `x` and `y` by assumptions, so that the
    /// circuits are exercised rather than folded away, and reads the result back from the model. That result is
    /// also the one the blaster evaluates from the inputs' values alone, as a path's kept model is evaluated.
    fn circuit_on(new: &dyn Fn() -> Blaster, width: usize, x: i64, y: i64, op: impl Fn(&mut Blaster, &Bits, &Bits) -> Bits) -> i64 {
        let mut b = new();
        let a = b.fresh(width);
        let c = b.fresh(width);
        let out = op(&mut b, &a, &c);
        let mut assumptions = Vec::new();
        for i in 0..width {
            assumptions.push(if (x >> i) & 1 == 1 { a[i] } else { -a[i] });
            assumptions.push(if (y >> i) & 1 == 1 { c[i] } else { -c[i] });
        }
        assert_eq!(b.solve_with(&assumptions), Some(true));
        let value = b.eval(&out);
        let mut model = b.snapshot();
        let evaluated: Vec<Lit> = out.iter().map(|&l| if b.holds(&mut model, l) { TRUE } else { FALSE }).collect();
        assert_eq!(b.constant_value(&evaluated), Some(value), "the model's value is the evaluated one ({x}, {y})");
        value
    }

    fn bit_on(new: &dyn Fn() -> Blaster, width: usize, x: i64, y: i64, op: impl Fn(&mut Blaster, &Bits, &Bits) -> Lit) -> bool {
        circuit_on(new, width, x, y, |b, a, c| vec![op(b, a, c)]) & 1 == 1
    }

    const INTS: &[i32] = &[0, 1, -1, 2, 3, 7, -7, 10, 100, 1000, 65535, 65536, -65536, 1 << 30, i32::MAX, i32::MIN, i32::MIN + 1, 0x5555_5555, -0x1234_5678];
    const LONGS: &[i64] = &[0, 1, -1, 3, -3, 1000, i32::MAX as i64, i32::MIN as i64, 1 << 40, -(1 << 40), i64::MAX, i64::MIN, i64::MIN + 1, 0x0123_4567_89AB_CDEF];

    #[test]
    fn int_arithmetic_is_the_jvms() {
        int_arithmetic_on(&Blaster::new);
    }

    #[test]
    fn long_arithmetic_is_the_jvms() {
        long_arithmetic_on(&Blaster::new);
    }

    /// A blaster over Bitwuzla given terms, if it is installed here.
    fn over_words() -> Option<impl Fn() -> Blaster> {
        if let Err(e) = super::super::bitwuzla::available() {
            eprintln!("skipped: {}", e.0);
            return None;
        }
        Some(|| Blaster::over(super::super::bitwuzla::boxed_configured(&[], true), None))
    }

    #[test]
    fn word_level_operations_on_bitwuzla_are_the_jvms() {
        let Some(new) = over_words() else { return };
        assert!(new().takes_terms());
        int_arithmetic_on(&new);
        long_arithmetic_on(&new);
    }

    #[test]
    fn word_level_operations_fold_constants_and_are_built_once() {
        let Some(new) = over_words() else { return };
        let mut b = new();
        let (x, y) = (b.fresh(32), b.fresh(32));
        let zero = b.constant(0, 32);
        let one = b.constant(1, 32);
        assert_eq!(b.add(&x, &zero), x);
        assert_eq!(b.sub(&x, &zero), x);
        assert_eq!(b.mul(&x, &one), x);
        assert_eq!(b.mul(&zero, &y), zero);
        assert_eq!(b.eq(&x, &x), TRUE);
        assert_eq!(b.ult(&x, &x), FALSE);
        let seven = b.constant(7, 32);
        let six = b.constant(6, 32);
        assert_eq!(b.add(&seven, &six), b.constant(13, 32));
        assert_eq!(b.word_operations(), 0);
        let p = b.mul(&x, &y);
        let q = b.mul_lazy(&y, &x);
        assert_eq!(p, q, "a product in either order is one operation");
        let (d, r) = b.sdivrem_lazy(&x, &y);
        assert_eq!(b.sdivrem(&x, &y), (d.clone(), r.clone()));
        assert_eq!(b.word_operations(), 3);
        assert_eq!(b.divisions(), (0, 0), "nothing is left to refinement");
        // A product a model gets wrong cannot happen: the solver is given the operation itself.
        let (x7, y6) = (b.eq(&x, &seven), b.eq(&y, &six));
        let p42 = b.eq(&p, &b.constant(42, 32).clone());
        assert_eq!(b.solve_with(&[x7, y6, -p42]), Some(false));
        assert_eq!(b.solve_with(&[x7, y6]), Some(true));
        assert_eq!((b.eval(&p), b.eval(&d), b.eval(&r)), (42, 1, 1));
        assert_eq!(b.wrong_operation(&b.every_operation()), None);
        assert_eq!(b.clauses, 1, "the constant's unit clause, and nothing else");
    }

    fn int_arithmetic_on(new: &dyn Fn() -> Blaster) {
        let circuit = |w, x, y, op: &dyn Fn(&mut Blaster, &Bits, &Bits) -> Bits| circuit_on(new, w, x, y, op);
        let bit = |w, x, y, op: &dyn Fn(&mut Blaster, &Bits, &Bits) -> Lit| bit_on(new, w, x, y, op);
        for &x in INTS {
            for &y in INTS {
                let (x64, y64) = (i64::from(x), i64::from(y));
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.add(a, c)) as i32, x.wrapping_add(y), "{x} + {y}");
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.sub(a, c)) as i32, x.wrapping_sub(y), "{x} - {y}");
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.mul(a, c)) as i32, x.wrapping_mul(y), "{x} * {y}");
                if y != 0 {
                    assert_eq!(circuit(32, x64, y64, &|b, a, c| b.sdivrem(a, c).0) as i32, x.wrapping_div(y), "{x} / {y}");
                    assert_eq!(circuit(32, x64, y64, &|b, a, c| b.sdivrem(a, c).1) as i32, x.wrapping_rem(y), "{x} % {y}");
                }
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.shl(a, c)) as i32, x.wrapping_shl(y as u32), "{x} << {y}");
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.shr(a, c)) as i32, x.wrapping_shr(y as u32), "{x} >> {y}");
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.ushr(a, c)) as i32, ((x as u32).wrapping_shr(y as u32)) as i32, "{x} >>> {y}");
                assert_eq!(bit(32, x64, y64, &|b, a, c| b.slt(a, c)), x < y, "{x} < {y}");
                assert_eq!(bit(32, x64, y64, &|b, a, c| b.sle(a, c)), x <= y, "{x} <= {y}");
                assert_eq!(bit(32, x64, y64, &|b, a, c| b.eq(a, c)), x == y, "{x} == {y}");
                assert_eq!(bit(32, x64, y64, &|b, a, c| b.ult(a, c)), (x as u32) < (y as u32), "{x} <u {y}");
            }
            assert_eq!(circuit(32, i64::from(x), 0, &|b, a, _| b.neg(a)) as i32, x.wrapping_neg());
            assert_eq!(circuit(32, i64::from(x), 0, &|b, a, _| b.sext(&b.trunc(a, 8), 32)) as i32, x as i8 as i32, "i2b");
            assert_eq!(circuit(32, i64::from(x), 0, &|b, a, _| b.zext(&b.trunc(a, 16), 32)) as i32, x as u16 as i32, "i2c");
            assert_eq!(circuit(32, i64::from(x), 0, &|b, a, _| b.sext(&b.trunc(a, 16), 32)) as i32, x as i16 as i32, "i2s");
            for &y in &[0x0F0F_0F0F, -1, i32::MIN] {
                let (x64, y64) = (i64::from(x), i64::from(y));
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.and_bits(a, c)) as i32, x & y, "{x} & {y}");
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.or_bits(a, c)) as i32, x | y, "{x} | {y}");
                assert_eq!(circuit(32, x64, y64, &|b, a, c| b.xor_bits(a, c)) as i32, x ^ y, "{x} ^ {y}");
                assert_eq!(circuit(32, x64, y64, &|b, a, c| { let less = b.slt(a, c); b.ite_bits(less, a, c) }) as i32, x.min(y), "min({x}, {y})");
            }
        }
    }

    fn long_arithmetic_on(new: &dyn Fn() -> Blaster) {
        let circuit = |w, x, y, op: &dyn Fn(&mut Blaster, &Bits, &Bits) -> Bits| circuit_on(new, w, x, y, op);
        let bit = |w, x, y, op: &dyn Fn(&mut Blaster, &Bits, &Bits) -> Lit| bit_on(new, w, x, y, op);
        for &x in LONGS {
            for &y in LONGS {
                assert_eq!(circuit(64, x, y, &|b, a, c| b.add(a, c)), x.wrapping_add(y), "{x} + {y}");
                assert_eq!(circuit(64, x, y, &|b, a, c| b.mul(a, c)), x.wrapping_mul(y), "{x} * {y}");
                if y != 0 {
                    assert_eq!(circuit(64, x, y, &|b, a, c| b.sdivrem(a, c).0), x.wrapping_div(y), "{x} / {y}");
                    assert_eq!(circuit(64, x, y, &|b, a, c| b.sdivrem(a, c).1), x.wrapping_rem(y), "{x} % {y}");
                }
                assert_eq!(bit(64, x, y, &|b, a, c| b.slt(a, c)), x < y, "{x} < {y}");
            }
            for &s in &[0i64, 1, 31, 32, 63, 64, 100, -1] {
                assert_eq!(circuit(64, x, s, &|b, a, c| b.shl(a, &b.trunc(c, 32))), x.wrapping_shl(s as u32), "{x} << {s}");
                assert_eq!(circuit(64, x, s, &|b, a, c| b.shr(a, &b.trunc(c, 32))), x.wrapping_shr(s as u32), "{x} >> {s}");
                assert_eq!(circuit(64, x, s, &|b, a, c| b.ushr(a, &b.trunc(c, 32))), ((x as u64).wrapping_shr(s as u32)) as i64, "{x} >>> {s}");
            }
            assert_eq!(circuit(64, x, 0, &|b, a, _| b.sext(&b.trunc(a, 32), 64)), x as i32 as i64, "l2i then i2l");
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

    /// What the engine's solve loop does: lemmas first, then circuits, until the model is real or there is none.
    fn solve_refined(b: &mut Blaster, assumptions: &[Lit]) -> Option<bool> {
        loop {
            match b.solve_with(assumptions) {
                Some(true) => match (b.inconsistent_pair(&b.every_operation()), b.wrong_operation(&b.every_operation())) {
                    (Some((i, j, swapped)), _) => b.add_congruence(i, j, swapped),
                    (None, None) => return Some(true),
                    (None, Some(i)) => b.refine_operation(i),
                },
                other => return other,
            }
        }
    }

    #[test]
    fn equal_operands_give_equal_results_without_building_a_circuit() {
        // real/bucket/fix-confined: Math.abs(hash) % n and (hash & 0x7fffffff) % n, for a hash that is not negative.
        let mut b = Blaster::new();
        let (hash, n) = (b.fresh(32), b.fresh(32));
        let mask = b.constant(0x7fff_ffff, 32);
        let cleared = b.and_bits(&hash, &mask);
        let (_, r1) = b.sdivrem_lazy(&hash, &n);
        let (_, r2) = b.sdivrem_lazy(&cleared, &n);
        assert_ne!(r1, r2, "different operand terms: separate bits");
        let non_negative = -b.negative(&hash);
        let differ = -b.eq(&r1, &r2);
        assert_eq!(solve_refined(&mut b, &[non_negative, differ]), Some(false));
        assert_eq!(b.divisions(), (2, 0), "no divider was built");
        assert!(b.congruences >= 1);
        // For a negative hash the operands differ, and so may the remainders: the lemma leaves that model.
        assert_eq!(solve_refined(&mut b, &[-non_negative, differ]), Some(true));
        assert_ne!(b.eval(&r1), b.eval(&r2));
        // Products are one function of their operands in either order.
        let (p1, p2) = (b.mul_lazy(&hash, &n), b.mul_lazy(&n, &cleared));
        let differ = -b.eq(&p1, &p2);
        assert_eq!(solve_refined(&mut b, &[non_negative, differ]), Some(false));
        assert_eq!(b.multiplications().1, 0, "no multiplier was built");
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
        while let Some(i) = b.wrong_operation(&b.every_operation()) {
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
        assert_eq!(b.wrong_operation(&b.every_operation()), None);
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
        assert_eq!(b.wrong_operation(&b.every_operation()), Some(0));
        b.refine_operation(0);
        assert_eq!(b.solve_with(&[x_300, y_500, p_wrong]), Some(false), "300 * 500 is 150000 once the circuit is there");
        assert_eq!(b.solve_with(&[x_300, y_500]), Some(true));
        assert!(b.value(p_right));
        assert_eq!(b.wrong_operation(&b.every_operation()), None);
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
        while let Some(i) = b.wrong_operation(&b.every_operation()) {
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
    fn deferred_gates_reach_the_solver_when_a_call_depends_on_them_and_answer_the_same() {
        let mut b = Blaster::new();
        let (x, y) = (b.fresh(32), b.fresh(32));
        let early = b.add(&x, &y);
        b.defer();
        let given = b.clauses;
        // Built and never asked about: the solver is given nothing.
        let unused = b.mul(&early, &x);
        let late = b.sub(&early, &y);
        assert_eq!(b.clauses, given, "{unused:?}");
        // Asked about: x + y - y == x, whatever the values, and a value the solver chooses is read back.
        let same = b.eq(&late, &x);
        assert_eq!(b.solve_with(&[-same]), Some(false));
        assert!(b.clauses > given);
        let x_is = b.eq(&x, &b.constant(40, 32).clone());
        let sum_is = b.eq(&early, &b.constant(42, 32).clone());
        assert_eq!(b.solve_with(&[x_is, sum_is]), Some(true));
        assert_eq!((b.eval(&x), b.eval(&y), b.eval(&late)), (40, 2, 40));
        let mut model = b.snapshot();
        assert!(b.holds(&mut model, same));
    }

    #[test]
    fn an_index_that_goes_round_an_array_is_exact_without_its_division() {
        // (i + 1) % n for 0 <= i < n is i + 1, or zero at the end: the facts given once clauses are deferred say
        // so, and no divider is built.
        let mut b = Blaster::new();
        b.defer();
        let (i, n) = (b.fresh(32), b.fresh(32));
        let (zero, one) = (b.constant(0, 32), b.constant(1, 32));
        let next = b.add(&i, &one);
        let (_, r) = b.sdivrem_lazy(&next, &n);
        let inside = [b.sle(&zero, &i), b.slt(&i, &n)];
        let last = b.eq(&next, &n);
        let wraps = b.is_zero(&r);
        let steps = b.eq(&r, &next);
        let exact = b.ite(last, wraps, steps);
        assert_eq!(b.solve_with(&[inside[0], inside[1], -exact]), Some(false));
        let in_bounds = b.ult(&r, &n);
        assert_eq!(b.solve_with(&[inside[0], inside[1], -in_bounds]), Some(false));
        assert_eq!(b.divisions(), (1, 0), "no circuit was built");
        // A division by a constant power of two is shifts from the start.
        let eight = b.constant(8, 32);
        let (q, _) = b.sdivrem_lazy(&i, &eight);
        let minus_nine = b.eq(&i, &b.constant(-9, 32).clone());
        let minus_one = b.eq(&q, &b.constant(-1, 32).clone());
        assert_eq!(b.solve_with(&[minus_nine, -minus_one]), Some(false), "-9 / 8 == -1");
        assert_eq!(b.divisions(), (1, 0));
    }

    #[test]
    fn a_models_copy_shares_its_pages_until_one_of_the_two_writes() {
        let mut model = Model::default();
        model.set(5, true);
        model.set(100_000, false);
        let mut copy = model.clone();
        assert!(std::rc::Rc::ptr_eq(model.pages[0].as_ref().unwrap(), copy.pages[0].as_ref().unwrap()));
        copy.set(6, true);
        assert!(!std::rc::Rc::ptr_eq(model.pages[0].as_ref().unwrap(), copy.pages[0].as_ref().unwrap()));
        assert_eq!((model.get(5), model.get(6), model.get(100_000), model.get(100_001)), (Some(true), None, Some(false), None));
        assert_eq!((copy.get(5), copy.get(6), copy.get(100_000)), (Some(true), Some(true), Some(false)));
        // A variable the model does not fix is false, or drawn by the salt, the same each time it is asked.
        let salted = model.salted(7);
        assert!(!model.free(9));
        assert_eq!(salted.free(9), salted.free(9));
        assert!((0..64).any(|v| salted.free(v)) && (0..64).any(|v| !salted.free(v)));
    }

    #[test]
    fn the_encoding_is_estimated_from_a_sample_of_the_operations() {
        let mut b = Blaster::new();
        let (x, y) = (b.fresh(32), b.fresh(32));
        let started = std::time::Instant::now();
        let mut acc = x.clone();
        for _ in 0..20_000 {
            let sum = b.add(&acc, &y);
            acc = b.xor_bits(&sum, &x);
        }
        let wall = started.elapsed();
        assert!(b.encoding > std::time::Duration::ZERO, "some operations were timed");
        // Every operation here builds circuits, so the estimate is the loop's time, give or take the sample's
        // error and the loop's own work.
        assert!(b.encoding < wall * 2 && b.encoding > wall / 4, "estimated {:?} of {:?}", b.encoding, wall);
        // An operation inside another (the adders of a multiplication) counts as part of it, once.
        let before = b.encoding;
        let product = b.mul(&x, &y);
        assert_eq!(product.len(), 32);
        assert!(!b.timing, "the clock is not left running");
        assert!(b.encoding >= before);
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

    /// A short run's encoding is estimated within the phases' tolerance of the time its operations took, wherever
    /// its one large circuit falls among cheap gates: a sampled multiplier is not counted many times over.
    #[test]
    fn the_encoding_estimate_does_not_count_a_large_circuit_many_times_over() {
        let gates = 4 * ENCODING_SAMPLE as usize;
        for at in 0..=gates {
            let mut b = Blaster::new();
            let (x, y) = (b.fresh(32), b.fresh(32));
            let lits = b.fresh(2 * gates + 2);
            let started = std::time::Instant::now();
            for i in 0..=gates {
                if i == at {
                    b.mul(&x, &y);
                } else {
                    b.and(lits[2 * i], lits[2 * i + 1]);
                }
            }
            let took = started.elapsed().as_secs_f64();
            let estimate = b.encoding.as_secs_f64();
            let tolerance = crate::phases::TOLERANCE_SHARE * took + crate::phases::TOLERANCE_SECONDS;
            assert!(estimate <= took + tolerance, "the multiplication at operation {at}: encoding estimated {estimate:.6} s of {took:.6} s");
        }
    }
}
