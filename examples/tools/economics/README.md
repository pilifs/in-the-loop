# The economics changes

The changes [`economics.py`](../economics.py) makes to each javac app whose recorded examples the proof cache serves,
one of each kind: what a rerun costs after a change once proofs are kept. Each is a patch from the repository's root,
applied to the app alone (not one on top of another). The cache serves only the B9 examples the tool's own checker
proves (`--engine native`), which are on Crosscut and Mica, so Quorum has none.

Each change is checked two ways:
- **rebased**: each served example with the change beneath it, on both sides, so that its claim is the example's
  own, on changed code. Where the example's patch touches the lines the change does, it doesn't apply, and the
  example is listed as not rebased.
- **own**: the change itself, on the served examples' targets, with each example's domain and settings.

`jvmcontract impact` on the app and the app with the change names the own claims below as invalidated, and every
other one as unchanged.

| Change | What it does | Claims it reaches (own) | What it should show |
|---|---|---|---|
| [`crosscut-unrelated`](crosscut-unrelated.patch) | `Backoff`'s constructor message reworded: bytecode no served claim reads | none | the rebased claims are exact hits; the own ones have nothing to prove |
| [`crosscut-helper-rewrite`](crosscut-helper-rewrite.patch) | `TokenBucket.lastAfter` computes the credited time as whole periods past the last credit, behaviour kept on every input | `RetryAfter#nanosUntilToken` | the first claim proves the helper and shares it; the second (example 161's domain, the same bounds) finds its proof in the cache |
| [`crosscut-representation`](crosscut-representation.patch) | `RetryAfter` waits for the part of the period not yet credited, its own helper, instead of the credited time from `TokenBucket.lastAfter` | `RetryAfter#nanosUntilToken` | proved again with no helper shared: a helper whose result is only related to the old one stays as written |
| [`crosscut-regression`](crosscut-regression.patch) | `TokenBucket.tokensAfter` rounds the tokens earned up, crediting a token before its period is over | `TokenBucket#tokensAfter`, `RetryAfter#nanosUntilToken` | refuted, with a witness that replays |
| [`mica-unrelated`](mica-unrelated.patch) | `SymbolTable.tableSizeFor` with `Integer.numberOfLeadingZeros`, as `HashMap` does it | none | as for Crosscut's |
| [`mica-helper-rewrite`](mica-helper-rewrite.patch) | `LookupSwitch.midpoint` halves the unsigned sum by a division: the same on every `int` (and not trivial, so it is offered for a proof) | `LookupSwitch#find` | the first claim proves the helper; the second, with the same bounds, finds its proof; the third (example 145's array bound of 12) proves it again, since a helper's check has its caller's bounds and so another claim |
| [`mica-representation`](mica-representation.patch) | `find` takes the midpoint as `low` plus half the distance to `high`, a helper of another meaning | `LookupSwitch#find` | proved again with no helper shared |
| [`mica-regression`](mica-regression.patch) | `ModifiedUtf8.encodeInto` writes U+07FF in three bytes, not two | `ModifiedUtf8#encodeInto` | refuted, with a witness that replays |

Checked inline when written: both helper rewrites' own proofs hold over every input, in 0.06 s (`midpoint`) and
0.22 s (`lastAfter`) of checker time. `economics.py --plan` builds every tree and lists the claims without proving
anything.

`report.md` and `report.json` here are what the last run of `economics.py` measured, written by its pipeline job.
