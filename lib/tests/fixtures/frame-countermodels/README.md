# Countermodels of a write set

The challenge stream of `domain-advances` (2026-11-17), item 5. It is against the state stream's write set, its
first effect contract (`qrqtplwq`, `prove --writes`, `property::Options::writes`).

`--writes this.displayName` states which fields of the receiver and the object parameters a method may write. The
check then proves a frame with the property: every other field of those inputs is what it was (`this.admin ==
\old(this.admin)`). The own checker refuses, inside the call, a write to anything else that was there before it
(`Engine::keeps`, `Options::frame`).

The frame is part of the assertion, so it is read where the assertion is:
- only after a normal return;
- only on the harness's inputs, where each object parameter is a distinct object made by its constructor.

A JVM sees the field written in each of these cases (`lib/tests/frame_countermodels.rs`,
`each_protected_field_a_frame_misses_is_written_on_a_jvm`):

| Method of `fc/Framed.java` | The write set | What the frame does not read | A JVM | The checker |
|---|---|---|---|---|
| `Bean#rename(String, int)`: sets `admin`, throws `IllegalArgumentException` when `length < 0`, else writes `displayName` and puts `admin` back | `this.displayName`, with `--throws 'java.lang.IllegalArgumentException when length < 0'` | the state an exceptional exit leaves | `rename("b", -1)` throws and leaves `admin` true | **Verified** |
| `Bean#promote(Bean other)`: `other.admin = true` | `other.admin` | the receiver passed as `other` | `b.promote(b)` sets `b.admin` | **Verified** `this.admin == \old(this.admin)` |
| static `grant(Bean from, Bean to)`: `to.admin = true` | `to.admin` | one bean passed twice | `grant(b, b)` sets `from.admin` | **Verified** `from.admin == \old(from.admin)` |

Reproduced on 2026-11-17 on the state stream's checker, built apart, at two commits:
- `qrqtplwq`, which adds the write set;
- `vwktulky`, its next commit, where a setter's checked write set also stands in for its calls.

What each result says:
- `rename`'s result reads "rename writes this.displayName" and "throws java.lang.IllegalArgumentException when
  length < 0". It does not say that the frame holds only where the method returns. Without the throws clause, the
  same exit is a violation of the frame, with its witness run on a JVM. So the check does see the state the
  exception leaves, and a declared exception is what turns it off.
- The two alias cases state their domain as "a Bean made by its constructor × another, ... no two the same String
  object". Nothing says the two beans are distinct objects, and the frame is a statement about values ("after the
  call, `this.admin == \old(this.admin)`"). One bean passed twice is made by its constructor, and a JVM breaks that
  statement on it.
- That aliasing is outside every check's input space is older than this run. The write set is what makes it
  false, since its frame is a statement about two inputs that may be one object.

This is what 286's protected state needs a write set for. A binder that writes a protected field and then fails with
a declared exception, or a target object that is also a source, gets past the frame.

The commands, with `Framed.java` compiled into `classes`:

```
jvmcontract prove --classes classes --classpath classes 'fc.Framed$Bean#rename' --writes this.displayName \
  --throws 'java.lang.IllegalArgumentException when length < 0' --engine native
jvmcontract prove --classes classes --classpath classes 'fc.Framed$Bean#promote' --writes other.admin --engine native
jvmcontract prove --classes classes --classpath classes 'fc.Framed#grant' --writes to.admin --engine native
```

**What the checker should say instead** is the state stream's to decide, since the write set is its rule this run.
Options:
- *Exceptional exits.* Check the frame on a declared exceptional exit as well: the harness catches the declared
  exception and asserts the frame there. Or refuse a write set beside a throws clause by name, or state in the result
  that the frame is of a normal return only.
- *Aliasing.* The frame is of locations, as JML's `assignable` is: `this.admin` may change where `this == other`.
  So either let the harness pass one object for two inputs of compatible classes, or refuse a write set over two such
  inputs. Or state "distinct objects" in the domain: then the frame stays true as stated, but a caller that passes
  one object twice cannot use it.

The test it should pass, to be added to `lib/tests/frame_countermodels.rs` with the fix. It fails on all three on the
state stream's line today:

```rust
use jvmcontract::{property, Engine, Verdict};

/// The checker's side: no frame proved of a protected field a JVM sees written (the test above).
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
        if out.verdict == Verdict::Verified {
            wrong.push(target);
        }
    }
    assert!(wrong.is_empty(), "a frame proved where a JVM sees the field written: {wrong:?}");
}
```

## Tried and found guarded

Each was run on the state stream's checker, with `--writes this.displayName` unless named:
- **A write through a callee** (a static helper given `this`), **through a lambda** that captures `this`, and **at
  the bottom of a recursion**. Each is refuted with the frame: the harness reads the field after the call, whoever
  wrote it.
- **The default locale** (`Locale.setDefault` inside the call). It is refused by name ("sets the default locale,
  outside its write set", `bmc/locale.rs` through `Engine::keeps`).
- **A StringBuilder parameter.** The harness takes no such parameter, so there is no input whose content the frame
  does not read.
- **The frame of a String field compared by identity**, with `--writes ''`, against what JDK 25 does. Sixteen
  operations put the result back into the field: `concat("")`, `substring(0)`, `toLowerCase()` with and without a
  locale, `toUpperCase()`, `trim()`, `strip()`, `intern()`, `String.valueOf`, `toString()`, `replace` of a char by
  itself, `+ ""`, `repeat(1)`, `new String(s)`, a StringBuilder's `toString()`, and `replace("q", "r")`.
  - Proved: `substring(0)` and `toString()`, which return the same object on a JVM.
  - Refuted: `toLowerCase` (witness `"P"`, which a JVM makes a new object of), `+ ""` and the StringBuilder, which a
    JVM always makes a new object of.
  - Every other is a gap refused under strict.
  - No identity the checker gives differs from the JVM's.
- **An inherited field.** `harness::Fields` comes from `equivalence::fields_of`, which refuses a class that extends
  another. So no field of an input is left out of the frame.
- **A contract used in a state its reads differ in.** Not tried here: at `qrqtplwq` no call stands on a write set.
  `vwktulky` makes a setter's checked write set stand in for its calls. That use, and whether the two holes above
  carry into a caller's proof, is the challenge stream's next piece.

## Audit

Which accepted results use the mechanism, and whether they are affected:
- No example task passes `--writes`, on this line or on the state, evidence or preservation lines (their
  `target.json`s, drivers and claims, read on 2026-11-17).
- The state stream's brief says the beans for 286's protected state are the `claims.Frames` fixture's for now.
- No accepted result rests on the holes, so there is nothing for the watcher.
- Both holes bear on the claim the write set is for: 286's protected state.
