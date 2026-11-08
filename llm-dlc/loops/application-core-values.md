# Stream brief: application core, bounded Java values

One of four streams of [`application-core.md`](application-core.md) that run in parallel, each in its own jj
workspace on its own branch. The others are [`application-core-objects.md`](application-core-objects.md),
[`application-core-environment.md`](application-core-environment.md) and
[`application-core-reuse.md`](application-core-reuse.md). Once all four are finished, the main brief's loop merges
them ([Reconciling](application-core.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh application-core` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh application-core-values` from this stream's workspace
(`jj workspace root --name application-core-values`). The loop refuses any other.

**The main brief is the instruction.** Read [`application-core.md`](application-core.md) and the acceptance contract
[`application-core-acceptance.md`](application-core-acceptance.md) in full every cycle, with their inputs. Their
direction, starting point, working rules, safety rules, deferrals and decisions all apply here. This file says which
items are yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section. Edit
implementation files according to the main brief's [ownership](application-core.md#streams).

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/application-core-integration.md`, if it exists. A failure
in your files on the latest combined commits is your next piece of work, and a conflict in a file you own is a
coordination task: record it under Progress, don't work around it.

## Goal

Make bounded Strings, and one family of immutable lists, real proof values across the whole boundary. Don't build a
general JDK emulator or add a solver.

## Starting evidence

Recounted in the main brief's [Where it starts from](application-core.md#where-it-starts-from). In short:
- the native engine's Strings are opaque objects; concatenation can make an opaque value, but has no symbolic
  content semantics;
- `lib/models/` has `List.of`/`copyOf` and immutable-list bytecode models, marked JBMC-only.

Audit which parts native can execute faithfully before writing replacements. Support in the concrete interpreter
doesn't by itself establish symbolic support.

## Your items

In order, with acceptance rows V1 and V2 of the [contract](application-core-acceptance.md#mandatory-rows).

### V1. Bounded strings (required)

- Represent a String's contents as bounded UTF-16 code units with an explicit logical length.
  - No Rust UTF-8 indexing, and no silent restriction of inputs to ASCII or to well-formed Unicode.
  - Cover null separately, as well as empty content, an embedded NUL, surrogate pairs and isolated surrogates.
  - Keep value equality apart from Java reference identity.
- Start with construction from the supported character representation, plus `length`, `isEmpty`, `charAt`, `equals`
  and `startsWith`.
  - Implement only the narrow compiler-generated concatenation that String and literal payloads need.
  - General object-to-string conversion and numeric formatting are outside the core.
  - Include the relevant exceptional outcomes.
- Expose a value adapter used by object construction, by result and field observation, by effect snapshots and by
  JVM replay. A String parameter the engine can inspect but the witness can't rebuild is not complete support.
- Bounds are explicit. An input String's length is an input-domain bound. An output or intermediate content cap
  reached during execution is a named unresolved limit, never a silently truncated string or a dropped input.

### V2. One bounded immutable-list family (required)

- Reuse the existing model assets for a narrowly listed `List.of`/`List.copyOf` family where that is feasible.
  - Lists of constructor-made application elements first.
  - String elements once V1 is integrated.
  - Don't make the identity semantics of boxed primitives an unplanned dependency.
- The required operations are construction, `size`, `isEmpty`, `get`, and the small iterator path an enhanced `for`
  loop needs, if the chosen fixture uses one.
  - `copyOf` needs only the supported source family, not arbitrary `Collection` implementations.
  - An unsupported source implementation is refused explicitly.
- Keep each of these: order, duplicate elements, element alias relationships, null rejection, mutation refusal, and
  the supported exceptional outcomes.
  - A list is not a set, and its elements are not deeply immutable.
  - Don't claim a fresh list identity from a factory that may reuse an instance. Either model the relevant identity
    behaviour of the pinned JDK, bound to that JDK, or name the identity-sensitive cases as unsupported.
- Bounded list inputs and fields come in through the shared construction adapter, not only as a list a test makes
  internally from constants. Native execution, observation and replay all use the same modelled domain.
- Out: general `List` implementations, mutation, `Map`, `Set` and streams.

### V3. Semantic evidence and end-to-end model registration (required)

- For every modelled operation, record:
  - the source and JDK identity;
  - the inputs it admits and the exceptions it was seen to throw;
  - the behaviour it leaves out;
  - its evidence level: implemented, modelled, tested, trusted or proved.
- Run small JVM conformance cases at the boundaries. Sampled conformance is never labelled a universal proof.
- Add strict gap detection for operations outside the model. Existing workloads without strings keep their results.
- Wire the model and value-domain identity into canonical claims, through reuse's registered projection and Phase
  0's schemas.

Required negative controls:
- a dropped prefix character;
- a supplementary character mishandled as one code unit;
- equal content behind distinct references;
- a reordered or duplicated list element;
- alias-sensitive behaviour of a mutable element.

### Optional, after the core

One String method (`substring`, say) or one list method, needed directly by a small fixture it would unblock.

Out of scope: regex, locale and case conversion, `Charset` encoders, a `StringBuilder` platform, hashing
collections, general streams, floating point, and solver migration.

## Ownership and cooperation

- **Yours**: `lib/src/bmc/`, the semantics of `lib/src/interp/` and `lib/models/`, the new value adapters, and their
  model conformance tests.
- **Others**:
  - objects owns the harness and the integration of object replay. Provide it the functions to build a leaf, take a
    snapshot and replay.
  - environment uses your snapshots, and must not add a second String encoding.
  - reuse uses your model digests and value bounds.
- Keep generic engine edits to registered dispatch, storage and merge hooks. Avoid a big rewrite of the value
  representation that would make every other stream wait.
- Example numbers 250–259.

## Acceptance

- A bounded String goes into an ordinary object's field, changes execution, appears in a result or effect
  snapshot, and replays on a JVM.
- A bounded supported list goes into a check, is traversed, and keeps its sequence and identity observations.
- Correct refactors prove, planted defects refute with replay, and unsupported operations stay named.
- Changing a String or list bound, a model's semantics or a snapshot rule invalidates the cached evidence it
  affects.
- A tiny sweep over the bound finds any immediate encoding cliff. It is not a new benchmarking campaign.

## Working rules

The main brief's [How to work through it](application-core.md#how-to-work-through-it): the pipeline and the two-failure
timebox. Small semantic tests on a real `java` may run inline, but symbolic proofs are jobs. Never widen a model
just to bring a gap count down.

## Progress

- Forked 2026-11-08 after the main brief's [launch prerequisites](application-core.md#launch-prerequisites), Phase 0
  included. No integration report yet at the first cycle.
- 2026-11-08, **the audit** ("which parts native can execute faithfully"), against the code at the fork:
  - **The own checker** (`bmc/`): as the main brief's table says. A String is an opaque object: each literal one
    interned object with no content, a concatenation a fresh opaque one, and `length`, `charAt`, `equals` and the
    like the gap `jdk-primitive-method` (no assume form). A String parameter is refused (`bmc::unsupported_parameter`).
  - **The interpreter** (`interp/`), the replay reference, was **lossy**: a String was Rust UTF-8 text, so every
    isolated surrogate became U+FFFD (`"\uD800".equals("\uFFFD")` and `"\uD800".equals("\uDC00")` were both true,
    `charAt` gave 65533, a surrogate pair split by `substring` became two U+FFFD). `new String(char[])` was refused.
    `StringBuilder.append(CharSequence, int, int)` appended the whole sequence, `setLength(-1)` clamped to 0 instead
    of throwing, and `reverse` broke surrogate pairs. `strip` and `isBlank` used Rust's whitespace, not
    `Character.isWhitespace`'s.
- 2026-11-08, **V1 step 1, the interpreter's Strings are UTF-16 code units** (this commit): `interp::JStr` holds a
  String's and a `StringBuilder`'s code units, and every modelled operation works on them as the JDK's do; an
  operation that needs Unicode's tables (case, `equalsIgnoreCase`, number syntax) is refused on a String with an
  isolated surrogate, and `Integer.parseInt` on any non-ASCII code unit, instead of answering for other text.
  Exception messages that quote a String keep its units (`Machine::throw_units`), and `Objects.requireNonNull`'s
  message is the very String given (`throw_with`). The reproducer is `tests/values.rs`, the stream's model
  conformance test: 67 cases run on the JVM and in the interpreter must give the same code units, or a listed
  refusal. Before the fix 28 differed and one was refused.
- **Found, not fixed** (outside V1's core, for the for-review list):
  - `Character`'s classification natives use Rust's Unicode tables, not Java's: `isDigit` is `char::is_numeric`,
    `isWhitespace` and `isSpaceChar` are both Rust's whitespace, and `digit` only knows ASCII, so
    `Character.digit('\u0667', 16)` gives -1 where the JVM gives 7 (example 109's `toDigit`). These are wrong
    answers, not refusals. A fix would refuse non-ASCII input in the interpreter, or model the tables.
  - `render::primitive` writes a surrogate `char` as U+FFFD (`render::char_to_string`), so two different `char`
    results render alike in a contract.
- **Interface request, for the merge** (not additive, so it waits): the class reader decodes a `CONSTANT_Utf8`
  lossily (`classfile::decode_modified_utf8` ends in `String::from_utf16_lossy`, and `Constant::Utf8` holds a Rust
  `String`), so a string literal with an isolated surrogate in its source is read as U+FFFD by the interpreter and
  every engine alike. Keeping the code units of a literal (`ConstantPool::utf16(index)`, say) would close it.
- 2026-11-08, **the integration check** (05:36, the four streams' first commits) stopped at the merge: a 4-sided
  conflict in `lib/README.md`, where every stream added its paragraph at the same place, after the application-core
  paragraph of the foundations IR section, and in the generated `llm-dlc/README.md`, `index.json` and `traces/`
  files. The README's additions are all additive and resolve as their union. To keep this stream out of it, this
  commit moves its paragraph to the end of "The tool's own checker" (before "Library use"). The generated files
  are `sync.py`'s, for the merge.
- 2026-11-08, **V1 step 2, the own checker's bounded Strings** (this commit), in `bmc/`:
  - **The representation**: a String is an `Obj` of class `java/lang/String` whose `array` is its content, `char`
    cells of a symbolic length (`Obj::content`, kept apart from an array by `Obj::as_array`), so that merging,
    aliasing and witnesses reuse the arrays' machinery. Any of the 65,536 code units is a content. A literal has
    its units (one interned object per literal). Identity is the object, apart from content.
  - **The methods**, modelled on content (`Engine::string_method`, `bmc::models_string_method`, which the gap scan
    shares): `length`, `isEmpty`, `charAt` (`StringIndexOutOfBoundsException` out of range), `equals` (the same
    object, null, another class, then the lengths and every unit) and `startsWith` (`NullPointerException` on
    null). On a String with no content they stay the JDK gap they were.
  - **The concatenation** (`Engine::concatenation`): Strings, `null` as "null", `char`s and the recipe's constants
    give the content of the parts in order. A number or a boolean converted gives a String with no content
    (numeric formatting is outside the core), and one that could pass `bmc::MAX_STRING_CONTENT` (64) units has
    none either, with a named limit: asking for its content ends the path with no verdict, never a truncated
    String.
  - **A String parameter** is taken only under an explicit bound, `bmc::Parameters::max_string_length` (`None`,
    the default, refuses it by name, so no check borrows a bound it didn't state). It has every content up to the
    bound, is nullable or one String with another under the same `nullable` and `may_alias` as an array, and its
    witness is its code units in `raw_arrays` (decimal). A bound makes `Parameters::is_default` false, so
    `property` refuses JBMC for such a domain, as it does for a widened array domain.
  - **Reproducer and checks**: before, every String parameter was refused (`bmc::unsupported_parameter`: "a
    java.lang.String parameter"), and `length`, `charAt` and the like were the gap `jdk-primitive-method`. Now
    `tests/values.rs` runs the checker on harness-shaped methods (`tests/fixtures/values/values/Checks.java`),
    merging from the start and never, and replays every violation's witness on the JVM and in the interpreter,
    each of which must throw the check's `AssertionError`:
    - the quote fixture's `Codes.vip` rewrite proved up to 5 units, and its dropped-prefix defect refuted with
      "VI" and a third unit that isn't 'P' (negative control: a dropped prefix character);
    - an isolated high surrogate and "A\0" found as inputs; a pair is two units, and a defect taking it for one
      (`charAt(0) == 0x1F600`) refuted with the pair (negative control: a supplementary character as one unit);
    - `equals` agreeing with a unit-by-unit comparison; equal content behind two references refuting a claim that
      they are one object, with and without `may_alias` (negative control: equal content behind distinct
      references); one object equal to itself; null and another class unequal; a literal interned with its
      content;
    - `charAt`'s bounds, `startsWith(null)`, `isEmpty`, a nullable String refuted by null and its `length` a
      `NullPointerException`;
    - the bound: `length() <= 4` proved under 4 and refuted with 5 units under 5; no bound, no check;
    - concatenations proved by content, a wrong commutation claim refuted, `null` as "null", nine copies proved
      under 7 (63 units) and a named limit under 8 (72), and a number concatenated still the gap;
    - the gap scan counts the modelled methods as no gap, and `toUpperCase` still as one.

    Evidence level: `tested` (sampled JVM conformance of the methods, and replays), not `proved`. No job: these
    checks are seconds, run inline as unit tests.
  - **Not yet**: no proof entry point takes a String parameter. `equivalence` and `property` refuse it through
    `values::adapter`, which is next.
- 2026-11-08, **V1 step 3, the String value adapter** (this commit), `values::StringAdapter` in `lib/src/values.rs`:
  - **Its domain** is the shared `spec::plans::ValueDomain`: kind `string`, the bound, whether null is a value,
    and the model's evidence (`values::string_model`): its identity (`values::STRING_MODEL`, to be bumped whenever
    the semantics change, for V3's claim key), the JDK sampled (25.0.5), the level `tested`, and what it leaves
    out (every other method a named gap, numeric formatting, the content cap, `hashCode` and `intern`).
  - **Its functions**, for the checks that take a String: `bound` (the checker's
    `bmc::Parameters::max_string_length`), `read` (a String argument out of the checker's witness, `raw_arrays` and
    `raw_same`: its units, null, or the same object as an earlier argument), and `encode` and `rebuild` between
    the interpreter's `JStr` and a witness's units (a snapshot of a result, field or payload; a replay). A String
    outside the domain (longer than the bound, null where it isn't nullable, not code units) is refused by each,
    never cut or widened.
  - **Checks**: four unit tests (the domain round-trips as the shared type; units, null, an earlier argument, a
    String too long and a malformed unit read; rebuilt Strings with surrogates, NUL and the empty one encode as the
    same units). `tests/values.rs` now reads every refutation's witness through `read` and rebuilds each String in
    the interpreter's replay through `rebuild`, checked to encode back as its witness. The whole lib suite passes,
    the contract included (one timing test of `bmc::bits`, untouched, failed once under load and passed alone and
    on the rerun).
  - **Not registered yet**: `values::adapter`, which the regression and property checks ask about a String
    parameter, still refuses it, now saying that the adapter is built and what the check lacks. Returning it
    would make `equivalence::adapted_refusal` say "a value adapter is built for it, but this check doesn't take
    one yet", and the contract's V1 row (`v1_a_symbolic_string_crosses_the_proof_boundary`, which accepts only
    the values stream's refusal) would fail on a wiring that is in other streams' files.
- **Interface request, to the objects stream** (its files: `harness/`, `equivalence.rs`, `property.rs`,
  `jbmc.rs`'s `arguments`, the replay), for V1's row: for a String parameter of a regression or property check,
  1. take it in the layout and declare it in the harness as the String it is (`harness/mod.rs` makes a
     non-primitive parameter `Object` today);
  2. give the own checker its bound with `StringAdapter::bound` (equivalence passes `bmc::Parameters::default()`
     today), and its nullability and aliasing as an array's;
  3. read the witness's String with `StringAdapter::read` (`jbmc::JbmcResult::arguments` reads a String slot as a
     scalar today), and rebuild it for the replay with `ValueAdapter::rebuild`;
  4. state the bound in the statement (`statement::Bounds::max_value_length`) and the model's evidence
     (`Models::values`, `values::string_model`).

  When that lands, `values::adapter` returns the adapter (one line here), and the contract's V1 row reaches its
  verdicts (`Codes#vip`: the rewrite verified, `short-prefix` refuted). The environment stream's String payload
  snapshot (`effects.rs`, a literal only today) can use `encode`. Until then V1's row waits on that wiring.
- 2026-11-08, **V2's audit**, against the code at `nlkuyptr`:
  - **The models** (`lib/models/java/util/List.java`, `ImmutableCollections.java`) are the JDK's lists step for step,
    written without a JDK call: `List12` for one or two elements (the second the sentinel `EMPTY` for one), `ListN`
    over an array of its own otherwise, one `EMPTY_LIST`, `NullPointerException` on a null element, every change
    `UnsupportedOperationException`, `get` out of range `IndexOutOfBoundsException` from a `List12` and
    `ArrayIndexOutOfBoundsException` from a `ListN`, `ListItr` (`NoSuchElementException` past the end), `copyOf` of
    one of them the list itself and of any other `Collection` its `isEmpty` and `toArray`. Marked JBMC only, they
    are on JBMC's class path and nowhere else; the interpreter keeps natives that do the same
    (`interp::ImmutableList`, the corpus's `the_models_only_jbmc_runs_agree_with_the_jvm`).
  - **The own checker** ran none of it: `List.of` was the gap `jdk-static-method`, so no check reached a list. Its
    bytecode is inside the checker's fragment once four things are admitted: a static call of a model only for
    JBMC (`ClassPath::checker_runs`), `ImmutableCollections`' initializer and statics, `AbstractCollection()`'s
    empty constructor, and the gap scan's dispatch of an interface call to the models.
  - **The L fixture** (`basket`) takes a `List<Line>` parameter of at most 3 constructor-made lines, any two of
    which may be one object. Its regression checks (`Basket#total`, `#clearAll`) stop today at `values::adapter`,
    and its three claims at the planned domain (`Part::Objects`). A list parameter needs the harness to make it, as
    for a String: objects' files.
  - **Found, not fixed**: the interpreter names every immutable list `ImmutableCollections$ListN`
    (`interp::value::Native::class_name`), a `List12` included, so its `getClass()` differs from the JVM's for a list
    of one or two (its `get` and searches do throw as a `List12`'s).
- 2026-11-08, **V2 step 1, the own checker runs the immutable-list models** (this commit):
  - **What changed**: `models::CHECKER_RUNS` adds `List`, `ImmutableCollections` and its four list classes. The
    checker calls a static method of one of them as an application method (its class initialized first), holds
    `ImmutableCollections`' statics and runs its initializer (`ClassPath::checker_class`, `checker_statics`), and
    reproduces `AbstractCollection()` exactly (`gaps::exact_jdk_call`). The gap scan walks the same methods and
    counts an interface call on a list or its iterator as no gap where the models implement it
    (`gaps::dispatched_to_models`): every other `java.util` collection or iterator the checker could hold is made by
    a JDK constructor or method, a gap where it is made. `copyOf` of an `ArrayList` still meets its JDK calls.
  - **Reproducer and checks**: `tests/values.rs` runs the checker on harness-shaped methods
    (`tests/fixtures/values/values/Lists.java`) that make their lists as a harness would, by `List.of` over 0 to 3
    constructor-made lines, any two of which may be one object, each version in a world of its own; every
    refutation is replayed on the JVM and in the interpreter, which must throw the check's `AssertionError`.
    Before, all of them met `List.of` as the gap `jdk-static-method`. Now, merging from the start and never:
    - the basket's three rewrites by index (`total`, `first`, `clearAll`) proved;
    - its four defects refuted: a duplicate skipped (a line given twice in a row), the last line for the first (a
      reordering), a copy for the element (identity), every line read before any is cleared (an alias between
      elements), and a wrong claim that two elements are two lines (negative controls: a duplicated or reordered
      element, alias-sensitive behaviour of a mutable element);
    - `size`, `isEmpty` and the iterator in order then `NoSuchElementException`; `get` out of range by the JDK's
      classes, and a claim that both kinds throw one class refuted with a list of one or two; a null element
      refused; `add` and `set` refused; `copyOf` of such a list the list itself, and one empty list;
    - `copyOf` of an `ArrayList` refused by name (`jdk-constructor`); the gap scan finds no gap over the models.

    Evidence level: `tested` (the models' bytecode is the JDK's lists as written by hand; sampled JVM replays and
    the corpus's conformance), not `proved`. No job: seconds, inline.
  - **The conformance corpus** (`tests/conformance.rs`): 12 of its list claims had no verdict on the own checker
    (recorded `U`) and are now decided, each as the JVM decides it (`listSizes`, `listNull`, `listChange`,
    `listCopySame`, `listGet` proved and refuted; the refutations of `listCopyMutable` and `listOfArray`). The rest
    still reach another JDK call (an `ArrayList`, a boxed `Integer`'s methods) and stay `U`. The records are updated,
    and `lib/benchmark/conformance.json` re-blessed from them (12 `nativeStrict` values). One assertion is narrowed:
    it took any claim strict decides while advised stops on a gap as the scan seeing a gap no input reaches, but
    `listCopyMutable`'s refutation is a violation on a path with no gap (`copyOf(null)`), which strict's rule lets
    stand while other paths meet the `ArrayList`'s gaps; it now fails only on a strict *proof* advised stops on.
  - **The interpreter**, found by the corpus: an immutable list's or set's iterator refused `remove` instead of
    throwing `UnsupportedOperationException` as the JDK's does, so `listChange`'s refutation (`n=17`) didn't
    replay. `Native::Iterator` now knows its collection is immutable.
  - **Job** `20261108-070211-application-core-values-v2-step-1-the-co`: the corpus's two JBMC tests (`--engine
    jbmc`/`auto`, and `auto --confirm`, which now asks JBMC to confirm the checker's list proofs), expected to pass.
    Nothing below waits on it.
  - **Not yet**: a list *parameter*. As for a String, a check takes one only once the harness makes it.
- 2026-11-08, **V2 step 2, the list value adapter** (this commit), `values::ListAdapter` in `lib/src/values.rs`:
  - **Its domain** is the shared `ValueDomain` of kind `list`: the element class (an `ElementKind::Object`), the
    bound (at most `values::MAX_LIST_LENGTH`, 10: `List.of`'s fixed forms, its array form left out), whether null
    is a value, and the model's evidence (`values::list_model`): its identity (`values::LIST_MODEL`, with the
    SHA-256 of the list models' bytecode, `values::list_model_digest`, so that a change in a model changes it), the
    JDK (25.0.5), the level `tested`, and what it leaves out (other implementations, the array form, lists of
    Strings, the models' untested methods, the interpreter's `getClass` of a `List12`).
  - **How a harness makes one** (`choices`, `admitted`, `java`): the shape `Lists.list` had, generalized. The
    harness makes `max_length` objects by the plan; the checker is free in int choices: null (where nullable), the
    length, and for each element `i` after the first which made object (`0` to `i`) it is, so that every pattern of
    duplicates and aliases is a choice; the list is `List.of` over the first `length` elements. Each version makes
    its own list from the same choices. Since the checker runs the models (step 1), a list needs no symbolic form of
    its own.
  - **Its functions**: `read` (the witness's list from the choices' values and the made objects' node ids:
    `WitnessValue::List` of nodes in order, or null), and `encode` and `rebuild` between the interpreter's list and
    the witness's, through the plan's objects (`values::Nodes`, a node id to a run's object; `ValueAdapter`'s two
    methods now take it, and a String ignores it). `rebuild` uses the interpreter's own `List.of`, so a rebuilt
    list is the one empty list or of the JDK's class for its length. A list outside the family (an `ArrayList`),
    longer than the bound, holding an object the plan didn't make, or with a choice outside the admitted ones is
    refused by each, never cut or copied in. A list of Strings is refused by name.
  - **Reproducer and checks**: before, nothing could read a list out of a witness or rebuild one, and
    `values::adapter` refused every list as unbuilt. Five unit tests (the domain and its digest; the harness's Java
    exactly; reading duplicates, a pick past the length, every out-of-domain choice; rebuilding as `List12`, `ListN`
    and the one empty list, each encoding back as its nodes; each refusal). `tests/values.rs`'s new
    `the_list_adapter_makes_reads_and_rebuilds_lists_that_keep_order_duplicates_and_identity` generates a
    harness-shaped class from the adapter's own Java over the basket's kernels, compiles it and runs the checker on
    it, merging from the start and never: `total`, `first` (identity: the plan node returned), `clearAll` (with
    every line's quantity after) and a nullable `total` proved; a duplicate skipped, the last line for the first, a
    copy for the element, and an alias between mutable elements refuted (the negative controls), and a nullable
    domain's null found. Each witness is read by `read` and replayed on the JVM (the harness's `AssertionError`) and
    in the interpreter, each version's kernel called on its own on the list `rebuild` makes over that version's
    lines, which must observe the difference, and each rebuilt list encodes back as the witness's. Sabotaging the
    picks (no element ever another's object) fails the test: the duplicate defect then proves. The whole lib suite
    passes.

    Evidence level: `tested`. No job: seconds, inline.
  - **Not registered yet**: `values::adapter` still refuses a list parameter, now saying that `values::ListAdapter`
    is built and what a check lacks, for the same reason as a String (the contract's V2 row accepts only the values
    stream's refusal, and the wiring is in other streams' files).
- **Interface request, to the objects stream** (its files: `harness/`, `equivalence.rs`, `spec/heap.rs`'s planned
  domain, the replay), for V2's row: for a list parameter of a regression check, or a planned domain's `adapted`
  list root (the basket's three claims),
  1. make the adapter for the parameter's domain (`ListAdapter::new`, the element class, the bound: the claim's
     `max_length`, 3 for the basket), declare its choices (`ListAdapter::choices`) as int inputs, and return before
     the check where `ListAdapter::admitted` is false;
  2. make `max_length` element objects per version by the plan (constructor-made, as a node), then the list by
     `ListAdapter::java` over them, in each version's world;
  3. read the witness's list with `ListAdapter::read` (the choices' values, the made objects' nodes), and rebuild it
     for the replay with `ValueAdapter::rebuild`, over the replay's objects for those nodes (`values::Nodes`);
     encode a result or field list for a snapshot with `ValueAdapter::encode`;
  4. state the bound and the model's evidence in the statement (`Bounds::max_value_length`, `Models::values`).

  When that lands, `values::adapter` returns the adapter, and the contract's V2 row reaches its verdicts.
- **For the merge** (shared types, not additive):
  - a list of Strings needs a bound for its elements' code units, which the shared `ElementKind::String` has no
    place for (`ElementKind::String { max_length }`, say);
  - the frozen basket claims' model evidence (`golden/basket-*-claim.json`: level `modelled`, leaving out "the
    identity of an empty list") differs from the adapter's (`tested`, and the one empty list is modelled, as
    `List.of()` gives it). The claims are frozen, so a gate that compares them with the adapter's domain should
    take the adapter's evidence as the record, or the claims' as the weaker statement; for the main loop to settle.
- 2026-11-08, **V3 step 1, the evidence records** (this commit), `values::OPERATIONS` in `lib/src/values.rs`:
  - **The records**: one `values::OperationEvidence` per modelled operation, 14 in all. For Strings: the literal,
    the compiler's concatenation, `length`, `isEmpty`, `charAt`, `equals` and `startsWith`. For lists: `List.of`'s
    fixed forms, `copyOf`, `size`, `isEmpty`, `get`, the iterator's path, and the changes the lists refuse (`add`,
    `set`, `remove(int)`, `clear`, `Iterator.remove`). Each has its family (`string_model` or `list_model`, whose
    identity a claim key will carry), what implements it in the own checker, the interpreter and for JBMC, the JDK
    (25.0.5), the inputs it admits, the exceptions it was seen to throw, what it leaves out, its level (`tested`), and
    the boundary cases that sample it.
  - **The boundary cases**: `tests/fixtures/values/values/Operations.java`, 86 cases covering:
    - empty, one, the most and past the end (`get` on lists of 1, 2, 3 and 10);
    - null where an operation takes it, and isolated surrogates, a pair and NUL as content;
    - duplicates and aliases as elements, the one empty list, and fresh lists otherwise.

    Strings are made at run time, never as literals with isolated surrogates, which the class reader decodes lossily.
  - **The check**: `tests/values.rs`'s `every_modelled_operation_has_a_record_…` runs every case on the JVM and in the
    interpreter, and in the own checker through a generated method per case that asserts the JVM's outcome. A String
    is checked by its code units, an exception by its exact class (an `IndexOutOfBoundsException` is told from its
    subclasses). Each generated method must be proved. The test also fails unless:
    - the exceptions a record's cases throw on the JVM are exactly the ones the record lists;
    - each case belongs to exactly one record;
    - every String method of the JDK's class that `bmc::models_string_method` accepts has a record;
    - each record's JDK is the one the cases run on.

    There was nothing to reproduce: before, the evidence was one record per model (`string_model`, `list_model`),
    which said nothing of an operation's inputs or exceptions. All three engines agreed on every case, the first run
    included. Each sabotage below fails the test:
    - dropping `StringIndexOutOfBoundsException` from `charAt`'s record;
    - expecting another int or boolean from 42 cases;
    - expecting `ArrayIndexOutOfBoundsException` from a `List12`'s `get` (the checker's
      `IndexOutOfBoundsException` then leaves the generated check).

    No job: seconds, inline. The whole lib suite passes.
- 2026-11-08, **V3 step 2, strict gap detection** (this commit):
  - **The audit**: a String method other than the five was already the JDK call it is, a named gap (`toUpperCase`,
    `indexOf`, `hashCode`, `substring`, `compareTo`, `equals` through `Object`, `length` through `CharSequence`,
    `String.valueOf`). A list method was not. Since V2 step 1 the checker ran every method the list models
    implement, so claims over `equals`, `hashCode`, `toArray`, `addAll`, `remove(Object)`, `sort` and `List.of(E...)`
    were proved on bytecode no record samples. `contains`, `indexOf` and `lastIndexOf` stopped at an element's
    `equals` inside the models, not at the call. The gap scan also walked the models' `equals` and `hashCode` for any
    `Object.equals` or `hashCode` call.
  - **The change**: each record names its calls (`OperationEvidence::calls`). A call from outside the list models
    into them that no list record names (`values::samples_list_call`) is the JDK call it names, for the engine and
    the scan alike (`gaps::outside_the_list_records`, `models::of_the_list_family`): a gap of its kind, or a refusal
    for `toArray`'s array result. The models' calls among themselves are unchanged. `values::LIST_MODEL` is bumped to
    2, since the checker's list semantics changed. The docs move with it: the engine's table, the scan's module docs,
    `lib/models/README.md`, and a `lib/README.md` paragraph.
  - **Reproducer and checks**: `tests/values.rs`'s `an_operation_outside_the_values_models_is_a_named_gap_under_strict`
    runs 20 checks (`tests/fixtures/values/values/Outside.java`), each reaching one such operation. Every claim holds
    on the JVM. Under strict, merging from the start and never, each must end with no verdict, naming its gap (its id
    up to the JDK), and the scan must report the same gap and walk none of the models' unsampled methods. Before the
    fix, 37 of its 60 checks failed. A unit test holds each record's calls to the models (each implemented with code)
    and to the String methods the checker models. Two sabotages fail the test: dropping the rule from the engine's
    dispatch (20 operations), and from the scan's walk of overrides (11).
  - **Workloads without Strings keep their results**: the whole lib suite passes unchanged, apart from four list
    claims of the conformance corpus. Those reach the array form `List.of(E...)` on the paths in question, and go back
    to `U`, the verdict they had before this stream: `listNull`'s proof, both of `listCopySame`'s, and
    `listOfArray`'s refutation. `lib/benchmark/conformance.json` is re-blessed (4 `nativeStrict` values). One
    assertion is narrowed to a single named claim and its exact gaps (`ADVISED_ON_EXCLUDED_PATHS`): strict still
    proves `listChange` under `n == 0 || n == 8`, pruning the paths to `remove(Object)` and `addAll`, while `--gaps
    advised`, deciding from the static scan, stops on those two gaps. The scan's documented imprecision, not a wrong
    verdict. The benchmark's 27 Python tests pass.

    Evidence level: unchanged (`tested`). No job: seconds, inline. The corpus's JBMC tests (`auto` now falls back to
    JBMC on those four claims, as before V2 step 1) are covered by the next job that runs them. Job
    `20261108-070211-…` is of V2 step 1's revision.
  - **Found, for the for-review list**: the array form is sampled by the corpus on the JVM (`listOfArray`, and
    `the_models_only_jbmc_runs_agree_with_the_jvm`), but by no record. If a fixture needs it, a record with boundary
    cases in `Operations.java` would bring those four claims back. That is the optional "one list method", and no
    fixture needs it now.
- 2026-11-08, **VF-023, V2 step 1's job failed** (`20261108-070211-…`, at `1fd39455`; triaged by the verification
  loop in `verification/findings.md`). This is the first failure on V2's confirmation, so one timebox attempt is
  left.
  - **What failed**: step 1 (the corpus under `jbmc` and `auto`) passed. Step 2 (`auto --confirm`) failed with 8
    disagreements, all from two claims under strict and assume: `listSizes [n >= 1 && n <= 3; result == n * 10]` and
    `listChange [n == 0 || n == 8; result == 1]`. The own checker proves both, and JBMC 6.11.0 refutes them with
    `listSizes(n=1)` and `listChange(n=0)`, which the interpreter, the JVM and the models run on a JVM all hold. So
    JBMC is wrong, not the checker.
  - **What it narrows to**: JBMC is also `Unverifiable` on both under `--engine jbmc`, before and after this stream,
    a refutation the JVM doesn't reproduce. Both witnesses are a one-element `List.of`, whose `List12` keeps the static
    sentinel `ImmutableCollections.EMPTY` as its second element, with `size()` being `e1 != EMPTY ? 2 : 1`. JBMC gets
    every list claim right that doesn't ask a one-element list's size: a two-element `List12`'s size (`listNull`), a
    one-element one's `get(0)` (`listGet`), and `EMPTY_LIST`'s identity (`listCopySame`). `listIterate`, whose
    iterator asks for the size, is `Unverifiable` under JBMC too. So JBMC sees `e1 != EMPTY` where the JVM doesn't. My
    guess is that the constructor's read of `EMPTY` comes before `ImmutableCollections`' initializer, but that is
    a guess.
  - **The diagnosis, a job** (`20261108-082244-vf-023-s-diagnosis-why-jbmc-refutes-that`, this commit): the triage
    script `verification/triage/vf023.sh` runs three probes under JBMC alone and keeps their traces' assignments to
    `EMPTY`, `e1` and the initialization flags:
    - `one`, the case reduced;
    - `oneAfterInit`, with `List.of()` first, so that the class is initialized before the constructor runs;
    - `two`, the control.

    On the JVM they give 1, 1 and 2 (checked inline). Nothing is changed before its result: the attempt left goes to
    a fix the trace supports. That might be a sentinel the model needn't read from a static (`List12` rejects a null
    element, so a null `e1` can mean one element), with `values::LIST_MODEL` and its digest bumped, or a reason
    recorded for leaving it.
- 2026-11-08, **VF-023's diagnosis came back** (job `20261108-082244-…`, passed at `8ddb0f74`): it **refutes my guess**.
  JBMC proves all three probes: `List.of(new Object()).size() == 1`, the same after `List.of()`, and two elements' size
  2 (each in 0.1 s, 2 properties). A one-element `List12` alone is no problem for JBMC, so the class's initialization
  order isn't the cause, and nothing in the models is changed on it. What the corpus's two claims have and the probes
  don't is a choice between lists of different classes: `listSizes` picks `List.of()`, a one-, two- or three-element
  list by `n` and then calls `size()` and `isEmpty()` on the merged reference; `listChange` picks a `List12` or (for
  `n >= 10`, excluded by the assumption but in the program) a `ListN`. So the next probe is that choice: the
  corpus's methods as they are under their assumptions, then `n == 1 ? List.of(a) : List.of(a, b)` and
  `n == 1 ? List.of(a) : List.of(a, b, c)`, each with JBMC's failed property and trace kept. No timebox attempt is
  spent: nothing was fixed.
- 2026-11-08, **the tiny bound sweep** (this commit), `tests/values.rs`'s `a_tiny_sweep_over_the_string_and_list_bounds`:
  the own checker on one correct check and one planted defect per family, at a few bounds, under both search orders,
  timed. Times are printed (`--nocapture`), never asserted; the verdicts are.
  - **Strings: no cliff up to the content cap.** `vipRewritten` proved, `vipShortened` refuted (from 2 units: "VI"),
    and `equalsByUnits` proved at bounds 1, 2, 4, 8, 16, 32 and 64. Every check takes 0.07 s or less (release),
    `equalsByUnits` growing from 0.00 s to 0.07 s. One thing the sweep shows: a check that loops over a String's units
    itself needs an unwinding bound past the String's. Under the default `--unwind 16`, `equalsByUnits` at 32 is the
    named limit "a loop was not fully unwound with --unwind 16", no verdict. That is right (two bounds, each
    explicit), and the sweep asserts it.
  - **Lists: a cliff at 6 to 7 elements**, inside the adapter's bound (`values::MAX_LIST_LENGTH`, 10). Merging from the
    start (release): 90 paths for 4 lines (0.1 s), 345 for 5 (0.2 s), 1,833 for 6 (4 s; 40 s in the dev profile), and 7
    doesn't finish (`total7` gave up at 138 s, under a 20 s limit). Never merging, 5 lines take 13 s. The solver
    isn't the cost (0.1 s of solving at 6 and at 7); the paths are. The adapter's picks give `n!` alias patterns
    (`ListAdapter::choices`: element `i` any of the `i + 1` objects made so far), and each pick is a chain of
    conditionals, which the checker forks on. The suite sweeps 1 to 5 lines (8 s for the whole file, dev profile).
    Lists of 6, 7, 8 and 10 lines are the reproducer `the_list_sweep_past_five_lines`, `#[ignore]`d because it fails
    today. The fix would be an encoding that doesn't fork, such as `made[pick]` over an array of the made objects (a
    symbolic index is a formula, not a branch), perhaps with picks kept to the first unused object (Bell numbers of
    patterns, not `n!`). Or the bound comes down to what the checker decides. The basket's bound is 3, so no frozen
    claim is near it.
  - **Found, for the for-review list**: the checker's time limit overshoots. `total7`'s 20 s limit ended at 138.68 s
    ("the engine did not finish within the time limit"), since the deadline is read every 256 steps
    (`bmc/mod.rs`), and a step over a large merged state can take long.
  - No job: the sweep is seconds inline (release: under 2 s for the Strings, about 3 s for lists of up to 5 lines).
- 2026-11-08, **VF-023's second probe, a job** (`20261108-091002-vf-023-s-second-probe-which-ingredient-o`, this
  commit): `verification/triage/vf023-choice.sh` runs nine property proofs under JBMC alone, one ingredient of the two
  claims at a time. The first two are the corpus's own `listSizes` and `listChange` under their assumptions, which must
  reproduce the refutation. The others are:
  - a choice between two `List12`s (`oneOrTwo`), a `List12` or a `ListN` (`oneOrThree`), and `EMPTY_LIST` or a
    `List12` (`emptyOrOne`);
  - a one-element list under `listSizes`' assumption (`oneAssumed`), and after three objects are made (`oneMadeFirst`);
  - `listChange`'s choice without its switch (`changeNoSwitch`), and its switch over one list without the choice
    (`oneThenSwitch`).

  For each refutation it keeps JBMC's failed property and trace steps. On the JVM every claim holds, and the own
  checker proves all nine (both checked inline). Nothing is changed before its result, and the timebox attempt left
  goes to a fix the trace supports.
- **Next**: VF-023's second probe's result, when it comes. Meanwhile the list encoding past five lines, with
  `the_list_sweep_past_five_lines` as its reproducer, or the bound brought down to what is decided. Then the cache
  invalidation of the models' and domains' identities (R1's projection, with the reuse stream), and V3's wiring of
  model identity into claims.
- Status: working

## Loop settings

- session: b8c9cad1-a1e9-4dff-af3c-fd39c8035d6f
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: application-core-values
- fork: 3da21514-fe46-49d5-8200-08d3cf89ea17

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when V1–V3 and your share of the combined String and list acceptance pass,
or each is deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or
another stream, and is recorded under Progress. Defer further library families: a complete model is not this loop's
goal. Anything new you find goes under Progress, for the main brief's for-review list.
