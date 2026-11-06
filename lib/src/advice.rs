//! The gap protocol of `--gaps advised` (step 3a of `llm-dlc/loops/sound-verdicts.md`): the tool hands the agent
//! driving it exactly the gaps it cannot close, before it solves anything, with what a contract for each must state.
//!
//! A proof driver under advised builds its harness as under any mode, then scans what the tool's own checker would
//! run, the harness and every method it may reach ([`crate::bmc::gaps::scan`]), on the class path the engine is
//! given. No solver runs. A gap the scan finds with no contract stops the run: the verdict is unverifiable, with the
//! finding `gaps-need-contracts`, and the outcome's `advice` ([`Advice`]) lists each gap with
//!
//! - its stable id (kind, member, descriptor, and the JDK's version for a JDK call), which a contract is filed under;
//! - the call as Java writes it, its parameters with their names and types, its result type, and where it is made;
//! - the claim it stands in the way of, and the harness that states it;
//! - what `--gaps assume` would take it to do, which is what a contract replaces;
//! - what a contract must state ([`Obligation`]): the result, the exceptions and when each is thrown, the effects on
//!   the receiver and on the arguments, and whether it has any other;
//! - a template in the contract format ([`template`]), with a `TODO` for each of those.
//!
//! It also lists what the engine refuses whatever the contracts say (floating point, a static JDK method it does not
//! model, ...), since a contract does not bring those into its fragment. With no gap, the run goes on as under
//! `--gaps strict`: advised is strict given no contracts, and the engine refuses a gap the scan did not see.
//!
//! The template is the format `--contracts` reads ([`crate::gap_contracts`]), built on the property syntax of
//! `prove`: a block per gap headed by its id, with `call:` (naming the parameters), `assume:` (the inputs the
//! contract is about), `throws: <exception> when <condition>` (as in a property), `assert:` (what holds after the
//! call: of the arrays it modifies, or which object it returns), `modifies:` (`nothing`, `this`, or a parameter),
//! and `written-by:`. With `--contracts`, a gap whose contract the engine accepts no longer stops the run, and the
//! advice lists the gaps still open, each with the reason its contract was refused if it was.
//!
//! The agent is whoever drives the tool. The library calls no model and holds no keys: it returns data and stops.

use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::bmc::gaps::{self, Gap, GapKind, Refusal};
use crate::classfile::{MemberRef, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::Error;

/// What a run under `--gaps advised` returns when it reaches gaps it has no contract for.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Advice {
    /// `contracts-needed`: the run stopped before solving, and a contract for each gap lets it go on.
    pub status: String,
    /// The claim the gaps stand in the way of.
    pub claim: Claim,
    /// The JDK the gaps of JDK members are about, from its `release` file; a contract is checked against it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub jdk: Option<String>,
    pub gaps: Vec<GapAdvice>,
    /// The gaps the proof reaches that a contract closes (`--contracts`), by id.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub closed: Vec<String>,
    /// What the engine refuses whatever the contracts say, with the first member and site of each kind and how
    /// many sites: a contract does not bring these into its fragment.
    #[serde(skip_serializing_if = "BTreeMap::is_empty")]
    pub outside: BTreeMap<String, Refusal>,
    /// Every gap's template in one file, for the agent to fill in.
    pub template: String,
    /// Where the template was written, in the work directory.
    pub template_file: PathBuf,
    /// The checker whose gaps they are: `jbmc` when JBMC's goto program named them ([`crate::jbmc_contracts`]),
    /// absent for the tool's own checker's.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checker: Option<String>,
}

/// The claim a run under advised was asked to prove.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Claim {
    /// `property` or `regression`.
    pub kind: String,
    /// `pkg.Class#method`.
    pub target: String,
    /// The claim in words, as the verdict would state it.
    pub text: String,
    /// The harness that states it, as Java.
    pub harness: PathBuf,
}

