# Countermodels of the pair of versions

The challenge stream of `domain-advances` (2026-11-17), item 1. Each method of `old/app/Entry.java` and its namesake
in `new/app/Entry.java` give different results when each version runs alone on a JVM (`lib/tests/pairing_countermodels.rs`,
`each_version_alone_is_what_a_jvm_says_it_is`, under an English default locale):

| Method | Previous version alone | New version alone | What the pair (`lib/src/pairing.rs`) does not say |
|---|---|---|---|
| `locale(s)` | sets a Turkish default, lowers: `I` → U+0131 | lowers under the JVM's own: `I` → `i` | the previous version runs first in the same JVM, so the new one lowers under the default the previous one set (`pairing.rs:39-41`, stated in the report's note, guarded by nothing) |
| `flag(k)` | writes `lib.Flags.on`, returns 1 | reads `lib.Flags.on`, never set alone: 0 | without `--before-classpath` a library's statics are one copy for both versions: the new one reads what the previous one wrote (`equivalence.rs`, `Previous::shared`) |
| `thrown(k)` | throws `lib.AException` at 1 | throws `lib.BException` at 1 | both are `RuntimeException`s outside `harness::EXCEPTIONS`: one category, so they "agree" (`pairing.rs:105-146`) |
| `argument(k)` | throws `IllegalArgumentException` at 1 | throws `lib.BadArgument` (a subclass) at 1 | the subclass is caught by the superclass's `catch`: one category |
| `scoped(s)` | lowers under the default | lowers under `tr-TR` | the scope `app.Entry.special(s)` is the new version's code, run before both calls; it is false everywhere (nothing is meant to change) and sets a Turkish default, which the previous version then lowers under |

Reproduced on 2026-11-17 on the checker as it was (`lupovnmv`): each of the five is **Verified** ("the two versions
agree on every input where ..."), with `--before-classpath` everywhere but `flag`. Each is false of the versions run
alone, and each would be false of a claim that says "return the same value or throw the same exception", as 287's,
289's, 290's and 307's preservation claims say.

**The order of the two calls is observable.** Swapping the versions' roles runs the calls in the other order and
changes nothing else in the statement (the comparison is symmetric): `flag` swapped is a violation on `k=0`, and
`locale` swapped is unverifiable (the checker's witness `s="I"` is right, but the interpreter lowers without the
locale, `interp/natives.rs` `toLowerCase`, finds the versions agreeing, and drops it: a conservative miss of the
interpreter, not a false proof). `flag` with `--before-classpath` is a violation in either order. Those three
violations are the test `in_the_other_order_or_on_its_own_library_the_pair_sees_the_static_differ`.

**What the checker should say instead** is the stream that changes the pairing's to decide (the preservation stream
in this run): a refusal by name, each version in a fresh state, the exceptions compared by class, or a scope held to
read nothing and write nothing. The test it should pass, to be added to `lib/tests/pairing_countermodels.rs` with
the fix (it fails today, on all five):

```rust
/// The checker's side: each pair of versions differs when each runs alone (the test above), so a proof that they
/// agree is false. Each case is also run with the versions' roles swapped, which runs the calls in the other order
/// and changes nothing else in the statement: where the order is observable the two verdicts differ.
#[test]
fn the_pair_does_not_prove_two_versions_agree_that_differ_when_each_runs_alone() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let mut wrong = Vec::new();
    let mut check = |name: &str, o: equivalence::Options| {
        let (v, out) = verdict(&o);
        eprintln!("--- {name}: {v:?}\n{out}");
        if v == Verdict::Verified {
            wrong.push(name.to_string());
        }
    };
    // Shared JDK state: the previous version sets the default locale the new one lowers under.
    for (name, before, after) in [("locale", &c.old, &c.new), ("locale-swapped", &c.new, &c.old)] {
        let mut o = options(before, after, "app.Entry#locale", name);
        o.before_classpath = Some(vec![c.library.clone()]);
        o.assume = Some(ASCII.into());
        check(name, o);
    }
    // A library's static, shared by the two versions without --before-classpath.
    for (name, before, after) in [("flag", &c.old, &c.new), ("flag-swapped", &c.new, &c.old)] {
        let mut o = options(before, after, "app.Entry#flag", name);
        o.assume = Some(SMALL.into());
        check(name, o);
    }
    // Exceptions by category: two unrelated RuntimeExceptions, and an IllegalArgumentException against a subclass.
    for method in ["thrown", "argument"] {
        let mut o = options(&c.old, &c.new, &format!("app.Entry#{method}"), method);
        o.before_classpath = Some(vec![c.library.clone()]);
        o.assume = Some(SMALL.into());
        check(method, o);
    }
    // The allowed change runs the new version's code before both calls: a scope that is false everywhere but sets
    // the default locale makes the claim "agree on every input" and makes the versions agree.
    let mut o = options(&c.old, &c.new, "app.Entry#scoped", "scoped");
    o.before_classpath = Some(vec![c.library.clone()]);
    o.assume = Some(ASCII.into());
    o.unchanged_unless = Some("app.Entry.special(s)".into());
    check("scoped", o);
    assert!(wrong.is_empty(), "proved to agree, though each version alone gives another result: {wrong:?}");
}
```
