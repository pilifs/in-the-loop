//! Proving a contract for a gap against the JDK's own bytecode (step 3c of `llm-dlc/loops/sound-verdicts.md`): the
//! strongest evidence a contract ([`crate::gap_contracts`]) can have. Where the JDK method is in the tool's own
//! checker's fragment, the checker runs it, as the JDK image has it, on every input the contract is about, and
//! checks the contract as the JVM test checks it ([`crate::contract_testing`]): inside `assume:`, the first throws
//! clause that holds before the call decides, and the method must throw exactly that class; where none holds, it
//! must return, with `assert:` holding of its result.
//!
//! A class, `GapContractProofs`, is generated with a method `p<i>` per contract, the statement for contract `i`
//! over its parameters, and run by the tool's own checker under `--gaps strict` with the JDK method's class taken
//! from the JDK image onto the class path as bytecode to run. Anything the method reaches that the checker does not
//! implement (a gap, a static field that is not a constant, a loop past the unwinding bound) leaves the contract
//! unproved, with the reason, and its JVM test stands. No contract is applied inside a proof.
//!
//! What a proof is about:
//! - **The JDK's bytecode, not the JVM's code for it.** HotSpot replaces some of these methods with intrinsics
//!   (`Integer.numberOfLeadingZeros` is one); an intrinsic computes what the bytecode does, by the JVM's own
//!   contract, and the JVM test runs the intrinsic.
//! - **The JDK's classes initialized already**, as the tool's own checker takes them in every proof.
//! - **Static methods whose parameters are primitives.** An instance method's receiver has state the checker does
//!   not keep, and a proof over arrays covers them up to a bound, where the call the contract is applied at may be
//!   given a longer one.
//!
//! A proof that refutes the contract gives an input, which goes to the JVM test with the others: only the JVM's run
//! of the JDK's call makes it a counterexample. A witness the JVM does not reproduce is a disagreement with the
//! JVM, a bug in jvmcontract, and leaves the contract tested and unproved, with the witness.

use std::path::Path;
use std::time::Duration;

use crate::bmc::gaps::GapKind;
use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::{flags, Cond, Kind, Type};
use crate::classpath::ClassPath;
use crate::contract_testing::{describe, kind_of, Value};
use crate::gap_contracts::{Proof, Shape, INTRINSICS};
use crate::harness::expr;
use crate::Verdict;

/// The generated class.
pub const CLASS: &str = "GapContractProofs";
/// How long the checker is given for each contract.
const TIMEOUT: Duration = Duration::from_secs(30);
/// How many times a loop of the JDK's method may be unwound.
const UNWIND: u32 = 16;

/// What the proof of a contract against the JDK's bytecode came to.
#[derive(Debug, Clone)]
pub(crate) enum Proving {
    /// The checker proved it on every input inside `assume:`.
    Proved(Proof),
    /// The checker found an input on which the JDK's bytecode does what the contract does not say: `words` by the
    /// `call:` line's names.
    Refuted { input: Vec<Value>, words: String },
    /// No proof, and why: the call is not one a proof is about, or the checker gave no verdict.
    Unproved(String),
}

