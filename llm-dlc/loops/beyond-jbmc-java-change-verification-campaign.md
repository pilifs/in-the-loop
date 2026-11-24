# Beyond JBMC on Java change verification

**Execution brief for `pilifs/in-the-loop`**  
[Starting revision · 867fa025][head] · [JBMC benchmark baseline][benchmark]

Establish which persisted values Lucene 8.11.0 and 9.0.0 can read from each other in both directions. Each release correctly reads its own writes, so both mixed-version checks matter. Next, close a demonstrated native gap on floating-point multiplication. Freeze the resulting checker and measure how often it discovers and decides the relevant property on an unfamiliar upgrade without a supplied caller.

## Where the comparison stands

Use the published results below as regression controls. Refresh the 187 historical claims with strict native, integrated JBMC and standalone JBMC. Evaluate public caller construction and property discovery on released artifacts, and carry independently checked proof evidence through to the caller where available.

| Population | Recorded outcome | Consequence for this run |
|---|---|---|
| Historical 187 Java claims, at `c9995ae1` | 133 both, 24 native only, 13 staged JBMC only, 17 neither. Totals 157/187 and 146/187. | Later work recovered all 13 historical JBMC-only claims on a targeted replay. Only a fresh 187-row matrix can establish the new totals. [Frozen results][historical] |
| Selected 15-family panel | Strict native 57/60, integrated JBMC 24/60. Three ordinary monitor/thread claims remain deferred under VF-056. | Preserve the 57 as regression controls. The deferred thread scope is a separate decision. [Receipts][semantics] |
| Calls, conversions and arrays follow-up | Strict native grew from 7 to **49/49**, comprising 29 proofs and 20 original-JVM refutations. Staged JBMC decided 26/49. All four #375 decimal claims are decided. | Keep the resulting semantics. New work should expose a different failure or support a stronger claim. [Receipts][follow] |
| External upgrades and receiver recovery | Automatic strict primary claims were 0/32 on the historical V3 upgrades. Later work decided 4/46 finite caller sides, or 2/23 complete pairs. Both JVMs reached the caller for 16/23, and 0/34 unrestricted paired overloads closed. | The product problem is the pair of released artifacts, a faithful public caller and a meaningful observation. The earlier reviewed workflow reproduced 3/12 registered changes, preserved 12/12 routine claims and transferred on 5/8; prospective maintainer decisions were 0/15. Keep those populations separate. [Upgrade run][upgrades] · [Receiver run][receivers] |
| Spring and proof assurance | Spring has 16/16 JVM controls and 10/16 original-scope decisions including two process-start witnesses, with 8/16 decided directly. The independent checker covers selected search, fill and alias claims. | Transfer those foundations to new callers. Use the VF-057/VF-058 recovery results for Commons Configuration, long fill/fastutil and whole-verdict SAT evidence as they become available. [Spring run][springrun] · [Kernel inventory][kernel] |

**Start by pinning the 187-claim benchmark and sealing the 16-upgrade selection.** Record the opening comparison, then work through W01 and W02 on Lucene, followed by N01 on vecmath. Choose H01 if receiver construction is the first blocker, or S01 followed by S02 if reflection metadata is the blocker. Let the first refusal on a real public caller guide the implementation. Once a capability decides a claim, try it on a second library before adding more cases around the same primitive.

**Campaign inventory.** The **68 named tasks** comprise nine wire-compatibility cases, eleven numeric/text cases, fourteen heap/history cases, three exception-site cases, nine Spring cases, ten composition/reuse cases and twelve public benchmark programs. The historical 187 and the sealed 16 are distinct evaluations. Use the order below as a dependency guide. Once a second implementation demonstrates transfer, move to the next unresolved public caller.

## 1. Refresh the comparison before changing the checker

1. Record the actual starting commit, tool binaries and digests. Read the archived JSON’s `cases` list (file SHA-256 `14c25280da82eaba7116753d704c33527aedf0e2008ff0eb664a805068d1de75`), assert exactly 187 unique IDs, and match each to its historical claim, inputs and artifact. Use the exact-ID argument to `lib/benchmark/run.py::run(options, case_ids=...)`. The CLI’s `--cases` is a substring filter. Retain an unmodified copy of the historical file. Write fresh reports at campaign start and close. Use its original JDK 25.0.5 profile, staged integrated JBMC, groups 1–4, strict mode, recorded per-case bounds (historical defaults unwind 16 and array length 8), 120-second checker setting and JVM search of 200,000. Label any necessary substitute toolchain separately. [Runner][runner] · [Historical artifact][historical]
2. Run **strict native**, **integrated staged JBMC**, and **standalone stock JBMC** as three columns. Pin JBMC 6.11.0 and its packaged Java models for the historical comparison. Publish the actual standalone invocation, original classpath, assertion ID, exceptions policy, unwinding assertions and result. Stock has its own object factory and model choices. Where a stock public harness has a different input universe, supply the same caller to both tools and keep the published stock profile alongside it. Preserve unequated domains as such. If evaluating another JBMC version, lock that profile before looking at outcomes. [JBMC][jbmc]
3. For relational claims let both engines use an equivalent two-copy harness with isolated releases and the same observations. Identify the actual question proved. A method tested twice inside one classpath can silently become a same-release comparison. A standalone success that never reached the named assertion can survive even a deliberately false post-call assertion. Check an observable post-call false control, the expected target assertion and unwinding on every new harness family. On disagreement, keep the trace, replay the alleged input on the original JVM, check specifications or bytecode for contested universal claims, and classify any remaining dispute as unresolved.
4. Keep one matrix for each population below. For matched, correct decisions publish both/native-only/JBMC-only/neither, then proofs, replayed refutations, wrong decisions, unknowns, timeouts, incomplete unwinding and scope mismatches. Keep individual tool outputs even when a result is ineligible for matched credit. Log both a standalone command that uses stock models and, if justified, a separately named profile using matched JDK bytes or models. Preregister profile eligibility and use the strongest admissible result across those profiles when claiming a lead over JBMC. Report costs on matched solved pairs plus censoring on the full panel. Preserve historical aggregate results even if a claim has since drifted.

## 2. Casebook

IDs below are work items. Several test separate properties of one upgrade. Score shared inputs at the **upgrade-pair or benchmark-task level** as well as by property. Cases named in this brief are disclosed. A JVM preflight is evidence about those inputs. A proposed theorem, a sample result and an accepted proof belong in different columns.

### W · Upgrade compatibility that single-release proofs can miss

**Use W01 as the first end-to-end deliverable.** Compile a thin caller once. Put each Lucene version in an isolated class loader or separate process. Exchange only the encoded bytes and primitive observations between releases. Start with `lucene-core` 8.11.0 and 9.0.0, `ByteArrayDataOutput(byte[], offset, length)` and `ByteArrayDataInput` on the same slice. At offset 1, `0x01020304` produced `33 01 02 03 04 55` and `33 04 03 02 01 55` in hex, including sentinels. Both same-version round trips returned the original. Reading with the other release produced `0x04030201` in both directions. The change is documented by Lucene. [Migration guide][lucene]

