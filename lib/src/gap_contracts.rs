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
//! | `assert:` | what holds when it returns: over the parameters and the arrays it modifies; for a call that returns an object, which object (`result == this`, `result == <parameter>`, `result == null`, or `\fresh(result)` for a new one) | `true` if absent, required for an object result |
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
//! Every contract the engine applies is `trusted` here: nothing checks it yet against the JDK's bytecode or a JVM
//! (step 3c), and the verdict says that it rests on it.
//!
//! The engine applies a contract by calling a method of a class generated here, [`CLASS`], with the call's
//! arguments (and its receiver, for a method that may return it): a branch per throws clause that throws, a
//! choice of new values for each array it modifies, the assertion as a condition the path must meet, and the
//! result. Three calls of [`INTRINSICS`] mean what bytecode cannot say: `open(int)` (the gap of contract `int` is
//! met: an input outside `assume:`), `havoc(Object)` (the array's elements become fresh values) and
//! `infeasible()` (no run of the JDK's call takes this path, as the assertion says).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::bmc::gaps::{self, Closing, Closure, ContractUse, Gap, GapKind, JdkCall};
use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};
use crate::classfile::{flags, Cond, Kind, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::harness::expr::{self, Param};
use crate::Error;

/// The generated class whose methods apply the contracts.
pub const CLASS: &str = "GapContracts";
/// The class of the engine's intrinsics the generated methods call; it exists on no class path.
pub const INTRINSICS: &str = "jvmcontract/GapIntrinsics";

/// How a contract is backed: what checked it. Only `trusted` for now: step 3c adds `proved` (against the JDK's
/// bytecode) and `tested` (on a real JVM).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Evidence {
    /// Nothing has checked it: the verdict rests on whoever wrote it.
    Trusted,
}

impl Evidence {
    pub fn name(self) -> &'static str {
        match self {
            Evidence::Trusted => "trusted",
        }
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
    pub line: usize,
    /// What it states, in a line: `throws java.lang.IllegalArgumentException when capacity < 0; modifies nothing`.
    pub summary: String,
    pub written_by: String,
    pub evidence: Evidence,
}

/// A contract the engine cannot apply, and why: its gap stays open.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Refused {
    pub id: String,
    pub line: usize,
    pub reason: String,
}

/// A contracts file, read and checked against the class path the proof runs on.
#[derive(Debug, Clone, Default)]
pub struct Loaded {
    pub file: PathBuf,
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
    let kind = match kind {
        "jdk-constructor" => GapKind::JdkConstructor,
        "jdk-void-method" => GapKind::JdkVoidMethod,
        "jdk-reference-method" => GapKind::JdkReferenceMethod,
        "class-initializer" => GapKind::ClassInitializer,
        "string-conversion" => GapKind::StringConversion,
        _ => return None,
    };
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

/// Reads the contracts in `file` and checks each against the class path `cp` the proof runs on, under the JDK
/// `jdk`: each is accepted, with how the engine applies it, or refused with the reason.
pub fn load(file: &Path, cp: &ClassPath, jdk: Option<&str>) -> Result<Loaded, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("cannot read the contracts in {}: {e}", file.display())))?;
    let blocks = parse(&text, &file.display().to_string())?;
    let mut loaded = Loaded { file: file.to_path_buf(), ..Loaded::default() };
    let mut writer = ClassWriter::new(CLASS);
    writer.source_file = Some(file.file_name().map(|f| f.to_string_lossy().into_owned()).unwrap_or_default());
    for block in &blocks {
        let index = loaded.accepted.len();
        match accept(block, cp, jdk, index, &mut writer) {
            Ok((gap, closing, summary)) => {
                if loaded.closed.contains_key(&gap) {
                    loaded.refused.push(Refused { id: block.id.clone(), line: block.line, reason: "a second contract for the gap: the first one stands".into() });
                    continue;
                }
                let written_by = block.value("written-by").unwrap_or_default().to_string();
                let contract = ContractUse { summary: summary.clone(), written_by: written_by.clone(), evidence: Evidence::Trusted, file: file.display().to_string(), line: block.line, index };
                loaded.closed.insert(gap, Closure { how: closing, contract });
                loaded.accepted.push(Accepted { id: block.id.clone(), line: block.line, summary, written_by, evidence: Evidence::Trusted });
            }
            Err(reason) => loaded.refused.push(Refused { id: block.id.clone(), line: block.line, reason }),
        }
    }
    if !writer.methods.is_empty() {
        loaded.class = Some(writer.to_bytes());
    }
    Ok(loaded)
}

/// Why `--contracts` is refused under a gap mode other than advised.
pub const CONTRACTS_NEED_ADVISED: &str = "--contracts needs --gaps advised: under strict a gap is refused whatever its contract, and under assume it is approximated";

/// The gap setting a proof driver runs the tool's own checker with: the mode, and under advised the contracts in
/// `file`, read against the class path `entries` (with the tool's models when `models`), with the class that
/// applies them written into `work/contracts`. Returns the contracts as read, and a note line for each refused.
pub fn setting(mode: gaps::GapMode, file: Option<&Path>, entries: &[PathBuf], models: bool, work: &Path) -> Result<(gaps::GapSetting, Option<Loaded>, String), Error> {
    let mut setting = gaps::GapSetting::from(mode);
    let Some(file) = file else { return Ok((setting, None, String::new())) };
    if mode != gaps::GapMode::Advised {
        return Err(Error::new(CONTRACTS_NEED_ADVISED));
    }
    let cp = crate::witness::classpath(entries.iter().map(PathBuf::as_path))?.with_models(models);
    let loaded = load(file, &cp, gaps::jdk_release().as_deref())?;
    if let Some(bytes) = &loaded.class {
        let dir = work.join("contracts");
        std::fs::create_dir_all(&dir)?;
        std::fs::write(dir.join(format!("{CLASS}.class")), bytes)?;
        setting.class_dir = Some(dir);
    }
    setting.contracts = std::sync::Arc::new(loaded.closed.clone());
    let mut notes = String::new();
    for r in &loaded.refused {
        notes.push_str(&format!("note: the contract for {} ({}:{}) is refused, and its gap stays open: {}\n", r.id, file.display(), r.line, r.reason));
    }
    Ok((setting, Some(loaded), notes))
}

