# From Java entry points to independently checkable properties

**Execution brief for `pilifs/in-the-loop` · 22 November 2026**  
**Run after** the [15-case Java semantics campaign][prior]. **Planning baseline** [develop at `2fff2b0d`][head]. Reconcile both with the checkout and completed receipts on the execution VM.

## The question to answer

Given a library JAR, a public method and explicit bounds, can the checker construct receivers a caller could actually reach, identify which safety checks matter on those paths, and let an investigator decide one check and replay its witness? These are gaps **1 (receiver and heap construction)** and **5 (property discovery and investigation)**. Work on them together. A real receiver can make a previously invisible check reachable. A selected check can also explain which receiver shape or prior call is missing.

The first milestone is one previously blocked public caller decided by strict native checking at its registered scope, plus a transfer to an independently selected library. The longer-term test is whether those capabilities continue to work when the interesting operation is inside a parser, floating-point mutation or concurrent history. Agents choose the construction, analysis and solver techniques. Use the examples to decide which abstractions deserve to live in the project.

| In order | Cases | Evidence that warrants advancing |
|---|---|---|
| Establish what the checker discovers on its own | 1. Shared inventory; 2. Caught, escaping and unreachable instructions | Both receiver identities reached, false invariant replayed, one physical safety site independently selected, and a short unwind reported incomplete |
| Exercise existing callers, then remove a real blocker | 3. Commons CSV; 4. Commons Configuration JSON and YAML | CSV retains its existing decisions. A newly reached Configuration path is identified precisely, then the original public result is checked on both dependency versions |
| Test transfer outside that host library | 5. JGraphT; 6. JavaParser and XZ startup | An unfamiliar receiver history or initializer is handled without a target-specific rule. Report exactly which histories and process states were covered |
| Extend the same investigation workflow | 7. Guava parser; 8. Commons Lang floating point; 9. Three-worker scheduling | Each runs from the declared entry, exercises its selected property, and includes a false claim with a replay. Track closure separately for each gap |

## Start from the actual frontier

Of 23 historical receiver-blocked upgrade cases, 16 already reached both original methods on the JVM for their registered inputs. The project subsequently verified two complete bounded callers on both original versions, Commons CSV and Commons Compress framed LZ4. All 34 unrestricted paired overloads in that cohort remained open. A JVM invocation, a supplied bounded caller, and an unrestricted native result answer three different questions. Example 366 below is a separate CSV pull request and also has existing ordinary decisions. [Receiver cohort and recount][foundation] · [Java campaign results][java-results]

On the execution checkout, use `python3 examples/tools/build.py --plan 360 366` to inspect the ordinary JavaParser and CSV tasks, then repeat their named jobs and the Configuration receipts below. Record any closures from the preceding brief as opening results. Start at the first surviving blocker. The preflight observations in this brief used ordinary JVM execution and, for selected cases, standalone JBMC 6.11.0. New native verdicts are for the execution campaign to establish. [Earlier brief and comparator profiles][prior] · [Latest workstream results][streams]

## Wave 1 · Construction and discovery on the same run

### 1. A factory builds two stocks that can share identity

Use the runnable `Checkout.java` in the appendix. `Pair.open(int n, boolean shared)` clamps the initial count at zero and constructs either one shared stock or two equal-valued stocks. Its constructor is private. The first `take()` decrements a positive primary stock. Ask these questions independently.

| Question | Scope and expected outcome |
|---|---|
| Can the primary stock start negative? | A raw non-null field graph permits it. Through `open` and the declared history, the field is always nonnegative |
| Does taking a unit succeed? | Through `open`, exactly when `n > 0`, for every signed Java int and both choices of `shared` |
| Does the backup lose a unit? | Exactly when the stocks are shared and positive. The wrong claim that the backup always keeps its value fails at `open(1, true)` |