| ID | Claim to check | Distinguishing observation or control |
|---|---|---|
| W01 | Characterize 32-bit fixed-width compatibility for **every** signed int. Each same-release composition is identity. Each mixed composition is `Integer.reverseBytes(v)`; compatibility holds iff the four bytes form a palindrome. | Save both directions and both local controls. Exactly 2¹⁶ of 2³² values preserve. A weak equality-only round trip accepts both releases. |
| W02 | Under normal startup, show what Lucene 9’s byte-array view does to all four bytes and to the cursor. Transfer the result to reading. Vary a valid starting offset and entry bytes, including a second reference to the same buffer. | Frame bytes outside the write and check observed end position. Evaluate the real VarHandle access mode, order, width and bounds. Try a flipped byte order and an off-by-one write on a disposable control. |
| W03 | Transfer W01 to `writeShort/readShort` and `writeLong/readLong`, covering signed reads and both mixed directions. | The JVM preflight exhaustively found 256/65,536 short values preserved. For longs, predict 2³²/2⁶⁴. Seeds near a sign change distinguish sign extension from reversed unsigned magnitude. |
| W04 | Show Lucene `writeVInt/readVInt` retain the wire representation across the same upgrade on all int bit patterns. | Independently encode unsigned 7-bit groups. Test 127/128, 16383/16384 and −1. Verify length and next unread byte. This is a preservation result in a class whose fixed-width encoding changed. |
| W05 | Transfer the VInt lemma to Protobuf `CodedOutputStream.writeUInt32NoTag` and back to a Lucene reader. | Compare bytes and consumed length in both libraries. On −1, protobuf UInt32 uses five bytes and signed Int32 uses ten. Swapping the entrypoint must invalidate the shorter-width claim. |
| W06 | Protobuf 3.25.5→4.33.0 `computeUInt32SizeNoTag` and `computeUInt64SizeNoTag`: prove old and new agree with an independent repeated-unsigned-shift length oracle. | Use the bits crossing each 7-bit boundary and all-ones inputs. This tests a changed sizing implementation without relying on either writer as the reference. |
| W07 | Protobuf across those releases: size, write and read UInt32, UInt64 and ZigZag SInt64 on exact-sized slices. Compose old writer→new reader and the reverse. | Preserve flanking bytes, check value and exact consumption. Decode a trailing tag after the field. A size-only theorem cannot expose a wrong terminal byte. |
| W08 | Compose a Lucene fixed-width header and a stable variable-width field into a stored record. Identify which fields a mixed-version reader preserves. | Observe header, payload, next offset and suffix independently. Include a palindromic header and a record whose payload accidentally masks a damaged header under a coarse aggregate observation. |
| W09 | Stretch: lift one-record results to arbitrary finite record sequences by induction on complete records and remaining capacity. | Prove base, progress, byte frame and cursor bounds without overflow. Hold out a different field ordering. A bounded sequence result is publishable at its actual bound. |

**Measured opening on W01/W02.** The JVM preflight exercised all short values, 3,000 seeded ints and longs each, and 3,014 variable-int controls against each of protobuf-java 3.25.5 and 4.28.3. On the same all-int little-endian predicate, strict native refuted Lucene 8 at −2 and refused Lucene 9 at `BitUtil.<clinit> → MethodHandles.byteArrayViewVarHandle`. On the 8.x same-release round trip, stock JBMC 6.11.0 passed the target assertion and its post-call false control failed as expected. Strict native stopped at `DataInput.<init>`. On 9.x the integrated JBMC witness did not reproduce on the JVM. These are concrete entry points for both catch-up and stronger relational work. A separate 3.25.5→4.33.0 Protobuf JVM preflight checked 3,570 wire frames per direction. [Lucene release bytes][lucenejar] · [Protobuf release source][proto]

### N · Arithmetic and parsing where JBMC or the physical JVM gives a demanding reference

| ID | Released caller or property | Opening evidence and next test |
|---|---|---|
| N01 | Java3D `javax.vecmath:vecmath:1.5.2`, `Tuple2f.scale(float)`. Choose independently symbolic binary32 factors in [1,2) and [2,4). Check the rounded product’s range [2,8) and the sign-related companion component. | Stock JBMC proved the preflight. Native strict refused float multiplication above 64 reachable tuples. Integrated strict JBMC already proves N01 and N02. There are 2⁴⁶ pairs. `nextUp(1f)` and `nextUp(2f)` expose an oracle that retains the binary64 product without rounding. |
| N02 | Same public method with both factors in [2⁻⁷⁵,2⁻⁷⁴). Determine the possible rounded results and when the product is zero. | Stock proved the result lies in {0, 2⁻¹⁴⁹, 2⁻¹⁴⁸} and is zero iff both factors are 2⁻⁷⁵. The JVM refuted “positive inputs always give a positive product.” Carry the large symbolic domain through the calculation. |
| N03 | Vecmath `scaleAdd` on a component with a cancellation term. Distinguish Java’s separate rounds from fused multiply-add. | At (1+2⁻²³)(1−2⁻²³)−1 the two operations yield zero, the exact fused result is −2⁻⁴⁶. Native already found the finite negative control. Generalize the proof and preserve a signed-zero observation where the API exposes it. |
| N04 | Jackson Core 2.19.0 `NumberInput.inLongRange`, String and offset-char-array overloads, for magnitudes `9223372036854775ddd` with either sign. | JVM saw 1,617 accepted out of 2,000. Last accepted suffix is 807 for positive, 808 for negative. Native stops at `NumberInput.<clinit> → String.valueOf(long)`. Reachability first: the stock preflight passed a deliberately false post-call assertion. |
| N05 | On N04’s accepted inputs, prove `parseLong19` on a slice returns the mathematical signed integer. Expand from the threshold family to all 19 ASCII digits with the public method’s documented input conditions. | An independent decimal accumulator must represent the magnitude of MIN_VALUE. Change a digit outside the slice, vary the offset, and test the first rejected magnitude under the range predicate separately. |
| N06 | Commons Lang 3.17.0 `NumberUtils.isParsable("0."+c)` over all UTF-16 code units. Recover the lexical rule and compare it to JDK decimal parsing. | Physical JDK 21 accepted 370 code units through Commons. Equating the two APIs disagreed on 397 cases. Distinguish Unicode decimal digits, JDK suffixes and trailing space; pin the Unicode/JDK data version. |
| N07 | Transfer Guava 33.4.8-jre `Ascii.equalsIgnoreCase` to a comparison with Lang 3.17.0 `StringUtils.equalsIgnoreCase` on one-code-unit strings. | Native already proves Guava’s ASCII fold on all independently symbolic units. Lang’s `regionMatches` is open. Kelvin sign U+212A versus K distinguishes the APIs. Check symmetry, null cases and the stated UTF-16 domain separately. |
| N08 | Commons Numbers `FP64`, field and core 1.1→1.2. Which of equals/hashCode/compareTo agree for signed zero and independently boxed NaNs? | Both zeros compare equal by `equals` on both versions, but hashes for the two zeros disagree before and agree after. NaN equality changed. `compareTo` still distinguishes zero signs. Test raw bits and canonical NaNs as different observations. |
| N09 | JTS Core 1.18.2→1.20.0 `Orientation.index((0,0),(x,y),(u,v))`: verify orientation sign against an exact integer determinant over a declared box. Increase the box or add a cancellation family. | Both releases agreed on all 81 unit-grid inputs. Keep exact oracle arithmetic wide enough. Freeze before near-collinear extension, and retain a swapped-point sign reversal control. |
| N10 | Commons Math 3.6.1 `Vector2D.scalarMultiply(double)`, independent operands in [2⁻⁵³⁸,2⁻⁵³⁷) × [2⁻⁵³⁷,2⁻⁵³⁶). | On this binary64 transfer, stock proved the rounded result lies in {0, 2⁻¹⁰⁷⁴, 2⁻¹⁰⁷³} and vanishes iff both operands equal their lower endpoints. Native refused Double Mul above 64 tuples. A fresh-vector frame on normal values is a distinct, harder property. |
| N11 | Jackson Core 2.17.1→2.17.2 `NumberInput.looksLikeValidNumber(String)`, a public predicate for stringified numbers. | Over all 11,111 strings of length 0–4 on {0,7,9,+,−,.,e,E,x,U+0661} (ASCII minus in the fixture), exactly 63 flipped false→true and 11,048 preserved. The changed inputs in that domain are optional sign + ASCII digits + trailing dot. Prove this partition, retain null as an unchanged rejection, and extend or falsify it for longer inputs. The strings `.` and `7.e1` remain rejected. Strict native equivalence already stopped at the same `String.valueOf(long)` initialization as N04; one capability can unlock both callers. [Release diff][jackson217] |

