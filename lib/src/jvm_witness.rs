//! A counterexample run on a real JVM. The tool's own interpreter replays a witness before it is reported, but it
//! cannot run every JDK call (`new java.util.Random(seed)` is outside it), and under `--gaps advised` such a call
//! is exactly where a contract stood in for the JDK during the proof. A contract admits what the JDK's call may
//! never do (any value in a range), so a witness found through one is only a counterexample once the JDK's real
//! call is shown to take the program there.
//!
//! The harness the checker proved is a class like any other, so the JVM runs it: `WitnessRun`, generated here,
//! calls the harness's `check` on the witness, with the JDK's real calls where the contracts stood. An
//! `AssertionError` is the statement failing on the JVM, and the witness is real. A normal return is the JVM's
//! calls not doing what the contract let the checker suppose, and the witness is not one. The method under proof
//! is then called on its own, on fresh copies of the same arguments, for the outcome to report (step 3e's
//! follow-up in `llm-dlc/loops/sound-verdicts.md`).
//!
//! The harness runs first, in a fresh JVM, so that it sees the classes uninitialized, as the checker does.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

use crate::classfile::writer::{ClassWriter, CodeBuilder, Label, MethodWriter};
use crate::classfile::{flags, Cond, Kind, Type};
use crate::interp::Value;
use crate::jbmc::Argument;
use crate::witness::Replayed;

/// The generated class.
pub const CLASS: &str = "WitnessRun";
/// How long the JVM is given.
const TIMEOUT: Duration = Duration::from_secs(60);

/// A method to call on its own on the witness, for its outcome: a static method whose parameters are the harness's.
#[derive(Debug, Clone)]
pub struct DirectCall {
    /// The owner's internal name (`before/fixtures/Sized` for a previous version).
    pub owner: String,
    pub name: String,
    pub descriptor: String,
    pub ret: Type,
}

/// What the harness did on the JVM.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Check {
    /// It returned: the statement holds on the witness, on the JVM.
    Holds,
    /// It threw `AssertionError`: the statement fails on the witness, on the JVM.
    Refuted,
    /// It threw something else, which a harness should not.
    Threw(String),
}

/// One run.
#[derive(Debug, Clone)]
pub struct Run {
    /// The JDK the JVM was, as its release file names it.
    pub jdk: String,
    pub check: Check,
    /// What each direct call did, in order, as the interpreter's replay would say it.
    pub calls: Vec<Replayed>,
}

/// Runs the harness `harness_class.check`, whose parameters are `types`, on `arguments` on a JVM, then each of
/// `calls` on the same arguments; `slots` are the parameters' local slots, which key the arrays a call leaves.
/// `entries` is the class path: the harness's directory and the application's classes, never the tool's JDK
/// models or extracted JDK classes, which the JVM has of its own.
pub fn run(dir: &Path, harness_class: &str, types: &[Type], slots: &[u16], arguments: &[Argument], calls: &[DirectCall], entries: &[PathBuf]) -> Result<Run, String> {
    crate::phases::timed(crate::phases::Step::Jvm, || run_untimed(dir, harness_class, types, slots, arguments, calls, entries))
}

