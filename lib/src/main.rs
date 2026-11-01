//! The `jvmcontract` command line.

use std::path::PathBuf;
use std::process::ExitCode;

use clap::{Args, Parser, Subcommand};

use jvmcontract::{capabilities, classpath::ClassPath, equivalence, property, statemachine, tla, verifier, Error};

#[derive(Parser)]
#[command(name = "jvmcontract", version, about = "Formal verification of JVM bytecode as contracts: behavioural, regression, capability and API contracts, and TLA+ models generated from them.", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Check that the code still behaves exactly as the contracts in a directory say (exit 1 on any drift).
    Verify(ContractArgs),
    /// Rewrite the contracts in a directory from the code; --add creates new ones.
    Update(ContractArgs),
    /// Derive the contract of one method and print it, without touching any file.
    Derive {
        /// `pkg.Class#method`.
        target: String,
        #[command(flatten)]
        classes: ClassesArgs,
        /// Print the contract as JSON.
        #[arg(long)]
        json: bool,
        /// Report the execution cost (steps, allocations, call depth).
        #[arg(long)]
        cost: bool,
        /// Let record components of reference type also be null.
        #[arg(long)]
        null_components: bool,
    },
    /// Prove two compiled versions of a method equivalent with JBMC, or show an input on which they differ.
    Equivalence(EquivalenceArgs),
    /// Prove a property of a method on every input with JBMC, or show an input that violates it.
    Prove(ProveArgs),
    /// Print the capability contract of a module (directories or jars), without touching any file.
    Capabilities {
        /// Directories of classes or jars. Each is analysed as one module unless --each is given.
        #[arg(required = true)]
        paths: Vec<PathBuf>,
        /// Analyse each path as a module of its own: a capability contract per dependency jar.
        #[arg(long)]
        each: bool,
        /// Print JSON instead of the contract text.
        #[arg(long)]
        json: bool,
        /// The module name for the contract header.
        #[arg(long, default_value = "module")]
        module: String,
    },
    /// Print the public API contract of a module.
    Api {
        #[arg(required = true)]
        paths: Vec<PathBuf>,
        #[arg(long, default_value = "module")]
        module: String,
    },
    /// Turn a behavioural contract into a TLA+ operator, for a model checked by TLC.
    Tla {
        /// The contract file (`OrderLifecycle.decide.contract`).
        contract: PathBuf,
        /// The TLA+ module to write.
        output: PathBuf,
        /// The module name; defaults to the output file's stem.
        #[arg(long)]
        module: Option<String>,
        /// The operator name; defaults to the method name, capitalised.
        #[arg(long)]
        operator: Option<String>,
    },
    /// Run TLC on a TLA+ specification and report the verdict, the state count and any counterexample trace.
    Tlc {
        /// The specification file (`BoxOffice.tla`); its `.cfg` sits next to it.
        spec: PathBuf,
        /// Print JSON.
        #[arg(long)]
        json: bool,
        /// Workers (`1` keeps the reported trace stable between runs).
        #[arg(long, default_value = "1")]
        workers: String,
        /// Seconds before giving up.
        #[arg(long, default_value_t = 1800)]
        timeout: u64,
        /// Where TLC finds the standard modules, if not in its jar (`-DTLA-Library`).
        #[arg(long)]
        library: Option<PathBuf>,
        /// Also report a reachable state in which no action is enabled, as a deadlock (off by default: a
        /// finished system is meant to stop).
        #[arg(long)]
        deadlock: bool,
    },
    /// Draw the state machine a behavioural contract describes, as Mermaid or DOT.
    Statemachine {
        contract: PathBuf,
        /// `mermaid` (default) or `dot`.
        #[arg(long, default_value = "mermaid")]
        format: String,
        /// The outcome field that names the next state.
        #[arg(long, default_value = "next")]
        next_field: String,
    },
    /// Print the structure of a class file: constant pool size, members, attributes and bytecode.
    Inspect {
        class_file: PathBuf,
        /// Also disassemble each method.
        #[arg(long)]
        code: bool,
    },
}

#[derive(Args, Clone)]
struct ClassesArgs {
    /// The module's compiled classes: a directory or jar (repeatable).
    #[arg(long = "classes", required = true)]
    classes: Vec<PathBuf>,
    /// Further class path entries the classes refer to (repeatable, or PATH-separated).
    #[arg(long = "classpath")]
    classpath: Vec<String>,
}

