# Setup for the trusted-kernel experiment brief

Mechanical setup for [`in-the-loop-trusted-kernel-experiment-brief.md`](in-the-loop-trusted-kernel-experiment-brief.md),
done on 2026-11-23 by a setup session (Claude Opus 5.5) before the domain work starts. It checked the released Guava
jar and its dependencies against Maven Central and their signatures, extracted and hashed the `Ints` and `Longs` class
entries, checked out the Guava release commit, checked the installed Lean toolchains against their release archives,
fetched and built CaDiCaL 1.9.5 and `cake_lpr` and ran the LRAT round trip on a made-up formula, built the checker's
release binary at this head, and replayed the release behaviours the brief names on a JDK 21 JVM. It wrote no claims,
examples, sidecars, adapters, recipes or checker code, allocated no example ids, and ran neither the project verifier
nor any prover on any claim. Everything downloaded or built is outside the checkout, under `~/.cache/in-the-loop/`,
except the checker binary, which cargo writes to its usual place, `lib/target/release/`.

`$B` below is `~/.cache/in-the-loop/trusted-kernel`. The brief's cases are unmodified releases or in-repo fixtures: no
upstream build and no upstream test run is needed, so **no verification job was queued**. The two baseline commands
of Stage 1 run the project verifier on the existing claims (and `build.py` on a B11 example is a job under
`CLAUDE.md`), so they are left to the domain agent, below.

## Starting commit

The brief's reference is `d717edd200ec3a781b7c7e179200e4a7dc549740` (develop, 2026-11-22). This setup ran at
`3471332a3` ("Merge the single-agent run jbmc-fast-follow into the line"), 150 commits later, with `d717edd2` an
ancestor. Of the paths the brief links, only `lib/tests/integration.rs` changed: one tool-tier test,
`direct_object_array_replays_field_values_and_aliases_in_a_named_package`, was added after line 549 (+80 −3 in the
file). The scalar-pair lines the brief links (`#L464`) and everything else are unchanged: `examples/336-…`,
`examples/346-…`, `examples/337-…`, `lib/python/jvm_array_induction.py`, `examples/tools/targets/array_induction.py`,
`lib/python/test_jvm_array_induction.py`, `lib/src/classfile/bytecode.rs`, `lib/src/bmc/transcript.rs`,
`lib/solvers/README.md`, `lib/tests/fixtures/java/fixtures/Overloads.java`. Check:
`git diff --stat d717edd200ec3a781b7c7e179200e4a7dc549740 HEAD -- PATHS`.

## Layout

