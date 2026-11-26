# Setup for the generated callers and observers brief

Mechanical setup for [`in-the-loop-generated-observers-and-callers-brief.md`](in-the-loop-generated-observers-and-callers-brief.md).
A setup session (Claude Opus 5.5) did it on 2026-11-26, before the domain work starts.

All 13 cases of the brief's worked campaign were already prepared by earlier campaigns: deployments, source worktrees
at the pins, JDKs and the historical observers. **Nothing needed fetching.** The session:

- checked every artifact those cases name against its recorded digest, at the path the case's reader resolves, and
  checked every source worktree against its pinned commit and tree;
- re-ran on the original JVMs, read-only, the registered public observations of all 13 cases. Each fresh result
  equals the committed receipt, and each agrees with the outcome the brief states;
- extracted the second draw's original jars for successor slots 06 and 09 from their signed Ubuntu packages;
- listed each pin pair's changed production files, with git blob ids;
- rebuilt `jvmcontract`, which was older than the last `lib/src` change.

It wrote no claims, examples, sidecars, adapters, callers, recipes or library code. It allocated no example ids,
ran neither the verifier nor any prover on a claim, and did not run the product's change plan, `construct`, or any
generator: those runs are the brief's measurements. It changed no file in the repository other than this one.
**No verification job was needed.** The brief names no upstream build or upstream regression test. Its expected
outcomes are the registered public observations, and every one of those runs in seconds. The earlier setups record
the upstream test runs of these pins (links per case below).

`$G` below is `~/.cache/in-the-loop/generated-observers-and-callers` (this work, 18 MB). The other caches are the
earlier campaigns':

| Name | Path | Setup record |
|---|---|---|
| `$O` | `~/.cache/in-the-loop/spring-pr-links-o01-o20` | [O01–O20 setup](spring-framework-pr-links-o01-o20-brief-setup.md) |
| `$P` | `~/.cache/in-the-loop/spring-pr-links-p01-p30` | [P01–P30 setup](spring-framework-pr-links-p01-p30-brief-setup.md) |
| `$M` | `~/.cache/in-the-loop/merged-pr-links-m01-m10` | [M01–M10 setup](organic-java-merged-pr-links-m01-m10-brief-setup.md) |
| `$P20` | `~/.cache/in-the-loop/organic-pr-20` (`SETUP` in `verification/product-behaviour/register.py`) | [product-behaviour setup](organic-java-pr-product-behaviour-20-additional-cases-setup.md) |
| `$FF` | `~/.cache/in-the-loop/organic-composition-ff` | [fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md) |
| `$SP` | `~/.cache/in-the-loop/beyond-jbmc/scaffold-first-successor-panel` (`AREA` in `lib/benchmark/beyond-jbmc/blind/successor.py`) | [campaign setup](beyond-jbmc-java-change-verification-campaign-setup.md) |

## Starting commit

The brief was reviewed against `develop` at `32d3a22cfbae921d272649eaaae608d60ae89ecf`. This setup ran at
`4b3fe27267e8756c756730e2f17b15f262b360ee` ("Merge the single-agent run classpath-and-entry-discovery into the line"),
which has `32d3a22c…` as an ancestor (`git merge-base --is-ancestor`). The brief's "companion entry-discovery brief"
link points at a private chat library. The repository's copy is
[`in-the-loop-classpath-and-entry-discovery-brief.md`](in-the-loop-classpath-and-entry-discovery-brief.md), and its
results are merged at this head ([results](in-the-loop-classpath-and-entry-discovery-brief-results.md)).

## Layout of `$G`

