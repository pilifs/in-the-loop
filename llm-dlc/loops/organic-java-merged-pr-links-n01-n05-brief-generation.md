# Generation record for merged Java pull requests N01–N05

| Pull request | State | Authoring inputs, outcomes and open questions |
|---|---|---|
| apache/commons-cli#450 | written | Read the two submitted commits, squashed parser change, preset control and three new regressions. The PR author reports the three failing on master and passing with the change. The author’s follow-up (PR comment 6470259241) reports the preset control passing after the rebase. Both parse bodies process properties before checking required options. The failed parse with o=discarded followed by a fresh-parser retry with o=retry is unexecuted. |
| HdrHistogram/HdrHistogram#145 | written | Read #144, the merge and its first parent, the autosizing constructor, reset, equality and the regression. Its assertions distinguish lengths 54,272 and 55,296 and put the larger receiver first. Reverse-direction equality and unequal interior counts with identical extrema and totals remain unexecuted. |
| ThreeTen/threeten-extra#463 | written | Read all eight changed paths, including the package design rules, both era conversions and both regression suites. The backward regression expects −6 months and −7 days from 20 March to 2 September. For 18 March to 1 September the independent calendar count gives −6 residual days. Its period readback and ISO epoch comparison remain unexecuted. |
| Esri/geometry-api-java#329 | written | Read #328, both submitted commits, the Java facade, restoration and both WKT orientations in the landed regression. The original observations came from .NET. Issue comment 5455650694 also reports the forward Java operator call throwing, without identifying a SHA or exception type. The Java test expects six edges on the first loop and five on the second. Java parent behavior and the ten surviving edges after extending T–A to B remain unexecuted. |
| spring-projects/spring-framework#37322 | written | Read the PR’s MySQL 9.1.0 report, both allocators, the public entry and the Mockito test. With rollback to 98 the PR reports 100/99/100 before and 99/100/101 after. The test scripts returned maxima 2/2/4. The neighboring failure after a successful commit, during auto-commit restoration, has no upstream result. Its predicted next ranges and inserted keys remain unexecuted. |

The cached GitHub responses, pinned files and landed diffs are under `~/.cache/in-the-loop/agent-tmp/ea63c5f6-1929-4c3f-9921-139ac43a8b86/n-brief/<PR number>/`. All runtime expectations described as predictions remain unexecuted.

## Final check

All five submitted PRs are accessible and appear once in input order. Reviewed the 17 rows for a public observation, an independent expectation and a specific refutation. The 30 file links resolve in the saved before/after trees. All 50 full text blobs matched their Git object IDs, including the ThreeTen release note in its declared ISO-8859-1 encoding.

Compared each landed range with the PR path list and addition/deletion counts on all 17 paths. Sixteen landed blobs equal the submitted head blobs. For HdrHistogram’s AbstractHistogram.java the target branch had other changes. The submitted and landed patches have identical added and removed lines in both PR files. Four PRs have a single-parent landing. HdrHistogram has a merge whose second parent is the submitted head.

The cache retains the PR, immutable comparison and source responses as `pr.json`, `comparison.json` and `sources.json` per case, the submitted HdrHistogram patches, and the issue/review discussions. Source review established the predictions and their limits. No runtime probe, database transaction or project build was performed.
