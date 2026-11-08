# The fixtures of the application-core loop

The three small fixture families of [`llm-dlc/loops/application-core.md`](../../../../llm-dlc/loops/application-core.md),
frozen in its Phase 0 (step 5), before any stream forked, with the claims they are checked under and the verdict each
case must reach. Their semantics are fixed now, not after seeing which proof succeeds: a stream doesn't change what
a case must reach, and a change to one is a note for the main brief's reconcile. The families are the
[acceptance contract](../../../../llm-dlc/loops/application-core-acceptance.md#small-fixture-families)'s Q, H and L.
[`lib/tests/application_core.rs`](../../application_core.rs) checks each row against them, and
`llm-dlc/tools/application-core-integration.sh` runs it on the merge of the streams while they work.

Each family has `before/` and `after/`, each a complete source tree, and `defects/NAME/`, each overlaid on `after/`:
its files replace theirs. A defect's changed lines are marked `// DEFECT:`.

## Q: the quote service (`quote/`, package `quotes`)

`QuoteService` is an ordinary receiver holding a fee policy (`feeCents`, `floorCents`) and three dependencies:
`Rates`, a read-only query whose `rate(code)` may throw the checked `RateUnavailable`; `Offers`, whose `find(code)`
returns a nullable `Offer` DTO; and `Events`, which is sent a `QuoteEvent` with its code and amount. A
`QuoteRequest` carries a String code and an array of quantities. `quote` asks for the code's rate (-1 without one),
adds the fee from the helper `fee(lines)`, which reads the receiver's policy and halves it for more than two lines,
takes a tenth off for a VIP code (`Codes.vip`), and announces a positive quote. `offerQuote` uses the standing offer
instead, never below the floor. `checked` hands back the caller's own request once it has a line.

The refactor from `before/` to `after/` keeps the external meaning of request, response and event: it reads the
request's parts once, extracts `subtotal`, inverts the event's branch, rewrites `fee` and `units` and `checked`'s
test, and rewrites `Codes.vip` with `length` and `charAt` in place of `startsWith`.

| Defect | What it does | Row |
|---|---|---|
| `wrong-query-key` | asks for the standard rate, whatever the code | E1 |
| `ignored-rate` | asks for the rate, then uses 100 | E1 |
| `missing-catch` | lets `RateUnavailable` propagate (`quote` now declares it) | E1, VF-015 |
| `wrong-branch-event` | announces a quote of 0 too | E1 |
| `wrong-prefix` | `Codes.vip` takes `VI` for `VIP` | V1 |
| `helper-extra-field` | `fee` also reads `floorCents` for more than two lines | R2 |
| `alias-to-copy` | `checked` hands back a copy | O2 |

## H: the throttle (`throttle/`, package `throttle`)

`Throttle(capacity)` rejects a capacity below 1. The setup call `take(n)` takes up to what is left; the target
`allows(n)` says whether n more fit. The refactor computes what is left instead of the sum, which can't overflow.

| Defect | What it does | Row |
|---|---|---|
| `after-setup` | one unit short once a call has taken some: the same right after construction | O3 |
| `one-short` | one unit short from the start | O1 |

## L: the basket (`basket/`, package `basket`)

`Basket`'s kernels take an immutable list of `Line`s (`List.of`, `List.copyOf`; no nulls, any two elements may be
one object): `total` adds every line, a line twice counting twice; `first` hands back the first line itself, or
null; `clearAll` clears every line's quantity and returns what it cleared, an element given twice cleared once. The
refactor walks the list by index.

| Defect | What it does | Row |
|---|---|---|
| `duplicate-skipped` | `total` counts a line given twice in a row once | V2 |
| `last-not-first` | `first` hands back the last line | V2 |
| `copied-first` | `first` hands back a copy of the first line | V2 (identity) |
| `alias-blind` | `clearAll` reads two lines before clearing either: one object given twice counts twice | V2 (aliases) |

## The claims and the verdicts (`golden/`)

Each `NAME-claim.json` is a canonical claim (`lib/src/spec/`) with a planned domain (`spec::plans`): the
construction plan of each version, the String and list domains with their bounds, and for Q the environment model
(`Rates.rate` a query keyed by its code, returning a long or throwing `RateUnavailable`; `Offers.find` a fresh
`Offer` or null; `Events.send` the recorded effect). The two throttle claims are different domains: right after the
constructor, and after one `take`. `expected.json` names every build's verdict under every claim, and under the
plain regression checks (`regressions`) that rows O1, V1, V2 and R2 reach first. Its parts that the checks don't
compute yet (`closures`, `tools`) say "computed by cache::key".

**Checked on a real JVM** (2026-11-08, JDK 25.0.5), with
[`Conformance.java`](Conformance.java), which loads each build in its own class loader and gives every build the
same dependency stubs: `after` agrees with `before` on every case of the grid (30,240 for Q, over fees, floors,
codes including an isolated surrogate, quantities including overflowing ones, five rate tables with and without
`RateUnavailable`, and three offers; 315 for H; 43 for L), and each defect differs exactly in the methods its
expectations name. `after-setup` never differs right after construction. Rerun it with
`java Conformance.java FAMILY CLASSES` over the compiled builds (`CLASSES/NAME`).
