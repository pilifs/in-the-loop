# Countermodels of the fresh pair of versions

The challenge stream of `domain-advances` (2026-11-17), item 5. It is against the preservation stream's new rule for
the pair of versions (`zmvkptqz`, `lib/src/pairing.rs`), which answered [the first countermodels](../pairing-countermodels/README.md):
- each version now starts from a fresh state (`fresh()`: the static fields, the classes' initialization and the default locale);
- an exception is now compared by its class's name, with the previous version's copy (`before.x.E`) taken for `x.E`.

Each method of `old/app/Entry.java` and its namesake in `new/app/Entry.java` behave differently for a caller when
each version runs alone on a JVM (`lib/tests/fresh_pair_countermodels.rs`, `each_version_alone_is_what_a_jvm_says_it_is`):

| Method | Previous version alone | New version alone | What the pair does not say |
|---|---|---|---|
| `first(cells)`, scope `app.Entry.zeroed(cells)` | the first cell: 5 on `{5}` | 0 on `{5}` | The scope is called on the caller's own arrays (`meantToChange(passed)`), and the copies each version gets are taken after it. A scope that writes a cell decides what both versions see: here it is false everywhere and zeroes the first cell, so the claim reads "agree on every input". The fresh state covers statics, not the arguments. |
| `failing(k)` | throws its `app.Failure`, an `IllegalArgumentException`: a caller's handler for one catches it | throws its `app.Failure`, an `IllegalStateException`: the handler does not catch it | Two classes of one name are one answer (`thrown`: `getClass().getName()`, the copy's `before.` taken off). What a caller sees of an exception is its class's place among the handlers, i.e. what it extends, and that may change between releases while the name stays. |

Reproduced on 2026-11-17. On the preservation stream's checker (`domain-advances-preservation@-`, `zmvkptqz`, built
apart), each is **Verified**: "the two versions agree on every input where ...", non-vacuous, with no
`--before-classpath` needed, since each version holds its own `app` classes.
- `first` is also Verified on the challenge line's checker, which still compares by category (`smnuqrou`): the scope's write is older than the fresh state.
- `failing` is a violation there, since `IllegalStateException` is in no category of `harness::EXCEPTIONS` and so falls in the last.

The commands, with the fixtures compiled into `old/` and `new/` (`javac -g -parameters`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#first' --engine native \
  --max-array-length 2 --assume 'cells != null' --unchanged-unless 'app.Entry.zeroed(cells)'
jvmcontract equivalence --before old --after new --target 'app.Entry#failing' --engine native \
  --assume 'k >= 0 && k < 4'
```

**What the checker should say instead** is the preservation stream's to decide. Options:
- For the scope:
  - call it on copies of its own (`copies`, not `passed`), so that each version's copy is taken from the caller's input; or
  - refuse a scope that writes what it is given.
- For the exception, either:
  - compare the names of the class and of each superclass up to `Throwable`, so that two classes of one name with
    different handlers' answers are two answers; or
  - state in the claim that a class is compared by name alone.

The test it should pass, to be added to `lib/tests/fresh_pair_countermodels.rs` with the fix (it fails today on
both):

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: each pair of versions is told apart by a caller when each runs alone (the test above), so a
/// proof that they agree is false.
#[test]
fn the_fresh_pair_does_not_prove_two_versions_agree_that_a_caller_tells_apart() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for (name, assume, scope) in [("first", "cells != null", Some("app.Entry.zeroed(cells)")), ("failing", "k >= 0 && k < 4", None)] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.max_array_length = 2;
        o.assume = Some(assume.into());
        o.unchanged_unless = scope.map(Into::into);
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("fresh-pair-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though a caller tells the versions apart when each runs alone: {wrong:?}");
}
```

## Audit

Which accepted results use the mechanism, and whether they are affected:
- **The scope.** The allowed changes of 288, 289 and 290 (in their claims) are expressions over the parameters that
  call only the JDK's reading methods (`indexOf`, `length`, `Arrays.stream(...).anyMatch`, `IntStream.range(...).allMatch`)
  and write nothing. 290's `!(servlets.length == 1 && servlets[0] == 0)` reads one cell. None is affected.
- **The exception.** 289's and 290's preservation claims say "throw the same exception", and their rerun under the
  class comparison (job `20261117-134306-examples-289-and-290-preservation-again`) would read it as "one class name":
  weaker only where a class of one name extends another class in the other release. Whether any class the adapters
  reach does was not checked here. No accepted result rests on it today: the evidence stream's `ymzlyksq` refuses
  289's and 290's accepted preservation answers until a rerun, so the check belongs with the fix, before that rerun
  is accepted.
