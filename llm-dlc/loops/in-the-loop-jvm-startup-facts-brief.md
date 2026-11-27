# Record the JVM startup facts a proof actually uses

**Product implementation brief for `in-the-loop`**  
Reviewed November 26, 2026 against [`develop` at `32d3a22cfbae`][head]. Work through the existing single-agent run and watcher.

When a proof stops during JVM startup, the product should identify the missing fact, observe it on the original deployment, and retry the same claim with an explicit account of what that observation justifies. Start with the default charset, a reflective `Method` field, and two kinds of properties reads. The first deliverable is a running Commons IO example in which changing only the JVM’s effective charset changes the recorded fact and the measured byte output while the registered claim stays frozen.

## The incidents to recover

| Existing case | What happened | What a product result should show |
|---|---|---|
| **Commons IO #520** | Strict native stopped at `Charsets.<clinit>`. Requesting an observed initializer exposed the unbound `Charset.defaultCharset()` dependency. Sixteen fresh JVM trials already crossed explicit and defaulted constructors with measured UTF-8 and US-ASCII defaults. | Which default the JVM selected, which constructor actually used it, and what the native checker can now evaluate. Explicit UTF-8 preserves the original bytes in both profiles. The defaulted ASCII encoder replaces both unrepresentable characters with `3f`. [Original refusals][io-stop] · [Independent trials][io-trials] |
| **ThreeTenBP #77** | Initializing `DateTimeFormatter` also initialized `Chronology`. Its `LOCALE_METHOD` held a `java.lang.reflect.Method`. The observer could neither describe the value nor check whether initialization altered state reachable through it. Upstream looks up `Locale.getUnicodeLocaleType(String)` and later invokes it with `"ca"`. | A bound member identity and a checked account of the supported state or operation. Report separately whether the original public path needed reflective invocation. The DST-overlap histories and TZDB resource remain independent evidence. [Native refusal][three-stop] · [Lookup and use][three-source] · [Public histories][campaign] |
| **Apache POI #1420 with Log4j** | The initial selector stopped at `Locale.equals` before construction. A case-specific caller moved the locale into the launch and began with `new DataFormatter()`. Both revisions then reached `DataFormatter.<clinit>`, where Log4j enumerated the **live system-properties table**. Even the controlled-process attempt refused it. | Identify the actual table operation, its caller and the observations it can support. Reproduce the original twelve locale observations on the unmodified deployments and record the first remaining native dependency. [Constructor-first experiment][poi-stop] · [Original and finite routes][campaign] |
| **Batik, actual properties-file transfer** | Batik’s older loader consulted `XMLResourceDescriptor.properties`. In the 1.17 source, `getParserProps()` loads the packaged stream through `Properties.load(InputStream)` and memoizes it on first use. The CSS parser setter can bypass that read. | Bind the selected resource and bytes, the parsing operation, and the moment the caller first consumes the value. Keep this lazy read distinct from class initialization and from POI’s in-memory table. [Measured campaign][batik-report] · [Batik source][batik-source] · [Packaged input][batik-file] |

## Build on the current observer

- **Capture and import already exist.** `ObservedInitializer.java` runs the requested class on a JVM, watches property reads, and describes static fields and objects. `lib/src/observed.rs` binds the observation to the class and runtime, checks effects on other initialized classes, and supports ordered joint snapshots. The native importer preserves represented aliases and marks unsupported state. It already emits assumption IDs when a path consumes an initializer. Extend this producer–consumer pair with typed facts and evidence of their use. Give each supported JVM operation a shared capture rule, admission checks, and an importer that explicitly lists the operations it can supply. Keep project names and expected outputs in the exercises. [JVM recorder][java-rec] · [Binding and assumptions][obs] · [Native importer][native]
- **The current checks explain why a positive result requires more than a new serializer.** The charset guard scans member references, including calls inside methods that might never execute. The properties recorder installs a `Properties` subclass populated with `putAll(original)`. Its own table can have a different identity, defaults chain or iteration behavior. The reflection model supports a restricted zero-argument lookup and returns zero for its parameter-count operation. Feeding it ThreeTen’s one-argument member would give a wrong answer. Preserve the old refusals outside each newly qualified case. [Setting guards][guards] · [Properties hook][hook] · [Reflection model][reflect]
- **Several campaigns already supply independent controls.** The foundation startup profiler runs paired instrumented and ordinary JVMs, compares their public answers, and collects field events and selected classes. The finite upgrade tracer can witness a specified startup call under a specified caller. The resource model already handles ordered local JARs and a narrow bulk-read path for the pinned JDK’s `Properties$LineReader`. Reuse these capabilities without importing the historical case-specific expected values into the recorder. [Paired profiling][profiles] · [Finite tracer][trace] · [JAR resource reader][jar]

