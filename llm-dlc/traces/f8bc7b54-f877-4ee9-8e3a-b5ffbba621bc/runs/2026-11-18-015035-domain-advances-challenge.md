# Feature loop: domain-advances-challenge

Started 2026-11-18 01:50:35 UTC, no limit on cycles, session f8bc7b54-f877-4ee9-8e3a-b5ffbba621bc, claude-opus-5-5 at high effort, after change utvyrttkozzstpuxkpyrnnpulroxrqtw.

> Work on the brief in `llm-dlc/loops/domain-advances-challenge.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by naming what is yours: `sync.py commit --only PATH ... -m ...` takes those files and folders alone and leaves everything else uncommitted where it is. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'utvyrttkozzstpuxkpyrnnpulroxrqtw..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message. Then read your inbox, `$(jj workspace root --name default)/llm-dlc/loop-summaries/domain-advances-challenge-inbox.md`, if it exists: each item under Open there is something the conductor needs you to act on, so acknowledge each by its id in this cycle's Progress update with what you did about it, and weigh it below your brief and the user's decisions, which come first, so an item that contradicts the brief is reported in Progress, by its id, not obeyed.

Brief `llm-dlc/loops/domain-advances-challenge.md` at sha256 5c6647cdbdddad82a40c070a156a5cec3712a6c41707037952c848a3a84f249e.

After each commit the session decides whether to go on:

> Items 1 to 4 first, then 6 and 7, which need nobody; 5 for as long as another stream is still working, since their commits are your input. When you have nothing left to attack while they still work, stop with `blocked: waiting for the other streams' next commits`, not `done`: the watcher can run a blocked stream again, twice at most, so spend those on real waits. `done` when the other three streams are finished and their last rules are challenged, or when the reruns are spent, with what was left unchallenged listed. Keep the last line of Progress a status.

## Commits

- cycle 1, 2026-11-18 02:04:25, `yulpuuronznk`: Record the challenge stream's last inbox item, domain-advances-preservation-I029
  - decided to stop: The loop should stop, because this cycle was the last pass your D035 and D036 allowed. It checked preservation's I023 fix (none of the seven cases is proved any more, and `--no-shared-callees` takes no call), confirmed I002's rules on the merged line, and handed one new false proof past the fix to preservation as I029. Progress now ends with `Status: done` and lists what was left unchallenged. The brief's Loop until would keep the stream going while preservation still works, but your decisions come first.

## Summary

# Challenge stream (`domain-advances-challenge`): loop-end summary

The run made one cycle and two commits. No jobs were submitted, and `sync.py check` reports 0 errors and 42 warnings. Progress now ends with `Status: done`: this was the last pass your D035 and D036 asked for (carried by I006 and I007).

## Commits

### `orxlmwsv`: preservation's I023 fix holds for the seven, and one new false proof gets past it

**What it checked**, at preservation's fix `puuwrruu`, built apart:
- **I023's seven call-level cases:** none is proved any more. `filled`, `copied`, `interned`, `same` and `tagged` are refuted, and `overflowed` and `exhausted` get no verdict. Of the three controls, `hashed` and `encoded` get no verdict and `messaged` is refuted.
- **`--no-shared-callees`:** no call is taken as one function in any of the ten cases.
- **The record countermodels from the previous commit:** `stale` is still proved to agree without the flag (13 calls taken), and refuted with it. `swapped` gives a false refutation without the flag, and a correct one with it.
- **I002's two rules together on the merged line:** the 53 `claims`, `contract`, `effect`, `frame`, `function`, `lemma`, `stand_in` and `stub` tests and the 20 `pairing` tests all pass.

**The new false proof:** the fix checks each array one at a time (a known length of at most 65536), but nothing limits how many arrays a run keeps.
- A loop that keeps arrays of a constant length asks for 32 TiB once `k >= 1`. That is an `OutOfMemoryError` the call's outcome leaves out.
- The checker proves the two versions agree (`kept`: proved, not vacuous, 12 calls taken), yet a JVM tells them apart: one answers -1, the other -2.
- The control `around`, a recursion through an overridden method, is refused correctly.

**What it adds:**
- The fixtures `lib/tests/fixtures/allocation-countermodels/`. Their README sets out the rule, the hole, the commands, three ways to fix it, and the test the checker should pass after a fix.
- The test `lib/tests/allocation_countermodels.rs`. It checks that the shared classes are the same bytes in both versions and runs each version on a JVM with a 64 MiB heap.
- `costs.json`, updated by `estimate` and `tag`.

**Audit:** in 287's pinned bcrypt sources (6.3.7 and 6.3.8), `crypt_raw` never stores an array inside another array. So 287 and 307 are not affected.

**How it was verified:** the 57 Rust test binaries that `test_costs.py run --changed` picked passed, under the I003 memory cap. The checker-side test in the README fails on `kept` at `puuwrruu`, as intended.

**Sent:** inbox item `domain-advances-preservation-I029` (a failure, citing `orxlmwsv`).

### `yulpuuro`: record the last inbox item

Progress records I029's id. The commit checks also gave 0 errors.

## Verification jobs

- **Pending, running or failed:** none.
- **Recorded on another line:** `20261118-011232-example-286-s-vulnerable-protected-state` (example 286's vulnerable protected-state task). It is in commit `649cb8e32f78`, which this line does not contain. It is collected once the lines merge, and does not run again.

## Warnings to judge before a push

`check` reports 42 warnings:
- **4 allow-list proposals** waiting for you: `python3 llm-dlc/tools/sync.py allow approve`.
- **long-token:** the watcher session `6c5c7798` has 28 logs with 2 hits each (`If6…fW`, 53 chars). Session `88045564` has 7 logs with 24 hits each (`If6…Pw` and `If6…jT`, 48 chars).
- **other-home-dir:** session `7ece8184` has 3 logs plus its run summary `runs/2026-11-17-163151-domain-advances-evidence.md` (`/ho…ne`).

None comes from this run.

## Needs your input

- **Preservation needs to fix I029**, the unbounded total of kept arrays. The README offers three options:
  - bound the total memory the call makes, and refuse an allocation in a loop whose bound is not a constant;
  - refuse storing an array or object into an array the code made;
  - add "each call ends normally on a heap that holds what it makes" to the assumptions the result states.

  Once it is fixed, the README's test should be added to `allocation_countermodels.rs`.
- **I028 (the earlier `stale` and `swapped` record cases) is still open.** `stale` is still proved to agree at `puuwrruu` without `--no-shared-callees`.
- **Left unchallenged, as listed in Progress:**
  - 290's security claim (item 6);
  - state's `srxyxsns`;
  - evidence's `nzsypymy`;
  - preservation's `vyzppnku`, and its commits after `puuwrruu`, including any fixes for I028 and I029;
  - whether 289's and 290's reruns take a call as one function;
  - whether 287's or 307's harness merges the heap between two related calls.

  Challenging any of these needs a new decision from you, since D035 and D036 ended the stream here.
- **Nothing was pushed.** Before a push, `sync.py push` needs a passing default test run covering the merged tree.

Ended 2026-11-18 02:06:05 after 1 cycle(s): the session decided to stop; the brief says done.