/// One gap, with what an agent needs to write a contract for it.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct GapAdvice {
    /// The stable id the contract is filed under.
    pub id: String,
    pub kind: GapKind,
    /// The call as Java writes it: `java.util.ArrayList.<init>(int)`.
    pub call: String,
    /// The class, as Java names it.
    pub owner: String,
    /// The method (`<init>` for a constructor, `<clinit>` for a class's initializer).
    pub name: String,
    /// The JVM descriptor.
    pub descriptor: String,
    /// The parameters, named as the class file names them (`arg0` ... when it does not).
    pub parameters: Vec<Parameter>,
    /// The result's type as Java writes it, `void` for none.
    pub returns: String,
    /// Where the code the proof reaches makes the call, `pkg.Class.method:line`.
    pub sites: Vec<String>,
    /// What `--gaps assume` would take the call to do: what a contract replaces.
    pub assumed: String,
    /// What a contract for the call must state.
    pub must_state: Vec<Obligation>,
    /// The call's block of the template.
    pub template: String,
    /// Why the contract the agent gave for the gap was refused (`--contracts`), with where it is.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub refused_contract: Option<String>,
    /// The inputs on which a JVM refutes the contract given for the gap, when that is why it was refused.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub counterexamples: Vec<crate::gap_contracts::Counterexample>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Parameter {
    pub name: String,
    /// As Java writes it.
    #[serde(rename = "type")]
    pub ty: String,
}

/// One thing a contract must state, and the question it answers.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Obligation {
    pub part: Part,
    pub question: String,
}

/// The parts of a call's behaviour a contract states (step 3b of the brief).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Part {
    /// What it returns.
    Result,
    /// What it throws, and on which arguments.
    Exceptions,
    /// What it changes of the object it is called on, or constructs.
    Receiver,
    /// What it changes of an object or array passed to it.
    Arguments,
    /// The static state a class's initializer sets.
    State,
    /// Whether it has any effect beyond those.
    Purity,
}

/// Scans what the tool's own checker would run of the harness `class.method`, on the class path `entries` (the
/// engine's, with the tool's models when `models`): the class path, and every gap it may reach.
pub fn scan_harness(entries: &[PathBuf], models: bool, class: &str, method: &str) -> Result<(ClassPath, gaps::Scan), Error> {
    let cp = crate::witness::classpath(entries.iter().map(PathBuf::as_path))?.with_models(models);
    let harness = cp.application(class)?.ok_or_else(|| Error::new(format!("the harness class {class} is not on the class path")))?;
    let check = harness.methods.iter().find(|m| m.name == method).ok_or_else(|| Error::new(format!("the harness has no method {method}")))?;
    let scan = gaps::scan(&cp, &[MemberRef::new(class, method, &check.descriptor)])?;
    Ok((cp, scan))
}

/// The advice when the harness's `scan` ([`scan_harness`]) reaches a gap that none of `contracts` closes; none when
/// the proof can go on. The template, of the gaps still open, is written to `work/contracts.template`. `checker` is
/// `jbmc` when the gaps are JBMC's ([`crate::jbmc_contracts`]), none for the tool's own checker's.
pub fn preflight(cp: &ClassPath, scan: &gaps::Scan, claim: Claim, work: &Path, contracts: Option<&crate::gap_contracts::Loaded>, checker: Option<&str>) -> Result<Option<Advice>, Error> {
    let jdk = scan.jdk.clone();
    let is_closed = |g: &Gap| contracts.is_some_and(|c| c.closed.contains_key(g));
    let closed: Vec<String> = scan.gaps.keys().filter(|g| is_closed(g)).map(|g| g.id(jdk.as_deref())).collect();
    let open: Vec<(&Gap, &std::collections::BTreeSet<gaps::Site>)> = scan.gaps.iter().filter(|(g, _)| !is_closed(g)).collect();
    if open.is_empty() {
        return Ok(None);
    }
    let advised: Vec<GapAdvice> = open
        .into_iter()
        .map(|(gap, sites)| {
            let mut a = advise(cp, gap, sites.iter().map(gaps::Site::display).collect(), jdk.as_deref());
            if let Some(r) = contracts.and_then(|c| c.refusal(&a.id)) {
                a.refused_contract = Some(format!("{} ({}:{})", r.reason, r.file, r.line));
                a.counterexamples = r.testing.as_ref().map(|t| t.counterexamples.clone()).unwrap_or_default();
            }
            a
        })
        .collect();
    let template = template(&advised, jdk.as_deref(), checker);
    let template_file = work.join("contracts.template");
    std::fs::write(&template_file, &template)?;
    Ok(Some(Advice { status: "contracts-needed".into(), claim, jdk, gaps: advised, closed, outside: scan.refused.clone(), template, template_file, checker: checker.map(str::to_string) }))
}