## First product slice

1. Run the existing small `sc.Encoded` countermodel and Commons IO #520 through normal preparation. Preserve the unchanged entry, claim, bounds, old/new JAR order and the initial strict refusal. The existing IO driver used `-Dfile.encoding=COMPAT` with `C.UTF-8` and `C` on the pinned image. Read `Charset.defaultCharset()` inside the subject process. The flag alone cannot identify the selected charset. [Small countermodel][encoded] · [Pinned profile driver][io-driver] · [JDK behavior][charset-spec]
2. Record the requested launch profile, the effective canonical charset name, the implementation/provider identity where it matters, the process and class-loader context, and the exact consumer or initializer. Distinguish a potential read found in bytecode, an executed read, and an observation actually consumed by the checker. A preflight that calls `defaultCharset()` itself does not demonstrate that application code used it.
3. Import only operations with a qualified interpretation on that JDK. A name may suffice for a name comparison. An encoding claim needs the real or modeled encoder behavior for the admitted inputs. Check `"é".getBytes().length` against fresh, untouched JVMs: two bytes for UTF-8 and one replacement byte under the recorded ASCII profile. Apply the same capability to the original IO graph. Record the next unsupported constructor, provider, or effect if it stops again.
4. Change only the profile, substitute the other side’s receipt, and withhold the needed fact. A wrong receipt must fail admission and a missing premise must reopen a dependent result unless another route establishes it independently. The explicit-UTF-8 control should keep its public result across both profiles. Show the watcher’s report for a normal run and for a resumed run. Require a clean checkout to reproduce both through shared code, with zero case-specific startup probes or hand-entered facts.

## Evidence and scope contract

Produce one versioned **startup receipt** per revision, launch profile and observation boundary. The aim is to reuse it across compatible claims and to explain why a different claim cannot consume it. Reuse the existing class-binding, observation and proof-statement formats wherever they already express the needed information. For example, two receipts can both observe ASCII under `file.encoding=COMPAT`, yet only the history that chooses the default encoder should be credited with consuming that choice for its output. Record a startup read separately if it still occurred in the explicit history.

| Receipt component | Required information |
|---|---|
| **What ran** | Revision, ordered artifact identities, selected class/resource origins and bytes, defining loader and relevant delegation, JDK image and VM identity, recorder version and capture options. Record the effective process inputs relevant to the fact, including locale category, startup properties, working directory or processor setting where used. |
| **When it happened** | Root and original binary name, initiating caller or bytecode site when available, actual ordered roots, first active use or explicit pre-entry initialization, lazy first-use boundary where applicable, and success or failure. Identify what was already initialized. Keep events produced by inspecting or serializing the snapshot outside the observation window. |
| **What was observed** | Fact kind and typed value, lookup or read operation, source and scope, missing versus present, owning class and field, dependencies, aliases and order where observable. Preserve partial reads, exceptions and unsupported effects. A digest can bind the evidence while the evaluator still needs the value or a narrowly checked operation to execute. |
| **What used it** | Claim and revision, checker route, supported operation, premise ID or IDs actually consumed, downstream public observation, independent replay reference and first remaining blocker. Keep diagnostic-only facts visible without adding them as proof premises. |

A fresh-JVM observation can establish what happened **in that execution**. A native proof can then cover symbolic inputs **under the stated startup assumptions**. The unrestricted claim is decided only if the original contract admits that profile as its complete scope, the checker covers all admitted states, or independence is separately established. A counterexample replayed on an original JVM in a prestate admitted by the claim can refute that claim. A class-initialization exception before entry counts only for a property whose semantics include that event. Preserve the original claim and report a narrower result alongside it when appropriate. [Existing assumption text][assumptions] · [Original-scope Avro finding][avro] · [Startup witness handling][witness]

### Admission rules for the remaining fact types

