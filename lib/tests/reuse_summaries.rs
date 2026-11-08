//! The reuse stream's R2 tests (`llm-dlc/loops/application-core-reuse.md`): read-only heap helpers. The read
//! footprint of a helper is established from its bytecode, never listed: the frozen quote fixture's `fee` reads its
//! receiver's fee policy only, its `helper-extra-field` defect reads the floor too, and every kind of helper outside
//! the category is refused by name. A helper lifted over its footprint agrees with the helper on a real JVM. Its
//! summary rests on a proof of its own, stored in the proof cache and reused exactly; a helper whose two versions
//! differ, or whose versions read fields of different layouts, has none. On the own checker, with no JBMC.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::classfile::MemberRef;
use jvmcontract::classpath::ClassPath;
use jvmcontract::reuse::{self, footprint};
use jvmcontract::spec::plans::{Effects, OutcomeRelation, Summary};
use jvmcontract::Engine;

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("reuse-summaries").join(name)
}

/// Compiles the Java `sources` (directories of a source tree, later ones replacing the files of earlier ones) into
/// `target/tmp/reuse-summaries/NAME`, once per run of the tests, so that tests side by side never remove each
/// other's classes. The tests need `javac`.
fn compile(name: &str, sources: &[&Path]) -> PathBuf {
    static BUILT: std::sync::Mutex<Vec<String>> = std::sync::Mutex::new(Vec::new());
    let mut built = BUILT.lock().unwrap_or_else(|e| e.into_inner());
    let out = tmp(name).join("classes");
    if built.iter().any(|b| b == name) {
        return out;
    }
    let mut files = std::collections::BTreeMap::new();
    for dir in sources {
        for f in java_files(dir) {
            files.insert(f.strip_prefix(dir).unwrap().to_path_buf(), f.clone());
        }
    }
    let _ = std::fs::remove_dir_all(&out);
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files.values()).status().expect("the tests need javac");
    assert!(status.success(), "{name} compiles");
    built.push(name.to_string());
    out
}

fn compile_text(name: &str, files: &[(&str, &str)]) -> PathBuf {
    let src = tmp(name).join("src");
    let _ = std::fs::remove_dir_all(&src);
    for (path, text) in files {
        let p = src.join(path);
        std::fs::create_dir_all(p.parent().unwrap()).unwrap();
        std::fs::write(p, text).unwrap();
    }
    compile(name, &[&src])
}

fn java_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(dir) else { return out };
    for e in entries {
        let p = e.unwrap().path();
        if p.is_dir() {
            out.extend(java_files(&p));
        } else if p.extension().is_some_and(|x| x == "java") {
            out.push(p);
        }
    }
    out
}

fn quote(build: &str) -> PathBuf {
    let family = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/quote");
    let after = family.join("after");
    match build {
        "before" => compile("quote-before", &[&family.join("before")]),
        "after" => compile("quote-after", &[&after]),
        defect => compile(&format!("quote-{defect}"), &[&after, &family.join("defects").join(defect)]),
    }
}

fn class_path(dir: &Path) -> ClassPath {
    let mut cp = ClassPath::new();
    cp.add(dir).unwrap();
    cp.with_default_jdk()
}

fn fee() -> MemberRef {
    MemberRef::new("quotes/QuoteService", "fee", "(I)J")
}

fn read_names(fp: &footprint::Footprint) -> Vec<&str> {
    fp.fields.iter().map(|f| f.name.as_str()).collect()
}

#[test]
fn the_quote_helpers_footprint_is_its_fee_policy_and_the_defects_extra_read_is_found() {
    for build in ["before", "after"] {
        let fp = footprint::footprint(&class_path(&quote(build)), &fee()).unwrap();
        assert_eq!(read_names(&fp), ["feeCents"], "{build}");
        assert!(fp.calls.is_empty(), "{build}: {:?}", fp.calls);
        assert_eq!(fp.fields[0].declared_by, "quotes/QuoteService");
    }
    let extra = footprint::footprint(&class_path(&quote("helper-extra-field")), &fee()).unwrap();
    assert_eq!(read_names(&extra), ["feeCents", "floorCents"]);
}