/// The advice for one gap.
pub fn advise(cp: &ClassPath, gap: &Gap, sites: Vec<String>, jdk: Option<&str>) -> GapAdvice {
    let (params, returns) = match MethodDescriptor::parse(&gap.descriptor) {
        Ok(d) => (d.params, d.ret),
        Err(_) => (Vec::new(), Type::Void),
    };
    let names = cp.bytecode_method(&gap.owner, &gap.name, &gap.descriptor).map(|(cf, m)| m.parameter_names(&cf.pool)).filter(|n| n.len() == params.len()).unwrap_or_else(|| (0..params.len()).map(|i| format!("arg{i}")).collect());
    let parameters: Vec<Parameter> = names.into_iter().zip(&params).map(|(name, t)| Parameter { name, ty: t.java_name() }).collect();
    let mut advice = GapAdvice {
        id: gap.id(jdk),
        kind: gap.kind,
        call: gap.call(),
        owner: gap.owner.replace('/', "."),
        name: gap.name.clone(),
        descriptor: gap.descriptor.clone(),
        parameters,
        returns: returns.java_name(),
        sites,
        assumed: gap.kind.approximation().to_string(),
        must_state: obligations(gap.kind, &params, &returns),
        template: String::new(),
        refused_contract: None,
        counterexamples: Vec::new(),
    };
    advice.template = block(&advice);
    advice
}

/// What a contract for a gap of `kind`, with these parameter types and result, must state.
fn obligations(kind: GapKind, params: &[Type], returns: &Type) -> Vec<Obligation> {
    let o = |part, question: &str| Obligation { part, question: question.to_string() };
    let references = params.iter().any(|t| matches!(t, Type::Object(_) | Type::Array(_)));
    let mut out = Vec::new();
    match kind {
        GapKind::JdkConstructor => {
            out.push(o(Part::Exceptions, "Which exceptions does it throw, and on which arguments? (none, or `throws: <exception> when <condition>` for each)"));
            out.push(o(Part::Receiver, "What does the new object keep of its arguments that a later call on it reads? (a later call on it is a gap of its own)"));
        }
        GapKind::JdkVoidMethod => {
            out.push(o(Part::Exceptions, "Which exceptions does it throw, and on which arguments and states of the receiver?"));
            out.push(o(Part::Receiver, "How does it change the object it is called on? (`modifies: this`, and what holds after it, or nothing)"));
        }
        GapKind::JdkReferenceMethod => {
            out.push(o(Part::Result, "What does it return: may it be null, is it the receiver or an argument, or a new object? (`assert:` over `result`)"));
            out.push(o(Part::Exceptions, "Which exceptions does it throw, and on which arguments and states of the receiver?"));
            out.push(o(Part::Receiver, "Does it change the object it is called on? (`modifies: this`, or nothing)"));
        }
        GapKind::StringConversion => {
            out.push(o(Part::Result, "What does this class's toString return: may it be null? (`assert:` over `result`)"));
            out.push(o(Part::Exceptions, "Does it throw, and when?"));
            out.push(o(Part::Receiver, "Does it change the object it is called on?"));
        }
        GapKind::ClassInitializer => {
            out.push(o(Part::Exceptions, "Does the initializer throw? (the class's first use then throws ExceptionInInitializerError, and every later use NoClassDefFoundError)"));
            out.push(o(Part::State, "Which static fields does it set, and to what?"));
        }
        GapKind::JdkPrimitiveMethod => {
            out.push(o(Part::Result, "What does it return, as a condition over the arguments and `result`? (`assert: 0 <= result && result < bound`; the receiver's state is not kept, so not over `this`)"));
            out.push(o(Part::Exceptions, "Which exceptions does it throw, and on which arguments and states of the receiver?"));
            out.push(o(Part::Receiver, "Does it change the object it is called on? (`modifies: this`, or nothing)"));
        }
        GapKind::JdkStaticMethod => {
            match returns {
                Type::Void => {}
                Type::Object(_) => out.push(o(Part::Result, "What does it return: null, an argument, or a new object? (`assert:` over `result`)")),
                _ => out.push(o(Part::Result, "What does it return, as a condition over the arguments and `result`? (`assert: 0 <= result && result <= 32`)")),
            }
            out.push(o(Part::Exceptions, "Which exceptions does it throw, and on which arguments?"));
        }
        // JBMC's (crate::jbmc_gaps), which JBMC applies no contract for yet: what one would state.
        GapKind::MissingBody => {
            if *returns != Type::Void {
                out.push(o(Part::Result, "What does it return, as a condition over the arguments and `result`?"));
            }
            out.push(o(Part::Exceptions, "Which exceptions does it throw, and on which arguments?"));
            out.push(o(Part::Receiver, "Does it change the object it is called on? (`modifies: this`, or nothing)"));
        }
        GapKind::InvokeDynamic => out.push(o(Part::Result, "What does the call site compute, as a condition over its arguments and `result`?")),
        GapKind::Monitor => out.push(o(Part::Exceptions, "Is the monitor ever null? (it throws NullPointerException there)")),
    }
    if references && kind != GapKind::ClassInitializer {
        out.push(o(Part::Arguments, "Does it change an array or object passed to it? (`modifies: <parameter>`, and what holds of it after, with `\\old`)"));
    }
    out.push(o(Part::Purity, "Has it any other effect: static state, I/O, another thread?"));
    out
}

