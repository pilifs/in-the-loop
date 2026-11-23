# A covariant store preserves the old cell on failure

A single store and a released Commons iterator expose the exception type and the original cell through a retained reference.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `ArrayStores#history` (stores) | A single store and a released Commons iterator expose the exception type and the original cell through a retained reference. | established |
| `ArrayStores#alwaysSucceeds` (stores) | An incompatible object can be stored in a String array through its Object[] view. | refuted |
| `IteratorStores#history` (store-iterator) | A single store and a released Commons iterator expose the exception type and the original cell through a retained reference. | established |

Inspect each strict task with `python3 examples/tools/build.py --plan 380`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm stores store-iterator --output "$TMPDIR/semantics"
```
