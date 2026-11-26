# Temporary-directory retention follows the owning Jupiter test’s outcome

The successful Jupiter owner’s temporary directory disappeared even after a sibling failed. Reversing their order left only the failed owner’s marker after launcher completion.

An independently successful owner’s cleanup policy does not depend on whether a sibling has already failed. Files.exists is an observation outside the test engine.

The intermediate commit f7f1d51d4c57 changed only release notes. Its junit-jupiter-engine/src/main tree (bf0e7ee77cdfc878a8075699153823292105238e) is identical to the parent’s. The second commit changed that production tree.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `1/1,failed=F,passed=P` | `1/1,failed=F,passed=absent` | matched |
| Control | `0/1,passed=absent` | `0/1,passed=absent` | matched |
| Challenge | `1/1,failed=F,passed=P / 1/1,failed=F,passed=absent` | `1/1,failed=F,passed=absent / 1/1,failed=F,passed=absent` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 587`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/junit-team/junit-framework/pull/4466)
