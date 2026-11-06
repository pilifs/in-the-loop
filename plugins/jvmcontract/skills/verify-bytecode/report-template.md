# Bytecode verification of OWNER/REPO#N: <title>

<One paragraph: what the pull request says it does; what was proved, refuted or not covered, in one sentence each. The headline is the finding a reviewer must see: a violation outside the stated intent, a new capability, a failed Javadoc claim. If everything is verified, say so and move on.>

Compared `MERGE_BASE[:12]` (the commit the branch left `base` at) with `HEAD_SHA[:12]`, module `<module>`, compiled with <JDK>. jvmcontract <version>, JBMC <version>.

| Method | Proof | Verdict | Detail |
|---|---|---|---|
| `pkg.Class#method(int, int)` | regression (equivalence) | ✗ Violation | differs on `method(k=-2, e=31)`: before threw `ArithmeticException`, after returns `-2147483648`; this is the change the pull request describes |
| `pkg.Class#method(int, int)` | confined change, `--unchanged-unless 'k == -2 && e == 31'` | ✓ Verified | equivalent on every other input (2^64 inputs) |
| `pkg.Class#method(int, int)` | property: Javadoc `@throws` and `@return` | ✓ Verified | on head; the same property fails on base at `method(k=-2, e=31)` |
| `pkg.Class#jitter(int, int, long)` | property: Javadoc `@return` | ✓ Verified | on every input, relying on 3 contracts for JDK calls: 1 proved, 2 tested (below) |
| `pkg.Class#other(long, int)` | regression (equivalence) | ⚠ Unverifiable | JBMC timed out at 300 s on 64-bit multiplication; not finished |
| `pkg.Class#parse(String)` | none | not covered | `String` parameter: outside the symbolic verifier; covered by the module-level contracts only |

## Findings

### <method>: <one-line finding>

<The witness exactly as the tool printed it, both outcomes, and whether it matches the pull request's intent. The statement proved, in words. The bounds, if arrays.>

```bash
<the exact command>
```

## Contracts for JDK calls

<Only when a proof went through contracts (`--gaps advised`). One line per contract: the call, what the contract states, who wrote it (you, or the tool's library), and its evidence, as the `contract:` line gives it: **proved** against the JDK's bytecode (the class, the JDK, the digest), **tested** on a real JVM (how many inputs, the seed), or **trusted** (why nothing could check it). A verdict that rests on a tested contract is as good as that test, and the report says so. List each contract the JVM refuted on the way, with the input it refuted it on and how you corrected it, and each gap left open, with the tool's reason.>

<Contracts worth keeping: the ones you wrote that were proved or tested and that the library lacks, checked with `jvmcontract gap-contracts --dir` and offered for `lib/models/contracts/` of jvmcontract's repository, with the path of the files in the working directory.>

## Not covered

<Each changed method, constructor or field that no proof reached, with the tool's reason. Non-Java changes (build files, dependencies, resources).>

## Module-level contracts

**Capabilities** (what the module's bytecode can reach): <unchanged / the diff, with each new entry and its call site>.

**Public API**: <unchanged / the diff; removed or changed members are breaking for a library>.

## How this was produced

- Pull request fetched with `gh`; `MERGE_BASE` and `HEAD_SHA` checked out into `<WORK>/base` and `<WORK>/head`. The project's build (<Maven/Gradle>) was run for both, which runs the pull request's build scripts. <Or: the changed files were compiled alone with `javac`, because ...>
- Tools: jvmcontract <version>, JBMC <version>, JDK <version>.
- Contracts for JDK calls, if any: `<WORK>/gaps.contracts`, written by <the agent and model> from the JDK's documentation.
- Every proof's harness, statement and JBMC log is under `<WORK>/<proof dir>`; the commands:

```bash
<every jvmcontract command, in order>
```

Verdicts: *Verified* means the proof covered every input within the stated bounds. *Violation* means a concrete input was found and replayed; for a regression proof that is a behaviour change, intended or not. *Unverifiable* means the tool gave no verdict, for the reason given; it is never a pass. A verdict *relying on contracts* holds if the JDK calls do what the contracts say: a proved contract does on every input, against the JDK's bytecode; a tested one did on every input the JVM was given.
