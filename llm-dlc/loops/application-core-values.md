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
- **Next**: V1 step 2, the own checker's bounded Strings. A String is an object with a code-unit array of
  symbolic length up to a bound. A literal has its content. `length`, `isEmpty`, `charAt`, `equals` and
  `startsWith` are modelled with their exceptions. A String parameter of the harness has every content up to the
  bound, and its witness holds its code units. Then `values::adapter` for a String, for the objects stream to take.
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
