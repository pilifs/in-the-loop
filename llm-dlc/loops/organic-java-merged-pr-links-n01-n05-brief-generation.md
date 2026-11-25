# Generation record for merged Java pull requests N01–N05

| Pull request | State | Authoring inputs, outcomes and open questions |
|---|---|---|
| apache/commons-cli#450 | written | Read the two submitted commits, squashed parser change, preset control and three new regressions. The PR author reports the three failing on master and passing with the change. Both parse bodies process properties before checking required options. The failed parse with o=discarded followed by a fresh-parser retry with o=retry is unexecuted. |
| HdrHistogram/HdrHistogram#145 | written | Read #144, the merge and its first parent, the autosizing constructor, reset, equality and the regression. Its assertions distinguish lengths 54,272 and 55,296 and put the larger receiver first. Reverse-direction equality and unequal interior counts with identical extrema and totals remain unexecuted. |
| ThreeTen/threeten-extra#463 | written | Read all eight changed paths, including the package design rules, both era conversions and both regression suites. The backward regression expects −6 months and −7 days from 20 March to 2 September. For 18 March to 1 September the independent calendar count gives −6 residual days. Its period readback and ISO epoch comparison remain unexecuted. |
| Esri/geometry-api-java#329 | not yet | — |
| spring-projects/spring-framework#37322 | not yet | — |

The cached GitHub responses, pinned files and landed diffs are under `~/.cache/in-the-loop/agent-tmp/ea63c5f6-1929-4c3f-9921-139ac43a8b86/n-brief/<PR number>/`. All runtime expectations described as predictions remain unexecuted.
