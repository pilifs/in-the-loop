# Remove an element before or after iterator prefetch

JDK deque iterator removal and released Commons filter iterators are checked through the original owner and element identities.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `DequeRemoval#history` (deque) | JDK deque iterator removal and released Commons filter iterators are checked through the original owner and element identities. | established |
| `DequeRemoval#stillReturns` (deque) | The old iterator returns the original next element after its owner removed it. | refuted |
| `DequeRemoval#singleton` (deque) | Prefetch keeps the element pending and removal after consumption follows the underlying singleton policy. | established |
| `DequeRemoval#filtered` (deque) | A pending element prevents delegate removal. Removal after consumption updates the correct original deque. | established |

Inspect each strict task with `python3 examples/tools/build.py --plan 385`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm deque --output "$TMPDIR/semantics"
```
