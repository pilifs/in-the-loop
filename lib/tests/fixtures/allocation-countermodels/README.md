# Countermodels of a call's memory

The challenge stream of `domain-advances` (2026-11-18), item 5. It targets the preservation stream's call-level rule
as its fix for I023 leaves it, at `puuwrruu`.

The rule (`lib/src/bmc/ties.rs`, `shared::one_function`) takes a call of code both versions share as one function of
its inputs. Its outcomes are a result, the cells it writes, and an exception from a fixed list. Since `puuwrruu`, an
`Error` the code decides is kept out of the call in three ways:
- a `StackOverflowError`, by refusing code that can call itself;
- an `OutOfMemoryError`, by refusing an array whose length the inputs give, and a JDK call given a length;
- at the call, by checking that each array the code makes has a known length of at most 65536.

What is left, by its own comment, is "the JVM's own limits, a heap or a stack already all but full, which no check
models anywhere".

**What that leaves out:** the lengths are checked one allocation at a time, and nothing bounds how many arrays a run
keeps. A loop the inputs bound can keep arrays of a constant length until no heap holds them. That is an
`OutOfMemoryError` the code decides, on a heap that starts empty.

`Shared`, `Node` and `Deep` compile to the same bytes in `old/` and `new/`, and the JVM test checks it. `Shared`'s
methods each have a loop of three rounds, since the rule takes no call of loop-free code. `Entry` differs: the
previous version answers the `Error` with -1, the new one with -2.

| Method | What the shared code does | Previous alone | New alone | At `puuwrruu`, `--engine native --assume 'k >= 0'` |
|---|---|---|---|---|
| `kept` | an `Object[16384]` of rows, each an `Object[16384]` of `long[16384]`, one row per round while `i < k`: 32 TiB once k >= 1 | -1 at 1 | -2 | **Verified**: "the two versions agree on every input where k >= 0", non-vacuous (`agree(k=20) reaches the calls`), 12 calls taken as one function. With `--no-shared-callees`, no verdict: a loop not fully unwound |
| `around` (control) | `new Deep().f(k)`: `Deep.f` calls `Node.g`, which calls `f`, `Deep`'s override | -1 at 100000000 | -2 | no verdict: the calls run as written ("calls nested deeper than 64"). The reach refuses `Node.f` as overridable, so the recursion check, which follows each call to the method it names and not to an override, is never asked |

Each version's `main` runs both methods alone, on a 64 MiB heap (`lib/tests/allocation_countermodels.rs`,
`each_version_alone_answers_the_shared_codes_error_on_a_jvm`). `kept` asks for 32 TiB, so the heap's size does not
decide it.

The checker is right without the rule. Only the rule is wrong.

## The commands

With the fixtures compiled into `old/` and `new/` (`javac -g -parameters --release 21`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#kept' --engine native \
  --jbmc /nonexistent/jbmc --assume 'k >= 0'
```

## What the checker should say instead

This is the preservation stream's to decide, since the rule is its own this run. Options:

- **Refuse an allocation in a loop** in `one_function` unless the loop's bound is a constant, and bound the total the
  call makes, the product of the lengths and the rounds, at the call.
- **Refuse a store of a reference into an array** the code made (`aastore` of an array or an object), so that what
  the code keeps is bounded by the arrays it holds in locals. bcrypt's `crypt_raw` stores only numbers.
- **State it**: put "each call ends normally on a heap that holds what it makes" among the assumptions the result
  states, beside "each call ends".

## The test the checker would pass after the fix

To be added to `lib/tests/allocation_countermodels.rs` with the fix. At `puuwrruu` it fails on `kept`:

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: each version alone answers the Error differently (the test above), so a proof that they
/// agree is false.
#[test]
fn a_calls_outcome_holds_the_memory_its_code_keeps() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["kept", "around"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some("k >= 0".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("allocation-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though each version alone tells them apart: {wrong:?}");
}
```

## Audit

- **287's preservation**, accepted at bound 80, and **307's**: they take `crypt_raw`. In 287's pinned 6.3.7 and 6.3.8
  sources (sha256s as in its `sources.lock.json`), the arrays `crypt_raw` reaches are made the same way in both:
  - `cdata`, a clone of `bf_crypt_ciphertext`;
  - `ret = new byte[clen * 4]`, `clen` being `cdata.length`;
  - `P` and `S` in `init_key`, clones of the static tables;
  - `lr = { 0, 0 }` in `key` and `ekskey`, once per call of each.

  Each is of a length from constants and static tables. No reference to any of them is stored into an array, so a
  loop keeps none of them. So `kept` cannot occur there.
- 289 and 290: whether their reruns take a call was not read, as in the function countermodels' audit.

Nothing for the watcher.