Run three entries: the raw parameter, an explicit factory wrapper, and an entry for which the checker must discover a public producer for `Pair`. Supply the automatic lane the classpath, type or method, property and bounds. Keep the factory call, alias selector and evaluator’s plans out of its inputs. Allow one public producer and up to one stock mutation for this first exercise. Report the actual generated construction for each witness. If the automatic search only covers some public histories, a proof is local to that subset. In particular, a counterexample from writing fields directly establishes a violation only for that raw domain until a legal history reproduces it.

Standalone JBMC admitted a negative integer through the raw parameter, established the factory invariants and rejected the alias-blind claim. On the JVM, the boundary counts `MIN_VALUE, -1, 0, 1, MAX_VALUE` passed in both alias states and the small shared witness failed as expected. Use the existing plan and heap machinery as a starting point. The new capability is finding and replaying the path from the public surface. [Construction][construction] · [Plans][plans] · [Heap inputs][heap]

### 2. Independently investigate a caught divide, an escaping access and a dead dereference

Compile `SafetySites.java` from the appendix with debug information. Inventory the candidate checks in the original `run(II)I` bytes. Select each by owner, descriptor, bytecode offset and check kind. The bindings below were observed on the preflight classfile. Resolve them again on the campaign build.

| Input or mutation | Observation on JDK 21 | What an independent query must distinguish |
|---|---|---|
| `run(0,0)`, then `run(0,3)` | `idiv` at offset 19 throws and enters the handler at 21 on zero. The calls return −10 and 6 | “The division never throws” fails. “No arithmetic exception escapes this method” holds on this branch |
| `run(1,2)` | `iaload` at 44 throws `ArrayIndexOutOfBoundsException` across the `run` boundary | Replay the actual instruction, index and escaping exception. An outer observer may catch it |
| `run(3,0)` | Guard returns −99 before `arraylength` at 54. Change the first guard to `mode > 3` and the same input throws `NullPointerException` there | Mark the original site unreachable, then rediscover and rebind the site in the mutant |
| `run(2,0)` | Seven iterations produce 21. With JBMC unwind 3 the user assertion was green while the unwinding assertion failed. At 9 both passed | Report incomplete at the smaller bound. Preserve the completeness check when a single property is selected |

Two comparator details matter. JBMC’s occurrence checks can report a division by zero that Java catches. In the preflight exception-throwing profile, stock JBMC also reported an uncaught exception for the same-method handler. Moving the division into a helper called inside the same `try` preserved the JVM outcome and let JBMC prove the true return claim and refute its inverse. Retain both bytecode shapes and match the property meaning before comparing verdicts. Native already has exception-dispatch unit tests. The new deliverable is discovery, selection and evidence for the original physical site. [JBMC property, loop and exception controls][jbmc] · [Native execution and tests][bmc] · [Original bytecode and handler tables][classfile]

### 3. Calibrate against an already decided public change · Apache Commons CSV #218

Use original example 366. Its adapter constructs a format through the public builder, parses a reader, tests for a record, checks its field count, reads fields and checks for exhaustion. For `a||b||`, the parent yields `["a","b|"]`. The fix yields `["a","b",""]`. On this parent input the field-count check returns early. A downstream content check cannot witness the discrepancy on that path.

Give the agent the original entry and guards. Have it discover implicit JVM checks and separately register the user-specified observations of count, field contents and exhaustion. Selecting count should expose the parent difference without requiring the investigator to reverse-engineer the adapter’s aggregate Boolean. Selecting a field observation should state on which paths it ran. Keep the four existing ordinary decisions green. Success here is better investigation of known results. [Public caller][csv] · [Existing results][java-results]

## Wave 2 · Recover a blocked public caller and test transfer

### 4. Two Commons Configuration upgrades share a startup blocker

Use the registered `UpgradeProbe.observe` from #565 (JSON, Jackson Databind 2.18.3 → 2.19.0) and #601 (YAML, SnakeYAML 2.4 → 2.5). Each constructs a fresh configuration, reads a document and calls `getList(String.class, key)`. The four registered observations on each dependency side are `"[red, blue]"`, `"[Ada]"`, `"[7]"` and `null`. The four last strict runs stopped at `InMemoryNodeModel.<clinit>`, reached from `BaseHierarchicalConfiguration.createNodeModel`. The initializer creates a static dummy tree. Each live node model also carries its own atomic reference. [JSON caller][json-probe] · [YAML caller][yaml-probe] · [JSON receipt][json-receipt] · [YAML receipt][yaml-receipt]

