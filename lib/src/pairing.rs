//! A regression check as a property of the pair: both versions called by one method that says whether they agree.
//!
//! The regression harness ([`crate::harness`]) makes its inputs itself, and takes what it has learned to make:
//! numbers, arrays of them, records, objects by their constructors, a String, a list. A library's entry point
//! often takes more of what a property check already takes ([`crate::property`]): a `String[]` whose elements may
//! be null, a String or an array that may be null, a domain stated in Java with a lambda in it. For those the
//! regression claim is stated as Java and checked as a property. [`CLASS`] is written beside the two versions,
//!
//! ```java
//! public final class RegressionPair {
//!     static boolean meantToChange(P...) { try { return SCOPE; } catch (Throwable t) { return false; } }
//!     public static boolean agree(P...) {
//!         if (meantToChange(p...)) { return true; }
//!         R a = ZERO; int ea = 0;
//!         try { a = before.pkg.Target.method(COPIES); } catch (NumberFormatException t) { ea = 1; } catch ...
//!         R b = ZERO; int eb = 0;
//!         try { b = pkg.Target.method(COPIES); } catch (NumberFormatException t) { eb = 1; } catch ...
//!         return ea == eb && (ea != 0 || EQUAL);
//!     }
//! }
//! ```
//!
//! and compiled by javac against both: the previous version relocated under `before`, with its own dependency
//! closure when it has one ([`crate::relocate::with_closure`]), exactly as the harness's own check has it. The
//! claim is then `agree` returns true on every input of the assumption, which the property check proves or refutes
//! with everything it has: the tool's own checker, its String and array inputs, lemmas, and a witness run on a
//! JVM. It is the statement the harness's Java rendering makes (`EquivalenceHarness.java`), with these readings:
//!
//! - **the scope** (`--unchanged-unless`) is read on the new version's classes, and an input on which it throws
//!   is not among those the change is meant for, so the versions are compared on it;
//! - **an array argument** is each version's own copy (`clone()`), so that neither sees what the other wrote;
//!   a String is immutable and is passed as it is;
//! - **an exception** is the category of the first class of [`crate::harness::EXCEPTIONS`] that catches it, and
//!   any other `Throwable` one more category: the versions agree when they return equal results or throw in the
//!   same category. A method that declares checked exceptions is refused here, since two of them would be one
//!   category;
//! - **the result** is compared by `==` for a primitive and by content for a String, two nulls agreeing.
//!
//! What both versions share is the JDK, and with it the JDK's own state: a default locale one version sets is the
//! default the other starts under. The previous version runs first. A target that reads such state before it
//! writes it would be compared under two states; the statement says so.
//!
//! Taken here: a static method whose parameters are integral or boolean values, arrays of them, Strings and
//! `String[]`, and whose result is one of the values, a String or nothing. Asked for by `--assume` or `--lemmas`,
//! by a `String[]` parameter, or by a String parameter named `--nullable`; every other regression check is the
//! harness's, as before.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use crate::classfile::{ClassFile, Method, Type};
use crate::equivalence::Options;

/// The generated class and its method.
pub const CLASS: &str = "RegressionPair";
pub const METHOD: &str = "agree";

/// Whether a check with these options and this target is one this module takes: see the module's notes.
pub fn asked(options: &Options, method: &Method, names: &[String]) -> bool {
    let Ok(descriptor) = method.parsed_descriptor() else { return false };
    options.assume.is_some()
        || options.lemmas.is_some()
        || descriptor.params.iter().any(crate::harness::is_string_array)
        || names.iter().zip(&descriptor.params).any(|(n, t)| crate::values::is_string(t) && options.nullable.contains(n))
}

fn value(t: &Type) -> bool {
    matches!(t, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long)
}

fn parameter(t: &Type) -> bool {
    value(t) || crate::values::is_string(t) || crate::harness::is_string_array(t) || matches!(t, Type::Array(e) if value(e))
}