/// One gap's block of the template.
fn block(g: &GapAdvice) -> String {
    let mut out = String::new();
    let params = g.parameters.iter().map(|p| format!("{} {}", p.ty, p.name)).collect::<Vec<_>>().join(", ");
    let _ = writeln!(out, "{}", g.id);
    let _ = writeln!(out, "  # {} {}, at {}.", g.call, describe(g.kind), g.sites.join(", "));
    if g.kind.assumable() {
        let _ = writeln!(out, "  # --gaps assume would take it that it {}.", g.assumed);
    } else {
        let _ = writeln!(out, "  # --gaps assume has no approximation of it: only a contract closes it.");
    }
    match g.kind {
        GapKind::ClassInitializer => {
            let _ = writeln!(out, "  call: {}.<clinit>()", g.owner);
            let _ = writeln!(out, "  throws: TODO when TODO");
            let _ = writeln!(out, "  modifies: TODO (nothing, or the static fields it sets)");
            let _ = writeln!(out, "  assert: TODO (what the fields it sets hold)");
        }
        _ => {
            let _ = writeln!(out, "  call: {}.{}({params}){}", g.owner, g.name, if g.returns == "void" { String::new() } else { format!(" -> {}", g.returns) });
            let _ = writeln!(out, "  assume: true");
            let _ = writeln!(out, "  throws: TODO when TODO");
            if g.must_state.iter().any(|o| o.part == Part::Result) {
                let over = if matches!(g.kind, GapKind::JdkReferenceMethod | GapKind::StringConversion) { "the arguments, this and result" } else { "the arguments and result" };
                let _ = writeln!(out, "  assert: TODO (over {over})");
            } else if g.must_state.iter().any(|o| o.part == Part::Arguments) {
                let _ = writeln!(out, "  assert: TODO (what holds of an argument it changes, with \\old for its value before; true for nothing)");
            }
            let _ = writeln!(out, "  modifies: TODO (nothing, this, or a parameter)");
        }
    }
    let _ = writeln!(out, "  written-by: TODO (an agent, or a person)");
    out
}