**Reflective members.** Capture lookup success, null fallback or exception, declaring type and defining loader, method name and full JVM descriptor, modifiers, and object aliases within the captured graph. Bind application members to original class bytes and JDK members to the pinned image. Verify the member independently from the returned metadata. Compare the supported state in the initialization-together and initialization-alone runs when that boundary requires it. Account for observable accessibility changes, distinct reflection objects for one member and any escaped aliases; refuse an unsupported use. Metadata inspection, reference identity, and `Method.invoke` have different semantics. An invocation needs a separately validated target, access, dispatch and outcome. Give the checker the one-argument descriptor for ThreeTen and make an unsupported operation name its actual use site. [ThreeTen consumer][three-source] · [Native member model][reflect] · [Observed effects][obs]

**Live system properties.** Start with a controlled launch and an exact supported table shape. Identify the operation performed, own entries, inherited defaults, presence/value semantics, and the iteration sequence if the consumer depends on it. Treat a saved table reference, a live view, a replacement and a later mutation as different observations. Start with standard string keys and values. A non-string entry, custom subclass, live mutation or escaped view needs matching semantics or a specific refusal. A sorted map suffices only for a projection shown to be order-independent. Compare a recorder-enabled run with an untouched JVM for the full public observation and the relevant intermediate projection. A wrapper that changes an observable class, identity, membership or order must be corrected or rejected. Where hooks cannot observe an operation, retain the conservative guard. Store full replay inputs only in the appropriate evidence artifact; public receipts can carry scoped hashes and relevant safe facts. If a required value cannot be bound, mark that premise unavailable. [Current recording wrapper][hook] · [Whole-table guard][guards] · [Own/defaults and mutation controls][config]

**Properties files and resources.** Bind the original locator, lookup API, loader or resolved file, ordered sources, selected bytes and digest, and absence/presence. Record the actual bytes consumed or a justified complete-file read, decoder and parser. `load(InputStream)` uses Latin-1 with properties escapes; `load(Reader)` consumes characters from the selected reader. Retain duplicate-key precedence, continuation and failure behavior of the actual JDK parser. For ordinary files use a bound fixture under the declared launch directory. For JAR resources use the classpath resource model. Reopening a resource in another loader or hashing a similarly named file cannot establish what the caller read. [JDK properties contract][properties-spec] · [Existing local-JAR support][jar]

**A stronger result to attempt.** On the small charset fixture, leave the selection symbolic over the two registered profiles and check one explicit-UTF-8 operation and one defaulted operation. Try to discharge the selection premise for the explicit operation and produce a real separating input for the defaulted one. State the quantified set. Two agreeing replays alone cannot remove a premise from a proof.

## Worked qualification campaign

Run exercises 1–7 while building the feature. Freeze the shared implementation and input policy before exercises 8–11. Published outcomes serve as evaluation oracles. Record every case-specific hint, probe, launch edit or hand-authored fact separately from automatic recovery.

