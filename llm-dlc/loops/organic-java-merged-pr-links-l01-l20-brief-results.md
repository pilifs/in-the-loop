# Twenty merged Java changes at their public APIs, L01–L20

The twenty examples register all **60 questions** from the brief. **55 of 60 merged-behavior predictions held** on the specified inputs. All 20 controls matched on both sides. Nineteen intent predictions held in full. JGraphT produced the expected routes and weights, but returned an edge object outside the original graph. The other four refutations were the picocli, JGraphT, Commons Statistics and JSqlParser challenges. [Original brief](organic-java-merged-pr-links-l01-l20-brief.md) · [Question and deployment audit](../../verification/merged-pr-links/l01-l20/audit.json)

A pass runs **136 fresh caller JVMs over 23 deployment pairs**. Both Arrow allocator backends, both Guava artifacts and both Quartz databases run separately. Nineteen parent-to-merge intent histories differed. The 127×127 Commons Imaging comparisons ran on the corrected decoder, with the 264×264 control on both sides. The Gradle comparison runs the exact changed method on one published distribution, as described below. Each verdict concerns these executions. [Setup and upstream regression evidence](organic-java-merged-pr-links-l01-l20-brief-setup.md)

| Case | What the public caller established |
|---|---|
| [L01 · Gson](../../examples/423-gson-roundtrip-keys/README.md) | Equal numeric keys created and parsed through different paths now retrieve the same map entry. Signed-zero replacement and removal leave the map empty. |
| [L02 · Commons Collections](../../examples/424-multiset-view-removal/README.md) | Both distinct views now remove the full multiplicity. Reinsertions, the other view, the array and the backing size agree. |
| [L03 · picocli](../../examples/425-picocli-live-aliases/README.md) | Ordinary alias updates repair dispatch. Accepting the primary name as an alias and clearing it removes the primary entry. |
| [L04 · java-diff-utils](../../examples/426-diff-utils-equal-lines/README.md) | Explicit and implicit equal deltas produce the same complete formatted rows, including both decorated boundaries. |
| [L05 · JUnit Jupiter](../../examples/427-jupiter-nested-reselection/README.md) | Both same-named test bodies ran on class selection. Each saved unique ID reran its own declaring class and no other body. |
| [L06 · Arrow](../../examples/428-arrow-listview-intervals/README.md) | Both allocators now expose [3,5) and [40,50]. Relocation to offset zero preserves the element hash. |
| [L07 · JGraphT](../../examples/429-jgrapht-disjoint-routes/README.md) | Both algorithms return weights 3, 7 and 8. The 3→7 edge object in their first path is absent from the input graph in both three-route fixtures. |
| [L08 · Commons Statistics](../../examples/430-cauchy-scaled-tails/README.md) | The ordinary tail plateau disappears. Scaling a subnormal probability case with a finite real answer still produces infinities. |
| [L09 · RDF4J](../../examples/431-rdf4j-empty-groups/README.md) | Explicit grouping returns zero rows on an empty match and implicit MAX returns one unbound row. A matching triple makes the outer join return exactly a and b. |
| [L10 · Calcite](../../examples/432-calcite-set-multiplicities/README.md) | With the transpose rule enabled in the JDBC planner, the two duplicate fixtures produce EXCEPT/INTERSECT counts 2/1 and 0/3. |
| [L11 · Commons Imaging](../../examples/433-imaging-edge-pixels/README.md) | The fixed full decode meets all pixel tolerances and the six bottom-right ARGB values agree exactly with the region decode. |
| [L12 · Quartz](../../examples/434-quartz-trigger-replacement/README.md) | On Derby and PostgreSQL, the parent reports CRON with extension counts 1/0. On the merge the scheduler and persisted rows agree after both type changes, including the similarly named trigger in another group. |
| [L13 · Maven Shade](../../examples/435-shade-relocated-services/README.md) | A real offline plugin invocation changes from a duplicate-descriptor error to one descriptor containing two providers. Both input orders pass isolated ServiceLoader instantiation. |
| [L14 · Iceberg](../../examples/436-iceberg-binary-delete-keys/README.md) | The parent’s Parquet scan returned 200, 201 and 203 after deleting keys A–C. The merge returned only 203 and preserved the independent nested binary snapshot. |
| [L15 · Gradle](../../examples/437-gradle-named-actions/README.md) | Both action forms left A behind on the parent method and wrote B on the fixed method. The unchanged repeat skipped correctly. |
| [L16 · Guava](../../examples/438-guava-future-registration/README.md) | The completed input’s registration count dropped from one to zero. The ordinary and reentrant completions kept the input ordering in both editions on JDK 21. |
| [L17 · ical4j](../../examples/439-ical4j-zoned-exdates/README.md) | An exception at a UTC occurrence start now removes the Paris instance. The shift to summer time distinguishes the 07:00Z and 08:00Z exceptions. |
| [L18 · RxJava](../../examples/440-rxjava-group-cancellation/README.md) | Cancellation now releases the stalled suffix, while a survivor with demand for one waits for its next request before receiving 5–8. |
| [L19 · Kafka Streams](../../examples/441-kafka-final-sessions/README.md) | The stream admits A at the inclusive boundary and emits only the merged final count. Every raw and suppressed output, including tombstones, is retained. |
| [L20 · JSqlParser](../../examples/442-jsqlparser-active-alter/README.md) | Both ASTs visit only 2 and emit one CASCADE. Their PostgreSQL reparses reject the suffix. Removing it is accepted by the parser and by PostgreSQL itself. |

