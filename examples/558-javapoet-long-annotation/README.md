# Reflected long annotation members compile in generated Java

The generated long annotation compiled and reflected back as 12345678910. Reflection on a compiled long array also preserved the negative out-of-int-range element and its position.

Reflecting on the compiled consumer checks the literal type, element order and sign independently of source formatting.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `false/false/-` | `true/true/12345678910` | matched |
| Control | `true/7` | `true/7` | matched |
| Challenge | `false/-` | `true/[7, -2147483649]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 558`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/square/javapoet/pull/994)