fn describe(kind: GapKind) -> &'static str {
    match kind {
        GapKind::JdkConstructor => "is a JDK constructor the tool's own checker has no model of",
        GapKind::JdkVoidMethod => "is a JDK method returning nothing that the tool's own checker has no model of",
        GapKind::JdkReferenceMethod => "is a JDK method returning an object that the tool's own checker has no model of",
        GapKind::StringConversion => "is the toString a string concatenation calls on an object, which the tool's own checker does not run",
        GapKind::ClassInitializer => "is a class initializer, which the tool's own checker does not run",
        GapKind::JdkPrimitiveMethod => "is a JDK method returning a primitive that the tool's own checker has no model of",
        GapKind::JdkStaticMethod => "is a static JDK method the tool's own checker has no model of",
        GapKind::MissingBody => "is a method JBMC has no bytecode for, which it gives a stub",
        GapKind::InvokeDynamic => "is an invokedynamic call site JBMC does not link, which it gives the value zero",
        GapKind::Monitor => "synchronizes, and JBMC drops its monitor instructions",
    }
}

/// The template file: a header, then each gap's block.
pub fn template(gaps: &[GapAdvice], jdk: Option<&str>, checker: Option<&str>) -> String {
    let mut out = String::new();
    let whose = if checker == Some("jbmc") { "JBMC, which jvmcontract runs," } else { "jvmcontract's own checker" };
    let _ = writeln!(out, "# Contracts for the gaps of {whose} (--gaps advised), one block per gap, under its id.");
    let _ = writeln!(out, "# Replace each TODO: `throws:` may be repeated or removed, and `assume:` narrows the inputs a contract is about.");
    let _ = writeln!(out, "# The conditions name the parameters as the `call:` line does, which may rename them (a JDK class file keeps no names).");
    if let Some(v) = jdk {
        let _ = writeln!(out, "# The JDK calls are those of JDK {v}; a contract is checked against it before it is relied on.");
    }
    let _ = writeln!(out, "kind: gap-contracts");
    for g in gaps {
        let _ = writeln!(out);
        out.push_str(&g.template);
    }
    out
}

impl Advice {
    /// Why the run has no verdict, for the verdict line.
    pub fn problem(&self) -> String {
        let n = self.gaps.len();
        let list = self.gaps.iter().map(|g| format!("{} ({} at {})", g.id, g.call, g.sites.join(", "))).collect::<Vec<_>>().join("; ");
        format!(
            "the proof reaches {n} gap{s} of {who} with no contract (--gaps advised), so nothing was solved: {list}. Write a contract for {each} from the template in {file}.",
            s = if n == 1 { "" } else { "s" },
            who = if self.checker.as_deref() == Some("jbmc") { "JBMC" } else { "the tool's own checker" },
            each = if n == 1 { "it" } else { "each" },
            file = self.template_file.display()
        )
    }

    /// The lines under the verdict: each gap with what its contract must state, what is outside the fragment
    /// whatever the contracts, and the template.
    pub fn lines(&self) -> String {
        let mut out = String::new();
        for g in &self.gaps {
            let _ = writeln!(out, "  gap {}  {} at {}", g.id, g.call, g.sites.join(", "));
            let _ = writeln!(out, "    a contract states: {}", g.must_state.iter().map(|o| part_name(o.part)).collect::<Vec<_>>().join(", "));
            if let Some(r) = &g.refused_contract {
                let _ = writeln!(out, "    its contract is refused: {r}");
            }
            for c in g.counterexamples.iter().skip(1).take(4) {
                let _ = writeln!(out, "      also {}", c.line());
            }
        }
        if !self.closed.is_empty() {
            let _ = writeln!(out, "  closed by a contract: {}", self.closed.join(", "));
        }
        for (why, r) in &self.outside {
            let outside = if self.checker.as_deref() == Some("jbmc") { "approximated by JBMC whatever the contracts" } else { "outside the fragment whatever the contracts" };
            let _ = writeln!(out, "  {outside}: {why}: {} at {}{}", r.first, r.at, if r.sites > 1 { format!(", {} sites in all", r.sites) } else { String::new() });
        }
        let _ = writeln!(out, "\n{}", self.template.trim_end());
        out
    }
}

