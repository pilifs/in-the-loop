# Results · Reconcile the Rust and Python architecture of `lib`

The record of the run of [`lib-architecture-fast-follow.md`](lib-architecture-fast-follow.md): what was measured
before anything changed, what each part changed, how it was verified, and what is left. One agent, on the line that
holds the process-plumbing run (`develop` at `86ce57af` when it started, 2026-11-21).

## Where it stands

| Part of the brief | State |
|---|---|
| Baseline: both disagreements reproduced, callers listed | done (below) |
| 1. Proof output as a library contract | done: Rust module, Python reader, four consumers switched, typed helper decisions |
| 2. Bind the proof to the class that ran | done: one binding in `lib/src/classpath.rs`, asked in one process for a launch; the preparation binds by what the JVMs load; the launch guard compares the two |
| 3. Array induction into `lib` | not started |
| Ownership map in `lib/README.md` | written; the row for class selection moved with part 2, and the one for proof methods moves with part 3 |

## Baseline (before any change)

### Proof output: three readers, one row

The first established row of example 359's `contents-fix` selector record
(`records/native-selectors/fix/20261121T110735Z-f1bc304b`, selector 0, wire version 1, exit 0, one of 2,865 admitted
and checked cases), through the readers as they were, changing one thing at a time in memory:

| Input | Ordinary decoder (`checker_output.decode`) | Native-selector row (`disposition`) | Benchmark, expected `verified` (`classify`) |
|---|---|---|---|
| Original v1 row, exit 0 | decodes one outcome | `established` | `correct` |
| Only `wire_version` changed to 999 | refused: unsupported checker wire version 999 | `established` | `correct` |
| Only `stated.bounds.complete` changed to the string `"false"` | decodes one outcome | `established` | `correct` |
| Original row, exit 2 | decodes one outcome | `open` | `correct` |

This is the brief's table, reproduced. The readers' callers at the baseline:

- `checker_output.decode`: `runtime.run_verifier` (every ordinary verifier run), `build.py`'s `json_outcome` and
  `json_outcomes`; `supported_version` in `accept.py`; `is_outcome` in `workflow_ingest.verifier_outcome`.
- The selector check read `native.json` with `json.loads` and no decoder, live (`native_case`) and archived
  (`validate_result`), and decided by `disposition`, which took `stated.bounds.complete` by truthiness.
- `lib/benchmark/run.py` read with `json.loads` (`outcome_of`, the first element of whatever list) and scored the
  verdict whatever the exit (`classify`); `lib/solvers/compare.py` calls both.
- Two readers parsed the proof cache's English notes for helpers: `build.py`'s `helpers_record` and
  `economics.py`'s `measure`. Neither pattern matched the two notes a summary writes.

Reading example 359's archived selector records (7 records, 2,871 retained cases, `validate_result` over each):
0.53 s, median of three, on this machine.

### The class that ran: two JARs, five JVMs

A multi-release JAR with two implementations of `fixture.Gate.marker()I` (the base returns 1, the Java 17 entry
returns 17), built twice with manifests that differ only in how `Multi-Release`'s value is spelled. Digests are the
first 12 hex digits of SHA-256; they differ from the brief's because the classes were compiled here.

| Manifest value | Python preparation (`read_class`) | Python effective entry for Java 21 (`effective_class`) | Rust checker bound to 21 (`JVMCONTRACT_JAR_RELEASE`) | JDK 8, 11 | JDK 17, 21, 25 |
|---|---|---|---|---|---|
| `Multi-Release: true` on one line | `97f456237790` (base) | `a859291a3844` (versioned) | reads the versioned entry (`marker` is 17) | base, returns 1 | versioned, returns 17 |
| the same value folded, `tr\r\n ue` | `97f456237790` (base) | `a859291a3844` (versioned) | reads the versioned entry (`marker` is 17) | base, returns 1 | base, returns 1 |

So on the folded manifest the Python effective entry and the Rust checker agree with each other and disagree with
every JVM tried: bound to release 21 the checker refutes `result == 1`, which the JVM satisfies. On the one-line
manifest the preparation's digest is the base class's while the JVM loads the versioned one. Unbound, the Rust
checker refuses the class for both JARs (the existing refusal). The JVM column is `LoadedClasses` and an ordinary
call through the application class loader on Temurin 8.0.512, 11.0.33, 17.0.21, 21.0.13 and 25.0.5.

How those three JDKs (17, 21, 25) read other spellings, measured the same way (17 means the versioned entry loaded):

| Manifest | Loaded |
|---|---|
| `Multi-Release: true`, CRLF or LF line ends, or with no final blank line | versioned |
| `multi-release: TRUE` | versioned |
| `false` then `true` in the main section | versioned |
| `true` then `false` in the main section | base |
| value folded onto a continuation line | base |
| value folded in the main section, and the literal `Multi-Release: true` in a per-entry section | versioned |
| the literal in a per-entry section only | base |
| `true ` with a trailing space; two spaces before `true`; `yes`; the attribute absent | base |
| the line not ended by a line break | base |
| the attribute's name folded | the class does not load at all |

