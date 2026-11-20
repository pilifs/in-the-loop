# Commons CSV row limits distinguish format equality

Two formats with different maxRows can read different numbers of records while the parent compares them equal.

The strict native checker decided all six original claims over the nine ordered pairs of limits. The native witness selects limits 10 and 2, which compare equal on the parent but read three and two rows. The independent grid also distinguishes limits 1 and 2. Equality is wrong for six pairs. Equal objects have equal hashes on both revisions, including every stable JVM enum identity hash. Both original parsers read one, two and three rows for limits 1, 2 and 10 by executing the real iterator and sequential collector. [Original claims and measured job](../../verification/results/20261120-083146-verify-all-csv-equality-hash-and-row-lim/result.json)

The independent JVM oracle covered 9 inputs on each revision. parent mismatches were 6 for equal, 0 for hashContract, 0 for rows. fix mismatches were 0 for equal, 0 for hashContract, 0 for rows.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)
