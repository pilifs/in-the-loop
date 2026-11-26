# An interrupted stream read preserves bytes already copied

An interrupted empty read now throws with the interrupt flag set and cancels the source. A bulk read preserved three bytes at offset one before the next read threw.

The controlled publisher stays open. A bounded reader observes the parent's continued wait, then sends completion and joins it. No competing byte is emitted.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · await | `waiting for upstream` | `InterruptedIOException flag=true cancelled=true` | matched |
| Control · normal | `255,-1` | `255,-1` | matched |
| Challenge · partial | `waiting for upstream` | `3:.ABC... InterruptedIOException flag=true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 492` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37159)