Start on JSON. Discover the public construction path, identify the first stopping instruction and select a downstream property of the lookup. Run YAML with the same implementation before adding any YAML-specific behavior. Include an isolation control that reads different documents into two fresh configurations and observes both after the second mutation. An implementation that confuses shared startup state with a shared live tree should fail it. Report each dependency version separately. Reaching an initializer or even reaching `getList` is progress; closure requires the registered public observation. These are two dependency transfers inside one host library.

### 5. Blind receiver transfer · JGraphT adds an edge to a directed acyclic graph

Use the released `org.jgrapht:jgrapht-core:1.5.2`, `DirectedAcyclicGraph.addEdge(source,target,edge)`. Give the generator the release, public target and bounds (three distinct labeled vertices, at most three pre-existing edges, no self-loops). Keep the evaluator’s builder and transition oracle separate. Freeze the generator on cases 1–4 before running this caller. A hand-authored graph builder can still establish a bounded claim and gives a useful comparison if discovery falls short. [Public implementation][jgrapht]

For evaluation, enumerate the six ordered non-self arcs. Keep each acyclic subset, construct it through public calls in lexicographic arc order, and try each arc with a fresh edge from a fresh copy of that graph. Predict the outcome independently with transitive closure. Compare every pre-existing edge and both endpoint identities after the operation, including rejected operations. The original JAR on the JVM produced **25 graphs and 150 transitions: 48 insertions, 48 duplicate pairs returning false, 54 cycle exceptions**. This census covers canonical construction orders. Other orders may induce different internal states.

Add an identity control on a single-edge graph. Reusing its existing edge with an unregistered source returns false. Using a fresh edge with that same source throws `IllegalArgumentException`. Passing a null edge with valid endpoints throws `NullPointerException`. The topology remains unchanged. Report how many of the 25 starting graphs and three outcome classes the automatic route actually reaches. For any missing family, return its first blocker and reproduce one representative through the public API. No native or JBMC result is claimed for this holdout.

### 6. Transfer startup reasoning between JavaParser traversal and XZ reads

- **JavaParser #4538, example 360.** Construct an empty `CompilationUnit` and one with package `com`. Observe `findAll(Node.class, POSTORDER)` and the public postorder iterator. The fixed populated tree returns the exact identities `name, package, root`; the empty tree returns the root. The parent has an empty-tree `EmptyStackException` witness. Include preorder as a control. The project had 2/8 ordinary decisions and 8/8 with a supplied non-null separator of up to two UTF-16 units. Investigate the first read of `line.separator` and which outcomes reach the selected traversal check. Preserve both the absent-property initialization failure and the failure on repeated use of the erroneous class. [Caller][javaparser] · [Scope and receipts][foundation]
- **Commons Compress #767.** Construct `XZCompressorInputStream` over the registered frames and read to EOF. The four outputs are empty, `hello\n`, bytes `00 ff 00 80`, and bytes 0 through 15. Both strict dependency graphs stopped at `org.tukaani.xz.ArrayCache.<clinit>` reading a system property. Fresh JVMs with XZ 1.11 and 1.12 selected the dummy cache when absent or `Dummy`, and the basic cache for `Basic`. `Bogus` caused an `Error` on first use and `NoClassDefFoundError` on the next use in that loader. Run profiles in fresh processes. Observe both the cache selection and the caller’s outcome; two cache identities can produce the same bytes. [Registered receipt][xz-receipt] · [XZ initializer][xz-source]

Try one reusable way to account for a real property read. It might prove independence of selected outputs, model the relevant property symbolically, or establish a conditional fact. Quantify over the exact environment admitted by the caller, including missing values where allowed. A captured or assumed value earns a conditional result. Credit an ordinary universal claim only when the evidence covers that original scope. Keep a counterexample replayed at ordinary entry in its own right.

