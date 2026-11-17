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
//!     static void fresh() { ... }
//!     static String named(Class<?> c, boolean previous) { ... c.getName(), `before.` taken off for the previous ... }
//!     static boolean same(Class<?> a, Class<?> b) { ... one name, and same(a.getSuperclass(), b.getSuperclass()) ... }
//!     public static boolean agree(P...) {
//!         fresh();
//!         if (meantToChange(COPIES)) { return true; }
//!         fresh();
//!         R a = ZERO; Class<?> ea = null;
//!         try { a = before.pkg.Target.method(COPIES); } catch (Throwable t) { ea = t.getClass(); }
//!         fresh();
//!         R b = ZERO; Class<?> eb = null;
//!         try { b = pkg.Target.method(COPIES); } catch (Throwable t) { eb = t.getClass(); }
//!         return ea == null ? eb == null && EQUAL : eb != null && same(ea, eb);
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
//! - **the scope** (`--unchanged-unless`) is read on the new version's classes, on copies of its own of the array
//!   arguments, and an input on which it throws is not among those the change is meant for, so the versions are
//!   compared on it. A scope that writes a cell of what it is given writes its own copy: until 2026-11-17 it was
//!   given the caller's arrays, and the versions' copies were taken after it, so a scope that zeroed a cell decided
//!   what both versions saw (`tests/fixtures/fresh-pair-countermodels`, `first`);
//! - **an array argument** is each version's own copy (`clone()`), so that neither sees what the other wrote;
//!   a String is immutable and is passed as it is;
//! - **an exception** is its class and each class above it up to `Object`, by name, a copy of the previous
//!   version's class (`before.x.E`) being that class (`x.E`): the versions agree when they return equal results or
//!   throw exceptions whose classes have one name and extend classes of one name, so that every `catch` and every
//!   `instanceof` of a class takes both or neither. Two subclasses of `RuntimeException`, or
//!   `IllegalArgumentException` and a subclass of it, are two answers (the countermodels of
//!   `tests/fixtures/pairing-countermodels`, 2026-11-17, which a comparison by the categories of
//!   [`crate::harness::EXCEPTIONS`] proved to agree), and so are two classes of one name of which one extends
//!   `IllegalArgumentException` and the other `IllegalStateException` (`tests/fixtures/fresh-pair-countermodels`,
//!   `failing`, which a comparison by the class's name alone proved to agree). The interfaces a class implements are
//!   not compared: an `instanceof` of an interface may tell two such answers apart. A method that declares checked exceptions is refused, not yet taken;
//! - **the result** is compared by `==` for a primitive and by content for a String, two nulls agreeing;
//! - **each version starts as if it ran alone** ([`FRESH`]): the scope, the previous version and the new one each
//!   begin where the checker has given the path a fresh state, the static fields and the classes' initialization
//!   as no call had touched them, and the default locale the JVM's own ([`crate::bmc`], which holds the default
//!   locale among the statics). A version that sets the default locale, writes a library's static (without
//!   `--before-classpath` the library is one copy for both) or initializes a class leaves nothing for the next:
//!   the order of the calls is not observable. Every other object a version reaches is its own (the arrays are
//!   copies, a String is immutable) or one the engine models without content (a class literal, a `Logger`);
//!   JDK state the engine does not model is a call it does not run, which stops the check. A witness is replayed
//!   in the interpreter, which starts each version the same way, or on a JVM, where `fresh()` sets the default
//!   locale back and a library's statics stay shared: a difference only a static shows is then dropped there as
//!   no reproduction, never proved.
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
        return Some("the method declares checked exceptions, which a regression check as a property of the pair of versions (lib/src/pairing.rs) does not take yet".into());
    }
    if !own_checker {
        return Some("a regression check with an assumption, lemmas, a String[] or a nullable String is the tool's own checker's (--engine native or auto, without --confirm): JBMC is given none of them".into());
    }
    None
}

/// The method of the pair's class that stands between the calls: the checker gives each version a fresh state
/// there ([`crate::bmc`]: the static fields and the classes' initialization the path has, the default locale with
/// them, as no call had run yet); on a JVM it does nothing.
pub const FRESH: &str = "fresh";

/// The relocation's package as a binary name's prefix: a copy of the previous version's `x.Y` is `before.x.Y` on a
/// JVM, and `getName()` of it is that ([`crate::relocate`]). The checker gives a copy its own class's name.
const RELOCATED: &str = "before.";

