# Countermodels of the pair of versions' exceptions

The challenge stream of `domain-advances` (2026-11-17), item 5. It is against the preservation stream's fix for
the earlier countermodels ([pairing](../pairing-countermodels/README.md), [fresh pair](../fresh-pair-countermodels/README.md)),
`wokytpkz` in `lib/src/pairing.rs`:
- the scope is now read on copies of its own;
- an exception is now its class's name and the names of every class above it up to `Object`
  (`same(a, b)` over `getSuperclass()`). The module says "the interfaces a class implements are not compared".

Both parts hold. At `wokytpkz`, built apart, `pairing_countermodels.rs` and `fresh_pair_countermodels.rs` pass,
the checker-side tests included. `based` below is refuted as it should be.

What the comparison still leaves out of an exception is the rest of what a caller's handler can read of it. Each
method of `old/app/Entry.java` and its namesake in `new/app/Entry.java` give a caller's handler (`Entry.handled`)
different answers when each version runs alone on a JVM (`lib/tests/thrown_pair_countermodels.rs`,
`each_handler_tells_the_versions_apart_on_a_jvm`):

| Method at 1 | Previous version alone | New version alone | Pair at `wokytpkz` | What the pair does not compare |
|---|---|---|---|---|
| `marked` | `retried`: its `app.Marked` implements `app.Retryable` | `escaped app.Marked`: same name, same superclass, no interface | **Verified** | an interface (`instanceof Retryable`), as the module says |
| `messaged` | `argument negative` | `argument too long` | **Verified** | the message (`getMessage()`) |
| `coded` | `code 403` | `code 404` | **Verified** | a field of the exception's own class (`app.Coded.code`) |
| `wrapped` | `argument inside`: a `RuntimeException` caused by an `IllegalArgumentException` | `escaped java.lang.RuntimeException`: caused by an `IllegalStateException` | no verdict: `RuntimeException(Throwable)` is a gap under strict | the cause (`getCause()`). Under `--gaps assume` the assumption it states ("keeps nothing of its arguments") is false of the JDK, so it is no false proof either |
| `based` | `argument bad`: `app.Based extends app.Base extends IllegalArgumentException` | `escaped app.Based`: `app.Base` extends `IllegalStateException` | violation at `based(k=1)` | nothing: the chain is compared through the previous version's own `app.Base` |

Each **Verified** is "the two versions agree on every input where k >= 0 && k < 4", non-vacuous (`agree(k=0)`
reaches the calls), with no assumption stated, and the note names what was compared ("the interfaces are not
compared"). So `marked` is the documented limit, reproduced. `messaged` and `coded` are not in the note: it says
"threw exceptions of classes of one name that extend classes of one name up to Object", which is true of both, but
a claim that says "throw the same exception" says more.

The commands, with the fixtures compiled into `old/` and `new/` (`javac -g -parameters`):

```
jvmcontract equivalence --before old --after new --target 'app.Entry#marked' --engine native \
  --jbmc /nonexistent/jbmc --assume 'k >= 0 && k < 4'
```

and the same with `#messaged`, `#coded`, `#wrapped` and `#based`.

**What the checker should say instead** is the preservation stream's to decide. Options:
- Compare more of the exception. For example:
  - the interfaces of each class in the chain, as `getInterfaces()` names them;
  - the message, by content;
  - the exception's own fields, as a result object's are compared;
  - the cause's class, recursively, once `RuntimeException(Throwable)` is modelled.
- Or state in each claim that uses the pair what "the same exception" is: one class name and one chain of
  superclass names. 289's and 290's preservation claims (the evidence stream restates claims) are the ones this
  bears on.

The test the checker would pass after either fix, to be added to `lib/tests/thrown_pair_countermodels.rs` with the
fix. It fails today on `marked`, `messaged` and `coded`:

```rust
use jvmcontract::{equivalence, Engine, Verdict};

/// The checker's side: a caller's handler tells each pair of versions apart when each runs alone (the test above), so
/// a proof that they agree is false.
#[test]
fn the_pair_does_not_prove_two_versions_agree_whose_exceptions_a_handler_tells_apart() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["marked", "messaged", "coded", "wrapped", "based"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some("k >= 0 && k < 4".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("thrown-pair-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though a caller's handler tells the versions apart: {wrong:?}");
}
```

A fix that states the limit in the claims, and does not compare more, keeps `marked`, `messaged` and `coded`
Verified. That fix drops them from the list and says why in the test.

## Tried and guarded

- A superclass's superclass that changed while the class and its direct superclass keep their names (`based`):
  refuted, through the previous version's copy of `app.Base`.
- A scope that writes a cell: [fresh pair](../fresh-pair-countermodels/README.md)'s `first` is a violation at
  `wokytpkz`. The scope now gets `clone()`s, and the pair takes only integral, boolean and String arrays, whose
  cells are values or immutable, so a shallow copy is a whole copy.
- The cause of an exception: refused as a gap (`wrapped`, above).

## Audit

Which accepted results use the mechanism, and whether they are affected:
- 289's and 290's `preservation` say "return the same value or throw the same exception". Their rerun on this
  checker (job `20261117-151521-examples-289-and-290-preservation-once-m`) reads that as one class name and one chain
  of superclass names.
- With `javap -p`, across the releases' pinned JARs (hashes checked against `target.json`), every class named
  `*Exception` or `*Error` was compared: 101 for 289 and 191 for 290. None differs in what it extends, what it
  implements, or its fields and methods. So `marked` and `coded` cannot occur there, and the JDK's exceptions are one
  JDK's on both sides.
- Whether a message differs between the releases on the claims' domain was not checked. A message is a literal at
  each `throw`, which the comparison of headers does not see. So the claims stand as the pair reads them, and say
  "the same exception" without saying the message is not compared. That goes in both examples' notes and to the
  owner.
- No accepted result is shown to rest on these holes, so there is nothing for the watcher.
