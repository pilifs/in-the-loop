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
| 3. Array induction into `lib` | done: the method is `lib/python/jvm_array_induction.py`, called on a bound method and a rule; the examples keep an adapter; the five declared contracts repeat their stored results |
| Ownership map in `lib/README.md` | written, five rows, each with its owner and one working control |
| The brief's exit | [reported below](#the-exit-what-the-brief-asked-to-be-shown) |

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

## Part 3 · Array induction as a library method

**What moved.** The proof method is `lib/python/jvm_array_induction.py` (530 lines): the walk over a method's
disassembled instructions, the obligations of each rule, the SMT query and the solver's answers read back. Its entry
is `prove(javap, class_file, name, descriptor, rule, work, seconds, caller=...)`, which returns the obligations with
their expected and obtained answers, the certificate, the widths and the bytecode walked. It takes a bound method
and a declared rule and has no knowledge of an example, a sidecar, a revision or a record. The reading of a class
file's methods from `javap` is `lib/python/jvm_disassembly.py` (53 lines), which three other tools used through the
old module.

**What stayed.** `examples/tools/targets/array_induction.py` (696 lines before, 315 now) is the adapter: it finds the
declared contract, takes the revision the contract names, prepares the artifacts, loads the classes by the prepared
class path, refuses a class whose initializer the rule does not qualify, and publishes the record. It decides no
obligation. It still exports the names other modules took from it.

**The consumers outside the defining module.** The adapter (examples 336, 337 and 346 through
`build.py NNN --array-induction`); `lib/python/test_jvm_array_induction.py`, which compiles a search of its own and
proves it with no example anywhere; and, for the disassembly reader, `monitor_histories.py`,
`schedule_reduction.py` and `synchronized_map.py`, which now import `jvm_disassembly` and no proof method.

**No switch on an example.** Cell width is read from the descriptor (`([JJ)I` is 64-bit cells), indices are Java
`int`s either way, and the rule is named by the contract. The library test shows it on classes that are no example's:
`int` and `long` searches established, a search with `<=` for `<` not established on a `safe array access`
obligation (expected `unsat`, obtained `sat`), an unknown rule and a method the rule does not fit refused.

