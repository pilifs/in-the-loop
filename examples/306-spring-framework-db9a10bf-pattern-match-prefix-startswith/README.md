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