impl ClassesArgs {
    fn classpath_entries(&self) -> Vec<PathBuf> {
        self.classpath.iter().flat_map(|s| std::env::split_paths(s).collect::<Vec<_>>()).collect()
    }
}

#[derive(Args)]
struct ContractArgs {
    /// The directory of `.contract` files.
    #[arg(long)]
    contracts: PathBuf,
    #[command(flatten)]
    classes: ClassesArgs,
    /// Source roots, to anchor findings to lines (repeatable).
    #[arg(long = "sources")]
    sources: Vec<PathBuf>,
    /// The directory SARIF paths are relative to.
    #[arg(long)]
    base: Option<PathBuf>,
    /// Write `contracts.sarif` into this directory.
    #[arg(long)]
    report: Option<PathBuf>,
    /// The module name, for the capability and API contract headers.
    #[arg(long, default_value = "module")]
    module: String,
    /// A target to add: `pkg.Class#method`, `capabilities`, or `api` (repeatable).
    #[arg(long = "add")]
    add: Vec<String>,
    /// Report the execution cost of each derivation.
    #[arg(long)]
    cost: bool,
    /// Let record components of reference type also be null.
    #[arg(long)]
    null_components: bool,
}

#[derive(Args)]
struct EquivalenceArgs {
    /// The previous version's classes.
    #[arg(long)]
    before: PathBuf,
    /// The new version's classes.
    #[arg(long)]
    after: PathBuf,
    /// `pkg.Class#method`, a static method with primitive parameters.
    #[arg(long)]
    target: String,
    /// A Java boolean expression over the parameters naming the inputs the change is meant to affect.
    #[arg(long = "unchanged-unless")]
    unchanged_unless: Option<String>,
    /// Further class path entries (PATH-separated or repeatable).
    #[arg(long = "classpath")]
    classpath: Vec<String>,
    /// A working directory for the harness, relocated classes and JBMC logs (a temporary one by default).
    #[arg(long)]
    work: Option<PathBuf>,
    /// Write `equivalence.sarif` into this directory.
    #[arg(long)]
    report: Option<PathBuf>,
    #[arg(long = "sources")]
    sources: Vec<PathBuf>,
    #[arg(long)]
    base: Option<PathBuf>,
    /// Loop unwinding bound for JBMC.
    #[arg(long, default_value_t = 16)]
    unwind: u32,
    /// Seconds before each JBMC run is given up.
    #[arg(long, default_value_t = 600)]
    timeout: u64,
    /// The `jbmc` executable.
    #[arg(long, default_value = "jbmc")]
    jbmc: String,
    /// Print JSON.
    #[arg(long)]
    json: bool,
}

#[derive(Args)]
struct ProveArgs {
    /// `pkg.Class#method`, a static method with primitive or array parameters. With --properties, only this
    /// target's properties are proved.
    target: Option<String>,
    #[command(flatten)]
    classes: ClassesArgs,
    /// A properties file (`properties.contract`): every property in it is proved, and the exit code is 1 if any
    /// is violated or cannot be verified.
    #[arg(long)]
    properties: Option<PathBuf>,
    /// The inputs the property is about: a Java boolean expression over the parameters (every input by default).
    #[arg(long)]
    assume: Option<String>,
    /// The property: a Java boolean expression over the parameters, `result`, and calls of the method itself,
    /// such as `result == merge(b, a)`. A boolean method's property is `result` by default.
    #[arg(long = "assert")]
    assert_: Option<String>,
    /// The exceptional behaviour, `<exception class> when <condition>`: the method throws that exception exactly on
    /// the inputs where the condition holds, such as `java.lang.ArithmeticException when divisor == 0`. May be
    /// repeated; the first clause whose condition holds is the one expected.
    #[arg(long = "throws")]
    throws: Vec<String>,
    /// A working directory for the harness and JBMC logs (a temporary one by default).
    #[arg(long)]
    work: Option<PathBuf>,
    /// Write `property.sarif` into this directory.
    #[arg(long)]
    report: Option<PathBuf>,
    #[arg(long = "sources")]
    sources: Vec<PathBuf>,
    #[arg(long)]
    base: Option<PathBuf>,
    /// Loop unwinding bound for JBMC.
    #[arg(long, default_value_t = 16)]
    unwind: u32,
    /// The longest array an array parameter is given; a quantifier's loop must fit the unwinding bound.
    #[arg(long, default_value_t = 8)]
    max_array_length: u32,
    /// Report the counterexample as JBMC found it, without shrinking it in the interpreter.
    #[arg(long)]
    no_shrink: bool,
    /// Seconds before each JBMC run is given up.
    #[arg(long, default_value_t = 600)]
    timeout: u64,
    /// The `jbmc` executable.
    #[arg(long, default_value = "jbmc")]
    jbmc: String,
    /// Print JSON.
    #[arg(long)]
    json: bool,
}

