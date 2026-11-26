# Check the named bean's generic type before returning it

Named generic lookup now rejects the count bean as Box<String> in Java and Kotlin. Both languages report the bean name, raw and generic requirement, and actual class, and both retrieve the same Box<Number> singleton.

The Kotlin client was compiled against each revision because the extension is inline. The parent Kotlin binary accepted the mismatched count singleton.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · java | `absent` | `text/count:Box:true:CountBox` | matched |
| Control · raw | `count/text/NoSuchBeanDefinitionException` | `count/text/NoSuchBeanDefinitionException` | matched |
| Challenge · kotlin | `kotlin=count` | `java=count:Box:true:CountBox kotlin=count:Box:true:CountBox success=true/true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 512` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/35808)
