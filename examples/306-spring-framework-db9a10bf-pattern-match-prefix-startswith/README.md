# 306: spring-framework@db9a10bf: simpleMatch's prefix check as startsWith (positive scaffold)

[← All examples](../README.md)

**State: source-locked, artifacts pinned, claim and controls written, not prepared.** No replay or proof has run
through the integrated path, so there is no verdict. The work manifest is [`target.json`](target.json); what was
checked upstream, and how, is in [`sources.lock.json`](sources.lock.json).

## The change

[db9a10bf](https://github.com/spring-projects/spring-framework/commit/db9a10bf3524923e8cd5be3f2b847002b8289f75)
(2021-04-21, [gh-26822](https://github.com/spring-projects/spring-framework/issues/26822)), parent `27bfcbbc`, changes
one expression of `PatternMatchUtils.simpleMatch(String,String)`:

```java
pattern.substring(0, firstIndex).equals(str.substring(0, firstIndex))
// becomes
pattern.startsWith(str.substring(0, firstIndex))
```

The length guard before it and the recursive wildcard algorithm stay. The contract is decision preservation, not a new
locale or case guarantee, and a preserved helper predicate is not `DataBinder` mutation protection.

## The artifacts

`PatternMatchUtils.java` at `27bfcbbc` is byte-identical to the file at tag `v5.3.6` and in Maven Central's
`spring-core-5.3.6-sources.jar`; at `db9a10bf` it is identical to `v5.3.7` and `spring-core-5.3.7-sources.jar`. So the
release pair 5.3.6 → 5.3.7 runs the two commits' original method bytecode from Maven Central, with no upstream build.
The JARs' sha256s are pinned in `target.json`. The method calls only `String` methods and itself.

## The claims

| Task | Kind | Expected | What it says |
|---|---|---|---|
| `replay` | replay, release pair | (controls) | Each release's original JAR in its own JVM on JDK 21 and 25, over the probes `(null,"x")`, `("*","")`, `("abc*","ab")`, `("abc*","abcdef")`, `("abc*","xbcdef")`, `("a*c","abbbc")`, `("a*c","abbbd")`, `("a**c","abc")`, `("é*","éx")` and the star shapes |
| `preservation` | equivalence | established | Same boolean and exceptions over a declared bounded UTF-16 domain of nullable strings; bounds frozen in the claim file |
| `mutant-replay` | replay, the `mutation` pair | (controls) | `release-after` against the constructed mutant (the revision `mutant`, `release-after` with the patch applied), with the same driver, probes and oracle: `release-after` holds, the mutant fails at `("abc*","xbcdef")` |
| `mutant-preservation` | equivalence, the `mutation` pair | refuted | `preservation`'s claim file and domain, unchanged, over `release-after` and the mutant: the mutation control (gate A4's nearby mutation) |

At least one true and one false case must reach the changed prefix branch (`("abc*","abcdef")` and `("abc*","xbcdef")`).

## The packet

| File | What it is |
|---|---|
| [`claims/simple-match-preservation.json`](claims/simple-match-preservation.json) | The frozen claim of `preservation`: each argument null or at most 6 UTF-16 code units of any value (`maxArrayLength` 6, `unwind` 16), the boolean and the exception observed |
| [`replay/probes.json`](replay/probes.json) | 40 probes: the brief's nine, the star shapes, a prefix mismatch, non-ASCII, a surrogate pair, half a pair and isolated surrogates |
| [`controls/oracle.py`](controls/oracle.py) | The independent oracle: a glob decision by dynamic programming over code units, checking each revision's lines and the two revisions against each other |
| [`replay/driver`](replay/driver/inloop/p306/SimpleMatchDriver.java) | The driver: one JSON line per probe, its arguments hex code units so that surrogates arrive exactly |
| [`controls/drop-prefix.patch`](controls/drop-prefix.patch) | The mutant: release-after with the prefix condition dropped. It must fail the same oracle and claim (at `("abc*","xbcdef")`) |
| [`records/simple-match-gaps.json`](records/simple-match-gaps.json) | A static `jvmcontract gaps` scan, run by hand (a note): seven JDK `String` methods the native checker approximates, so the strict attempt is predicted to be refused |

A hand replay with the pinned JARs on JDK 21 and 25 (a note, in `example.json`) found both releases agreeing with the
oracle and with each other on every probe, and the mutant failing on six.

## Observed blockers

Every proof task's first attempt (Phase 5, 2026-11-14) stopped before any proof, at a capability gap of the checker or
the route (VF-027). As the user decided on 2026-11-15, each is recorded as an observed gap, not restated: the claims and
their expected conclusions are unchanged, the claims stay unresolved, and each task's readiness is blocked. Each packet
cites its job and receipt and gives the refusal, the semantics needed, the likely owner module and the closure check.

| Task | Refused at | Observed by job | Packet |
|---|---|---|---|
| `mutant-preservation` | a `String` parameter the check doesn't take | `20261114-234214-example-306-mutant-preservation-phase-5` | [`records/refusals/mutant-preservation.json`](records/refusals/mutant-preservation.json) |
| `preservation` | before and after with different dependency closures, where jvmcontract's equivalence takes one classpath | `20261114-234213-example-306-preservation-phase-5-step-1` | [`records/refusals/preservation.json`](records/refusals/preservation.json) |

`python3 examples/tools/targets/workflow_refusal.py 306 TASK` reruns a task and passes only while its recorded refusal
recurs under the same claim key; a verdict or another refusal fails it. Those reruns are queued (2 jobs,
`20261115-005928-example-306-mutant-preservation-vf-027-r` to
`20261115-005928-example-306-preservation-vf-027-rerun-st`).
