# Report the suite outcome when all tests are registered dynamically

Two dynamically registered successful leaves now made the enclosing suite succeed. An empty dynamic container still failed the suite with NoTestsDiscoveredException.

A container is registered dynamically too. Its node groups children, while the two finished leaves independently establish the count.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `leaves=[A, B],unique=2,suite=FAILED/NoTestsDiscoveredException` | `leaves=[A, B],unique=2,suite=SUCCESSFUL` | matched |
| Control | `leaves=[],unique=0,suite=FAILED/NoTestsDiscoveredException` | `leaves=[],unique=0,suite=FAILED/NoTestsDiscoveredException` | matched |
| Challenge | `leaves=[A, B],unique=2,suite=FAILED/NoTestsDiscoveredException / leaves=[],unique=0,suite=FAILED/NoTestsDiscoveredException` | `leaves=[A, B],unique=2,suite=SUCCESSFUL / leaves=[],unique=0,suite=FAILED/NoTestsDiscoveredException` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 586`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/junit-team/junit-framework/pull/5839)
