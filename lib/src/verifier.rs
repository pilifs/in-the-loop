//! Derives the behavioural contract of a method from its bytecode in three steps, each of which can refuse:
//!
//! 1. **Purity** ([`crate::purity`]): the method is a function of its arguments.
//! 2. **Domain** ([`crate::domain`]): its parameters have finitely many values.
//! 3. **Execution** ([`crate::interp`]): run it on every input and record the outcome, a value or an exception,
//!    with the effect monitor on.
//!
//! Together these decide the method's behaviour exactly, which is why the result can serve as a contract: two
//! versions of the code with equal contracts behave identically on every input.
//!
//! This module also holds the `verify`/`update` workflow over a directory of contract files, as the command line
//! and build plugins run it.

use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::capabilities;
use crate::classfile::{ClassFile, Method, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::contract::Contract;
use crate::domain;
use crate::interp::{render, Cost, Fault, Limits, Machine, Value};
use crate::purity::{Purity, PurityResult};
use crate::sarif::{self, Finding};
use crate::Error;

/// How a contract is derived.
#[derive(Debug, Clone, Copy)]
pub struct Options {
    pub domain: domain::Options,
    pub limits: Limits,
    /// Whether an instance method with a finite receiver type is accepted, with the receiver as the first
    /// dimension of the domain.
    pub instance_methods: bool,
}

impl Default for Options {
    fn default() -> Options {
        Options { domain: domain::Options::default(), limits: Limits::default(), instance_methods: true }
    }
}

/// The result of deriving a contract: either the contract, or why it cannot be derived.
#[derive(Debug, Clone, Serialize)]
pub struct Derivation {
    pub target: String,
    pub contract: Option<Contract>,
    pub purity: Option<PurityResult>,
    pub problem: Option<String>,
    /// The internal name of the class that declares the method, when it was found.
    pub owner: Option<String>,
    /// The first source line of the method, or 1.
    pub line: u32,
    pub cost: Cost,
}

impl Derivation {
    fn failed(target: &str, problem: String, purity: Option<PurityResult>, owner: Option<String>) -> Derivation {
        let line = purity.as_ref().map(|p| p.first_line).filter(|l| *l > 0).unwrap_or(1);
        Derivation { target: target.to_string(), contract: None, purity, problem: Some(problem), owner, line, cost: Cost::default() }
    }

    /// `N cases, M methods proven pure, trusting a, b, c`.
    pub fn stats(&self) -> String {
        let cases = self.contract.as_ref().map(|c| c.cases.len()).unwrap_or(0);
        match &self.purity {
            Some(p) => format!("{cases} cases, {} methods proven pure, trusting {}", p.reached.len(), p.trusted.iter().cloned().collect::<Vec<_>>().join(", ")),
            None => format!("{cases} cases"),
        }
    }
}

pub struct Verifier<'a> {
    cp: &'a ClassPath,
    pub options: Options,
}

/// Splits `pkg.Class#method`, or `pkg.Class#method(int, long[])`, into the internal class name and the method name.
/// The parameter types, when given, pick one of several overloads; [`select_method`] applies them.
pub fn parse_target(target: &str) -> Option<(String, String)> {
    let (class, method) = target.trim().split_once('#')?;
    let method = method.split_once('(').map_or(method, |(name, _)| name).trim();
    if class.is_empty() || method.is_empty() {
        return None;
    }
    Some((class.replace('.', "/"), method.to_string()))
}

/// The parameter types a target names, `pkg.Class#pow(int, int)` giving `["int", "int"]`, with their whitespace
/// removed; `None` when the target names the method alone.
pub fn target_parameters(target: &str) -> Option<Vec<String>> {
    let (_, method) = target.trim().split_once('#')?;
    let (_, rest) = method.split_once('(')?;
    let inside = rest.trim().strip_suffix(')')?.trim();
    Some(if inside.is_empty() { Vec::new() } else { inside.split(',').map(|p| p.split_whitespace().collect()).collect() })
}