The vecmath JVM preflight sampled 32,768 pairs per wide slice. Attach the raw stock target checks and replay a known wrong formula before broadening to double precision or more operations. Pin the dependency and JDK for every numeric claim. On N07 both checkers proved the ASCII algorithm with a one-code-unit custom CharSequence. Only the original String construction exposed the comparator discrepancy. Carry both profiles. [Vecmath][vec] · [Jackson Core][jackson] · [Commons Lang][lang] · [Commons Numbers][numbers] · [JTS][jts]

Carry N11 all the way to a public consumer as well. On matched Jackson Core/Databind/Annotations 2.17.1 and 2.17.2, all 11,111 inputs were also run as quoted tokens through `ObjectMapper.readValue` for Double, Float, BigDecimal and Number. The exact same 63 changed for each type. At `"-0."` the old release threw `InvalidFormatException` in all four. The new release produced binary64/binary32 negative zero, a scale-zero BigDecimal, and a boxed Double with negative-zero bits. On nine controls, mixing old/new core independently of the other two modules made the result follow core. Prove where this generalizes. This is one upgrade with four observations and an identifiable dependency.

### H · Receivers, shared state and public operation histories

| ID | Case | Property and first distinguishing observation |
|---|---|---|
| H01 | Commons Lang `MutableInt` behind a reference-valued `Cell[].payload` | `getAndAdd(1)` returns the entry value and stores entry+1 with Java int wrap. Stock JBMC proved the tree-shaped caller and refuted “unchanged” at −1. Native strict refused the reference-valued component field. Hold null, shared and distinct receivers as separate input domains. |
| H02 | Three Commons Lang `MutableObject` nodes explicitly linked with `setValue` | Walk by identity until null or first repeat. Both engines proved the bounded successor-index oracle on 64 topologies × four starts and rejected a predecessor-only detector on a two-node cycle. Use this to qualify generated heap inputs that include the self-loop and two-node graph missing from an independent-tree generator. |
| H03 | Two independently supplied roots, shared tail or disjoint payloads | Build via public setters; mutate one reachable `MutableInt`, observe both roots, untouched siblings and identity. Distinguish equal values in separate objects from actual aliasing. Serialize and replay the same edge graph on the JVM. |
| H04 | PCollections 3.1.4→4.0.2 `TreePVector.with` then `minus` on sibling histories | Branch from a public vector and keep both siblings. Across both releases require base and siblings to match independent sequence copies after every operation. The JVM passed all 21 disclosed size/index combinations on each release. |
| H05 | RoaringBitmap 1.6.16→1.6.17, clone a forward flyweight iterator | On elements 10,20,30,65576,65586,65596, advance just the clone through a container boundary. Original `peekNext()` stayed 10 on the new release; on the old it became 40 or 50. Check independent cursors after each step. |
| H06 | Same RoaringBitmap releases, reverse flyweight iterator | Repeat in reverse, alternate which cursor advances, then exhaust one. In preflight, advancing only the clone moved the old origin from 65596 to 65566 or 65556. Require order, cursor independence and exhausted status independently. |
| H07 | RoaringBitmap 1.6.26→1.6.27, public range containment across a missing bit | Populate [0,10000) except h. Test containment of [h−4,h+d) for d=0,1,2. At seven boundary/interior h values the old outcomes were true,true,false; the new were true,false,false. Widen h and change representation through public operations. |
| H08 | jsoup 1.18.1→1.18.2 `FormElement.elements()` on parse→append→remove | Start with input a and append input b. Public name snapshots were [a]/[a]/[a] before and [a]/[a,b]/[a] after. Extend to reparenting between forms and capture each form after each mutation. Check snapshots collected at each observation. |
| H09 | jsoup 1.18.2→1.18.3 XML attribute serialization | On a public XML-output document with a `unit` element and value `7`, alpha and _name survived both releases. The old release dropped a-b, a.b and a1; the new preserved them. Classify a bounded name grammar and check serialization plus reparsing. |

For H05–H07 the first changed **published JAR** was one patch later than the release attribution suggested. The listed pairs were replayed on the JVM. Preserve the artifact hashes and at least one unchanged neighbor. This is a transfer test for version selection as much as for heap semantics. [Roaring iterator fix][roar842] · [Roaring containment fix][roar888] · [jsoup form][jsoup2140] · [jsoup XML][jsoup2235] · [PCollections][pcollections]

Four small catch-up cases isolate common blockers in those public histories. Each has a physically replayed witness and an explicit stock-JBMC harness. The explicit harness is available to either engine. Compare automatic input generation separately.

| ID | Scope | Acceptance |
|---|---|---|
| H10 | Lang 3.17.0 `ArrayUtils.reverse(Object[])` on a `char[][][]` with two planes | Preserve the two plane identities and swap their positions, including identical planes. Stock proved the explicit property; native refused the runtime array shape. |
| H11 | Two roots of type `Flat[]`, sharing or distinct, reverse through a | Observe b[0] as old a[1] if a==b, old b[0] otherwise. Stock proved the conditional with an explicit shared-or-fresh choice. Its independently generated tree roots also accepted the false unconditional frame. |
| H12 | Two roots of different types, a `Flat[]` slot and a scalar `Flat` | Increment the slot and observe the scalar. Hold the graph fixed while changing the primitive to MAX_VALUE to force wrapping. Require reproduction of both the identity relation and the wrapped value. |
| H13 | Three constructible runtime types inside a base-class array | Install each type, call the actual override, require the mapping 4/9/7. Reject “always 4.” Stock passed the mapping; native refused a nonfinal component class. Transfer to one real library registration. |
| H14 | A node with a `next` field of its own declared type | Admit a self-link, a two-node cycle and a null tail. The native message identifies self-referential classes. Stock proves `next != this` on its default tree but refutes it when the public caller explicitly admits a self-link. Both results must carry the heap domain. |

