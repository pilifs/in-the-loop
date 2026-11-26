# Assert servlet redirect and forward destinations with Ant patterns

The new MockMvc matchers accepted the intended redirect and forward. A single star rejected the extra path segment and a double star accepted it.

A separate exact forward assertion retained its literal question mark. The caller checked the actual dispatched destination before applying each matcher.

Each pin supplies its changed production classes on spring-test-4.0.0.M3-q19. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · factories | `absent` | `pass/pass/reject` | matched |
| Control · exact | `/api/resource/1?arg=value:pass/reject` | `/api/resource/1?arg=value:pass/reject` | matched |
| Challenge · segments | `absent` | `pass/reject/pass` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 526` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/374)
