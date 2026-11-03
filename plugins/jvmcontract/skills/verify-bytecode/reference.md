# jvmcontract, for the agent running it

The full documentation is the crate's [README](https://github.com/pilifs/in-the-loop/blob/main/lib/README.md). This is what you need while verifying a pull request.

## Targets

`pkg.Class#method`. An overloaded method is named with its parameter types in Java's spelling, simple or qualified, `pkg.Class#pow(int, int)`, `pkg.Codec#encode(byte[], int)`; without them the tool refuses and lists the overloads (`expected one method named pow, found 5: pow(int, int), pow(long, int), ...; name one as pow(int, int)`). A nested class is `pkg.Outer$Inner#method`. `javap -p -cp CLASSES pkg.Class` lists the methods with their parameter types.

## Commands

Exit code 0 is verified, 1 is a violation or an unverifiable target, 2 is a usage or I/O error. `--json` prints the outcome as data (`verdict` is `"Verified"`, `"Violation"` or `"Unverifiable"`, with `counterexample`, `proof`, `problem`, `findings`, `work`).

```bash
# Regression proof: new bytecode == old bytecode on every input, or the input where they differ.
jvmcontract equivalence --before BASE_CLASSES --after HEAD_CLASSES --target T \
    [--unchanged-unless 'EXPR'] [--classpath 'a.jar:b.jar'] [--max-array-length 8] [--unwind 16] \
    [--timeout 600] [--work DIR] [--report DIR] [--no-shrink] [--json]

# Property proof: the method satisfies a statement on every input, or the input where it does not.
jvmcontract prove T --classes HEAD_CLASSES [--assume 'EXPR'] [--assert 'EXPR'] [--throws 'CLASS when EXPR']... \
    [--classpath ...] [--max-array-length 8] [--unwind 16] [--timeout 600] [--engine jbmc|native|auto] [--work DIR] [--report DIR] [--json]

# Behavioural contract: every input of a finite domain, executed in the interpreter; prints the table. No JBMC.
jvmcontract derive T --classes CLASSES [--classpath ...] [--json]

# What a module's bytecode can reach, and its public surface. No JBMC. Diff the two versions' outputs.
jvmcontract capabilities CLASSES [--module NAME] [--json]
jvmcontract capabilities --each lib/*.jar          # one contract per jar, for a dependency change
jvmcontract api CLASSES [--module NAME]
# A Spring Boot module's boundaries: routes, listeners, schedules, bean definitions, the advice on each bean, `!`
# lines where an annotation does not do what it says (self-invocation, advice the proxy cannot intercept, a checked
# exception that commits, a lost @Async result, constraints never enforced); what enables each kind of annotation (an
# @Enable annotation on a configuration in scope, an auto-configuration whose conditions hold, a Bean Validation
# provider on the class path), with a `!` line for a family nothing enables; the configuration keys (what the classes
# read, what application.yaml under --resources sets, what the dependencies' metadata on --classpath declares), with
# `!` lines for a key nothing binds, a deprecated key, a value of the wrong type; the wire types: the JSON shape
# of each request, response and message as Jackson encodes it, with `!` lines for a subtype missing from
# @JsonSubTypes, a type id that is a class name, a polymorphic type without @JsonTypeInfo, and for the Bean
# Validation constraints: a nested type's constraints no @Valid leads into, a body taken without @Valid, a group a
# @Valid or @Validated leaves out, a constraint on a type its validator cannot handle; and the stored types: the
# shape of each Spring Data MongoDB document under its stored names, with `!` lines for a query, update, index, sort,
# projection or @Query string that names a field the document does not have. No JBMC.
jvmcontract boundaries CLASSES [--classpath JARS] [--resources DIR] [--module NAME] [--json]

# A class file's structure and bytecode, when you need to see what a method does at the bytecode level.
jvmcontract inspect path/to/Class.class [--code]
```

`--report DIR` writes SARIF (`equivalence.sarif`, `property.sarif`) if the user wants it for code scanning. `--work DIR` keeps the harness, the relocated classes, the statement as Java source and JBMC's logs; use one directory per proof under the pull request's working directory, so everything is reproducible.