fn main() -> ExitCode {
    match run(Cli::parse()) {
        Ok(code) => ExitCode::from(code as u8),
        Err(e) => {
            eprintln!("jvmcontract: {e}");
            ExitCode::from(2)
        }
    }
}

fn run(cli: Cli) -> Result<i32, Error> {
    match cli.command {
        Command::Verify(args) | Command::Update(args) => {
            let update = matches!(std::env::args().nth(1).as_deref(), Some("update"));
            let mut run = verifier::ContractsRun::new(&args.contracts);
            run.classes = args.classes.classes.clone();
            run.classpath = args.classes.classpath_entries();
            run.sources = args.sources.iter().map(|s| std::fs::canonicalize(s).unwrap_or_else(|_| s.clone())).collect();
            if let Some(base) = args.base {
                run.base = std::fs::canonicalize(&base).unwrap_or(base);
            }
            run.report = args.report;
            run.module = args.module;
            run.add = args.add;
            run.update = update;
            run.show_cost = args.cost;
            run.options.domain.null_components = args.null_components;
            let outcome = verifier::run(&run)?;
            print!("{}", outcome.output);
            Ok(outcome.exit_code)
        }
        Command::Derive { target, classes, json, cost, null_components } => {
            let cp = load_classpath(&classes)?;
            let mut v = verifier::Verifier::new(&cp);
            v.options.domain.null_components = null_components;
            let derivation = v.derive(&target);
            if json {
                println!("{}", serde_json::to_string_pretty(&derivation).expect("serializable"));
            } else if let Some(problem) = &derivation.problem {
                println!("✗ {target} cannot be verified: {problem}");
            } else {
                print!("{}", derivation.contract.as_ref().expect("derived").render());
                eprintln!("({})", derivation.stats());
                if cost {
                    eprintln!("(cost: {} steps, {} allocations, depth {})", derivation.cost.steps, derivation.cost.allocations, derivation.cost.max_depth);
                }
            }
            Ok(if derivation.problem.is_some() { 1 } else { 0 })
        }
        Command::Equivalence(args) => {
            let mut options = equivalence::Options::new(&args.before, &args.after, &args.target);
            options.unchanged_unless = args.unchanged_unless;
            options.classpath = args.classpath.iter().flat_map(|s| std::env::split_paths(s).collect::<Vec<_>>()).collect();
            options.work = args.work;
            options.report = args.report;
            options.sources = args.sources;
            if let Some(base) = args.base {
                options.base = base;
            }
            options.unwind = args.unwind;
            options.timeout_seconds = args.timeout;
            options.jbmc = args.jbmc;
            let outcome = equivalence::run(&options)?;
            if args.json {
                println!("{}", serde_json::to_string_pretty(&outcome).expect("serializable"));
            } else {
                print!("{}", outcome.output);
            }
            Ok(outcome.verdict.exit_code())
        }
        Command::Prove(args) => {
            let declarations = match (&args.properties, &args.target) {
                (Some(file), only) => {
                    let all = property::read_declarations(file)?;
                    let selected: Vec<_> = all.into_iter().filter(|d| only.as_ref().is_none_or(|t| &d.target == t)).collect();
                    if selected.is_empty() {
                        return Err(Error::new(format!("no properties{} in {}", only.as_ref().map(|t| format!(" of {t}")).unwrap_or_default(), file.display())));
                    }
                    selected
                }
                (None, Some(target)) => vec![property::Declaration { target: target.clone(), assume: args.assume.clone(), assert: args.assert_.clone(), throws: args.throws.clone(), max_array_length: None, unwind: None }],
                (None, None) => return Err(Error::new("give a target `pkg.Class#method`, or --properties FILE")),
            };
            let mut outcomes = Vec::new();
            let mut findings = Vec::new();
            let mut exit = 0;
            for (i, declaration) in declarations.iter().enumerate() {
                let mut options = property::Options::new(&args.classes.classes, &declaration.target);
                options.classpath = args.classes.classpath_entries();
                options.assume = declaration.assume.clone();
                options.assert = declaration.assert.clone();
                options.throws = declaration.throws.clone();
                options.work = args.work.as_ref().map(|w| if declarations.len() > 1 { w.join(format!("property-{}", i + 1)) } else { w.clone() });
                options.report = if declarations.len() > 1 { None } else { args.report.clone() };
                options.sources = args.sources.clone();
                if let Some(base) = &args.base {
                    options.base = base.clone();
                }
                options.unwind = declaration.unwind.unwrap_or(args.unwind);
                options.max_array_length = declaration.max_array_length.unwrap_or(args.max_array_length);
                options.shrink = !args.no_shrink;
                options.timeout_seconds = args.timeout;
                options.jbmc = args.jbmc.clone();
                let outcome = property::run(&options)?;
                exit = exit.max(outcome.verdict.exit_code());
                if !args.json {
                    print!("{}", outcome.output);
                }
                findings.extend(outcome.findings.iter().cloned());
                outcomes.push(outcome);
            }
            if declarations.len() > 1 {
                if let Some(report) = &args.report {
                    jvmcontract::sarif::write(&report.join("property.sarif"), &findings)?;
                }
            }
            if args.json {
                println!("{}", serde_json::to_string_pretty(&outcomes).expect("serializable"));
            }
            Ok(exit)
        }
        Command::Capabilities { paths, each, json, module } => {
            if each {
                for path in &paths {
                    let report = capabilities::analyse(std::slice::from_ref(path))?;
                    let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| module.clone());
                    if json {
                        println!("{}", serde_json::to_string_pretty(&serde_json::json!({ "path": path, "report": report })).expect("serializable"));
                    } else {
                        println!("{}", report.render(&name));
                    }
                }
            } else {
                let report = capabilities::analyse(&paths)?;
                if json {
                    println!("{}", serde_json::to_string_pretty(&report).expect("serializable"));
                } else {
                    print!("{}", report.render(&module));
                }
            }
            Ok(0)
        }
        Command::Api { paths, module } => {
            let mut cp = ClassPath::new();
            for p in &paths {
                cp.add(p)?;
            }
            let surface = jvmcontract::api::analyse(&cp)?;
            print!("{}", surface.render(&module));
            Ok(0)
        }
        Command::Tla { contract, output, module, operator } => {
            let contract = jvmcontract::contract::Contract::read(&contract)?;
            let module_name = module.unwrap_or_else(|| output.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "Contract".into()));
            let text = tla::operator_module(&contract, &module_name, operator.as_deref())?;
            std::fs::write(&output, &text)?;
            println!("wrote {}: {} cases", output.display(), text.lines().filter(|l| l.contains("->")).count());
            Ok(0)
        }
        Command::Tlc { spec, json, workers, timeout, library, deadlock } => {
            let mut options = tla::TlcOptions::new(&spec);
            options.workers = workers;
            options.timeout_seconds = timeout;
            options.library = library;
            options.deadlock = deadlock;
            let result = tla::run_tlc(&options)?;
            if json {
                println!("{}", serde_json::to_string_pretty(&result).expect("serializable"));
            } else {
                print!("{}", result.summary());
            }
            Ok(result.verdict.exit_code())
        }
        Command::Statemachine { contract, format, next_field } => {
            let contract = jvmcontract::contract::Contract::read(&contract)?;
            let machine = statemachine::from_contract(&contract, &next_field)?;
            match format.as_str() {
                "dot" => print!("{}", machine.dot()),
                _ => print!("{}", machine.mermaid()),
            }
            Ok(0)
        }
        Command::Inspect { class_file, code } => {
            let bytes = std::fs::read(&class_file)?;
            let class = jvmcontract::classfile::ClassFile::parse(&bytes)?;
            print!("{}", jvmcontract::classfile::describe(&class, code)?);
            Ok(0)
        }
    }
}

fn load_classpath(classes: &ClassesArgs) -> Result<ClassPath, Error> {
    let mut cp = ClassPath::new();
    for path in &classes.classes {
        cp.add(path)?;
    }
    for path in classes.classpath_entries() {
        if path.exists() {
            cp.add(&path)?;
        }
    }
    Ok(cp.with_default_jdk())
}
