# Feature loop: example-targets-negative

Started 2026-11-14 15:26:46 UTC, no limit on cycles, session 70d4b729-3b1f-41d1-a89c-03fd78a71818, claude-opus-5-5 at high effort, after change qpvlyptuzssruqtxruvqznvkntkoknup.

> Work on the brief in `llm-dlc/loops/example-targets-negative.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'qpvlyptuzssruqtxruvqznvkntkoknup..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/example-targets-negative.md` at sha256 6f1a4abdcbd77a0bfcc222dde44853a4dcc34df3ccf6bd126851212e94307e22.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when N0–N4 and your acceptance are met, or each is deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Don't go on into an unbounded proof or introducing-commit investigation. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

Session 70d4b729-3b1f-41d1-a89c-03fd78a71818 was forked from session e9be5afb-09c9-4473-a9e9-38f2fb61ca80.

- cycle 1, 2026-11-14 15:35:29, `pomrmppunkzt`: example-targets negative N0: the Spring CVE catalog, 285-300, with every revision checked upstream
  - decided to continue: This run has one commit so far, N0 (the catalog). N1–N4 still need only my own work: the method-label, binder and BCrypt packets, then the CVE-2025-22234 follow-up and the handoffs. Each starts by reading the upstream sources and writing tasks, oracles, probes and controls, and nothing waits on a job, the user or another stream yet.
- cycle 2, 2026-11-14 15:53:25, `mkwpnurukopq`: example-targets negative N1: the CVE-2023-34055 method-label packet (285), source-locked with frozen claims, oracle, carrier, driver and mutant
  - decided to continue: This run has two commits: N0, the catalog (`pomrmppu`), and N1, the method-label packet for 285 (`mkwpnuru`). N2 (the binder packet for 286), N3 (the BCrypt packet for 287) and N4 (the CVE-2025-22234 follow-up and the handoffs) are still to do. Each needs only my own work: reading upstream sources and writing locks, claims, oracles, probes, mutation controls and drivers, with no job, user decision or other stream to wait for.
- cycle 3, 2026-11-14 16:15:50, `kwzmplxtmktn`: example-targets negative N2: the CVE-2022-22968 binder packet (286), source-locked, with the decision lemma, preservation and protected-state claims, oracle, driver and mutant
  - decided to continue: This run has committed N0 (the catalog), N1 (the method-label packet, 285) and N2 (the binder packet, 286). N3 (the BCrypt packet, 287) and N4 (the CVE-2025-22234 follow-up and the handoffs) are still to do. Both need only my own work: reading upstream sources and writing locks, claims, oracles, probes, mutants and drivers, with no job, user decision or other stream to wait for.
- cycle 4, 2026-11-14 16:35:26, `mpmuuzlyovxn`: example-targets negative N3: the CVE-2025-22228 BCrypt packet (287), source-locked, with the public matches claim, preservation, a byte-array guard lemma, oracle, independent stored hashes, driver and mutant
  - decided to continue: The run has committed N0 to N3: the catalog, and the packets for 285, 286 and 287. N4 is still open and needs only my own work: the CVE-2025-22234 research-only entry in 300, linked to N3, with its gap packets and handoffs, and a check of the three packets against the acceptance. It needs no job, user decision or other stream, and it is bounded. The uncommitted allow-list proposals wait for you, but they don't block N4.
- cycle 5, 2026-11-14 16:46:48, `zuoknplnoqpy`: example-targets negative N4: CVE-2025-22234 (300) research-only with the 6.3.9 policy as a proposed contract and a source lock; handoffs and acceptance checked
  - decided to stop: The run has five commits: N0, the catalog, then N1 to N4, the packets for 285, 286 and 287 and the follow-up in 300 with the handoffs. The acceptance checks pass on this branch, and the brief's Status already says `done`. What remains is A3, which needs the merge and Phase 5, and the allow-list proposals, which wait on you; neither needs only my work.

## Summary

# Example-targets negative stream: summary of the run

