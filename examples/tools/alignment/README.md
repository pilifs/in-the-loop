# The ground truth for alignment inference

The mappings people wrote by hand for the regression examples 121–139, broken into parts, each saying what fixes it.
This is step A1 of [`llm-dlc/loops/foundations-alignment.md`](../../../llm-dlc/loops/foundations-alignment.md): every
later step of alignment inference (`jvmcontract align`) is scored against it. The table is
[`ground-truth.json`](ground-truth.json); [`../alignment.py`](../alignment.py) checks it and writes the table below.

```
python3 examples/tools/alignment.py check               # the table agrees with every example.json's flags
python3 examples/tools/alignment.py check --signatures  # and with the compiled classes (javac and javap, ~20 s)
python3 examples/tools/alignment.py render              # rewrite the table below from ground-truth.json
```

## What is in it

Every B9 example from 121 to 139: the nine with a hand-written mapping (`previousSymbol`, `previousArguments` or
`resultsAgreeWhen` in their `example.json`, the tool's `--before-target`, `--before-arguments` and
`--results-agree-when`), and the ten whose method kept its signature, where the right mapping is the tool's default
and inference must not propose another. No other recorded example has a hand-written mapping (checked on 2026-11-07
with a search of every `example.json`).

Each entry has the example's expected verdict, both versions' signatures as compiled (`check --signatures` compares
them with `javap`), the scope (`intendedInputs`, `--unchanged-unless`) where the example declares one, and its parts:

| Part | One for | Says |
|---|---|---|
| `method` | a method renamed or moved | the old and the new symbol, and `how`: `renamed` or `moved` |
| `input` | each old input, the receiver `this` first for an instance method, in the order `--before-arguments` takes them | the expression over the new inputs that gives it, and its `anchor`; a record built from the new inputs lists its `components` |
| `new-input` | a new input with no old counterpart | that the mapping leaves it free |
| `result` | the result | its `relation` to the old one, and `holds`, the `--results-agree-when` expression, where it isn't equality |

The parts amount exactly to the example's flags, with the tool's defaults left out (the same symbol, the arguments by
position, the results equal): `check` rebuilds the flags from the parts and compares.

**Anchors** of an input:
- `anchored`: the same parameter in both versions, by name and type (its position may move). Its mapping is fixed to
  itself; inference proposes no arithmetic or other change of it. This is where the offset defect of the
  [main brief](../../../llm-dlc/loops/foundations.md#direction) (`before.c = after.c + 1`) must be impossible.
- `internal`: a representation that changed, such as a parameter gathered into a record's component, or a record
  that gained a component. Inference may propose how the two relate.
- `new` (a `new-input` part): no old counterpart. The mapping leaves it free, so the claim covers every value the
  constructor admits; restricting it is the scope, a person's decision.

**Relations** of the result:
- `equal`: compared by equality (component by component for a record), as the contract requires.
- `components`: a record result that gained a component, each old component compared with the same-named new one. No
  old observation is dropped; the new component is one the old version doesn't have.
- `changed`: what the result means changed (a `boolean` became a `long`). How they relate is a person's decision: a
  catalogue relation can be proposed and proved, but a proof shows only that it holds, not that it is the one meant.

**Decided by**: `infer` where inference should reach the part by itself, `person` where only a person can. A scope is
always a person's: it declares which inputs the change is meant to affect, and is counted as a decision, not scored as
a mapping.

## How inference is scored against it

Each part of each example gets one score, from what `jvmcontract align` proposes on the example's two builds:

| Score | For a part decided by `infer` | For a part decided by `person` |
|---|---|---|
| **found** | the one candidate left after collapsing equivalent ones is the table's, proposed and not approved by the tool; for an unchanged signature, the identity or no hint at all | (not possible: the tool doesn't decide these) |
| **asked** | a question listing candidates, the table's among them | a question, or a proposal reported as unconfirmed, the table's among the candidates |
| **wrong** | one candidate, not the table's; or a question without the table's | a single candidate given as decided, or a question without the table's |
| **missed** | no proposal for the part, or the step doesn't support it | the same |

