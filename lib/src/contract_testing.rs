//! Testing a contract for a gap on a real JVM (step 3c of `llm-dlc/loops/sound-verdicts.md`): the JDK's own call
//! runs on the boundary values of its parameters' types and on random inputs drawn with a recorded seed, and the
//! contract ([`crate::gap_contracts`]) is checked on each. The interpreter and the engines share the tool's models,
//! so their agreement says nothing about the JVM; a JVM run of the JDK's real call does.
//!
//! One class, `GapContractTests`, is generated for every contract of a file, and run once. Its method `t<i>` takes
//! one input for contract `i`, evaluates the contract's conditions with the bytecode the engine's own method for it
//! uses ([`crate::harness::expr::emit`]), calls the JDK, and answers with a code: inside `assume:` or not, returned
//! or thrown as the contract says, or how it differs (another exception, none where a clause says one, an array
//! changed that `modifies:` leaves out, an assertion that fails, another object than the one named). `main` calls
//! it on every input and prints a line for each.
//!
//! What the test does not see:
//! - The receiver's state: an instance method is called on an object built afresh for each input by the class's
//!   constructor of no arguments (`new java.util.Random()`), and `modifies: this` is not checked.
//! - A `null` array, which a contract does not cover: the engine meets the gap there instead.
//! - What only other receivers or more inputs would show. A tested contract is evidence, not a proof.
//!
//! An input on which the JVM runs out of the test's memory or stack (a `VirtualMachineError`, as for
//! `new ArrayList<>(Integer.MAX_VALUE)`) says nothing either way, and is counted apart: a proof is about a JVM with
//! enough of both.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

use crate::classfile::writer::{ClassWriter, CodeBuilder, FieldWriter, MethodWriter};
use crate::classfile::{flags, Cond, Kind, Type};
use crate::classpath::ClassPath;
use crate::gap_contracts::{Counterexample, ResultForm, Shape, Testing};
use crate::bmc::gaps::GapKind;
use crate::harness::expr;

/// The counterexamples kept of each contract; the rest are counted.
pub const KEPT: usize = 20;
/// The seed of the random inputs.
pub const SEED: u64 = 1;
/// How many random inputs a contract with parameters gets, after its boundary values.
const RANDOM: usize = 256;
/// The most combinations of boundary values a contract gets; past that, each parameter's boundary values in turn.
const MOST_COMBINATIONS: usize = 512;
/// The inputs one method of the generated class runs.
const CHUNK: usize = 32;
/// How long the JVM is given.
const TIMEOUT: Duration = Duration::from_secs(60);
/// The generated class.
pub const CLASS: &str = "GapContractTests";

/// Tests each contract on a JVM, in `dir`, with `entries` on the class path (for an initializer's class): what the
/// test found, or why the JVM cannot test it, in the order given. `extra` holds, by contract, inputs to run besides
/// the boundary and random ones: the witness of a proof against the JDK's bytecode that refutes it
/// ([`crate::contract_proving`]), which only the JVM's run makes a counterexample.
pub(crate) fn test(shapes: &[Shape], cp: &ClassPath, entries: &[PathBuf], dir: &Path, extra: &[Vec<Vec<Value>>]) -> Vec<Result<Testing, String>> {
    let plans: Vec<Result<Plan, String>> = shapes
        .iter()
        .enumerate()
        .map(|(i, s)| {
            let mut plan = plan(s, cp)?;
            for input in extra.get(i).into_iter().flatten() {
                if !plan.inputs.contains(input) {
                    plan.inputs.push(input.clone());
                }
            }
            Ok(plan)
        })
        .collect();
    if plans.iter().all(Result::is_err) {
        return plans.into_iter().map(|p| Err(p.err().unwrap_or_default())).collect();
    }
    let ran = run(shapes, &plans, entries, dir);
    plans
        .into_iter()
        .enumerate()
        .map(|(i, plan)| {
            let plan = plan?;
            let lines = ran.as_ref().map_err(Clone::clone)?;
            Ok(judge(&shapes[i], &plan, lines.iter().filter(|l| l.contract == i)))
        })
        .collect()
}

/// A value of a parameter.
#[derive(Debug, Clone, PartialEq)]
pub(crate) enum Value {
    /// Of an integral type, `char` or `boolean` (0 or 1).
    Int(i64),
    Float(f64),
    Array(Vec<Value>),
}

/// What a contract is tested on.
struct Plan {
    inputs: Vec<Vec<Value>>,
    /// The class whose constructor of no arguments builds the receiver.
    receiver: Option<String>,
}

