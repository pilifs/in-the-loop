# The runtime stream's vertical slice: `PatternMatchUtils.simpleMatch` from published spring-core

Not an example and not in the router. It is the case R5 of
[`example-targets-runtime.md`](../../../../llm-dlc/loops/example-targets-runtime.md) runs end to end, through
[`runtime_slice.py`](../runtime_slice.py). The number 315, from the runtime stream's range, is used in its plan.

- `target.json`: a valid `example-target/v1` sidecar. Its revisions are the Spring Framework release tags v5.3.18 and
  v5.3.19, by their full commits, checked with `git ls-remote` on 2026-11-14. Its preparation is the
  published-artifact route. Each release lists its spring-core JAR first, then spring-jcl, spring-core's one compile
  dependency in its POM at that version. Each JAR has its Maven Central URL and the sha256 recorded by
  `runtime_maven.py pin`, which also checked it against Central's `.sha1`.
- `adapter/`: calls the original method with the two raw inputs, and nothing else.
- `driver/`: one JSON line per input, the outcome as the JVM gave it.
- `oracle.py`: the statement written from the method's Javadoc, and the 45 `PROBES`. It never calls spring-core.
- `mutant/suffix-anywhere.patch`: a constructed mutant of 5.3.19, declared in `target.json` as workflow W1 shapes it
  (the revision `mutant`, the `mutation` pair and the `mutant-replay` task). The patch turns the suffix branch's
  `str.endsWith(pattern.substring(1))` into `str.contains(...)`. Until the merge it sat beside `target.json` in a
  `mutation.json` of the same content, which `runtime_slice.py` merged into the plan; it moved in as it was on
  2026-11-14. On the published-artifact route the mutant is a copy of 5.3.19's JAR whose `PatternMatchUtils` is recompiled from the
  v5.3.19 commit's source with the patch applied. It is a sensitivity control, never a revision of Spring.

```text
python3 examples/tools/targets/runtime_slice.py ATTEMPT            # acquires what the cache lacks, from Central
python3 examples/tools/targets/runtime_slice.py ATTEMPT --offline  # the cache only
python3 examples/tools/targets/runtime_slice.py ATTEMPT --case simplematch-mutant  # a job: checks out the commit
```

What it showed on 2026-11-14:
- Both releases are artifacts-ready.
- On JDK 21 and 25 each, all 45 observations agree with the oracle.
- The two JDKs agree on each release.
- The 4 records reached `workflow.ingest`, which is still Phase 0's stub.
- `PatternMatchUtils.class` is byte-identical in the two JARs (sha256 `8562b278…ff28`). The CVE-2022-22968 fix
  between these releases changed `DataBinder`, not this method.

What the mutant job showed (`20261114-180443-example-targets-runtime-r2-a-constructed`, at `b5e28e26`, passed):
- 5.3.19 and the mutant are artifacts-ready. The mutant's `PatternMatchUtils` was recompiled by javac 25 with
  `--release 8 -g -parameters`, read off the published class (major 52, with a LocalVariableTable and
  MethodParameters).
- On JDK 21 and 25 each, 5.3.19 agrees with the oracle on all 45 probes. The mutant disagrees at `("*bc","bcx")`,
  `("a*c*e","abced")` and `("*a*b","acba")` alone, each `true` where the statement says `false`. The JDKs agree.
- The unpatched recompile isn't byte-identical to the published class (`b45705e5…` against `8562b278…`). So the
  mutant differs from 5.3.19 by the patch and by the compiler. Its class is `93f15dfe…`, its JAR `7887b8fe…`.
- The job's outputs are in the history under `runtime-mutant/attempt/` (the records, logs and small JARs), but the
  three spring-core JARs aren't: at 1.4 MiB they exceed jj's snapshot limit (VF-025). Nothing is lost. The two
  published ones are acquired again by their recorded sha256, and the mutant JAR is rebuilt by the command above.
  `prepared.json` records its hash and its classes'.

This is a conformance replay of the route, not a claim, and no part of the matching-predicates packets.
