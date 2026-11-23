# Default interface methods on a refined receiver

Interface order, a class override and a qualified super call determine the result for every signed int.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `DefaultDispatch#dispatch` (dispatch) | Both declaration orders select the refined default and the class override wins, at every int value. | established |
| `DefaultDispatch#firstDeclared` (dispatch) | The first-listed base interface wins over the more specific default. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 382`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm dispatch --output "$TMPDIR/semantics"
```