/// The inputs for a contract, or why the JVM cannot test it.
fn plan(shape: &Shape, cp: &ClassPath) -> Result<Plan, String> {
    let gap = &shape.gap;
    if gap.kind == GapKind::ClassInitializer {
        return Ok(Plan { inputs: vec![Vec::new()], receiver: None });
    }
    let owner = gap.owner.replace('/', ".");
    let class = cp.load(&gap.owner).ok().flatten().ok_or_else(|| format!("the test finds no class {owner}"))?.class;
    if class.access & flags::PUBLIC == 0 {
        return Err(format!("{owner} is not public, so the test cannot call it"));
    }
    let receiver = match gap.kind {
        GapKind::JdkConstructor => {
            if class.access & (flags::ABSTRACT | flags::INTERFACE) != 0 {
                return Err(format!("{owner} is abstract, so the test cannot build one"));
            }
            let public = class.method("<init>", &gap.descriptor).is_some_and(|m| m.access & flags::PUBLIC != 0);
            if !public {
                return Err(format!("{owner}'s constructor is not public, so the test cannot call it"));
            }
            None
        }
        GapKind::JdkStaticMethod => {
            let (_, m) = cp.find_method(&gap.owner, &gap.name, &gap.descriptor).ok_or_else(|| format!("the test finds no method {}.{}", owner, gap.name))?;
            if m.access & flags::PUBLIC == 0 || m.access & flags::STATIC == 0 {
                return Err(format!("{owner}.{} is not a public static method, so the test cannot call it", gap.name));
            }
            None
        }
        _ => {
            let (_, m) = cp.find_method(&gap.owner, &gap.name, &gap.descriptor).ok_or_else(|| format!("the test finds no method {}.{}", owner, gap.name))?;
            if m.access & flags::PUBLIC == 0 || m.access & flags::STATIC != 0 {
                return Err(format!("{owner}.{} is not a public instance method, so the test cannot call it", gap.name));
            }
            let buildable = class.access & (flags::ABSTRACT | flags::INTERFACE) == 0 && class.method("<init>", "()V").is_some_and(|m| m.access & flags::PUBLIC != 0);
            if !buildable {
                return Err(format!("{owner} has no public constructor of no arguments, so the test has nothing to call {} on", gap.name));
            }
            Some(gap.owner.clone())
        }
    };
    let mut domains = Vec::new();
    for (name, t) in shape.names.iter().zip(&shape.descriptor.params) {
        domains.push(Domain::of(t).ok_or_else(|| format!("parameter {name} is a {}, which the test makes no values of", t.java_name()))?);
    }
    Ok(Plan { inputs: inputs(&domains, SEED), receiver })
}

/// The values a parameter is tested on.
struct Domain {
    ty: Type,
    boundary: Vec<Value>,
}

impl Domain {
    fn of(t: &Type) -> Option<Domain> {
        let boundary = match t {
            Type::Array(inner) if inner.is_primitive() => {
                let e = Domain::of(inner)?;
                let mut out = vec![Value::Array(Vec::new())];
                out.extend(e.boundary.iter().take(4).map(|v| Value::Array(vec![v.clone()])));
                out.push(Value::Array(e.boundary.iter().rev().take(3).cloned().collect()));
                out
            }
            Type::Array(_) | Type::Object(_) | Type::Void => return None,
            _ => scalar_boundary(t)?,
        };
        Some(Domain { ty: t.clone(), boundary })
    }

    /// A random value: a boundary value, a small one, a middling one, or any, a quarter of the time each.
    fn random(&self, rng: &mut Rng) -> Value {
        match &self.ty {
            Type::Array(inner) => {
                let e = Domain::of(inner).expect("an array of primitives");
                let n = (rng.next() % 5) as usize;
                Value::Array((0..n).map(|_| e.random(rng)).collect())
            }
            t => {
                let pick = rng.next();
                match pick % 4 {
                    0 => self.boundary[(rng.next() % self.boundary.len() as u64) as usize].clone(),
                    k => match t {
                        Type::Float | Type::Double => {
                            let x = (rng.next() >> 11) as f64 / (1u64 << 53) as f64;
                            let scale = [0.0, 16.0, 65536.0, 1e30][k as usize];
                            let v = (x * 2.0 - 1.0) * scale;
                            Value::Float(if *t == Type::Float { v as f32 as f64 } else { v })
                        }
                        _ => {
                            let (lo, hi) = range(t);
                            let bound: i64 = [0, 16, 65536, i64::MAX][k as usize];
                            let raw = rng.next() as i64;
                            let v = if k == 3 { raw } else { raw.rem_euclid(2 * bound + 1) - bound };
                            Value::Int(wrap(v, t).clamp(lo, hi))
                        }
                    },
                }
            }
        }
    }
}

/// The smallest and largest value of an integral type, `char` or `boolean`.
fn range(t: &Type) -> (i64, i64) {
    match t {
        Type::Boolean => (0, 1),
        Type::Byte => (i8::MIN.into(), i8::MAX.into()),
        Type::Char => (0, u16::MAX.into()),
        Type::Short => (i16::MIN.into(), i16::MAX.into()),
        Type::Int => (i32::MIN.into(), i32::MAX.into()),
        _ => (i64::MIN, i64::MAX),
    }
}

/// `v` as the type would hold it: wrapped to its width, as a cast does.
fn wrap(v: i64, t: &Type) -> i64 {
    match t {
        Type::Boolean => v & 1,
        Type::Byte => i64::from(v as i8),
        Type::Char => i64::from(v as u16),
        Type::Short => i64::from(v as i16),
        Type::Int => i64::from(v as i32),
        _ => v,
    }
}

