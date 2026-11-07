//! Contracts for the gaps of the tool's own checker (`--contracts FILE` under `--gaps advised`, step 3b of
//! `llm-dlc/loops/sound-verdicts.md`): what the agent driving the tool states about a call the engine does not
//! implement, in the format of the template [`crate::advice`] hands it, which the engine then applies at the call
//! in place of the gap.
//!
//! A file holds `kind: gap-contracts`, then a block per gap, headed by the gap's id at the start of a line, with
//! its keys indented under it (`#` starts a comment):
//!
//! ```text
//! kind: gap-contracts
//!
//! jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25.0.4.1
//!   call: java.util.ArrayList.<init>(int capacity)
//!   throws: IllegalArgumentException when capacity < 0
//!   modifies: nothing
//!   written-by: an agent (claude-opus-5-5)
//! ```
//!
//! | Key | What it states | |
//! |---|---|---|
//! | `call:` | the call, with a name for each parameter (`owner.name(type name, ...) [-> type]`), which the conditions use | required |
//! | `assume:` | the inputs the contract is about, a condition over the parameters; on the others the gap stays open and is refused | `true` if absent |
//! | `throws: X when c` | the call throws `X` (built by its constructor of no arguments) exactly where `c` holds, the first clause whose condition holds deciding, as in a property's throws clauses; it may be repeated | none if absent |
//! | `assert:` | what holds when it returns: over the parameters, the arrays it modifies, and `result` when it returns an integer, a `char` or a `boolean` (`0 <= result && result < bound`); for a call that returns an object, which object (`result == this`, `result == <parameter>`, `result == null`, or `\fresh(result)` for a new one) | `true` if absent, required for an object result |
//! | `modifies:` | `nothing`, or what it changes: `this` (whose state the engine does not keep) and parameters that are arrays of primitives, whose elements become any values `assert:` admits | required |
//! | `written-by:` | who wrote it: an agent or a person | required |
//!
//! The conditions use `prove`'s expression language ([`crate::harness::expr`]) over the parameters the `call:`
//! line names, which are of a primitive type or arrays of them. `\old` is not applied yet.
//!
//! A contract the engine cannot apply is refused, with the reason, and its gap stays open: a key still `TODO`, a
//! call that does not match the id, a parameter of a type the expressions do not have, `this` in a condition (the
//! engine keeps no state of a JDK object), a result of a form it cannot choose an object for, an initializer that
//! throws or sets state, a contract for a JDK other than the one the proof runs on, or for a string conversion.
//! Every contract the engine accepts is then tested on a real JVM ([`crate::contract_testing`], step 3c): the JDK's
//! own call runs on the boundary values of the parameters' types and on seeded random inputs, and the contract is
//! checked on each. One the JVM refutes is refused, with the inputs that refute it, and its gap stays open, so the
//! counterexample goes back to the agent with the advice. One no input refutes is `tested`, with the number of
//! inputs; one the JVM cannot test (a parameter it cannot make values of, a receiver it cannot build, no JVM) is
//! `trusted`, with the reason. Before the test, a contract for a static JDK method of primitives is proved against
//! the JDK's own bytecode where the method is in the checker's fragment ([`crate::contract_proving`]): such a
//! contract the JVM does not refute either is `proved`, the strongest level, and the witness of a proof that
//! refutes one is among the JVM's inputs. The verdict says which contracts it rests on, at which level. A gap the
//! file has no contract for takes the contract library's ([`crate::contract_library`], step 3d), applied on the
//! record of its check ([`Record`]) rather than checked again, and `--max-trust N` refuses the trusted contracts
//! when there are more than N.
//!
//! The engine applies a contract by calling a method of a class generated here, [`CLASS`], with the call's
//! arguments (and its receiver, for a method that may return it): a branch per throws clause that throws, a
//! choice of new values for each array it modifies, the assertion as a condition the path must meet, and the
//! result. Calls of [`INTRINSICS`] mean what bytecode cannot say: `open(int)` (the gap of contract `int` is met: an
//! input outside `assume:`), `havoc(Object)` (the array's elements become fresh values), `anyInt()` and
//! `anyLong()` (a primitive result is any value, which the method narrows to the result's type and the assertion
//! constrains) and `infeasible()` (no run of the JDK's call takes this path, as the assertion says). Under
//! `--engine jbmc` (or JBMC's turn under `auto`), JBMC runs the same class, the call sites rewritten into calls of
//! its methods and the intrinsics a class of JBMC's own ([`crate::jbmc_contracts`]).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::bmc::gaps::{self, Closing, Closure, ContractUse, Gap, GapKind, JdkCall};
use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::{flags, Cond, Kind, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::contract_proving::Proving;
use crate::harness::expr::{self, Param};
use crate::Error;

/// The generated class whose methods apply the contracts.
pub const CLASS: &str = "GapContracts";
/// The class of the engine's intrinsics the generated methods call; it exists on no class path.
pub const INTRINSICS: &str = "jvmcontract/GapIntrinsics";

/// How a contract is backed: what checked it, strongest first.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Evidence {
    /// The tool's own checker proved it against the JDK's bytecode, on every input inside `assume:`
    /// ([`crate::contract_proving`]); a JVM test runs too, and refutes none of it.
    Proved,
    /// A real JVM ran the JDK's call on the contract's boundary values and seeded random inputs, and none refutes
    /// it ([`crate::contract_testing`]).
    Tested,
    /// Nothing has checked it: the verdict rests on whoever wrote it.
    Trusted,
}

impl Evidence {
    pub fn name(self) -> &'static str {
        match self {
            Evidence::Proved => "proved",
            Evidence::Tested => "tested",
            Evidence::Trusted => "trusted",
        }
    }
}

/// What a test of a contract on a real JVM found ([`crate::contract_testing`]).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Testing {
    /// The inputs inside `assume:` on which the JVM ran the call to its end, which the contract is checked on.
    pub inputs: usize,
    /// Of those, how many returned, and how many threw as each throws clause says, in order.
    pub returned: usize,
    pub thrown: Vec<usize>,
    /// Inputs outside `assume:`, which say nothing about the contract.
    pub outside: usize,
    /// Inputs on which the JVM ran out of the test's memory or stack (a `VirtualMachineError`), which say nothing
    /// either way: a proof is about a JVM with enough of both.
    pub exhausted: usize,
    /// The seed the random inputs were drawn with, so the test can be repeated.
    pub seed: u64,
    /// The JDK whose `java` ran the test.
    pub jdk: String,
    /// The object an instance method was called on, built afresh for each input: `new java.util.Random()`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub receiver: Option<String>,
    /// Every input on which the JVM did what the contract does not say, at most [`crate::contract_testing::KEPT`].
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub counterexamples: Vec<Counterexample>,
    /// How many counterexamples there were in all.
    #[serde(default, skip_serializing_if = "is_zero")]
    pub refuting: usize,
}

fn is_zero(n: &usize) -> bool {
    *n == 0
}

impl Testing {
    /// In words: `tested on 312 inputs on JDK 25.0.4.1 (seed 1), none refuting it`.
    pub fn words(&self) -> String {
        let mut out = format!("tested on {} input{} on JDK {} (seed {})", self.inputs, if self.inputs == 1 { "" } else { "s" }, self.jdk, self.seed);
        if let Some(r) = &self.receiver {
            out.push_str(&format!(", each called on {r}"));
        }
        if self.exhausted > 0 {
            out.push_str(&format!(", {} more running out of the test's memory", self.exhausted));
        }
        if self.refuting == 0 {
            out.push_str(", none refuting it");
        }
        out
    }
}

/// What a proof of a contract against the JDK's bytecode was ([`crate::contract_proving`]).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Proof {
    /// The class whose bytecode was run: `java.lang.Integer`.
    pub class: String,
    /// The JDK whose image it came from, and the class file's digest.
    pub jdk: String,
    pub digest: String,
    /// The checker, with its SAT solver.
    pub checker: String,
    /// How many times a loop could be unwound: the proof is complete within it, or there is none.
    pub unwind: u32,
    pub paths: u64,
    pub seconds: f64,
}

