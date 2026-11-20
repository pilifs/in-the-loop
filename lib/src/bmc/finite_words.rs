//! Exact finite-domain queries in front of the word-level solver. Each node branches on a free
//! Boolean input, in a fixed order; its leaves are machine words. Applying an operation to nodes
//! splits on the earliest input until the operands are concrete. Interning equal subtrees keeps
//! single-input arithmetic and repeated comparisons shared across paths.
//!
//! The backing solver receives every term and clause. A diagram limit only changes which solver
//! answers the query. A counterexample is one satisfying path through the complete Boolean result.

use std::collections::HashMap;
use std::time::{Duration, Instant};

use super::bits::{word_value, Lit};
use super::sat::{Gate, Sat, Terms, WordOp};

type Id = u32;
const ZERO: Id = 0;
const ONE: Id = 1;
const MAX_INPUTS: usize = 18;
const MAX_NODES: usize = 750_000;
const MAX_CACHE: usize = 500_000;

#[derive(Clone, Copy, Hash, PartialEq, Eq)]
enum Node {
    Value(u64),
    Branch(Lit, Id, Id),
}

#[derive(Clone, Copy, Hash, PartialEq, Eq)]
enum Op {
    Word(WordOp, u8),
    Bit(u8),
    Insert(u8),
}

impl Op {
    fn value(self, x: [u64; 3]) -> u64 {
        match self {
            Self::Bit(k) => (x[0] >> k) & 1,
            Self::Insert(k) => x[0] | (x[1] << k),
            Self::Word(op, width) => {
                let result = word_value(op, width.into(), &x.map(|v| v as i64)) as u64;
                result & (u64::MAX >> (64 - width))
            }
        }
    }
}

#[derive(Clone, Copy)]
struct Bit {
    word: Id,
    index: u8,
}

struct Diagrams {
    nodes: Vec<Node>,
    unique: HashMap<Node, Id>,
    cache: HashMap<(Op, [Id; 3]), Id>,
    // A literal can refer to one bit of a word without materializing the other bit diagrams.
    bits: HashMap<Lit, Bit>,
    words: HashMap<Vec<Lit>, Id>,
    inputs: usize,
    asserted: Id,
    model: HashMap<Lit, bool>,
}

impl Diagrams {
    fn new() -> Self {
        let mut s = Self { nodes: Vec::new(), unique: HashMap::new(), cache: HashMap::new(),
            bits: HashMap::new(), words: HashMap::new(), inputs: 0, asserted: ONE, model: HashMap::new() };
        s.intern(Node::Value(0)).unwrap();
        s.intern(Node::Value(1)).unwrap();
        s
    }

    fn intern(&mut self, node: Node) -> Option<Id> {
        if let Node::Branch(_, low, high) = node {
            if low == high { return Some(low); }
        }
        if let Some(&id) = self.unique.get(&node) { return Some(id); }
        if self.nodes.len() >= MAX_NODES { return None; }
        let id = self.nodes.len() as Id;
        self.nodes.push(node);
        self.unique.insert(node, id);
        Some(id)
    }

    fn apply(&mut self, op: Op, args: [Id; 3]) -> Option<Id> {
        match (op, args) {
            (Op::Word(WordOp::And, 1), [ZERO, _, _] | [_, ZERO, _]) => return Some(ZERO),
            (Op::Word(WordOp::And, 1), [ONE, a, _] | [a, ONE, _]) => return Some(a),
            (Op::Word(WordOp::Or, 1), [ONE, _, _] | [_, ONE, _]) => return Some(ONE),
            (Op::Word(WordOp::Or, 1), [ZERO, a, _] | [a, ZERO, _]) => return Some(a),
            (Op::Word(WordOp::Ite, _), [ZERO, _, b]) => return Some(b),
            (Op::Word(WordOp::Ite, _), [ONE, a, _]) => return Some(a),
            (Op::Word(WordOp::Ite, _), [_, a, b]) if a == b => return Some(a),
            (Op::Insert(_), [a, ZERO, _]) => return Some(a),
            _ => {}
        }
        if let Some(&id) = self.cache.get(&(op, args)) { return Some(id); }
        let nodes = args.map(|a| self.nodes[a as usize]);
        let var = nodes.iter().filter_map(|n| match n { Node::Branch(v, ..) => Some(*v), _ => None }).min();
        let id = if let Some(var) = var {
            let branch = |high| std::array::from_fn(|i| match nodes[i] {
                Node::Branch(v, l, h) if v == var => if high { h } else { l },
                _ => args[i],
            });
            let low = self.apply(op, branch(false))?;
            let high = self.apply(op, branch(true))?;
            self.intern(Node::Branch(var, low, high))?
        } else {
            let x = nodes.map(|n| match n { Node::Value(x) => x, _ => unreachable!() });
            self.intern(Node::Value(op.value(x)))?
        };
        if self.cache.len() >= MAX_CACHE { self.cache.clear(); }
        self.cache.insert((op, args), id);
        Some(id)
    }

