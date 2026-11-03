# Bytecode verification of FasterXML/jackson-core#1203: faster division by 1000 in `NumberOutput`

[← All examples](../README.md)

[The pull request](https://github.com/FasterXML/jackson-core/pull/1203) (merged 2024-02-15 into the 2.17 branch) adds `NumberOutput.divBy1000(int)`, which computes `number / 1000` for non-negative numbers as `(int) (number * 274_877_907L >>> 38)`, and uses it in place of the division in `outputInt(int, char[], int)`, `outputInt(int, byte[], int)` and the private helpers `outputLong` shares with them. In `ByteQuadsCanonicalizer` it adds `multiplyByFourFifths(int)`, `(int) (number * 3_435_973_837L >>> 32)`, for `number * 4 / 5`. Forty-eight lines of tests compare the two formulas on sampled values.

This is the kind of change a regression proof exists for: a formula replaced by a faster one that must agree on every input the callers pass. Here the verifier reached no verdict on any of it. Each proof pits a 64-bit multiply-and-shift against a 32-bit division, and division is the operation the tool's reference names as the one that can exhaust the solver: the `divBy1000` property did not finish in 300 s, the equivalence of `outputInt(int, char[], int)` did not finish in 600 s, and the other two formatters ran out of memory. The one verdict is a witness that documents the method's precondition: `divBy1000(-1)` is `67108863`, not `0`, and every caller passes a non-negative value. The module-level contracts are unchanged apart from the two new methods.

| Method | Proof | Verdict | Detail |
|---|---|---|---|
| `NumberOutput#divBy1000(int)` | property `result == number / 1000` under `number >= 0` | ⚠ Unverifiable | JBMC did not finish within 300 s |
| `NumberOutput#divBy1000(int)` | property `result == number / 1000` over every `int` | ✗ Violation | `divBy1000(number=-1)` returns `67108863`; found in 3.1 s as `divBy1000(-36864)`, shrunk in 27 interpreter runs. Not a bug: the formula is for non-negative numbers, and `outputInt` and `outputLong` handle the sign before calling it |
| `NumberOutput#outputInt(int, char[], int)` | regression (equivalence) | ⚠ Unverifiable | JBMC did not finish within 600 s (795 s wall clock) |
| `NumberOutput#outputInt(int, byte[], int)` | regression (equivalence) | ⚠ Unverifiable | JBMC ran out of memory (3 GiB) in 11 s |
| `NumberOutput#outputLong(long, char[], int)` | regression (equivalence) | ⚠ Unverifiable | JBMC ran out of memory (3 GiB) in 11 s |
| `ByteQuadsCanonicalizer#multiplyByFourFifths(int)` | property `result == (int) (number * 4L / 5)` under `number >= 0` | ⚠ Unverifiable | JBMC did not finish within 300 s |
| `ByteQuadsCanonicalizer`'s use of the new method | none | not covered | an instance method over the symbol table's state |
| release notes | none | not covered | not Java |

## Findings

### `divBy1000` outside its precondition

```
✗ Property of com.fasterxml.jackson.core.io.NumberOutput#divBy1000 violated: `result == number / 1000`:
  divBy1000(number=-1)
    outcome: 67108863
  (found by JBMC 6.11.0 in 3.1 s searching inputs in [-100000:100000] as divBy1000(number=-36864), shrunk to the input above in 27 interpreter runs, replayed in the interpreter; domain number: int)
```

`-1 * 274877907` is negative, and an unsigned shift of a negative `long` by 38 is a large positive number. The identity `divBy1000(n) == n / 1000` holds only for `n >= 0`, which is what the pull request intends: both `outputInt` methods negate a negative `v` before the division, so the new method never sees one. The witness is the precondition, found in three seconds; proving the identity under the precondition is what did not finish.

### Why nothing was proved

The proofs are bounded model checks over bit-vectors. A 32-bit division by a constant becomes a circuit the solver must relate to a 64-bit multiplication and shift; the tool's reference measures "a 64-bit division on both sides can exhaust the solver", and this is that case with the division on one side and the multiplication on the other. The formatters are worse: `outputInt(int, char[], int)` divides twice on the old side and multiplies twice on the new one, over a symbolic array and offset, and the comparison includes what each version writes into the array. The 300 s and 600 s budgets are the skill's defaults; the reference suggests tens of minutes for full-domain proofs over multiplication, run in the background, and that was not done here.

## Not covered

- Everything above, as unverifiable: no claim is made about the new formulas beyond the witness.
- `ByteQuadsCanonicalizer`: the new static method's use is in instance methods over the canonicalizer's arrays.

## Module-level contracts

**Capabilities**: unchanged; the only difference is the method count, 3,033 to 3,035, the two new static methods. **Public API**: unchanged (3,511 lines, identical apart from the command line the tool writes into the file).

## How this was produced

- Fetched with the skill's `fetch-pr.sh`: merge base `f46b4d5b`, head `f3e01de9`, checked out side by side on 2026-11-02.
- Compiled with `javac -proc:none -parameters -g`, not Maven: `NumberOutput` and the `schubfach` classes it uses for the method proofs; for the module-level contracts the whole module (163 classes), with `PackageVersion.java` generated from its `.java.in` template as the build does and the one compile dependency, `ch.randelshofer:fastdoubleparser:1.0.0`, downloaded from Maven Central.
- Tools: `jvmcontract` from this repository, JBMC 6.11.0, JDK 25, on an 8-core, 9 GB machine while other proofs were running.
- The commands, as run:

```bash
N='com.fasterxml.jackson.core.io.NumberOutput'
jvmcontract prove "$N#divBy1000" --classes head-classes --assume 'number >= 0' --assert 'result == number / 1000' --timeout 300
jvmcontract prove "$N#divBy1000" --classes head-classes --assert 'result == number / 1000' --timeout 300
jvmcontract equivalence --before base-classes --after head-classes --target "$N#outputInt(int, char[], int)" --timeout 600
jvmcontract equivalence --before base-classes --after head-classes --target "$N#outputInt(int, byte[], int)" --timeout 600
jvmcontract equivalence --before base-classes --after head-classes --target "$N#outputLong(long, char[], int)" --timeout 600
jvmcontract prove 'com.fasterxml.jackson.core.sym.ByteQuadsCanonicalizer#multiplyByFourFifths' --classes head-module-classes --assume 'number >= 0' --assert 'result == (int) (number * 4L / 5)' --timeout 300
jvmcontract capabilities base-module-classes --module jackson-core > capabilities-base.txt
jvmcontract capabilities head-module-classes --module jackson-core > capabilities-head.txt
jvmcontract api base-module-classes --module jackson-core > api-base.txt
jvmcontract api head-module-classes --module jackson-core > api-head.txt
```

Verdicts: *Verified* means the proof covered every input within the stated bounds. *Violation* means a concrete input was found and replayed; for a regression proof that is a behaviour change, intended or not. *Unverifiable* means the tool gave no verdict, for the reason given; it is never a pass.
