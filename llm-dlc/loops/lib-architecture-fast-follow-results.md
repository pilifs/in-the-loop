# Results · Reconcile the Rust and Python architecture of `lib`

The record of the run of [`lib-architecture-fast-follow.md`](lib-architecture-fast-follow.md): what was measured
before anything changed, what each part changed, how it was verified, and what is left. One agent, on the line that
holds the process-plumbing run (`develop` at `86ce57af` when it started, 2026-11-21).

## Where it stands

| Part of the brief | State |
|---|---|
| Baseline: both disagreements reproduced, callers listed | done (below) |
| 1. Proof output as a library contract | done: Rust module, Python reader, four consumers switched, typed helper decisions |
| 2. Bind the proof to the class that ran | not started; the disagreement and the JVM's manifest rule are measured, and the design is below |
| 3. Array induction into `lib` | not started |
| Ownership map in `lib/README.md` | written; its rows for class selection and proof methods name today's owners and move with parts 2 and 3 |

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
