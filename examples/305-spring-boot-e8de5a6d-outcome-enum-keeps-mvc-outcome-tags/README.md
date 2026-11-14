# 305: spring-boot@e8de5a6d: the Outcome enum keeps WebMvcTags.outcome's tags (positive scaffold)

[← All examples](../README.md)

**State: a partial scaffold, its slice jobs queued.** Source-locked, with its claims frozen and its oracle, driver,
probes and mutant written ([the packet](#the-packet)). It is prepared by the source-slice route (below), whose three
replay jobs are queued: until they pass, no replay has run through the pipeline, so there is no verdict. The work
manifest is [`target.json`](target.json); what was checked upstream, and how, is in
[`sources.lock.json`](sources.lock.json).

## The change

[e8de5a6d](https://github.com/spring-projects/spring-boot/commit/e8de5a6d95ffb45cd532c2a863e6a726e159b7e3) (2019-09-05,
[gh-18150](https://github.com/spring-projects/spring-boot/issues/18150)), parent `9b8decf9`, adds the enum
`org.springframework.boot.actuate.metrics.http.Outcome`, six constants each caching `Tag.of("outcome", name())`, and
rewrites the MVC entry:

```java
// before: HttpStatus.Series.resolve(response.getStatus()) and a switch over five cached tags, else OUTCOME_UNKNOWN
// after:
Outcome outcome = (response != null) ? Outcome.forStatus(response.getStatus()) : Outcome.UNKNOWN;
return outcome.asTag();
```

Only `WebMvcTags.outcome(HttpServletResponse)` is selected. The patch's eight files also change the RestTemplate,
WebClient and WebFlux tag factories and remove a client exception catch: none of that is claimed here. Upstream's new
`OutcomeTests` document the intended ranges; they are provenance, not proof evidence.

## The claims

| Task | Kind | Expected | What it says |
|---|---|---|---|
| `replay` | replay, both revisions | (controls) | Each revision's original JAR in its own JVM on JDK 21 and 25, over null and the statuses 99, 100, 199, 200, 299, 300, 399, 400, 499, 500, 599, 600, `Integer.MIN_VALUE`, `Integer.MAX_VALUE` |
| `preservation` | equivalence | established | Same tag key and value, and the same specified exceptions, for a null response or any `int` status; object identity excluded on purpose (the patch moves allocation and caching) |
| `finite-outcome-before`, `finite-outcome-after` | prove, one revision each | established | The tag's key is `outcome` and its value one of INFORMATIONAL, SUCCESS, REDIRECTION, CLIENT_ERROR, SERVER_ERROR, UNKNOWN |
| `mutant-replay` | replay, the `mutation` pair | (controls) | `after` against the constructed mutant (the revision `mutant`, `after` with the patch applied), with the same driver, probes and oracle: `after` holds, the mutant fails at status 200 alone (INFORMATIONAL for SUCCESS) |
| `mutant-preservation` | equivalence, the `mutation` pair | refuted | `preservation`'s claim file and domain, unchanged, over `after` and the mutant: the mutation control |

All proof tasks name `--engine native --gaps strict`. Established would say one tag dimension of one entry is finite and
preserved, not that a server or release is secure. Compared with the negative (CVE-2023-34055's method label), the input
here is an `int`, not a method string.

## Preparation

The exact commits' Maven build is predicted irreproducible: both pin SNAPSHOT and milestone dependencies (Spring Data
Moore-BUILD-SNAPSHOT, Spring Framework 5.2.0.RC2 and 12 more, listed in `sources.lock.json`), which Maven Central does
not have and whose 2019 snapshots are gone. The handoff in `target.json` keeps that as a predicted build blocker.

The user's decision of 2026-11-14 is the narrower **source-slice route**, a separately labelled scope
(`extracted-source-slice` in every receipt):
- each commit's `WebMvcTags.java` (and after's `Outcome.java`) is taken from its checkout and compiled alone by JDK 8,
  with `-g -parameters -source 1.8 -target 1.8 -encoding UTF-8`;
- it is compiled against Framework 5.2.0.RC2's spring-web, spring-webmvc and spring-core (with spring-jcl), from
  repo.spring.io/milestone, and micrometer-core 1.2.0 and javax.servlet-api 4.0.1, from Central, each pinned by
  sha256. spring-webmvc and spring-core weren't named in the decision, but `WebMvcTags` needs them to compile.
- Boot 2.2.0.M6 (`fb75cbbc`) carries after's two files unchanged, so its published spring-boot-actuator JAR is the
  revision `release-m6`. The task `m6-replay` replays it beside the after slice, and the two must show the same
  observations (a `correspondence` pair).
- A hand compile (a note, in `sources.lock.json`) found the after slice's `WebMvcTags.class` and `Outcome.class`
  byte-identical to M6's published ones. So after's slice is Spring's own build of those sources. Before has no
  published counterpart, so its slice is checked only by the same recipe.

A claim about the slices is about these classes. It reaches the commits' own builds only through such a
correspondence: for after there is one (M6), for before there is none.

## The packet

| File | What it is |
|---|---|
| [`claims/outcome-preservation.json`](claims/outcome-preservation.json) | The frozen claim of `preservation`: a null response or a carrier whose `getStatus()` returns any `int`; the tag's key and value (by value, never identity) and the exception observed; `unwind` 16, which leaves the domain unbounded |
| [`claims/finite-outcome.json`](claims/finite-outcome.json) | The claim `finite-outcome-before` and `finite-outcome-after` share: key `outcome`, one of the six values, nothing thrown, over the same domain |
| [`replay/probes.json`](replay/probes.json) | 27 probes: the brief's 15, then negative statuses that test the old path's truncating division, and codes past 599 |
| [`controls/oracle.py`](controls/oracle.py) | The independent oracle: the HTTP status class read from the status's decimal spelling (RFC 9110, section 15), unlike either revision's division or ranges; it checks each revision's lines and the revisions against each other |
| [`replay/driver`](replay/driver/inloop/p305/OutcomeDriver.java) | The driver: one JSON line per probe, the response a `Proxy` carrier whose `getStatus()` returns the probe and whose other methods throw, with its `getStatus()` call count as an annotation |
| [`controls/status-200.patch`](controls/status-200.patch) | The mutant: after's `Outcome.forStatus` with `status < 200` turned into `status <= 200`, so 200 is INFORMATIONAL. It must fail the oracle and the preservation claim at 200, and only there |
| [`sources.lock.json`](sources.lock.json) | The commits' source blob ids, the slice's six pinned JARs (`sliceDependencies`), and M6's published JAR and class hashes with the byte-identical slice compile |
| [`records/outcome-gaps.json`](records/outcome-gaps.json) | A static `jvmcontract gaps` scan, run by hand (a note): `Pattern.compile` in `WebMvcTags.<clinit>` and `Objects.requireNonNull` in micrometer's `ImmutableTag.<init>`, on both sides, so every strict attempt is predicted to be refused |

A hand replay (a note, in `example.json`) found before and after agreeing with the oracle and with each other on every
probe, on JDK 21 and 25, and the mutant failing at 200 only. Before's side was compiled from its source, since no
artifact carries it.

The 200-boundary mutant satisfies the finite-outcome property by design: it still gives one of the six values. That
property bounds the label set and can't see a misclassification; the mutant's failing contract is the preservation claim
and the oracle's range statement.

## What a proof needs

Requirements read from the source at both commits, and from the static scan; each is a prediction until an attempt
reaches it.

- **The enum.** After classifies through `Outcome.forStatus(int)`, an enum's static method: five range tests, no loop.
  Before resolves `HttpStatus.Series` by dividing by 100 and searching `Series.values()` (an array clone and a five-step
  loop), then switches over the series through the compiler's switch map, the synthetic `WebMvcTags$1`.
- **Tag.** Both revisions build their tags with micrometer's `Tag.of(String, String)`, an interface's static method that
  returns an `ImmutableTag`, whose constructor calls `Objects.requireNonNull` twice: a JDK method with no approximation,
  so a refusal under strict gaps. Observing the result needs `getKey()` and `getValue()` through the `Tag` interface.
- **Class initialization.** Each side's tags exist only after an initializer runs: before's `WebMvcTags.<clinit>` (six
  outcome tags) and `WebMvcTags$1`'s with `HttpStatus.Series`'s; after's `Outcome.<clinit>` (six constants, each
  calling `Tag.of`). Both sides' `WebMvcTags.<clinit>` also compiles two regular expressions, which `outcome()` never
  uses but its class initialization runs: `Pattern.compile` is outside the checker. The initializer is never removed to
  get past it.
- **The response interface.** The parameter is `javax.servlet`'s `HttpServletResponse`, a library interface with about
  forty methods, of which each revision calls only `getStatus()`, once. The checker dispatches `invokeinterface` only to
  application methods, so a non-null response is predicted to be an input-construction refusal; the claim's domain is
  never narrowed to the null response to get past it.
- **Compared with the negative** (CVE-2023-34055's method label): the input is one `int`, all 2^32 values, with no loop
  that depends on it, against the negative's request method `String`, an unbounded sequence that needs a length bound
  and String semantics. So this positive's arithmetic is the easy part, and what stops it is the surrounding structure
  (initializers, a library interface, a library value class), the structure the two families share.
