//! The integration contract of `llm-dlc/loops/application-core.md` (Phase 0 step 4), run by
//! `llm-dlc/tools/application-core-integration.sh` on the merge of the four streams while they work. One test per
//! row of the acceptance contract (`llm-dlc/loops/application-core-acceptance.md`) that a unit-level run can reach,
//! on the frozen fixtures of `tests/fixtures/application-core/` and the verdicts their `golden/expected.json` fixes.
//!
//! Each case must reach its expected verdict, or give the named refusal of a stream that owns the row and hasn't
//! built its part yet: `Unsupported` naming that part, or a check refused with that stream's words. Anything else
//! fails: another verdict, a refusal naming no stream of the row, or one naming another's. Every check runs on the
//! native engine with no JBMC (J2's guard): `jbmc` is a path that doesn't exist.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::spec::{CanonicalClaim, Construction};
use serde_json::Value;

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core")
}

fn expected() -> &'static Value {
    static EXPECTED: OnceLock<Value> = OnceLock::new();
    EXPECTED.get_or_init(|| serde_json::from_str(&std::fs::read_to_string(fixtures().join("golden/expected.json")).unwrap()).unwrap())
}

fn golden(name: &str) -> CanonicalClaim {
    let path = fixtures().join(format!("golden/{name}.json"));
    serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

/// Every build of every family, compiled once: `before`, `after`, and each defect overlaid on `after`. The
/// contract needs `javac`: without it, it fails rather than pass by skipping.
fn builds() -> &'static Path {
    static DIR: OnceLock<PathBuf> = OnceLock::new();
    DIR.get_or_init(|| {
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core");
        let _ = std::fs::remove_dir_all(&root);
        for family in ["quote", "throttle", "basket"] {
            let dir = fixtures().join(family);
            let mut names = vec!["before".to_string(), "after".to_string()];
            names.extend(std::fs::read_dir(dir.join("defects")).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()));
            for name in names {
                let base = dir.join(if name == "before" { "before" } else { "after" });
                let mut files = std::collections::BTreeMap::new();
                for f in java_files(&base) {
                    files.insert(f.strip_prefix(&base).unwrap().to_path_buf(), f.clone());
                }
                let overlay = dir.join("defects").join(&name);
                for f in java_files(&overlay) {
                    files.insert(f.strip_prefix(&overlay).unwrap().to_path_buf(), f.clone());
                }
                let out = root.join(family).join(&name);
                let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files.values()).status().expect("the contract needs javac");
                assert!(status.success(), "{family}/{name} compiles");
            }
        }
        root
    })
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

/// The frozen claims are the shared types: each parses as a canonical claim and writes back the same JSON, and each
/// plan has the shape of a bounded DAG of its own nodes.
#[test]
fn the_frozen_claims_are_the_shared_types() {
    for entry in std::fs::read_dir(fixtures().join("golden")).unwrap() {
        let path = entry.unwrap().path();
        let name = path.file_stem().unwrap().to_string_lossy().into_owned();
        if !name.ends_with("-claim") {
            continue;
        }
        let original: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        let claim = golden(&name);
        assert_eq!(serde_json::to_value(&claim).unwrap(), original, "{name} round-trips");
        let Some(Construction::Planned { before, after }) = claim.domain.as_ref().map(|d| &d.made_by) else { panic!("{name} has a planned domain") };
        for plan in [before, after] {
            assert_eq!(plan.shape_problem(), None, "{name}");
        }
    }
}

/// Every build of every family compiles, and the expectations name each one under every claim and regression.
#[test]
fn every_build_compiles_and_every_case_has_its_verdict() {
    for family in ["quote", "throttle", "basket"] {
        let mut names: Vec<String> = std::fs::read_dir(builds().join(family)).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()).filter(|n| n != "before").collect();
        names.sort();
        for (case, cases) in expected()[family].as_object().unwrap() {
            let mut named: Vec<String> = cases.as_object().unwrap().keys().cloned().collect();
            named.sort();
            assert_eq!(named, names, "{family} {case}");
        }
    }
}