The run made five commits in workspace `in-the-loop-example-targets-negative`, and the brief's Status is now **done**. Examples 285–287 are complete packets ready for Phase 5: source-locked, with frozen claims, oracles, drivers and mutants. 300 is a linked research case, and the other 13 are catalog entries. **No verifier has run on any of them.** Every hand run below is a developer note, not evidence, and all 50 recorded blockers are still predictions.

## Commits

| Commit | What it adds | How it was verified |
|---|---|---|
| **pomrmppu** `b142c8b3` N0: Spring CVE catalog | • Examples 285–300: the archived registry's 15 Spring CVEs plus CVE-2025-22234 (300).<br>• Each has `example.json`, a `target.json` sidecar (`example-target/v1`) and a README written by hand.<br>• 285, 286 and 287 become role negative; 13 are catalog entries whose missing pieces are recorded as predicted blockers; 300 is research only, linked to 287.<br>• `examples/tags.json` gains 11 tags (additions only). | • Every revision checked upstream: release tags via `git ls-remote`, the 17 fix commits and their parents fetched, and ancestry checked with `git merge-base`. All matched the registry.<br>• `build.py --plan` validates all 16 sidecars.<br>• The integration script passes. |
| **mkwpnuru** `6cebf641` N1: 285, CVE-2023-34055 (Spring Boot `WebMvcTags.method`) | • Release pair 2.7.17 → 2.7.18 selected; it carries the exact fix faithfully.<br>• `sources.lock.json`: seven-JAR class paths with sha256.<br>• Four tasks: replay, vulnerable/fixed security on one frozen claim (8 HttpMethod names plus UNKNOWN), preservation.<br>• Controls: carrier, adapter, driver, 15 probes, independent oracle, mutation patch. | • The claims validate against the workflow stream's claim schema, and its planner plans all four tasks.<br>• Integration script passes.<br>• Hand run on Temurin 21 and 25: 2.7.17 fails at exactly the 5 trigger probes, 2.7.18 holds, the mutant fails at the same 5, and both JDKs give identical output. |
| **kwzmplxt** `beec61d8` N2: 286, CVE-2022-22968 (`DataBinder` case-insensitive disallowed fields) | • Release pair 5.3.18 → 5.3.19 selected, with a source lock.<br>• Three claims and six tasks: the decision lemma, preservation, and a protected-state claim on the actual bind.<br>• Controls: 46 probes, oracle with self-test, a mutant that lower-cases only one side. | • Claims validate and all six tasks plan.<br>• Integration script passes.<br>• Hand run: 5.3.18 fails at exactly the 12 triggers, 5.3.19 holds, preservation holds, the mutant fails 13 probes; identical on both JDKs. |
| **mpmuuzly** `723c4047` N3: 287, CVE-2025-22228 (BCrypt ignores bytes past 72) | • Release pair 6.3.7 → 6.3.8. Between the two JARs only `BCrypt.hashpw(byte[],String,boolean)` differs.<br>• Three claims and six tasks: the public `matches` rejection claim, preservation, and a byte-array guard lemma (diagnostic).<br>• 33 probes against 9 stored hashes made independently by pyca bcrypt.<br>• Oracle, driver, and a mutant that counts UTF-16 units instead of bytes. | • Claims validate and all six tasks plan.<br>• Integration script passes.<br>• Hand run: every outcome was the one written down before the run. 6.3.7 authenticates the 9 overlong triggers, 6.3.8 rejects all 12 overlong probes, the mutant authenticates the multibyte ones.<br>• A Java harness checked that the claim's own expressions agree with the oracle. |
| **zuoknpln** `8b9753fe` N4: 300, CVE-2025-22234, plus handoffs and acceptance | • 300 stays research only. It keeps three properties apart: 287's blanket rejection, the 6.3.9 policy, and the timing mitigation.<br>• The 6.3.9 policy (encode refuses more than 72 bytes; matching depends only on the first 72) is recorded as a proposed contract, not a frozen claim.<br>• New source lock; 3 predicted blockers.<br>• 287's README and notes now say its claim fails on 6.3.9 by design.<br>• 286 and 287 mark their release pair selected. | • All 16 sidecars validate; the planner plans all 16 tasks of 285–287.<br>• Integration script passes (about 82 s, exit 0).<br>• Hand run of 287's driver on the 6.3.9 JAR: every outcome equals 6.3.7's.<br>• pyca bcrypt 5.0.0 confirms that the legacy hash is the hash of the first 72 bytes. |

