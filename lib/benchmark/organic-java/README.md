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

To rebuild the original library, submit `upstream.py NNN --maven-cache PATH --output PATH` as a verification job. Set `TMPDIR` under `~/.cache/in-the-loop/` and give all jobs the same Maven cache outside the checkout. `--repos PATH` optionally supplies existing Git mirrors named for the upstream projects. For Guava, use `--jdk26 PATH` for the pinned compiler. The build records both revision identities and the original production class digest before transplanting only the landed test source on the parent. After obtaining both build records, `upstream.py NNN --bind-existing --output PATH` binds the example to them. [Guava compiler distribution](temurin26.json)

The baseline runner checks the pinned source fingerprint and executable digest. If working on a later revision, it exports the baseline tree from the project's Git repository. A retained historical binary can be supplied using `ORGANIC_BASELINE_BINARY`, and a repository containing the historical source can be supplied using `ORGANIC_SOURCE_REPOSITORY`. Repeat runs with `run.py NNN --stage NAME --route native` or `--route finite` as verification jobs. Use a fresh stage name to preserve the first observation. The Commons Lang full-domain fixed proof also uses the normal `--native-selectors` route. [Baseline identity](baseline.json)
