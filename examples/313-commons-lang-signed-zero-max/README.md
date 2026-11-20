# Commons Lang maximum distinguishes negative and positive zero

When zero is the maximum and both signs occur, the historical parent can return negative zero. The fixed revision returns positive zero.

The independent JVM oracle covered 84 inputs on each revision. parent mismatches were 0 for numeric, 7 for rawBits. fix mismatches were 0 for numeric, 0 for rawBits.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

The strict native checker proved numeric agreement on both revisions and raw-bit agreement on the fix. It refuted the parent on `[-0.0, +0.0]`. [Original-scope native checks](../../verification/results/20261120-053726-confirm-signed-zero-maxima-on-the-final/result.json)