The rule that fits every row: the JAR is multi-release when the manifest's bytes hold `Multi-Release: true`
literally (letters in either case, one space) and the main section's attribute, unfolded and with the last value
taken, is exactly `true` in either case on a terminated line. It is what these runtimes do, not what the JAR
specification says about continuation lines, so a reader that unfolds first (both of ours did) differs from them.

## Part 1 · Proof output as a library contract

**Rust.** `lib/src/proof_wire.rs` owns the contract: the wire version, the envelope, what `prove --json` (an ordered
array) and `equivalence --json` (one object) print, and the exit of a run (the maximum over its rows). The command
line calls it. `lib/src/wire.rs` keeps its meaning (wire types of application contracts). No outcome type moved, so
no re-export was needed. Checked on one run with the baseline binary and the new one: the same JSON but for timings,
the same exits (0 verified, 1 violation).

**Python.** `lib/python/jvmcontract_io.py` is the reader, standard library only. It keeps three questions apart:
`decode` (can these bytes be decoded), `completion` (did the process end as the command ends) and, for the consumer's
own question, typed access (`facts`, `boolean`, `at`, `mistyped`). `examples/tools/checker_output.py` keeps its names
and reads through it.

**Consumers switched.**

| Consumer | Before | Now |
|---|---|---|
| Ordinary ingestion (`runtime.run_verifier`, `workflow_ingest.verifier_outcome`) | decoded with the version check; exit judged apart | the same decoder, now the shared one; a row with a decision field of another type is unreadable, and the execution's reason names what the reader refused |
| Live native selectors (`native_case`) | `json.loads`, truthiness | `read` with `rows=1`: an unknown version, a wrong exit, a mistyped field leave the row open with the reason; a new row records `wireVersion`, and a new record names both rule files (`ruleFiles`) beside `ruleSha256` |
| Archived selector validation (`validate_result`) | `json.loads`, truthiness | `decode`, then `disposition` over typed facts and strict equality (`True` is not `1`) |
| Benchmark (`run.py`), and through it the solver comparison | first element of any list; verdict scored whatever the exit | exactly one row for the one property; no score beside a kill, an unknown version, a mistyped field, exit 2 (`tool failure`) or an exit that contradicts the verdict (`contradictory exit`); a refutation is still `correct` at exit 1 |

The same table after the change, through the entry points in use
(`examples/tools/targets/test_proof_output.py`, which fails 16 ways on the baseline tools):

| Input | Ordinary ingestion | Live selector | Archived selector record | Benchmark and solver comparison |
|---|---|---|---|---|
| Original v1 row, exit 0 | completed, `verified` | `established` | `established`, 2,865 of 2,865 | `correct` |
| `wire_version` 999 | invalid output: unsupported checker wire version 999 | `open`, same reason | ineligible, same reason | `unsupported`: unsupported wire version |
| `complete` the string `"false"` | invalid output: `stated.bounds.complete` of another type | `open`, same reason | ineligible: the status does not follow from the retained record | `unsupported`: malformed outcome |
| Original row, exit 2 | tool error | `open`: exit code 2 | ineligible: the status does not follow | `unsupported`: tool failure |

**Historical readings are unchanged.** Every archived native-selector record in the repository (58 records over
examples 339, 341, 345, 347, 354 and 359) validates to the same line before and after, byte for byte. Of the 2,933
published benchmark and solver-comparison records that hold a class, an exit and a verdict, none has an exit the new
rule refuses, so none would be scored differently. Reading 359's archived selectors takes 0.54 s (0.53 s before).
No artifact was rewritten.

**Typed helper decisions.** A regression check under `--cache` now says what it did with each changed helper as data
(`helpers` in the outcome, `HelperDecision` in `proof_wire.rs`): callee (class, method, descriptor), action
(`shared`, `summary-applied`, `stays-as-written`, `keeps-body`), the claim key of the proof it rests on and whether
that was found in the cache, a summary's reads and facts, and a reason code where the helper keeps its code. The
notes in `output` are rendered from the decision, word for word what they were, and the proof cache stores the
decisions with the result so an exact hit carries them. `build.py`'s `helpers_record` and `economics.py` read the
data when it is there and the notes only for an outcome from before the field. `shared`, and so an example's
`expected.sharedHelpers`, still means a helper proved equal on every input; a summary applied at calls is its own
action. With every note reworded and the reasons' texts changed, the structured record is identical
(`test_build.py`).

**Not done in part 1, on purpose.** `equivalence::Search` and `Replay` stay where they are: nothing needed them moved.
The wire version stays 1: `helpers` is a field an older reader may ignore.

## Part 2 · Bind the proof to the class that ran

Three parties can each say which bytes a class name means: the checker, a JVM, and the Python tools. Before, each
had a rule of its own, and two of them were wrong in the same way. Now:

