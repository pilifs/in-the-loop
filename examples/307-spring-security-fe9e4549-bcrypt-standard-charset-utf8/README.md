# 307: spring-security@fe9e4549: BCrypt.hashpw with StandardCharsets.UTF_8 (positive scaffold)

[← All examples](../README.md)

**State: a reproducible scaffold, on the source slice.** It is source-locked and its claim is frozen. Its route is the
extracted-source slice, the user's choice of 2026-11-15 (below). Its replay (job `20261115-003616`) and mutant-replay
(`20261115-003617`) passed: before's class equals Spring Security 5.2.0.M4's published `BCrypt.class` byte for byte,
both slices hold the oracle on JDK 21 and 25, and the us-ascii mutant fails at the non-ASCII probes only. Its native
attempts, `preservation` and `mutant-preservation` (jobs `20261115-011448-…`), were both refused before any proof, at
the nullable `String` password (VF-028), so there is no verdict: both claims stay unresolved and both tasks are blocked
(below). The work manifest is [`target.json`](target.json); what was checked upstream,
and how, is in [`sources.lock.json`](sources.lock.json).

**Since 2026-11-17: a proof beside the route.** VF-028's refusal is gone. [`proofs/prove.py`](proofs/prove.py) runs
`preservation` and `mutant-preservation` on the route's own slices (each JAR checked against the replay that ran it),
at the claim's bound, with the job's time rather than the route's ten minutes. The checker takes the unchanged
`hashpw(byte[], String)` as one function of both versions (`lib/src/bmc/ties.rs`), so the proof compares the two
conversions' bytes and not the cipher. Capped probes give `preservation` verified and `mutant-preservation` refuted at a
non-ASCII password, reproduced on a JVM. The jobs `20261117-210114-…` decide both; `example.json`'s notes say more.

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
differs from after's by an unused import and a `final`), and the commits' own Gradle builds can't resolve their
buildscript from the allowed hosts. Lookups on 2026-11-14 (HEAD requests and pinned fetches, kept as a record in
[`sources.lock.json`](sources.lock.json)'s `buildRoute`) found that plugins.gradle.org serves its plugins by a redirect
to `plugins-artifacts.gradle.org`, that at least two second-level dependencies were published only to JCenter, and that
Spring's build plugin is on no anonymous allowed repository. The user decided on 2026-11-15 that those hosts and
maven.aliyun.com's mirrors stay disallowed.

**The route: the extracted-source slice** (`preparation.slice` in `target.json`, the route 305 uses). Each commit's
`BCrypt.java` is compiled alone by javac 8 with `-g -source 1.8 -target 1.8 -encoding UTF-8`; BCrypt needs only the JDK,
so the slice has no dependency JARs. Every receipt labels the classes `extracted-source-slice`: a narrower scope than
the commits' own builds, whose blocker stays in the handoff for them.

**The check against Spring's own build.** Every preparation of `before` fetches Spring Security 5.2.0.M4's published
`spring-security-crypto` JAR from repo.spring.io/milestone by its sha256 (`8871c1fe…`) and compares its `BCrypt.class`
(sha256 `0b137406…`) with the slice's, byte for byte (`slice.matches`). A difference fails the preparation, recorded as
a blocker, and the slice is not used. A hand compile on 2026-11-14 (a note) gave the identical bytes. `after` has no
published counterpart, so its slice rests on the same recipe; the mutant is after's slice with the patch applied.

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
reaches it, and only the nullable password has been reached so far.

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
  never null, so a null password or salt is an input-construction refusal. Observed for the password by both native
  attempts ([Observed blockers](#observed-blockers)); the salt's is not reached, since the check stops at the first. The salt domain is seven fixed
  strings, stated with `String.equals` in the claim's `assume`.
- **Compared with the negative** (CVE-2025-22228, whose fix put a 72-byte guard in
  `BCrypt.hashpw(byte[],String,boolean)`, reached through `BCryptPasswordEncoder.matches`): the same conversion and the
  same cyclic 72-byte key, without the encoder, its regex check of the stored hash, or a length policy. This pair adds
  no limit: a 73-byte password hashes like its 72-byte prefix on both revisions, which the probes observe as preserved
  behaviour, not as a defect of this change.

## Observed blockers

Both native attempts (Phase 5, 2026-11-15) stopped before any proof, at the same input-construction gap: in a regression check the checker takes a `String` parameter only as non-null bounded UTF-16, and the claim's domain has a null password (VF-028, the cause VF-027 found for 306 `mutant-preservation` and 287's guard tasks). As the user decided on 2026-11-15 for VF-027, each is recorded as an observed gap, not restated: the claim and its expected conclusions are unchanged, both claims stay unresolved, and both tasks' readiness is blocked. Each packet cites its job and receipt and gives the refusal, the semantics needed, the likely owner module and the closure check. The predicted stop at the conversion (above) is still a prediction: no attempt got that far.

| Task | Refused at | Observed by job | Packet |
|---|---|---|---|
| `mutant-preservation` | a nullable `String` parameter (`password`) in a regression check | `20261115-011448-example-307-mutant-preservation-phase-5` | [`records/refusals/mutant-preservation.json`](records/refusals/mutant-preservation.json) |
| `preservation` | a nullable `String` parameter (`password`) in a regression check | `20261115-011448-example-307-preservation-phase-5-step-1` | [`records/refusals/preservation.json`](records/refusals/preservation.json) |

`python3 examples/tools/targets/workflow_refusal.py 307 TASK` reruns a task and passes only while its recorded refusal recurs under the same claim key; a verdict or another refusal fails it.