    fn literal(&mut self, lit: Lit) -> Option<Id> {
        let v = lit.abs();
        let bit = if let Some(&bit) = self.bits.get(&v) { bit } else {
            if self.inputs >= MAX_INPUTS { return None; }
            self.inputs += 1;
            let bit = Bit { word: self.intern(Node::Branch(v, ZERO, ONE))?, index: 0 };
            self.bits.insert(v, bit);
            bit
        };
        let value = self.apply(Op::Bit(bit.index), [bit.word, ZERO, ZERO])?;
        if lit > 0 { Some(value) } else { self.apply(Op::Word(WordOp::Xor, 1), [value, ONE, ZERO]) }
    }

    fn operand(&mut self, bits: &[Lit]) -> Option<Id> {
        if let Some(&id) = self.words.get(bits) { return Some(id); }
        let mut value = ZERO;
        for (k, &lit) in bits.iter().enumerate() {
            let bit = self.literal(lit)?;
            value = self.apply(Op::Insert(k as u8), [value, bit, ZERO])?;
        }
        self.words.insert(bits.to_vec(), value);
        Some(value)
    }

    fn word(&mut self, outs: &[Lit], op: WordOp, operands: &[&[Lit]]) -> Option<()> {
        let mut args = [ZERO; 3];
        for (i, operand) in operands.iter().enumerate() { args[i] = self.operand(operand)?; }
        let width = operands.last()?.len() as u8;
        let word = self.apply(Op::Word(op, width), args)?;
        self.words.insert(outs.to_vec(), word);
        for (k, &out) in outs.iter().enumerate() { self.bits.insert(out, Bit { word, index: k as u8 }); }
        Some(())
    }

    fn gate(&mut self, out: Lit, gate: Gate) -> Option<()> {
        let (op, a, b, c) = match gate {
            Gate::And(a, b) => (WordOp::And, a, b, None),
            Gate::Xor(a, b) => (WordOp::Xor, a, b, None),
            Gate::Ite(c, a, b) => (WordOp::Ite, c, a, Some(b)),
        };
        let args = [self.literal(a)?, self.literal(b)?, if let Some(c) = c { self.literal(c)? } else { ZERO }];
        let word = self.apply(Op::Word(op, 1), args)?;
        self.bits.insert(out, Bit { word, index: 0 });
        Some(())
    }

    fn clause(&mut self, lits: &[Lit]) -> Option<()> {
        // A first use as a permanent unit fixes that variable for all future queries.
        if let &[lit] = lits {
            if let std::collections::hash_map::Entry::Vacant(e) = self.bits.entry(lit.abs()) {
                e.insert(Bit { word: if lit > 0 { ONE } else { ZERO }, index: 0 });
                return Some(());
            }
        }
        let mut clause = ZERO;
        for &lit in lits {
            let term = self.literal(lit)?;
            clause = self.apply(Op::Word(WordOp::Or, 1), [clause, term, ZERO])?;
        }
        self.asserted = self.apply(Op::Word(WordOp::And, 1), [self.asserted, clause, ZERO])?;
        Some(())
    }

    fn solve(&mut self, assumptions: &[Lit]) -> Option<bool> {
        self.model.clear();
        let mut root = self.asserted;
        for &lit in assumptions {
            let term = self.literal(lit)?;
            root = self.apply(Op::Word(WordOp::And, 1), [root, term, ZERO])?;
            if root == ZERO { return Some(false); }
        }
        while let Node::Branch(var, low, high) = self.nodes[root as usize] {
            let choose_high = low == ZERO;
            self.model.insert(var, choose_high);
            root = if choose_high { high } else { low };
        }
        Some(root == ONE)
    }

    fn value(&self, lit: Lit) -> bool {
        let Some(bit) = self.bits.get(&lit.abs()) else { return lit < 0 };
        let mut node = self.nodes[bit.word as usize];
        loop {
            match node {
                Node::Value(v) => return ((v >> bit.index) & 1 != 0) == (lit > 0),
                Node::Branch(var, low, high) => {
                    node = self.nodes[if self.model.get(&var) == Some(&true) { high } else { low } as usize];
                }
            }
        }
    }
}