/// Proves each contract against the JDK's bytecode where it can, in `dir`, with the JDK image and models of `cp`.
pub(crate) fn prove(shapes: &[Shape], cp: &ClassPath, dir: &Path) -> Vec<Proving> {
    let mut writer = ClassWriter::new(CLASS);
    writer.source_file = Some(format!("{CLASS}.java"));
    let mut owners: Vec<(String, Vec<u8>)> = Vec::new();
    let mut planned: Vec<Result<(String, String), String>> = Vec::new();
    for (i, shape) in shapes.iter().enumerate() {
        planned.push(provable(shape, cp).map(|bytes| {
            if !owners.iter().any(|(o, _)| *o == shape.gap.owner) {
                owners.push((shape.gap.owner.clone(), bytes.clone()));
            }
            let method = format!("p{i}");
            statement(shape, &method, &mut writer);
            (method, crate::digest::sha256_hex(&bytes))
        }));
    }
    if planned.iter().all(Result::is_err) {
        return planned.into_iter().map(|p| Proving::Unproved(p.err().unwrap_or_default())).collect();
    }
    let written = (|| -> Result<ClassPath, String> {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        std::fs::write(dir.join(format!("{CLASS}.class")), writer.to_bytes()).map_err(|e| e.to_string())?;
        for (owner, bytes) in &owners {
            let file = dir.join(format!("{owner}.class"));
            if let Some(parent) = file.parent() {
                std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            std::fs::write(file, bytes).map_err(|e| e.to_string())?;
        }
        // The JDK method's class is on the class path as a directory's, so the checker runs its bytecode rather
        // than meeting the gap; the rest of the JDK is the image's, as in every proof.
        let mut proof_cp = ClassPath::new();
        proof_cp.add(dir).map_err(|e| e.to_string())?;
        let proof_cp = match cp.jdk() {
            Some(_) => proof_cp.with_default_jdk(),
            None => proof_cp,
        };
        Ok(proof_cp.with_models(cp.has_models()))
    })();
    let jdk = crate::bmc::gaps::jdk_release().unwrap_or_else(|| "unknown".into());
    planned
        .into_iter()
        .zip(shapes)
        .map(|(plan, shape)| {
            let (method, digest) = match plan {
                Ok(p) => p,
                Err(why) => return Proving::Unproved(why),
            };
            let proof_cp = match &written {
                Ok(cp) => cp,
                Err(e) => return Proving::Unproved(format!("the proof's classes could not be written: {e}")),
            };
            let options = crate::bmc::Options { unwind: UNWIND, timeout: TIMEOUT, ..crate::bmc::Options::default() };
            let outcome = match crate::bmc::check(proof_cp, CLASS, &method, &options) {
                Ok(o) => o,
                Err(e) => return Proving::Unproved(format!("the tool's own checker could not run the proof: {e}")),
            };
            match outcome.verdict {
                Verdict::Verified => Proving::Proved(Proof {
                    class: shape.gap.owner.replace('/', "."),
                    jdk: jdk.clone(),
                    digest: format!("sha256:{digest}"),
                    checker: format!("jvmcontract's own checker ({})", outcome.solver),
                    unwind: UNWIND,
                    paths: outcome.paths,
                    seconds: outcome.seconds,
                }),
                Verdict::Violation => {
                    let input = witness(shape, &outcome.raw_inputs);
                    let words = describe(shape, &input);
                    Proving::Refuted { input, words }
                }
                Verdict::Unverifiable => Proving::Unproved(format!("the tool's own checker gives no proof against the JDK's bytecode: {}", outcome.problem.unwrap_or_else(|| "no reason".into()))),
            }
        })
        .collect()
}

/// The JDK method's class file, when a proof is about the contract's call; why not otherwise.
fn provable(shape: &Shape, cp: &ClassPath) -> Result<Vec<u8>, String> {
    let gap = &shape.gap;
    match gap.kind {
        GapKind::JdkStaticMethod => {}
        GapKind::ClassInitializer => return Err("an initializer's contract is not proved: the checker does not run initializers".into()),
        _ => return Err("only a static method's contract is proved against the JDK's bytecode: the call has an object whose state the tool's own checker does not keep".into()),
    }
    if let Some((name, t)) = shape.names.iter().zip(&shape.descriptor.params).find(|(_, t)| !t.is_primitive()) {
        return Err(format!("parameter {name} is a {}: a proof covers arrays only up to a bound, and the call may be given a longer one", t.java_name()));
    }
    if !(shape.descriptor.ret == Type::Void || expr::ty_of(&shape.descriptor.ret).is_some()) {
        return Err(format!("the call returns {}, which a proof does not check", shape.descriptor.ret.java_name()));
    }
    let owner = gap.owner.replace('/', ".");
    let jdk = cp.jdk().ok_or("no JDK image to take the method's bytecode from")?;
    let bytes = jdk.read_class(&gap.owner).ok().flatten().ok_or_else(|| format!("{owner} is not in the JDK image"))?;
    let class = crate::classfile::ClassFile::parse(&bytes).map_err(|e| format!("{owner} in the JDK image: {e}"))?;
    let method = class.method(&gap.name, &gap.descriptor).ok_or_else(|| format!("{owner} declares no {}{}", gap.name, gap.descriptor))?;
    if method.access & flags::STATIC == 0 {
        return Err(format!("{owner}.{} is not static", gap.name));
    }
    if method.code.is_none() {
        return Err(format!("{owner}.{} has no bytecode (it is native)", gap.name));
    }
    Ok(bytes)
}

/// The input of a witness, by parameter, from the checker's values by slot.
fn witness(shape: &Shape, raw: &std::collections::BTreeMap<u32, String>) -> Vec<Value> {
    let mut slot = 0u32;
    let mut out = Vec::new();
    for t in &shape.descriptor.params {
        let v = raw.get(&slot).and_then(|s| s.parse::<i64>().ok()).unwrap_or(0);
        out.push(Value::Int(v));
        slot += u32::from(t.slots());
    }
    out
}

/// Writes `method`, the statement of the contract `shape` over its parameters: it returns where the contract holds
/// of the JDK's call, and throws an `AssertionError` where it does not.
fn statement(shape: &Shape, method: &str, writer: &mut ClassWriter) {
    let gap = &shape.gap;
    let params = &shape.descriptor.params;
    let mut code = CodeBuilder::new();
    let base = shape.first_free.max(shape.slots_used);
    let (expected, thrown) = (base, base + 1);
    let fail = code.label();

    // Outside `assume:` the contract says nothing.
    if let Some(a) = &shape.assume {
        let inside = code.label();
        expr::emit(a, &mut code, &mut writer.pool);
        code.if_zero(Cond::Ne, inside);
        code.return_(None);
        code.bind(inside);
    }
    // The clause that should decide: the first whose condition holds before the call.
    code.iconst(-1);
    code.store(Kind::Int, expected);
    let chosen = code.label();
    for (k, (_, when)) in shape.throws.iter().enumerate() {
        let next = code.label();
        expr::emit(when, &mut code, &mut writer.pool);
        code.if_zero(Cond::Eq, next);
        code.iconst(k as i32);
        code.store(Kind::Int, expected);
        code.goto(chosen);
        code.bind(next);
    }
    code.bind(chosen);

    // The JDK's call.
    let (call_start, call_end, returned, threw) = (code.label(), code.label(), code.label(), code.label());
    code.bind(call_start);
    let mut slot = 0u16;
    for t in params {
        code.load(kind_of(t), slot);
        slot += t.slots();
    }
    let m = writer.pool.method_ref(&gap.owner, &gap.name, &gap.descriptor);
    code.op_u16(0xb8, m); // invokestatic
    if let (Some(s), t) = (shape.result_slot, &shape.descriptor.ret) {
        code.store(kind_of(t), s);
    }
    code.bind(call_end);
    code.goto(returned);

    // It threw: exactly the class of the clause that decides, which is built to compare its class with.
    code.bind(threw);
    code.store(Kind::Ref, thrown);
    code.load(Kind::Int, expected);
    code.if_zero(Cond::Lt, fail);
    for (k, (class, _)) in shape.throws.iter().enumerate() {
        let skip = code.label();
        code.load(Kind::Int, expected);
        code.iconst(k as i32);
        code.if_icmp(Cond::Ne, skip);
        code.load(Kind::Ref, thrown);
        let c = writer.pool.class(class);
        code.op_u16(0xbb, c); // new
        code.op(0x59); // dup
        let init = writer.pool.method_ref(class, "<init>", "()V");
        code.op_u16(0xb7, init);
        let same = writer.pool.method_ref(INTRINSICS, "sameClass", "(Ljava/lang/Object;Ljava/lang/Object;)Z");
        code.op_u16(0xb8, same);
        code.if_zero(Cond::Eq, fail);
        code.return_(None);
        code.bind(skip);
    }
    code.goto(fail);

    // It returned: where no clause holds, with the assertion holding of its result.
    code.bind(returned);
    code.load(Kind::Int, expected);
    code.if_zero(Cond::Ge, fail);
    if let Some(a) = &shape.after {
        expr::emit(a, &mut code, &mut writer.pool);
        code.if_zero(Cond::Eq, fail);
    }
    code.return_(None);

    code.bind(fail);
    let error = writer.pool.class("java/lang/AssertionError");
    code.op_u16(0xbb, error);
    code.op(0x59);
    let init = writer.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
    code.op_u16(0xb7, init);
    code.op(0xbf); // athrow

    code.handler(call_start, call_end, threw, None);
    code.max_stack = 32;
    code.max_locals = code.max_locals.max(base + 2) + 4;
    let descriptor = format!("({})V", params.iter().map(Type::descriptor).collect::<String>());
    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: method.to_string(), descriptor, code: Some(code) });
}
