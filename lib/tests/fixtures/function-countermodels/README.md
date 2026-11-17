# Countermodels of a call taken as one function of both versions

The challenge stream of `domain-advances` (2026-11-17), item 5 and inbox item `domain-advances-challenge-I004`. It
targets the preservation stream's call-level rule, `uxyusvsv` and `xuwlklyo` (`lib/src/bmc/ties.rs`,
`shared::one_function`), at `qmsonuow`, which also holds its fixes for I021 and I022 (`sqprlwkv`).

The rule: in a check of a pair of versions, a call of a method both versions share (the same fingerprint) whose
arguments and statics are numbers, Strings and arrays of numbers is not run. Its outcome is new bits: whether it
throws and which class of `OneFunction::throws`, the result, and, where its code stores into an array, the cells
of every array it reaches. A later call of the same code, on either side, takes the earlier call's outcome
wherever their inputs are equal. The module's soundness argument: "the same code on the same values gives the same
outcome", and every outcome a run of the callee has is among the ones the bits allow.

The I004 floor holds. `lib/tests/fixtures/callee-countermodels/check.py --rule-landed` at `qmsonuow` (built apart,
sources touched), JDK 25.0.5: `same`, `copied` and `parsed` are verified. `twice`, `table` and `aliased` get no
verdict, from a spurious witness that does not reproduce. `seeded`, `helped`, `wiped`, `counted` and `caught` are
each a violation. No row is a false proof.

What the outcome leaves out, each shown by a pair below:
- **Cells a JDK method writes.** `OneFunction::writes_arrays` is set by an `ArrayStore` instruction in the
  application's code alone. `Arrays.fill` and `System.arraycopy` are in `ONE_FUNCTION_JDK`, and each writes into an
  argument. A callee that writes only through them leaves its arguments' cells as they were.
- **A String's identity.** The inputs name a String by its length and cells, and two related calls return the
  very same object. `if_acmp` is allowed in the callee. On a JVM, what a callee answers about `s == "key"` depends on
  which object `s` is. Two calls that each build a String return two objects, and a callee that returns a literal
  returns the interned object every time.
- **An `Error` the JVM raises.** `ONE_FUNCTION_THROWN` lists ten exceptions and no `Error`. Recursion is allowed,
  and so is an array of a length the arguments give, so a `StackOverflowError` or an `OutOfMemoryError` leaves
  the call.

`Shared` compiles to the same bytes in `old/` and `new/` (the JVM test checks it). Every callee has a loop of
three rounds, since the rule takes no call of loop-free code. `Entry` differs. Each method takes `int k`.

| Method | Previous alone | New alone | What differs | Why the rule does not see it |
|---|---|---|---|---|
| `filled` | 5 at 5 | 0 | the previous version reads the cell `Shared.fill` filled with `Arrays.fill` | no `ArrayStore` in the callee, so no cell is an outcome: the cell is 0 after the call |
| `copied` | 5 at 5 | 0 | the same, through `System.arraycopy(from, 0, cells, 0, 1)` | the same |
| `interned` | 1 | 0 | `Shared.isKey("key")` against `isKey(new StringBuilder("ke").append('y').toString())`; the callee tests `s == "key"` | the inputs are equal by content, so both calls give one answer |
| `same` | 0 | 1 | `Shared.name(k) == Shared.name(k)`, two `StringBuilder.toString()`s | the second call is related to the first and returns the same object |
| `tagged` | 1 at 2 | 0 | `Shared.tag(k) == "big"`; the callee returns the literal | the result is a new object, never the literal |
| `overflowed` | -1 at 100000000 | -2 | the previous version's handler of `StackOverflowError` returns -1, the new one's -2 | no `Error` is among the outcomes |
| `exhausted` | -1 at `Integer.MAX_VALUE` | -2 | the same, for `OutOfMemoryError` from `new long[k]` | the same |

Each version's `main` runs every method alone (`lib/tests/function_countermodels.rs`,
`each_version_alone_differs_past_the_shared_call_on_a_jvm`).

On the checker at `qmsonuow`, with `--engine native --assume 'k >= 0'`, all seven are **Verified**: "the two versions
agree on every input where k >= 0". Each is non-vacuous (`agree(k=20) reaches the calls`), with "12 calls of
methods both versions share taken as one function of both, 11 of them related" (13 and 12 for `same`). The only
assumption stated is the rule's own: "each call of app.Shared.NAME taken as one function of both versions ends".
Each call here ends.

The checker is right without the rule. In a copy built with `bmc::Options::calls_as_one_function` false by default
(a scratch switch, not committed), no call is taken, and none of the seven is proved:
- `interned`, `same` and `tagged` are violations;
- `filled` and `copied` stop at the gaps `Arrays.fill` and `System.arraycopy`;
- `overflowed` stops at "calls nested deeper than 64";
- `exhausted` stops at "an array of computed size".