/// The pair's class as Java: see the module's notes.
pub fn source(class: &str, method: &str, names: &[String], params: &[Type], ret: &Type, scope: Option<&str>) -> String {
    let declared = names.iter().zip(params).map(|(n, t)| format!("{} {n}", t.java_name())).collect::<Vec<_>>().join(", ");
    // Each version writes into its own copy of an array.
    let copies = names.iter().zip(params).map(|(n, t)| if matches!(t, Type::Array(_)) { format!("{n} == null ? null : {n}.clone()") } else { n.clone() }).collect::<Vec<_>>().join(", ");
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
        let _ = writeln!(s, "    static boolean {SCOPE_METHOD}({declared}) {{\n        try {{\n            return {scope};\n        }} catch (Throwable t) {{\n            return false;\n        }}\n    }}\n");
    }
    s.push_str("    /** The default locale the first version started under. */\n    private static java.util.Locale start;\n\n");
    s.push_str("    /** Where each version starts: the checker and the interpreter give it a fresh state here, as if it ran alone; on a JVM the default locale is set back to the one the first started under. */\n");
    let _ = writeln!(s, "    static void {FRESH}() {{\n        if (start == null) {{\n            start = java.util.Locale.getDefault();\n        }} else {{\n            java.util.Locale.setDefault(start);\n        }}\n    }}\n");
    s.push_str("    /** A class's own name: a copy of the previous version's class is that class. */\n");
    let _ = writeln!(s, "    static String named(Class<?> c, boolean previous) {{\n        String name = c.getName();\n        return previous && name.indexOf(\"{RELOCATED}\") == 0 ? name.substring({}) : name;\n    }}\n", RELOCATED.len());
    s.push_str("    /** Whether the previous version's class and the new one's have one name, and so do the classes above them, up to Object. */\n");
    s.push_str("    static boolean same(Class<?> a, Class<?> b) {\n        if (a == null || b == null) {\n            return a == b;\n        }\n        return named(a, true).equals(named(b, false)) && same(a.getSuperclass(), b.getSuperclass());\n    }\n\n");
    let _ = writeln!(s, "    public static boolean {METHOD}({declared}) {{");
    // The first call keeps the state every version is to start in, before the scope can change it.
    let _ = writeln!(s, "        {FRESH}();");
    if scope.is_some() {
        let _ = writeln!(s, "        if ({SCOPE_METHOD}({copies})) {{ return true; }}");
    }
    for (var, owner) in [("a", format!("before.{class}")), ("b", class.to_string())] {
        let call = format!("{owner}.{method}({copies});");
        let _ = writeln!(s, "        {FRESH}();");
        if *ret == Type::Void {
            let _ = writeln!(s, "        Class<?> e{var} = null;\n        try {{ {call} }} catch (Throwable t) {{ e{var} = t.getClass(); }}");
        } else {
            let _ = writeln!(s, "        {} {var} = {zero}; Class<?> e{var} = null;\n        try {{ {var} = {call} }} catch (Throwable t) {{ e{var} = t.getClass(); }}", ret.java_name());
        }
    }
    let _ = writeln!(s, "        return ea == null ? eb == null && {equal} : eb != null && same(ea, eb);\n    }}\n}}");
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
pub fn run(options: &Options, work: &Path, relocated_dir: &Path, class: &ClassFile, method: &Method, names: &[String], previous: crate::relocate::Previous, observed: (Vec<String>, Vec<String>)) -> Result<Result<Paired, String>, crate::Error> {
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
    // What the previous version's code asks by name is answered as on its own class path, and an initializer to
    // observe is observed in each version on that version's (`observed`: the new version's classes, then the
    // previous version's).
    property.requested_models = options.requested_models.clone();
    property.observed_initializers = observed.0;
    property.previous = Some((previous, observed.1));
    let mut outcome = crate::property::run(&property)?;
    if let (crate::Verdict::Verified, Some(change)) = (outcome.verdict, options.unchanged_unless.as_deref()) {
        compared(&mut outcome, &property, change, work)?;
    }
    let own = if options.before_classpath.is_some() { ", each on its own dependency closure" } else { "" };
    let scope = match &options.unchanged_unless {
        Some(s) => format!(", outside the inputs the change is meant to affect (`{s}`, read on the new version)"),
        None => String::new(),
    };
    let note = format!(
        "note: checked as a property of the pair of versions: {CLASS}.{METHOD} ({}) calls the previous version's {target}, relocated under `before`, and then the new one's on the same inputs{own}{scope}, each array argument a copy of its own, and returns whether they returned equal results or threw exceptions of classes of one name that extend classes of one name up to Object (a copy's class being its own; the interfaces are not compared). Each starts as if it ran alone: the scope, the previous version and the new one each from a fresh state of the static fields, the classes' initialization and the default locale",
        statement.display(),
        target = options.target,
    );
    Ok(Ok(Paired { outcome, statement, note }))
}

/// The name of the generated method that says whether an input is inside the allowed change.
pub const SCOPE_METHOD: &str = "meantToChange";

