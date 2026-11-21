# Two disclosed BUMP screening cases

| Client upgrade | Archived CI before and after | Maintainer decision |
|---|---|---|
| FSCrawler, Apache POI OOXML 4.1.2 → 5.1.0 | The original build passed. In the upgraded Tika module, two document tests received null content. The ordinary DOCX test expected text containing “This is a sample text available in page”. | Treat the change as a document-indexing regression on this runtime closure. Align the POI components, then rerun the ordinary DOCX and text assertions before accepting the upgrade. |
| AssertJ Guava, AssertJ Core 3.22.0 → 3.23.0 | All 355 original tests passed. On the new revision Maven Enforcer rejected `net.bytebuddy:byte-buddy:jar:1.12.10` before Surefire. | Review whether to admit that compile dependency under the client’s build policy. Exclude this pair from behavioral scoring. |

Both pairs changed only `pom.xml`. The BUMP registry disclosed both, so neither enters the scored or transfer sets. The evidence comes from the images named by the two pinned BUMP records. The original logs report Maven’s own build status. The image entry command pipes Maven output to `tee`, so a container process exit alone cannot certify that tests passed. [Paired revisions and pinned OCI descriptors](oci-lock.json) · [Historical CI lines with offsets and log hashes](historical.json)

### FSCrawler

The rejected upgrade left `poi` and `poi-scratchpad` at 4.1.2 alongside `poi-ooxml` 5.1.0 and `poi-ooxml-lite` 5.1.0. The archived test JVM recorded the order of 159 classpath entries, including 152 JARs. In 4.1.2, `POITextExtractor` is an abstract class and `POIXMLTextExtractor` extends it. In 5.1.0 the OOXML extractor is an interface extending `POITextExtractor`. The mixed classes cannot link. FSCrawler caught the extraction failure and left `Doc.getContent()` null for the ordinary document.

The breaking log names `TikaDocParserTest.testExtractFromDocx` and `testDocxWithEmbeddedBadPDF`. The run reported 24 tests in two Tika suites, two failures and one ignored assumption. The archived pre build reports the same suite count and one ignored assumption, followed by success. Its log lacks per-method pass lines. The targeted local replay uses the unmodified ordinary DOCX method and `testExtractFromTxt`, with the same two ordinary fixtures supplied to `TikaDocParser.generate` for an independent content observation. [Upstream dependency change](https://github.com/dadoonet/fscrawler/pull/1296) · [FSCrawler original assertions](https://github.com/dadoonet/fscrawler/blob/097d93fbb2f9998ef1390ad10f92d1b70fda8b90/tika/src/test/java/fr/pilato/elasticsearch/crawler/fs/tika/TikaDocParserTest.java#L194) · [Targeted replay job](../../../../../verification/jobs/20261121-001305-replay-fscrawler-ordinary-docx-across-th.json)

### AssertJ Guava

The Enforcer execution `enforce-java-and-dependencies` bans compile-scope JARs and allows the declared AssertJ Core dependency. Core 3.23.0 introduced its non-optional compile dependency on Byte Buddy. The historical breaking log identifies `org.apache.maven.plugins.enforcer.BannedDependencies` and Byte Buddy 1.12.10. It contains no executed new-side application testcase. The pre run completed all 355 tests with zero skipped, failures or errors. [Upstream dependency change](https://github.com/assertj/assertj-guava/pull/98) · [Client Enforcer rule](https://github.com/assertj/assertj-guava/blob/0968864d08e0fce1e5e1caaf89afddd2cc1b2569/pom.xml#L97) · [Full lifecycle replay job](../../../../../verification/jobs/20261121-000727-replay-bump-assertj-guava-enforcer-on-bo.json)

The independent networkless rerun reproduced all 355 passing tests on the pre revision in 28.2 seconds. On the breaking revision Maven exited 1 after 5.1 seconds with the same rule and artifact, before any Surefire totals. [Independent full-build outcomes](assertj-replay.json) · [Job receipt](../../../../../verification/results/20261121-000727-replay-bump-assertj-guava-enforcer-on-bo/result.json)

### Reproducing the evidence

The two images per client use the same Alpine Linux and JDK/Maven runtime layers. The archived FSCrawler fork bootstrap and AssertJ Surefire XML identify Alpine OpenJDK 11.0.19+7-alpine-r1. The isolated runtime itself reports Apache Maven 3.9.2. The original pre/upgrade subject sources come from the two Git revisions in the lock; it records the complete image manifests, which layers were actually acquired, byte sizes, digests, and image entry commands. [BUMP FSCrawler record](https://github.com/chains-project/bump/blob/324d5513aa5ca40b5cb32de5b816a58fa60bd7bb/data/benchmark/097d93fbb2f9998ef1390ad10f92d1b70fda8b90.json) · [BUMP AssertJ Guava record](https://github.com/chains-project/bump/blob/324d5513aa5ca40b5cb32de5b816a58fa60bd7bb/data/benchmark/0968864d08e0fce1e5e1caaf89afddd2cc1b2569.json)

For an offline reproduction, put the four final blobs under their `localLayer` names, the first two shared blobs under `common-alpine.tgz` and `common-jdk-maven.tgz`, and Git databases containing the listed source commits under `fscrawler.git` and `assertj.git` in `$INPUTS`. The first command below only inspects the archived historical outputs. The two Maven replays are verification jobs. They use a read-only runtime, a private writable checkout, a separate per-image Maven repository and a networkless unprivileged namespace. From this directory run:

```sh
python3 -I inspect_evidence.py "$INPUTS" --output "$OUT/historical.json"
python3 -I replay.py fscrawler --inputs "$INPUTS" --output "$OUT/fscrawler.json"
python3 -I replay.py assertj --inputs "$INPUTS" --output "$OUT/assertj.json"
```

The shared cache contains 1,374 distinct archived Central artifacts from these four public images, 529 JARs and 845 POMs. Each entry had a Central-origin marker and a matching retained SHA-1. The importer records a fresh SHA-256 and accepts regular release files at Maven repository paths. A writable run can take a private copy of its `repository/`. To build the shared cache from a verified final layer, run `python3 -I import_cache.py LAYER SHA256 DIRECTORY`. [Cache counts and provenance](maven-cache.json)
