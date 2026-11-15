//! The lint of the Rust tests' cost tiers in `cargo test` (step 7 of llm-dlc/loops/test-cost.md), against the
//! inventory `lib/tests/costs.json`:
//!
//! - every `#[ignore]` reason is a proof tag, `cost:proof: WHAT IT RUNS, ~TIME; proxy: TEST`;
//! - its proxy names tests that run by default, or says `proxy: none yet` for a test on the inventory's list;
//! - no test the inventory says calls JBMC or TLC runs by default, except its `retier: pending` tests;
//! - every test is in the inventory, and every test the inventory names exists.
//!
//! It reads what can be read here without following a test into its helpers. `python3 lib/tools/test_costs.py lint`
//! checks all of it, for Rust and Python, and also that what the inventory records of each test (what it calls, its
//! tag) is current and that each test's `tool_tier!` call is the one its tier asks for; `lib/tools/test_tier_lint.py`
//! runs it in the Python default run. `lib/README.md`'s Tests section says what to do about each problem.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const PROOF_PREFIX: &str = "cost:proof: ";
const NONE_YET: &str = "none yet";

/// A `#[test]` function in the sources: file (from the repository root), name, and its ignore reason.
struct Test {
    file: String,
    name: String,
    ignore: Option<String>,
}

fn lib() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

/// Every `.rs` file that holds tests: the library's sources and each test target (not its modules' files).
fn sources() -> Vec<PathBuf> {
    fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
        let mut entries: Vec<_> = std::fs::read_dir(dir).unwrap().map(|e| e.unwrap().path()).collect();
        entries.sort();
        for p in entries {
            if p.is_dir() {
                walk(&p, out);
            } else if p.extension().is_some_and(|e| e == "rs") {
                out.push(p);
            }
        }
    }
    let mut out = Vec::new();
    walk(&lib().join("src"), &mut out);
    let mut tests: Vec<_> = std::fs::read_dir(lib().join("tests"))
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "rs"))
        .collect();
    tests.sort();
    out.extend(tests);
    out
}

/// A string attribute's value as Rust reads it: a `\` at a line's end joins the next line without its indentation.
fn reason(attribute: &str) -> String {
    let (Some(a), Some(b)) = (attribute.find('"'), attribute.rfind('"')) else { return String::new() };
    if b <= a {
        return String::new();
    }
    let raw = &attribute[a + 1..b];
    let mut out = String::new();
    let mut lines = raw.split('\n').peekable();
    let mut join = false;
    while let Some(line) = lines.next() {
        let line = if join { line.trim_start() } else { line };
        join = line.ends_with('\\') && lines.peek().is_some();
        out.push_str(if join { &line[..line.len() - 1] } else { line });
        if !join && lines.peek().is_some() {
            out.push('\n');
        }
    }
    out
}

/// The tests of one file: each `fn` whose attributes, on the lines before it, include `#[test]`. The `#[ignore]`
/// of any `fn` (a test or not) is returned with it, so that a reason on a non-test is checked too.
fn tests_of(file: &str, text: &str) -> (Vec<Test>, Vec<(String, String)>) {
    let fn_name = regex::Regex::new(r"^(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)").unwrap();
    let (mut tests, mut ignores) = (Vec::new(), Vec::new());
    let (mut attrs, mut open): (Vec<String>, Option<String>) = (Vec::new(), None);
    for line in text.lines() {
        let t = line.trim();
        if let Some(mut a) = open.take() {
            a.push('\n');
            a.push_str(line);
            if t.ends_with(']') {
                attrs.push(a);
            } else {
                open = Some(a);
            }
            continue;
        }
        if t.starts_with("#[") {
            if t.ends_with(']') {
                attrs.push(t.to_string());
            } else {
                open = Some(t.to_string());
            }
            continue;
        }
        if t.is_empty() || t.starts_with("//") {
            continue;
        }
        if let Some(m) = fn_name.captures(t) {
            let ignore = attrs.iter().find(|a| a.starts_with("#[ignore")).map(|a| reason(a));
            if let Some(r) = &ignore {
                ignores.push((format!("{file}::{}", &m[1]), r.clone()));
            }
            if attrs.iter().any(|a| a == "#[test]") {
                tests.push(Test { file: file.to_string(), name: m[1].to_string(), ignore });
            }
        }
        attrs.clear();
    }
    (tests, ignores)
}

fn inventory() -> serde_json::Value {
    let text = std::fs::read_to_string(lib().join("tests/costs.json")).unwrap();
    serde_json::from_str(&text).unwrap()
}

fn last(name: &str) -> &str {
    name.rsplit("::").next().unwrap()
}

