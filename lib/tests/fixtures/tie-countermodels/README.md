# Countermodels of what the pair of versions takes as the same code

The challenge stream of `domain-advances` (2026-11-17), item 5. It targets the preservation stream's `owrsowqm`
(`lib/src/bmc/ties.rs`, with `shared::fingerprint`). In a pair of versions, a loop summarized past the bound on each
side takes one set of free bits where the state key is the same on both sides. The key has three parts:
- the code: the method's fingerprint, "with everything it reaches";
- the static fields of the classes that code uses;
- the reachable objects, each by its class. A previous version's copy of a class goes by its own name when the two
  versions' classes "agree on what a call from outside a fingerprint can reach": the supertypes, the fields, and the
  methods that are neither static nor private.

All three rest on `reach` in `lib/src/shared.rs`, and it skips any call whose owner is a JDK class
(`InvokeVirtual | InvokeInterface`: "the JDK is the same in both versions"). A call through `IntUnaryOperator`,
`Runnable`, `Comparator` or `Object.toString` can still run an application class's code. That code is then in no
fingerprint. Its private and static helpers are in no class surface. The static fields it reads belong to classes the
code does not "use", so they are not in the key.

The same reach decides an older check: a target "identical in both versions, with everything it reaches", verified
with nothing to prove (`plan.identical` in `shared::plan_untimed`, used in `equivalence.rs`). That one is on every
line, this one included.

`old/app` and `new/app` differ only in `Step`'s private helper (2 against 1 past 1000) and in `Config`'s initializer
(`step = 2` against `1`). `Entry` and `Setting` are the same in both. Each version's `main` runs the three methods
alone (`lib/tests/tie_countermodels.rs`, `each_version_alone_differs_past_a_thousand_on_a_jvm`):

| Method | Previous alone | New alone | Checked | Preservation's line (`lmyvttyt`) | This line (`uqrzluvx`) | What it misses |
|---|---|---|---|---|---|---|
| `supplied` | `supplied(1001) == 2` | `== 1` | defaults | **"behaves as before on every input (... identical in both versions; nothing to prove)"** | **the same** | `Step.applyAsInt`, reached through `IntUnaryOperator`, is not in the reach |
| `summed` | `summed(1002) == 2` | `== 1` | `--engine native --assume 'k >= 0 && k < 2000' --unwind 2` | **Verified**, non-vacuous (`agree(k=20)`), both loops "covered by invariants" | no verdict: spurious `agree(k=3)` past the loops | the ties: `Step`'s surface leaves out `amount`, which is private |
| `configured` | `configured(1002) == 2` | `== 1` | the same | **Verified**, non-vacuous | no verdict, as above | the ties: `Config` is used by no code the fingerprint reached, so `Config.step` is not in the key |

Neither **Verified** states an assumption. Both hold with and without `--no-shared-callees`. Each proof is of two
versions a JVM tells apart at an input inside the assumption. Without the ties, each side's summary is free bits of
its own and the check ends in a spurious counterexample, as on this line.

The commands, with the fixtures compiled into `old/` and `new/` (`javac -g -parameters`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#supplied' --jbmc /nonexistent/jbmc
jvmcontract equivalence --before old --after new --target 'app.Entry#summed' --engine native \
  --jbmc /nonexistent/jbmc --assume 'k >= 0 && k < 2000' --unwind 2
```

and the same as the second with `#configured`. The shortcut is taken under any engine where no `--assume` is
given; with one, the input search over `[-100000:100000]` finds `supplied(1001)` first. The differences start at 1000 so that
the search over `[0:20]` before the loop proofs does not find them first. With the first ones written to differ at 1,
it did.

## Tried and guarded

- **A lambda** for the operator: `reach` follows `LambdaMetafactory`'s method handle, and `state_key` gives a state
  holding a lambda no key.
- **The helper called directly** (`invokestatic`, or `invokevirtual` on an application class that is effectively
  final): it is in the fingerprint.
- **A previous version whose loop adds 0** (an invariant `acc == 0` on its side only): the new side's tied state
  contradicts it, and `tied` falls back to its own bits (no verdict). That is a conservative miss, and it is why the
  fixtures differ by 2 against 1 and not by 0 against 1.
- **A JDK static method that calls back** (`String.valueOf(Object)` calling `toString`, `Arrays.sort` with a
  `Comparator`): not run. `reach` skips JDK static calls not in `JDK_SHAREABLE` in the same way, so this is the same
  cause.

## What the checker should say instead

This is the preservation stream's to decide. `shared.rs` and `ties.rs` are its own this run. Options:

- **In `reach`**, a call whose owner is a JDK class or interface and whose method is not final in a final class
  leaves the reach not closed (`closed = false`). The same goes for a JDK static call given a reference of a type that
  is not a final JDK class. Simplest, and it refuses the shortcut and the ties alike. It may cost 287, whose loops call
  only `BCrypt`'s own statics and arrays.
- **Or follow the application side**: for each application class whose objects the reached code can hold (a `new`, a
  parameter, a field or a cell read), add every method of the class that overrides or implements a JDK method to the
  reach.
- **For the ties alone**:
  - `surface` should compare every method of the class (private and static ones included) with everything they
    reach;
  - the classes those methods use should join `uses`, so that their static fields are in the key.

The test the checker would pass after either fix, to be added to `lib/tests/tie_countermodels.rs` with the fix. It
fails today on all three at `lmyvttyt`, and on `supplied` on every line:

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: each version alone tells `supplied`, `summed` and `configured` apart (the test above), so a
/// proof that they agree is false.
#[test]
fn the_pair_does_not_prove_two_versions_agree_whose_code_a_jdk_interface_reaches() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["supplied", "summed", "configured"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.jbmc = "/nonexistent/jbmc".into();
        if name != "supplied" {
            o.engine = Engine::Native;
            o.assume = Some("k >= 0 && k < 2000".into());
            o.unwind = 2;
        }
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("tie-countermodels").join(name));
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

- **The ties**: they exist on preservation's line only (`owrsowqm`), and no accepted result was checked there with
  them. The result they are made for is 287's preservation, which is open. Its loops (`ekskey`, `crypt_raw`,
  `encipher`) call `BCrypt`'s own static methods and read its own static arrays, which are in the fingerprint and the
  key. No interface call was found on them, so the hole should not reach 287's rerun. Whoever accepts that rerun
  should check it against the fix all the same.
- **The shortcut**: it is taken only without `--before-classpath` (`shared_callees` and no closure of the previous
  version's own). The decided preservation results of the run are 289's and 290's, and both pass
  `--before-classpath`, so they never take it. 286's, 287's and 307's preservation are not decided. Older results
  outside this run that say "nothing to prove" are the proof cache's economics cases
  (`examples/tools/economics`). Their edits are the report's own patches, and none was read against this hole.
  Nothing for the watcher.