### E · Same exception, different instruction

| ID | Occurrence property | Evidence and transfer |
|---|---|---|
| E01 | A caller invokes `w.read()` where w is null at mode 0; at mode 1 w exists and its `int[]` is null; at mode 2 the array has length one. | The ordinary JVM reported NPE at the caller, NPE at the callee and return 1 respectively. Both engines proved the coarse throw/result contract. Stock reported distinct failing null-check property IDs; the native site report said the caller invoke could not yet distinguish null receiver from nested throw. Require independent occurrence selection and JVM top-frame replay. |
| E02 | Change only mode 0 to construct the receiver and track the surviving exception occurrence. | Identify the repaired caller-site failure and the reachable callee failure, even though the method-wide exception class stays the same. Hold out an extra helper between caller and callee. |
| E03 | Propagate or explicitly catch and rethrow the same exception instance across the helper. | Preserve original throw-site identity, exception class and catch history. Add a control that creates a new exception of the same type in the handler. Report which original bytecode site is reachable in each revision. For E01 freeze separate modes for stock site reporting and exception propagation. |

### S · Spring reflection, public binding and histories that make metadata observable

Start with S01 before modelling the whole framework. On an ordinary JDK 21.0.13 run the intended S01 predicate passed and its inverse failed. At `867fa025` strict native stopped at `Class.getGenericInterfaces`. Standalone JBMC 6.11.0, packaged core models, class major version 52 and unwinding assertions at 8, **failed the intended user assertion and passed the inverse**. This gives a named target for a comparative lead. A family-level lead requires a native proof of the intended predicate, a refutation of the inverse and transfer to released Spring callers.

| ID | Caller | Claim and discriminator |
|---|---|---|
| S01 | Local `C implements Convert<Enum<?>,String>` | The measured predicate checked interface count, parameterized raw type, a fresh interface array after mutation, and the String type argument. Extend it to the wildcarded enum and defensive copies of argument arrays. Check type equality, argument order, defensive copy and the original predicate’s inverse. |
| S02 | Spring Core 6.1.14→6.2.0, upstream #30079, resolve `List<List<T>>` in different subinterfaces | Call `GenericTypeResolver.resolveType`, then `ResolvableType.forType(...).getGeneric(0).getGeneric(0).resolve()` in String→Integer→String contexts. The JVM returned null/null/null before, String/Integer/String after. Detect a cache that confuses the two callers. |
| S03 | Spring formatter #374 through its historical public binder | After scalar converter registration, qualify the generic interfaces of the actual `EnumToStringConverter` and traverse the next refusal. With US locale and UTC, both revisions can display `10/31/09 1:05`; only the fixed path updates the backing Date. Observe field value, binding result, and presentation. Label the historical source slices precisely; repeat on a release pair before reporting release-level coverage. |
| S04 | Spring `BridgeMethodResolver` on a generated `name(Object)` bridge | Resolve it to `name(String)` with a decoy `name(Integer)`. Check `Method.equals` against `getDeclaredMethod("name", String.class)`, declaring class and parameters across cold and warm resolution. |
| S05 | Composed Spring annotation declaring `@AliasFor` | Ensure merged lookup populates both aliases and direct lookup remains absent. Unequal explicit values must throw `AnnotationConfigurationException`. A parser that reads only the directly present annotation should fail. |
| S06 | `GenericConversionService` public registration history | Query empty service, register converter +1, replace with +2, remove. Observe conversion after each step and an untouched second service. Detect stale negative and positive cache entries separately. |
| S07 | `ApplicationListenerMethodAdapter.supportsEventType` with String and List<String> listeners | Across Spring 6.1.14 and 6.2.0, query `PayloadApplicationEvent` of List<T>, T, List<String> and String in order. Preservation vectors measured F,T,F,T and F,T,T,F respectively. Accept these as a second caller for generic metadata. |
| S08 | `AnnotationConfigApplicationContext` on Spring 6.1.14→6.2.0, upstream #20727 | Register the page assembler and a specific assembler. Check four optional sites in order: `Assembler<Some>`, `Assembler<Other>`, `Assembler<Page<String>>`, `Assembler<Page<?>>`. The JVM returned specific/page/page/page before and specific/absent/page/page after. Then vary registration order and prove whether all three intended injections preserve identity. |
| S09 | Reflection arrays through `ResolvableType.forClass(C.class).as(Converter.class)` | Mutate the arrays from `getGenericInterfaces`, `getActualTypeArguments` and `getUpperBounds`. After `ResolvableType.clearCache()`, the original `Converter<Enum<?>,String>` structure must reappear. Transfer S01 beyond the local fixture. |

S02 and S08 are release-pair observations. Pin both complete release classpaths. A tighter upstream parent/fix experiment can establish attribution independently. For a transfer back to #368, recheck the two bean edit-history claims after `map(String::trim).distinct().toList()`, retaining bean state, the error ledger and all edit prefixes. The JVM exercised S04–S06 on Spring 6.1.3, 6.1.14, 6.2.0 and 6.2.3, giving immediate preservation controls. [Recursive generic resolution][s30079] · [Optional bean matching][s20727] · [Historical formatter receipts][springrun]

### C · Changes across three versions, composition and reusable evidence

