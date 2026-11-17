# Countermodels of the models on request under assumed gaps

The challenge stream of `domain-advances` (2026-11-17), item 5. It is against the state stream's models on request of
`java.util.ArrayDeque` and `java.util.HashSet` (`kztoupry`, `lib/models/java/util/lists/`), which join
`java.util.ArrayList`'s (`jvmcontract::models::ON_REQUEST`): with `--model C`, the own checker runs the model's
bytecode for each constructor and method of `C` it keeps, and any other is the JDK call it names, a gap.

Under `--gaps assume`, a gap is taken to do what `lib/src/bmc/gaps.rs` says:
- a constructor "constructs the object and does nothing else";
- a method that returns an object "returns a new object, never null".

Either way the object is `Obj::new(class)`, with no field written. When `class` is one the check runs a model of, a
later call the model keeps reads those fields, and the result is a value nobody computed. Without the model, the same
call is a `jdk-primitive-method` gap, which has no assume form ("its value could only be made up") and is refused.

Each method of `mc/Gapped.java` returns the size of a collection of one element made by such a call
(`lib/tests/model_countermodels.rs`, `each_collection_a_gap_makes_is_what_a_jvm_says_it_is`):

| Method | The call the model does not keep | A JVM | The checker, `--gaps assume`, with the model | What the assumption says of the JDK |
|---|---|---|---|---|
| `cloned()` | `ArrayDeque.clone()`, whose return type is `ArrayDeque` | 1 | **Verified** `result == 0` | true: the JDK's `clone` returns a new object, never null, throws nothing and changes neither its receiver nor its arguments |
| `copied()` | `ArrayDeque(Collection)` | 1 | **Verified** `result == 0` | false, and stated: "keeps nothing of its arguments" |
| `listed()` | `ArrayList(Collection)` | 1 | **Verified** `result == 0` | false, and stated, as above |

Reproduced on 2026-11-17, each with the stated assumptions listed and non-vacuous:
- On the state stream's checker (`domain-advances-state@-`, `qrqtplwq`, built apart), all three.
- On the challenge line's checker (`roqtqlpm`), `listed()`: the ArrayList model on request is older than this run.

`cloned()` is the plain false proof: every assumption its result states is true of the JDK. In the other two, the
stated assumption is false of the JDK, but a reader is not told that it was turned into a value: the gaps table
makes the same constructor assumption for every class, and without the model it would not give `size()` a value.

The commands, with `Gapped.java` compiled into `classes`:

```
jvmcontract prove --classes classes --classpath classes 'mc.Gapped#cloned' --assert 'result == 0' \
  --engine native --gaps assume --model java.util.ArrayDeque
jvmcontract prove --classes classes --classpath classes 'mc.Gapped#copied' --assert 'result == 0' \
  --engine native --gaps assume --model java.util.ArrayDeque
jvmcontract prove --classes classes --classpath classes 'mc.Gapped#listed' --assert 'result == 0' \
  --engine native --gaps assume --model java.util.ArrayList
```

**What the checker should say instead** is the state stream's to decide, since the models on request are its this run.
Options:
- Refuse the gap under assume when the object it would make, or construct, is of a class the check runs a model of
  (`ClassPath::runs_model`): its fields could only be made up, as a primitive's value could.
- Or give such an object the model's fields as any values. That is sound, but every model method would then see
  states its constructors never make (a negative `size`, a null array), and the refusal is simpler.

The test it should pass, to be added to `lib/tests/model_countermodels.rs` with the fix. It fails on all three on the
state stream's line today:

```rust
use jvmcontract::bmc::gaps::GapMode;
use jvmcontract::{property, Engine, Verdict};

/// The checker's side: under `--gaps assume`, with the class's model asked for, no proof that the collection is
/// empty, since a JVM says it holds one element (the test above).
#[test]
fn a_model_does_not_read_fields_no_constructor_of_it_wrote() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for (method, model) in [("cloned", "java.util.ArrayDeque"), ("copied", "java.util.ArrayDeque"), ("listed", "java.util.ArrayList")] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("mc.Gapped#{method}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.gaps = GapMode::Assume;
        o.assert = Some("result == 0".into());
        o.requested_models = vec![model.to_string()];
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("model-countermodels").join(method));
        let out = property::run(&o).unwrap();
        eprintln!("--- {method}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(method);
        }
    }
    assert!(wrong.is_empty(), "proved empty, though a JVM says each holds one element: {wrong:?}");
}
```

## Tried and found guarded

Each was run on the state stream's checker, with the class's model asked for:
- **The methods the models leave out**, under `--gaps strict`, the default: `clone()`, `equals`, `hashCode` and
  `toString()` of either class, and a `HashSet` as a key of the `HashMap` model. Each is the JDK call it names, a gap
  refused by name; none falls through to `Object`'s method. `equals` and `hashCode` stay refused under assume too.
- **`HashSet(int)` under `--gaps advised`**: the contract library's contract for it says "modifies nothing", which
  would leave the model's `map` null. Nothing is solved: the run reports the model's `isEmpty()` after it as a gap
  with no contract. A run that let the model's methods past the scan would meet the same state as above.
- **An element whose hash changes after `add`** (`moved`): the checker proves that the set no longer finds it, as
  the JDK's does, since the `HashMap` model compares the stored hash before `equals`.
  - The interpreter's set finds elements by `equals` alone (`interp/natives.rs`, `set_method`), so the checker's
    witness against the opposite property does not replay.
  - That is a refusal, not a false result.
- **A lemma that reads a deque from before the call** (`STACK.size()` on a final static): refused, since the
  method reads the field `size` of an object that was there before the call (`Engine::reads`). The models are
  bytecode the engine runs, so their field and array accesses pass the same gates as the application's.
- **The exception classes**: `push(null)` throws `NullPointerException` and `pop()` on an empty deque
  `NoSuchElementException`, as on JDK 25. The state stream's `claims.Deques` holds both to a JVM.

## Audit

Which accepted results use the mechanism, and whether they are affected:
- No example's task runs under `--gaps assume`: every task of 286 to 290 and 307 is `strict`, and the only `advised`
  ones are 147 to 149, which ask for no model.
- 286's and 290's drivers ask for the models (`STATE_MODELS`, `MODELS`) under strict, where each of these calls
  is refused.
- No accepted result rests on the hole, so there is nothing for the watcher.