## Wave 3 · Carry the same entry and property workflow into deeper semantics

### 7. Follow a symbolic string through Guava’s real integer parser

Pass a direct symbolic `String` to Guava 33.4.8-jre `Ints.tryParse(s,16)`, through its digit table, long parsing, narrowing and boxed result. Admit `"7ffffff" + u` or `"-8000000" + u` for every UTF-16 code unit. On the positive branch, an ASCII hex digit of value d returns `0x7ffffff0 + d` and anything else returns null. On the negative branch only `u == '0'` returns a value, `Integer.MIN_VALUE`. An independent ASCII oracle checked all **131,072 strings on the JVM**. The wrong claim rejecting the minimum fails exactly once. [Guava entry][guava] · [Parser and digit table][guava-longs]

Stock JBMC spuriously accepted `7ffffff~` as a number on the direct-String route. Adding the unmodified OpenJDK 21.0.13 `java/util/Arrays.class` to its classpath let JBMC establish the direct properties and reject both the false minimum rule and a false assertion after return. Keep that comparator profile distinct from packaged models and from constructing the input with `new String(char[])`. On native, select the null/boxed-return observations independently and bind the actual digit-table initializer.

**Composition test.** Build a small client for `id=<hex>`. Exactly one equals sign is required. Check the key, slice the value and call the released Guava method. Return distinct outcomes for malformed shape, unknown key, invalid value and parsed integer. Compare with an independent one-pass scanner over code units. All **137,257** non-null strings of length 0–6 over `{i, d, =, 0, F, -, U+D800}` agreed on the JVM: 83,136 malformed, 53,862 unknown key, 208 invalid, 51 parsed. Null separately gives malformed. Checking the key too early misclassifies `d==F`. Dropping the sign turns `id=-F` from −15 into +15. Run the native proof from the client’s string parameter on the full bounded language. The four longer tokens around the signed-int limits are separate probes. No JBMC or native decision is assumed for this composition.

### 8. Mutate a Commons Lang receiver with two independent floating-point inputs

On `org.apache.commons:commons-lang3:3.17.0`, construct `MutableFloat(x)`, call `subtract(y)`, and observe `floatValue()`. Let **both** operands range independently over all binary32 values in `[1,2)`: 2⁴⁶ pairs. Widen the returned value to double and assert it equals `(double)x - (double)y`. All inputs lie on a grid spaced 2⁻²³ and their difference fits exactly. In a separate claim, wrongly assert that adding `2.0f` to both inputs before running the same sequence preserves the result. The solver’s witness was `x=0x3f800001` and `y=0x3f800000` in raw float bits. The JVM returned `0x34000000` (2⁻²³) for the original and positive zero after translation. [Released method][lang] · [Native floating-point execution][fp]

JBMC established the true property over the full Cartesian product, refuted the wrong one and reached a false assertion after return. The JVM also checked 100,081 boundary and seeded pairs. Route the mutation through the construction/history machinery from case 1 and preserve the exact argument bits in replay. Qualification at a smaller tuple cap is a separate result. A useful transfer is the same receiver and property over `[2,4)` with its corresponding spacing, followed by an operation that requires rounding. An adjacent-range success qualifies reuse across ranges; it establishes no claim for NaNs, infinities or unrestricted IEEE 754.

### 9. Discover a bad three-worker schedule

Create three workers on one object, initially all on duty (mask 7). Each checks whether its next neighbor is present and, if so, clears its own bit. Use two real `Thread.start()` calls and let the caller execute the third turn. All shared accesses take the same monitor. Check `mask != 0` when the **third commit** finishes. The atomic version holds the monitor from the check through the update. The split version releases it between reading the neighbor and committing. This is a protocol failure with synchronized accesses.

