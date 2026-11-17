//! Countermodels of the pair of versions (`jvmcontract::pairing`): two versions of a method that give different
//! results when each runs alone on a JVM, and that the generated `RegressionPair.agree` finds agreeing, because it
//! runs both in one JVM, the previous version first, after the scope, and compares exceptions by category. The
//! fixtures are `tests/fixtures/pairing-countermodels` (a shared library, `old/` and `new/`); each version's `main`
//! runs one method alone, and the first test holds the fixtures to what a JVM says. The checker's side of each
//! countermodel, the proofs it should not make, is in the fixtures' README for the stream that changes the pairing
//! (domain-advances-preservation, 2026-11-17); the last test here is what the checker already gets right.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::{equivalence, Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The library, the previous version and the new one, compiled: `None` without a JDK.
struct Classes {
    library: PathBuf,
    old: PathBuf,
    new: PathBuf,
}

fn classes() -> Option<&'static Classes> {
    static OUT: OnceLock<Option<Classes>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/pairing-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("pairing-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let javac = |dir: &str, classpath: Option<&Path>| {
            let files: Vec<PathBuf> = walk(&sources.join(dir));
            let mut c = Command::new("javac");
            c.args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(out.join(dir));
            if let Some(cp) = classpath {
                c.arg("-cp").arg(cp);
            }
            assert!(c.args(&files).status().expect("javac runs").success(), "{dir} compiles");
            out.join(dir)
        };
        let library = javac("lib", None);
        let old = javac("old", Some(&library));
        let new = javac("new", Some(&library));
        Some(Classes { library, old, new })
    })
    .as_ref()
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            files.extend(walk(&path));
        } else if path.extension().is_some_and(|e| e == "java") {
            files.push(path);
        }
    }
    files.sort();
    files
}

/// What each version's `main` prints for each method, each in a JVM of its own whose default locale is English.
#[test]
fn each_version_alone_is_what_a_jvm_says_it_is() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let alone = |version: &Path| {
        ["locale", "flag", "thrown", "argument", "scoped"]
            .iter()
            .map(|m| {
                let cp = std::env::join_paths([version, c.library.as_path()]).unwrap();
                let out = Command::new("java").args(["-Duser.language=en", "-Duser.country=US", "-cp"]).arg(cp).args(["app.Entry", m]).output().expect("java runs");
                assert!(out.status.success(), "{m}: {}", String::from_utf8_lossy(&out.stderr));
                String::from_utf8_lossy(&out.stdout).trim().to_string()
            })
            .collect::<Vec<_>>()
            .join(" ")
    };
    assert_eq!(alone(&c.old), "locale=305 flag=1 thrown=AException argument=IllegalArgumentException scoped=105");
    assert_eq!(alone(&c.new), "locale=105 flag=0 thrown=BException argument=BadArgument scoped=305");
}

fn options(before: &Path, after: &Path, target: &str, work: &str) -> equivalence::Options {
    let c = classes().unwrap();
    let mut o = equivalence::Options::new(before, after, target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.classpath = vec![c.library.clone()];
    o.max_array_length = 2;
    o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("pairing-countermodels").join(work));
    o
}

const ASCII: &str = "s.length() == 1 && s.chars().allMatch(c -> c < 128)";
const SMALL: &str = "k >= 0 && k < 4";

fn verdict(o: &equivalence::Options) -> (Verdict, String) {
    let out = equivalence::run(o).unwrap();
    (out.verdict, out.output)
}

/// What the checker already gets right about the same fixtures: run in the other order (the versions' roles
/// swapped, which changes nothing else in the statement), the library's static the new version reads is still unset,
/// and the pair finds the versions differing on a witness run in the interpreter; with `--before-classpath`, each
/// version has a copy of the library of its own, and the pair finds them differing in either order. So the order of
/// the two calls is observable, and the false proofs of `flag` rest on the shared library and the order together.
#[test]
fn in_the_other_order_or_on_its_own_library_the_pair_sees_the_static_differ() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    for (name, own) in [("flag-swapped", false), ("flag-own", true), ("flag-own-swapped", true)] {
        let (before, after) = if name.ends_with("swapped") { (&c.new, &c.old) } else { (&c.old, &c.new) };
        let mut o = options(before, after, "app.Entry#flag", name);
        o.assume = Some(SMALL.into());
        if own {
            o.before_classpath = Some(vec![c.library.clone()]);
        }
        let (v, out) = verdict(&o);
        assert_eq!(v, Verdict::Violation, "{name}: {out}");
        assert!(out.contains("the two versions differ on flag(k="), "{name}: {out}");
    }
}
