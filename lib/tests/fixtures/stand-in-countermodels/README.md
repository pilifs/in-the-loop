# Stand-in countermodels: what a lemma's proof rested on is not stated by the check that uses it

The state stream's `qlylowvo` (2026-11-17) lets a stand-in class, sampled against a library method on a JVM, replace
that method in the tool's own checker (`prove --stand-in CLASS`, `lib/src/stand_in.rs`). A result that made such a
call states the stand-in as what it rests on: sampled, not proved. That is the rule's own guard, since a stand-in is
only as good as its sampler.

A lemma (`--lemmas`) is proved first by a check of its own, given the check's options, the stand-ins and the models on
request included (`property::run_check`, the lemma loop). The check that uses the lemma then states it as one
assumption, of basis `proved`: "satisfies ... proved beside this check, at its bounds". What the lemma's proof rested
on is not carried over. The check's statement holds only what its own run's engine noted (`checker_assumptions(last)`).
Where the lemma's proof made the stand-in's call and the check's own path did not, the check says it rests on nothing
sampled.

## The case

`sn/` holds a reflective property writer (`Wrapper.set`, which upper-cases a name's first unit, so "age" and "Age"
both write age) and a stand-in, `NarrowStandIn`. The stand-in takes names only as written. Its sampler is honest but
narrow: it compares the bean's whole state and the exception on four names ("age", "name", "x", ""), and each agrees.
It never tries "Age".

| Target | With | Checker (state's `zlvqxmst`, built apart) | States the stand-in | A JVM |
| --- | --- | --- | --- | --- |
| `sn.Use#ageAfter` | `--stand-in sn.NarrowStandIn` | Verified `result == 0` where `name.length() == 3 && name.charAt(0) != 'a'` | yes, "4 samples ... not proved" | `ageAfter("Age") == 32` |
| `sn.Use#viaLemma` | the same, and `--lemmas age.lemmas` (the row above as a lemma) | **Verified**, non-vacuous | **no**: the lemma is stated as `proved` | `viaLemma("Age") == 32` |

The first row is the rule working: a false result that says what it rests on. The second is the same false result with
no word of the stand-in. The text output's `lemma:` lines show the lemma's verdict and not what it rested on either.

The same loss holds for a model on request, the state stream's `kztoupry`: `sn.Queued#queued` (an `ArrayDeque` pushed
once, `--model java.util.ArrayDeque`) states the model, and a method that calls it through a lemma states only the
lemma (probed at `zlvqxmst`, not kept as a fixture: the model is right there, so no JVM tells the results apart). An
engine assumption a lemma's proof would carry, the default locale for `toLowerCase()`, is refused inside a lemma's proof
("reads the default locale ... which a caller can change"), so it cannot be lost this way.

## Commands

```sh
javac -g -parameters -proc:none --release 21 -d /tmp/sn-classes lib/tests/fixtures/stand-in-countermodels/sn/*.java
cd lib/tests/fixtures/stand-in-countermodels
jvmcontract prove 'sn.Use#viaLemma' --classes /tmp/sn-classes --engine native \
  --assume "name.length() == 3 && name.charAt(0) != 'a'" --assert 'result == 0' \
  --lemmas age.lemmas --stand-in sn.NarrowStandIn --json
java -cp /tmp/sn-classes sn.Use              # ageAfter=32 viaLemma=32
java -cp /tmp/sn-classes sn.NarrowStandIn    # four samples, each the same
```

`lib/tests/stand_in_countermodels.rs` holds the fixture to a JVM: both entries give 32 on "Age", and the sampler's
four samples agree.

## Options

- Carry the lemma proof's engine assumptions (each with its basis: `stand-in`, `model`, `observed`, `gap`) into the
  statement of the check that uses it, beside the lemma. The lemma's own `stated` already has them.
- Or give the lemma's assumption the weakest basis of what its proof rested on, so that a lemma proved through a
  stand-in is `sampled`, not `proved`.
- Or refuse a lemma whose proof rested on anything but the code (no stand-in, no model on request), as the lemma's
  proof already refuses the default locale.

## The checker's side

For the state stream, beside `lib/tests/stand_in.rs` (`sn` compiled like `si` there):

```rust
/// A check that uses a lemma whose proof made a stand-in's call states the stand-in, or gives no proof.
#[test]
fn a_check_through_a_lemma_states_the_stand_in_the_lemmas_proof_rested_on() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/stand-in-countermodels");
    let mut o = property::Options::new(&[classes.to_path_buf()], "sn.Use#viaLemma");
    o.engine = Engine::Native;
    o.jbmc = "/nonexistent/jbmc".into();
    o.assume = Some("name.length() == 3 && name.charAt(0) != 'a'".into());
    o.assert = Some("result == 0".into());
    o.lemmas = Some(dir.join("age.lemmas"));
    o.stand_ins = vec!["sn.NarrowStandIn".into()];
    o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("stand-ins").join("through-a-lemma"));
    let out = property::run(&o).unwrap();
    let named = out.stated.as_ref().map(|s| s.assumptions.iter().any(|a| a.text.contains("sn.NarrowStandIn.set stands in"))).unwrap_or(false);
    assert!(out.verdict != Verdict::Verified || named, "proved through the lemma with no word of the stand-in: {}", out.output);
}
```

It fails at `zlvqxmst`, as it should.

## Tried and guarded

- The receiver check: a stand-in is taken only on an object of exactly its class that no gap made
  (`!assumed` in `invoke_instance`), so a subclass's receiver runs the method as written (state's own test).
- A pair of versions: a previous version's classes are copies under other names, so a stand-in of the new version's
  method is never taken on the old one's.
- The stand-in's hand-back: a call the method makes of itself from inside, reached through the stand-in, is taken by
  the stand-in again. It is the same method on the same kind of input, so this is no new case beyond sampling.
- What the rule states and does not check: a sampler can compare little, or nothing honest at all (`x<TAB>x`). The
  statement says "the same on each in what the sampler compares ... and not proved". The rule takes that as given, and
  no countermodel is built on it.
- The state a stand-in runs in: the sampler runs in a fresh JVM, and the check calls the stand-in in whatever state
  the caller left (a static the caller set, a system property). Like the point above, this is a limit of sampling,
  which the statement makes. For 286's stand-in: the sampler makes a fresh `BeanWrapperImpl` with only
  `extractOldValueForEditor` and `suppressNotWritablePropertyException` varied, so a wrapper with a registered custom
  editor or a conversion service is outside what it samples, and the stand-in converts `age` by `Integer.parseInt`
  regardless. 286's adapter registers neither, as far as its claims go.

## Audit

The only example that passes `--stand-in` is 286, whose driver also passes `--lemmas proofs/simple-match.contract` and
`--model java.util.ArrayList`. The lemma is `PatternMatchUtils.simpleMatch`, which calls only `String` methods. Its
proof makes no call of the bean wrapper and runs no `ArrayList`, so it rests on neither, and 286's statements lose
nothing. 288 uses the same lemma, with no stand-in. Nothing for the watcher.
