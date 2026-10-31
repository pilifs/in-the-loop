//! Capability contracts: everything a module's bytecode can reach beyond pure computation, grouped by capability
//! (the clock, randomness, the file system, the network, processes, reflection, ...), plus the libraries it calls.
//! Like an app's permission manifest, except computed from the compiled code rather than declared, and checked in.
//!
//! The claim is one of absence, and it is sound on a simple argument: on the JVM every capability is exercised
//! through a JDK entry point, so bytecode that contains no call to the entry points of a capability cannot exercise
//! it. The ways around that argument (reflection, method handles, class loading, native code, serialization) are
//! capabilities on the list themselves. What this does not cover is what the module's *libraries* do with the
//! calls it makes into them; the libraries are listed so that a new one is visible, and
//! [`analyse`] accepts jars, so that each library can be given a capability contract of its own.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use regex::Regex;
use serde::Serialize;

use crate::classfile::{ClassFile, Insn};
use crate::classpath::ClassPath;
use crate::Error;

/// One call from the module to a JDK entry point, with the capability it exercises.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Use {
    pub capability: String,
    /// `pkg.Class.method`.
    pub caller: String,
    /// `java.lang.Class.forName`, or `a native method`.
    pub callee: String,
    /// The caller's class, internal name.
    pub caller_class: String,
    pub line: u32,
}

impl Use {
    pub fn text(&self) -> String {
        format!("{} calls {}", self.caller, self.callee)
    }
}

