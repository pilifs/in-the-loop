# Three upstream defects and a PostgreSQL grammar correction

The public callers that exercised the merges also ran on the Maven releases and upstream branches checked on 2026-11-25. Each release and development run checks the original class provider and repeats the three registered histories with the historical caller bytecode. The receipts contain every return value and the hashes of the exact sources, classes and runtime dependencies. [Frozen inputs](inputs.json)

Run the following from the repository root after the campaign setup. On a fresh machine, add `--fetch` to retrieve missing public inputs. The development Cauchy distribution uses the timestamped Commons RNG snapshot from the historical setup.

```sh
python3 verification/merged-pr-links/upstream/recheck.py --campaign l01-l20 425 429 430
python3 examples/442-jsqlparser-active-alter/controls/grammar.py
```

### picocli loses its primary dispatch entry

On picocli 4.7.7 and `main` at `10509c0af89a`, register one child named `sub`, set its aliases to `"sub"`, then clear them. The model accepts both edits. The parent no longer contains the primary name, and `execute("sub")` returns 2 without invoking the child. On a fresh root it returns 0 and invokes the child once. Replacing ordinary distinct aliases still works. The same primary-name edits preserved dispatch on the historical parent.

Issue #1528 and PR #1529 concern keeping a parent's dispatch table synchronized with alias edits. The primary-name collision extends that case. A November 25 tracker search for `"primary" alias subcommand` returned no matching issue. The user can file the two-edit history against the current release. [Caller](../../../../examples/425-picocli-live-aliases/caller/PublicCaller.java) · [Release and development receipts](425.json) · [Related issue](https://github.com/remkop/picocli/issues/1528) · [Current alias implementation](https://github.com/remkop/picocli/blob/10509c0af89aa3254ca14ba90d9b3b7168e57994/src/main/java/picocli/CommandLine.java)

### JGraphT returns an edge outside the path's graph

Both Suurballe and Bhandari on JGraphT 1.5.3 and `master` at `ee3a1084f737` returned the right three vertex sequences and weights 3, 7 and 8. In the first path, the returned 3→7 edge object failed `inputGraph.containsEdge(edge)`. Looking up 3→7 by its endpoints in the input graph succeeds. The one-path control returns the original edge. The witness persists when lowering the unused 5→7 edge introduces a tie.

`GraphPath.getGraph()` identifies the containing graph and `getEdgeList()` exposes the edges traversed. Issue #790 and PR #792 address the earlier reconstruction exception. The separate membership defect survives the repair. A November 25 tracker search for `"edge" "disjoint" getEdgeList` returned no matching issue. The user can file the missing edge from the supplied graph using either algorithm. The caller contains the complete fixture and both checks. [Caller](../../../../examples/429-jgrapht-disjoint-routes/caller/PublicCaller.java) · [Release and development receipts](429.json) · [GraphPath contract](https://github.com/jgrapht/jgrapht/blob/ee3a1084f7373cf2873bcba59ee5c1b6b17ec8ad/jgrapht-core/src/main/java/org/jgrapht/GraphPath.java) · [Historical issue](https://github.com/jgrapht/jgrapht/issues/790)

### Commons Statistics overflows a representable scaled Cauchy tail

Create `CauchyDistribution.of(0, Math.scalb(1.0, -100))` and pass `Math.scalb(1.0, -1050)` to the lower and survival inverse APIs. Their reference magnitudes are approximately 2⁹⁵⁰/π, within binary64 range. The merge and `master` at `8381f56aa3ec` returned negative and positive infinity. The standardized cotangent overflows before multiplication by the small scale. The published 1.3 release predates #140 and returns approximately ±1.2883×10⁻¹⁴ for this input via the older tail formula. The merged ordinary-scale cases agreed with their numerical references and the endpoint control held.

A November 25 search of the GitHub tracker for `Cauchy overflow` returned no matching issue. The user can attach the finite scaled case to the #140 discussion or file a follow-up for the development version. [Caller and numerical tolerance](../../../../examples/430-cauchy-scaled-tails/caller/PublicCaller.java) · [Release and development receipts](430.json) · [Original change](https://github.com/apache/commons-statistics/pull/140) · [Development formula](https://github.com/apache/commons-statistics/blob/8381f56aa3eca00444b1310dd4bf0b2c739e42f4/commons-statistics-distribution/src/main/java/org/apache/commons/statistics/distribution/CauchyDistribution.java)

### JSqlParser's two reparses

The merged ALTER visitor sees only 2 on both hand-built ASTs and emits exactly one CASCADE. The PostgreSQL dialect rejects the resulting TYPE/USING statement on both stale-default inputs. PostgreSQL 16.16 independently returned syntax error 42601 for that text. Removing only CASCADE made JSqlParser round-trip the SQL and PostgreSQL change the stored integer from 1 to 103. The PostgreSQL ALTER COLUMN TYPE syntax ends with an optional USING expression. The original challenge's reparse prediction remains refuted. [Historical readbacks](../../../../examples/442-jsqlparser-active-alter/observations.json) · [Database receipt](../../../../examples/442-jsqlparser-active-alter/controls/postgres.json) · [PostgreSQL ALTER TABLE grammar](https://www.postgresql.org/docs/16/sql-altertable.html)