fn run_untimed(dir: &Path, harness_class: &str, types: &[Type], slots: &[u16], arguments: &[Argument], calls: &[DirectCall], entries: &[PathBuf]) -> Result<Run, String> {
    for t in types {
        let element = match t {
            Type::Array(e) => e.as_ref(),
            other => other,
        };
        if !matches!(element, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long) {
            return Err(format!("a parameter of type {} is not one the JVM run passes", t.java_name()));
        }
    }
    let home = crate::jimage::JImage::find_java_home().ok_or("no JVM to run it on (set JAVA_HOME)")?;
    let java = home.join("bin").join("java");
    let jdk = crate::bmc::gaps::jdk_release().unwrap_or_else(|| "of unknown version".into());

    let mut writer = ClassWriter::new(CLASS);
    writer.default_constructor();
    let check_descriptor = format!("({})V", types.iter().map(Type::descriptor).collect::<String>());
    let mut main = CodeBuilder::new();
    // Locals: 0 the arguments array of main, 1 an exception or a result array, 2 a loop index, 3.. the arrays
    // passed to a direct call, one per parameter.
    let first_array_local = 3u16;
    main.max_locals = first_array_local + types.len() as u16 * 2 + 2;
    main.max_stack = 16;

    // The harness's check.
    {
        let (start, end, assertion, any, done) = (main.label(), main.label(), main.label(), main.label(), main.label());
        let locals = references(arguments, types, first_array_local, &mut main, &mut writer);
        main.bind(start);
        pass(arguments, types, &locals, &mut main, &mut writer);
        let check = writer.pool.method_ref(harness_class, crate::harness::METHOD, &check_descriptor);
        main.op_u16(0xb8, check);
        main.bind(end);
        print_line(&mut main, &mut writer, "@check holds");
        main.goto(done);
        main.bind(assertion);
        main.op(0x57); // pop
        print_line(&mut main, &mut writer, "@check refuted");
        main.goto(done);
        main.bind(any);
        main.store(Kind::Ref, 1);
        print(&mut main, &mut writer, "@check threw ");
        print_class_name(&mut main, &mut writer, 1);
        main.bind(done);
        let error = writer.pool.class("java/lang/AssertionError");
        main.handler(start, end, assertion, Some(error));
        main.handler(start, end, any, None);
    }

    for (k, call) in calls.iter().enumerate() {
        let (start, end, thrown, done) = (main.label(), main.label(), main.label(), main.label());
        // Fresh arrays for the call, kept in locals to print what it leaves in them (a null one leaves nothing).
        let locals = references(arguments, types, first_array_local, &mut main, &mut writer);
        let array_locals: Vec<(usize, u16)> = locals.iter().enumerate().filter_map(|(i, l)| l.filter(|_| holds_array(arguments, i)).map(|l| (i, l))).collect();
        main.bind(start);
        pass(arguments, types, &locals, &mut main, &mut writer);
        let m = writer.pool.method_ref(&call.owner, &call.name, &call.descriptor);
        main.op_u16(0xb8, m);
        main.bind(end);
        match &call.ret {
            Type::Void => print_line(&mut main, &mut writer, &format!("@call {k} void")),
            Type::Long => {
                main.store(Kind::Long, 1);
                print(&mut main, &mut writer, &format!("@call {k} value "));
                out(&mut main, &mut writer);
                main.load(Kind::Long, 1);
                let println = writer.pool.method_ref("java/io/PrintStream", "println", "(J)V");
                main.op_u16(0xb6, println);
            }
            Type::Array(element) => {
                main.store(Kind::Ref, 1);
                print(&mut main, &mut writer, &format!("@call {k} array"));
                print_elements(&mut main, &mut writer, 1, element);
            }
            t if t.is_primitive() => {
                main.store(Kind::Int, 1);
                print(&mut main, &mut writer, &format!("@call {k} value "));
                out(&mut main, &mut writer);
                main.load(Kind::Int, 1);
                let println = writer.pool.method_ref("java/io/PrintStream", "println", "(I)V");
                main.op_u16(0xb6, println);
            }
            _ => {
                main.op(0x57);
                print_line(&mut main, &mut writer, &format!("@call {k} object"));
            }
        }
        main.goto(done);
        main.bind(thrown);
        main.store(Kind::Ref, 1);
        print(&mut main, &mut writer, &format!("@call {k} threw "));
        print_class_name(&mut main, &mut writer, 1);
        // The message on a line of its own, after a marker: `@message` and the text, or `@nomessage`.
        let (none, printed) = (main.label(), main.label());
        main.load(Kind::Ref, 1);
        let message = writer.pool.method_ref("java/lang/Throwable", "getMessage", "()Ljava/lang/String;");
        main.op_u16(0xb6, message);
        main.store(Kind::Ref, 2);
        main.load(Kind::Ref, 2);
        main.if_null(none);
        print(&mut main, &mut writer, "@message ");
        out(&mut main, &mut writer);
        main.load(Kind::Ref, 2);
        let println = writer.pool.method_ref("java/io/PrintStream", "println", "(Ljava/lang/String;)V");
        main.op_u16(0xb6, println);
        main.goto(printed);
        main.bind(none);
        print_line(&mut main, &mut writer, "@nomessage");
        main.bind(printed);
        main.bind(done);
        main.handler(start, end, thrown, None);
        // What the call left in each array, whether it returned or threw.
        for (i, local) in &array_locals {
            let Type::Array(element) = &types[*i] else { unreachable!() };
            print(&mut main, &mut writer, &format!("@left {k} {i}"));
            print_elements(&mut main, &mut writer, *local, element);
        }
    }
    print_line(&mut main, &mut writer, "@end");
    main.return_(None);
    writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "main".into(), descriptor: "([Ljava/lang/String;)V".into(), code: Some(main) });

    let _ = std::fs::remove_dir_all(dir);
    std::fs::create_dir_all(dir).map_err(|e| format!("cannot write the JVM run into {}: {e}", dir.display()))?;
    std::fs::write(dir.join(format!("{CLASS}.class")), writer.to_bytes()).map_err(|e| format!("cannot write the JVM run: {e}"))?;
    let absolute = |p: &Path| std::path::absolute(p).unwrap_or_else(|_| p.to_path_buf());
    let mut class_path = vec![absolute(dir)];
    if open_classes(&dir.join(OPENED), harness_class, calls, entries)? {
        class_path.push(absolute(&dir.join(OPENED)));
    }
    class_path.extend(entries.iter().map(|e| absolute(e)));
    let class_path = std::env::join_paths(&class_path).map_err(|e| format!("a class path entry cannot be joined: {e}"))?;
    let stdout = std::fs::File::create(dir.join("stdout")).map_err(|e| e.to_string())?;
    let stderr = std::fs::File::create(dir.join("stderr")).map_err(|e| e.to_string())?;
    let mut child = Command::new(&java)
        .args(["-Xmx256m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-XX:-UsePerfData", "-cp"])
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
            return Err(format!("the JVM run did not finish within {} s", TIMEOUT.as_secs()));
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    let text = std::fs::read_to_string(dir.join("stdout")).unwrap_or_default();
    if !text.lines().any(|l| l == "@end") {
        let err = std::fs::read_to_string(dir.join("stderr")).unwrap_or_default();
        let tail: Vec<&str> = err.lines().rev().take(3).collect();
        return Err(format!("the JVM run stopped before its end{}", if tail.is_empty() { String::new() } else { format!(": {}", tail.into_iter().rev().collect::<Vec<_>>().join(" / ")) }));
    }
    parse(&text, jdk, types, slots, calls)
}

