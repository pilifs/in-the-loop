# Commons Geometry intersects a unit cube at a shared vertex

A line reaching a boundary edge or vertex can lose the first intersection with the polyhedron.

The independent JVM oracle covered 6 inputs on each revision. parent mismatches were 4 for hit, 4 for point. fix mismatches were 0 for hit, 0 for point.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

Both original geometry revisions were compiled with the same immutable Commons Numbers 1.0-beta1 dependencies. Their POM named a mutable 1.0-SNAPSHOT. The first positive intersection was calculated with rational slab intervals for each ray. The comparison permits an absolute coordinate error of 1e-10. The returned facet identities are outside the observation.

All four native checks reach `Math.sin` with input bits `0xbff921fb54442d18`, the binary64 value nearest to −π/2. These obligations remain open on this route. [Original-scope native checks](../../verification/results/20261120-053726-recheck-cube-intersections-with-linked-j/result.json)

The strict native checker proved first-hit presence and all three coordinates for the six fixed rays. Both parent claims were refuted on the diagonal from (−1, −1, −1), where the parent returned no facet and the slab oracle returns (0, 0, 0). Across the full grid four diagonal rays fail and both face controls pass. Sine and cosine cover both certified rounding choices, and the live ArrayList iterators traverse actual BSP nodes. [Four native results](../../verification/results/20261120-091739-verify-both-original-cube-repairs-throug/result.json)
