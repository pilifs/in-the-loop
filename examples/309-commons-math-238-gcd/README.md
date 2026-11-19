# Apache Commons Math MATH-238

The parent of Apache’s repair used an int product to test whether either input was zero. The packet compiles each complete upstream MathUtils.java using JDK 21. The powers claim admits exactly 441 independently chosen pairs of powers of two up to 2²⁰. The zero claim admits (0, n) for n from 0 through 255. [Apache repair](https://github.com/apache/commons-math/commit/dabf3a5beb9ab697d570154b9961078a8586c787)

| Independent JVM check | Parent | Fix |
|---|---:|---:|
| Power-family discrepancies | 45 / 441 | 0 / 441 |
| Zero-family discrepancies | 0 / 256 | 0 / 256 |
| gcd(65536, 65536) | 131072 | 65536 |
| Apache regression case | 3440640 | 98304 |

The property computes the expected GCD as the smaller admitted operand. The finite oracle computes it from the smaller exponent. The public history establishes the repair boundary. The introduction is unknown.