const PROBE: &str = r#"package h;
public class Probe {
    long rate; long floor; int count; long[] table = new long[2]; String name = "x"; Probe peer;
    public Probe(long rate, long floor) { this.rate = rate; this.floor = floor; }
    long ok(int n) { long s = 0; for (int i = 0; i < n && i < 4; i++) { s += rate * i; } return Math.max(s, floor) + Scale.of(n) + count / 3; }
    long writes(int n) { count = n; return rate; }
    long allocates(int n) { return new long[n].length; }
    long throwsOwn(int n) { if (n < 0) { throw new IllegalStateException(); } return rate; }
    long staticRead(int n) { return Statics.k + rate; }
    long external(int n) { return System.nanoTime() + rate; }
    long overridden(int n) { return rate; }
    long recursive(int n) { return Scale.down(n) + rate; }
    long escapes(int n) { return Scale.weigh(this, n); }
    long arrayRead(int n) { return table[0]; }
    long divides(int n) { return rate / n; }
    long instanceCall(int n) { return ok(n) + 1; }
    long peerRead(int n) { return peer.rate; }
    synchronized long locked(int n) { return rate; }
    long floating(int n) { return (long) (rate * 1.5); }
    long nameRead(int n) { return name.length(); }
    void nothing(int n) { }
    static long plain(int n) { return n; }
}
"#;

fn probe() -> PathBuf {
    compile_text(
        "probe",
        &[
            ("h/Probe.java", PROBE),
            ("h/Sub.java", "package h; public class Sub extends Probe { public Sub() { super(0, 0); } long overridden(int n) { return 0; } }"),
            ("h/Scale.java", "package h; public class Scale { public static long of(int n) { return n < 0 ? -n : n; } static long down(int n) { return n <= 0 ? 0 : down(n - 1); } static long weigh(Probe p, int n) { return n; } }"),
            ("h/Statics.java", "package h; public class Statics { static int k = 3; }"),
        ],
    )
}

/// Every kind of helper the category leaves out is refused, by what it does: the brief's exclusions (a write, an
/// allocation, an exception of its own, an external call, a dispatch the class path doesn't fix, recursion, an
/// escaping reference, an array) and the rest of what the footprint's proof rests on.
#[test]
fn each_kind_of_helper_outside_the_category_is_refused_by_name() {
    let cp = class_path(&probe());
    let ok = footprint::footprint(&cp, &MemberRef::new("h/Probe", "ok", "(I)J")).unwrap();
    assert_eq!(read_names(&ok), ["count", "floor", "rate"]);
    assert_eq!(ok.calls.iter().map(|c| format!("{}.{}", c.owner, c.name)).collect::<Vec<_>>(), ["java/lang/Math.max", "h/Scale.of"]);
    for (method, descriptor, says) in [
        ("writes", "(I)J", "writes a field: not read-only"),
        ("allocates", "(I)J", "allocates"),
        ("throwsOwn", "(I)J", "creates an exception of its own: not total"),
        ("staticRead", "(I)J", "reads a static field"),
        ("external", "(I)J", "calls java.lang.System#nanoTime()J, outside the application and the JDK's arithmetic"),
        ("overridden", "(I)J", "h.Sub overrides it"),
        ("recursive", "(I)J", "is recursive, through h.Scale#down(I)J"),
        ("escapes", "(I)J", "calls h.Scale#weigh(Lh/Probe;I)J, which takes a h.Probe"),
        ("arrayRead", "(I)J", "reads the array field h.Probe.table: bounded primitive arrays come after the field-only case"),
        ("divides", "(I)J", "divides by a value that may be zero"),
        ("instanceCall", "(I)J", "calls h.Probe#ok(I)J on an object"),
        ("peerRead", "(I)J", "reads the reference field h.Probe.peer"),
        ("locked", "(I)J", "synchronizes"),
        ("floating", "(I)J", "floating point"),
        ("nameRead", "(I)J", "reads the reference field h.Probe.name"),
        ("nothing", "(I)V", "returns nothing"),
        ("plain", "(I)J", "it is static"),
    ] {
        let refused = footprint::footprint(&cp, &MemberRef::new("h/Probe", method, descriptor)).expect_err(method);
        assert!(refused.what.contains(says), "{method}: {}", refused.what);
        assert!(refused.what.starts_with(&format!("h.Probe#{method}{descriptor} has no read-only summary")), "{method}: {}", refused.what);
    }
}