**The five contracts, before and after.** Each was proved again through the extracted method into a scratch folder
and compared with the stored record of the same source, field by field (source key, entry, revision, rule, status,
domain, preparation, class path, class digests, cell and index widths, the bytecode walked, every obligation's name
with its expected and obtained answer, the certificate's digest, the caller's evidence; and, as the machine's own,
the JDK, `javap`, the solver and the disassembly's digest).

| Example | Contract | Stored | Proved again | Obligations | Cells, indices | Differs in |
|---|---|---|---|---|---|---|
| 336 | `first-any-length` | established | established | 10 of 10 as expected | 32, 32 | nothing |
| 337 | `fill-any-length` | established | established | 10 of 10 | 32, 32 | nothing |
| 337 | `caller-any-length` | established | established | 12 of 12 | 32, 32 | nothing |
| 337 | `caller-extra-any-length` (the negative control) | unresolved | unresolved | 13 of 14: `caller read follows from the proved frame` expected `unsat`, obtained `sat` | 32, 32 | nothing |
| 346 | `first-any-length` | established | established | 11 of 11 | 64, 32 | nothing |

The SMT certificates are the same bytes as the stored ones. All five take 7 s together. This comparison is now a
mode of the adapter, `build.py NNN --array-induction CONTRACT --compare`: it writes nothing to the example and exits
0 when the stored result is repeated, whatever its status, so the negative control passes by staying unresolved on
the same obligation. Job `20261121-220624-array-induction-through-the-library-meth` runs the five at the commit.

**The rule implementation in a record.** A stored record has `rulesSha256`: the digest of the one adapter file as it
was when it held the method. After the move that digest would cover the adapter alone, a wrapper. A new record
(`java-array-induction-result/v2`) has `rules` instead: each file of the rule by digest (`jvm_array_induction.py`,
`jvm_disassembly.py`, and the adapter, which qualifies initializers) and one digest over them. The fifteen stored
records are untouched and are read as before (`evidence` reads neither field); `rules_of` gives either format in one
shape, the old one as the one file's digest with no combined digest invented for it. No new record was added to an
example: a claim's next run writes one.

**The organic benchmark's baseline.** `lib/benchmark/organic-java/run.py` fingerprints a baseline's inputs and exports
them for a frozen run, and both lists named paths under `lib/src`, `lib/models` and `examples/tools` only. Code
moved to `lib/python` would have been outside the fingerprint, and an export of a new baseline would not have
started: the example tools import the reader from `lib/python` since part 1. The lists are now versioned
inventories, and a pin names its own (`inputs`; none is inventory 1).

| | Inventory 1 (the pin of 2026-11, and any pin without the key) | Inventory 2 (a new baseline) |
|---|---|---|
| Fingerprint covers | `lib/src`, `lib/models`, `examples/tools/targets`, four named files | the same, and `lib/python`, `verification/layout.py` |
| Export for a frozen run | as it was | the same, and `lib/python`, `verification/layout.py` |
| The pinned revision `5e41cd71`, exported | 224 files, `3e212359370b…`: the pin's own numbers | not asked: the pin has no `inputs` |
| This tree | 228 files, `80d0426b1534…` | 232 files, `8e174eb1aa63…` |
| Only `lib/python/jvm_array_induction.py` changed | the same fingerprint | another fingerprint |
| A frozen export, run with `python3 -I` from inside it | does not start: `jvmcontract_io` is not found | loads its own `jvmcontract_io`, `jvm_array_induction` and `jvm_disassembly` |

`verification/layout.py` is in inventory 2 because `examples/tools/accept.py` loads it at import since the
process-plumbing run: an export without it stopped there, whatever this run did. The existing pin is not re-pinned:
which revision a new baseline freezes is a decision about the benchmark, not about this change.

Tests: `lib/python/test_jvm_array_induction.py` (6, with `javac`, `javap` and Z3 on formulas of a few hundred
terms, 3.5 s), `examples/tools/targets/test_array_induction.py` (3), `lib/benchmark/organic-java/test_run.py` (4,
among them the pinned revision exported by its inventory and the frozen export under `-I`). Examples 336, 337, 346,
342 and 343 pass `validate_example.py`.

**Not done in part 3, on purpose.** No port to Rust, and no generic backend interface: the brief asks for neither.
The method still shells out to `javap` and Z3 exactly as before, so it starts no new process. The schedule and
monitor experiments were moved onto the disassembly reader and otherwise left alone.

## The exit: what the brief asked to be shown

| Asked | Where |
|---|---|
| The two reproducers and their corrected outcomes | [Proof output: three readers, one row](#proof-output-three-readers-one-row) and [the same table after](#part-1--proof-output-as-a-library-contract), kept as `examples/tools/targets/test_proof_output.py`; [The class that ran](#the-class-that-ran-two-jars-five-jvms) and [the table, after](#the-table-after), kept as `examples/tools/targets/test_class_binding.py` and `lib/tests/class_bindings.rs` |
| One real consumer of the extracted induction core outside its defining module | the examples' adapter, on 336, 337 and 346, with the five contracts repeated (above); and the library test |
| Unchanged or explicitly explained historical readings | 58 archived selector records validate to the same lines; none of 2,933 published benchmark and solver records would be scored differently; the fifteen array records are read as before; the old organic pin exports and matches. Changed on purpose, and only for new readings: an unknown wire version, a mistyped field or a failed process no longer earns a selector row or benchmark credit; a class with several class files is bound by what a JVM loads, and the folded-manifest JAR is no longer read as versioned |
| The ownership map | [`lib/README.md`](../../lib/README.md#who-owns-which-decision), five rows |
| New subprocesses for a proof | one for a native verifier launch and one for a native-selector task (`class-bindings`, 18 to 29 ms), whatever the number of sides, classes and selectors; none for reading output, none for array induction, none at an ordinary JAR's preparation; `javac` once and one JVM for each JDK only when a class has several class files |
| Time to read 359's archived selectors, same machine | 0.59 s before, 0.55 s after (7 records, 2,871 cases, second and third of three passes, two alternating rounds: 0.58 to 0.60 against 0.55 to 0.56). No process is started |

**Left open, for a person.**

- The organic benchmark's pin still names the revision of 2026-11 and inventory 1. A new baseline, pinned with
  `"inputs": 2`, is a decision about the benchmark.
- `equivalence::Search` and `Replay` were not moved beside the wire module: nothing in the three parts needed it.
- A class loaded by a custom class loader or changed by an agent is outside what `LoadedClasses` observes; the
  binding says so in its scope and refuses nothing for it.
