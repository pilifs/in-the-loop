# Stream brief: foundations, mapping and alignment inference

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-summaries.md`](foundations-summaries.md) and [`foundations-observations.md`](foundations-observations.md).
Once all are finished, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-alignment` from this stream's workspace
(`jj workspace root --name alignment`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its three
inputs too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file says which
part of its plan is yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section;
edit implementation files according to the ownership rules below.

**Every cycle, read the integration check** first: `$(jj workspace root --name default)/llm-dlc/loop-summaries/foundations-integration.md`,
if it exists. A failure in your part of the [integration contract](foundations.md#phase-0-the-shared-ir-and-the-integration-contract)
on the latest combined commits is your next piece of work.

## Your phases

Priority 4: the tool proposes the internal relation, and the developer steps in only where meaning changes. All of
it works under the comparison's [preservation contract](foundations.md#direction), which inference may never weaken:
it relates internal representations, and leaves the external inputs' meaning, the required observations and the
accepted behaviour as they are. In order:

- **A1. The ground truth.** From examples 121–139 (and any other recorded example with `--before-target`,
  `--before-arguments` or `--results-agree-when`), a table of the hand-written mappings: method correspondence,
  argument expressions, record component maps, result relations. For each, which parts are anchored by something
  external (an unchanged parameter, a field reached from a route) and which are internal. Every later phase is scored
  against it: found, asked about, wrong, missed. A wrong mapping that a proof accepts is the worst outcome and is
  counted on its own.
- **A2. Method correspondence.** `jvmcontract align --before DIR --after DIR`: for each changed or vanished method of
  the old build, candidate new methods (same name and descriptor; renamed or moved with the same body shape; a
  changed signature with a similar body and the same callers), ranked, each with its evidence. Written to Phase 0's
  hints file as proposed, evidence unchecked. Static, no proofs.
- **A3. Argument, record and result mappings, under the contract.** For a corresponding pair with different
  signatures:
  - **What may be inferred.** An anchored input keeps its meaning: for a parameter that both versions take from the
    same external value, the mapping is fixed to that value, and no arithmetic or other transformation of it is
    proposed. Inference proposes only how *internal* representations relate (a parameter split into a record's
    components, a reordering, a widening of a parameter the contract doesn't fix) and result relations only for
    results that aren't required observations. A required observation is compared as the contract says, never under
    an inferred relation. The `price` case of the main brief (`before.c = after.c + 1`) must never be proposed for an
    anchored input; it's a planted defect in your examples, and the test is that no candidate hides it.
  - **Candidates**, from type, name and data flow into the same uses, and a small catalogue of result relations
    (equal; equal after a widening or a known conversion; a boolean against a comparison of the new result), each
    checked by the existing regression proof.
  - **Collapse before asking.** Candidates equivalent under the contract (they give every external input the same
    old-side value; checked by a proof, or by syntax where trivially the same) are one candidate.
  - **The outcome.** One candidate proved and not vacuous: evidence "proved for claim key K", intent still proposed.
    Several after collapsing: ask, listing them and what tells them apart. None: report the mappings tried and their
    counterexamples, so the developer sees whether the change is a bug or the mapping is missing.
  - **No anchor.** For a standalone method with nothing external fixing its inputs, a proved mapping is reported as
    "this relation is proved; whether it is the intended one is unconfirmed", not as an approved refactor.
  - **Accounting.** Every observation the old version is held to stays in the result's count: preserved, changed with
    approval, or unresolved. A mapping can't remove one.

  The hand-written mappings of A1 are the test: run `align` on each example's builds and score it.
- **A4. Field correspondence candidates.** For classes that changed shape between builds (fields renamed, split,
  merged, wrapped in a value object), candidate field-path equations in Phase 0's correspondence format, from names,
  types and how constructors in each version route their parameters into fields. They relate internal state only,
  under the same rules as A3. Do first the case the joint example needs (its automatic-mapping row: a primitive
  amount becoming a value object), checked by the heap stream's H5 through the integration check; then widen.
- **A5. The question, well put.** Where a decision is the developer's, the output says exactly what to decide, with
  the candidates and what each would mean (a counterexample under each, say), and a one-line way to approve one in
  the hints file. Approving sets the intent state only; the evidence state still comes from a proof under the current
  claim key, and goes stale when either version changes. A run on a hints file whose entries are all approved and
  proved asks nothing.

**Your core:** A1–A3, and A4's narrow case for the joint example. The rest of A4, and A5, come after.

Not yours: object inputs and correspondence proofs (heap), the cache (summaries; its claim key covers the mapping, so
a proved mapping's evidence is reused there), entry-point matching (observations' O2 matches entry points; you match
methods), the preservation contract's external part (it comes from the observation spec or the signature, not from
you). Loop and control-flow alignment and LLM-proposed mappings are [deferred](foundations.md#deferred-not-in-this-loop).

## Boundaries

You own `lib/src/spec/align.rs`, your interface in the shared IR, which returns a named `Unsupported` until your
part is done; your checks in `lib/tests/foundations.rs` turn from unsupported to passed as you do it. You also own the new alignment module, the `align` command, the hints file's reading and writing, and the scoring tool for
A1, with their tests. You call into `equivalence.rs` to check candidates as a caller, not by changing how a check
runs. The refusal messages that suggest an expression today (`equivalence.rs:768-810`) may call your inference
instead of their own matching, as a hook.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.

## Working in a stream

- **Commit only here**, with `sync.py commit` as CLAUDE.md says. Never push, merge, rebase onto another branch, or
  move a bookmark. The branch is this workspace's `@-` line; the reconcile loop merges it.
- **Quick jobs are awaited briefly; long jobs never** (the main brief's [rule](foundations.md#how-to-work-through-it)).
  Heavy work is still never run inline: submit it with `verification/pipeline.py submit`, stating the verdict or
  figure it should give, commit it with the change, and list it under Progress with its id. A quick job (a few
  minutes or less) goes in with `--priority 10`, and you may await it within the cycle: work on, then poll
  `python3 "$(jj workspace root --name default)/verification/pipeline.py" status` about once a minute, for at most
  15 minutes after submitting; if it is back, use its `report` like an inline result and record it. Otherwise, and
  for every long job, go on: it is *for review* after the run, and you don't wait for, poll or read it again. A step
  is done when its code, its inline tests and its jobs are committed; a criterion only an unreturned job can show is
  met pending review.
- **The timebox** (the main brief's [rule](foundations.md#how-to-work-through-it)): an item that fails its verification
  twice in a row (two quick jobs that came back, or two inline attempts) is logged under Progress as *deferred by the
  timebox*, with both jobs or attempts, the finding, and what a further attempt would try and cost; then move on to
  work that doesn't depend on it. No third attempt: it has very likely been underestimated, and a person handles it
  separately, in another session. If it is part of your core, your status at the end is `blocked: ...` naming it.
- **Status.** The last line of `## Progress` is a status, kept current in every commit and read by `run-streams.sh`:
  `- Status: working` while there is work you can do, `- Status: done` when your phases are finished, or
  `- Status: blocked: ...` with what needs the user. Never `waiting on jobs`. `done` requires that your part of the
  integration contract passes on this branch and that every job you submitted is listed under Progress; it doesn't
  require any job's result.
- **Another session is not your concern**: the other streams work in their own directories and never touch this
  working copy.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `ae994066`,
  compacted), so you share its context with the other streams. What it settled is in the briefs; where your memory of
  it and a brief differ, the brief wins.

## Progress

- **A1 done** (2026-11-07): the ground truth, [`examples/tools/alignment/ground-truth.json`](../../examples/tools/alignment/ground-truth.json),
  with its page and scoring rules in [`examples/tools/alignment/README.md`](../../examples/tools/alignment/README.md)
  and its checker `examples/tools/alignment.py` (`check`, `check --signatures`, `render`; tests in
  `test_alignment.py`). All 19 B9 examples 121–139, 85 parts: 50 anchored inputs, 8 internal inputs, 4 methods
  (2 renamed, 2 moved), 4 new inputs left free, 15 results equal, 2 record results by component, 2 changed results
  that are a person's decision; 7 scopes counted as a person's decisions. The parts rebuild each example's flags
  exactly, and both versions' signatures were checked against the compiled classes (`check --signatures`: 0
  problems). No example outside 121–139 has a hand-written mapping. Scoring (found, asked, wrong, missed, and wrong
  and accepted on its own) is defined on the page; its code comes with A2's first output.
- **A2 done** (2026-11-07): `jvmcontract align --before DIR --after DIR [--hints FILE] [--json]`, in the new module
  `lib/src/alignment.rs`. Static. An old method the new build declares with the same class, name and descriptor
  corresponds to itself and nothing else (no hint if its code is unchanged). For a vanished one, the candidates are
  the new build's new methods of the same kind that something ties to it: the same name (in its class or moved), the
  same body shape, a similar body (≥ 50% of instruction kinds in common), a caller in common, or the same parameters
  in the same class. Each tie has a weight, and candidates are ranked by score. The first *leads* only with at least
  `LEAD` (3) points and 3 ahead of the next; otherwise it's a person's choice. `--hints` replaces the file's
  inferred, proposed method hints and keeps every stated or approved one; it adds no proposal for a subject a person
  has decided. Tests: 2 unit tests, 7 in `lib/tests/alignment.rs` (rename, move with callers, a tie that is a
  question, a lone weak candidate that is a question, overloads, the joint example's kernel, the command keeping an
  approved hint); 4 more in `examples/tools/test_alignment.py` for the scoring rules.
  - **Score** (`alignment.py score --record`, kept in `examples/tools/alignment/scores/A2-methods.json` and on the
    page): methods that kept their name 15 found of 15; moved 2 found of 2; renamed 1 found, 1 asked (122: the only
    tie is the same parameters, 2 points, so it's a question). Nothing wrong, nothing missed, nothing wrong and
    accepted (no proofs yet).
  - **Caveat:** the same-parameters tie was added after the first run missed 122, and the lead threshold after that
    found 122 on a weak tie. The table and the scorer come from this stream too, so this score shows consistency
    with the table, not generality. Elsewhere in each module (unscored) a vanished constructor is matched with its
    changed self (130, 131, 134, 135), and `BatchCommit#<init>` (128, 129) gets candidates but no lead.
  - On the joint example: `Pricing#total` and `#discount` correspond to themselves; `Quote#<init>(long, int)` leads
    to `Quote#<init>(Money, int)`; `Quote#cents()` leads to `Money#cents()` (the same name and body shape, in the
    value object). Relating the two receivers is A4's work.
  - `align::propose` still returns `Unsupported`: the integration contract's alignment checks want the field
    correspondence (A4's narrow case), and a proposal without it would fail them.
- Shared files changed: `examples/README.md` (one line in its tools list); `lib/src/lib.rs` (`pub mod alignment`);
  `lib/src/main.rs` (the `align` command); `lib/src/spec/mod.rs` (two optional fields on `Hint`: `rank` and `why`,
  serde-defaulted and skipped when empty, so the golden files are unchanged; a `Hint { .. }` literal in another
  stream's code would need them at the merge); `lib/README.md` (the command, and a sentence on the hints file);
  `lib/tests/alignment.rs` (new).
- For the reconcile loop: `sync.py check` in this workspace reports errors this stream can't fix, all "session …
  has no manifest", for other streams' commits that `check` sees in the shared repository: `xuxuymrrrqsq` and
  `spkzmqwzmuom` (summaries S1, S2a), `uyqkxslyysrm` (heap H1) and `lslmmpwrvxuz` (observations O1). None is on this
  branch. Their manifests are in their own workspaces; the errors should resolve at the merge. After A3's static
  half (2026-11-07) `check` lists 18: the same kind for more of the other streams' commits (`xstwptusvqsx`,
  `uvmurzwkyukn`, `wwxvkxkmywxp`, `tumpnkkqksyp`, `zmqrplsqzwmm`, among them), and five of the planning session's
  launch commits before the fork (`olwyzkwouyln`, `xrkxxnnuwwuq`, `nnqrnknuvslx`, `xpsxzuolnwop`, `kxnqrntnkztt`),
  which "point at log 1f2230c9f137 that the manifest does not list". Those are ancestors of every stream, their traces
  outside what a stream may edit; none of the 18 is this stream's commit.
- **A3, its static half, done** (2026-11-07): `align` now maps the arguments, records and result of every pair it
  matches (`lib/src/alignment/mappings.rs`), under the comparison's preservation contract (`--contract FILE`, or for
  a standalone method the one its two signatures imply, reported as standalone).
  - An anchored input (an external input with the identity derivation; standalone, a parameter both versions take
    by name and type, wherever it now stands) is mapped to itself and nothing else, and a stated derivation is used
    as stated. Candidates are only names, field paths, an integral cast and a record built with its canonical
    constructor, never arithmetic, so the offset mapping can't arise (a test plants it, with and without a contract).
  - Internal inputs get candidates from the new inputs no anchored one took (parameters, `p.c`, `this.f`), ranked by
    name (the same, or one inside the other), type and position; an old record whose components changed is built
    component by component. A lone match on type alone, or a tie, is a question. A new input nothing uses is left
    free. An old object that isn't a record and whose fields changed is left to A4, named as such.
  - The result, from the catalogue: equal; widened; wrapped in or unwrapped from a one-component record; a record
    compared on its old components; or a changed meaning (a boolean against `result OP 0`, six candidates), always a
    question. Every required observation is accounted for, with how it is compared; a changed result stays
    unresolved.
  - Collapse is syntactic only so far (the same expression up to spacing); collapse by proof is A3's second half.
  - Each proposal is written to the hints file as a correspondence (`Correspondence::from_flags`), inferred,
    proposed, unchecked, ranked when there are several, its `why` naming each input's anchor and basis, what is left
    free, "standalone", and the flags it amounts to. A default mapping (the same method, inputs by position, results
    equal) gets no hint. Tests: 8 more in `lib/tests/alignment.rs` (offset, stated derivation, reordering, gathered
    into a record, a record that gained a component, a tie on type alone, the result catalogue with its accounting,
    the kernel's `Quote` left to A4), and 4 in `test_alignment.py` for the part scoring.
  - **Score** (`alignment.py score --record`, `scores/A3-mappings.json`): inputs anchored 50 found of 50, internal 8
    of 8, new inputs left free 4 of 4, results equal 15 of 15, by components 2 of 2, changed 2 asked of 2 (122, 123:
    `previous == (result <= 0)` among six, a person's decision). Nothing wrong or missed. The flags each mapping
    amounts to are the example's own hand-written flags in 17 of 19, and one of a question's in the other 2.
  - **Caveat:** written with the table in view, by the stream that wrote the table, and right at its first run; it
    shows the rules reproduce the table, not that they generalize. Nothing is proved yet, so nothing can be wrong and
    accepted.
  - `align::propose` stays `Unsupported`, its message narrowed to A4: the kernel's `Pricing#total` takes a `Quote`
    whose fields changed, which only field correspondence relates.
- Shared files changed: `lib/src/main.rs` (`align --contract`, and the mappings in its output and hints);
  `lib/README.md` (the `align` paragraph and the module sentence); `lib/tests/alignment.rs` (the A3 tests, and each
  kernel test compiling into its own directory: three tests sharing one raced).
- **A4's narrow case done** (2026-11-07): field correspondence, in `lib/src/alignment/fields.rs`, and
  `align::propose` implemented. For a class both builds declare whose shape changed, each old field is given as a
  path into the new object, from the constructors:
  - Each version's constructor is read for the fields it sets straight from a parameter (`this.f = p`, once, `p`
    never reassigned). One that delegates with `this(...)` or calls a method of its own class routes nothing.
  - The old constructor is paired with the one A2 matched to it, and its parameters are mapped by A3's rules (name,
    type, position, record component, integral cast; never arithmetic). Composed: the old `cents` is set from the
    parameter `cents`, which is the new `amount.cents`, and the new constructor sets `amount` from `amount`, so
    `old.q.cents == new.q.amount.cents`.
  - An anchored object input stays fixed to itself; only its internal fields are related. A field set any other way,
    or whose counterpart is, is named unsupported, and nothing partial is proposed. Several candidates for a field
    are a question, as for an input. In the hints file the field equations replace the input's own equation; they
    have no flag form.
  - `align::propose` loads both builds, aligns them under the contract, and returns the hints. A subject whose
    mapping is incomplete gets `Unsupported`, naming the gaps.
  - **Integration contract on this branch:** `alignment propose after` and `alignment propose offset` pass (2 passed,
    22 unsupported, 0 failed). `after` gets the golden correspondence; `offset` gets the same equations and no shifted
    input (its `Quote` is `after`'s; the defect is in `Pricing#total`, for the heap stream's proof to find).
  - **Tests:** 3 replace the A3 test that left `Quote` to A4: the kernel (with the contract, standalone, and through
    `propose`); a renamed field, with a new field left free; and constructors that wrap the value in a new object or
    shift it (`this.cents = cents + 1`), never related. All 17 in `lib/tests/alignment.rs` pass, and the whole cargo
    suite.
  - **Score:** unchanged on 121–139, where no class changed shape behind a constructor. Re-recorded under the new
    tool's hash.
  - **The rest of A4, not yet done:**
    - fields a constructor computes (`this.amount = new Money(cents)`);
    - two different classes (`Quote#cents` moved to `Money#cents`, whose receivers differ);
    - nested shapes;
    - a result whose class changed shape (still `changed`, a person's decision);
    - a method whose code is unchanged but whose classes changed: `Pricing#withQuantity` is unchanged to A2, so it
      gets no mapping, while the heap part checks it under the same correspondence.
- Shared files changed: `lib/README.md` (the `align` paragraph and the module sentence); `lib/tests/alignment.rs`
  (the A4 tests).
- **A3's second half, code done** (2026-11-07), its score pending job `20261107-053806-alignment-a3-second-half-every-proposal`
  (quick, priority 10): `align --prove [--subject S] [--unchanged-unless E] [--engine …] [--gaps …] [--unwind N]`
  (`lib/src/alignment/proofs.rs`) runs `equivalence::run` as a caller on every complete mapping of a pair, with the
  flags it amounts to.
  - A vacuous proof counts as none (evidence unknown). A proposal with field equations isn't tried: they have no
    flag form, and their proof is the heap stream's.
  - **Collapse by proof:** proved mappings with the same result relation are one candidate. Each makes the old
    version's observations a function of the new one's on every input of the claim, so the two give the old version
    the same observations. That is observational equivalence, which is what the review's rationale asks for;
    "the same old-side value", as the brief has it, is stronger. The first by rank stands for them, the others are
    named in its `why` and left out of the hints.
  - **Outcomes:** one proved: evidence `proved` for its claim key, intent still proposed. For a standalone method the
    note says the relation is proved and whether it is the intended one is unconfirmed; for a changed result, that
    approving it is a person's decision. Several relations proved: a question. None: each mapping tried, with its
    counterexample or why it has no verdict. The hints carry each proposal's evidence (refuted ones with their
    witness).
  - **The claim key is provisional:** `whole-builds:sha256:` over the tool's binary, every class file of both
    builds, the pair, the flags and the settings, so any change to either build makes it stale. For the reconcile
    loop: replace it with `spec::cache::key` once the summaries stream's canonical key exists.
  - **Tests:** 5 more in `lib/tests/alignment.rs`, by the own checker on methods of one line each (22 pass, 3 s):
    - the offset defect is refuted, and no mapping hides it;
    - of a question on type alone, the proof keeps the one mapping that holds, and the rest are refuted;
    - a sum's two orders are both proved and collapse into one candidate;
    - a changed result with two relations proved is a question;
    - the outcome rules on made-up attempts: vacuous counts as none, and a changed result's proof is still a
      person's decision.

    4 more in `test_alignment.py` for the proof scoring (23 OK). The static scores are unchanged, re-recorded under
    the new tool's hash. The full cargo suite passes. The integration contract on this branch: 2 passed, 22
    unsupported, 0 failed.
  - **The job** runs `alignment.py score --step proofs --record` on 121–139, under each example's scope and proof
    options. It should give 10 verified examples found (the table's mapping proved; for 123 still a person's
    decision), 9 violations found (none proved, counterexamples shown), and nothing wrong and accepted.
- Shared files changed: `lib/src/main.rs` (`align --prove` and its proof options); `lib/README.md` (the `align`
  example and the module sentence); `lib/tests/alignment.rs` (the proof tests).
- **For review:** job `20261107-053806-alignment-a3-second-half-every-proposal` was still pending, with nothing
  running, 15 minutes after it was submitted (05:38 to 05:53; no runner was taking jobs). It now counts as a long
  job, not awaited again. A3's score under proof is met *pending review*: the job should find each verified
  example's hand-written mapping proved (123's relation still a person's decision), no mapping proved for any of the
  9 violations, and `wrongAndAccepted` empty in `scores/A3-proofs.json`. An example listed there is a mapping that
  hides a regression, and the first thing to look at.
- For the reconcile loop: after this commit `sync.py check` lists 24 errors, all of the kinds named above (other
  streams' commits without a manifest here, and the five launch commits before the fork). None is this stream's.
  (It was 27 by the end of that cycle, and is 30 before the next commit: the same kinds, as the other streams commit.)
- **A4: value objects a constructor makes, and a method moved into one, done** (2026-11-07), in
  `lib/src/alignment/fields.rs`:
  - **Constructed fields.** Constructor routing now follows a field set to a new object made from parameters passed
    straight (`this.amount = new Money(cents)`) into that class's own constructor, to three levels. So
    `old.q.cents == new.q.amount.cents` for that constructor, `new.q.amount.c.v` when `Money`'s constructor makes a
    `C` in turn, and the other way round `old.q.amount.cents == new.q.cents`. Anything computed is named and not
    related: `new Money(cents * 2)`, `cents + 1`, or a constant an old value object's constructor sets
    (`this.scale = 2`).
  - **A method moved into the value object** (`Quote#cents` to `Money#cents`, whose receivers differ). The old method
    must do nothing with its object but read fields (`aload; getfield`), and the class's correspondence must put
    every field it reads inside one field `g` of the new class (`amount`). Then a new input of `g`'s class stands for
    it: `old.this.cents == new.this.cents`. The fields it never reads (`quantity`) are named in the mapping and in
    the hint's `why`, and no equation relates them. A read of a field kept elsewhere is named, and nothing is
    proposed. `FieldCorrespondence` gains `within` and `unread`, serde-defaulted and skipped when empty.
  - **For the reconcile loop:** such a correspondence leaves old fields with no equation. The heap stream should read
    them as unconstrained (any value the old constructor accepts). That is sound only because the old method never
    reads them; the IR's doc for `Correspondence.inputs` ("how the old input is made from the new one's") doesn't
    say so yet.
  - **Tests:** 4 replace the A4 test that held a constructed value object never related, since that was the gap this
    step closes: wrapped, nested and unwrapped are related; shifted, computed in the argument list, and an old
    constant are not; the kernel's `Quote#cents` takes the `Money`; a moved method that reads a field the value
    object doesn't keep is not related. All 25 in `lib/tests/alignment.rs` pass, and the whole cargo suite. The
    integration contract on this branch: 2 passed, 22 unsupported, 0 failed.
  - **Score:** unchanged on 121–139, where no class changed shape behind a constructor. Re-recorded under the new
    tool's hash.
- Shared files changed: `lib/README.md` (the `align` comment); `lib/tests/alignment.rs` (the A4 tests).
- **A4: nested shapes, done** (2026-11-07), in `lib/src/alignment/fields.rs` and `mappings.rs`:
  - **A class counts as changed when anything it holds changed.** `same_shape` compared a class's own fields only, so
    a `Q` holding an `L` whose `cents` became `amount.cents` counted as unchanged. It is now deep: the members' types
    too, an array's element type, and a class met again on the way (`N next`) taken as the same where it is met. So
    such a `q` is no longer anchored by the signatures alone, and a result of such a class is no longer `equal`
    (it is `changed`, a person's decision, until the next item).
  - **The field is related through its class.** An old field set from a parameter whose own class changed shape is
    related by that class's correspondence, prefixed with where the new constructor stores the parameter:
    `old.q.line.cents == new.q.line.amount.cents`. The parameter is matched by class, the same name first. A
    candidate is as sure as the less sure of its two steps, so a question inside stays a question. The inner class's
    free fields are free at their paths (`line.tag`), and its constructors are named with the outer one's. An inner
    class that can't be related leaves the outer field unsupported, with the inner gap named.
  - **Not followed:** more than three levels, or a class holding its own class (`N next`). That needs a relation over
    a chain of objects, not field paths. It is named as such and nothing is proposed.
  - **Tests:** 1 more in `lib/tests/alignment.rs`: nested, with a free inner field; an inner shift that leaves the
    outer field unrelated; a chain of `N`, named and not followed. All 26 pass, and the whole cargo suite. The
    integration contract on this branch: 2 passed, 22 unsupported, 0 failed. Also fixed: an ambiguous rustdoc link in
    `alignment.rs`.
  - **Score:** unchanged on 121–139, whose records hold primitives only. Re-recorded under the new tool's hash.
- Shared files changed: `lib/README.md` (the `align` comment); `lib/tests/alignment.rs` (the nested test).
- **A4: a result whose class changed shape, done** (2026-11-07), in `lib/src/alignment/mappings.rs`:
  - **The relation.** A result of a class both builds declare, whose shape changed, is no longer `changed`: it is
    compared by the class's field correspondence, the one its inputs are related by, each old field at its path in
    the new object. A new result kind `fields`, with the relation `previous.cents == result.amount.cents &&
    previous.quantity == result.quantity`, which the hints file writes as `Correspondence.outputs` (one relation for
    the observation `result`: `old.result.cents == new.result.amount.cents && …`). Only paths and integral casts. Every
    old field is compared, so the accounting says the relation "compares every old value"; a new field no equation
    reaches is named as not compared. Several candidates for a field give one relation per combination, a question.
  - **Not related, a person's decision with the gap named** (`ResultMapping.gaps`, shown by `align`): a field the
    class's correspondence can't relate (a constructor that shifts it), and a field that is a reference (a
    `String`): comparing it across versions would compare object ids, which mean nothing across two runs; it needs
    field observations inside it.
  - **Not proved here:** `align --prove` doesn't try such a proposal (the regression check can't observe an object
    result; evidence unknown, the proof is the heap stream's).
  - **Tests:** 1 more in `lib/tests/alignment.rs`: the relation, its accounting, its hint's outputs, no proof
    attempted; a shifted field and a `String` field left a person's decision with the gap named. All 27 pass, and the
    unit, conformance, foundations and skill suites. In `tests/integration.rs` 63 passed and one failed:
    `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs`, where JBMC on `fixtures.Pricing#total` "did not finish
    within the time limit" after 615 s, with the other streams' loops running. It runs no alignment code, and it
    passed in the earlier cycles. A JBMC run isn't repeated inline. The integration contract on this branch: 2 passed,
    22 unsupported, 0 failed.
  - **Score:** unchanged on 121–139, whose results are primitives or records of primitives. Re-recorded under the new
    tool's hash.
- Shared files changed: `lib/README.md` (the `align` comment); `lib/tests/alignment.rs` (the result test).
- **A4: unchanged code over a class that changed shape, done** (2026-11-07), in `lib/src/alignment.rs`. With it A4
  is done: every item listed under its narrow case above is now covered.
  - **A2 no longer calls such a method unchanged.** An old method the new build declares with the same code and
    access flags is still unchanged only if every class it takes or returns (its receiver's, a parameter's, the
    result's) keeps its shape, as `same_shape` has it (deeply). Otherwise a new change kind, `reshaped`, matches it
    to itself, and A3 and A4 map it like a changed method. On the kernel: `Pricing#withQuantity` and `Quote#quantity`
    are reshaped, and `align` prints them as such.
  - **What they get.** `withQuantity(Quote q, int quantity)`, standalone: `q` internal, related field by field
    (`old.q.cents == new.q.amount.cents`, `old.q.quantity == new.q.quantity`), `quantity` anchored, and the result
    compared by `fields` (`previous.cents == result.amount.cents && previous.quantity == result.quantity`), one
    proposal. `Quote#quantity()`: `this` related the same way, the `int` result equal. The method changes `q` in
    place; here that is seen only through the result it hands back. Observing a parameter object's fields is the
    heap stream's (H3). A reshaped method over a class whose constructor shifts what it stores is named, and nothing
    is proposed.
  - **Tests:** 1 more in `lib/tests/alignment.rs` (the kernel's two reshaped methods, their mappings and hint, a
    method over unchanged classes still unchanged, and the shifted constructor). The A2 kernel test asserted that
    `withQuantity` is unchanged, which was the gap this step closes; it now asserts `reshaped`. All 28 pass. Also
    passing: the unit (185), foundations (3), skill (1) and conformance (9, 2 ignored) suites, and every test target
    compiles. `tests/integration.rs` wasn't rerun: it runs no alignment code, and its JBMC case ran out of time last
    cycle under load. The integration contract on this branch: 2 passed, 22 unsupported, 0 failed.
  - **Score:** unchanged on 121–139, where no unchanged method takes a class that changed shape. Re-recorded under the
    new tool's hash.
  - **For A5:** two cases where the output doesn't put the question well yet. Both are visible on the kernel compiled
    without `-parameters`, where every field is matched on type alone:
    - a field question with a single candidate still gives one proposal and one result relation;
    - a field reached only by a question's candidate is listed as free ("not compared: amount"), because `free` counts
      what the leading candidates reach.
- Shared files changed: `lib/README.md` (the `align` comment); `lib/tests/alignment.rs` (the reshaped test, and the
  A2 kernel test's `withQuantity` assertion).
- **A5, first step: the questions and their approval, done** (2026-11-07), in the new `lib/src/alignment/questions.rs`
  and in `mappings.rs`, `fields.rs` and `alignment.rs`:
  - **A hint that answers a person's decision says so.** `Hint` gains `ask` (`Ask { decide, means }`): what to decide,
    the same for every candidate of the subject, and what approving this candidate would settle, part by part (each
    undecided input as it would be made, each undecided field's equation, the result relation where it is part of the
    decision, and what it leaves free). Such a hint is ranked even when it is the only candidate (`rank: 1`).
  - **What is asked.** Before a proof: an input or field none of whose candidates leads (several, none ahead, or one
    on type alone), a result field likewise, a result whose meaning changed, and a vanished method no candidate leads
    to. After `--prove`: one proved settles it (unless the result's meaning changed: then whether it is the intended
    one); several relations proved ask which is intended; every candidate refuted asks whether the change is a
    regression or the intended mapping is one not tried. A standalone proved mapping is not asked: its note says the
    relation holds and whether it is the intended one is unconfirmed.
  - **The questions.** `align` ends with them, read from the hints file after the merge: each decision, every
    candidate with what it means, its evidence (the counterexample where a proof refuted it), and the one line that
    approves it, `jvmcontract approve --hints FILE --kind correspondence --subject 'shop.Pricing#total' --rank 1`. The
    new `approve` command sets the chosen proposal's intent to approved and nothing else, and drops the subject's other
    proposals of that kind; it refuses a decided subject, a missing one, and an unnamed choice among several. A subject
    with an approved or stated hint is not asked again, so a hints file whose decisions are all approved asks nothing.
  - **The two cases above, fixed.** A field question with one candidate is still one proposal, now asked as such. What
    only a question's candidate reaches is no longer free: `free` is what no candidate reaches, and a new `open` (on
    `Mapping` and `FieldCorrespondence`, serde-defaulted) is what only some candidates reach, so each proposal, and
    each result candidate, names what it leaves uncompared (`FieldCorrespondence::free_under`, `Mapping::free_under`).
    On the kernel without names, `amount` is no longer called "not compared".
  - **Tests:** 3 more in `lib/tests/alignment.rs` (the lone candidate on the kernel without names, asked and nothing
    called free, and the kernel with names asking nothing; `approve` through the command, intent only, then reruns
    asking 2, then nothing; `approve`'s refusals), and questions asserted in 4 existing tests (a method tie, two
    inputs tied on type with what each candidate leaves free, a proof settling a question, two relations proved with
    a counterexample under each refuted candidate). All 31 pass, and the unit (185), foundations (3), skill (1) and conformance (9, 2 ignored)
    suites; every test target compiles; the Python tests pass. The integration contract on this branch: 2 passed, 22
    unsupported, 0 failed.
  - **Score:** unchanged on 121–139 (122 and 123 asked). Re-recorded under the new tool's hash.
  - **Not done yet, A5's second step:**
    - an approved hint's evidence on a rerun: `merge_hints` keeps it as it is, so evidence proved under an older claim
      key stays "proved". It should turn `stale` when the key no longer matches, and an `--prove` run should give it
      the evidence of its proof under the current key;
    - "asks nothing" for approved *and proved*: today an approved subject is not asked whatever its evidence; one whose
      evidence isn't proved under the current key should be listed as approved and unproved (not asked);
    - what tells two proved relations apart is said in words only, with no input that separates them.
  - On the kernel without names, `Quote#cents -> Money#cents` has no mapping: the field it reads is itself a lone
    question in `Quote`'s correspondence, so it is decided through that question, not asked on its own.
- Shared files changed: `lib/src/spec/mod.rs` (`Hint.ask` and the `Ask` type, serde-defaulted and skipped when empty,
  so the golden files are unchanged; a `Hint { .. }` literal in another stream's code would need `ask: None` at the
  merge; `rank`'s doc now also covers a question's lone candidate); `lib/src/main.rs` (the `approve` command, and the
  questions at the end of `align`); `lib/README.md` (the `approve` example and a sentence on the hints file);
  `lib/tests/alignment.rs` (the A5 tests).
- **A5, second step, its first two items done** (2026-11-07): a decision's evidence on a rerun, and approved apart
  from proved, in the new `lib/src/alignment/evidence.rs` and in `questions.rs`:
  - **The evidence comes from a proof under the current claim key.** Every `align --hints` run now works out, for
    every relation it proposes (collapsed or not), its claim key under the current builds and settings, and the
    evidence of any proof it made of it (`evidence::current`). Each hint a person approved or stated then gets
    (`evidence::refresh`, after the merge): the evidence of this run's proof of the same relation; otherwise its own,
    kept while its claim key is one the current builds, flags and settings give, and `stale` once it isn't (a change
    to either build, another tool binary, other proof settings). A relation the run doesn't propose at all has no
    current key, so its proved or refuted evidence is stale. An approved method takes its pair's evidence: proved
    when one of the pair's mappings is. Unchecked and unknown evidence stays until a proof.
  - **Approved is not proved.** `align` lists every decision a person made that isn't proved under the current claim
    key, with its evidence (unchecked, stale, or refuted with its counterexample), and doesn't ask it again. The last
    line counts them; a hints file whose decisions are all approved and proved asks nothing and lists nothing
    ("questions: none; 1 decision a person made, proved under the current claim key").
  - **Tests:** 2 more in `lib/tests/alignment.rs`, by the own checker. Through the command: an approval before any
    proof is listed as unproved; `--prove` gives it proved for key K and lists nothing; a static rerun under the same
    settings keeps K; one with `--unwind 8` makes it stale; a proof makes it proved again; a change to the new build
    makes it stale; a proof there gives a new key. And: an approved order a proof refutes is listed with its
    counterexample; an approved method takes its pair's proof; a relation not proposed at all goes stale. The kernel
    test now checks its three approved, unproved decisions are listed. All 33 pass, and the unit (185), foundations
    (3), skill (1) and conformance (9, 2 ignored) suites; every test target compiles; the Python tests pass (23). The
    integration contract on this branch: 2 passed, 22 unsupported, 0 failed.
  - **Score:** unchanged on 121–139. Re-recorded under the new tool's hash.
- Shared files changed: `lib/src/main.rs` (`align` builds the proof settings on every run, since they are part of
  every claim key, refreshes the decisions' evidence after the merge, and lists the unproved ones);
  `lib/README.md` (the `approve` comment and the module sentence); `lib/tests/alignment.rs` (the two tests, the
  kernel test's listing, and `questions::render`'s new argument). `mappings.rs` gains `Mapping::correspondence`,
  taken out of `checked_hints` unchanged.
- The integration report of 07:01:39 is a merge conflict between the streams in shared files (`examples/README.md`,
  `lib/README.md`, `equivalence.rs`, `build.py`, the `llm-dlc` indexes and traces), the script not run: for the
  reconcile loop, and no failure in this stream's part.
- **A5 done** (2026-11-07), with its last item, what tells two proved relations apart, in `lib/src/alignment/proofs.rs`
  and `mappings.rs`. With it every phase of this stream is done.
  - **Collapse by the same inputs too.** Two proved proposals with the same input mapping give the old version the
    same inputs, so the same observations, and are one candidate by the brief's rule, whatever their relations; so are
    two with the same relation, as before, and the grouping is closed transitively ("the same old-side observations
    on every input" is an equivalence). The test's `previous == (result > 0)` and `previous == (result != 0)` on
    `n > 0 ? 1 : 0` are now one candidate, not a question.
  - **What tells them apart** is said with the candidate that stands for them: a new result at which no old result
    satisfies both, so no input of the claim produces it, found by evaluating the two relations (`harness::expr`) on
    every old `boolean` and sampled new results (`proofs::apart`): "at -1, the first admits an old result of true and
    the second false". It is in the proof's `Settled::Proved.apart`, the kept hint's `why`, and its question's
    `means`. For an old result of another type nothing is claimed (its values can't all be tried).
  - **Different inputs and different relations stay a question**, with an input that separates two of them where a
    proposal tried shows one: a refuted proposal with the inputs of one and the relation of the other. There the
    first gives the old version an observation the second's relation doesn't admit while the second holds, so the
    two differ (`Settled::Asked.apart`, and the question's `decide`). Had that proposal been proved, the two would be
    one candidate. No proof is run for it beyond the proposals already tried; where it wasn't among them, the question
    says no separating input was among those tried. Within the catalogue such a question is rare: two different
    mappings both proved under different boolean relations would need the new result to encode two independent
    comparisons.
  - **Tests:** the test that asserted two proved relations are a question (that was the gap) now asserts they are one
    candidate, with -1 named, the one proved answer's `means` saying so, the refuted ones with their counterexamples,
    and `apart` on relations that agree everywhere giving nothing. One more, on made-up attempts over a real mapping:
    a question with its separating input, without one, and collapsed when the cross proposal is proved. All 34 in
    `lib/tests/alignment.rs` pass, and the unit (185), foundations (3), skill (1) and conformance (9, 2 ignored)
    suites; every test target compiles; the Python tests pass. The integration contract on this branch: 2 passed, 22
    unsupported (all other streams' parts: heap 6, summaries 3, observations 13), 0 failed.
  - **Score:** unchanged on 121–139. Re-recorded under the new tool's hash.
  - **For review:** job `20261107-053806-alignment-a3-second-half-every-proposal` runs the proofs under the collapse
    rule of its commit, where relations proved with the same inputs were a question. Under this commit's rule they are
    one candidate (for a changed result still a person's decision), so where 122 or 123 shows two such relations as
    `asked`, that is the rule since changed, not a regression; `wrongAndAccepted` should still be empty.
- Shared files changed: `lib/README.md` (the `align --prove` comment); `lib/tests/alignment.rs` (the two tests, and
  `Settled`'s new fields in a pattern). `mappings.rs` gains `ResultMapping.returns` (the two result types, as
  descriptors, serde-defaulted and skipped when empty).
- The integration report is still the one of 07:01:39 (a merge conflict between the streams in shared files, the
  script not run): for the reconcile loop, and no failure in this stream's part.
- Every job this stream submitted is listed above: `20261107-053806-alignment-a3-second-half-every-proposal`, for
  review.
- Status: done

## Loop settings

- session: 11f93b59-b830-4090-8775-33313957ef5c
- model: claude-opus-5-5
- effort: high
- workspace: alignment
- fork: ae994066-d1ea-4620-b03e-176a07061175

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step needs the user. When a step's evidence is a long job, submit it and go on; a job is never a reason to stop, and a quick one is awaited only as above. Stop
with `done` when your phases are finished, or `blocked: ...` when what is left needs the user and is recorded under
Progress. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish, and don't start another stream's work.
