//! R3 of `llm-dlc/loops/application-core-reuse.md`: where a small `compare` run spends its time, stage by stage, so
//! that a cache of preparation is added only if a repeated stage is material.
//!
//! The run is the joint example's (examples 190 and 191, the builds of `tests/fixtures/foundations/`): its entry
//! points' effect-trace proofs and its kernel's checks, a changed pure helper proved once and used in its caller.
//! Six scenarios, each repeated: a cold run under a fresh proof cache, an unchanged rerun, a cold run on a real
//! defect (`offset`, a cent more per item, refuted at the route and in the kernel), and its rerun, which replays the
//! stored witnesses; then, for J4, two edits checked from the proof cache a cold run of `after` leaves (a copy of it
//! each time), as a developer's next edit would be: an unrelated edit (`tests/fixtures/preparation/unrelated-edit`, a
//! class nothing reaches, every proof an exact hit) and a safe rewrite of a helper (`helper-rewrite`, `discount`
//! rewritten again: its own proof made again, and `total` proved again on that proof, the helper evidence, while
//! `withQuantity` is an exact hit). Each is timed in process under the ledger of `jvmcontract::reuse::preparation`, proof by proof,
//! and as the `jvmcontract compare` process `build.py` runs. Apart from the runs, the stages a run repeats are timed
//! one by one on the same builds: compiling each build, decoding a build, relocating the old one, aligning the two,
//! reading their entry points' specs, the models' digest a key takes, and the binary's digest the tool identity
//! takes once per process.
//!
//! A benchmark, so a queued job's (`--ignored`); the unit test of the ledger's arithmetic is in the module. The report
//! goes to `$PREPARATION_REPORT` (JSON, with a Markdown table beside it), by default under `CARGO_TARGET_TMPDIR`.

mod foundations_fixture;
use foundations_fixture::{build, builds, root};

use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Instant;

use jvmcontract::compare::{self, Options, Report};
use jvmcontract::reuse::preparation::{self, Proof};
use jvmcontract::spec::cache::Reuse;
use jvmcontract::spec::ClaimBounds;
use serde_json::{json, Value};

fn repeats() -> usize {
    std::env::var("PREPARATION_REPEATS").ok().and_then(|v| v.parse().ok()).unwrap_or(5).max(1)
}

fn median(mut v: Vec<f64>) -> f64 {
    v.sort_by(f64::total_cmp);
    let n = v.len();
    if n == 0 {
        0.0
    } else if n % 2 == 1 {
        v[n / 2]
    } else {
        (v[n / 2 - 1] + v[n / 2]) / 2.0
    }
}

fn ms(s: f64) -> f64 {
    (s * 1e6).round() / 1e3
}

fn timed<T>(f: impl FnOnce() -> T) -> (T, f64) {
    let started = Instant::now();
    let out = f();
    (out, started.elapsed().as_secs_f64())
}

fn options(after: &Path, cache: &Path) -> Options {
    Options { before: build("before").to_path_buf(), after: after.to_path_buf(), cache: Some(cache.to_path_buf()), bounds: ClaimBounds { unwind: 16, max_array_length: 8 }, environment: Vec::new(), domains: Default::default() }
}

