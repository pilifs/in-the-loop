# Joda-Time distances between leap-year MonthDay values

Resolving partial dates against a nonleap reference year loses leap day or throws while converting it.

The independent JVM oracle covered 25 inputs on each revision. parent mismatches were 9 for normal, 17 for days, 0 for reversal. fix mismatches were 0 for normal, 0 for days, 0 for reversal.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

Two further claims execute both actual directional calls in their Java guard, then test reversal only where both returned. The earlier implication covering all 25 input pairs remains in history.

All ten strict native checks reach System.getProperty("org.joda.time.DateTimeZone.Provider") in DateTimeZone.getDefaultProvider while the historical classes initialize. The provider choice remains open on that route. The independent 25-pair JVM results retain their original ISO-UTC chronology. [First provider diagnostic](../../verification/results/20261120-063346-verify-partial-dates-past-the-shared-lis/result.json) · [Repeated on the reader checker](../../verification/results/20261120-081743-recheck-both-partial-date-revisions-alon/result.json)
