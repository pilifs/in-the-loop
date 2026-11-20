# Commons Math fraction percentages across integer overflow

Multiplying a numerator by 100 in its integer representation changes the percentage near the signed 32-bit boundary.

The independent JVM oracle covered 13 inputs on each revision. parent mismatches were 4 for bits, 0 for normal. fix mismatches were 0 for bits, 0 for normal.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

The numerical checker’s earlier six native checks stopped at the static initializer for `Fraction`. The independent JVM grid supplies the percentage results at the overflow boundary. [Original-scope native checks](../../verification/results/20261120-053726-recheck-fraction-percentages-on-the-fina/result.json)

Following the fourteen static Fraction constants and their reachable constructors let the strict checker decide all six original claims. The parent has four wrong raw percentages among 13 inputs. Both revisions complete normally and preserve the three small controls. [Verification job](../../verification/results/20261120-063347-repeat-fraction-overflow-checks-on-the-s/result.json)
