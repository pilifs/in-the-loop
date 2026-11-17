//! Countermodels of a write set (`prove --writes`, the state stream's first effect contract, `qrqtplwq`,
//! 2026-11-17). The frame is read after a normal return, of a call whose object inputs are distinct objects each made
//! by its constructor. A method that writes a protected field and then throws a declared exception, or one handed the
//! same object twice, leaves the field written on a JVM while the check proves it unchanged. The fixtures are
//! `tests/fixtures/frame-countermodels/fc`, and this test holds them to what a JVM says. The checker's side, the
//! proofs it should not make, is in the fixtures' README for the stream that owns the write set
//! (domain-advances-state), and the last test here holds the checker to it.

use jvmcontract::{property, Engine, Verdict};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The fixtures, compiled: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/frame-countermodels/fc");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("frame-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).arg(sources.join("Framed.java")).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// Each method leaves on a JVM the protected field written that its write set does not name.
#[test]
fn each_protected_field_a_frame_misses_is_written_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").arg("-cp").arg(classes).arg("fc.Framed").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "rename.threw=true rename.admin=true promote.this.admin=true grant.from.admin=true");
}

/// The checker's side: no frame proved of a protected field a JVM sees written (the test above). The frame holds on
/// a declared exceptional exit too, so `rename("b", -1)`, which leaves `admin` written, refutes it with a witness.
/// It is of locations, as JML's `assignable` is, over inputs that may be one object: `b.promote(b)` writes
/// `other.admin`, which is `this.admin`, so what is proved of `this.admin` is `this == other || this.admin ==
/// \old(this.admin)`, which a JVM keeps, and never `this.admin == \old(this.admin)` alone, which it breaks.
#[test]
fn a_write_set_is_not_proved_where_a_jvm_sees_a_field_it_does_not_name_written() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for (target, writes, throws) in [
        ("fc.Framed$Bean#rename", "this.displayName", Some("java.lang.IllegalArgumentException when length < 0")),
        ("fc.Framed$Bean#promote", "other.admin", None),
        ("fc.Framed#grant", "to.admin", None),
    ] {
        let mut o = property::Options::new(&[classes.to_path_buf()], target);
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.writes = Some(vec![writes.to_string()]);
        o.throws = throws.map(|t| vec![t.to_string()]).unwrap_or_default();
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("frame-countermodels").join(target.replace(['#', '$'], "-")));
        let out = property::run(&o).unwrap();
        eprintln!("--- {target}: {:?}\n{}", out.verdict, out.output);
        let unaliased = ["this.admin == \\old(this.admin)", "from.admin == \\old(from.admin)"].iter().any(|f| out.output.contains(&format!("&& {f} &&")) || out.output.contains(&format!("satisfies `{f}")));
        if out.verdict == Verdict::Verified && (throws.is_some() || unaliased) {
            wrong.push(target);
        }
        if throws.is_some() {
            // Refuted, not refused: the witness is the call a JVM sees write the field.
            assert_eq!(out.verdict, Verdict::Violation, "{target}: {}", out.output);
            assert_eq!(out.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{target}: {}", out.output);
        }
    }
    assert!(wrong.is_empty(), "a frame proved where a JVM sees the field written: {wrong:?}");
}

/// What the frame allows: named, a field is the method's to write on either exit, and the inputs a frame of locations
/// lets be one object make no write outside it. Each of these is proved, so the refutations above are of the frame
/// and not of the exit or the alias as such.
#[test]
fn a_write_set_that_names_what_a_jvm_sees_written_is_proved() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for (target, writes, throws, frame) in [
        ("fc.Framed$Bean#rename", &["this.displayName", "this.admin"][..], Some("java.lang.IllegalArgumentException when length < 0"), None),
        ("fc.Framed$Bean#promote", &["other.admin"][..], None, Some("(this == other || this.admin == \\old(this.admin))")),
        ("fc.Framed#grant", &["to.admin"][..], None, Some("(from == to || from.admin == \\old(from.admin))")),
    ] {
        let mut o = property::Options::new(&[classes.to_path_buf()], target);
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.writes = Some(writes.iter().map(|w| w.to_string()).collect());
        o.throws = throws.map(|t| vec![t.to_string()]).unwrap_or_default();
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("frame-countermodels-named").join(target.replace(['#', '$'], "-")));
        let out = property::run(&o).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{target}: {}", out.output);
        if let Some(frame) = frame {
            // The proved frame says where it reads the field, and the domain that the two may be one object.
            assert!(out.output.contains(frame) && out.output.contains("may be the same object"), "{target}: {}", out.output);
        }
    }
}