impl Proof {
    /// In words: `proved on every input against the bytecode of java.lang.Integer in JDK 25.0.4.1 (sha256:...)`.
    pub fn words(&self) -> String {
        let short = self.digest.get(..19).unwrap_or(&self.digest);
        format!("proved on every input against the bytecode of {} in JDK {} ({short}...), by {} over {} path{}", self.class, self.jdk, self.checker, self.paths, if self.paths == 1 { "" } else { "s" })
    }
}

/// An input on which the JVM did what a contract does not say.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Counterexample {
    /// The input, by the `call:` line's names: `capacity = -1`.
    pub input: String,
    /// What the contract says the call does there.
    pub expected: String,
    /// What the JVM did.
    pub observed: String,
}

impl Counterexample {
    /// In a line: `on capacity = -1 the JVM's call throws ..., where the contract says it returns normally`.
    pub fn line(&self) -> String {
        format!("on {} the JVM's call {}, where the contract says it {}", if self.input.is_empty() { "no arguments".to_string() } else { self.input.clone() }, self.observed, self.expected)
    }
}

/// What testing needs of a contract the engine accepted: the call, its parameters, and its conditions compiled.
#[derive(Debug, Clone)]
pub(crate) struct Shape {
    pub gap: Gap,
    pub descriptor: MethodDescriptor,
    /// The `call:` line's names, one per parameter.
    pub names: Vec<String>,
    /// Whether the call has a receiver, in local 0 of the contract's methods.
    pub receiver: bool,
    pub assume: Option<expr::Expr>,
    /// Each throws clause's exception and condition, and as written.
    pub throws: Vec<(String, expr::Expr)>,
    pub throws_text: Vec<String>,
    pub modified: Vec<Param>,
    pub after: Option<expr::Expr>,
    pub assert: Option<String>,
    pub result: Option<ResultForm>,
    /// For a primitive result, the slot `result` names in the assertion: the first after the parameters.
    pub result_slot: Option<u16>,
    /// The first slot after the receiver, parameters and result, and the first no condition uses.
    pub first_free: u16,
    pub slots_used: u16,
}

impl Shape {
    /// An initializer's contract: it throws nothing.
    fn initializer(gap: &Gap) -> Shape {
        Shape { gap: gap.clone(), descriptor: MethodDescriptor { params: Vec::new(), ret: Type::Void }, names: Vec::new(), receiver: false, assume: None, throws: Vec::new(), throws_text: Vec::new(), modified: Vec::new(), after: None, assert: None, result: None, result_slot: None, first_free: 0, slots_used: 0 }
    }
}

/// One block of a contracts file, as written.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Block {
    pub id: String,
    /// The line of its id, from 1.
    pub line: usize,
    /// Its keys in order, with their values and lines.
    pub keys: Vec<(String, String, usize)>,
}

impl Block {
    fn values(&self, key: &str) -> Vec<&str> {
        self.keys.iter().filter(|(k, _, _)| k == key).map(|(_, v, _)| v.as_str()).collect()
    }

    fn value(&self, key: &str) -> Option<&str> {
        self.values(key).first().copied()
    }
}

/// The keys a contract has.
const KEYS: &[&str] = &["call", "assume", "throws", "assert", "modifies", "written-by"];

/// Reads the blocks of a contracts file; `origin` names it in errors. An error is the file's structure: a
/// contract that cannot be applied is refused one by one, by [`load`].
pub fn parse(text: &str, origin: &str) -> Result<Vec<Block>, Error> {
    let mut blocks: Vec<Block> = Vec::new();
    let mut kind = false;
    for (i, raw) in text.lines().enumerate() {
        let n = i + 1;
        let line = match raw.find('#') {
            Some(c) if raw[..c].trim().is_empty() || raw[..c].ends_with(char::is_whitespace) => &raw[..c],
            _ => raw,
        };
        if line.trim().is_empty() {
            continue;
        }
        let indented = line.starts_with(char::is_whitespace);
        if !kind {
            if indented || line.trim() != "kind: gap-contracts" {
                return Err(Error::new(format!("{origin}:{n}: a contracts file starts with `kind: gap-contracts`")));
            }
            kind = true;
            continue;
        }
        if !indented {
            let id = line.trim();
            if id.contains(char::is_whitespace) {
                return Err(Error::new(format!("{origin}:{n}: a contract starts with a gap's id alone on its line, as the template has it, found {id:?}")));
            }
            blocks.push(Block { id: id.to_string(), line: n, keys: Vec::new() });
            continue;
        }
        let Some(block) = blocks.last_mut() else {
            return Err(Error::new(format!("{origin}:{n}: a key before any contract's id")));
        };
        let (key, value) = line.trim().split_once(':').ok_or_else(|| Error::new(format!("{origin}:{n}: a contract's line is `key: value`, found {:?}", line.trim())))?;
        block.keys.push((key.trim().to_string(), value.trim().to_string(), n));
    }
    if !kind {
        return Err(Error::new(format!("{origin}: a contracts file starts with `kind: gap-contracts`")));
    }
    Ok(blocks)
}

/// A contract the engine applies.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Accepted {
    pub id: String,
    /// Where it was written: the `--contracts` file, or the contract library's file
    /// ([`crate::contract_library`]), and the line of its id.
    pub file: String,
    pub line: usize,
    /// What it states, in a line: `throws java.lang.IllegalArgumentException when capacity < 0; modifies nothing`.
    pub summary: String,
    pub written_by: String,
    pub evidence: Evidence,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub testing: Option<Testing>,
    /// Why it is trusted: what kept the JVM from testing it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub untested: Option<String>,
    /// The proof against the JDK's bytecode, for a proved contract.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proof: Option<Proof>,
    /// Why it is not proved: the call is not one a proof is about, or the checker gave no proof.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unproved: Option<String>,
    /// When its evidence is the contract library's record, not this run's check: `checked once, on JDK
    /// 25.0.4.1 by jvmcontract 0.1.0, and recorded in the contract library (checked.json)`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recorded: Option<String>,
}

/// A contract the engine cannot apply, or a JVM refutes, and why: its gap stays open.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Refused {
    pub id: String,
    /// Where it was written, as for [`Accepted::file`].
    pub file: String,
    pub line: usize,
    pub reason: String,
    /// The inputs on which the JVM refutes it, when it was tested.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub testing: Option<Testing>,
}

/// A contracts file, read and checked against the class path the proof runs on.
#[derive(Debug, Clone, Default)]
pub struct Loaded {
    pub accepted: Vec<Accepted>,
    pub refused: Vec<Refused>,
    /// By gap, how the engine applies its contract.
    pub closed: BTreeMap<Gap, Closure>,
    /// The class [`CLASS`], when a contract needs a method of it.
    pub class: Option<Vec<u8>>,
}

impl Loaded {
    /// The refusal of the contract for a gap, by its id.
    pub fn refusal(&self, id: &str) -> Option<&Refused> {
        self.refused.iter().find(|r| r.id == id)
    }
}

/// The gap an id names: `kind:owner.name(descriptor)[@jdk-version]`, with the version.
pub fn gap_of(id: &str) -> Option<(Gap, Option<String>)> {
    let (kind, rest) = id.split_once(':')?;
    let kind = GapKind::from_name(kind)?;
    let (member, version) = match rest.rsplit_once("@jdk-") {
        Some((m, v)) => (m, Some(v.to_string())),
        None => (rest, None),
    };
    let open = member.find('(')?;
    let (owner, name) = member[..open].rsplit_once('.')?;
    let descriptor = &member[open..];
    MethodDescriptor::parse(descriptor).ok()?;
    Some((Gap { kind, owner: owner.replace('.', "/"), name: name.to_string(), descriptor: descriptor.to_string() }, version))
}

/// A contract to check and apply: its block, where it was written, and the record of an earlier check of it, from
/// the contract library ([`crate::contract_library`]).
#[derive(Debug, Clone)]
pub struct Source {
    pub block: Block,
    pub file: String,
    pub record: Option<Record>,
    /// The id as written, when it named another JDK than the proof's and was moved to the proof's: the library's
    /// contract is checked again on this JDK.
    pub written_for: Option<String>,
}