| # | Exercise | Discriminating observation or required refusal |
|---|---|---|
| 1 | **Effective charset, small control and Commons IO #520.** Run the first slice, crossing old/new, explicit/default constructor and both measured defaults. | Verify the 16 historical JVM trials and the public byte differences. Show a native proof consuming the small fact and an original IO attempt advancing past the exact charset refusal, with its actual next result. [Controls][io-trials] |
| 2 | **ThreeTenBP #77, one-argument `Method`.** Qualify `Chronology.LOCALE_METHOD` in the transitive initialization of `DateTimeFormatter`. | Verify declaring class, parameter and return type, and arity one. A wrong descriptor, wrong loader or mutated accessible state must invalidate the relevant use. Keep the formatter’s TZDB evidence and New York/Berlin overlap observations intact. Report any later invocation or startup gap at its own location. [Refusal][three-stop] · [Original histories][campaign] |
| 3 | **POI #1420, process table enumeration.** Run the DataFormatter-first control with the registered locales, then perturb a controlled property and repeat with recording off. | Identify Log4j’s actual bulk reader. Key addition or deletion must change the affected dependency identity even when the public formatting string stays the same. A fixture where the added key changes the result must expose a stale receipt. Match all twelve original public observations before using the recorder on this route. [POI records][poi-stop] |
| 4 | **Batik parser properties, first use.** Observe `getCSSParserClassName()` on the pinned deployment. In a labelled control, replace the packaged value at the same path. Compare an already initialized loader, a fresh one, and a prior call to the explicit setter. | Identify the actual source and parsed value. The fresh loader must see the changed value; the memoized one retains the original as long as its loaded state is the same. The setter-first call should bypass the read. Report the registered PNG question separately. [Lazy implementation][batik-source] · [Original resource observations][batik-report] |
| 5 | **File vs reader decoding.** Create a small startup fixture with a literal non-ASCII byte sequence, escaped Unicode, a continued line and a duplicate key. Read via `InputStream` and an explicitly UTF-8 `Reader` in separate profiles. Add a missing file and a malformed Unicode escape. | The two readers can produce different strings from the same bytes. Match the JDK’s last assignment and exact failure boundary. Changing only a comment changes the source digest while preserving the parsed values; changing the winning assignment changes the observation. [JDK contract][properties-spec] |
| 6 | **Observer perturbation and missed reads.** Use the existing six setting countermodels, then add a whole-table `hashCode` or `equals` consumer with an extra key chosen to change its public result. | Unsupported reads keep their named refusal; a newly admitted read must carry its own bound premise. Reject a capture that agrees on named reads while the untouched JVM disagrees on the bulk result. Include a property supplied through defaults and a saved reference to the original table. [Six known countermodels][setting] · [Existing limits][obs] |
| 7 | **Order, aliases and failed captures.** Reuse `oc.JointStartup` with roots in both orders and its opaque-object consumer. Interrupt a capture after one root completes. | Root→Reader gives 7; Reader→Root gives 0. Preserve separate assumption identities and the opaque-read refusal. A partial or failed capture must leave no reusable successful state. For overlapping class initialization on multiple threads, retain an explicit unsupported result until ordering and waiting are modeled. [Existing tests][joint] · [JVM initialization rules][jvms] |
| 8 | **Commons Configuration #565/#601, own versus inherited.** Use the same invalid lookup name `_` on the installed table and in its defaults. Retain the table, replace it, then remove the parent entry. | An invalid own entry yields first-use `ExceptionInInitializerError` and subsequent `NoClassDefFoundError`; the inherited setting preserves the ordinary outputs in the recorded control. The saved reference and live updates must match. The four original predicates already have witnesses against their wider guarantee. [Recovery and public evidence][config] |
| 9 | **JavaParser #4538 and paper example 332, reads at different times.** Remove `line.separator` before first use; compare LF and CRLF profiles. For 332, replay the nine pairs of settings changed before and after initialization. | JavaParser’s missing property produced initialization failure with a null-pointer cause, then erroneous-class use. In 332 distinguish the one-time selection from the live-read mutant and preserve the initialization count. An output derived from a value set after first use must not be credited to startup. [JavaParser measurements][config] · [Example 332][paper] |
| 10 | **Spring example 480, reflective types.** Add a labelled control that caches the original non-bridge override’s `Method` and passes it to the existing public history. | A bound member descriptor and the public generic return type are different facts. Preserve the registered raw `Collection` versus `Collection<Optional<String>>` outcome and the distinct Long/String sibling cases. A recorder that supplies the expected generic answer from the method name fails. The extra fixture is a transfer test, separate from the historical example. [Example 480][spring] |
| 11 | **Avro #3878, conditional scope at scale.** Consume the existing four-root ordered profile on the two 124-entry classpaths. Vary the profile or withhold a root. | The original four-root profile captured 220 classes and 1,079 objects and supported seven conditional obligations. Preserve that scope. A smaller or reordered capture needs its own evidence. A result asserting coverage of arbitrary startup needs independent proof. Raw capture, partial effect coverage and proved independence must be distinguishable in the report. Record startup JVM count, bytes and repeat captures so reuse gains can be measured. [VF-054][avro] · [Independent profiling harness][profiles] |

## Put it in the workflow and decide when to ship

Stage 2 retains the approved claim and startup assumptions. Stage 3 or the first blocked proof attempt should derive a recording request from the bound entry and first native diagnostic, launch each original side, persist the result, and retry on the existing recipe. Preserve the explicit native/JBMC capability boundary. The current `observedInitializers` class→digest map is emitted in sorted name order; add an explicit ordered representation when a joint profile depends on order. Continue to read legacy claims. Surface the qualifying profile, consumed facts and any gap through the watcher and final report. The corresponding caller or entry may be supplied by existing preparation or the companion product work. [Target schema][schema] · [Proof recipe][recipe] · [Workflow stages][stages] · [Generated callers brief][companion]

