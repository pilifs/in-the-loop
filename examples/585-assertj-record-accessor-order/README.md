# Recursive comparison reads a record’s named component before its boolean alias

Recursive comparison detected different record components sharing a boolean alias. A constant JavaBeans getter still caused different stored strings to compare equal.

The landed source tries getField() before the bare accessor. Both objects return the same constant. The generated component accessor provides an independent reference.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `equal=true,unequal=false` | `equal=false,unequal=true` | matched |
| Control | `equal=true` | `equal=true` | matched |
| Challenge | `field=one/two,getter=fixed/fixed,equal=true` | `field=one/two,getter=fixed/fixed,equal=true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 585`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/assertj/assertj/pull/3710)
