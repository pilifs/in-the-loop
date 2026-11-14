# 305: spring-boot@e8de5a6d: the Outcome enum keeps WebMvcTags.outcome's tags (positive scaffold)

[← All examples](../README.md)

**State: catalogued and source-locked, not prepared.** No build, replay or proof has run, so there is no verdict.
The work manifest is [`target.json`](target.json); what was checked upstream, and how, is in
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

All proof tasks name `--engine native --gaps strict`. Established would say one tag dimension of one entry is finite and
preserved, not that a server or release is secure. Compared with the negative (CVE-2023-34055's method label), the input
here is an `int`, not a method string.

## Preparation

The exact commits' Maven build is predicted irreproducible: both pin SNAPSHOT and milestone dependencies (Spring Data
Moore-BUILD-SNAPSHOT, Spring Framework 5.2.0.RC2 and 12 more, listed in `sources.lock.json`), which Maven Central does
not have and whose 2019 snapshots are gone. 2.2.0.RELEASE carries after's `WebMvcTags.java` unchanged; no release
carries before's. The handoff in `target.json` records this as a predicted build blocker, and the narrower scope that
stays possible.