impl PartialOrd for Use {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Use {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.text().cmp(&other.text()).then_with(|| self.capability.cmp(&other.capability))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Report {
    pub classes: usize,
    pub methods: usize,
    pub uses: BTreeMap<String, BTreeSet<Use>>,
    pub libraries: BTreeSet<String>,
}

pub const FILE_NAME: &str = "capabilities.contract";

pub const CAPABILITIES: &[&str] = &[
    "clock", "console", "environment", "filesystem", "jndi", "native", "network", "process", "randomness", "reflection",
    "scripting", "serialization", "threads",
];

struct Rule {
    capability: &'static str,
    owner: Regex,
    names: Regex,
}

/// The JDK entry points of each capability. The first rule whose owner and name both match decides.
const RULES: &[(&str, &str, &str)] = &[
    ("native", "java/lang/(System|Runtime)", "load|loadLibrary"),
    ("native", "java/lang/foreign/.*", ".*"),
    ("process", "java/lang/ProcessBuilder", ".*"),
    ("process", "java/lang/ProcessHandle.*", ".*"),
    ("process", "java/lang/Runtime", "exec|halt|exit|addShutdownHook|removeShutdownHook"),
    ("process", "java/lang/System", "exit"),
    ("environment", "java/lang/System", "getenv|getProperty|getProperties|setProperty|setProperties|clearProperty"),
    ("environment", "java/lang/Runtime", "availableProcessors|totalMemory|freeMemory|maxMemory|gc"),
    ("clock", "java/lang/System", "currentTimeMillis|nanoTime"),
    ("clock", "java/time/Clock", "system|systemUTC|systemDefaultZone|tick|tickMillis|tickSeconds|tickMinutes"),
    ("clock", "java/time/(Instant|LocalDate|LocalDateTime|LocalTime|ZonedDateTime|OffsetDateTime|OffsetTime|Year|YearMonth|MonthDay)", "now"),
    ("clock", "java/time/ZoneId", "systemDefault"),
    ("clock", "java/util/Calendar", "getInstance"),
    ("clock", "java/util/TimeZone", "getDefault"),
    ("console", "java/lang/System", "console|out|err|in"),
    ("console", "java/io/Console", ".*"),
    ("randomness", "java/util/(Random|SplittableRandom|concurrent/ThreadLocalRandom|random/.*)", ".*"),
    ("randomness", "java/security/SecureRandom", ".*"),
    ("randomness", "java/lang/(Math|StrictMath)", "random"),
    ("randomness", "java/util/UUID", "randomUUID"),
    ("randomness", "java/util/Collections", "shuffle"),
    ("reflection", "java/lang/Class", "forName|newInstance|getMethods?|getDeclaredMethods?|getConstructors?|getDeclaredConstructors?|getFields?|getDeclaredFields?|getResource|getResourceAsStream|getClassLoader|getRecordComponents|getEnumConstants"),
    ("reflection", "java/lang/reflect/.*", ".*"),
    ("reflection", "java/lang/invoke/MethodHandles", "lookup|privateLookupIn|reflectAs"),
    ("reflection", "java/lang/invoke/MethodHandles\\$Lookup", ".*"),
    ("reflection", "java/lang/ClassLoader", ".*"),
    ("reflection", "java/util/ServiceLoader", ".*"),
    ("reflection", "java/lang/Thread", "getContextClassLoader|setContextClassLoader"),
    ("serialization", "java/io/(ObjectInputStream|ObjectOutputStream|ObjectInputFilter.*)", ".*"),
    ("serialization", "java/beans/(XMLDecoder|XMLEncoder)", ".*"),
    ("jndi", "javax/naming/.*", ".*"),
    ("scripting", "javax/script/.*", ".*"),
    ("filesystem", "java/io/(File|FileInputStream|FileOutputStream|FileReader|FileWriter|RandomAccessFile)", ".*"),
    ("filesystem", "java/nio/file/(Files|FileSystems|Path|Paths)", ".*"),
    ("filesystem", "java/nio/channels/FileChannel", ".*"),
    ("filesystem", "java/util/(zip/ZipFile|jar/JarFile)", ".*"),
    ("network", "java/net/.*", ".*"),
    ("network", "javax/net/.*", ".*"),
    ("network", "java/rmi/.*", ".*"),
    ("network", "java/nio/channels/(Socket|ServerSocket|Datagram|AsynchronousSocket|AsynchronousServerSocket)Channel.*", ".*"),
    ("threads", "java/lang/Thread", "<init>|start|ofVirtual|ofPlatform|startVirtualThread|sleep|interrupt|setDaemon|join|setPriority"),
    ("threads", "java/lang/Thread\\$Builder.*", ".*"),
    ("threads", "java/util/concurrent/(Executors|ForkJoinPool|ThreadPoolExecutor|ScheduledThreadPoolExecutor|Executor|ExecutorService|ScheduledExecutorService)", ".*"),
    ("threads", "java/util/concurrent/CompletableFuture", ".*Async"),
    ("threads", "java/util/(Timer|TimerTask)", ".*"),
];

/// JDK types that look like capabilities by package but are plain values: never a capability.
const VALUE_TYPES: &str = "java/net/(URI|URLEncoder|URLDecoder|IDN)";

fn rules() -> &'static [Rule] {
    static RULES_COMPILED: OnceLock<Vec<Rule>> = OnceLock::new();
    RULES_COMPILED.get_or_init(|| {
        RULES
            .iter()
            .map(|(capability, owner, names)| Rule {
                capability,
                owner: Regex::new(&format!("^(?:{owner})$")).expect("valid rule"),
                names: Regex::new(&format!("^(?:{names})$")).expect("valid rule"),
            })
            .collect()
    })
}

fn value_types() -> &'static Regex {
    static VALUE: OnceLock<Regex> = OnceLock::new();
    VALUE.get_or_init(|| Regex::new(&format!("^(?:{VALUE_TYPES})$")).expect("valid"))
}

/// The capability a call to `owner.name` exercises, if any. `None` for a plain computation.
pub fn classify_call(owner: &str, name: &str) -> Option<&'static str> {
    if value_types().is_match(owner) {
        return None;
    }
    rules().iter().find(|r| r.owner.is_match(owner) && r.names.is_match(name)).map(|r| r.capability)
}

/// Analyses every class under the given directories and jars, as one module.
pub fn analyse(paths: &[PathBuf]) -> Result<Report, Error> {
    let mut cp = ClassPath::new();
    for path in paths {
        if path.exists() {
            cp.add(path)?;
        }
    }
    analyse_classpath(&cp)
}

