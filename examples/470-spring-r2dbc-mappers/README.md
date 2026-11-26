# Mapping R2DBC results by property or constructor name

Both new R2DBC mappers read the row. Strict constructor mapping nevertheless rejected a complete one-property result.

| History | Observation |
|---|---|
| Intent | Both mapper classes were absent on the parent. The merged bean setter and record constructor each produced the requested type with Ada and age 37. |
| Control | An explicit driver row lambda on the same projection produced exactly one Person(Ada,37) on each revision. |
| Challenge | Default constructor mapping stored ADA without calling the setter. Strict mapping of the same complete row threw InvalidDataAccessApiUsageException. |

The projections run on R2DBC H2. The caller is compiled with -parameters, reads the actual driver row and preserves the constructor-versus-setter distinction.

With the prepared Spring cache, run `python3 examples/tools/build.py 470` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #30530](https://github.com/spring-projects/spring-framework/pull/30530)
