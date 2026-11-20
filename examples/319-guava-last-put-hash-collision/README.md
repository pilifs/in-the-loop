# Guava keeps the last put across a key collision

Two distinct String keys with equal hashes can displace a bucket entry when a later put repeats a key.

The independent JVM oracle covered 121 inputs on each revision. parent mismatches were 2 for size, 10 for lookup, 2 for entries. fix mismatches were 0 for size, 0 for lookup, 0 for entries.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

The parent first differs at length four for each observer. All 40 shorter put traces passed. At length four two traces change the size and entry set, and ten change lookup. [Minimum traces and ordered classpaths](records/finite-grid.json)
