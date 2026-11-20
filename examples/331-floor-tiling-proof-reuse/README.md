# Floor tiling counts and two dependent callers

Exact counts and parity share a helper. A changed base case and a discarded two-cell choice exercise both dependents.

The independent JVM oracle covered 19 inputs on each revision. recursive mismatches were 0 for exact, 0 for parity. iterative mismatches were 0 for exact, 0 for parity. one-tile mismatches were 17 for exact, 6 for parity. base-change mismatches were 18 for exact, 13 for parity.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

The oracle sums binomial coefficients. It gives 4,181 tilings of length 18. Dropping the two-cell choice first fails at length 2. The benchmark compares two consumers on the same compiled caller and captures cold and warm results when the helper's base case changes.

At the same 25-second budget the first recursive exact check took 24.257 seconds inlined and 2.001 seconds with the bounded helper proof. Parity took 17.749 and 1.914 seconds. Changing the helper's base case kept the callers byte-identical and invalidated the helper proof. Both recursive caller tasks now use the checked lemma on 0 through 18. [Measurements and 24 raw checks](records/reuse/comparison.json)
