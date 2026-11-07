# Brief: decide by the solver whether a proof enters a JBMC stub

**Drafted 2026-11-07, and chosen by the user that day** over a `String.format` model ([Decisions](#decisions)). It
starts once the cleanup loop's merge is committed ([`cleanup.md`](cleanup.md)): it changes `lib/src/jbmc_gaps.rs`, which
the cleanup jbmc stream also changes.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run alone in the default workspace:
`llm-dlc/tools/feature-loop.sh llm-dlc/loops/stub-reachability.md`. It makes JBMC's gap preflight count a stub as
entered only when a path the proof checks can reach it. Then it closes VF-015, which waits on exactly that.

**Inputs.** Read these in full before the first piece of work of every cycle:
- this brief;
- `lib/src/jbmc_gaps.rs`'s module doc and `preflight_untimed`, `symbolic`, `entered` and `find_told`, at the merge;
- `verification/findings.md`'s entry VF-015, and the cleanup native stream's N3 in `cleanup.md`'s folded Progress.

## Direction

- **Sound first.** The JVM is the semantic reference, and only JBMC's `VERIFICATION SUCCESSFUL` is a JBMC proof.
- **A gap is left out only on evidence.** A stub is left out of the gaps only when the solver shows that no path within
  the proof's bounds and assumptions enters it. When the check can't tell (a timeout, an unknown, unreadable output),
  the stub stays a gap, as today.
- **`--gaps strict` keeps its meaning**: a proof that enters a stub is no verdict. Only the count of what "enters"
  becomes precise.
- **No model of `String.format`** ([decision 1](#decisions)). Under `--no-refine-strings`, JBMC can't read a format
  string's contents, so a model would be either unsound (assuming every format string is well formed and every
  `toString` pure) or a source of spurious refutations in equivalence checks.

## Where it starts from

Recounted at the cleanup jbmc stream's `@-` on 2026-11-07. Recount it at the merge.
- **The listing.** The preflight first lists JBMC's goto program (`--show-goto-functions`), whose call graph takes
  every branch.
- **The symbolic run.** When that graph reaches a stub, the preflight runs JBMC's symbolic execution alone
  (`symbolic_command`: `--program-only`, with the proof's `--unwind`). A stub none of whose locations appears in the
  formula is left out (`entered`, `Found::unreached`).
- **Why that falls short.** Symbolic execution drops a branch only when it simplifies the condition to false. A
  condition the solver would decide is kept, so is a stub behind an `--assume`.
- **The case.** VF-015's job `20261107-165827-…`, at step 3, runs
  `prove Hex#toDigit --assume 'ch == 1632' --assert 'result == 0'` on commons-codec's old `Hex`:
  - JBMC proves it;
  - the preflight names `String.format(String, Object[])` as entered, called by
    `DecoderException(String, Object...)` on `toDigit`'s exception path;
  - so strict refuses the proof;
  - yet with `ch == 1632`, `Character.digit` (the model) returns 0, and that path is infeasible.

## How to work through it

The [standing rules](brief-template.md#standing-rules) apply, the [timebox](brief-template.md#the-timebox) included:
- one step per cycle;
- check each claim against the code first;
- JBMC runs are queued, never run inline;
- nothing gets weaker;
- docs move with the behaviour;
- a reproducer before a fix.

Verification runs with the pipeline. When everything left waits on jobs, end Progress with
`- Status: waiting on jobs` and the ids, with no other word between them. `run-streams.sh` reads only id-shaped words
there now, but a single loop is rerun by hand.

## The plan

1. **The experiment, as one job.** It reproduces VF-015's step 3 with `--work` kept, then runs JBMC on the same
   harness in two ways:
   - `--cover location`, reading the goals at the entry of the `String.format` stub (expected: not covered);
   - the alternative the session finds in `jbmc --help` and the CProver docs: say, a reachability assertion at the
     call site, from a rewritten harness or goto program.

   Each is timed, beside the proof's own time. The job's description names the expected outcome of each method.
   JBMC 6.11 has `--cover`, though not with `--unwinding-assertions`; check how `--unwind` then bounds the paths.
2. **Choose the method** from the job, and record why under Progress: correct on the case, and cheap next to the
   proof. If neither is correct, or both cost more than the proof itself, stop with `blocked:` and the measurements,
   for the user.
3. **Implement it** in `jbmc_gaps.rs`, as a third step after `symbolic`, only for the stubs the symbolic run still
   enters, within the preflight's budget.
   - A stub the solver shows unreachable joins `Found::unreached`, with its reason named in the note.
   - Unit tests on recorded JBMC output, in the style of `entered`'s, are the reproducer: failing before, passing
     after.
   - The module doc, `lib/README.md`'s gap section and `Preflight::paths`' doc move with it.
4. **The checks, as jobs**:
   - VF-015's job resubmitted unchanged (`pipeline.py resubmit`), its title naming "closes VF-015 when it passes".
     That is N3's second and last attempt under the cleanup timebox. If step 4's replay then fails on
     `StandardCharsets.UTF_8` (`lib/src/interp/natives.rs:373`), that is the interpreter fix VF-015's entry names, and
     it is this brief's next item.
   - A guard that no stub a proof does enter is left out: the gap-preflight tests in `lib/tests/` and the conformance
     corpus under `--engine jbmc` (`the_corpus_agrees_with_the_jvm_under_jbmc_and_auto`), unchanged, expected to pass.

## Done when

| Step | Criterion |
|---|---|
| 1–2 | the method chosen on the job's evidence, or `blocked:` with the measurements |
| 3 | the reproducer fails before and passes after, and the docs are updated |
| 4 | VF-015's job passes (closing it), or is deferred by the timebox with the finding; the guard jobs pass |

## Deferred: not in this loop

- A `String.format` model or any other JDK model ([decision 1](#decisions)).
- JBMC's string solver (`--refine-strings`).
- External JBMC work.

## Decisions

Settled by the user on 2026-11-07:
1. Settle VF-015 by deciding stub reachability with the solver, after the cleanup merge, not by a `String.format`
   model in `lib/models/` and not by running step 3 under `--gaps assume`.

## Progress

- Drafted 2026-11-07 by session `3da21514`, while the cleanup run was still going.
- 2026-11-07: the cleanup loop's merge is committed (`lpvnwkuz`) and pushed, and the loop is done, so this brief starts.
- Status: working

## Loop settings

- session: 807d6ed2-a98d-4f93-8dbb-28d70736eff7
- model: claude-opus-5-5
- effort: high

## Loop until

Stop with `done` once step 4's criterion is met. Stop with `blocked: ...` when step 2 finds no method that is both
correct and cheap, or the user is needed. Set the status to `working` when the cleanup merge is committed, before
starting. Don't take on other gaps or models.