fn scalar_boundary(t: &Type) -> Option<Vec<Value>> {
    let ints = |v: &[i64]| Some(v.iter().map(|&x| Value::Int(x)).collect());
    match t {
        Type::Boolean => ints(&[0, 1]),
        Type::Byte => ints(&[0, 1, -1, 2, i8::MIN.into(), i8::MAX.into()]),
        Type::Char => ints(&[0, 1, 'a' as i64, 0x7f, 0x80, 0xffff]),
        Type::Short => ints(&[0, 1, -1, 2, i16::MIN.into(), i16::MAX.into()]),
        Type::Int => ints(&[0, 1, -1, 2, -2, i32::MIN.into(), i32::MIN as i64 + 1, i32::MAX as i64 - 1, i32::MAX.into()]),
        Type::Long => ints(&[0, 1, -1, 2, -2, i32::MIN.into(), i32::MAX.into(), i64::MIN, i64::MIN + 1, i64::MAX - 1, i64::MAX]),
        Type::Float => Some([0.0, -0.0, 1.0, -1.0, 0.5, f64::NAN, f64::INFINITY, f64::NEG_INFINITY, f32::MIN_POSITIVE as f64, f32::MAX as f64].into_iter().map(Value::Float).collect()),
        Type::Double => Some([0.0, -0.0, 1.0, -1.0, 0.5, f64::NAN, f64::INFINITY, f64::NEG_INFINITY, f64::MIN_POSITIVE, f64::MAX].into_iter().map(Value::Float).collect()),
        _ => None,
    }
}

/// The inputs: every combination of boundary values (or, past [`MOST_COMBINATIONS`], each parameter's in turn
/// against the others' cycling), then [`RANDOM`] random ones, each once.
fn inputs(domains: &[Domain], seed: u64) -> Vec<Vec<Value>> {
    let mut out: Vec<Vec<Value>> = Vec::new();
    let push = |input: Vec<Value>, out: &mut Vec<Vec<Value>>| {
        if !out.contains(&input) {
            out.push(input);
        }
    };
    if domains.is_empty() {
        return vec![Vec::new()];
    }
    let combinations = domains.iter().try_fold(1usize, |n, d| n.checked_mul(d.boundary.len()).filter(|&n| n <= MOST_COMBINATIONS));
    match combinations {
        Some(n) => {
            for mut k in 0..n {
                let mut input = Vec::new();
                for d in domains {
                    input.push(d.boundary[k % d.boundary.len()].clone());
                    k /= d.boundary.len();
                }
                push(input, &mut out);
            }
        }
        None => {
            for (i, d) in domains.iter().enumerate() {
                for (j, v) in d.boundary.iter().enumerate() {
                    let input = domains.iter().enumerate().map(|(o, other)| if o == i { v.clone() } else { other.boundary[(j + o) % other.boundary.len()].clone() }).collect();
                    push(input, &mut out);
                }
            }
        }
    }
    let mut rng = Rng(seed);
    for _ in 0..RANDOM {
        let input = domains.iter().map(|d| d.random(&mut rng)).collect();
        push(input, &mut out);
    }
    out
}

/// SplitMix64: small, and the same on every machine.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }
}

// The codes `t<i>` answers with.
const OK: i32 = 0;
const OUTSIDE: i32 = 1;
const EXHAUSTED: i32 = 2;
const THREW: i32 = 3;
const ASSERTION: i32 = 5;
const UNLOADABLE: i32 = 8;
const CONDITION: i32 = 9;
const WRONG_EXCEPTION: i32 = 100;
const NO_EXCEPTION: i32 = 200;
const AS_STATED: i32 = 300;
const CHANGED: i32 = 400;
const OTHER_RESULT: i32 = 600;
/// A result's class: `null`, the receiver, parameter `k` from 3, or another object.
const RESULT_NULL: i32 = 1;
const RESULT_THIS: i32 = 2;
const RESULT_PARAMETER: i32 = 3;
const RESULT_OTHER: i32 = 99;

/// One line of the JVM's output.
#[derive(Debug, Clone)]
struct Line {
    contract: usize,
    input: usize,
    code: i32,
    /// What the JVM threw, as its `toString` gives it.
    thrown: String,
}

