# Joda-Time distances between leap-year MonthDay values

Resolving partial dates against a nonleap reference year loses leap day or throws while converting it.

Ten additional native claims bind the DateTimeZone and DateTimeUtils startup states on JDK 21.0.13. They produced eight proofs and two independently replayed counterexamples. From March 1 to February 29 the parent throws IllegalFieldValueException where the signed distance should be −1. The fixed revision returns the oracle’s value on all 25 pairs. Reversal holds on the 16 pairs where both parent calls return and all 25 on the fix. [Ten qualified partial-date outcomes](../../verification/results/20261120-100118-verify-all-partial-date-claims-through-b/result.json) · [Parent signed-distance witness](../../examples/327-joda-monthday-distance/receipts/days-parent-observed/executions/20261120T100703Z-b214ddc0/replay.json)

The independent JVM oracle covered 25 inputs on each revision. parent mismatches were 9 for normal, 17 for days, 0 for reversal. fix mismatches were 0 for normal, 0 for days, 0 for reversal.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

Two further claims execute both actual directional calls in their Java guard, then test reversal only where both returned. The earlier implication covering all 25 input pairs remains in history.

All ten strict native checks reach System.getProperty("org.joda.time.DateTimeZone.Provider") in DateTimeZone.getDefaultProvider while the historical classes initialize. The provider choice remains open on that route. The independent 25-pair JVM results retain their original ISO-UTC chronology. [First provider diagnostic](../../verification/results/20261120-063346-verify-partial-dates-past-the-shared-lis/result.json) · [Repeated on the reader checker](../../verification/results/20261120-081743-recheck-both-partial-date-revisions-alon/result.json)
