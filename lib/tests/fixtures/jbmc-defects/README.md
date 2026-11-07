# Where JBMC 6.11.0 runs bytecode otherwise than the JVM

Step 3 of `llm-dlc/loops/engine-priorities.md`: why JBMC's counterexamples to `conformance/caught/1` and
`conformance/nestedHandler/1` (`n=0`) do not reproduce in the interpreter. Found on cvm (x86_64) with JBMC 6.11.0
(`cbmc-6.11.0`), the options every run passes (`--throw-runtime-exceptions`, `--no-refine-strings`, CaDiCaL), and
JDK 25.0.5. It is not the models, nor reading the trace: JBMC's trace says what JBMC computed, and it is not what the JVM
does. There are two causes, and each also gave a false proof (below). A third, found while reading step 2b's benchmark
job (`20261106-201041`), is [JBMC's right shifts](#cause-3-jbmc-right-shifts-by-the-whole-distance-a-jbmc-defect):
`conformance/shiftRight/2`'s counterexample under the `full-range` and `tight` staging policies did not reproduce.
A fourth, found by the Phase 5 job `20261106-203501` (`conformance/declaring/2`, a false proof), is
[the initializers JBMC runs](#cause-4-jbmc-runs-initializers-the-jvm-does-not-a-jbmc-defect).

`p/D.java` is the fixture of `jbmc_gaps`'s tests (`the_preflight_names_where_jbmc_runs_the_bytecode_otherwise_than_the_jvm`),
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
| `shifted` | `x >> s` | shifts by the whole `s` | `unmasked-shift` |
| `shiftedUnsigned` | `x >>> s` on a `long` | shifts by the whole `s` | `unmasked-shift` |
| `literal` | `x >> 33` | shifts by 33: `0` or `-1` | `unmasked-shift` |
| `masked` | `x >>> (s & 31)` | as the JVM | — |
| `halved` | `x >> 1` | as the JVM | — |
| `left` | `x << s` | masks the distance, as the JVM | — |
| `declaring` | `Sub.value`, a field `Holder` declares | initializes `Sub` | `extra-initializer` |
| `assigned` | `Sub.value = n` | initializes `Sub` | `extra-initializer` |
| `inherited` | `Sub.get()`, a method `Holder` declares | initializes `Sub` (and stubs `Sub.get`) | `extra-initializer` |
| `direct` | `Holder.value` | initializes `Holder`, as the JVM | — |
| `defaults` | `Hello.value(n)`, `Hello implements Bare, Greeter` | initializes `Bare` and `Greeter` | `extra-initializer` |
| `created` | `new Sub()` | initializes `Holder`, then `Sub`, as the JVM | — |

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

## Cause 3: JBMC right-shifts by the whole distance (a JBMC defect)

The JVM shifts an `int` by the low five bits of the distance and a `long` by the low six (JVMS `ishr`, `iushr`, `lshr`,
`lushr`), so `x >> 33` is `x >> 1` and `x >> -1` is `x >> 31`. JBMC 6.11.0 masks the left shifts but not the right
ones. In `--show-goto-functions`:

```
x << s    ASSIGN ...#return_value := shl(x, bitand(s, 31))
x >> s    ASSIGN ...#return_value := ashr(x, s)
```

`ashr` and `lshr` by 32 or more, or by a negative distance read as unsigned, fill the value with its sign or with zeros.
`x >> -1` happens to agree (`x >> 31` is the sign fill). Everything else outside `0..31` (`0..63` for a `long`)
differs. Checked with `jvmcontract prove --engine jbmc` under both staging policies, against the own checker and the JVM:

- `x >> s` where `s == 33`, asserting `result == 0 || result == -1`: JBMC ✓ **verified**, while the JVM gives
  `shiftRight(4, 33) == 2`. The own checker gives a violation. That is a false proof under strict, now
  `conformance/shiftRight/3`.
- `x >>> s` where `s == 32`, asserting `result == 0`: JBMC ✓ verified, while the JVM gives `x`. Now
  `conformance/shiftUnsigned/3`.
- `result == x >> 1` for `x >> s` where `s == 33`, which holds: JBMC's counterexample (`x = -2147483648` over the full
  range, `x = 2` under staged) does not reproduce. `conformance/shiftRight/2` (`result == x / 2`) is refuted on the JVM
  by `x = -1` as well, which the staged search finds first and which reproduces. The full range found
  `x = -2147483648`, where `x >> 1 == x / 2` on the JVM but not in JBMC, and that witness did not reproduce. That is the
  one case whose class differed between the staging policies in job `-201041`.
- `x >> 33` with the literal 33 (javac does not reduce it), `x >>> 32`, and `long` shifts by 64 or 65 disagree the
  same way. `x << 32`, `x << 64` on a `long`, and `x >> (s & 31)` agree with the JVM.

The preflight names a right shift by a distance not known to be within the width as `unmasked-shift`. That is any
distance but a constant in `0..31` (`0..63`), or a bitwise and with such a constant, computed by instructions no
branch joins. A proof that reaches one is refused under every `--gaps` mode. The rule is broad: a proof that keeps the
distance in range by an assumption (`conformance/shiftRight/1`, `x == -1`) is refused too, and `--engine auto` lets the
own checker prove it.

## Cause 4: JBMC runs initializers the JVM does not (a JBMC defect)

JVMS §5.5 initializes, at a `getstatic`, `putstatic` or `invokestatic`, the class that *declares* the resolved field or
method, and, when it initializes a class, first its superclass and those of its superinterfaces that declare a default
method (a non-abstract, non-static method). JBMC 6.11.0 does otherwise in two ways, both read from
`--show-goto-functions` (the listing alone, nothing solved) on `p/D.java` and on `conformance.Conformance`:

- It initializes the class the instruction *names*. For `Sub.value`, where `Sub extends Holder` and `Holder` declares
  `value`, javac emits `getstatic Sub.value`, and JBMC calls `Sub.<clinit_wrapper>` there, which runs `Holder.<clinit>`
  and then `Sub.<clinit>`. The JVM runs `Holder.<clinit>` alone. The same goes for `putstatic` and for
  `invokestatic Sub.get()` of a static method `Holder` declares (where JBMC also gives `Sub.get` a stub, a
  `missing-body` gap the preflight already names).
- A class's `<clinit_wrapper>` calls the wrapper of every direct superinterface, so JBMC initializes an interface
  with no default method that the JVM leaves alone. `Hello implements Bare, Greeter`, where only `Greeter` declares a
  default method: `Hello.value(n)` runs `Bare`'s initializer in JBMC and not on the JVM.

Each gave a **false proof under strict** on `--engine jbmc`: `conformance/declaring/2` (`result == n + 107`, where
`declaring(3)` returns 10 on the JVM: `Sub`'s initializer marks the trace in JBMC alone) was verified by JBMC in
job `-203501`, and `defaults(n)` returns 43 in JBMC where the JVM returns 3, which is why JBMC's counterexample to
`defaults/1` (`result == 3`) did not reproduce. `defaults/3` (`result == 43`) is in the corpus now, as the shape's
false proof. The own checker runs the initializers as the JVM does (`bmc::gaps::initializers`) and refutes both.

The preflight names an instruction at which JBMC's goto program calls a wrapper that runs the `<clinit>` of an
application class the JVM does not initialize there as `extra-initializer`, comparing the wrappers' calls with
`bmc::gaps::initializers` of the declaring class. A proof that reaches one is refused under every `--gaps` mode. Only
initializers JBMC runs and the JVM does not are named: an instruction whose wrapper call JBMC put elsewhere is not one.

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

## Draft report for CBMC/JBMC, cause 3 (not filed: for the user to decide)

> **JBMC: `ishr`, `iushr`, `lshr` and `lushr` do not mask the shift distance (`x >> 33` is not `x >> 1`)**
>
> JBMC 6.11.0 (cbmc-6.11.0), Linux x86_64. Classes compiled by javac 25.
>
> ```java
> public class S {
>     public static void r(int x) { assert (x >> 33) == (x >> 1); }
>     public static void u(int x) { assert (x >>> 32) == x; }
>     public static void l(int x) { assert (x << 33) == (x << 1); }
> }
> ```
>
> On the JVM all three assertions hold for every `x`: JVMS §6.5 says `ishr` and `iushr` use the low 5 bits of the
> distance (`lshr` and `lushr` the low 6). `jbmc S --function S.r` fails (for example with `x = 2`), as does `S.u`
> (`x = 1`). `S.l` is `VERIFICATION SUCCESSFUL`. In `--show-goto-functions` the left shift is
> `shl(x, bitand(s, 31))`, but the right shift of `x >> s` is `ashr(x, s)` and of `x >>> s` is `lshr(x, s)`, with no
> `bitand`. Masking the distance of `ishr`, `iushr`, `lshr` and `lushr` as is done for `ishl` and `lshl` would match
> the JVM.

## Draft report for CBMC/JBMC, cause 4 (not filed: for the user to decide)

The example is `I.java` next to this file. The JVM's run and JBMC's listing were done inline; JBMC's verdicts on it
come from job `20261107-010728`'s last step (`lib/target/report-i.log` among its outputs), and the report is not ready to send
until they say `VERIFICATION FAILED` for both methods.

> **JBMC: a static member named through a subclass initializes the subclass, and initializing a class initializes
> every superinterface (JVMS §5.5)**
>
> JBMC 6.11.0 (cbmc-6.11.0), Linux x86_64. Classes compiled by javac 25.
>
> ```java
> public class I {
>     static int log;
>     static int mark(int v) { log = log * 10 + v; return v; }
>     static class Holder { static int value = 7; }
>     static class Sub extends Holder { static { mark(1); } }
>     interface Bare { int B = mark(4); }
>     interface Greeter { int G = mark(3); default int greet() { return G; } }
>     static class Hello implements Bare, Greeter { static int v() { return 0; } }
>     public static void field() { int v = Sub.value; assert log == 0 && v == 7; }
>     public static void iface() { Hello.v(); assert log == 3; }
> }
> ```
>
> On the JVM (`java -ea`) both assertions hold. In `field`, javac emits `getstatic I$Sub.value`, which resolves to
> `I$Holder.value`, and JVMS §5.5 initializes the class that declared the resolved field, `I$Holder`, so
> `I$Sub.<clinit>` does not run. In `iface`, initializing `I$Hello` initializes its superinterfaces that declare a
> non-abstract, non-static method (§5.5, step 7): `I$Greeter`, not `I$Bare`, so `log` is 3.
>
> In JBMC's `--show-goto-functions`, `I.field` calls `java::I$Sub.<clinit_wrapper>()` at the `getstatic`, which runs
> `I$Holder.<clinit>` and then `I$Sub.<clinit>`; and `java::I$Hello.<clinit_wrapper>` calls both
> `java::I$Bare.<clinit_wrapper>()` and `java::I$Greeter.<clinit_wrapper>()`, so `log` is 43. The same holds for
> `putstatic`, and for `invokestatic` of a static method a superclass declares (where `I$Sub.get` also gets a
> nondeterministic stub in place of `I$Holder.get`). Initializing the class that declares the resolved member, and
> with a class only the superinterfaces that declare a non-abstract, non-static method, would match the JVM.