## Interpreting the five refutations

Picocli and JGraphT reproduced on their latest published releases and development branches as checked on 2026-11-25. The Cauchy overflow reproduced on the merged and development implementations. Its latest release predates the formula change and gives a different wrong finite result. These three reports await the user's filing decision. The two JGraphT refutations share one cause. [Reports, exact versions and reproductions](../../verification/merged-pr-links/l01-l20/upstream/README.md)

The remaining refutation corrects the brief. PostgreSQL's ALTER COLUMN TYPE syntax permits USING, and gives CASCADE to other ALTER forms. PostgreSQL 16.16 returned 42601 on the emitted TYPE statement with CASCADE. Removing it allowed the stored value to change from 1 to 103. Both the successful deparser observations and the original falsified prediction are preserved. [Database receipt](../../examples/442-jsqlparser-active-alter/controls/postgres.json) · [PostgreSQL syntax](https://www.postgresql.org/docs/16/sql-altertable.html)

## Deployment and replay

Use `python3 examples/tools/build.py --plan 434` for a registration and `python3 examples/tools/build.py 434` to repeat both database variants. The campaign audit checks the brief’s question IDs, histories, expectations, source pins, dependency and caller digests, exact receipt coverage and verdicts offline. An independent replay additionally executes every caller. [Audit](../../verification/merged-pr-links/audit.py) · [Runtime locks and deployment examples](../../examples/434-quartz-trigger-replacement/runtime.json)

```sh
python3 verification/merged-pr-links/audit.py --campaign l01-l20
python3 verification/merged-pr-links/upstream/recheck.py --campaign l01-l20 425 429 430
```

Gradle's original grolifant 0.16.1 JAR was recovered from a public JCenter mirror. Its SHA-256 is exactly the value in both Git pins. Gradle 7.5.1 resolved it under each original strict verification policy in a fresh offline cache. The registered L15 comparison compiles each pin’s original implementation and installs the changed named-action method into one verified 7.6 distribution. The same histories were also run on released 7.5.1 and 7.6. A separate job builds both complete historical distributions in a disposable checkout and compares their class digests, task outcomes and file bytes. [Strict input checks](../../examples/437-gradle-named-actions/setup/strict-resolution.json) · [Released distributions](../../examples/437-gradle-named-actions/setup/release-histories.json) · [Full pin-build job](../../verification/jobs/2026/11/25/20261125-184502-build-both-complete-gradle-pins-with-the.json)

Shade runs the actual pin-built Maven goal with release-8 fixture classes and an offline dependency repository. Kafka’s original setup omitted the test-driver JAR. The domain setup rebuilt all seven driver sources from each exact revision against that revision’s locked runtime. Those two driver JARs were byte-identical and all six Kafka histories reproduced. [Shade observer](../../examples/435-shade-relocated-services/caller/PublicCaller.java) · [Kafka driver build](../../examples/441-kafka-final-sessions/setup/prepare.py)

The independent pipeline checks cover the 136-JVM matrix, the eighteen release and development histories plus PostgreSQL grammar, and 24 debugger trials at three original methods. A retained probe has already qualified JGraphT’s original method twice per side on the tie history. [Matrix repeat](../../verification/jobs/2026/11/25/20261125-183811-replay-60-l-series-java-questions-on-23.json) · [Upstream and grammar repeat](../../verification/jobs/2026/11/25/20261125-183812-repeat-three-l-series-upstream-defects-a.json) · [Method-entry repeat](../../verification/jobs/2026/11/25/20261125-183812-qualify-l-series-alias-graph-and-probabi.json) · [Retained debugger evidence](../../verification/merged-pr-links/entry-receipts/429-pins.json)

All 20 examples passed their normal replay validators. The first slice passed its 54 selected suites, and the completed campaign passed all 56 selected suites. Negative checks rejected a missing observation, a falsified verdict, reversed revision pins, the later Central grolifant JAR, and a modified cached Gradle installation. The preceding 61-question campaign's audit totals and its original jOOλ release and development receipts also reproduced through the shared tools.