/// The one method a target names: the method of that name, or, when the name is overloaded, the one whose
/// parameter types the target lists (`pow(int, int)`, in Java's spelling, simple or qualified). The error names
/// the overloads found, so that the caller can pick one.
pub fn select_method<'c>(class: &'c ClassFile, target: &str) -> Result<&'c Method, String> {
    let (_, name) = parse_target(target).ok_or("target must be <class>#<method>")?;
    let wanted = target_parameters(target);
    let named: Vec<&Method> = class.methods.iter().filter(|m| m.name == name && !m.is_synthetic() && !m.is_bridge()).collect();
    let signature = |m: &Method| match m.parsed_descriptor() {
        Ok(d) => format!("{name}({})", d.params.iter().map(|t| t.java_name()).collect::<Vec<_>>().join(", ")),
        Err(_) => format!("{name}(?)"),
    };
    let found = |methods: &[&Method]| methods.iter().map(|m| signature(m)).collect::<Vec<_>>().join(", ");
    let matches: Vec<&Method> = match &wanted {
        None => named.clone(),
        Some(types) => named
            .iter()
            .copied()
            .filter(|m| {
                m.parsed_descriptor().is_ok_and(|d| {
                    d.params.len() == types.len() && d.params.iter().zip(types).all(|(t, w)| t.java_name() == *w || t.java_name().replace('$', ".") == *w || t.simple_name() == *w)
                })
            })
            .collect(),
    };
    match (matches.as_slice(), wanted) {
        ([one], _) => Ok(one),
        ([], Some(types)) if !named.is_empty() => Err(format!("no method {name}({}); found {}", types.join(", "), found(&named))),
        ([], _) => Err(format!("expected one method named {name}, found 0")),
        (several, _) => Err(format!("expected one method named {name}, found {}: {}; name one as {}", several.len(), found(several), signature(several[0]))),
    }
}

