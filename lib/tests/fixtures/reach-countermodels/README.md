# Countermodels of the code two versions are taken to share, past the reach's fix

The challenge stream of `domain-advances` (2026-11-17), item 5. It targets the preservation stream's `kskmpmny`, its
fix for `domain-advances-preservation-I010`. `reach` in `lib/src/shared.rs` now:
- leaves the reach open where a call into the JDK may come back into the application;
- takes in the initializers of the application classes the code uses: a class made, a static method called, a static
  field read or written, each with its superclasses' initializers.

Two checks rest on it:
- the shortcut that verifies a target "identical in both versions, with everything it reaches" with nothing to prove
  (`plan.identical`; older than the run, and taken only without `--before-classpath`);
- the ties of the tool's own checker (`shared::fingerprint`), which give a loop summarized past the bound in both
  versions one set of bits where the code and state are "the same".

The fix holds for what it was made for. At `kskmpmny` (built apart, with the sources touched),
`tie_countermodels.rs` passes, its checker-side test included.

What the reach still leaves out, each in `old/app` against `new/app`:

| Method | Previous alone | New alone | What differs | Why the reach does not see it |
|---|---|---|---|---|
| `Entry#removed` | 2 | 1 | `Square` (final) overrides `Base.area` in the previous version only | Only the new version's reach is walked. Its call `Square.area` resolves to `Base.area`, and `same_everywhere` looks the previous version up by that declaring class, `Base`, whose `area` is the same. The previous version's own `Square.area` is never compared. A static method the previous version hides is the same case |
| `Entry#hidden` | 0 | 1 | the previous version's `Box` declares a field `x` that hides `Holder.x` | `getfield Box.x` reads as the same text in both, and no part of the shortcut compares a class's fields. A hidden static is the same case |
| `Entry#constant` | 2 | 1 | the initializer of the interface `Limits`, whose `LIMIT` is read as `Impl.LIMIT` | javac names the class the field was read through (`getstatic app/Impl.LIMIT`). The JVM initializes the interface that declares the field. `initialized` takes `Impl` and its superclasses, never an interface |
| `Entry#defaulted` | 2 | 1 | the initializer of `Tagged`, which `Item` implements and which declares a default method | Making an `Item` initializes every superinterface with a default method (JVMS §5.5). Only superclasses are taken in |
| `Own#f` | 2 | 1 | `Own`'s own initializer | The method's own class is initialized by the call itself, and `initialized` is asked only of what the code's instructions name |
| `Entry#looped` | 2 at 1002 | 1 | `Limits`' initializer, read through `Impl` in a loop | The ties: `Limits` is in no fingerprint and its static is not in the key |

Each version's `main` runs every method alone (`lib/tests/reach_countermodels.rs`,
`each_version_alone_differs_where_the_reach_does_not_look_on_a_jvm`).

On the checker:
- The first five, under the defaults: **"behaves as before on every input (... identical in both versions; nothing to
  prove)"**, on `kskmpmny` and on the challenge line (`plqpmmop`) alike.
- `looped`, with `--engine native --assume 'k >= 0 && k < 2000' --unwind 2`: **Verified** at `kskmpmny`, non-vacuous
  (`agree(k=20)`), with "2 loops beyond the bound covered by invariants". The same holds with
  `--no-shared-callees`. On the challenge line, which has no ties, it is no verdict: the spurious `agree(k=3)`
  does not reproduce.
- With `Impl.LIMIT` first read inside the loop, the loop "initializes a class" and is refused. So `looped` reads it
  once before the loop.

The commands, with the fixtures compiled into `old/` and `new/` (`javac -g -parameters --release 21`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#removed' --jbmc /nonexistent/jbmc
jvmcontract equivalence --before old --after new --target 'app.Entry#looped' --engine native \
  --jbmc /nonexistent/jbmc --assume 'k >= 0 && k < 2000' --unwind 2
```

The same as the first for `#constant`, `#defaulted`, `#hidden` and `app.Own#f`.

## Tried and guarded, or not run

- **The JDK side of the fix** was read, not run, against what can come back from a call:
  - a charset by name through `String.getBytes(String)` and `new String(byte[], ..., String)`, refused by name,
    including from inherited JDK code (`ByteArrayOutputStream.toString(String)`);
  - an inherited JDK method of an effectively final application class is walked, and any virtual call in it on a JDK
    class that is not sealed leaves the reach open (`Random.nextInt` calling `next`);
  - `toString` of a concatenated object;
  - `Object.toString` reached through an application class.
  
  No countermodel was found there.
- **Not built**:
  - a static method of a JDK class given only sealed arguments from JDK code the reach walks. Such a call counts as
    inert (`!from_application`), which takes in `Class.forName(String)`, `Charset.forName(String)` and
    `ServiceLoader`-backed lookups. No JDK method was found that an application class inherits and that makes such a
    call with a name the application chooses.
  - `System.setProperties` with an application subclass installed before the call. A sealed call such as
    `Integer.getInteger` then runs that subclass's `getProperty`. The installation is outside the code compared, so the
    pair's fresh state is what decides it.

## What the checker should say instead

This is the preservation stream's to decide, since `shared.rs` is its own this run. Options:

- **Walk both versions.** `same_everywhere` should compare the previous version's reach with the new one's, method for
  method by declaring class, and not look the previous version up by the new one's declarations. That closes
  `removed`, and with it any method the previous version declared that the new one resolves elsewhere.
- **Compare what a class declares**: the fields of every class whose fields the code reads or writes, and every class
  that it reaches, with their supertypes, by name, type and access. That closes `hidden`.
- **Initializers**, in `initialized`:
  - resolve a field to its declaring class or interface, as the JVM does (JVMS §5.4.3.2), and take that one;
  - for a class made, add every superinterface that declares a non-abstract, non-static method;
  - add the root's own class (and its superclasses and such superinterfaces), or that of the receiver for an instance
    method.
- Or **refuse**: leave the reach open where a field reference names a class that does not declare the field, or where
  a class reached has an application superinterface with an initializer.

The test the checker would pass after the fix, to be added to `lib/tests/reach_countermodels.rs` with it. It fails on
all six at `kskmpmny`:

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: each version alone tells every method apart (the test above), so a proof that they agree is
/// false, and so is "identical in both versions; nothing to prove".
#[test]
fn the_pair_does_not_take_as_the_same_code_what_the_reach_leaves_out() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for target in ["app.Entry#removed", "app.Entry#constant", "app.Entry#defaulted", "app.Entry#hidden", "app.Own#f", "app.Entry#looped"] {
        let mut o = equivalence::Options::new(old, new, target);
        o.jbmc = "/nonexistent/jbmc".into();
        if target.ends_with("looped") {
            o.engine = Engine::Native;
            o.assume = Some("k >= 0 && k < 2000".into());
            o.unwind = 2;
        }
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("reach-countermodels").join(target.replace(['.', '#'], "-")));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {target}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(target);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though each version alone tells them apart: {wrong:?}");
}
```

## Audit

- **The shortcut** is taken only without `--before-classpath`. 288, 289 and 290 pass it. 286's, 287's and 307's
  preservation are not decided, and their targets differ between the versions, so they are never identical.
- **The ties**:
  - 289's rerun on `kskmpmny` (job `20261117-185623`) unwinds its loops fully (26) and summarizes none.
  - 290's step failed in that job.
  - 287's loops are in `BCrypt`. In both pinned releases (hashes checked against `target.json`), `BCrypt` extends
    `Object`, implements no interface, and every field it reads or writes is its own.
  - So no case above can occur in any of them.
- Nothing for the watcher.
