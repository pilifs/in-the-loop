# 307: spring-security@fe9e4549: BCrypt.hashpw with StandardCharsets.UTF_8 (positive scaffold)

[← All examples](../README.md)

**State: catalogued and source-locked, not prepared.** No build, replay or proof has run, so there is no verdict.
The work manifest is [`target.json`](target.json); what was checked upstream, and how, is in
[`sources.lock.json`](sources.lock.json).

## The change

[fe9e4549](https://github.com/spring-projects/spring-security/commit/fe9e4549780e940c9cef7f2991e75e0b686fc5d1)
(2019-08-08 UTC), parent `fb39d9c2`:

```java
// before
try {
    passwordb = password.getBytes("UTF-8");
} catch (UnsupportedEncodingException uee) {
    throw new AssertionError("UTF-8 is not supported");
}
// after
passwordb = password.getBytes(StandardCharsets.UTF_8);
```

Only `BCrypt.hashpw(String,String)` is selected; the patch also changes `crypto.codec.Utf8`'s cached charset and a test
utility. This pair has no length restriction of its own: what it shares with CVE-2025-22228 is the password's UTF-8
representation.

## The claims

| Task | Kind | Expected | What it says |
|---|---|---|---|
| `replay` | replay, both revisions | (controls) | Each revision's original JAR in its own JVM on JDK 21 and 25, a fixed valid low-cost salt from an upstream test, passwords empty, ASCII, BMP non-ASCII, supplementary, and 71, 72 and 73 UTF-8 bytes |
| `preservation` | equivalence | established | Same returned string and exceptions on the frozen password and salt domains and the pinned JDK's charset behaviour |

A proof may reuse a checked summary of the unchanged `hashpw(byte[],String)`, bound to its bytecode; without it the
full claim stays unresolved beside a separate local conversion lemma, and no cipher is substituted.

## Preparation

No Maven Central artifact carries either side's exact `BCrypt.java` (before's is 5.2.0.M4's, a milestone; 5.2.0.RELEASE
differs from after's by an unused import and a `final`). The upstream Gradle build needs services.gradle.org and
repo.spring.io, outside the downloads policy, but pins no SNAPSHOT. The handoff in `target.json` records this as a
predicted build blocker.
