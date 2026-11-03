# Bytecode verification of apache/commons-numbers#223: `ArithmeticUtils.pow` accepts the representable minimum-value powers

[← All examples](../README.md)

[The pull request](https://github.com/apache/commons-numbers/pull/223) ([NUMBERS-218](https://issues.apache.org/jira/browse/NUMBERS-218), merged 2026-10-18 as `8cfc04e8`) changes two comparisons in `org.apache.commons.numbers.core.ArithmeticUtils`: `pow(int, int)` throws `ArithmeticException` for `e > 31` instead of `e >= 31`, and `pow(long, int)` for `e > 63` instead of `e >= 63`, so that `(-2)^31` returns `Integer.MIN_VALUE` and `(-2)^63` returns `Long.MIN_VALUE` instead of reporting overflow. It adds one unit test for the boundary and a release note.

The regression proof of `pow(int, int)` found the one input whose behaviour changes, `pow(-2, 31)`, from the two versions' bytecode alone, with no test and no specification written. The fix was then proved as a property on the new version and refuted on the old one, the Javadoc was proved on the new version, and with the pull request's intent stated as `k == -2 && e == 31`, the new `pow` was proved to behave as the old one on every other input: all 2^64 of them. The `long` overload, which the same pull request changes in the same way, was not reached by the recorded run.

| Method | Proof | Verdict | Detail |
|---|---|---|---|
| `ArithmeticUtils#pow(int, int)` | regression (equivalence) | ✗ Violation | differs on `pow(k=-2, e=31)`: before threw `ArithmeticException("integer overflow")`, after returns `-2147483648`; found by JBMC 6.11.0 in 184.7 s searching inputs in `[-100000:100000]`, replayed in the interpreter; this is the change the pull request describes |
| `ArithmeticUtils#pow(int, int)` | confined change, `--unchanged-unless 'k == -2 && e == 31'` | ✓ Verified | equivalent on every other input (domain `k: int × e: int`, 2^64 inputs); did not finish in the default 300 s, verified in 1083.5 s with `--timeout 1500`; all three JBMC stages ended with `VERIFICATION SUCCESSFUL` |
| `ArithmeticUtils#pow(int, int)` | property: `result == -2147483648` under `k == -2 && e == 31` | ✓ Verified on head, ✗ on base | proved on the new version in 1.0 s; on the old version refuted in 0.7 s, with the `ArithmeticException` above |
| `ArithmeticUtils#pow(int, int)` | property: Javadoc, `@throws IllegalArgumentException if e < 0`, with the documented results for `k` in `{-1, 0, 1}` | ✓ Verified | on the new version, in 1.4 s; the `@throws ArithmeticException if the result would overflow` is not part of this property |
| `ArithmeticUtils#pow(long, int)` | none | not covered | changed by the pull request in the same way (`e > 63`); not proved in the recorded run |
| `ArithmeticUtilsTest`, `src/changes/changes.xml` | none | not covered | a test and a release note: outside main source sets |

## Findings

### `pow(int, int)`: the fix's input, found by the regression proof

```
✗ Behaviour of org.apache.commons.numbers.core.ArithmeticUtils#pow(int, int) changed:
  pow(k=-2, e=31)
    before: throws ArithmeticException("integer overflow")
    after:  -2147483648
  (found by JBMC 6.11.0 in 184.7 s searching inputs in [-100000:100000], replayed in the interpreter; domain k: int × e: int)
```

The statement a regression proof checks is "the new bytecode behaves as the old bytecode on every input". Both versions of the method are compiled into one program with a harness that calls each on the same symbolic `k` and `e` and asserts that the outcomes agree, including which exception is thrown. JBMC searches small inputs first, then the whole domain; the witness is the smallest it found, replayed in `jvmcontract`'s interpreter to confirm both outcomes. The input it found is exactly the one the pull request names, so the violation is the intended change, and the question for a reviewer becomes whether anything else changed.

### `pow(int, int)`: the change confined to the one input

With the intent stated, `--unchanged-unless 'k == -2 && e == 31'`, the statement becomes "on every input except `(-2, 31)`, the new bytecode behaves as the old". JBMC proved it over the full domain. The proof is a bounded model check over chained 32-bit multiplications (`pow` is a square-and-multiply loop with `Math.multiplyExact`), which is why it costs minutes where the property proofs below cost a second; the skill runs such proofs in the background with a budget and reports how far they got. At the default timeout of 300 s it had not finished; with `--timeout 1500` it finished in 1083.5 s, and the three stages of its JBMC log each end with `VERIFICATION SUCCESSFUL`, which is the only line that counts as a proof.

### `pow(int, int)`: the fix and the Javadoc as properties

`result == -2147483648` under the assumption `k == -2 && e == 31` holds on the new version (1.0 s) and fails on the old one (0.7 s), where the method throws. The Javadoc's `@throws IllegalArgumentException if e < 0` and its documented results for `k` in `{-1, 0, 1}` (`0^0 = 1`, `0^e = 0`, `1^e = 1`, `(-1)^e = ±1` by the parity of `e`), written as a `--throws` clause and an `--assert` over every `e` with `k` restricted to those three values, hold on the new version (1.4 s). The Javadoc did not change in the pull request, so proving it on the new version shows the fix did not break what the method documents. The Javadoc's other clause, `@throws ArithmeticException if the result would overflow`, is not stated by this property: stating when a square-and-multiply loop overflows needs the result itself, and outside `k` in `{-1, 0, 1}` the assertion above is violated by exactly those overflows (the tool's witness is `pow(12, 10)`, shrunk from the first input JBMC found), which is the right answer to a property that forgot to declare them.

## Not covered

- `pow(long, int)`, the second method the pull request changes. The recorded run proved the `int` overload only. The same three proofs apply to it, with `k == -2L && e == 63` as the intent; the 64-bit multiplications make the full-domain proof more expensive than the `int` one.
- The module-level capability and public API diffs of `commons-numbers-core`, before and after. No record of them survives from the run, so none is claimed here.

## How this was produced

- The run was made on 2026-11-01 while building the `/verify-bytecode` skill, by the sessions recorded in [this summary](../../llm-dlc/traces/a308f9d3-8d8a-42ca-b074-d388818c2418/summary.md) and [this one](../../llm-dlc/traces/2e359813-25c2-4259-888b-42d3a5f0eee6/summary.md), with the times recorded in the [plugin README](../../plugins/jvmcontract/README.md) and the skill's [reference](../../plugins/jvmcontract/skills/verify-bytecode/reference.md#costs-so-you-can-budget). It is the run those pages quote.
- The pull request was fetched with `gh` and its merge base and head checked out side by side. The module's Maven build could not be run in that session (the permission classifier of the agent's sandbox declined to run the external project's build), so `ArithmeticUtils.java` was compiled alone with `javac` for each version, which the skill's step 3 provides for a changed file that depends only on the JDK. The class under proof is therefore the one `javac` produces from the pull request's source, not the one the library's own build produces; for this file, which has no annotation processing or build-time generation, they are the same source compiled by the same compiler.
- Tools: `jvmcontract` as of this repository on 2026-11-01, JBMC 6.11.0.
- The commands, in the skill's shape (the working directory of the original run was not kept, so these are the commands to rerun it, not a copy of its log):

```bash
T='org.apache.commons.numbers.core.ArithmeticUtils#pow(int, int)'
jvmcontract equivalence --before base/classes --after head/classes --target "$T"
jvmcontract equivalence --before base/classes --after head/classes --target "$T" --unchanged-unless 'k == -2 && e == 31' --timeout 1500
jvmcontract prove "$T" --classes head/classes --assume 'k == -2 && e == 31' --assert 'result == -2147483648'
jvmcontract prove "$T" --classes base/classes --assume 'k == -2 && e == 31' --assert 'result == -2147483648'
jvmcontract prove "$T" --classes head/classes --assume 'k >= -1 && k <= 1' --throws 'java.lang.IllegalArgumentException when e < 0' \
    --assert '(k != 0 || e != 0 || result == 1) && (k != 0 || e == 0 || result == 0) && (k != 1 || result == 1) && (k != -1 || (e & 1) != 0 || result == 1) && (k != -1 || (e & 1) == 0 || result == -1)'
```

**Rerun on 2026-11-01**, when this record was written, to check the commands: `ArithmeticUtils.java` at the head commit `79aa4643` and at `e7c172d2` (the commit the squash merge landed on, whose copy of the file is the pre-fix one) compiled alone with `javac -parameters` (JDK 25), `jvmcontract` from this repository, JBMC 6.11.0. The three property proofs gave the same verdicts: the fix's property verified on head in 1.7 s and refuted on base in 1.1 s with the witness above; the Javadoc property verified on head in 2.2 s. The regression proof found the same witness, `pow(k=-2, e=31)`, in 495.3 s, and the confined-change proof with `--timeout 1500` verified in 1838.1 s (JBMC: 4 properties proved over `k: int × e: int`). Both ran slower than the recorded run because two other JBMC proofs were running on the same 8-core, 9 GB machine at the time; the verdicts are what matter, the times are a budget.

Verdicts: *Verified* means the proof covered every input within the stated bounds. *Violation* means a concrete input was found and replayed; for a regression proof that is a behaviour change, intended or not. *Unverifiable* means the tool gave no verdict, for the reason given; it is never a pass.