/// Why the check is not one for this module, in a refusal's words; `None` when it is. `own_checker` is whether
/// the check is the tool's own checker's alone (`--engine native` or `auto`, without `--confirm`).
pub fn refusal(options: &Options, method: &Method, before: Option<&Method>, own_checker: bool) -> Option<String> {
    let descriptor = method.parsed_descriptor().ok()?;
    if options.plan.is_some() || options.correspondence.is_some() || options.before_target.is_some() || options.before_arguments.is_some() || options.results_agree_when.is_some() || !options.may_alias.is_empty() {
        return Some("a regression check with an assumption, lemmas, a String[] or a nullable String is checked as a property of the pair of versions (lib/src/pairing.rs), which takes no plan, correspondence, --before-target, --before-arguments, --results-agree-when or --may-alias yet".into());
    }
    if !method.is_static() {
        return Some("a regression check with an assumption, lemmas, a String[] or a nullable String is checked as a property of the pair of versions (lib/src/pairing.rs), which takes a static method".into());
    }
    if let Some(t) = descriptor.params.iter().find(|t| !parameter(t)) {
        return Some(format!("a regression check with an assumption, lemmas, a String[] or a nullable String is checked as a property of the pair of versions (lib/src/pairing.rs), which takes integral and boolean parameters, arrays of them, Strings and String[]: not a {}", t.java_name()));
    }
    if !(descriptor.ret == Type::Void || value(&descriptor.ret) || crate::values::is_string(&descriptor.ret)) {
        return Some(format!("a regression check as a property of the pair of versions (lib/src/pairing.rs) compares an integral or boolean result, a String or none: not a {}", descriptor.ret.java_name()));
    }
    let Some(before) = before else { return Some("the previous version has no such method: a regression check as a property of the pair of versions calls the same method of both".into()) };
    if before.descriptor != method.descriptor || !before.is_static() {
        return Some("the previous version's method has another descriptor: a regression check as a property of the pair of versions calls the same method of both".into());
    }
    if [method, before].iter().any(|m| m.attributes.iter().any(|a| a.name == "Exceptions")) {
        return Some("the method declares checked exceptions, which a regression check as a property of the pair of versions (lib/src/pairing.rs) would not tell apart".into());
    }
    if !own_checker {
        return Some("a regression check with an assumption, lemmas, a String[] or a nullable String is the tool's own checker's (--engine native or auto, without --confirm): JBMC is given none of them".into());
    }
    None
}

/// The pair's class as Java: see the module's notes.
pub fn source(class: &str, method: &str, names: &[String], params: &[Type], ret: &Type, scope: Option<&str>) -> String {
    let declared = names.iter().zip(params).map(|(n, t)| format!("{} {n}", t.java_name())).collect::<Vec<_>>().join(", ");
    let passed = names.join(", ");
    // Each version writes into its own copy of an array.
    let copies = names.iter().zip(params).map(|(n, t)| if matches!(t, Type::Array(_)) { format!("{n} == null ? null : {n}.clone()") } else { n.clone() }).collect::<Vec<_>>().join(", ");
    let catches = |var: &str| {
        let mut s = String::new();
        for (i, exception) in crate::harness::EXCEPTIONS.iter().enumerate() {
            let _ = write!(s, " catch ({} t) {{ {var} = {}; }}", exception.replace('/', "."), i + 1);
        }
        let _ = write!(s, " catch (Throwable t) {{ {var} = {}; }}", crate::harness::EXCEPTIONS.len() + 1);
        s
    };
    let (zero, equal) = match ret {
        Type::Void => ("", "true"),
        Type::Boolean => ("false", "a == b"),
        t if value(t) => ("0", "a == b"),
        _ => ("null", "(a == null ? b == null : a.equals(b))"),
    };
    let mut s = String::new();
    s.push_str("/** Generated by jvmcontract: both versions of a method called on the same inputs, as one method that says whether they agree (lib/src/pairing.rs). */\n");
    let _ = writeln!(s, "public final class {CLASS} {{");
    let _ = writeln!(s, "    private {CLASS}() {{}}\n");
    if let Some(scope) = scope {
        s.push_str("    /** The inputs the change is meant to affect, read on the new version; an input on which the expression throws is not among them. */\n");
        let _ = writeln!(s, "    static boolean meantToChange({declared}) {{\n        try {{\n            return {scope};\n        }} catch (Throwable t) {{\n            return false;\n        }}\n    }}\n");
    }
    let _ = writeln!(s, "    public static boolean {METHOD}({declared}) {{");
    if scope.is_some() {
        let _ = writeln!(s, "        if (meantToChange({passed})) {{ return true; }}");
    }
    for (var, owner) in [("a", format!("before.{class}")), ("b", class.to_string())] {
        let call = format!("{owner}.{method}({copies});");
        if *ret == Type::Void {
            let _ = writeln!(s, "        int e{var} = 0;\n        try {{ {call} }}{}", catches(&format!("e{var}")));
        } else {
            let _ = writeln!(s, "        {} {var} = {zero}; int e{var} = 0;\n        try {{ {var} = {call} }}{}", ret.java_name(), catches(&format!("e{var}")));
        }
    }
    let _ = writeln!(s, "        return ea == eb && (ea != 0 || {equal});\n    }}\n}}");
    s
}