Keep **recording reuse** and **proof-result reuse** separate. The Rust property route currently rejects `--observed-initializer` with `--cache` because its key omits the observation. Start by reusing qualified evidence across compatible claims while keeping that guard. Before enabling cached verdicts, key or revalidate each consumed fact, input absence, side, ordered providers/roots, loader, JDK image, recorder and effect model, caller boundary, and claim scope. Use atomic publication; failed or incomplete records cannot seed a retry. Re-run warm, cold and clean after changing one dependency at the same path and after restoring it. Preserve an independent unchanged side where its evidence warrants reuse. [Property guard][cache] · [Application side cache][side-cache]

**Release evidence.** Hand back the shared implementation, a normal setup and resumed-run demonstration, and a machine-readable scorecard per case, revision, profile and claim. For each, report the original stop, facts requested and observed, admission or rejection reason, actual consumption and assumption ID, public-JVM parity, post-retry result, manual interventions and cache action. A recorded value, a cleared blocker, a conditional proof and an original-scope decision count separately.

**Acceptance bar.** Ship the first slice when the charset fixture’s proof is sensitive to its receipt, the unchanged Commons IO claim passes its former refusal on both sides, and stale or missing relevant evidence cannot produce a false success. For the full capability, require all three motivating incidents to pass their named blocker on their original deployments via shared code, plus Batik’s independently checked resource read. A later unsupported operation is a valid reported outcome. Require zero false admissions on the failure, alias, order, profile and stale-cache controls. Publish the first frozen transfer results, including refusals and unexecuted cases. Follow the repository’s standard changed-test and queued-proof conventions.

[head]: https://github.com/pilifs/in-the-loop/commit/32d3a22cfbae921d272649eaaae608d60ae89ecf
[io-stop]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/verification/organic-composition/io/observed-frontier.json
[io-trials]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/verification/organic-composition/io/charset-profiles.json
[three-stop]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/verification/organic-composition/threeten/observed-native.json
[three-source]: https://github.com/ThreeTen/threetenbp/blob/f0865ac1e3f5d06822560f09bc9c59f5138fa16f/src/main/java/org/threeten/bp/chrono/Chronology.java#L164-L249
[campaign]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/llm-dlc/loops/organic-java-pr-capability-composition-fast-follow-results.md
[poi-stop]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/verification/organic-composition/poi/observed-frontier.json
[batik-report]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/verification/beyond-jbmc/scaffold-first/RESULTS.md#jvm-and-cache-boundaries
[batik-source]: https://github.com/apache/xmlgraphics-batik/blob/batik-1_17/batik-util/src/main/java/org/apache/batik/util/XMLResourceDescriptor.java#L69-L135
[batik-file]: https://github.com/apache/xmlgraphics-batik/blob/batik-1_17/batik-util/src/main/resources/org/apache/batik/util/resources/XMLResourceDescriptor.properties
[java-rec]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/observed/ObservedInitializer.java
[obs]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/observed.rs
[native]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/bmc/observed.rs#L24-L140
[guards]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/observed.rs#L556-L633
[hook]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/observed/ObservedInitializer.java#L295-L355
[reflect]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/bmc/reflection.rs#L47-L113
[profiles]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/benchmark/domain-foundations/startup.py#L176-L252
[trace]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/examples/tools/targets/java/UpgradeTrace.java#L173-L228
[jar]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/bmc/jar_resources.rs
[encoded]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/tests/fixtures/setting-countermodels/sc/Encoded.java
[io-driver]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/benchmark/organic-composition/io/charset/profiles.py
[charset-spec]: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/nio/charset/Charset.html#defaultCharset()
[assumptions]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/observed.rs#L272-L311
[avro]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/verification/findings.md#L433-L449
[witness]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/property/startup_witness.rs
[config]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/benchmark/receiver-discovery/recovery.md
[properties-spec]: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/Properties.html
[setting]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/tests/fixtures/setting-countermodels/README.md
[joint]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/tests/observed_countermodels.rs#L115-L163
[jvms]: https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-5.html#jvms-5.5
[paper]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/examples/332-paper-initialization/README.md
[spring]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/examples/480-spring-nested-return-type/README.md
[schema]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/examples/schema/target-claim.schema.json#L63-L80
[recipe]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/examples/tools/targets/recipes.py#L120-L174
[stages]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/llm-dlc/runtime.md#stage-3-set-the-examples-up
[companion]: https://chatgpt.com/library?file_id=libfile_fde3_f-4229445dcda481918d52fb185111ae45_1a220e41ac0481919d2d88e5f0713c02&account_id=personal
[cache]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/lib/src/property.rs#L294-L309
[side-cache]: https://github.com/pilifs/in-the-loop/blob/32d3a22cfbae921d272649eaaae608d60ae89ecf/examples/tools/targets/change_evidence.py#L48-L105