/// What a check of a contract found, recorded so that a later run applies it with that evidence rather than
/// checking it again (the contract library's `checked.json`, [`crate::contract_library`]). It is about the
/// contract's text ([`digest`]) on one JDK, and a proof is about one class file of it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Record {
    /// The contract's id as written, for a reader.
    pub id: String,
    /// The [`digest`] of the contract the check was about.
    pub contract: String,
    /// The JDK it was checked on.
    pub jdk: String,
    /// The jvmcontract that checked it.
    pub by: String,
    pub evidence: Evidence,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub testing: Option<Testing>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub untested: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proof: Option<Proof>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub unproved: Option<String>,
}

impl Record {
    /// The record of a contract the check accepted, on the JDK `jdk`.
    pub fn of(accepted: &Accepted, block: &Block, jdk: &str) -> Record {
        Record {
            id: block.id.clone(),
            contract: digest(block),
            jdk: jdk.to_string(),
            by: format!("jvmcontract {}", env!("CARGO_PKG_VERSION")),
            evidence: accepted.evidence,
            testing: accepted.testing.clone(),
            untested: accepted.untested.clone(),
            proof: accepted.proof.clone(),
            unproved: accepted.unproved.clone(),
        }
    }

    /// Whether this records a check of `block` on the JDK `jdk` that still holds: the same contract, the same
    /// JDK, and for a proof the same class file in the JDK image of `cp`. Why not, otherwise.
    pub fn holds_for(&self, block: &Block, jdk: Option<&str>, cp: &ClassPath) -> Result<(), String> {
        if self.contract != digest(block) {
            return Err("the contract changed since its record was made".into());
        }
        if Some(self.jdk.as_str()) != jdk {
            return Err(format!("its record is for JDK {}, and the proof runs on {}", self.jdk, jdk.unwrap_or("an unknown JDK")));
        }
        if let Some(p) = &self.proof {
            let owner = p.class.replace('.', "/");
            let bytes = cp.jdk().and_then(|j| j.read_class(&owner).ok().flatten());
            if bytes.map(|b| format!("sha256:{}", crate::digest::sha256_hex(&b))).as_deref() != Some(p.digest.as_str()) {
                return Err(format!("the bytecode of {} it was proved against is not this JDK image's", p.class));
            }
        }
        Ok(())
    }

    /// In words, for the verdict: `checked once, on JDK 25.0.4.1 by jvmcontract 0.1.0, and recorded in the contract
    /// library`.
    pub fn words(&self) -> String {
        format!("checked once, on JDK {} by {}, and recorded in the contract library, not checked again by this run", self.jdk, self.by)
    }
}

/// A contract's digest, `sha256:...`, over its gap (the id without its JDK, which a record names apart) and its
/// keys in order: comments, blank lines and indentation don't change it.
pub fn digest(block: &Block) -> String {
    let gap = block.id.rsplit_once("@jdk-").map_or(block.id.as_str(), |(g, _)| g);
    let mut text = format!("{gap}\n");
    for (k, v, _) in &block.keys {
        text.push_str(&format!("{k}: {v}\n"));
    }
    format!("sha256:{}", crate::digest::sha256_hex(text.as_bytes()))
}

/// Reads the contracts in `file` and checks each, as [`load_sources`] does.
pub fn load(file: &Path, cp: &ClassPath, jdk: Option<&str>, entries: &[PathBuf], work: &Path) -> Result<Loaded, Error> {
    Ok(load_sources(read(file)?, cp, jdk, entries, work))
}

/// The contracts in `file`, as sources with no record.
pub fn read(file: &Path) -> Result<Vec<Source>, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("cannot read the contracts in {}: {e}", file.display())))?;
    let origin = file.display().to_string();
    Ok(parse(&text, &origin)?.into_iter().map(|block| Source { block, file: origin.clone(), record: None, written_for: None }).collect())
}

/// Checks each contract against the class path `cp` the proof runs on, under the JDK `jdk`: each is accepted, with
/// how the engine applies it, or refused with the reason. Each accepted contract is then checked, strongest first:
/// proved against the JDK's bytecode where it can be ([`crate::contract_proving`]), and tested on a real JVM
/// ([`crate::contract_testing`], in `work`, with `entries` on its class path). One the JVM refutes is refused, with
/// the inputs that refute it, and one it cannot test is trusted, with the reason. A contract whose source carries a
/// record that still holds ([`Record::holds_for`]) is not checked again: it has the record's evidence.
pub fn load_sources(sources: Vec<Source>, cp: &ClassPath, jdk: Option<&str>, entries: &[PathBuf], work: &Path) -> Loaded {
    let mut loaded = Loaded::default();
    let mut writer = ClassWriter::new(CLASS);
    writer.source_file = sources.first().and_then(|s| Path::new(&s.file).file_name()).map(|f| f.to_string_lossy().into_owned());
    // The contracts to check in this run, and those whose record stands, with it.
    let mut shapes = Vec::new();
    let mut checking = Vec::new();
    let mut recorded = Vec::new();
    let mut index = 0;
    for source in &sources {
        let block = &source.block;
        match accept(block, cp, jdk, index, &mut writer) {
            Ok((gap, closing, summary, shape)) => {
                // Its method is written, so the next one is named apart even when this one is refused.
                let this = index;
                index += 1;
                if loaded.closed.contains_key(&gap) {
                    loaded.refused.push(Refused { id: block.id.clone(), file: source.file.clone(), line: block.line, reason: "a second contract for the gap: the first one stands".into(), testing: None });
                    continue;
                }
                let written_by = block.value("written-by").unwrap_or_default().to_string();
                let contract = ContractUse { summary: summary.clone(), written_by: written_by.clone(), evidence: Evidence::Trusted, testing: None, untested: None, proof: None, unproved: None, recorded: None, file: source.file.clone(), line: block.line, index: this };
                loaded.closed.insert(gap, Closure { how: closing, contract });
                let accepted = Accepted { id: block.id.clone(), file: source.file.clone(), line: block.line, summary, written_by, evidence: Evidence::Trusted, testing: None, untested: None, proof: None, unproved: None, recorded: None };
                match source.record.as_ref().filter(|r| r.holds_for(block, jdk, cp).is_ok()) {
                    Some(r) => recorded.push((accepted, r.clone())),
                    None => {
                        checking.push(accepted);
                        shapes.push(shape);
                    }
                }
            }
            Err(reason) => loaded.refused.push(Refused { id: block.id.clone(), file: source.file.clone(), line: block.line, reason, testing: None }),
        }
    }
    if !writer.methods.is_empty() {
        loaded.class = Some(writer.to_bytes());
    }

    // Each accepted contract proved against the JDK's bytecode where it can be, then on a real JVM, with the
    // witness of a proof that refutes it among the JVM's inputs: only the JVM's run makes it a counterexample.
    let (proofs, tested) = if shapes.is_empty() {
        (Vec::new(), Vec::new())
    } else {
        let proofs = crate::contract_proving::prove(&shapes, cp, &work.join("contract-proofs"));
        let extra: Vec<Vec<Vec<crate::contract_testing::Value>>> = proofs.iter().map(|p| if let Proving::Refuted { input, .. } = p { vec![input.clone()] } else { Vec::new() }).collect();
        let tested = crate::contract_testing::test(&shapes, cp, entries, &work.join("contract-tests"), &extra);
        (proofs, tested)
    };
    let mut kept = Vec::new();
    for ((accepted, result), proving) in checking.into_iter().zip(tested).zip(proofs) {
        let gap = gap_of(&accepted.id).map(|(g, _)| g).expect("an accepted contract's id is a gap's");
        let refused = match (&result, &proving) {
            (Ok(testing), _) if testing.refuting > 0 => {
                let first = testing.counterexamples.first().map(Counterexample::line).unwrap_or_default();
                Some(format!("a JVM refutes it: {first} ({} of {} input{} refute it, on JDK {}, seed {})", testing.refuting, testing.inputs, if testing.inputs == 1 { "" } else { "s" }, testing.jdk, testing.seed))
            }
            (Err(why), Proving::Refuted { words, .. }) => Some(format!("the tool's own checker refutes it against the JDK's bytecode on {words}, which no JVM could confirm, since {why}")),
            _ => None,
        };
        if let Some(reason) = refused {
            loaded.closed.remove(&gap);
            loaded.refused.push(Refused { id: accepted.id, file: accepted.file, line: accepted.line, reason, testing: result.ok() });
            continue;
        }
        let (evidence, proof, unproved) = match proving {
            Proving::Proved(p) => (Evidence::Proved, Some(p), None),
            Proving::Refuted { words, .. } => (Evidence::Tested, None, Some(format!("the tool's own checker refutes it against the JDK's bytecode on {words}, where the JVM's call does as the contract says: a disagreement with the JVM, which is a bug in jvmcontract"))),
            Proving::Unproved(why) => (if result.is_ok() { Evidence::Tested } else { Evidence::Trusted }, None, Some(why)),
        };
        let (testing, untested) = match result {
            Ok(t) => (Some(t), None),
            Err(why) => (None, Some(why)),
        };
        kept.push(Accepted { evidence, testing, untested, proof, unproved, ..accepted });
    }
    for (accepted, r) in recorded {
        kept.push(Accepted { evidence: r.evidence, testing: r.testing.clone(), untested: r.untested.clone(), proof: r.proof.clone(), unproved: r.unproved.clone(), recorded: Some(r.words()), ..accepted });
    }
    for accepted in &kept {
        let gap = gap_of(&accepted.id).map(|(g, _)| g).expect("an accepted contract's id is a gap's");
        let closure = loaded.closed.get_mut(&gap).expect("an accepted contract closes its gap");
        closure.contract.evidence = accepted.evidence;
        closure.contract.testing = accepted.testing.clone();
        closure.contract.untested = accepted.untested.clone();
        closure.contract.proof = accepted.proof.clone();
        closure.contract.unproved = accepted.unproved.clone();
        closure.contract.recorded = accepted.recorded.clone();
    }
    kept.sort_by(|a, b| (&a.file, a.line).cmp(&(&b.file, b.line)));
    loaded.accepted = kept;
    loaded.refused.sort_by(|a, b| (&a.file, a.line).cmp(&(&b.file, b.line)));
    loaded
}

