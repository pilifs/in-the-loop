# Feature loop: example-targets-positive

Started 2026-11-14 15:26:46 UTC, no limit on cycles, session ddf78f27-05e0-438a-81be-8e7620b07bb7, claude-opus-5-5 at high effort, after change qpvlyptuzssruqtxruvqznvkntkoknup.

> Work on the brief in `llm-dlc/loops/example-targets-positive.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'qpvlyptuzssruqtxruvqznvkntkoknup..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/example-targets-positive.md` at sha256 3779f456bd75d197d023f35daa93d78505a469e8fa65e94e9f49c250054970f4.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when P1–P3, P5 and your acceptance are met (P4 is optional), or each is deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Don't expand into broad positive mining or cryptographic verification. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

Session ddf78f27-05e0-438a-81be-8e7620b07bb7 was forked from session e9be5afb-09c9-4473-a9e9-38f2fb61ca80.

- cycle 1, 2026-11-14 15:39:22, `rzvwqpqtuumn`: example-targets positive: the three positive packets source-locked (305, 306, 307)
  - decided to continue: This run has one commit, the source locks for 305–307, and most of the brief is still work I can do on my own. P2's claim file, oracle, replay driver, probes and mutant come next. After that come the same pieces for P1 and P3, and P5's migration of 105. P1 and P3's build routes wait on your decision, but that only stops their preparation, not their claims, oracles, drivers or mutants. Nothing is waiting on jobs, and nothing is blocked yet.
- cycle 2, 2026-11-14 15:48:44, `xlxqqpyrozos`: example-targets positive P2: 306's claim, oracle, driver, probes and dropped-prefix mutant
  - decided to continue: This run has two commits: the source locks for 305–307, and P2's full packet for 306 (claim, oracle, driver, probes and mutant). The next pieces need only my own work: P1's packet for 305 (claim, oracle, driver, probes and the 200-boundary mutant), then the same for P3 (307), then P5's migration of 105. Your decision on the download policy only holds up building 305 and 307, not writing their packets, and nothing is waiting on jobs.
- cycle 3, 2026-11-14 15:59:05, `kyzpskvsmxlx`: example-targets positive P1: 305's claims, oracle, driver, probes and 200-boundary mutant
  - decided to continue: This run has three commits: the source locks for 305–307, P2's packet for 306, and now P1's packet for 305. P3's packet for 307 and P5's migration of 105 still need nothing but my own work. Your download-policy decision holds up only the builds of 305 and 307, not writing their packets, and nothing is waiting on jobs.
- cycle 4, 2026-11-14 16:13:32, `vwsxyvlrttlq`: example-targets positive: propose upstream BCrypt test vectors for the allow list
  - decided to continue: The loop should go on. This run has written the packets for P1, P2 and P3, each with its claim, oracle, driver, probes, mutant and hand checks. P5 still needs nothing but my own work: resolving example 105's revisions afresh, writing its sidecar and packet, choosing a small obligation that can give gate A5 a real proved or refuted result, and listing examples 105–109. Your download decision holds up only the builds for 305 and 307, and nothing is waiting on jobs.
- cycle 5, 2026-11-14 16:26:46, `uzxpwmkuyytm`: example-targets positive: record the two new cross-workspace manifest errors for the coordinator
  - decided to stop: This run has delivered everything the brief asks of this stream: the source-locked P1–P3 packets, each with claims, an oracle, probes, a mutant and a driver, and 105's migration with its A5 obligation and the 105–109 inventory. The acceptance is met and Progress already says `Status: done`. What remains is outside my own work: P1's and P3's build route and the 15 allow-list proposals wait on you, the builds, replays and A4/A5 attempts belong to runtime and Phase 5, and P4 is optional.

## Summary

# Example-targets positive stream: run summary

The stream is **done**. It wrote packets for the three new positive examples (P1–P3: 305, 306, 307) and moved the existing example 105 to the new route (P5). P4 is optional and was not done. Its acceptance is met: P1 and P3 are complete but labelled partial, each with its predicted build blocker recorded. No build, replay or proof from this stream ran through the pipeline. Every run listed below was done by hand, and each is recorded as a note, not as evidence. Phase 5 runs the real replays and the gate A4 and A5 attempts. Nothing was pushed.

## Commits (oldest first)

**`rzvwqpqt`: the three positive packets source-locked (305, 306, 307)**
- **Adds:**
  - three new examples, each with `example.json`, a `target.json` sidecar, a `sources.lock.json` and a README:
    - 305: Spring Boot `WebMvcTags.outcome`;
    - 306: Spring Framework `PatternMatchUtils.simpleMatch`;
    - 307: Spring Security `BCrypt.hashpw`.
  - Every commit and parent was checked against github.com.
  - 306 uses the published Central JARs (spring-core 5.3.6 and 5.3.7, pinned by sha256), because its source file is byte-identical to the commits'.
  - 305 and 307 each record a predicted build blocker.
- **Verified:**
  - `sidecar.load` accepts all three;
  - `build.py --plan` stops each task at the workflow stream's Phase 0 stub, as expected;
  - the integration script passes (contract, the targets suite with 41 tests, test_build with 190, test_pipeline with 29).

**`xlxqqpyr`: P2, 306's packet**
- **Adds:**
  - a claim in the workflow stream's `example-target-claim/v1` format: arguments null or at most 6 UTF-16 code units;
  - 40 probes;
  - an independent oracle that matches the pattern by dynamic programming;
  - a driver;
  - the mutant `drop-prefix.patch`.
