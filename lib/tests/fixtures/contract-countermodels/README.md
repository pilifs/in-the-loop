# Countermodels of an effect contract past its fix

The challenge stream of `domain-advances`, item 5, on the state stream's `nslmqyry`, the fix for
`domain-advances-state-I007`. An effect contract stands in for a setter's calls. Its proof shows the setter writes
only what it states, and that it "reads nothing that was there before" the call: a field of a receiver or argument
the caller holds, or a static field that is not a constant.

What the read gate leaves out is a **final instance field** (`reads_field` in `bmc/mod.rs`, `!self.final_field(..)`).
The contract's proof makes the receiver and each object argument with its constructor in the harness's fresh state.
A caller's objects were made in the caller's state, so a final field that a constructor computes from a setting
holds what the proof never had.

| Caller in `cc.Held` | Its contract | A JVM | The checker at `nslmqyry` |
|---|---|---|---|
| `snapshotLevel(level)`: `Config.locked = true`, then `new Snapshot(1)` (field `final boolean locked = Config.locked`), the setting put back, `setLevel(level)` | `cc.Held$Snapshot#setLevel`, `writes: this.level`, `assert: this.level == level` | 0 for 5 | **Verified** `result == level` |
| `scaledLevel(level)`: a `Source` made with the setting on (`final int scale = Config.locked ? 0 : 1`) is the argument of `Scaled.setFrom(source, level)` | `cc.Held$Scaled#setFrom`, `writes: this.level`, `assert: this.level == level` | 0 for 5 | **Verified** `result == level` |
| `chosenLevel(level)`: `Chosen` has two constructors, and the one the caller uses sets the final flag | `cc.Held$Chosen#setLevel`, the same | 0 for 5 | refused: "an object made by one of several [constructors] is not supported yet" |

The two proofs state no assumption ("on every input"), and the contract's note says it "reads nothing that was there
before it", which is false of both: `setLevel` reads `this.locked`, and `setFrom` reads `source.scale`.
`Config.locked` is put back before each call, so neither reads a setting at the call: the hole is the field, not the
static the I007 fix gated.

`lib/tests/contract_countermodels.rs` holds the fixture to a JVM. The commands, with the fixture compiled into
`classes` and each contract in its own file:

```
printf 'cc.Held$Snapshot#setLevel\n  writes: this.level\n  assert: this.level == level\n' > snap.contract
jvmcontract prove --classes classes --engine native --jbmc /nonexistent/jbmc \
  --assert 'result == level' --lemmas snap.contract 'cc.Held#snapshotLevel'
```

**Options, for the state stream:**
- In the closed frame, put a read of a final field of an object that was there before through `Engine::reads` as well.
  A setter that reads its own final configuration is then refused, which is conservative.
- Or keep the exemption only for a final field that each constructor of its class sets from its parameters alone,
  with nothing else read on the way. The proof's symbolic constructor arguments then cover every value a caller's
  object can hold.

## Tried and guarded

- **A contract whose call starts a class initializer**, one of the cases `domain-advances-challenge-I002` names. The
  real call would run the initializer at that point, and the contract's stub would leave it for later, in another
  state. `Engine::initializes_in_frame` refuses initializing a class that has an initializer inside a framed method
  (`initialise_class`, on both the run and the observed route). Its superclasses go through the same routine. A class
  with no initializer has no state to make.
- **A receiver of a class with several constructors**: refused by the harness's layout (the table's last row).
- **A static final field an initializer computed**: refused since `nslmqyry` (`constant_field`). Its fixture is
  `effect-countermodels`' `lockedLevel`.
- **The write-set fix (`sltlykpk`) and the effect-contract fix (`nslmqyry`)**: `frame_countermodels.rs` and
  `effect_countermodels.rs`, built apart at `nslmqyry`, pass. Each of the six earlier cases is refuted, or refused,
  or proved as JML's `assignable` states it.

## The checker's side, for the state stream

This test fails at `nslmqyry` on both callers, as it should:

```rust
/// The checker's side, for the state stream (`nslmqyry`): no caller's property proved through an effect contract
/// that read a final field a constructor computed from a setting. A JVM gives 0 for each (the test above).
#[test]
fn an_effect_contract_reads_no_final_field_a_caller_made_in_another_state() {
    use jvmcontract::{property, Engine, Verdict};
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("contract-countermodels");
    let _ = std::fs::create_dir_all(&dir);
    let mut wrong = Vec::new();
    for (caller, contract) in [
        ("snapshotLevel", "cc.Held$Snapshot#setLevel\n  writes: this.level\n  assert: this.level == level\n"),
        ("scaledLevel", "cc.Held$Scaled#setFrom\n  writes: this.level\n  assert: this.level == level\n"),
    ] {
        let file = dir.join(format!("{caller}.contract"));
        std::fs::write(&file, contract).unwrap();
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("cc.Held#{caller}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some("result == level".into());
        o.lemmas = Some(file);
        o.work = Some(dir.join(caller));
        let out = property::run(&o).unwrap();
        eprintln!("--- {caller}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(caller);
        }
    }
    assert!(wrong.is_empty(), "a call proved through an effect contract that read a caller's final field: {wrong:?}");
}
```

## Audit

No example task has a `writes:` lemma or passes `--writes` on any line (state, evidence and preservation at their
latest commits). So no accepted result rests on this hole, and there is nothing for the watcher. It bears on 286's
protected state, the claim effect contracts are for.