/// Why `--contracts` is refused under a gap mode other than advised.
pub const CONTRACTS_NEED_ADVISED: &str = "--contracts needs --gaps advised: under strict a gap is refused whatever its contract, and under assume it is approximated";

/// Where a proof driver takes the contracts for its gaps from, under `--gaps advised`.
#[derive(Debug, Clone)]
pub struct ContractOptions {
    /// The agent's file (`--contracts`), whose contract for a gap comes first, even when it is refused.
    pub file: Option<PathBuf>,
    /// Whether the contract library closes the gaps the file has no contract for (no `--no-contract-library`).
    pub library: bool,
    /// The most trusted contracts the proof may rest on (`--max-trust`); none means any number.
    pub max_trust: Option<usize>,
}

impl Default for ContractOptions {
    fn default() -> Self {
        ContractOptions { file: None, library: true, max_trust: None }
    }
}

/// The gap setting a proof driver runs the tool's own checker with: the mode, and under advised the contracts for
/// the gaps `scan` reached: the agent's, in `options.file`, then the contract library's for the gaps the file has
/// none for ([`crate::contract_library`]), read against the class path `entries` (with the tool's models when
/// `models`), with the class that applies them written into `work/contracts`. Under `--max-trust N`, when more than
/// N of the contracts for the gaps reached are trusted, every one of those is refused, so its gap goes back to the
/// agent. Returns the contracts as read, and a note line for each refused, and for each of the library's that this
/// run checks again.
pub fn setting(mode: gaps::GapMode, options: &ContractOptions, scan: Option<&gaps::Scan>, entries: &[PathBuf], models: bool, work: &Path) -> Result<(gaps::GapSetting, Option<Loaded>, String), Error> {
    crate::phases::timed(crate::phases::Step::Contracts, || setting_untimed(mode, options, scan, entries, models, work))
}

fn setting_untimed(mode: gaps::GapMode, options: &ContractOptions, scan: Option<&gaps::Scan>, entries: &[PathBuf], models: bool, work: &Path) -> Result<(gaps::GapSetting, Option<Loaded>, String), Error> {
    let mut setting = gaps::GapSetting::from(mode);
    if options.file.is_some() && mode != gaps::GapMode::Advised {
        return Err(Error::new(CONTRACTS_NEED_ADVISED));
    }
    if mode != gaps::GapMode::Advised {
        return Ok((setting, None, String::new()));
    }
    let jdk = gaps::jdk_release();
    let mut sources = match &options.file {
        Some(f) => read(f)?,
        None => Vec::new(),
    };
    if let (true, Some(scan)) = (options.library, scan) {
        let given: std::collections::BTreeSet<Gap> = sources.iter().filter_map(|s| gap_of(&s.block.id).map(|(g, _)| g)).collect();
        let reached: Vec<&Gap> = scan.gaps.keys().filter(|g| !given.contains(g)).collect();
        sources.extend(crate::contract_library::Library::embedded()?.sources(&reached, jdk.as_deref())?);
    }
    if sources.is_empty() {
        return Ok((setting, None, String::new()));
    }
    let cp = crate::witness::classpath(entries.iter().map(PathBuf::as_path))?.with_models(models);
    let mut notes = String::new();
    for s in sources.iter().filter(|s| s.file.starts_with(crate::contract_library::ORIGIN)) {
        let why = match &s.record {
            None => "it has no record of a check on this JDK".to_string(),
            Some(r) => match r.holds_for(&s.block, jdk.as_deref(), &cp) {
                Ok(()) => continue,
                Err(why) => why,
            },
        };
        let written = s.written_for.as_ref().map(|w| format!(", written as {w}")).unwrap_or_default();
        notes.push_str(&format!("note: the contract library's contract for {} ({}:{}{written}) is checked by this run, since {why}: `jvmcontract gap-contracts --record` keeps its evidence\n", s.block.id, s.file, s.block.line));
    }
    let mut loaded = load_sources(sources, &cp, jdk.as_deref(), entries, work);
    if let Some(n) = options.max_trust {
        limit_trust(&mut loaded, n, scan);
    }
    if let Some(bytes) = &loaded.class {
        let dir = work.join("contracts");
        std::fs::create_dir_all(&dir)?;
        std::fs::write(dir.join(format!("{CLASS}.class")), bytes)?;
        setting.class_dir = Some(dir);
    }
    setting.contracts = std::sync::Arc::new(loaded.closed.clone());
    for r in &loaded.refused {
        notes.push_str(&format!("note: the contract for {} ({}:{}) is refused, and its gap stays open: {}\n", r.id, r.file, r.line, r.reason));
    }
    Ok((setting, Some(loaded), notes))
}

/// Refuses every trusted contract for a gap `scan` reached (every gap, without one) when there are more than `n`:
/// a run under `--max-trust n` rests on at most `n` contracts nothing has checked, and their gaps go back to the
/// agent, who can give a contract the JVM can test.
fn limit_trust(loaded: &mut Loaded, n: usize, scan: Option<&gaps::Scan>) {
    let reached = |id: &str| gap_of(id).is_some_and(|(g, _)| scan.is_none_or(|s| s.gaps.contains_key(&g)));
    let trusted: Vec<usize> = loaded.accepted.iter().enumerate().filter(|(_, a)| a.evidence == Evidence::Trusted && reached(&a.id)).map(|(i, _)| i).collect();
    if trusted.len() <= n {
        return;
    }
    let allows = if n == 0 { "none".to_string() } else { format!("at most {n}") };
    let count = trusted.len();
    for i in trusted.into_iter().rev() {
        let a = loaded.accepted.remove(i);
        if let Some((gap, _)) = gap_of(&a.id) {
            loaded.closed.remove(&gap);
        }
        let why = a.untested.as_deref().map(|w| format!(", since {w}")).unwrap_or_default();
        let reason = format!("it is trusted: nothing has checked it{why}; the proof would rest on {count} trusted contract{}, and --max-trust {n} allows {allows}", if count == 1 { "" } else { "s" });
        loaded.refused.push(Refused { id: a.id, file: a.file, line: a.line, reason, testing: None });
    }
    loaded.refused.sort_by(|a, b| (&a.file, a.line).cmp(&(&b.file, b.line)));
}

