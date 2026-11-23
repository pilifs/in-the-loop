# JGraphT public graph histories and edge identity

The target is JGraphT 1.5.2 on three distinct labeled vertices. The automatic generator tries the six ordered non-self pairs after at most three successful public insertions in canonical order. Each attempt starts with a fresh graph. An independently compiled auditor checks transitive closure and every existing edge and endpoint identity. The separate supplied builder uses explicit DefaultEdge instances.

Run the ordinary identity replay with `python3 examples/tools/build.py 399 --task replay`. To repeat the complete original-JVM holdout, run `python3 lib/benchmark/receiver-discovery/holdout.py --checker lib/target/release/jvmcontract --jvm-only --output "$TMPDIR/jgrapht"`.