/// The sums of a run's proofs, by stage, every level of proof included (a helper's own proof is inside its caller's
/// `helpers`, so that is left out), with what no proof's span covers.
fn stages(proofs: &[Proof], seconds: f64) -> Vec<(&'static str, f64)> {
    let sum = |f: fn(&Proof) -> f64| proofs.iter().map(f).sum::<f64>();
    let (before, plan, key, closures, lookup, store, replay, after, runs, loading, lowering) = (
        sum(|p| p.before),
        sum(|p| p.plan),
        sum(|p| p.key),
        sum(|p| p.closures),
        sum(|p| p.lookup),
        sum(|p| p.store),
        sum(|p| p.replay),
        sum(|p| p.after_lookup),
        sum(|p| p.runs),
        sum(|p| p.loading),
        sum(|p| p.lowering),
    );
    let covered = before + plan + key + lookup + store + after;
    vec![
        ("before each proof: relocating, decoding the target's classes, the layout, the harness, and the caller's steps between proofs", before),
        ("plan: both versions' reach and closures compared", plan),
        ("key: the claim and its digest", key - closures),
        ("key's closures: both versions' closures digested", closures),
        ("lookup: reading the store", lookup - replay.min(lookup)),
        ("checker runs: decoding classes and methods (loading, lowering)", loading + lowering),
        ("checker runs: exploring, encoding and solving", runs - loading - lowering),
        ("after the runs: the witness replayed, shrunk and run on a JVM, the statement", after - runs),
        ("store: writing the result, a refutation's witness replayed first", store),
        ("replay of a stored or new witness (inside lookup and store)", replay),
        ("outside every proof: compare's own steps after the last proof", seconds - covered),
    ]
}

struct Measured {
    seconds: f64,
    proofs: Vec<Proof>,
    report: Report,
}

fn measured(after: &Path, cache: &Path) -> Measured {
    preparation::begin();
    let (report, _) = timed(|| compare::run(&options(after, cache)));
    let ledger = preparation::end().expect("the ledger begun");
    let report = report.unwrap_or_else(|u| panic!("compare before {}: {u}", after.display()));
    Measured { seconds: ledger.seconds, proofs: preparation::proofs(&ledger), report }
}

/// Every proof's verdict in a report: the entry points' and the kernel's, by subject.
fn verdicts(r: &Report) -> Vec<(String, String)> {
    let mut out: Vec<(String, String)> = r.entries.iter().map(|e| (e.entry.clone(), e.checked.as_ref().map(|c| format!("{:?}", c.outcome.verdict)).unwrap_or_else(|| "unsupported".into()))).collect();
    out.extend(r.kernel.iter().map(|k| (k.subject.clone(), k.outcome.as_ref().map(|o| format!("{:?}", o.verdict)).unwrap_or_else(|| "unsupported".into()))));
    out
}

/// How each proof of a report was reached: an exact hit of its claim, or proved (by the checker, in this run), with
/// the keys of the changed helpers' own proofs it was proved on (the helper evidence), by subject. A subject with no
/// proof (unsupported, or unresolved before any proof) is `unchecked`.
fn evidence(r: &Report) -> Vec<(String, &'static str, Vec<String>)> {
    let how = |reuse: Option<&Reuse>, proved: bool| match reuse {
        Some(Reuse::Exact { .. }) => "exact hit",
        _ if proved => "proved",
        _ => "unchecked",
    };
    let mut out: Vec<(String, &'static str, Vec<String>)> = r.entries.iter().map(|e| (e.entry.clone(), how(e.checked.as_ref().and_then(|c| c.reuse.as_ref()), e.checked.as_ref().is_some_and(|c| c.key.is_some())), Vec::new())).collect();
    out.extend(r.kernel.iter().map(|k| {
        let callees = k.callees.iter().filter_map(|c| if let Reuse::Callee { callee, key } = c { Some(format!("{callee} {}", key.0)) } else { None }).collect();
        (k.subject.clone(), how(k.reuse.as_ref(), k.outcome.is_some()), callees)
    }));
    out
}

fn evidence_rows(r: &Report) -> Value {
    Value::Array(evidence(r).into_iter().map(|(subject, how, callees)| json!({"subject": subject, "reached": how, "helper_proofs": callees})).collect())
}

/// A copy of the directory `from` at `to`, which is removed first.
fn copy_dir(from: &Path, to: &Path) {
    let _ = std::fs::remove_dir_all(to);
    std::fs::create_dir_all(to).unwrap();
    for entry in std::fs::read_dir(from).unwrap() {
        let path = entry.unwrap().path();
        let target = to.join(path.file_name().unwrap());
        if path.is_dir() {
            copy_dir(&path, &target);
        } else {
            std::fs::copy(&path, &target).unwrap();
        }
    }
}

/// `after`'s sources with the overlay `dir`'s files in place of theirs, or added, as the fixtures' defects are made.
fn overlaid(dir: &Path) -> Vec<PathBuf> {
    let after_dir = root().join("after");
    let overlay = java_files(dir);
    let replaced: Vec<PathBuf> = overlay.iter().map(|p| p.strip_prefix(dir).unwrap().to_path_buf()).collect();
    let mut files: Vec<PathBuf> = java_files(&after_dir).into_iter().filter(|p| !replaced.contains(&p.strip_prefix(&after_dir).unwrap().to_path_buf())).collect();
    files.extend(overlay);
    files
}

/// Where a scenario's proof cache starts.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Start {
    /// Empty, every repeat.
    Fresh,
    /// As the same build's run left it.
    Rerun,
    /// A copy of what a cold run of `after` left, every repeat: the next edit after it.
    AfterCold,
}

