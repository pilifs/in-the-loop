# Spring property names follow record metadata

A record component preserves its exact spelling. An additional getter of the same spelling has no backing field and follows bean naming. Pair one of three altered component names with one preserved record or bean accessor.

Run `python3 examples/tools/build.py 372 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)

## Recorded results

The ordinary native checker and the finite JVM each established three of the four primary obligations and refuted the parent component claim.

The preceding checker constructed the cache segments, resolved the caller’s zero-argument method, inserted the nine wrapper/primitive pairs and reached `Map.entrySet()` in `ClassUtils.<clinit>:174` on all four ordinary claims. [First startup recheck](../../verification/results/2026/11/23/20261123-011836-recheck-all-ordinary-spring-claims-after/result.json) · [Cache and writer recheck](../../verification/results/2026/11/23/20261123-024401-trace-the-four-spring-cache-and-writer-s/result.json)

The record component getWidget() and the extra getter getWidget() have identical method spellings. Only the component retained that spelling on the fix. The transplanted historical test suite failed 9 of 18 on the parent and passed all 18 on the landed artifact. [Opening job](../../verification/results/2026/11/22/20261122-162530-spring-accessor-names-on-paired-method-m/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-165839-qualified-check-record-metadata-at-the-p/result.json) · [Scorecard](../../verification/spring-java-data/spring.json)

## Historical names with a recorded lookup table

Run `python3 -B lib/benchmark/spring-java-data/metadata_lookup.py --replay` to read the six names and both public claim outcomes on each original JVM. The separate native check captures ClassUtils at startup and binds its HashMaps for string-key lookup. All three parent component selectors produced JVM-replayed native violations. The three landed component cases and all six getter controls verified. [Public replay](companions/MetadataNames.java) · [Parent selectors](records/class-utils-lookup/parent/measurement.json) · [Landed selectors](records/class-utils-lookup/landed/measurement.json) · [Managed evidence](../../verification/results/2026/11/23/20261123-030518-measure-four-spring-startup-boundaries-o/result.json)

## Ordinary class tables

Both historical JARs reach the original public calls after constructing the lookup tables from the ordinary initializer. The parent returned `""`, `"sue"` and `"widget"` for the three changed components. The fix returned `"budget"`, `"issue"` and `"getWidget"`. Each JVM returned `"widget"` for the additional getter. Run `python3 -B lib/benchmark/spring-java-data/metadata_lookup.py --ordinary --replay` to reproduce the names. [Parent proofs and counterexamples](records/ordinary-class-tables/parent/measurement.json) · [Landed proofs](records/ordinary-class-tables/landed/measurement.json) · [Four startup measurements](../../verification/results/2026/11/23/20261123-042108-bind-four-spring-startup-controls-to-the/result.json)

Each timing includes preparing the cached historical JARs, compiling and binding the callers, replaying both JVM name tables and checking six native selectors per JAR. Both routes used the same checker and artifact digests. Each produced nine proofs and three JVM-replayed violations. The first pair took **6.18 s from ordinary startup** and **19.72 s with ClassUtils recorded**. In reverse order the recorded route took **24.99 s** and the ordinary route **7.83 s**. Recording ClassUtils took 3.19× as long in both orders on this machine. [Paired trials](records/class-table-cost/measurement.json) · [Raw outcomes](records/class-table-cost/cases.tar.gz) · [Paired workflow measurements](../../verification/results/2026/11/23/20261123-042542-compare-ordinary-and-recorded-spring-met/result.json)
