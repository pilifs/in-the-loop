# Working draft: a downstream JBMC patch queue

**WORKING DRAFT. Not a loop brief yet: don't run it.** It is for the user to refine and weigh over time. It has no
Loop settings on purpose, and nothing here is approved. It was split out of [`sound-verdicts.md`](sound-verdicts.md)
on 2026-11-05, where it had been the last phase. That brief's Phase 5 measurements are the evidence this one waits for.

The input is [`sound-verdicts-review-jbmc.md`](sound-verdicts-review-jbmc.md), an outside review of CBMC/JBMC at
commit `8e018d0c0ef67`, read against this repository at `c4fa2f64`.

## The question

Should the project maintain a small downstream branch of JBMC, and if so, with which patches?

The review's view:
- The shared CBMC engine is actively maintained (6.11.0, August 2026). Taking it over would be a large commitment.
- Java-specific development is thin: five commits to `jbmc/src` in a year. The Java models bundle is pinned to an
  October 2022 revision with known defects.
- So the strongest case is control over **Java semantics and models**, then a few **focused encoding patches**, with
  the branch kept close to upstream.

What [`sound-verdicts.md`](sound-verdicts.md) already does without a fork:
- JBMC's own approximations (reachable stubs, the zero/null `invokedynamic` fallback) become gaps (its Phase 4c).
- Redundant interval stages, the per-check deadline and `--json-ui` are adapter work (Phase 4a, 4b).
- The models the project relies on are already its own (`lib/models`).

A fork has to earn its keep beyond all that.

## Candidate patches, in the review's order

Each would be measured on `sound-verdicts.md`'s Phase 5 corpus before and after, and dropped if it doesn't pay.

1. **Strict Java mode.** JBMC itself refuses reachable missing bodies, unapproved stubs and unsupported bootstrap
   methods, instead of the adapter detecting them from output. It makes Phase 4c's gaps native to JBMC.
2. **Model selection separated from string refinement.** Today `--refine-strings` also swaps in JBMC's Character
   replacements, which is why the project runs `--no-refine-strings`. `forDigit` ignores its radix, for example.
   Separating them would let string reasoning back in with the project's own models.
3. **One shared quotient/remainder encoding.** `a / b` and `a % b` each build a full divider today. Cache the pair by
   (dividend, divisor, width, signedness). It has to keep Java's zero-divisor exception and `MIN_VALUE / -1`. The
   review's best first performance candidate.
4. **Same-width modular multiplication without sign circuitry.** The low w bits of a product are the same signed and
   unsigned. Keep the overflow, widened, fixed-point and floating-point paths as they are.

Larger engine work, only with strong evidence from the measurements:
- array representations chosen by read/write counts, with lazy consistency constraints;
- persistent symbolic prefixes with incremental solving across paths;
- a compiled-model cache behind a worker pool;
- structural hashing of Boolean gates.

## What it would take

- **Network access** to fetch CBMC at a pinned commit, and an **ARM64 build from source** as a pipeline job. The build
  is long and heavy: estimate it before the first job.
- **A patch queue in the repository** (proposed: `lib/jbmc/patches/`), applied to the pinned commit. The resulting
  JBMC is recorded by version and patch-set digest in every attempt.
- **A standing commitment.** Each upstream release means rebasing the queue and re-running the conformance and
  benchmark corpora.
- **Upstream reports** (the `forDigit` radix bug, `--incremental-loop` not wired into JBMC's checker selection,
  unbounded trace output for nondeterministic strings) are outward-facing. They would be drafted for the user, never
  filed by an agent.

## Open questions for the user

1. Is a fork worth it at all, given `sound-verdicts.md`'s adapter work and the native engine's growing fragment? The
   Phase 5 table is meant to answer this.
2. If yes: which patches first? The review suggests strict mode and model selection for correctness, and
   quotient/remainder for performance.
3. Contribute patches upstream, keep them downstream, or both?
4. Where does the CBMC build run, and how is it cached across jobs?

## Notes

- Nothing yet.