/// Writes the class, runs it, and reads its lines; why not, when the JVM cannot.
fn run(shapes: &[Shape], plans: &[Result<Plan, String>], entries: &[PathBuf], dir: &Path) -> Result<Vec<Line>, String> {
    let home = crate::jimage::JImage::find_java_home().ok_or("no JVM to test it on (set JAVA_HOME)")?;
    let java = home.join("bin").join("java");
    let mut writer = ClassWriter::new(CLASS);
    writer.default_constructor();
    writer.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: "last".into(), descriptor: "Ljava/lang/Object;".into() });
    let r = report(&mut writer);
    writer.methods.push(r);
    let mut runs = Vec::new();
    for (i, (shape, plan)) in shapes.iter().zip(plans).enumerate() {
        let Ok(plan) = plan else { continue };
        let descriptor = tester(shape, i, &mut writer);
        for (c, chunk) in plan.inputs.chunks(CHUNK).enumerate() {
            let name = format!("run{i}_{c}");
            let mut code = CodeBuilder::new();
            for (j, input) in chunk.iter().enumerate() {
                code.iconst(i as i32);
                code.iconst((c * CHUNK + j) as i32);
                if let Some(owner) = &plan.receiver {
                    let class = writer.pool.class(owner);
                    code.op_u16(0xbb, class);
                    code.op(0x59);
                    let init = writer.pool.method_ref(owner, "<init>", "()V");
                    code.op_u16(0xb7, init);
                }
                for (v, t) in input.iter().zip(&shape.descriptor.params) {
                    push_value(v, t, &mut code, &mut writer);
                }
                let t = writer.pool.method_ref(CLASS, &format!("t{i}"), &descriptor);
                code.op_u16(0xb8, t);
                let r = writer.pool.method_ref(CLASS, "r", "(III)V");
                code.op_u16(0xb8, r);
            }
            code.return_(None);
            code.max_stack = 32;
            writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: name.clone(), descriptor: "()V".into(), code: Some(code) });
            runs.push(name);
        }
    }
    let mut main = CodeBuilder::new();
    for name in &runs {
        let m = writer.pool.method_ref(CLASS, name, "()V");
        main.op_u16(0xb8, m);
    }
    out(&mut main, &mut writer);
    let end = writer.pool.string("@end");
    main.ldc(end);
    let println = writer.pool.method_ref("java/io/PrintStream", "println", "(Ljava/lang/String;)V");
    main.op_u16(0xb6, println);
    main.return_(None);
    main.max_locals = 1;
    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "main".into(), descriptor: "([Ljava/lang/String;)V".into(), code: Some(main) });

    let _ = std::fs::remove_dir_all(dir);
    std::fs::create_dir_all(dir).map_err(|e| format!("cannot write the JVM test into {}: {e}", dir.display()))?;
    std::fs::write(dir.join(format!("{CLASS}.class")), writer.to_bytes()).map_err(|e| format!("cannot write the JVM test: {e}"))?;
    // The JVM runs in `dir`, so every entry is made absolute first: a relative `--work` or `--classes` would
    // otherwise name another directory.
    let absolute = |p: &Path| std::path::absolute(p).unwrap_or_else(|_| p.to_path_buf());
    let mut class_path = vec![absolute(dir)];
    class_path.extend(entries.iter().map(|e| absolute(e)));
    let class_path = std::env::join_paths(&class_path).map_err(|e| format!("a class path entry cannot be joined: {e}"))?;
    let stdout = std::fs::File::create(dir.join("stdout")).map_err(|e| e.to_string())?;
    let stderr = std::fs::File::create(dir.join("stderr")).map_err(|e| e.to_string())?;
    let mut child = Command::new(&java)
        .args(["-Xmx128m", "-Xss1m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData", "-cp"])
        .arg(&class_path)
        .arg(CLASS)
        .current_dir(dir)
        .stdout(stdout)
        .stderr(stderr)
        .spawn()
        .map_err(|e| format!("cannot run {}: {e}", java.display()))?;
    let started = Instant::now();
    loop {
        if child.try_wait().map_err(|e| e.to_string())?.is_some() {
            break;
        }
        if started.elapsed() > TIMEOUT {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!("the JVM test did not finish within {} s", TIMEOUT.as_secs()));
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    let text = std::fs::read_to_string(dir.join("stdout")).unwrap_or_default();
    if !text.lines().any(|l| l == "@end") {
        let err = std::fs::read_to_string(dir.join("stderr")).unwrap_or_default();
        let tail: Vec<&str> = err.lines().rev().take(3).collect();
        return Err(format!("the JVM test stopped before its end{}", if tail.is_empty() { String::new() } else { format!(": {}", tail.into_iter().rev().collect::<Vec<_>>().join(" / ")) }));
    }
    let mut lines: Vec<Line> = Vec::new();
    for l in text.lines() {
        match l.strip_prefix('@').filter(|r| *r != "end").map(|r| r.splitn(4, ' ').collect::<Vec<_>>()) {
            Some(parts) if parts.len() == 4 => {
                let (Ok(contract), Ok(input), Ok(code)) = (parts[0].parse(), parts[1].parse(), parts[2].parse()) else { continue };
                lines.push(Line { contract, input, code, thrown: parts[3].to_string() });
            }
            // A message of several lines goes on with the line before.
            _ => {
                if let Some(last) = lines.last_mut().filter(|_| !l.starts_with('@')) {
                    last.thrown.push('\n');
                    last.thrown.push_str(l);
                }
            }
        }
    }
    Ok(lines)
}

/// `getstatic System.out`.
fn out(code: &mut CodeBuilder, writer: &mut ClassWriter) {
    let field = writer.pool.field_ref("java/lang/System", "out", "Ljava/io/PrintStream;");
    code.op_u16(0xb2, field);
}

/// `r(contract, input, code)`: prints `@contract input code last`, and clears `last`.
fn report(writer: &mut ClassWriter) -> MethodWriter {
    let mut code = CodeBuilder::new();
    let print_char = writer.pool.method_ref("java/io/PrintStream", "print", "(C)V");
    let print_int = writer.pool.method_ref("java/io/PrintStream", "print", "(I)V");
    let println = writer.pool.method_ref("java/io/PrintStream", "println", "(Ljava/lang/Object;)V");
    let last = writer.pool.field_ref(CLASS, "last", "Ljava/lang/Object;");
    out(&mut code, writer);
    code.iconst('@' as i32);
    code.op_u16(0xb6, print_char);
    for slot in 0..3 {
        if slot > 0 {
            out(&mut code, writer);
            code.iconst(' ' as i32);
            code.op_u16(0xb6, print_char);
        }
        out(&mut code, writer);
        code.load(Kind::Int, slot);
        code.op_u16(0xb6, print_int);
    }
    out(&mut code, writer);
    code.iconst(' ' as i32);
    code.op_u16(0xb6, print_char);
    out(&mut code, writer);
    code.op_u16(0xb2, last);
    code.op_u16(0xb6, println);
    code.op(0x01);
    code.op_u16(0xb3, last);
    code.return_(None);
    code.max_locals = 3;
    MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "r".into(), descriptor: "(III)V".into(), code: Some(code) }
}