/// The words for a reference result's forms, in a refusal.
const RESULT_FORMS: &str = "`result == this`, `result == <parameter>`, `result == null`, or `\\fresh(result)` for a new object";

/// Checks one block, and writes the method that applies it into `writer`; the reason it is refused otherwise.
fn accept(block: &Block, cp: &ClassPath, jdk: Option<&str>, index: usize, writer: &mut ClassWriter) -> Result<(Gap, Closing, String, Shape), String> {
    for (key, value, _) in &block.keys {
        if !KEYS.contains(&key.as_str()) {
            return Err(format!("unknown key `{key}:`; a contract has {}", KEYS.iter().map(|k| format!("`{k}:`")).collect::<Vec<_>>().join(", ")));
        }
        if value.contains("TODO") {
            return Err(format!("`{key}:` still says TODO"));
        }
        if value.is_empty() {
            return Err(format!("`{key}:` is empty"));
        }
        if key != "throws" && block.values(key).len() > 1 {
            return Err(format!("`{key}:` is given more than once; only `throws:` may be repeated"));
        }
    }
    let (gap, version) = gap_of(&block.id).ok_or_else(|| format!("{:?} is not a gap's id: `kind:owner.name(descriptor)`, with `@jdk-<version>` for a JDK call, as the template has it", block.id))?;
    if gap.kind.of_the_jdk() {
        match (version.as_deref(), jdk) {
            (None, _) => return Err("a contract for a JDK call names the JDK it is about (`@jdk-<version>` in its id), since another JDK's method may behave otherwise".into()),
            (Some(v), Some(here)) if v != here => return Err(format!("it is about JDK {v}, and the proof runs on JDK {here}: a contract is about one JDK's method, and is checked again for another")),
            _ => {}
        }
    }
    let call = block.value("call").ok_or("no `call:` line, which names the call and its parameters")?;
    let modifies = block.value("modifies").ok_or("no `modifies:` line: a contract states what the call changes (`nothing`, `this`, or a parameter)")?;
    block.value("written-by").ok_or("no `written-by:` line: a contract says who wrote it, an agent or a person")?;
    let descriptor = MethodDescriptor::parse(&gap.descriptor).map_err(|e| e.to_string())?;
    let names = call_names(call, &gap, &descriptor)?;
    match gap.kind {
        GapKind::StringConversion => return Err("the tool's own checker applies no contract inside a string concatenation yet".into()),
        GapKind::ClassInitializer => {
            let (gap, closing, summary) = initializer(block, gap, modifies)?;
            let shape = Shape::initializer(&gap);
            return Ok((gap, closing, summary, shape));
        }
        _ => {}
    }
    let static_call = gap.kind == GapKind::JdkStaticMethod;
    let classified = if static_call { gaps::jdk_static_call(&gap.owner, &gap.name, &gap.descriptor) } else { gaps::jdk_instance_call(cp, &gap.owner, &gap.name, &gap.descriptor) };
    match classified {
        JdkCall::Gap(kind) if kind == gap.kind => {}
        JdkCall::Gap(kind) => return Err(format!("the call is a gap of kind {}, not {}", kind.name(), gap.kind.name())),
        JdkCall::Exact => return Err("the tool's own checker reproduces the call exactly: it is no gap".into()),
        JdkCall::Refused => return Err("the tool's own checker refuses the call whatever a contract says (floating point, or an array result)".into()),
    }
    if static_call && cp.model(&gap.owner).is_some() && cp.bytecode_method(&gap.owner, &gap.name, &gap.descriptor).is_some_and(|(_, m)| m.code.is_some()) {
        return Err("the tool's models run the call's own bytecode: it is no gap".into());
    }

    // The method's locals: the receiver (for an instance method, which may return it), the parameters, and a
    // primitive result.
    let receiver = !matches!(gap.kind, GapKind::JdkConstructor | GapKind::JdkStaticMethod);
    let mut slot: u16 = u16::from(receiver);
    let mut params = Vec::new();
    for (name, t) in names.iter().zip(&descriptor.params) {
        if expr::ty_of(t).is_some() || expr::element_ty(t).is_some() {
            params.push(Param { name: name.clone(), ty: t.clone(), slot });
        }
        slot += t.slots();
    }
    let primitive = expr::ty_of(&descriptor.ret).map(|_| descriptor.ret.clone());
    let result_slot = primitive.as_ref().map(|_| slot);
    if let Some(t) = &primitive {
        slot += t.slots();
    }
    let first_free = slot;
    let mut after_params = params.clone();
    if let (Some(t), Some(s)) = (&primitive, result_slot) {
        after_params.push(Param { name: "result".into(), ty: t.clone(), slot: s });
    }
    let parse = |text: &str, what: &str, params: &[Param]| -> Result<expr::Expr, String> {
        if mentions_word(text, "this") {
            return Err(format!("{what} names `this`: the tool's own checker keeps no state of a JDK object, so a condition cannot read it"));
        }
        if text.contains("\\old") {
            return Err(format!("{what} uses \\old, which the tool's own checker does not apply yet: state what holds after the call alone"));
        }
        expr::parse_in(text, params, None, first_free).map_err(|e| {
            let other = names.iter().zip(&descriptor.params).find(|(n, t)| mentions_word(text, n) && !params.iter().any(|p| &p.name == *n) && !t.is_primitive());
            match other {
                Some((n, t)) => format!("{what} names {n}, a {}: a condition reads parameters of a primitive type and arrays of them", t.java_name()),
                None if mentions_word(text, "result") && !params.iter().any(|p| p.name == "result") => format!("{what} names `result`, which only `assert:` reads, after the call"),
                None => format!("{what}: {e}"),
            }
        })
    };
    let condition = |text: &str, what: &str| parse(text, what, &params);
    let assume = match block.value("assume") {
        Some(a) if a != "true" => Some(condition(a, "`assume:`")?),
        _ => None,
    };
    let mut throws = Vec::new();
    for clause in block.values("throws") {
        if clause == "nothing" {
            continue;
        }
        let (class, when) = clause.split_once(" when ").ok_or_else(|| format!("`throws: {clause}` is not `<exception> when <condition>`"))?;
        let class = exception_class(cp, class.trim())?;
        throws.push((class, condition(when.trim(), &format!("`throws: {clause}`"))?));
    }
    let modified = modified(modifies, &names, &descriptor.params, u16::from(receiver))?;
    let assert = block.value("assert").filter(|a| *a != "true");
    let result = match (&descriptor.ret, assert) {
        (Type::Object(_) | Type::Array(_), None) => return Err(format!("no `assert:` on the result: a contract for a call that returns an object says which object, {RESULT_FORMS}")),
        (Type::Object(_) | Type::Array(_), Some(a)) => Some(result_form(a, &names, &descriptor)?),
        (Type::Void, _) => None,
        (_, _) if primitive.is_some() => None,
        (t, _) => return Err(format!("the call returns {}, which the tool's own checker does not take from a contract", t.java_name())),
    };
    let after = match (&result, assert) {
        (None, Some(a)) => Some(parse(a, "`assert:`", &after_params)?),
        _ => None,
    };

    // The method.
    let mut code = CodeBuilder::new();
    let ret_kind = match &primitive {
        Some(Type::Long) => Some(Kind::Long),
        Some(_) => Some(Kind::Int),
        None if result.is_some() => Some(Kind::Ref),
        None => None,
    };
    let give_up = |code: &mut CodeBuilder| {
        match ret_kind {
            Some(Kind::Ref) => code.op(0x01),  // aconst_null
            Some(Kind::Long) => code.op(0x09), // lconst_0
            Some(_) => code.iconst(0),
            None => {}
        }
        code.return_(ret_kind);
    };
    let mut slots_used = first_free;
    // A contract is about arrays that are there, which is what testing it gives it: a null array meets the gap.
    for p in params.iter().filter(|p| matches!(p.ty, Type::Array(_))) {
        let there = code.label();
        code.load(Kind::Ref, p.slot);
        code.if_nonnull(there);
        code.iconst(index as i32);
        let open = writer.pool.method_ref(INTRINSICS, "open", "(I)V");
        code.op_u16(0xb8, open);
        give_up(&mut code);
        code.bind(there);
    }
    if let Some(a) = &assume {
        let proceed = code.label();
        expr::emit(a, &mut code, &mut writer.pool);
        code.if_zero(Cond::Ne, proceed);
        code.iconst(index as i32);
        let open = writer.pool.method_ref(INTRINSICS, "open", "(I)V");
        code.op_u16(0xb8, open);
        give_up(&mut code);
        code.bind(proceed);
        slots_used = slots_used.max(a.slots_used());
    }
    for (class, when) in &throws {
        let next = code.label();
        expr::emit(when, &mut code, &mut writer.pool);
        code.if_zero(Cond::Eq, next);
        let c = writer.pool.class(class);
        code.op_u16(0xbb, c); // new
        code.op(0x59); // dup
        let init = writer.pool.method_ref(class, "<init>", "()V");
        code.op_u16(0xb7, init);
        code.op(0xbf); // athrow
        code.bind(next);
        slots_used = slots_used.max(when.slots_used());
    }
    for p in &modified {
        code.load(Kind::Ref, p.slot);
        let havoc = writer.pool.method_ref(INTRINSICS, "havoc", "(Ljava/lang/Object;)V");
        code.op_u16(0xb8, havoc);
    }
    // A primitive result: any value of its type, which the assertion below constrains.
    if let (Some(t), Some(s), Some(kind)) = (&primitive, result_slot, ret_kind) {
        let any = if *t == Type::Long { writer.pool.method_ref(INTRINSICS, "anyLong", "()J") } else { writer.pool.method_ref(INTRINSICS, "anyInt", "()I") };
        code.op_u16(0xb8, any);
        match t {
            Type::Boolean => {
                code.iconst(1);
                code.op(0x7e); // iand
            }
            Type::Byte => code.op(0x91),  // i2b
            Type::Char => code.op(0x92),  // i2c
            Type::Short => code.op(0x93), // i2s
            _ => {}
        }
        code.store(kind, s);
    }
    if let Some(a) = &after {
        let holds = code.label();
        expr::emit(a, &mut code, &mut writer.pool);
        code.if_zero(Cond::Ne, holds);
        let infeasible = writer.pool.method_ref(INTRINSICS, "infeasible", "()V");
        code.op_u16(0xb8, infeasible);
        give_up(&mut code);
        code.bind(holds);
        slots_used = slots_used.max(a.slots_used());
    }
    match &result {
        Some(ResultForm::This) => code.load(Kind::Ref, 0),
        Some(ResultForm::Parameter(slot)) => code.load(Kind::Ref, *slot),
        Some(ResultForm::Null) => code.op(0x01),
        Some(ResultForm::Fresh) => {
            let class = match &descriptor.ret {
                Type::Object(name) => name.clone(),
                other => other.descriptor(),
            };
            let c = writer.pool.class(&class);
            code.op_u16(0xbb, c);
        }
        None => {
            if let (Some(s), Some(kind)) = (result_slot, ret_kind) {
                code.load(kind, s);
            }
        }
    }
    code.return_(ret_kind);
    code.max_locals = slots_used.max(first_free) + 4;
    code.max_stack = 16;
    let method = format!("c{index}");
    let method_descriptor = format!("({}{}){}", if receiver { "Ljava/lang/Object;" } else { "" }, descriptor.params.iter().map(Type::descriptor).collect::<String>(), descriptor.ret.descriptor());
    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: method.clone(), descriptor: method_descriptor.clone(), code: Some(code) });

    let mut summary = Vec::new();
    if let Some(a) = block.value("assume").filter(|a| *a != "true") {
        summary.push(format!("on {a}"));
    }
    for (class, when) in block.values("throws").iter().filter(|c| **c != "nothing").filter_map(|c| c.split_once(" when ")).zip(&throws).map(|((_, when), (class, _))| (class, when)) {
        summary.push(format!("throws {} when {}", class.replace('/', "."), when.trim()));
    }
    if throws.is_empty() {
        summary.push("throws nothing".into());
    }
    if let Some(a) = assert {
        summary.push(format!("then {a}"));
    }
    summary.push(format!("modifies {modifies}"));
    let throws_text = block.values("throws").into_iter().filter(|c| *c != "nothing").map(str::to_string).collect();
    let shape = Shape { gap: gap.clone(), descriptor, names, receiver, assume, throws, throws_text, modified, after, assert: assert.map(str::to_string), result, result_slot, first_free, slots_used };
    Ok((gap, Closing::Stub { method, descriptor: method_descriptor, receiver }, summary.join("; "), shape))
}

