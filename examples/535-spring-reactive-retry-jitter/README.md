# Bound jitter on a reactive retry without changing attempt counts

Reactive retry now tolerates jitter larger than its five-millisecond delay and recovers on subscription two. A 107000-day jitter still overflowed during adaptation before the target publisher had any subscription.

The large and small jitter inputs were both exercised with an immediately successful cold target. No long backoff was needed.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · oversized | `IllegalArgumentException:0` | `ok:2` | matched |
| Control · small | `ok:1` | `ok:1` | matched |
| Challenge · duration | `IllegalArgumentException:0/IllegalArgumentException:0` | `ok:1/ArithmeticException:0` | refuted |

With the prepared campaign cache, run `python3 examples/tools/build.py 535` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/35140)