| ID | Case | Theorem or observation to seek |
|---|---|---|
| C01 | Commons Codec `MurmurHash3.hash128(bytes,off,len,seed)`, 1.13→1.14→1.15 | The first and third releases agreed on 1,300 JVM slices. The middle agreed with 1.15’s `hash128x64`. Characterize exactly when the public historical function differs in the middle, with seed ≥0 as the candidate preservation boundary. Empty slice and seed −1 distinguish immediately. Preserve the two output longs. |
| C02 | Codec 1.15 `hash32` versus `hash32x86` | Candidate exact condition: outputs differ iff a signed-negative byte occurs in the trailing len mod 4 bytes. JVM exercised 97,655 small arrays/slices and seeds. At one byte ff, seed 0, results were 79a8e694 and fd6cf10d. Prove the condition or return a counterexample. Numeric inequalities from a grid do not establish collision-freedom. |
| C03 | Codec `IncrementalHash32x86` over two arbitrary chunks | Compare start/add/add/end to the one-shot hash with the same seed and active slice. Include an empty chunk, every split modulo four and a second `end`. Preserve the original caller’s input bytes. |
| C04 | Same streaming API, any finite partition and reinitialization | Induct over complete blocks and 0–3 pending bytes. Include resetting from a partial block. A 659,180-check JVM preflight covered split, empty, reset and repeat-end controls. Freeze the lemma, transfer to three or more chunks and report the strongest supported length/overflow assumptions. |
| C05 | Dependency-sensitive reuse between Codec 1.14 and 1.15 | The 32-bit entry and three relevant helpers have matching normalized instruction listings. The 128-bit wrapper changed. Check that clean and warm verdicts agree. Old 128-bit evidence applied blindly to the new wrapper should fail on seed −1. Record proof dependency identity beyond a method signature. |
| C06 | Joda-Time 2.12.0→2.12.1 `DateTimeZone.forID("America/Mexico_City").getOffset(instant)` | On the 15th of each month at 12:00 UTC in 2023, April–October shifted from −5h to −6h; the other five preserved −6h. All 247 common class entries are byte-identical. The bundled zone resource changed. Run the old proof cache on the new JAR, then clean; seek an explicit reason to invalidate the affected result. |
| C07 | Joda-Time zone data reuse on a second observation | Derive the interval of differing offsets from the pinned rule resources, including transition endpoints. Before running the checker, use a recorded seed to select an unaffected zone whose reachable dependencies are identical across the releases. Check whether its cached evidence can be reused. Record provider identity, JAR, resource lookup and any environment contribution. |
| C08 | Semver4j 5.6.0→5.7.0 `Semver.coerce` | On 1.08, 1.8, 01.02.03, plain: old null/1.8.0/null/null; new 1.8.0/1.8.0/1.2.3/null. Characterize a declared grammar of decimal groups, including zero and missing groups. |
| C09 | Semver4j 6.0.0→6.1.0 prerelease comparison | Compare `1.0.0-<digits>` to `1.0.0-1`. Both handle 9 and 9223372036854775807. Old throws on 9223372036854775808 and 10000000000000000000; new returns positive. Use normalized digit length then lexicographic order as oracle. Observe throws/returns before asserting sign. |
| C10 | Same semver4j pair, `satisfies` caret range grammar | Check ^0, ^0.x, ^0.0 and ^0.0.x on 0.0.0, 0.0.5, 0.5.0 and 1.0.0. New first two ranges implement [0,1.0.0), last two [0,0.1.0). Preserve failing and passing boundary points. Transfer the parsing machinery from C08 while fixing this library’s range semantics independently. |

C01–C04 are non-cryptographic hash semantics. For the strongest C01 claim, try proving invertibility of a fixed-input mixing round and finalization; the concrete change affects how the seed is extended. For C06 the date is explicit UTC and the provider is the release’s embedded data. Avoid importing the host’s timezone rules as an oracle. [Codec release notes][codec] · [Codec source][code] · [Joda changes][joda] · [IANA changes][iana] · [Semver4j changes][semchanges] · [SemVer ordering][semver]

### B · Twelve independent public benchmark tasks

Run these unmodified `valid-assert.prp` tasks from the pinned SV-Benchmarks Java tree. Every cell names a task; the paired rows are separate programs. Keep the original nondeterminism and assertion semantics. The corpus also declares a separate no-runtime-exception property on these programs. Score the specified property. The public competition column below is historical JBMC 6.8.0 at its competition budget; remeasure current local binaries at the campaign budget. [Pinned inputs][sv] · [Official per-task results][svres]

| IDs | Source subdirectory and tasks, expected true / false | Published JBMC outcomes in that order | Concrete discriminator |
|---|---|---|---|
| B01/B02 | `jbmc-regression/StringBuilderCapLen01` / `StringBuilderCapLen02` | true / false | Track length vs capacity; shrinking the true case leaves “Diffblue”. Empty input replays the false case. |
| B03/B04 | `jbmc-regression/StringBuilderInsertDelete01` / `StringBuilderInsertDelete02` | true / unknown | Mixed insert/delete overloads and a live buffer. Two empty Strings reach the false assertion in the second program. |
| B05/B06 | `jayhorn-recursive/SatFibonacci02` / `UnsatFibonacci02` | true / false | The true case checks fib(9)=34; n=8 witnesses the false assertion. |
| B07/B08 | `jayhorn-recursive/SatEvenOdd01` / `UnsatEvenOdd01` | error (42) / false | Mutual recursion on a nondeterministic nonnegative int. n=0 witnesses the false task. Report the input/stack scope and unwinding result. |
| B09/B10 | `algorithms/BinaryTreeSearch-FunSat01` / `BinaryTreeSearch-FunUnsat01` | error (42) / false | The true tree stores nonnegative values and searches for a negative. Choice stream 2,0 violates the paired zero-absence assertion. |
| B11/B12 | `algorithms/InsertionSort-FunSat01` / `InsertionSort-FunUnsat01` | out of memory / false | The true task sorts a descending sequence of distinct integers and checks its first two are strictly increasing. Duplicates refute this in the second program. Choice stream 2,0,0 replays the original assertion. |

All six false-task witnesses above replayed with assertions enabled on the pinned programs, substituting a typed choice stream for the corpus’s verifier nondeterminism. Fixed-input JVM checks on B01 and B05 passed. Local stock 6.11.0 and a published competition result can diverge on model details. Inspect assertion IDs and traces before treating any difference as a lead. Source translations or narrower inputs get a separate result.

## 3. Decide whether the advances transfer

**First checkpoint — catch a real change and close a genuine JBMC lead.** Publish the four-cell Lucene writer/reader table with a replayable mixed-release witness, the preservation control W04, and the strongest symbolic scope reached. Publish N01/N02 with the same 2⁴⁶-pair domains on both engines, then attempt N10 with the frozen implementation. Separately, repair the first unsupported public input in H01 or the metadata gap in S01 and show one relevant public library caller benefits. Choose the implementation based on the common failure observed. A generalized VarHandle model, an accurate bit-vector rule or a generator improvement earns its keep when another caller uses it.

**Second checkpoint — establish a reusable result about a change.** Complete one public pair with affected and unaffected observations and test its summaries in a second pair. Good first combinations are W04→W05/W07, S01→S02→S08, H03→H05/H06, and C05→C06. For an independently checked result, bind the theorem, assumptions, original bytes, dependent methods/resources and query evidence. Start with a small byte-order or size lemma if the recovery work supplies the checker. An LRAT receipt for one UNSAT query establishes that query only. For an any-length claim retain the base/step, loop summary, termination assumptions and whole-caller composition. Keep bounded, inductive and independently checked results separately visible.

**Third checkpoint — test unfamiliar upgrades once, cold.** Before feature work, use a reproducible draw to seal **16 release pairs across at least eight previously unused projects**. Draw four pairs per stratum covering persisted representation, public object histories, numeric/text interpretation, and metadata/resource-driven behavior. Start from a dated release population with published binaries, source and an executable public API. Exclude examples already in the casebook, repository or recovery queue. Sort eligible entries by artifact and version, record the random seed and stratify by project. Include routine consecutive upgrades alongside documented behavior changes. Use release metadata and executable specifications to set eligibility. Write the selected pairs to a sealed manifest and publish only its digest during development. Keep the case identities and reference material out of development until the checker, tool profiles and selection policies are frozen.

After the freeze, use the published specification or upstream tests to pin a reference caller, one primary question, its expected behavior and at least one unchanged observation per pair. Record these before inspecting either checker’s results. Give the **automatic workflow** only the artifact pair and the allowed public materials. Withhold the reference caller, labels and expected outputs. Save whether the workflow discovered the relevant observation, reached the public path on both releases and decided the original question.