/// What an initializer's contract may be: it throws nothing and sets nothing the proof reads, so the class is
/// taken to be initialized, as the JVM leaves it.
fn initializer(block: &Block, gap: Gap, modifies: &str) -> Result<(Gap, Closing, String), String> {
    if block.values("throws").iter().any(|t| *t != "nothing") {
        return Err("the tool's own checker applies an initializer's contract only when it throws nothing; JBMC runs initializers (--engine auto under --gaps strict)".into());
    }
    if modifies != "nothing" {
        return Err("the tool's own checker reads only a static field that is a constant, so an initializer's contract modifies nothing".into());
    }
    if block.value("assert").is_some_and(|a| a != "true") {
        return Err("an initializer's contract that modifies nothing has nothing to assert".into());
    }
    if block.value("assume").is_some_and(|a| a != "true") {
        return Err("an initializer takes no arguments, so its contract assumes nothing".into());
    }
    Ok((gap, Closing::Initialised, "throws nothing; modifies nothing".into()))
}

/// The parameter names the `call:` line gives, checked against the id: the same owner, name and parameter types,
/// and the result type if it states one.
fn call_names(call: &str, gap: &Gap, descriptor: &MethodDescriptor) -> Result<Vec<String>, String> {
    let (head, ret) = match call.split_once("->") {
        Some((h, r)) => (h.trim(), Some(r.trim())),
        None => (call.trim(), None),
    };
    let open = head.find('(').ok_or_else(|| format!("`call: {call}` is not `owner.name(type name, ...)`"))?;
    let close = head.rfind(')').filter(|&c| c > open).ok_or_else(|| format!("`call: {call}` is not `owner.name(type name, ...)`"))?;
    let member = format!("{}.{}", gap.owner.replace('/', "."), gap.name);
    if head[..open].trim() != member {
        return Err(format!("`call:` names {}, and the id {member}", head[..open].trim()));
    }
    let inner = head[open + 1..close].trim();
    let parts: Vec<&str> = if inner.is_empty() { Vec::new() } else { inner.split(',').map(str::trim).collect() };
    if parts.len() != descriptor.params.len() {
        return Err(format!("`call:` has {} parameters, and the call {}", parts.len(), descriptor.params.len()));
    }
    let mut names = Vec::new();
    for (i, (part, t)) in parts.iter().zip(&descriptor.params).enumerate() {
        let (ty, name) = part.rsplit_once(char::is_whitespace).ok_or_else(|| format!("parameter {} of `call:` is `type name`, found {part:?}", i + 1))?;
        if ty.trim() != t.java_name() {
            return Err(format!("parameter {} of `call:` is a {}, and the call's a {}", i + 1, ty.trim(), t.java_name()));
        }
        let name = name.trim();
        if name == "this" || name == "result" || !name.chars().all(|c| c.is_alphanumeric() || c == '_') {
            return Err(format!("{name:?} cannot name a parameter"));
        }
        if names.iter().any(|n| n == name) {
            return Err(format!("two parameters are named {name}"));
        }
        names.push(name.to_string());
    }
    if let Some(r) = ret {
        if r != descriptor.ret.java_name() {
            return Err(format!("`call:` returns {r}, and the call {}", descriptor.ret.java_name()));
        }
    }
    Ok(names)
}