/// The directory, under the run's, of the application classes it loads opened.
const OPENED: &str = "opened";

/// Writes into `out` an opened copy ([`crate::relocate::opened`]) of every application class the harness names and
/// of each direct call's owner, as the first of `entries` that has it holds it, so that the harness, a class of
/// the unnamed package, may read their fields and call their constructors on a JVM as it does in the checker,
/// which doesn't check access: a record's fields are private, and a class's are often package-private. JDK
/// classes are never copied: they aren't in `entries`. Returns whether it wrote any.
fn open_classes(out: &Path, harness_class: &str, calls: &[DirectCall], entries: &[PathBuf]) -> Result<bool, String> {
    let find = |name: &str| entries.iter().map(|e| e.join(format!("{name}.class"))).find(|p| p.is_file());
    let Some(harness) = find(harness_class) else { return Ok(false) };
    let bytes = std::fs::read(&harness).map_err(|e| format!("cannot read {}: {e}", harness.display()))?;
    let mut names = crate::relocate::referenced_classes(&bytes).map_err(|e| format!("cannot read {}: {e}", harness.display()))?;
    names.extend(calls.iter().map(|c| c.owner.clone()));
    names.sort();
    names.dedup();
    let mut wrote = false;
    for name in names.iter().filter(|n| n.as_str() != harness_class) {
        let Some(path) = find(name) else { continue };
        let bytes = std::fs::read(&path).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
        let opened = crate::relocate::opened(&bytes).map_err(|e| format!("cannot open {name} for the JVM run: {e}"))?;
        let target = out.join(format!("{name}.class"));
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        std::fs::write(&target, opened).map_err(|e| e.to_string())?;
        wrote = true;
    }
    Ok(wrote)
}

