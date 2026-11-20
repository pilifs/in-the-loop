# Proving an unchanged Java application across two dependency upgrades

**Run brief for `pilifs/in-the-loop` · 20 November 2026 · 14 new examples and 3 existing examples to revisit**

**Start with the CSV importer in 14.** One ordinary Java client exercises two historical Apache repairs. On an independent JVM pilot, fixing Commons IO restored the bytes, fixing Commons CSV restored the row count, and installing both restored the page. An agent can start with a known answer and spend its effort proving which dependency caused each change. The other examples ask the verifier to handle startup, inputs too large to enumerate, and operations performed by actual Java threads. All 14 are non-CVE correctness cases.

## What the last run earned

The previous single-agent run took **8 hours 41 minutes** from its recorded start to the conductor's stop decision. At the first checkpoint, about 2 hours 23 minutes in, every finite-JVM claim already had an answer while 70 native claims were open. The final report for examples 312–331 records **125/125 finite-JVM decisions** (92 established, 33 refuted). Strict native checking reached **107/125 at original scope** (78 established, 29 refuted). Another **18** (14 established, 4 refuted) were decided under recorded startup conditions. The review accepts those qualified results and keeps the 18 original native obligations open. There were zero reported contradictions. [Campaign ledger](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/verification/twenty-example-fast-follow-results.json) · [Run timestamps and checkpoints](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/llm-dlc/decisions/single-twenty-example-fast-follow.jsonl) · [Scope ruling](https://github.com/pilifs/in-the-loop/commit/8caa52484ac75159779fcb84de20ccb80461e1f2)

Three results change the engineering priorities. Example 308 now proves the released Commons Text LCS at its original bound. Example 331 reduced one exact-count check from 24.257 s inlined to 2.001 s with a checked helper under the same 25 s budget. Example 330 covers six explicitly supplied schedules. Those are starting points for a length-independent array claim, reuse across two real dependency JARs, and scheduling the compiled monitor operations themselves. The existing native engine already has bit-vector checking, induction, loop invariants and effect contracts. Extend the relevant mechanism when the new example shows where it loses the required information. [308 transfer](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/308-commons-text-longest-common-subsequence/README.md) · [331 measurements](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/331-floor-tiling-proof-reuse/README.md) · [330 schedules](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/330-two-editor-interleavings/README.md) · [Verifier and existing contracts](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/lib/README.md)

## The first result to reproduce

The client constructs a stream that strips a UTF-8 byte-order mark, optionally previews one byte and resets the stream, then reads a page with a maximum row count and a starting record number. Compile the client once. Cross the parent and fix for **each** library. Observe the bytes before character decoding, the number of returned records, and the whole page of numbered field lists. The byte observation uses a fresh identically configured stream, so inspecting it cannot consume the parser's input.

| Commons IO | Commons CSV | Wrong bytes / 96 | Wrong row count / 96 | Wrong complete page / 96 |
|---|---|---:|---:|---:|
| Parent | Parent | 48 | 40 | 68 |
| Fix | Parent | 0 | 40 | 40 |
| Parent | Fix | 48 | 0 | 48 |
| Fix | Fix | 0 | 0 | 0 |

**One input explains the matrix.** With `a,b\nc,d\n`, no BOM, an implicit reset after preview, starting number 2 and a one-row page, the CSV parent returns no records with either IO version. With CSV fixed and IO old, the first row is numbered 2 with fields `["a","ba","b"]`. With both fixed, it is numbered 2 with fields `["a","b"]`. A row-count check alone would approve the third combination. A comparison of just the two diagonal cells would miss which fix mattered.

**Calibration provenance.** These are direct observations I ran on Debian OpenJDK 21.0.13+9 using the same client classes in fresh JVMs for the four configurations. The pilot used JARs compiled from the pinned upstream production sources needed by the client. Its expected values come from the supplied bytes and literal records independently of either library. The execution campaign should repeat this on full upstream builds and bind the actual loaded JARs. All new symbolic results below are targets. The appendix contains the runnable calibration.