pub(crate) fn kind_of(t: &Type) -> Kind {
    match t {
        Type::Long => Kind::Long,
        Type::Float => Kind::Float,
        Type::Double => Kind::Double,
        Type::Object(_) | Type::Array(_) => Kind::Ref,
        _ => Kind::Int,
    }
}

fn push_value(v: &Value, t: &Type, code: &mut CodeBuilder, writer: &mut ClassWriter) {
    match (v, t) {
        (Value::Int(x), Type::Long) => match x {
            0 => code.op(0x09),
            1 => code.op(0x0a),
            _ => {
                let c = writer.pool.long(*x);
                code.ldc2(c);
            }
        },
        (Value::Int(x), _) => {
            if (-32768..=32767).contains(x) {
                code.iconst(*x as i32);
            } else {
                let c = writer.pool.integer(*x as i32);
                code.ldc(c);
            }
        }
        (Value::Float(x), Type::Float) => {
            let c = writer.pool.float(*x as f32);
            code.ldc(c);
        }
        (Value::Float(x), _) => {
            let c = writer.pool.double(*x);
            code.ldc2(c);
        }
        (Value::Array(items), Type::Array(inner)) => {
            code.iconst(items.len() as i32);
            let (atype, store) = match inner.as_ref() {
                Type::Boolean => (4, 0x54),
                Type::Char => (5, 0x55),
                Type::Float => (6, 0x51),
                Type::Double => (7, 0x52),
                Type::Byte => (8, 0x54),
                Type::Short => (9, 0x56),
                Type::Int => (10, 0x4f),
                _ => (11, 0x50),
            };
            code.op_u8(0xbc, atype);
            for (k, item) in items.iter().enumerate() {
                code.op(0x59);
                code.iconst(k as i32);
                push_value(item, inner, code, writer);
                code.op(store);
            }
        }
        _ => unreachable!("a value of another type"),
    }
}