/// Reads the run's lines.
fn parse(text: &str, jdk: String, types: &[Type], slots: &[u16], calls: &[DirectCall]) -> Result<Run, String> {
    let mut check = None;
    let mut replayed: Vec<Replayed> = calls.iter().map(|_| Replayed { outcome: "<not run>".into(), returned: None, result_array: None, result_fields: None, arrays_after: Vec::new(), objects_after: Vec::new(), thrown: None, references: Vec::new(), views: Vec::new(), category: None, result_paths: Default::default(), object_paths: Vec::new() }).collect();
    let mut message_of: Option<usize> = None;
    for line in text.lines() {
        if let Some(rest) = line.strip_prefix("@check ") {
            check = Some(match rest {
                "holds" => Check::Holds,
                "refuted" => Check::Refuted,
                other => Check::Threw(other.strip_prefix("threw ").unwrap_or(other).to_string()),
            });
            message_of = None;
        } else if let Some(rest) = line.strip_prefix("@call ") {
            let mut parts = rest.splitn(3, ' ');
            let k: usize = parts.next().and_then(|k| k.parse().ok()).ok_or_else(|| format!("unreadable line {line}"))?;
            let kind = parts.next().unwrap_or_default();
            let value = parts.next().unwrap_or_default();
            let r = replayed.get_mut(k).ok_or_else(|| format!("unreadable line {line}"))?;
            message_of = None;
            match kind {
                "void" => r.outcome = "void".into(),
                "object" => r.outcome = "<an object>".into(),
                "value" => {
                    let v = match calls[k].ret {
                        Type::Long => Value::Long(value.parse().map_err(|_| format!("unreadable line {line}"))?),
                        _ => Value::Int(value.parse().map_err(|_| format!("unreadable line {line}"))?),
                    };
                    r.outcome = crate::interp::render::primitive(v, &calls[k].ret);
                    r.returned = Some(v);
                }
                "array" => {
                    let Type::Array(element) = &calls[k].ret else { return Err(format!("unreadable line {line}")) };
                    let data = elements(value, element)?;
                    r.outcome = crate::witness::array(&data, element);
                    r.result_array = Some(data);
                }
                "threw" => {
                    let internal = value.replace('.', "/");
                    r.outcome = format!("throws {}", crate::classfile::simple_name_of(&internal));
                    r.thrown = Some(internal);
                    message_of = Some(k);
                }
                _ => return Err(format!("unreadable line {line}")),
            }
        } else if let Some(rest) = line.strip_prefix("@left ") {
            let mut parts = rest.splitn(3, ' ');
            let (Some(Ok(k)), Some(Ok(i))) = (parts.next().map(str::parse::<usize>), parts.next().map(str::parse::<usize>)) else { return Err(format!("unreadable line {line}")) };
            let Some(Type::Array(element)) = types.get(i) else { return Err(format!("unreadable line {line}")) };
            let data = elements(parts.next().unwrap_or_default(), element)?;
            replayed[k].arrays_after.push((slots[i], data));
            message_of = None;
        } else if let Some(text) = line.strip_prefix("@message ") {
            if let Some(k) = message_of {
                let r = &mut replayed[k];
                // As the interpreter renders it, but an NPE's message, which the interpreter has none of.
                if r.thrown.as_deref() != Some("java/lang/NullPointerException") {
                    r.outcome = format!("{}({})", r.outcome, crate::interp::render::quote(text));
                }
            }
        } else if line == "@nomessage" || line == "@end" {
            message_of = None;
        } else if let Some(k) = message_of {
            // A message of several lines goes on.
            let r = &mut replayed[k];
            if r.outcome.ends_with("\")") {
                r.outcome.truncate(r.outcome.len() - 2);
                let quoted = crate::interp::render::quote(line);
                r.outcome = format!("{}\\n{}\")", r.outcome, &quoted[1..quoted.len() - 1]);
            }
        }
    }
    Ok(Run { jdk, check: check.ok_or("the JVM run printed no outcome of the harness")?, calls: replayed })
}

