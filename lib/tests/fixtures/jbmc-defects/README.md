# Where JBMC 6.11.0 lets a runtime exception past its handler

Step 3 of `llm-dlc/loops/engine-priorities.md`: why JBMC's counterexamples to `conformance/caught/1` and
`conformance/nestedHandler/1` (`n=0`) do not reproduce in the interpreter. Found on cvm (x86_64) with JBMC 6.11.0
(`cbmc-6.11.0`), the options every run passes (`--throw-runtime-exceptions`, `--no-refine-strings`, CaDiCaL), and
JDK 25.0.5. It is not the models, nor reading the trace: JBMC's trace says what JBMC computed, and it is not what the JVM
does. There are two causes, and each also gave a false proof (below).

`p/D.java` is the fixture of `jbmc_gaps`'s tests (`the_preflight_names_where_jbmc_raises_an_exception_past_its_handler`),
one method per shape:

| Method | Shape | JBMC 6.11.0 | Preflight |
|---|---|---|---|
| `returned` | `try { return 10 / n; } catch (ArithmeticException e)` | the exception escapes the method | `return-past-handler` |
| `field` | `try { return d.v; } catch (NullPointerException e)` | the exception escapes the method | `return-past-handler` |
| `stored` | `try { int r = 10 / n; return r; } catch (ArithmeticException e)` | caught, as on the JVM | — |
| `uncaught` | `try { return a[i]; } catch (ArithmeticException e)` | escapes, as on the JVM | — |
| `called` | `try { return Math.abs(10 / n); } catch (ArithmeticException e)` | caught, as on the JVM | — |
| `superCatch` | `try { int r = 10 / n; return r; } catch (RuntimeException e)` | the exception escapes the handler | `stubbed-handler` |
| `thrown` | `throw new IllegalArgumentException()` caught as `RuntimeException` | the exception escapes the handler | `stubbed-handler` |
| `exact` | `throw new IllegalStateException()` caught as itself | caught, as on the JVM | — |

`conformance/caught/1` is the first shape, the first cause. `nestedHandler/1` has both: its `IllegalArgumentException` escapes
the `catch (RuntimeException e)`, and its `return 100 / n` the inner `catch (ArithmeticException x)`.

## Cause 1: JBMC computes a returned value after the try block has ended (a JBMC defect)

javac ends an exception handler's range before a `return` instruction. For `return 10 / n;` in a try block:

```
0: bipush 10
2: iload_0
3: idiv
4: ireturn
5: astore_1 ...
Exception table: from 0 to 4 target 5 type java/lang/ArithmeticException
```

JBMC turns the operand stack into expressions and emits a statement only where a value is consumed. `idiv` at 3 becomes
the expression `10 / n`, consumed by `ireturn` at 4, which is outside the range. `--show-symbol-table` shows
`push_catch` at `pc0`, `pop_catch` at `pc2`, and then, at `pc4`, the statement with the check that
`--throw-runtime-exceptions` adds:

```
pc4: if (n == 0) { new_exception = new java.lang.ArithmeticException; throw(new_exception); }
     return 10 / n;
```

So the exception is thrown after the handler has been popped, and it escapes the method. The same goes for any check JBMC
attaches to an expression: integer division and remainder (`int` and `long`), an array element (bounds and null), a field
(null), an array's length (null), and probably a cast. A value stored in a local first (`int r = 10 / n; return r;`), passed
to a call, or compared in a branch is computed inside the range, and is caught. A `finally` stores the value first and is
not affected.

The tool's preflight (`lib/src/jbmc_gaps.rs`, `Defect`) finds this shape in the bytecode JBMC runs and names it as
`return-past-handler`. A JBMC proof that reaches one is refused under every `--gaps` mode. A counterexample is still
replayed, and when it doesn't reproduce, the message names the defect.

## Cause 2: JBMC's stub of a JDK exception class has no superclass (this repository's class path)

JBMC 6 embeds no model of the class library. Every JDK class the tool gives it no class file of is a stub, and a stub has no
superclass. So `catch (RuntimeException e)` matches only `RuntimeException` itself: an `ArithmeticException` from a division,
or an `IllegalArgumentException` thrown, escapes it. With the real class files of `Throwable`, `Exception`,
`RuntimeException` and `ArithmeticException` on the class path, JBMC catches the division's exception. The real
`Throwable` brings its native `fillInStackTrace` with it, which JBMC has no body for, so the real classes are no fix either.

The fix is in this repository: models of the exception classes with their superclasses, in `lib/models` (the native
stream's, so recorded for the reconcile loop). Until then, the preflight names the shape as `stubbed-handler`: a handler
of a class JBMC has no class file of, and an exception the program may raise whose class extends it on the JVM but not in
JBMC. A proof that reaches one is refused as above.

## The false proofs

Both causes made JBMC prove what the JVM refutes, under `--gaps strict` and the default `--engine jbmc`. The corpus now
holds both, as `conformance/caught/3` and `conformance/caughtAsRuntime/2`:

- `prove conformance.Conformance#caught --assert 'result == 10 / n' --throws 'java.lang.ArithmeticException when n == 0'`
  was ✓ verified, but on the JVM `caught(0)` returns -1;
- the same claim on `caughtAsRuntime`, the shape of `superCatch`.

The own checker gives a violation on both. With the preflight, JBMC's proof of either is refused.

## Draft report for CBMC/JBMC (not filed: for the user to decide)

> **JBMC: a runtime exception from an expression consumed after the end of a try range escapes the handler (`return a / b`)**
>
> JBMC 6.11.0 (cbmc-6.11.0), Linux x86_64, `--throw-runtime-exceptions`. Classes compiled by javac 25.
>
> ```java
> public class E {
>     static int a(int n) { try { return 10 / n; } catch (ArithmeticException e) { return -1; } }
>     static int b(int n) { try { int r = 10 / n; return r; } catch (ArithmeticException e) { return -1; } }
>     public static void ca(int n) { int r = a(n); assert n != 0 || r == -1; }
>     public static void cb(int n) { int r = b(n); assert n != 0 || r == -1; }
> }
> ```
>
> `jbmc E --function E.ca --throw-runtime-exceptions` reports `no uncaught exception: FAILURE` with `n = 0`, where the JVM
> returns -1 from `a(0)`. `E.cb`, which differs only in storing the quotient in a local, is `VERIFICATION SUCCESSFUL`.
>
> javac's exception table for `a` is `from 0 to 4 target 5`, which leaves out the `ireturn` at 4. In
> `--show-symbol-table`, the method's body has `push_catch` at `pc0` and `pop_catch` at `pc2`. The division, with the
> `ArithmeticException` check that `--throw-runtime-exceptions` instruments, is emitted at `pc4` as part of `return 10 / n`,
> after the `pop_catch`, so the exception is not caught by the method's own handler. The same happens with `irem`, `ldiv`,
> `lrem`, `iaload` (`return a[i]`, `ArrayIndexOutOfBoundsException`), `getfield` (`return o.f`, `NullPointerException`)
> and `arraylength`.
>
> The value of `idiv` stays on the converted operand stack until the instruction that consumes it, past the end of the
> range. Saving the operand stack to temporaries at the end of a try range, as is done at jump targets, or emitting the
> instrumented check at the address of the instruction that raises it, would keep the exception within the range's
> handler.