#[test]
fn every_rust_test_is_tagged_with_its_cost_tier_as_the_inventory_says() {
    let root = lib().parent().unwrap().to_path_buf();
    let (mut tests, mut ignores) = (Vec::new(), Vec::new());
    for path in sources() {
        let file = path.strip_prefix(&root).unwrap().to_string_lossy().into_owned();
        let (t, i) = tests_of(&file, &std::fs::read_to_string(&path).unwrap());
        tests.extend(t);
        ignores.extend(i);
    }
    let doc = inventory();
    let rows = doc["rust"].as_array().unwrap();
    let mut problems = Vec::new();
    let fix = "run `python3 lib/tools/test_costs.py estimate`, then `lint`";

    // Every test is in the inventory, and every test it names exists (by file and name, the module path aside).
    let mut counts: BTreeMap<(String, String), i32> = BTreeMap::new();
    for t in &tests {
        *counts.entry((t.file.clone(), t.name.clone())).or_default() += 1;
    }
    for r in rows {
        let key = (r["file"].as_str().unwrap().to_string(), last(r["name"].as_str().unwrap()).to_string());
        *counts.entry(key).or_default() -= 1;
    }
    for ((file, name), n) in &counts {
        match n.signum() {
            1 => problems.push(format!("{file}::{name}: not in the inventory: {fix}")),
            -1 => problems.push(format!("{file}::{name}: in the inventory, but no such test: {fix}")),
            _ => {}
        }
    }

    // Every ignore reason is a proof tag whose proxy runs by default, or is on the inventory's `none yet` list.
    let runs: BTreeMap<&str, ()> = tests.iter().filter(|t| t.ignore.is_none()).map(|t| (t.name.as_str(), ())).collect();
    for (at, reason) in &ignores {
        if !reason.starts_with(PROOF_PREFIX) {
            problems.push(format!("{at}: its ignore reason doesn't start with {PROOF_PREFIX:?}: {reason:?}"));
        }
        let Some((_, proxies)) = reason.rsplit_once("; proxy:") else {
            problems.push(format!("{at}: its proof tag names no proxy (`; proxy: TEST`, or `; proxy: {NONE_YET}`)"));
            continue;
        };
        let proxies = proxies.trim();
        if proxies == NONE_YET {
            let (file, name) = at.rsplit_once("::").unwrap();
            let listed = rows.iter().any(|r| {
                r["file"] == file
                    && last(r["name"].as_str().unwrap()) == name
                    && r["ignored"].as_str().is_some_and(|i| i.contains("proxy: none yet"))
                    && r.get("unlisted").is_none()
            });
            if !listed {
                problems.push(format!("{at}: `proxy: none yet`, but the inventory doesn't list it: {fix}"));
            }
            continue;
        }
        for proxy in proxies.split(',').map(str::trim) {
            if !runs.contains_key(last(proxy)) {
                problems.push(format!("{at}: its proxy {proxy} is no test that runs by default"));
            }
        }
    }

    // No test the inventory says calls JBMC or TLC runs by default, unless it is on the `retier: pending` list; and
    // no test joined a list without a person.
    for r in rows {
        let at = format!("{}::{}", r["file"].as_str().unwrap(), r["name"].as_str().unwrap());
        let calls: Vec<&str> = r["calls"].as_array().unwrap().iter().filter_map(|c| c.as_str()).collect();
        // (TLC's name in capitals: the inventory reads a lowercase one in quotes as a test that runs TLC.)
        let proof = calls.iter().any(|c| *c == "jbmc" || c.eq_ignore_ascii_case("TLC"));
        if proof && r.get("ignored").is_none() && r.get("retier").and_then(|v| v.as_str()) != Some("pending") {
            problems.push(format!(
                "{at}: calls JBMC or TLC but isn't proof tier: tag it #[ignore = \"cost:proof: …; proxy: TEST\"] and \
                 queue it, or a person lists it as retier: pending"
            ));
        }
        if let Some(why) = r.get("unlisted").and_then(|v| v.as_str()) {
            problems.push(format!("{at}: {why}"));
        }
    }

    assert!(problems.is_empty(), "{} problems with the tests' cost tiers:\n{}", problems.len(), problems.join("\n"));
}

#[test]
fn a_reason_is_read_as_rust_reads_a_string_continued_over_lines() {
    let attr = "#[ignore = \"cost:proof: JBMC, ~4 min; \\\n    proxy: a, \\\n    b\"]";
    assert_eq!(reason(attr), "cost:proof: JBMC, ~4 min; proxy: a, b");
    let src = "#[test]\n#[ignore = \"cost:proof: x; \\\n    proxy: none yet\"]\nfn slow() {}\n\n#[test]\nfn quick() {}\n\
               #[ignore = \"why\"]\nfn helper() {}\n";
    let (tests, ignores) = tests_of("f.rs", src);
    let names: Vec<_> = tests.iter().map(|t| (t.name.as_str(), t.ignore.as_deref())).collect();
    assert_eq!(names, [("slow", Some("cost:proof: x; proxy: none yet")), ("quick", None)]);
    assert_eq!(ignores.iter().map(|(a, r)| (a.as_str(), r.as_str())).collect::<Vec<_>>(),
               [("f.rs::slow", "cost:proof: x; proxy: none yet"), ("f.rs::helper", "why")]);
}
