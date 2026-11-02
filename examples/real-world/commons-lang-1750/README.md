# Bytecode verification of apache/commons-lang#1750: `ArrayUtils.reverse` with `Integer.MIN_VALUE` as the end index

[← Real-world examples](../README.md)

[The pull request](https://github.com/apache/commons-lang/pull/1750) (merged 2026-07-17) changes one line in each of the nine `ArrayUtils.reverse(array, startIndexInclusive, endIndexExclusive)` overloads: the end of the range, `Math.min(array.length, endIndexExclusive) - 1`, becomes `max0(Math.min(array.length, endIndexExclusive)) - 1`, so that an end index of `Integer.MIN_VALUE` no longer wraps to `Integer.MAX_VALUE`. It adds 41 lines of tests.

The regression proofs of the six overloads the verifier handles found the one input the fix is about, `endIndexExclusive = Integer.MIN_VALUE`, from the bytecode alone and shrunk it to an empty array; the confined-change proofs show that on every other end index the two versions do the same thing to arrays of up to four elements; and a property proof shows the new `reverse(int[], int, int)` throws on no input at all, where the old one does on the witness. The module's capability and API contracts are unchanged.

| Method | Proof | Verdict | Detail |
|---|---|---|---|
| `reverse(int[], int, int)` | regression (equivalence), arrays ≤ 4, `--unwind 6` | ✗ Violation | `reverse(array=[], startIndexInclusive=0, endIndexExclusive=-2147483648)`: before throws `ArrayIndexOutOfBoundsException("Index 2147483647 out of bounds for length 0")`, after returns; found in 100.3 s as `reverse([0, 0], 134219777, -2147483648)`, shrunk in 35 interpreter runs; this is the bug the pull request fixes |
| `reverse(long[], int, int)` | the same | ✗ Violation | the same witness, found in 386.7 s |
| `reverse(byte[], int, int)` | the same | ✗ Violation | the same witness, 9.4 s |
| `reverse(char[], int, int)` | the same | ✗ Violation | the same witness, 25.8 s |
| `reverse(short[], int, int)` | the same | ✗ Violation | the same witness, 22.8 s |
| `reverse(boolean[], int, int)` | the same | ✗ Violation | the same witness, 5.0 s |
| the six above | confined change, `--unchanged-unless 'endIndexExclusive == -2147483648'` | ✓ Verified | equivalent on every other input, arrays of up to 4 elements × `startIndexInclusive: int` × `endIndexExclusive: int`; int 120.7 s, long 473.6 s, byte 9.1 s, char 28.1 s, short 30.5 s, boolean 5.1 s |
| `reverse(int[], int, int)` | property `true` (no exception on any input), on head and on base | ✓ Verified on head, ✗ on base | the new version returns normally for every array of up to 4 elements and every pair of indices (1.2 s); the old one throws on the witness above (1.2 s) |
| `reverse(double[], int, int)`, `reverse(float[], int, int)` | none | not covered | `double[]` and `float[]` are outside the symbolic verifier |
| `reverse(Object[], int, int)` | none | not covered | a reference-array parameter |
| `ArrayUtilsTest` | none | not covered | a test |

## Findings

### The witness is the bug

```
✗ Behaviour of org.apache.commons.lang3.ArrayUtils#reverse(int[], int, int) changed:
  reverse(array=[], startIndexInclusive=0, endIndexExclusive=-2147483648)
    before: throws ArrayIndexOutOfBoundsException("Index 2147483647 out of bounds for length 0")
    after:  void
  (found by JBMC 6.11.0 in 100.3 s as reverse(array=[0, 0], startIndexInclusive=134219777, endIndexExclusive=-2147483648), shrunk to the input above in 35 interpreter runs, replayed in the interpreter; domain array: int[] of length ≤ 4 × startIndexInclusive: int × endIndexExclusive: int)
```

With `endIndexExclusive = Integer.MIN_VALUE`, `Math.min(array.length, endIndexExclusive)` is `Integer.MIN_VALUE` and subtracting one wraps to `Integer.MAX_VALUE`; `j > i` holds, and the first read `array[j]` throws. After the fix `max0` clamps the minimum to zero, `j` is `-1`, and the loop does not run. JBMC found the input with a two-element array and a large start index; the interpreter shrank it to an empty array and a start of zero, the smallest input on which the two versions differ. The same input is the witness for all six element types.

### Nothing else changed, within the bounds

With the intent stated as `endIndexExclusive == -2147483648`, JBMC proved each of the six overloads equivalent to its old version on every other input: arrays of up to four elements with any contents, and any `startIndexInclusive` and `endIndexExclusive`. The comparison includes what each version leaves in the array and which exception it throws. The bound on the array is the proof's: at the defaults (arrays of up to 8 elements, loops unwound 16 times) the SAT solver ran out of its 3 GiB in 35 s for `int[]` and 11 s for `long[]`, because reversing both versions' arrays means up to sixteen writes at symbolic positions, the shape the tool's reference lists as a known blow-up. At 4 and 6 every proof finished.

### The fix as a property

`reverse(int[], int, int)` with the assertion `true` and no throws clause states "returns normally on every input". It holds on the new version and fails on the old one with the witness above, which is the fix stated independently of the diff.

## Not covered

- The `double[]`, `float[]` and `Object[]` overloads: the symbolic verifier takes primitive parameters and arrays of integral or boolean elements. The change in them is the same line.
- Arrays longer than four elements. The proofs are bounded; the witness itself needs no elements at all.

## Module-level contracts

**Capabilities** (what the module's bytecode can reach): unchanged, 391 classes before and after. **Public API**: unchanged. The only lines that differ between the before and after outputs are the command lines the tool writes into them.

## How this was produced

- Fetched with the skill's `fetch-pr.sh`: merge base `9f57c08e` (the tip of `master` when the branch was made), head `4a0fde24`, checked out side by side on 2026-11-02.
- The module has no compile-time dependencies, so both versions were compiled with `javac -proc:none -parameters -g` over `src/main/java` (391 classes each) rather than with Maven; the pull request's build scripts were not run.
- Tools: `jvmcontract` from this repository, JBMC 6.11.0, JDK 25 (Temurin 25.0.4.1), on an 8-core, 9 GB machine while other proofs were running.
- The commands, as run:

```bash
B="--max-array-length 4 --unwind 6"
for ty in int long byte char short boolean; do
  T="org.apache.commons.lang3.ArrayUtils#reverse(${ty}[], int, int)"
  jvmcontract equivalence --before base-classes --after head-classes --target "$T" $B --timeout 600
  jvmcontract equivalence --before base-classes --after head-classes --target "$T" $B --unchanged-unless 'endIndexExclusive == -2147483648' --timeout 900
done
T='org.apache.commons.lang3.ArrayUtils#reverse(int[], int, int)'
jvmcontract prove "$T" --classes head-classes $B --assert 'true' --timeout 300
jvmcontract prove "$T" --classes base-classes $B --assert 'true' --timeout 300
jvmcontract capabilities base-classes --module commons-lang3 > capabilities-base.txt
jvmcontract capabilities head-classes --module commons-lang3 > capabilities-head.txt
jvmcontract api base-classes --module commons-lang3 > api-base.txt
jvmcontract api head-classes --module commons-lang3 > api-head.txt
```

Verdicts: *Verified* means the proof covered every input within the stated bounds. *Violation* means a concrete input was found and replayed; for a regression proof that is a behaviour change, intended or not. *Unverifiable* means the tool gave no verdict, for the reason given; it is never a pass.
