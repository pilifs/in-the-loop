# Recover the nested return type inherited through a generic interface

Resolving the interface type now recovers Collection<Optional<String>>. Sibling subclasses preserve distinct Long and String leaves without overrides.

The caller also checks equality with the non-bridge override's reflective Type. The parent returned only the raw Collection.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · override | `Collection equal=false` | `Collection<Optional<String>> equal=true` | matched |
| Control · direct | `String` | `String` | matched |
| Challenge · siblings | `Collection / Collection` | `Collection<Optional<Long>> / Collection<Optional<String>>` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 480` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36480)
