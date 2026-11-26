# A programmatic fallback participates in single-bean selection

A programmatically registered fallback now loses single-bean selection to the regular bean. The provider stream retained both singleton identities in either registration order.

The same programmatic overload with Primary selected the reserve bean on both revisions.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · fallback | `NoUniqueBeanDefinitionException` | `regular` | matched |
| Control · primary | `reserve` | `reserve` | matched |
| Challenge · stream | `both=true single=NoUniqueBeanDefinitionException / both=true single=NoUniqueBeanDefinitionException` | `both=true single=regular / both=true single=regular` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 498` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/33533)
