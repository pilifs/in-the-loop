# Bytecode verification of apache/commons-lang#1585: `ArrayUtils.subarray` index arithmetic overflow (LANG-1814)

[← All examples](../README.md)

[The pull request](https://github.com/apache/commons-lang/pull/1585) (merged 2026-01-26) changes one line in each of the nine `ArrayUtils.subarray(array, startIndexInclusive, endIndexExclusive)` overloads: the end index, clamped only from above by `Math.min(endIndexExclusive, array.length)`, is also clamped from below with `max0(...)`. Its description says why: with a negative end index and a positive start, `newSize = endIndexExclusive - startIndexInclusive` can overflow to a positive number, and the method, documented to return an empty array when the end is before the start, instead tries to allocate and copy, and fails with `ArrayIndexOutOfBoundsException` or `OutOfMemoryError`.

The regression proofs found that input for `int[]` and `byte[]`: the old version runs out of memory where the new one returns an empty array. The confined-change proof shows that on every input where the subtraction does not overflow, the two versions agree, for arrays of up to eight elements. The first attempt crashed the tool: the interpreter replaying JBMC's witness tried to allocate the two-billion-element array literally, and that is fixed in the same commit as this record. The module's capability and API contracts are unchanged.

| Method | Proof | Verdict | Detail |
|---|---|---|---|
| `subarray(int[], int, int)` | regression (equivalence) | ✗ Violation | `subarray(array=[], startIndexInclusive=9, endIndexExclusive=-2147483640)`: before throws `OutOfMemoryError("Java heap space")`, after returns `[]`; found in 5.2 s as `subarray([2088763390], 9, -2147483640)`, shrunk in 38 interpreter runs; the bug the pull request describes |
| `subarray(byte[], int, int)` | regression (equivalence) | ✗ Violation | `subarray(array=[], startIndexInclusive=1, endIndexExclusive=-2147483648)`: the same outcomes; 3.1 s |
| `subarray(int[], int, int)` | confined change, `--unchanged-unless 'startIndexInclusive > 0 && endIndexExclusive < startIndexInclusive - 2147483647 - 1'` | ✓ Verified | equivalent on every other input: arrays of up to 8 elements × `startIndexInclusive: int` × `endIndexExclusive: int`, 6.1 s. The expression is "`endIndexExclusive - startIndexInclusive` overflows", written without the overflow |
| `subarray(int[], int, int)` | property `result.length <= array.length`, on head and on base | ⚠ Unverifiable | JBMC's counterexample (`subarray([0, 0, 0, 0], 0, 5)`) does not reproduce: the interpreter returns a four-element array and the property holds. JBMC treats the array of computed size the method allocates as one of arbitrary length; the tool reports the proof as unverifiable rather than trusting either side |
| the other seven overloads | none | not run | the same one-line change; `double[]`, `float[]` and `Object[]` are outside the symbolic verifier, and `long[]`, `char[]`, `short[]`, `boolean[]` would prove as `int[]` and `byte[]` did |
| `ArrayUtilsTest` | none | not covered | a test |

## Findings

### The overflow

```
✗ Behaviour of org.apache.commons.lang3.ArrayUtils#subarray(byte[], int, int) changed:
  subarray(array=[], startIndexInclusive=1, endIndexExclusive=-2147483648)
    before: throws OutOfMemoryError("Java heap space")
    after:  []
  (found by JBMC 6.11.0 in 3.1 s as subarray(array=[0], startIndexInclusive=1, endIndexExclusive=-2147483648), shrunk to the input above in 34 interpreter runs, replayed in the interpreter; domain array: byte[] of length ≤ 8 × startIndexInclusive: int × endIndexExclusive: int)
```

In the old version `startIndexInclusive` is clamped to `1` and `endIndexExclusive` to `min(-2147483648, 0)`, which is `-2147483648`; `newSize = -2147483648 - 1` wraps to `2147483647`, and `new byte[2147483647]` is the allocation the pull request describes. The `OutOfMemoryError` is the interpreter's: it refuses arrays of more than 2^24 elements with the error a JVM throws when its heap is too small, which for 2 GiB of bytes is every default heap; a JVM with a larger heap would reach `System.arraycopy` and throw `ArrayIndexOutOfBoundsException` instead, the other outcome the pull request names. Either way the documented behaviour, an empty array, is what the new version does.

### Confined to the overflow

With the intent stated as the inputs on which the subtraction overflows, JBMC proved the two versions equivalent on every other input in six seconds, for arrays of up to eight elements: the returned arrays agree element by element, including the shared empty-array constant and `null` for a `null` input.

### The tool crash

The first run of each regression proof ended in `memory allocation of 34359738352 bytes failed` and an abort: JBMC's witness asked the interpreter for `new int[2147483647]`, and the interpreter allocated it literally, 32 GiB of values. The interpreter now throws `OutOfMemoryError("Java heap space")` for any array longer than 2^24 elements, which is also what makes the witness above readable. The limit is a model of a JVM heap, not a measurement of one.

## Not covered

- The length property, as above: an array allocated with a computed size is a shape JBMC handles imprecisely, which the tool's reference notes ("a method that allocates `new byte[n]` with `n` computed from the data never finished"); here it finished with an answer the replay refuted.
- The other overloads and arrays longer than eight.

## Module-level contracts

**Capabilities**: unchanged, 382 classes before and after. **Public API**: unchanged. The only differing lines in the outputs are the command lines the tool writes into them.

## How this was produced

- Fetched with the skill's `fetch-pr.sh`: merge base `e7cdeac0`, head `ccf0b46b`, checked out side by side on 2026-11-02.
- The module has no compile-time dependencies, so both versions were compiled with `javac -proc:none -parameters -g` over `src/main/java` (382 classes each); Maven was not run.
- Tools: `jvmcontract` from this repository, rebuilt with the array-length limit for the second run, JBMC 6.11.0, JDK 25.
- The commands, as run:

```bash
for ty in int byte; do
  jvmcontract equivalence --before base-classes --after head-classes --target "org.apache.commons.lang3.ArrayUtils#subarray(${ty}[], int, int)" --timeout 600
done
T='org.apache.commons.lang3.ArrayUtils#subarray(int[], int, int)'
jvmcontract equivalence --before base-classes --after head-classes --target "$T" --unchanged-unless 'startIndexInclusive > 0 && endIndexExclusive < startIndexInclusive - 2147483647 - 1' --timeout 900
jvmcontract prove "$T" --classes head-classes --assert 'result.length <= array.length' --timeout 300
jvmcontract prove "$T" --classes base-classes --assert 'result.length <= array.length' --timeout 300
jvmcontract capabilities base-classes --module commons-lang3 > capabilities-base.txt
jvmcontract capabilities head-classes --module commons-lang3 > capabilities-head.txt
jvmcontract api base-classes --module commons-lang3 > api-base.txt
jvmcontract api head-classes --module commons-lang3 > api-head.txt
```

Verdicts: *Verified* means the proof covered every input within the stated bounds. *Violation* means a concrete input was found and replayed; for a regression proof that is a behaviour change, intended or not. *Unverifiable* means the tool gave no verdict, for the reason given; it is never a pass.