## Setup Agent Notes

### What is ready, and where

- Every case's inputs are prepared and checked; the only new download is Batik's upstream source at `1_17`. Pins,
  digests and readers are in [Cases: inputs, pins and digests](#cases-inputs-pins-and-digests). In short:
  - Commons IO, ThreeTenBP, POI: `lib/benchmark/organic-composition/{io,threeten,poi}/{old,new}/prepared.json`, which
    point at `~/.cache/in-the-loop/organic-composition-ff/artifacts/{E-commons-io,A-threetenbp,B-poi}-{parent,fix}.jar`
    (POI adds six jars from `~/.cache/in-the-loop/organic-composition-ff/m2`, including log4j-api 2.26.1 and its
    sources jar). Source worktrees: `~/.cache/in-the-loop/organic-composition-ff/worktrees/{E-commons-io,A-threetenbp,B-poi}-{parent,fix}`.
  - Batik 1.17 → 1.18: `~/.cache/in-the-loop/beyond-jbmc/panel/evaluation/04/packet/{old,new}/NNN.jar` with
    `inputs.json`; upstream source at `~/.cache/in-the-loop/jvm-startup-facts/worktrees/batik-1_17` (commit
    `3c83de345f21cae4f4a64dfe6244483f87885808`), mirror `~/.cache/in-the-loop/git-mirrors/xmlgraphics-batik.git` (shallow).
  - Commons Configuration #565/#601: `callers.prepared_inputs(dir, [key])` in `lib/benchmark/receiver-discovery/callers.py`
    over `~/.cache/in-the-loop/receiver-construction/receivers/area/slices/commons-configuration-{565,601}`; sources in
    `~/.cache/in-the-loop/receiver-construction/src/configuration-{565,601}-{old,new}`.
  - Examples 355 (Avro, two 124-entry classpaths) and 360 (JavaParser): their captured builds restore wholly from the
    Maven cache ([table](#javaparser-4538-example-360-and-avro-3878-example-355-exercises-9-11)); 480 reads
    `runtime.json` against `~/.cache/in-the-loop/spring-pr-links-p01-p30`; 332 and the countermodel fixtures are in
    the repository.
- Source blob ids and class digests of the startup classes (`Charsets`, `Chronology`, `DateTimeFormatter`,
  `DataFormatter`, `XMLResourceDescriptor` and its properties, `ConfigurationInterpolator`, `LineSeparator`):
  [Startup classes](#startup-classes-source-blobs-and-class-digests).
- JDKs 8, 17, 21.0.13 and 25.0.5 with their `release` and `lib/modules` digests: [Tools](#tools). Every case except 480
  names JDK 21.0.13 (`~/.sdkman/candidates/java/21.0.13.0+9-tem`); 480 names 17. The default `java` on `PATH` is
  JDK 25: give the others by full path.
- `lib/target/release/jvmcontract`, sha256 `d0bcabc8fe2cc1af89d2e999c55bbc5995231a47fe8b8b3cfb91090ba8895258`, is
  current at `5f0b2389344879610f907ac9ee5b048dd59c9df8`. Rebuild it after changing `lib/src`.
- The scripts that reproduce each check in seconds are in `~/.cache/in-the-loop/jvm-startup-facts/scripts/`, with
  commands in [What was run on a JVM](#what-was-run-on-a-jvm).

### What was verified on a JVM

- The registered public observations, on the original deployments in fresh JVMs, equal the committed receipts: Commons
  IO 8/8, ThreeTenBP 12/12 (the New York and Berlin overlaps), POI 12/12 (`poi/physical.json`), Spring 480.
- **The 16 historical Commons IO charset trials reproduce byte for byte** (`verification/organic-composition/io/charset-profiles.json`):
  under `C` the defaulted constructor encodes `Aé中Z` with `3f3f`, the explicit one keeps `c3a9e4b8ad5a`.
- `"é".getBytes().length` on untouched JVMs: 2 under `C.UTF-8`; 1 under `C` with `-Dfile.encoding=COMPAT`; 2 under `C`
  without the flag. The same on JDK 21.0.13 and 25.0.5.
- Commons Configuration, all four deployments: own `_` gives `ExceptionInInitializerError` then `NoClassDefFoundError`;
  `_` inherited through a defaults table gives the 14 ordinary lookups twice. JavaParser, both sides: cleared
  `line.separator` gives `ExceptionInInitializerError` caused by `NullPointerException`, then `NoClassDefFoundError`.
- Batik's `XMLResourceDescriptor.java` and `.properties` at `1_17` have the same git blob ids as the Debian `.orig` and
  as the properties entry in both deployed jars that carry it.

### What to know before starting

- **Under `C` with `COMPAT`, `file.encoding` is not the canonical name**: it reads `ANSI_X3.4-1968` while
  `Charset.defaultCharset().name()` is `US-ASCII`. Without `-Dfile.encoding=COMPAT`, JDK 18+ selects UTF-8 under `C`,
  so the ASCII profile exists only with the flag.
- **Batik has two copies of `XMLResourceDescriptor` on each side**: 1.17 `old/000.jar` (batik-all) and `old/014.jar`
  (the util bundle, whose manifest says `Bundle-Version: 1.12.0`); 1.18 `new/000.jar` and `new/006.jar`. All four
  copies of the class and of the properties file are identical, and 1.17 and 1.18 are identical, so the selected copy
  follows classpath order, and changing the resource "at the same path" (exercise 4) has two candidate jars.
- The brief's `batik-1_17` link is a branch; the release tag `1_17` points at the same commit. The mirror is shallow
  (`--depth 1`): there is no history behind `3c83de345f21cae4f4a64dfe6244483f87885808`.
- In-repository anchors moved since the brief's review commit: the `--observed-initializer`/`--cache` refusal is at
  `lib/src/property.rs:302-304`, VF-054 at `verification/findings.md:485`; `change_evidence.py`, `recipes.py`,
  `UpgradeTrace.java` and `llm-dlc/runtime.md` grew. The observer, importer, reflection and JAR-resource sources are
  unchanged ([Starting commit](#starting-commit)).
- POI's classpath has log4j-api but no log4j-core: Log4j prints "could not find a logging provider" on stderr, which
  is harmless. The deployments are built `SNAPSHOT` jars at the pins (fixed bytes, digest-checked), not snapshot
  resolutions that can move.
- Configuration's sources in `~/.cache/in-the-loop/receiver-construction/src/` are exports, not git checkouts.
- **Keep the evaluator material apart** where the brief asks for automatic recovery: the historical observers and
  drivers (`lib/benchmark/organic-composition/*/UpgradeProbe.java`, `io/charset/`, `poi/StartupHistory.java`), their
  receipts, and `~/.cache/in-the-loop/jvm-startup-facts/probes/` and `logs/` hold callers and actual outcomes. The
  `DefaultBytes` and `TableModes` probes are this setup's checks, not product probes, and count as case-specific if used.
- No verification job was queued or is pending for this setup.

### What is left for the domain work on purpose

- Everything the brief asks to build or measure: the typed startup facts and receipts, the capture rules, admission
  checks and importer operations, the workflow integration, the cache keys, and the scorecard.
- Running normal preparation, `ObservedInitializer` captures, the native checker and JBMC on any case, including
  reproducing the original strict refusals (IO `Charsets.<clinit>`, ThreeTen `LOCALE_METHOD`, POI `DataFormatter.<clinit>`)
  and Avro's four-root profile.
- Observing Batik's `getCSSParserClassName()`, writing the labelled replaced-resource control and exercise 5's
  properties fixture, the exercise 6 whole-table consumer, the exercise 10 cached-`Method` control, and the
  perturbation, stale-receipt and interrupted-capture controls.
- Running `lib/tests/observed_countermodels.rs` and any new tests under the repository's tiers.
- Any new example ids or registrations.