Use an independent enumerator at synchronized-operation boundaries. There are six complete serial orders for the atomic version, all safe. The split version has 90 read-before-own-commit orders: 48 leave no worker on duty and 42 leave one. Under its default sequentially consistent threading profile, JBMC 6.11.0 established the atomic claim and refuted the split claim. A fresh JVM replay paused each participant after a positive read and reproduced the assertion with three commits and mask zero. A false assertion on the third commit is reachable in both versions. [JBMC threading and unwind options][jbmc]

Give the analyzer the classes, thread and operation bounds, and the selected assertion. Hold back the enumerated schedules and failing trace until evaluation. Require it to find a schedule, preserve the participating object identity and monitor order, and replay the witness. Report the explored scheduling model and which complete executions it covers. This milestone covers a bounded safety property under the declared memory model. Liveness, fairness and weaker-memory behavior need their own claims.

## What to submit and how to decide the next investment

Use the repository’s normal example, verification-job and result paths. Keep the fixture source, original artifact coordinates/hashes, ordered classpaths, checker/build IDs, bounds and comparator profile with every claim. Record enough to rerun one selected property from the repository. Keep Rust execution semantics, Python campaign intake and existing witness formats where they fit. A new framework or upfront architectural redesign is unnecessary to start. [Property representation][properties] · [JVM witness support][witness] · [Existing receiver intake][intake]

| The investigator should be able to ask | Evidence to retain |
|---|---|
| What heap did this claim cover? | Entry and preconditions, producer and public call history, aliases and dynamic types, declared bounds, candidate histories missed or cut off. Identify automatic, explicitly supplied and raw-field results |
| Which checks could I select? | Candidate inventory for the inspected bytecode, kinds supported and skipped (e.g. null, bounds, arithmetic, cast/store and assertions as encountered). For each selected site bind class hash, owner, method and descriptor, bytecode offset, check kind, boundary and check policy. Map changes across revisions explicitly |
| What did this property decide? | Reachability plus proof/refutation/incompleteness, remaining unwind or model obligations, expected or escaping exception, and the first unresolved instruction. A green assertion behind an unclosed unwind or an unreachable site carries no proof of reached behavior |
| Can I reproduce the result? | A public JVM replay for each claimed original-scope violation with inputs, observable result, and site or boundary where applicable. For a proof, retain stated domain, evidence that the target ran, independent oracle or negative control, and strict verification receipt. Preserve justified comparator disagreements |

**Score the opening pair on a frozen denominator.** For each selected public case show (a) receiver reached on both original sides where there are two, (b) reachable checks with independent verdicts, (c) original public claims newly decided, and (d) whether any case-specific construction hint or model was needed. Count existing decisions, supplied-startup proofs and original-scope closures in their own columns. Compare the automatic and supplied lanes on the same bounds. On held-out callers, publish the misses as well as the hits. A fresh blocker with a minimal reproduction is a legitimate research result.

**Recommended sequence after this brief is queued.**

1. **Run cases 1–4 first.** Publish one command that selects a physical property on a constructed receiver, one alias-sensitive replay, and the before/after results for both Configuration upgrades. If construction succeeds but setup still dominates, follow the initializer into case 6. If the method runs but the cause is invisible, finish single-property investigation on case 3.
2. **Freeze the improvement and run transfer.** Execute JGraphT blind, then replay JavaParser/XZ and the frozen set of 23 receiver-blocked upgrades with the same implementation. Record newly reached targets and newly decided original claims separately. Prioritize the first mechanism that changes outcomes in a second host library. If the two Configuration cases alone improve, retain that result and diagnose the first independent miss before broadening the work.
3. **Use the next semantics queue selectively.** Default to the Guava parser first because it reuses startup and property selection on a full caller. Start the two-input arithmetic lane independently once its comparator and native baseline match the intended scope. Move schedule exploration forward when the witness format can express histories on a shared object. If the new native baseline already decides any proposed example, promote its composition or held-out transfer instead of counting the same win again.
4. **Remeasure the remaining JBMC lead.** Re-run the earlier 15-case campaign’s matched pairs on the new head and the established property IDs or their reviewed replacements. Report new native-only, JBMC-only, shared and unresolved decisions, with original bounds and model profiles. Keep JVM-confirmed comparator discrepancies visible. Use the surviving public callers to choose the following brief.

