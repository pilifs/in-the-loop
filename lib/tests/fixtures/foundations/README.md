# The joint example of the foundations loop

The fixture of [`llm-dlc/loops/foundations.md`](../../../../llm-dlc/loops/foundations.md)'s Phase 5, fixed in its
Phase 0 so that the four streams build towards the same target. [`lib/tests/foundations.rs`](../../foundations.rs)
checks each stream's part against it, and `llm-dlc/tools/foundations-integration.sh` runs that test on a merge of the
streams while they work. [`lib/tests/compare.rs`](../../compare.rs) runs the four parts together, as `jvmcontract compare`
does, and holds the result to each row of Phase 5's table.

**The change.** A small pricing kernel behind one thin, real annotated entry point (`POST /quotes`, which returns the
total and sends a `QuoteEvent` on the `quotes` topic when the total is positive). The refactor from `before/` to
`after/` turns the primitive amount of `Quote` into a value object, `Money`, and rewrites the pure helper
`Pricing.discount`. The external request's meaning (`cents`, `quantity`) and the required observations (response,
exception, status, the event) stay fixed.

**The defects** (`defects/NAME/`, each overlaid on `after/`: its files replace theirs). Each is aimed at an automation
layer that could make it disappear:

| Defect | What it does | What must catch it |
|---|---|---|
| `offset` | a cent too much per item | no inferred mapping may shift the anchored input (`before.cents = after.cents + 1` would hide it) |
| `alias-to-copy` | `withQuantity` hands back a copy with the same values, for every quantity (made for one item, then given the quantity, so that the constructor's refusal doesn't tell them apart) | the identity relation `result == q`, compared within each version |
| `dropped-effect` | no event for 100 items or more | the effect trace |
| `duplicated-effect` | two events for a bulk order | the effect trace, in exact order |
| `outside-domain` | wrong only for a quantity the constructor rejects | the result's domain label: proved over constructor-made quotes, and nothing claimed beyond |
| `route-change` | the route is renamed | the obligation is changed, not proved, without approval; a cached result for the old route is not reused |

`POST /quotes/text` builds a string by concatenation, which this loop doesn't support: it stays visibly unresolved.

**Checked on a real JVM** (2026-11-07, JDK 25.0.5): over a grid of amounts and quantities, `before` and `after` give
the same responses and send the same events; each defect differs from `after` exactly where its row says, and
`outside-domain` not at all through the constructor. The `alias-to-copy` copy first went through the constructor with the new quantity, and so threw where `after` doesn't, for a quantity below 1; it was changed by the reconcile loop, and rechecked the same day on 270 cases (six amounts, five quantities the constructor accepts, and nine new quantities from `Integer.MIN_VALUE` to `Integer.MAX_VALUE`): every field agrees with `after`'s, and `result == q` holds in none of them.

**The golden files** (`golden/`) are the joint example's IR in the shared types of `lib/src/spec/`: the entry point's
preservation contract and claim, the kernel's contract, domain, correspondence and claim, the environment model, an
outcome, a hints file, and `expected.json`, the verdict every case must reach. A stream may add to them; changing what
one says is a note for the reconcile loop.
