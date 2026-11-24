# Setup for the trusted-kernel and receiver-recovery brief

Mechanical setup for [`trusted-kernel-and-receiver-recovery-brief.md`](trusted-kernel-and-receiver-recovery-brief.md),
done on 2026-11-24 by a setup session (Claude Opus 5.5) before the domain work starts. The session:
- re-checked every pinned tool and input against the two setup records the brief builds on;
- ran the brief's five inventory checks;
- resolved, checksum-checked and signature-checked the three releases new to this brief (Guava 31.1-jre, Beam's
  vendored Guava 32.1.2, fastutil 8.5.15);
- pinned their sources;
- extracted and disassembled every class the brief names;
- rebuilt the trusted-kernel consumer at this head;
- restored one cleaned-away cache from its snapshot;
- reproduced on a JVM every observation the brief states for an existing artifact.

It wrote no claims, examples, sidecars, adapters, recipes or checker code, allocated no example ids, and ran neither
the project verifier nor any prover on any claim. Everything it fetched or built is outside the checkout. **No
verification job was needed**: every JVM check took seconds, no upstream build or upstream test run is named by the
brief, and the one landed regression it relies on (JavaParser #4538) already has a committed run at the pinned commits.

`$B` below is `~/.cache/in-the-loop/trusted-kernel-receiver-recovery` (this work). `$TK` is
`~/.cache/in-the-loop/trusted-kernel` ([trusted-kernel setup](in-the-loop-trusted-kernel-experiment-brief-setup.md))
and `$RC` is `~/.cache/in-the-loop/receiver-construction`
([receiver setup](receiver-construction-and-property-discovery-brief-setup.md)). `$J` is Temurin 21.0.13+9,
`~/.sdkman/candidates/java/21.0.13.0+9-tem/bin`. **The default `java` on `PATH` is JDK 25.0.5**, so name JDK 21 by
its full path.

## Starting commit

The brief's baseline is `develop` at `867fa025a5b4ee4fecf312a3bd304c3c831c8e3d` (the 2026-11-24 promotion). This
setup ran at `b00ba515540524e7f1e379a006ac68de5a2e6b9a` ("Queue the brief beyond-jbmc-java-change-verification-cam"),
with `867fa025` an ancestor. The last change to the trusted-kernel Rust sources is `2d657ab9cb6024243ce6111e07c8fd501d7ddbe7`
("Check JDK range fill and its caller frame").

## Layout

| Path | What it holds |
|---|---|
| `$B/releases/NAME/{lib,sources}/`, `classpath.txt`, `tree.txt` | The three new release graphs from Maven Central: `guava-31.1-jre`, `beam-vendor-guava-32_1_2-jre-0.1` (no sources jar is published), `fastutil-8.5.15`. |
| `$B/resolve/NAME/pom.xml`, `$B/m2`, `$B/maven-settings.xml` | A throwaway POM per graph, the local repository (seeded by hard links from `$RC/m2`) and settings pointing at it. |
| `$B/classes/` | Class entries extracted from the release jars and the JDK image, with `$B/logs/classes.sha256` ([below](#class-entries)). |
| `$B/src/fastutil-355d8ebf`, `$B/src/guava-31.1` | Detached worktrees of the pinned source commits ([below](#pinned-sources)). Mirrors `~/.cache/in-the-loop/git-mirrors/{fastutil,guava}.git`, refs `refs/pinned/WORKTREE`. To add one: `$B/scripts/mirror.sh OWNER/REPO MIRROR WORKTREE SHA`. |
| `$B/kernel/kernel-at-head` | The trusted-kernel consumer compiled at this head ([below](#trusted-kernel-consumer)). |
| `$B/probes/jvm/*.java`, `out/` | Throwaway JVM programs reproducing the brief's stated observations (`$B/probes/probes.sha256`). Not claims, adapters or drivers. |
| `$B/probes/historical/{frame,miss,Ints}/` | The two historical incorrect Guava variants, rebuilt the way `controls.py` builds them, and the release class beside them ([below](#historical-variants)). |
| `$B/scripts/` | `mirror.sh`, `historical_variants.py` (the probe driver for the variants). |
| `$B/keys/central/`, `$B/keys/fresh/`, `$B/gnupg` | Central's `.asc`, `.sha1`, `.md5` (and `.sha512` where published), the signing keys, and this setup's own keyring (`GNUPGHOME=$B/gnupg`). Its agent was stopped. |
| `$B/logs/` | Resolution logs, `release-jars.sha256`, `signatures.txt`, `classes.sha256`, `javap-*.txt` for every extracted class, JVM probe output (`jvm-*.txt`, `jvm-historical-variants.json`), receiver area checks, the Lean recheck and the cargo log. |
| `$B/tmp` | `TMPDIR` for this work (left empty). |

## Pinned tools: still as recorded

Each was checked against the digest the earlier setups and the committed evidence name. All match.

| Tool | Where | sha256 / identity |
|---|---|---|
| Temurin 21.0.13+9 | `~/.sdkman/candidates/java/21.0.13.0+9-tem` | `lib/modules` `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c`; `java -version` "Temurin-21.0.13+9 (build 21.0.13+9-LTS)" |
| Z3 5.3.3 | `~/.local/bin/z3` → `~/tools/z3/z3-5.3.3-x64-glibc-2.39/bin/z3` | `fcd0ca765d1c0b4eac776f442ec0f10294b9a6416be91fad4e52fa19012c8d01` (= `frame_witness.py` `Z3`) |
| CaDiCaL 1.9.5 CLI | `$TK/src/cadical-1.9.5/build/cadical`, commit `146207318796f094dcded87349a64f0c6927309e` | `0fabbda6d757d7076ca003c8e9ffadd4ef893c3cacaabcf5986c415e0de74ec4` (= `bounded_sat.py`) |
| `cake_lpr` | `$TK/src/cake_lpr-033aad53/cake_lpr`, commit `033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2` | `c14ff49853e890436d6a2fbf66a85b9492dad1dcd2d76254f16a89f2236c8a54` (= `bounded_sat.py`, `cases.json`) |
| Lean 4.36.0 | `~/.elan/toolchains/leanprover--lean4---v4.36.0` | `bin/lean` `db7f559d05795e7af52e42bc966c90240a39dcb9712161c54c97afa546e20c00` (= `cases.json`); all 18,248 files equal the archive listing `$TK/logs/inst-4.36.0.txt` (`$B/logs/lean-4.36.0-recheck.txt`, 0 failures) |
| Rust | `~/.local/bin/{rustc,cargo}` | rustc 1.99.1 (58cf8f9c3 2026-10-13), cargo 1.99.1 |
| `jvmcontract` release | `lib/target/release/jvmcontract` | `a61246d28d07c5f63df21694b7ec1484b26a06b79faad7b532579e10c95afa28`; `cargo build --release --bin jvmcontract` found it fresh at this head |
| `setpriv` (the isolation `replay.py` uses) | `/usr/bin/setpriv` | util-linux 2.41.3, with `--landlock-access` and `--landlock-rule` |
| Maven | on `PATH` | 3.10.0 |

`bounded_sat.py` refuses to run unless the `cake_lpr` and CaDiCaL digests above match.

## Inventory checks

The five commands of the brief, run at this head from the repository root (each under a second):

| Command | Result |
|---|---|
| `decision_evidence.py --check` | 111 keyed cases; guava observed 18 SAT and 8 UNSAT, 8 certified, 0 without solver; prefix-sums 8 SAT and 10 UNSAT, 10 certified |
| `range_qualification.py --check` | the 14 range cases as recorded: `fill-any-length`, `caller-any-length`, `saved-local` accepted; `strict-empty-guard`, `wrong-loop-slot` unsupported; the other 9 rejected |
| `frame_witness.py --check` | "preserve the input heap": changing store SAT, same-value store UNSAT; caller read: shared empty range SAT, distinct valid observation UNSAT |
| `bounded_sat.py --check` | 336/first-8-release 8/8 UNSAT certified, 18 SAT calls, 0 constant-false; held/prefix-sums 10/10, 8 SAT, 0 |
| `receiver-discovery/results.py --check` | "verified receiver campaign results" |

These validate saved evidence. None of them re-executes a run.

## Released artifacts

Resolved from Maven Central with `mvn --strict-checksums`. Every main and sources jar was checked again against a
fresh copy of Central's `.sha1` (16 of 16 match; the three `.sha512` Central publishes also match) and its `.asc` in
this setup's own keyring (16 of 16 `VALIDSIG`). Table: `$B/logs/signatures.txt`; all jar digests:
`$B/logs/release-jars.sha256`.

| Jar | sha256 | Signed by |
|---|---|---|
| `guava-31.1-jre.jar` | `a42edc9cab792e39fe39bb94f3fca655ed157ff87a8af78e1d6ba5b07c4a00ab` | Christopher Povirk `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` |
| its graph: failureaccess 1.0.1, listenablefuture 9999.0, jsr305 3.0.2, checker-qual 3.12.0, error_prone_annotations 2.11.0, j2objc-annotations 1.3 | `$B/logs/release-jars.sha256` | Povirk; Colin Decker subkey `694621A7227D8D5289699830ABE9F3126BB741C1`; Tagir Valeev; Checker Framework; Liam Miller-Cushon; Tom Ball |
| `beam-vendor-guava-32_1_2-jre-0.1.jar` (no dependencies) | `44669a8f43cdef8ac20e02484ead0d1cf8199d47e00c7f1828b579b7dfb0f9a2` | Yi Hu (Beam) `2011EC936303D9A1DB662EE1CB6974C8170405CB`. **Key expired 2023-10-09**; signature made 2023-08-03, while it was live (`EXPKEYSIG` + `VALIDSIG`) |
| `fastutil-8.5.15.jar` | `cffeb6673bdf1e6e4377d684df2f55ac359cf5cf6df613e05e62deeea500936a` (**= brief**) | Sebastiano Vigna `0CB5871FB7BF3B351614BBF6CA85FFE638D4407A`. **The signature (2024-10-19) is cryptographically valid but postdates the key's published expiry (2022-11-08)**. keyserver.ubuntu.com and pgp.mit.edu both carry only that expiry; keys.openpgp.org did not answer. The jar's digest equals the brief's and Central's `.sha1`/`.md5`. |
| `fastutil-8.5.15-sources.jar` | `57d0e59cd6f6bd931d893ab0089bdcb13aee0ed78f1f8e85d88bc55b89815211` | the same as the jar |

Reused from earlier setups, digests re-checked today: Guava 33.4.8-jre `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed`
(`$TK/releases/guava-33.4.8-jre/lib/`, = brief) and its sources jar `9d3c6aad893daac9d4812eb9fa4c3f7956a9f2e472eb7df2fea0e467fed7e766`
(= `controls.py` `SOURCE_SHA`); Commons Lang 3.17.0 `6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4`
(`$RC/releases/commons-lang3-3.17.0/lib/`, = brief).

To redo a resolution: `cd $B/resolve/NAME && mvn -B -s $B/maven-settings.xml --strict-checksums
dependency:copy-dependencies -DoutputDirectory=$B/releases/NAME/lib -DincludeScope=runtime` (add `-Dclassifier=sources
-DfailOnMissingClassifierArtifact=false` for sources). **Offline** works for all three:
`mvn -B -o -s $B/maven-settings.xml dependency:build-classpath -Dmdep.outputFile=$B/releases/NAME/classpath.txt
-DincludeScope=runtime` wrote each `classpath.txt`.

## Pinned sources

| Worktree (`$B/src/`) | Commit | Tree | Identity |
|---|---|---|---|
| `fastutil-355d8ebf` | `355d8ebfaf2bcc4032cc1c25bec9f3fe827f8175` | `63ad8589dc493fd53167173f255497f1a27e1cba` | = tag `8.5.15` (lightweight, unsigned; `build.properties` `version=8.5.15`); the brief's link. Parent `d75a9af680a1c2e10eb820320447b6858aefcd44`. |
| `guava-31.1` | `0a17f4a429323589396c38d8ce75ca058faa6c64` | `7246e90fff1df63a2a0b4a31280a7ab3f58e4207` | = tag `v31.1` (lightweight, unsigned). Not linked by the brief; pinned for the release's sources. |

Also used, from earlier setups: Guava 33.4.8 `f06690fa3e874f65515e8fd338a74d636e2c792f` (`$TK/src/guava-33.4.8`),
Commons Lang 3.17.0 `29ccc7665f3bc5d84155a3092ab2209a053324e6` (`$RC/src/commons-lang-3.17.0`, the brief's link),
Commons Configuration #565 new side `d2101a20e2b74ced47ae57dd3b6d1d90b03d409b` (`$RC/src/configuration-565-new`, the
brief's link) and the other Configuration, Compress and JavaParser sides listed in the receiver setup.

**Released sources equal the tags.** `Ints.java`, `Longs.java` and `IntsMethodsForWeb.java` in the Guava 31.1 sources
jar are byte-identical to `v31.1`. fastutil's `it/unimi/dsi/fastutil/Arrays.java` in the sources jar is
byte-identical to the tag. `IntArrays.java` is generated from `drv/Arrays.drv`, so it is not in the tag. Its `fill`
(sources jar lines 292–296) is the template at `drv/Arrays.drv` lines 376–380:
`ensureFromTo(array, from, to); if (from == 0) while (to-- != 0) array[to] = value; else for (int i = from; i < to; i++) array[i] = value;`.

**Configuration initializer.** At `d2101a20`, `ConfigurationInterpolator.java` line 100 is
`static final DefaultPrefixLookupsHolder INSTANCE = new DefaultPrefixLookupsHolder(System.getProperties());`, and
lines 167–172 (the brief's link) read `props.containsKey(DEFAULT_PREFIX_LOOKUPS_PROPERTY) ?
parseLookups(props.getProperty(...)) : createDefaultLookups()`. So the read is `containsKey` and then `getProperty`.
Lines 150–190 are identical at the #565 old side and the #601 new side.

## Class entries

Extracted with `unzip` from the release jars; the JDK class with the repository's own
`range_qualification.py --extract-arrays`. All are class-file major 52 except `Arrays.class` (the JDK's own). Full
list with the inner classes: `$B/logs/classes.sha256`. Disassembly: `$B/logs/javap-*.txt`.

| Entry (`$B/classes/…`) | sha256 | Bytes |
|---|---|---|
| `jdk-21.0.13/Arrays.class` (`java/util/Arrays`) | `4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab` (**= brief**, = `$RC/jdk/temurin-21.0.13/classes/java/util/Arrays.class`) | 59937 |
| `guava-31.1-jre/com/google/common/primitives/Ints.class` | `eabfacbd2cdbcabe454f2ace17add37b33db8d0dd3f964e68f2662e7ab1e9a6f` | 8183 |
| `guava-31.1-jre/…/IntsMethodsForWeb.class` (superclass of `Ints`) | `c356227267677f91131b7de0e9b3020956fa14656a5ab2ccf40fbca6e3296d81` | 550 |
| `guava-31.1-jre/…/Longs.class` | `c19ed9c07ff3c3df1970dc233d3928106e4f30b99bf5707844c7c4e38d80a2f4` | 8519 |
| `beam-vendor-guava-32_1_2-jre-0.1/org/apache/beam/vendor/guava/v32_1_2_jre/com/google/common/primitives/Ints.class` | `db1bba7192869fb40970108088b804ee2fa9cd452a1149db41e973a87f893e35` | 9560 |
| `…/v32_1_2_jre/…/IntsMethodsForWeb.class` | `fe4198a61b552bdb882580006a8cee38f404b2a4dda2171504dcedd8c5cb0412` | 714 |
| `…/v32_1_2_jre/…/Longs.class` | `54c7919264e3616e328b3e56edbd9c725a1b764d4019888991cb9518cbdcfd28` | 10035 |
| `guava-33.4.8-jre/com/google/common/primitives/Shorts.class` | `762e9f8985815128ec8984898bc18b5e01fde5420147db7b75d6aa56f64ca22a` | 8490 |
| `guava-33.4.8-jre/…/ShortsMethodsForWeb.class` (superclass of `Shorts`) | `7e053ddddb1d5d60e74c1e9e1905b2d8471670d4c583a109dde59a2f225458fd` | 451 |
| `guava-33.4.8-jre/…/Chars.class` (superclass `java.lang.Object`) | `bab3b36def41d6f2284a8bad9eb13d65b79b5cd23256f28f947a5c2e8d4980a5` | 8058 |
| `fastutil-8.5.15/it/unimi/dsi/fastutil/ints/IntArrays.class` | `b455b9400c7fe47a938229a25f04f7d55c4cc09a2332580d28e098d80afe1f0c` | 35412 |
| `fastutil-8.5.15/it/unimi/dsi/fastutil/Arrays.class` | `1ecbd5a1984248e84cd734a5a6c674aa91f2362dd3ce42c77d5c35b91ad22d96` | 6328 |
| `commons-lang3-3.17.0/org/apache/commons/lang3/ArrayUtils.class` | `f21e4f7f69b2d98bed01748bd5b711b47458007ee762d07f1e4c4c32147bc8cc` (**= brief**) | 77444 |

The Beam package is **`org.apache.beam.vendor.guava.v32_1_2_jre`** (with `_jre`), not `v32_1_2`. None of the Guava
classes above has a `<clinit>`. `IntArrays`, fastutil's `Arrays` and `ArrayUtils` each have one.

The methods, from `javap -c -p`:

```text
JDK Arrays.fill([JIIJ)V      0 aload_0; 1 arraylength; 2 iload_1; 3 iload_2; 4 invokestatic rangeCheck:(III)V; 7 iload_1;
                             8 istore 5; 10 iload 5; 12 iload_2; 13 if_icmpge 27; 16 aload_0; 17 iload 5; 19 lload_3;
                             20 lastore; 21 iinc 5,1; 24 goto 10; 27 return          (locals: a 0, from 1, to 2, val 3–4, i 5)

Guava 31.1 and Beam Ints.indexOf([II)I / ([IIII)I   byte-for-byte the 33.4.8 sequences (wrapper 0–8, helper 0–27,
                             iaload at 12); only constant-pool indices differ (wrapper invokestatic #4 in 31.1, #66 in Beam)
Guava 31.1 and Beam Longs.indexOf([JJ)I / ([JJII)I  the 33.4.8 sequences (laload 13, lcmp 15, helper 0–29); #4 / #50

Shorts.indexOf([SSII)I       0 iload_2; 1 istore 4; 3 iload 4; 5 iload_3; 6 if_icmpge 26; 9 aload_0; 10 iload 4; 12 saload;
                             13 iload_1; 14 if_icmpne 20; 17 iload 4; 19 ireturn; 20 iinc 4,1; 23 goto 3; 26 iconst_m1; 27 ireturn
Chars.indexOf([CCII)I        the same with 12 caload. Both wrappers ([SS)I, ([CC)I: 0 aload_0 … 5 invokestatic … 8 ireturn

fastutil IntArrays.fill([IIII)V  (@Deprecated)
                             0 aload_0; 1 iload_1; 2 iload_2; 3 invokestatic IntArrays.ensureFromTo:([III)V; 6 iload_1;
                             7 ifne 24; 10 iload_2; 11 iinc 2,-1; 14 ifeq 44; 17 aload_0; 18 iload_2; 19 iload_3; 20 iastore;
                             21 goto 10; 24 iload_1; 25 istore 4; 27 iload 4; 29 iload_2; 30 if_icmpge 44; 33 aload_0;
                             34 iload 4; 36 iload_3; 37 iastore; 38 iinc 4,1; 41 goto 27; 44 return
IntArrays.ensureFromTo([III)V    0 aload_0; 1 arraylength; 2 iload_1; 3 iload_2; 4 invokestatic it/unimi/dsi/fastutil/Arrays.ensureFromTo:(III)V; 7 return
fastutil Arrays.ensureFromTo(III)V  0 getstatic $assertionsDisabled; 3 ifne 18; 6 iload_0; 7 ifge 18; 10–17 new AssertionError … athrow;
                             18 iload_1; 19 ifge 54; 22–53 AIOOBE "Start index (…) is negative"; 54 iload_1; 55 iload_2;
                             56 if_icmple 100; 59–99 IllegalArgumentException; 100 iload_2; 101 iload_0; 102 if_icmple 146;
                             105–145 AIOOBE "End index (…) is greater than array length (…)"; 146 return
                             (<clinit>: $assertionsDisabled = !Arrays.class.desiredAssertionStatus())

Lang ArrayUtils.reverse([III)V   0 aload_0; 1 ifnonnull 5; 4 return; 5 iload_1; 6 iconst_0; 7 Math.max; 10 istore_3; 11 aload_0;
                             12 arraylength; 13 iload_2; 14 Math.min; 17 iconst_1; 18 isub; 19 istore 4; 21 iload 4; 23 iload_3;
                             24 if_icmple 54; 27 aload_0; 28 iload 4; 30 iaload; 31 istore 5; 33 aload_0; 34 iload 4; 36 aload_0;
                             37 iload_3; 38 iaload; 39 iastore; 40 aload_0; 41 iload_3; 42 iload 5; 44 iastore; 45 iinc 4,-1;
                             48 iinc 3,1; 51 goto 21; 54 return
```

This matches the brief:
- **JDK long fill**: the long value is in slots 3–4, the cursor in 5, and the store is `lastore` at PC 20.
- **fastutil**: the range check crosses from `IntArrays` into `it.unimi.dsi.fastutil.Arrays`, one call deep, behind an
  assertion guard on a `<clinit>`-set static. The descending loop's test is the post-decrement at 11/14, which leaves
  `to == -1` when it exits.
- **Lang `reverse`**: `isub` at PC 18, and the first read `iaload` at PC 30 comes before any store.

## Trusted-kernel consumer

`cd lib/benchmark/trusted-kernel && rustc --edition=2021 -C opt-level=2 -C target-feature=+crt-static -C
strip=symbols main.rs -o $B/kernel/kernel-at-head` (the flags of `replay.py` `build_kernel`; 0.7 s) gives
`635cc9433ada216c0f065c10d823c2b4d3f1cc67f5e9354de9151995f9604da1`. This is **byte-identical** to the range-capable
checker the committed evidence names (`checkerVersion` in `evidence/cases.json`, `evidence/range-proof/results.json`,
`evidence/frame-witness/results.json`), so the build is reproducible at this rustc. Earlier recorded binaries: frozen
Guava checker `8732c7a527559fa4a85408575ce914aedfa56d78fc5aec0ecfb66d5cf72112bc` and final Guava checker
`5e4cb3be8d3531a53702046b185b5bd0f1df3ee7dd07c30d92c318bc72427d2b` (`evidence/clean-replay.json`, source commit
`74e9e6bdb92d873219e19c5b3f55cc2fb91b7629`). This setup did not run the consumer on any request: its first response
to the long-fill and fastutil requests is the domain work's.

## Historical variants

`$B/scripts/historical_variants.py REPO $B/probes/historical` calls `controls.compile_variant` (unchanged) for the
`frame` and `miss` cases: javac 21 `--release 8` over the Guava 33.4.8 sources jar. It runs each class with the
repository's `java/Observe.java` under `-Xverify:all`. Output: `$B/logs/jvm-historical-variants.json`.

| Class | sha256 | Input | JVM |
|---|---|---|---|
| heap-writing (`frame`) | `7432818271aeb2cccc0e68215c022e585a1aaba29feb72d8c60f52a202993747` (= `historical-frame-control.json` `classSha256`) | `[7]`, 7 | return 0, heap `[0]` |
| | | `[0]`, 0 | return 0, heap `[0]` (the store writes the old value) |
| wrong miss (`miss`) | `4cbdc3e3e7ddda3196050ee42b1606e7c6ebb8aedfab66eec0aec669c479da02` (= `evidence/freeze/miss/external.request`) | `[]`, 7 | return 0 |
| release `Ints` | `ae581f721521c93250639d17348c5b7215f3591a1bb433fb63985caa4364edbb` | `[]`, 7 / `[7]`, 7 / `[0]`, 0 | −1 / 0 heap `[7]` / 0 heap `[0]` |

The rebuilt classes reproduce the recorded digests, so the compile is deterministic. In the heap-writing helper
(`$B/logs/javap-historical-frame.txt`) the store is `25: iastore` (`21 aload_0; 22 iload 4; 24 iconst_0; 25 iastore`),
as the brief says. The miss helper ends `26: iconst_0; 27: ireturn` in place of `iconst_m1`.

## What was replayed on a JVM

All on Temurin 21.0.13 (`-Xverify:all` for the grids), inline, each in about a second. Output:
`$B/logs/jvm-grids.txt`. Sources: `$B/probes/jvm/` (sha256 in `$B/probes/probes.sha256`). Where the brief does not
list its grid, the value sets are this probe's choice and are named in each source file. Every count the brief gives
came out the same.

| Brief statement | Probe | Observed |
|---|---|---|
| long fill: 245 small valid-range controls pass; narrowing the value to 32 bits changes 80; extending the interval by one cell where possible changes 140 | `LongFill`: lengths 0–4, every valid range, values `{0, 1, -1, 2^32, MIN, MAX, 0x80000000}`, sentinel cells | `checks=245 pass=245 narrowChanged=80 extendChanged=140` (105 empty-range, 28 whole-range checks); one-cell write of `4294967296L` stores `4294967296` (narrowed: 0); `from<0` and `to>len` throw `ArrayIndexOutOfBoundsException`, `from>to` throws `IllegalArgumentException` |
| Guava 31.1 and Beam: 780 int and 1,554 long calls per JAR | `IndexOfReleases`: lengths 0–3, every array over 5 int values / 6 long values, every target from the set, against a first-match oracle; `URLClassLoader` per JAR | both JARs: `int calls=780 agree=780`, `long calls=1554 agree=1554`, every heap unchanged. Loaded class digests = the table above |
| fastutil: 7,745 checks pass, 2,735 zero-origin and 5,010 other | `FastutilFill`: lengths 0–4, all arrays over `{-1,0,1}`, every valid range, five values `{2,-2,7,MIN,MAX}` | `checks=7745 pass=7745 zeroOriginBranch=2735 otherBranch=5010`. `[0,2)` with 99 on `[0,0,0]` → `[99,99,0]`; `[1,1)` on `[5,6,7]` unchanged. Invalid ranges: AIOOBE "Start index (-1) is negative", IAE "Start index (1) is greater than end index (0)", AIOOBE "End index (3) is greater than array length (2)" |
| Shorts/Chars: six boundary patterns incl. `0x8000`, `0xffff`; 33 of 216 calls per type distinguish a wrong extension of the loaded cell | `ShortsChars`: patterns `{0x0000,0x0001,0x7fff,0x8000,0x8001,0xffff}`, every length-2 array, every target | `shorts calls=216 agreeOracle=216 distinguishWrongExtension=33`; `chars` the same |
| reverse: 44,165 calls, 40,525 normal and 3,640 exact exceptions with the array preserved; `reverse(new int[0],0,MIN)` throws AIOOBE; start `MAX` skips; null returns | `LangReverse`: the brief's grid exactly (365 arrays incl. null × 121 bound pairs) | `calls=44165 normal=40525` (all 40,525 equal reversing the clipped range; 121 are null), `exceptions=3640`, all `ArrayIndexOutOfBoundsException` with the array unchanged, 0 others. `reverse(new int[0],0,MIN)` → AIOOBE; `reverse([1,2,3],MAX,3)` unchanged; `reverse(null,0,1)` normal |
| the live properties table (§5.1), on OpenJDK 21.0.13 | `LiveTable`: fresh JVM, private key `itl.setup.probe.<nanotime>` | `getProperties()` twice: same object. The installed String reads back identically through the original table, and the class initializer saved that same reference. `setProperty` with an equal distinct String returns the first (identical), and the table then holds the second; the saved value is still the first. Child `Properties(old)` installed: `containsKey` false, `get` null, `getProperty` and `System.getProperty` return the second (identical). Removing the key from the parent makes live lookup null, and the saved reference stays the first |

### Receiver inputs, re-checked

- **The receiver campaign's Maven cache had been cleaned away.**
  `~/.cache/in-the-loop/agent-tmp/0cea9d0e-0fe8-427e-8e71-96614b084e11/external-upgrade-shared-maven/repository`
  (the `--maven-cache` of `receiver_campaign.py`, and the absolute path in the area's `prepared.json` files) was gone,
  with its parent's mtime 2026-11-23 22:57. `check_area.py` found 1,025 missing classpath entries of 586
  (`$B/logs/receiver-area-check.txt`).
- **It was restored from the receiver setup's hard-link snapshot**:
  `cp -al $RC/receivers/maven-repository …/external-upgrade-shared-maven/repository`. That takes no new blocks.
  `check_area.py ~/.cache/in-the-loop/tmp/domain-foundations-receivers` then reads all 64 prepared records and 586
  classpath files: **0 missing or changed** (`$B/logs/receiver-area-check-after-restore.txt`). The area itself
  (`modules/`, `slices/`, `sources/`) was intact.
- **Configuration #565 and #601**, both sides, through `$RC/receivers/cp/*.cp` and the registered `UpgradeProbe`:
  `[red, blue]`, `[Ada]`, `[7]`, `null` on all four (`$B/logs/jvm-upgrades-recheck.txt`).
- **Compress #767**, both sides: the four frames (empty, `aGVsbG8K`, `AP8AgA==`, `AAECAwQFBgcICQoLDA0ODw==`).
- **XZ cache profiles** on 1.11 and 1.12, one fresh JVM each. Absent and `Dummy` give `org.tukaani.xz.ArrayCache`,
  and `Basic` gives `BasicArrayCache`, with all frames decoded. `Bogus` gives frame 1 `java.lang.Error: Unsupported
  value 'Bogus' …`, then `NoClassDefFoundError: Could not initialize class org.tukaani.xz.ArrayCache`
  (`$B/logs/jvm-xz-javaparser-recheck.txt`).
- **JavaParser #4538** on the captured JARs (parent `cbe961009b6fafe13085b895a486660a470485ac34316043e20df41188f446a8`,
  fix `62cf2f2c4bb4be2ced24f7914b4d22ae9cc2a760a5ab11cd2cd867e68d69cd27`):
  - parent: empty postorder and `PostOrderIterator` throw `EmptyStackException`;
  - fix: they give `root`;
  - both: package `com` postorder `name package root`;
  - with `line.separator` cleared: use 1 `ExceptionInInitializerError` caused by NPE, use 2 `NoClassDefFoundError`.

## Examples of §3

`python3 examples/tools/build.py --plan 336 337 346 393 395` (`$B/logs/build-plan.json`): every task the brief names
is executable. These are `336 first-8-release`, `346 first-8-release`, `337 caller-8-*`/`caller-64-*`,
`393 conversion-equivalence-classified` and `node-checks-same`, and `395 exact-order-same-reference`. The jars their
`target.json` or `controls/libraries.json` list are in `~/.cache/in-the-loop/targets/sha256/`: 336 and 346 3 of 3
(the fourth digest is the `last-match.patch`), 393 4 of 4 (Jackson 2.19.0, Lang 3.17.0), 395 7 of 7. 337 is a
fixture with nothing to fetch. `held/prefix-sums` is in `lib/solvers/compare.py` `CASES`. None of these was run: each
runs the native engine on a claim.

## Disk

`$B` is 117 MB as `du` counts it without `m2` (most of it the fastutil jar and sources, 45 MB, and their extracted
classes). `$B/m2` is hard links into `$RC/m2` plus about 30 MB of new jars. The restored Maven cache takes no new
blocks. The fastutil mirror is 16 MB and the Guava mirror, with both pinned revisions, 18 MB. `$B/tmp` is empty; nothing was left in `/tmp`.

## Setup Agent Notes

### What is ready, and where

- `$B` = `~/.cache/in-the-loop/trusted-kernel-receiver-recovery`. JDK 21 by full path:
  `~/.sdkman/candidates/java/21.0.13.0+9-tem/bin/` (the default `java` is 25).
- **Pinned tools, all matching the earlier record and the evidence** ([table](#pinned-tools-still-as-recorded)):
  - Temurin 21.0.13+9;
  - Z3 5.3.3;
  - CaDiCaL 1.9.5 at `~/.cache/in-the-loop/trusted-kernel/src/cadical-1.9.5/build/cadical`;
  - `cake_lpr` at `~/.cache/in-the-loop/trusted-kernel/src/cake_lpr-033aad53/cake_lpr`;
  - Lean 4.36.0, every file;
  - rustc 1.99.1;
  - `lib/target/release/jvmcontract`, fresh at this head.
- **The brief's five inventory checks pass at this head** ([results](#inventory-checks)).
- **Trusted-kernel consumer at this head**: `$B/kernel/kernel-at-head`, sha256
  `635cc9433ada216c0f065c10d823c2b4d3f1cc67f5e9354de9151995f9604da1`. This is byte-identical to the range-capable
  checker in `evidence/cases.json`, so it is the int-capable binary to freeze.
- **New releases**, checksum- and signature-checked, with ordered classpaths in `$B/releases/NAME/classpath.txt`:
  - `guava-31.1-jre` (jar `a42edc9cab792e39fe39bb94f3fca655ed157ff87a8af78e1d6ba5b07c4a00ab`);
  - `beam-vendor-guava-32_1_2-jre-0.1` (`44669a8f43cdef8ac20e02484ead0d1cf8199d47e00c7f1828b579b7dfb0f9a2`);
  - `fastutil-8.5.15` (`cffeb6673bdf1e6e4377d684df2f55ac359cf5cf6df613e05e62deeea500936a`, = brief).
- **Reused releases**:
  - Guava 33.4.8-jre: `~/.cache/in-the-loop/trusted-kernel/releases/guava-33.4.8-jre/`;
  - Commons Lang 3.17.0: `~/.cache/in-the-loop/receiver-construction/releases/commons-lang3-3.17.0/`.
- **Class bytes** for every class the brief names, extracted, with full digests and disassembly: [Class entries](#class-entries),
  `$B/classes/`, `$B/logs/classes.sha256`, `$B/logs/javap-*.txt`. Among them:
  - JDK `Arrays.class`: `$B/classes/jdk-21.0.13/Arrays.class`,
    `4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab`, 59,937 bytes;
  - `ArrayUtils.class`: `f21e4f7f69b2d98bed01748bd5b711b47458007ee762d07f1e4c4c32147bc8cc`, = brief.
- **Sources**:
  - fastutil tag `8.5.15` = `355d8ebfaf2bcc4032cc1c25bec9f3fe827f8175` at `$B/src/fastutil-355d8ebf`;
  - Guava `v31.1` = `0a17f4a429323589396c38d8ce75ca058faa6c64` at `$B/src/guava-31.1`;
  - Guava 33.4.8, Lang 3.17.0, and the Configuration, Compress and JavaParser sides, from the earlier setups.
- **Historical variants**, rebuilt with the unchanged `controls.compile_variant`: `$B/probes/historical/frame/artifact.bin`
  (`7432818271aeb2cccc0e68215c022e585a1aaba29feb72d8c60f52a202993747`) and `$B/probes/historical/miss/artifact.bin`
  (`4cbdc3e3e7ddda3196050ee42b1606e7c6ebb8aedfab66eec0aec669c479da02`). Both equal the recorded digests.
- **Receiver campaign**: the area and its Maven cache are whole again (64 records, 586 files, 0 missing). Keep pointing
  `receiver_campaign.py` at the original paths. Ordered classpaths: `~/.cache/in-the-loop/receiver-construction/receivers/cp/`.
- **§3 examples** 336, 337, 346, 393 and 395: every named task is executable, and their jars are in the target cache.

### What was verified on a JVM

Every count and observation the brief states for an existing artifact reproduced ([table](#what-was-replayed-on-a-jvm)):
- JDK long fill: 245 pass, 80 changed by narrowing, 140 changed by extension, and the one-cell `4294967296L`.
- Guava 31.1 and Beam `indexOf`: 780 int and 1,554 long calls per JAR, all first-match, heap unchanged.
- fastutil: 7,745 checks (2,735 zero-origin, 5,010 other), `[0,2)` and `[1,1)`.
- Shorts and Chars: 33 of 216 per type.
- Lang `reverse`: 44,165 calls, 40,525 normal (each the clipped reversal) and 3,640 AIOOBE with the array preserved;
  `(new int[0], 0, MIN)` throws; `MAX` skips; null returns.
- The live properties table sequence (§5.1), step by step.
- Historical variants: heap-writing returns 0 and leaves `[0]` from `[7]`/7, and `[0]`/0 keeps `[0]`. Wrong miss
  returns 0 on `[]`, where the release returns −1.
- Configuration #565 and #601 (four observations, all four sides), Compress #767 frames, XZ profiles on 1.11 and 1.12,
  and JavaParser #4538 parent and fix, with the cleared-separator failure.

### What to know before starting

- **The receiver campaign's Maven cache under `agent-tmp/` had been cleaned** (2026-11-23 about 22:57) and was
  restored by hard links from `~/.cache/in-the-loop/receiver-construction/receivers/maven-repository`. It sits in a
  scratch folder, so a later cleanup can remove it again. Re-run the same `cp -al` if `check_area.py` reports missing
  files.
- **fastutil's signature postdates its key's published expiry.** It was made 2024-10-19; the expiry on
  keyserver.ubuntu.com and pgp.mit.edu is 2022-11-08. It is cryptographically valid, and the jar matches the brief's
  digest and Central's checksums. Beam's signing key also expired (2023-10-09), but after its signature.
- **The Beam package is `org.apache.beam.vendor.guava.v32_1_2_jre`** (with `_jre`). Its `Ints`/`Longs` bodies are
  byte-identical to Guava 33.4.8's; only constant-pool indices and names differ. The same holds for Guava 31.1.
- **fastutil's `fill` is `@Deprecated`.** Its range check is two calls deep: `IntArrays.ensureFromTo([III)V` →
  `it.unimi.dsi.fastutil.Arrays.ensureFromTo(III)V`. The second begins with an assertion guard on
  `$assertionsDisabled`, which `<clinit>` sets from `desiredAssertionStatus()`, so it depends on `-ea`. A negative
  `from` gives AIOOBE, `from > to` gives `IllegalArgumentException`, and `to > length` gives AIOOBE.
- **The Configuration initializer reads `props.containsKey(...)` and then `props.getProperty(...)`** on the live
  `System.getProperties()` (line 100, lines 167–172). On a child `Properties` with defaults, `containsKey` is false.
- The JVM grids' value sets are this setup's choice where the brief does not list them. They reproduce the brief's
  counts but are not its grids.
- `cake_lpr` exits 0 when it rejects. Acceptance is the stdout line `s VERIFIED UNSAT`. `bounded_sat.py` refuses to
  run if either SAT tool's digest changes.
- elan's default toolchain is the channel `stable`. Name `leanprover/lean4:v4.36.0` (as `replay.py` does) rather than
  a bare `lean`.
- Nothing here is a snapshot dependency. The JavaParser and CSV originals are SNAPSHOT builds of exact commits,
  pinned by digest.

### What is left for the domain work on purpose

- Freezing the checker binary, and its first response to the long-fill, fastutil, Shorts/Chars and reverse requests.
  No request or certificate for them exists, and the consumer was run on none.
- The disposable historical-producer checkout, the tautology and omitted-exit edits, and all five answers per trial.
- Every native run of §3: 336 `first-8-release` through the ordinary entry, `held/prefix-sums`, the 393 and 395
  tasks, the certification path, its controls and its overheads. These run the engine on claims; B9/B11 runs are jobs.
- Managed-runner isolation of each comparison, the Lean range-branch export and its bridge, and the second-opinion
  pilot on 336, 346 and 337.
- §5: the Configuration JSON and YAML runs, the JavaParser and XZ transfer reruns, and the cohort recount. All of these
  are campaign or B11 runs.
- All claims, examples, requests, certificates, scoring and the comparative results table.