| Subject | First parent | Fix | Why this boundary |
|---|---|---|---|
| Commons IO, IO-893 | [`16bcc65a`](https://github.com/apache/commons-io/commit/16bcc65a493123dfc1eeba7b3943a69acf03e47c) | [`4f1e3e56`](https://github.com/apache/commons-io/commit/4f1e3e564d0be5e2a01702039b1ddf3b5cea16ce) | This commit changes how an implicit reset rebuilds the buffered prefix. Later commits with the same title extend tests and documentation. |
| Commons CSV, CSV-327 | [`4f9a4037`](https://github.com/apache/commons-csv/commit/4f9a4037a2c1890154e1f077d66306ec54afbf60) | [`7a4f93f3`](https://github.com/apache/commons-csv/commit/7a4f93f3d13218a74dce0c8d8b85af4b341ac3ac) | The merge relative to its first parent changes the iterator to count produced records independently of their displayed numbers. |
| Commons Collections, TreeList | [`dc4d1c92`](https://github.com/apache/commons-collections/commit/dc4d1c92c2c68d1e7b74d20e73991f751eec64f1) | [`fe8eb498`](https://github.com/apache/commons-collections/commit/fe8eb4989392cb436438978b151aa800b70195b9) | A refused indexed change used to invalidate an iterator over an otherwise unchanged list. |

**Build detail that affects the result.** Build each CSV revision against its declared Commons IO 2.22.0 and Commons Codec 1.22.0. Then select one IO and one CSV JAR at **runtime**, with Codec fixed. I tried compiling the two projects' sources together first. The later IO source adds a public `getPosition()` that conflicts at Java compile time with CSV's package-private method. Separate compilation produced all four working runtime configurations. Record compile-time and runtime closures separately and keep the selected IO JAR unique on each runtime path. [CSV dependency versions](https://github.com/apache/commons-csv/blob/7a4f93f3d13218a74dce0c8d8b85af4b341ac3ac/pom.xml) · [IO 2.22.0 source](https://github.com/apache/commons-io/tree/c14acc16f73e44a75b2062b17aacb26c4feda746) · [Codec 1.22.0 source](https://github.com/apache/commons-codec/tree/81a6295f071df5819893422a397d94bc396f2edd)

## Four outcomes worth spending the run on

| Outcome | Evidence that earns it |
|---|---|
| Explain a dependency upgrade to an application developer | On unchanged client bytecode, seek native decisions for the 12 cells formed by three observations and four artifact configurations. Replay both single-repair page failures and establish the fixed/fixed page. Name the dependency, the input and which user-visible result changed. |
| Prove something a larger test grid cannot reach | Check the 64-bit Guava mean over all `2^128` ordered input pairs. Obtain a proof of at least one real array loop for arbitrary legal length, with a checked invariant, heap observation and termination argument. Publish the bounded milestone independently. |
| Explain the startup assumptions | Re-run all 23 original native obligations in 310, 321 and 327. Aim to decide at least one unchanged original through modeled startup, admissible counterexample or a proof of independence from the remaining environment. Report separately how many assumptions were discharged and where they still matter. |
| Connect a bounded concurrent verdict to Java bytecode | Check at least one correct monitor-based implementation and produce a JVM-replayable non-linearizable history for a changed one. Transfer the same method to the actual JDK synchronized-map wrapper. State thread, call, heap and scheduling bounds on the verdict. |

## Example specifications

Numbers 01–14 are local to this brief. Allocate repository IDs from the implementation branch. A historical repair, a released method with a deliberately changed control, and a controlled fixture are different subjects. Record which one supplied every result.

### Startup and the runtime environment

**01 · A print setting read before or after initialization.** Two small classes expose the configured paper size. One caches `System.getProperty("print.paper","A4")` in a static initializer. Its preserving rewrite uses a helper in the same initializer. A control reads the property on every call. Run all nine ordered pairs of initial and later settings from absent, A4 and Letter. Force initialization with a first call, set or clear the property, then observe the second value and a one-time initialization counter. Absent → Letter gives A4 for the cached versions and Letter for the live version. The oracle is the two-event lookup rule. Use a fresh JVM per pair. Bind the property consulted, its absence or value, and when it was read. First transfer is 327.

**02 · A service chosen by the thread context class loader.** A `PageStyle` fixture has two real providers, Compact and Wide, with distinct observable results. Give the application loader and each candidate context loader a common parent that defines the service API and has no provider descriptor. The application loader sees Compact. Each context loader sees its own resources. Start with empty, Compact only, Compact then Wide, and Wide then Compact in **one** descriptor. Compare the default `ServiceLoader.load(PageStyle.class)` with an explicitly selected context loader as a preservation case, then with the application loader fixed to Compact as a distinguishing control. Record provider order, chosen implementation and first construction. Freeze loader parentage, visible resources, order within the descriptor and actual class bytes. Change only the context loader and obtain a fresh ServiceLoader for a second call. A generic service model must follow lookup and lazy iteration on these inputs. Transfer to the chronology lookup in 310. [ServiceLoader contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/ServiceLoader.html)

**03 · A calendar appointment in a skipped or repeated hour.** Call `ZoneRules.getValidOffsets(LocalDateTime)` for UTC and America/Toronto at 01:30, 02:30, 03:30 on 10 March 2024 and 00:30, 01:30, 02:30 on 3 November 2024. Check the count and ordered signed offsets, with ordinary hours as controls. In my JVM calibration using tzdb 2026e, Toronto's spring 02:30 had no valid offset. Its autumn 01:30 had two, UTC−04 and UTC−05 in that order. A client that wraps `getOffset` in a singleton loses both distinctions. Derive the twelve expected entries from the published transition rules and fixed UTC, independently of the Java lookup. Pin the runtime image and zone-data bytes. Switch the process default while keeping the explicit zone fixed as a preservation check. [Java contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/zone/ZoneRules.html#getValidOffsets(java.time.LocalDateTime)) · [Historical Toronto rules](https://github.com/eggert/tz/blob/2024a/northamerica)

**Return to 310, 321 and 327.** Match the original source-claim identities, bindings, observers and bounds. In 310 the five original tasks reach service discovery in chronology initialization. In 321 eight reach the default time zone. In 327 ten reach the Joda provider property. Run the existing observed-startup receipts as controls, then rerun each original with the new implementation. An explicit finite set of environment profiles earns its own scoped claim. To discharge an original, cover all environment choices its statement admits or show that the unmodeled choices cannot influence its observer. A single admissible, independently replayed counterexample suffices for a refutation. An environmental assumption can be necessary, and the report should identify the choice that makes it so. [310](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/310-threeten-complete-hours/README.md) · [321](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/321-jfreechart-empty-series-range/README.md) · [327](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/327-joda-monthday-distance/README.md)

### Symbolic inputs and array invariants

**04 · Guava's signed mean at both word widths.** Use the released Guava 33.4.8-jre `IntMath.mean` and `LongMath.mean`. Freeze independent properties for all int pairs and all long pairs. Widen each operand by one signed bit, add exactly, arithmetic-shift the sum right once and compare to the sign-extended result. A JVM oracle uses `BigInteger.add().shiftRight(1)` on a boundary grid. Include (−1,0) and (MAX,MAX) to distinguish rounding toward zero and signed overflow in the deliberately changed `(x+y)/2` implementation. Prove the released descriptors on unconstrained primitive arguments. A reduced-width exhaustive comparison is a diagnostic for the encoding. Keep the full domains on the receipts. [IntMath source](https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/math/IntMath.java#L696) · [LongMath source](https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/math/LongMath.java#L975)

**05 · Guava finds the first matching array element.** Check `Ints.indexOf(int[], int)` on a non-null array with arbitrary signed cells and target. A returned index must denote a match with no earlier match. Returning −1 requires every cell to differ. Check normal termination and input preservation. On `[7,7], 7`, the released source selects index 0 and a last-match control selects index 1. Start with lengths 0–8, then 0–64 with symbolic cells. The full target quantifies over any already allocated legal Java array. At the loop head prove that the inspected prefix has no match. Check entry, preservation, each exit and the decreasing measure `length − i` with Java overflow semantics. Publish enough information to recheck these obligations. [Released method and helper](https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/primitives/Ints.java#L153)

**06 · A range fill seen through an alias.** Exercise the selected JDK's `Arrays.fill(int[], from, to, value)` for valid half-open ranges on an existing array. Verify the new value inside the range and the old value everywhere else. A second root either aliases the array or names a distinct array that must retain its contents. The control writes one extra cell when `to < length`. On `[4,5], [0,1), 9` an alias sees `[9,9]` instead of `[9,5]`. Check empty and whole-array ranges. Repeat the 8/64/any-legal-length progression from 05, introducing an arbitrary observed index. Prove which slice has been written at the loop head and which pre-state cells survive. Have a caller consume the checked frame. A change to the helper or its write range must trigger reassessment of that caller. [Java range-fill contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/Arrays.html#fill(int%5B%5D,int,int,int))

### Stateful library behavior on real classes

**07 · Commons IO rewinds a prefetched byte prefix.** Use the IO-893 parent and fix above with `BOMInputStream` over `ByteArrayInputStream`. Exercise no preview, read one byte and reset before an explicit mark, and a valid explicit mark/read/reset. Use no BOM and a UTF-8 BOM, include and exclude modes, and payloads of length 0, 1 and at least 4. Compare remaining bytes and EOF with a byte cursor over the supplied payload and selected BOM policy. Recover the duplicated prefix in the flagship and check that the explicit-mark companion still returns the right bytes. Capture the delegate and wrapper as separate objects. Their positions can diverge before the caller has consumed a whole prefix. [IO-893](https://issues.apache.org/jira/browse/IO-893)

**08 · Commons CSV separates page length from record numbers.** On both CSV revisions parse one-, two- and three-row documents with start 1 or 2 and cap 1 or 2. The oracle takes the first `min(cap, rows)` rows and numbers them from the requested start. Check count, labels and ordered fields. Run a second path which calls `hasNext()` twice before each `next()`. At start 2 and cap 1, a two-row input should yield one row numbered 2. Start 1 supplies a preserving companion. Keep the real iterator and its prefetched record visible to the checker. The receipt for reading a page is consumed by 14. [CSV-327](https://issues.apache.org/jira/browse/CSV-327)

**09 · Commons Collections keeps an old iterator usable after a refused list edit.** Seed a `TreeList<String>` with 1–3 A/B values, create an iterator, then attempt indexed add or remove at −1, size+1, 5 or 10. Observe the exception class, list contents and next element or exception on the **same iterator**. The oracle leaves the list and its cursor unchanged on rejection. With `["a","b"]`, I checked both historical revisions on the JVM. A rejected add at 5 or remove at 10 left size 2 on both. Each parent iterator then threw `ConcurrentModificationException` and each fixed iterator returned `"a"`. An iterator created after rejection is a preserving companion. This is a second consumer for pre-state and alias tracking outside an array. [Repair and upstream test](https://github.com/apache/commons-collections/commit/fe8eb4989392cb436438978b151aa800b70195b9)

**10 · One UTF-8 decoder across every chunk boundary.** Generate the 40 strings of 0–3 code points over A, é and 😀. For each encoding admit every partition into nonempty byte chunks, with one empty-input case. Compare a single JDK `InputStreamReader` over the chunks with an independent oracle given by the original code points. A deliberately changed client constructs a new UTF-8 string for each chunk. On the JVM I measured **5,578** string/partition pairs, zero streaming mismatches and **5,448** mismatches for the per-chunk control. The two bytes of é split across reads give a small witness. Qualify returned UTF-16 units and EOF separately. Transfer the decoder across a BOM stream from 07. The symbolic objective is invariance under any admitted partition, including a cut inside a four-byte character. [Reader contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/io/InputStreamReader.html)

### Concurrent histories from Java bytecode

**11 · Two real threads ask for the next ticket.** Start at zero. Each of two threads calls once. The reference returns `++issued` in a synchronized method. A preserving rewrite uses one synchronized block on the same receiver. The control reads under that monitor, releases it, and later writes the saved value plus one under the monitor. On the JVM I gated the control after both reads, outside the synchronized sections. Both calls returned 1 and the final value was 1. The reference returned 1 and 2 with final value 2. The sequential oracle accepts a history if some ordering of the calls respects non-overlapping invocation/return intervals, returns the recorded tickets to their respective callers and leaves the recorded state. Check serial calls as well as overlapping ones. Bind the actual method flags or monitor opcodes and the receiver identity.

**12 · One winner on a JDK synchronized map.** Two threads reserve the same named slot for A or B using `Collections.synchronizedMap(new HashMap<>())`. The reference encloses `containsKey` and the conditional `put` in a single synchronized block on the returned wrapper. The control relies on the wrapper's per-method synchronization. In a gated JVM run the reference reported one success and the control reported two. Both maps ended at size 1. Distinguish return history, final size and stored winner. Add two distinct slots as a preserving companion. Run the selected JDK wrapper's actual methods and resolve the monitor they use. A simplified map can earn a separate intermediate result. [JDK implementation family](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/Collections.html#synchronizedMap(java.util.Map))

**13 · Validate schedule reduction where two names may mean one object.** Two workers each reserve a seat and record an acknowledgment. Admit distinct seat objects, two handles to the same seat, and distinct seats reporting into one synchronized, ordered audit list. Compare exhaustive exploration with partial-order reduction at two workers and at most two calls each. Use an independent interpreter keyed by seat and log identity. Enumerate sequential reservations consistent with each invocation history, then all audit orders consistent with program order and synchronization. Compare the full set of labeled observations, including caller returns, final owners and the selected audit trace. Treating named handles as independent can prune a genuinely different winner or lose one of `[A,B]` and `[B,A]`. Keep a control with independent per-worker logs where differently ordered internal steps are unobservable. Increase to three workers only after exact outcome-set agreement on the small corpus. Report visited states, transitions, time and memory, including cases where reduction adds overhead.

For 11–13, start with bounded, sequentially consistent execution of the named monitor-protected bytecode, two platform threads, fixed allocations and completed calls. Cover contended acquisitions, release, thread start/join, and synchronized methods as well as blocks along the admitted paths. State treatment of blocking or unfinished histories. Derive scheduling choices from the bytecode or validate a translation against it. Replay a witness on real JVM threads and record synchronization points and map any gating or instrumentation back to an admissible original execution. A stronger Java Memory Model claim requires a separate argument for the program fragment. The preexisting TLA+ infrastructure and example 330 are independent controls for small histories. [Java synchronization and memory model](https://docs.oracle.com/javase/specs/jls/se21/html/jls-17.html)

### Integration and independently reusable evidence

**14 · An unchanged paged importer across two dependency upgrades.** Register the four artifact combinations in the opening matrix. Freeze **12** primary obligations, one per combination and observation. The pilot predicts **five establishments and seven refutations**. A positive control disables preview/reset and uses start 1. All four combinations should then produce the correct complete page. The formal entry must consume the stream and invoke the parser on the selected dependencies. The checker must derive the observations from those calls. Keep the independent literal-row oracle outside the subject. For any integer selector that encodes the input grid, prove coverage of the 96 cases, correspondence to direct calls, and non-vacuity per claim.

Drive compositional verification with two consumers. The page client uses IO and CSV. A byte-preview client reads the same reset stream and observes its remaining bytes, so its proof can depend on IO alone if the checker establishes that closure. First run the page checks inlined. Then use a checked fact about the remaining byte sequence from 07 and a checked fact about page consumption/numbering from 08. Bind the decoder correspondence, state read and written, exception behavior, input bounds and preconditions at each call. Demonstrate that both summaries' postconditions establish the downstream preconditions. A substituted assumption with no checked producer earns an explicitly conditional result.

Change only IO, only CSV, and an unrelated unused class. Bind each new prepared artifact identity, recover exactly which earlier evidence is admissible, and compare with a clean recomputation. Reuse across a changed closure needs evidence that resolution, state and dependencies of the reused claim agree. Conservative recomputation is a valid baseline. The release-quality demonstration is a one-page explanation showing which upgrade repaired bytes, which repaired pagination, which defect could mask the other, and which proof work each upgrade caused.

## Running order and completion

Use a single implementation loop with queued proof jobs, as in the previous run. Give 14 first priority and 05 second if resources tighten. Schedule-reduction tuning in 13 can wait while a native importer proof or a checked array invariant is within reach.

| When | Work to queue | Evidence to bring back |
|---|---|---|
| First cycle | Freeze 07, 08 and 14. Build both pairs and reproduce the JVM matrix immediately. Queue the full-width arithmetic check in 04 and the two-thread positive/negative pair in 11. | The four JVM configurations, one real native application attempt, and the first native blocker on each independent proof route. |
| While those jobs run | Use 01–02 on whichever of 310/321/327 they advance first. Run 05 at bound 8 and start the array invariant. Try 12 against the recipe from 11. | A paired startup result with the old assumptions visible, a checked loop obligation and a JVM-replayed caller history. |
| After the first shared facilities work | Transfer to 03, 06, 09, 10 and 13. Return to 05 at the original length-independent target. Rerun every affected historical obligation and the three earlier regression controls 197, 308 and 331. | A second consumer per shared change, a comparison with exhaustive small-domain results, and an explicit disposition for each original claim. |
| Final cycle | Inline and compose 14, change each dependency independently, repeat the whole matrix from a clean checkout. | The 12-cell dispositions, qualifying witnesses, evidence dependencies and a matched cold/warm cost comparison. |

At startup reconcile the pinned baseline `4f87fd1fc9cb4d87a6368109a6387173b7daeae7` with the implementation branch. Keep existing `target.json`, milestones, preparation, receipts and execution history as the public workflow. Preview a registered target with `python3 examples/tools/build.py --plan NNN`. Inspect a result with `python3 examples/tools/targets/workflow_handoff.py handoff NNN`. Submit heavy verification through the existing pipeline. Put any generally useful new observer, recipe or proof rule on that path so a second example can use it. [Workflow handoff](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/examples/tools/targets/workflow_handoff.py) · [Verification queue](https://github.com/pilifs/in-the-loop/blob/4f87fd1fc9cb4d87a6368109a6387173b7daeae7/verification/README.md)

Freeze the inputs, subjects, observations, expected answer, positive control and distinguishing control before changing the checker. When a route stalls, preserve the original attempt with its first unsupported operation, then carry forward independent work. Retry the same claim after the first relevant extension. Smaller domains, supplied initialization, altered loaders, simplified JDK operations, gated programs and sampled schedules each get their own scope. Any disagreement between an accepted result and direct replay takes priority over adding examples.

**Measure the part a user waits for.** Example 320 recorded 11.09 aggregate preparation seconds and 0.277 checker seconds in a 13.82-second verification packet. For 14 record preparation, solving, witness replay, end-to-end wall time, and peak RSS for a clean initial run, an unchanged repeat, and each one-dependency update. Keep the checker, machine limits, JDK, artifacts, bounds and observers matched across strategy comparisons. Report recomputed and reused obligations, and count the initial subproof cost in a cold compositional total. For 05/06 record the largest bound decided and exactly what justified a generalization. For 11–13 record thread/call bounds, schedule coverage and replay success. No speedup is assumed.

**Final accounting.** Give every frozen claim/subject pair its expected and obtained disposition, route, scope, and receipt or first blocker. Report exhaustive JVM, native at original scope, native with added assumptions, and replay-only observations in separate columns. Count dispositions once per claim, with attempts and retries as costs. Give 310/321/327 their own row group with denominators 5/8/10. The headline is how many of the four outcomes above the run earned. A core target still open at close should have a reproducible blocker and the next experiment that could decide it.

**If the four outcomes land early**, take `Longs.indexOf(long[],long)` from the same released Guava JAR as a holdout. Run the 05 recipe on it with the element width changed, through the public entry, before adding checker code. Then widen 14 to include one non-ASCII field split during a four-byte character, using 10's checked decoder and a literal row oracle. Record exactly what transferred unchanged. [Guava holdout](https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/primitives/Longs.java)

## Appendix · Reproduce the four-cell JVM calibration

Compile the class below once as `PageCalibration.java` with the fixed CSV API, its **declared** IO dependency, and Codec. The shell variables name the corresponding JAR paths and a directory for the compiled client. For each run, supply exactly one of the two built IO versions and one of the two built CSV versions. The appendix oracle admits only the three literal unquoted documents below. Each run prints the total and mismatches in the order shown in the opening table.

```sh
mkdir -p "$CLIENT_CLASSES"
javac -g:none -encoding UTF-8 -cp "$CSV_FIX:$IO_222:$CODEC" -d "$CLIENT_CLASSES" PageCalibration.java
for io in "$IO_PARENT" "$IO_FIX"; do
  for csv in "$CSV_PARENT" "$CSV_FIX"; do
    java -cp "$CLIENT_CLASSES:$io:$csv:$CODEC" PageCalibration
  done
done
```

```java
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.apache.commons.csv.*;
import org.apache.commons.io.ByteOrderMark;
import org.apache.commons.io.input.BOMInputStream;

public class PageCalibration {
    record Row(long number, List<String> fields) {}
    record Input(String doc, boolean bom, boolean oneByte, boolean preview, int start, int cap) {}

    static InputStream open(Input in) throws IOException {
        String encoded = (in.bom() ? "\uFEFF" : "") + in.doc();
        byte[] data = encoded.getBytes(StandardCharsets.UTF_8);
        var delegate = new ByteArrayInputStream(data) {
            @Override public synchronized int read(byte[] buf, int off, int len) {
                return super.read(buf, off, in.oneByte() ? Math.min(1, len) : len);
            }
        };
        var stream = BOMInputStream.builder().setInputStream(delegate)
                .setByteOrderMarks(ByteOrderMark.UTF_8).setInclude(false).get();
        if (in.preview()) {
            stream.read();
            stream.reset();
        }
        return stream;
    }

    static List<Row> page(Input in) throws IOException {
        var format = CSVFormat.DEFAULT.builder().setMaxRows(in.cap()).get();
        try (var reader = new InputStreamReader(open(in), StandardCharsets.UTF_8);
             var parser = CSVParser.builder().setReader(reader).setFormat(format)
                     .setRecordNumber(in.start()).get()) {
            List<Row> rows = new ArrayList<>();
            for (CSVRecord record : parser) {
                rows.add(new Row(record.getRecordNumber(), record.toList()));
            }
            return rows;
        }
    }

    static List<Row> expected(Input in) {
        List<Row> rows = new ArrayList<>();
        for (String line : in.doc().split("\n")) {
            if (rows.size() == in.cap()) break;
            rows.add(new Row(in.start() + rows.size(), Arrays.asList(line.split(",", -1))));
        }
        return rows;
    }

    public static void main(String[] args) throws IOException {
        String[] docs = {"a,b\nc,d\n", "x,y\n", "z,1\nz,2\nz,3\n"};
        boolean[] flags = {false, true};
        int cases = 0, wrongBytes = 0, wrongCount = 0, wrongPage = 0;
        for (String doc : docs)
            for (boolean bom : flags)
                for (boolean oneByte : flags)
                    for (boolean preview : flags)
                        for (int start = 1; start <= 2; start++)
                            for (int cap = 1; cap <= 2; cap++) {
                                var in = new Input(doc, bom, oneByte, preview, start, cap);
                                var want = expected(in);
                                var got = page(in);
                                try (var stream = open(in)) {
                                    if (!Arrays.equals(stream.readAllBytes(),
                                            doc.getBytes(StandardCharsets.UTF_8))) wrongBytes++;
                                }
                                if (got.size() != want.size()) wrongCount++;
                                if (!got.equals(want)) wrongPage++;
                                cases++;
                            }
        System.out.printf("%d cases, wrong bytes %d, wrong count %d, wrong page %d%n",
                cases, wrongBytes, wrongCount, wrongPage);
    }
}
```