Then run the **matched proof comparison** with the same reference caller, observations and input domain on both engines. Publish the manifest, seed, selection history, and reasons for any exclusions or replacements. Keep unsupported classpaths, timeouts and missed properties in the original denominator. Archive any subsequent assisted run separately so its results can guide the next change.

### What would justify saying “ahead”

| Claim | Evidence to publish |
|---|---|
| Caught up on a Java semantic family | A named former JBMC-only property now decided by native under the same inputs, plus an independent transfer or a false sibling. Report lost historical decisions beside recovered ones. |
| Better on a named family | Two independently implemented public callers, a qualified native result, and an equivalent stock comparison. Identify the exact stock status and profile. If the benefit comes from automatic caller/graph construction, measure it there and also give JBMC the explicit caller. |
| Stronger change evidence | A mixed-version characterization, audited dependency-aware reuse, or an any-length theorem checks a stronger quantified statement. Show the concrete question answered, any assumptions and one deliberately wrong observation it rejects. Record how far JBMC reaches on the bounded equivalent. |
| Provisional lead on unfamiliar upgrades | Suggested target: at least **8/16** original primary questions decided by the automatic workflow, across ≥4 projects; more correct native-only than JBMC-only decisions in the *matched* blind panel, with independent wins in ≥3 projects and zero known incorrect native decisions. Publish the full 16, paired counts and project-level uncertainty. Separate contracted and partial theorems. This small cohort can support a scoped claim about the evaluated release changes. |
| General-purpose JBMC replacement | Keep this question open while ordinary threaded execution is deferred and large areas of the public corpus remain untested. A second independently drawn panel and a larger public-corpus run are sensible next tests if the focused lead holds. |

For each original claim, report the numerator and denominator, the exact observation, caller, permitted input/heap topology, startup/JDK profile, bounds, status and first unresolved operation. Keep physical refutations, strict bounded proofs, independently checked theorems, qualified assumptions and sampled JVM observations distinct. A narrowed result is progress if its scope is named and the original remains open. For each blind pair retain before/after digests, classpath order, relevant resources and replayable witnesses. For each native/comparator disagreement include both literal results and the adjudication. Compare cold and warm resource use. Count how often a caller, observation or proof rule required manual input.

Keep the existing 32 external upgrades as a historical shadow evaluation on the frozen tool. Keep their original automatic primary claims and assistance settings; publish any changed decisions alongside the old 0/32. Supplement them with the sealed 16. Where the existing recovery or change-verification brief has already delivered a relevant caller, checksum and reuse it, and disclose that exposure.

**Record and resume.** Save the versioned case manifest, exact commands and digests, per-engine reports and a short results matrix using the repository’s existing benchmark conventions. At the end of each cycle, record the case ID, new result, transfer outcome and next unresolved instruction or dependency. After an interruption, resume at that instruction using the saved receipt. After the blind panel, order the next semantic investments by how many independent projects a common blocker held up. A result that neither checker can decide, with a single small missing premise identified on multiple public callers, is an actionable campaign outcome.

## 4. Reproduce the first compatibility witness

Use the following small caller to reproduce the four W01 observations on unmodified artifacts. It works across separate JVMs, including on machines where loading two definitions of the same class in one analysis is inconvenient. The writer checks cursor and both sentinels. The reader checks the consumed length. Keep the symbolic proof harness separate from this concrete witness.

```java
// WirePair.java
import org.apache.lucene.store.ByteArrayDataInput;
import org.apache.lucene.store.ByteArrayDataOutput;
import java.nio.file.Files;
import java.nio.file.Path;

public final class WirePair {
    public static void main(String[] args) throws Exception {
        Path file = Path.of(args[1]);
        if ("write".equals(args[0])) {
            byte[] frame = {0x33, 0, 0, 0, 0, 0x55};
            ByteArrayDataOutput out = new ByteArrayDataOutput(frame, 1, 4);
            out.writeInt(0x01020304);
            if (out.getPosition() != 5 || frame[0] != 0x33 || frame[5] != 0x55)
                throw new AssertionError();
            Files.write(file, frame);
        } else {
            byte[] frame = Files.readAllBytes(file);
            ByteArrayDataInput in = new ByteArrayDataInput(frame, 1, 4);
            System.out.printf("%08x%n", in.readInt());
            if (in.getPosition() != 5) throw new AssertionError();
        }
    }
}
```

```sh
# In a fresh directory with WirePair.java and JDK 21, on a Unix-like system
for v in 8.11.0 9.0.0; do
  curl -fsSLO "https://repo.maven.apache.org/maven2/org/apache/lucene/lucene-core/$v/lucene-core-$v.jar"
done
javac -cp lucene-core-8.11.0.jar WirePair.java
for writer in 8.11.0 9.0.0; do
  java -cp ".:lucene-core-$writer.jar" WirePair write "frame-$writer"
  for reader in 8.11.0 9.0.0; do
    printf '%s -> %s  ' "$writer" "$reader"
    java -cp ".:lucene-core-$reader.jar" WirePair read "frame-$writer"
  done
done
```

| Writer | Reader 8.11.0 | Reader 9.0.0 |
|---|---|---|
| 8.11.0 | 01020304 | 04030201 |
| 9.0.0 | 04030201 | 01020304 |

Verify the artifact SHA-256 digests below and record the full environment in the campaign receipt. The exploratory JVM runs used OpenJDK 21.0.13. Historical reproduction uses its published JDK 25.0.5 profile.

| Artifact | SHA-256 |
|---|---|
| lucene-core 8.11.0 | `5069436519426486f74a84a77763895ec9ace807929dc931ab36760893cb8267` |
| lucene-core 9.0.0 | `f03aa0afc676ac80d111189c235974e6f4c628182e511aeb7e58b01db577c91a` |
| vecmath 1.5.2 | `3558e81ca74c60dc01baca7ef05f48594bbaed43af45d4f1b9196e479734e675` |
| spring-core 6.1.14 | `e15a1179fc9642ffed13ca55e2863e2da524ccd1083b7c6f1b5cfd5733f3b2c5` |
| spring-core 6.2.0 | `3b82629da38717dd616a70ec1055f9a8e208d58132071a6314a32159f8bce162` |
| protobuf-java 3.25.5 | `8540247fad9e06baefa8fb45eb313802d019f485f14300e0f9d6b556ed88e753` |
| protobuf-java 4.33.0 | `6c50b4323a101dfd7b8aea209337ac49ecf5d8e33e0b210b196fc654291ed2cc` |

## 5. Two small checker entrypoints

The Lucene example above demonstrates the product question. These two starters reproduce the arithmetic and reflection questions with symbolic inputs or a single fully specified metadata shape. Build them in separate class directories. The same product bytes and intended properties go to both checkers. Keep the stock assertions in their adapter. Putting them on the numeric product class introduces a class-initialization read of assertion status and changes the strict integrated comparison.