/// What `modifies:` names: `nothing`, `this`, and parameters that are arrays of primitives, whose elements the
/// engine replaces.
fn modified(text: &str, names: &[String], types: &[Type], first: u16) -> Result<Vec<Param>, String> {
    if text == "nothing" {
        return Ok(Vec::new());
    }
    let mut out = Vec::new();
    let mut slot = first;
    let slots: Vec<u16> = types
        .iter()
        .map(|t| {
            let s = slot;
            slot += t.slots();
            s
        })
        .collect();
    for part in text.split(',').map(str::trim) {
        if part == "this" {
            continue;
        }
        let i = names.iter().position(|n| n == part).ok_or_else(|| format!("`modifies:` names {part:?}, which is not `nothing`, `this` or a parameter"))?;
        if expr::element_ty(&types[i]).is_none() {
            return Err(format!("`modifies:` names {part}, a {}: the tool's own checker changes only an array of primitives", types[i].java_name()));
        }
        out.push(Param { name: part.to_string(), ty: types[i].clone(), slot: slots[i] });
    }
    Ok(out)
}

/// Which object a call that returns one returns.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ResultForm {
    This,
    /// The parameter in this slot of the contract's method.
    Parameter(u16),
    Null,
    Fresh,
}

fn result_form(text: &str, names: &[String], descriptor: &MethodDescriptor) -> Result<ResultForm, String> {
    let compact: String = text.chars().filter(|c| !c.is_whitespace()).collect();
    if compact == "\\fresh(result)" {
        return Ok(ResultForm::Fresh);
    }
    let Some(other) = compact.strip_prefix("result==") else {
        return Err(format!("`assert: {text}` is not a form the tool's own checker can choose the result by: {RESULT_FORMS}{}", if compact == "result!=null" { " (`result != null` alone does not say which object)" } else { "" }));
    };
    match other {
        "this" => Ok(ResultForm::This),
        "null" => Ok(ResultForm::Null),
        name => {
            let mut slot: u16 = 1;
            for (n, t) in names.iter().zip(&descriptor.params) {
                if n == name {
                    return match t {
                        Type::Object(_) | Type::Array(_) => Ok(ResultForm::Parameter(slot)),
                        _ => Err(format!("`assert: {text}`: {name} is a {}, not an object", t.java_name())),
                    };
                }
                slot += t.slots();
            }
            Err(format!("`assert: {text}`: {name} is not a parameter; the forms are {RESULT_FORMS}"))
        }
    }
}

/// The exception class a throws clause names: in full, or by its simple name in `java.lang`; a Throwable with a
/// constructor of no arguments, which the contract's method calls.
fn exception_class(cp: &ClassPath, name: &str) -> Result<String, String> {
    let internal = if name.contains('.') { name.replace('.', "/") } else { format!("java/lang/{name}") };
    if !cp.exists(&internal) {
        return Err(format!("no class {name}{}", if name.contains('.') { "" } else { " in java.lang (name another package's class in full)" }));
    }
    if !cp.is_subtype(&internal, "java/lang/Throwable") {
        return Err(format!("{name} is not a Throwable"));
    }
    let constructed = if crate::classpath::is_jdk_name(&internal) { gaps::exact_jdk_call(cp, &internal, "<init>", "()V") } else { cp.bytecode_method(&internal, "<init>", "()V").is_some() };
    if !constructed {
        return Err(format!("{name} has no constructor of no arguments, which the contract's exception is built with"));
    }
    Ok(internal)
}

