# Replaying the organic Java pull requests

The corpus contains six historical parent/fix pairs and two conditional transfer cases. Each example supplies a public Java driver, a separately written oracle, frozen claims and a target recipe. The subject JVM is Temurin 21.0.13. The original build can use a different compiler. [Revisions and test selectors](cases.json) · [Campaign results](../../../llm-dlc/loops/organic-java-pr-campaign-results.md)

To inspect saved results offline, run these commands from the checkout root.

```sh
python3 lib/benchmark/organic-java/domains.py --check
python3 lib/benchmark/organic-java/report.py --check
python3 examples/tools/build.py --plan 353
python3 examples/tools/targets/workflow_handoff.py handoff 353 --markdown
```

The `records` folder in each example contains original Maven build and Surefire records, plus the first native and finite attempts and later reruns. Receipts record original JAR hashes, production-class bytes, the ordered runtime classpath, the JDK and the verifier. For Avro, that classpath includes the Hadoop client supplied by the host. The same target recipes support this repository's ordinary `build.py NNN --task replay` and queued native, native-selector and finite-domain jobs.

A receipt retains the size and SHA-256 of a large JVM stream plus its first 512 KiB. For a public finite grid that exceeds it, `public_observations.py NNN` repeats the same original JVM controls, checks every byte against that receipt and retains whole JSON rows in small text files. The scorecard joins and validates these files before counting a grid.

The scorecard links the latest fixed-side Commons Lang and Eclipse selector proofs directly to the collector archives. The normal selector evidence reader checks the archive manifest and the raw results for all 1,515 windows and 2,865 insertions.

Avro has separate tasks for ambient startup and JVM-preinitialized state. The `*-writable-startup` tasks initialize `org.apache.avro.Schema` and `org.apache.hadoop.io.BytesWritable` in one JVM, in that order. The `bounds-fix-factory-startup` task adds `org.apache.hadoop.mapred.JobConf` as the third root. Each claim pins the common state digest and sets `observedRuntime` to `{"processors":2,"emptyEnvironment":true,"rootWorkingDirectory":true,"preinitializeTogether":true}`. The subject JVM checks the process settings, while the native checker binds the original classes and shared static fields before running the public entry. The earlier single-class observations are retained under their own task names.

The `bounds-fix-registry-startup` claim enables `weakMapValues` on the same three roots. The JVM checks that every existing value of the exact weak map is null. Collection can remove keys while preserving this fact. The `bounds-fix-credentials-startup` claim also initializes Hadoop's `Credentials` as a fourth root before running the same factory. Each observation has its own state digest.

The eight `*-lookup-startup` tasks use those four roots and request the atomic deprecation context, its application receiver, the Commons Collections map wrappers, and the backing String-key tables. The checker binds each application's class bytes and field layout. Lookup preserves collisions, missing keys and present null values. Both original classpaths produced the same 220-class, 1,079-object state.

To reproduce the public factory run, queue the registered job steps on the pinned verifier. The first step checks bounds, excluded absolute reads, prefix contents and the full-length control on both revisions. The next two steps independently replay the factory counterexamples at their original entries. The final two check the nested converter and its original witness. [Job specification](../../../verification/jobs/20261121-155347-prove-the-original-avro-factory-and-repl.json)

To repeat the direct converter comparison, queue the first command below as a verification job. Run the witness review after the normal workflow has produced a matching native refutation.

```sh
python3 examples/tools/build.py 355 --tasks direct-limit-parent-writable-startup,direct-limit-fix-writable-startup
python3 examples/tools/build.py 355 --original-witness direct-limit-parent --from-task direct-limit-parent-writable-startup
```

To rebuild the original library, submit `upstream.py NNN --maven-cache PATH --output PATH` as a verification job. Set `TMPDIR` under `~/.cache/in-the-loop/` and give all jobs the same Maven cache outside the checkout. `--repos PATH` optionally supplies existing Git mirrors named for the upstream projects. For Guava, use `--jdk26 PATH` for the pinned compiler. The build records both revision identities and the original production class digest before transplanting only the landed test source on the parent. After obtaining both build records, `upstream.py NNN --bind-existing --output PATH` binds the example to them. [Guava compiler distribution](temurin26.json)

The baseline runner checks the pinned source fingerprint and executable digest. The fingerprint covers an inventory of inputs that the pin names (`inputs`; a pin without the key is inventory 1, read as it always was): inventory 2, for a new baseline, adds `lib/python`, where the proof output reader and the array-induction method are, and `verification/layout.py`, which the example tools load. A frozen run exports the paths of the pin's own inventory, so an old revision exports as before ([`test_run.py`](test_run.py)). If working on a later revision, it exports the baseline tree from the project's Git repository. A retained historical binary can be supplied using `ORGANIC_BASELINE_BINARY`, and a repository containing the historical source can be supplied using `ORGANIC_SOURCE_REPOSITORY`. Repeat runs with `run.py NNN --stage NAME --route native` or `--route finite` as verification jobs. Use a fresh stage name to preserve the first observation. The Commons Lang full-domain fixed proof also uses the normal `--native-selectors` route. [Baseline identity](baseline.json)