pub(super) struct Solver {
    diagrams: Option<Diagrams>,
    backing: Box<dyn Sat>,
    table_model: bool,
    limit: Option<Duration>,
    diagram_queries: u64,
    backing_queries: u64,
}

impl Solver {
    pub(super) fn new(backing: Box<dyn Sat>) -> Self {
        Self { diagrams: Some(Diagrams::new()), backing, table_model: false, limit: None, diagram_queries: 0, backing_queries: 0 }
    }

    fn update(&mut self, f: impl FnOnce(&mut Diagrams) -> Option<()>) {
        if self.diagrams.as_mut().is_some_and(|d| f(d).is_none()) {
            self.diagrams = None;
            self.table_model = false;
        }
    }
}

impl Terms for Solver {
    fn gate(&mut self, out: Lit, gate: Gate) {
        self.backing.terms().unwrap().gate(out, gate);
        self.update(|d| d.gate(out, gate));
    }

    fn word(&mut self, outs: &[Lit], op: WordOp, operands: &[&[Lit]]) {
        self.backing.terms().unwrap().word(outs, op, operands);
        self.update(|d| d.word(outs, op, operands));
    }
}

impl Sat for Solver {
    fn signature(&self) -> String { format!("{} with finite word diagrams", self.backing.signature()) }
    fn record(&self) -> crate::statement::Sat {
        let mut record = self.backing.record();
        record.configuration.push(format!("exact reduced word diagrams up to {MAX_INPUTS} input bits and {MAX_NODES} nodes, then the full Bitwuzla formula"));
        record
    }
    fn terms(&mut self) -> Option<&mut dyn Terms> { Some(self) }
    fn add_clause(&mut self, lits: &[Lit]) {
        self.backing.add_clause(lits);
        self.update(|d| d.clause(lits));
        self.table_model = false;
    }
    fn set_limit(&mut self, seconds: Option<f32>) {
        self.limit = seconds.map(|s| Duration::from_secs_f32(s.max(0.0)));
        self.backing.set_limit(seconds);
    }
    fn solve(&mut self, assumptions: &[Lit]) -> Option<bool> {
        let started = Instant::now();
        self.table_model = false;
        if let Some(answer) = self.diagrams.as_mut().and_then(|d| d.solve(assumptions)) {
            self.diagram_queries += 1;
            if self.limit.is_some_and(|limit| started.elapsed() >= limit) { return None; }
            self.table_model = answer;
            return Some(answer);
        }
        self.diagrams = None;
        self.backing_queries += 1;
        self.backing.set_limit(self.limit.map(|limit| limit.saturating_sub(started.elapsed()).as_secs_f32()));
        self.backing.solve(assumptions)
    }
    fn value(&self, lit: Lit) -> Option<bool> {
        if self.table_model { Some(self.diagrams.as_ref()?.value(lit)) } else { self.backing.value(lit) }
    }
    fn variables(&self) -> i32 { self.backing.variables() }
    fn finite_queries(&self) -> Option<super::sat::FiniteQueries> {
        Some(super::sat::FiniteQueries { diagrams: self.diagram_queries, bitwuzla: self.backing_queries })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn signed3(x: u64) -> i64 { ((x << 61) as i64) >> 61 }

    #[test]
    fn finite_word_queries_and_witnesses_agree_with_every_three_bit_input() {
        use WordOp::*;
        let operations = [Add, Sub, Mul, Div, Rem, Shl, Shr, Ushr, And, Or, Xor, Ult, Slt, Eq, Ite];
        let a = [2, 3, 4];
        let b = [5, 6, 7];
        let condition = [-2];
        let mut d = Diagrams::new();
        d.clause(&[1]).unwrap();
        let mut next = 8;
        for op in operations {
            let inputs: Vec<&[Lit]> = if op == Ite { vec![&condition, &a, &b] } else { vec![&a, &b] };
            let count = if op.compares() { 1 } else { 3 };
            let outs: Vec<_> = (next..next + count).collect();
            next += count;
            d.word(&outs, op, &inputs).unwrap();
            for x in 0u64..8 {
                for y in 0u64..8 {
                    let expected = match op {
                        Add => x + y, Sub => x.wrapping_sub(y), Mul => x * y,
                        Div if y == 0 => if signed3(x) < 0 { 1 } else { 7 },
                        Rem if y == 0 => x,
                        Div => (signed3(x) / signed3(y)) as u64,
                        Rem => (signed3(x) % signed3(y)) as u64,
                        Shl => x << y, Shr => (signed3(x) >> y) as u64, Ushr => x >> y,
                        And => x & y, Or => x | y, Xor => x ^ y,
                        Ult => u64::from(x < y), Slt => u64::from(signed3(x) < signed3(y)),
                        Eq => u64::from(x == y), Ite => if x & 1 == 0 { x } else { y },
                    } & 7;
                    let fixed = [(&a, x), (&b, y)].into_iter().flat_map(|(bits, word)| {
                        bits.iter().enumerate().map(move |(k, &l)| if word >> k & 1 == 1 { l } else { -l })
                    }).collect::<Vec<_>>();
                    assert_eq!(d.solve(&fixed), Some(true));
                    for (k, &lit) in outs.iter().enumerate() {
                        let bit = expected >> k & 1 == 1;
                        assert_eq!(d.value(lit), bit, "{op:?}({x}, {y}) bit {k}");
                        let mut impossible = fixed.clone();
                        impossible.push(if bit { -lit } else { lit });
                        assert_eq!(d.solve(&impossible), Some(false), "{op:?}({x}, {y}) bit {k}");
                        assert_eq!(d.solve(&fixed), Some(true));
                    }
                }
            }
        }
        // Read a model of an output constraint alone, without prescribing all of its inputs.
        d.gate(next, Gate::And(-a[0], b[1])).unwrap();
        d.gate(next + 1, Gate::Xor(next, a[2])).unwrap();
        d.gate(next + 2, Gate::Ite(a[1], next, next + 1)).unwrap();
        assert_eq!(d.solve(&[next + 2]), Some(true));
        let selected = !d.value(a[0]) && d.value(b[1]);
        assert!(if d.value(a[1]) { selected } else { selected ^ d.value(a[2]) });
        d.clause(&[-(next + 2)]).unwrap();
        assert_eq!(d.solve(&[next + 2]), Some(false));
        assert_eq!(d.solve(&[]), Some(true));
    }

    #[test]
    fn word_diagrams_preserve_signed_long_overflow_and_wide_shift_distances() {
        use WordOp::*;
        let bits = |v: u64| (0..64).map(|k| if v >> k & 1 == 1 { 1 } else { -1 }).collect::<Vec<_>>();
        let min = i64::MIN as u64;
        for (op, a, b, expected) in [(Div, min, u64::MAX, min), (Rem, min, u64::MAX, 0),
            (Div, min, 0, 1), (Div, 0, 0, u64::MAX), (Rem, min, 0, min),
            (Mul, min + 1, 2, 2), (Ushr, min, 63, 1), (Ushr, min, 64, 0),
            (Shl, 1, 64, 0), (Shr, min, 127, u64::MAX)] {
            let outs = (2..66).collect::<Vec<Lit>>();
            // A solver term is defined exactly once.
            let mut run = Diagrams::new();
            run.clause(&[1]).unwrap();
            run.word(&outs, op, &[&bits(a), &bits(b)]).unwrap();
            assert_eq!(run.solve(&[]), Some(true));
            let value = outs.iter().enumerate().fold(0u64, |v, (k, &l)| v | (u64::from(run.value(l)) << k));
            assert_eq!(value, expected, "{op:?}({a}, {b})");
        }
    }

    #[test]
    fn falling_back_at_the_input_limit_retains_all_clauses_and_terms() {
        let Ok(backing) = super::super::bitwuzla::Bitwuzla::configured(&[], true) else { return };
        let mut solver = Solver::new(Box::new(backing));
        solver.add_clause(&[1]);
        solver.gate(100, Gate::Xor(2, 3));
        solver.add_clause(&[-100]);
        assert_eq!(solver.solve(&[2, -3]), Some(false));
        assert_eq!(solver.solve(&[-2, -3]), Some(true));
        let many: Vec<_> = (2..(MAX_INPUTS as i32 + 5)).collect();
        solver.add_clause(&many);
        assert!(solver.diagrams.is_none());
        assert_eq!(solver.solve(&[2, -3]), Some(false));
        assert_eq!(solver.solve(&[-2, -3]), Some(true));
        assert_eq!(solver.value(100), Some(false));
        assert!(many.iter().any(|&v| solver.value(v) == Some(true)));
        assert_eq!(solver.finite_queries().unwrap(), super::super::sat::FiniteQueries { diagrams: 2, bitwuzla: 2 });
    }
}
