# The runtime stream's upstream-build check: `ArithmeticUtils.pow` built from two pinned commons-numbers commits

Not an example and not in the router. It is the case the upstream-build route of
[`example-targets-runtime.md`](../../../../llm-dlc/loops/example-targets-runtime.md) (R2) is checked on, through
[`runtime_slice.py --case numbers`](../runtime_slice.py), as a pipeline job: an upstream build is never run inline. The
number 316, from the runtime stream's range, is used in its plan.

- `target.json`: a valid `example-target/v1` sidecar. Its two revisions and its build recipe are example 105's, as the
  positive stream's sidecar records them on its branch (read here read-only, 2026-11-14): `e7c172d2` (before) and
  `8cfc04e8` (after, the squash merge of apache/commons-numbers#223, whose one parent is before), built by
  `mvn --projects commons-numbers-core ... package` on JDK 11. Example 105's packet, tasks, oracle and controls are
  the positive stream's; this folder is no part of them.
- `adapter/`: calls the original `ArithmeticUtils.pow(int, int)` with the two raw inputs, and nothing else.
- `driver/`: one JSON line per input, the outcome as the JVM gave it.
- `oracle.py`: the statement written from the method's Javadoc (the same at both commits), and its `PROBES`. It never
  calls commons-numbers. The source at before was read once, to check that what it throws is the two classes the
  Javadoc names.

```text
python3 examples/tools/targets/runtime_slice.py ATTEMPT --case numbers   # fetches and builds: a job
```

Expected: both commits are artifacts-ready, each built by Maven from a fresh checkout and a fresh local repository with
Maven Central as its one repository, the recorded parent checked, the checkout unchanged by the build. On JDK 21 and 25
each, before disagrees with the oracle at `pow(-2, 31)` alone (it throws `ArithmeticException` where `-2^31` is an
`int`) and after nowhere, and the two JDKs agree on each commit.

This is a conformance replay of the route, not a claim.