/// Writes `t<index>`, which runs one input of the contract, and returns its descriptor.
fn tester(shape: &Shape, index: usize, writer: &mut ClassWriter) -> String {
    let mut code = CodeBuilder::new();
    let last = writer.pool.field_ref(CLASS, "last", "Ljava/lang/Object;");
    if shape.gap.kind == GapKind::ClassInitializer {
        // Initializing the class on the JVM: it throws nothing, as the contract says.
        let (start, end, vm, missing, any) = (code.label(), code.label(), code.label(), code.label(), code.label());
        code.bind(start);
        let name = writer.pool.string(&shape.gap.owner.replace('/', "."));
        code.ldc(name);
        code.iconst(1);
        let me = writer.pool.class(CLASS);
        code.ldc(me);
        let loader = writer.pool.method_ref("java/lang/Class", "getClassLoader", "()Ljava/lang/ClassLoader;");
        code.op_u16(0xb6, loader);
        let for_name = writer.pool.method_ref("java/lang/Class", "forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;");
        code.op_u16(0xb8, for_name);
        code.op(0x57); // pop
        code.bind(end);
        code.iconst(OK);
        code.return_(Some(Kind::Int));
        for (label, class, answer) in [(vm, Some("java/lang/VirtualMachineError"), EXHAUSTED), (missing, Some("java/lang/ClassNotFoundException"), UNLOADABLE), (any, None, THREW)] {
            code.bind(label);
            code.op_u16(0xb3, last);
            code.iconst(answer);
            code.return_(Some(Kind::Int));
            let catch = class.map(|c| writer.pool.class(c));
            code.handler(start, end, label, catch);
        }
        code.max_stack = 8;
        code.max_locals = 1;
        writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: format!("t{index}"), descriptor: "()I".into(), code: Some(code) });
        return "()I".into();
    }

    let gap = &shape.gap;
    let params = &shape.descriptor.params;
    let mut slots = Vec::new();
    let mut slot = u16::from(shape.receiver);
    for t in params {
        slots.push(slot);
        slot += t.slots();
    }
    let base = shape.first_free.max(shape.slots_used);
    let (expected, result, thrown) = (base, base + 1, base + 2);
    let copies: Vec<(usize, u16)> = params
        .iter()
        .enumerate()
        .filter(|(i, t)| matches!(t, Type::Array(_)) && !shape.modified.iter().any(|m| m.slot == slots[*i]))
        .enumerate()
        .map(|(k, (i, _))| (i, base + 3 + k as u16))
        .collect();
    let int_return = |code: &mut CodeBuilder, answer: i32| {
        code.iconst(answer);
        code.return_(Some(Kind::Int));
    };

    let (outer_start, outer_end, call_start, call_end) = (code.label(), code.label(), code.label(), code.label());
    let (vm, any, returned, condition) = (code.label(), code.label(), code.label(), code.label());
    code.bind(outer_start);
    if let Some(a) = &shape.assume {
        let inside = code.label();
        expr::emit(a, &mut code, &mut writer.pool);
        code.if_zero(Cond::Ne, inside);
        int_return(&mut code, OUTSIDE);
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
    // The arrays the contract says it leaves, copied to compare after.
    for (i, copy) in &copies {
        let array = params[*i].descriptor();
        code.load(Kind::Ref, slots[*i]);
        let clone = writer.pool.method_ref(&array, "clone", "()Ljava/lang/Object;");
        code.op_u16(0xb6, clone);
        let class = writer.pool.class(&array);
        code.op_u16(0xc0, class);
        code.store(Kind::Ref, *copy);
    }
    // The JDK's call.
    code.bind(call_start);
    let owner = writer.pool.class(&gap.owner);
    if gap.kind == GapKind::JdkConstructor {
        code.op_u16(0xbb, owner);
        code.op(0x59);
    } else if shape.receiver {
        code.load(Kind::Ref, 0);
        code.op_u16(0xc0, owner);
    }
    for (t, s) in params.iter().zip(&slots) {
        code.load(kind_of(t), *s);
    }
    if gap.kind == GapKind::JdkConstructor {
        let init = writer.pool.method_ref(&gap.owner, "<init>", &gap.descriptor);
        code.op_u16(0xb7, init);
        code.store(Kind::Ref, result);
    } else {
        let m = writer.pool.method_ref(&gap.owner, &gap.name, &gap.descriptor);
        code.op_u16(if gap.kind == GapKind::JdkStaticMethod { 0xb8 } else { 0xb6 }, m);
        match (&shape.descriptor.ret, shape.result_slot) {
            (Type::Void, _) => {}
            // A primitive result goes where the contract's `result` reads it.
            (t, Some(s)) => code.store(kind_of(t), s),
            _ => code.store(Kind::Ref, result),
        }
    }
    code.bind(call_end);
    code.goto(returned);

    // It threw.
    code.bind(vm);
    code.op_u16(0xb3, last);
    int_return(&mut code, EXHAUSTED);
    code.bind(any);
    code.store(Kind::Ref, thrown);
    code.load(Kind::Ref, thrown);
    code.op_u16(0xb3, last);
    let some_clause = code.label();
    code.load(Kind::Int, expected);
    code.if_zero(Cond::Ge, some_clause);
    int_return(&mut code, THREW);
    code.bind(some_clause);
    let wrong = code.label();
    for (k, (class, _)) in shape.throws.iter().enumerate() {
        let skip = code.label();
        code.load(Kind::Int, expected);
        code.iconst(k as i32);
        code.if_icmp(Cond::Ne, skip);
        code.load(Kind::Ref, thrown);
        let get_class = writer.pool.method_ref("java/lang/Object", "getClass", "()Ljava/lang/Class;");
        code.op_u16(0xb6, get_class);
        let c = writer.pool.class(class);
        code.ldc(c);
        code.if_acmpne(wrong);
        int_return(&mut code, AS_STATED + k as i32);
        code.bind(skip);
    }
    code.bind(wrong);
    code.load(Kind::Int, expected);
    code.iconst(WRONG_EXCEPTION);
    code.op(0x60); // iadd
    code.return_(Some(Kind::Int));

    // It returned.
    code.bind(returned);
    let normally = code.label();
    code.load(Kind::Int, expected);
    code.if_zero(Cond::Lt, normally);
    code.load(Kind::Int, expected);
    code.iconst(NO_EXCEPTION);
    code.op(0x60);
    code.return_(Some(Kind::Int));
    code.bind(normally);
    for (i, copy) in &copies {
        let same = code.label();
        code.load(Kind::Ref, slots[*i]);
        code.load(Kind::Ref, *copy);
        let element = match &params[*i] {
            Type::Array(inner) => inner.descriptor(),
            _ => unreachable!(),
        };
        let equals = writer.pool.method_ref("java/util/Arrays", "equals", &format!("([{element}[{element})Z"));
        code.op_u16(0xb8, equals);
        code.if_zero(Cond::Ne, same);
        int_return(&mut code, CHANGED + *i as i32);
        code.bind(same);
    }
    if let Some(form) = shape.result {
        // The result's class, against the one the contract names.
        let references: Vec<(usize, u16)> = params.iter().enumerate().filter(|(_, t)| t.is_reference()).map(|(i, _)| (i, slots[i])).collect();
        let want = match form {
            ResultForm::Null => RESULT_NULL,
            ResultForm::This => RESULT_THIS,
            ResultForm::Parameter(s) => RESULT_PARAMETER + references.iter().position(|(_, rs)| *rs == s).unwrap_or(0) as i32,
            ResultForm::Fresh => RESULT_OTHER,
        };
        let classified = code.label();
        let answer = |code: &mut CodeBuilder, class: i32| {
            code.iconst(class);
            code.store(Kind::Int, expected);
            code.goto(classified);
        };
        let not_null = code.label();
        code.load(Kind::Ref, result);
        code.if_nonnull(not_null);
        answer(&mut code, RESULT_NULL);
        code.bind(not_null);
        let mut candidates = vec![(0u16, RESULT_THIS)];
        candidates.extend(references.iter().enumerate().map(|(k, (_, s))| (*s, RESULT_PARAMETER + k as i32)));
        for (s, class) in candidates {
            let other = code.label();
            code.load(Kind::Ref, result);
            code.load(Kind::Ref, s);
            code.if_acmpne(other);
            answer(&mut code, class);
            code.bind(other);
        }
        answer(&mut code, RESULT_OTHER);
        code.bind(classified);
        let named = code.label();
        code.load(Kind::Int, expected);
        code.iconst(want);
        code.if_icmp(Cond::Eq, named);
        code.load(Kind::Int, expected);
        code.iconst(OTHER_RESULT);
        code.op(0x60);
        code.return_(Some(Kind::Int));
        code.bind(named);
    }
    if let Some(a) = &shape.after {
        let holds = code.label();
        expr::emit(a, &mut code, &mut writer.pool);
        code.if_zero(Cond::Ne, holds);
        // What the call returned, for the counterexample.
        if let Some(s) = shape.result_slot {
            let (kind, boxing) = if shape.descriptor.ret == Type::Long { (Kind::Long, ("java/lang/Long", "(J)Ljava/lang/Long;")) } else { (Kind::Int, ("java/lang/Integer", "(I)Ljava/lang/Integer;")) };
            code.load(kind, s);
            let value_of = writer.pool.method_ref(boxing.0, "valueOf", boxing.1);
            code.op_u16(0xb8, value_of);
            code.op_u16(0xb3, last);
        }
        int_return(&mut code, ASSERTION);
        code.bind(holds);
    }
    int_return(&mut code, OK);
    code.bind(outer_end);
    // A condition of the contract that throws.
    code.bind(condition);
    code.op_u16(0xb3, last);
    int_return(&mut code, CONDITION);

    let vm_class = writer.pool.class("java/lang/VirtualMachineError");
    code.handler(call_start, call_end, vm, Some(vm_class));
    code.handler(call_start, call_end, any, None);
    code.handler(outer_start, outer_end, condition, None);
    code.max_stack = 32;
    code.max_locals = code.max_locals.max(base + 3 + copies.len() as u16) + 4;
    let descriptor = format!("({}{})I", if shape.receiver { "Ljava/lang/Object;" } else { "" }, params.iter().map(Type::descriptor).collect::<String>());
    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: format!("t{index}"), descriptor: descriptor.clone(), code: Some(code) });
    descriptor
}