- **The checker's selection is said once**, `ClassPath::bind` in `lib/src/classpath.rs`: the first class path
  entry that holds the class provides it, and in a multi-release JAR the bound release selects among its class
  files. Everything in the checker that reads a class's bytes goes through it. It returns the provider, the JAR
  entry, the SHA-256, how it was selected, every candidate class file, and later entries that hold the class too;
  or a typed refusal (`unbound-release`, `ambiguous-manifest`, `observation-differs`, `observation-unmatched`,
  `shadows-jdk`, `missing-class`, `unreadable`) with the candidates' digests and origins.
- **The manifest is read as the JDK's reader reads it** (the table above). A spelling the JAR specification's
  reading and the JDK's differ on is `ambiguous`: a class with a versioned entry in such a JAR is refused unless a
  JVM said which it loads.
- **A JVM's selection is observed, never computed.** `JVMCONTRACT_CLASS_OBSERVATIONS` names what a JVM of the bound
  release was seen to load. The rule's bytes must be those bytes, and where the rule has no answer the observed
  class file is the one read.
- **The Python tools select nothing by rule.** `examples/tools/targets/class_binding.py` lists a class's class
  files (the physical inventory, whatever the manifest says) and hands out bytes only where there is one. A class
  with several is bound at preparation by `LoadedClasses` on each JDK the artifact runs on: the prepared target
  then records the loaded bytes (`classSha256`, with `jarEntry` and `classObservation`). JDKs that load different
  bytes, bytes from another entry, or bytes no class file has are a refusal that names both digests and where each
  is. Parameter lookup and every reader of a prepared entry class take the bound entry (`runtime.bound_class`).
- **The launch guard asks the checker, in one process.** Before a native launch, `jvmcontract class-bindings`
  answers for every side's entry and subject class under the launch's own environment, and for an equivalence it
  also says which entry stands for each logical name of the JAR that is extracted. The guard compares provider and
  digest with the prepared binding. Before, the guard compared the prepared digest with a second Python reading of
  the manifest, so two Python readers could agree on the wrong class.

`runtime_jar.effective_entries` stays for the tools that list a whole JAR (the upgrade review's), with the measured
rule, held to the same fifteen spellings as the checker's; a JAR whose manifest readers differ on is listed by its
base entries, as those runtimes read it.

### The table, after

| Manifest value | Preparation (`_check_classpath`, JDK 21 and 25) | Checker bound to 21, with the preparation's observation | Checker bound to 21, alone | JVM 21 |
|---|---|---|---|---|
| `Multi-Release: true` on one line | versioned entry, `a859291a3844`, seen loaded | the same, by rule and observation: `result == 17` verified, `result == 1` refuted | the same, by rule | versioned, returns 17 |
| the same value folded | base entry, `97f456237790`, seen loaded | the same, by observation: `result == 1` verified, `result == 17` refuted | refused, `ambiguous-manifest`, naming both digests (it read the versioned class and refuted `result == 1`) | base, returns 1 |

Also shown, each a test: an ordinary JAR is prepared to the same record as before, with no JVM run and no new key;
the class path's first holder provides the class in either order and the other is named as shadowed (the
preparation's refusal of an undeclared duplicate is unchanged); no bound release is `unbound-release`, as before; a
descriptor the bound class file does not declare is said with the overloads it has; a class that JDK 8 and JDK 21
load as different bytes is refused with both; and Guava 33.4.8's `Ints`, example 336's subject, binds through the
inventory, the old reader and the checker to the digest that example recorded. One real task of example 336
(`first-8-release`) run through the changed workflow with the real checker ends established as expected, with the
verifier's environment as it was.

### What it costs

| | Before | After |
|---|---|---|
| Processes for one native verifier launch (property or equivalence, any number of sides and classes) | the probe and the proof | one more: `class-bindings`, 18 ms for two sides of Guava's 2.9 MB JAR with its logical entries, 29 ms with 50 classes asked on each side |
| Processes for one native-selector task | one a selector | one more for the task, whatever the number of selectors (2,865 for example 359's) |
| Processes at preparation, ordinary JAR | none for binding | none |
| Processes at preparation, a class with several class files | none (the base class was taken) | `javac` once for the probe, and one JVM for each JDK the artifact runs on |
| Reading example 359's archived selectors (7 records, 2,871 cases) | 0.53 s | 0.57 s, within what three runs vary by; no process is started |

Every archived selector record validates to the same line as at the baseline.

Tests: `lib/tests/class_bindings.rs` (8, one of them the fifteen spellings against the JVM on the PATH),
`examples/tools/targets/test_class_binding.py` (10, the table through preparation, JVMs and the real checker, and the
real target), `test_runtime.py` (77: the folded-manifest test that pinned the old reading now pins the measured one,
and the stand-in checker answers `class-bindings`).

**Scope kept explicit.** The observation is `LoadedClasses` through the application class loader, with an ordinary
call as cross-check in the tests: a custom loader or a bytecode transformation is outside it. The manifest rule is
what Temurin 17.0.21, 21.0.13 and 25.0.5 do; `lib/tests/class_bindings.rs` asks the JVM at hand again on every run.
An equivalence over a JAR with an ambiguous manifest and versioned entries is refused whole: which of its other
classes a JVM loads was not observed.
