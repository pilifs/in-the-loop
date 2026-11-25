# Solr counts documents in multivalued enum facets

The six-document enum facet changed from empty buckets to Low 4, Medium 3, Not Available 3 and High 2. Duplicating Low on one document preserved the counts. The string-field control returned all four buckets on both sides.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. Both pins supply their changed facet classes over Solr 9.8.0 with identical core configuration. The full pin-built core could not start on the release SolrJ support graph.

Run `python3 examples/tools/build.py 407` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/apache/solr/pull/3158)
