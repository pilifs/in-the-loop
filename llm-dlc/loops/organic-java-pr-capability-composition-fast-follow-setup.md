# Setup for the organic Java PR capability-composition fast follow

Mechanical setup for [`organic-java-pr-capability-composition-fast-follow.md`](organic-java-pr-capability-composition-fast-follow.md),
done on 2026-11-24 by a setup session (Claude Opus 5.5) before the domain work starts. It fetched the 20 pinned upstream
revisions of cases A–I, built the production jars, ran each PR's landed test on both sides, resolved the released versions the
brief names, and reproduced the brief's JVM preflight observations on the built jars.

It wrote no claims, examples, sidecars, adapters, observers, workflows, manifests, lemma declarations or checker code, allocated
no example ids, and ran neither the project verifier nor JBMC on anything. The small Java programs under `$O/probes/` only
reproduce the brief's stated preflight observations; they are setup checks, not the case's caller artifacts. Everything
fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/organic-composition-ff`. `$M` is `~/.cache/in-the-loop/git-mirrors`. JDKs are
Temurin under `~/.sdkman/candidates/java/`: `$J8` = `8.0.512.0+9-tem`, `$J11` = `11.0.33.0+10-tem`, `$J17` =
`17.0.21.0+9-tem`, `$J21` = `21.0.13.0+9-tem`. **The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

*(In progress: sections are filled in as the setup proceeds.)*

## Starting commit

- Checkout at setup: `da56af5745f8727ff505d9b98281408861371a57` ("Record the brief queue's handover"), after the Beyond
  JBMC landing `4547213152` ("Merge the single-agent run beyond-jbmc-java-change-verification-cam into the line").
- The brief's planning baseline `96d1883e78d65f01507240f122108d8f1c668437` is an ancestor. `lib/` tree at setup
  `d7159867d97c4cd918cd73119d51094de9149d6d`, at the baseline `d08a6ab533d23456820af7004b8c9a6911b2a17d`: they differ.
  `git diff --stat 96d1883e HEAD -- lib/src examples/tools/targets lib/benchmark/domain-foundations` shows 34 files,
  1721 insertions, 265 deletions. Reading what changed is left to the domain work (the brief's "Starting point").

## Jobs

Queued with this record (`$O/scripts/submit_jobs.py` wrote them):

| Job | Subject |
|---|---|
| `20261124-134447-setup-build-apache-poi-s-poi-module-at-b` | B: `:poi:jar` at both revisions, `TestDataFormatter` own and transplanted |
| `20261124-134447-setup-build-icu4j-core-at-both-3249-revi` | D: ICU4J `main/core` at both revisions, RBBI tests own and transplanted |
| `20261124-134447-setup-build-log4j-core-at-both-1173-revi` | G: `log4j-core-test -am` at both revisions, `PatternProcessorTest` own and transplanted |