fn proof_rows(proofs: &[Proof]) -> Value {
    Value::Array(
        proofs
            .iter()
            .map(|p| {
                json!({
                    "target": p.target, "inside": p.inside, "cache": p.cache, "before_ms": ms(p.before), "plan_ms": ms(p.plan),
                    "helpers_ms": ms(p.helpers), "key_ms": ms(p.key), "closures_ms": ms(p.closures), "lookup_ms": ms(p.lookup),
                    "after_lookup_ms": ms(p.after_lookup), "runs_ms": ms(p.runs), "loading_ms": ms(p.loading), "lowering_ms": ms(p.lowering),
                    "store_ms": ms(p.store), "replay_ms": ms(p.replay),
                })
            })
            .collect(),
    )
}

fn java_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            out.extend(java_files(&path));
        } else if path.extension().is_some_and(|e| e == "java") {
            out.push(path);
        }
    }
    out.sort();
    out
}

fn class_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            out.extend(class_files(&path));
        } else if path.extension().is_some_and(|e| e == "class") {
            out.push(path);
        }
    }
    out
}

/// One `javac` of `files` into `out`, as the fixture compiles them, timed.
fn javac(out: &Path, classpath: Option<&Path>, files: &[PathBuf]) -> f64 {
    let _ = std::fs::remove_dir_all(out);
    std::fs::create_dir_all(out).unwrap();
    let mut cmd = Command::new("javac");
    cmd.args(["-g", "-parameters", "-proc:none", "-d"]).arg(out);
    if let Some(cp) = classpath {
        cmd.arg("-cp").arg(cp);
    }
    let (status, seconds) = timed(|| cmd.args(files).status().expect("javac runs"));
    assert!(status.success(), "the fixture compiles into {}", out.display());
    seconds
}

/// The `jvmcontract compare` process on `after`, as build.py runs it, timed; its JSON report's verdicts.
fn process(after: &Path, cache: &Path) -> (f64, Vec<(String, String)>) {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_jvmcontract"));
    cmd.arg("compare").arg("--cache").arg(cache).arg("--json").arg(build("before")).arg(after);
    let (output, seconds) = timed(|| cmd.output().expect("jvmcontract runs"));
    let report: Value = serde_json::from_slice(&output.stdout).unwrap_or_else(|e| panic!("compare's JSON: {e}: {}", String::from_utf8_lossy(&output.stderr)));
    let mut v = Vec::new();
    for e in report["entries"].as_array().into_iter().flatten() {
        v.push((e["entry"].as_str().unwrap_or("").to_string(), e["checked"]["outcome"]["verdict"].as_str().unwrap_or("unsupported").to_string()));
    }
    for k in report["kernel"].as_array().into_iter().flatten() {
        v.push((k["subject"].as_str().unwrap_or("").to_string(), k["outcome"]["verdict"].as_str().unwrap_or("unsupported").to_string()));
    }
    (seconds, v)
}

