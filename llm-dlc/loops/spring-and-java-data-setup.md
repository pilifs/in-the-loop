# Setup for the Spring and Java data briefs

Mechanical setup for [`spring-and-java-data-workstream-briefs.md`](spring-and-java-data-workstream-briefs.md), done
on 2026-11-22 by a setup session (Claude Opus 5.5) before the domain work starts. It fetched the pinned sources and
dependencies, built the original artifacts, and ran the original regressions and the brief's headline JVM witnesses.
It wrote no claims, examples, sidecars, adapters or recipes, and changed nothing in `lib/` or the checker. Everything
it downloaded or built lives outside the checkout, under `~/.cache/in-the-loop/`.

Status of each subject is in the [summary table](#summary) at the end.

## Layout

| Path | What it holds |
|---|---|
| `~/.cache/in-the-loop/git-mirrors/{spring-framework,spring-security,commons-lang,vavr}.git` | One bare repository per upstream, shared. Only the pinned commits were fetched (`git fetch --depth=2 origin SHA`, depth 4 for Spring Security), not branches or tags. `origin` points at the GitHub repository. |
| `~/.cache/in-the-loop/spring-java-data/src/NAME` | One detached worktree per pinned revision (names below). Check out another with `git -C ~/.cache/in-the-loop/git-mirrors/R.git worktree add --detach DIR SHA` after `git fetch --depth=1 origin SHA`. |
| `~/.cache/in-the-loop/spring-java-data/m2` | The Maven local repository for these builds and for the release artifacts. |
| `~/.cache/in-the-loop/spring-java-data/maven-settings.xml` | Settings that point Maven at that repository (`mvn -s THIS ...`). Default remote repositories (Central). |
| `~/.cache/in-the-loop/spring-java-data/gradle-home` | `GRADLE_USER_HOME` for the Spring builds: wrapper distributions and the dependency cache. |
| `~/.cache/in-the-loop/spring-java-data/artifacts` | The jars built from each pinned revision, named after the worktree. |
| `~/.cache/in-the-loop/spring-java-data/releases` | Released artifacts from Maven Central, with their classpaths. |
| `~/.cache/in-the-loop/spring-java-data/logs` | The log of every build and test run named below. |
| `~/.cache/in-the-loop/spring-java-data/probes` | The throwaway JVM programs that replayed the brief's witnesses (not claims, not adapters). |
| `~/.cache/in-the-loop/spring-java-data/keys`, `gnupg` | Public keys used to check signatures, in a keyring of their own (`GNUPGHOME=.../gnupg`), apart from the user's. |

JDKs (SDKMAN, already installed): `~/.sdkman/candidates/java/8.0.512.0+9-tem`, `11.0.33.0+10-tem`,
`17.0.21.0+9-tem`, `21.0.13.0+9-tem` (the brief's preflight JVM, OpenJDK 21.0.13), `25.0.5.0+8-tem`. Maven 3.10.0
(`~/.sdkman/candidates/maven/current`, runs on JDK 8 too). Nothing had to be downloaded for a JDK.

## Pinned revisions

Every commit was fetched by its full id, so its content is checked by git's object ids. The tree ids are recorded so
a source slice can be compared without the history. Each landed commit's first parent is the brief's "before"
commit; for Spring Security the chain is `10d88cdf → 7d366242 → ee8bc78c`, as the brief says.

| Subject | Worktree | Commit | Tree | Date, author | Signature |
|---|---|---|---|---|---|
| A2 before | `spring-security-14196-before` | `10d88cdf28449cbc4789edfe7111f2cdec9902d6` | `570195076377a4606f6e776d33a16c56f4fa2ae9` | 2023-12-06, Josh Cummings | unsigned |
| A2 feature | `spring-security-14196-feature` | `7d366242ce4ec377880fdb29b7e5ba068cf52deb` | `462c9c83ee48cd9393d81eed2b8f2b134179660a` | 2023-11-26, Federico Herrera | unsigned |
| A2 landed | `spring-security-14196-landed` | `ee8bc78cbcd4a0a42c7e7dc2a05b5aeb29c336ae` | `b94f6141f520a83ec0a0660c7f4102dee4562d5b` | 2023-12-06, Josh Cummings | unsigned |
| A3 parent | `spring-framework-36911-parent` | `fd95ab16baa2353416e96bddbd979169a9618260` | `85ca69bfa4e2b93deaf2e4ab5027297dbce2dfcb` | Sam Brannen | good SSH signature, Sam Brannen's GitHub signing key |
| A3 landed | `spring-framework-36911-landed` | `f067d40f0a646a98d0e2735a34b6e31f0e3f2c97` | `527211e78415a7d4382db393fb9975592f108fac` | 2026-08-20 | good, GitHub web-flow key `968479A1…B5690EEEBB952194` |
| A4 parent | `spring-framework-23893-parent` | `43a86565cac09de05e50678721cbc83a61a43a6e` | `13cf3cbf3ae71bfddcfd111c9e4e57554f9c32b0` | Juergen Hoeller | unsigned |
| A4 landed | `spring-framework-23893-landed` | `4beb25b318486baef65fbc3c1118b43aab9f3dc5` | `c664e4296a9c03f83384be27d8a8af233018e251` | 2019-10-30, Brian Clozel | unsigned |
| B2 parent | `vavr-1829-parent` | `a8cace88bfb12a9a7e1977a5765753798962e942` | `2f14c9a300b7d2f321571648d1217739dc65e1db` | GitHub merge | unsigned |
| B2 landed | `vavr-1829-landed` | `84a4c690a009c55098ec8f7106c4867e0af747c0` | `29d530af36e1cc3e4b6d83025a7af948c6793cf3` | 2017-01-20, Pap Lőrinc | unsigned |
| B3 parent | `commons-lang-1589-parent` | `9bca5d09c6d16a5524a3cd1d38305687ad7fdca4` | `720946d836bcbd7b27096f9ada7e119bd62a64c6` | Gary Gregory | good, `F4DD59C9…530AA5F25C25011F` (Gary Gregory, in Apache Commons KEYS) |
| B3 landed | `commons-lang-1589-landed` | `52c06bea2f2b6c277c517dc9f5bb0d62d17e073c` | `2b05e8671a71c9bbb6a52124803fdceaabc0c089` | 2026-01-28, Ivan Ponomarev | good, GitHub web-flow key |
| B4 parent | `commons-lang-1635-parent` | `1dd7cb14c233140a8e76ba5441b6360a239a98dc` | `29241e075b006eca8158b5ae60e6857728add51d` | Gary Gregory | good, `F4DD59C9…530AA5F25C25011F` |
| B4 landed (also B1) | `commons-lang-1635-landed` | `5904c573ffacaa5d8836ffc2b346f400c8901ed1` | `a2ba93de7141b6a03d336c97c0e5ca588aa7fb46` | 2026-05-05, Gary Gregory | good, GitHub web-flow key |

"Good" means `git log --format=%G?` gave `U`: a good signature from a key with no trust path in that private keyring.
The keys came from `https://github.com/web-flow.gpg` (sha256 `6e8af687…a3ef84`), the Apache Commons KEYS file
`https://downloads.apache.org/commons/KEYS` (sha256 `f154a693…3299a`), and
`https://api.github.com/users/sbrannen/ssh_signing_keys` (sha256 `4ebe6133…23d625`), all read on 2026-11-22. To check
again: `GNUPGHOME=~/.cache/in-the-loop/spring-java-data/gnupg git -C MIRROR log -1 --format=%G?%GF SHA`, and for the
SSH signature `git -c gpg.ssh.allowedSignersFile=~/.cache/in-the-loop/spring-java-data/keys/allowed_signers verify-commit fd95ab16`.

## Brief B · data processing

### Commons Lang (B1, B3, B4)

Build: Maven, `commons-parent` 96 (`#1589` pair) and 99 (`#1635` pair), version `3.21.0-SNAPSHOT`, source and target
1.8. Built and tested with JDK 21.0.13 (`JAVA_HOME=~/.sdkman/candidates/java/21.0.13.0+9-tem`). Each compile took
about 20 s, each named-test run 6 to 11 s, all inline.

```bash
B=~/.cache/in-the-loop/spring-java-data
export JAVA_HOME=~/.sdkman/candidates/java/21.0.13.0+9-tem TMPDIR=$B/tmp
cd $B/src/commons-lang-1589-parent        # or -1589-landed, -1635-parent, -1635-landed
mvn -o -B -s $B/maven-settings.xml -ntp test-compile
mvn -o -B -s $B/maven-settings.xml -ntp test -Dtest='ArrayUtilsTest#testIndexOfDoubleNaN+testContainsDoubleNaN+testIndexOfDoubleTolerance'   # B3
mvn -o -B -s $B/maven-settings.xml -ntp test -Dtest='NumberUtilsTest#testCreateNumber+testCreateBigDecimal+testCreateDouble'               # B4
mvn -o -B -s $B/maven-settings.xml -ntp -DskipTests -Dmaven.javadoc.skip=true -Dmaven.source.skip=true package
```

The offline form (`-o`) works for all four revisions for `test-compile`, `test` and `package` (checked). Running
without `-Dtest` runs the whole suite; the default goal of `commons-parent` adds RAT, japicmp, checkstyle, PMD,
SpotBugs and Javadoc, none of which were run or fetched.

**Named upstream tests.** Each side's own test methods pass on that side (3 of 3 each). The test changes of both
PRs only add assertions to existing methods:

- `#1589` adds tolerance-taking assertions to `ArrayUtilsTest#testContainsDoubleNaN`, `#testIndexOfDoubleNaN` and
  `#testIndexOfDoubleTolerance`.
- `#1635` adds `"0.100000001490116121"` assertions to `NumberUtilsTest#testCreateBigDecimal`, `#testCreateDouble`
  and `#testCreateNumber` (the last is the regression; the rest of that diff reflows lines).

**The regression, transplanted.** The landed test file compiled against the parent's production code, in a
throwaway copy of the parent worktree (deleted after), fails as expected:

- `#1589`: 2 of 3 fail, `testIndexOfDoubleNaN` `expected: <1> but was: <-1>` and `testContainsDoubleNaN`
  `expected: <true> but was: <false>`. Log: `logs/commons-lang-1589-parent.landed-tests-on-parent.log`.
- `#1635`: `testCreateNumber` fails, `expected: <0.100000001490116121> but was: <0.1>` (line 646). Log:
  `logs/commons-lang-1635-parent.landed-tests-on-parent.log`.

**Built jars** (`artifacts/`, `Build-Jdk-Spec: 21`). Jar digests include build timestamps; the class digests show that
each pair differs exactly in the class the PR changed (first 16 hex digits of sha256):

| Jar | sha256 | `ArrayUtils.class` | `math/NumberUtils.class` |
|---|---|---|---|
| `commons-lang-1589-parent.jar` | `4487945e5a4bbcfbf0eeae7c9a0b96bb09968d66236657e9523f2c2d9be50425` | `0509c97f1785880b` | `30aaccb455344893` |
| `commons-lang-1589-landed.jar` | `c28e470a728a9ccbfa03e474daf20ace98b8a86f38cc3df3fccafa3000abb775` | `a421c9e2f6084ed8` | `30aaccb455344893` |
| `commons-lang-1635-parent.jar` | `e83aa9d86adf5d0c613f107c54faedd5f9e57f12cdb4ec308f554537c35e2f38` | `89f3f0cb8ad76107` | `c667f2bac810296e` |
| `commons-lang-1635-landed.jar` | `4f6b509b49e10b69de68d29cd4c7c0f378a6ee5f9e97f22778e24290de675d1c` | `89f3f0cb8ad76107` | `33f7877270f9c6f9` |

The worktrees' `target/` folders were left in place (about 30 MB each) so the domain agent can compile against
`target/classes` and `target/test-classes` at once; delete them freely, a rebuild is 20 s offline.

**Released Commons Lang 3.17.0** (for B1's single-row diagnostic), in `releases/commons-lang3-3.17.0/`: the jar and
sources jar from `https://repo.maven.apache.org/maven2/org/apache/commons/commons-lang3/3.17.0/`, SHA-1 matching
Central's `.sha1` files, and the jar's `.asc` a good signature by Gary David Gregory's code signing key
`2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (from the Apache Commons KEYS file). sha256: jar
`6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4`, sources
`5fdcac21ad329766054a95367d7583dfcdca737d221d5e01a5f2a198c04c6b18`.

**The brief's JVM witnesses, replayed** on JDK 21.0.13 against the built jars (programs in `probes/b/`, run as
`java -cp JAR Witness.java`):

- B1 (`commons-lang-1635-landed.jar`, and the same on 3.17.0): row `a` gives `[-2, 0, 0, 0, 7]`; the eight-row
  fixture gives 28 of 28 distinct output-row pairs; writing `out[0][0]` leaves the sibling row, the input and a second
  call's result unchanged; an empty outer array gives an empty result. `javac` 21 compiles `parseRows` to exactly
  four `invokedynamic` sites (two `Function`, two `IntFunction`), with `Integer.valueOf(I)` boxing in the generated
  adaptation; `probes/b/cls/B1Witness.class` is the compiled caller.
- B3: `indexOf([-∞, NaN, +∞, -0.0, +0.0], NaN, 0, 0.0)` is −1 on the parent and 1 on the landed jar; −∞, +∞ and 0.0
  give 0, 2 and 3 on both.
- B4: `createNumber` of `0.100000001490116121`, `…122` and `-0.100000001490116121` gives `Float 0.1` (or `-0.1`) on
  the parent and `BigDecimal` with unscaled value `100000001490116121` (`…122`, negative) and scale 18 on the landed
  jar; `0.1`, `0.5`, `17` give `Float 0.1`, `Float 0.5`, `Integer 17` on both; `1eE` throws `NumberFormatException` on
  both.

### Vavr / Javaslang (B2)

Build: Maven, parent `2.1.0-SNAPSHOT` (`oss-parent` 9), modules `javaslang`, `javaslang-match`, `javaslang-test`;
`javaslang` regenerates `src-gen` with a Scala 2.11.7 script through `scala-maven-plugin` 3.2.2 at
`generate-sources`. Built with **JDK 8** (`8.0.512.0+9-tem`); Maven 3.10.0 runs on it. On both revisions the
regenerated `src-gen` is identical to the committed one (`git status` clean after the build). Compile about 30 s.

```bash
B=~/.cache/in-the-loop/spring-java-data
export JAVA_HOME=~/.sdkman/candidates/java/8.0.512.0+9-tem TMPDIR=$B/tmp
cd $B/src/vavr-1829-landed                # or vavr-1829-parent
mvn -o -B -s $B/maven-settings.xml -ntp -pl javaslang -am test-compile
L='shouldNotTransposeForMissingOrEmptyValues+shouldTransposeIfMultiValuedWithMoreColumnsThanRows'
mvn -o -B -s $B/maven-settings.xml -ntp -pl javaslang -am test -DfailIfNoTests=false \
    -Dtest="ListTest#$L,StreamTest#$L,QueueTest#$L,ArrayTest#$L,VectorTest#$L"
mvn -o -B -s $B/maven-settings.xml -ntp -pl javaslang -am -DskipTests -Dmaven.javadoc.skip=true -Dmaven.source.skip=true package
```

`-o` works for both revisions for `test-compile`, `test` and `package` (checked).

**Named upstream tests.** `AbstractSeqTest#shouldNotTransposeForMissingOrEmptyValues` exists only on the landed
side (the PR replaces the parent's `shouldTransposeIfMissingValues`, `shouldTransposeIfMissingAndEmptyValues` and
`shouldNotBeEqualIfTransposedTwiceWithMissingValues` with it, and renames
`shouldBeEqualIfTransposedTwiceWithNoMissingValues` to `shouldBeEqualIfTransposedTwice`, now expecting
`IllegalArgumentException`). `#shouldTransposeIfMultiValuedWithMoreColumnsThanRows` exists on both. The concrete
subclasses that inherit them are `ListTest`, `StreamTest`, `QueueTest`, `ArrayTest`, `VectorTest` (and
`CharSeqTest`, not run).

- Landed, the two named methods through the five concrete classes: 10 of 10 pass (27 s, offline).
- Parent, its own `shouldTransposeIfMissingValues`, `shouldTransposeIfMissingAndEmptyValues` and
  `shouldTransposeIfMultiValuedWithMoreColumnsThanRows` through the same five: 15 of 15 pass.
- The landed `AbstractSeqTest.java` on the parent's production code (throwaway copy): `ListTest` 2 run, 1 fails,
  `shouldNotTransposeForMissingOrEmptyValues` `Expected exception: java.lang.IllegalArgumentException`. Log:
  `logs/vavr-1829-parent.landed-tests-on-parent.log`.

**Built jars** (`artifacts/`, `Build-Jdk: 1.8.0_512`):

| Jar | sha256 | `collection/Collections.class` | `collection/List.class` |
|---|---|---|---|
| `vavr-1829-parent.jar` | `514ffd18de1df82478bfb73d49735b81aede41333ffe9475af126fb0246bcb5b` | `1c8a78c4a2430c5d` | `8394ac5807e3e14b` |
| `vavr-1829-landed.jar` | `5ad6e4ae3cfc10b1377dced13f796906aad8d0a48df7cf86a83b59db0885713e` | `10618033b82bf305` | `40f536c3cd74d9af` |

The jar has no dependencies at run time. **The brief's table, replayed** on JDK 21.0.13 (`probes/b2/B2Witness.java`):
all four rows match, `[[1,2],[3]]` and `[[],[1]]` giving `[[1,3],[2]]` and `[[1]]` on the parent and
`IllegalArgumentException` on the landed jar, `[[],[]]` giving `List()` on both. The 400-matrix grid was not
enumerated here: that is the domain agent's to freeze.

## Brief A · Spring

### Released artifacts (A1, A2's release controls, A3's and A4's slice dependencies)

Each graph was resolved from Maven Central by a throwaway POM in `~/.cache/in-the-loop/spring-java-data/resolve/NAME/`
(a Spring Framework BOM import where a Framework version is forced), with `mvn --strict-checksums`, so every file's
SHA-1 was checked against Central's. Each `releases/NAME/` folder holds `lib/` (the jars), `sources/` (their sources
jars), `classpath.txt` (the ordered classpath, absolute paths into `m2/`, ready for `java -cp $(cat classpath.txt)`)
and `tree.txt` (`mvn dependency:tree`). To redo one: `cd resolve/NAME && mvn -B -s ../../maven-settings.xml
--strict-checksums dependency:copy-dependencies -DoutputDirectory=../../releases/NAME/lib`; add `-o` once cached.

| Graph (`releases/…`) | For | Jars (sha256) |
|---|---|---|
| `spring-framework-6.2.3` | A1 | spring-context `53feea6d8c61a25089d8c474c4f92ebd24f0ef7eb52ecdaf46f11e9a253fdb4e`, spring-beans `4e289d6c0aa3ea74633005dae06d7cc827510e5b840d68bfcebdcf0bdd363f44`, spring-core `49531684df2304f0e611f775faba79273c77504eb7d856592d830e2389e9eb14`, spring-aop `5e6fc3da…`, spring-expression `e901e26b…`, spring-jcl `8c65ec5e…`, micrometer-observation 1.14.4 `28dd4b00…`, micrometer-commons 1.14.4 `6bb0f56f…` |
| `spring-security-6.3.0-framework-6.1.7` | A2 combined grid, A1 requalification | spring-security-core 6.3.0 `038a52f99d98f2843be8a382f5b18a2583be8dcb78bf4f7b4ab177fb7b36bd91`, spring-security-crypto 6.3.0 `dcce78f1…`, spring-context 6.1.7 `43cef529…`, spring-beans 6.1.7 `c65ed71b…`, spring-core 6.1.7 `9391d131…`, spring-aop, spring-expression, spring-jcl 6.1.7, micrometer 1.12.6 |
| `spring-security-6.2.0-framework-6.1.1` | A2 source-slice support | spring-security-core 6.2.0 `f4a810cd1f1142379f6236c5be63b1d9c477be91972381aac45c066ffd0795b0`, spring-security-crypto 6.2.0 `31d6e76a…`, spring-context 6.1.1 `b46807c3…`, spring-core 6.1.1 `a2ef6992…`, spring-beans 6.1.1 `2bca4b8c…`, spring-aop, spring-expression, spring-jcl 6.1.1, micrometer 1.12.0 |
| `spring-core-7.0.4-jspecify-1.0.0` | A3 source slice | spring-core 7.0.4 `e347ee91a4814f7925e53749c081b3186c1e902833b7a58818383440d2963577`, jspecify 1.0.0 `1fad6e6be7557781e4d33729d49ae1cdc8fdda6fe477bb0cc68ce351eafdfbab`, commons-logging 1.3.5 `6d7a744e…` (Spring 7 dropped spring-jcl) |
| `spring-framework-5.2.0.RELEASE` | A4 preflight | spring-context `8cfa528363a4ef6aaecee09218e0c1d2d8bb3f04cd09ca3179d3e78cb3e4b253`, spring-core `3573bfb8…`, spring-beans `7d8dab8e…`, spring-aop `bb1d8d2f…`, spring-expression `93d91bff…`, spring-jcl `8ebb7c28…` |

Full digests: `cd releases/NAME/lib && sha256sum *.jar`.

**Signatures.** The `.asc` of spring-context, spring-beans and spring-core 6.2.3, spring-security-core 6.3.0 and
6.2.0, and spring-core 7.0.4 are good signatures by "Spring Builds (JAR Signing)", key id `928FBF39003C0425`, fetched
from `https://keys.openpgp.org/vks/v1/by-keyid/928FBF39003C0425` on 2026-11-22 (no trust path). **Not checked:**
spring-context 5.2.0.RELEASE is signed by key `9A2C7A98E457C53D`; keys.openpgp.org serves it with no user ID (gpg
skips it), and keyserver.ubuntu.com returned only a revocation certificate for it. Its SHA-1s match Central's.

**JVM replays on JDK 21.0.13** (throwaway programs in `probes/a/`, `java -cp $(cat releases/NAME/classpath.txt) X.java`):

- A1 on 6.2.3, the brief's order (name, invalid count, valid count), both heap shapes: every row of the brief's table
  matches, including `getPrimary() == getBackup()` false/true after every call, one field error `backup.count`
  rejected `oops` after the second call, and the same single error after the third. The six permutations and the
  fresh-binder control were not run (the domain agent freezes those).
- A2 on Security 6.3.0 + Framework 6.1.7, fluent builder `A → B`, `B → C, D`, `hasAuthority(prefix + "D")` with
  `setRoleHierarchy`: 14 of 16 subsets granted for each of `ROLE_` and `CUSTOM_PREFIX_`, as the brief says. Legacy
  text configuration and the 64-history combined grid were not run.

### Gradle and JDKs for the historical Spring builds

| Worktrees | Version | Gradle (wrapper) | Runs on | Compiles with |
|---|---|---|---|---|
| `spring-security-14196-{before,feature,landed}` | 6.3.0-SNAPSHOT | 8.5 | JDK 17.0.21 | toolchain 17 (the same JDK) |
| `spring-framework-36911-{parent,landed}` | 7.1.0-SNAPSHOT | 9.7.0 | JDK 25.0.5 | toolchain 25 (`JavaConventions`: language 25, release 17) |
| `spring-framework-23893-{parent,landed}` | 5.2.1.BUILD-SNAPSHOT | 5.6.3 | JDK 8 (1.8.0_512) | the same JDK, source 1.8 |

The three distributions are unpacked in `gradle-home/wrapper/dists/` (fetched by each wrapper's `./gradlew
--version`). Checked against gradle.org's published checksums (read 2026-11-22): 5.6.3's zip sha256
`60a6d8f687e3e7a4bc901cc6bc3db190efae0f02f0cc697e323e0f9336f224a3` matches; 8.5's is pinned in Spring Security's
`gradle-wrapper.properties` (`9d926787…41026`, equal to gradle.org's) and the wrapper checked it; 9.7.0 pins none and
the wrapper deleted its zip, so the zip was downloaded once more, matched gradle.org's
`84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae`, and its contents are identical to the unpacked
tree (`diff -r`). All seven checkouts' `gradle-wrapper.jar` match gradle.org's `gradle-VERSION-wrapper.jar.sha256`.

Repositories the builds name: Spring Security uses the plugin portal, Central and `repo.spring.io/milestone` (200
anonymously); Framework 7.1 uses Central and the plugin portal only; Framework 5.2 uses Central,
`repo.spring.io/libs-spring-framework-build` (200 anonymously) and, for plugins after the portal,
`repo.spring.io/plugins-release`, which answered **401** anonymously on 2026-11-22. If a 5.2 build plugin is found
only there, the A4 build stops; the job below will say.

### Builds and upstream tests: queued as jobs

The Spring builds take minutes and several GB, so they are verification jobs, committed with this record (see the
commit). Each job builds the module jar at every revision with that checkout's own wrapper and dependencies (the first
run fills `gradle-home`), runs the named upstream tests, copies the jar to `artifacts/WORKTREE.jar` and prints its
sha256, writes `logs/WORKTREE.MODULE.runtimeClasspath.txt`, reruns the landed tests with `--offline`, and finally
removes the build trees (`git clean -fdxq` in each worktree). A transplanted test file is removed again after its run.

| Job | Subject | What it runs |
|---|---|---|
| `20261122-151858-setup-build-spring-security-core-at-the` | A2 | `:spring-security-core` at before, feature, landed; each side's own `RoleHierarchyImplTests` and `AuthorityAuthorizationManagerTests`; the builder tests (`testBuilderWithDefaultRolePrefix`, `testBuilderWithRolePrefix` and five argument checks) exist from the feature commit on |
| `20261122-151858-setup-build-spring-framework-spring-core` | A3 | `:spring-core` at landed and parent; `PropertyTests` is new in the change, so on the parent the landed file is transplanted and `resolveNameForRecordAccessorEmbeddingGetPrefix` must fail |
| `20261122-151858-setup-build-spring-framework-spring-cont` | A4 | `:spring-context` at landed and parent; each side's own `DateFormattingTests`, then the landed file on the parent, where `testBindDateAnnotatedPatternWithGlobalFormat` must fail |

The commands, for a rerun by hand (each over a minute, so as a job):

```bash
B=~/.cache/in-the-loop/spring-java-data; export GRADLE_USER_HOME=$B/gradle-home TMPDIR=$B/tmp
# A2 (JDK 17)
cd $B/src/spring-security-14196-landed && JAVA_HOME=~/.sdkman/candidates/java/17.0.21.0+9-tem ./gradlew --no-daemon \
  -Porg.gradle.java.installations.auto-download=false :spring-security-core:test \
  --tests 'org.springframework.security.access.hierarchicalroles.RoleHierarchyImplTests'
# A3 (Gradle on JDK 25, toolchain 25)
cd $B/src/spring-framework-36911-landed && JAVA_HOME=~/.sdkman/candidates/java/25.0.5.0+8-tem ./gradlew --no-daemon \
  -Porg.gradle.java.installations.auto-download=false \
  -Porg.gradle.java.installations.paths=$HOME/.sdkman/candidates/java/25.0.5.0+8-tem \
  :spring-core:test --tests 'org.springframework.core.convert.PropertyTests'
# A4 (JDK 8)
cd $B/src/spring-framework-23893-landed && JAVA_HOME=~/.sdkman/candidates/java/8.0.512.0+9-tem ./gradlew --no-daemon \
  :spring-context:test --tests 'org.springframework.format.datetime.DateFormattingTests'
```

Add `--offline` once the job has filled the cache. The job steps themselves are in `verification/jobs/ID.json`; the
script that wrote them is `~/.cache/in-the-loop/spring-java-data/scripts/submit_jobs.py`.