/// Analyses every application class of a class path, as one module.
pub fn analyse_classpath(cp: &ClassPath) -> Result<Report, Error> {
    let classes = cp.application_classes()?;
    let own: BTreeSet<&str> = classes.keys().map(String::as_str).collect();
    let mut report = Report { classes: classes.len(), methods: 0, uses: BTreeMap::new(), libraries: BTreeSet::new() };
    for class in classes.values() {
        analyse_class(class, &own, &mut report)?;
    }
    Ok(report)
}

fn analyse_class(class: &ClassFile, own: &BTreeSet<&str>, report: &mut Report) -> Result<(), Error> {
    let class_name = &class.name;
    for method in &class.methods {
        report.methods += 1;
        let caller = format!("{}.{}", class_name.replace('/', "."), method.name);
        if method.is_native() {
            add(report, Use { capability: "native".into(), caller: caller.clone(), callee: "a native method".into(), caller_class: class_name.clone(), line: 0 });
        }
        let Some(code) = &method.code else { continue };
        for (pc, insn) in code.instructions()? {
            let line = code.line_at(pc).map(u32::from).unwrap_or(0);
            match insn {
                Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => {
                    let member = class.pool.member(i)?;
                    classify(report, own, &caller, class_name, line, &member.owner, &member.name);
                }
                Insn::GetStatic(i) => {
                    let member = class.pool.member(i)?;
                    classify(report, own, &caller, class_name, line, &member.owner, &member.name);
                }
                _ => {}
            }
        }
    }
    Ok(())
}

fn classify(report: &mut Report, own: &BTreeSet<&str>, caller: &str, caller_class: &str, line: u32, owner: &str, name: &str) {
    if owner.starts_with('[') || own.contains(owner) {
        return;
    }
    if !crate::classpath::is_jdk_name(owner) {
        let parts: Vec<&str> = owner.split('/').collect();
        let keep = 3.min(parts.len().saturating_sub(1));
        report.libraries.insert(parts[..keep].join("."));
        return;
    }
    if let Some(capability) = classify_call(owner, name) {
        add(report, Use {
            capability: capability.to_string(),
            caller: caller.to_string(),
            callee: format!("{}.{name}", owner.replace('/', ".")),
            caller_class: caller_class.to_string(),
            line,
        });
    }
}

fn add(report: &mut Report, use_: Use) {
    report.uses.entry(use_.capability.clone()).or_default().insert(use_);
}

impl Report {
    /// The contract text, one line per use, every capability listed (`none` when empty), then the libraries.
    pub fn lines(&self) -> Vec<String> {
        let mut out = Vec::new();
        for capability in CAPABILITIES {
            match self.uses.get(*capability) {
                None => out.push(format!("{capability}: none")),
                Some(set) if set.is_empty() => out.push(format!("{capability}: none")),
                Some(set) => {
                    out.push(format!("{capability}:"));
                    out.extend(set.iter().map(|u| format!("  {}", u.text())));
                }
            }
        }
        out.push(String::new());
        if self.libraries.is_empty() {
            out.push("libraries: none".into());
        } else {
            out.push("libraries:".into());
            out.extend(self.libraries.iter().map(|l| format!("  {l}")));
        }
        out
    }

    /// `capability: caller calls callee` and `library: name` entries, for comparison with a checked-in contract.
    pub fn entries(&self) -> BTreeSet<String> {
        let mut entries = BTreeSet::new();
        for (capability, set) in &self.uses {
            for u in set {
                entries.insert(format!("{capability}: {}", u.text()));
            }
        }
        for l in &self.libraries {
            entries.insert(format!("library: {l}"));
        }
        entries
    }

    pub fn total_uses(&self) -> usize {
        self.uses.values().map(BTreeSet::len).sum()
    }

    /// `N classes, M methods, K capability uses, L libraries`.
    pub fn stats(&self) -> String {
        format!("{} classes, {} methods, {} capability uses, {} libraries", self.classes, self.methods, self.total_uses(), self.libraries.len())
    }

    /// The first use whose entry is among the given diff lines (`added capability: text`), to anchor a finding.
    pub fn first_added(&self, diff: &[String]) -> Option<&Use> {
        self.uses.values().flatten().find(|u| diff.contains(&format!("  added {}: {}", u.capability, u.text())))
    }

