# 306: spring-framework@db9a10bf: simpleMatch's prefix check as startsWith (positive scaffold)

[← All examples](../README.md)

**State: catalogued and source-locked, artifacts pinned, not prepared.** No replay or proof has run, so there is no
verdict. The work manifest is [`target.json`](target.json); what was checked upstream, and how, is in
[`sources.lock.json`](sources.lock.json).

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