## Comparator profiles for the deeper cases

The preflight JBMC 6.11.0 executable had SHA-256 `2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c`. Its packaged core-model JAR had SHA-256 `2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de`.

| Case | Inputs that make the comparison reproducible |
|---|---|
| JGraphT | JAR SHA-256 `dfa596e9f0d0838f1b5e81dd0cd60e3a76c2c290ac25a0a029ffde58cf5e4c14`. Construct the evaluator graph with `new DirectedAcyclicGraph<>(null,null,false)`, ordinary vertices and explicit `new DefaultEdge()` insertions |
| Guava direct parser | JAR SHA-256 `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed`. The successful profile added a directory containing only the original JDK `java/util/Arrays.class` (SHA-256 `4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab`) before the core-model JAR. Use string bound 9, array bound 10, unwind 11, and loop-specific unwinds 27 for `Longs$AsciiDigits.<clinit>:()V.1` and 129 for `Arrays.fill:([BB)V.0`. Enable unwinding assertions and runtime exceptions |
| Commons Lang | JAR SHA-256 `6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4`. Use a public entry with two primitive float parameters and guards on the original operands. Retain a caller that unconditionally fails after a reachable return |
| Three-worker control | Enable `--java-threading --unwind 6 --unwinding-assertions` and record the default memory model. Use the separate terminal false-assertion control on both atomic and split versions |

## Reproducing the opening controls

Extract the following two source blocks into the named files. On a JDK 21 checkout run `javac -g Checkout.java SafetySites.java`, `java -ea Checkout`, `javap -c -p SafetySites`, and `java -ea SafetySites 1 2`. The latter prints the exception that escaped `run`. To repeat the comparator controls use standalone JBMC 6.11.0, a matching packaged core-model JAR, and separate entries such as `--function Checkout.viaFactory` and `--function SafetySites.loop`. Use `--show-properties` and `--property <id>` for comparator selection, and `--show-loops` with `--unwinding-assertions` for the two unwind budgets. Retain the assertion and all required completeness obligations when interpreting its result. Repository-native selection is an outcome to build and demonstrate. [JBMC reference][jbmc]

### Checkout.java

```java
public final class Checkout {
    public static final class Stock {
        private int left;
        public int remaining() { return left; }
        private Stock(int n) { left = n < 0 ? 0 : n; }
        public boolean take() {
            if (left == 0) return false;
            left--;
            return true;
        }
    }
    public static final class Pair {
        private final Stock primary, backup;
        public Stock primary() { return primary; }
        public Stock backup() { return backup; }
        private Pair(Stock primary, Stock backup) {
            this.primary = primary;
            this.backup = backup;
        }
        public static Pair open(int n, boolean shared) {
            Stock first = new Stock(n);
            return new Pair(first, shared ? first : new Stock(n));
        }
    }
    public static void raw(Pair p) {
        if (p != null && p.primary() != null) assert p.primary().remaining() >= 0;
    }
    public static void viaFactory(int n, boolean shared) {
        Pair p = Pair.open(n, shared);
        raw(p);
        int initial = n < 0 ? 0 : n;
        boolean taken = p.primary().take();
        assert taken == (n > 0);
        assert p.backup().remaining() == initial - (shared && n > 0 ? 1 : 0);
    }
    public static void assumesDistinct(int n, boolean shared) {
        Pair p = Pair.open(n, shared);
        int before = p.backup().remaining();
        p.primary().take();
        assert p.backup().remaining() == before;
    }
    public static void main(String[] args) {
        if (!Checkout.class.desiredAssertionStatus()) throw new IllegalStateException("Enable assertions");
        for (int n : new int[]{Integer.MIN_VALUE, -1, 0, 1, Integer.MAX_VALUE}) {
            viaFactory(n, true);
            viaFactory(n, false);
        }
        try { assumesDistinct(1, true); }
        catch (AssertionError expected) { System.out.println("Shared backup changed from 1 to 0"); return; }
        throw new AssertionError("False claim survived");
    }
}
```