#[test]
#[ignore = "a benchmark: run as a queued job (R3)"]
fn where_a_compare_runs_time_goes_stage_by_stage() {
    if builds("preparation").is_none() {
        return;
    }
    let n = repeats();
    let tmp = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("preparation-run");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();

    // Compilation, per build, as the fixture compiles them (the Spring stand-ins first, which every build is compiled
    // against).
    let spring_sources = java_files(&Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/spring/org"));
    let spring = tmp.join("javac-spring");
    let mut compiled: Vec<(String, f64)> = Vec::new();
    let mut spring_times = Vec::new();
    for _ in 0..n {
        spring_times.push(javac(&spring, None, &spring_sources));
    }
    compiled.push(("the Spring stand-ins".into(), median(spring_times)));
    // J4's two edits are compiled only here: the last compile of each is the build its scenario runs on.
    let edits = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/preparation");
    for (name, files) in [
        ("before", java_files(&root().join("before"))),
        ("after", java_files(&root().join("after"))),
        ("offset", overlaid(&root().join("defects/offset"))),
        ("unrelated-edit", overlaid(&edits.join("unrelated-edit"))),
        ("helper-rewrite", overlaid(&edits.join("helper-rewrite"))),
    ] {
        let times: Vec<f64> = (0..n).map(|_| javac(&tmp.join(format!("javac-{name}")), Some(&spring), &files)).collect();
        compiled.push((name.into(), median(times)));
    }
    let build_of = |name: &str| -> PathBuf {
        match name {
            "unrelated-edit" | "helper-rewrite" => tmp.join(format!("javac-{name}")),
            _ => build(name).to_path_buf(),
        }
    };

    // The stages a run repeats, one by one on the same builds.
    let before = build("before");
    let classes = class_files(before);
    let bytes: u64 = classes.iter().map(|c| std::fs::metadata(c).map(|m| m.len()).unwrap_or(0)).sum();
    let unit = |f: &mut dyn FnMut()| median((0..n).map(|_| timed(&mut *f).1).collect());
    let mut units: Vec<(String, f64)> = Vec::new();
    units.push((
        format!("decoding every class file of the old build ({} files, {bytes} bytes)", classes.len()),
        unit(&mut || {
            for c in &classes {
                jvmcontract::classfile::ClassFile::parse(&std::fs::read(c).unwrap()).unwrap();
            }
        }),
    ));
    let relocated = tmp.join("relocated");
    units.push((
        "relocating the old build into package before/ (each proof does once)".into(),
        unit(&mut || {
            let _ = std::fs::remove_dir_all(&relocated);
            jvmcontract::relocate::directory(before, &relocated, "before").unwrap();
        }),
    ));
    units.push(("loading both builds for alignment (compare does once)".into(), unit(&mut || {
        jvmcontract::alignment::Build::load(before).unwrap();
        jvmcontract::alignment::Build::load(build("after")).unwrap();
    })));
    let (b, a) = (jvmcontract::alignment::Build::load(before).unwrap(), jvmcontract::alignment::Build::load(build("after")).unwrap());
    units.push(("aligning the two builds (compare does once)".into(), unit(&mut || {
        jvmcontract::alignment::align(&b, &a, None);
    })));
    units.push(("reading both builds' entry points' observation specs (compare does once)".into(), unit(&mut || {
        jvmcontract::spec::observe::entry_points(before).unwrap();
        jvmcontract::spec::observe::entry_points(build("after")).unwrap();
    })));
    // Opening the JDK's image. Its table of classes is shared within the process by index (R3's cache), so a first
    // open is timed on a copy of the index, alone in a file, that differs from every earlier one in one byte of its
    // redirect table: that open builds the table, as every open did before the cache.
    let home = jvmcontract::jimage::JImage::find_java_home().expect("a JDK");
    let index = {
        use std::io::Read;
        let mut file = std::fs::File::open(home.join("lib").join("modules")).unwrap();
        let mut header = [0u8; 28];
        file.read_exact(&mut header).unwrap();
        let field = |at: usize| u32::from_le_bytes(header[at..at + 4].try_into().unwrap()) as usize;
        assert_eq!(field(0), 0xCAFE_DADA, "a little-endian image");
        let mut index = header.to_vec();
        index.resize(28 + field(16) * 8 + field(20) + field(24), 0);
        file.read_exact(&mut index[28..]).unwrap();
        index
    };
    let fresh = tmp.join("fresh-image");
    std::fs::create_dir_all(fresh.join("lib")).unwrap();
    let mut variant = 0u32;
    units.push(("opening the JDK's image the first time in a process, its table of classes built, writing the copy of its index included (each open did before R3's cache)".into(), unit(&mut || {
        variant += 1;
        let mut bytes = index.clone();
        let redirect = u32::from_le_bytes(bytes[28..32].try_into().unwrap()) ^ variant;
        bytes[28..32].copy_from_slice(&redirect.to_le_bytes());
        std::fs::write(fresh.join("lib").join("modules"), &bytes).unwrap();
        jvmcontract::jimage::JImage::open(&fresh).expect("the copy opens");
    })));
    jvmcontract::jimage::JImage::open_default().expect("a JDK");
    units.push(("opening the JDK's image again, its table shared (each class path with the JDK does: several per proof)".into(), unit(&mut || {
        jvmcontract::jimage::JImage::open_default().expect("a JDK");
    })));
    let models = tmp.join("models");
    units.push((
        format!("writing the models' {} class files into a work directory (each proof does once, after its lookup)", jvmcontract::models::MODELS.len()),
        unit(&mut || {
            let _ = std::fs::remove_dir_all(&models);
            jvmcontract::models::write_to(&models).unwrap();
        }),
    ));
    units.push(("the models' digest (each claim key takes it)".into(), unit(&mut || {
        jvmcontract::statement::models(true);
    })));
    let binary = std::fs::read(env!("CARGO_BIN_EXE_jvmcontract")).unwrap();
    units.push((
        format!("the binary's digest ({} bytes; once per process)", binary.len()),
        unit(&mut || {
            jvmcontract::digest::sha256_hex(&binary);
        }),
    ));

    // The runs, in process under the ledger, then as processes.
    // What a cold run of `after` leaves, in process and as a process (their tools' identities differ, so their keys
    // do): the cache J4's two edits start from, copied for each repeat.
    let seed = tmp.join("seed-after");
    let _ = std::fs::remove_dir_all(&seed);
    let cold_after = measured(build("after"), &seed);
    let process_seed = tmp.join("process-seed-after");
    let _ = std::fs::remove_dir_all(&process_seed);
    process(build("after"), &process_seed);
    let mut scenarios = Vec::new();
    let mut table = String::new();
    for (scenario, after, start) in [
        ("cold", "after", Start::Fresh),
        ("unchanged rerun", "after", Start::Rerun),
        ("unrelated edit", "unrelated-edit", Start::AfterCold),
        ("safe helper rewrite", "helper-rewrite", Start::AfterCold),
        ("defect, cold", "offset", Start::Fresh),
        ("defect, rerun", "offset", Start::Rerun),
    ] {
        let after_dir = build_of(after);
        let cache = tmp.join(format!("cache-{after}"));
        let mut runs: Vec<Measured> = Vec::new();
        for _ in 0..n {
            match start {
                Start::Fresh => {
                    let _ = std::fs::remove_dir_all(&cache);
                }
                Start::Rerun if !cache.is_dir() => {
                    measured(&after_dir, &cache);
                }
                Start::Rerun => {}
                Start::AfterCold => copy_dir(&seed, &cache),
            }
            runs.push(measured(&after_dir, &cache));
        }
        let verdicts_first = verdicts(&runs[0].report);
        assert!(runs.iter().all(|r| verdicts(&r.report) == verdicts_first), "{scenario}: every repeat reaches the same verdicts");
        let hits = |r: &Measured| r.proofs.iter().filter(|p| p.cache == "hit").count();
        let misses = |r: &Measured| r.proofs.iter().filter(|p| p.cache == "miss").count();
        let cache_outcomes = |r: &Measured| r.proofs.iter().map(|p| (p.target.clone(), p.cache.clone(), p.inside)).collect::<Vec<_>>();
        if start == Start::Rerun || after == "unrelated-edit" {
            assert!(runs.iter().all(|r| r.proofs.iter().all(|p| p.cache != "miss")), "{scenario}: nothing is proved again: {:?}", cache_outcomes(&runs[0]));
        }
        if start == Start::AfterCold {
            assert_eq!(verdicts_first, verdicts(&cold_after.report), "{scenario}: the edit keeps after's verdicts");
        }
        if after == "unrelated-edit" {
            for r in &runs {
                let reached = evidence(&r.report);
                assert!(reached.iter().all(|(_, how, _)| *how != "proved"), "{scenario}: every proof is an exact hit: {reached:?}");
                assert!(reached.iter().any(|(_, how, _)| *how == "exact hit"), "{scenario}: some proof is reused: {reached:?}");
            }
        }
        if after == "helper-rewrite" {
            // The helper's own proof is made again (a new claim), its caller is proved again on it, and what doesn't
            // reach the helper is an exact hit.
            let helper_key = |r: &Report| evidence(r).into_iter().find(|(s, _, _)| s == "shop.Pricing#total").map(|(_, how, callees)| (how, callees)).expect("total is checked");
            let (_, cold_callees) = helper_key(&cold_after.report);
            assert_eq!(cold_callees.len(), 1, "a cold run of after proves total on discount's own proof: {cold_callees:?}");
            for r in &runs {
                let (how, callees) = helper_key(&r.report);
                assert_eq!(how, "proved", "{scenario}: total is proved again");
                assert_eq!(callees.len(), 1, "{scenario}: total rests on discount's proof: {callees:?}");
                assert!(callees[0].contains("discount"), "{scenario}: the helper is discount: {callees:?}");
                assert_ne!(callees, cold_callees, "{scenario}: on a new proof of the rewritten helper, not the earlier one");
                let reached = evidence(&r.report);
                assert!(reached.iter().any(|(s, how, _)| s == "shop.Pricing#withQuantity" && *how == "exact hit"), "{scenario}: withQuantity doesn't reach the helper and is an exact hit: {reached:?}");
                assert!(r.proofs.iter().any(|p| p.inside.is_some() && p.cache == "miss"), "{scenario}: the helper's own proof is made again: {:?}", cache_outcomes(r));
            }
        }
        let mut by_stage: Vec<(&'static str, Vec<f64>)> = Vec::new();
        for r in &runs {
            for (i, (name, s)) in stages(&r.proofs, r.seconds).into_iter().enumerate() {
                if by_stage.len() <= i {
                    by_stage.push((name, Vec::new()));
                }
                by_stage[i].1.push(s);
            }
        }
        let seconds = median(runs.iter().map(|r| r.seconds).collect());
        let typical = runs.iter().min_by(|x, y| (x.seconds - seconds).abs().total_cmp(&(y.seconds - seconds).abs())).unwrap();
        let process_cache = tmp.join(format!("process-cache-{after}"));
        let process_times: Vec<f64> = (0..n)
            .map(|_| {
                match start {
                    Start::Fresh => {
                        let _ = std::fs::remove_dir_all(&process_cache);
                    }
                    Start::Rerun if !process_cache.is_dir() => {
                        process(&after_dir, &process_cache);
                    }
                    Start::Rerun => {}
                    Start::AfterCold => copy_dir(&process_seed, &process_cache),
                }
                let (s, v) = process(&after_dir, &process_cache);
                assert_eq!(v.iter().map(|(k, x)| (k.clone(), x.to_lowercase())).collect::<Vec<_>>(), verdicts_first.iter().map(|(k, x)| (k.clone(), x.to_lowercase())).collect::<Vec<_>>(), "{scenario}: the process reaches the in-process verdicts");
                s
            })
            .collect();
        let stage_rows: Vec<(String, f64)> = by_stage.into_iter().map(|(name, v)| (name.to_string(), median(v))).collect();
        let from = match start {
            Start::Fresh => "an empty proof cache",
            Start::Rerun => "the cache the same build's run left",
            Start::AfterCold => "a copy of the cache a cold run of `after` left",
        };
        table.push_str(&format!("\n### {scenario} (`{after}`, from {from})\n\n{} proofs, {} exact hits, {} proved; in process {:.1} ms, as a process {:.1} ms (medians of {n})\n\n", typical.proofs.len(), hits(typical), misses(typical), ms(seconds), ms(median(process_times.clone()))));
        table.push_str("| Subject | Reached | On the helper proofs |\n|---|---|---|\n");
        for (subject, how, callees) in evidence(&typical.report) {
            table.push_str(&format!("| {subject} | {how} | {} |\n", if callees.is_empty() { "".to_string() } else { callees.join(", ") }));
        }
        table.push_str("\n| Stage | ms |\n|---|---|\n");
        for (name, s) in &stage_rows {
            table.push_str(&format!("| {name} | {:.1} |\n", ms(*s)));
        }
        scenarios.push(json!({
            "scenario": scenario, "after": after, "from": from, "verdicts": verdicts_first, "proofs": typical.proofs.len(), "hits": hits(typical), "proved": misses(typical),
            "evidence": evidence_rows(&typical.report),
            "in_process_ms": ms(seconds), "in_process_ms_each": runs.iter().map(|r| ms(r.seconds)).collect::<Vec<_>>(),
            "process_ms": ms(median(process_times.clone())), "process_ms_each": process_times.iter().map(|s| ms(*s)).collect::<Vec<_>>(),
            "stages_ms": stage_rows.iter().map(|(k, s)| json!({"stage": k, "ms": ms(*s)})).collect::<Vec<_>>(),
            "typical_run_proofs": proof_rows(&typical.proofs),
        }));
    }

    let report = json!({
        "what": "R3 and J4 of llm-dlc/loops/application-core-reuse.md: a small compare run's time by stage, on the joint example's builds (lib/tests/fixtures/foundations, examples 190 and 191) and two edits of after (lib/tests/fixtures/preparation), for these fixtures only",
        "repeats": n,
        "jvmcontract": env!("CARGO_PKG_VERSION"),
        "profile": if cfg!(debug_assertions) { "debug" } else { "release" },
        "compilation_ms": compiled.iter().map(|(k, s)| json!({"build": k, "ms": ms(*s)})).collect::<Vec<_>>(),
        "units_ms": units.iter().map(|(k, s)| json!({"stage": k, "ms": ms(*s)})).collect::<Vec<_>>(),
        "scenarios": scenarios,
    });
    let mut md = format!("# R3 and J4: a small compare run's time by stage\n\nThe joint example's builds (examples 190, 191) and two edits of `after` (`lib/tests/fixtures/preparation`), medians of {n} repeats, {} build; for these fixtures only.\n\n## Compilation (javac)\n\n| Build | ms |\n|---|---|\n", if cfg!(debug_assertions) { "a debug" } else { "a release" });
    for (k, s) in &compiled {
        md.push_str(&format!("| {k} | {:.1} |\n", ms(*s)));
    }
    md.push_str("\n## Repeated stages, one by one\n\n| Stage | ms |\n|---|---|\n");
    for (k, s) in &units {
        md.push_str(&format!("| {k} | {:.2} |\n", ms(*s)));
    }
    md.push_str("\n## The runs\n");
    md.push_str(&table);
    let out = std::env::var_os("PREPARATION_REPORT").map(PathBuf::from).unwrap_or_else(|| tmp.join("preparation.json"));
    if let Some(dir) = out.parent() {
        std::fs::create_dir_all(dir).unwrap();
    }
    std::fs::write(&out, serde_json::to_string_pretty(&report).unwrap()).unwrap();
    std::fs::write(out.with_extension("md"), &md).unwrap();
    println!("{md}\nwritten to {} and {}", out.display(), out.with_extension("md").display());
}