/// The words for a reference result's forms, in a refusal.
const RESULT_FORMS: &str = "`result == this`, `result == <parameter>`, `result == null`, or `\\fresh(result)` for a new object";

/// Checks one block, and writes the method that applies it into `writer`; the reason it is refused otherwise.
fn accept(block: &Block, cp: &ClassPath, jdk: Option<&str>, index: usize, writer: &mut ClassWriter) -> Result<(Gap, Closing, String), String> {
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
    let of_the_jdk = matches!(gap.kind, GapKind::JdkConstructor | GapKind::JdkVoidMethod | GapKind::JdkReferenceMethod);
    if of_the_jdk {
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
        GapKind::ClassInitializer => return initializer(block, gap, modifies),
        _ => {}
    }
    match gaps::jdk_instance_call(cp, &gap.owner, &gap.name, &gap.descriptor) {
        JdkCall::Gap(kind) if kind == gap.kind => {}
        JdkCall::Gap(kind) => return Err(format!("the call is a gap of kind {}, not {}", kind.name(), gap.kind.name())),
        JdkCall::Exact => return Err("the tool's own checker reproduces the call exactly: it is no gap".into()),
        JdkCall::Refused => return Err("the tool's own checker refuses the call whatever a contract says (a JDK method with a primitive result)".into()),
    }

    // The method's locals: the receiver (for a method, which may return it), then the parameters.
    let receiver = gap.kind != GapKind::JdkConstructor;
    let mut slot: u16 = u16::from(receiver);
    let mut params = Vec::new();
    for (name, t) in names.iter().zip(&descriptor.params) {
        if expr::ty_of(t).is_some() || expr::element_ty(t).is_some() {
            params.push(Param { name: name.clone(), ty: t.clone(), slot });
        }
        slot += t.slots();
    }
    let first_free = slot;
    let condition = |text: &str, what: &str| -> Result<expr::Expr, String> {
        if mentions_word(text, "this") {
            return Err(format!("{what} names `this`: the tool's own checker keeps no state of a JDK object, so a condition cannot read it"));
        }
        if text.contains("\\old") {
            return Err(format!("{what} uses \\old, which the tool's own checker does not apply yet: state what holds after the call alone"));
        }
        expr::parse_in(text, &params, None, first_free).map_err(|e| {
            let other = names.iter().zip(&descriptor.params).find(|(n, t)| mentions_word(text, n) && !params.iter().any(|p| &p.name == *n) && !t.is_primitive());
            match other {
                Some((n, t)) => format!("{what} names {n}, a {}: a condition reads parameters of a primitive type and arrays of them", t.java_name()),
                None => format!("{what}: {e}"),
            }
        })
    };
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
        (t, _) => return Err(format!("the call returns {}, which the tool's own checker does not take from a contract yet", t.java_name())),
    };
    let after = match (&result, assert) {
        (None, Some(a)) => Some(condition(a, "`assert:`")?),
        _ => None,
    };

    // The method.
    let mut code = CodeBuilder::new();
    let ret_kind = if result.is_some() { Some(Kind::Ref) } else { None };
    let give_up = |code: &mut CodeBuilder| match ret_kind {
        Some(_) => {
            code.op(0x01); // aconst_null
            code.return_(Some(Kind::Ref));
        }
        None => code.return_(None),
    };
    let mut slots_used = first_free;
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
        None => {}
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
    Ok((gap, Closing::Stub { method, descriptor: method_descriptor, receiver }, summary.join("; ")))
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
enum ResultForm {
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
        let (_, closing, summary) = accept(&block(&format!("{head}{ok}  throws: IllegalArgumentException when n < 0\n")), &cp, Some("25"), 0, &mut writer).unwrap();
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
        let (_, closing, _) = accept(&block(&format!("{append}  assert: result == this\n")), &cp, Some("25"), 3, &mut writer).unwrap();
        assert!(matches!(&closing, Closing::Stub { method, descriptor, receiver: true } if method == "c3" && descriptor == "(Ljava/lang/Object;I)Ljava/lang/StringBuilder;"), "{closing:?}");

        let clinit = "class-initializer:p.Boom.<clinit>()V\n  call: p.Boom.<clinit>()\n  written-by: a test\n";
        let mut writer = ClassWriter::new(CLASS);
        assert!(matches!(accept(&block(&format!("{clinit}  modifies: nothing\n")), &cp, Some("25"), 0, &mut writer).unwrap().1, Closing::Initialised));
        assert!(refusal(&format!("{clinit}  modifies: nothing\n  throws: IllegalStateException when true\n")).contains("only when it throws nothing"));
        assert!(refusal(&format!("{clinit}  modifies: p.Boom.state\n")).contains("modifies nothing"));
        assert!(refusal("string-conversion:p.Item.toString()Ljava/lang/String;\n  call: p.Item.toString()\n  modifies: nothing\n  written-by: a test\n").contains("string concatenation"));
    }
}
