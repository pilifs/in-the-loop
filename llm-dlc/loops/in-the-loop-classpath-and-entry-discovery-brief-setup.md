# Setup for the class-path and entry-discovery brief

Mechanical setup for [`in-the-loop-classpath-and-entry-discovery-brief.md`](in-the-loop-classpath-and-entry-discovery-brief.md).
A setup session (Claude Opus 5.5) did it on 2026-11-26, before the domain work starts. The brief builds on inputs
that earlier campaigns prepared: Log4j #1173, Parquet J08, the scaffold-first release panel, the Java semantics-gap
graphs and examples 312, 323 and 333. Little needed fetching. The session:

- checked every artifact those inputs name against its recorded digest, at the path the product or campaign
  script reads;
- chained the release panel's 480 packet jars back to signed Ubuntu indexes and extracted each brief slot's
  original `/usr/share/java` layout;
- fetched the one new upstream input, the OpenJDK `ClassPath.java` manifest fixture at `jdk-21+35`, and
  reproduced its JVM behaviour;
- re-ran on JDK 21 the original-JVM observations the brief relies on for Log4j and J08;
- validated the three reused examples;
- rebuilt `jvmcontract` at this head.

It wrote no claims, examples, sidecars, adapters, recipes or library code. It allocated no example ids and ran neither
the verifier nor any prover on a claim. It did not run the product's change plan, resource discovery or binding path
on any input: those runs are the brief's measurements. **No verification job was needed.** The brief names no upstream
build. The one landed regression it relies on (Log4j `PatternProcessorTest`) already has a passed job at both pins
(below). Every check here took seconds, except the example validations (about 3 minutes each) and the `cargo build`
(3 minutes).

`$B` below is `~/.cache/in-the-loop/classpath-entry-discovery` (this work). `$O` is
`~/.cache/in-the-loop/organic-composition-ff` ([fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md)).
`$P20` is `~/.cache/in-the-loop/organic-pr-20` ([product-behaviour setup](organic-java-pr-product-behaviour-20-additional-cases-setup.md)).
`$BJ` is `~/.cache/in-the-loop/beyond-jbmc` ([campaign setup](beyond-jbmc-java-change-verification-campaign-setup.md)).
`$SG` is `~/.cache/in-the-loop/jbmc-java-semantics-gap` ([semantics-gap setup](jbmc-java-semantics-gap-brief-setup.md)).
`$J21` is Temurin 21.0.13+9, `~/.sdkman/candidates/java/21.0.13.0+9-tem/bin`. **The default `java` on `PATH` is JDK
25.0.5**, so give JDK 21 by its full path.

## Starting commit