/// Whether a proof of the pair compares the versions on any input. `agree` returns true on an input inside the
/// allowed change without calling either version, and the property check's own probe asks only for an input of the
/// assumption: alone it would call a proof non-vacuous whose every assumed input lies inside the change (with
/// `--unchanged-unless true`, every proof). So `meantToChange` is checked against `result` over the same assumption,
/// domain and class path. A proof says every assumed input is inside the change, and the pair's proof is vacuous; a
/// witness, which the property check replays as it replays any, is an assumed input outside the change, on which
/// both versions are called, and becomes the statement's witness, said to lie outside the change; no verdict
/// leaves it unknown. The pair's statement and output say which.
fn compared(outcome: &mut crate::property::Outcome, property: &crate::property::Options, change: &str, work: &Path) -> Result<(), crate::Error> {
    use crate::statement::Vacuity;
    let mut inside = property.clone();
    inside.target = format!("{CLASS}#{SCOPE_METHOD}");
    inside.assert = Some("result".into());
    inside.throws = Vec::new();
    inside.lemmas = None;
    inside.work = Some(work.join("pair-outside"));
    let checked = crate::property::run(&inside)?;
    let (vacuity, line) = match checked.verdict {
        crate::Verdict::Violation => {
            let witness = checked.counterexample.as_ref().map(|c| c.input.replacen(SCOPE_METHOD, METHOD, 1));
            let line = format!("  outside the allowed change: {} lies outside `{change}`, so both versions are called on it", witness.as_deref().unwrap_or("an input"));
            (Vacuity::reached(witness).outside_of(change), line)
        }
        crate::Verdict::Verified => {
            let reason = format!("every input in the domain where the assumption holds lies inside the allowed change `{change}`, on which {METHOD} returns true without calling either version; the proof compares the versions on none and says nothing");
            outcome.vacuous = Some(reason.clone());
            (Vacuity::vacuous(&reason), format!("  vacuously: {reason}"))
        }
        crate::Verdict::Unverifiable => {
            let problem = checked.problem.clone().unwrap_or_else(|| "no reason".into());
            let line = format!("  vacuity unknown: whether any input where the assumption holds lies outside the allowed change `{change}` is not known: the check of {SCOPE_METHOD} gave no verdict ({problem})");
            (Vacuity::unknown(&problem), line)
        }
    };
    let _ = writeln!(outcome.output, "{line}");
    if let Some(stated) = outcome.stated.as_mut() {
        stated.vacuity = Some(vacuity);
    }
    if let (Some(search), Some(other)) = (outcome.search.as_mut(), checked.search) {
        search.runs.extend(other.runs.into_iter().map(|mut r| {
            r.purpose = format!("outside-change {}", r.purpose);
            r
        }));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The statement as Java: a fresh state first, the scope read on copies of its own and a throw in it compared, each version from a
    /// fresh state on its own copy of an array, an exception by its class and those above it, the previous version's
    /// copy taken for its own class, a String result compared by content.
    #[test]
    fn the_pairs_class_calls_both_versions_on_copies_from_fresh_states_and_compares_results_and_classes() {
        let names: Vec<String> = ["k", "patterns", "field"].iter().map(|s| s.to_string()).collect();
        let params = vec![Type::Int, Type::Array(Box::new(Type::Object("java/lang/String".into()))), Type::Object("java/lang/String".into())];
        let java = source("x.Adapter", "allowed", &names, &params, &Type::Boolean, Some("k == 2"));
        assert!(java.contains("static boolean meantToChange(int k, java.lang.String[] patterns, java.lang.String field)"), "{java}");
        assert!(java.contains("return k == 2;") && java.contains("catch (Throwable t) {\n            return false;"), "{java}");
        let fresh = |at: &str| java.find(at).unwrap_or_else(|| panic!("{at}: {java}"));
        let calls = [fresh("public static boolean agree"), fresh("        fresh();\n        if (meantToChange(k, patterns == null ? null : patterns.clone(), field)) { return true; }\n        fresh();\n        boolean a"), fresh("a = before.x.Adapter.allowed(k, patterns == null ? null : patterns.clone(), field);"), fresh("        fresh();\n        boolean b"), fresh("b = x.Adapter.allowed(k, patterns == null ? null : patterns.clone(), field);")];
        assert!(calls.windows(2).all(|w| w[0] < w[1]), "{java}");
        assert!(java.contains("Class<?> ea = null;\n        try { a = before.x.Adapter") && java.contains("catch (Throwable t) { ea = t.getClass(); }") && java.contains("catch (Throwable t) { eb = t.getClass(); }"), "{java}");
        assert!(java.contains("return previous && name.indexOf(\"before.\") == 0 ? name.substring(7) : name;") && java.contains("return named(a, true).equals(named(b, false)) && same(a.getSuperclass(), b.getSuperclass());"), "{java}");
        assert!(java.contains("return ea == null ? eb == null && a == b : eb != null && same(ea, eb);"), "{java}");
        let text = source("x.A", "name", &names[..1], &params[..1], &Type::Object("java/lang/String".into()), None);
        assert!(!text.contains("meantToChange") && text.contains("(a == null ? b == null : a.equals(b))"), "{text}");
        let nothing = source("x.A", "run", &names[..1], &params[..1], &Type::Void, None);
        assert!(nothing.contains("try { before.x.A.run(k); }") && nothing.contains("return ea == null ? eb == null && true : eb != null && same(ea, eb);"), "{nothing}");
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