/// What the lines of one contract say.
fn judge<'a>(shape: &Shape, plan: &Plan, lines: impl Iterator<Item = &'a Line>) -> Testing {
    let jdk = crate::bmc::gaps::jdk_release().unwrap_or_else(|| "unknown".into());
    let mut t = Testing { inputs: 0, returned: 0, thrown: vec![0; shape.throws.len()], outside: 0, exhausted: 0, seed: SEED, jdk, receiver: plan.receiver.as_ref().map(|r| format!("new {}()", r.replace('/', "."))), counterexamples: Vec::new(), refuting: 0 };
    let clause = |k: i32| -> String {
        let k = k as usize;
        format!("throws {}, by `throws: {}`", shape.throws.get(k).map(|(c, _)| c.replace('/', ".")).unwrap_or_default(), shape.throws_text.get(k).cloned().unwrap_or_default())
    };
    let initializer = shape.gap.kind == GapKind::ClassInitializer;
    for line in lines {
        let input = plan.inputs.get(line.input).map(|i| describe(shape, i)).unwrap_or_default();
        let found = |expected: String, observed: String| Counterexample { input: input.clone(), expected, observed };
        let counterexample = match line.code {
            OK => {
                t.returned += 1;
                None
            }
            OUTSIDE => {
                t.outside += 1;
                continue;
            }
            EXHAUSTED => {
                t.exhausted += 1;
                continue;
            }
            UNLOADABLE => {
                t.exhausted += 1;
                continue;
            }
            THREW if initializer => Some(found("throws nothing".into(), format!("throws {}", line.thrown))),
            THREW => Some(found("returns normally".into(), format!("throws {}", line.thrown))),
            ASSERTION => {
                let returned = line.thrown.trim().parse::<i64>().ok().filter(|_| shape.result_slot.is_some()).map(|v| show(&Value::Int(v), &shape.descriptor.ret));
                let observed = match returned {
                    Some(v) => format!("returns {v}"),
                    None => "returns with it false".into(),
                };
                Some(found(format!("returns with `assert: {}` holding", shape.assert.as_deref().unwrap_or("true")), observed))
            }
            CONDITION => Some(found("can be checked, its conditions being defined there".into(), format!("leaves a condition of the contract throwing {}", line.thrown))),
            c if (AS_STATED..CHANGED).contains(&c) => {
                if let Some(n) = t.thrown.get_mut((c - AS_STATED) as usize) {
                    *n += 1;
                }
                None
            }
            c if (WRONG_EXCEPTION..NO_EXCEPTION).contains(&c) => Some(found(clause(c - WRONG_EXCEPTION), format!("throws {}", line.thrown))),
            c if (NO_EXCEPTION..AS_STATED).contains(&c) => Some(found(clause(c - NO_EXCEPTION), "returns normally".into())),
            c if (CHANGED..OTHER_RESULT).contains(&c) => {
                let name = shape.names.get((c - CHANGED) as usize).cloned().unwrap_or_default();
                Some(found(format!("leaves {name} as it was, `modifies:` not naming it"), format!("changes {name}")))
            }
            c if c >= OTHER_RESULT => {
                let what = |class: i32| -> String {
                    let references: Vec<&String> = shape.names.iter().zip(&shape.descriptor.params).filter(|(_, t)| t.is_reference()).map(|(n, _)| n).collect();
                    match class {
                        RESULT_NULL => "returns null".into(),
                        RESULT_THIS => "returns the object it is called on".into(),
                        RESULT_OTHER => "returns a new object".into(),
                        k => format!("returns {}", references.get((k - RESULT_PARAMETER) as usize).map(|s| s.as_str()).unwrap_or("a parameter")),
                    }
                };
                let named = match shape.result {
                    Some(ResultForm::Null) => RESULT_NULL,
                    Some(ResultForm::This) => RESULT_THIS,
                    Some(ResultForm::Fresh) => RESULT_OTHER,
                    Some(ResultForm::Parameter(s)) => {
                        let mut slot = u16::from(shape.receiver);
                        let mut k = 0;
                        for p in &shape.descriptor.params {
                            if slot == s {
                                break;
                            }
                            if p.is_reference() {
                                k += 1;
                            }
                            slot += p.slots();
                        }
                        RESULT_PARAMETER + k
                    }
                    None => RESULT_OTHER,
                };
                Some(found(what(named), what(c - OTHER_RESULT)))
            }
            _ => Some(found("is checked".into(), format!("answered the test with code {}", line.code))),
        };
        t.inputs += 1;
        if let Some(c) = counterexample {
            t.refuting += 1;
            if t.counterexamples.len() < KEPT {
                t.counterexamples.push(c);
            }
        }
    }
    t
}