**`--no-shared-callees` does not turn the rule off.** Its help says "Prove each callee as written, instead of taking
a callee unchanged in both versions as one function in both". With it, all seven are still Verified, each with
"12 calls ... taken as one function of both". The flag sets `equivalence::Options::shared_callees`, which plans the
older shared-callee proof (`equivalence.rs`) and the proof cache's key. Nothing passes it to
`bmc::Options::calls_as_one_function`, which is always true. So a reader who asks for every callee as written gets
this rule, and its stated assumption is the only sign of it.

The pair is made only where the check asks for it (`pairing::asked`: `--assume`, `--lemmas`, a `String[]` or a
nullable String). Without `--assume` the rule never runs: `self.previous` is `None`, and each method is checked as
written.

## Tried and guarded

These are kept in the fixture as controls, and the checker-side test runs them too.

| Method | Previous alone | New alone | What guards it |
|---|---|---|---|
| `hashed` | 0 | 1 | `String.valueOf((Object) cells)` shows the array's identity hash. The callee's reach is not closed, since `valueOf(Object)` calls `toString()` back, so the call runs as written and stops at the gap `String.valueOf(Object)` |
| `encoded` | -1 | -2 | `"abc".getBytes("nope")` throws `UnsupportedEncodingException`, which `ONE_FUNCTION_THROWN` does not list. The rule declines the call (the charset lookup leaves the reach open), and as written it stops at "getBytes on an object the engine does not model" |
| `messaged` | 1 at 2 | 0 | the previous version reads `getMessage()` of the exception the callee made, which a taken call makes with no message. `IllegalArgumentException.getMessage()` is a gap under strict. Under `--gaps assume` the stated assumption is "never null", false only of an exception made with none |

Also read, not run: an instance method's receiver (the `KEYED` countermodels in `lib/tests/pairing.rs` cover a
live local, a static, a handler and another object), and `uses`, which each static the code reads resolves to its
declaring class since `qopxypnn`.

## The commands

With the fixtures compiled into `old/` and `new/` (`javac -g -parameters --release 21`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#filled' --engine native \
  --jbmc /nonexistent/jbmc --assume 'k >= 0'
```

The same for each method.

## What the checker should say instead

This is the preservation stream's to decide, since the rule is its own this run. Options:

- **Cells**: count each listed JDK method that writes into an argument (`Arrays.fill`, `System.arraycopy`, and
  `String.getBytes(int, int, byte[], int)`, which is listed by name) as an array store, or set `writes_arrays`
  whenever the reach holds one.
- **Identity**: refuse `if_acmp` in the callee's code where either operand may be a String (or any reference), and
  make a String result a new object at every call, related only by `equals` (as the module's own `twice` control
  says: "a shared outcome is equal content, never one object"). A callee that may return a literal must then not
  have its result compared by `==`. Refusing a String result compared by `if_acmp` in the caller covers that.
- **Errors**: add `StackOverflowError` and `OutOfMemoryError` to the outcomes the bits allow, or refuse a callee
  that recurses or makes an array of a length the arguments give. The second would keep bcrypt's
  `new byte[cdata.length * 4]`, whose length is a constant.
- **The switch**: have `--no-shared-callees` set `calls_as_one_function` false, as its help says it does.

The test the checker would pass after the fix, to be added to `lib/tests/function_countermodels.rs` with it. It fails
on exactly the seven at `qmsonuow`:

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: each version alone tells every method apart (the test above), so a proof that they agree is
/// false.
#[test]
fn a_call_taken_as_one_function_does_not_prove_what_its_outcome_leaves_out() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["filled", "copied", "hashed", "interned", "same", "tagged", "encoded", "overflowed", "exhausted", "messaged"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some("k >= 0".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("function-countermodels").join(name));
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

- **287's preservation**, accepted at bound 80 (52 calls of `crypt_raw` taken), is not affected. Its `BCrypt` and
  `BCryptPasswordEncoder` were read with `javap -c -p` from the pinned 6.3.7 and 6.3.8 JARs, with their sha256s
  checked against `sources.lock.json`:
  - neither has an `if_acmp`, an `Arrays.fill` or a `System.arraycopy`;
  - `BCrypt` stores into arrays (1215 `iastore`/`bastore`), so `writes_arrays` holds anyway;
  - no method calls itself (the calls by name are between overloads, down one chain);
  - the encoder has no handler of an `Error` or a `Throwable`, and neither release's caller catches one. So an
    `Error` the shared call raised would leave both versions alike.
- **307's preservation and mutant-preservation**: the route's slices (sha256s matched in 307's receipts) are not
  affected. Each `BCrypt` has no `if_acmp`, `fill` or `arraycopy`. The previous version's only handler catches
  `UnsupportedEncodingException` around `getBytes("UTF-8")`, before the shared call.
- 289's and 290's preservation: `xuwlklyo` reports their capped probes verify as before. Whether the rule takes a call
  there was not read: an open point for their rerun on this checker. A call the rule takes needs a loop and inputs
  of numbers, Strings and arrays of numbers only.

Nothing for the watcher.