impl<'a> Verifier<'a> {
    pub fn new(cp: &'a ClassPath) -> Verifier<'a> {
        Verifier { cp, options: Options::default() }
    }

    /// Derives the contract of `pkg.Class#method`.
    pub fn derive(&self, target: &str) -> Derivation {
        let Some((owner, name)) = parse_target(target) else {
            return Derivation::failed(target, "target must be <class>#<method>".into(), None, None);
        };
        let class = match self.cp.application(&owner) {
            Ok(Some(c)) => c,
            Ok(None) => return Derivation::failed(target, format!("class not found: {}", owner.replace('/', ".")), None, None),
            Err(e) => return Derivation::failed(target, e.to_string(), None, None),
        };
        let method = match select_method(&class, target) {
            Ok(m) => m.clone(),
            Err(problem) => return Derivation::failed(target, problem, None, Some(owner)),
        };
        let descriptor = match method.parsed_descriptor() {
            Ok(d) => d,
            Err(e) => return Derivation::failed(target, e.to_string(), None, Some(owner)),
        };
        let receiver = if method.is_static() {
            None
        } else if self.options.instance_methods && domain::is_finite_shape(self.cp, &Type::Object(owner.clone()), &mut Default::default()) {
            Some(Type::Object(owner.clone()))
        } else if self.options.instance_methods {
            return Derivation::failed(target, format!("only static methods, and instance methods of finite types (enums, records, sealed types), are supported; {} is not finite", owner.replace('/', ".")), None, Some(owner));
        } else {
            return Derivation::failed(target, "only static methods are supported".into(), None, Some(owner));
        };

        let purity = Purity::new(self.cp).analyse(&owner, &name, &method.descriptor);
        if !purity.is_pure() {
            let problem = format!("not provably pure:\n  {}", purity.violations.join("\n  "));
            return Derivation::failed(target, problem, Some(purity), Some(owner));
        }

        let mut machine = Machine::new(self.cp);
        machine.limits = self.options.limits;
        match self.execute(&mut machine, &owner, &name, &descriptor, receiver.as_ref()) {
            Ok((summary, cases)) => Derivation {
                target: target.to_string(),
                contract: Some(Contract::new(target, Some(summary), cases)),
                line: if purity.first_line > 0 { purity.first_line } else { 1 },
                purity: Some(purity),
                problem: None,
                owner: Some(owner),
                cost: machine.cost,
            },
            Err(problem) => Derivation::failed(target, problem, Some(purity), Some(owner)),
        }
    }

    fn execute(&self, m: &mut Machine, owner: &str, name: &str, descriptor: &MethodDescriptor, receiver: Option<&Type>) -> Result<(String, Vec<(String, String)>), String> {
        let describe_fault = |m: &Machine, f: &Fault, when: &str| match f {
            Fault::Unsupported(s) => format!("the interpreter does not model {s} ({when})"),
            Fault::Impure(s) => format!("not pure: the method {s} ({when})"),
            Fault::Budget(s) => format!("did not finish: {s} ({when})"),
            Fault::Throw(r) => format!("{} ({when})", render::thrown(m, *r)),
        };
        // Domains, from the types. Enumeration itself runs code (enum initialisers, record constructors).
        let mut types: Vec<Type> = Vec::new();
        if let Some(r) = receiver {
            types.push(r.clone());
        }
        types.extend(descriptor.params.iter().cloned());
        let mut domains = Vec::new();
        let mut summary = Vec::new();
        for (i, t) in types.iter().enumerate() {
            let is_receiver = receiver.is_some() && i == 0;
            let values = match domain::values(m, t, !is_receiver, self.options.domain) {
                Ok(v) => v,
                Err(domain::DomainError::Unbounded(what)) => return Err(format!("input domain is not finite: {what}")),
                Err(domain::DomainError::Execution(f)) => return Err(describe_fault(m, &f, &format!("while enumerating {}", t.java_name()))),
            };
            summary.push(if is_receiver { format!("this: {}", domain::describe(t, values.len())) } else { domain::describe(t, values.len()) });
            domains.push(values);
        }
        let inputs = match domain::product(&domains) {
            Ok(i) => i,
            Err(domain::DomainError::Unbounded(what)) => return Err(format!("input domain is not finite: {what}")),
            Err(domain::DomainError::Execution(f)) => return Err(describe_fault(m, &f, "")),
        };
        let summary = format!("{} = {} cases", summary.join(" × "), inputs.len());

        // Every input, executed with the effect monitor on.
        let mut cases = Vec::with_capacity(inputs.len());
        for args in inputs {
            let mark = m.begin_case();
            let input = self.render_input(m, name, &args, &types, receiver.is_some()).map_err(|f| describe_fault(m, &f, "while rendering an input"))?;
            let result = match receiver {
                Some(_) => m.call_virtual(args[0], owner, name, &descriptor.descriptor(), args[1..].to_vec()),
                None => m.call_static(owner, name, &descriptor.descriptor(), args.clone()),
            };
            let outcome = match result {
                Ok(Some(v)) => render::value(m, v, &descriptor.ret).map_err(|f| describe_fault(m, &f, &format!("while rendering the result of {input}")))?,
                Ok(None) => "void".to_string(),
                Err(Fault::Throw(r)) => render::thrown(m, r),
                Err(f) => return Err(describe_fault(m, &f, &format!("on {input}"))),
            };
            cases.push((input, outcome));
            m.end_case(mark);
        }
        Ok((summary, cases))
    }

    fn render_input(&self, m: &mut Machine, name: &str, args: &[Value], types: &[Type], has_receiver: bool) -> Result<String, Fault> {
        let mut parts = Vec::with_capacity(args.len());
        for (v, t) in args.iter().zip(types) {
            parts.push(render::value(m, *v, t)?);
        }
        Ok(if has_receiver {
            format!("{}.{name}({})", parts[0], parts[1..].join(", "))
        } else {
            format!("{name}({})", parts.join(", "))
        })
    }
}

/// The `verify`/`update` workflow over a contracts directory, as the command line runs it.
#[derive(Debug, Clone)]
pub struct ContractsRun {
    /// The directory of `.contract` files.
    pub contracts: PathBuf,
    /// The module's compiled classes (directories or jars): the code under verification.
    pub classes: Vec<PathBuf>,
    /// Further class path entries (dependency jars) the classes refer to.
    pub classpath: Vec<PathBuf>,
    /// Source roots, to anchor findings to lines.
    pub sources: Vec<PathBuf>,
    /// The base the SARIF paths are relative to.
    pub base: PathBuf,
    /// Where to write `contracts.sarif`, if anywhere.
    pub report: Option<PathBuf>,
    pub module: String,
    /// Targets to add (`pkg.Class#method`, or `capabilities`, or `api`).
    pub add: Vec<String>,
    /// `update` rewrites the contracts; `verify` checks them.
    pub update: bool,
    pub options: Options,
    /// Also print the cost (steps, allocations, depth) of each derivation.
    pub show_cost: bool,
}

impl ContractsRun {
    pub fn new(contracts: &Path) -> ContractsRun {
        ContractsRun {
            contracts: contracts.to_path_buf(),
            classes: Vec::new(),
            classpath: Vec::new(),
            sources: Vec::new(),
            base: std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            report: None,
            module: "module".into(),
            add: Vec::new(),
            update: false,
            options: Options::default(),
            show_cost: false,
        }
    }
}

/// What a run produced: the console text, the findings, and the exit code (`0` clean, `1` findings).
#[derive(Debug, Clone, Default)]
pub struct Outcome {
    pub output: String,
    pub findings: Vec<Finding>,
    pub exit_code: i32,
}

/// Runs `verify` or `update` over every contract in the directory plus the targets being added.
pub fn run(run: &ContractsRun) -> Result<Outcome, Error> {
    let mut out = String::new();
    let mut findings = Vec::new();
    let mut cp = ClassPath::new();
    for path in &run.classes {
        if path.exists() {
            cp.add(path)?;
        }
    }
    for path in &run.classpath {
        if path.exists() {
            cp.add(path)?;
        }
    }
    let cp = cp.with_default_jdk();

    // Every target: those with a contract file, plus any being added. The module's capability and API contracts
    // are targets of their own kind.
    let mut targets: BTreeMap<String, PathBuf> = BTreeMap::new();
    let mut added = run.add.clone();
    let capabilities_file = run.contracts.join(capabilities::FILE_NAME);
    let check_capabilities = capabilities_file.exists() || take(&mut added, "capabilities");
    let api_file = run.contracts.join(crate::api::FILE_NAME);
    let check_api = api_file.exists() || take(&mut added, "api");
    if run.contracts.is_dir() {
        let mut files: Vec<PathBuf> = std::fs::read_dir(&run.contracts)?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().is_some_and(|e| e == "contract"))
            .collect();
        files.sort();
        for file in files {
            let name = file.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if name == capabilities::FILE_NAME || name == crate::api::FILE_NAME || name == crate::property::FILE_NAME {
                continue; // the module-level contracts; properties are proved by `prove --properties`
            }
            let contract = Contract::read(&file)?;
            targets.insert(contract.target, file);
        }
    }
    for target in &added {
        targets.entry(target.clone()).or_insert_with(|| run.contracts.join(Contract::file_name(target)));
    }
    if targets.is_empty() && !check_capabilities && !check_api {
        let _ = writeln!(out, "No contracts in {}. Add one with: update --add <class>#<method>, or the module's capability contract with: update --add capabilities", run.contracts.display());
        return Ok(Outcome { output: out, findings, exit_code: 0 });
    }

