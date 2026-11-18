# Countermodels of the code two versions are taken to share, past the reach's second fix: a class's supertypes

The challenge stream of `domain-advances` (2026-11-17), item 5. It targets the preservation stream's `qopxypnn`, its
fix for `domain-advances-preservation-I019` (`lib/tests/fixtures/reach-countermodels`). `reach` in
`lib/src/shared.rs` now:
- walks both versions (`same_everywhere(before, after, before_reach, after_reach)`);
- resolves each field to the class that declares it, and compares those (`Reach::fields`);
- takes in the initializers the JVM runs, superinterfaces with a default method and the root's own class included.

The fix holds for what it was made for. At `qopxypnn` (built apart, with the sources touched),
`reach_countermodels.rs` passes, its checker-side test included.

What the reach still compares is each method's code (`shape`), the declaring class of each field, and the
initializers and constants of the classes whose statics are used. It never compares a class's header: its superclass
and its interfaces. Two of the four reach facts depend on them. Which method a call resolves to depends on the
superclass and the superinterfaces. What `instanceof` and `checkcast` answer depends on every supertype.
`same_everywhere` checks that each method one version reaches exists, with the same code, in the other. It does not
check that both versions reach the same methods. So where a call resolves to a different method that exists in both,
the code is "the same everywhere".

Each case is in `old/app` against `new/app`. Every method of every class is the same text in both versions; only the
headers of `Child`, `Plain` and `Mixed` differ.

| Method | Previous alone | New alone | What differs | Why the reach does not see it |
|---|---|---|---|---|
| `Entry#rebased` | 2 | 1 | `Child extends One` against `Child extends Two`. `One.value` and `Two.value` are each the same in both versions | javac names `Child.value`, and the JVM resolves it through `Child`'s superclass. The previous version reaches `One.value` and the new one `Two.value`. Each is found, the same, in the other version, and nothing compares the two lists |
| `Entry#marked` | 2 | 1 | `Plain implements Marker` in the previous version only | `instanceof app/Marker` is the same text in both, and `Plain`'s constructor calls `Object.<init>` in both |
| `Entry#cast` | 2 | `ClassCastException` | the same | `checkcast app/Marker` is the same text |
| `Entry#mixed` | 2 | 1 | `final Mixed implements Left` against `implements Right`; each declares a default `m` | the case of `rebased`, through a superinterface's default method |
| `Entry#looped` | 2 at 1002 | 1 | `marked`'s `instanceof` in a loop past the bound | The ties: the loop's fingerprint holds no class's header |

Each version's `main` runs every method alone (`lib/tests/supertype_countermodels.rs`,
`each_version_alone_differs_by_a_supertype_on_a_jvm`).

On the checker:
- The first four, under the defaults: **"behaves as before on every input (its bytecode and that of the method it
  reaches are identical in both versions; nothing to prove)"**. This holds at `qopxypnn` and on the challenge line
  alike, since the shortcut is older than the run.
- `looped`, with `--engine native --assume 'k >= 0 && k < 2000' --unwind 2`, is **Verified** at `qopxypnn`,
  non-vacuous (`agree(k=20)`), with "2 loops beyond the bound covered by invariants". The same holds with
  `--no-shared-callees`.
- The checker's own semantics are right, and only the shortcut and the ties are wrong:
  - With `--engine native --before-classpath` an empty folder, which turns the shortcut off, `marked`, `rebased`
    and `mixed` are each refuted.
  - `looped` with `--assume 'k == 1002' --unwind 1003` is refuted.
- A first `looped` that made one `Plain` before the loop and tested it in every iteration was no verdict (a spurious
  witness). So the object is made in each iteration, as is the call `isMarker(new Plain())` (also Verified, not kept).
  `Plain` is made once before the loop, since a loop that initializes a class is refused.

The commands, with the fixtures compiled into `old/` and `new/` (`javac -g -parameters --release 21`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#rebased' --jbmc /nonexistent/jbmc
jvmcontract equivalence --before old --after new --target 'app.Entry#looped' --engine native \
  --jbmc /nonexistent/jbmc --assume 'k >= 0 && k < 2000' --unwind 2
```

The same as the first for `#marked`, `#cast` and `#mixed`.

## What the checker should say instead

This is the preservation stream's to decide, since `shared.rs` is its own this run. Options:

- **Compare the headers.** For every application class the reach takes in (a method's owner, a class made, a class
  named by `instanceof`, `checkcast`, `anewarray`, an `ldc` of a class or a handler's catch type, and each of their
  supertypes), compare the superclass and the interfaces by name in both versions. Put the same in the fingerprint.
- **Compare the reaches.** Require the two reaches' methods to be the same list by declaring class (`before_reach.methods`
  against `after_reach.methods`, by name), as the fix already does for `fields` and `statics`. That closes `rebased`
  and `mixed`, but not `marked`, `cast` or `looped`.
- Or **refuse**: leave the reach open where an application class's header differs between the versions.

The test the checker would pass after the fix, to be added to `lib/tests/supertype_countermodels.rs` with it. It fails
on all five at `qopxypnn`:

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: each version alone tells every method apart (the test above), so a proof that they agree is
/// false, and so is "identical in both versions; nothing to prove".
#[test]
fn the_pair_does_not_take_as_the_same_code_what_a_supertype_changes() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for target in ["app.Entry#rebased", "app.Entry#marked", "app.Entry#cast", "app.Entry#mixed", "app.Entry#looped"] {
        let mut o = equivalence::Options::new(old, new, target);
        o.jbmc = "/nonexistent/jbmc".into();
        if target.ends_with("looped") {
            o.engine = Engine::Native;
            o.assume = Some("k >= 0 && k < 2000".into());
            o.unwind = 2;
        }
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("supertype-countermodels").join(target.replace(['.', '#'], "-")));
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

Each class file in each example's pinned releases was read, with every JAR's sha256 checked against the example's
`sources.lock.json`. For each class in both releases, its superclass, its interfaces and whether it is an interface
were compared:
- 289: spring-security-web 5.6.3/5.6.4 with spring-core, spring-web and spring-jcl 5.3.19/5.3.20. 2431 classes, none
  differs.
- 290: spring-security-config, -core and -web 5.8.4/5.8.5 with spring-beans, -context, -core, -jcl, -web and -webmvc
  5.3.28/5.3.29. 5269 classes, none differs.
- 287: spring-security-crypto 6.3.7/6.3.8. 52 classes, none differs.

So no case above can occur in them, under the shortcut (which 288 to 290 do not take anyway, since each passes
`--before-classpath`) or under the ties. 307's pair is a commit and its parent, compiled by its route, and was not
read. Its target differs between the versions, so the shortcut is not taken there. 286 and 288 have no decided
preservation. Nothing for the watcher.