fn part_name(p: Part) -> &'static str {
    match p {
        Part::Result => "its result",
        Part::Exceptions => "its exceptions and when",
        Part::Receiver => "its effect on the receiver",
        Part::Arguments => "its effect on its arguments",
        Part::State => "the static state it sets",
        Part::Purity => "any other effect",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_template_has_a_todo_for_each_part_a_contract_states() {
        let cp = ClassPath::new().with_default_jdk();
        let gap = Gap { kind: GapKind::JdkConstructor, owner: "java/util/ArrayList".into(), name: "<init>".into(), descriptor: "(I)V".into() };
        let a = advise(&cp, &gap, vec!["p.C.m:3".into()], Some("25"));
        assert_eq!(a.id, "jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25");
        assert_eq!(a.parameters.len(), 1);
        assert_eq!(a.parameters[0].ty, "int");
        assert_eq!(a.returns, "void");
        let parts: Vec<Part> = a.must_state.iter().map(|o| o.part).collect();
        assert_eq!(parts, vec![Part::Exceptions, Part::Receiver, Part::Purity]);
        assert!(a.template.starts_with("jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25\n"), "{}", a.template);
        assert!(a.template.contains(&format!("  call: java.util.ArrayList.<init>(int {})\n", a.parameters[0].name)), "{}", a.template);
        assert!(a.template.contains("  throws: TODO when TODO\n") && a.template.contains("  modifies: TODO") && a.template.contains("  written-by: TODO"));
        assert!(!a.template.contains("assert:"), "a constructor has no result to state");

        let gap = Gap { kind: GapKind::JdkVoidMethod, owner: "java/util/Random".into(), name: "nextBytes".into(), descriptor: "([B)V".into() };
        let a = advise(&cp, &gap, vec!["p.C.m:4".into()], Some("25"));
        assert!(a.must_state.iter().any(|o| o.part == Part::Arguments), "an array argument may be changed");

        let gap = Gap { kind: GapKind::JdkReferenceMethod, owner: "java/lang/StringBuilder".into(), name: "append".into(), descriptor: "(I)Ljava/lang/StringBuilder;".into() };
        let a = advise(&cp, &gap, vec!["p.C.m:5".into()], Some("25"));
        assert_eq!(a.must_state[0].part, Part::Result);
        assert!(a.template.contains(" -> java.lang.StringBuilder\n") && a.template.contains("  assert: TODO"), "{}", a.template);

        let gap = Gap { kind: GapKind::ClassInitializer, owner: "p/Boom".into(), name: "<clinit>".into(), descriptor: "()V".into() };
        let a = advise(&cp, &gap, vec!["p.C.m:6".into()], Some("25"));
        assert_eq!(a.id, "class-initializer:p.Boom.<clinit>()V", "no JDK version on an application's initializer");
        assert!(a.must_state.iter().any(|o| o.part == Part::State));
        let file = template(&[a], Some("25"), None);
        assert!(file.contains("\nkind: gap-contracts\n\nclass-initializer:p.Boom.<clinit>()V\n"), "{file}");

        // A call whose value the proof reads: its result is a condition over `result`, and assume has no form of it.
        let gap = Gap { kind: GapKind::JdkPrimitiveMethod, owner: "java/util/Random".into(), name: "nextInt".into(), descriptor: "(I)I".into() };
        let a = advise(&cp, &gap, vec!["p.C.m:7".into()], Some("25"));
        assert_eq!(a.must_state[0].part, Part::Result);
        assert!(a.template.contains("  # --gaps assume has no approximation of it: only a contract closes it.\n"), "{}", a.template);
        assert!(a.template.contains(" -> int\n") && a.template.contains("  assert: TODO (over the arguments and result)\n"), "{}", a.template);
        let gap = Gap { kind: GapKind::JdkStaticMethod, owner: "java/util/Arrays".into(), name: "fill".into(), descriptor: "([II)V".into() };
        let a = advise(&cp, &gap, vec!["p.C.m:8".into()], Some("25"));
        let parts: Vec<Part> = a.must_state.iter().map(|o| o.part).collect();
        assert_eq!(parts, vec![Part::Exceptions, Part::Arguments, Part::Purity], "a void static method has no result, and may change its array");
    }
}
