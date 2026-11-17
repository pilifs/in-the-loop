# Countermodels of an effect contract at a call

The challenge stream of `domain-advances` (2026-11-17), item 5. It is against the state stream's `vwktulky`: a
lemma with a `writes:` line is an effect contract of a public instance method, proved first with its frame and as
reading nothing that was there before the call (`bmc::Options::closed_frame`), and then used at the method's calls.
A call on a receiver of exactly the contract's class, with arguments within its bounds, runs a stub instead
(`summary::effect`, the `effect` intrinsic in `bmc/mod.rs`). The stub writes each field the contract names, in the
order of its `writes:` line, either as the parameter the assertion pins it to or as any value, and changes nothing else.

The stub stands for the method on every state and every set of arguments a caller can bring. The contract's proof
covers fewer:
- the receiver and the object parameters are distinct objects;
- each is of exactly its declared class;
- each class is initialized in the harness's fresh state.

Every contract below is proved (`effect: ✓`), and each caller's property is then **Verified** where a JVM breaks
it (`lib/tests/effect_countermodels.rs`, `each_call_an_effect_contract_stands_in_for_does_what_it_does_not_say_on_a_jvm`):

| Caller in `ec/Uses.java` | The contract | What the stub does not see | A JVM | The checker |
|---|---|---|---|---|
| `lockedLevel(level)`: sets `Config.locked`, makes a `Locked`, calls `setLevel(level)` | `Uses$Locked#setLevel`, writes `this.level`, `this.level == level` | `Locked.LOCKED`, a final static its initializer takes from `Config.locked`. The contract may read it, and its proof initialized the class with the setting false | `lockedLevel(5)` is 0 | **Verified** `result == level` |
| `pairedLevel(mine, theirs)`: `bean.setBoth(bean, mine, theirs)` | `Pair#setBoth`, writes `this.level, other.level`, `this.level == mine && other.level == theirs` | the receiver passed as `other`. The method writes `other.level` first, and the stub writes in the `writes:` order, so the stub leaves `theirs` and the method leaves `mine` | `pairedLevel(1, 2)` is 1 | **Verified** `result == theirs` |
| `linkedAdmin(links)`: `linking.link(new Rogue(false), links)` | `Uses$Linking#link`, writes `this.links`, `this.links == links`, with the frame `peer.admin == \old(peer.admin)` | an argument of a subclass: `link` calls `peer.linked()`, which `Rogue` overrides to set `admin`. Only the receiver's class is checked to be exact | `linkedAdmin(1)` is true | **Verified** `!result` |

The commands, with the four files compiled into `classes` and each contract in its own file:

```
jvmcontract prove --classes classes --classpath classes 'ec.Uses#lockedLevel' --assert 'result == level' --lemmas locked.contract --engine native
jvmcontract prove --classes classes --classpath classes 'ec.Uses#pairedLevel' --assert 'result == theirs' --lemmas pair.contract --engine native
jvmcontract prove --classes classes --classpath classes 'ec.Uses#linkedAdmin' --assert '!result' --lemmas link.contract --engine native
```

```
ec.Uses$Locked#setLevel
  writes: this.level
  assert: this.level == level

ec.Pair#setBoth
  writes: this.level, other.level
  assert: this.level == mine && other.level == theirs

ec.Uses$Linking#link
  writes: this.links
  assert: this.links == links
```