### SafetySites.java

```java
public final class SafetySites {
    static int run(int mode, int value) {
        if (mode < 0 || mode > 2) return -99;
        if (mode == 0) {
            try { return 18 / value; }
            catch (ArithmeticException expected) { return -10; }
        }
        if (mode == 1) {
            int[] scores = {3, 4};
            return scores[value];
        }
        if (mode == 3) {
            int[] dead = null;
            return dead.length;
        }
        int sum = 0;
        for (int i = 0; i < 7; i++) sum += i;
        return sum;
    }
    public static void caught(int value) {
        if (value == 0) assert run(0, value) == -10;
    }
    public static void caughtMutant(int value) {
        if (value == 0) assert run(0, value) != -10;
    }
    public static void escaping(int value) {
        if (value >= 0 && value <= 2) { int result = run(1, value); assert result > 0; }
    }
    public static void dead(int mode) {
        if (mode == 3) assert run(mode, 0) == -99;
    }
    public static void loop() { assert run(2, 0) == 21; }
    public static void main(String[] args) {
        int mode = Integer.parseInt(args[0]), value = Integer.parseInt(args[1]);
        try { System.out.println("returned " + run(mode,value)); }
        catch (RuntimeException e) { System.out.println("escaped " + e.getClass().getName()); }
    }
}
```

[head]: https://github.com/pilifs/in-the-loop/tree/2fff2b0d3c2e55c88422de4201065ed907a23c4e
[prior]: https://chatgpt.com/library?file_id=libfile_fde3_f-18f68a35e2cc8191b3bfffb7c3c98dd0_1a220e41ac0481919d2d88e5f0713c02&account_id=personal
[foundation]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/llm-dlc/loops/domain-foundations-strategy-results.md
[java-results]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/llm-dlc/loops/java-domain-proof-campaign-results.md
[streams]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/llm-dlc/loops/spring-and-java-data-workstream-results.md
[construction]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/construction.rs
[plans]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/spec/plans.rs
[heap]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/spec/heap.rs
[bmc]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/bmc/mod.rs
[classfile]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/classfile/mod.rs
[csv]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/examples/366-commons-csv-delimiter-lookahead/adapter/campaign/DelimitedFields.java
[javaparser]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/examples/360-javaparser-postorder-root/adapter/organic/TreeOrder.java
[fp]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/bmc/floating.rs
[properties]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/property.rs
[witness]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/src/jvm_witness.rs
[intake]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/benchmark/domain-foundations/receiver_campaign.py
[json-probe]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/benchmark/external-upgrades/scenarios/commons-configuration-565/UpgradeProbe.java
[json-receipt]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/verification/domain-foundations/receiver-verified/04/callers/commons-configuration-565.json
[yaml-probe]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/lib/benchmark/external-upgrades/scenarios/commons-configuration-601/UpgradeProbe.java
[yaml-receipt]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/verification/domain-foundations/receiver-verified/04/callers/commons-configuration-601.json
[xz-receipt]: https://github.com/pilifs/in-the-loop/blob/2fff2b0d3c2e55c88422de4201065ed907a23c4e/verification/domain-foundations/receiver-verified/04/callers/commons-compress-767.json
[jbmc]: https://diffblue.github.io/cbmc/man/jbmc.html
[xz-source]: https://github.com/tukaani-project/xz-java/blob/v1.12/src/org/tukaani/xz/ArrayCache.java
[jgrapht]: https://github.com/jgrapht/jgrapht/blob/fe2d4cdfa42073eb1141e789844adc9c1fc8bf36/jgrapht-core/src/main/java/org/jgrapht/graph/DirectedAcyclicGraph.java#L341
[guava]: https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/primitives/Ints.java#L834-L840
[guava-longs]: https://github.com/google/guava/blob/f06690fa3e874f65515e8fd338a74d636e2c792f/guava/src/com/google/common/primitives/Longs.java#L404-L442
[lang]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/mutable/MutableFloat.java#L374-L376