/// The lifted helper is the helper as a function of its arguments and its read fields' values: on a real JVM, over a
/// grid, it gives what the helper gives on a receiver holding those values, lifted over its own fields and over more.
/// This is tested, not proved: the proof is the footprint's, in `reuse::footprint`'s documentation.
#[test]
fn a_lifted_helper_agrees_with_the_helper_on_the_jvm() {
    let classes = probe();
    let cp = class_path(&classes);
    let ok = footprint::footprint(&cp, &MemberRef::new("h/Probe", "ok", "(I)J")).unwrap();
    let mut wider = ok.fields.clone();
    // Lifted over a field it doesn't read too, as it is when the other version reads one more.
    let fee = footprint::footprint(&class_path(&quote("helper-extra-field")), &fee()).unwrap();
    let floor = fee.fields.iter().find(|f| f.name == "floorCents").unwrap().clone();
    assert!(footprint::lift(&cp, &ok, &[]).unwrap_err().what.contains("which its lifting leaves out"));
    wider.insert(0, footprint::FieldRead { name: "aaa".into(), descriptor: "J".into(), declared_by: "h/Probe".into() });
    let lifted = footprint::lift(&cp, &ok, &wider).unwrap();
    assert_eq!(lifted.method.owner, "h/Probe$Footprint$ok");
    assert_eq!(lifted.method.descriptor, "(IJIJJ)J", "its argument, then aaa, count, floor and rate");
    let run = tmp("lifted-run");
    let _ = std::fs::remove_dir_all(&run);
    std::fs::create_dir_all(run.join("h")).unwrap();
    std::fs::write(run.join("h/Probe$Footprint$ok.class"), &lifted.bytes).unwrap();
    let driver = r#"package h;
public class Driver {
    public static void main(String[] args) throws Exception {
        java.lang.reflect.Method lifted = Class.forName("h.Probe$Footprint$ok").getMethod("ok", int.class, long.class, int.class, long.class, long.class);
        long[] rates = {-3, 0, 2, 1L << 40, Long.MAX_VALUE};
        long[] floors = {Long.MIN_VALUE, -1, 0, 7};
        int[] counts = {-7, 0, 5, Integer.MAX_VALUE};
        int[] ns = {Integer.MIN_VALUE, -1, 0, 1, 3, 5, 9};
        int cases = 0;
        for (long rate : rates) for (long floor : floors) for (int count : counts) for (int n : ns) {
            Probe p = new Probe(rate, floor);
            p.count = count;
            long want = p.ok(n);
            long got = (Long) lifted.invoke(null, n, 12345L, count, floor, rate);
            if (want != got) { System.out.println("differs at rate=" + rate + " floor=" + floor + " count=" + count + " n=" + n + ": " + want + " != " + got); System.exit(1); }
            cases++;
        }
        System.out.println("agrees on " + cases);
    }
}
"#;
    let src = tmp("lifted-driver");
    let _ = std::fs::remove_dir_all(&src);
    std::fs::create_dir_all(src.join("h")).unwrap();
    std::fs::write(src.join("h/Driver.java"), driver).unwrap();
    let cp_arg = format!("{}:{}", classes.display(), run.display());
    let status = Command::new("javac").args(["-proc:none", "-nowarn", "-cp", &cp_arg, "-d"]).arg(&run).arg(src.join("h/Driver.java")).status().expect("javac");
    assert!(status.success());
    let out = Command::new("java").args(["-cp", &cp_arg, "h.Driver"]).output().expect("the test needs java");
    let printed = String::from_utf8_lossy(&out.stdout);
    assert!(out.status.success() && printed.contains("agrees on 560"), "{printed}{}", String::from_utf8_lossy(&out.stderr));
    // The quote's helper lifted over the union of both versions' reads takes the floor as an argument it ignores.
    let after_fee = footprint::footprint(&class_path(&quote("after")), &MemberRef::new("quotes/QuoteService", "fee", "(I)J")).unwrap();
    let union = [after_fee.fields[0].clone(), floor];
    assert_eq!(footprint::lift(&class_path(&quote("after")), &after_fee, &union).unwrap().method.descriptor, "(IJJ)J");
}