## Verification jobs

- **This stream queued none.** By design, Phase 5 runs the capability probes on prepared artifacts.
- Two jobs are pending, both from the **runtime** stream:
  - `20261114-162937-example-targets-runtime-r3-run-verifier`
  - `20261114-164239-example-targets-runtime-r3-after-vf-024`
- No jobs are running, and none are finished but uncollected. `report` shows no failures for this stream.

## `sync.py check`: what you need to judge before pushing

- **warn: 8 allow-list proposals wait for you.** They are all `long-token` false positives in this session's logs:
  - 7 are 53-character `Ex4…` values: 262bb771, 36f507b2, 7789bb63, 587e045b, 541a7555, 043a3764, 981d7f81.
  - dd2fcadc is a 44-character `iX5…` value: the bcrypt hash from upstream's public test.

  Approve them with `python3 llm-dlc/tools/sync.py allow approve` in your terminal. The other two warns (logs `0af677ae…` and `e9437712…`) are the same findings and clear when you approve. The proposals are uncommitted in the working copy (`M llm-dlc/allowlist.json`), as the procedure expects. The brief's Progress says 7 proposals; there are now 8.
- **ERROR ×25: "session … has no manifest".** All are in other sessions' changes (sessions ddf78f27, 3bb5a1f4, eaff7dd7, 8b430aa4 and c9b766bf), which come from the other streams merged into this workspace. None is in this stream's commits. I left them alone, since those changes aren't mine. They need to be resolved at the merge or by the coordinator before a push.

## Waiting on you or on the merge

- **A3 (the final acceptance step):** it needs the streams merged and then Phase 5 to prepare 285–287 and run the replay and capability probes. Next step for each packet: `build.py --plan NNN --task replay`.
- **Router regeneration:** `examples/README.md` and `index.json` were not regenerated because they belong to the coordinator. They need regenerating at the merge.
- **Interface requests for the merge**, recorded under Progress in N1: how a constructed mutant is represented as a revision, and how a driver is invoked.
- **Integration report (16:28):** it stopped on conflicts only in generated shared files (`llm-dlc/README.md`, `index.json`, `traces/`), none of them this stream's.

## Other things worth your attention (for review, also under Progress)

- **6.3.9 brings 287's bug back for matching, on purpose.** `matches` authenticates by a 72-byte prefix again; only encoding stays fixed. Anyone reading CVE-2025-22228 as "fixed from 6.3.8 on" would miss that.
- **300: a possible functional distinguisher.** Read from source, not run: on 6.3.8 an unknown user and a known user with a non-bcrypt stored encoding end in different exceptions for an overlong password.
- **300: upgrading a legacy password throws.** Also read from source, not run: on 6.3.9, upgrading the encoding after a legacy overlong match calls `encode`, which throws.
- **287:** unpaired surrogates authenticate against a hash of `?` characters on every revision. This is in range, so it isn't this CVE.
- **287:** a cost-31 hash never terminates (read from the bytecode).
- **287:** the frozen claim is a strict rejection policy, stricter than the seed's "may reject".
- **286:** outside ASCII, 5.3.19 allows `dataΣx` against `dataΣ*`, because of how Java lower-cases the final sigma.
- **286:** under the tr-TR locale, 5.3.19 allows a case alias (example 288's property).
- **The brief is out of date in one place** (said in N2's commit message): N2 asks for upstream's "changed wildcard tests", but fix a7cf19ce changes none. The packet copies that test's inputs instead.

Ended 2026-11-14 16:48:51 after 5 cycle(s): the session decided to stop; the brief says done.