- **Verified:**
  - The claim validates against the workflow stream's schema.
  - The workflow stream's planner plans both tasks.
  - The integration script passes.
  - By hand: 5.3.6 and 5.3.7 agree with the oracle on all 40 probes, on JDK 21 and 25. The mutant fails 6 probes.

**`kyzpskvs`: P1, 305's packet**
- **Adds:**
  - two claims: preservation, and the finite-outcome claim at both revisions;
  - 27 probes;
  - an oracle that reads the HTTP status class from the status's decimal spelling (RFC 9110);
  - a driver that uses a `Proxy` response;
  - the mutant `status-200.patch`.
- **Verified:**
  - By hand on JDK 21 and 25: before (compiled from source), after (from source and as published) and the oracle agree on all 27 probes. The mutant differs at 200 only.
  - A gaps scan predicts that every strict attempt is refused.
  - The planner plans all four tasks, and the test suites pass.

**`umpplsnu`: P3, 307's packet**
- **Adds:**
  - a claim whose domain covers a null password, malformed surrogates and invalid salts; exception messages are excluded;
  - 45 probes around bcrypt's 72-byte key limit;
  - an oracle that computes no cipher;
  - a driver;
  - the mutant `us-ascii.patch`.
- **Verified:**
  - By hand: both commits and Central's 5.2.0.RELEASE agree with the oracle on all 45 probes, byte-identically on JDK 21 and 25. The mutant fails the oracle 9 times.
  - The planner plans both tasks, and the test suites pass.

**`vwsxyvlr`: allow-list proposals for upstream BCrypt test vectors**
- **Adds:** 15 long-token findings in this session's log, proposed with `sync.py allow propose`.
- **Verified:** each was checked masked with `review show`. All are expected hashes from Spring Security's public `BCryptTests` test-vector table, not credentials.

**`xopqylpx`: P5, 105 migrated (commons-numbers#223, `ArithmeticUtils.pow`)**
- **Adds:**
  - `target.json`; 105's README, summary and verdict label stay as the historical report;
  - the revisions, resolved afresh:
    - before `e7c172d2`;
    - after `8cfc04e8`;
    - pull request head `79aa4643`;
    - 1.3 release, the same source as before.
  - gate A5's selected obligation, `claims/pow-minus-two.json`: (-2)^e for 0 ≤ e ≤ 31. It is expected established on after and refuted on before at e = 31.
  - a preservation claim for the historical report's two equivalence rows, kept as diagnostics;
  - a Javadoc oracle, a driver and 75 probes;
  - a gaps record;
  - `records/legacy-inventory.json`, covering 105–109. 106–109 were not touched and none is counted as a success.
- **Verified:**
  - By hand on JDK 21 and 25: after meets the contract on 75 of 75 probes. Before and the published 1.3 JAR deviate only at (-2, 31). The oracle fails, as it should, on the wrong revision's output.
  - The claims and the sidecar validate, and the planner plans all five tasks.
  - The test suites and `build.py --plan` pass.

**`uzxpwmku`: Progress update for the coordinator**
- Records that the post-commit check now reports 13 "no manifest" errors, all on other streams' changes.

## Verification jobs

- **Pending:** 0. **Running:** 0. **Finished but not collected:** 0.
- This stream submitted no jobs.
- The pipeline report shows nothing failed or outstanding.

## Before you push: what `sync.py check` reports

The result is 13 errors and 5 warnings.

- **13 ERRORs: "session … has no manifest".** None is on this stream's changes. They are on the runtime stream's changes (session 3bb5a1f4), the workflow stream's (eaff7dd7) and the negative stream's (70d4b729), for example `wqsyopql`, `qyzrtrwr` and `kwzmplxt`. It looks like an effect of the check reading across workspaces. They are listed under Progress for the coordinator, and must be cleared before a push.
- **1 warn: "15 proposed entries await a person".** These are the BCrypt test vectors above. To accept them, run `python3 llm-dlc/tools/sync.py allow approve` when you choose.
- **4 warns: long tokens in this session's logs.** They are the same 15 findings, repeated in later copies of the log. Approving the proposals settles these too.

## Waiting on your decision

- **The build route for P1 (305) and P3 (307).** Neither can be prepared under decision 1 (Central and github.com only). Choose one of:
  - **(a)** Extend decision 1 to repo.spring.io, services.gradle.org and plugins.gradle.org, with every download hash-pinned. This is enough for P3, but not for P1, whose commits pin SNAPSHOT dependencies.
  - **(b)** Accept a narrower scope with its own label: compile the selected classes from each commit's sources outside the upstream build, against pinned Central releases of their dependencies.

  A4 doesn't need either: it can rest on P2.

## Also worth your attention

- **Three interface requests for the merge**, recorded in Progress:
  1. The schema needs a way to name a "base commit plus patch" revision for the mutants. Until then each mutant is a `controls` entry.
  2. Run `build.py --index-only` at the merge, so `find.py` lists 305–307 and 105's sidecar.
  3. Link 305–307 to the negative stream's examples once it numbers them.
- **The brief is out of date in one place.** Its starting evidence says these pairs have no published JARs and need the upstream build. That is wrong for P2, whose published JARs are used, and only half right for P1: 2.2.0.RELEASE carries after's class, and nothing published carries before's.
- **Predicted refusals.** Static scans predict that the strict attempts for 305, 306 and 307, and 105's `confined-change` diagnostic, are refused at gaps: JDK methods the tool's own checker approximates. These are predictions, not observations, and are recorded as blockers. 105's selected obligation reaches no gap.

Ended 2026-11-14 16:28:51 after 5 cycle(s): the session decided to stop; the brief says done.