    if check_capabilities {
        check_capability_contract(run, &cp, &capabilities_file, &mut out, &mut findings)?;
    }
    if check_api {
        check_api_contract(run, &cp, &api_file, &mut out, &mut findings)?;
    }

    let mut verifier = Verifier::new(&cp);
    verifier.options = run.options;
    for (target, file) in &targets {
        let derivation = verifier.derive(target);
        let uri = derivation.owner.as_deref().and_then(|o| sarif::source_file(o, &run.sources)).map(|f| sarif::relative_uri(&run.base, &f));
        let line = derivation.line;
        if let Some(problem) = &derivation.problem {
            let message = format!("{target} cannot be verified: {problem}");
            let _ = writeln!(out, "✗ {message}");
            findings.push(Finding::new("unverifiable", message, uri, line));
            continue;
        }
        let actual = derivation.contract.clone().expect("derived");
        let mut stats = derivation.stats();
        if run.show_cost {
            let _ = write!(stats, "; cost: {} steps, {} allocations, depth {}", derivation.cost.steps, derivation.cost.allocations, derivation.cost.max_depth);
        }
        if run.update {
            actual.write(file)?;
            let _ = writeln!(out, "✓ wrote {} ({stats})", file.display());
            continue;
        }
        if !file.exists() {
            let message = format!("{target} has no contract file {}", file.display());
            let _ = writeln!(out, "✗ {message}");
            findings.push(Finding::new("behaviour-changed", message, uri, line));
            continue;
        }
        let expected = Contract::read(file)?;
        let diff = Contract::diff(&expected, &actual);
        if diff.is_empty() {
            let _ = writeln!(out, "✓ {target} matches its contract ({stats})");
        } else {
            let lines: Vec<String> = diff.iter().map(|c| c.render()).collect();
            let message = format!("Behaviour of {target} differs from its contract in {} of {} cases:\n{}", diff.len(), actual.cases.len(), lines.join("\n"));
            let _ = writeln!(out, "✗ {message}");
            let _ = writeln!(out, "  ({stats})");
            findings.push(Finding::new("behaviour-changed", message, uri, line));
        }
    }