**Wrong and accepted** is counted on its own, apart from wrong: a wrong candidate whose evidence is *proved*. It is the
worst outcome, a mapping that a proof makes look right; on an anchored part or on the defective examples (122, 124,
126, 128, 130, 132, 134, 136 and 139 refute) it is the regression the mapping hid. A run's score is the count of each,
by part kind and anchor, with every wrong-and-accepted part listed by name.

## Scores

Each step's last recorded score (`alignment.py score --record`), with the tool binary it ran. Step A2 scores method
correspondence alone: an example's method part where it has one (renamed or moved), and otherwise the method that
kept its name, which must be proposed alone (or get no hint, its own code unchanged). *Leads* is a candidate alone,
or ahead of the next by `LEAD` points ([`lib/src/alignment.rs`](../../../lib/src/alignment.rs)); without a lead it
counts as asked. What else in the module changed is listed, unscored: the table has no part for it.
Step A3 scores the input, new-input and result parts, on the mapping `align` proposes for the table's pair (for a
method that none leads to, each candidate's mapping; the table's is scored). Its record also says, per example,
whether the flags the proposal amounts to are the example's own hand-written ones. That static score proves nothing,
so none of its parts can be wrong and accepted.
Step A3's second half (`score --step proofs`, a verification job: it runs proofs) scores one row per example, on what
`align --prove` settles for the table's pair, under the example's scope and proof options. A verified example is
found when the mapping proved (alone after collapsing, or with the table's among those collapsed) is the table's,
asked when the table's is among a question's proved ones, and missed when none proved. A violation is found when no
mapping proved, its counterexamples shown. Any other proved mapping is wrong and accepted: on a violation, the
regression a mapping hid.

<!-- scores:begin (generated by examples/tools/alignment.py render) -->

**A2-methods** (2026-11-07, `jvmcontract` sha256:1c5254da7b2a…; [A2-methods.json](scores/A2-methods.json)). Wrong and accepted: none.

| Part | found | asked | wrong | missed |
|---|---|---|---|---|
| method kept its name | 15 | 0 | 0 | 0 |
| method moved | 2 | 0 | 0 | 0 |
| method renamed | 1 | 1 | 0 | 0 |

| Example | Part | Table | Score | Proposed | Elsewhere in the module |
|---|---|---|---|---|---|
| 121 | method kept its name | `LastWriterWins#winner` | found | leads: `LastWriterWins#winner` (8) | 0 changed |
| 122 | method renamed | `Expiry#remainingMillis` | asked | none leads: `Expiry#remainingMillis` (2) | 0 changed |
| 123 | method renamed | `Expiry#remainingNanos` | found | leads: `Expiry#remainingNanos` (4) | 0 changed |
| 124 | method kept its name | `Partitioner#partitionFor` | found | leads: `Partitioner#partitionFor` (10) | 0 changed |
| 125 | method kept its name | `JwtTimestamps#valid` | found | leads: `JwtTimestamps#valid` (10) | 0 changed |
| 126 | method kept its name | `Backoff#delayMillis` | found | leads: `Backoff#delayMillis` (10) | 0 changed |
| 127 | method kept its name | `Backoff#delayMillis` | found | leads: `Backoff#delayMillis` (10) | 0 changed |
| 128 | method moved | `Batch#offsetToCommit` | found | leads: `Batch#offsetToCommit` (7) | 0 changed; vanished: `BatchCommit#<init>` → none leads |
| 129 | method moved | `Batch#offsetToCommit` | found | leads: `Batch#offsetToCommit` (9) | 0 changed; vanished: `BatchCommit#<init>` → none leads |
| 130 | method kept its name | `Backoff#delayMillis` | found | leads: `Backoff#delayMillis` (10) | 3 changed; vanished: `Backoff#<init>` → `Backoff#<init>` |
| 131 | method kept its name | `Backoff#delayMillis` | found | leads: `Backoff#delayMillis` (10) | 3 changed; vanished: `Backoff#<init>` → `Backoff#<init>` |
| 132 | method kept its name | `TokenBucket#tokensAfter` | found | leads: `TokenBucket#tokensAfter` (10) | 0 changed |
| 133 | method kept its name | `TokenBucket#tokensAfter` | found | leads: `TokenBucket#tokensAfter` (10) | 0 changed |
| 134 | method kept its name | `Window#counted` | found | leads: `Window#counted` (10) | 3 changed; vanished: `Window#<init>` → `Window#<init>` |
| 135 | method kept its name | `Window#counted` | found | leads: `Window#counted` (10) | 3 changed; vanished: `Window#<init>` → `Window#<init>` |
| 136 | method kept its name | `Window#counted` | found | leads: `Window#counted` (10) | 0 changed |
| 137 | method kept its name | `Window#counted` | found | leads: `Window#counted` (10) | 0 changed |
| 138 | method kept its name | `Window#counted` | found | leads: `Window#counted` (10) | 0 changed |
| 139 | method kept its name | `Window#counted` | found | leads: `Window#counted` (10) | 0 changed |

**A3-mappings** (2026-11-07, `jvmcontract` sha256:1c5254da7b2a…; [A3-mappings.json](scores/A3-mappings.json)). Wrong and accepted: none.

| Part | found | asked | wrong | missed |
|---|---|---|---|---|
| input anchored | 50 | 0 | 0 | 0 |
| input internal | 8 | 0 | 0 | 0 |
| new input | 4 | 0 | 0 | 0 |
| result changed | 0 | 2 | 0 | 0 |
| result components | 2 | 0 | 0 | 0 |
| result equal | 15 | 0 | 0 | 0 |

The example's hand-written flags are what the mapping amounts to in 17 of 19 examples, one of a question's alternatives in 2, and neither in 0.

Every part that isn't found:

| Example | Part | Table | Score | Proposed |
|---|---|---|---|---|
| 122 | result changed | `previous == (result <= 0)` | asked | changed, a question: previous == (result <= 0) \| previous == (result < 0) \| previous == (result == 0) \| previous == (result != 0) \| previous == (result > 0) \| previous == (result >= 0) |
| 123 | result changed | `previous == (result <= 0)` | asked | changed, a question: previous == (result <= 0) \| previous == (result < 0) \| previous == (result == 0) \| previous == (result != 0) \| previous == (result > 0) \| previous == (result >= 0) |

<!-- scores:end -->

## The table

<!-- table:begin (generated by examples/tools/alignment.py render) -->

19 examples, 85 parts: 50 input anchored (infer), 8 input internal (infer), 2 method moved (infer), 2 method renamed (infer), 4 new-input new (infer), 2 result changed (person), 2 result components (infer), 15 result equal (infer).

| Example | Verdict | Part | Old | New | Anchor or relation | Decided by | Why |
|---|---|---|---|---|---|---|---|
| [121](../../121-tie-break-parameters-grouped-by-kind-proved-under-the-reordering/README.md) | verified | input | `tsA` | `tsA` | anchored | infer | the same name and type in both versions; its position moved, the parameters now grouped by kind |
|  |  | input | `nodeA` | `nodeA` | anchored | infer | the same name and type in both versions; its position moved, the parameters now grouped by kind |
|  |  | input | `tsB` | `tsB` | anchored | infer | the same name and type in both versions; its position moved, the parameters now grouped by kind |
|  |  | input | `nodeB` | `nodeB` | anchored | infer | the same name and type in both versions; its position moved, the parameters now grouped by kind |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| [122](../../122-cache-expiry-in-milliseconds-left-expires-entries-in-their-last-millisecond/README.md) | violation | method | `Expiry#isExpired` | `Expiry#remainingMillis` | renamed | infer | renamed, the same parameters, its result changed from boolean to long; the old method is gone |
|  |  | input | `writtenAtNanos` | `writtenAtNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `ttlNanos` | `ttlNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `previous == (result <= 0)` | changed | person | boolean became long (milliseconds left): what the result means changed, so how the two relate is a person's decision; the catalogue's 'a boolean against a comparison of the new result' can propose it, and a proof shows only that it holds |
| | | scope | | `!(writtenAtNanos >= 0 && nowNanos >= writtenAtNanos && ttlNanos > 0)` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [123](../../123-cache-expiry-as-the-time-left-proved-expired-exactly-when-none-is-left/README.md) | verified | method | `Expiry#isExpired` | `Expiry#remainingNanos` | renamed | infer | renamed, the same parameters, its result changed from boolean to long; the old method is gone |
|  |  | input | `writtenAtNanos` | `writtenAtNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `ttlNanos` | `ttlNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `previous == (result <= 0)` | changed | person | boolean became long (nanoseconds left): what the result means changed, so how the two relate is a person's decision; the catalogue's 'a boolean against a comparison of the new result' can propose it, and a proof shows only that it holds |
| | | scope | | `!(writtenAtNanos >= 0 && nowNanos >= writtenAtNanos && ttlNanos > 0)` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [124](../../124-partitioner-rewritten-with-floormod-moves-every-negative-key/README.md) | violation | input | `hash` | `hash` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `numPartitions` | `numPartitions` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| [125](../../125-jwt-skew-moved-to-the-clock-proved-equal-by-the-tools-own-checker/README.md) | verified | input | `nowSeconds` | `nowSeconds` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `notBefore` | `notBefore` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `expiresAt` | `expiresAt` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `skewSeconds` | `skewSeconds` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| | | scope | | `!(skewSeconds >= 0 && skewSeconds <= 86400 && nowSeconds >= 0 && nowSeconds <= 1099511627776L && notBefore >= 0 && notBefore <= 1099511627776L && expiresAt >= 0 && expiresAt <= 1099511627776L)` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [126](../../126-backoff-loop-replaced-by-a-shift-overflows-on-the-records-components/README.md) | violation | input | `this` | `this` | anchored | infer | the receiver: the same record class with the same components |
|  |  | input | `attempt` | `attempt` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| [127](../../127-backoff-loop-replaced-by-a-guarded-shift-proved-equal-on-the-records-components/README.md) | verified | input | `this` | `this` | anchored | infer | the receiver: the same record class with the same components |
|  |  | input | `attempt` | `attempt` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| [128](../../128-batch-commit-made-a-records-method-loses-the-failed-index-check/README.md) | violation | method | `BatchCommit#offsetToCommit` | `Batch#offsetToCommit` | moved | infer | moved from a static helper class to an instance method of the new record Batch, the same name; the old class is gone |
|  |  | input | `batchStart` | `this.start` | internal | infer | a parameter gathered into the new receiver: its component start, the same type, named as the parameter without the class's name |
|  |  | input | `batchSize` | `this.size` | internal | infer | a parameter gathered into the new receiver: its component size, the same type, named as the parameter without the class's name |
|  |  | input | `failedIndex` | `failedIndex` | anchored | infer | the same parameter in both versions, name and type; its position moved, the other two having gone into the receiver |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| [129](../../129-batch-commit-made-a-records-method-proved-equal-on-the-batchs-components/README.md) | verified | method | `BatchCommit#offsetToCommit` | `Batch#offsetToCommit` | moved | infer | moved from a static helper class to an instance method of the new record Batch, the same name; the old class is gone |
|  |  | input | `batchStart` | `this.start` | internal | infer | a parameter gathered into the new receiver: its component start, the same type, named as the parameter without the class's name |
|  |  | input | `batchSize` | `this.size` | internal | infer | a parameter gathered into the new receiver: its component size, the same type, named as the parameter without the class's name |
|  |  | input | `failedIndex` | `failedIndex` | anchored | infer | the same parameter in both versions, name and type; its position moved, the other two having gone into the receiver |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| [130](../../130-backoff-with-a-multiplier-counts-a-negative-attempt-down-to-the-cap/README.md) | violation | input | `this` | `new Backoff(this.baseMillis, this.capMillis)` | internal | infer | the record gained a component: the old record is made from the new one's components of the same name and type |
|  |  | input | `attempt` | `attempt` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | new-input |  | `this.multiplier` | new | infer | no old counterpart: left free, so the claim covers every multiplier the constructor admits; that the change is meant for multipliers other than two is the scope, a person's decision |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| | | scope | | `this.multiplier != 2` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [131](../../131-backoff-with-a-multiplier-proved-equal-to-the-doubling-record-for-a-multiplier-of-two/README.md) | verified | input | `this` | `new Backoff(this.baseMillis, this.capMillis)` | internal | infer | the record gained a component: the old record is made from the new one's components of the same name and type |
|  |  | input | `attempt` | `attempt` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | new-input |  | `this.multiplier` | new | infer | no old counterpart: left free, so the claim covers every multiplier the constructor admits; that the change is meant for multipliers other than two is the scope, a person's decision |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| | | scope | | `this.multiplier != 2` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [132](../../132-a-refill-that-counts-periods-from-the-epoch-credits-a-token-for-a-nanosecond/README.md) | violation | input | `tokens` | `tokens` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `lastNanos` | `lastNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `periodNanos` | `periodNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `capacity` | `capacity` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| | | scope | | `!(periodNanos > 0 && lastNanos >= 0 && nowNanos >= lastNanos && nowNanos <= 4611686018427387903L && capacity > 0 && capacity <= 1000000000L && tokens >= 0 && tokens <= capacity)` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [133](../../133-a-refill-capped-by-the-room-left-proved-equal-within-the-modules-precondition/README.md) | verified | input | `tokens` | `tokens` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `lastNanos` | `lastNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `periodNanos` | `periodNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `capacity` | `capacity` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same return type: compared by equality, as the contract requires |
| | | scope | | `!(periodNanos > 0 && lastNanos >= 0 && nowNanos >= lastNanos && nowNanos <= 4611686018427387903L && capacity > 0 && capacity <= 1000000000L && tokens >= 0 && tokens <= capacity)` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [134](../../134-a-window-counter-that-advances-by-one-window-leaves-its-start-behind-a-quiet-client/README.md) | violation | input | `this` | `new Window(this.startNanos, this.count)` | internal | infer | the record gained a component: the old record is made from the new one's components of the same name and type |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `windowNanos` | `windowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | new-input |  | `this.previousCount` | new | infer | no old counterpart: left free, so the claim covers every previous count the constructor admits |
|  |  | result | `result` | `previous.startNanos == result.startNanos && previous.count == result.count` | components | infer | the record result gained a component: each old component is compared with the same-named new one, so no old observation is dropped; the new previousCount is one the old version doesn't have |
| | | scope | | `windowNanos > 0 && this.startNanos % windowNanos != 0` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |
| [135](../../135-a-window-counter-with-the-previous-count-proved-equal-on-the-start-and-the-count/README.md) | verified | input | `this` | `new Window(this.startNanos, this.count)` | internal | infer | the record gained a component: the old record is made from the new one's components of the same name and type |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `windowNanos` | `windowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | new-input |  | `this.previousCount` | new | infer | no old counterpart: left free, so the claim covers every previous count the constructor admits |
|  |  | result | `result` | `previous.startNanos == result.startNanos && previous.count == result.count` | components | infer | the record result gained a component: each old component is compared with the same-named new one, so no old observation is dropped; the new previousCount is one the old version doesn't have |
| [136](../../136-a-window-start-aligned-by-masking-opens-a-window-per-request-unless-the-window-is-a-power-of-two/README.md) | violation | input | `this` | `this` | anchored | infer | the receiver: the same record class with the same components |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `windowNanos` | `windowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same record type: compared component by component, as the contract requires |
| [137](../../137-a-window-start-aligned-by-a-mask-on-power-of-two-windows-and-by-the-remainder-elsewhere-proved-equal/README.md) | verified | input | `this` | `this` | anchored | infer | the receiver: the same record class with the same components |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `windowNanos` | `windowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same record type: compared component by component, as the contract requires |
| [138](../../138-a-window-start-computed-as-the-window-s-index-times-its-length-proved-equal-to-the-remainder-form/README.md) | verified | input | `this` | `this` | anchored | infer | the receiver: the same record class with the same components |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `windowNanos` | `windowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same record type: compared component by component, as the contract requires |
| [139](../../139-a-window-index-held-in-an-int-refuses-every-request-after-two-billion-windows/README.md) | violation | input | `this` | `this` | anchored | infer | the receiver: the same record class with the same components |
|  |  | input | `nowNanos` | `nowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | input | `windowNanos` | `windowNanos` | anchored | infer | the same parameter in both versions, name, type and position |
|  |  | result | `result` | `result` | equal | infer | the same record type: compared component by component, as the contract requires |

<!-- table:end -->
