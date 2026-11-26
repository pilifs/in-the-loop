# Plain and qualified injection of scoped service proxies

The unqualified consumer now invokes D(L,C) through scoped proxies. An added archive delegate remains reachable by qualifier without changing that route.

The unproxied control used the same candidacy flags. Each result comes from invoking the injected services.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · proxied | `NoUniqueBeanDefinitionException` | `D(L,C)` | matched |
| Control · plain | `D(L,C)` | `D(L,C)` | matched |
| Challenge · extra | `NoUniqueBeanDefinitionException` | `D(L,C) / A` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 499` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/35627)