```java
// Product.java — requires javax.vecmath:vecmath:1.5.2
import javax.vecmath.Vector2f;

public final class Product {
    public static boolean underflow(float x, float y) {
        boolean admitted = x >= 0x1p-75f && x < 0x1p-74f
                        && y >= 0x1p-75f && y < 0x1p-74f;
        if (!admitted) return true;
        Vector2f value = new Vector2f(x, 0f);
        value.scale(y);
        boolean tie = x == 0x1p-75f && y == 0x1p-75f;
        return (value.x == 0f) == tie
                && (value.x == 0f || value.x == 0x1p-149f || value.x == 0x1p-148f);
    }

}

// Put the stock assertion adapter in a separate class from the product predicate.
final class ProductChecks {
    public static void expected(float x, float y) { assert Product.underflow(x, y); }
    public static void reach() { Product.underflow(0x1p-75f, 0x1p-75f); assert false; }
}
```

```java
// InterfaceShape.java — no framework dependency
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;

public final class InterfaceShape {
    interface Convert<T, U> {}
    static final class C implements Convert<Enum<?>, String> {}

    public static boolean intact() {
        Type[] interfaces = C.class.getGenericInterfaces();
        if (interfaces == null || interfaces.length != 1
                || !(interfaces[0] instanceof ParameterizedType)) return false;
        ParameterizedType original = (ParameterizedType) interfaces[0];
        interfaces[0] = String.class;
        return original.getRawType() == Convert.class
                && C.class.getGenericInterfaces()[0].equals(original)
                && original.getActualTypeArguments()[1] == String.class;
    }

    public static void expected() { assert intact(); }
    public static void inverted() { assert !intact(); }
}
```

```sh
# Set CORE_MODELS to this JBMC distribution's packaged core-models.jar.
mkdir -p product reflection
javac -source 8 -target 8 -g -cp vecmath-1.5.2.jar -d product Product.java
javac -source 8 -target 8 -g -d reflection InterfaceShape.java
jvmcontract prove 'Product#underflow' --classes product --classpath vecmath-1.5.2.jar --engine native --gaps strict --assert result --json
jvmcontract prove 'Product#underflow' --classes product --classpath vecmath-1.5.2.jar --engine jbmc --gaps strict --assert result --json
jbmc ProductChecks --classpath "product:vecmath-1.5.2.jar:$CORE_MODELS" --function 'ProductChecks.expected:(FF)V' --throw-runtime-exceptions --unwind 8 --unwinding-assertions --sat-solver cadical
jvmcontract prove 'InterfaceShape#intact' --classes reflection --engine native --gaps strict --assert result --json
for property in expected inverted; do
  jbmc InterfaceShape --classpath "reflection:$CORE_MODELS" --function "InterfaceShape.$property:()V" --unwind 8 --unwinding-assertions
done
```

Use `ProductChecks.reach:()V` as the post-call false control and the two lower endpoints as a witness against strict positivity. On the reflection fixture the JVM’s target outcomes are true/false. For the first Spring transfer, keep the released Spring generic-resolution path and its real converter signature.

[head]: https://github.com/pilifs/in-the-loop/tree/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d
[benchmark]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/RESULTS.md
[historical]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/results.json
[runner]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/run.py
[semantics]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/jbmc-java-semantics-gap-results.md
[follow]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md
[upgrades]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/external-upgrade-evaluation-results.md
[receivers]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/receiver-construction-and-property-discovery-results.md
[springrun]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/spring-and-java-data-workstream-results.md
[kernel]: https://github.com/pilifs/in-the-loop/tree/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel
[jbmc]: https://www.cprover.org/jbmc/
[lucene]: https://lucene.apache.org/core/9_0_0/MIGRATE.html
[lucenejar]: https://repo.maven.apache.org/maven2/org/apache/lucene/lucene-core/
[proto]: https://github.com/protocolbuffers/protobuf/commit/0a2f7757e38b07c2e40c5c885a7100e8c16eb40f
[vec]: https://repo.maven.apache.org/maven2/javax/vecmath/vecmath/1.5.2/
[jackson]: https://repo.maven.apache.org/maven2/com/fasterxml/jackson/core/jackson-core/2.19.0/
[jackson217]: https://github.com/FasterXML/jackson-core/compare/jackson-core-2.17.1...jackson-core-2.17.2
[lang]: https://repo.maven.apache.org/maven2/org/apache/commons/commons-lang3/3.17.0/
[numbers]: https://repo.maven.apache.org/maven2/org/apache/commons/commons-numbers-field/
[jts]: https://repo.maven.apache.org/maven2/org/locationtech/jts/jts-core/
[roar842]: https://github.com/RoaringBitmap/RoaringBitmap/pull/842
[roar888]: https://github.com/RoaringBitmap/RoaringBitmap/pull/888
[jsoup2140]: https://github.com/jhy/jsoup/issues/2140
[jsoup2235]: https://github.com/jhy/jsoup/issues/2235
[pcollections]: https://repo.maven.apache.org/maven2/org/pcollections/pcollections/
[s30079]: https://github.com/spring-projects/spring-framework/pull/30079
[s20727]: https://github.com/spring-projects/spring-framework/issues/20727
[code]: https://github.com/apache/commons-codec/blob/c89d2af770f05457fbefa5fb4713c888bf177fb2/src/main/java/org/apache/commons/codec/digest/MurmurHash3.java
[codec]: https://commons.apache.org/proper/commons-codec/changes.html
[joda]: https://www.joda.org/joda-time/changes-report.html
[iana]: https://data.iana.org/time-zones/tzdb-2022g/NEWS
[semchanges]: https://github.com/semver4j/semver4j/pull/478
[semver]: https://semver.org/#spec-item-11
[sv]: https://gitlab.com/sosy-lab/benchmarking/sv-benchmarks/-/tree/7efe28dd29576b46927b7a34e8f742bd90966a75/java
[svres]: https://sv-comp.sosy-lab.org/2026/results/results-verified/jbmc.2025-12-09_16-35-43.results.SV-COMP26_valid-assert.Java.valid-assert.Main.xml.bz2.fixed.xml.bz2.table.html

## Setup Agent Notes

### What is ready, and where

- `$B` = `~/.cache/in-the-loop/beyond-jbmc`. JDK 21.0.13 by full path, `~/.sdkman/candidates/java/21.0.13.0+9-tem/bin/`.
  The default `java` is 25.0.5 (`~/.sdkman/candidates/java/25.0.5.0+8-tem`), the historical profile.
