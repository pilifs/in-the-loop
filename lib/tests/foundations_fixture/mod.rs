//! The foundations loop's joint example (`tests/fixtures/foundations/`), compiled: `before`, `after`, and each
//! defect overlaid on `after`. Shared by `tests/foundations.rs` (the integration contract) and `tests/compare.rs`
//! (the joint run), each compiling into a directory of its own so that the two can run at once.

#![allow(dead_code)]

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

pub const DEFECTS: &[&str] = &["offset", "alias-to-copy", "dropped-effect", "duplicated-effect", "outside-domain", "route-change"];

pub fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations")
}

fn has(program: &str) -> bool {
    let found = Command::new(program).arg("-version").output().is_ok();
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "{program} not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
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

static BUILDS: OnceLock<Option<Vec<(String, PathBuf)>>> = OnceLock::new();

/// The builds by name: `before`, `after`, and each defect overlaid on `after` (its files replace theirs). Compiled once
/// per test binary into `CARGO_TARGET_TMPDIR/<into>`, against the Spring stand-ins of `tests/fixtures/spring/org`.
/// None without javac.
pub fn builds(into: &str) -> Option<&'static Vec<(String, PathBuf)>> {
    BUILDS
        .get_or_init(|| {
            if !has("javac") {
                return None;
            }
            let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join(into);
            let _ = std::fs::remove_dir_all(&out);
            let spring = out.join("spring");
            let stand_ins = java_files(&Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/spring/org"));
            javac(&spring, &[], &stand_ins);
            let after = java_files(&root().join("after"));
            let mut builds = vec![("before".to_string(), java_files(&root().join("before"))), ("after".to_string(), after.clone())];
            for defect in DEFECTS {
                let dir = root().join("defects").join(defect);
                let overlay = java_files(&dir);
                let names: Vec<_> = overlay.iter().map(|p| p.strip_prefix(&dir).unwrap().to_path_buf()).collect();
                let mut files: Vec<PathBuf> = after.iter().filter(|p| !names.contains(&p.strip_prefix(root().join("after")).unwrap().to_path_buf())).cloned().collect();
                files.extend(overlay);
                builds.push((defect.to_string(), files));
            }
            Some(
                builds
                    .into_iter()
                    .map(|(name, files)| {
                        let dir = out.join(&name);
                        javac(&dir, &[&spring], &files);
                        (name, dir)
                    })
                    .collect(),
            )
        })
        .as_ref()
}

fn javac(out: &Path, classpath: &[&Path], files: &[PathBuf]) {
    std::fs::create_dir_all(out).unwrap();
    let mut cmd = Command::new("javac");
    cmd.args(["-g", "-parameters", "-proc:none", "-d"]).arg(out);
    if !classpath.is_empty() {
        cmd.arg("-cp").arg(std::env::join_paths(classpath).unwrap());
    }
    let status = cmd.args(files).status().expect("javac runs");
    assert!(status.success(), "the foundations fixture compiles into {}", out.display());
}

/// The build `name` of [`builds`], which must have been compiled.
pub fn build(name: &str) -> &'static Path {
    let builds = BUILDS.get().and_then(Option::as_ref).expect("the fixture is compiled first, by builds()");
    &builds.iter().find(|(n, _)| n == name).unwrap_or_else(|| panic!("no build {name}")).1
}