/// An input by the `call:` line's names: `capacity=-1, bytes=[0, 1]`.
pub(crate) fn describe(shape: &Shape, input: &[Value]) -> String {
    shape.names.iter().zip(&shape.descriptor.params).zip(input).map(|((n, t), v)| format!("{n}={}", show(v, t))).collect::<Vec<_>>().join(", ")
}

fn show(v: &Value, t: &Type) -> String {
    match (v, t) {
        (Value::Int(x), Type::Boolean) => (*x != 0).to_string(),
        (Value::Int(x), Type::Char) => match char::from_u32(*x as u32) {
            Some(c) if c.is_ascii_graphic() || c == ' ' => format!("'{c}'"),
            _ => format!("'\\u{x:04x}'"),
        },
        (Value::Int(x), Type::Long) => format!("{x}L"),
        (Value::Int(x), _) => x.to_string(),
        (Value::Float(x), Type::Float) => float_text(*x, "Float", "f"),
        (Value::Float(x), _) => float_text(*x, "Double", ""),
        (Value::Array(items), Type::Array(inner)) => format!("[{}]", items.iter().map(|i| show(i, inner)).collect::<Vec<_>>().join(", ")),
        _ => "?".into(),
    }
}

fn float_text(x: f64, class: &str, suffix: &str) -> String {
    if x.is_nan() {
        format!("{class}.NaN")
    } else if x.is_infinite() {
        format!("{class}.{}_INFINITY", if x > 0.0 { "POSITIVE" } else { "NEGATIVE" })
    } else {
        format!("{x:?}{suffix}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inputs_are_boundary_values_then_seeded_random_ones_each_once() {
        let int = Domain::of(&Type::Int).unwrap();
        let bytes = Domain::of(&Type::Array(Box::new(Type::Byte))).unwrap();
        let a = inputs(&[int, bytes], SEED);
        let int = Domain::of(&Type::Int).unwrap();
        let bytes = Domain::of(&Type::Array(Box::new(Type::Byte))).unwrap();
        assert_eq!(a, inputs(&[int, bytes], SEED), "the same seed draws the same inputs");
        assert!(a.contains(&vec![Value::Int(-1), Value::Array(Vec::new())]));
        assert!(a.contains(&vec![Value::Int(i32::MIN.into()), Value::Array(vec![Value::Int(-1)])]));
        assert!(a.len() > 9 * 6 && a.len() <= 9 * 6 + RANDOM);
        for input in &a {
            let Value::Int(n) = input[0] else { panic!() };
            assert!(i32::try_from(n).is_ok(), "{n} is an int");
            let Value::Array(items) = &input[1] else { panic!() };
            assert!(items.len() <= 4 && items.iter().all(|v| matches!(v, Value::Int(b) if i8::try_from(*b).is_ok())));
        }
        assert_eq!(inputs(&[], SEED), vec![Vec::<Value>::new()]);
        assert_eq!(describe_values(&[Value::Int(-1), Value::Array(vec![Value::Int(0x80)])], &[Type::Long, Type::Array(Box::new(Type::Char))]), "a=-1L, b=['\\u0080']");
    }

    fn describe_values(input: &[Value], types: &[Type]) -> String {
        let names = ["a", "b"];
        names.iter().zip(types).zip(input).map(|((n, t), v)| format!("{n}={}", show(v, t))).collect::<Vec<_>>().join(", ")
    }
}