Each JBMC run is limited to 3 GiB of address space (`JVMCONTRACT_JBMC_MEMORY_MB`, 0 for no limit) and dies as *unverifiable* beyond it. A run counts as proved only if JBMC itself ends with `VERIFICATION SUCCESSFUL`: a solver that gives up prints `** 0 of N failed` too, and that is no proof.

## What each proof needs

| Proof | Method | Parameters | Needs |
|---|---|---|---|
| `equivalence`, `prove` | `static` | primitives, and arrays of `int`, `long`, `short`, `byte`, `char`, `boolean` (never `null`, every length up to `--max-array-length`); `float`/`double` scalars are fine, `double[]` is not | `jbmc`; a JDK (the tool reads `java.lang.Math`, `StrictMath`, `Integer`, `Long`, `Short`, `Byte` and declared exception classes from the JDK image) |
| `derive` | static, or an instance method of an enum, record or sealed type | enums, booleans, records and sealed interfaces of those (each reference parameter also takes `null`); must be pure | nothing |
| `capabilities`, `api`, `boundaries` | a module | | nothing (`boundaries` reads the class path and the JDK image for the exception hierarchy) |

Refusals you will see, and what they mean:

- `only static methods are supported`: an instance method. Not provable by `equivalence`/`prove`; if its receiver and parameters are finite, `derive` covers it.
- `parameter X has type Y; the symbolic verifier handles primitive parameters and arrays of integral or boolean elements`: a `String`, object or `double[]` parameter. Not provable per method; report as not covered.
- `input domain is not finite` (from `derive`): an `int`, `long`, `String`, ... parameter. If static and primitive, use `equivalence`/`prove` instead.
- `... is not known to be pure` / `writes static field` / `open to implementations outside the analysed code`: `derive` cannot prove purity; the method's behaviour depends on more than its arguments.
- `cannot be verified: ... both versions agree on it` (equivalence) or a property witness on which the replay finds the property holding: JBMC had no bytecode for a method the target calls (a native method such as `Float.floatToRawIntBits`, a class missing from `--classpath`, or a JDK class it has no model of) and treated its result as arbitrary. Add the classpath entry, or report a tool limit. The tool ships models of a few JDK classes JBMC lacks (the boxing caches, `Character.digit`, `java.nio.charset`; `jvmcontract models` lists them) and puts them on JBMC's class path by itself; a violation in a class whose static initializer reads another JDK class is an artifact until that class has a model too (`lib/models/README.md` says how to add one).
- `--engine auto` tries the tool's own checker first (methods over integers, no arrays or floating point) and hands anything else to JBMC with a `note:` line; it needs no JBMC for what it handles. The default is still JBMC.
- JBMC timed out or was killed: the domain is too hard (64-bit division or multiplication on both sides, long loops, large arrays). Retry with smaller bounds and report the bounds as what was proved, or report it as not finished. Lower `--unwind` along with `--max-array-length`, or the smaller arrays save little: start at the array length plus 2, which is `--max-array-length 4 --unwind 6`, and the tool says so if a loop needs more. On one array method, 4 and 6 was proved in 275 s and 664 MB, while 4 and 8 had not finished at 170 s and 4 and 16 ran out of memory.

## The expression language

