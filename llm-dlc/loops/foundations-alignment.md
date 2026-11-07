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
- Next, the rest of A4:
  - nested shapes: an old field set from a parameter whose own class changed shape, named today as "nested field
    correspondence is not done yet";
  - a result whose class changed shape, still `changed`, a person's decision;
  - `Pricing#withQuantity`, unchanged code over changed classes.

  Then A5.
- Status: working

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