    if let Some(report) = &run.report {
        sarif::write(&report.join("contracts.sarif"), &findings)?;
    }
    if findings.iter().any(|f| f.rule_id == "behaviour-changed") {
        let _ = writeln!(out, "\nIf a change is intended, run `jvmcontract update` and commit the contract with the code. The contract diff then shows reviewers exactly which behaviour changed.");
    }
    if findings.iter().any(|f| f.rule_id == "unverifiable") {
        let _ = writeln!(out, "\nA method that cannot be verified has no contract. Move the impure or unbounded part out of it, or pass it in as a parameter, so that the method is a pure function of finite inputs again.");
    }
    if findings.iter().any(|f| f.rule_id == "capability-changed") {
        let _ = writeln!(out, "\nIf the module is meant to have this capability, run `jvmcontract update` and commit the contract with the code. The contract diff then shows reviewers the new power and where it is used.");
    }
    if findings.iter().any(|f| f.rule_id == "api-changed") {
        let _ = writeln!(out, "\nIf the API change is intended, run `jvmcontract update` and commit the contract with the code. The contract diff is the API change, for reviewers.");
    }
    let exit_code = if findings.is_empty() { 0 } else { 1 };
    Ok(Outcome { output: out, findings, exit_code })
}

fn take(list: &mut Vec<String>, item: &str) -> bool {
    match list.iter().position(|s| s == item) {
        Some(i) => {
            list.remove(i);
            true
        }
        None => false,
    }
}

fn check_capability_contract(run: &ContractsRun, cp: &ClassPath, file: &Path, out: &mut String, findings: &mut Vec<Finding>) -> Result<(), Error> {
    if run.classes.is_empty() {
        return Err(Error::new("--classes DIR is required for the capability contract"));
    }
    // The module's own classes only: the extra class path is context, not the module.
    let mut module_cp = ClassPath::new();
    for path in &run.classes {
        if path.exists() {
            module_cp.add(path)?;
        }
    }
    let _ = cp;
    let report = capabilities::analyse_classpath(&module_cp)?;
    let stats = report.stats();
    if run.update {
        report.write(file, &run.module)?;
        let _ = writeln!(out, "✓ wrote {} ({stats})", file.display());
        return Ok(());
    }
    let diff = capabilities::diff(&capabilities::read(file)?, &report.entries());
    if diff.is_empty() {
        let _ = writeln!(out, "✓ module {} matches its capability contract ({stats})", run.module);
        return Ok(());
    }
    let message = format!("Capabilities of module {} differ from its contract:\n{}", run.module, diff.join("\n"));
    let _ = writeln!(out, "✗ {message}");
    let _ = writeln!(out, "  ({stats})");
    // Anchor the finding to the first added use, when there is one.
    let mut uri = None;
    let mut line = 1;
    if let Some(added) = report.first_added(&diff) {
        if let Some(source) = sarif::source_file(&added.caller_class, &run.sources) {
            uri = Some(sarif::relative_uri(&run.base, &source));
            line = added.line.max(1);
        }
    }
    findings.push(Finding::new("capability-changed", message, uri, line));
    Ok(())
}

fn check_api_contract(run: &ContractsRun, cp: &ClassPath, file: &Path, out: &mut String, findings: &mut Vec<Finding>) -> Result<(), Error> {
    let mut module_cp = ClassPath::new();
    for path in &run.classes {
        if path.exists() {
            module_cp.add(path)?;
        }
    }
    let _ = cp;
    let surface = crate::api::analyse(&module_cp)?;
    if run.update {
        surface.write(file, &run.module)?;
        let _ = writeln!(out, "✓ wrote {} ({} public types, {} members)", file.display(), surface.types.len(), surface.member_count());
        return Ok(());
    }
    let expected = crate::api::read(file)?;
    let diff = crate::api::diff(&expected, &surface.entries());
    if diff.is_empty() {
        let _ = writeln!(out, "✓ module {} matches its API contract ({} public types, {} members)", run.module, surface.types.len(), surface.member_count());
        return Ok(());
    }
    let message = format!("Public API of module {} differs from its contract:\n{}", run.module, diff.join("\n"));
    let _ = writeln!(out, "✗ {message}");
    findings.push(Finding::new("api-changed", message, None, 1));
    Ok(())
}
