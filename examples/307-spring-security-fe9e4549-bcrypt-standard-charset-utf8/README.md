# 307: spring-security@fe9e4549: BCrypt.hashpw with StandardCharsets.UTF_8 (positive scaffold)

[← All examples](../README.md)

**State: a partial scaffold.** It is source-locked, its claim is frozen, and its oracle, driver, probes and mutant are
written. It is not prepared: the build route waits on the downloads policy. No pipeline replay or proof has run, so there
is no verdict. The work manifest is [`target.json`](target.json); what was checked upstream, and how, is in
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
| `replay` | replay, both revisions | (controls) | Each revision's original class in its own JVM on JDK 21 and 25, over the 45 probes of [`replay/probes.json`](replay/probes.json): fixed salts from upstream's tests, passwords empty, ASCII, BMP non-ASCII, supplementary, 71, 72 and 73 UTF-8 bytes, malformed surrogates and null, and four invalid salts |
| `preservation` | equivalence | established | [`claims/hashpw-preservation.json`](claims/hashpw-preservation.json): a null password or one of at most 80 UTF-16 code units (any values), one of seven fixed salts (null and three other invalid ones included); the same returned String or the same exception class, on one JDK |
| `mutant-replay` | replay, the `mutation` pair | (controls) | `after` against the constructed mutant (the revision `mutant`, `after` with the patch applied), with the same driver, probes and oracle: `after` holds, the mutant fails at the non-ASCII probes |
| `mutant-preservation` | equivalence, the `mutation` pair | refuted | `preservation`'s claim file and domain, unchanged, over `after` and the mutant: the mutation control |

A proof may reuse a checked summary of the unchanged `hashpw(byte[],String)`, bound to its bytecode; without it the
full claim stays unresolved beside a separate local conversion lemma, and no cipher is substituted.

## Preparation

No Maven Central artifact carries either side's exact `BCrypt.java` (before's is 5.2.0.M4's, a milestone; 5.2.0.RELEASE
differs from after's by an unused import and a `final`). The upstream Gradle build needs services.gradle.org and
repo.spring.io, which decision 1's extension allows (hash-pinned), and pins no SNAPSHOT. But its build plugin,
`spring-build-conventions` 0.0.23.RELEASE, is served by no anonymous repository: repo.spring.io answers 401, and
plugins.gradle.org redirects to Maven Central, which has 404 (HEAD requests, 2026-11-14). The handoff in `target.json`
records this as a predicted build blocker, with the narrower extracted-source scope as the alternative.

## The packet

| File | What it is |
|---|---|
| [`claims/hashpw-preservation.json`](claims/hashpw-preservation.json) | The frozen claim of `preservation`, with the domain decisions: a null password (NullPointerException), malformed surrogates (encoded as `?`, as `String.getBytes` specifies), and four invalid salts (IllegalArgumentException) are all in the domain; the exception is observed by class, never by message |
| [`replay/probes.json`](replay/probes.json) | 45 probes over seven salts, each from upstream's `BCryptTests`: the `abc` test vector's cost-6 salt and its stored hash, the `$2$05$` salt, and null, empty, cost-03 and too-short salts. Three known answers come from the same tests |
| [`controls/oracle.py`](controls/oracle.py) | The independent oracle, with no cipher: it encodes UTF-8 itself, predicts which probes must share a result (the same salt and the same first 72 bytes of the cyclic key, the NUL terminator included) and, as a stated assumption, which must not; it also checks the known answers, the result's format and the exceptions |
| [`replay/driver`](replay/driver/inloop/p307/HashpwDriver.java) | The driver: one JSON line per probe, with arguments as UTF-16 code units in hex so that isolated surrogates reach the method exactly |
| [`controls/us-ascii.patch`](controls/us-ascii.patch) | The mutant: after's `getBytes(StandardCharsets.UTF_8)` turned into `US_ASCII`. It must fail on non-ASCII passwords: `é` hashes as `?`, and `'a'*70 + 'é'` stops sharing its result with its 73-byte extension |
| [`records/hashpw-gaps.json`](records/hashpw-gaps.json) | A static `jvmcontract gaps` scan, run by hand (a note). It refuses the changed conversion itself on both sides, and in the callee `Arrays.copyOf`, plus `Integer.parseInt` and `StringBuilder.charAt` with no approximation |

A hand replay (a note, in `example.json`) found before, after and the published 5.2.0.RELEASE class agreeing with the
oracle and with each other on all 45 probes, identically on JDK 21 and 25. The mutant broke the oracle's rules nine
times and differed from before on 17 probes, every one with a non-ASCII password. Before's and after's sides were
compiled from each commit's `BCrypt.java` alone, since no artifact carries them.

The stored hash matters because comparing two revisions can't see an encoding that both get wrong. Hashing with the
stored hash as the salt and comparing the result with it is `checkpw`'s match. With an upstream known answer on that
salt, a wrong encoding would show as a lost or gained match.

## What a proof needs

Requirements read from the source at both commits, and from the static scan; each is a prediction until an attempt
reaches it.

- **The conversion.** The changed line is a JDK call that returns an array: `String.getBytes(String)` at before, and
  `String.getBytes(Charset)` with a read of the non-constant field `StandardCharsets.UTF_8` at after. The scan refuses
  all of them by name. So the strict attempt is predicted to stop at the change itself, before the cipher. This is the
  password-bytes family's shared demand, CVE-2025-22228's too: UTF-16 to UTF-8, with surrogate pairs, malformed input
  and its `?` replacement.
- **The unchanged callee.** `hashpw(byte[],String)` and everything it calls are the same source at both commits. Javac
  8 compiles them to the same bytecode, apart from constant-pool indices, which turn some `ldc_w` in `<clinit>` into
  `ldc`. The callee runs Blowfish's key schedule: S-box loops of 512 steps, 64 cost rounds at cost 6, `Arrays.copyOf`,
  `Integer.parseInt`, and StringBuilder base64. A checked summary of it, bound to that bytecode, would reduce
  preservation to a local lemma: the two conversions give the same bytes on the domain. Without that summary the full
  claim stays unresolved. No cipher is substituted, and a lemma over the conversion alone is a separate, narrower claim.
- **Class initialization.** `BCrypt.<clinit>` fills `P_orig`, `S_orig` (1,024 words) and the base64 tables from
  constants. Nothing in it is a gap, but it is large; it is never removed.
- **Inputs.** Both parameters are Strings and both may be null. The checker takes a String parameter as bounded UTF-16,
  never null, so a null password or salt is a predicted input-construction refusal. The salt domain is seven fixed
  strings, stated with `String.equals` in the claim's `assume`.
- **Compared with the negative** (CVE-2025-22228, whose fix put a 72-byte guard in
  `BCrypt.hashpw(byte[],String,boolean)`, reached through `BCryptPasswordEncoder.matches`): the same conversion and the
  same cyclic 72-byte key, without the encoder, its regex check of the stored hash, or a length policy. This pair adds
  no limit: a 73-byte password hashes like its 72-byte prefix on both revisions, which the probes observe as preserved
  behaviour, not as a defect of this change.
