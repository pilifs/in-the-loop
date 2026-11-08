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
/// The builds compiled so far in this run.
static COMPILED: std::sync::Mutex<Vec<String>> = std::sync::Mutex::new(Vec::new());

fn compile(name: &str, sources: &[&Path]) -> PathBuf {
    let mut built = COMPILED.lock().unwrap_or_else(|e| e.into_inner());
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

/// Writes `files` and compiles them as [`compile`] does, once per run: tests side by side that need one build wait
/// for each other here, rather than rewrite its sources while another compiles them.
fn compile_text(name: &str, files: &[(&str, &str)]) -> PathBuf {
    static WRITING: std::sync::Mutex<()> = std::sync::Mutex::new(());
    let _writing = WRITING.lock().unwrap_or_else(|e| e.into_inner());
    let built = tmp(name).join("classes");
    if COMPILED.lock().unwrap_or_else(|e| e.into_inner()).iter().any(|b| b == name) {
        return built;
    }
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

// R2 at a caller: a changed helper's summary, proved on its own, reused by a changed caller at each of its calls.

const TARIFF_BEFORE: &str = "package r;
public class Tariff {
    long feeCents;
    long floorCents;
    public Tariff(long feeCents, long floorCents) { this.feeCents = feeCents; this.floorCents = floorCents; }
    long fee(int lines) { return lines <= 2 ? feeCents : feeCents / 2; }
}
";
/// A safe rewrite of the helper.
const TARIFF_AFTER: &str = "package r;
public class Tariff {
    long feeCents;
    long floorCents;
    public Tariff(long feeCents, long floorCents) { this.feeCents = feeCents; this.floorCents = floorCents; }
    long fee(int lines) {
        if (lines > 2) {
            return feeCents / 2;
        }
        return feeCents;
    }
}
";
/// The helper starts reading an extra field.
const TARIFF_EXTRA: &str = "package r;
public class Tariff {
    long feeCents;
    long floorCents;
    public Tariff(long feeCents, long floorCents) { this.feeCents = feeCents; this.floorCents = floorCents; }
    long fee(int lines) {
        if (lines > 2) {
            return feeCents / 2 < floorCents ? floorCents : feeCents / 2;
        }
        return feeCents;
    }
}
";
const BILL_BEFORE: &str = "package r;
public class Bill {
    static long total(Tariff t, int lines, long amount) { return amount + t.fee(lines); }
    static long twice(Tariff t, int lines) { long a = t.fee(lines); t.feeCents = t.feeCents + 1; long b = t.fee(lines); return a + b; }
    static long pair(Tariff a, Tariff b, int lines) { a.feeCents = 7; return b.fee(lines); }
}
";
/// A safe rewrite of every caller.
const BILL_AFTER: &str = "package r;
public class Bill {
    static long total(Tariff t, int lines, long amount) { long f = t.fee(lines); return f + amount; }
    static long twice(Tariff t, int lines) { long a = t.fee(lines); t.feeCents++; return a + t.fee(lines); }
    static long pair(Tariff a, Tariff b, int lines) { a.feeCents = 7; long r = b.fee(lines); return r; }
}
";
/// Defects: `twice` reuses the fee read before its mutation of the fee, and `pair` reads before the write, which
/// differs only when the two tariffs are one.
const BILL_STALE: &str = "package r;
public class Bill {
    static long total(Tariff t, int lines, long amount) { long f = t.fee(lines); return f + amount; }
    static long twice(Tariff t, int lines) { long a = t.fee(lines); t.feeCents++; return a + a; }
    static long pair(Tariff a, Tariff b, int lines) { long r = b.fee(lines); a.feeCents = 7; return r; }
}
";

fn tariff(build: &str) -> PathBuf {
    let (tariff, bill) = match build {
        "before" => (TARIFF_BEFORE, BILL_BEFORE),
        "after" => (TARIFF_AFTER, BILL_AFTER),
        "stale" => (TARIFF_AFTER, BILL_STALE),
        "extra" => (TARIFF_EXTRA, BILL_AFTER),
        _ => unreachable!(),
    };
    compile_text(&format!("tariff-{build}"), &[("r/Tariff.java", tariff), ("r/Bill.java", bill)])
}

fn tariff_fee() -> MemberRef {
    MemberRef::new("r/Tariff", "fee", "(I)J")
}

fn bill(after: &str, target: &str, cache: &Path, run: &str) -> jvmcontract::equivalence::Outcome {
    let mut o = options(&tariff("before"), &tariff(after), cache, run);
    o.target = format!("r.Bill#{target}");
    jvmcontract::equivalence::run(&o).unwrap()
}

fn summaries_used(outcome: &jvmcontract::equivalence::Outcome) -> Vec<(String, String)> {
    let stated = outcome.stated.as_ref().expect("a statement");
    stated.assumptions.iter().filter(|a| a.kind == jvmcontract::statement::AssumptionKind::Summary).map(|a| (a.id.clone().unwrap_or_default(), a.text.clone())).collect()
}

fn reproduced(outcome: &jvmcontract::equivalence::Outcome) -> bool {
    outcome.verdict == jvmcontract::Verdict::Violation && outcome.replay.as_ref().is_some_and(|r| r.reproduced)
}

/// The summary a claim carries, read back from its assumption's text: the whole applicability record.
fn carried(text: &str) -> Summary {
    serde_json::from_str(&text[text.find('{').expect("the summary's JSON")..]).unwrap()
}

/// The tariff's `fee`, rewritten, has a summary proved on its own and stored. A changed caller then reuses it: its
/// claim carries the whole summary, under its proof's key, and its proof applies the summary at each call, in both
/// versions, through an adapter that reads the fee policy from the actual receiver. Two calls on one tariff around a
/// mutation of the policy are two inputs, and so is a call on a tariff another parameter may write. An unchanged
/// rerun of the caller is an exact hit of its own claim.
#[test]
fn a_changed_callers_proof_reuses_the_helpers_summary_at_each_call() {
    let cache = fresh("caller-cache");
    let summary = reuse::summarize(&options(&tariff("before"), &tariff("after"), &cache, "caller-helper"), &tariff_fee(), &tmp("caller-helper")).unwrap();
    assert_eq!(summary.reads, ["this.feeCents", "arg0"]);
    assert_eq!(entries(&cache), 1, "the helper's own proof");

    let total = bill("after", "total", &cache, "caller-total");
    assert_eq!(total.verdict, jvmcontract::Verdict::Verified, "{}", total.output);
    let used = summaries_used(&total);
    assert_eq!(used.len(), 1, "{used:?}");
    assert_eq!(used[0].0, summary.proof, "the assumption's id is the helper proof's claim key");
    assert_eq!(carried(&used[0].1), summary, "the claim carries the whole summary, its reads included");
    assert!(total.output.contains("Tariff.fee, changed, is applied by its summary at each call in both versions") && total.output.contains("found in the proof cache"), "{}", total.output);
    assert!(total.proof.as_deref().unwrap_or("").contains("Tariff.fee changed, applied by its summary at each call"), "{:?}", total.proof);
    assert_eq!(entries(&cache), 2, "the caller's claim is new, and the helper's proof is the one stored");
    // Each call in both versions goes to its version's adapter, which reads the fee from the receiver it is given.
    let substituted = total.work.join("substituted-classes");
    for class in ["r/Bill.class", "before/r/Bill.class", "r/Tariff$Footprint$fee.class", "r/Tariff$Footprint$fee$Call.class"] {
        assert!(substituted.join(class).exists(), "{class} in {}", substituted.display());
    }

    for target in ["twice", "pair"] {
        let o = bill("after", target, &cache, &format!("caller-{target}"));
        assert_eq!(o.verdict, jvmcontract::Verdict::Verified, "{target}: {}", o.output);
        assert_eq!(summaries_used(&o).iter().map(|(k, _)| k.as_str()).collect::<Vec<_>>(), [summary.proof.as_str()], "{target}");
    }
    let mut o = options(&tariff("before"), &tariff("after"), &cache, "caller-pair-alias");
    o.target = "r.Bill#pair".into();
    o.may_alias = vec![("a".into(), "b".into())];
    let aliased = jvmcontract::equivalence::run(&o).unwrap();
    assert_eq!(aliased.verdict, jvmcontract::Verdict::Verified, "{}", aliased.output);

    let again = bill("after", "total", &cache, "caller-total-again");
    assert_eq!(again.verdict, jvmcontract::Verdict::Verified);
    assert!(matches!(again.reuse, Some(jvmcontract::spec::cache::Reuse::Exact { .. })), "{}", again.output);
}

/// The summary is applied on the receiver's state at each call, so a caller that reuses a fee read before it
/// mutated the policy is refuted, and so is one whose read comes before a write through another parameter, once the
/// two may be one tariff (and only then). Each witness replays.
#[test]
fn a_caller_that_reads_the_receiver_before_its_mutation_or_through_an_alias_is_refuted() {
    let cache = fresh("stale-cache");
    let twice = bill("stale", "twice", &cache, "stale-twice");
    assert!(reproduced(&twice), "{}", twice.output);
    assert_eq!(summaries_used(&twice).len(), 1, "refuted with the summary applied: {}", twice.output);

    let apart = bill("stale", "pair", &cache, "stale-pair");
    assert_eq!(apart.verdict, jvmcontract::Verdict::Verified, "two tariffs: the write is to the other one: {}", apart.output);
    let mut o = options(&tariff("before"), &tariff("stale"), &cache, "stale-pair-alias");
    o.target = "r.Bill#pair".into();
    o.may_alias = vec![("a".into(), "b".into())];
    let aliased = jvmcontract::equivalence::run(&o).unwrap();
    assert!(reproduced(&aliased), "{}", aliased.output);
    assert_eq!(summaries_used(&aliased).len(), 1, "{}", aliased.output);
}

/// A helper that starts reading an extra field has no summary (lifted over both fields, its versions differ), so
/// its caller keeps its body in both versions and is refuted on the floor it now reads, with a replayed witness.
#[test]
fn a_caller_of_a_helper_reading_an_extra_field_keeps_its_body_and_is_refuted() {
    let cache = fresh("extra-cache");
    let total = bill("extra", "total", &cache, "extra-total");
    assert!(total.output.contains("Tariff.fee, changed, keeps its body in both versions") && total.output.contains("its two versions differ"), "{}", total.output);
    assert!(summaries_used(&total).is_empty());
    assert!(reproduced(&total), "{}", total.output);
}

const CLAMPED_BEFORE: &str = "package p;
public class Tariff {
    long feeCents;
    public Tariff(long feeCents) { this.feeCents = feeCents < 0 ? 0 : feeCents; }
    long fee(int lines) { return lines <= 2 ? feeCents : feeCents / 2; }
}
";
/// Halving by a shift: the same as before on every fee the constructor makes (none is negative), not on a negative
/// odd one.
const CLAMPED_AFTER: &str = "package p;
public class Tariff {
    long feeCents;
    public Tariff(long feeCents) { this.feeCents = feeCents < 0 ? 0 : feeCents; }
    long fee(int lines) { return lines <= 2 ? feeCents : feeCents >> 1; }
}
";
const CLAMPED_BILL: &str = "package p;
public class Bill {
    static long once(Tariff t, int lines) { return t.fee(lines); }
    static long again(Tariff t, int lines) { long a = t.fee(lines); t.feeCents = t.feeCents - 3; return a + t.fee(lines); }
}
";

/// A helper whose versions agree only on what its constructor makes: its precondition (a fee that isn't negative)
/// holds at a first call on a constructor-made tariff and not at a second one after the caller lowered the fee. No
/// summary is offered: a summary is proved on every value of the fields it reads, and a proof over constructor-made
/// receivers would not cover the state the caller reached. So the callers keep the helper's body: a single call on a
/// constructor-made tariff is verified, as the constructor domain makes it, and the second call is refuted, replayed.
#[test]
fn a_summary_over_constructor_made_receivers_is_not_offered_where_a_later_call_breaks_its_precondition() {
    let before = compile_text("clamped-before", &[("p/Tariff.java", CLAMPED_BEFORE), ("p/Bill.java", CLAMPED_BILL)]);
    let after = compile_text("clamped-after", &[("p/Tariff.java", CLAMPED_AFTER), ("p/Bill.java", CLAMPED_BILL)]);
    let cache = fresh("clamped-cache");
    let run = |target: &str| {
        let mut o = options(&before, &after, &cache, &format!("clamped-{target}"));
        o.target = format!("p.Bill#{target}");
        jvmcontract::equivalence::run(&o).unwrap()
    };
    let once = run("once");
    assert!(once.output.contains("Tariff.fee, changed, keeps its body in both versions") && once.output.contains("its two versions differ"), "{}", once.output);
    assert_eq!(once.verdict, jvmcontract::Verdict::Verified, "{}", once.output);
    assert!(summaries_used(&once).is_empty());
    let again = run("again");
    assert!(summaries_used(&again).is_empty());
    assert!(reproduced(&again), "{}", again.output);
}

/// The classes a caller's proof runs with its summary applied (its callers redirected to the adapters, the lifted
/// helper and the adapters) give, on a real JVM over a grid, what the versions as written give. Tested, not proved.
/// The adapters read fields of the other package's receiver classes, so every class runs opened, as a JVM replay of
/// a harness runs them ([`jvmcontract::relocate::opened`]).
#[test]
fn a_callers_classes_with_the_summary_applied_agree_with_the_versions_as_written_on_the_jvm() {
    let cache = fresh("jvm-cache");
    let total = bill("after", "twice", &cache, "jvm-twice");
    assert_eq!(total.verdict, jvmcontract::Verdict::Verified, "{}", total.output);
    let run = tmp("jvm-run");
    let _ = std::fs::remove_dir_all(&run);
    let open = |from: &Path, to: &Path| {
        for f in java_class_files(from) {
            let target = to.join(f.strip_prefix(from).unwrap());
            std::fs::create_dir_all(target.parent().unwrap()).unwrap();
            std::fs::write(&target, jvmcontract::relocate::opened(&std::fs::read(&f).unwrap()).unwrap()).unwrap();
        }
    };
    let applied = run.join("applied");
    let written = run.join("written");
    for (dir, with) in [(&applied, true), (&written, false)] {
        open(&tariff("after"), dir);
        open(&total.work.join("before-classes"), dir);
        if with {
            open(&total.work.join("substituted-classes"), dir);
        }
    }
    let driver = r#"package drv;
public class Driver {
    public static void main(String[] args) throws Exception {
        long[] fees = {Long.MIN_VALUE, -7, -1, 0, 1, 2, 9, Long.MAX_VALUE};
        int[] lines = {Integer.MIN_VALUE, -1, 0, 2, 3, 7};
        StringBuilder out = new StringBuilder();
        for (String version : new String[] {"before.r", "r"}) {
            Class<?> tariff = Class.forName(version + ".Tariff");
            Class<?> bill = Class.forName(version + ".Bill");
            java.lang.reflect.Constructor<?> make = tariff.getDeclaredConstructor(long.class, long.class);
            java.lang.reflect.Method total = bill.getDeclaredMethod("total", tariff, int.class, long.class);
            java.lang.reflect.Method twice = bill.getDeclaredMethod("twice", tariff, int.class);
            java.lang.reflect.Method pair = bill.getDeclaredMethod("pair", tariff, tariff, int.class);
            for (java.lang.reflect.Method m : new java.lang.reflect.Method[] {total, twice, pair}) m.setAccessible(true);
            for (long fee : fees) for (int n : lines) {
                Object t = make.newInstance(fee, 3L);
                out.append(total.invoke(null, t, n, 5L)).append(' ').append(twice.invoke(null, t, n)).append(' ');
                out.append(pair.invoke(null, make.newInstance(1L, 1L), t, n)).append(' ').append(pair.invoke(null, t, t, n)).append('\n');
                try { total.invoke(null, null, n, 5L); } catch (java.lang.reflect.InvocationTargetException e) { out.append(e.getCause().getClass().getName()).append('\n'); }
            }
        }
        System.out.print(out);
    }
}
"#;
    let src = run.join("src/drv");
    std::fs::create_dir_all(&src).unwrap();
    std::fs::write(src.join("Driver.java"), driver).unwrap();
    let classes = run.join("driver");
    assert!(Command::new("javac").args(["-proc:none", "-nowarn", "-d"]).arg(&classes).arg(src.join("Driver.java")).status().expect("javac").success());
    let output = |dir: &Path| {
        let out = Command::new("java").args(["-Xverify:all", "-cp"]).arg(format!("{}:{}", classes.display(), dir.display())).arg("drv.Driver").output().expect("the test needs java");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8(out.stdout).unwrap()
    };
    let (with, without) = (output(&applied), output(&written));
    assert_eq!(with.lines().count(), 2 * 8 * 6 * 2, "{with}");
    assert!(with.contains("java.lang.NullPointerException"), "a call on null still throws: {with}");
    assert_eq!(with, without);
}

fn java_class_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(dir) else { return out };
    for e in entries {
        let p = e.unwrap().path();
        if p.is_dir() {
            out.extend(java_class_files(&p));
        } else if p.extension().is_some_and(|x| x == "class") {
            out.push(p);
        }
    }
    out
}