- **Tools** ([table](#starting-commit-and-tools)):
  - `lib/target/release/jvmcontract`, rebuilt at `9920f659e67c1aea4aa114c59c93813dbd61b69d`, sha256
    `f02a6de8c6298109711f9cc4f81fb00c84168cfb276abfd57c1e1ab4dc6f9ca6`;
  - JBMC 6.11.0, both packages. On `PATH`: `/usr/bin/jbmc` with `/usr/lib/core-models.jar`. The 22.04 package is
    under `~/.cache/in-the-loop/jbmc-java-semantics-gap/releases/cbmc-6.11.0/ubuntu-22.04/`.
- **Historical 187**:
  - unmodified copy `$B/historical/results-867fa025.json`, sha256 `14c25280da82eaba7116753d704c33527aedf0e2008ff0eb664a805068d1de75`;
  - 187 unique IDs, all present in `run.load_cases` at this head;
  - what changed in their inputs: [The historical 187](#the-historical-187).
- **42 release graphs** in `$B/releases/NAME/` (`lib/`, `sources/`, `classpath.txt` ordered, `tree.txt`). They cover
  every released version the brief names, plus RoaringBitmap neighbours 1.6.15, 1.6.18, 1.6.25 and 1.6.28, and Spring
  6.1.3 and 6.2.3 with `spring-context`. Every jar was checked against Central's checksums and its signature; digests
  are in [the release table](#released-artifacts) and `$B/logs/release-jars.sha256`. Offline resolution works with
  `mvn -o -s $B/maven-settings.xml`.
- **Pinned sources** ([table](#pinned-sources)):
  - Commons Codec `c89d2af770f05457fbefa5fb4713c888bf177fb2` (= `rel/commons-codec-1.15`), `$B/src/commons-codec-c89d2af7`;
  - protobuf `0a2f7757e38b07c2e40c5c885a7100e8c16eb40f`, `$B/src/protobuf-0a2f7757` (`java/` only);
  - SV-Benchmarks `7efe28dd29576b46927b7a34e8f742bd90966a75` (= `svcomp26`), `$B/src/sv-benchmarks-7efe28dd` (`java/` only).
- **SV-COMP 26 official JBMC results**: `$B/svcomp/results.xml.bz2` and `table.html`, with the twelve B rows extracted
  [here](#pinned-sources).
- **Class bytes and disassembly** for every class the casebook names: `$B/classes/RELEASE/`, `$B/logs/classes.sha256`,
  `$B/logs/javap/RELEASE/` ([Class entries](#class-entries)).
- **JVM probes and their outputs**: `$B/probes/{sv,jvm/wn,jvm/hc,jvm/s}/` and `$B/logs/jvm-*.txt`. They reproduce
  observations; they are not adapters. `$B/probes/sv/replay.sh JDKBIN` replays the twelve B tasks with a typed
  choice-stream `Verifier`.

### What was verified on a JVM

On Temurin 21.0.13, and for the B tasks on 25.0.5 as well. Full rows: [What was replayed on a JVM](#what-was-replayed-on-a-jvm).
- **B**: all six false-task witnesses fail their assertion (B02 `s`, B04 `s,s`, B06 `i8`, B08 `i0`, B10 `i2,i0`,
  B12 `i2,i0,i0`), and B01, B03, B05 pass.
- **W01–W07**: the four-cell WirePair table exactly. W01, W04, W05 and W06-UInt32 hold over **all 2³² ints**. W03's
  256/65,536 shorts. W05 holds on all three protobuf versions.
- **N01–N11**: every JVM statement, including N04's 1,617/2,000 (807/808), N06's 370 and 397, N08's hash and NaN
  changes, N11's 63/11,048 and its `ObjectMapper` paragraph (63 per type, `-0.`, mixes follow core).
- **H01, H03–H06, H08–H10, C01–C06, C08, C09**: as stated, with the exceptions below.
- **C10**: the new release as stated.
- **S01, S02, S04–S09**: as stated, on Spring 6.1.3, 6.1.14, 6.2.0 and 6.2.3.

### What to know before starting

- **H07 does not reproduce with `RoaringBitmap.contains(long,long)`**: true,false,false on 1.6.25–1.6.28 for every h
  and representation. The stated true,true,false → true,false,false appears only with the subset form
  `contains(RoaringBitmap)`, where the superset is a bitmap container (9,999 single adds) and the query a run
  container. The 1.6.26→1.6.27 diff is `BitmapContainer.contains(RunContainer)` (and its Mappeable twin). The caller
  is yours to choose.
- **H08 differs by append path**: `appendElement("input").attr("name","b")` shows [a]/[a]/[a] → [a]/[a, b]/[a], while
  `append("<input name=b>")` gives [a]/[a, b]/[a] on both 1.18.1 and 1.18.2.
- **H02's "predecessor-only detector" is undefined** in the brief. Next == previous node is not rejected on the
  two-node cycle; next == current node does not terminate on it. The oracle part holds 256/256.
- **N06's 397** is against `Double.parseDouble`; against `new BigDecimal` there are 0 disagreements.
- **C10's old release**: 6.0.0 makes ^0 and ^0.x true on all four versions (1.0.0 included), and ^0.0 and ^0.0.x
  false on all four (0.0.0 included).
- **H06**: old releases also throw `ArrayIndexOutOfBoundsException` (index −1) once the origin passes the container
  start.
- **First changed RoaringBitmap jars**: the iterator clone first changed in **1.6.17** (1.6.15 and 1.6.16 old, 1.6.18
  new); containment first changed in **1.6.27** (1.6.25 and 1.6.26 old, 1.6.28 new).
- **W02**: the slice bound is only an `assert` in both Lucene releases, so the outcome depends on `-ea`. Without it, a
  len=3 slice takes 4 bytes.
- **The protobuf pin `0a2f7757` is PR #15043's head, not a release tag.** The released sources are the sources jars.
- **SV-COMP 26 ran on SV-Benchmarks `svcomp26-rc.1`** (`e8b309124df9bee33baf12bd47c629245971fce7`), not the pinned
  `svcomp26`. The twelve tasks, `common` and `valid-assert.prp` are object-identical at both. The published run was
  JBMC 6.8.0 at 900 s and 15 GB.
- **The checker at this head is not the baseline's**: `lib/` changed after `867fa025` (last commit
  `850595ae1e2f91815eee3b5822cd640f96eed630`). For the historical refresh:
  - `conformance.json` gained `conformance/mapCapacity/2`, so pass the 187 IDs exactly;
  - `Conformance.java` gained 22 lines, which moves later line numbers;
  - 22 conformance cases changed only their `nativeStrict` annotation.
- **Class majors**: lucene-core 9.0.0 is 55, Spring 6.x and semver4j 6.x are 61. The rest are ≤ 52.
- **Two JBMC 6.11.0 packages with different `core-models.jar`**; the archived benchmark names only the version.
  Name the pairing in each standalone run.
- **Signatures**: JTS 1.18.2's key expired 2022-03-20, after its 2021-08-27 signature (`EXPKEYSIG` + `VALIDSIG`).
  No snapshot dependencies.
- **Grids**: where the brief gives none, the probes chose them (named in each row). Several reproduce the brief's
  counts on a different or smaller grid: C04 150,000 vs 659,180 checks; the long and float spaces are sampled.

### What is left for the domain work on purpose

- **All checker runs**:
  - the three-column refresh of the 187 (strict native, integrated staged JBMC, standalone stock JBMC);
  - every native or JBMC statement in the casebook;
  - the brief's §5 `jvmcontract`/`jbmc` commands;
  - every proof, cache or reuse question (C05 clean/warm, C06/C07 cache).
- **The 16-pair blind panel**: drawing, seeding, sealing and its manifest. This setup did not look at any candidate
  population.
- **Fixtures with no released input**: H11–H14, E01–E03, S03 (historical formatter slices), C07 (the zone choice),
  W08/W09, and the H08 reparenting and H07 widening.
- **Every harness, caller, adapter, claim, example and score.**
