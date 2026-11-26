# Complete reactive resource cleanup before reporting transaction completion

The merged reactive operator releases its owned lease before completion. On rollback it withheld the original application error until the cleanup gate opened and another caller could acquire the lease.

The parent committed or rolled back but left the lease held. A participating transaction on both revisions kept its owner's lease and made no commit.

Each pin supplies its changed production classes on spring-tx-5.2.0.M2-q26. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · owned | `[1, 2, 3, 4]:complete:c1:r0:released0:available=false` | `[1, 2, 3, 4]:complete:c1:r0:released1:available=true` | matched |
| Control · participate | `[7]:complete:c0:r0:released0:available=false` | `[7]:complete:c0:r0:released0:available=false` | matched |
| Challenge · rollback | `[1]:early=true:waiting=false:sentinel=true:c0:r1:released0:available=false` | `[1]:early=false:waiting=true:sentinel=true:c0:r1:released1:available=true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 533` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/22881)
