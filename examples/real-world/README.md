# Real-world examples

[← Examples](../README.md)

Pull requests to published Java libraries, verified from their compiled bytecode with the [`/verify-bytecode`](../../plugins/jvmcontract/README.md) skill. Nothing here is constructed: the pull request, the commit it left its base at and its head are the library's own, and the proofs ran over the classes the library's build produces. Each folder is one pull request, and holds the report as the skill writes it ([the template](../../plugins/jvmcontract/skills/verify-bytecode/report-template.md)): the verdict per changed method, each finding with its witness and the command that produced it, what no proof reached and why, and how it was produced. The [demo examples](../demo/README.md) show what each verification approach does on code arranged for it; these show what the same verifiers do on code nobody here wrote.

| # | Library | Pull request | Verified | What the proofs said |
|---|---|---|---|---|
| 001 | [Apache Commons Numbers](https://github.com/apache/commons-numbers) | [#223](https://github.com/apache/commons-numbers/pull/223), `ArithmeticUtils.pow` accepts `(-2)^31` | [commons-numbers-223](commons-numbers-223/README.md) | The one input the fix is about, `pow(-2, 31)`, found from the bytecode alone in 185 s; the Javadoc proved on the new version; the change proved confined to that input on all 2^64 others in 18 minutes |

## Libraries to try next

Good subjects have small Maven or Gradle builds, an active pull request flow, and static utility methods over primitives and primitive arrays, which is where the regression and property proofs land. Five popular ones, with the classes to look for:

| Library | Build | Where the proofs land | Try |
|---|---|---|---|
| [Apache Commons Numbers](https://github.com/apache/commons-numbers) | Maven, multi-module | `ArithmeticUtils` (`gcd`, `lcm`, `pow`, `isPowerOfTwo`, `remainderUnsigned`, `divideUnsigned`), `Precision`, `DD` | [#223](commons-numbers-223/README.md), the `pow` fix: regression proof, confined change, and the Javadoc proved. Next: `pow(long, int)`, which the same pull request changed and the recorded run did not reach |
| [Joda-Time](https://github.com/JodaOrg/joda-time) | Maven, one module | `org.joda.time.field.FieldUtils` (`safeAdd`, `safeSubtract`, `safeMultiply`, `safeNegate`, `safeToInt`, `safeMultiplyToInt`), with `@throws ArithmeticException` in every Javadoc | any pull request touching `FieldUtils`; or `--only org.joda.time.field.FieldUtils#safeMultiply(long, int)` on a recent one, to see the overflow contract proved |
| [Apache Commons Codec](https://github.com/apache/commons-codec) | Maven, one module | `Hex` (`encodeHex(byte[])`, `decodeHex(char[])`), `BaseNCodec` helpers, `PureJavaCrc32`, `MurmurHash3` (`hash32x86(byte[], int, int, int)`) | pull requests to `binary/` and `digest/`: regression proofs over `byte[]` and `char[]`, bounded in length |
| [jackson-core](https://github.com/FasterXML/jackson-core) | Maven, one module | `com.fasterxml.jackson.core.io.NumberOutput` (`outputInt(int, char[], int)`, `outputLong`, `divBy1000`), `NumberInput`, `CharTypes` | pull requests to `io/`: the number formatters are static, over `int`, `long` and `char[]` |
| [Apache Commons Lang](https://github.com/apache/commons-lang) | Maven, one module | `ArrayUtils` over primitive arrays (`indexOf(int[], int)`, `reverse(int[])`, `isSorted(int[])`), `BooleanUtils` (`toBoolean(int)`, `and(boolean...)`), `CharUtils`, `NumberUtils.compare` | the primitive-array methods: regression proofs that compare what each version leaves in the array |

What does not work well: `String`-heavy libraries (jsoup, Commons Text), anything whose build takes longer than the proofs (Guava, Netty), and methods whose only parameters are objects. The limits are the tool's, in the [library README](../../lib/README.md#limits); the skill's [reference](../../plugins/jvmcontract/skills/verify-bytecode/reference.md#costs-so-you-can-budget) has the measured costs to budget by.

## Recording an example

1. Run `/verify-bytecode <pull request>` (or `/jvmcontract:verify-bytecode`, from the plugin). It leaves `report.md` and every harness, statement and JBMC log in its working directory, and does not write to the pull request unless asked with `--post`.
2. Copy the report to `real-world/<library>-<N>/README.md`. Keep every number tied to the run: the witness, the verdict lines and the times as the tool printed them, and the exact commands, so the proofs can be rerun. Say what the run did not reach, including what the environment prevented (a build that could not run, a proof that did not finish in its budget), and say so where a proof was made on a file compiled alone rather than by the library's build.
3. Link the library's source rather than copying it; quote the lines the witness is about, with their license's attribution, if the report needs them.
4. Add a row to the table above, and move the library's row in the list below it if it was there.

Only `VERIFICATION SUCCESSFUL` in JBMC's log is a proof; a run that stopped at its timeout or ran out of memory is reported as unverifiable, never as a pass.
