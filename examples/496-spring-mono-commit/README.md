# A successful transactional Mono waits for commit completion

The transactional Mono now waited for the gated commit. A separate H2 connection saw zero matching rows at parent completion and one at merged completion.

The historical spring-tx operator wraps a JDBC-backed ReactiveTransactionManager. The read runs in the subscriber's completion callback at READ_COMMITTED, before the fixture releases any still-pending commit.

Each pin supplies its changed production classes on spring-tx 5.2.0.RC2. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · gate | `cancel=true early=true values=[7] complete=true commits=1 rollbacks=0` | `cancel=false early=false values=[7] complete=true commits=1 rollbacks=0` | matched |
| Control · error | `marker=true values=[] commits=0 rollbacks=1` | `marker=true values=[] commits=0 rollbacks=1` | matched |
| Challenge · visible | `count=1 visibleAtCompletion=0 visibleAfterRelease=1` | `count=1 visibleAtCompletion=1 visibleAfterRelease=1` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 496` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/23562)