fn options(before: &Path, after: &Path, cache: &Path, run: &str) -> jvmcontract::equivalence::Options {
    let mut o = jvmcontract::equivalence::Options::new(before, after, "quotes.QuoteService#quote");
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.cache = Some(cache.to_path_buf());
    o.timeout_seconds = 300;
    o.work = Some(tmp(run));
    o
}

fn entries(dir: &Path) -> usize {
    let Ok(groups) = std::fs::read_dir(dir.join("claims")) else { return 0 };
    groups.map(|g| std::fs::read_dir(g.unwrap().path()).unwrap().count()).sum()
}

fn fresh(name: &str) -> PathBuf {
    let dir = tmp(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

/// The quote's `fee`, rewritten from a conditional expression to an early return, has a summary: its two versions,
/// lifted over the fee policy, are proved to give the same result on every value of it and of the line count, and
/// the proof is in the cache under the key the summary names. Asked again, the proof is the stored one, under the
/// same key. The defect whose helper also reads the floor has none: lifted over both fields, its versions differ.
#[test]
fn a_helpers_summary_rests_on_its_own_proof_and_a_helper_reading_an_extra_field_has_none() {
    let cache = fresh("summary-cache");
    let o = options(&quote("before"), &quote("after"), &cache, "summary-cold");
    let summary = reuse::summarize(&o, &fee(), &tmp("summary-cold")).unwrap();
    assert_eq!(summary.helper, "quotes.QuoteService#fee(I)J");
    assert_eq!(summary.reads, ["this.feeCents", "arg0"]);
    assert!(summary.facts.is_empty() && summary.depends_on.is_empty(), "{summary:?}");
    assert_eq!((summary.relation.clone(), summary.effects.clone()), (OutcomeRelation::Equal, Effects::ReadOnly));
    assert!(summary.domain.contains("every value of the fields it reads (this.feeCents) and of its arguments"), "{}", summary.domain);
    let hex = summary.proof.strip_prefix("sha256:").expect("a claim key");
    let stored: serde_json::Value = serde_json::from_slice(&std::fs::read(cache.join("claims").join(&hex[..2]).join(format!("{hex}.json"))).unwrap()).unwrap();
    assert_eq!(stored["outcome"]["verdict"], "verified", "{stored}");
    // The summary is the shared applicability record, and reads back as written.
    let written = serde_json::to_value(&summary).unwrap();
    assert_eq!(serde_json::from_value::<Summary>(written).unwrap(), summary);

    let stored_before = entries(&cache);
    let again = reuse::summarize(&options(&quote("before"), &quote("after"), &cache, "summary-rerun"), &fee(), &tmp("summary-rerun")).unwrap();
    assert_eq!(again, summary, "the same claim, reused");
    assert_eq!(entries(&cache), stored_before, "nothing new is stored");

    let extra = reuse::summarize(&options(&quote("before"), &quote("helper-extra-field"), &cache, "summary-extra"), &fee(), &tmp("summary-extra")).unwrap_err();
    assert!(extra.what.contains("its two versions differ"), "{}", extra.what);
}

/// A field one version reads that the other's receiver doesn't declare is a change of layout: the two versions'
/// reads can't be related without a representation adapter, which nothing establishes, so there is no summary.
#[test]
fn a_helper_whose_versions_read_fields_of_different_layouts_has_no_summary() {
    let before = compile_text("layout-before", &[("l/L.java", "package l; public class L { long a; public L(long a) { this.a = a; } long f(int n) { return a + n; } static long g(L x, int n) { return x.f(n); } }")]);
    let after = compile_text("layout-after", &[("l/L.java", "package l; public class L { long b; public L(long b) { this.b = b; } long f(int n) { return b + n; } static long g(L x, int n) { return x.f(n); } }")]);
    let cache = fresh("layout-cache");
    let mut o = options(&before, &after, &cache, "layout");
    o.target = "l.L#g".into();
    let refused = reuse::summarize(&o, &MemberRef::new("l/L", "f", "(I)J"), &tmp("layout")).unwrap_err();
    assert!(refused.what.contains("the version before's receiver has no instance field l.L.b of type long"), "{}", refused.what);
    assert!(refused.what.contains("no representation adapter is established"), "{}", refused.what);
}
