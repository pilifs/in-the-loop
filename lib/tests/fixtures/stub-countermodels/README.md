# Countermodels of an effect contract's stub inside a proof that limits writes

An effect contract (a `--lemmas` declaration with `writes:`, the state stream's `vwktulky` and after) stands in for a
method's calls by a stub. The stub's `effect` intrinsic (`Engine`'s contract intrinsics, `lib/src/bmc/mod.rs`) puts
each written field into the object directly. It does not ask `Engine::keeps`, the gate every `putfield` passes. Two
proofs rest on that gate:

- **A proof by induction** (`--decreases`). The hypothesis that stands in for the method's calls of itself states
  their result and nothing else, so `keeps` refuses a write to an object that was there before the call ("the
  induction hypothesis states the result of its calls of itself only").
- **A write set** (`--writes`). `keeps` refuses a write to a static's object that is none of the method's inputs
  ("outside its write set").

Through the stub, each write passes unseen. The inbox item I002 asked where the lemma rule and the write-set rule
meet in `Engine::call`. This is where they meet in practice. A lemma's own proof and a contract's own proof are given
no lemma and no contract (`lemmas: None` in `lib/src/property.rs`), so neither can run a stub. A check's own
`--decreases` or `--writes` can.

`sc.M.main` runs both on a JVM (`java -cp CLASSES sc.M` prints `f=-1 held=5`), and
`lib/tests/stub_countermodels.rs` holds the fixture to it. The challenge stream reproduced both on 2026-11-17, at
state's `twtuqvvr` and on a trial merge of the challenge line (`klqnuoxw`'s parent `xnqlyxnw`) with state's
`vvpxytqs`, each built apart.

| entry point | the contract (`set-level.contract`) | a JVM | the checker, with the contract | without it |
|---|---|---|---|---|
| `Store.f(k)`: `if (k <= 0) return 0; BEAN.setLevel(k); f(k - 1); return BEAN.level - k;`, `--decreases k`, `--assert 'result == 0'` | `sc.Bean#setLevel`, `writes: this.level`, `assert: this.level == level` | `f(2) == -1` | **Verified** "on every input", non-vacuous | refused: "writes a field of an object made before it was called, and the induction hypothesis states the result of its calls of itself only" |
| `Touch.touch(v)`: `HELD.setLevel(v); return v;`, `--writes ''` (it writes nothing that was there before the call), `--assert 'result == v'` | the same | `HELD.level` becomes 5 | **Verified**; the result does not state the empty write set at all | refused: "outside its write set" |

The commands, with the fixture compiled into `classes`:

```
jvmcontract prove 'sc.Store#f' --assert 'result == 0' --decreases k --lemmas set-level.contract \
  --engine native --jbmc /nonexistent/jbmc --classes classes --work WORK
jvmcontract prove 'sc.Touch#touch' --assert 'result == v' --writes '' --lemmas set-level.contract \
  --engine native --jbmc /nonexistent/jbmc --classes classes --work WORK
```

The first is a false result about the method's value. `f(2)`'s call of `f(1)` sets the level to 1, and the
hypothesis leaves it at 2. The second is a false frame. An empty write set over a static method has no inputs, so
the frame is the engine's refusals alone (`frame` in `lib/src/property.rs` returns `None`), and the statement says
nothing of writes. A reader cannot tell that `--writes ''` was asked for, nor that it is false.

**Options, for the state stream:** have the `effect` intrinsic ask `self.keeps(path, Some(o), "writes a field of an
object made before it was called")` for each write, before it inserts the value. That gives the same refusal as the
method run as written. Or refuse an effect contract in a check with `--decreases` or `--writes`. Separately, state
the write set in the statement when it has no field to read after the call.

**Tried and guarded:**

- A lemma whose proof runs a call an effect contract stands in for, and an effect contract inside a summarized method:
  a lemma's proof is given no lemma and no contract (`lemmas: None`). The call runs as written there, and `keeps`
  sees it.
- An effect contract whose proof uses another: the same.
- A framed method or a contract whose call starts a class initializer: refused by `Engine::initializes_in_frame`
  (tried at `nslmqyry`).
- A framed method over object inputs that uses a contract: a check over objects takes no lemmas or contracts ("the
  property is not well-formed: the check uses a lemma or a proof by induction"), since the claim's class is over
  plain parameters only.

**The test the state stream's checker should pass**, beside `effect_countermodels.rs`'s:

```rust
/// An effect contract's stub inside a proof by induction or under a write set: each write it makes passes the gate
/// the method's own write would meet. On a JVM f(2) is -1 and touch(5) sets HELD.level (tests/stub_countermodels.rs).
#[test]
fn an_effect_contracts_writes_meet_the_induction_and_the_write_set() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let contract = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/stub-countermodels/set-level.contract");
    for (entry, extra) in [("sc.Store#f", ["--assert", "result == 0", "--decreases", "k"]), ("sc.Touch#touch", ["--assert", "result == v", "--writes", ""])] {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env_remove("JAVA_TOOL_OPTIONS")
            .arg("prove").arg(entry).args(extra).arg("--lemmas").arg(&contract)
            .args(["--engine", "native", "--jbmc", "/nonexistent/jbmc", "--classes"]).arg(classes)
            .arg("--work").arg(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join(format!("stub-{entry}")))
            .output()
            .unwrap();
        let stdout = String::from_utf8_lossy(&out.stdout);
        assert!(!stdout.starts_with("✓"), "{entry}: proved where a JVM says otherwise\n{stdout}");
    }
}
```

**Audit** (2026-11-17), on the challenge, state, evidence and preservation lines:

- The only `decreases:` of any example is the `simpleMatch` lemma (286's and 288's `simple-match.contract`), a
  lemma whose proof takes no contract.
- No example has a `writes:` declaration or passes `--writes`.

No accepted result rests on the hole, and there is nothing for the watcher.