/// What the check came to, for [`crate::equivalence`] to report as its own.
pub struct Paired {
    pub outcome: crate::property::Outcome,
    /// The generated class's source.
    pub statement: PathBuf,
    /// The header the report begins with.
    pub note: String,
}

/// Writes and compiles the pair's class and proves `agree` of it: see the module's notes. `relocated_dir` holds the
/// previous version under `before`, `class` and `method` are the new version's. `Err` is a refusal, in its words.
pub fn run(options: &Options, work: &Path, relocated_dir: &Path, class: &ClassFile, method: &Method, names: &[String]) -> Result<Result<Paired, String>, crate::Error> {
    let descriptor = method.parsed_descriptor()?;
    let dir = work.join("pair");
    std::fs::create_dir_all(&dir)?;
    let java = source(&class.name.replace('/', "."), &method.name, names, &descriptor.params, &descriptor.ret, options.unchanged_unless.as_deref());
    let statement = dir.join(format!("{CLASS}.java"));
    std::fs::write(&statement, &java)?;
    let home = match &options.java_home {
        Some(h) => h.clone(),
        None => match crate::jimage::JImage::find_java_home() {
            Some(h) => h,
            None => return Ok(Err("no JDK to compile the pair of versions with (set JAVA_HOME)".into())),
        },
    };
    let mut entries: Vec<PathBuf> = vec![options.after.clone(), relocated_dir.to_path_buf()];
    entries.extend(options.classpath.iter().cloned());
    let cp = std::env::join_paths(entries.iter()).map_err(|e| crate::Error::new(e.to_string()))?;
    let javac = home.join("bin").join("javac");
    let compiled = std::process::Command::new(&javac).args(["-proc:none", "-Xlint:none", "-nowarn", "-g", "-parameters", "-cp"]).arg(&cp).arg("-d").arg(&dir).arg(&statement).output().map_err(|e| crate::Error::new(format!("{}: {e}", javac.display())))?;
    if !compiled.status.success() {
        let said = String::from_utf8_lossy(&compiled.stderr);
        let first = said.lines().find(|l| l.contains("error:")).map(|l| l.split("error:").nth(1).unwrap_or(l).trim().to_string()).unwrap_or_else(|| said.trim().to_string());
        return Ok(Err(format!("the regression claim as Java ({}) does not compile: {first}", statement.display())));
    }
    let mut property = crate::property::Options::new(&[dir.clone(), options.after.clone(), relocated_dir.to_path_buf()], &format!("{CLASS}#{METHOD}"));
    property.classpath = options.classpath.clone();
    property.assume = options.assume.clone();
    property.nullable = options.nullable.clone();
    property.lemmas = options.lemmas.clone();
    property.work = Some(work.join("pair-work"));
    property.sources = options.sources.clone();
    property.base = options.base.clone();
    property.unwind = options.unwind;
    property.max_array_length = options.max_array_length;
    property.shrink = options.shrink;
    property.timeout_seconds = options.timeout_seconds;
    property.jbmc = options.jbmc.clone();
    property.java_home = options.java_home.clone();
    property.engine = options.engine;
    property.gaps = options.gaps;
    property.contracts = options.contracts.clone();
    property.contract_library = options.contract_library;
    property.max_trust = options.max_trust;
    let outcome = crate::property::run(&property)?;
    let own = if options.before_classpath.is_some() { ", each on its own dependency closure" } else { "" };
    let scope = match &options.unchanged_unless {
        Some(s) => format!(", outside the inputs the change is meant to affect (`{s}`, read on the new version)"),
        None => String::new(),
    };
    let note = format!(
        "note: checked as a property of the pair of versions: {CLASS}.{METHOD} ({}) calls the previous version's {target}, relocated under `before`, and then the new one's on the same inputs{own}{scope}, each array argument a copy of its own, and returns whether they returned equal results or threw in the same category. The two share the JDK and its state (a default locale one sets is the other's to start under); the previous version runs first",
        statement.display(),
        target = options.target,
    );
    Ok(Ok(Paired { outcome, statement, note }))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The statement as Java: the scope read first and a throw in it compared, each version on its own copy of an
    /// array, the exceptions in the harness's categories with any other Throwable one more, a String result
    /// compared by content.
    #[test]
    fn the_pairs_class_calls_both_versions_on_copies_and_compares_results_and_categories() {
        let names: Vec<String> = ["k", "patterns", "field"].iter().map(|s| s.to_string()).collect();
        let params = vec![Type::Int, Type::Array(Box::new(Type::Object("java/lang/String".into()))), Type::Object("java/lang/String".into())];
        let java = source("x.Adapter", "allowed", &names, &params, &Type::Boolean, Some("k == 2"));
        assert!(java.contains("static boolean meantToChange(int k, java.lang.String[] patterns, java.lang.String field)"), "{java}");
        assert!(java.contains("return k == 2;") && java.contains("catch (Throwable t) {\n            return false;"), "{java}");
        assert!(java.contains("if (meantToChange(k, patterns, field)) { return true; }"), "{java}");
        assert!(java.contains("a = before.x.Adapter.allowed(k, patterns == null ? null : patterns.clone(), field);"), "{java}");
        assert!(java.contains("b = x.Adapter.allowed(k, patterns == null ? null : patterns.clone(), field);"), "{java}");
        assert!(java.contains("catch (java.lang.NumberFormatException t) { ea = 1; }") && java.contains(&format!("catch (Throwable t) {{ eb = {}; }}", crate::harness::EXCEPTIONS.len() + 1)), "{java}");
        assert!(java.contains("return ea == eb && (ea != 0 || a == b);"), "{java}");
        let text = source("x.A", "name", &names[..1], &params[..1], &Type::Object("java/lang/String".into()), None);
        assert!(!text.contains("meantToChange") && text.contains("(a == null ? b == null : a.equals(b))"), "{text}");
        let nothing = source("x.A", "run", &names[..1], &params[..1], &Type::Void, None);
        assert!(nothing.contains("try { before.x.A.run(k); }") && nothing.contains("return ea == eb && (ea != 0 || true);"), "{nothing}");
    }

    /// Only the tool's own checker is given a String[], a nullable String, an assumption or lemmas: any other
    /// engine is refused by name, as is a method the previous version has with another descriptor or not at all.
    #[test]
    fn another_engine_and_a_previous_method_of_another_shape_are_refused_by_name() {
        let method = |descriptor: &str| Method { access: crate::classfile::flags::STATIC, name: "allowed".into(), descriptor: descriptor.into(), code: None, attributes: Vec::new() };
        let taken = method("([Ljava/lang/String;Ljava/lang/String;)Z");
        let options = Options::new(Path::new("before"), Path::new("after"), "x.A#allowed");
        assert!(refusal(&options, &taken, Some(&taken), false).is_some_and(|r| r.contains("JBMC is given none of them")));
        assert_eq!(refusal(&options, &taken, Some(&taken), true), None);
        assert!(refusal(&options, &taken, Some(&method("(Ljava/lang/String;)Z")), true).is_some_and(|r| r.contains("another descriptor")));
        assert!(refusal(&options, &taken, None, true).is_some_and(|r| r.contains("has no such method")));
        assert!(refusal(&options, &method("(Ljava/util/List;)Z"), None, true).is_some_and(|r| r.contains("not a java.util.List")));
    }
}