The brief was reviewed against `develop` at `00800750fc71d393f9c1dc837d387fc5a9adcf4a`. This setup ran at
`84737ea19bd88de62e203232f9e2fd98a66029cd` ("Merge the single-agent run organic-java-merged-pr-links-r01-r50-brief
into the line"), which has `00800750` as an ancestor.

## Layout

| Path | What it holds |
|---|---|
| `$B/src/openjdk-jdk-21+35-paths` | Sparse detached worktree of `test/langtools/tools/javac/Paths/` at OpenJDK `jdk-21+35` ([below](#openjdk-manifest-fixture)). Mirror `~/.cache/in-the-loop/git-mirrors/jdk21u.git`, ref `refs/pinned/jdk-21+35-paths`. |
| `$B/layouts/SLOT/{old,new}/root/usr/share/{java,maven-repo}` | The packaged layout of panel slots 03, 04, 08, 10, 13, 15 and 16, extracted from their verified `.deb`s with files and symlinks as packaged ([below](#original-layouts)). 109 MB. |
| `$B/probes/log4j/`, `$B/probes/j08/`, `$B/probes/openjdk-classpath-21/` | Throwaway JVM programs and their outputs ([below](#what-was-run-on-a-jvm)). Not claims, adapters or drivers. |
| `$B/scripts/` | `digest_refs.py`, `verify_panel.py`, `extract_layouts.sh`, `openjdk_classpath_fixture.sh`, `j08_physical.py`. Digests in `$B/logs/scripts.sha256`. |
| `$B/keys/ubuntu-archive-keyring.gpg`, `$B/gnupg` | A copy of the system's Ubuntu archive keyring (sha256 `80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31`) and this setup's own home for `gpgv`. No daemon is running. |
| `$B/logs/` | Every result below, and `cache-jar-index.sha256` (sha256 of all 13,112 jars and zips in `$O`, `$P20`, `$BJ` and `$SG`). |
| `$B/tmp` | `TMPDIR` for this work (left empty). |

## Tools

| Tool | Where | Identity |
|---|---|---|
| Temurin 21.0.13+9 | `~/.sdkman/candidates/java/21.0.13.0+9-tem` | `release` sha256 `f83f6dcc966043c93cd498ac8e7ee7c310852074970d62c702e4ad2710002898` (= `jdkReleaseSha256` in the Log4j and J08 manifests); `lib/modules` `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c` (= the semantics-gap and trusted-kernel setups, and `jdkSha256` in `origins.json`) |
| Temurin 25.0.5+8 | `~/.sdkman/candidates/java/25.0.5.0+8-tem` (the default `java`; `history.py` `JDK` for the release panel) | `lib/modules` `f5463cffa81c51b3c13f57e2c23eacceab2b12e842069acf2facd5485f63bc85` (= campaign setup) |
| Temurin 17.0.21+9 | `~/.sdkman/candidates/java/17.0.21.0+9-tem` | `lib/modules` `fcdfc72acc1ec5e8542fc2170c587ef23edbbdeddcbf435f169d270e02469d7c` (= fast-follow setup) |
| Temurin 11.0.33+10 | `~/.sdkman/candidates/java/11.0.33.0+10-tem` | `lib/modules` `c08aa45bcf1a51a18faeab078421519a2198a5ae272150e276add2ee28030fae` (= fast-follow setup) |
| Temurin 8u512-b09 | `~/.sdkman/candidates/java/8.0.512.0+9-tem` (Log4j's Maven runs on it) | `jre/lib/rt.jar` `e699f968b854b98994148dac954cfb1fa78a0a7065d64e374a6d57fb463d5d5e` |
| `jvmcontract` release | `lib/target/release/jvmcontract` | Was stale (built 2026-11-25). `cargo build --release --bin jvmcontract` at this head (3 min) gave `0ff2ba8821339d856389eefe52c2525afc1c36c0924652c2cd21ae17c2153c70`. It has `class-bindings`. |
| `dpkg-deb`, `gpgv`, `xz` | `/usr/bin` | system |

## Inputs: digests at the paths their readers use

`$B/scripts/digest_refs.py` collected every `(file, sha256)` pair in the inputs' JSON. Each was then checked at the
path its reader resolves.

| Input | Reader's base | Result |
|---|---|---|
| Log4j `lib/benchmark/organic-composition/log4j/{old,new}/prepared.json` | absolute paths into `$O/artifacts` | 4/4 match. Worktrees `$O/worktrees/G-logging-log4j2-{parent,fix}` are at the pinned commit and tree (table below). |
| J08 `verification/product-behaviour/cases/J08/bindings.json` (113 entries a side) | `$P20` | 114/114 distinct files match. `bindings.json` `c430cdff49f562b82e508e8c05506a56b4cf2f82f36374b060147a7ee2f5d810`, `case.json` `176cca47f57cbfff0e5f3b68dec13b05996fd747d5c92a295a7772fca6784830` and `UpgradeProbe.java` `c4015a819a0c07d6a4bddbabfc17935cc084c0802777db09cf0e850bbbab747b` equal the digests in `physical.json`. Worktrees `$P20/worktrees/J08-parquet-java-{parent,fix}` are clean at the pins. |
| Java semantics gap `verification/java-semantics-gap/heap-and-gson/origins.json` | `$SG` (`campaign.CACHE`) | 21 graphs, 283 class bindings. 17/17 distinct jars match at `$SG/artifacts/…`. Each graph also has one `adapter` entry, which `origins.py` compiles at run time. The jar entries equal `lib/benchmark/java-semantics-gap/classpaths.json` (`$B/logs/origins-inputs.txt`). |
| Scaffold-first records `verification/beyond-jbmc/scaffold-first/**.json` | repository and `$BJ/panel/evaluation` | 372/372 committed output archives match `jobs.json` (= `audit.json` `outputDigests`). 387/387 jar references were found by digest under `$BJ/panel/evaluation`. The remaining references are receipts, logs and streams inside those archives. |
| Release panel packets, slots 01–16 | `$BJ/panel/evaluation/SLOT/packet` | `scaffold_first.registered(slot)`, the campaign's own locked-input check, passes for all 16 (`$B/logs/panel-packets.txt`, which also lists every jar's manifest `Class-Path`) |

| Pin | Commit | Tree |
|---|---|---|
| Log4j parent | `e325de9abf771a4501bae7cd7910fcbce31f5663` | `c2ace3b75ab10944e6f21c1de36a8c8a6f1e7492` |
| Log4j fix | `7107cd655380d81dea72df930a832e598173971e` | `7b506a6963f271fd3897f41b30aa2a02869af9a5` |
| Parquet J08 parent | `5c360ff5d879d3567f23cea3290894712fb336d9` | `fdca60b7968396b96ac09362e2a90ccfc0064036` |
| Parquet J08 fix | `5e14d7cd43403a95d331be8791e8792dbf38683d` | `4005c46207142ab7b0c19de2711fc2114e0414e4` |
| OpenJDK `jdk-21+35` | `890adb6410dab4606a4f26a942aed02fb2f55387` (tag object `07687d169a5e181789869817f10f3e8a4a4c30a9`) | `b9ed4cfe56716a7e3b4649f98ed41d528fe8e2eb` |

The Log4j jars (2.19.1-SNAPSHOT, built by job `20261124-141323-setup-build-log4j-core-at-both-1173-revi`):

| Jar | sha256 |
|---|---|
| `$O/artifacts/G-logging-log4j2-parent-log4j-api.jar` and `…-fix-log4j-api.jar` (byte-identical) | `c9d2f400916a5346816deff5309f725069804a810e7d0492294d931a391d7582` |
| `$O/artifacts/G-logging-log4j2-parent-log4j-core.jar` | `da05ae3790513bb74285ce65a37e9b06829b82d9af2939df826a815176802b6f` |
| `$O/artifacts/G-logging-log4j2-fix-log4j-core.jar` | `c98f9f1dad7d5e81f893838971083cabe252e454c3568c11db0f47e4f3df9b60` |

## Release panel: signed chain

`$B/scripts/verify_panel.py` checks the chain InRelease → Packages index → `.deb` → jar at `graphs.json`'s `source` →
packet jar (`$B/logs/panel-chain.json`, sha256 `49991ff32a87724b32fad518d429a1412e75198eacc55f77129e07d2fd3cec48`).

- **InRelease.** `gpgv` with `$B/keys/ubuntu-archive-keyring.gpg` gives a good signature on `$BJ/panel/{jammy,noble,resolute}/InRelease`,
  from "Ubuntu Archive Automatic Signing Key (2018)", key `F6ECB3762474EDA9D21B7022871920D1991BC93C`. The signatures
  are dated 2022-04-21, 2024-04-25 and 2026-04-23.
- **Indexes.** Each cached `Packages.xz` has the digest its InRelease lists. **Resolute's universe index is not in the
  cache**: `seal_panel.py` took it from apt, and so did this check. `/var/lib/apt/lists/archive.ubuntu.com_ubuntu_dists_resolute_universe_binary-amd64_Packages`
  has sha256 `9c009342905706a05822f6e751f5b1ac34b687f054bfca9a0a652178445fc44c`, the digest the cached resolute
  InRelease lists. That InRelease is byte-identical to apt's. The check fails for resolute-universe packages if apt's
  copy changes.
- **Debs and jars.** 200/200 `.deb` digests match both their index and the file `$BJ/panel/SHA256.deb`. 480/480 packet
  jars (both sides of all 16 slots) are byte-identical to the file at their `source` path inside their `.deb`.

Command: `python3 -I $B/scripts/verify_panel.py $BJ/panel $B/tmp OUT.json resolute=/var/lib/apt/lists/archive.ubuntu.com_ubuntu_dists_resolute_universe_binary-amd64_Packages`
(about 1 minute).

## Original layouts

Each slot's `graphs.json` (`$BJ/panel/evaluation/SLOT/graphs.json`) records the captured layout for each side: the
suite, the packages with their `.deb` digests, and for each ordered entry its neutral `path` (`old/000.jar`), its
`source` in the package (`usr/share/java/…`), its package, and its `manifestClassPath`. It also records
`unresolvedManifestPaths`, `matchingBasenameOnOrderedClasspath` and `nonJavaOrUnresolvedDepends`. The packets use the
neutral names only.

`$B/scripts/extract_layouts.sh $BJ/panel $B/layouts SLOT…` extracts `usr/share/java` and `usr/share/maven-repo`, as
packaged, from every `.deb` of a side. Every ordered entry of the seven slots resolves inside its side's root to a
file with the recorded digest, following the package's own relative symlinks. No symlink is absolute
(`$B/logs/layout-check.txt`). The inventories are in `$B/logs/layouts-files.sha256` (1,483 files, sha256
`785c4bb9ad5ee2a550ad8a526aba963ee66dc53c93f08cba7178b0e483a35c4a`) and `$B/logs/layouts-symlinks.txt` (1,333 links,
`da86217ce073114e98ed066a19becd0cdb58308790b88c4ddf6cab0118e072ab`).

| Slot | Suites old → new | Entries old/new | Manifest edges old/new | Unresolved old/new | Basename matches old |
|---|---|---|---|---|---|
| 03 Sisu Plexus | noble → resolute | 19/20 | 3/3 | 0/0 | 0 |
| 04 Batik | noble → resolute | 53/39 | 240/186 | 33/1 | 22 |
| 08 ISCWT | noble → resolute | 6/6 | 10/10 | 1/1 (`usr/share/java/rt.jar`) | 0 |
| 10 HtmlCleaner | jammy → noble | 3/3 | 1/1 | 0/0 | 0 |
| 13 OpenCensus | noble → resolute | 136/138 | 38/38 | 0/0 | 0 |
| 15 Annotation Indexer | noble → resolute | 1/1 | 0/0 | 0/0 | 0 |
| 16 dom4j | jammy → noble | 2/2 | 0/0 | 0/0 | 0 |

Every manifest edge in these slots is absolute (`/usr/share/java/…`) except 108 of Batik's old edges and one of
ISCWT's (`rt.jar`). This machine's own `/usr/share/java` holds only `com.microsoft.z3.jar`, `libintl.jar` and
`libintl-0.23.2.jar`, none of the targets. A JVM given the packet jars therefore finds no absolute manifest target
here today. That depends on the host, not on the packet.

## Archived paths that no longer exist

`$B/logs/archived-absolute-paths.txt` lists the absolute paths that the committed `plans.zip` and `executions.zip`
under `verification/beyond-jbmc/scaffold-first/` name, by archive and root. They fall into three groups:

- Under `$BJ/tmp/…`: job scratch folders, all gone. They are not inputs.
- Under `/home/filip/code/in-the-loop/verification/.state`: the runner's state.
- Under `$BJ/panel/evaluation/SLOT/packet/…`: either present (the packet jars) or missing. The missing ones are manifest
  URLs resolved against the neutral packet folder: 248 for slot 04 (for example `packet/old/lib/…`) and 8 for slot 08.
  They are missing by design, because the neutral layout has no such files.

The Log4j manifests' absolute `$O/artifacts` paths all exist on this machine, so nothing needed rebasing here.

## OpenJDK manifest fixture

`git ls-remote` gives the same `jdk-21+35` (tag `07687d169a5e181789869817f10f3e8a4a4c30a9`, commit
`890adb6410dab4606a4f26a942aed02fb2f55387`) on `openjdk/jdk` and `openjdk/jdk21u` (`$B/logs/openjdk-*-ls-remote.txt`).
It was fetched into the existing blobless mirror: `git fetch --depth=1 --filter=blob:none origin
'refs/tags/jdk-21+35:refs/tags/jdk-21+35'`. Git also followed the tags `jdk-21-ga` (the same commit) and `jdk-21.0.13+9`,
`jdk-21.0.13-ga`, `jdk-21.0.13.0.2+0` (all on `ba94eace682733f66e623c089bcafcf4a1b8e39c`, which was already there).
The mirror grew from 14 MB to 31 MB. The worktree is sparse (`/test/langtools/tools/javac/Paths/`, 14 files).
`ClassPath.java` has blob `5b6bb5fe5bc058a9a0d6196e5463b35cb5f55306`, as listed in the pinned tree.

The test needs jtreg's `ToolBox`, which is not set up here. `$B/scripts/openjdk_classpath_fixture.sh JDK_BIN EMPTY_DIR`
re-creates its `java` steps (lines 64–131) with plain `javac`/`jar`/`java`: `A.jar` (Class-Path `B.zip`, `pkg/A.class`)
and `B.zip` (Class-Path `A.jar`, `pkg/B.class`).

## What was run on a JVM

All on `$J21`, one fresh process per row.

**OpenJDK fixture** (`$B/logs/jvm-openjdk-classpath-fixture.txt`): 6/6 as the test expects. `-cp A.jar:. Main` and
`-cp B.zip:. Main` exit 0. After moving both into `jars/`, `-cp jars/A.jar:. Main` and `-cp jars/B.zip:. Main` exit 0.
`-Xbootclasspath/a:jars/B.zip -cp . Main` fails (exit 1). `-jar Main.jar` with `Class-Path: A.jar` exits 0.

**Log4j, built jars, API then core** (`$B/probes/log4j/RolloverProbe.java`, copied from `$O/probes/G`, sha256
`f33d6e890e0074ce73a4fd322812bc230d06c2b68f90c392c9965bbbb287143c`; `$B/logs/jvm-log4j-built-api-core.txt`). It calls
`getNextTime(2014-03-04T10:00Z, 1, false)` and gives the fast-follow setup's table again:

| Default zone | Pattern | parent next | fix next |
|---|---|---|---|
| GMT+10 | `logs/app-%d{yyyy-MM-dd}{GMT-6}.log.gz` | `2014-03-04T14:00:00Z` | `2014-03-05T06:00:00Z` |
| GMT-10 | the same | `2014-03-05T10:00:00Z` | `2014-03-05T06:00:00Z` |
| GMT+10 | `logs/app-%d{yyyy-MM-dd}.log.gz` (zone omitted) | `2014-03-04T14:00:00Z` | `2014-03-04T14:00:00Z` |
| GMT-10 | the same | `2014-03-05T10:00:00Z` | `2014-03-05T10:00:00Z` |

`Origin.java` (non-initializing `Class.forName`, sha256 `7a714c06c9b9ccd0ff4e1ec9ef922508e0a792ada409893d9ae475c974a7ebff`;
`$B/logs/jvm-log4j-origins.txt`) shows that the application loader takes `PatternProcessor` and `DatePatternConverter`
from the core jar on each side. The class digests are:

| Class | parent | fix |
|---|---|---|
| `PatternProcessor` | `0ff2c4356701b9bb4249bbaad5bb2c1352d18cb5d6a8ecadafd86d39a35a6aa1` | `538564676d2e264f509005f722b199f0d02a248984b48b8c748188a9b6fb987e` |
| `DatePatternConverter` | `0b9a9ec0f1a1afa981705c54e23fb6b35dfdc2b193c959b6595e46a86e89df01` | `3eaffab3d596a60d4f235ff6a67386cbd57b12687fee7687b05cd1da123cfeec` |

Both digests equal the fast-follow record. The api jar has no `PatternProcessor` entry. `javap` gives
`public long getNextTime(long, int, boolean)`, descriptor `(JIZ)J`, on both sides. The probe's own class directory came
first on that class path, so core was at index 2 there, not index 1.

**Log4j landed regression** (not re-run, already a passed job): `20261124-141323-setup-build-log4j-core-at-both-1173-revi`.
`PatternProcessorTest`: fix 25/25, the parent's own 14/14, the landed file on the parent 9 failures, fix offline 25/25.
Command and failing tests are in the [fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md).

**Parquet J08** (`$B/scripts/j08_physical.py` with `$B/probes/j08/ObserveMain.java`, a `main` that only calls the
committed `UpgradeProbe.observe`; `$B/logs/jvm-j08-physical.json`). The probe was compiled with `-proc:none` against
each side's `bindings.json` class path in order (113 entries, resolved under `$P20`), then run once per input with that
class path after the probe directory. Result: **10/10 returns equal `physical.json`**. This check recorded no class
origins, on purpose (see the notes).

**Examples** (`python3 examples/tools/validate_example.py NNN`, about 3 minutes each; `$B/logs/validate-NNN.txt`): 312,
323 and 333 pass. The working copy was unchanged afterwards.

**Existing binding tests**: `python3 -m unittest examples/tools/targets/test_class_binding.py` ran 10 tests in 4.9 s,
OK. These include the Gate `marker()I` multi-release fixtures of exercise 8. pytest is not installed, so use
`unittest` or `test_costs.py`.

## Commands for the product entry points (not run here)

From `examples/tools/targets/change_plan.py` and `examples/tools/build.py`:

- `python3 examples/tools/build.py --change-plan application --before OLD --after NEW --jdk JDK --workflows WF --output OUT [--run] [--cache DIR] [--previous PLAN]`.
  `--before`, `--after`, `--jdk` and `--workflows` are required. Further options: `--before-test`, `--after-test`,
  `--after-jdk`, `--fixtures`, `--old-dependency`, `--new-dependency`, `--checker` (default `lib/target/release/jvmcontract`)
  and `--seconds` (default 60). For Log4j, the frozen inputs are `lib/benchmark/organic-composition/log4j/{old,new}/prepared.json`,
  `workflows.json`, `explicit.json` and `omitted.json`.
- `python3 examples/tools/build.py --discover-resource-workflows …` hands its arguments to
  `targets/resource_workflows.main`.
- The campaign drivers: `python3 -B lib/benchmark/beyond-jbmc/blind/original_plans.py SLOT --label manifest-bound --modes cold warm clean wrong`
  and `python3 -B lib/benchmark/beyond-jbmc/blind/manifest_controls.py`. These ran as jobs before; run them as jobs
  again. `manifest_controls.py` builds its own jars in scratch and reads no cached input.

## Setup Agent Notes

### What is ready, and where

- **Log4j #1173.** `lib/benchmark/organic-composition/log4j/{old,new}/prepared.json` name `$O/artifacts/G-logging-log4j2-{parent,fix}-log4j-{api,core}.jar`
  (`$O` = `~/.cache/in-the-loop/organic-composition-ff`), in the order api, core. All four match their digests
  ([table](#inputs-digests-at-the-paths-their-readers-use)), and the paths exist as written, so nothing needs
  rebasing on this machine. The source worktrees `$O/worktrees/G-logging-log4j2-{parent,fix}` are at the pins.
- **Parquet J08.** All 114 distinct files of `verification/product-behaviour/cases/J08/bindings.json` match, resolved
  under `~/.cache/in-the-loop/organic-pr-20`. That includes the overlays at index 0
  (`artifacts/J08-parquet-java-parent-overlay.jar` `28b3eb17a9d72a4f678e86642f52fa2ec7cf17b42626d1deda37e7c04e9ab2ae`
  and `artifacts/J08-parquet-java-fix-overlay.jar` `cb7a4d77da751a8ae262afc22a6609803319065cae001f7eb2dd8ac5c0a23095`)
  and the release column jar at index 2 (`m2/org/apache/parquet/parquet-column/1.18.2/parquet-column-1.18.2.jar`
  `e453c9725e323ca3a1165b842cae325c35fc3eed0ec37856ba15fe61290569a6`).
- **Release panel** (exercises 3 and 9). The packets are `~/.cache/in-the-loop/beyond-jbmc/panel/evaluation/SLOT/packet`,
  with neutral names `old/NNN.jar`. They pass the campaign's own locked-input check, and every jar is byte-identical to
  its file in a `.deb` that chains to a signed Ubuntu index ([chain](#release-panel-signed-chain)). The neutral-name
  ↔ deployment-path mapping and the manifest edges are in each slot's `graphs.json`. The packaged layouts of slots
  03, 04, 08, 10, 13, 15 and 16, with their symlinks, are in `~/.cache/in-the-loop/classpath-entry-discovery/layouts/SLOT/{old,new}/root/usr/share/{java,maven-repo}`
  ([table of edges and unresolved paths](#original-layouts)).
- **Historical origins** (exercise 12). The 21 graphs and 283 class bindings of
  `verification/java-semantics-gap/heap-and-gson/origins.json`: all 17 library jars match at `~/.cache/in-the-loop/jbmc-java-semantics-gap/artifacts/`.
- **OpenJDK fixture** (exercise 5). `~/.cache/in-the-loop/classpath-entry-discovery/src/openjdk-jdk-21+35-paths/test/langtools/tools/javac/Paths/ClassPath.java`,
  commit `890adb6410dab4606a4f26a942aed02fb2f55387`, blob `5b6bb5fe5bc058a9a0d6196e5463b35cb5f55306`. A plain-JDK
  re-creation of its java steps is `~/.cache/in-the-loop/classpath-entry-discovery/scripts/openjdk_classpath_fixture.sh JDK_BIN EMPTY_DIR`.
- **Examples 312, 323, 333** validate. **`jvmcontract`** is rebuilt at this head
  (`0ff2ba8821339d856389eefe52c2525afc1c36c0924652c2cd21ae17c2153c70`).
- **JDKs** 8, 11, 17, 21.0.13 and 25.0.5 (Temurin) are in `~/.sdkman/candidates/java/`, with digests in
  [Tools](#tools). The default `java` is 25.0.5. The Log4j and J08 manifests' `jdkReleaseSha256`
  `f83f6dcc966043c93cd498ac8e7ee7c310852074970d62c702e4ad2710002898` is the `release` file of 21.0.13.

### What was verified on a JVM

- The OpenJDK `A.jar ↔ B.zip` fixture on JDK 21: from either root, moved together, the boot-path failure, and `-jar`
  with a manifest Class-Path all behave as the test expects (6/6).
- Log4j on the built jars, api then core, JDK 21, one JVM per zone. The four `getNextTime` rows are the
  [recorded ones](#what-was-run-on-a-jvm): with the zone given, the fix moves the rollover to `2014-03-05T06:00:00Z`;
  with it omitted, the two sides agree. `PatternProcessor` comes from the core jar with digests parent
  `0ff2c4356701b9bb4249bbaad5bb2c1352d18cb5d6a8ecadafd86d39a35a6aa1` and fix `538564676d2e264f509005f722b199f0d02a248984b48b8c748188a9b6fb987e`,
  descriptor `(JIZ)J`. The landed `PatternProcessorTest` passes on the fix and fails (9 tests) on the parent:
  job `20261124-141323-setup-build-log4j-core-at-both-1173-revi`, not re-run.
- J08: the ten `physical.json` observations reproduce in fresh JVMs on the recorded 113-entry orders (10/10).

### What to know before starting

- **J08 is a withheld case.** This setup recorded no class origins or shadowing for J08, so that the brief's frozen
  transfer stays cold. `case.json` and `physical.json` already hold its nominated entry and answers: keep them out
  of the discovery input.
- **The panel's manifests name absolute Debian paths.** Most are `/usr/share/java/…`; slot 04 also has relative
  `lib/…` edges and slot 08 has `rt.jar`. The neutral packets cannot satisfy them. The archived manifest-bound plans
  resolved them against `packet/old/…`, where they are absent by design. On this host `/usr/share/java` holds none of
  the targets, but that is a property of the host. The faithful layout is the extracted `root/`, whose absolute
  edges point at `/usr/share/java` and not into `root/`. How to map them (a chroot-like root, or a verified mapping)
  is the brief's design question, so this setup did not decide it.
- **Slot 04 old has 33 unresolved manifest paths and 22 basename matches. Slot 08 has `usr/share/java/rt.jar`
  unresolved on both sides.** These come from `graphs.json`; nothing here added to or settled them.
- **Resolute's universe index** is checked from apt's copy in `/var/lib/apt/lists/`, which matches the signed
  InRelease today. If apt refreshes it, the chain for the resolute-side packages of slots 03–06, 08, 13 and 15 needs
  that index fetched again (its sha256 is in the cached InRelease).
- The build of the Log4j jars needs Maven 3.8.4 on JDK 8 with toolchain 11
  ([fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md)). Nothing in this brief needs a
  rebuild.
- There are no snapshot dependencies in the runtime class paths, apart from Log4j's own 2.19.1-SNAPSHOT build, which
  is pinned by digest.
- The default `java` is 25.0.5, and the panel scripts use 25.0.5 (`history.py`). The Log4j, J08 and origins evidence
  was recorded on 21.0.13.
- pytest is not installed: run the Python tests with `unittest` or `lib/tools/test_costs.py`.

### What is left for the domain work on purpose

- Every run of the product on these inputs: the Log4j change plan and its first open reason, candidate discovery, the
  manifest-bound slots through the shared path, the frozen J08 transfer, and the 283-binding replay through the
  shared binding path. The same goes for the scorecard and the counts of scans, batches and probes.
- The small generated layouts of exercises 2, 4, 5, 6 and 7, including the moved, broken and duplicate-`lib.jar`
  variants of the OpenJDK fixture.
- How a faithful deployment maps absolute manifest URLs, and how a cache rename keeps a verified layout.
- Reproducing the published 22/32 and 32/32 from the records. The records and their 372 archives are verified, but
  were not re-scored here.
