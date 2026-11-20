# ThreeTen-Extra formats and parses negative fractional seconds

On the 20 pinned TAI instants the parent failed six exact formatting and six independent parsing cases. Every object round trip passed. The fix passed all three comparisons on every input.

At negative half a second the parent prints -1.500000000s(TAI) and reads the canonical -0.500000000s(TAI) as positive half a second. Both directions use separately supplied oracle inputs.

[Declared claims and revisions](target.json) · [Required claim bindings](milestones.json) · [Independent check](controls/table.json) · [JVM evidence](receipts/replay)