Java boolean expressions over the parameters by name (`javap -p` shows the names when the class was compiled with `-parameters`; else they are `p0, p1, ...`; the tool's `domain` line shows what it uses). Java's operators and precedence, integer literals with `L` and hex (no character literals: write `'0'` as `48` or `0x30`), casts `(long) x`, the conditional `? :`, `&&`, `||`, `!`. No method calls other than the method under proof itself. No `Integer.MAX_VALUE`: write `2147483647`, `-2147483648`, `9223372036854775807L`.

- `result` (in `--assert` only): the method's return value. A `result` that is an array is read element by element: `result.length`, `result[i]`.
- A call of the method under proof, `delayMillis(attempt - 1, baseMillis, capMillis)`, `merge(b, a)`, `offsetOf(offsetDelta, k - 1)`: how laws are stated (commutativity `result == f(b, a)`, idempotence `result == f(result)`, monotonicity `result >= f(n - 1)`, antisymmetry `result == 1 - winner(tsB, nodeB, tsA, nodeA)`).
- Arrays: `a.length`, `a[i]`, and JML's quantifiers with a range that bounds the variable below and above: `(\forall int i; 0 <= i && i < a.length; a[i] >= 0)`, `(\exists int i; 0 <= i && i < a.length; a[i] == key)`, `(\sum int i; 0 <= i && i <= k; a[i])`, `(\num_of int i; ...; a[i] == 0)`, `(\max int i; ...; a[i])`, `(\min ...)`. An array parameter is read *after* the call; `\old(a[i])` is its value before the call (a frame condition: `(\forall int i; n <= i && i < out.length; out[i] == \old(out[i]))`).
- `--throws 'java.lang.IllegalArgumentException when e < 0'` (repeatable): the method throws exactly that exception (or a subclass) on exactly the inputs where the condition holds, and returns normally with the assertion holding elsewhere. Clauses are matched in order like `catch`: a subclass before its superclass. Use the fully qualified class name.
- `--assume`: the inputs the property is about. Everything outside is not checked. Too weak an assumption gives a violation that is the assumption's fault, not the code's.
- A boolean method with no `--assert` is its own property: it must return `true`.

Turning Javadoc into a property:

| Javadoc | Flag |
|---|---|
| `@param e Exponent (must be positive or zero)` | `--assume 'e >= 0'` |
| `@throws IllegalArgumentException if e < 0` | `--throws 'java.lang.IllegalArgumentException when e < 0'` |
| `@throws ArithmeticException if the result overflows` | Not a condition over the inputs; leave it to a regression proof, or assume inputs that cannot overflow |
| `@return the non-negative remainder` | `--assert 'result >= 0'` |
| `@return k^e` with a recurrence in mind | `--assume 'e >= 1 && ...' --assert 'result == k * pow(k, e - 1)'` |
| "idempotent" / "commutative" / "never decreases" | `result == f(result)` / `result == f(b, a)` / `result >= f(n - 1)` |
| "the change only affects groups of eight or more" (pull request text) | `equivalence ... --unchanged-unless 'seats >= 8'` |

## Reading the output

Text output starts the verdict line with `✓` (verified), `✗` (violation, or `cannot be verified: <reason>` for unverifiable) and shows: the `domain` (the parameters and their types, with array bounds), the proof stages JBMC ran (small inputs first, then the full domain), and for a violation the witness as Java would write it, `pow(k=-2, e=31)`, with what each version did (`before: threw java.lang.ArithmeticException: integer overflow; after: -2147483648`) and, for arrays, what each left in them. The witness is shrunk towards zero and shorter arrays, so it is the smallest the tool found and is stable between runs; JBMC's original input is printed beside it. The statement that was proved is written as Java source into the work directory (`statement` in the JSON) for the report.

## Costs, so you can budget

Measured on Apache Commons Numbers' `ArithmeticUtils.pow(int, int)` (a square-and-multiply loop with `Math.multiplyExact`): the regression proof found the differing input in 185 s; the Javadoc property proved in 1.4 s; a property under a narrow assumption (`k == -2 && e == 31`) proved in 1.0 s and was refuted on the old version in 0.7 s; the full-domain proof of the confined change (`--unchanged-unless 'k == -2 && e == 31'`) did not finish in 300 s and was verified in 1083 s with `--timeout 1500`. Budget full-domain proofs over multiplication loops in tens of minutes, and run them in the background. Measured in this repository's examples: a behavioural contract of 36 cases derives in about 15 ms. Properties over `int`/`long` arithmetic prove in seconds; five properties of a replication kernel in four seconds, sixteen of a JVM's decision kernels in a minute and a half. Equivalence of two 64-bit multiplications with `Math.multiplyExact` takes about ten seconds; a 64-bit division on both sides can exhaust the solver. Arrays: binary search over sorted `int[]` up to 8 elements in seconds; a regression proof over arrays costs about twice a property proof; two UTF-8 encoders ran out of memory at the defaults (8, 16) but proved equal in 94 s at `--max-array-length 3 --unwind 6`. A quantifier that repeats a linear scan, eight writes at symbolic positions followed by a quantifier, or a method that allocates `new byte[n]` with `n` from the data, do not finish. Loops that the unwinding bound does not cover are reported as unverifiable, not assumed away.