fn elements(text: &str, element: &Type) -> Result<Vec<Value>, String> {
    text.split_whitespace()
        .map(|v| match element {
            Type::Long => v.parse().map(Value::Long),
            _ => v.parse().map(Value::Int),
        })
        .collect::<Result<_, _>>()
        .map_err(|_| format!("unreadable elements {text}"))
}

/// `getstatic System.out`.
fn out(code: &mut CodeBuilder, writer: &mut ClassWriter) {
    let field = writer.pool.field_ref("java/lang/System", "out", "Ljava/io/PrintStream;");
    code.op_u16(0xb2, field);
}

fn print(code: &mut CodeBuilder, writer: &mut ClassWriter, text: &str) {
    out(code, writer);
    let s = writer.pool.string(text);
    code.ldc(s);
    let print = writer.pool.method_ref("java/io/PrintStream", "print", "(Ljava/lang/String;)V");
    code.op_u16(0xb6, print);
}

fn print_line(code: &mut CodeBuilder, writer: &mut ClassWriter, text: &str) {
    out(code, writer);
    let s = writer.pool.string(text);
    code.ldc(s);
    let println = writer.pool.method_ref("java/io/PrintStream", "println", "(Ljava/lang/String;)V");
    code.op_u16(0xb6, println);
}

/// Prints the class name of the throwable in `local`, and a line's end.
fn print_class_name(code: &mut CodeBuilder, writer: &mut ClassWriter, local: u16) {
    out(code, writer);
    code.load(Kind::Ref, local);
    let get_class = writer.pool.method_ref("java/lang/Object", "getClass", "()Ljava/lang/Class;");
    code.op_u16(0xb6, get_class);
    let get_name = writer.pool.method_ref("java/lang/Class", "getName", "()Ljava/lang/String;");
    code.op_u16(0xb6, get_name);
    let println = writer.pool.method_ref("java/io/PrintStream", "println", "(Ljava/lang/String;)V");
    code.op_u16(0xb6, println);
}

/// Prints ` e0 e1 ...` for the array in `local`, each element as a number (a char as its code unit, a boolean as
/// 0 or 1), and a line's end.
fn print_elements(code: &mut CodeBuilder, writer: &mut ClassWriter, local: u16, element: &Type) {
    let index = 2u16;
    let (head, end): (Label, Label) = (code.label(), code.label());
    code.iconst(0);
    code.store(Kind::Int, index);
    code.bind(head);
    code.load(Kind::Int, index);
    code.load(Kind::Ref, local);
    code.op(0xbe); // arraylength
    code.if_icmp(Cond::Ge, end);
    print(code, writer, " ");
    out(code, writer);
    code.load(Kind::Ref, local);
    code.load(Kind::Int, index);
    let (load, descriptor) = match element {
        Type::Boolean | Type::Byte => (0x33, "(I)V"),
        Type::Char => (0x34, "(I)V"),
        Type::Short => (0x35, "(I)V"),
        Type::Long => (0x2f, "(J)V"),
        _ => (0x2e, "(I)V"),
    };
    code.op(load);
    let p = writer.pool.method_ref("java/io/PrintStream", "print", descriptor);
    code.op_u16(0xb6, p);
    code.iinc(index, 1);
    code.goto(head);
    code.bind(end);
    out(code, writer);
    let println = writer.pool.method_ref("java/io/PrintStream", "println", "()V");
    code.op_u16(0xb6, println);
}