    pub fn render(&self, module: &str) -> String {
        let mut lines = vec![
            "# Capability contract, generated by jvmcontract. Do not edit: regenerate it with `jvmcontract update`.".to_string(),
            "# It lists every call from this module's bytecode to a JDK API that reaches beyond pure computation, grouped".to_string(),
            "# by capability, and the libraries the module calls. The build checks it against the bytecode.".to_string(),
            "# A change here is a change in what the module is able to do: review it like a new permission.".to_string(),
            "kind: capabilities".to_string(),
            format!("module: {module}, {} classes, {} methods", self.classes, self.methods),
            String::new(),
        ];
        lines.extend(self.lines());
        let mut text = lines.join("\n");
        text.push('\n');
        text
    }

    pub fn write(&self, file: &Path, module: &str) -> Result<(), Error> {
        if let Some(parent) = file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(file, self.render(module))?;
        Ok(())
    }
}

/// The checked-in uses of a contract file, as entries comparable with [`Report::entries`].
pub fn read(file: &Path) -> Result<BTreeSet<String>, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("cannot read {}: {e}", file.display())))?;
    parse(&text)
}

pub fn parse(text: &str) -> Result<BTreeSet<String>, Error> {
    let mut entries = BTreeSet::new();
    let mut section: Option<String> = None;
    for line in text.lines() {
        if line.trim().is_empty() || line.starts_with('#') || line.starts_with("kind:") || line.starts_with("module:") {
            continue;
        }
        if !line.starts_with(' ') {
            let colon = line.find(':').ok_or_else(|| Error::new(format!("capability contract: bad section line {line:?}")))?;
            section = Some(line[..colon].to_string());
            continue;
        }
        let section = section.as_deref().ok_or_else(|| Error::new(format!("capability contract: entry before any section: {line:?}")))?;
        let prefix = if section == "libraries" { "library" } else { section };
        entries.insert(format!("{prefix}: {}", line.trim()));
    }
    Ok(entries)
}

/// Lines describing what the code has that the contract does not, and the reverse.
pub fn diff(contract: &BTreeSet<String>, actual: &BTreeSet<String>) -> Vec<String> {
    let mut lines: Vec<String> = actual.difference(contract).map(|e| format!("  added {e}")).collect();
    lines.extend(contract.difference(actual).map(|e| format!("  removed {e}")));
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classifies_entry_points() {
        assert_eq!(classify_call("java/lang/Class", "forName"), Some("reflection"));
        assert_eq!(classify_call("java/time/Instant", "now"), Some("clock"));
        assert_eq!(classify_call("java/time/Instant", "plus"), None);
        assert_eq!(classify_call("java/util/UUID", "randomUUID"), Some("randomness"));
        assert_eq!(classify_call("java/lang/System", "getenv"), Some("environment"));
        assert_eq!(classify_call("java/lang/Math", "abs"), None);
        assert_eq!(classify_call("java/net/URI", "create"), None);
        assert_eq!(classify_call("java/net/Socket", "<init>"), Some("network"));
        assert_eq!(classify_call("java/lang/System", "out"), Some("console"));
    }

    #[test]
    fn diff_and_parse_agree_with_the_file_format() {
        let contract: BTreeSet<String> = ["clock: A.f calls java.time.Instant.now", "library: tools.jackson.databind"].iter().map(|s| s.to_string()).collect();
        let actual: BTreeSet<String> = ["clock: A.f calls java.time.Instant.now", "reflection: A.g calls java.lang.Class.forName"].iter().map(|s| s.to_string()).collect();
        assert_eq!(diff(&contract, &actual), vec!["  added reflection: A.g calls java.lang.Class.forName", "  removed library: tools.jackson.databind"]);
        let parsed = parse("kind: capabilities\nmodule: m, 1 classes, 2 methods\n\nclock:\n  A.f calls java.time.Instant.now\nnetwork: none\n\nlibraries:\n  tools.jackson.databind\n").unwrap();
        assert_eq!(parsed, contract);
    }
}