| Path | What it holds |
|---|---|
| `$G/scripts/` | `check_inputs.py`, `physical_copy.py`, `io_observe.py`, `successor_copy.py` (below). Digests in `$G/logs/scripts.sha256`. |
| `$G/logs/inputs.json` | The digest and pin check of every case (below). |
| `$G/logs/replay-{445,458,466,484}.txt`, `physical-J{06,10,14,16,17,19}.txt`, `io-observe.txt`, `successor-06-09.txt` | The JVM re-runs (below). |
| `$G/logs/changed-production-files.txt`, `changed-production-files-J10-J14.txt` | `git diff --raw` of each pin pair's production sources (below). |
| `$G/logs/cargo-build.txt` | The `jvmcontract` rebuild. |
| `$G/probes/physical/J*/`, `$G/probes/io/`, `$G/probes/successor/` | Scratch copies and outputs of the re-runs. **Evaluator material**: they hold the historical observers and their actual outcomes. |
| `$G/probes/successor/packets/{06,09}/{old,new}/NNN.jar` | The original jars of successor slots 06 and 09, extracted by `successor.packet` (digests below). |
| `$G/tmp` | `TMPDIR` for this work. |

No keyring was needed (nothing was downloaded), so no `gpg` daemon was started.

## Tools

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512-b09 | `~/.sdkman/candidates/java/8.0.512.0+9-tem` (J10, J19) | `release` `b965ee876a40eb8b76e7146403b3efc54e309ebd573064a18c7b87665ce4d89e`; `jre/lib/rt.jar` `e699f968b854b98994148dac954cfb1fa78a0a7065d64e374a6d57fb463d5d5e` |
| Temurin 11.0.33+10 | `~/.sdkman/candidates/java/11.0.33.0+10-tem` | `release` `065d95ec83774b32bf27d20a827c3b934b08ca2e77e80609711c9a77e83d6681`; `lib/modules` `c08aa45bcf1a51a18faeab078421519a2198a5ae272150e276add2ee28030fae` |
| Temurin 17.0.21+9 | `~/.sdkman/candidates/java/17.0.21.0+9-tem` (458, 466, 484) | `release` `9568390645661374febde48f3c7a019f21cb116d6e4c627de29c119aa7bd0efc`; `lib/modules` `fcdfc72acc1ec5e8542fc2170c587ef23edbbdeddcbf435f169d270e02469d7c` |
| Temurin 21.0.13+9 | `~/.sdkman/candidates/java/21.0.13.0+9-tem` (445, Commons IO, J06, J16, J17) | `release` `f83f6dcc966043c93cd498ac8e7ee7c310852074970d62c702e4ad2710002898`; `lib/modules` `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c` |
| Temurin 25.0.5+8 | `~/.sdkman/candidates/java/25.0.5.0+8-tem` (J14; the successor panel's `JDK`; **the default `java` on `PATH`**) | `release` `8545053a54a73969a65db2c8157f40f89bcdcf7526ae90a7ce9b3061c01bc34a`; `lib/modules` `f5463cffa81c51b3c13f57e2c23eacceab2b12e842069acf2facd5485f63bc85` |
| `jvmcontract` release | `lib/target/release/jvmcontract` | The build of 19:39 (`0ff2ba8821339d856389eefe52c2525afc1c36c0924652c2cd21ae17c2153c70`) predated `3c448d85f941d2dbc16bda43d3ee8554fa052e91`, the last commit touching `lib/src`. `cargo build --release -j 4 --bin jvmcontract` at this head (3 min 18 s) gave `d0bcabc8fe2cc1af89d2e999c55bbc5995231a47fe8b8b3cfb91090ba8895258`. It has `construct`, `sites` and `class-bindings`. |

Every case's recorded `jdkReleaseSha256` equals the `release` digest of the JDK it names.

## Cases: inputs, pins and digests

`$G/scripts/check_inputs.py` (run as `python3 -I $G/scripts/check_inputs.py . $G/logs/inputs.json` from the
repository root) checked every case. Result: **all inputs match**.

### Numbered public comparisons (examples 445, 458, 466, 484)

The reader is `examples/tools/targets/public_comparison.py`: cache `~/.cache/in-the-loop/<runtime.cache>`, JDK
`~/.sdkman/candidates/java/<runtime.jdk>`. Every classpath entry in each `runtime.json` has a digest there, and every
digest matches.

| Brief # | Example | Cache, worktrees | JDK | Files matching | Parent commit / tree | Fix commit / tree |
|---|---|---|---|---|---|---|
| 1 | `458-spring-positive-hex` (Spring #37434) | `$O`, `worktrees/O01-{parent,fix}` | 17 | 4/4 | `2c5c6b580f90ce77973d16d24bce4c5dce00b558` / `64dae15cf57f82b20023b9e17fa6e5699ec70c58` | `3e05e8872f529c5f843e68fb6a82250349b9f019` / `59f29d64d54bc8fc5828c76ce341e7352a2ef508` |
| 2 | `445-vavr-matched-null` (Vavr #3272) | `$M`, `worktrees/M03-vavr-{parent,fix}` | 21 | 5/5 | `c6f0be585529bf16a4597b35f966439cffde894b` / `fc22de6faaf45cd2bfe92c656ab0f093dce8f5e7` | `8bd9c6b92ac07259f82ce30a09d037dfc5c78d81` / `e7b3c6a8a6452efd2e38ab6a1f18a0c2256ee5b7` |
| 12 | `466-spring-sse-retry` (Spring #37193) | `$O`, `worktrees/O09-{parent,fix}` | 17 | 21/21 | `60b9f4cd3a491a84e1dfe294005729cf49ed36e5` / `92420c69c0fa5d9f01983ed229eb4b0026b5520a` | `adbc8ceeab6e004ad8664c2ff5639449c18f2396` / `f488f59913a5ae016dce38b8945df06a5d71c9e1` |
| 13 | `484-spring-mail-date-copy` (Spring #36626) | `$P`, `worktrees/P07-{parent,fix}` | 17 | 12/12 | `e940a38014cfad78aaef39a77db128e778f2f9ae` / `1da7a0e6cb639862d0892052195263730fc700fe` | `4b0101a9dcdf7dbe1841dfc33992fa8eb27eaf2f` / `8cfb663789f3bc2165232e3f8d1fc4813c12222f` |

Each worktree is at its pin, with no tracked change. The Spring deployments are the `7.1.0-SNAPSHOT` jars the O and
P setups built at the pins (see those records for the builds). Example 458's classpath, as an illustration of the
shape: `artifacts/O01-{parent,fix}/jars/spring-core-7.1.0-SNAPSHOT.jar` (parent
`b5443b2c1d2ee7fb9edd1ff8a41652b9650fec35fdd62de7e8991243860fb57e`, fix
`244fb25bb3c97c6c5053e20c95b793399d6c17a8c12d2b3180720f949333ee55`), then `commons-logging-1.3.5.jar`
(`6d7a744e4027649fbb50895df9497d109f98c766a637062fe8d2eabbb3140ba4`) and `jspecify-1.0.1.jar`
(`070d75f261fe4c5b8202508366715f7f2d4660f88c8ef7e6d3575e48c9683b66`) from `$O/gradle-home`. The other examples'
digests are in their `runtime.json`, which `$G/logs/inputs.json` records by sha256.

### Product-behaviour cases (J06, J10, J14, J16, J17, J19)

The reader is `verification/product-behaviour/register.py` (`SETUP` = `$P20`): `bindings.json` per side, worktrees
`$P20/worktrees/<case>-<project>-{parent,fix}`. Every `physical.json` binds the current `bindings.json`, `case.json`,
`UpgradeProbe.java` and JDK release.

| Brief # | Case | JDK | Classpath matching (old / new) | Parent commit | Fix commit | How the deployment was made |
|---|---|---|---|---|---|---|
| 6 | J06 Zip4j #541 | 21 | 1/1, 1/1 | `f2e4a5a4f762dab1593f97f34c2b45d599a286cf` | `6d1678bdf03e6eafadebef9a860e74488485fe65` | pinned source build |
| 7 | J10 Kryo #530 | 8 | 5/5, 5/5 | `7a433cf0036101c6693cca6b4410454e211dbd6c` | `73540094596bef8874a48726edd0fdd014e84e45` | pinned source overlay over Kryo 4.0.2 |
| 9 | J14 Lucene #15727 | 25 | 2/2, 2/2 | `182ee9c4cc3bc52ace12e699248b750377a3aa2f` | `167503f6d84d8e43db4ec6ae3baf17337290393f` | pinned source overlay over Lucene 10.4.0 |
| 3 | J16 JGraphT #941 | 21 | 3/3, 3/3 | `c01e02903d45c82a9ecaf5c4329cdf847eb9e183` | `637503d4ebfbce3bb1ffca97348a90e856f4346e` | pinned source overlay over JGraphT 1.5.1 |
| 8 | J17 Eclipse Collections #786 | 21 | 2/2, 2/2 | `9084111e068612ebf817a3fa6fe80d9623df4c29` | `7ce7a19722e5471a71a2799737c3c2a0ed5510ff` | pinned source overlay over 10.2.0 |
| 4 | J19 Resilience4j #892 | 8 | 6/6, 6/6 | `4e564affebf280ba20880bdc8736b42f8f92234a` | `4ecc7c889cad7bfa6cb574af52252480f7e0d7cf` | pinned source overlay over 1.3.1 |

Each worktree is at its pin with the tree that `bindings.json` records, and has no tracked change. The trees are in the
[product-behaviour setup](organic-java-pr-product-behaviour-20-additional-cases-setup.md#upstream-revisions), with
the overlay construction and the upstream test runs of each case.

### Commons IO #520 (brief # 5)

The reader is `lib/benchmark/organic-composition/io/{old,new}/prepared.json`, which name absolute paths.

| Side | Commit | Tree | Jar | sha256 |
|---|---|---|---|---|
| old | `dccc7011046542e9375b6a4f90b24ca02b01a890` | `8739971752b6f238f6ac2b78decdc501dee0e61c` | `$FF/artifacts/E-commons-io-parent.jar` | `24718c09f6e0f7990a968e144be96042a20b97510b4dc611e1c97c3c3189e341` |
| new | `3e7f57784c2fa8190fb3c75c977920ba6022de66` | `0e3c864e504db0ba773198c0254794cad2ac8fc4` | `$FF/artifacts/E-commons-io-fix.jar` | `48fc79897f329de108aa4452288c86be27f76c7146e33c38bfc345b5d7885dcc` |

Worktrees `$FF/worktrees/E-commons-io-{parent,fix}` are at these pins and trees, with no tracked change. Both jars are
the complete production jar built at the pin with JDK 17 `--release 8` ([fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md)).
`prepared.json` names JDK 21 (`f83f6dcc…` above). The helper reference, `io/helper.json`, binds no artifact of its own:
it names `java.lang.Math#min(II)I` called from `CharSequenceInputStream#read([BII)I`, and the six rows.

### Successor slots 06 (CSS Parser) and 09 (Conversant stack) (brief # 11, # 10)

The reader is `lib/benchmark/beyond-jbmc/blind/successor.py`: `packet(slot)` takes each package from `$SP/<sha256>.deb`,
checks the `.deb` digest, and checks each jar it extracts against `verification/beyond-jbmc/successor/deployments/SLOT.json.gz`.
The sealed draw (`selection.json`, `draw/*.json.gz`) passed `successor.draw()`'s digest checks. The extracted jars:

| Slot | Side | Suite, package | Jar | sha256 |
|---|---|---|---|---|
| 06 | old | jammy, `libcssparser-java` 0.9.5-2 | `$G/probes/successor/packets/06/old/000.jar` (`usr/share/java/cssparser.jar`) | `2a94a6266b20ea80a7bc69394bec47a396454ac214854877339d010c089e514f` |
| 06 | old | jammy, `libsac-java` 1.3+dfsg-6 | `$G/probes/successor/packets/06/old/001.jar` (`usr/share/java/sac.jar`) | `d5f2e45a0a1affb4ddcdb59efe971aaa5aa4a25bd742bc33b3acbad95c136298` |
| 06 | new | noble, `libcssparser-java` 0.9.29-1 | `$G/probes/successor/packets/06/new/000.jar` | `5d5e091561b6ed71ed53ae0555abeea23fc9b2232cc9c9b3f9ea4cf9413faf6c` |
| 06 | new | noble, `libsac-java` 1.3+dfsg-6 | `$G/probes/successor/packets/06/new/001.jar` | `d5f2e45a0a1affb4ddcdb59efe971aaa5aa4a25bd742bc33b3acbad95c136298` |
| 09 | old | bionic, `libconversant-disruptor-java` 1.2.11-1 | `$G/probes/successor/packets/09/old/000.jar` (`usr/share/java/conversant-disruptor.jar`) | `ff91f938cde5ea002721213aa16746995d7b1a1e67a995666ad264fe1c422014` |
| 09 | new | focal, `libconversant-disruptor-java` 1.2.15-1 | `$G/probes/successor/packets/09/new/000.jar` | `75c5c0198fb173b772a0273d9c97600d1580375dfc7b972f2647246488b4cec7` |

Slot 09's deployment records `libslf4j-java` as an unavailable package on both sides, and its classpath is the one
jar. The deployment files record the signed index chain; `successor.packet(slot, dest)` rebuilds this layout anywhere.

## Changed production files

`git diff --raw --abbrev=40 PARENT FIX` over each case's production roots (`$G/logs/changed-production-files*.txt`).
Every pair changes only these files; old and new blob ids:

| Case | File | Old blob | New blob |
|---|---|---|---|
| 458 | `spring-core/src/main/java/org/springframework/util/NumberUtils.java` | `259b04f2216bacd8f0d57d4415d509d3be78ed93` | `bbd7ba5f10bfc7a1acff85e4499489f1d4ffffe1` |
| 445 | `vavr/src/main/java/io/vavr/collection/Iterator.java` | `91b119d67b9187a012e0ca0db596fab61865a8ff` | `0791102abac13edbda8b79da8150012d7fca2849` |
| 466 | `spring-web/src/main/java/org/springframework/http/codec/ServerSentEventHttpMessageReader.java` | `3966bcba7d709626ba50256cf995990a239dbe36` | `10dedd76de1fa947743a0597978d8b46248779d6` |
| 484 | `spring-context-support/src/main/java/org/springframework/mail/SimpleMailMessage.java` | `e1f8422caa0214d9be95ad2f4f3b023a8123c0ab` | `9f9fe568cd3fa605cc7ef3af422cb6d0ce5d945c` |
| IO | `src/main/java/org/apache/commons/io/input/CharSequenceInputStream.java` | `303e03578f77ee652297134982087d59e7d710fd` | `9860ada2ba3c28de28aea86e8572d3da7cc625ad` |
| J06 | `src/main/java/net/lingala/zip4j/tasks/RenameFilesTask.java` | `179d9c9026b5e2aa874657381dd257455af9b241` | `05402e44d1ad154ab8f7e3db8a106c0612166bd9` |
| J10 | `src/com/esotericsoftware/kryo/Kryo.java` | `6e899318362d21f012fd075819272cbc11f3e578` | `8b4507df5f4ee7e4695ee3760f7c6520da41a2f7` |
| J10 | `src/com/esotericsoftware/kryo/serializers/DefaultSerializers.java` | `dd5fc09b26af86e7762684e95c3741838343aeaa` | `a01fadf480a6f28a1a88caf322fc6bc50d967aaf` |
| J14 | `lucene/join/src/java/org/apache/lucene/search/join/BlockJoinSelector.java` | `1da660ffa3b7c68d9e3ae3a017e38977d82b3cdf` | `22cab53fbe2a9c8a33819e1a15a2d8946a3c2b4a` |
| J14 | `lucene/join/src/java/org/apache/lucene/search/join/ToParentBlockJoinSortField.java` | `b3d70320b6fe2e88d82ee7099a56e3857509e651` | `fa3cdaecb342b0376055b4eb76e5afda003ee487` |
| J14 | `lucene/join/src/java/org/apache/lucene/search/join/ToParentDocValues.java` | `bcf409ebbda48e0f0d4c47df445d6f53f4f5986e` | `8ba6b0e01b433deb8a8e3f03eb7bd9f226bc3e58` |
| J16 | `jgrapht-core/src/main/java/org/jgrapht/graph/AsWeightedGraph.java` | `a305ea99f10dc6a2047ffa30e194254bb8ff7501` | `fea8f065114cf01a0bf4b04e592b26c5dde8cda3` |
| J17 | `eclipse-collections/src/main/java/org/eclipse/collections/impl/map/mutable/UnifiedMap.java` | `26b21a8a199916b7cbb60ab81ea9b0acd92cade3` | `90df8584880c31aec89b0c946d7efee7edb40cc2` |
| J19 | `resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/CircuitBreaker.java` | `de1a2b7fd7955361a477ff8f0fe18941a38cec3b` | `d78e905284ce172148ac26f33762cf549adf6e47` |
| J19 | `resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine.java` | `a9b9de44934cad5472691adc0ac94bb12a4404ae` | `025edffc84897dcfb4f98576b7a8a5a95575e3a2` |

The successor slots are Ubuntu release pairs, not commits. Their source evidence is in each slot's committed
receipt (`verification/beyond-jbmc/successor/scaffolds/SLOT.json.gz`, field `basis`), from the `.orig` tarballs in `$SP`.

## What was run on a JVM

Every run below is read-only with respect to the repository (`jj diff` was empty afterwards), each under
`systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- timeout 300`, with
`TMPDIR=$G/tmp`. Each took 1–6 s.

| Cases | Command (from the repository root) | Result |
|---|---|---|
| 458, 445, 466, 484 | `PYTHONPATH=examples/tools python3 -m targets.public_comparison NNN` (no `--record`: it raises if the fresh observations differ from `observations.json`) | All four exit 0: fresh observations equal the committed receipts. (`python3 examples/tools/targets/public_comparison.py NNN` fails with `No module named 'targets'`; run it as a module, or through `build.py`.) |
| J06, J10, J14, J16, J17, J19 | `python3 -I $G/scripts/physical_copy.py . CASE $G/probes/physical`: copies the case folder and calls `register.physical()` on the copy, then compares the fresh `physical.json` with the committed one | All six equal: 6, 4, 10, 12, 4 and 6 fresh-JVM histories |
| Commons IO | `python3 -I $G/scripts/io_observe.py . $G/probes/io ~/.sdkman/candidates/java/21.0.13.0+9-tem`: compiles `io/UpgradeProbe.java` with the shared `UpgradeObservation` launcher against each prepared jar, and runs each case of `rewinds.json` and `preservation.json` in a fresh JVM, as `register.physical()` does | All 8 histories equal their registered values (old: the scope's `expected`; new: `workflows.json`'s `expectedNew`, else `expected`) |
| Successor 06, 09 | `python3 -I $G/scripts/successor_copy.py . $G/probes/successor 06 09`: points `successor.OUT` and `successor.REFS` at copies, then runs `successor.packet` and `successor.scaffold` | Both "registered on both original releases"; both receipts and both generated `ReferencePair.java` equal the committed ones |

Agreement with the brief's stated outcomes (read from the fresh outputs in `$G/logs/`):

| # | Case | What the brief says | Fresh observation |
|---|---|---|---|
| 1 | 458 | Parent rejects `+0x7f` as Integer and BigInteger; fix returns 127 in each. `-0x7f`/`+127` preserved. Fix gives `Short(128)` and rejects both Byte cases | Q1 parent `NumberFormatException NumberFormatException`, fix `Integer=127 BigInteger=127`; Q2 both `Integer=-127 BigInteger=127`; Q3 parent four exceptions, fix `Short=128 NumberFormatException Short=128 NumberFormatException` |
| 2 | 445 | Matched null: parent `(false, 99, 1)`, fix `(true, null, 0)` | Q1 (`null`) parent `false/99/1`, fix `true/null/0`; Q2 (`ordinary`, no match then an odd value) `false/99/1,true/3/0` on both; Q3 (`reorder`, registered on the fix only) fix `true/null/0,true/7/0,true/null/0,true/7/0` |
| 3 | J16 | Assertions off, uncached write-through: parent view 7, backing 9 then 11; fix rejects both, backing 2 | parent `returned/7.0/9.0|returned/7.0/11.0`, fix `UnsupportedOperationException/7.0/2.0` twice; the assertions-on and cached/local profiles as registered |
| 4 | J19 | Parent and fix differ on repeat-command exceptions; three transitions, counts `1,1,2,2,3,3`; invalid control unchanged, no event | as stated |
| 5 | Commons IO | The second rewind distinguishes `b8 ad 5a` from `c3 a9 e4` | parent third read `51b8ad5a253647`, fix `51c3a9e4253647` |
| 6 | J06 | Parent produces `dogalog` then `houndalog`; fix preserves `catalog` | as stated; directory and isolated controls equal on both |
| 7 | J10 | Fourth token `Enum.class` fails during write on the parent; fix round-trips five classes and consumes the stream | parent `write/3/java.lang.Enum/IllegalArgumentException`; fix five classes, `fully-consumed=true`; the four-token control equal |
| 8 | J17 | Equal across both releases | `127/120/0/321/127` on both sides, both orders |
| 9 | J14 | Fixed side `A/null` after the valid parent baseline refutes the filtered-child preservation prediction | filtered: parent `2=B:20,A:30`, fix `2=A:null,B:20` |
| 10 | Successor 09 | Empty peeks throw an index exception before, return null after; populated peek preserved | old rows `[0,-1,42],[1,-1,42]`, new `[0,0,42],[1,0,42]` (the reference encodes outcomes as row values; `matched/09` holds the decoded view) |
| 11 | Successor 06 | Both releases retained spelling, type and magnitude | rows `[0,1,1],[1,1,1]` on both sides |
| 12 | 466 | Parent: `WebClientResponseException` caused by `NumberFormatException` before any event; fix delivers `foo` and `bar`; trailing space still 25 ms | Q1 parent `[] error=WebClientResponseException cause=NumberFormatException`, fix `[foo@null, bar@null] complete`; Q3 `[foo@25]` on both |
| 13 | 484 | Fix preserves 1234 in message and copy; overridden-getter subclass: getter 1234, copy null, target 77 | Q1 fix `1234/1234` three times; Q3 fix `1234/null/77` |

## What was not done, and why

- No download, signature check or keyring: every input was already in a cache and checked against its recorded digest.
  The `.deb` and jar digests of the successor slots were checked by `successor.packet`; the earlier setups verified the
  signatures and publisher checksums of everything else.
- No build and no upstream test run, inline or as a job: the brief names none, and the deployments are the ones
  earlier setups built and tested at the pins. No offline build command was needed, so none was resolved or checked.
- The product's change plan (`python3 examples/tools/build.py --change-plan application --before OLD --after NEW --jdk JDK --workflows WORKFLOWS --run --output REPORT`)
  was not run; the entry exists (`examples/tools/build.py` `main`). Its run on generated bundles is the brief's measurement.

## Setup Agent Notes

### What is ready, and where

- All 13 campaign cases are prepared and checked; nothing new was fetched. Deployments, pins and readers are listed in
  [Cases: inputs, pins and digests](#cases-inputs-pins-and-digests). In short: examples 445, 458, 466 and 484 read
  `runtime.json` against `~/.cache/in-the-loop/{merged-pr-links-m01-m10,spring-pr-links-o01-o20,spring-pr-links-o01-o20,spring-pr-links-p01-p30}`;
  J06, J10, J14, J16, J17 and J19 read `bindings.json` against `~/.cache/in-the-loop/organic-pr-20`; Commons IO reads
  `lib/benchmark/organic-composition/io/{old,new}/prepared.json`, which point at
  `~/.cache/in-the-loop/organic-composition-ff/artifacts/E-commons-io-{parent,fix}.jar`; successor slots 06 and 09
  rebuild their jars with `successor.packet(slot, dest)`. A copy is already at
  `~/.cache/in-the-loop/generated-observers-and-callers/probes/successor/packets/{06,09}/{old,new}/NNN.jar` (digests in
  the [successor table](#successor-slots-06-css-parser-and-09-conversant-stack-brief--11--10)).
- Source worktrees at every pin, clean: `<cache>/worktrees/{O01,O09,P07,M03-vavr,E-commons-io}-{parent,fix}` and
  `~/.cache/in-the-loop/organic-pr-20/worktrees/<case>-<project>-{parent,fix}`.
- The changed production files of every pair, with old and new blob ids: [Changed production files](#changed-production-files).
- JDKs 8, 11, 17, 21 and 25, with `release` digests equal to every case's recorded one: [Tools](#tools). The default
  `java` on `PATH` is JDK 25; give the others by full path.
- `lib/target/release/jvmcontract` rebuilt at `4b3fe27267e8756c756730e2f17b15f262b360ee`, sha256
  `d0bcabc8fe2cc1af89d2e999c55bbc5995231a47fe8b8b3cfb91090ba8895258` (`construct`, `sites`, `class-bindings`).
  Rebuild it if `lib/src` changes again.

### What was verified on a JVM

- Every case's registered public observation was re-run on its original deployment in fresh JVMs and equals the
  committed receipt: examples 445, 458, 466, 484 (`observations.json`), J06, J10, J14, J16, J17, J19 (`physical.json`),
  Commons IO (the `rewinds` and `preservation` scopes' registered values), successor 06 and 09 (`scaffolds/SLOT.json.gz`).
- Each agrees with the outcome the brief states for it, including Spring 458's four width outcomes, Vavr's
  `false/99/1` against `true/null/0`, Lucene's fixed-side `A/null`, J19's `1,1,2,2,3,3`, and Commons IO's second rewind
  (`b8 ad 5a` on the parent, `c3 a9 e4` on the fix). The row-by-row comparison is in
  [What was run on a JVM](#what-was-run-on-a-jvm). These are the historical authored observers, not generated ones:
  the numbers are the evaluator's reference, and nothing about generation was tested.
- Commands that reproduce each check in seconds are in the same section. Run `public_comparison` as
  `PYTHONPATH=examples/tools python3 -m targets.public_comparison NNN`: the plain script path fails on its import.

### What to know before starting

- **Keep the evaluator material away from the operator.** The worked campaign's historical callers
  (`examples/NNN/caller/PublicCaller.java`, `verification/product-behaviour/cases/J*/UpgradeProbe.java` and helpers,
  `lib/benchmark/organic-composition/io/UpgradeProbe.java`, `lib/benchmark/beyond-jbmc/blind/successor/{06,09}/Reference*.java`),
  their receipts, and this setup's `~/.cache/in-the-loop/generated-observers-and-callers/probes/` and `logs/replay-*`,
  `physical-*`, `io-observe.txt`, `successor-06-09.txt` all hold callers or actual outcomes. The worktrees also hold the
  upstream tests; the brief counts their use as assisted.
- The J10, J14, J16, J17 and J19 deployments are pinned-source overlays over released jars, not full builds at the
  pin; J06 is a pinned source build. The [product-behaviour setup](organic-java-pr-product-behaviour-20-additional-cases-setup.md#summary-by-case)
  records how each was made and which upstream tests ran. Their JDKs differ: J10 and J19 are JDK 8, J14 is JDK 25.
- The Spring deployments are `7.1.0-SNAPSHOT` jars built at the pins by the O and P setups, with their dependencies in
  those caches' `gradle-home`. They are fixed bytes, digest-checked, not a snapshot resolution that can move.
- Successor slot 09's deployment lists `libslf4j-java` as unavailable on both sides; its classpath is the single
  Conversant jar.
- The brief's "companion entry-discovery brief" link is private; the repository copy is
  `llm-dlc/loops/in-the-loop-classpath-and-entry-discovery-brief.md`, and that work is merged at this head.
- No verification job was queued or is pending for this setup.

### What is left for the domain work on purpose

- Everything the brief asks to build or measure: the generator, its seam with `scaffold_example.py` and
  `register.py`, generated callers, observers, fixtures, manifests, scopes and helper tables, the
  `--scaffold-only`/resume demonstration, the planted false greens, the mutation and wrong-expectation controls,
  the isolated authorship experiment and the scorecard.
- Running the product's change plan, `jvmcontract construct`, the resource and integer-codec generators and the
  helper checker on any case.
- Choosing what goes into each operator input packet (registered meanings, changed selectors, permitted API evidence)
  and what stays with the evaluator.
- Any new example ids or registrations.