/// Makes the arguments that are references, each into a local of its own from `first`: a new array, null, or the
/// array an earlier argument is. `None` for a primitive.
fn references(arguments: &[Argument], types: &[Type], first: u16, code: &mut CodeBuilder, writer: &mut ClassWriter) -> Vec<Option<u16>> {
    let mut locals: Vec<Option<u16>> = Vec::new();
    for (i, (a, t)) in arguments.iter().zip(types).enumerate() {
        let local = first + i as u16;
        match a {
            Argument::Scalar(_) => {
                locals.push(None);
                continue;
            }
            Argument::Same(j) => match locals.get(*j).copied().flatten() {
                Some(earlier) => code.load(Kind::Ref, earlier),
                None => code.op(0x01),
            },
            _ => push(a, t, code, writer),
        }
        code.store(Kind::Ref, local);
        locals.push(Some(local));
    }
    locals
}

/// Whether argument `i` is an array, its own or an earlier argument's, rather than null.
fn holds_array(arguments: &[Argument], i: usize) -> bool {
    match arguments.get(i) {
        Some(Argument::Array(_)) => true,
        Some(Argument::Same(j)) => holds_array(arguments, *j),
        _ => false,
    }
}

/// Passes the arguments: each primitive as a constant, each reference from its local ([`references`]).
fn pass(arguments: &[Argument], types: &[Type], locals: &[Option<u16>], code: &mut CodeBuilder, writer: &mut ClassWriter) {
    for (i, (a, t)) in arguments.iter().zip(types).enumerate() {
        match locals[i] {
            Some(local) => code.load(Kind::Ref, local),
            None => push(a, t, code, writer),
        }
    }
}

/// Pushes an argument: a constant, a new array of constants, or null.
fn push(a: &Argument, t: &Type, code: &mut CodeBuilder, writer: &mut ClassWriter) {
    match (a, t) {
        (Argument::Scalar(v), t) => push_scalar(*v, t, code, writer),
        (Argument::Array(items), Type::Array(element)) => {
            code.iconst(items.len() as i32);
            let (atype, store) = match element.as_ref() {
                Type::Boolean => (4, 0x54),
                Type::Char => (5, 0x55),
                Type::Byte => (8, 0x54),
                Type::Short => (9, 0x56),
                Type::Long => (11, 0x50),
                _ => (10, 0x4f),
            };
            code.op_u8(0xbc, atype);
            for (k, item) in items.iter().enumerate() {
                code.op(0x59);
                code.iconst(k as i32);
                push_scalar(*item, element, code, writer);
                code.op(store);
            }
        }
        _ => code.op(0x01), // aconst_null
    }
}

fn push_scalar(v: Value, t: &Type, code: &mut CodeBuilder, writer: &mut ClassWriter) {
    let wide = match v {
        Value::Long(x) => x,
        Value::Int(x) => i64::from(x),
        _ => 0,
    };
    if *t == Type::Long {
        match wide {
            0 => code.op(0x09),
            1 => code.op(0x0a),
            _ => {
                let c = writer.pool.long(wide);
                code.ldc2(c);
            }
        }
    } else {
        let x = wide as i32;
        if (-32768..=32767).contains(&x) {
            code.iconst(x);
        } else {
            let c = writer.pool.integer(x);
            code.ldc(c);
        }
    }
}