`Pair`, `Peer` and `Rogue` are top-level classes because the stub names a nested parameter class with its `$`
(`ec.Uses$Pair other`), which javac does not take. A contract over such a parameter is then not well-formed ("javac
does not take its expressions ... cannot find symbol"). That is a refusal, not a false result, but it bars every
contract whose object parameter is a nested class, as the `claims.Frames` beans are.

Reproduced on 2026-11-17 on the state stream's checker at `vwktulky`, built apart.

**What the checker should say instead** is the state stream's to decide, since the effect contract is its rule this
run. Options:
- *A final static.* Hold a contract to its class's initialization:
  - refuse a contract whose method reads a static field, final or not, whose value an initializer computes from
    anything but constants;
  - or prove the contract with the class's statics as any value;
  - or refuse the stub where the class was initialized after anything the check did. This is item 3's lemma hole
    (`Own.LIMIT = Settings.value` in `lemma-countermodels`) by another route.
- *Aliasing.* Prove the contract with every two object inputs of one class allowed to be one object, as
  `prove --may-alias this,other` does. With it, `Pair`'s assertion is refuted, and so is the frame of
  `frame-countermodels`' `promote`, which the probe showed. Or refuse a contract with two such inputs, or the stub at
  a call that passes one object twice.
- *Subclass arguments.* Require each object argument, not only the receiver, to be of exactly its declared class
  at the call. Or refuse a contract whose method makes a virtual call on an input.

The test it should pass, to be added to `lib/tests/effect_countermodels.rs` with the fix. It fails on all three on
the state stream's line today:

```rust
use jvmcontract::{property, Engine, Verdict};

/// The checker's side: no caller's property proved through a contract where a JVM breaks it (the test above).
#[test]
fn an_effect_contract_does_not_prove_a_call_a_jvm_breaks() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effect-countermodels");
    let _ = std::fs::create_dir_all(&dir);
    let mut wrong = Vec::new();
    for (caller, assertion, contract) in [
        ("lockedLevel", "result == level", "ec.Uses$Locked#setLevel\n  writes: this.level\n  assert: this.level == level\n"),
        ("pairedLevel", "result == theirs", "ec.Pair#setBoth\n  writes: this.level, other.level\n  assert: this.level == mine && other.level == theirs\n"),
        ("linkedAdmin", "!result", "ec.Uses$Linking#link\n  writes: this.links\n  assert: this.links == links\n"),
    ] {
        let file = dir.join(format!("{caller}.contract"));
        std::fs::write(&file, contract).unwrap();
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("ec.Uses#{caller}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some(assertion.into());
        o.lemmas = Some(file);
        o.work = Some(dir.join(caller));
        let out = property::run(&o).unwrap();
        eprintln!("--- {caller}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(caller);
        }
    }
    assert!(wrong.is_empty(), "a call proved through an effect contract where a JVM breaks the property: {wrong:?}");
}
```

## Whether the write set's holes carry into a caller's proof

These are the holes of `frame-countermodels`, handed over as `domain-advances-state-I005`:
- *An exceptional exit*: no. An effect contract refuses `throws:` by name. Without it, an exception the method
  throws within its bounds refutes the contract, with its witness run on a JVM. Tried with `ec.Checked`:
  `setLevel` throws on a negative level, and a caller catches it. The result: "the effect contract ... is not proved
  (it is refuted: see above)". `Uses$Failing`, which sets `admin` and puts it back unless it throws, is refused
  because it reads `admin`.
- *Aliasing*: yes, through the order of two pinned writes to one location (`pairedLevel` above). An unpinned write
  is any value, written into whichever object the caller passed. So `b.promote(b)` under `promote`'s contract leaves
  `b.admin` any value, which is sound.

## Tried and found guarded

Each was run on the state stream's checker or read in `vwktulky`, with the guard named:
- **A static switch, a receiver field a caller set, a literal's identity, a subclass receiver, a name past the
  bound.** These are the state stream's own countermodels (`claims.Frames`, the test
  `an_effect_contract_is_not_used_where_the_call_is_outside_what_it_was_proved_of`). The guards are `closed_frame`,
  the exact-class check, and the stub's bounds guard. Each guard fails in the table above only where its side
  condition is narrower than the stub's use: a final static, an argument rather than the receiver, and two inputs
  rather than one.
- **An exception after a partial write**, in the section above.
- **A call made while the contract's class is being initialized.** The stub is not used: `invoke_instance` checks
  `ClassState::InProgress`.

## Audit

Which accepted results use the mechanism, and whether they are affected:
- No example task has a lemma with a `writes:` line, or passes `--writes`. This was read on 2026-11-17 on this
  line and on the state, evidence and preservation lines.
- No accepted result rests on these holes, so there is nothing for the watcher.
- All three bear on 286's protected state, where the effect contract is meant to stand in for `DataBinder`'s
  setters. A binder target's class may take a final static from a setting. A bean may be set from another of its
  class, possibly itself. And a property's value may be of a subclass.
