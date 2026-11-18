# Countermodels of an exception's message kept from its constructor

The challenge stream of `domain-advances` (2026-11-18), item 5 and inbox item `domain-advances-challenge-I005`. It
targets the state stream's `vwrmzmst` (`lib/src/bmc/throwables.rs`), at its final commit `kmytvuop`.

The rule: where the engine runs the JDK's constructor `Throwable()`, `Throwable(String)` or
`Throwable(String, Throwable)` (directly, or through a JDK subclass's constructor that only passes its arguments up),
it keeps the message and the cause. Then `getMessage()`, `getLocalizedMessage()`, `getCause()` and `toString()` of
that exception are modelled as `Throwable`'s. Before the rule each was a JDK call, a gap under strict.

What it leaves out: **the constructor the engine saw is not always the one the JDK runs.** The engine runs its
models of JDK classes (`lib/models`) as bytecode. Where a model throws an exception the JDK's code throws too, with
the same class but another message, the engine keeps the model's message. Two of the models do so:

| Model | Line | The model throws | The JDK throws (JDK 25.0.5) |
|---|---|---|---|
| `java/util/ImmutableCollections.java`, `List12.get` | 303 | `new IndexOutOfBoundsException()` | `outOfBounds(index)`: "Index: 2 Size: 1" |
| `java/util/HashMap.java`, `HashMap(int)` | 37 | `new IllegalArgumentException()` | "Illegal initial capacity: -1" |

The other models' throws were read against the JDK's source and agree: `ArrayList`'s index message and capacity
message, its iterator's, `LinkedHashMap`'s iterator's, `ImmutableCollections`' `uoe()` and its iterator's, the
streams' "stream has already been operated upon or closed", `EventObject`'s "null source", and `ArrayDeque`'s
`NoSuchElementException()`. A `NullPointerException`'s message methods are its own, not `Throwable`'s, so they stay
gaps. So do those of `UnsupportedCharsetException` and `IllegalCharsetNameException`, whose constructors do more than
pass the message up.

`tm/Thrown.java` has four methods, each taking `int k`:

| Method | Property | A JVM gives | Verdict at `kmytvuop` |
|---|---|---|---|
| `listed`: `List.of("a").get(k)`, then `e.getMessage() == null ? 1 : 2` | `result != 2` where `k >= 1 && k < 3` | 2 | **Verified** |
| `listedText`: the same exception's `toString().length()` | `result == 35` where `k == 2` | 53 | **Verified** |
| `sized`: `new HashMap<String, String>(k)`, then `e.getMessage() == null ? 1 : 2` | `result != 2` where `k < 0` | 2 | **Verified** |
| `sizedLocalized`: the same exception's `getLocalizedMessage()`'s length, -1 for none | `result == -1` where `k == -1` | 28 | **Verified** |

Each proof is non-vacuous, and states nothing beyond the engine's usual "every JDK class is initialized already".
`getLocalizedMessage()` is what Spring's binder records as a binding error's default message, the reason for the
rule.

Only the rule is wrong. On a checker without it (this stream's line), each of the four stops at the gap
`jdk-reference-method` of `getMessage()`, `toString()` or `getLocalizedMessage()`.

## The commands

With `tm/Thrown.java` compiled into `classes` (`javac -g -parameters --release 21`):

```
jvmcontract prove --classes classes 'tm.Thrown#sized' --engine native --jbmc /nonexistent/jbmc \
  --assume 'k < 0' --assert 'result != 2'
```

The same for each row, with its own assumption and assertion.

## What the checker should say instead

This is the state stream's to decide, since the rule is its own this run. Options:

- **The models' messages.** Give `List12.get` and `HashMap(int)` the JDK's messages, and hold every model's throw
  to the JDK's by a test that runs both on a JVM and compares class and message.
- **Or the rule's reach.** Keep the message only of an exception that application code constructed, and leave an
  exception a model made (one whose `new` is in a model class, `ClassPath::checker_class`) a gap, as one the JDK
  made is.

The test the checker would pass after the fix, to be added to `lib/tests/throwable_countermodels.rs` with it. It
fails on all four at `kmytvuop`:

```rust
use jvmcontract::{property, Engine, Verdict};

/// The checker's side: a JVM gives the JDK's message in each, so a proof that there is none is false.
#[test]
fn a_message_a_model_left_out_is_not_proved_absent() {
    jvmcontract::tool_tier!();
    if !has("javac") || !has("java") {
        return;
    }
    let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/throwable-countermodels/tm");
    let classes = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("throwable-countermodels-checked");
    let _ = std::fs::remove_dir_all(&classes);
    let files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).collect();
    assert!(Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&classes).args(&files).status().expect("javac runs").success());
    let mut wrong = Vec::new();
    for (name, assume, assert) in [("listed", "k >= 1 && k < 3", "result != 2"), ("listedText", "k == 2", "result == 35"), ("sized", "k < 0", "result != 2"), ("sizedLocalized", "k == -1", "result == -1")] {
        let mut o = property::Options::new(&[classes.clone()], &format!("tm.Thrown#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some(assume.into());
        o.assert = Some(assert.into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("throwable-countermodels").join(name));
        let out = property::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to have no message, though a JVM gives the JDK's: {wrong:?}");
}
```

## Tried and guarded

Read, not run:

- an application subclass that overrides `fillInStackTrace()`: its constructor is refused by name;
- an application override of `getMessage()`: `getLocalizedMessage()` calls it, and `toString()` is modelled only
  where neither message method is overridden;
- an exception the engine raises itself (a null receiver, an index out of range, a cast): `raise` allocates it with
  no message kept, so its message methods stay gaps;
- an exception a JDK call threw: no message is kept, so its methods stay gaps;
- a choice of message after a merge of paths: the JDK call, a gap;
- a lemma reading an exception that was there before its call: `reads_field`.

## Audit

No accepted result rests on the rule. The state stream's own uses, at `kmytvuop`, are not accepted results:

- 286's fixed protected-state task, proved over ASCII names in a probe, is not decided;
- 288's binding under its locales is proved on 6.1.14 in job 20261117-235132, but it is no task and not accepted.

Whether either path calls `List.of(…).get` past the end or `new HashMap(int)` with a negative capacity was not
read. Each would be a defect of the library's own on the path, which the proofs bound to ASCII names make unlikely.
Nothing for the watcher.
