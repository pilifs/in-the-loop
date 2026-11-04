# Mica

The decision kernels of a small Java virtual machine written in Java: the class initialization procedure, the type checker's assignability relation, access control at resolution time, the arithmetic and comparison instructions with their corner cases, the bisection of a `lookupswitch`, the lookup of an exception handler in the exception table, the offsets of stack map frames, the length of a `Code` attribute, the numbering of the constant pool, the assembler's `max_stack`, its choice between `tableswitch` and `lookupswitch` and its sort of a `lookupswitch`'s pairs, the sizing of the symbol table, and the modified UTF-8 of the constant pool.
Each is the few lines of a virtual machine where the Java Virtual Machine Specification says exactly what must happen, written as a function so that it can be proved, with the runtime around it (the locks, the threads, the heap, the host) left to perform what the kernel decides.
It is the fourth subject system of the [examples](../../README.md) (034 to 056, 140 to 145), verified by [`jvmcontract`](../../../lib/README.md), the Rust tool, which is itself an interpreter of Java bytecode: a verifier of JVM kernels, running the kernels of a JVM.

The design rule is the one that makes these kernels provable: a kernel takes its inputs as arguments (the class's state, the two verification types, the two operands) and returns a decision or a value; it holds no lock, reads no clock, and never reaches the host's reflection.
The module's [capability contract](src/contract/capabilities.contract) says so, with every capability `none`, and the build checks it: an interpreter that computes a guest's `StrictMath.sin` by looking the name up on the host would be the first capability it gains ([example 041](../../041-math-intrinsics-through-method-handles-give-the-interpreter-reflection/README.md)).
Every kernel here has a contract, a property or a model checked on every build.

## The kernels, and the specification each implements

| Kernel | JVMS | What it decides | Verified by | Examples |
|---|---|---|---|---|
| [`init.ClassInitialization`](src/main/java/net/terminalvalue/mica/init/ClassInitialization.java) | §5.5, the initialization procedure | What a thread does when it needs a class: run the initializer, wait, proceed (including the recursive request by the initializing thread), or throw `NoClassDefFoundError`; and what happens when the initializer returns or throws | A [behavioural contract](src/contract/ClassInitialization.decide.contract), and a [TLA+ model](spec/README.md) of threads racing for one class, checked by TLC with deadlock detection | 042, 043 |
| [`verify.Assignability`](src/main/java/net/terminalvalue/mica/verify/Assignability.java) | §4.10.1.2, `isAssignable` | Whether a verification type may be used where another is expected: primitives, `null`, the uninitialized types, classes, an interface, arrays | A [behavioural contract](src/contract/Assignability.isAssignable.contract): all 289 pairs | 038 |
| [`link.AccessControl`](src/main/java/net/terminalvalue/mica/link/AccessControl.java) | §5.4.4, access control | Whether a member is accessible from the referring class: `public`, `protected` with the receiver rule, package access, `private` (and nestmates, [JEP 181](https://openjdk.org/jeps/181)) | A [behavioural contract](src/contract/AccessControl.check.contract): all 120 cases | 039, 040 |
| [`interp.Arithmetic`](src/main/java/net/terminalvalue/mica/interp/Arithmetic.java) | §6.5, `idiv` and `irem` | The quotient and remainder, with `Integer.MIN_VALUE / -1` as specified and `ArithmeticException` on zero | Properties: division by -1 negates and by 1 is the identity, on every input; a throws clause: `ArithmeticException` exactly when the divisor is zero | 034, 053 |
| [`interp.Comparison`](src/main/java/net/terminalvalue/mica/interp/Comparison.java) | §6.5, `lcmp`, `fcmpg`/`fcmpl`, `dcmpg`/`dcmpl` | -1, 0 or 1, with NaN as the opcode says | Regression proofs against the previous version (floats included) | 035 |
| [`interp.LookupSwitch`](src/main/java/net/terminalvalue/mica/interp/LookupSwitch.java) | §6.5, `lookupswitch` | The bisection of the sorted match-offset pairs | Properties: the midpoint stays within the bounds, for the sizes a `Code` attribute allows; the search finds every key in every sorted table and -1 exactly when the key is absent, quantified over the array; regression proofs of the half-open rewrite against the closed form on every strictly sorted table, by the tool's own checker; a short-table scan declared as the intended change, proved vacuously at the default bound and for real at a larger one | 045, 046, 140, 141, 144, 145 |
| [`classfile.ExceptionTable`](src/main/java/net/terminalvalue/mica/classfile/ExceptionTable.java) | §4.7.3 and §2.10, the exception table | Which entry handles an exception thrown at a pc: the first in table order whose half-open range covers it; and whether an entry is well-formed, `start_pc < end_pc <= code_length` and `handler_pc < code_length`, a `ClassFormatError` otherwise | A property over the table's columns: the entry found covers the pc, none before it does, and -1 means none does; a throws clause: `ClassFormatError` exactly when the entry breaks one of the three constraints | 047, 054 |
| [`classfile.StackMapTable`](src/main/java/net/terminalvalue/mica/classfile/StackMapTable.java) | §4.7.4, the StackMapTable attribute | The bytecode offset of a frame from the `offset_delta` of every frame: the first at its delta, each later one `offset_delta + 1` further | A property with JML's `\sum`: frame `k` is at `k` plus the sum of the deltas, and above the previous frame, stated by calling the reader on `k - 1` | 049 |
| [`classfile.CodeAttribute`](src/main/java/net/terminalvalue/mica/classfile/CodeAttribute.java) | §4.7.3, the Code attribute | The `attribute_length` of a `Code` attribute: the fixed part, the code, the handlers, and the nested attributes with their headers | A property with `\sum` over the nested attributes' lengths | 050 |
| [`classfile.ConstantPool`](src/main/java/net/terminalvalue/mica/classfile/ConstantPool.java) | §4.4.5, `CONSTANT_Long_info` and `CONSTANT_Double_info` | The constant pool number of an entry: from 1, with two numbers for each `long` or `double` before it | A property with `\num_of`: the number is `1 + entry` plus the count of two-number entries before it | 051 |
| [`asm.MaxStack`](src/main/java/net/terminalvalue/mica/asm/MaxStack.java) | §4.7.3, `max_stack` | The deepest the operand stack gets in a straight-line sequence | A property with `\max` over `\sum`: the largest prefix sum of the stack effects | 052 |
| [`interp.Intrinsics`](src/main/java/net/terminalvalue/mica/interp/Intrinsics.java) | §2.11.3 (the host computes what the guest's natives would) | Which `StrictMath` functions the host computes for the guest | The [capability contract](src/contract/capabilities.contract): none | 041 |
| [`asm.SwitchLowering`](src/main/java/net/terminalvalue/mica/asm/SwitchLowering.java) | §3.10 (javac's heuristic in `Gen.visitSwitch`), §6.5 (`lookupswitch`) | `tableswitch` or `lookupswitch`, by space and time cost; the sort of a `lookupswitch`'s match-offset pairs | A regression proof against the previous version; a property: the sort leaves the keys sorted and every pair it received among the pairs it left (`\old`), a permutation that keeps each offset with its key | 036, 056 |
| [`rt.SymbolTable`](src/main/java/net/terminalvalue/mica/rt/SymbolTable.java) | (the runtime's own) | The power-of-two capacity for a requested size | A property: a power of two, at least the request, the smallest such; a regression proof of the JDK 11 rewrite | 037 |
| [`classfile.ModifiedUtf8`](src/main/java/net/terminalvalue/mica/classfile/ModifiedUtf8.java) | §4.4.7, `CONSTANT_Utf8_info` | How many bytes a code unit takes, its first byte, and the encoding of a `char[]` into a buffer | Properties: never a zero byte; one byte exactly for U+0001 to U+007F; no byte the encoder writes is zero or in `0xf0` to `0xff`, and the bytes past what it wrote are as they were (`\old`). A regression proof of an ASCII fast path, which JBMC could not finish at the default bound of 8 and the tool's own checker proves in seconds, and of the same fast path off by one, which only the comparison with the previous version catches | 044, 048, 055, 142, 143 |

The runtime around the kernels is not in this module: it is where the initialization lock, the thread, the heap and the host JVM live.
A kernel is used from it in one line, for example under the initialization lock of a class:

```java
Decision<InitState, InitEffect> d = ClassInitialization.decide(klass.initState(), new Request(klass.initializer() == Thread.currentThread()));
```

so that the part of the runtime that decides is the part the build proves, and the part that performs is the part a JVM's test suite exercises.

## Layout

```
src/main/java/        the kernels
src/test/java/        plain tests, run by Tests.main; no framework, no build system
src/contract/         the contracts the build checks:
  *.decide.contract, *.check.contract, *.isAssignable.contract   behavioural contracts (generated by `jvmcontract update`)
  properties.contract   the properties proved by JBMC (written by hand; the proofs are regenerated)
  capabilities.contract what the module's bytecode can reach (generated)
  api.contract          the public surface (generated)
spec/                 the TLA+ model of class initialization; ClassInitContract.tla is generated from the contract
verify.sh             compile, test, and run every check below
```

## Verify it

```bash
examples/apps/mica/verify.sh
```

which is, step by step (from this directory, with `jvmcontract` on the `PATH`, as `cargo install --path ../../../lib` puts it):

```bash
javac -parameters -g -d build/main $(find src/main/java -name '*.java')
javac -parameters -g -cp build/main -d build/test $(find src/test/java -name '*.java')
java -ea -cp build/main:build/test net.terminalvalue.mica.Tests

jvmcontract verify --contracts src/contract --classes build/main --module mica            # three behavioural contracts, capabilities, API
jvmcontract prove --properties src/contract/properties.contract --classes build/main        # sixteen property proofs, nine over arrays, four with throws clauses, two with \old
jvmcontract tla src/contract/ClassInitialization.decide.contract spec/ClassInitContract.tla
jvmcontract tlc spec/ClassInit.tla --deadlock --library ../../tools/tla/standard-modules    # 37 states, no invariant violated, no deadlock
```

Every check but the property proofs runs in about three seconds in all; the proofs take about a minute and a half, most of it the three sums and the sort.