| Path | What it holds |
|---|---|
| `$B/releases/guava-33.4.8-jre/{lib,sources}/` | Guava 33.4.8-jre and its whole runtime graph, main and sources jars (hard links to the files `~/.cache/in-the-loop/jbmc-fast-follow` resolved, re-checked here). |
| `$B/keys/central/` | The `.asc` and `.sha1` of every one of those jars, fetched fresh from Maven Central for this setup. |
| `$B/keys/fresh/` | The three signing keys, fetched by full fingerprint from keyserver.ubuntu.com. |
| `$B/gnupg` | This setup's own keyring (`GNUPGHOME=$B/gnupg`). Its agent was stopped. |
| `$B/classes/guava-33.4.8-jre/com/google/common/primitives/` | The 10 class entries `Ints*.class`, `IntsMethodsForWeb.class`, `Longs*.class`, extracted from the release jar; digests in `$B/classes/guava-33.4.8-jre.classes.sha256`. |
| `$B/src/guava-33.4.8` | Worktree of the Guava release commit `f06690fa` (mirror `~/.cache/in-the-loop/git-mirrors/guava.git`). |
| `$B/src/cadical-1.9.5` | Worktree of CaDiCaL `rel-1.9.5`, built: `build/cadical`. Mirror `git-mirrors/cadical.git`. |
| `$B/src/cake_lpr-033aad53` | Worktree of `tanyongkiam/cake_lpr` at its current head, built: `cake_lpr`. Mirror `git-mirrors/cake_lpr.git`. |
| `$B/src/coch-demo-30dfe25a` | Worktree of `marijnheule/coch-demo` (the brief's LRAT example), not built. Mirror `git-mirrors/coch-demo.git`. |
| `$B/probes/jvm/GuavaIndexOf.java` | One throwaway JVM program replaying the brief's release inputs ([below](#what-was-replayed-on-a-jvm)). Not a claim, not an adapter, not a driver. |
| `$B/probes/lrat-smoke/` | The made-up CNFs and proofs of the LRAT round trip ([below](#sat-certificate-toolchain)). |
| `$B/probes/lean-smoke/Smoke.lean` | A two-theorem file that shows both toolchains run and print axioms. |
| `$B/probes/scalar/out-jdk25/` | `Overloads.java` and `TrafficLight.java` compiled as the Rust tests compile them ([below](#scalar-fixtures)). |
| `$B/logs/` | Signature table, `javap -c -p -v` of `Ints`, `Longs`, `IntsMethodsForWeb`, JVM probe output, CaDiCaL and `cake_lpr` build logs, the CaDiCaL upstream-vs-crate diff, the Lean tree listings, the cargo build log. |
| `$B/tmp` | `TMPDIR` for this work. |

## Released artifacts

Guava's runtime graph, as `jbmc-fast-follow`'s setup resolved it with Maven 3.10.0 (`--strict-checksums`); its
classpath is in `~/.cache/in-the-loop/jbmc-fast-follow/releases/guava-33.4.8-jre/classpath.txt`. Here every main and
sources jar was checked again against a fresh copy of Central's `.sha1` (11 of 11 match) and its `.asc` in this
setup's own keyring (11 of 11 `VALIDSIG`; `listenablefuture-9999.0` has no sources jar). Table: `$B/logs/signatures.txt`.

| Jar | sha256 | Signed by |
|---|---|---|
| `guava-33.4.8-jre.jar` | `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed` (**= brief**, = `targets/sha256/f3/…`) | `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` (Christopher Povirk) |
| `error_prone_annotations-2.36.0.jar` | `77440e270b0bc9a249903c5a076c36a722c4886ca4f42675f2903a1c53ed61a5` (= targets) | `EE0CA873074092F806F59B65D364ABAA39A47320` (Liam Miller-Cushon) |
| `jspecify-1.0.0.jar` | `1fad6e6be7557781e4d33729d49ae1cdc8fdda6fe477bb0cc68ce351eafdfbab` (= targets) | `41CD49B4EF5876F9E9F691DABAC30622339994C4` (Chris Povirk) |
| `failureaccess-1.0.3.jar`, `listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.jar`, `j2objc-annotations-3.0.0.jar` | see `jbmc-fast-follow-calls-conversions-and-arrays-setup.md` | `BDB5FA4F…` |

The example preparer's own cache, `~/.cache/in-the-loop/targets/sha256/`, already holds the three jars that 336's
and 346's `target.json` list (guava, error_prone_annotations, jspecify), each matching its name. `build.py` reads them
from there: nothing needs fetching for the baseline commands.

### Class entries

Extracted with `unzip` from the release jar. Class-file major version 52 (Java 8) for all.

| Entry | sha256 | Bytes |
|---|---|---|
| `com/google/common/primitives/Ints.class` | `ae581f721521c93250639d17348c5b7215f3591a1bb433fb63985caa4364edbb` | 9186 |
| `com/google/common/primitives/IntsMethodsForWeb.class` (superclass of `Ints`) | `a31b977048c2bc8257a8371ab2c89e9026e0c52507746c09e34a47ad94217bd6` | 445 |
| `com/google/common/primitives/Longs.class` (superclass `java.lang.Object`) | `b8c75a5f24b89f0a6a263bd56b4e4e9f4c53bd7a1e8e2fc9ad4975113f4396d9` | 9547 |
| `Ints$IntArrayAsList`, `Ints$IntConverter`, `Ints$LexicographicalComparator`, `Longs$AsciiDigits`, `Longs$LexicographicalComparator`, `Longs$LongArrayAsList`, `Longs$LongConverter` | `$B/classes/guava-33.4.8-jre.classes.sha256` | |

These equal the digests in 336's and 346's `first-any-length` records (`classes` in `result.json`; 336's record binds
`Ints` and `IntsMethodsForWeb`, 346's binds `Longs` alone) and in their bounded receipts. Neither `Ints`,
`IntsMethodsForWeb` nor `Longs` has a static initializer (`<clinit>`). The four methods, from `javap -c -p`
(full output in `$B/logs/javap-*.txt`):

```text
Ints.indexOf([II)I         0 aload_0; 1 iload_1; 2 iconst_0; 3 aload_0; 4 arraylength; 5 invokestatic #11 indexOf:([IIII)I; 8 ireturn
Ints.indexOf([IIII)I       (private) 0 iload_2; 1 istore 4; 3 iload 4; 5 iload_3; 6 if_icmpge 26; 9 aload_0; 10 iload 4; 12 iaload;
                           13 iload_1; 14 if_icmpne 20; 17 iload 4; 19 ireturn; 20 iinc 4,1; 23 goto 3; 26 iconst_m1; 27 ireturn
Longs.indexOf([JJ)I        0 aload_0; 1 lload_1; 2 iconst_0; 3 aload_0; 4 arraylength; 5 invokestatic #11 indexOf:([JJII)I; 8 ireturn
Longs.indexOf([JJII)I      (private) 0 iload_3; 1 istore 5; 3 iload 5; 5 iload 4; 7 if_icmpge 28; 10 aload_0; 11 iload 5; 13 laload;
                           14 lload_1; 15 lcmp; 16 ifne 22; 19 iload 5; 21 ireturn; 22 iinc 5,1; 25 goto 3; 28 iconst_m1; 29 ireturn
```

### Source

Guava tag `v33.4.8` is a lightweight tag on GitHub pointing at `f06690fa3e874f65515e8fd338a74d636e2c792f` (checked
with `git ls-remote`), the commit 336's and 346's `target.json` pin. The commit is not signed. `Ints.java`,
`Longs.java` and `IntsMethodsForWeb.java` at that commit are byte-identical to the ones in the signed sources jar
(sha256 `2e997bb7…e992e2`, `fafc1a56…29f2c0`, `714bd9d9…753c6`). Worktree: `$B/src/guava-33.4.8`, files under
`guava/src/com/google/common/primitives/`.

## JDK, solver and checker

| Tool | Where | Identity |
|---|---|---|
| JDK 21 (the preparer's, `runtime_jdk.home("21")`) | `~/.sdkman/candidates/java/21.0.13.0+9-tem` | Temurin 21.0.13+9; `lib/modules` sha256 `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c`, the same image the existing records name and the `jbmc-fast-follow` setup checked. |
| JDK on `PATH` (`current`) | `~/.sdkman/candidates/java/25.0.5.0+8-tem` | javac 25.0.5; what the Rust tests' `compile()` uses. |
| Z3 | `~/.local/bin/z3` → `~/tools/z3/z3-5.3.3-x64-glibc-2.39/bin/z3` | "Z3 version 5.3.3 … build hashcode 430d19e6…", sha256 `fcd0ca765d1c0b4eac776f442ec0f10294b9a6416be91fad4e52fa19012c8d01`, **= the solver both existing records name**. The system Python has no `z3` module; the induction route calls the binary. |
| Checker | `lib/target/release/jvmcontract` | Built with `cargo build --release --manifest-path lib/Cargo.toml` at `3471332a3` (4 min 20 s, under an 8 GB cap); sha256 `b1e0edad5632990ef4797b8aaf23f82fa0beba809c9c8d8cfbd00805cf5ef389`. A rebuild after any change to `lib/` changes it. |
| Rust | `~/.local/bin/{rustc,cargo}` | rustc 1.99.1 (58cf8f9c3 2026-10-13). |
| CaDiCaL inside the checker | `cadical` crate 0.1.16 (`Cargo.lock` checksum `a54f8130…7778e`) | Bundles CaDiCaL **1.9.5**. Its sources differ from upstream `rel-1.9.5` in 11 files, all Windows portability (`_WIN32` branches, `_popen`, `_BitScanReverse`, stub RSS on Windows, an include moved): `$B/logs/cadical-upstream-vs-crate-0.1.16.diff`. On Linux the solver is upstream 1.9.5. |
| gcc | `/usr/bin/gcc` | 15.2.0 (Ubuntu 15.2.0-16ubuntu1), used for CaDiCaL and `cake_lpr`. |

## SAT certificate toolchain

| Tool | Revision | Build | Binary sha256 |
|---|---|---|---|
| CaDiCaL CLI 1.9.5 | `arminbiere/cadical` tag `rel-1.9.5` (lightweight) = `146207318796f094dcded87349a64f0c6927309e`; `VERSION` says 1.9.5 | `cd $B/src/cadical-1.9.5 && ./configure && make -j8` (under a minute) | `0fabbda6d757d7076ca003c8e9ffadd4ef893c3cacaabcf5986c415e0de74ec4` (`build/cadical`) |
| `cake_lpr` | `tanyongkiam/cake_lpr` head `033aad53d1733bd4b8ca41cf6f1b5fb5d84f8de2` (2026-11-01, "last cake_lpr update (before overhaul)"); built from HOL4 `9783a499…`, CakeML `665f9b21…` per its README | `cd $B/src/cake_lpr-033aad53 && sha256sum -c cake_lpr.sha256 && make` (`cc -O2 basis_ffi.c cake_lpr.S -o cake_lpr`) | `c14ff49853e890436d6a2fbf66a85b9492dad1dcd2d76254f16a89f2236c8a54` |
| coch-demo | `marijnheule/coch-demo` head `30dfe25a047604379b6b649c5e884054618e8a9f` | not built (reference only) | |

`cake_lpr.sha256` (Makefile, `basis_ffi.c`, `cake_lpr.S`, `cake_lpr_arm8.S`) all pass, but it lives in the same
repository as the files it covers, so it binds them to the commit and no more. Neither repository signs its tags or
commits.

The round trip, on made-up formulas (`$B/probes/lrat-smoke/`): pigeonhole 4 into 3 (`php43.cnf`, 12 variables, 22
clauses) and a two-clause satisfiable formula (`sat.cnf`).

```sh
CAD=$B/src/cadical-1.9.5/build/cadical; CAKE=$B/src/cake_lpr-033aad53/cake_lpr
$CAD -q --lrat --no-binary php43.cnf php43.lrat   # exit 20, "s UNSATISFIABLE"; text LRAT, 347 bytes
$CAD -q --lrat php43.cnf php43.blrat              # binary LRAT (the default with --lrat)
$CAKE php43.cnf php43.lrat                        # "s VERIFIED UNSAT"; the binary proof too
```

| Input | `cake_lpr` stdout | Exit |
|---|---|---|
| `php43.cnf` + its text LRAT | `s VERIFIED UNSAT` | 0 |
| `php43.cnf` + its binary LRAT | `s VERIFIED UNSAT` | 0 |
| proof with its last line removed | `c empty clause not derived at end of proof` | **0** |
| proof with one literal of its first lemma negated | `c Checking failed at line: 0. Reason: clause not empty or singleton after reduction` | **0** |
| `sat.cnf` + the pigeonhole proof | `c Checking failed at line: 0. Reason: clause index unavailable: 22` | **0** |

**`cake_lpr` exits 0 whether it accepts or not.** Acceptance is the line `s VERIFIED UNSAT` on stdout and nothing
else. CaDiCaL's exit codes are the usual 10 (SAT) and 20 (UNSAT).

Peak memory: GNU `time` is not installed (`time` is the shell keyword only). This works and needs nothing new:
`python3 -I -c "import resource,subprocess,sys; subprocess.run(sys.argv[1:]); print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)" CMD…`
(KiB; about 12 MB for either tool on the pigeonhole formula).

## Lean

elan's default is the channel `stable` (`~/.elan/settings.toml`), so a bare `lean` moves with each release:
running `lean --version` during this setup fetched and installed **v4.36.0**, which `stable` now resolves to. Two
toolchains are installed:

| Toolchain | Commit | Archive sha256 (`lean-V-linux.tar.zst`, = GitHub's asset digest) | Installed tree |
|---|---|---|---|
| `leanprover/lean4:v4.36.0` | `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9` | `2b7ab1ed8b92d2e6abfaf41344823b510064dbc9c0260cac73eb496ab2dea6eb` | identical to the archive's (every file's sha256; `$B/logs/inst-4.36.0.txt`) |
| `leanprover/lean4:v4.35.0` | | `7289597a44543246c9227b8cae501767e095ce17f6d448b95fc4a8dc97268f6d` | identical to the archive's (`$B/logs/inst-4.35.0.txt`) |

`elan run leanprover/lean4:v4.36.0 lean $B/probes/lean-smoke/Smoke.lean` checks a `bv_decide` proof of
`2 * x = x + x` over `BitVec 32` (with `import Std.Tactic.BVDecide`) and prints its axioms
(`propext, Classical.choice, Quot.sound`); a `Nat.add_comm` theorem prints "does not depend on any axioms". The
same holds on v4.35.0. No Lake package, Mathlib or other library was fetched: none is named in the brief.

## Scalar fixtures

`lib/tests/fixtures/java/fixtures/Overloads.java` holds `twice(int) = 2 * x` (and `twice(long) = 2L * x`). The
`x * 2` and `x + x` methods are Java strings inside `lib/tests/integration.rs` (`Shares.twice` at lines 464 and 484),
compiled at test time by `compile()`: `javac -parameters -g -proc:none -d OUT SOURCES` with the `javac` on `PATH`,
which is JDK 25. The fixture folder does **not** compile with JDK 21: `TrafficLight.java`, which `Overloads.java`
uses, has an unnamed variable (`case Next _`), a preview feature before 22. Compiled the test's way with javac 25
(`$B/probes/scalar/out-jdk25/`, major 69), `Overloads.twice(int)` is `iconst_2; iload_0; imul; ireturn`. The choice of
JDK and the frozen byte sequences are the domain work's; nothing was frozen here.

## What was replayed on a JVM

`$B/probes/jvm/GuavaIndexOf.java` (sha256 `59a17bd2…0bc38`) calls the release methods with the brief's inputs on
Temurin 21.0.13, prints the sha256 of each class as the JVM loaded it, and checks the array is unchanged after each
call. Output: `$B/logs/jvm-guava-indexof.txt`. All 14 cases as the brief says:

| Call | Result |
|---|---|
| `Ints.indexOf([7, 7], 7)` | 0 (the first match; the brief's last-match mutant would give 1) |
| `Ints.indexOf([], 7)` | −1 |
| `Ints.indexOf([5], 5)` | 0 (singleton at index zero) |
| `Ints.indexOf([1, 2, 3], 4)` | −1 |
| `Ints.indexOf([MIN, MAX], MAX)` / `(…, MIN)` | 1 / 0 |
| `Ints.indexOf([0, 3, 1, 3], 3)` | 1 |
| `Longs.indexOf([7, 7], 7)`, `([], 7)`, `([5], 5)` | 0, −1, 0 |
| `Longs.indexOf([0, 4294967296], 4294967296)` | **1** (a truncating comparison would give 0) |
| `Longs.indexOf([4294967296], 0)` | −1 (same low 32 bits, no match) |
| `Longs.indexOf([Long.MIN, Long.MAX], MAX)` / `(…, MIN)` | 1 / 0 |

Every array was unchanged after its call, and the loaded classes had the digests above. To rerun:

```sh
J=~/.sdkman/candidates/java/21.0.13.0+9-tem/bin; CP=$(ls $B/releases/guava-33.4.8-jre/lib/*.jar | tr '\n' ':')
$J/javac -d $B/probes/jvm/out -cp "$CP" $B/probes/jvm/GuavaIndexOf.java && $J/java -cp "$B/probes/jvm/out:$CP" GuavaIndexOf
```

The mutants of the brief's controls (last match, wrong wrapper or helper, damaged heap, no-progress loop, the
harmless layout change) are not built: designing and compiling them is the experiment's work.

## Commands for the domain work

| What | Command (from the repository root) | Notes |
|---|---|---|
| Stage 1 baseline, 336 | `python3 examples/tools/build.py 336 --array-induction first-any-length --compare` | Runs the project verifier on the existing claims: not run here. `build.py` on a B11 example is a job under `CLAUDE.md`. Inputs are all cached. |
| Stage 1 baseline, 346 | `python3 examples/tools/build.py 346 --array-induction first-any-length --compare` | The same. |
| SAT comparator transcript | `JVMCONTRACT_TRANSCRIPTS=DIR python3 examples/tools/build.py 336 --task first-8-release` | Not run here (native engine on a claim). Each check writes `DIR/PID-N.icnf` (`p inccnf`; `a … 0` lines are calls, each followed by `c answer …`); `jvmcontract transcript FILE` replays one. The fallback workload `held/prefix-sums` is in `lib/solvers/compare.py` `CASES`. |
| 337 (optional) | `python3 examples/tools/build.py 337 --array-induction fill-any-length` (then `caller-any-length`, `caller-extra-any-length`) | 337 is B9 (a job), route `fixture`, JDK 21; nothing to fetch. |
| Checker binary | `cargo build --release --manifest-path lib/Cargo.toml` | Done at this head ([above](#jdk-solver-and-checker)). |

Offline: none of these fetches anything once the caches above exist; Maven and Gradle are not involved.

## Setup Agent Notes

### What is ready, and where

`$B` = `~/.cache/in-the-loop/trusted-kernel`.
- The release jar `guava-33.4.8-jre.jar` (sha256 `f3d7f57f…e617ed`, = brief) and its runtime graph, signature- and
  checksum-checked: `$B/releases/guava-33.4.8-jre/lib/`; sources jars beside it. The preparer's cache
  (`~/.cache/in-the-loop/targets/sha256/`) already holds what 336 and 346 list.
- The class bytes, extracted: `$B/classes/guava-33.4.8-jre/com/google/common/primitives/`. `Ints.class`
  `ae581f72…a7151`, `IntsMethodsForWeb.class` (its superclass) `a31b9770…17bd6`, `Longs.class` `b8c75a5f…96d9`; all
  equal to the existing records. `javap` of each: `$B/logs/javap-*.txt`.
- Guava source at the release commit `f06690fa`: `$B/src/guava-33.4.8`.
- CaDiCaL 1.9.5 CLI: `$B/src/cadical-1.9.5/build/cadical`. `cake_lpr`: `$B/src/cake_lpr-033aad53/cake_lpr`. LRAT
  round-trip example: `$B/probes/lrat-smoke/`.
- Lean `v4.36.0` and `v4.35.0`, both checked file by file against their release archives.
- JDK 21 (Temurin 21.0.13+9), Z3 5.3.3 (the records' binary, same digest), and the checker built at this head.

### What was verified on a JVM

On Temurin 21.0.13 with the release jar: `Ints.indexOf([7,7],7) = 0`, empty → −1, `[5]`/5 → 0, signed extrema at
both ends, and `Longs.indexOf([0, 2^32], 2^32) = 1` (no truncation), `[2^32]`/0 → −1, `Long` extrema; every input
array unchanged, and the classes the JVM loaded have the digests above (`$B/logs/jvm-guava-indexof.txt`, 14 of 14).
None of the brief's mutants exists yet.

### What to know before starting

- This head is `3471332a3`, 150 commits after the brief's `d717edd2`. Of the linked paths, only
  `lib/tests/integration.rs` changed (one test added after line 549); the `#L464` scalar lines are unchanged.
- **`cake_lpr` exits 0 when it rejects.** Read stdout for `s VERIFIED UNSAT`. It rejected a truncated proof, a proof
  with one literal flipped, and a proof against a satisfiable formula, all with exit 0.
- `cake_lpr` is at its upstream head, whose README says it is the last release before it is "superseded by a new
  checker in this repository": pin `033aad53`, not the branch. Heap and stack sizes are flags
  (`--CML_HEAP_SIZE=<MiB>`), no longer environment variables.
- The checker's bundled solver is CaDiCaL 1.9.5 (crate `cadical` 0.1.16), differing from the upstream tag only in
  Windows portability code, so the brief's pinned CLI is the same solver as the engine's.
- `lean` follows elan's `stable` channel and moved to v4.36.0 during this setup. Pin a toolchain (a
  `lean-toolchain` file or `elan run leanprover/lean4:vX`) before recording "the exact Lean version".
- The scalar fixtures are compiled by the tests with javac 25 (`-parameters -g -proc:none`), not JDK 21, and the
  fixture folder does not compile with JDK 21 (`TrafficLight.java` uses `_`). `Overloads.twice(int)` is
  `iconst_2; iload_0; imul; ireturn` under javac 25.
- GNU `time` is absent; the `resource.getrusage(RUSAGE_CHILDREN)` line above gives peak memory.
- Nothing here is a snapshot: every input is a pinned release, tag or commit.

### What is left for the domain work on purpose

- The two Stage 1 baseline runs (`build.py 336|346 --array-induction first-any-length --compare`), which run the
  verifier on the existing claims: submit them as jobs (B11) or run them as the brief and `CLAUDE.md` allow.
- The `first-8-release` transcript for the SAT comparator, the choice of query, the DIMACS export and its LRAT proof.
- The claim, assumptions, certificate format, the scalar pair (methods, JDK, frozen bytes), all controls and mutants,
  the Rust and Lean checkers, and the optional 337 runs.