/// Whether `text` has `word` as a whole word.
fn mentions_word(text: &str, word: &str) -> bool {
    let ident = |c: char| c.is_alphanumeric() || c == '_' || c == '$';
    text.match_indices(word).any(|(i, _)| !text[..i].chars().next_back().is_some_and(ident) && !text[i + word.len()..].chars().next().is_some_and(ident))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn block(text: &str) -> Block {
        parse(&format!("kind: gap-contracts\n{text}"), "t").unwrap().remove(0)
    }

    fn refusal(text: &str) -> String {
        let cp = ClassPath::new().with_default_jdk();
        let mut writer = ClassWriter::new(CLASS);
        accept(&block(text), &cp, Some("25"), 0, &mut writer).map(|_| ()).unwrap_err()
    }

    #[test]
    fn a_file_is_read_by_blocks_and_its_structure_checked() {
        let blocks = parse("# a comment\nkind: gap-contracts\n\njdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25  # after the id\n  call: java.util.ArrayList.<init>(int n)\n  throws: IllegalArgumentException when n < 0\n  throws: java.lang.OutOfMemoryError when n > 1000000\n", "f").unwrap();
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].id, "jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25");
        assert_eq!(blocks[0].line, 4);
        assert_eq!(blocks[0].values("throws").len(), 2);
        assert!(parse("call: x\n", "f").unwrap_err().to_string().contains("starts with `kind: gap-contracts`"));
        assert!(parse("kind: gap-contracts\n  call: x\n", "f").unwrap_err().to_string().contains("f:2: a key before any contract's id"));
        assert!(parse("kind: gap-contracts\nan id with spaces\n", "f").unwrap_err().to_string().contains("alone on its line"));
        let (gap, version) = gap_of("jdk-reference-method:java.lang.StringBuilder.append(I)Ljava/lang/StringBuilder;@jdk-25.0.4.1").unwrap();
        assert_eq!((gap.owner.as_str(), gap.name.as_str(), gap.descriptor.as_str(), version.as_deref()), ("java/lang/StringBuilder", "append", "(I)Ljava/lang/StringBuilder;", Some("25.0.4.1")));
        assert_eq!(gap_of("class-initializer:p.Boom.<clinit>()V").unwrap().0.owner, "p/Boom");
        assert!(gap_of("jdk-constructor:ArrayList").is_none());
    }

    #[test]
    fn a_contract_the_engine_cannot_apply_is_refused_with_the_reason() {
        let head = "jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25\n";
        let ok = "  call: java.util.ArrayList.<init>(int n)\n  modifies: nothing\n  written-by: a test\n";
        let cp = ClassPath::new().with_default_jdk();
        let mut writer = ClassWriter::new(CLASS);
        let (_, closing, summary, _) = accept(&block(&format!("{head}{ok}  throws: IllegalArgumentException when n < 0\n")), &cp, Some("25"), 0, &mut writer).unwrap();
        assert_eq!(summary, "throws java.lang.IllegalArgumentException when n < 0; modifies nothing");
        assert!(matches!(closing, Closing::Stub { receiver: false, .. }));

        assert!(refusal(&format!("{head}{ok}  throws: TODO when TODO\n")).contains("`throws:` still says TODO"));
        assert!(refusal(&format!("{head}{ok}  ensures: true\n")).contains("unknown key `ensures:`"));
        assert!(refusal(&format!("jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-21\n{ok}")).contains("about JDK 21, and the proof runs on JDK 25"));
        assert!(refusal(&format!("jdk-constructor:java.util.ArrayList.<init>(I)V\n{ok}")).contains("names the JDK it is about"));
        assert!(refusal(&format!("{head}  call: java.util.ArrayList.<init>(long n)\n  modifies: nothing\n  written-by: a test\n")).contains("is a long, and the call's a int"));
        assert!(refusal(&format!("{head}  call: java.util.ArrayList.<init>(int n)\n  written-by: a test\n")).contains("no `modifies:` line"));
        assert!(refusal(&format!("{head}{ok}  assume: this != null\n")).contains("names `this`"));
        assert!(refusal(&format!("{head}{ok}  throws: IllegalArgumentException when m < 0\n")).contains("`throws: IllegalArgumentException when m < 0`"));
        assert!(refusal(&format!("{head}{ok}  throws: NoSuchThing when n < 0\n")).contains("no class NoSuchThing in java.lang"));
        assert!(refusal(&format!("{head}{ok}  throws: java.lang.String when n < 0\n")).contains("is not a Throwable"));
        assert!(refusal(&format!("{head}  call: java.util.ArrayList.<init>(int n)\n  modifies: n\n  written-by: a test\n")).contains("changes only an array of primitives"));
        assert!(refusal("jdk-constructor:java.util.ArrayList.<init>(Ljava/util/Collection;)V@jdk-25\n  call: java.util.ArrayList.<init>(java.util.Collection c)\n  modifies: nothing\n  written-by: a test\n  assume: c.size() > 0\n").contains("names c, a java.util.Collection"));
        assert!(refusal("jdk-constructor:java.lang.Object.<init>()V@jdk-25\n  call: java.lang.Object.<init>()\n  modifies: nothing\n  written-by: a test\n").contains("reproduces the call exactly"));

        let append = "jdk-reference-method:java.lang.StringBuilder.append(I)Ljava/lang/StringBuilder;@jdk-25\n  call: java.lang.StringBuilder.append(int i) -> java.lang.StringBuilder\n  modifies: this\n  written-by: a test\n";
        assert!(refusal(append).contains("says which object"));
        assert!(refusal(&format!("{append}  assert: result != null\n")).contains("does not say which object"));
        assert!(refusal(&format!("{append}  assert: result == i\n")).contains("i is a int, not an object"));
        let mut writer = ClassWriter::new(CLASS);
        let (_, closing, _, _) = accept(&block(&format!("{append}  assert: result == this\n")), &cp, Some("25"), 3, &mut writer).unwrap();
        assert!(matches!(&closing, Closing::Stub { method, descriptor, receiver: true } if method == "c3" && descriptor == "(Ljava/lang/Object;I)Ljava/lang/StringBuilder;"), "{closing:?}");

        let clinit = "class-initializer:p.Boom.<clinit>()V\n  call: p.Boom.<clinit>()\n  written-by: a test\n";
        let mut writer = ClassWriter::new(CLASS);
        assert!(matches!(accept(&block(&format!("{clinit}  modifies: nothing\n")), &cp, Some("25"), 0, &mut writer).unwrap().1, Closing::Initialised));
        assert!(refusal(&format!("{clinit}  modifies: nothing\n  throws: IllegalStateException when true\n")).contains("only when it throws nothing"));
        assert!(refusal(&format!("{clinit}  modifies: p.Boom.state\n")).contains("modifies nothing"));
        assert!(refusal("string-conversion:p.Item.toString()Ljava/lang/String;\n  call: p.Item.toString()\n  modifies: nothing\n  written-by: a test\n").contains("string concatenation"));

        // A primitive result is stated by `assert:` over `result`, which no other condition reads; a static call
        // has no receiver.
        let ntz = "jdk-static-method:java.lang.Integer.numberOfTrailingZeros(I)I@jdk-25\n  call: java.lang.Integer.numberOfTrailingZeros(int i) -> int\n  modifies: nothing\n  written-by: a test\n";
        let mut writer = ClassWriter::new(CLASS);
        let (_, closing, summary, shape) = accept(&block(&format!("{ntz}  assert: 0 <= result && result <= 32\n")), &cp, Some("25"), 1, &mut writer).unwrap();
        assert!(matches!(&closing, Closing::Stub { method, descriptor, receiver: false } if method == "c1" && descriptor == "(I)I"), "{closing:?}");
        assert_eq!(summary, "throws nothing; then 0 <= result && result <= 32; modifies nothing");
        assert_eq!((shape.result_slot, shape.first_free), (Some(1), 2));
        assert!(refusal(&format!("{ntz}  throws: IllegalArgumentException when result < 0\n")).contains("names `result`, which only `assert:` reads"));
        assert!(refusal("jdk-static-method:java.lang.Math.addExact(II)I@jdk-25\n  call: java.lang.Math.addExact(int a, int b) -> int\n  modifies: nothing\n  written-by: a test\n").contains("reproduces the call exactly"));
        assert!(refusal("jdk-static-method:java.lang.Integer.numberOfLeadingZeros(I)I@jdk-25\n  call: java.lang.Integer.numberOfLeadingZeros(int i) -> int\n  modifies: nothing\n  written-by: a test\n").contains("reproduces the call exactly"));
        assert!(refusal("jdk-static-method:java.lang.Integer.numberOfTrailingZeros(I)I\n  call: java.lang.Integer.numberOfTrailingZeros(int i)\n  modifies: nothing\n  written-by: a test\n").contains("names the JDK it is about"));
        let next = "jdk-primitive-method:java.util.Random.nextInt(I)I@jdk-25\n  call: java.util.Random.nextInt(int bound) -> int\n  throws: IllegalArgumentException when bound <= 0\n  assert: 0 <= result && result < bound\n  modifies: this\n  written-by: a test\n";
        let mut writer = ClassWriter::new(CLASS);
        let (_, closing, _, shape) = accept(&block(next), &cp, Some("25"), 0, &mut writer).unwrap();
        assert!(matches!(&closing, Closing::Stub { descriptor, receiver: true, .. } if descriptor == "(Ljava/lang/Object;I)I"), "{closing:?}");
        assert_eq!(shape.result_slot, Some(2), "after the receiver and the bound");
    }
}

#[cfg(test)]
mod proving_tests {
    use super::*;
    use crate::contract_proving::{prove, Proving};

    /// The shapes of contracts as `accept` makes them, for the proof alone (no JVM runs here).
    fn proofs(blocks: &[&str]) -> Vec<Proving> {
        let cp = ClassPath::new().with_default_jdk();
        if !cp.has_jdk() {
            return Vec::new();
        }
        let mut writer = ClassWriter::new(CLASS);
        let shapes: Vec<Shape> = blocks.iter().enumerate().map(|(i, b)| accept(&parse(&format!("kind: gap-contracts\n{b}"), "t").unwrap().remove(0), &cp, Some("25"), i, &mut writer).unwrap().3).collect();
        let dir = std::env::temp_dir().join(format!("jvmcontract-proving-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let out = prove(&shapes, &cp, &dir);
        let _ = std::fs::remove_dir_all(&dir);
        out
    }

    #[test]
    fn a_contract_is_proved_against_the_jdk_bytecode_with_the_exception_class_exact() {
        let divide = |throws: &str| format!("jdk-static-method:java.lang.Integer.divideUnsigned(II)I@jdk-25\n  call: java.lang.Integer.divideUnsigned(int a, int b) -> int\n  throws: {throws} when b == 0\n  assert: b != 1 || result == a\n  modifies: nothing\n  written-by: a test\n");
        let ntz = |assert: &str| format!("jdk-static-method:java.lang.Integer.numberOfTrailingZeros(I)I@jdk-25\n  call: java.lang.Integer.numberOfTrailingZeros(int i) -> int\n  assert: {assert}\n  modifies: nothing\n  written-by: a test\n");
        let random = "jdk-primitive-method:java.util.Random.nextInt(I)I@jdk-25\n  call: java.util.Random.nextInt(int bound) -> int\n  modifies: this\n  written-by: a test\n";
        let out = proofs(&[&divide("ArithmeticException"), &divide("RuntimeException"), &ntz("i <= 0 || result == 31 - (31 - result)"), &ntz("result != 7"), random]);
        if out.is_empty() {
            return; // no JDK
        }
        assert!(matches!(&out[0], Proving::Proved(p) if p.class == "java.lang.Integer" && p.digest.starts_with("sha256:")), "{:?}", out[0]);
        // The JDK throws an ArithmeticException, a RuntimeException but not of that class.
        assert!(matches!(&out[1], Proving::Refuted { words, .. } if words.ends_with("b=0")), "{:?}", out[1]);
        assert!(matches!(&out[2], Proving::Proved(_)), "{:?}", out[2]);
        // 7 trailing zeros: any i whose lowest byte is 0x80.
        let Proving::Refuted { input, .. } = &out[3] else { panic!("{:?}", out[3]) };
        let crate::contract_testing::Value::Int(i) = input[0] else { panic!() };
        assert_eq!(i & 0xff, 0x80, "{i}");
        assert!(matches!(&out[4], Proving::Unproved(why) if why.contains("only a static method's contract")), "{:?}", out[4]);
    }
}
