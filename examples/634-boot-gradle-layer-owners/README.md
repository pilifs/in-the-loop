# An excluded archive entry remains available to the next Gradle layer

The original Gradle builds assign Open and Hidden to opposite layers under an exclusion. The merge also keeps Hidden out of the first layer when a broader include matches it.

The consumer expands directory rules from the packaged layers.idx and rejects a missing entry, duplicate owner or changed class bytes.

| Registered history | Public observation |
|---|---|
| Intent | Parent owners Open=rest, Hidden=public. Merged owners Open=public, Hidden=rest. |
| Control | Both include-only builds assigned Hidden to public and Open to rest. |
| Challenge | On the merge, Open was in public. Hidden and Third were in rest. The three archived class files equaled the compiler outputs. |

`python3 examples/tools/build.py 634` checks the archived evidence. The original experiment can be repeated with the commands in the case record. [Case record](recorded-comparison.json) · [Claim registration](../../llm-dlc/loops/spring-boot-merged-pr-links-s01-s50-brief.md) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52530)
