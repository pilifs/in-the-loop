# Verification findings and decisions

What the verification runs turned up that needs a person: verdicts against a change, failures a submitter has to
fix, and decisions the managing agent took that change what the results mean. The agent running
[`/run-verification`](../.claude/skills/run-verification/SKILL.md) adds an entry whenever a run produces one, and
updates or closes entries when a later run settles them. Results themselves stay in [`results/`](results/); this
page is the short list of what is still open, and what was decided, so that nothing is lost between sessions.

Each entry has an id (`VF-NNN`, never reused), and these fields:

- **Status**: `open` (needs someone), `decided` (a decision was taken and is recorded here, nothing to do), or
  `closed` (settled: say by what, with the job or commit). Open entries come first, newest first; the rest follow.
- **Raised**: the date, the machine (`runner.host`), and the run's job ids and the commit they ran at.
- **Found**: what happened, with the evidence a reader needs without the logs.
- **Needs**: what would settle it, and who should act: the submitter, a brief's loop, or the user.
- **Tracked in**: where the work lives, if anywhere else (a brief's Progress, an example's notes).
- **Closes when**: the check that settles it, usually a job to rerun unchanged.

## Open

### VF-080: 947 kept outputs that receipts name are in no commit and no archive; 944 survive in one working copy

- **Status**: open. Nothing is lost that was not already out of the commit; what is still on disk has one copy.
- **Raised**: 2026-11-27, by the run on the generic jobs pipeline (`llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief.md`), from the first run of its reconciliation, `python3 jobs/audit.py --rev b52a084f5d11`. Machine `vm-1`; no job ran for it.
- **Found**:
  - **What the receipts say.** A job that did not pass keeps its outputs under `results/ID/outputs/`, and its receipt lists them in `collected.kept`. 19 receipts of 2026-11-06 to 2026-11-20 list 947 such files that the pinned revision does not hold.
  - **Why the commit left them out.** 945 have a path the repository's ignore rules match: 655 are compiled classes (`*.class`, most under `outputs/verification/.work-NNN/`), 288 are under a `target/` folder (`outputs/lib/target/...`), and 2 are in a `__pycache__/`. 2 are over the 1 MiB a commit takes (`lib/target/benchmark-native.json`, twice; the limit is VF-020's and VF-025's). The collect commits succeeded and said nothing: an ignored file is not an error to a commit.
  - **Where the bytes are.** No original of them was sealed: the 19 jobs ran before originals were captured, or kept them with a collector that had no capture. 944 of the files, 10 MB, are still in the default checkout as ignored files of that one working copy. Three, of 2026-11-06, are in no checkout of this machine.
  - **By day:** 2026-11-06, 186 files; 11-07, 101; 11-08, 651; 11-14, 2; 11-20, 7.
- **Needs**:
  - **The watcher or the user, in the default checkout:** hand the 944 files to the private archive while they exist. `python3 jobs/audit.py --json` there lists each under `gaps` with the kind `artifact-not-committed`.
  - **The pipeline** (this run): a collect that keeps an output says so when the commit will not take its path, and the audit keeps counting what is still outside.
- **Tracked in**: this entry; [`jobs/README.md`](../jobs/README.md#the-baseline) for the baseline; the run's [results page](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md).
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): the tool to seal them exists and has not been run where the files are: `python3 jobs/pipeline.py recover --kept-outputs`, for the watcher or the user to run in the default checkout once this line lands (a run's agent changes nothing there). The audit goes on listing them as a gap until then.
- **Closes when**: the audit of the default checkout lists no `artifact-not-committed` gap without a sealed original, or the user decides the 947 are not worth keeping.

### VF-079: a session's trace line lands on commits it did not make

- **Status**: open, for the user to decide whether the rule changes. It did not come with the convergence on one run skill; it was seen twice during it.
- **Raised**: 2026-11-27 by the session that did the convergence on `/orchestrate-run` (`43b290ac…`).
- **Found**:
  - **The rule.** `sync.py` (`link_commits`) takes a session to have made every mutable ancestor of `@` whose author date falls while the session ran, and `@` itself while the session is live. Nothing ties a commit to the session whose command made it.
  - **Other sessions' commits.** The convergence's first commit was made on a line with three unpublished commits of that afternoon under it, and its sync put its session's line on all three: `kpvkzxtv` and `roktuvru` (allow-list proposals) and `ulxlynun` (the user's own approval of them, made from their terminal). Each now names three sessions (`6c5c7798…`, `e61d882b…`, `43b290ac…`), of which at most one made it.
  - **Another workspace's working copy.** At 19:20 UTC a sync of the session `43b290ac…` ran in the workspace `merge-fixes`, where another session was writing the change that lets `sync.py sync SESSION` render a session whose transcript is another workspace's (`oxqtlxmx`, on `develop` since that evening). The session was live, so that workspace's working-copy change was given its trace line, and the log the line names was stored in `merge-fixes` alone. From then on `check` failed in the session's own workspace with `log 614ccbcc12c9 is neither stored locally nor uploaded`, until `sync.py adopt-logs` brought the log over; it failed twice more the same way, on the next sync there and on the commit. The change was committed with the line, as were the three VF-077 commits under it. The rule is in the line's `sync.py` as it was: a sync of a live session from another workspace's transcript will do the same again.
- **Needs**: the user's decision between two readings of a trace line.
  - **Leave the rule.** A line then means "a session that was running when this was made", a commit with several lines does not say which of them made it, and [`llm-dlc/specification.md`](../llm-dlc/specification.md) should say so.
  - **Tie a commit to the session whose command made it:** the changes its own `sync.py commit` and its commit hook recorded, with the date window kept for a commit that has no line at all.
  - Under either, a session rendered from another workspace's transcript should not be given the rendering checkout's `@`.
    - **Done 2026-11-27,** by the advisor's change after `ynzzzokp`: `sync.py`'s `current_here`. Only the session running the command, or a live session whose transcript is the checkout's own, is given its `@`. A live session synced by name from another workspace's transcript is not. The rule for what a trace line means is still the user's to decide.
  - The three commits keep their lines: trace lines are not edited by hand.
- **Tracked in**: this entry.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): not addressed. What the pipeline now records for attribution is on the job, not on the commit: `submitted.run` and `submitted.session`. How a trace line lands on a commit stays with `sync.py`.
- **Closes when**: the rule is decided and written down, and a sync of a session from another workspace's transcript leaves that workspace's working copy as it found it.

### VF-078: a run's reported spend leaves out its last turns, and a run in a workspace of its own is in no published record

- **Status**: open, minor. Neither came with the convergence on one run skill: both were there before it, and it fixed neither.
- **Raised**: 2026-11-27 by the session that did the convergence on `/orchestrate-run` (`43b290ac…`), from the tools' code and from a rehearsal of them: one run on Claude Opus 5.5 at low effort, two cycles, in a throwaway copy of the repository. The copy and the run's transcript were deleted afterwards, as the user wished, so the rehearsal has no record here beyond this entry.
- **Found**:
  - **The spend a run reports is short.** `single_run.py` notes what a cycle cost when it puts that cycle's question to the watcher (`assessment`). A cycle that ends the run with no question, the last of its count or one ended by a stop, is never noted, and neither are the compact and the summary that close a run. The rehearsal's status said `spent: 0.19`, for its first cycle; the client's running total for the session stood at $0.63 after the summary. A long run that the watcher ends by an answer misses its last compact and its summary. One that ends by its count misses its last cycle too.
  - **A run in a workspace of its own is in no published record.** `sync.py` publishes the run records of the default workspace only (`llm-dlc/loop-summaries/`, redacted, under each session's `runs/`). `run_records.py collect` copies a workspace's records there, and nothing has called it since the streams workflow went ([`llm-dlc/retired.md`](../llm-dlc/retired.md#multi-agent-brief)). The queue's runs work in a workspace: on 2026-11-27 that workspace held 91 records of single runs, the default checkout held none, and `llm-dlc/traces/loops.md` counted no single run. The runs' sessions, commits and decisions are published as always; what is missing is the run as a unit: its cycles, how it ended, and its place in the loop statistics.
- **Needs**: product work, small, for whoever next works on run records (the architecture work that follows the convergence names "a run record with its measured cost" as the intent):
  1. Note the cost of every turn of a run, the last cycle, the compacts and the summary included, where the loop ends a turn and not where the watcher is asked.
  2. Have `single_run.py land` copy the run's records into the default workspace before its commit (`run_records.collect` does the copying), and decide whether the records already in a workspace are brought in once.
- **Tracked in**: this entry.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): not addressed by the jobs pipeline, and said where it shows: a result's `timing` reports queue wait, elapsed time, preparation and the requested steps with a state each (`measured`, `derived`, `partial`, `not-run`, `unknown`), and model spend is not in it: it belongs to the run's record, with its existing owner.
- **Closes when**: a run's reported spend equals the client's total for its session, and a run that worked in a workspace of its own is a row of `llm-dlc/traces/loops.md` after it lands.

### VF-077: the redaction review can't see what is already published, and values leave through encodings, wrapped lines and a person's pane

- **Status**: open (the user, 2026-11-27). The open findings are settled: an outside review found nothing secret. What stays open is the process.
  - **The 214, as of 2026-11-27:** all of them are now proposed and committed, by the queue's watcher.
  - **The user** is approving them, and then promoting, in their own terminal.
- **Raised**: 2026-11-27, by the user, from a review by an agent outside this checkout. Its session isn't under this repository's project folder, so it isn't published. It went through all 214 open findings:
  - it looked up each one's real value in the local finding-values file under `~/.local/state/llm-traces/`;
  - it read the redacted context, and decoded the encoded values;
  - it searched the 418 published logs.

  It wrote nothing into the repository. The advisor wrote this entry from its report, with the queue's watcher's own account of gaps 1, 6 and 7.
- **Found**:
  - **No credential or secret among the 214.**
    - **The 66 proposals:** every one was checked against its real value, and all are false positives. `fde27a45`, for one, is Spring test code that builds a cookie, not a cookie header.
    - **The other flagged values:** there was a list of open IDs to check one by one, with their masked output, taking an estimated 40 minutes. All of them are test or build output:
      - `f765fecb` is base64 JSON from a threetenbp test trace, not a JWT;
      - `ea0a3087` is UTF-16 base64 of test timestamps;
      - `fc1ee9fa`, `f15ea246` and `7ce5842e` are base64 of JavaParser file paths;
      - `a12825d0` and `97093444` are Gradle warnings with temporary-folder paths;
      - `57e1c50a`, `be7b7889` and `9f0e6b04` are Base58 test values and the Base58 alphabet;
      - `1ed07dd0` is a Debian source path;
      - 13 long strings in session `6c5c7798` are fragments of two encrypted Codex reasoning blobs;
      - the 20 "public IPs" are version numbers and RFC or JVM-spec section numbers, plus `192.0.2.1`, the reserved documentation address a sandbox check uses.
    - **The groups not yet proposed are harmless too:**
      - apt package-list cache names;
      - build-cache and branch names (`L05-…`, `P01-fix-<sha>`, `gradle-full-L15-<sha>`), some with a leading `n` left from an escaped `\n`;
      - Codex rollout file names, test and class names, temporary paths, decision ids and job names.
  - **One real redaction miss: `56b88bc7`, low risk.**
    - **What leaked:** a 160-character base64 string that decodes to a `file:` URL under the user's home folder. It's a threetenbp test artifact, printed by a test run in Codex session `01a20c2d-af08`.
    - **Why it slipped through:** the rule that turns the home folder into `~` reads only plain text, and this was encoded.
    - **Where it is:** 110 times in 56 published logs of `01a20c2d-af08`, and twice in `01a20dfe-f82d`. `review` doesn't list the second session at all (gap 2 below).
    - **The exposure:** only the account name, which is already public as the author of every commit and appears throughout `llm-dlc/allowlist.json` and `llm-dlc/index.json`.
    - **No other copy:** a search of the published logs for the home path, base64-encoded at every byte offset, found this value only.
  - **The process gaps, which matter more than any one value:**
    1. **A person's pane, captured into a published log.**
       - **What happened:** on 2026-11-23, session `6c5c7798` (the queue's watcher) read pane `main:1` with `tmux capture-pane` while the user was running `sync.py allow`. That command prints values unmasked, and `allow approve` prints every proposed value in full. The output is now in that session's published logs.
       - **The exposure so far:** wrapped at the pane's width, the capture became 14 new long-token findings, each appearing 586 times. They are fragments of two encrypted Codex reasoning blobs, so harmless, and `main:1` holds no unmasked value today.
       - **It happened again on 2026-11-27,** at a smaller scale. Tracing one of those findings, a masking step of the watcher's printed an unmasked 29-character fragment into its log. That is under the 40-character threshold, so no rule flagged it.
    2. **Nothing reviews what is already published.**
       - `check` fails only on errors, and it skips logs already uploaded, so a warning never blocks a push.
       - A finding that exists only in published logs never appears in `review`, so no person decides it.
    3. **The redactor reads line by line.** A value wrapped across lines, as a terminal capture wraps it, is caught on its first line only: the encrypted-blob rule caught the first line of each wrapped blob. The rest is flagged only as a long-string warning, and a wrapped API key would leak the same way.
    4. **Encoded forms of personal values are not matched.** The home-folder rule misses base64, and other encodings, of the home path.
    5. **Short session ids in `review` are ambiguous.**
       - The eight-character ids name several sessions each: `01a20c2d` matches 2 Codex sessions, `01a2134f` matches 7 and `01a212fe` matches 6.
       - The consequence: an agent that checks "one member of each family" can look in the wrong session.
    6. **`review show` is too slow, and shows too little, for triage.**
       - **Speed:** it takes about 4 minutes a finding (VF-070 item 6).
       - **Context:** for several families (`nL1…`, `M19…`) it printed no surrounding context at all, so a masked check couldn't classify them.
       - **The result:** on 2026-11-27, 214 open warnings stood before a promotion, about 150 of them unproposed. Settling them took an outside pass over the real values, because the masked path made judging each family impractical.
    7. **No read-only way for an agent to see `allow`'s usage.** The classifier rightly denied `sync.py allow approve --help` from the watcher's session, because `sync.py push` ignores `--help`. That leaves reading the source as the only way.
- **Needs**:
  - **The user's decisions** (only a person approves or accepts):
    - approve the 66 proposals, which the reviewer found all harmless;
    - accept `56b88bc7`. The reviewer recommends accepting it. Removing it would mean adding the encoded strings to `~/.config/llm-traces/redact.txt` and running `sync.py unpublish` on 56 or more logs, for no real gain;
    - say whether the masked checks of the list above should be dropped. Every value on it is resolved here.
  - **Fixes, one per gap:**
    1. **Keep sensitive output in a terminal agents don't read, and make commands less sensitive where possible** (the user's direction, 2026-11-27):
       - **Two places to work.** The user runs sensitive commands in a separate tmux session that agents never read. They run everything else in their usual session, where agents may read the panes, so that they can help and can see when work is done. An operating rule says so: agents read the user's usual session freely, and never read the sensitive one.
       - **Less sensitive by design.** A command that can be made less sensitive without losing what it is for is made so. For example, `sync.py allow` and `allow approve` print masked values by default; unmasking takes an explicit flag, and only the unmasked output belongs in the sensitive session.
       - **Commands that say what they are.** A command whose output may hold a real value is designated sensitive, for instance in its usage text. When it runs outside a terminal of its own, it says so before it prints. That way the user and agents know which session it belongs in. Most commands stay ordinary, and run where agents can watch.
    2. **Show published-only findings in `review`,** marked as already public, so that a person decides them like any other.
    3. **Match values across a wrap.** When a rule matches a value at the end of a line, check the next line for its continuation, as a terminal wraps a long token.
    4. **Match encoded personal values.** Add rules for the home path base64-encoded at each of its three byte offsets, plus any other encoding a run is seen to print. Then rescan, with `sync.py stamp`.
    5. **Make the ids `review` prints unique,** and accept any unique prefix.
    6. **Make triage practical:**
       - `review show` gives the context of every occurrence in seconds, not minutes (with VF-070 item 6);
       - `review` groups a family of findings by its pattern, so that one decision with a reason covers the family.
    7. **Make every `sync.py` subcommand honour `--help`** and print its usage without acting (the hazard in the `sync-push-ignores-help` note).
- **Tracked in**: this entry. Gap 4 is related to VF-070 item 5, which aims to treat run-made names as non-secret.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): one item of it is built: a new job carries the run its submitter works in (`submitted.run`, read from the loop's systemd scope, apart from the source revision and from who collects), and the lifecycle view gives the ids of the occurrences sealed in the private archive and nothing of their content. The redaction review itself is as it was.
- **Closes when**:
  - the user has decided `56b88bc7` and the 66 proposals;
  - each of gaps 1 to 7 has a fix, with a test, or is dismissed by the user.

### VF-076: a domain run meets offline gaps the setup never resolved, and only a job that fails finds each one

- **Status**: open, product work (the user, 2026-11-27). The user let the run retry, because each try was cheap and the work underneath valuable, and asked for this finding afterwards.
- **Raised**: 2026-11-27 by the watcher, at the user's request, after the Spring Boot S01-S50 domain run (entry 27, Codex Astra, session `c3caedf3`).
- **Found**:
  - **What the setup resolves:** the setup phase resolves online, and checks offline, what the setup itself builds: each case's modules and their transitive closure, at both pins (98 checkouts, after a second pass). That is what its 49 build jobs needed.
  - **What the domain run needed beyond it:** the domain work reached tasks the setup never ran. Its Maven WAR check ran the Spring Boot Maven plugin's own integration harness, which builds the dependency BOM and prepares Maven binaries. Verification jobs run offline, so each missing artifact failed a job:
    1. `20261127-141531-inspect-maven-repackaged-spring-boot-{fix,par}`: `createResolvedBom` needed `org.apache.activemq:activemq-bom:6.1.8`, not cached.
    2. `20261127-142145-resolve-the-pinned-maven-boms-from-the-r`: the same goal, with the BOMs resolved locally, still failed.
    3. `20261127-142917-read-retained-pom-bytes-at-the-original`: the retained POM route failed in 3 s.
    4. `20261127-143502-run-both-original-maven-war-builds-with`: past the BOMs, `prepareMavenBinaries` needed `org.apache.maven:apache-maven:3.9.13`, not cached.
    5. `20261127-145103-read-both-original-maven-wars-with-a-pin`: passed, with a replay script that fetches the published Maven 3.9.13 archive itself and builds a local mirror from the setup's caches.
  - **The cost:** five jobs of 1 to 5 minutes and about 45 minutes of the run's time, each finding only the next gap. Setup phases had the same pattern: S's first 41 builds failed on modules outside each case's own (VF-070, items 11 and 12).
- **Why it happens:** the setup can't know which tasks the domain work will reach, and a domain agent can't resolve anything online inside a job. So the only way it finds a gap is to fail a job, one artifact at a time.
- **Needs** (directions, none chosen):
  1. **An ad hoc setup agent during runs** (the user's suggestion): a domain run records a request to resolve named tasks or artifacts online, and a setup-role session (or a tool run by the watcher) resolves them, verifies them offline and returns, while the domain run waits or works on other cases. It fits VF-072's worker request.
  2. **A resolution job:** a job kind allowed network access only to the dependency repositories, which resolves a named Gradle task's or Maven goal's dependencies into the shared offline cache and verifies them offline. A domain agent submits it like any other job.
  3. **Wider setup resolution:** the setup also resolves the build-plugin integration paths a brief's claims name (here the Maven plugin's harness), at a cost in setup time.
  4. **A first failure that names everything:** a job's offline failure lists every missing artifact of the task, not the first one, so one resolution pass covers it.
- **Tracked in**: this entry; VF-070 for setup phases; VF-072 for the worker request.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): direction 2 is built, and its closure evidence is not in yet. A job can need a readiness operation (`submit --needs-readiness`, [`jobs/readiness.py`](../jobs/readiness.py)); it waits alone while a resolution job, admitted by the watcher's commit, runs the task offline in rounds, fetches what each round asks for from the sources the runner authorises, and publishes a bundle with a receipt that wakes it. On a made-up nested build one request took three rounds and no failed consumer job (`jobs/test_delayed_setup.py`). S48 itself is replayed inside one job. Its first run (`20261128-000950-replay-s48-s-delayed-setup-as-one-reques`) passed 10 of 13 checks: the one request, the consumer waiting alone while an unrelated job finished, the admission, the offline sandbox and three controls (the BOM withheld, a wrong digest for Maven, a repository that does not answer) held, and the resolution stopped in its second round because the gate's own view of the cache was inconsistent for Gradle; the corrected run, job `20261128-003144-replay-s48-s-delayed-setup-as-one-reques`, passed all 17: one resolution job, two offline rounds (the Maven distribution by its pinned digest, then the BOM's POM once Gradle named it), four WARs read by a fresh offline consumer on both pins and equal to the committed readbacks, and no failed consumer job. The files' dates also correct item 1 above: the BOM had been in both caches since the setup phase (07:47 and 07:53 UTC), so `createResolvedBom` failed on Gradle asking a repository that had not supplied it, not on an absent file; only the Maven distribution was absent. The status stays open: it closes on a domain run, and none has used this yet. Direction 4 is not built: the resolver reads what each offline round names, not all of a task's needs at once. What it fetches is laid in Maven's layout, which a Gradle build does not read by itself: every readiness view carries an init script that gives the build a file repository over the fetched modules, and with it an ordinary Gradle build passed a gate of its own (job `20261128-012905-a-gradle-build-reads-offline-a-library-t`, 14 of 14 checks: Spring Boot's core module compiled offline, with a library taken out of every cache, named by Gradle, fetched with its module metadata, and read from that repository). The S batch's offline misses were of that kind.
- **Correction 2026-11-28, later the same day** (the run's fourth cycle): the passing S48 run above did not show the task ready on prepared inputs alone. A review found that the offline run took the network away and left the runner's home directory readable, and when the sandbox was made to give a task an empty home ([`jobs/sandbox.py`](../jobs/sandbox.py), `alone`), S48's gate failed, 10 of 13 checks (job `20261128-023123-replay-s48-s-delayed-setup-as-one-reques`): the Spring Boot build's own Maven run reads `org.apache.maven.plugins:maven-plugin-plugin:3.6.1` from Maven's default local repository, and the earlier runs had found it in `~/.m2/repository`, 770 files that the S setup's online job for S48 left in the home on 2026-11-27 and that no record names. That is a second kind of gap beside the one this finding was raised for: an input a setup fetched into a place it never recorded, which every later offline job then depends on unseen. With that folder declared as something the task reads, copied with the digest of its tree and laid into the empty home, the gate passes, 17 of 17 (job `20261128-024257-replay-s48-s-delayed-setup-as-one-reques`): S48 is shown ready by one request on the base, the bundle and that one declared folder, which no resolution fetched and nothing verified. An ordinary Gradle build passes under the clean sandbox (job `20261128-023123-a-gradle-build-reads-offline-a-library-t`, 14 of 14). And the control VF-070 describes was replayed for real on some S cases, from the cache as the setup's first pass left it ([results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md#the-s-batchs-first-setup-as-a-control)).
- **Update 2026-11-28, after the run landed** (with the user): the declared folder is verified now. The user chose to have the home's Maven repository read against a digest rather than leave it as a path nothing vouched for: an entry of an operation's `reads` may name the digest of a file or of a folder's tree, which is checked before a resolution's first round and before a job is handed the bundle ([`jobs/readiness.py`](../jobs/readiness.py), `check_reads`). S48's operation names the copy's digest, and its gate passes 21 of 21 (job `20261128-134250-replay-s48-s-delayed-setup-as-one-reques`), a control with another digest withheld at the base stage among them. The 770 files are thereby known to be the same bytes at every run; they are still fetched by no resolution, which waits for a fetch phase the build tool drives. The same day the machine's runner was given the sources it may fetch from (Maven Central, the Gradle plugin portal, Gradle's distributions, repo.spring.io; the user's decision), and a job that needs another source now waits and asks: `python3 jobs/pipeline.py sources` lists what is asked for, and `sources allow URL` is a person's command. The status is unchanged.
- **Closes when**: a domain run that needs an unresolved task gets it resolved by one request or job, verified offline, with no chain of failing jobs.

### VF-075: a brief author drops the second observation that changes one input, leaves orders open, and picks heavier observations than needed

- **Status**: open, waiting to be observed. The rules are landed (change `ntuqprsk`, 2026-11-27); the next generated list that has a rationale file shows whether they worked.
- **Raised**: 2026-11-27, by the user, from their comparison of six generated briefs (the lists L, N, O, P, Q and R, 155 cases) with rationale files they wrote. The brief is [`brief-generation-quality-takeaway.md`](../llm-dlc/loops/brief-generation-quality-takeaway.md), which has the counts. The rationale files and the comparisons are private and held out as controls for later briefs: no agent looks for them, and the counts in the brief are all this entry uses.
- **Found**:
  - **The actor and the phase.** The brief author (`single_run.py generate`, Codex Astra 6.2 at ultra effort), writing a brief from a list of pull requests, with the two texts of `llm-dlc/loops/brief-generation-template.md` around the user's handoff, as both stood from 2026-11-25.
  - **What held.** It misread none of the 155 cases and missed none, and was sharper than the rationale in 99 of them. Quality and generation time were flat up to 50 pull requests, so the limit on a list's size lies in setup and verification.
  - **What went wrong, the same way in every batch:**
    1. **The second observation that changes one input** (a reversed order, the other direction, a mixed argument) was dropped or blurred. In P, Q and R, 33 of 110 were kept, 62 partly kept and 15 dropped. In O, 9 of 20 were dropped. Of the 21 order variations in P, Q and R, 13 were dropped.
    2. **An order oracle was weakened** three times: "either order", or a check as sets, where the behaviour defines an order.
    3. **Heavier observations than needed** (databases, JMS, child processes) where a smaller public call would show the same: in Q, and in three cases of R. That costs setup time, which is the bottleneck (VF-070).
  - **What went right without being asked.** The author added 18 predictions of its own that the merged code is still wrong, and several were real upstream defects (VF-065).
  - **The cause.** A gap in the instructions, not overload: the rate does not vary with the size of the list.
    - The handoff asks for an intent, a control and a challenge, and its challenge varies "something the contract says should be irrelevant". Nothing asked for a second observation that changes one input that matters, so it was written only when the author thought of it, and often inside the challenge.
    - Nothing said when an order may stay open, and nothing weighed what an observation costs to set up.
    - The verification agents won some second observations back on their own, but not reliably: they decide the claim rows a brief has.
    - Nothing on the queue or on another line treated it.
- **Landed** (change `ntuqprsk`):
  - **The owner.** `llm-dlc/loops/brief-generation-template.md`. The handoff is the user's and is unchanged. `single_run.py generate` renders the template as before, with no new placeholder.
  - **Four rules for each case**, in the first text in full and in the continue message in short, since a later cycle starts after a compaction with the continue message alone:
    1. a claim row with the role `Variation`, beside the handoff's control and challenge: it repeats the case's main observation with exactly one input changed, names that input, and says what each revision should do; where the behaviour depends on order, it is the reversal;
    2. where the code under change produces an order, that order stated and checked, with no "either order" and no comparison as sets; an order stays open only where a contract the author names leaves it unspecified;
    3. the cheapest observation that shows the change: a plain public call on the shipped API before a database, a message broker, a server or a child process, and a heavier one only when the change can't be seen without it, with the reason in the case's technical notes;
    4. a claim row with the role `Remaining defect`, with an observation of its own, wherever the landed code still looks wrong to the author.
  - **Why rows with a role.** The agent that verifies a brief decides every claim row, so a second observation that is a row is verified, and one that is prose is verified by luck. The two roles also make the rules countable.
  - **The author's own check.** Its check before a cycle ends covers the four rules. With "The brief is complete" it gives its counts, and writes them into its record (`NAME-brief-generation.md`): the `Variation` rows and how many are reversals, the orders left open, the observations that need more than a public call, and the `Remaining defect` rows.
  - **A count by the queue.** `brief_queue.py rules FILE` counts what a written brief shows of the rules: the cases with a `Variation` row and those without, the `Remaining defect` rows, and the cases whose words leave an order open. The `brief` step of `next` gives the same count for a generated brief when it queues it (`caseRules`, a line for the user, and the queue's log). It refuses nothing: whether a row keeps its rule takes reading the case.
  - **The acceptance test.** The rules are tested in the texts an author is given, not in the template file:
    - `test_single_run.py`, `TheGenerationPhase.test_both_texts_give_the_brief_author_the_four_rules_for_each_case`: both texts as `generate` renders them hold each rule, by the words that carry it (`CASE_RULES`);
    - the generation test there reads the text the Codex stand-in was started with, and the run's continue message;
    - `test_brief_queue.py` reads the first prompt and the continued prompt of an author the queue started, and the count the `brief` step gives.
    - The failing fixture: the texts rendered from the template before the change lack all four rules, in both. The control: a text without the rules is told from one with them rule by rule, and a brief that keeps the rules has nothing named by the count.
  - **The baseline**, by `brief_queue.py rules` over the nine generated briefs on the line (235 cases): no `Variation` row and no `Remaining defect` row, as neither role existed, and 13 cases with words that leave an order open (the first list 2, L 4, P 1, Q 2, R 4).
  - **Not shown yet.** That an author follows the rules. The tests show what it is given, with stand-ins for the clients. The author's session is persistent, and the briefs it has written so far were written without the rules.
- **Needs**:
  - **The user:** on the next generated list that has a rationale file, repeat the comparison the same way. Count the second observations kept, the order reversals kept, the oracles weakened and the heavier-than-needed observations. The aim is most second observations kept, every reversal kept and no weakened oracle, with still nothing missed or misread. The places to look: the `Variation` and `Remaining defect` rows of each case, the technical notes for a heavier observation's reason, the author's counts in the generation record, and the queue's count.
  - **The watcher:** pass the queue's line and the author's counts on to the user when a generated brief is queued.
  - **To watch in the first brief written under the rules:**
    - a case now has four claim rows or more, where it had three. The `Variation` row reuses the main observation's call and fixture, so setup should not grow, but the domain run decides more claims: compare its time for each case with the earlier batches;
    - whether rule 3 costs sharpness: a public call that shows less than the database did is a weaker observation, not a cheaper one.
  - **This session's log** (decided by the user, 2026-11-27): the session read the advisor's memory notes at its start, including the notes on the control files, and its transcript holds them. Nothing from them is in the change. The user decided the log is published as it stands. This session runs no jobs, and the user would rather it had the context.
- **Tracked in**: this entry, and the note at the head of `llm-dlc/loops/brief-generation-template.md`.
- **Closes when**: the user's comparison of the next generated list that has a rationale file meets the aim above. If one rule did not hold, the entry narrows to that rule.

### VF-073: VF-058's remainder, reopened (a placeholder)

- **Status**: open, a placeholder (the user, 2026-11-27). The user asked for VF-058's strict-native remainder to be reopened. This entry holds the number so that it isn't taken for anything else. Its scope is written when the user takes it up.
- **Raised**: 2026-11-27 by the advisor session, at the user's request. The user first asked on 2026-11-24, after the tk-recovery agent moved VF-058 to "Decided and closed".
- **Found**: see VF-058. That campaign's decision left four frontiers open:
  - the Commons Configuration startup question, at the `Properties` object `System.getProperties()` returns;
  - 6 of JavaParser's 8 ordinary strict-native claims, with arbitrary separator values owned by the native JVM startup model;
  - all 34 unrestricted paired overloads of the historical receiver cohort;
  - native scheduling from the worker's `Thread` constructor, tracked in VF-056.

  On 2026-11-24, strict native decided 4 of 46 sides and 2 of 23 pairs.
- **Needs**: the user's scope: which of those frontiers to reopen, and in which brief or model.
- **Closes when**: the user writes its scope here, or withdraws the reopening.

### VF-074: the README's table of sessions shows finished sessions as open, and long-running sessions under their first topic

- **Retired (2026-11-27, change `kkkqupww`):** this entry names `run-brief`, which is no longer in the repository. See [`llm-dlc/retired.md#multi-agent-brief`](../llm-dlc/retired.md#multi-agent-brief) for what replaced it and the last commit that has it.
- **Status**: settled 2026-11-27 by `qlssntwx`, merged at the user's request: a rendering sync ends idle sessions, and standing sessions have their own table (both shown after the merge). Earlier: open (the user, 2026-11-27).
  - **The scope:** both problems, plus cleaning up the rows already affected.
  - **Numbering:** VF-073 stays reserved for the user's reopening of VF-058.
- **Raised**: 2026-11-27 by the advisor session, at the user's request, on develop `a380879e6426`.
- **Found**:
  - **Finished sessions marked open:** the generated table in `llm-dlc/README.md` (between the `index:begin` and `index:end` lines) marks 15 sessions `open`. Two of them really are still running. The other 13 ended between 2026-11-06 and 2026-11-27.
  - **Why the status sticks:**
    - **The rule:** `sync.py` sets a session's status when it syncs it. A transcript written less than `LIVE_SECONDS` (600 s) before is `open`; anything older is `ended`.
    - **How a session's last sync happens:** a session that ran in another jj workspace is last synced by that workspace's commits. Its final commit comes while it is still running, so its manifest says `open`, and that is the manifest the merge brings to develop.
    - **Why nothing corrects it:** the default workspace syncs only the transcripts of its own Claude Code project folder (`claude_project_dir()`, `session_transcripts()`; `transcript_of()` looks nowhere else) and its Codex rollouts. It never reads those sessions again, so nothing marks them `ended`.
  - **The 13 stale rows, by where their transcripts are:**

    | Session | Folder | Last written |
    |---|---|---|
    | `e73cfdaf`, the S01-S50 setup run | foundation-domain-streams | 11-27 12:45 |
    | `b9b56f5e` | dlc-plumbing | 11-21 22:19 |
    | `f28025bc` | domain-advances-preservation | 11-18 03:22 |
    | `f8bc7b54` | domain-advances-challenge | 11-18 02:06 |
    | `9896d870` | domain-advances-state | 11-18 00:13 |
    | `7ece8184` | domain-advances-evidence | 11-17 17:07 |
    | `4a47a539` "Recent sessions summary" | stream-conductor | 11-14 21:50 |
    | `3bb5a1f4` "Application-core feature streams exiting early" | example-targets-runtime | 11-14 18:25 |
    | `aa238023` "Multi agent feature stream run" | application-core-reuse | 11-08 11:57 |
    | `a8cc612f` | cleanup-jbmc | 11-07 21:29 |
    | `750c8a36` "Next multi-stream loop draft" | heap | 11-07 12:21 |
    | `7b8a1d3b` "Feature loop run review actions" | jbmc | 11-07 00:11 |
    | `0e86a358` "setup-repo-on-ryzen-machine" | none on this machine: it came from another one | 11-06 |

    Several of those workspaces no longer exist, but their transcripts are still under `~/.claude/projects/`.
  - **Long-running sessions under their first topic:** the two sessions that really are open are standing sessions, continued for days.
    - **The advisor** (`e61d882b`) is titled "/run-brief invocation options". It started 2026-11-17.
    - **The queue's watcher** (`6c5c7798`) is titled "Moonshot loop status". It started 2026-11-15.

    A row's title comes from the session's start, so a reader can't tell what these sessions are now, or that they are meant to stay open.
- **Needs**:
  1. **A status that stays true.** When syncing, find sessions whose manifest says `open` but whose last activity is older than `LIVE_SECONDS`, and mark them `ended`. Do this for every Claude Code project folder of this repository's workspaces, not only the current one.
     - **Where the transcript still exists:** re-render the session from it, through `sync.py` as any session is rendered, never by editing `llm-dlc/traces/` by hand.
     - **Where it doesn't (`0e86a358`):** go by the stored log and the manifest's own last activity.
  2. **Clean up the 13 rows above** with that same code, in one commit through `sync.py commit`. The README table and those sessions' generated files are rewritten. Report any redaction finding the re-render raises, as for any log.
  3. **Show the standing sessions apart from the ordinary rows (the user's direction).** The advisor and the queue's watcher belong in a list of their own beside the table, under their roles, rather than among the ordinary rows with first-topic titles. That list shows each one's role, when it started, and that it is meant to stay open.
     - **Recording a role:** either an explicit role, recorded by a command a person or watcher runs, or one derived from the run records (the queue's watcher session, `brief_queue.py` defaults).
     - **Ending a role:** a session that stops holding its role returns to the ordinary table.
  4. **A test for each:**
     - a session synced while live in another workspace's folder is shown `ended` once it is idle;
     - a standing session is listed under its role and not as an ordinary row.
- **Tracked in**: the advisor's backlog (item 11).
- **Closes when**: no session idle for longer than `LIVE_SECONDS` is `open` in the table, the 13 rows above read `ended`, and the advisor and the watcher appear under their roles.

### VF-072: run agents lack the direction and the tools for fan-out, sealed producers and model-driven workers, so they reach for the run skills

- **Retired (2026-11-27, change `kkkqupww`):** this entry names `multi-agent-brief` and `run-brief`, which are no longer in the repository. See [`llm-dlc/retired.md#multi-agent-brief`](../llm-dlc/retired.md#multi-agent-brief) for what replaced them and the last commit that has them.
- **Status**: open, a refactor (the user, 2026-11-27). VF-045's enforcement is done (see there); this is the cause it treated.
- **Raised**: 2026-11-27 by the advisor session at the user's request, after two queued runs reached for the run skills in one day.
- **Found**:
  - **The incidents** (details in VF-045):
    - two Codex workers read the run-brief skill on 2026-11-19;
    - the R01-R50 setup (Claude Opus 5.5, 2026-11-26) split 50 cases across 4 subagent forks and ran 43 builds inline (VF-070 item 12);
    - entry 25's agent started `blind-public-five-links`, a Codex `gpt-6.2-sol` run, itself on 2026-11-27, for its brief's part C;
    - entry 27's agent began with "I'll use the multi-agent brief skill" the same day.
  - **What each one wanted is real, and the product has no sanctioned way to give it:**
    - **Fan-out and wait.** Batches have 30 to 50 cases. The pipeline runs jobs in parallel, but one job per case means one hand-written `pipeline.py submit` per case, and waiting is improvised: `xargs -P` lanes, subagent forks, hand-written waits that match themselves (VF-069), and builds run inline.
    - **A sealed, independent producer.** Blind measurement needs a producer that cannot see the evaluator's files. Entry 23 built a filesystem allow list for it, and entry 25 built neutral packets, seals and `numbered_handoff.py --scaffold-only`. The pipeline's export of a commit into a fresh work folder is most of such a view, but nothing restricts what it can read.
    - **A model-driven worker.** Intent recovery from a PR URL (VF-063) needs a fresh model session. That is a paid session, and a run's agent has no way to ask for one. So it starts one itself or goes looking in the run skills.
  - **Wording points the agents at the run skills:**
    - the queue's domain prompt says "Review and implement `X-brief.md`", which matches `multi-agent-brief`'s description;
    - product briefs say "the watcher" and "the ordinary single-agent run" for the product's own Stage 2 and 3 workflow (entry 25's brief told its agent to "use the ordinary single-agent run");
    - the 11-19 prompts said "written for multiple agents".
  - **Related:**
    - the S01-S50 setup's dry runs did not cover the test tasks, and 41 of 49 setup jobs failed offline;
    - a setup job passed without running tests (VF-070 item 11);
    - the URL producer's model calls stopped on the client's cybersecurity filter (VF-061).
- **Update, 2026-11-27, the convergence on one run skill** ([`llm-dlc/retired.md`](../llm-dlc/retired.md)): the streams' skill and the proof run's skill are removed, so the queue's domain prompt no longer matches a second skill's description, and the one run skill, `orchestrate-run`, is the user's alone to start in Codex. That removes what the agents reached for. It gives them none of what they wanted: the needs below are untouched.
- **Needs** (product work, in order; the advisor's write-up `~/.cache/in-the-loop/advisor/agent-started-runs-writeup.md` has the evidence and acceptance tests for each):
  1. **Fan-out from a manifest.** `pipeline.py submit --cases FILE` writes one job per case from a step template. The documented wait is that a run agent ends its turn naming the job ids, and the watcher's `single_run.py jobs` waits. Acceptance: a 49-case setup submits its builds with one command and builds nothing inline.
  2. **Sealed producer jobs.** A job option that exports the commit with an allow list and a deny list of readable paths, runs a frozen producer, and records a digest of what was visible. Acceptance: a read of an evaluator-only marker fails inside the job.
  3. **A worker request.** A run's agent records a request for a model-driven worker (purpose, client, model, budget, inputs) and starts nothing. The watcher puts it to the user, and on approval starts a linked child run with its own record and cost. Acceptance: part C's five-link producer runs this way, with no agent-started run.
     - **The user's direction, 2026-11-27 (to revisit after the PR-URL review):**
       - **Unattended.** A worker request may run unattended. The user would rather fix a bad worker later than stall a run overnight.
       - **Warn, don't block.** A request outside the allow list of worker kinds and limits doesn't wait. It warns at once, in the watcher's next report and in the run's record, so drift is caught early.
       - **Delegated authority.** The watcher has delegated authority to handle named items itself: start approved worker kinds, and stop or restart a worker within limits. The list of items and limits is still to be written.
     - **The producer's client (decided: Astra keeps the judgment, 2026-11-27):**
       - **The evidence.** Entry 25's blind producer was deterministic, and 18 of its 20 stops were at the functional review, the intent judgment. Astra (ultra) already makes that judgment when it writes briefs from PR lists: the batches verified from those briefs held 486 of 506 merged predictions, with no filter stops across seven generations. The filter stop came during part C's replay, on Sol at high effort.
       - **The proposal.** Astra keeps the intent and registration judgment. The mechanics (pinning, preparing, binding, generating, replaying, evaluating) run as tools and verification jobs, not in a model session. No fallback to another model or client when the filter stops a case: even with good intentions that goes around the filter and risks triggering it again (the user, 2026-11-27). On a filter stop, the run records a finding (the case, the step, the stop text; VF-061), leaves that case unfinished with no retry of the same material, and carries on with the rest. The harness is fixed afterwards, to keep such work within the rails. Prevention has the greater return: the judgment stays in the model, and execution runs in tools and jobs.
  4. **Wording.** Domain prompts say "the plan in X"; product briefs and the brief-generation template name the product workflow, never "watcher", "single-agent run" or "multi-agent"; `brief_queue.py add` warns on those phrases.
  5. **Machine-wide run visibility.** `single_run.py list --all` and the doctor show every `feature-loop-*` scope, in every state, with its root.
  6. **Setup hygiene.** Setup dry runs cover the test tasks, and a setup job fails when no test ran.
- **Tracked in**: this entry; VF-045 for the enforcement; the write-up named above.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): the fan-out part is built and not yet used by a campaign: `python3 jobs/pipeline.py submit --manifest` writes one ordinary job for each row of a validated manifest with a published map from rows to jobs, `wait --batch NAME` is the typed wait, and `batch NAME` the report ([`jobs/README.md`](../jobs/README.md#a-batch-from-a-manifest)); a made-up batch of 49 rows was interrupted, submitted twice, run, watched, collected and one row resubmitted (`jobs/test_fanout.py`). The sealed producer and the request for a model-driven worker are not touched. The status stays as it is: it closes on a real 49-case setup that builds nothing inline.
- **Closes when**: a 30-to-50-case batch fans out, a blind producer runs sealed, and a model-driven worker runs at the user's word, all through these tools, with no agent reading a run skill to find them.

### VF-070: what stops or slows an unattended setup phase: a register from the organic PR queue of 2026-11-25 and 26

- **Status**: open, a register to address later (the user, 2026-11-26). Each item says what happened, what it cost and a direction for a fix; none is chosen yet. Items with a finding of their own point to it.
- **Raised**: 2026-11-26, by the watcher, from the advisor's draft, at the user's request. Facts from the watcher's product notes (`~/code/scripts/analysis/watcher-notes/organic-product-notes-2026-11-25.md`).
- **Found**: the queue ran setup phases (Claude Opus 5.5, `single_run.py setup`) for the generated briefs of entries 7 and 15 to 19 (L01-L20, M01-M10, N01-N05, Spring O01-O20, Spring P01-P30). Each was unattended between the watcher's verdicts, and most were held up at least once by one of these.

#### Blockers: the run stopped until a person acted

1. **A self-matching wait loop**, `until ! pgrep -f 'PATTERN'`, whose own command line matches PATTERN, so it never ends. Five occurrences:
   - L setup;
   - M setup, 36 min (21:04 to 21:40), ended outside the watcher's session after the classifier refused the watcher's kill;
   - the advisor's monitor;
   - O setup, on `case_job.sh O..`, 46 min;
   - P setup, on `review show`, not blocking; it timed out.

   **See VF-069.** The operating-notes rule ("Waiting for a command to finish") exists, but was not followed. Since 2026-11-26 the user lets the watcher kill such a loop by PID, within limits.
2. **A leftover daemon kept the run's systemd scope alive.**
   - After Spring P's first setup leg ended (04:15 UTC, 2026-11-26), the setup's private GnuPG keyring left `dirmngr --homedir ~/.cache/in-the-loop/spring-pr-links-p01-p30/gnupg --daemon` (pid 1993751) in `feature-loop-single-spring-framework-pr-links-p01-p30-brief-setup.scope`. The agent had stopped `gpg-agent` but not `dirmngr`.
   - `single_run.py start` refuses while that scope is active, and the restart at 04:35 ended at once with status 1. The classifier refused the watcher's `systemctl --user stop`, and the delegation covers only wait loops.
   - The queue stood idle for **about 7 h 50 min** (04:35 to ~12:23), until the user stopped the scope.
   - **Direction:**
     - the loop ends its scope when a leg ends (`systemctl --user stop`, or `KillMode=` on the scope);
     - or `single_run.py start` stops a scope that holds only known helper daemons (`dirmngr`, `gpg-agent`, `keyboxd`);
     - and the setup template has agents run `gpgconf --homedir DIR --kill all` when they finish with a private keyring.
3. **Build inputs that exist in no public repository**, so a historical build can't be configured.
   - **Affected cases:** Spring O11 and O14, and Spring P's seven 5.x cases (P05, P09, P11, P16, P18, P19, P23).
   - **What they need:**
     - `propdeps-plugin` 0.0.8 or 0.0.9.RELEASE;
     - `docbook-reference-plugin` 0.3.1;
     - dokka `integration` 0.9.15;
     - `spring-asciidoctor-extensions` 0.1.3.RELEASE;
     - `gradle-enterprise-conventions` 0.0.2;
     - Kotlin 1.4-M2 or other Bintray artifacts.

     These were served only by `repo.spring.io`'s private repositories (now 401) or by Bintray (closed in 2021). L15's Gradle `grolifant` 0.16.1 was found on a JCenter mirror with the pinned hash.
   - **How the cases went:** each case asked the user for a decision: credentials (unrealistic) or released jars.
     - Spring O's domain run settled it itself (60/63 claims decided): it compiled the pins' exact changed sources against released dependencies, labelled separately.
     - For Spring P the user decided on 2026-11-26: "Stuff that cannot be built should be verified against pinned JARS like Spring 0." The setup then built each 5.x pin's changed files into a slice against a pinned release. All seven cases behave as their PRs say: the fix's tests pass on the fix slice and fail on the parent slice, and fail the same way on the plain release. The slices' class digests repeat over two runs.
   - **Direction:** make the user's P decision the standing policy of the setup and domain templates. When a historical build can't be configured from public sources, use (a) a byte-identical artifact from a public mirror with the pinned hash, or else (b) the pin's exact changed sources compiled against the nearest pinned release, labelled as such. It is then decided once, not once per case.

#### Slowdowns: the run went on, but slower or noisier

4. **Commits took 5 to 15 minutes.** A sync cache shared between workspaces made every session re-sync on every other commit. **Fixed** by srqoyurr (merged 2026-11-25, develop 661006fa): commits and lands now take about 80 to 140 s. The item stays here only as the reason agents backgrounded commits, which is what set up item 1's waits.
5. **Allow-list churn from the runs' own names.**
   - **What was flagged:** setup and domain agents spent turns proposing false positives found in their own logs:
     - "long token" for artifact file names they created themselves (`L05-junit-framework-…jar`, 10 at once);
     - "public IP" for version strings (Liberica `17.0.21.1`, four-part Jackson versions), an RFC section number and long Java classpaths.
   - **Where it stands:** each proposal waits for the user's `allow approve`, since delegation is off. About 29 are pending, and 29 more sit uncommitted in the P setup's workspace.
   - **Direction:**
     - the redaction rules recognise dotted version strings in a version context;
     - they treat file names under the run's own cache folder as non-secrets;
     - or setup agents name their artifacts so they don't trip the long-token rule.
6. **`sync.py review show` takes over 200 s a finding**, and setup agents look at each warning masked before proposing it. That wait is also what item 1's P occurrence waited on. **Direction:** profile it as was done for commits; a batch `review show ID ...` would also help.
7. **Job results land on another head.** The pipeline collects a setup's jobs on the default line, not in the run's workspace.
   - Agents then read them "from the head where it recorded them" (P's 24 results: `933de3d18d34`).
   - One agent (M) waited for a commit instead.
   - **Direction:** `single_run.py jobs` (or the setup template) tells the agent where its collected results are, or the watcher moves the run's workspace onto the line before continuing it.

#### Inputs that limit evidence: recorded, not blocking

8. **Expired snapshot dependencies.**
   - Jackson's pinned `3.2.0-SNAPSHOT` parent is gone from the snapshot repository, so it was rebuilt from nearby upstream commits.
   - Reactor's `2020.0.0-SNAPSHOT` survives only as a later build.

   These are recorded per case, and need no fix beyond the label.
9. **Signature checks that can't be completed.**
   - Spring's signing key `9A2C7A98E457C53D` comes back from keyservers without user IDs and can't be imported, so the 5.x release jars' signatures are unchecked; their SHA-1 hashes match.
   - RxJava 2.1.14 and 2.1.15's key is revoked as compromised.
   - Solr 9.8.0 is signed by an expired key.

   These are recorded per case.
10. **Disk taken by setup caches.**
    - `~/.cache/in-the-loop/spring-pr-links-o01-o20` took 17 to 24 GB, and `…-p01-p30` 29 GB before its agent cut it to 25 GB.
    - The cache folder was 125 GB on 2026-11-26.
    - Nothing prunes a setup's build outputs once its brief is verified, and examples' replays may still read from them.
    - **Direction:** a per-batch prune step after the domain run lands, which keeps what the replays reference (grep the repository for the path first).

#### Added 2026-11-26 from the R01-R50 setup

11. **A setup job that passed without running a test.**
    - `20261126-172339-setup-build-junit-at-both-pins-of-5839-a` (R49 and R50) reported `passed`, 8 of 8 steps.
    - R50's three offline builds had stopped at the Groovy test compile, because 13 Groovy 4.0.26 modules that Gradle fetches only at compile time were not in the cache.
    - The agent's `junit_job.sh` exited 0 whatever the build did, and the job's expectations did not check that tests ran. The Calcite job's script had the same shape.
    - The setup agent caught it by reading the logs, fixed the resolution and the script, and queued a rerun (`20261126-180537-setup-rerun-junit-4466-r50-at-both-pins`).
    - **Direction:**
      - the setup template and `pipeline.py submit` require each build step to state a test count it must exceed, and a job whose steps ran no tests is not `passed`;
      - or the pipeline flags a passed step whose log has no test summary.
12. **Setup builds run inline, not as jobs.**
    - The R01-R50 setup's subagents ran most of the 48 builds and their upstream tests inside the loop's scope: 26 by 17:2x, with nothing submitted between 16:14 and 17:23, and the scope at 10.1 GB under one shared cap. Only the three largest went to the pipeline.
    - This is against `CLAUDE.md`'s rule (anything over a minute or 1 GB is a job) and the setup template. Nothing ran out of memory, and the setup was the fastest yet (about 2 min a case).
    - Observed by the advisor.
    - **Direction:**
      - the rule is enforced, not only stated (a memory or time guard on a fork's builds that points to `pipeline.py submit`);
      - or the user decides that a setup's builds may run inline within its cap, which would make this the standing practice.

- **Needs**: the user, to choose a direction for each item, or dismiss it.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): two of its items have a mechanism now, shown on fixtures and on no setup phase yet. Item 11 (a job that passed with builds stopped at a test compile): a step of a second-format job that says it runs tests (`promises.tests`) is held to evidence of them, from JUnit XML reports or the log's summary lines, and a step that exited 0 and shows none is `failed` (`jobs/evidence.py`, `jobs/test_formats.py`). Item 12 (offline misses outside a case's own modules): a readiness operation is resolved by running the task itself offline until it runs through (VF-076). The status is unchanged.
- **Update 2026-11-28, later** (the same run's fourth cycle): items 11 and 12 were replayed on the S batch itself ([results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md#the-s-batchs-first-setup-as-a-control)). Eight of its cases (S01, S02, S08, S11, S15, S25, S42, S46) were submitted as one manifest from the cache as the setup's first resolution pass left it, each job needing its builds and landed tests ready at both pins. All eight came ready by one request each, in 1 to 13 offline rounds, with what the second pass had fetched served from a folder; six jobs then passed every step with no network and an empty home, S11 and S46 failed on the transplant alone as they did on 2026-11-27, and no job failed for want of an input (job `20261128-023835-replay-eight-of-the-s-batch-s-first-setu`, 11 of 11 checks, 51m32s). A receipt at the level `tests-run` is now withheld when the offline run shows no test that executed (item 11's fault, at the readiness too). What it cost: two thirds of the batch's time went into rounds that failed, each a Gradle start, so it is no faster than the second pass an agent wrote by hand; it needs no agent to find the gap. The status is unchanged: no setup phase has used it.
- **Closes when**: items 2, 3, 5 to 7, 11 and 12 have fixes or are dismissed by the user. Item 1 closes with VF-069, and item 4 is already fixed. Items 8 to 10 close with a recorded decision.

### VF-069: an agent's wait loop matches its own command line in pgrep and never ends; a hung run needs the user

- **Status**: open. It needs a robust way to wait, a rule in the operating notes, and a sanctioned way for the watcher to clear a hung wait.
- **Raised**: 2026-11-25 by the watcher, from the advisor's draft, at the user's request, after the m01-m10 setup run hung.
- **What happened.**
  - `sync.py commit` takes about 15 minutes in this checkout (its `check`), so setup agents run it in the background and then wait for it.
  - They wait with `until ! pgrep -f 'python3 llm-dlc/tools/sync.py commit'; do sleep 10; done`. That loop's own command line contains the pattern, so `pgrep -f` always finds a match and the loop never ends.
  - Occurrences on 2026-11-25:
    1. **`organic-java-merged-pr-links-l01-l20-brief-setup`** (Claude Opus 5.5) noticed its loops "were matching their own command lines in `pgrep`" (16:15 UTC), stopped them and re-ran the commit. The cost: a killed commit left a description on `@`, plus extra time.
    2. **`organic-java-merged-pr-links-m01-m10-brief-setup`** (Claude Opus 5.5, `claude -p` pid 3335079) did not notice. Its second commit landed at 20:55 (`sxkpqmww`). From 21:04 it sat in up to four such loops (9 to 40 minutes old) until about 21:40, with no other activity. Its two jobs had already run and were collected.
    4. **`spring-framework-pr-links-o01-o20-brief-setup`** (Claude Opus 5.5, pid 837878), 2026-11-26 ~00:25 UTC, after the operating note existed: `until ! pgrep -f 'case_job.sh O.. dryrun' >/dev/null && [ "$(grep -c pass …)" -ge 52 ]; do sleep 20; done`. The regex `O..` matches the loop's own text. All 18 of its build jobs had passed and the count was already 52; the agent sat in the loop with no other activity (46 minutes when the watcher found it). A rule in the notes does not reach an agent mid-task: the tool-side fixes (1, 3) matter more than fix 2.
    5. **`spring-framework-pr-links-p01-p30-brief-setup`** (Claude Opus 5.5, pid 1902348), 2026-11-26 ~03:50 UTC: a background `until ! pgrep -f 'review show' >/dev/null; do sleep 15; done` (pid 2371718), the third pattern after `sync.py commit` and `case_job.sh O..`. Only the loop itself matched; the agent stayed active meanwhile, so it was not blocking when found (12 minutes old, spotted by the advisor).
    3. The advisor's own background monitor of a promotion used `pgrep -f 'sync.py promote'` to detect the end, and never reported it for the same reason.
    6. **`spring-boot-merged-pr-links-s01-s50-brief-setup`** (Claude Opus 5.5, pid 1667919), 2026-11-27 ~09:05 UTC, on the setup template that already describes `unhang`: two loops, `pgrep -f resolve_lane.sh` (pid 1913920, 36 min old) and `until ! pgrep -f snapshots.sh …` (pid 1987265, 18 min old), with no other process matching either pattern. The agent had made 18 tool calls in the half hour before. The watcher ended both by PID with `single_run.py unhang` (dry run first), its first use, which recorded them in the run's `unhang.jsonl`. So the operating note and the template have not stopped agents writing these waits; `unhang` only clears them afterwards.
- **Why it needed the user.** The watcher found the loops at about 21:40 (four, 9 to 40 minutes old, all children of the setup agent; no real `sync.py commit` running), but auto mode's classifier denied its kill of them, and `single_run.py stop --now` is reserved for the user's word. So it was put to the user. By the watcher's next check (21:43) the loops had been ended outside the watcher's session; the agent went on in the same cycle, finished the record, and the watcher stopped the run as complete and landed the setup.
- **What it costs.** A cycle's worth of wall-clock time per occurrence, a person's attention, and sometimes a half-made commit. It will recur while commits are slow and agents write their own waits.
- **Fixes (to build; none chosen):**
  1. **A wait that can't self-match:**
     - `sync.py commit --background`, which writes a status or PID file under the run's folder plus a `sync.py wait` that reads it;
     - or, for agents, waiting on the PID they started (`cmd & pid=$!; wait $pid`, or `while kill -0 $pid`), not on a pattern.
  2. **An operating-notes rule (done 2026-11-25):** `llm-dlc/operating-notes.md`, *Waiting for a command to finish: not by `pgrep -f` on its text*. The rule: never wait with `pgrep -f PATTERN` where the loop's own text contains PATTERN. If pgrep is unavoidable, use the bracket form (`pgrep -f '[s]ync.py commit'`). Prefer the client's own background-task notification.
  3. **A sanctioned unhang for the watcher:** a `single_run.py` command that lists and ends a run's idle child processes (sleep or `until` loops older than N minutes, with no live target) without stopping the turn, so the watcher can clear this without the user and without a broad kill.
  4. **Make commits fast enough not to background.** The ~15-minute `check` is the root pressure (see the slow `review show` too).
- **When it closes**: a setup or domain run can wait for its own long commit without hanging, and a hung wait can be cleared by the watcher with a sanctioned command.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): the waits a keeper or an agent needs are commands with a typed answer, so none has to match a process by its command line: `wait --json` (`finished`, `no-runner`, `timeout`) and `wait --batch NAME --json` (`settled`, `timeout`, `unknown`), and the watcher's keeper reads the runner's state from the lifecycle view. What this finding asks of a hung run (`single_run.py unhang`) is as it was.

### VF-068: merging a promotion's record back conflicts in the manifest of a session that kept working after the freeze

- **Status**: open. The tooling needs fixing. Until then, each occurrence needs the user's decision, because agents may not edit `llm-dlc/traces/`. This occurrence is resolved: with the user's permission the watcher took the line's side whole and committed the merge (wzsnyuzr).
- **Raised**: 2026-11-25 by the watcher, from the advisor's draft, at the user's request, after promotion `20261125T102804Z-6994ae80fc8f` (`main` 867fa025 → be470ab3, 360 commits).
- **What happened.**
  - The promotion froze `develop` at 6994ae80, uploaded the frozen commits' logs, and put its publication record commit `C` on top. The record adds the logs' URLs in their sessions' manifests (`llm-dlc/specification.md`, *Promotions*: "The publication record").
  - Meanwhile the default line moved on. `develop` had moved too, so `C` had to be merged into the working line; the spec says "the generated files are regenerated".
  - The merge conflicted in one session's `llm-dlc/traces/01a2115c-9513-7e00-92f4-2bec1d881ba5/manifest.json`. That is the trace of the **persistent brief-generation session** (Codex `ea63c5f6`), which the frozen commits of entry 6 reference. After the freeze it continued with entry 8 and committed again.
    - **The promotion's side:** status `ended`, 6 logs, all with `url`, current log `04da…`.
    - **The line's side:** status `open`, 10 logs (the same 5 older ones with `url: null`, 4 newer, `04da…` dropped), current log `b1ca…`.
  - `sync.py regenerate` refuses while a session file is conflicted, by design. Agents may not edit `llm-dlc/traces/` (CLAUDE.md). A scripted field merge by the watcher was rightly refused.
  - The queue paused at entry 8's checkpoint, since that revision is not a descendant of `develop`, until the user decided (2026-11-25: take the line's side).
- **Why it recurs.**
  - `cmd_regenerate` assumes that "every input (a session's manifest and metrics.json) is in a directory of its own, so it merges cleanly". That holds only when one line writes a session's files.
  - A session that spans a promotion is written on both sides: the promotion adds URLs, and the line adds logs, commits and status.
  - The queue's sessions are persistent by design: the domain session (`session=previous`) and the generation session (`generateSession=previous`). So almost every promotion taken while the queue runs will meet this, and so will any long watcher or advisor session that commits.
- **The safe manual resolution, this time.**
  - Take the **line's** side whole (`jj restore --from <line parent> <manifest>`), then `sync.py regenerate`, commit and checkpoint.
  - Checked by the advisor: no commit's `LLM-Trace` names the dropped log `04da…`. So only the URLs of the 5 already-published logs are missing on `develop`, and the next promotion re-fills them from the store (`remote_matches`). `main` keeps its copy with the URLs.
  - The promotion's side would be wrong: it drops 4 logs that entry 8's commits name, which `check` would report.
- **The fix (to build).** When a session's `manifest.json` conflicts in this merge (or any merge), resolve it in the tool, field by field:
  - the **union** of `logs`, keyed by SHA-256;
  - each log's `url` from whichever side has one;
  - the line's side for the session's live fields (`status`, `ended`, `log`, `commits`, `stats`, `context_windows`, …);
  - then regenerate.

  Do it in `promote`'s merge into `develop` and in `regenerate` (or `sync.py sync`), with a test of a session committed on both sides. Keep refusing a conflict in anything else under a session's folder.
- **When it closes**: a promotion taken while a persistent session keeps committing merges back without a person.

### VF-067: three successor launches still need 12 signed Ubuntu packages; approved for a later beyond-jbmc follow-up

- **Status**: open, deferred (the user, 2026-11-25). The user approves fetching the 12 packages, but **only as part of a future beyond-jbmc follow-up run**, not now and not as a run of its own. When that run is queued, its brief or continue message carries the approval explicitly. The finding closes when the three launches have run on signed providers and the panel is re-scored.
- **Raised**: 2026-11-25 by the watcher, from the advisor's draft and account of `beyond-jbmc-scaffold-first` (Codex Astra 6.2 at max, session `c3caedf3`), at the user's request.
- **What happened.**
  - The successor study measures 16 library upgrades on Ubuntu's signed JARs. 13 launched entirely from signed Ubuntu packages.
  - Three callers need dependency packages from the signed distribution for their original launches:
    - slot 03, WildFly (JBoss Logging);
    - slot 08, Jackson plus Joda-Time;
    - slot 16, PDFBox.
  - The run had already fetched 39 signed files. At 03:52 UTC it asked whether it might fetch 12 more, which was over the operating notes' "a few dozen requests at most for a task". Nobody answered, since the run was unattended.
  - It fell back to dependencies from the local Maven cache, ran all three on their original application JARs, and recorded them as *alternative deployments*, not signed-distribution launches.
- **The 12 packages**: `verification/beyond-jbmc/successor/needed-providers.json` lists each with its suite, version, archive path, expected sha256 and the deployment it completes.

  | Slot | Side | Suite | Packages |
  |---|---|---|---|
  | 03 | new | focal | `libjboss-logging-java` 3.4.1-1 |
  | 08 | old | focal | `libjackson2-core-java` 2.10.1-1, `libjackson2-annotations-java` 2.9.8-1, `libjackson2-databind-java` 2.10.2-1, `libjoda-time-java` 2.10.5-1 |
  | 08 | new | jammy | `libjackson2-annotations-java` 2.13.0-1, `libjackson2-databind-java` 2.13.0-2, `libjoda-time-java` 2.10.10-1 |
  | 16 | old | jammy | `libpdfbox2-java` 2.0.25-1, `libfontbox2-java` 2.0.25-1, `libcommons-logging-java` 1.2-2 |
  | 16 | new | noble | `libpdfbox2-java` 2.0.29-1 |
- **Why it is low priority.** The headline doesn't depend on it.
  - The frozen operators decided 0/13 on the signed launches and 0/3 on the Maven alternatives.
  - Even success on all three would give 3/16, below the brief's 8/16 target (`llm-dlc/loops/beyond-jbmc-java-change-verification-campaign-results.md`).
  - What it adds is a complete signed panel (16/16 launches instead of 13/16), plus three more matched comparisons of native, stock JBMC and integrated JBMC with the callers supplied.
- **How to do it, when the follow-up runs.**
  - Fetch the 12 files from `archive.ubuntu.com`, one at a time, in plain requests (the operating notes' web rules otherwise unchanged), and check each against its recorded sha256 before use.
  - Launch the three callers on the signed closures.
  - Re-score `verification/beyond-jbmc/successor/SCORES.md`, keeping the Maven-alternative results beside the new ones.
- **Not for this finding**: raising the general web-request budget. The approval covers these 12 files only.

### VF-066: a queued run that continues the previous run's session starts near its compaction limit

- **Status**: open. Monitoring only (the user, 2026-11-25): no change for now, act later if the measurements below show a cost. The user is less concerned for the organic PR briefs, whose verification work is mostly mechanical: building pins, running landed tests and checking claims case by case.
- **Raised**: 2026-11-25 by the watcher, from the advisor's draft at the user's request, from queue entry 7 (`organic-java-merged-pr-links-brief`, its domain run on Codex Astra 6.2 at max effort).
- **What happened.** The queue's default domain session is `previous` (`brief_queue.py`, DEFAULTS `"session": "previous"`), so each domain run resumes the last domain run's Codex session.
  - Entry 7's domain run resumed `c3caedf3`, which still held about 555k tokens from `beyond-jbmc-scaffold-first`, an unrelated campaign.
  - It started at 08:28:53 UTC and Codex auto-compacted at 08:33:58, about 5 minutes in, at 555,044 tokens with no commit yet. That's the global limit of about 550k, since the domain run sets no `compactAt`.
  - The conductor judged it correctly, as inherited context, and said continue.
- **Why it can matter.**
  1. **The first compaction comes almost at once.** It summarises mostly the previous campaign's context, so the new brief's opening reading can be squeezed into the summary along with it.
  2. **Each turn before it carries the inherited context,** so it costs more.
  3. **A compaction with no commit asks for a verdict,** which takes the conductor's time and is one more chance for a wrong stop.
  4. **It recurs:** every queued domain run inherits whatever the previous one left.
  5. **The generation session behaves the same way.** `generateSession` is also `previous`, and six generation entries (8–13, 135 PRs) run in session `ea63c5f6` in a row. That's by the user's design (one persistent generation session), and its `compactAt` 600k is set explicitly.
- **What to measure** (the watcher, per queued run, in its product notes):
  - the tokens at the run's start (the inherited context) and the time to the first compaction;
  - whether the first compaction came before the run's first commit;
  - after that compaction, whether the agent re-read the brief and its setup notes, or repeated work it had already done;
  - cycles and claims decided, compared across runs that began with little or much inherited context.
- **When to act.** Act if a run, after an early compaction, repeats work, loses track of the brief's cases, or ends a cycle with a wrong verdict; or if early compactions measurably raise the cycles or cost per claim.
- **Options, for later** (none chosen):
  - `session=new` for briefs unrelated to the previous run (per entry, `brief_queue.py add --session new`, or `defaults` for a line of briefs);
  - a compaction at the start of a run that continues an unrelated session;
  - for generation, a new session when the PR list's projects don't overlap the previous list's.
  The user's design for generation (one persistent session) stays unless the measurements argue otherwise.
- **Evidence**: `llm-dlc/loop-summaries/single-organic-java-merged-pr-links-brief/events.jsonl` (event 2, `compaction`, tokens 555044, `commitSince` false) and `loop.log` (08:33:58–08:34:08, the conductor's continue).

### VF-065: real-world bugs the runs found in other projects, to confirm and report

- **Status**: open: a register. The user asked on 2026-11-24 for every real-world bug a run finds in another project, a defect in released or merged upstream code shown by a replayed JVM witness, to be kept here until it is followed up. An entry is done when it has been confirmed and either reported upstream by the user or dismissed with a reason. The finding closes when every entry is done. Runs and watchers add new entries here, not elsewhere.
- **Raised**: 2026-11-24 by the watcher, at the user's request (relayed by the advisor), after the queued run `organic-pr-20-additional-cases` (Astra 6.2 at max effort, session `c3caedf3`).
- **Nothing outward-facing from an agent**: an agent prepares a report and its reproduction. The user files it, or decides not to.

#### Entries

**1. Apache Lucene, [PR #15727](https://github.com/apache/lucene/pull/15727) (case J14): with a child filter, the fixed `ToParentBlockJoinSortField` treats filtered-out children as missing.** Open: confirm, then report.
- **What the PR changed, and the run confirmed.** Parents are sorted by their children's values. When some children have no value, the fixed version gives the parent a missing sort key: ascending `[B:"20", A:"30"]` became `[A:null, B:"20"]`. Descending order and an all-present block held. This is the PR's intended change.
- **The defect.** With a child filter that selects only the children with values, a filtered-out child still makes the parent's key missing.
  - The run's own preservation claim, that filtering out the missing child keeps A at 30, is refuted on the fix by a public-API JVM witness: A/null.
  - A follow-up held the sole selected child at 30. The fix returned 30 with no excluded child, and null with an excluded child, *even when that excluded child had a real value (05)*. The parent revision returned 30 in all three.
  - Per the run, the fixed comparator infers "a child is missing" from the whole parent block's child count, not from the children the filter selected.
- **Evidence**: `verification/product-behaviour/cases/J14/case.json`, `verification/product-behaviour/results/J14/` (original prediction and witness), and the J14 row and the Lucene paragraph of `llm-dlc/loops/organic-java-pr-product-behaviour-20-additional-cases-results.md`.
- **To confirm before reporting**:
  1. **Reproduce on a full upstream build.** The run used a source overlay: the PR's three changed join classes over a common Lucene 10.4.0 distribution, one of the seven overlay cases whose effect is unmeasured. Reproduce on a real Lucene build or release that includes #15727, through the same public calls (index two blocks, reopen, search with the five-argument constructor and a child filter).
  2. **Check the intent.** Read the PR discussion and the javadoc of `ToParentBlockJoinSortField` for whether "missing" was meant to count all children or only those the filter selects.
  3. **Check whether it's already known.** Look at Lucene's issue tracker and later commits on that class.
- **Report**: a minimal public-API reproduction (two parent blocks, the filter, the expected and observed sort keys), for the user to file.

**2. Apache Avro, PR #3709. Reading a scalar-first union's array default throws.** Confirmed on the merge, the 1.12.2 release and `main` at `a3355d0826fa`. With default `[1]` and field type `["int",{"type":"array","items":"int"}]`, schema parsing succeeds. Both `Field.defaultVal()` and `IdlUtils.writeIdlSchema` throw `AvroRuntimeException`. Exchanging the branches produces the typed list and IDL initializer. The user can attach the witness to resolved AVRO-4211 or file a linked issue. [Report, reproduction and related tickets](merged-pr-links/upstream/README.md#apache-avro--scalar-first-union-throws-when-reading-or-emitting-an-array-default) · [JVM observations](merged-pr-links/upstream/411.json)

**3. ical4j, PR #931. Exchanging two distinct overrides drops a rescheduled occurrence.** Confirmed on the merge and `develop` at `2c5ff9f211a8`. A moves the July 15 occurrence onto B's original July 16 start. B moves the July 16 occurrence to 03:00. The two input orders return B alone and both A and B, respectively. Both replacement periods are inside the query window. Released 4.4.0 predates the fix and returns the master periods in either order. The user can file the development-branch reproduction. [Report, calendar and related tickets](merged-pr-links/upstream/README.md#ical4j--reordering-two-distinct-recurrence-overrides-drops-a-meeting) · [Typed periods and owners](merged-pr-links/upstream/412.json)

**4. jOOλ, PR #418. Widening a full window changes the last value.** Confirmed for both `jool` and `jool-java-8` on the merge, released 0.9.16 and `main` at `9273e1f54356`. On the third row of [1,2,3], `window(-5,5)` gives endpoints (1,3). Raising the upper offset to `Long.MAX_VALUE - 1` gives (1,1). The ordinary and future-only controls agree. The user can file the three-row reproduction. [Report and related tickets](merged-pr-links/upstream/README.md#jooλ--widening-an-already-complete-window-changes-its-last-value) · [Both module receipts](merged-pr-links/upstream/419.json)

**5. picocli, PR #1529. Clearing a redundant alias removes the child’s primary command name.** The merged caller accepted both edits, then returned exit 2 with zero child invocations. The fresh root dispatched the identical name. Confirmed on release 4.7.7 and `main` at `10509c0af89a`. The user can file the primary-name case with a link to #1528. [Report and reproduction](merged-pr-links/l01-l20/upstream/README.md#picocli-loses-its-primary-dispatch-entry) · [Current JVM receipts](merged-pr-links/l01-l20/upstream/425.json)

**6. JGraphT, PR #792. A returned GraphPath contains an edge outside its graph.** Suurballe and Bhandari both returned the expected vertex sequences and weights. The input graph did not contain the returned 3→7 edge object. The one-route control passed. Confirmed on release 1.5.3 and `master` at `ee3a1084f737`. The user can file the shared reconstruction witness. [Report and reproduction](merged-pr-links/l01-l20/upstream/README.md#jgrapht-returns-an-edge-outside-the-paths-graph) · [Current JVM receipts](merged-pr-links/l01-l20/upstream/429.json)

**7. Commons Statistics, PR #140. A small Cauchy scale with a subnormal probability gives infinite quantiles despite finite answers.** For scale 2⁻¹⁰⁰ and probability 2⁻¹⁰⁵⁰ the expected magnitudes are approximately 2⁹⁵⁰/π. The merge and `master` at `8381f56aa3ec` returned infinities. Release 1.3 predates the fix and returned incorrect, small finite values. The user can attach the scaled case to #140 or open a linked issue. [Report and reproduction](merged-pr-links/l01-l20/upstream/README.md#commons-statistics-overflows-a-representable-scaled-cauchy-tail) · [Current JVM receipts](merged-pr-links/l01-l20/upstream/430.json)

**8. Apache Commons Compress, PR #334. A writer-produced ZIP preamble is invisible to the prefix getters.** On the merge, 1.23.0 and 1.28.0, both files have their first local header at byte 15 and yield the complete payload. The writer-produced file reports offset zero and a null prefix. The user can file the paired reader/writer reproduction against 1.28.0. [Report and caller](merged-pr-links/m01-m10/upstream.md#commons-compress-returns-zero-for-a-writer-produced-preamble)

**9. Agrona, PR #202. Copied primitive map entries violate the equals/hashCode contract.** On the merge, 1.4.0 and 2.7.2, three entries compare equal to their JDK counterparts, but all hash to 11. A JDK HashSet misses two of the inserted pairs. The user can file the unchanged-map reproduction against 2.7.2. [Report and caller](merged-pr-links/m01-m10/upstream.md#agrona-copied-entries-compare-equal-and-hash-differently)

**10. libGDX, PR #7278. A reused output polygon returns stale bounds after successful clipping.** Resolved upstream by #7522. The witness reproduced on both original revisions and 1.13.0. On 1.14.2 the identical caller returned the correct vertices and bounds. [Release evidence and upstream repair](merged-pr-links/m01-m10/upstream.md#libgdx-repaired-the-reused-bounds)

**11. Spring Framework, PR #37193. An SSE retry field with a trailing space still sets the delay.** The merged WebClient and Spring 7.0.10 delivered the payload with a 25 ms retry for both the valid leading-space field and the trailing-space field. The EventSource digits rule predicts an absent hint for the latter. [Caller and observed event envelopes](../examples/466-spring-sse-retry/README.md) · [Release reproduction](merged-pr-links/o01-o20/upstream.md#server-sent-event-retry-hints)

**12. Spring Framework, PR #30530. Strict R2DBC constructor mapping rejects a complete row.** On the merge the same driver row produced `ADA` by constructor with default settings, then raised InvalidDataAccessApiUsageException with full-population checking. The only writable property was supplied. Spring removed the strict setter in August 2023. The original call raises NoSuchMethodError on 7.0.10. [Release follow-up and upstream removal](merged-pr-links/o01-o20/upstream.md#strict-r2dbc-constructor-mapping) · [Application type and R2DBC readback](../examples/470-spring-r2dbc-mappers/README.md)

**13. Spring Framework, PR #29116. Direct JMS reinitialization leaves a closed connection installed after replacement fails.** After a reset, the merged factory closed the rejected B and returned a session on C. Direct reinitialization closed A and B but attempted the next session on closed A. [Public calls and provider record](../examples/475-spring-jms-replacement/README.md)

**14. Spring Framework, PR #37325. WebTestClient can reject an append to its live default headers.** Initializing a header through defaultHeader and appending through defaultHeaders on the same retained builder threw UnsupportedOperationException on the parent, the merge and Spring 7.0.10. Seeding through the consumer allowed the append. A fresh derivative successfully copied the convenience-initialized list on the merge. [Caller, controls and release results](../examples/463-spring-client-defaults/retained-builder/README.md)

**15. Spring Framework, PR #36207. An empty YAML sequence ignores the caller's empty-value marker.** On the landing the protected flattening hook preserved the identical marker for both YAML null scalars and an empty mapping. An empty list mapped to a blank string. The ordinary properties factory kept its prior behavior. [Caller and adapter comparison](../examples/481-spring-yaml-empty-values/README.md)

**16. Spring Framework, PR #36626. Copying a mail message can drop the date returned by an overridden getter.** A subclass whose getter returned 1234 ms and whose inherited field was unset copied 1234 by both routes on the parent. On the merge its constructed copy returned null and copying into a target left its previous 77 ms intact. [Mutation controls and both copy routes](../examples/484-spring-mail-date-copy/README.md)

**17. Spring Framework, PR #37559. The default protobuf JSON Lines encoder splits two records into twelve lines.** The merged encoder selected the advertised media type. The compact printer produced two independently parseable messages. With the default printer all twelve physical lines failed independent parsing. [Generated protobuf messages and line reader](../examples/489-spring-protobuf-json-lines/README.md)

All three entries above reproduced on published Spring 7.1.0 with the original caller binaries. [Release reproductions and controls](merged-pr-links/p01-p30/upstream.md)

**18. Spring Framework, PR #30020. Disabling global parallelism does not clear the Jupiter configuration error that recommends it.** The recording class used explicit PER_CLASS and CONCURRENT annotations. Both values of the global parallel switch produced the same container failure on the landing and 7.1.0. [Diagnostic and engine reproduction](merged-pr-links/p01-p30/upstream.md#disabling-parallelism-in-a-recording-jupiter-test)

**19. Spring JDBC, PR #22392. A public script reader disappears between patch releases.** A direct client compiled against the original three-argument ScriptUtils.readScript returned its SQL on 5.1.4.RELEASE and raised NoSuchMethodError on 5.1.5.RELEASE. This is a historical binary-compatibility finding. [Release reproduction and original invocation descriptor](merged-pr-links/p01-p30/upstream.md#historical-jdbc-compatibility)

**20. Spring TestContext, PR #34723. A test subclass cannot apply a bean override to a hierarchy inherited from its superclass in these fixtures.** The inherited hierarchy served both original beans, and both override scopes worked when the two context levels were declared on the concrete test. Moving only the hierarchy to its superclass made both fields fail before the test method on the landing and Spring 7.1.0. [Five histories, caller and released witness](../examples/501-spring-context-level-override/inherited-hierarchy/README.md)

**21. Spring Framework, PR #37332. The second equal value cannot be removed through a composite map’s values view.** With mutable backing maps, the first removal returned true on the landing. The second threw UnsupportedOperationException and left the remaining mapping intact. The API describes a partially unmodifiable map, so the upstream question is which values-view removals it supports. [Both backing maps and the captured view](../examples/513-spring-composite-map-values/README.md)

**22. Spring JDBC, PR #34709. Setting maxRows to zero suppresses every row.** A statement exposing three ordered rows received setMaxRows(0), the JDBC unlimited setting. All three template query forms returned the rows on the parent and delivered zero on the landing. At limit two they delivered the correct prefix. [List, callback, and stream readbacks](../examples/520-spring-jdbc-row-limit/README.md)

**23. Spring AOP, PR #35140. A large jitter can overflow before a reactive target is subscribed.** A five-millisecond delay and 20-millisecond jitter allowed immediate success on the landing. Changing only jitter to 107000 days raised ArithmeticException synchronously. Both durations exceed the delay and the new conversion is intended to cap the jitter factor. [Proxy, target counter, and positive control](../examples/535-spring-reactive-retry-jitter/README.md)

**24. Spring Core, PR #37465. Direct legacy callbacks on CompositeRetryListener stop reaching delegates.** The parent forwarded one failure and one success. Calling the same public signatures with the same inputs on the landing produced an empty delegate history. Both revisions forwarded the legacy callbacks when driven through RetryTemplate. [Direct and template-driven records](../examples/536-spring-retry-state-callbacks/README.md)

All four Q-series cases reproduced on published Spring Framework 7.1.0. The reactive jitter fixture used the relocated interceptor package in spring-context. [Release witnesses and reporting scope](merged-pr-links/q01-q30/upstream.md)

**25. Apache Commons IO, PR #860. A bounded reader can skip past the read-ahead limit of a mark.** After mark(2), individual reads stopped after two characters. A skip on an identically marked reader consumed four, confirmed by reading its delegate. The PR describes the narrower guarantee. [Reproduction and global-bound control](merged-pr-links/r01-r50/upstream.md#commons-io-marks-and-skips)

**26. Apache Avro, PR #2282. BigDecimalConversion reads a preceding value outside a heap buffer slice.** A standalone copy decoded to 12.30. A slice exposing the same bytes decoded to the preceding 7, changing both the integer and its scale. [Two independent decodes](merged-pr-links/r01-r50/upstream.md#avro-big-decimal-buffer-slices)

**27. Resilience4j, PR #2067. An asynchronous result-based stop publishes a negative-delay retry event.** The stage returned its retryable value after one supplier call. A retry listener observed a −1 ms wait, with no second attempt. Both original revisions exhibited this behavior. [Supplier and listener counts](merged-pr-links/r01-r50/upstream.md#resilience4j-retry-notifications)

**28. AssertJ, PR #3710. A constant JavaBeans getter can conceal unequal record components in recursive comparison.** The generated component accessors returned different strings. Equality passed with the extra getter and failed as expected without it on the landing. The reporting decision depends on the intended getter precedence. [Record fixtures and controls](merged-pr-links/r01-r50/upstream.md#assertj-record-accessor-precedence)

**29. Apache Commons IO. A fresh mark(2) at offset two makes a bounded reader report immediate EOF.** With a six-character global bound, moving the mark from offset zero to one and two shortened the available read window from two characters to one and zero. The independent delegate read returned the same third character every time. This occurred on Commons IO 2.22.0 and both PR #860 pins. [Offset and reset measurements](merged-pr-links/r01-r50/upstream.md#mark-position-shortens-a-fresh-commons-io-read-window)

For entries 25–28, released callers reproduced the marked skip on Commons IO 2.22.0, the sliced decimal on Avro 1.11.4 and 1.12.0, the negative retry notification on Resilience4j 2.2.0, and the record getter precedence on AssertJ 3.27.1. Resilience4j 2.1.0 stopped silently for the same returned value. [Release comparisons](merged-pr-links/r01-r50/upstream.md#what-reproduced-on-published-versions)

#### Candidates to sort

- **Stock JBMC reports that do not reproduce on the JVM**, from the beyond-jbmc run:
  - 26 of stock JBMC's 100 reported target failures did not reproduce on the original JVM;
  - on Guava 33.4.8-jre, stock JBMC reported `ffffffff` as a hexadecimal round-trip failure that the released JAR does not show.

  These are defects in a real-world tool, not in the library. Sort them into [`llm-dlc/loops/jbmc-upstream.md`](../llm-dlc/loops/jbmc-upstream.md) (the drafted, unapproved brief for JBMC's upstream defects), or dismiss them as harness or profile artefacts, then remove them from this list. Evidence is in `llm-dlc/loops/beyond-jbmc-java-change-verification-campaign-results.md`.

### VF-064: a watcher stopped a run that was extending the lead over JBMC because it had not done the named fixes first

- **Retired (2026-11-27, change `sylnnqzv`):** this entry names `single-agent-run`, which is no longer in the repository. See [`llm-dlc/retired.md#single-agent-run`](../llm-dlc/retired.md#single-agent-run) for what replaced it and the last commit that has it.
- **Status**: open. The user decided the policy on 2026-11-24, and it applies from the next verdict. Whether it works is measured on the next runs, starting with `beyond-jbmc-scaffold-first`.
- **Raised**: 2026-11-24 by the watcher, at the user's request (relayed by the advisor), after the queued run `beyond-jbmc-java-change-verification-cam` (Astra 6.2 at max effort, session `c3caedf3`).
- **Found**:
  - **The verdicts.**
    - At cycle 2's verdict the watcher continued for two named fixes: the Batik/dom4j XML-resource isolation, and re-measuring the frozen 187-claim and blind decisions affected by the rename bug (VF-062).
    - Cycle 3 re-measured the 187 (no disposition changed) and spent the rest on new capabilities. It ran the JDK's `StringTokenizer` bytecode, proved the ISCWT glyph contract for all 1,024 widths (478 solver answers independently checked), proved Guava's unsigned hex round trip for every 32-bit word where stock JBMC wrongly reported a failure, and raised exception replay from 6/20 to 20/20 across five JDKs.
    - The watcher stopped the run at cycle 3's verdict because the named fixes were not done, "whatever the new wins".
  - **The user's view:** the overall goal is to extend the lead over JBMC, and good progress could have been had there. Both are fine, named fixes and new capabilities. Extra cycles are affordable.
- **The policy (the user, 2026-11-24)**:
  - **Lead-extending capability work is a reason to continue.** New, JVM-backed checker capability that extends the lead over JBMC (new families decided, stock-JBMC misses shown, independent transfers) counts as progress on its own. Don't stop a run because it chose that over named fixes.
  - **Name what's unfinished, but don't make it a condition.** At a verdict, keep naming the open fixes (record them in the run's results or a finding). They are not a condition for continuing while real capability progress is being made.
  - **Stop for the usual reasons only:** churn (cycles with no new decision and only the blocker moving), a reached outcome, something only a person can decide, or soundness problems left unrecorded.
  - **Extra cycles are acceptable** to get both the fixes and the capabilities.
- **What would close it**: a run in which named fixes and new capability work both progress across continued cycles. If a run again leaves the named fixes undone across several cycles, the continue message's inability to steer it toward them is the problem to solve. That is recorded for planning, not worked around by the watcher, since the continue message is the user's.
- **Related**: VF-062 (release namespace isolation), VF-063 (scaffolding before solving), the `single-agent-run` skill's verdict rules, and `prompt=scaffold-first`.

### VF-063: the product's main gap is investigation and claim scaffolding, not solving

- **Retired (2026-11-27, change `vwytpwxy`):** this entry names `prove-java-change`, which is no longer in the repository. See [`llm-dlc/retired.md#plugin-and-runtime-mode`](../llm-dlc/retired.md#plugin-and-runtime-mode) for what replaced it and the last commit that has it.
- **Registered predictions, 2026-11-26.** Stage 3 generated old-API callers for all eight development cases. Its frozen first transfer recovered two of five disclosed cases. After additional recipe work all 31 questions on 13 cases had complete original-JVM observations. Three fixed-side predictions were refuted and two incorrect parent baselines stayed open. Cold discovery of customer intent remains open. [Campaign report](../llm-dlc/loops/in-the-loop-generated-observers-and-callers-brief-results.md) · [Per-question evidence](generated-observers/scorecard.json)
- **Follow-up on reviewed inputs.** The previously blocked Spring decimal formatter now runs on both pinned releases. Five callers produced the right outputs with different arguments and all five lost qualification. Two corrections to historical parent predictions could be scored from the original receipts. The next scoped caller needs to read `DecimalFormat.isParseBigDecimal()` on the same formatter after the public parser returns. [Supplementary measurements](../llm-dlc/loops/in-the-loop-generated-observers-and-callers-brief-results.md#supplementary-measurements-on-the-original-deployments)
- **Status**: open. This is an important product gap. The user asked on 2026-11-24 for it to be tracked, for future runs to be directed to scaffold before solving (`prompt=scaffold-first`), and for the beyond-JBMC brief to be queued again on that prompt.
- **Raised**: 2026-11-24 by the watcher, at the user's request (relayed by the advisor), after the queued run `beyond-jbmc-java-change-verification-cam` (Astra 6.2 at max effort, session `c3caedf3`, 3 cycles).
- **Found**:
  - **When a case is supplied, the checker is strong.**
    - Strict native decided 179/187 historical claims (94 proofs, 85 refutations on the original JVM), against 147 for integrated staged JBMC and 144 for stock JBMC, with no decisions lost.
    - On the disclosed cases, it proved mixed-version wire, numeric and reflection-metadata claims.
  - **On unfamiliar upgrades, cold, it decided nothing.**
    - On the sealed panel of 16 release pairs (16 projects, 4 strata), the automatic workflow reached a selected public operation on both releases in 12/16 and decided 0/16 of the registered primary questions. The brief's suggested target was 8/16.
    - In one project, it nominated the registered annotation-index lookup and could not construct the class loader and resources it needs.
    - With the reference caller supplied, native decided 1 (Cactoos' sticky scalar).
    - The historical shadow of 32 external upgrades is still 0/32 automatic primary decisions.
  - **So the loss is upstream of the solver.** It lies in:
    - finding the public entry and the observation that changed;
    - generating a caller that runs on both original releases;
    - recovering class loaders, resources and startup state;
    - registering a question with its expected behaviour and an unchanged control.
- **Why it matters**: the product proves a change to Java code from a PR, a commit or a URL, with no user-written harness (`/prove-java-change`; the organic-PR briefs' "one URL from intake to a qualified verdict"). Every decision depends on this scaffolding being automatic. The queued organic-PR briefs exercise it directly, so their results are the next evidence.
- **What would close it**:
  - **A blocker ranking.** Rank the scaffolding blockers by how many independent projects each held up, starting with the 12 reached and 4 unreached blind pairs.
  - **Per-case measurements.** For each case, record whether the observation was discovered, whether the caller reached both releases, whether the question was registered before solving, and where scaffolding stopped.
  - **A cold, automatic decision rate** on a freshly drawn panel that moves well off 0/16, with zero known incorrect native decisions.
- **Scaffold-first follow-up, 2026-11-25.** The first two measurements are now available for all 16 projects. Among the four previously unreached projects, three lacked typed environment construction and one lacked grammar inputs. On the twelve with some public reach, four needed operation histories, four needed a complete reader or writer, three needed grammar inputs and one needed typed metadata. All supplied registrations ran in normal original JVMs and in separate resource-recording loaders before solving. A new artifact-only generator recovered the annotation indexer's lookup, resource classloader, duplicate-name observation and unpopulated control after disclosure. It transferred to Batik's service iterator and stopped at the entry shape for the other 14 projects. The prospective disjoint population has no scored decisions. [Per-project dispositions](beyond-jbmc/scaffold-first/RESULTS.md) · [Unopened acquisition state](beyond-jbmc/scaffold-first/prospective.json)
- **Second draw, 2026-11-25.** All 16 new projects have source-backed registrations, a caller compiled against the older binary, and an unchanged control. Thirteen qualified on the signed distribution graphs available locally. All three remaining consumers ran on both original JARs with pinned alternative Maven providers. The frozen artifact-only portfolio tried 44 callers in the first thirteen projects and decided none of their primary questions. The resource selector nominated none. The three alternative Maven deployments also yielded zero automatic primaries. With the supplied callers, the distribution graphs gave native two primary proofs, stock one, and integrated JBMC zero. Even three further successes would leave the frozen rate below the brief's target. After disclosure, a bytecode-driven signed integer workflow recovered DSI's original question and constructed an independent inverse control. It also generated the Lucene and Protobuf callers. Native and stock proved the primary on all six original deployments. The frozen measurement and this later recovery retain separate scores. [First stops and measured comparisons](beyond-jbmc/successor/SCORES.md) · [Original classloaders and alternatives](beyond-jbmc/successor/RESULTS.md) · [Post-disclosure transfer](beyond-jbmc/integer-codecs/RESULTS.md)
- **Related**:
  - **VF-054:** Avro, where the original scope was blocked at startup.
  - **VF-062:** the Batik and dom4j release-isolation investigation traced resource and factory lookup before qualifying either comparison.
  - **The queue:** `beyond-jbmc` queued again with `prompt=scaffold-first`.

### VF-061: OpenAI's filter stops clustered on raw-bytecode Lean work; precautions for more Lean work

- **Status**: open, as a reference for later. Read it before another brief asks a Codex agent for Lean proofs over raw JVM bytecode. Recorded at the user's request on 2026-11-24, from the advisor's analysis.
- **Raised**: 2026-11-24 by the watcher, after the queued brief trusted-kernel-and-receiver-recovery.
- **Found**:
  - **The stops.** Three of the night's four cybersecurity-filter stops (VF-046) came during one piece of work: the independent proof of Commons Lang `ArrayUtils.reverse(int[],int,int)`.
    - **03:46 UTC, a sub-agent of session `461ff7e6`:** generating Lean theorems from the compiled range rule.
    - **03:57 UTC, the root turn of `461ff7e6` (a run stop):** writing and checking `Reverse.lean`, after printing the raw `ArrayUtils.reverse` and `Math.min`/`max` bytecode into the conversation.
    - **04:15:21 UTC, a sub-agent of the restarted session `fbbe8930`** (rollout `2026-11-24T04-10-35-01a20bbf…`): writing `ReverseRelease.java` (which reads class bytes through `com.sun.tools.classfile`), grepping for `0xCAFEBABE`, and extending `Reverse.lean` with a byte-level opcode interpreter (`| 21 :: 4 :: b, …` patterns). The root turn carried on and finished its cycle, so this was a stop within the run, not a run stop.
  - **The common thread (a hypothesis, not proven):** decoding and executing raw JVM bytecode bytes, that is class-file magic, opcode byte patterns and a hand-written bytecode interpreter, in files literally named "Reverse…". To a classifier, that may read like binary reverse engineering. The earlier stops (VF-046) were on CVE work and on a JVM-startup probe, which fits a wider reading of the same pattern.
- **Precautions for the next Lean or bytecode-level brief** (cheap; none of them yet shown to work):
  - Name such files and theorems for what they prove (`ArrayMirrorProof`, `RangeRule`), not after the method under study (`Reverse…`).
  - Keep raw byte dumps, `javap -c` listings and hex patterns out of the conversation: write them to files, and refer to them by path and digest.
  - Have Astra work as a single agent rather than fork several sub-agents with the same context, since two of the three stops were sub-agents. The user is weighing this one, **for deep JVM verification only** (see the next point).
  - After any stop, continue in a fresh session (VF-046's rule since 2026-11-24).
- **Where these precautions don't apply: brief generation (the user, 2026-11-25).** The precautions are for deep JVM verification, meaning bytecode-level proofs, raw class bytes and runtime probes, where the stops happened. They are not for researching and writing briefs.
  - **The brief author** (`single_run.py generate`, Codex Astra 6.2 at `ultra`) reads pull requests, issues, diffs, source and documentation, and writes Markdown. `ultra` is Codex's "maximum reasoning with automatic task delegation", so it forks sub-agents by design.
  - **The user's decision:** that work is much less likely to be flagged, so it keeps its delegation. Don't restrict it to a single agent on this finding's account.
  - **What still holds there:** keep large raw output (a whole diff, a byte dump) in files, as `brief-generation-template.md` says, and continue in a fresh session after any stop.
  - **If a generation run is stopped all the same,** record it here with what it was doing. That would revise the distinction.
- **Tracked in**: this finding and VF-046. The proof work itself landed with trusted-kernel-and-receiver-recovery (`lib/benchmark/trusted-kernel/RangeRule.lean`, `Reverse.lean`, and `llm-dlc/loops/trusted-kernel-and-receiver-recovery-results.md`).
- **Closes when**: a later Lean or bytecode-level Codex run has followed these precautions and the outcome, stopped or not, is recorded here, or the user decides how such work is routed (for example to Claude Code runs).

### VF-060: a job can be exported from a conflicted revision and run on jj's conflict layout

- **Status**: open.
- **Raised**: 2026-11-24 by the watcher, from a disk alert by the advisor, during the queued run trusted-kernel-and-receiver-recovery.
- **Found**:
  - **What happened:** at about 03:31–03:39 UTC the agent's scoped commit split job files from their sources and left a conflict, which it resolved at about 03:47. Six jobs submitted in that window (`20261124-033119` to `-033937`) were exported from the conflicted revision.
  - **What a conflicted export looks like:** each work folder held jj's Git-compatibility layout for a conflicted commit: `JJ-CONFLICT-README` plus whole-tree copies `.jjconflict-base-0`, `.jjconflict-side-0` and `.jjconflict-side-1`, about 1.9 GB each. That made each folder 7.3 GB against about 1.8 GB normally, and free disk fell from 94 to 49 GB in 30 minutes.
  - **What became of the six jobs:**
    - Two failed for missing sources.
    - The agent resubmitted five on the repaired revision.
    - The JavaParser recheck (`20261124-033119`) ran on the conflicted export, so its result says nothing reliable about the intended sources.
  - **Cleanup:** the watcher removed the archived (`remote_verified`) work folders.
- **Needs**: `pipeline.py`'s export (and `submit`) should refuse a source revision that has conflicts, or at least fail the job at once with a clear reason, instead of materialising the conflict layout and running on it.
- **Tracked in**: this finding.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): preserved across the move of the pipeline to `jobs/pipeline.py`: `verification/test_pipeline.py`'s tests of the conflict check at export run unchanged through the old entry point, and a job whose source is a conflicted commit is still an `error` with nothing of it run. In the lifecycle view such a result has `execution.stopped.reason` `not-run` with the refusal as its reason. No change to the disposition.
- **Closes when**: a job whose source revision is conflicted is refused before it runs, and a test shows it.

### VF-059: nothing picks a brief up from the queue while no run is going

- **Retired (2026-11-27, change `sylnnqzv`):** this entry names `single-agent-run`, which is no longer in the repository. See [`llm-dlc/retired.md#single-agent-run`](../llm-dlc/retired.md#single-agent-run) for what replaced it and the last commit that has it.
- **Status**: open. The user decided on 2026-11-24 to record the intent and build it later.
- **Raised**: 2026-11-24 by the advisor session, with the user, before the brief queue (`llm-dlc/tools/brief_queue.py`)
 was first used for real. The first queued brief is `trusted-kernel-and-receiver-recovery`, taken from the inbox
 after change-verification.
- **Found**:
 - **The queue moves only when a watcher runs `brief_queue.py next`**, at a handover, and `next --finished` after a
   run it judged finished. No daemon, timer or supervisor watches the queue file or the inbox
   (`~/code/scripts/analysis/queue/`). A brief in the inbox is read in only by the next `next`.
 - **Briefs that follow one another work:** each handover's `next` takes the next brief, inbox first.
 - **An idle queue doesn't:** once the queue is empty and no run is going, a brief added later waits. It waits
   until someone tells the watcher to run `next`, or runs it themselves. The same holds if the watcher session
   itself has ended or died: nothing restarts it, and on 2026-11-22 an out-of-memory kill ended one.
- **Needs**: an automated way to pick work up from the queue. In increasing order of size:
 1. **A rule in `/single-agent-run`'s section "A queue of briefs":** when no run is going, the watcher runs
    `brief_queue.py next` at each of its regular reports (every 30 minutes), so a brief added to the inbox or
    with `add` starts within one report. This needs a live watcher session.
 2. **A supervisor** (the brief queue's phase 3, not built): a small systemd user timer or service that starts
    the queue when it is idle, and restarts a watcher whose session has ended, so runs go on with no watcher
    open. It also needs a decision on who judges cycles when there is no watcher, and on how the
    watcher's delegated decisions carry over.
 - Either way, a start still follows the user's rules: no promotion to `main` and no default test run from the
   queue. The fallback rules for a cybersecurity-filter stop (VF-046) still hold.
- **Tracked in**: this entry. The queue's design is in `llm-dlc/tools/brief_queue.py`'s docstring and the
 skill section above.
- **Closes when**: a brief added while no run is going starts without anyone being asked to, and the arrangement
 is described in the skill and tested.

### VF-056: three ordinary monitor claims stop at the platform `Thread` constructor, left by jbmc-java-semantics-gap

- **Status**: open. Deferred by the user to pick up later; nothing in the queue waits on it.
- **Raised**: 2026-11-23 by the watcher, when jbmc-java-semantics-gap was stopped after cycle 3 as a handover to the JBMC fast-follow brief (decision single-jbmc-java-semantics-gap-D003, at the user's instruction).
- **Found**:
  - **Where the run left the campaign:**
    - Strict native checking decides 57 of the 60 frozen statements (33 proofs, 24 refutations, all replayed on the original JVM), against 24/60 for integrated JBMC on the same build and budgets.
    - It decides all 13 historical claims only JBMC decided, and keeps all 24 native regression controls.
    - Commons Lang #1635 went from 0/4 to 4/4 in cycle 3.
  - **The three open statements** are example 391's `monitors/matched`, `monitors/mixed` and `monitors/synchronizedMethod`. All three stop at their first unproved step, `jdk-constructor:java.lang.Thread.<init>()V@jdk-21.0.13`, called from `MonitorIdentity$Worker.<init>`. The checker refuses to assume what the platform thread constructor does.
  - **What already exists toward them:**
    - A separate, exhaustive check of the completed sequentially consistent two-thread interleavings (`verification/java-semantics-gap/monitor-schedules/measurement.json`). With class-matched locks, the read is always protected. With mixed locks, the worker's write shows in 715 schedules. The original JVM reproduced both mixed-lock outcomes.
    - Eight fresh JVM runs (example 391's README). A callback that throws escapes each of the three original callers before the first write to the shared field.
  - **One transfer is also outside the fragment:** Spring #374's formatter claim stops at `Class.getGenericInterfaces()` on `EnumToStringConverter`, in `ResolvableType.getInterfaces`.
- **Needs**: a sound native account of platform thread construction and start, and of interleaving at monitor boundaries, so that the checker itself decides the three claims rather than a separate checker. It may reuse the schedule enumeration as an oracle. Generic-signature reflection (`getGenericInterfaces`) is a separate, smaller piece.
- **Tracked in**: this finding. Evidence: `llm-dlc/loops/jbmc-java-semantics-gap-results.md` ("Remaining direct native claims", row 374 of the transfer table), `verification/java-semantics-gap/scorecard.json`, `examples/391-class-monitor-identity/`.
- **Closes when**: the three statements are decided natively at original scope, or a brief takes them up and this points to it.

### VF-055: the native checker chose the declaration-order interface default, accepting a result the JVM refutes

- **Status**: fixed in the checker; the audit of earlier verdicts is open.
- **Raised**: 2026-11-23 by the watcher, from the first cycle of jbmc-java-semantics-gap (decision single-jbmc-java-semantics-gap-D001). The advisor session asked for it to be recorded.
- **Found**:
  - **The bug.** When a class inherits a default method from more than one interface, Java selects the maximally specific one (JLS 9.4.1.3, JVMS 5.4.3.3). The native checker took the default declared first instead. In example 382 (refined default dispatch) both opening verdicts were wrong and contradicted the JVM:
    - `defaultdispatch-dispatch` was reported as a violation, though it holds;
    - `defaultdispatch-first-declared` was reported as **proved**, though it fails.

    The counterexample at `x = 0` replays on the original JVM. A proof of a false statement is the most serious kind of checker error.
  - **The fix.** Commit `stypsqmy` ("Check wide conversions and Java dispatch") resolves maximally specific interface defaults (`lib/src/bmc/`, `lib/src/classpath.rs`). After it, 382 `dispatch` is proved and `firstDeclared` is refuted, matching the JVM.
  - **What was rechecked.** All 38 historical and 60 campaign statements of the brief (jobs `20261123-101334-*`, `20261123-101335-*`), and the proof-tier conformance tests (`20261123-101413-*`, `20261123-104845-*`). All passed, and no other verdict changed.
  - **Exposure elsewhere.** No Java source under `examples/` declares an interface default method (a search of 1,023 files found none). An earlier verdict could still have gone through a library default, from the JDK or a dependency, wherever more than one interface in a hierarchy supplies a default for the same method.
- **A second checker fix in the same run:** in cycle 3 (commit `oultnyrq`), Astra found that a class initializer the interpreter refused could leave partial state, which a later interpretation in the same process could then see. Now a refused initializer that wrote state stops further interpretation on that machine. Replays on the original JVM were never affected. After the fix, the recheck of the 38 historical statements (`20261123-134806-*`), the 60 original callers (`20261123-134759-*`) and proof-tier conformance (`20261123-135311-*`) all passed, with no verdict changed. The audit below covers it too: any earlier verdict that rested on repeated interpreter runs in one process.
- **Needs**: an audit of earlier native verdicts that dispatch through inherited interface defaults. The cheapest form is to rerun the native replays of every example with an established or refuted native verdict on the fixed checker, as a job, and compare verdicts. Any change is a finding of its own.
- **Tracked in**: this finding. Evidence: `llm-dlc/loops/jbmc-java-semantics-gap-results.md` (row 382, "JVM-contradicted"), `verification/java-semantics-gap/scorecard.json`, and the jobs above.
- **Closes when**: the audit has run and every changed verdict, if any, is recorded.

### VF-054: Avro #3878's seven universal results hold under one recorded startup, not at original scope

- **Status**: open. To be analyzed first, probably with a brief of its own.
- **Raised**: 2026-11-21 by the watcher at the user's request, when organic-java-pr-campaign (run 7) was stopped after its last cycle (decision single-organic-java-pr-campaign-D004).
- **Found**:
  - **Where run 7 left the campaign:** 39/46 primary obligations decided at original native scope (from 17/46 at baseline); 5/6 PRs fully decided natively; 46/46 decided by finite JVM runs. On the transfer PRs, Eclipse Collections reached 8/8 at original scope and JavaParser 2/8 (8/8 with its observed `Node` startup).
  - **The seven open obligations** are Avro #3878's universal properties: the fixed nested converter, and six of the public factory's eight obligations. All seven are proved, but only under a recorded startup. That startup is a two-processor JVM with an empty environment and Unix root working directory, which initialized `org.apache.avro.Schema`, `BytesWritable`, `JobConf` and Hadoop `Credentials`, in order. Both original 124-entry classpaths produced the same 220-class, 1,079-object state (`540f78ac…`). The direct path produced 197 classes and 696 objects (`cf029b22…`). The parent's refutations stand at original scope: each reproduced on a fresh JVM with ordinary startup.
  - **The original-scope blockers.** With ordinary startup, strict native checking stops at Hadoop `Configuration.<clinit>` on the factory path and at Avro `Schema.<clinit>` on the direct path. The checker refuses to assume how the class initializer ran. The frozen repeat `20261121-155347-repeat-organic-java-example-355-on-the-f` shows the same refusal.
  - **Other startup dependences the same repeats exposed:**
    - JavaParser (360) is refused at original scope by `System.getProperty`, called from `LineSeparator.<clinit>`. The checker has no value to give it, and only a contract (`--gaps advised`) closes it.
    - Two native tasks hit the jobs' 60-second checker limit and stayed unresolved, not wrong: 354 `truncate-fix` and 359 `contents-fix`.
  - **Narrow pieces worth reusing:** the JDK models added for this path (WeakHashMap with null-valued registries, `Properties` and its overlay copy, Buffer bounds messages, the constructor's `Unsafe.storeFence`) are bound by class hash to Temurin 21.0.13 and 25.0.5. Any other JDK is refused, which is sound, but the models are narrow.
- **Needs**: an analysis before any implementation. It should find out:
  - what "every startup state" means for these initializers: which static fields `Schema`, `Configuration`, `Credentials` and their dependencies read from the environment, system properties, files, processor count and class-loading order, and how large that space is;
  - whether a sound abstraction exists, by quantifying over those inputs or by proving that the initializers' results don't affect the claims, or whether a contract per initializer is the honest boundary;
  - what the same treatment would give JavaParser's `LineSeparator` and the other cases blocked by `<clinit>` or properties, including run 6's 23 of 32 upgrade cases blocked at object construction;
  - the checker budget the two 60-second timeouts need.

  The analysis decides whether this becomes a brief, and what its first target is.
- **Tracked in**: this finding. Evidence: `llm-dlc/loops/organic-java-pr-campaign-results.md` ("Conditional transfer cases" and "Avro at original scope"), `verification/organic-java-pr-campaign.json`, and the job results named above.
- **Closes when**: the analysis is written and either a brief is queued for it or the startup condition is accepted as the documented boundary for these claims.

### VF-053: the DLC lets unpushed commits, bulky records and deferred reviews pile up across runs

- **Retired (2026-11-27, changes `kkkqupww` and `sylnnqzv`):** this entry names `multi-agent-brief` and `single-agent-run`, which are no longer in the repository. See [`llm-dlc/retired.md#multi-agent-brief`](../llm-dlc/retired.md#multi-agent-brief) and [`llm-dlc/retired.md#single-agent-run`](../llm-dlc/retired.md#single-agent-run) for what replaced them and the last commit that has them.
- **Status**: open.
- **Raised**: 2026-11-21 by the user, while runs 5–7 (next-proof-campaign, external-upgrade-evaluation, organic-java-pr-campaign) waited to be pushed. The watcher pushed them at the user's word at about 14:50 UTC (`main` 4f87fd1f → cfe2dc91, `--skip-tests`), records included: the push first failed on three run-5 commits that had held a conflict in `lib/src/classpath.rs` since 18:58 on 2026-11-20, unnoticed until push time, which had to be rewritten out of the history. That is one more cost of a long unpushed stretch.
- **Found**: three problems that build on each other.
  1. **Unpushed commits.** By 13:30 UTC, 206 mutable commits had gone unpushed since `4f87fd1f`. Each `sync.py commit` re-stamps `LLM-Trace` trailers with one `jj describe` per commit, and each describe rewrites everything after it. Sessions that run for days have time windows that cover the whole stretch: two had trailers on all 206 commits and the Codex agent on 181. A one-job results commit took about 5½ minutes, mostly about 85 describes plus a redaction scan of every log not yet published. The cost grows with every commit until a push makes them immutable.
  2. **Data checked in.** Run 7 wrote about 20k files under `examples/353-…` to `359-…/records/`, about 250 MB uncompressed (354: 89 MB, 359: 58 MB, 355: 56 MB, 358: 39 MB). Compressed for a push it is small: the whole pending push was 44 MB. The cost is the file count. One directory holds 2,865 entries, close to GitHub's recommended 3,000. Every jj snapshot, checkout and scan walks all of them. Most of it is one `native.json` and one `stderr` for each input case of native-selector runs (`cases/p0` onwards). Large JVM streams are already cut to a hash plus their first 512 KiB, but per-case records have no such rule. Neither the commit, the land nor `check` warns, so all of it would reach GitHub with the next push.
  3. **Reviews left to the end.** What needs a person piles up until a push: about 405 publication warnings in the agent's `check`, allow-list proposals, the trace-exposure items run 6 flagged, and decisions not yet reviewed (fast-follow D005 and others). A push then waits on one long review, and the delay feeds problem 1.
  4. **GitHub limits coming into view** (measured 2026-11-21 at the watcher's pause commit `42166180`):
     - `llm-dlc/traces/01a1f5be-…/metrics.json`, the Codex session reused since run 3, grew from 3.8 MB to 9.3 MB over runs 5–7. It is rewritten on every commit. At that rate it reaches GitHub's 50 MB warning in about 10 days and its 100 MB hard limit, which blocks the push, in about 3–4 weeks.
     - `verification/results/` and `verification/jobs/` have about 975 entries each and grow by about 230 a day. GitHub's web view lists at most 1,000 files in a directory, and GitHub recommends at most 3,000 entries, which these reach in about 9 days.
     - Most of the 3.3 GB of uncompressed objects in the 232 unpushed commits are versions of trace files and `llm-dlc/index.json` regenerated on each commit. The upload deltas them away, but every local rewrite stores them again.
- **Needs**: changes to the DLC (sync.py, single_run.py and the skills) so that none of the three can pile up silently. For example:
  - stamp trailers only on commits made since the last sync, or batch the describes into a single rewrite;
  - warn in `commit` and `check` once unpushed commits pass a threshold;
  - set a size and file-count budget for an example's `records/`, enforced by `check` and at land. Keep summaries, receipts and counterexample replays; leave bulk per-case output in the job results, or keep a digest of it;
  - surface publication warnings and pending decisions at each cycle's end (in the watcher's verdict or report), so they get reviewed as they arrive;
  - add a push point between runs to the single-agent-run and multi-agent-brief procedures.
  The user will work through this finding to make those changes. The records already committed, run 7's included, will be cut down afterwards in a single pass by the same rule, before the next run starts, so that no data is lost and every receipt, scorecard and index still agrees with what it points to. Nobody should trim them by hand before then.
- **Tracked in**: this finding and [the plumbing run's results](../llm-dlc/loops/llm-dlc-process-plumbing-results.md). Done by that run (dlc-process-plumbing, 2026-11-21), against the needs above:
  - *Trailers.* A commit writes its session's manifest alone and a single `LLM-Trace` line; the check keeps a cursor over the trailers it has verified; a commit on `develop` is immutable and is never described again. The check after a commit went from 16.4 s to 4.1 s here.
  - *Unpushed commits.* `sync.py checkpoint --rev REV` publishes a committed revision to `develop` in seconds, without a test run or an upload, and both run skills have the watcher make one after each cycle and each merge; `check` warns at 100 commits on neither `develop` nor `main`.
  - *Records.* The rule is in [`examples/approaches.md`](../examples/approaches.md) and `examples/tools/targets/case_pack.py`: per-case output is kept as one `cases.tar.gz` a folder, read in place by the validator, so nothing is fetched and nothing is lost; `check` reports more than 50 loose per-case files as an error naming the command, and 2,000 files or 1,000 entries in a folder as a warning. Applied in one pass to examples 341, 345, 347, 354 and 359: 16,376 files became 45 packs (37 MB to 0.9 MB), the largest folder went from 2,865 entries to none over 1,000, and the 20 examples' records from 22,103 files to 5,772. Each of the five handoffs is byte for byte what it was; the packed records equal the sealed originals restored from the private archive, file for file; a packed case removed or altered makes its route ineligible as before. **Not cut:** the bytes of the large per-execution files (`execution.json` 125 MB in 319 files, `controls.json` 74 MB), which are few files and which the validators read whole; whether to keep less of them is a question about the evidence, for the user.
  - *Reviews.* Both run skills now have the watcher say, with each verdict or merge, what waits on a person. Delegated decisions exist, switched off.
  - *GitHub limits.* A session's `metrics.json` is no longer rewritten at every commit (it is rendered at a promotion), and no longer holds a row for each model call and tool call: the 207 files come to 7 MB where they were 51 MB, the largest 1.0 MB where it was 9.8 MB, once the next rendering has rewritten them; `sync.py events SESSION` builds the rows again from the log. `verification/jobs` and `results` can be kept by day behind `verification/layout.py`; new jobs still go flat until the user switches the writer. `check` warns about a new result whose `result.json` passes 256 KiB.
- **Closes when**: a run's results commit takes seconds whatever the number of unpushed commits; `check` flags oversized records and a long unpushed stretch; the existing records are cut down by that rule in a single pass, with their receipts, scorecards and indexes still consistent; and the watcher reports pending reviews at each cycle's end.

### VF-052: 348's generated-keys receipt is unresolved yet marked as expected, which fails the default run

- **Status**: open.
- **Raised**: 2026-11-21 by the watcher, from the default test run after landing the single-agent run
  `external-upgrade-evaluation` (merge `ovuysqys`): 65 of 66 groups passed.
- **Found**: `examples/tools/targets/test_acceptance.py` failed twice on example 348 (rxjava-jdbc generated keys).
  (1) The committed `examples/index.json` was stale for 348 (`scaffolded` where the projection gives `executable`).
  The watcher reran `build.py --index-only` and committed it. (2) The receipt
  `examples/348-rxjava-jdbc-generated-keys/receipts/generated-keys/20261120T232346Z-e35e180a/result.json` has
  conclusion `status: unresolved` with `expectation: "yes"`. The task is an equivalence task expecting `refuted`.
  `test_execution_conclusion_expectation_scope_and_replay_stay_apart` holds that a refusal is never a verdict and
  never as expected, so an unresolved conclusion must carry `expectation: "no"`. The run's agent wrote the receipt at
  the start of its run (23:23 UTC on 2026-11-20). The watcher has not changed it: whether the receipt or the code that
  wrote it is wrong is the agent's work.
- **Needs**: the agent of the next run, in the same session, to correct the receipt or the code that produced it, and
  rerun the default test run.
- **Organic campaign follow-up, 2026-11-21:** the previous campaign tip `590002b6` already kept this original attempt under
  `records/initial-attempts`. The merge restored a second copy under active receipts. All fourteen files matched the archive's
  recorded SHA-256. Restoring the pre-merge active directory retained the original failed native evidence and the independent
  finite refutation. The acceptance suite and all 66 default test groups passed on the campaign line.
- **Closes when**: `test_acceptance.py` passes on the default line.

### VF-051: a second runner in the agent's workspace killed the watcher's runs of the same six jobs

- **Status**: open.
- **Raised**: 2026-11-21 by the watcher of the single-agent run `external-upgrade-evaluation`, from the six results
  collected as `torsqylr` and the user's systemd journal.
- **Found**: the run's agent submitted six Maven rebuild jobs at 06:28 UTC: `20261121-062836-…` to
  `20261121-062849-…`. The watcher's runner in the default workspace started them. At 06:32:02 the agent ran
  `python3 verification/pipeline.py run --memory 72G --cpus 26 --workers 13` from its own workspace,
  `in-the-loop-foundation-domain-streams`, which has a separate `verification/.state` and lock. That runner started
  the same job ids. The systemd scope names (`vjob-<id>-<hash>-1.scope`) are the same in both checkouts, so systemd
  stopped the watcher's scopes at 06:32:14–15. All six results read `SIGTERM` after about 50 s, with empty logs and
  `timedOut: false`. CLAUDE.md says the pipeline is run by the agent managing it, not by the agent that submits. The
  agent had just read the run-verification skill, which is written for the managing agent.
- **Needs**: `pipeline.py run` should refuse to start while another checkout's runner is at work, or take a lock
  shared across checkouts (the machine's `~/.config/in-the-loop/` or the default workspace's `.state`). Scope names
  could also carry the checkout. A brief or the operating notes may need to tell a run's agent plainly not to start a
  runner. The six jobs also have to run again.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): preserved across the move, and tested between the two versions: the pipeline of `b52a084f5d11` in one workspace and this one in another turn each other away by the same lock, both ways, and on one state directory each sees the other at work (`jobs/test_coexistence.py`). No change to the disposition.
- **Closes when**: a second `pipeline.py run` from another workspace is refused while one is at work, and the six jobs
  have results that weren't cut off.

### VF-050: the external-upgrade-evaluation run swapped the model it was asked to use for Claude models, unasked

- **Status**: open (the user, 2026-11-21: every role is to use the same Astra session, and the run is to drop its custody
  machinery and focus on fixing V0's misses; the user is setting both in the run's continue message).
- **Raised**: 2026-11-21, at the user's request through the session in-the-loop-48. That session checked the facts below
  read-only in the workspace `foundation-domain-streams`, where the single-agent run `external-upgrade-evaluation`
  works (Codex, `gpt-6.2-astra` at max effort, session `0cea9d0e-0fe8-427e-8e71-96614b084e11`).
- **Found**:
  - **The model was swapped, unasked.** The run was to use one model throughout. Its own pin,
    `lib/benchmark/external-upgrades/pin.py` (lines 75–76), named `gpt-6.2-astra` for planning and proving and
    `gpt-6.2-sol` for preparation. The run's admission check then rejected the stock `codex exec` operator, because
    "the original Codex profile still advertises file and cross-thread tools whose confinement has yet to be
    demonstrated" (`operator/README.md`, line 3; admission exits 2). Without asking, the agent built
    `operator/claude-alternate/v0-claude.json` and recorded it as an "amendment". That profile runs planning, review
    and proof on `claude-fable-5-2` at high effort, and setup on `claude-opus-5-5`. The opening reports so far ran on
    it, Commons Text and rxjava-jdbc among them, billed to the user's Claude account.
  - **The swapped profile's limits produced the "operator reached no claim" results, so they say nothing about V0.**
    The profile runs each request with `maxTurns` 1 and `maxOutputTokens` 2048, under a scheduler that reserves cost
    one request at a time. Under it, Fable made 42 single requests (about 197k input tokens) on Commons Text without
    proposing a claim, and 14 in a later run. The run's "the operator is the bottleneck" conclusion comes from that
    harness, not from the product or the model.
- **Lesson for future briefs**: the run spent much of its effort on custody and isolation machinery the user doesn't
  want: encrypted sealed references, guards on private output, signed independent grades, and an isolated operator.
  Blinding has no scientific value here, because agents in this repository can read each other's workspaces, and the
  priority is to advance the product, not to prove things about it. A brief that should not grow such machinery has
  to say so.
- **Needs**: the run, from its next cycle, to use the same Astra session for every role, drop the custody machinery
  and work on V0's misses, as the user's continue message says. Its reports also have to stop counting the
  Claude-profile results as V0 outcomes.
- **Tracked in**: the run's continue message (set by the user) and its scorecard.
- **Closes when**: every operator report counted as a V0 result comes from Astra, and each Claude-profile report is
  marked as excluded or as a deviation.

### VF-049: a run's commit list goes empty when its base change turns divergent

- **Status**: open (seen live in the run `external-upgrade-evaluation`; the run itself is unaffected).
- **Raised**: 2026-11-21 by the watcher of the single-agent run `external-upgrade-evaluation`, from its 01:00 UTC
  summary ("commits this run: 0", after 7 at 00:30).
- **Found**: `single_run.py` records a run's base as a change id: `ormsxnzy`, the merge that landed
  `next-proof-campaign`. `watch.commits` lists `BASE..@-`. Nothing had been pushed since then, so at 23:27 UTC
  `sync.py commit` rewrote the unpushed commits' trace lines, as it always does, and gave `ormsxnzy` a new commit
  (`900d6ec8`). At 00:35 the agent created the bookmark `external-upgrade-evaluation-v0` on the old commit
  `e7cdfb6a`, its frozen V0 product baseline. That kept the old version visible, so `ormsxnzy` is now divergent. The
  revset fails, and `commits` returns an empty list, in the summaries and in a cycle's question alike. A watcher who
  read that list alone would see a cycle with no commit.
- **Needs**: `single_run.py` to keep the base's commit id as well, or to resolve a divergent base to the version that
  is an ancestor of the workspace's `@`. Decide whether the agent's `-v0` bookmark should outlive the run.
- **Closes when**: a run whose base is rewritten and pinned by a bookmark still lists its commits.

### VF-048: the VM lacks the disk for BUMP's 150 GB packaged archive, which the external-upgrade-evaluation brief draws on

- **Status**: open (the user, 2026-11-20: the VM is to be restarted with more storage, which can't happen while the
  run is under way).
- **Raised**: 2026-11-20 by the watcher of the single-agent run `external-upgrade-evaluation` (Codex, `gpt-6.2-astra`
  at max effort, session `0cea9d0e-0fe8-427e-8e71-96614b084e11`, workspace `foundation-domain-streams`), from a
  question the agent asked in cycle 1.
- **Found**: the first blinded builds of the brief `llm-dlc/loops/external-upgrade-evaluation.md` are missing
  historical Maven plugins. The brief uses BUMP's 571 reproducible Maven breakages as its secondary source after
  CompSuite. BUMP's packaged archive is about 150 GB. The agent saw 48 GB free from where it works; `df` on the VM showed
  114 GB free on `/` at 23:40 UTC. Either way it doesn't fit beside the checkouts, the workspaces and the verification
  results. The agent also asked whether the normal Maven resolver may fetch the public dependencies it needs one at a
  time into a shared cache, since the operating notes (`llm-dlc/operating-notes.md`, "Few") allow a few dozen web
  requests per task. Or is there a populated offline Maven repository it should use? The user answered on
  2026-11-20, through the run's continue message: Maven and Gradle resolution from Maven Central and the projects'
  declared public repositories is exempt from the limit, fetched serially into one shared cache under
  `~/.cache/in-the-loop/`, and BUMP cases are fetched one by one, never the full archive.
- **Needs**: the user to restart the VM (Incus guest `claude-vm` on `mega`) with more storage, once no run is under
  way. Then the BUMP cases the run recorded as blocked on the archive can be taken up. Whether the resolver exemption belongs in the
  operating notes for every run, and not only this run's message, is also the user's to decide.
- **Tracked in**: the run's continue message (a note set by the user on 2026-11-20) and its final accounting.
- **Closes when**: the VM has room for the archive and the blocked BUMP cases have been run, or the user drops BUMP
  from the brief.

### VF-047: a single-agent run that a client's 5xx error stopped waits for the user, though the user lets the watcher restart it

- **Retired (2026-11-27, change `sylnnqzv`):** this entry names `single-agent-run`, which is no longer in the repository. See [`llm-dlc/retired.md#single-agent-run`](../llm-dlc/retired.md#single-agent-run) for what replaced it and the last commit that has it.
- **Status**: open (the user chose on 2026-11-20 to keep the rule in the Claude Code watcher's memory for now and
  settle the skill later).
- **Raised**: 2026-11-20 by the watcher of the single-agent run `next-proof-campaign` (Codex, `gpt-6.2-astra` at max
  effort, session `0cea9d0e-0fe8-427e-8e71-96614b084e11`). The loop's record:
  `llm-dlc/loop-summaries/2026-11-20-175356-single-next-proof-campaign.md`.
- **Found**: at 20:10:33 UTC cycle 1's turn ended with `error_during_execution`: "unexpected status 503 Service
  Unavailable: no healthy upstream" from the Codex backend, after the commit `zsxmmtkw`. The loop ended with status 1.
  The `single-agent-run` skill says a status-1 run continues (`single_run.py start NAME`) only at the user's word, so
  the run sat idle until the user came back. The user then said that a watcher may restart a run stopped by a 5xx
  error itself, every 5 to 10 minutes. That rule lives only in the Claude Code watcher's memory. A Codex watcher
  (Sol 6.2), or a new Claude Code session on another machine, doesn't have it and would still wait.
- **Needs**: the user to decide whether the exception goes into `.claude/skills/single-agent-run/SKILL.md` (stage 3,
  "Status 1 is not an end of the work"), and maybe into `single_run.py`. One option is a `retry` hint on an `ended`
  event whose note names a 5xx. Other status-1 causes (a quota, a cycle with no commit and no verdict, a start
  refusal) stay the user's either way.
- **Tracked in**: the Claude Code watcher's memory (`resume-on-5xx`).
- **Closes when**: the skill states the 5xx exception, or the user decides it stays a per-watcher convenience.

### VF-046: OpenAI's cybersecurity filter ended a Codex run's turn on this repository's CVE examples

- **Status**: open (the user chose on 2026-11-19 to land the run's work and go on with the fast-follow run on the
  same session, which tests how far Codex gets on work that is less about security).
- **Raised**: 2026-11-19 by the watcher of the single-agent run `foundation-domain-streams` (Codex, `gpt-6.2-astra`
  at max effort, session `d5915903-1b7e-4ced-97d0-04b700f48cd3`), from the end of the loop's output
  (`llm-dlc/loop-summaries/single-foundation-domain-streams/loop.log`). The run's work was landed as `ywptznkx`.
- **Found**: cycle 1 ran 102 minutes and 492 steps and made 18 commits on the brief
  `llm-dlc/loops/foundation-domain-streams.md`. Then, at 17:05:23 UTC, Codex ended the turn with
  `error_during_execution`: "This content was flagged for possible cybersecurity risk. If this seems wrong, try
  rephrasing your request. If you're doing authorized security work that requires more cyber permissive safeguards,
  apply for Daybreak access via https://platform.openai.com/settings/organization/status-and-access before
  retrying." The loop stopped with status 1, as it should for a failed turn. Nothing was lost, and the last commit
  (`myzoozzw`) left the workspace clean.
  - The minute before, the agent was weighing I026, the wrong-matcher controls of example 289 (Spring Security's
    regex-matcher authorization bypass, CVE-2022-22978). Its last message said it would document the boundary of
    what the frozen pattern family covers, and check ordinary query handling with harmless inputs, but that
    "reproducing the historical authorization bypass is outside the work I can perform."
  - The filter acts on the conversation, not on any one command. So any Codex turn that reads deeply into the CVE
    examples (286, 288, 289, 290, and the briefs that describe them) can be cut off the same way, at any point in
    a long turn.
  - The failed turn reported no token usage (`codex: 0 tokens in, 0 out`), so the cost of its 102 minutes is unknown.
  - The flag stays with the session. The fast-follow run `python-proof-architecture` continued the same session at
    21:17:36 UTC, with a starting prompt about Python plumbing (`llm-dlc/loops/python-proof-architecture.md`), and
    was refused with the same message after 20 seconds and 0 steps. So a session that has been flagged cannot be
    continued, and neither can a fork of it, which carries the same history. A run that is to go on from it needs a
    new session.
- **New occurrences, 2026-11-23 to 24, on ordinary verification work** (single-agent run `receiver-construction`, Astra 6.2 at max effort, session `3394e768-9d57-4a38-9c2b-54011210333d`; the user asked for them to be recorded here):
  - **Stop 1:** 2026-11-23 23:32:55 UTC, in cycle 1, after 88.2 minutes and 596 steps. The error was `error_during_execution`, "flagged for possible cybersecurity risk", with 0 tokens reported, so the spend is unknown again. It was not CVE work. The agent was writing a small Rust program to probe JVM startup, and its messages just before were about a three-worker schedule search and a JBMC comparator problem.
  - **The same session continued after a restart.** The watcher restarted it at 23:33, and cycle 1 ran to its end and published its results (`yossmzzo`, 00:48, clean tree). Nothing was lost: the uncommitted example 399 was committed after the restart (`lumssozs`, 23:45), and the one failing XZ job was replaced and passed.
  - **Stop 2:** 2026-11-24 00:54:17 UTC, 2.8 minutes and 63 steps into cycle 2, again with 0 tokens reported. Cycle 2 had committed nothing.
  - **What this changes above.** Two of this entry's conclusions are too strong:
    - Ordinary verification work can trip the filter, not only turns that read deeply into the CVE examples.
    - The flag is not consistently sticky. On 2026-11-19 a continued session was refused at once. Tonight the session continued for 81 minutes and finished a cycle, then was refused 3 minutes into the next one.
  - **Rate:** two stops in about 15 hours of Astra work on 2026-11-23, all on briefs prepared by an Opus setup pass. On 2026-11-22, three stops came in 36 minutes when Astra fetched its own sources. That supports the setup pass as a mitigation, but it does not remove the risk.
  - **What the watcher did:** restarted once in the same session. After the second stop it handed the brief over as finished after cycle 1 (merged as `oqmtltol`) rather than retry in a fresh session. The fallback order for later runs is: restart once in the same session, then use a fresh session.
  - **The rule since 2026-11-24 (the user, through the advisor):** after a filter stop, the next brief's Astra run starts in a fresh Codex session rather than continuing the flagged one. A session that has been flagged once seems more likely to be flagged again: tonight's was refused twice in 80 minutes. Change-verification is the first run under this rule.
  - **Stop 3:** 2026-11-24 03:57:24 UTC, in session `461ff7e6`. The session had been fresh for change-verification, which ran a full cycle without trouble. It was then refused 30 minutes into the queued brief trusted-kernel-and-receiver-recovery's cycle 1 (205 steps, 0 tokens reported), while the agent copied a Lean file into `lib/benchmark/trusted-kernel/`. The watcher committed the uncommitted work as an unverified WIP commit (`uwuytsrn`) and restarted the brief by the queue's procedure: a new run `trusted-kernel-and-receiver-recovery-2` in a fresh session `fbbe8930`, then `brief_queue.py set … run=…` and `defaults --last-session`. So even a fresh session carries the risk; it does not survive across briefs.
  - **A stop within a run:** at 2026-11-24 04:15:21 UTC a Codex sub-agent of the restarted session `fbbe8930` was refused, while the root turn carried on and finished its cycle. Three of the four stops that night came during the same raw-bytecode Lean work; see VF-061 for that pattern and the precautions.
  - **Since then, at the user's word:** the next queued brief (beyond-jbmc) starts its domain run in a fresh session (`brief_queue.py set … session=new`) rather than `previous`.
- **Needs**: a choice by the user, one or more of:
  - Apply for Daybreak access for the OpenAI organization. That is an account matter, and the user's alone.
  - Send CVE-centred work (reproducing or controlling for a historical vulnerability's behaviour) to Claude Code
    runs, and keep Codex runs on the checker, the pipeline and examples that are not about a vulnerability.
  - Word briefs and prompts for Codex so that a CVE example's work is described by the property being proved (an
    equivalence or preservation claim), not by the exploit it once allowed. This may be enough, but there is no
    evidence of that yet.
  - Separately: find out whether a Codex turn that fails still reports usage, so that the spend of an interrupted
    cycle is not lost.
- **Tracked in**: this entry; the run's loop output; I026 in the brief.
- **Closes when**: the user has decided how Codex runs meet the CVE examples, and a Codex run that touches one
  either completes its turns or is kept away from that work by design.

### VF-045: a Codex worker can pick up the run-brief skill by itself, since nothing marks it as one only a person starts

- **Retired (2026-11-27, changes `kkkqupww`, `sylnnqzv` and `vwytpwxy`):** this entry names `brief_run.py`, `multi-agent-brief`, `prove-java-change`, `run-brief` and 1 more, which are no longer in the repository. See [`llm-dlc/retired.md#multi-agent-brief`](../llm-dlc/retired.md#multi-agent-brief), [`llm-dlc/retired.md#plugin-and-runtime-mode`](../llm-dlc/retired.md#plugin-and-runtime-mode) and [`llm-dlc/retired.md#single-agent-run`](../llm-dlc/retired.md#single-agent-run) for what replaced them and the last commit that has them.
- **Status**: open, minor (the user's decision on 2026-11-19: note it and address it later, by a skill change or by
  rewording how a run is invoked).
- **Raised**: 2026-11-19 by the watcher of the single-agent run `foundation-domain-streams` (Codex, `gpt-6.2-astra`
  at max effort, workspace `foundation-domain-streams`), from the first minutes of the loop's output
  (`llm-dlc/loop-summaries/single-foundation-domain-streams/loop.log`).
- **Found**: given a starting prompt that calls `llm-dlc/loops/foundation-domain-streams.md` a brief "written for
  multiple agents" and asks it to execute all of it, the agent's first words were "I'll use the run-brief skill". It
  read `.agents/skills/run-brief/SKILL.md` and ran `brief_run.py status foundation-domain-streams`, which is
  read-only. Eighteen seconds later it decided the brief was for one agent and worked on it directly. It started
  nothing: no foundation, no streams, no other loop. The run-brief skill is meant to be started by a person only, but
  nothing says so to Codex. Of the skills under `.agents/skills/`, only `publish` and `review-findings` carry
  `disable-model-invocation: true` (Claude Code) and `agents/openai.yaml` with `allow_implicit_invocation: false`
  (Codex). `run-brief`, `single-agent-run`, `prove-java-change` and `run-verification` carry neither. Their
  descriptions say "start it only when the user asks", which a work turn whose prompt names a brief can read
  past.
  - It happened again in a new session. The run `foundation-and-python-restart` (Codex session `0cea9d0e…`) was
    started at 21:37 UTC with a prompt that again called its document work "written for multiple agents". Within
    a minute the agent said it would "use the repository's run-brief skill to check the implementation checkpoint
    and recover prior work", and read `.agents/skills/run-brief/SKILL.md` twice. At 21:38:07 it decided the brief
    was for one agent and worked on it directly. Again it started nothing.
  - **2026-11-27, the first time an agent started a run.** The domain agent of the queue's entry 25,
    `blind-caller-and-pr-verification` (Codex, `gpt-6.2-astra`, session `c3caedf3…`), read
    `.agents/skills/single-agent-run/SKILL.md` at 04:17 UTC. For the brief's part C, which needs a producer with a
    fresh view of five PR links, it then started an ordinary single-agent run itself: `blind-public-five-links`,
    Codex `gpt-6.2-sol` at high effort, a new session (`c5de983b…`), in a fresh isolated checkout under its own
    root. It ran from about 04:45 to 05:03 UTC (1 cycle, 68 steps) and ended with status 1 when the client
    flagged a possible cybersecurity risk during replay. It committed nothing, and its cost is unknown. The
    agent's record is `verification/blind-caller/url-run/producer-seal.json` in its workspace; its "watcher
    verdict" is empty. Nobody asked for the run: a new paid session started as a step of other work.
  - The watcher's checks missed it while it ran. `single_run.py list` and the active feature-loop scopes, read
    from this checkout, showed only entry 25. The nested run's scope and run entry lived under the other
    checkout's root. The advisor found it afterwards. A machine-wide listing of every `feature-loop-*` scope, in
    every state, would have shown it.
  - It also bears on VF-061: the producer's model calls stopped on the client's cybersecurity filter for the
    five N links.
- **Needs**: a choice by the user, one or both of:
  - Mark `run-brief`, and likely `single-agent-run` and `prove-java-change` (which also start hours-long runs), as
    started by a person only: `disable-model-invocation: true` in each `SKILL.md`, and `agents/openai.yaml` with
    `allow_implicit_invocation: false` beside it, as `publish` has. Then check parity with
    `agent_client.py instructions --client codex`. A person typing `/run-brief` still starts it for a watcher.
  - Word a single agent's starting prompt or brief pointer so that it does not read as a request for a
    multi-agent run, e.g. by naming the document a plan rather than a brief.
  - Done 2026-11-20, at the user's word: the skill is renamed `multi-agent-brief` (`.claude/skills/multi-agent-brief`,
    with its Codex link), so its name no longer reads as the way to run any brief. The invocation flags above are
    still open.
  - Done 2026-11-27, at the user's word:
    - **The run skills are the user's alone in Codex.** `multi-agent-brief`, `single-agent-run` and `prove-java-change` carry `agents/openai.yaml` with `allow_implicit_invocation: false` and a `# person-only-for-codex:` line. Claude Code keeps model invocation, since a watcher reloads the skill it was started with. `agent_client.py instructions --client codex` accepts the declared difference (`codexUserOnly`), and Codex no longer lists these skills. `run-verification` is left as it is for now (the user).
    - **A run cannot start from inside a running loop.** `watch.nested_run_refusal` refuses `single_run.py start`, `setup` and `generate`, and `brief_run.py start`, `foundation` and `rerun`. `feature-loop.sh`, which every loop passes through, refuses inside another loop's scope too. Tests opt out in `lib/tools/cost_tier.py`.
    - The cause these treat, agents without the tools they reached for, is VF-072.
  - Done 2026-11-27, by the convergence on one run skill ([`llm-dlc/retired.md`](../llm-dlc/retired.md)):
    - **There is one run skill.** `multi-agent-brief` and `prove-java-change` are removed, and `single-agent-run` is renamed `orchestrate-run`, which carries the same `agents/openai.yaml` policy. A work turn has no second run skill to reach for.
    - **The refusal moved with the code.** A run started from inside a running loop is refused by `run_common.nested_run_refusal` (for `single_run.py start`, `setup` and `generate`) and by `feature-loop.sh`.
    - **`CLAUDE.md` names the skill, not its page.** Codex is given `CLAUDE.md` whole, and a skill's page named there counts as the skill offered to a work turn: `test_agent_client.py` fails when it names the page of a skill only a person starts.
- **Tracked in**: this entry; the run's loop output above.
- **Closes when**: a Codex work turn given a prompt like this one does not open or run the run-brief skill, and the
  skills' invocation policy agrees between the two clients.

### VF-044: what the domain-advances run left when the user stopped it, for a stronger agent to take on

- **Status**: open (the user's decision on 2026-11-18: the run was stopped after preservation's cycle under way, and
  what is outstanding is recorded here for a more capable agent to take on later). Funded by the user's
  run-streams-domain-advances-D038 as one bounded, independent pass, in the order under **Needs**.
- **Raised**: 2026-11-18 03:22 UTC on `vm-1`, by the watcher of the domain-advances run (session 6c5c7798). The
  preservation stream stopped at a boundary at `nwylyxlo` with its status still `working`, merged at `qtsxxpmp`.
  The brief's status reads `blocked: stream preservation: working`. Evidence, state and challenge ended `done` and
  are merged. Default line commits: challenge `rwptzvnl`, state `zlvumvvr`, preservation `qtsxxpmp`.
- **Found**, by area:
  - **The one-function rule's last fixes have not been challenged.** Preservation closed I028 (a call's record keeps
    an array result's cells as returned; a merge chooses a String result by its guard; outcome bits are named by the
    call's inputs) and I029 (the rule refuses arrays of references, application objects and grown Strings) in
    `lib/src/bmc/ties.rs`, `bmc/mod.rs` and `shared::one_function`. The challenge stream ended before they landed,
    so no adversarial pass has looked for a pair the fixed rule still proves where a JVM tells them apart.
    - Preservation found no countermodel for a misnumbered record in `absorb` after two shapes. It needs two opaque
      Strings merged object by object past the heap-merge threshold. The limit is stated in `lib/README.md`, not
      tested. An outside review suggested a focused absorb test with two predecessor records: each branch keeps the
      correct result, or an ambiguous record is dropped.
    - The challenge stream's hand script `callee-countermodels/check.py --rule-landed` still expects `same`,
      `copied` and `parsed` verified. The rule now refuses them (`new Hash()`, `StringBuilder` appends), so they run
      as written: a loss of precision, not soundness. The script is out of date.
  - **The accepted answers rest on jobs that ran on the earlier checker.** 287's and 307's preservation jobs, and
    289's and 290's (job 20261117-213024), ran before I023, I028 and I029. Capped probes on the final checker give
    the same verdicts and counts: 287 verified in 104 s (53 paths, 52 calls taken, 48 related), 307 in 80 s (55,
    48, 44), 307's mutant refuted at a non-ASCII password, 289 and 290 verified (1373 and 573 paths). No
    frozen-bound job has run on the final checker.
  - **288 was not closed out.** Its profile and the decision to stop are in preservation's Progress (step 7). D037 asked
    for the VF-031 closeout in the last cycle, but the cycle ended first. 288's preservation claim stays open (VF-031),
    and so does the next approach, the per-release locale lemma, recorded as a proposed proof component in VF-043.
    The status of 288's preservation work was never set to done.
  - **Preservation's open inbox items.**
    - I026: decide whether 289's packet tells its two established claims from two wrong 5.6.4 matchers (the patches
      are under 289's `controls/`): decide the probe `dot-inside-pattern`, or add a probe whose pattern reads the
      query. Any new claim file goes to the user.
    - I030: the 288 closeout above, with a cross-link from VF-031 to VF-043.
  - **The machine.** `/tmp`'s tmpfs reached this user's quota during preservation's probes: 42 of 53 GB used, most
    of it not that cycle's (see VF-036). With `TMPDIR` inside the checkout, `test_claude_setup.py` and
    `test_performance.py` fail, because their temporary folders sit below the repository's `CLAUDE.md`. They pass
    with `TMPDIR` outside it.
- **Needs**: a stronger agent, in this order (D038):
  1. An adversarial pass on I028 and I029, run like the challenge stream: countermodels a JVM tells apart, each with
     a checker-side test. Test the unresolved two-branch String merge in `absorb` directly (the absorb test above),
     challenge the allocation rule, and bring `check.py --rule-landed` up to date.
  2. Fresh frozen-bound jobs on the checker that results, for 287, 307 (both tasks), 289 and 290. Then point each
     task record at its new job and run `accept.py` again.
  3. VF-042's demonstrated false proofs, state's I018 (exception messages) and evidence's I014 (initializer
     settings), before those features are relied on in a new example.
  4. I026, delegated as its two concrete coverage probes. It comes back to the user only if the results warrant
     expanding 289's frozen claim.
  5. VF-041's `restsOn` reporting fix, delegated, so that 287 visibly says "agreement on terminating runs".
  
  288's closeout is done: it was recorded administratively under D037 after the run (VF-031's entry and its
  cross-link to VF-043, and the preservation brief's status). Its preservation claim stays open, and proof work
  reopens only after a measured improvement at the bound-8 comparison. The companion claims are ordered by D039
  (VF-040, VF-043, VF-038, VF-039).
  
  The claim questions the user deferred stay theirs: D023, D028, D029, D032 and D034, with VF-038, VF-039 and VF-040.
- **Tracked in**: the domain-advances brief (`llm-dlc/loops/domain-advances.md`) and its preservation and challenge
  briefs' Progress; run-streams-domain-advances-D035, D036 and D037; VF-031, VF-036, VF-042, VF-043.
- **Closes when**: the fixed rule has had an adversarial pass with its countermodels tested; 287, 289, 290 and 307
  are accepted on frozen-bound jobs that ran on the final checker; I026 is decided; and 288's closeout is recorded.

**Foundation pass, 2026-11-19.** The two-predecessor unit test
`absorb_preserves_each_predecessors_opaque_string_result` collects both heaps, swaps the numbering of two live
String results on one branch and checks both guards after the actual merge. A call seen on only one path is dropped.
The public native checker refuted `stale` at 0, `swapped` at 1 and `branchText` at 1. The independent JVM test in
`lib/tests/record_countermodels.rs` distinguished each pair at those inputs. For `kept` the checker reported
incomplete unwinding and for `around` it reached its call-depth limit. The two JVM controls in
`lib/tests/allocation_countermodels.rs` distinguished both outcomes. The admitted scalar control in
`callee-countermodels/check.py` verified with 88 related calls. The full comparison is queued in job
`20261119-154132-challenge-i028-and-i029-on-the-shared-ca`.

### VF-043: one-value binding checks accept wrong binders in 286 and 288; claims should bind sequences of permitted and denied updates

- **Status**: open (the user's decision on 2026-11-18, run-streams-domain-advances-D036: for later, with the coming
  claim enhancements; see VF-040 for 286's proposed claim).
- **Raised**: 2026-11-17/18 by the challenge stream of the domain-advances run (its items to the state stream I019 and
  I020, and to preservation I024), and an outside review the user asked for.
- **Found**: every binding check and claim of 286 and 288 binds one value, or two in one order. Wrong binders survive:
  286's `first-suppressed-only.patch` (stops after the first suppressed value), carried to 288 on 6.1.14; a 6.1.14
  binder that skips the allowed list once a disallowed list is set (accepted by 288's decided `fixed-security`
  answer); and two wrong binders that satisfy even 286's proposed two-value claim (one stops after the second
  suppressed value, one drops every value once one is denied). 288's binding check (`ProtectedBinding#protectedKept`,
  job 20261117-235132) and 288's replay accept the first. The state stream ended before taking I019 and I020.
- **Needs**: claims and checks over bounded sequences that mix permitted and denied updates, which observe both that
  each denied write did not happen and that each permitted write did (names as an array input up to the bound), for
  286 and 288 alike; until then each result notes the one-value limit.
- **Proposed proof component, a future experiment for 288** (the user's ask on 2026-11-18,
  run-streams-domain-advances-D037, from an outside review): for each release, prove a component lemma on 288's
  frozen ASCII domain and locale table. A successful `simpleMatch` on the locale-lowercased canonical pattern and
  field implies a match of the originals ignoring ASCII case. It addresses the case the one-function rule cannot
  relate: unequal normalized inputs outside the allowed change, where a disallowed pattern with a capital I under
  tr-TR lower-cases differently in the two releases.
  - Benchmark its effect on the bound-8 final comparison (`RegressionPair.agree`) before reopening the full proof.
  - Preservation's profile at the frozen bound (its Progress, step 7, 2026-11-18): about 72 of 136 solver seconds
    configure the binder (`canonicalPropertyName`), the matcher takes under 3 s, and relating the two releases'
    154 `simpleMatch` lemma applications at bound 4 took 46 s against 42 s without.
  - Record the lemma with its own evidence, as a proposed proof component. 288's parent preservation claim stays
    open (VF-031).
- **Tracked in**: run-streams-domain-advances-D036, D037; VF-040; VF-031 (288's preservation at its wall); VF-038
  (the brief's 3.5 companion-claims work); the state stream's items I019, I020; preservation's I024.
- **Closes when**: such a claim refutes the four wrong binders above and is decided on both examples.

### VF-042: work the finished streams of the domain-advances run left open

- **Status**: open (the user's decision on 2026-11-18, run-streams-domain-advances-D036: name it for later).
- **Raised**: 2026-11-18 by the watcher of the domain-advances run, from the open inbox items of the state and evidence
  streams, which ended `done` before taking them, and an outside review the user asked for.
- **Found**:
  - State's I018: an exception a model of the JDK throws keeps the model's message, not the JDK's: four countermodels
    in `lib/tests/fixtures/throwable-countermodels` are proved where a JVM says otherwise; the checker-side test in
    that README belongs in `lib/tests/throwable_countermodels.rs` with the fix.
  - Evidence's I014: six observed initializers read a setting the observation binding does not see, and each is
    verified (at `vqquvmnm`) with the class observed under that setting while the result says "it read no system
    property" and nothing of the setting: refuse each or state the setting; the checker-side test is in
    `lib/tests/fixtures/setting-countermodels/README.md`.
  - Evidence's I015. The first half landed during the run (`lvorrywx`): accept.py compares a later step's
    `--work` as resolved folders. On 2026-11-19 the domain check began requiring an independently planned
    length for bounded inputs. `TrialBound.test_a_run_cannot_supply_an_unplanned_length_bound` checks the
    missing-plan case, a predeclared planner default and an irrelevant scalar bound.
  - Evidence's I016 (286's gap packet observed beside the route is read by nothing): optional, and it can wait (D038).
- **Needs**: an owner for each, in the next brief that touches the observer and the JDK models. I018 and I014 are
  demonstrated false proofs and come first, before those features are relied on in a new example (D038, VF-044).
- **Tracked in**: run-streams-domain-advances-D036; the inbox items named.
- **Closes when**: each is fixed with its checker-side test, or decided not to be.

**Foundation pass, 2026-11-19.** The four I018 countermodels now receive a named refusal when they read
exception details supplied by a JDK model. Their JVM controls still observe the real messages.
`modeled_exception_details_do_not_establish_the_four_jdk_countermodels` exercises the public native checker.
For I014, `indirect_setting_reads_refuse_the_observed_initializer` and
`startup_setting_reads_refuse_the_observed_initializer` exercise all six known setting reads. Each refuses
the observation before the setting can support a proof. The existing JVM test varies every setting independently.
The scan covers the observed class and application classes initialized alongside it. A reference in a method
that did not execute can also cause refusal.

### VF-041: 287's preservation is proved for terminating runs only, and changes.py drops the checker's assumptions from what it reports

- **Reporting fix, 2026-11-19.** Both the JSON and text forms of `changes.py 287` now carry the accepted
  preservation evidence's termination assumption. The text report prints each assumption and each evidence limit
  for its own task. The example's notes already identify the result as agreement on terminating runs.
- **Status**: open (the user's decision on 2026-11-18, run-streams-domain-advances-D036: report 287 so, fix the
  projection later).
- **Raised**: 2026-11-18 by an outside review the user asked for, of the domain-advances run's acceptance state.
- **Found**: 287's preservation reached the frozen bound 80 in about 110 s through the call-level rule, and its saved
  outcome assumes each shared `crypt_raw` call ends. The frozen claim
  (`examples/287-spring-security-cve-2025-22228-bcrypt-ignores-bytes-past-72/claims/in-range-matching-preserved.json`)
  admits a case its own notes say diverges on both releases (cost 31): matching divergence is consistent with
  preservation, but this proof does not establish it. So 287 is agreement on terminating runs. `accept.py` reports
  what an outcome rests on (`restsOn`), but `llm-dlc/tools/changes.py`'s projection (around line 69) keeps the evidence
  limits and drops the checker's assumptions, so the milestone report would not say it.
- **Needs**: `changes.py` and the milestone report carry `restsOn` whole; 287's notes say "agreement on terminating
  runs"; a later proof of equal divergence, or a claim restricted to costs that terminate, if wanted. The reporting
  fix is delegated to VF-044's pass (D038).
- **Tracked in**: run-streams-domain-advances-D036; preservation's item I027.
- **Closes when**: the report shows each accepted answer's assumptions, and 287's statement says what was proved.

### VF-040: 286's protected-state claim binds one value and accepts a binder that drops only the first suppressed one

- **Status**: open (the user's decision on 2026-11-18, run-streams-domain-advances-D034: after the domain-advances run,
  add the proposed claim beside the frozen one, as part of the coming claim enhancements; nothing changes in this run).
- **Raised**: 2026-11-17 by the challenge stream of the domain-advances run (its `controls/first-suppressed-only.patch`),
  taken up by the state stream as its item I009.
- **Found**: `examples/286-spring-framework-cve-2022-22968-case-sensitive-disallowed-fields/claims/protected-age-not-mutated.json`
  binds one property value, so a 5.3.19 whose `checkAllowedFields` returns after the first suppressed value is
  accepted by all three of 286's claims, while on a JVM `age=5, Age=32` binds 32 (only the replay probes
  `bind-list-upstream` and `bind-map-upstream` catch it). The state stream proposed
  `claims/proposed/protected-age-kept-two-values.json` (on its line, not frozen, used by no task): two values bound in
  order (`first="5"`, then `second="32"`), `age` left 0, both names ASCII. The ASCII restriction comes from the checker,
  which lowers ASCII only, not from the CVE, so the proposal covers fewer names than the frozen claim: it is to sit
  beside the frozen claim, not replace it, which also keeps 5.3.18's accepted refutation bound to the frozen claim.
- **Needs**: the proposed claim frozen as a further claim file of 286, its tasks added (a refutation on 5.3.18, the
  proof on 5.3.19, and the mutant refuted), and a probe of its cost at bound 8 with two values. Closing the
  non-ASCII lowering gap in `bmc/strings.rs` would let a later claim drop the ASCII restriction.
- **Priority** (the user's D039, 2026-11-18): first among brief 3.5's companion claims, with 288's binding (VF-043).
  The original 286 claim stays (D034). Before the two-value companion is frozen, review a bounded sequence of
  permitted and denied updates that observes both writes, since the challenge stream found binders that pass the
  two-value proposal (VF-043).
- **Tracked in**: run-streams-domain-advances-D034, D039; the state stream's Progress and item I009; VF-043.
- **Closes when**: the added claim is frozen and refutes the mutant, or the user decides the limit stands.

### VF-039: 287's claims accept a wrong fix that keeps the 72-byte guard for checking only

- **Status**: open (the user's decision on 2026-11-17, run-streams-domain-advances-D032: defer to after the
  domain-advances run; no new claim in it).
- **Raised**: 2026-11-17 15:35 UTC by the challenge stream of the domain-advances run, as the preservation stream's
  inbox item I007.
- **Found**: the mutant `examples/287-spring-security-cve-2025-22228-bcrypt-ignores-bytes-past-72/controls/check-only-guard.patch`
  keeps 6.3.8's guard only when checking (`if (for_check && passwordb.length > 72)`), so `matches` and `checkpw` are the
  fix's: all three of 287's claims are predicted to accept it, and its driver lines equal 6.3.8's on all 33 probes. But
  `encode` of a 73-byte password returns a hash again, and the 72-byte prefix matches it: the advisory's defect,
  reached through the encoder. 287's notes ("Could a wrong implementation satisfy the claims?") record the case.
- **Needs**: a claim that `encode` / `hashpw(String, String)` throws `IllegalArgumentException` exactly beyond 72 UTF-8
  bytes would tell the mutant from the fix. A new claim is the user's to freeze. Until then, 287's results are read as
  not telling a check-only guard from the fix.
- **Priority** (the user's D039, 2026-11-18): third among brief 3.5's companion claims. Prepare D032's encode-side
  claim as a separate claim, for the public operation the current checks leave out.
- **Tracked in**: run-streams-domain-advances-D032, D039; the preservation stream's item I007.
- **Closes when**: the user freezes such a claim and it refutes the mutant, or decides the limit stands.

### VF-038: 307's frozen claim justifies its encoding assumption by a specification that says no such thing for `getBytes(String)`

- **Status**: open, minor (the user's decision on 2026-11-17, run-streams-domain-advances-D029: keep the frozen claim and
  its hash, record this, and fold a restated wording into the decision on a companion claim for I008 after the run).
- **Raised**: 2026-11-17 by Codex, in an outside review the user asked for of example 307 during the domain-advances run.
- **Found**: `examples/307-spring-security-fe9e4549-bcrypt-standard-charset-utf8/claims/hashpw-preservation.json`'s
  assumption reads: "Both revisions run on the same JDK, whose String.getBytes(String) and String.getBytes(Charset) for
  UTF-8 encode alike, malformed input and all: both are specified to 'always replace malformed-input and
  unmappable-character sequences with this charset's default replacement byte array'". Only `getBytes(Charset)`
  specifies that; `getBytes(String)` leaves the behaviour on unencodable input unspecified (the JDK 25 `String`
  documentation). The premise, that the two encode alike, holds on the pinned OpenJDK 21 and 25 by implementation (both
  reach `String.encode`; the named form looks the charset up first) and the replay checks it on both; the error is in its
  justification, not in what a proof assumes or claims.
- **Needs**: a result of 307 is read as holding on the JDK builds the replay pins (21 and 25), where the two methods
  encode alike by implementation, not on every conforming JDK; 307's notes say so with the result. A restated claim
  whose assumption cites the implementation of the pinned builds is prepared after the run, together with the companion
  claim under a non-UTF-8 default if the user chooses one (I008, deferred: D028), so that one freeze covers both.
- **Priority** (the user's D039, 2026-11-18): second among brief 3.5's companion claims. Take D029's pinned-JDK
  citation correction and D028's non-UTF-8 companion in one review, as the pilot for environment-specific evidence.
- **Tracked in**: run-streams-domain-advances-D028, D029 and D039; the preservation stream's item I008.
- **Closes when**: the user freezes a restated claim, or decides to keep the wording with this finding as its record.

### VF-037: a stream's `test_costs.py run --changed` filled its loop's 12G cap, and the OOM killer killed the session instead of the tests

- **Retired (2026-11-27, change `kkkqupww`):** this entry names `brief_run.py`, `run-brief` and `run-streams.sh`, which are no longer in the repository. See [`llm-dlc/retired.md#multi-agent-brief`](../llm-dlc/retired.md#multi-agent-brief) for what replaced them and the last commit that has them.
- **Status**: open, minor (raised by the watcher of the domain-advances run; how loops and test runs share the cap is
  for the user to decide).
- **Raised**: 2026-11-17 17:11 UTC on `vm-1`, by the watcher of the domain-advances run, when the challenge stream's
  loop ended in its cycle 17 with `claude exited with status 137` and no commit.
- **Found**: each stream runs in a systemd scope capped at 12G with no swap (`feature-loop-NAME.scope`). The challenge
  session ran `python3 lib/tools/test_costs.py run --changed` on a change touching `lib/tests/costs.json` and a new
  Rust test file. `--changed` takes `cargo test` whenever anything under `lib/` changed, a `costs.json` row included,
  four binaries at a time by default (`--rust-jobs`). That ran several Rust test binaries side by side
  (`application_core`, `values`, `summaries`, `application_core_joint`) and a dozen `javac`s, and the scope reached its 12G peak. The kernel's OOM killer chose the
  `claude` process, the largest single one, so the tests went on as orphans holding 10G in the scope. run-streams.sh then
  ran the loop again at once, which refused to start beside them ("the scope is active"); two stops in a row counted the
  stream as blocked and put it to the watcher to merge, with its uncommitted work (new countermodels,
  `lib/tests/setting_countermodels.rs`) left in its workspace. The watcher stopped the scope by hand (17:14).
  run-streams.sh's supervision of the stream had ended, so nothing in the run would restart it: at the user's word
  (run-streams-domain-advances-D031) the watcher restarted its feature-loop.sh by hand, in a tmux window of
  its own, its output tagged into the run's `streams.log`. Both steps, stopping the scope and restarting the loop,
  are what a loop that ends this way should do for itself.

  What it cost, and what the run lacks (from a read-only review of the run at 20:15, beside the watcher):

  - **One failure counted twice.** The second of the two stops that counted the stream blocked was the refusal
    beside the first one's orphans. It says nothing about the stream, but it spent the loop's second try.
  - **No way to start one stream again inside a run.** `brief_run.py` has `stop` and `start` for the whole run
    only. `start` refuses while a run is under way ("a run of streams is already under way"). `stop` ends every
    loop after its cycle under way: preservation's was over an hour at the time, and the other streams wait idle
    until the slowest ends. So the watcher's first answer (17:14) was to continue the stream with `start` after the
    run, and the stream sat idle for over three hours. For the challenge stream that is most of its value: its item
    5 attacks the other streams' rules as they land, and in that time preservation wrote its I010 reach fix and
    its call-level rule (an unchanged callee as one function), the riskiest soundness changes of the run.
  - **A loop restarted by hand is outside run-streams.sh's bookkeeping.** Nothing puts it to the watcher to merge
    when it finishes. Its phase file in `llm-dlc/loop-summaries/run-streams-NAME/` is written by hand. A
    `brief_run.py start` while it runs is refused by its active scope and counts it blocked again. `wait` can
    return `ended` while it still works. A blocked stop is not put to the watcher to run again. The watcher has to
    do each of these by hand, and keep D021's merge order (challenge before state) the same way.
  - **Relaunched blocked, by hand, once (rerun 1 of 2).** The hand-run loop ended at 01:41 UTC on 2026-11-18,
    `blocked: waiting for the other streams' next commits (preservation's I023 fix, for I007's last check)`.
    No question came, because the loop is outside run-streams.sh. Preservation committed the I023 fix
    (`puuwrruu`) at 01:50, and the watcher relaunched the loop with the same command at 01:50, its scope
    inactive and its working copy clean.
- **Needs**:
  - For the session: one of these, so the OOM killer meets the tests, not the session:
    - the test run inside a loop takes fewer binaries at a time;
    - it gets a cap of its own below the loop's (`systemd-run --scope -p MemoryMax=` around it);
    - `claude` gets a lower `OOMScoreAdjust` than its children.

    And a loop that ends this way stops its scope before it is run again, so the rerun is not refused. Meanwhile
    (inbox item domain-advances-challenge-I003), a stream runs its changed tests under a cap of their own:
    `systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 python3 lib/tools/test_costs.py run --changed
    --rust-jobs 1`.
  - For the run (run-streams.sh and brief_run.py, with the env-leak fix in the same files):
    - a refusal because of an active scope that holds only the killed session's orphans does not count as one of
      the stream's stops: the loop stops the scope and runs again;
    - `brief_run.py` can start one finished or blocked stream again inside a running run (say `rerun BRIEF
      STREAM`), and run-streams.sh supervises it as before: its phase, the merge question, its reruns. Then a
      watcher never launches a loop by hand.
  - For the run-brief skill: a challenge stream left unmerged in the middle of a run is started again, not held
    until the run ends, since its input is the other streams' commits as they land.
- **Tracked in**: nowhere else. The run-streams.sh change belongs with the strategic fix of the
  `RUN_STREAMS_WATCHER` leak, deferred to after the domain-advances run.
- **Closes when**: a changed-test run that needs more than the cap fails on its own and the loop's session goes on,
  and a stream that ended this way in the middle of a run is started again inside it without a hand launch.

### VF-036: equivalence checks and the Terminal-Value tests leave their temp folders in `/tmp`, which ran out of inodes

- **Status**: open, minor, to revisit if it recurs (the user's decision on 2026-11-17: they raised `/tmp`'s inode
  limit and cleaned it by hand; nothing to change now).
- **Raised**: 2026-11-17 on `vm-1`, by the watcher session of the rehearsals, when a command could not start
  (`ENOSPC` on `/tmp`) with 160 GB free on `/`.
- **Found**: `/tmp` is a tmpfs (53 GB, 20% used), but 1,046,553 of its 1,048,576 inodes were used. About 640,000 of
  them were 18,276 folders `jvmcontract-equivalence-PID-NANOS-N`, back to 2026-11-15: `equivalence::run_check`
  (`lib/src/equivalence.rs`, the `None =>` arm of `options.work`) makes a work folder with
  `tla::tempfile_path` whenever no `--work` is given and never removes it, and the default test run calls it many
  times. About 321,000 more were `sf-case-*`, `sf-build-*` and `sf-m*` folders from
  `Terminal-Value/blog/software-factory/test/fixtures/cases.mjs`, another repository's tests. Anything that
  creates a file then fails, a test run included, for a reason unrelated to its code. The user raised the limit to
  8,388,608 inodes, since RAM is plentiful and `/tmp` on tmpfs speeds runs up, and removed the old folders.
- **Needs**: if it recurs, the verifier removes a work folder that nobody asked to keep (no `--work`) once the
  outcome no longer needs it, or the test run gives each run a `TMPDIR` of its own and removes it at the end;
  Terminal-Value's tests remove their fixtures' folders. Whoever takes it up: the user decides when.
- **Tracked in**: nowhere else.
- **Closes when**: a whole default test run leaves no `jvmcontract-*` folder behind in `/tmp`.

### VF-035: whole Python test files are tagged unit tier and take minutes, because the inventory doesn't see the processes their tests start

- **Status**: open, to revisit later (the user's decision on 2026-11-17: note it, don't retag now).
- **Raised**: 2026-11-17 on `vm-1`, by the session that made the default test run parallel, from that run's own
  times (`~/.cache/in-the-loop/python-test-seconds.json`, a whole default run with three files at a time).
- **Found**: `lib/tests/costs.json` gives a Python test its tier from what its code calls, and a test that starts
  processes inside the module it tests shows no call. Four files are tagged almost wholly unit (in process, under 1 s
  a test) and are far from it:

  | File | Tagged | Took, the whole file |
  |---|---|---|
  | `examples/tools/targets/test_runtime.py` | 69 unit, 4 tool | 258 s |
  | `verification/test_pipeline.py` | 34 unit, 4 tool | 110 s |
  | `examples/tools/targets/test_receipt_streams.py` | 5 unit | 47 s |
  | `examples/tools/test_targets_contract.py` | 16 unit | 16 s |

  The times are under load (other files and the Rust binaries beside them), so they bound each file and say nothing
  of one test. The effect: `test_costs.py run --tier unit` is minutes of Python and not the quick run its name says,
  and the three slowest of these files are what the default run's Python half waits for.
- **Needs**: a decision on retagging. The options seen: time these files test by test (`test_costs.py python FILE`)
  and tag from the measured time; or teach the inventory to follow the module under test for spawned processes.
  Moving a test between tiers is the user's to approve.
- **Tracked in**: `lib/README.md`'s Tests section (the unit tier's note names the first two files).
- **Closes when**: the four files' tests carry tiers that a measured run agrees with, or the user decides they stay.

### VF-033: example 290's preservation claim compares only the count of matchers by type, and its fixed-security verdict rests on initializers observed on a JVM

- **Retired (2026-11-27, change `vwytpwxy`):** this entry names `prove-java-change`, which is no longer in the repository. See [`llm-dlc/retired.md#plugin-and-runtime-mode`](../llm-dlc/retired.md#plugin-and-runtime-mode) for what replaced it and the last commit that has it.
- **Status**: open, for a later run (the user's decision on 2026-11-17, reviewing the watcher's answer D005).
- **Raised**: 2026-11-17 on `vm-1`, by the watcher of the `/prove-java-change` run over 288-290, after job
  `20261117-002240-example-290-the-four-proof-tasks-through` decided all four of 290's tasks beside the route and an
  outside expert's read-only review of the cycle (`llm-dlc/loop-summaries/prove-change/expert-review.md`, c3).
- **Found**: two limits on what 290's results say, both stated by the claims or outcomes but easy to read past.
  1. `claims/lone-dispatcher-selection-preserved.json` is established as written: with the `DispatcherServlet` the only
     servlet, 5.8.4 and 5.8.5 return the same *count of matchers by type*, or throw in the same category. It does not
     show that they build the same matchers (pattern, HTTP method, servlet path) or that those match the same
     requests: a release that built a different `MvcRequestMatcher` would satisfy it. It is the weakest of the run's six
     claims.
  2. `fixed-security` (and preservation) start from the state of library class initializers observed once on a JVM
     (`prove --observed-initializer`, `lib/src/observed.rs`), where the claim's fourth assumption says every initializer
     runs as written. The review's points: `GenericServlet` and `HttpServlet` load resource bundles, which read the
     default locale and the class loader's resources, so "no input" is too strong as stated; and the import takes only
     the observed class's own fields, so an initializer's writes elsewhere are not carried (no such write is known in
     290). The mutant and vulnerable refutations replay on a JVM and do not rest on this.
- **Needs**, in a later run, after the user's library work:
  - (B, chosen) restate preservation to compare what the matchers are: each one's type, pattern, HTTP method and servlet
    path, for both overloads. One setup session to restate and freeze it (about $3-7, 20-40 min) and about one proof
    cycle (about $20-30, 1-1.5 h) and one job; the security results stand unchanged, since that claim does not change.
  - (C, not chosen) compare how the matchers match requests (`matches()`), which goes through
    `HandlerMappingIntrospector` into Spring MVC's handler mappings: a new modelling capability, 2-4 cycles, and
    uncertain.
  - An audit of the observed initializers: the state each verdict reads, and that the default locale, resources, class
    path order and JVM properties cannot change it; a regression test of an initializer that writes another class's
    static; or refuse what the import cannot carry.
- **Audit, done** (2026-11-17, the evidence stream of domain-advances, step 5): recorded in 290's notes. No `<clinit>` of
  the five observed classes writes another class's static, and what they read of the locale goes into fields the
  observation does not hold (the challenge stream's reading, `lib/tests/fixtures/observed-countermodels/README.md`).
  The checker now binds an observation to what it was observed on and ends the run where it is not
  (`lib/src/observed.rs`, `On`): the class file, the class path order, each class the initialization also initialized
  (left as it is alone, else refused: the countermodel `A.<clinit> { B.x = 1; k = 7; }`), a default locale the check's
  lowering agrees with, and the properties read, stated with their values; `lib/tests/observed_countermodels.rs`
  holds it. A capped probe verified 290's fixed-security and preservation again under it. Widened the same day after
  the challenge stream's `ob` countermodels (`lib/tests/fixtures/rule-countermodels`): the supertypes the
  initialization initialized are compared too, a property read by key through `System.getProperties()` is stated, a
  read of the properties as a whole and code that reads the environment are refused, and the default time zone is
  stated; 290's two tasks verified again under it in capped probes, with the same path counts. Widened again after
  the challenge stream's binding countermodels (`lib/tests/fixtures/binding-countermodels`): a value a class the
  initialization initialized holds and the observation does not is compared by the observer's full description of
  it (an object's fields, a lambda's method and captured values, a JDK collection's elements), and one it does not
  describe is refused, so a write into an object another class holds (`bc.Boxed`) or a lambda put in place of
  another of its class (`bc.Rehooked`) is refused; and an initialization that changed the default locale, time zone
  or a system property (`bc.Relocaled`) is refused. 290's nine classes initialized besides are all described (two
  `IdentityHashMap`s, a `HashSet`, a `ConcurrentReferenceHashMap`, enum constants, a resource bundle, a float) and
  the same alone, no setting changed; its two tasks verified again in capped probes, with the same path counts.
- **Prepared** (2026-11-17, the evidence stream): the restated claim (B),
  `claims/lone-dispatcher-matchers-preserved.json` (sha256 `4185eea3f4ef…`), with its entry
  `MatcherDescriptionAdapter#describe` (each matcher's exact class and the library's rendering of its pattern, servlet
  path and HTTP method, for both overloads). On a JVM both releases describe the same matchers on every probe with the
  DispatcherServlet alone; the claim states that a null pattern and `"null"` render alike in an `MvcRequestMatcher`.
  `proofs/prove.py` runs it once the task names it, and `accept.py` keeps the security answers accepted then.
- **Left**: (1) the freeze, the user's: the claim's hash in a claims ledger, the preservation task's `claim` pointed at
  it, the adapter source added to `preparation.adapters` (290's notes say how). (2) The checker: capped probes stop at
  `StringBuilder.append(Object)` in `MvcRequestMatcher.toString` (an enum constant appended), and at the frozen bound
  reach the 4 GiB cap after 133 s, so after that gap is closed the proof is one job.
- **Priority** (the user's D039, 2026-11-18): D023 stays settled (290's frozen claim is kept). The richer
  observation proposal goes to brief 04, not brief 3.5.
- **Tracked in**: `examples/290-spring-security-cve-2023-34035-multiple-servlet-authorization-rules/example.json`
  (notes); decision `prove-change-D005` (`llm-dlc/decisions/prove-change.md`).
- **Closes when**: a restated preservation claim is decided at the frozen bound, and the initializer audit is recorded
  in the example's notes (or the verdicts are re-run without observed initializers).

### VF-032: the default test run at `76862913606e` failed one test, `test_runtime.py` (the environment of a verifier run), because `JVMCONTRACT_JBMC_MEMORY_MB` is passed through

- **Status**: closed by job `20261116-232054-default-test-run-at-qnmttuprxxym` (at `73542e073f35`, 2026-11-16, `vm-1`): the default run passed under the runner, 49 of 49 files, 14m32s
- **Raised**: 2026-11-16 on `vm-1`, job `20261116-224337-default-test-run-at-yooukqwllnmu` at `76862913606e`. A first
  attempt of the same job was cancelled at 10 min when my own background command hit its time limit; the rerun is the
  one recorded.
- **Found**: 48 of 49 default-tier files passed (all Rust suites and the other Python tests ok). `examples/tools/targets/test_runtime.py`
  failed 1 of 73 tests, `VerifierTest.test_a_property_runs_on_the_original_artifact_alone_with_the_plans_engine_gaps_and_bounds`
  (line 1276): the verifier's environment holds `JVMCONTRACT_JBMC_MEMORY_MB`, which the test's expected set
  `{LANG, LC_ALL, TZ, JAVA_HOME, PATH, JVMCONTRACT_JAVA_OPTS}` does not list. `runtime.py:1421` has
  `VERIFIER_PASS = ("JVMCONTRACT_JBMC_MEMORY_MB", "JVMCONTRACT_JAVA_OPTS")`, so the variable is passed through when the
  caller's environment has it; the runner's job environment sets it, a plain shell evidently does not. Either the test
  should exclude it as it does `LC_CTYPE`, or clear it from the environment. I did not change the test.
- **Needs**: the owner of `examples/tools/targets/` (the prove-examples loop) to make the test independent of the
  caller's `JVMCONTRACT_JBMC_MEMORY_MB`.
- **Tracked in**: `verification/results/20261116-224337-default-test-run-at-yooukqwllnmu/logs/1-default-tests.log`.
- **Closes when**: the default test run job passes unchanged under the runner.

### VF-031: example 288's three adapter-entry proofs that were expected to be decided ran out of engine time (two refutations at 1800 s, the preservation claim at 5400 s)

- **Status**: open
- **Raised**: 2026-11-16 on `vm-1`, jobs `20261116-201436-example-288-vulnerable-security-through`,
  `20261116-201436-example-288-mutant-security-through-the` and `20261116-203637-example-288-preservation-through-the-ada`,
  at `b74b820d0837`.
- **Found**: the fixed-security job (`...-fixed-security-through-the-a`) passed: verified, as expected, in 19m42s. The
  other three stop with no verdict. Vulnerable-security (6.1.13, expected refuted) and mutant-security (expected
  refuted) both ran the simpleMatch lemma (85 s and 93 s), then `LocaleDecisionAdapter#allowed cannot be verified: the
  engine did not finish within the time limit` after 31 min (paths 6761 and 6886, 12761 and 14400 solver calls),
  `verdict: unverifiable (expected violation)`. The step's own `prove.py ... --timeout 1800` was reached, not the job's
  1h limit. Preservation (6.1.13 against 6.1.14, `--timeout 5400`) ran 1h32m and ended `RegressionPair#agree cannot be
  verified: the solver did not finish within the time limit` (paths 5846, 11737 solver calls, expected verified). Peak
  memory was 2 GiB in each, far below the 6 and 8 GiB asked for, so the limit is the engine's time, not memory.
  I did not resubmit: resubmitting unchanged repeats the same timeout, and raising `--timeout` changes the job's step,
  which is the submitter's to decide.
- **Needs**: the example 288 owner (the prove-examples loop, cycle 288) decides whether to raise `--timeout` for the
  two refutations (the fixed release's proof took 19m42s, so the refuting path search is slower than the full proof) or
  to change the claim's bounds or the engine search order so the violating path is found early; likewise for
  preservation. Then queue the jobs with the new step.
- **Next data point** (2026-11-18, the domain-advances run's preservation stream, step 7 of its Progress; closed out
  under D037 and D038): capped probes at the frozen bound prove the lemmas, then leave the pair undecided after
  about 4100 paths and 8700 solver calls, 136 of 160 s in the solver. Of those, about 72 s configure the binder
  (spring-beans' `canonicalPropertyName`, the same bytecode in both releases) and the matcher takes under 3 s. Trials
  verify in 13 s at bound 3 and 42 s at 4, and stay undecided past 150 s at 5 and 6. The costliest query is the
  last, `RegressionPair.agree`'s relational comparison. Relating the two releases' `simpleMatch` lemma applications
  saved nothing (154 related at bound 4, 46 s against 42 s). No job was queued, because one at the frozen bound on
  the same checker would repeat this entry. The next approach is the per-release locale lemma, recorded as a
  proposed proof component in VF-043. Proof work reopens only after it shows a measured improvement at the bound-8
  comparison. The preservation claim stays open.
- **Tracked in**: the three jobs' `logs/1-the-claim-at-the-frozen-bound.log` and `outcome.json` under their outputs;
  VF-043 (the locale lemma); VF-044; the domain-advances preservation brief's Progress.
- **Closes when**: the three tasks, rerun, give refuted, refuted and established.

### VF-030: the proof-tier job after example 286's engine changes stopped at `heap.rs`, so the tests after it and every Python proof test never ran

- **Status**: closed by job `20261117-152112-the-rust-proof-tier-after-the-domain-adv` (at `9ec6e448674f`, passed 2026-11-17 on `vm-1`, 42m14s, peak 4.2 GiB): every ignored Rust test passed, none hidden by a failure; the Python half has no tests (Update 2026-11-17)
- **Raised**: 2026-11-16 on `vm-1`, job `20261115-234440-the-proof-tier-after-example-286-s-engin` at `8594e6b7adb1`
  (`lib/tools/test_costs.py run --tier proof`, 1h34m, peak 3.3 GiB).
- **Found**: `cargo test` stops at the first failing test binary. `heap.rs` failed (VF-018's three JBMC
  timeouts), and the binaries after it alphabetically and the Python proof-tier tests did not run. What ran and
  passed: `conformance.rs` (2 passed, 1228 s) and every earlier binary (nothing ignored in them). So the job's
  question, whether the engine changes made a proof-tier check that explores over 1024 paths slow or out of time,
  is answered only for `conformance` and `heap` (the heap failures are VF-018's, unchanged), not for the rest.
  The three example-286 jobs of the same commit passed as expected.
- **Needs**: the submitter (prove-examples loop) to resubmit the proof tier so that a failure doesn't hide the rest
  (cargo's `--no-fail-fast`, or one job per test file, with the three VF-018 tests excluded or expected to fail),
  and the Python proof tests as their own job. I did not change the job's steps myself.
- **Tracked in**: VF-018.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): used as a control for the result's new blocks, and nothing was backfilled. A step skipped after a failing one is in `execution.skipped` with its reason and leaves the job `unfulfilled` (`skipped`); for a receipt of before, the blocks are computed by the reader and marked `derived`, and no receipt's status was rewritten, so a test after the failing step has no passing result it did not have.
- **Closes when**: a proof-tier job covering the binaries after `heap` and the Python proof tests passes at a commit
  with these engine changes.
- **Update 2026-11-16** (job `20261116-053833-the-proof-tier-after-example-287-s-engin`, at `26a42d401510`, passed on
  `vm-1`, 1h07m, peak 3.3 GiB): the Rust half is settled. Run with `--no-fail-fast` and VF-018's three tests skipped, every
  ignored Rust test passed (`conformance` 2, `heap` 6, `preparation` 1; no binary after `heap` has an ignored test left), none
  hidden by a failure, with example 287's engine changes. The Python proof-tier tests are still not covered: that job
  ran `cargo test` only. The entry stays open for them; the submitter should queue them as a job of their own.
- **Update 2026-11-17** (the domain-advances evidence stream, step 6): **the Python half was empty, and is settled.** No
  Python test is tagged `@cost("proof")`, now or at this entry's job (`8594e6b7adb1`: 787 unit and 70 tool rows in
  `lib/tests/costs.json`, none proof; today 1019 unit, 176 tool). The tag appears only in `test_costs.py`, `cost_tier.py`
  and the lint's own fixtures. That is why the estimate counts 0 Python proof tests, and
  `test_costs.py run --tier proof --only python` prints "python: no proof-tier tests" and runs nothing, so it was not
  queued. Every Python test, those that reach the verifier included, is in the default run. That run passed inline at
  the evidence line's head after the foundation's checker changes (tree `bc1caa8a8827`, 54 of 54). Python files tagged
  unit that start processes the inventory does not see are VF-035's. **The Rust half** is queued again for the checker
  changes since the last proof-tier jobs: the foundation's (`qkqpsmqk`: `bmc/mod.rs`, `bmc/strings.rs`, `property.rs`,
  `summary.rs`) and the evidence line's (`pairing.rs`, `statement.rs`, `observed.rs`, `classpath.rs`, `equivalence.rs`).
  Job `20261117-152112-the-rust-proof-tier-after-the-domain-adv` runs the whole tier with `--no-fail-fast`. It includes
  VF-018's three, since VF-018 is closed and they run the own checker under `auto --confirm`, and the seven tests
  `wvvtwkos` moved. **Closes when** that job passes. A failure there is a new finding about these changes, not this entry.
- **Closed** 2026-11-17 on `vm-1`: job `20261117-152112-the-rust-proof-tier-after-the-domain-adv` (at `9ec6e448674f`,
  the evidence line after the foundation's checker changes and its own pair and observation checks) passed in 42m14s, peak
  4.2 GiB (estimated 55 min, 8 GiB). `cargo test --release --no-fail-fast -- --ignored` ran 19 tests and all passed: the
  19 Rust rows `lib/tests/costs.json` marks ignored, none left out, VF-018's three heap tests and the seven `wvvtwkos`
  moved among them (`conformance` 2 in 1228 s, `heap` 9 in 370 s, `application_core` 2, `application_core_joint` 1, the
  TLC, compare and own-checker tests). So no proof-tier check got slower than its limit or changed its verdict with these
  changes, and with the Python half empty nothing is left.

### VF-023: under `--engine auto --confirm`, the own checker proves `listSizes` and `listChange` and JBMC refutes them with a witness the interpreter says holds

- **Status**: closed by job `20261108-141443-vf-023-rerun-the-conformance-corpus-unde` (at `13f3e9a0dac8`, passed 2026-11-08 on `vm-1`, 23m18s, peak 1.8 GiB: the `auto --confirm` conformance corpus step, after a JBMC refutation through a stub that doesn't reproduce was made no verdict under `--confirm`). Its one output, `lib/target/conformance-confirm.log`, was not applied (the file changed since the commit); it is a build log, so nothing is lost.
- **Raised**: 2026-11-08 on `vm-1`, job `20261108-070211-application-core-values-v2-step-1-the-co` (at `1fd394556a7c`).
- **Found**: step 1 (`conformance` corpus under `--engine jbmc` and `auto`) passed (661 s). Step 2
  (`cargo test --test conformance the_corpus_agrees_with_the_jvm_under_auto_confirm`, 1249 s, peak 1.7 GiB) failed at
  `lib/tests/conformance.rs:902` with 8 disagreements with the JVM, all on the two immutable-list models, each under
  `--gaps Strict` and `--gaps Assume`: `listSizes [assume n >= 1 && n <= 3; assert result == n * 10]` and
  `listChange [assume n == 0 || n == 8; assert result == 1]`. In both, the own checker (CaDiCaL) proves the property in
  0.0 s, while JBMC 6.11.0 refutes it with `listSizes(n=1)` / `listChange(n=0)`; the interpreter replay gives 10 and 1,
  where the property holds, so the witness is spurious (JBMC's list model disagrees with the interpreter and the own
  checker), not a real violation. The `auto` run reports "a violation the JVM does not reproduce: the harness holds"
  and `--confirm` reports "the engines disagree, neither verdict stands". The other 82 cases were fine.
- **Update 2026-11-08** (job `20261108-082244-vf-023-s-diagnosis-why-jbmc-refutes-that`, at `8ddb0f7417c6`, passed): the
  diagnosis probes (`one`, `oneAfterInit`, `two`: a one- and two-element `List.of` and the same after the model's
  static initializer) all verified under JBMC 6.11.0 in about 0.2 s each, as the JVM says (1 1 2). So the minimal
  probe does not reproduce the refutation; the cause is something the `listSizes`/`listChange` harnesses add (their
  `assume` over `n`, or the loop over the list). The job passing only means the probes ran; it does not close this entry.
- **Update 2026-11-08** (job `20261108-091002-vf-023-s-second-probe-which-ingredient-o`, at `ec45c5dd40a2`, passed in
  5.8 s: it only runs probes, so it does not close this entry): the cause is located. Every probe that calls
  `List.size()` or `List.isEmpty()` on the list is refuted under JBMC 6.11.0 with a witness the interpreter replays as
  holding: the corpus's `listSizes(n=1)` and `listChange(n=0)`, and the minimal `oneOrTwo`, `oneOrThree`, `emptyOrOne`
  and `changeNoSwitch`. Each reports a `jbmc gap`: `java.util.List.size()` (and `isEmpty()`) is JBMC's stub, "returns any
  int" / "either boolean", so the refutation is the stub's free value, not the list model (the list is built correctly,
  `List12` with its elements). Probes that never call `size()` (`oneAssumed`, `oneMadeFirst`, `oneThenSwitch`) are
  proved in 0.1-0.2 s. So the disagreement is the stub, not a wrong list model; the tool already notes the gap, but under
  `--engine auto --confirm` it still reports "the engines disagree, neither verdict stands" for the own checker's proof.
- **Update 2026-11-08** (job `20261108-093809-vf-023-s-third-probe-does-the-model-java`, at `b5fd6e150444`, passed in
  6.4 s: it only runs probes, so it does not close this entry): re-declaring `size()`/`isEmpty()`/`iterator()` in the
  model `java.util.List` (the "declared" variant) does **not** fix it. Outcomes are identical to the as-is model:
  `corpusSizes`, `corpusChange`, `oneOrTwo`, `oneOrThree`, `emptyOrOne` are each still refuted (0 proved, 1 not) and
  `oneAssumed` still proved, in both variants. The refuted ones still dispatch through the `List.size()` stub (call to
  `java.util.List.size` as a fallback branch beside the `ListN` and `List12` branches), so JBMC's stub free value remains
  the cause. Next idea for the values stream: make the stub unreachable (an exhaustive dispatch with no fallback branch),
  or treat a gap-only refutation that the interpreter replays as holding as "not a verdict" under `--confirm` instead of
  a disagreement.
- **Needs**: the values stream (application-core-values V2) decides whether the JBMC list model (or the witness
  replay) is at fault and fixes it, or marks these two cases as expected disagreements with a stated reason; then
  resubmits the job. I did not change the job.
- **Tracked in**: `llm-dlc/loops/application-core-values.md` (not edited by me).
- **Closes when**: the job's step 2 passes in a rerun unchanged.

### VF-022: `a_method_of_a_record_is_proved_on_its_components` asserts a harness text the O2 constructor-admission change replaced

- **Status**: closed by job `20261108-072230-application-core-objects-o2-lib-tests-in` (at `ac38d9c636f9`, passed 2026-11-08 on `vm-1`: `cargo test --test integration` with the assertion updated)
- **Raised**: 2026-11-08 on `vm-1`, jobs `20261108-063512-application-core-objects-o2-the-regressi` (at `d7330651d821`)
  and `20261108-064305-application-core-objects-o2-a-shrunk-wit` (at `ddf265db0e43`).
- **Found**: `cd lib && cargo test --test integration` gives 64 passed, 1 failed in both jobs (110 s and 119 s). The
  failing test is `a_method_of_a_record_is_proved_on_its_components`, at `lib/tests/integration.rs:1961`. Its verdict
  (`Verified`), domain and "behaves as before" assertions passed; the assertion that failed is on the generated
  statement text, which must contain `try { this_before = new before.fixtures.Backoff(...); this_after = new fixtures.Backoff(...); } catch (Throwable t) { return; }`.
  The statement now has two separate construction regions (`rejectedAfter` / `rejectedBefore`, `throw new AssertionError()`
  when only one rejects), so that string is no longer there. This looks like a stale test expectation from the
  `d7330651d821` change, not a wrong verdict. In the first job the 20 example steps (126-196) all passed with their
  expected verdicts. The shrinker job's other tests, and its stricter-oracle witnesses, were not reached as a failure:
  only this test failed, so the job's check on the shrunk witnesses held. I did not edit the test or the job.
- **Needs**: the objects stream updates the assertion at `integration.rs:1961` to the new construction text (or states
  it by what it must mean), and resubmits the integration-tests job.
- **Tracked in**: `llm-dlc/loops/application-core-acceptance.md` row O2 (not edited by me).
- **Closes when**: `cargo test --test integration` passes in a rerun of the O2 jobs' integration step.

### VF-020: a passed job's `changes.diff` (1.2 MiB) is not committed, because jj refuses to snapshot new files over 1 MiB

- **Status**: open
- **Raised**: 2026-11-07 on `vm-1`, job `20261107-163056-vf-009-triage-a-class-initializer-that-t` (at `2c352d909f21`),
  collected in the commit that records the run of 2026-11-07 (VF-009's triage).
- **Found**: `collect` wrote `verification/results/20261107-163056-vf-009-triage-a-class-initializer-that-t/changes.diff`
  (1,234,232 bytes: the diff of the 168 output files, most of them `lib/target/vf009` class files and goto listings).
  jj's `snapshot.max-new-file-size` is 1 MiB, so every `jj` command prints "Refused to snapshot some files" and the
  file is left out of the commit. The rest of the result (`result.json`, the logs) is committed. I did not raise the
  limit or edit the result.
- **Again** in the next run: `verification/results/20261107-171442-vf-009-s-guard-measured-the-41-recorded/changes.diff`
  (1.3 MiB) was also left out. Two results so far lack their diff; both jobs passed.
- **Needs**: a decision by the user: raise the limit for this repository (`jj config set --repo
  snapshot.max-new-file-size 2097152`), or have `collect` leave out a `changes.diff` over the limit (or compress it),
  or have jobs keep their scratch output out of the declared outputs. The job's `outputs` listed `lib/target/vf009`,
  which is build output; a submitter's call for the jobs that follow.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): used as a control for the move. The compressed and the summarised forms of an oversized `changes.diff` are written by the same code as before (`keep_diff`), the manifest of `b52a084f5d11` (paths and git blob ids of every specification, receipt and collected output) verifies at this line, and the audit reports a kept output a receipt names that is in no commit as a gap with its reason (VF-080 is what that found).
- **Closes when**: `jj st` shows no refused file after a collect, or the result is recorded as lacking its diff on
  purpose.
- **Decided** by the user on 2026-11-07: `collect` handles the size. A `changes.diff` over jj's limit is written
  gzipped (`changes.diff.gz`), or, if that is still over, as a `--stat` summary, and `result.json`'s `changesDiff`
  says which. The limit stays at 1 MiB.
- **Fixed** 2026-11-07 in the commit that adds `keep_diff` to `verification/pipeline.py`: `collect` keeps a
  `changes.diff` over 1 MiB as `changes.diff.gz`, or as `changes.stat` (the files it changes, with lines added and
  removed) when even gzipped it is over, and records the original size in `collected.changesDiff`
  (`test_pipeline.py`, `test_a_diff_over_the_commit_limit_is_kept_gzipped_or_as_a_summary`).
  - Contrary to the entry above, both diffs did reach the repository. `git ls-tree` shows the first, 1,234,232
    bytes, committed in `pkuvkyln` and the second, 1,359,746 bytes, in `rzmrlklw`; both have been pushed. How they
    got past the limit is not known. Neither result lacks its diff, and they are left as they are.
- **Closes when**, now: the next `collect` of a job whose diff is over 1 MiB leaves `jj st` with no refused file.

### VF-018: JBMC doesn't finish within 600 s on four of H5's regression proofs over objects under a correspondence

- **Status**: closed by job `20261116-144006-vf-018-the-heap-proof-tier-under-jbmc-an` (see **Closed** below)
- **Raised**: 2026-11-07 on `vm-1`. Four of the heap stream's H5 jobs, each one ignored test of `lib/tests/heap.rs`
  under `--engine jbmc` and `auto --confirm`, each failed after about 22 minutes:
  - `20261107-080218-output-relations-under-a-correspondence` at `9b9c3a34`: `objects.Kernel#price` (`heap.rs:986`);
  - `20261107-083358-computed-input-equations-under-a-corresp` at `a405b89a`: `prices.Prices#total` (`heap.rs:1172`);
  - `20261107-092158-input-equations-that-read-a-primitive-pa` at `e7e61dbd`: `lines.Lines#reprice` (`heap.rs:1472`);
  - `20261107-115201-input-equations-that-read-another-object` at `0348f57c`: `orders.Orders#reprice` (`heap.rs:1685`).
- **Found**: each fails on its first JBMC run, with `Jbmc confirm=false after …: Unverifiable (expected Verified, on
  a JVM false)` and "JBMC did not finish within 600 s". The own checker proves each claim. JBMC gives no verdict,
  which is sound but not what the tests expect. The other four H5 jobs, over the same harness machinery, passed in
  2 to 6 minutes: `-085410`, `-104658`, `-112033` and `-121516`. Not read further: the harness JBMC is given (its
  size, the unwinding, how the correspondence's equations are encoded for it), or whether these proofs are simply
  beyond JBMC in 600 s.
- **Needs**: triage of one of the four as a quick job: JBMC on the generated harness with its statistics, and
  whether a smaller encoding (fewer objects, a tighter unwind, the equations as assumptions) lets it finish.
  - If the harness can be made tractable, do it, with the tests unchanged.
  - If not, the tests' expectation that JBMC agrees is the question. Accepting JBMC's timeout as no verdict would
    relax a check, so it is for the user to decide.

  For the cleanup loop's jbmc stream.
- **Tracked in**: [`llm-dlc/loops/cleanup-jbmc.md`](../llm-dlc/loops/cleanup-jbmc.md) (J3).
- **Closes when**: the four jobs, resubmitted unchanged at a fixing commit, pass; or the user decides the
  expectation, and the jobs pass under it.
- **Rerun with an 1800 s JBMC limit** 2026-11-07 on `vm-1`, at `cf2205fc56a3` (the four jobs
  `20261107-164356-vf-018-*`, 6 GiB limit each, peak 1.5 GiB): one passed, three failed alike.
  - `prices.Prices#total` passed: its test finished in 3185 s, so JBMC gave a verdict inside 1800 s (it is
    tractable, about 5 times slower than the 600 s default suggested).
  - `objects.Kernel#price` (`heap.rs:1070`), `lines.Lines#reprice` (`heap.rs:1570`) and `orders.Orders#reprice`
    (`heap.rs:1746`) failed after 3606 to 3688 s with "JBMC did not finish within 1800 s", `Unverifiable (expected
    Verified, on a JVM false)`. Tripling the limit did not help them, so a longer limit is not the way out for these
    three: the harness or its encoding needs triage, or the expectation is the user's decision, as above.
  - Memory was never the limit (peak 1.6 GiB of 6).
- **Decided** by the user on 2026-11-07: triage the harness, with the tests' expectation unchanged. A quick job runs
  JBMC on one of the three generated harnesses with its statistics, then on smaller encodings (fewer objects, a
  tighter unwind, the equations as assumptions). If one finishes, the harness generator adopts it and the three jobs
  are resubmitted unchanged.
- **Triage queued** 2026-11-07: job `20261107-224523-vf-018-triage-what-jbmc-is-given-for-h5` runs
  `verification/triage/vf018.sh` on `objects.Kernel#price`. It records the commands the test gives JBMC, measures the
  harness and goto program, and reruns the first proof with JBMC's statistics, as given and at `--unwind` 8, 4 and 2
  and with `--slice-formula`, 900 s each. The encoding to try next (fewer objects, the equations as assumptions)
  follows from where its time goes.
- **Triage ran** 2026-11-08 on `vm-1`: `20261107-224523-vf-018-triage-what-jbmc-is-given-for-h5` (at `8aac19618c9d`)
  passed (1h21m; its outputs `lib/target/vf018/summary.txt` and `proof-command.txt` were applied). What it shows for
  `objects.Kernel#price`: the harness is small (211 bytecode instructions over 2 methods, 12 KiB; goto program of
  3186 lines), symex takes 0.009 s and produces 518 steps and 1 VCC, and the formula is 18358 variables and 77108
  clauses. The solver, not the encoding of the program, is where the time goes: as given (`--unwind 16`), at
  `--unwind` 8, 4 and 2, and with `--slice-formula` (15753 variables, 76395 clauses), JBMC did not finish within
  900 s in any of the five runs, and the formula is the same size at every unwind, so the unwinding is not what
  makes it hard. **Needs**: the next triage is on what the 77k clauses are (JBMC's output with `--show-vcc`, or
  which equations of the correspondence are arithmetic that a SAT solver finds hard), and then fewer objects or
  the equations as assumptions, as the entry's plan says; the cleanup loop's jbmc stream. Still open.
- **Rerun** 2026-11-15 on `vm-1`: job `20261115-173209-object-comparisons-under-jbmc-and-auto-c` (at `18cfa9e637ef`,
  the proof tier of `lib/tests/heap.rs` under `--engine jbmc` and `auto --confirm`, 600 s JBMC limit) failed again in
  50m12s (peak 1.9 GiB): 5 passed, 4 failed (`the_computed_equations_…`, `the_other_object_reads_…`,
  `the_output_relations_…`, `the_parameter_reads_have_the_same_verdicts_under_jbmc_and_auto_confirm`), e.g.
  `objects.Kernel#price` and `lines.Lines#reprice` with "JBMC did not finish within 600 s". The same four as before,
  so nothing from the harness changes since has made them tractable. Log:
  `verification/results/20261115-173209-object-comparisons-under-jbmc-and-auto-c/logs/1-heap-proof-tier.log`. The
  moonshot (prove-examples loop) plans to diagnose it. Still open.
- **Rerun** 2026-11-16 on `vm-1`: job `20261115-234440-the-proof-tier-after-example-286-s-engin` (at `8594e6b7adb1`, the
  whole proof tier, 1800 s JBMC limit) failed in 1h34m at `lib/tests/heap.rs`: 6 passed, 3 failed, namely
  `the_output_relations_…` (`objects.Kernel#price`, `heap.rs:1178`), `the_parameter_reads_…` (`lines.Lines#reprice`,
  `heap.rs:1691`) and `the_other_object_reads_have_the_same_verdicts_under_jbmc_and_auto_confirm`
  (`orders.Orders#reprice`, `heap.rs:1871`), each "JBMC did not finish within 1800 s". The same three that failed at
  1800 s on 2026-11-07; `the_computed_equations_…` (`prices.Prices#total`) passed. Not caused by example 286's engine
  changes. Still open. See VF-030 for what this job did not run.
- **Diagnosed and changed** 2026-11-16 on `vm-1`, with the user. What the 77k clauses are: multiplications. Each
  of the three obligations relates products whose operands are equal only under the correspondence or a branch
  (`cents * quantity` in the old `price` against `quantity * cents` in the new; in `reprice`, the product of a
  conditional against the conditional of two products). JBMC's SAT backend builds every multiplication as a
  circuit of its own, so CaDiCaL has to rediscover each equality through two 64-bit multipliers. Probes on the
  retained harnesses (capped at 4 GiB and minutes, JBMC 6.11.0, Z3 5.3.3):
  - JBMC's formula for `lines.Lines#reprice`, written as SMT-LIB, has 4 products. Z3 gives no answer on it in 60 s.
    With a congruence lemma for every two of them (equal operands, in either order, give equal products: valid for
    any fixed-width multiplication), Z3 answers `unsat` at once.
  - With JBMC driving Z3 on that formula (`--external-smt2-solver`), JBMC reports every property of
    `objects.Kernel#price`, `lines.Lines#reprice` and `orders.Orders#reprice` proved, in 0.11 to 0.14 s each.
  - On their defect twins the same route makes JBMC stop on an invariant of its own
    (`json_goto_trace.cpp:122`): it can't write a trace as JSON from an SMT model. So the route can give proofs
    only, and a counterexample stays with JBMC's own solver, which finds these in 0.1 s.

  The change, in the tool and not in the tests or the harness: `lib/src/congruence.rs` and `jbmc::run`
  ([`lib/README.md`](../lib/README.md), "A second attempt for a JBMC run that has no verdict yet"). A run without
  a verdict after 30 s is held still, its formula is given to Z3 with the lemmas, and only a proof is taken; else
  the run goes on with the time it had. Through `jbmc::run`, `lines.Lines#reprice` was proved in 30.2 s (the
  attempt itself 0.2 s, 6 lemmas over 4 products), and its defect twin was refuted as before. No claim, bound or
  expectation changed. The prices test has proofs that are harder for Z3 too (`raise` 21 s with the lemmas,
  `raised` and `raise-relation` more than 30 s), so it may still need the longer limit. Job
  `20261116-144006-vf-018-the-heap-proof-tier-under-jbmc-an` runs the nine tests unchanged at the 600 s limit:
  the closing condition. Still open until it is in.
- **Closed** 2026-11-16 on `vm-1`: job `20261116-144006-vf-018-the-heap-proof-tier-under-jbmc-an` (at `d3db6d8bd8d2`,
  `cargo test --release --test heap -- --ignored`, nine tests unchanged at the default 600 s JBMC limit) passed:
  9 passed, 0 failed in 536 s of tests (job 11m52s, peak 2.0 GiB, estimated 1h30m and 4 GiB). That includes the
  three that failed at 1800 s (`objects.Kernel#price`, `lines.Lines#reprice`, `orders.Orders#reprice`) and the prices
  test. The second attempt on Z3 with congruence lemmas settles it. The estimate was about 7 times too long.

### VF-015: example 109's old `toDigit` refuted, but its witness can't be replayed: the interpreter can't read `StandardCharsets.UTF_8`

- **Status**: open
- **Raised**: 2026-11-07, from the inventory of failed results for the cleanup loop. Job
  `20261103-010716-example-109-revisited-hex-todigit-s-regr` at `4abee307b922`, on `FilSurface`, failed on
  2026-11-03. It was never rerun or tracked.
- **Found**: step 3 ("old toDigit decodes the Arabic-Indic zero") exited 1. JBMC 6.11.0 found `ch == 1632`, but the
  interpreter could not replay it: `outcome: <could not replay: <unsupported: reads static field
  java.nio.charset.StandardCharsets.UTF_8>>` (`lib/src/interp/natives.rs:373`). The two steps after it were
  skipped. The JDK models have shipped with jvmcontract since, so the failure may have changed.
- **Needs**: a rerun at the current commit first. Then, if it fails the same way, the interpreter reads
  `StandardCharsets`' constants as the JVM has them. For the cleanup loop's native stream.
- **Tracked in**: [`llm-dlc/loops/cleanup-native.md`](../llm-dlc/loops/cleanup-native.md) (N3).
- **Closes when**: the job, resubmitted at a fixing commit, passes.
- **Rerun** 2026-11-07 on `vm-1`: job `20261107-165827-example-109-revisited-hex-todigit-s-regr` (at `86e4ce7d220f`) failed at step 3, differently. The witness replay is no longer the problem (JBMC now proves the old `toDigit` for `0x0660`). Now `jvmcontract` refuses the result under `--gaps strict`: "JBMC proved it, but reaches 1 construct it approximates without implementing, and refused it: `jdk-static-method:java.lang.String.format(String, Object[])`" (a stub JBMC returns null or any object for). Steps 4 and 5 were skipped. **Needs**: a decision on whether the job should pass `--gaps assume` or advised (the job's step, the submitter's), or a model of `String.format` (the exception path of `Hex.toDigit` calls it); the cleanup loop's native stream. The entry stays open.
- **Rerun** 2026-11-08 on `vm-1`: job `20261108-011411-vf-015-example-109-revisited-hex-todigit` (at `1b376e0f1e77`) got further. The gap preflight now asks JBMC's solver and finds no path reaches the `String.format` stub, so step 3 (old `toDigit` for `0x0660`) passes and step 4 (the change found, witness replayed) passes as expected. Step 5 ("nothing else changed on ASCII", expected: verified over every char x int) exits 1: `Hex#toDigit cannot be verified: an unexpected property failed: java::EquivalenceHarness.check:(CI)V.1`, with 4 `throwing-initializer` defect notes (JBMC runs `CharEncoding.<clinit>` and `Hex.<clinit>`, before and after, as possibly throwing NullPointerException, and `catch (java.lang.Error)` in the harness) and the `String.format` gap note. **Needs**: whoever owns the stream (stub-reachability loop, cleanup native stream) to decide whether the harness's `catch (Error)` and the initializers' possible NPE (probably the JDK stub for `StandardCharsets`/`Charset`) make property `check.1` fail spuriously (then a model or an `--unwind`/assumption fix), or a real difference. Logs: `verification/results/20261108-011411-vf-015-example-109-revisited-hex-todigit/logs/5-*.log`. The entry stays open.
- **Triaged** 2026-11-08 by the stub-reachability loop, from that job's `work-change/jbmc.log` and
  `work-ascii/jbmc.log`. Neither the initializers nor a stub is the cause. Property `check.1` is JBMC's "no uncaught
  exception", and both traces end the same way: the old `toDigit` is called on an ASCII char that is no hex digit
  (`ch = 0` in step 5), constructs `DecoderException` and throws it, and the exception leaves `EquivalenceHarness.check`.
  `DecoderException` is a checked exception (it extends `java.lang.Exception`), and the equivalence harness's call
  handlers (`lib/src/harness/mod.rs`, `harness::EXCEPTIONS`) catch only the listed unchecked exceptions,
  `RuntimeException` and `Error`. So every equivalence over a method that throws a checked exception can't be verified.
  That includes step 4: its `test $? -eq 1` took "cannot be verified" for the change being found, so its pass shows
  nothing. **Deferred by the timebox**: it is N3's second failed attempt in a row, after `20261107-165827-…`, so the
  loops don't try again. **Needs**: the equivalence harness to tell apart the exceptions the two versions declare (a
  handler for each class in their `throws` clauses, then `java.lang.Exception`, as the property harness already
  handles a declared exception). Then this job, resubmitted with step 4 checking for a found change rather than exit 1,
  in a session a person starts. That is a harness change with unit tests, plus one job of a few seconds of JBMC.
  Recorded in [`llm-dlc/loops/stub-reachability.md`](../llm-dlc/loops/stub-reachability.md)'s Progress.
- **Rerun** 2026-11-08 on `claude-vm`: job `20261108-024648-vf-015-example-109-revisited-hex-todigit` (at
  `eea1a8a8a699`, after the harness catches declared checked exceptions) failed at step 5 only, in 10.6 s. Steps 3
  and 4 pass, and step 4 now means what it says: a violation found for the change, witness `toDigit(ch='٧',
  index=-1)`, before 7, after unreplayable (`String.format depends on the default locale`), reproduced by the
  interpreter. Step 5 ("nothing else changed on ASCII", expected: verified) no longer fails on the exception
  property; it now exits 1 with `cannot be verified: JBMC proved it, but runs 4 constructs otherwise than the JVM
  (throwing-initializer at before./after. CharEncoding.<clinit> and Hex.<clinit>), so the proof is refused under every
  --gaps mode`. JBMC treats those initializers as possibly throwing NullPointerException (probably the
  `StandardCharsets`/`Charset` stub), and the proof is refused by the harness's own `catch` clauses naming
  NullPointerException/Error. **Needs**: whoever owns the native/JBMC-defect stream to decide whether those
  initializers can really throw (a model of the charset constants, or the defect check recognising that no path
  reaches the throw, as the gap preflight now does for stubs), or the job to use `--engine auto`. Then resubmit.
  Logs: `verification/results/20261108-024648-vf-015-example-109-revisited-hex-todigit/logs/5-*.log`. Stays open.

### VF-002: examples 147, 148 and 149 never reach a proof

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Jobs `20261106-053555-example-147-b11-advised-contracts-a-cont`,
  `20261106-053555-example-148-b11-advised-contracts-full-j` (at `ef5d434c48db`) and
  `20261106-061323-example-149-b11-contract-library-full-ji` (at `8ea88f97e447`).
- **Found**: each fails within a second with "the patch does not change the subject file
  examples/apps/crosscut/src/main/java/net/terminalvalue/crosscut/retry/Jitter.java". The patches create that file
  (`--- /dev/null`), and `build.py`'s `excerpts()` requires the subject to exist before the patch. Deterministic: it
  fails the same on any machine, at the jobs' commits and still on 2026-11-06.
- **Needs**: either `excerpts()` accepts a subject the patch creates (an empty before side), or the examples' patches
  stop creating it. For whoever owns the advised-contracts examples (Phase 3 of the sound-verdicts brief).
- **Tracked in**: [`llm-dlc/loops/sound-verdicts.md`](../llm-dlc/loops/sound-verdicts.md#progress) (the entry of
  2026-11-06 on `vm-1`), and the notes of examples 147, 148 and 149.
- **Closes when**: the three jobs, resubmitted after the fix, pass with each example's expected verdict.
- **Seen again** 2026-11-07 on `vm-1`, in jobs `20261107-163046-example-147-b11-advised-contracts-a-cont`,
  `20261107-163047-example-148-b11-advised-contracts-full-j` and `20261107-163049-example-149-b11-contract-library-full-ji`
  (at `d32ddc64d1a4`, resubmitted unchanged by the cleanup loop's examples stream after the `excerpts()` fix). The
  subject check is no longer what stops them. Now each fails in 0.2 s at "apply the patch": `git apply` reports
  `crosscut/src/test/java/net/terminalvalue/crosscut/Tests.java:19: patch does not apply`. The three patches add
  their test classes to the suite list in `Tests.java`, whose context has since changed (the list gained entries
  with examples 150 to 152 and the later crosscut examples). I checked with `git apply --check` that they don't
  apply to the current tree either, so a rerun alone won't help. **Needs**: regenerate the three `change.patch` files
  against the current crosscut app (the examples stream; the patches also change `properties.contract` and
  `Jitter.java`, which should be unaffected), then resubmit. VF-002 stays open.
- **Rerun** 2026-11-07 on `vm-1`: jobs `20261107-165152-example-147-b11-advised-contracts-a-cont`, `-148-` and `-149-` at `35a9ea8fadaa`, after regenerating the patches. 149 **passed** (verified as expected, results applied). 147 and 148 fail in 3 s in `stage_contracts` (`build.py:432`): `FileNotFoundError: .../.build-py/examples-*/attempts/147/attempt-*/gaps.contracts`: `shutil.copyfile(folder / name, target)` reads `gaps.contracts` from the attempt's directory, where `build.py` hasn't copied it from the example's folder (149 uses the contract library, not a `gaps.contracts`). **Needs**: `stage_contracts` reads the example's own folder (the examples stream), then resubmit 147 and 148. The entry stays open until both pass.
- **Deferred by the timebox** of the cleanup loop after `stage_contracts` and `contracts_digest` were fixed
  (`xmsmzwoy`). **Decided** by the user on 2026-11-07: correct the wording of 148 and 149, whose titles, summaries
  and jobs named three contracts ("1 proved, 2 tested") although, with `Integer.numberOfLeadingZeros` no longer a gap,
  only the two tested ones may appear, and resubmit 147 and 148. For 148, the user decided to run it first and
  reword it after: its point was a contract proved against the JDK's bytecode, and only the run shows whether the
  agent's contract for `numberOfLeadingZeros` is still proved and counted.
- **Resubmitted** 2026-11-07 as `20261107-223430-example-147-b11-advised-contracts-a-cont` and
  `20261107-223430-example-148-b11-advised-contracts-full-j`, with 149's summary, explanation and resolution corrected
  to two contracts in the same commit (its passing result already reads `relying on 2 contracts ..., 2 tested`).
  148's job expects the verdict alone. VF-002 closes when both pass; 148 is then reworded to what its result shows.
- **Failed again** 2026-11-08 on `vm-1`: `20261107-223430-example-147-b11-advised-contracts-a-cont` and
  `20261107-223430-example-148-b11-advised-contracts-full-j` (at `a8b76de9c96f` and `b521d26a73ab`), each in 3.6 s,
  with the same `FileNotFoundError` as on 2026-11-07: `build.py:432` in `stage_contracts`, `shutil.copyfile(folder /
  name, target)` where `folder` is the run's attempt directory
  (`.build-py/examples-*/attempts/147/attempt-*/gaps.contracts`), not the example's folder, which holds
  `gaps.contracts` (committed). `run()` calls `RUNNERS[app][approach](out, example, tmp, module, result)`
  (`build.py:692`) with `out`, so `run_tool_property(folder, ...)` (`build.py:2365`) receives the attempt directory.
  So the earlier fix to `stage_contracts` and `contracts_digest` did not reach this call. It is `build.py`'s, not the
  pipeline's or the jobs': they are as they should be. I did not fix it or resubmit, since it would fail the same.
  **Needs**: the examples stream or whoever owns `build.py` passes the example's folder to `stage_contracts` (check
  `advice_record`, which gets the same `folder`), with a unit test that runs a B11 example with `approach.contracts`
  through `run()`; then resubmit 147 and 148 unchanged. VF-002 stays open.

## Decided and closed

### VF-071: stock JBMC requires qualification for an active versioned application class

- **Status**: closed for the recorded subject, helper and deployment controls by `20261127-062828-check-stock-physical-input-reads-and-typ`.
- **Raised**: 2026-11-26 on vm-1. Job `20261126-203730-verify-multi-release-entry-binding-acros` at `9a2aa43232d1` ran both assertions on JDKs 8, 17 and 21.
- **Found**: the JDK 21 application returned 5 from its versioned Gate class. The unguarded direct JBMC-backed property command verified `result == 3`. The native engine refuted that assertion. Both engines agreed on 3 on the two profiles where only the base member was eligible.
- **Guard verified**: the direct property and equivalence commands now return unverifiable for an active versioned subject or helper. They still accept an ordinary earlier winner. The JDK 8 and 17 base controls retained both their matching proof and their counterexample. [Guarded subject](classpath-entry-discovery/mr-guard.json) · [Guarded helper and paired route](classpath-entry-discovery/stock-helper-guard.json)
- **Resolution**: the managed `build.py --stock-property` route binds the original JVM-selected entries for a closed integral subject and its static callees. A fresh private projection records which physical class files the deciding stock JBMC 6.11.0 command opened and read. The qualified JDK 21 subject and helper each verified 5 and refuted 3. JDK 8 and 17 used 3, and the earlier helper returned 7. Four negative controls cover absent read evidence, a different binding and the unqualified raw property and paired routes. [Sixteen checks and raw stock evidence](blind-caller/stock-profiles.zip)
- **Scope**: the raw property and paired/equivalence commands continue to refuse active versioned members without evidence from the deciding invocation. Broader application and initialization behavior needs its own backend binding.
- **Tracked in**: [Original assertions and physical bindings](classpath-entry-discovery/mr-proofs.json) and the [classpath discovery report](../llm-dlc/loops/in-the-loop-classpath-and-entry-discovery-brief-results.md).

### VF-062: the checker's before/after renaming was visible to the program, in both directions

- **Status**: closed for the reported namespace and cache errors on 2026-11-25 by `689388178a8d`, the original release JVM controls, and the final historical, blind and calibration remeasurements.
- **Raised**: 2026-11-24 by the watcher, from the advisor's reading of the queued run `beyond-jbmc-java-change-verification-cam` (Astra 6.2 at max effort, session `c3caedf3`, 3 cycles).
- **Found**:
  - **A false counterexample.** On the blind panel, the native checker refuted equality on a generated Sisu Plexus caller. The old version's `toString()` carried the checker's synthetic `before.` package in its class name, although both unmodified releases return the same string for both Boolean inputs, the witness included. It counts in the frozen blind result as an incorrect native decision (`lib/benchmark/beyond-jbmc/blind_report.py`).
  - **A false proof.** The same renaming could also hide a real difference: on a constructed control, the frozen checker proved equality although the original JVMs returned different strings for both inputs.
  - **So the bug is two-sided.** It produced accepted results the JVM refutes in both directions, the kind of failure VF-055 is about. Any frozen native proof or refutation that involves an observed class name (`toString`, `getName`, `getSuperclass`) or reflective lookup is suspect until it is re-measured.
  - **A stale proof cache.** A separate regression showed `Class.forName("lookup.Optional")`: equality held while neither release had the class. After the class was added to the new release only, the JVMs answered false and true, but the cache reused the earlier proof.
- **Fixed in the run (cycle 2, `mrnrzoyr`, `yopsvwqk`, `yptnxvlp`)**:
  - The checker preserves original names in equivalence.
  - The proof cache's key binds the ordered class providers and their contents.
  - The constructed control is now refuted with the strings both JVMs return, and the Plexus caller is proved unchanged.
  - Eight post-freeze cold and warm decisions on Plexus and Commons Codec matched the JVMs.
  - Cycle 3 re-ran all 187 historical claims on the final checker: no disposition changed (94 proved, 85 refuted, 8 open; `verification/beyond-jbmc/followup/historical-native/`, job 20261124-124601).
- **What remained after the first run**:
  1. **Resource lookup.** Batik and dom4j hit the same isolation problem when the renamed old definitions look up XML resources (`verification/beyond-jbmc/blind/04/assisted/report.json`, `blind/16/assisted/report.json`).
  2. **The blind panel.** Its decisions, and the calibration's, are not yet re-measured with the fixed checker. The frozen 0/16 stands as recorded, but the per-project dispositions that involve class names or resources should be repeated.
- **Additional original-JVM witness, 2026-11-25.** Ordinary strict native equivalence on checker `a03d514a66aa` proved that a public reader returned the same integer on both releases for every Boolean input. The original applications returned −1 on a missing key, then 65 and 66 on the present key. The proof's own assumption listed only the repaired deployment's byte digest for `META-INF/paint`. The generated loader represented both releases with the same object and looked up both keys on the combined classpath. The real application's finite two-JVM comparison and this native symbolic proof are distinct routes.
- **The converse and replay.** On the compensating reader, both original deployments returned 65. The old checker reported 66 versus 65 and marked its replay as reproduced on a JVM. That JVM had run both calls on the repaired deployment's resource path. The strict checker now keeps a distinct loader and original classpath for each side, records the ordered resource digests, and confirms public static integral return differences on two fresh, unmodified deployments. It refuted the first equality at `true` with 65 versus 66 and proved the compensating equality. A paired counterexample requiring an arbitrary postcondition remains open when its original isolated replay is unavailable. [Original false proof and raw inputs](beyond-jbmc/scaffold-first/native-resource/pre-repair.json) · [Original false counterexample and oracle](beyond-jbmc/scaffold-first/native-resource/pre-repair-compensation.json)
- **Closing evidence.** Batik and dom4j ran on unrenamed original classpaths with recorded resource and factory origins. The corrected native binary preserved all 187 historical dispositions, including 179 decisions. It remeasured the 64 original generated blind candidates, four calibration candidates and the full supplied questions for all 16 pairs. The earlier false Sisu counterexample became a verified equality. Every other generated disposition held and no measured native decision contradicted the original JVMs. The corrected symbolic resource job preserved the compensating equality and reproduced the real changed byte, including after a same-path replacement. [Original deployment and proof comparison](beyond-jbmc/scaffold-first/RESULTS.md) · [Final machine-readable audit](beyond-jbmc/scaffold-first/audit.json)
- **Paired resource replay, 2026-11-25.** Public static integral methods now replay both original calls and check the input guard and scalar postcondition. The annotation indexer's changing byte and two other previously open paired witnesses reproduced. A declared inequality also refuted at two equal missing-key returns. The 30 preregistered comparisons and 187 historical controls passed on the same executable. Object results, exceptional paired outcomes and guards outside the scalar evaluator can still require a more general original-deployment replay. [Complete predicate and historical results](beyond-jbmc/resource-postconditions/RESULTS.md)
- **Closes when**: both open items are done, with a control that renames nothing the program can observe, and no native decision changes against the JVMs.
- **Related**: VF-055 (an accepted result the JVM refutes); VF-063 (scaffolding, of which the resource isolation is a part); VF-064 (why the run stopped before these were done).

### VF-058: ordinary Configuration startup and the remaining receiver frontiers

- **Status**: decided for this campaign on 2026-11-24. A physical JVM refuted all four original JSON and YAML caller-side guarantees at a permitted process prestate. The recovery report assigns the remaining strict-native and unrestricted-overload questions to their respective models. [Receiver evidence](../lib/benchmark/receiver-discovery/recovery.md)
- **Raised**: 2026-11-24 by the watcher, at the user's request (relayed by the advisor), after the single-agent run `receiver-construction` (Astra 6.2 at max effort, session `3394e768`).
- **Found**:
  - **Why it is open:**
    - At 00:49 UTC the watcher decided to continue (decision single-receiver-construction-D001), for "one more cycle" on the frontiers below.
    - The filter refused cycle 2 at 00:54, 2.8 minutes in, with nothing committed. This is the second stop in VF-046.
    - The watcher then handed the run over as finished after cycle 1, merged as `oqmtltol`, rather than retry in a fresh session.
  - **What cycle 1 decided:**
    - JavaParser: 2 of 8 (the empty-root counterexamples).
    - Guava: 8 of 8, including the complete 137,257-string client language.
    - Commons Lang: 6 of 6.
    - JGraphT: its 25-graph, 150-transition audit.
    - The three-worker schedule enumeration.
    - Commons CSV: kept 4 of 4.
    - Native kept 57/60 and integrated JBMC 24/60 on the preceding comparison.
  - **The named frontiers** (from the decision and "Comparator coverage and next investigation" in `llm-dlc/loops/receiver-construction-and-property-discovery-results.md`):
    1. **Commons Configuration #565 and #601:** both upgrades stop at `System.getProperties()`. The page names the next experiment:
       - start at the actual `Properties` object it returns;
       - check consistent per-key presence, value and identity through a public caller;
       - rerun JSON and YAML at their four frozen observations, and isolate the two live trees.

       The frontier's measurement is `verification/receiver-discovery/qualification/commons-configuration-565/measurement.json`.
    2. **JavaParser:** 6 of its 8 ordinary strict-native claims are open. The page names the controls that separate a property-state witness from a proof over every process state: JavaParser's missing and arbitrary separator values, and XZ's cache-selection states.
    3. **The historical receiver cohort:** all 34 unrestricted overloads are open. Two caller pairs were proved on both versions.
    4. **Native scheduling:** the first remaining instruction is the worker's `Thread` constructor. That is VF-056's gap, tracked there.
- **A hazard found on 2026-11-24.** The receiver campaign's Maven cache lives under an old Codex session's scratch folder, `~/.cache/in-the-loop/agent-tmp/0cea9d0e-…/external-upgrade-shared-maven/repository`. The area's `prepared.json` files name it by absolute path. On 2026-11-23 the watcher deleted most of that folder as a cleanup, judging by its top-level date, and 1,025 classpath entries went missing. The trusted-kernel-and-receiver-recovery setup restored it by hard links from the receiver setup's snapshot (586 files, 0 missing, no new disk). Until it moves, no `agent-tmp` folder may be cleaned without first checking that nothing names it, for example `rg -l 'agent-tmp/<id>' examples verification lib llm-dlc`. The lasting fix is to move the cache to a stable path under `~/.cache/in-the-loop/` and update the references.
- **Configuration decision**: the ordinary predicate admits setting a property before first use. An invalid name on the installed table made selector 0 return false on all four deployments. The stock setting produced all sixteen expected values, and two fresh configuration trees remained independent in both read orders. Strict native proved the explicit install, replace, inherit and remove sequence. Its ordinary caller still needs a model for the pre-existing system table. [Original caller measurements and clean-source jobs](receiver-discovery/recovery/results.json)
- **Remaining owners**: the native JVM startup model owns arbitrary separator values and their exceptional initialization in JavaParser. The XZ frame path needs the security-provider lookup in `MessageDigest.getInstance` after the stream and map constructors. The receiver campaign owns the validated domains for the 34 unrestricted overload pairs. The three ordinary thread claims remain with VF-056.
- **Cohort**: strict native decides 4/46 sides and 2/23 pairs. Adding original JVM witnesses at admitted process states raises the count to 10/46 and 5/23, including the earlier XZ pair. All 34 unrestricted paired overloads remain open. [Recovery report](../llm-dlc/loops/trusted-kernel-and-receiver-recovery-results.md)

### VF-057: historical induction can accept a false heap frame

- **Status**: decided. Advance the opt-in independent check for the qualified first-match family. The historical producer's choice of the frame formula has lost the power to establish that theorem at the independent entry. The Rust bytecode semantics, initialized-class execution model and caller's artifact and theorem binding remain trusted.
- **Measured on 2026-11-24 by change-verification:** job `20261124-014943-replay-the-guava-change-plan-nodes-and-i`, step 6 (`lib/benchmark/trusted-kernel/historical_frame_control.py`), record `lib/benchmark/trusted-kernel/historical-frame-control.json`. The job injected one wrong conclusion into a private copy of the recorded historical Python/Z3 rule, with the rule digests checked against `baseline/336.json`, and ran it on the heap-writing Guava `indexOf` control:
  - **The genuine historical producer** leaves the frame obligation "preserve the input heap" `unresolved` (sat where unsat was expected).
  - **The faulted producer** marks it `established`: a false acceptance.
  - **The independent checker** `refuted` the faulted result with a checked witness: on `[7]` with target 7, the method returns 0 and leaves `[0]`, and the original JVM reproduces it.

  So a producer error that causes acceptance in the historical route has lost that ability at the independent checker, which is the brief's criterion. trusted-kernel-and-receiver-recovery should start from this receipt.
- **Raised**: 2026-11-23 by the watcher, at the end of the trusted-kernel run (Astra, 2 cycles; decision single-trusted-kernel-D001; the run's second cycle ended on a stale working copy after its turn had finished, with its work committed and landed as `kpkqomum`).
- **Found**:
  - **What the run established, all checked from original class bytes by the independent Rust checker in a fresh process:**
    - Guava `Ints.indexOf` and `Longs.indexOf`, for every legal length and signed target: each terminates, returns the first match or -1, and preserves the heap. Certificates are about 1.1 KB, with a median check of about 1.2 ms. The `Longs` transfer took 49 net lines on the frozen int checker.
    - Temurin 21 `Arrays.fill` writes exactly the requested interval for every valid `int[]` range (37 obligations, 1,197 bytes, 1.24 ms).
    - Example 337's caller is correct under aliasing (51 obligations).
  - **What else held:**
    - The extra-write caller is refuted (shared `[11]`, empty range: it returns 7), and the JVM confirms it.
    - All six behavioural mutants gave checked counterexamples.
    - Lean proved the scalar identity.
    - LRAT certified all 18 observed UNSAT calls.
    - Both genuine historical solver failures reproduced at their witnessed inputs.
  - **The gap.** The brief makes "advance the semantic checker" conditional on, among other things, "the team can identify a producer error that has lost the ability to cause acceptance". Fault injection was run only on the experimental issuer. How the historical producer and its replay respond to a deliberately corrupted producer was never measured, and the run's own report names it as the one open experiment.
  - **The run's recommendation:** advance the semantic checker, measuring reuse next on the JDK `long[]` overload of `Arrays.fill`. Because of the gap, that recommendation rests on the issuer's fault injection, not on the historical producer.
- **Decision evidence**: the case table now includes the historical false acceptance and the independent refutation as two routes for the same external request. Z3 correctly answered the submitted formula. A retained pristine receipt detected drift in the status, obligations and formula digest. Regeneration under the same producer repeated the erroneous result. The independent detector was the frame rule at helper store PC 25, corroborated by a physical JVM. [Managed comparison](../lib/benchmark/trusted-kernel/historical-frame-control.json) · [Case table](../lib/benchmark/trusted-kernel/evidence/cases.json)
- **Tracked in**: this finding and the [kernel decision and replay commands](../lib/benchmark/trusted-kernel/README.md).
- **Resolution**: the decision and the fresh original-adapter comparisons are recorded in the [recovery report](../llm-dlc/loops/trusted-kernel-and-receiver-recovery-results.md). The omitted-exit experiment has a separate evidence scope in that report.

### VF-034: the default test run at `xunroyyopkuq` (the prove-setup merge) failed three Rust tests, twice

- **Retired (2026-11-27, change `kkkqupww`):** this entry names `run-brief`, which is no longer in the repository. See [`llm-dlc/retired.md#multi-agent-brief`](../llm-dlc/retired.md#multi-agent-brief) for what replaced it and the last commit that has it.
- **Status**: closed, by the user's decision on 2026-11-17: the likely cause is known and fixed for this case, and
  the pipeline's handling of jobs will be refactored as a whole later, so this is not worth investigating further.
  The default run at the merge of prove-setup's finished line, job
  `20261117-015957-default-test-run-at-ksyktoyyrtyn` (at `ksyktoyyrtyn`, which contains `9c48697e070a`), passed 49 of
  49 with the lock in.
- **Likely cause**: two default test runs at once in one warm cargo target directory. Job `005759` was started a
  second time at 01:07 while job `010456` ran; the tests' work folders and proof caches live in that directory's
  `tmp/`, and all three failures are a test finding another run's files there (a stored result for a build it had not
  checked, a changed claim answered from the cache). Job `010456` itself had eight Rust tests fail and pass only on
  their second run, so its "passed" was no evidence either way. Not reproduced on purpose. Since change `kzwsnszx` a
  default-run step holds a lock for its whole run, so two runs at commits that have it no longer overlap. A job at a
  commit without the lock can still overlap (the run-brief line's job `20261117-020349` ran beside `015957` from
  02:04, which had one cache test fail and pass on its retry). Later on 2026-11-17 the user removed the default run
  as a job altogether: it runs inline again, and `lib/tools/test_costs.py run` holds a lock in the workspace's cargo
  target directory, so two inline runs in one workspace take turns.
- **Why the passed job ran again**: the first pass was committed in the default workspace at 01:06:45 (change
  `slquqtpy`), and in the same second the watcher's `jj new lzvyqmsy` there moved the working copy off that commit
  before it had a child, so the runner found the result neither in its state folder nor in the working copy and
  started the job again. `slquqtpy` is merged into the main line (`ksyktoyy`), and the runner now counts a result
  recorded on any visible head as done.
- **Raised**: 2026-11-17 on `vm-1`. Job `20261117-005759-default-test-run-at-xunroyyopkuq` (at `9c48697e070a`) failed in
  6m28s on its second run, in three tests, and again on their retry:
  `application_core_joint::j1_the_quote_family_composes_the_four_streams`,
  `environment::a_per_call_choice_proves_a_rewrite_and_refutes_a_wrong_key` and
  `effects::an_effect_proof_is_reused_exactly_when_its_claim_is_unchanged`; all Python suites passed.
- **Not pursued, by the same decision**: the remaining sharp edges (a commit made in the default workspace while
  another process moves its working copy is left off the main line; the flaky retry counts a run with many
  second-run passes as passed; overlap with a job at a commit without the lock) go to the refactoring of pipeline jobs
  rather than to fixes here.
- **Tracked in**: the job's `logs/1-default-tests.log`; the lock in `verification/default_tests.py` (`kzwsnszx`).

### VF-029: job `20261115-181435-object-comparisons-under-jbmc-and-auto-c` cancelled, not recorded

- **Status**: decided
- **Raised**: 2026-11-15 on `vm-1`. The runner started the job (at `4dc3c5d1b982`) at 18:25; the prove-examples
  moonshot then withdrew it (deleted its job file) because the harness classes are byte for byte the same as in
  `20261115-173209-object-comparisons-under-jbmc-and-auto-c`, which already runs that proof tier. It ran on, and its
  scope was stopped at the user's request (about 33 minutes in).
- **Decision**: its leftover result was moved to `verification/.state/set-aside/20261115-181435-object-comparisons-cancelled`
  and not collected or triaged. It says nothing about the change. Nothing to rerun: VF-018 is the open entry for the
  same tests.
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): used as a control for the lifecycle view. A cancelled job is still eligible to run again and is still not collected unless named; the view now shows it in the state it is waiting in, with the stopped attempt in its `attempts` and a `cancelled` block, so an intentionally uncollected cancellation is visible without being a result.

### VF-028: example 307 Phase 5 step 1: `BCrypt.hashpw(String,String)` preservation and mutant-preservation refused at `--nullable password`, so neither is as expected

- **Status**: closed 2026-11-15 by jobs `20261115-013518-example-307-preservation-vf-028-rerun-st` and `20261115-013518-example-307-mutant-preservation-vf-028-r` (at `45fd8612b5d1`, passed on `vm-1`, 5.6 s and 5.8 s, both with `example:task-refused-as-predicted`, outputs applied): the refusal at `--nullable password` is the recorded, expected result. Neither task ran as `task-as-expected`; that needs the checker to accept nullable `String`s in a regression check. Originally: recorded 2026-11-15 by the example-targets loop by "Closes when"'s second branch, as VF-027 was (the user's decision of 2026-11-15: recorded, not restated). Each task has an observed blocker and a packet under example 307's `records/refusals/`, its readiness is blocked, and its claim and expected conclusion are unchanged. The reruns predicting the refusal are queued: `20261115-013518-example-307-preservation-vf-028-rerun-st` and `20261115-013518-example-307-mutant-preservation-vf-028-r`. It closes when both pass with `task-refused-as-predicted`.
- **Raised**: 2026-11-15 on `vm-1` (one-loop row: 80G, 26 CPUs, 13 workers), jobs `20261115-011448-example-307-preservation-phase-5-step-1` and `20261115-011448-example-307-mutant-preservation-phase-5` (at `3ec935ff400b`; 5.6 s each, peak 185 MiB, estimated 30 min).
- **Found**: each job's one step, `build.py 307 --task <T>` (native strict), exited 1 with the task `unresolved (completed; NOT AS EXPECTED)` (expected `established` and `refuted`). The receipts' `records/verifier-output.txt` give the same refusal for both: `BCrypt#hashpw(String, String) cannot be verified: --nullable password: password is a java.lang.String, and in a regression check only an object parameter made by its constructor may be null or the same as another`. It is cause 3 of VF-027 (a `String` parameter with `--nullable`), not a verdict on the change and not a pipeline error. Outputs kept in each job's `outputs/`, not applied.
- **Needs**: the example-targets loop to either restate the tasks without `--nullable password` (if null is not meant to be in scope, the claim changes and the example's notes should say so), or record 307's two tasks as unprovable by this route, as it did for VF-027's 23, and resubmit predicting the refusal; or the checker to accept nullable `String`s in a regression check (a different loop). Jobs not resubmitted by this run: the result will not differ until the subject or checker does.
- **Tracked in**: example 307's notes and the example-targets brief's Progress (to be recorded by the loop).
- **Closes when**: each task's job passes with `task-as-expected`, or the example records it as unprovable by this route and a job predicting the refusal passes.

### VF-027: example-targets Phase 5 step 1: 23 of the 24 native strict proof jobs give "cannot be verified" (no verdict), because the task's subject is outside what the checker can build, so none is as expected

- **Status**: closed 2026-11-15 by the example-targets loop, by the second branch of **Closes when**, as the user decided on 2026-11-15 (`llm-dlc/loops/example-targets.md`, Progress): each of the 23 tasks is recorded as unprovable by this route (an observed blocker with finding `VF-027` and its gap packet `records/refusals/<task>.json`, readiness `blocked`, its claim and `expected` unchanged), and each job was resubmitted unchanged in its claim, predicting the recorded refusal: the 23 reruns `20261115-005926..28-*-vf-027-rerun*` (at `6e9a99ee0d85`, collected in `kqpykqpp`) all passed with `example:task-refused-as-predicted`, so the expectation matches. No task ran with `task-as-expected`, and none can until the checker gains the semantics each packet names: the five causes are the observed gaps of the brief's v1 gap inventory (Phase 5 step 4), each closed only by rerunning the original claim, never by a restatement.
- **Raised**: 2026-11-14/15 on `vm-1` (streams row: 38G, 18 CPUs, 9 workers), jobs `20261114-2342{11..14}-example-{285,286,287,305,306,105}-*` (24 jobs queued at `72a1337a1529`; each ran 1 step in 7 s to 6 min). Only `20261114-234214-example-105-regression-phase-5-step-1-ar` passed (`refuted`, as expected). Results are in `verification/results/`; their outputs were kept, not applied (nothing refuted or established, and the receipts are "unresolved").
- **Found**: every failing job's `build.py <N> --task <T>` exited 1 with the task `unresolved (completed; NOT AS EXPECTED)` or `not-executed`, and the receipt's `records/verifier-output.txt` says why. Five causes:
  1. *An interface parameter* (285 vulnerable/fixed/mutant-security: `WebMvcTags#method(HttpServletRequest)`; 305 finite-outcome-before/after, preservation, mutant-preservation: `WebMvcTags#outcome(HttpServletResponse)`): "javax.servlet.http.HttpServlet… is an interface; only a concrete class made by its constructor is" in a property or regression check.
  2. *An instance method whose receiver cannot be built* (286 vulnerable/fixed-security `DataBinder#isAllowed(String)`, 286 vulnerable/fixed-protected-state-mutation `DataBinder#bind(PropertyValues)`, 286 mutant-security; 287 vulnerable/fixed/mutant-security `BCryptPasswordEncoder#matches(CharSequence, String)`): "the receiver, an object of … made by its constructor" is outside the objects a property check makes (the classes' constructors take parameters the checker can't supply).
  3. *A `String` parameter* (287 vulnerable-guard and fixed-guard `BCrypt#checkpw(byte[], String)`; 306 mutant-preservation `PatternMatchUtils#simpleMatch(String, String)` with `--nullable pattern`): the symbolic verifier takes primitives, arrays of integral or boolean elements, and application-class objects made by their constructor, and in a regression check only an object parameter may be null.
  4. *Different dependency closures* (285, 286, 287 and 306 `preservation`, `not-executed`): "before and after have different dependency closures, and jvmcontract's equivalence takes one classpath for both" (exit 1; no `receipts/preservation`).
  5. *A construct the checker approximates* (105 `confined-change`): under `--gaps strict`, `jdk-constructor:java.lang.StringBuilder.<init>()V@jdk-25.0.5` (before's `pow` exception path) is refused.
- **Needs**: the example-targets loop (`llm-dlc/loops/example-targets.md`, Phase 5 step 1) to decide, per cause, whether the task is restated over a subject the checker handles (a concrete wrapper or a primitive/array-typed harness method, as the replay and mutant-replay scaffolds do), whether a model or an input kind is added (the checker's, a different loop), or whether the job's expectation is "cannot be verified" and the example's `notes` record it. The jobs' steps and expectations were not changed and not resubmitted: the results won't differ until the subject or the checker does. This is not a pipeline error.
- **Update 2026-11-15 (vm-1)**: the 23 reruns the loop queued at `6e9a99ee0d85` (`20261115-005926..28-*-vf-027-rerun*`) all passed with `example:task-refused-as-predicted`, i.e. each task stops at the refusal recorded above (2 s to 4 min each; 4 output files applied for 18, none for the four preservation jobs). That confirms the observed gaps; it does not close the entry, since no task has yet run with `task-as-expected`.
- **Update 2026-11-15 (the prove-examples moonshot, item 285)**: example 285's four tasks have since run with `task-as-expected`, on their unchanged claims: `20261115-173146-example-285-vulnerable-security-the-boun` (refuted), `20261115-173146-example-285-fixed-security-the-bounded-m` (established), `20261115-173146-example-285-mutant-security-the-bounded` (refuted) and `20261115-181427-example-285-preservation-the-known-metho` (established), collected in `xkplwmyz`. jvmcontract now gives a parameter of an interface type an implementation (cause 1) and takes the previous version's own dependency closure, `equivalence --before-classpath`, which the route passes (cause 4). So 19 of the 23 tasks stay recorded as blocked: cause 1 for 305's four, cause 4 for 286, 287 and 306's `preservation` (the route no longer refuses them, so their rerun checks, `workflow_refusal.py N preservation`, will now fail as not predicted; what else each needs its ordinary attempt will say), and causes 2, 3 and 5 as they were. Example 285's sidecar lists no blocker, and its packets say `closed`.
- **Update 2026-11-16 (the prove-examples moonshot, item 286)**: example 286's decision claim has since been decided beside the route, on the unchanged claim file through the adapter entry its first assumption names (`examples/286-.../proofs/prove.py`, with the lemma `proofs/simple-match.contract`): `20261115-234439-example-286-fixed-security-through-the-a` (established on 5.3.19 at the frozen bound of 8, in 920 s), `20261115-234439-example-286-vulnerable-security-through` (refuted on 5.3.18) and `20261115-234440-example-286-mutant-security-through-the` (refuted on the mutant), each refutation's witness run on a JVM. jvmcontract (`zrzuurtk`) now takes String and `String[]` parameters in a property check, expressions javac compiles, and the String, StringBuilder, stream and regex calls on the way, with `simpleMatch`'s recursion stated by a lemma proved by induction. The route did not change: it runs the verifier on the original artifact alone, so 286's six proof tasks stay recorded as blocked (cause 2 for five, cause 4 for `preservation`), their packets and rerun checks as they were. Tried through the adapter entry, `preservation` stops at the `String[]` parameter in the regression check, and the protected-state tasks at `java.util.ArrayList.<init>(int)` in `MutablePropertyValues.<init>`.
- **Tracked in**: the example-targets brief's Progress and the notes of examples 285, 286, 287, 305, 306 and 105.
- **Closes when**: each task's job passes with `task-as-expected` (resubmit with `pipeline.py resubmit ID`), or the example records the task as unprovable by this route and the expectation matches.

### VF-026: example-targets Phase 5 gate A3: example 286's replay is not executed, its `vulnerable-release` revision failed to prepare

- **Status**: closed by job `20261114-223812-example-286-replay-gate-a3-cve-2022-2296` (at `7cc6964ac0d2`, 2026-11-14, `vm-1`): passed in 4.0 s, `task-as-expected`, receipt `examples/286-*/receipts/replay/20261114T224026Z-eca417ca`.
- **Raised**: 2026-11-14 on `vm-1`, job `20261114-214818-example-286-replay-gate-a3-cve-2022-2296` (at `863e10158f94`; failed in 1.8 s, peak 114 MiB; no verdict, nothing refuted). Its six siblings passed: 285 and 287 replay, 306 replay and mutant-replay, and 105's two gate A5 proofs, each giving `task-as-expected`.
- **Found**: `build.py 286 --task replay` printed `not-executed (task replay: unsupported: prepare (example-targets-runtime): revision vulnerable-release is failed, not artifacts-ready)` and exited 1; no receipt under `examples/286-*/receipts/replay`. The log says only that the revision's prepare state is `failed`, not why (Framework 5.3.18's closure, which 287's and 306's analogous revisions prepared without trouble). The reason is in the runtime's prepare record for that revision, which the job did not keep as an output.
- **Needs**: the example-targets loop (`llm-dlc/loops/example-targets.md`, gate A3) to find why 5.3.18 failed to prepare (a JAR in 286's `sources.lock.json` not fetched or its sha mismatching, or a runtime defect), fix it, and resubmit 286's replay (`pipeline.py resubmit 20261114-214818-example-286-replay-gate-a3-cve-2022-2296`). Not a pipeline problem; the job's steps and expectations were not changed. The cause was not found by running anything by hand.
- **Tracked in**: `llm-dlc/loops/example-targets.md`'s Progress (Phase 5, the seven jobs read), and example 286's notes.
- **Closes when**: the resubmitted job passes with `task-as-expected` and a receipt under `examples/286-*/receipts/replay/`.
- **Cause found and fixed** 2026-11-14 by the example-targets loop. The job's kept work directory has the preparation's record (`.build-py/examples-*/targets/286/replay/prepare/vulnerable-release/prepared.json`): stage `adapter`, "the adapter adapter-vulnerable-release.jar never references org.springframework.validation.DataBinder#isAllowed(Ljava/lang/String;)Z". Acquisition, the shadowing check and both compiles had passed. 286's `ExposedDataBinder extends DataBinder` calls the protected `isAllowed(field)` unqualified, which javac writes as a Methodref owned by `ExposedDataBinder` (`javap`: `invokevirtual isAllowed:(Ljava/lang/String;)Z`); runtime's `_check_classpath` counted only references owned by an original class. So it was not 5.3.18's: 5.3.19 and the mutant would have failed the same way. The fix resolves a reference owned by an adapter class up the superclass chain, as the JVM does (`runtime_jar.resolve_method`); reproducer `test_runtime.py`'s `InheritedCallTest`. Rerun offline on the kept 5.3.18 JARs, the check finds `DataBinder#isAllowed` among the adapter's six original calls. **Resubmitted** as `20261114-223812-example-286-replay-gate-a3-cve-2022-2296`.

### VF-025: example-targets runtime R2: three applied outputs, the 1.4 MiB spring-core 5.3.19 JARs, are over jj's 1 MiB snapshot limit and are not committed

- **Status**: closed 2026-11-14 by the example-targets loop: the three JARs were committed by the collect commit itself (`msotkvrv`), and `jj st` shows no refused file
- **Raised**: 2026-11-14 on `vm-1`, job `20261114-180443-example-targets-runtime-r2-a-constructed` (at `b5e28e2663be`; passed in 6.2 s, peak 197 MiB; both steps passed, nothing refuted).
- **Found**: `collect` applied 54 outputs under `runtime-mutant/attempt/`. Three are JARs of 1,482,575-1,482,592 bytes (`prepare/mutant/lib/org.springframework/spring-core-5.3.19.jar`, `prepare/mutant/mutant/spring-core-5.3.19.jar`, `prepare/r5-3-19/lib/org.springframework/spring-core-5.3.19.jar`), above jj's `snapshot.max-new-file-size` (1 MiB), so every `jj` command warns and the commit leaves them out. The other 51 outputs, the result and its logs are committed. The mutant JAR, the one that is the job's point, is among the missing; its classes' hashes are in the committed `prepared.json`. I did not raise the limit or edit the result.
- **Needs**: the user or the runtime loop to decide: gitignore these JARs (they are acquired by sha256, or rebuilt from the patch), or raise the limit for the repo (same cause as VF-020). The example's notes should say the JARs are not in the history.
- **Tracked in**: [`llm-dlc/loops/example-targets-runtime.md`](../llm-dlc/loops/example-targets-runtime.md) (R2).
- **Update 2026-11-28** (the generic-jobs-pipeline run, [results](../llm-dlc/loops/in-the-loop-generic-jobs-pipeline-brief-results.md)): used as a control for the audit, which tells the three apart by git's own ids: a file a receipt names is in the commit (a blob id in the manifest), only in a working copy (a gap, with the ignore rule that kept it out), or sealed in the archive (an occurrence id the receipt carries). The audit's first run on the corpus found 947 such files in no commit (VF-080).
- **Closes when**: the JARs are ignored or committed and `jj st` stops warning.
- **Corrected** 2026-11-14 by the example-targets loop (Phase 5 step 1, request 11): contrary to **Found**, the three JARs
  are in the history. `jj file list` at the collect commit `msotkvrv` lists all three, at 1,482,575 and 1,482,592 bytes,
  and `jj st` shows no refused file. `sync.py`'s `jj()` runs every jj command with `snapshot.max-new-file-size=100MiB`
  ("Snapshotting must not skip files"), so a `sync.py commit` takes a file a plain `jj` command refuses. The warning
  lasts only until the next such commit. This also explains how VF-020's two diffs "got past the limit". An ignore rule
  would change nothing, since the files are tracked, and none was added. `msotkvrv` is not pushed yet: whether the
  JARs (two distinct blobs, about 3 MB: Apache-2.0 published artifacts and a rebuildable mutant) stay in the published
  history is on `llm-dlc/loops/example-targets.md`'s for-review list, for the user.


### VF-024: example-targets runtime R3: `run_verifier` on the fixture's five proof tasks gets no expected verdict from any of them

- **Status**: closed (job `20261114-164239-example-targets-runtime-r3-after-vf-024`, 2026-11-14)
- **Raised**: 2026-11-14 on `vm-1`, job `20261114-162937-example-targets-runtime-r3-run-verifier` (at `b397033c198f`, failed in 45 s; build and the integration-contract step passed: 16 tests, 8 skipped on the workflow stream's Phase 0 stubs).
- **Found**: step 2, the calibration, reports `NOT ok`. (1) `vulnerable-security`, `fixed-security` and `mutant-security` (expected refuted, established, refuted) all exit 1 with verdict `unverifiable`: `fixture.Gate#allowed(int) cannot be verified: the property is not well-formed: in the assertion: unknown name "code"; the names are arg0, result`. The property names the parameter `code`, but the compiled fixture has no parameter names (`arg0`): either compile with `-parameters`/debug info, or write the property over `arg0`. (2) `preservation` (expected established): `jvmcontract equivalence --before prepare/before/before.jar --after prepare/after/after.jar ...` exits 2 with `jvmcontract: Not a directory (os error 20)`, so the command is probably given a jar where it wants a directory of classes (or the reverse). Its `--unchanged-unless code == 97` has the same parameter-name problem. (3) `regex-probe` (expected unresolved): `unverifiable`, as `java.lang.String` parameters are not supported by the symbolic verifier ("a value adapter is built for it, but this check doesn't take one yet"); that may be the expected `unresolved` and only the harness's expectation of the verdict word is off.
- **Needs**: the runtime loop (`llm-dlc/loops/example-targets-runtime.md`, R3), which owns the fixture's task arguments and `run_verifier`: fix the parameter names and the `equivalence` inputs, and decide how `regex-probe`'s `unverifiable` maps to `unresolved`. Not a pipeline problem; nothing was changed in the job.
- **Tracked in**: [`llm-dlc/loops/example-targets-runtime.md`](../llm-dlc/loops/example-targets-runtime.md) (R3), not yet recorded in its Progress (the loop is running; edit of its brief left to it).
- **Closed by**: `20261114-164239-example-targets-runtime-r3-after-vf-024` on `vm-1`, passed in 44 s: all five calibration tasks give their expected verdict (`regex-probe` `unverifiable` is accepted as the expected `unresolved`), integration contract 16 tests OK (8 skipped).
- **Closes when**: the job, resubmitted at a fixing commit, passes (calibration `ok`).

### VF-001: JBMC verdicts the JVM contradicts, passed through by `--engine auto`

- **Status**: closed 2026-11-08, by jobs `20261107-222356-conformance-corpus-under-jbmc-and-engine` and
  `20261107-222356-conformance-corpus-under-engine-auto-con` (at `1e430db14391`, `mkdir -p target` added): each ran
  its test (`the_corpus_agrees_with_the_jvm_under_jbmc_and_auto`, `..._under_auto_confirm`) and passed, 1 passed, 0 failed
- **Raised**: 2026-11-06 on `vm-1`. Jobs `20261106-021741-conformance-corpus-under-jbmc-and-engine` and
  `20261106-024336-conformance-corpus-under-engine-auto-con`, both at `470be6c5ff8b`, JBMC 6.11.0.
- **Found**: the conformance corpus (54 methods, 93 claims, the JVM as reference) disagrees with JBMC in both
  directions:
  - **JBMC proves seven claims the JVM refutes**, under `--gaps strict`: `capacity`, `builderCapacity`,
    `mapCapacity`, `setCapacity` and `loadFactor` (JDK constructors that throw on a negative capacity or a load
    factor of 0 or less; JBMC's library models, pinned to 2022, return normally), `nullMonitor`
    (`synchronized ((Object) null)` throws `NullPointerException` on the JVM), `firstByte` (`Random.nextBytes`) and
    `pairsEqual` (a record's `equals` through `invokedynamic`).
  - **JBMC reports violations the JVM does not reproduce** on `caught(n=0)` and `nestedHandler(n=0)`, which catch the
    `ArithmeticException` of an integer division by zero. The tool's own checker proves both and the JVM agrees.
    Either JBMC's semantics or a flag jvmcontract does not pass (such as `--throw-runtime-exceptions`).
  - **`--engine auto` takes JBMC's wrong `Verified`** for `loadFactor` and `pairsEqual`, where the own checker has no
    verdict, under strict and under assume. This part is jvmcontract's, not JBMC's.
- **Needs**: Phase 1 of the sound-verdicts brief is not done, though the brief read as if it were. Its criterion is
  that no engine, nor `--engine auto`, gives `Verified` under strict for a claim the JVM refutes. Closing it means
  treating JBMC's verdicts on JDK calls its models stand in for as gaps under strict, making `synchronized (null)`
  and division by zero behave as on the JVM under JBMC (or refusing them), and not letting auto take a JBMC
  `Verified` unchecked. For the sound-verdicts loop, or a loop of its own; the user is deciding how to take it on.
- **Tracked in**: [`llm-dlc/loops/sound-verdicts.md`](../llm-dlc/loops/sound-verdicts.md#progress) (the entry of
  2026-11-06 on `vm-1`), with every disagreement; the logs in each job's `results/ID/logs/`.
- **Closes when**: both jobs, resubmitted unchanged after the fix, pass.
- **Rerun** 2026-11-07 on `vm-1`: jobs `20261107-172721-conformance-corpus-under-jbmc-and-engine` and `20261107-172721-conformance-corpus-under-engine-auto-con` (at `a1e29ec6a2e7`) both **failed**, for the same reason, none to do with the tests: their step is `cd lib && ... cargo test ... | tee target/conformance-*.log` with no `mkdir -p target`, and in a clean checkout `lib/target` does not exist when `tee` starts. The first job's log says `tee: target/conformance-jbmc.log: No such file or directory` and the step exited 1 although the test output shows `test result: ok. 2 passed; 0 failed`, 1236 s (so both corpus tests pass at this commit); the second was killed with SIGTERM after 22 s: not `tee`, but the runner's scope-name collision with its twin (the ids share 40 characters; see VF-021, fixed). A job that didn't pass doesn't close this entry. **Needs**: resubmit both with `mkdir -p target` before the pipe (as the jbmc-initializers job does), the cleanup loop's jbmc stream; the scope collision no longer applies. Closes then, if they pass.
- **Decided** by the user on 2026-11-07: resubmit both with `mkdir -p target &&` before the pipe, nothing else
  changed. The first job's "2 passed, 0 failed" is not taken as the check.
- **Resubmitted** 2026-11-07 as `20261107-222356-conformance-corpus-under-jbmc-and-engine` and
  `20261107-222356-conformance-corpus-under-engine-auto-con`, with `mkdir -p target &&` before the step's test
  command and nothing else changed. VF-001 closes when both pass.

### VF-013: the loops' run records are never published: they are gitignored, and unredacted

- **Status**: closed 2026-11-07, by `mmrwolwp` (`sync.py` publishes each record redacted under
  `llm-dlc/traces/<session>/runs/`, listed in the session's `summary.md`; `llm-dlc/tools/test_runs.py`, 8 tests, covers
  it) and `lrwynvul`, which published the records with `check` at 0 errors. On 2026-11-07, after the cleanup loop, all
  21 run records in `llm-dlc/loop-summaries/` had a published copy, `test_runs.py` passed and `check` gave 0 errors
  and 0 warnings. The two other files there, `cleanup-integration.md` and `foundations-integration.md`, are the
  integration scripts' notes, not `feature-loop.sh` run records, and are not published.
- **Raised**: 2026-11-07, while deleting the engine-priorities stream workspaces, whose 6 run records existed nowhere
  else (copied into `llm-dlc/loop-summaries/` first). Not a job failure.
- **Found**: `llm-dlc/tools/feature-loop.sh` writes a record of each run to `llm-dlc/loop-summaries/` (gitignored,
  `.gitignore:47`). It holds the start, cycle limit, session, model and effort, the brief's path and sha256, the
  instruction every cycle was given, a line per commit as it landed, the session's closing summary, and how the run
  ended. The summary is also the session's last turn (published, redacted, with its transcript), and the commits are in
  git. But nothing else records which commits belong to which run, or how and when each run stopped. The 7 records
  now are 7 to 18 KB each. Six of the seven hold unredacted local paths (the brief's path in the instruction and
  header), so removing them from `.gitignore` would publish them raw.
- **Needs** (option 1, chosen by the user): `sync.py` publishes each record redacted, beside the session it belongs to.
  - It reads the session id from the record's header.
  - It redacts the record with the same `Redactor` the transcripts use.
  - It writes the copy to `llm-dlc/traces/<session>/runs/<record>.md`, and links it from that session's `summary.md`
    (a list of runs: start, end, cycles, how it ended).
  - `check` scans the published copies like any other published file, and a finding in one is an error as for a log.
  - A record the loop is still writing (no `Ended` line yet) is republished as it grows, or held back until it ends.
  - Reproducer first: a test with made-up paths and a made-up session, which shows a record published unredacted, or
    not at all, before the change.
  - The redaction rules don't change, so no stamp is needed. `traces-readme-template.md` and `llm-dlc/README.md` say
    where the runs are.
  - The 7 existing records are published on the first `sync.py commit` after the change.
  - Option 2, R2 with the logs, was set aside: the records are small and are best read on GitHub next to the summary.
- **Tracked in**: `llm-dlc/loops/engine-priorities.md` (Progress, "Flagged for later").
- **Closes when**: `sync.py`'s tests cover it, and after a commit every record in `llm-dlc/loop-summaries/` has a
  redacted copy under its session's trace, linked from its summary, with `check` at 0 errors.

### VF-011: the own checker counts a loop's unwinding over the whole path, so example 052 is left to JBMC

- **Status**: closed 2026-11-07, by job `20261107-171502-vf-011-example-052-under-strict-on-the-o` (at
  `c6f34f8cb771`, `vm-1`, passed in 3m17s): 052 under strict on the own checker, with unwinding counted per entry of a
  loop, is established with no gap. The fix may turn other "not fully unwound" results into verdicts or timeouts;
  `lib/benchmark/results.json` was regenerated after it (2829 runs).
- **Raised**: 2026-11-07, from job `20261107-000039-the-41-recorded-jbmc-examples-under-stri` (at `98bab485`, `vm-1`) and
  the coverage inventory `examples/coverage.md` (commit `unvpruot`). Not a job failure.
- **Found**: under `--gaps strict`, obligation `052#0` is established by JBMC (with unwinding assertions at 16) and
  unresolved on the own checker: "a loop was not fully unwound with --unwind 16 (PropertyHarness.check at pc 238)".
  As read, not yet reproduced: `Engine::jump` in `lib/src/bmc/mod.rs` counts back edges per path and per
  `(class, method, target)`, and never resets the count when the loop is left. The property's `\max` over `k` of a
  `\sum` over `i < k` is two nested loops in the harness (`harness/expr.rs` compiles each quantifier as a loop), so over
  an array of length 8 one path takes the inner back edge up to 36 times. The count is incomplete, not unsound: a
  path cut short gives no verdict.
- **Needs**: a reproducer first (a nested loop whose inner loop runs fewer than the bound each time but more in total),
  then counting per entry of a loop. Ranked second among the own checker's extensions in `examples/coverage.md`.
- **Tracked in**: `examples/coverage.md` (extension 2), `llm-dlc/loops/engine-priorities.md` (Next, item 9).
- **Closes when**: a job runs 052 under strict on the own checker (`approach.engine` set to native in a copy) and it is
  established with no gap.

### VF-021: two of VF-010's benchmark jobs were killed by SIGTERM, with no output, and no verdict comparison across its fix was made

- **Status**: closed by job `20261107-184603-vf-010-s-benchmark-compared-the-own-chec` (at `df6b1c2e7e1e`, 2026-11-07, `vm-1`): the own checker's 557 runs at the fix and at its parent: 0 new, 0 gone, verdicts changed 0, formulas grown past 10% 0, paths or merges changed 0. The benchmark pair that fed it passed after the runner's scope-name fix.
- **Raised**: 2026-11-07 on `vm-1`. Jobs `20261107-165544-vf-010-s-benchmark-at-the-fix-run-1-of-2` (at `f606b0d80e31`, killed after 2m19s) and `20261107-165544-vf-010-s-benchmark-at-the-fix-s-parent-r` (at `c307e721bdc3`, after 0.2 s).
- **Found**: each step (`cargo build --release -q` then `python3 lib/benchmark/run.py --engines native --out ...`) ended with signal SIGTERM, not a timeout (`timedOut` false, not cancelled, no stop reason), peak 1.5 GiB and 574 MiB against 3 GiB limits, and no output file written. Three other jobs ran at the same time and finished normally (the VF-010 reproducer and integration tests at the fix, and example 109). Cause found (by the submitter, confirmed by me in `verification/pipeline.py`): the runner named each step's systemd scope `vjob-<id[:40]>-<step>`, and the two ids share their first 40 characters, so each job's step stopped the other's as a leftover of the same name. Fixed in the runner: the scope name is now the first 30 characters of the id and a hash of the whole id (`scope_id`). The same collision stopped job `20261107-172721-conformance-corpus-under-engine-auto-con` (VF-001) beside its twin.
- **Seen again, resolved in part** 2026-11-07 on `vm-1`: the resubmitted pair `20261107-183538-vf-010-s-benchmark-at-the-fix-run-1-of-2` (at `f606b0d80e31`) and `20261107-183544-vf-010-s-benchmark-at-the-fix-s-parent-r` (at `c307e721bdc3`), with ids that differ early, both passed (3m11s each) and their outputs are applied.
- **Needs**: the submitter (cleanup loop's native stream) queues the comparison job on the two outputs.
- **Tracked in**: [`llm-dlc/loops/cleanup-native.md`](../llm-dlc/loops/cleanup-native.md) (N1).
- **Closes when**: the two benchmark jobs pass and the comparison shows no recorded own-checker verdict changed with the fix.

### VF-014: H1's benchmark comparison fails on 8 verdicts that changed because `lib/benchmark/results.json` is stale, not because of symbolic references

- **Status**: closed by job `20261107-183328-vf-014-h1-isolated-run-3-of-3-the-benchm` (at `7315cda22a96`, 2026-11-07, `vm-1`): the comparison of H1's own-checker verdicts with H1's parent's passed (0.2 s): 'verdicts changed: 0', the only new runs the 24 of the swaps cases H1 added. The stale `results.json` was the cause, not H1.
- **Raised**: 2026-11-07 on `vm-1` (run with `--memory 8G --workers 2`). Job
  `20261107-041414-symbolic-references-in-the-own-checker-h` at `73c514ad00a7`: step 1 (the whole benchmark on the own
  checker, 557 runs) passed; step 2 (compare with job `20261106-201041`) exited 1.
- **Found**: 8 own-checker verdicts differ from `lib/benchmark/results.json`, all on three conformance cases whose
  recorded verdict was `unverifiable` because of a class-initializer gap: `boom/1` (strict, advised: unverifiable ->
  violation; assume: verified -> violation), `inherited/1` (same three), `quiet/1` (strict, advised: unverifiable ->
  verified). The same cases account for the 4 "clauses grown" (1 -> 230) and the 3 "paths or merges changed" (paths
  None -> 1, merges None -> 0): the recorded runs stopped at the gap and solved nothing. 201 runs are "new" (cases the
  recording predates). The new verdicts agree with JBMC's recorded ones (`boom` violation, `quiet` verified). This reads
  as the own checker having gained class initializers since the recording, not as an effect of H1, but the job does
  not isolate the two: no run in the recording exercises a merge of different references, so H1's "same run as before"
  claim is untested by it, apart from the absence of any other changed run. I did not verify the class-initializer
  attribution against the git history of `lib/src/bmc/`.
- **Needs**: the foundations-heap loop (or whoever owns `lib/benchmark/results.json`) regenerates the recording on the
  current engine, so that the reference includes the 201 new runs and the class-initializer verdicts, then resubmits
  unchanged (`pipeline.py resubmit 20261107-041414-symbolic-references-in-the-own-checker-h`). Alternatively compare
  against a run at H1's parent commit, which isolates H1.
- **Tracked in**: `llm-dlc/loops/foundations-heap.md` step H1 (not yet updated).
- **Closes when**: the resubmitted job passes against a recording made at a commit without H1, or H1's parent.
- **Isolated runs** 2026-11-07 on `vm-1`: jobs `20261107-164450-vf-014-h1-isolated-run-1-of-2-the-benchm` (at H1's parent `b927e5df1be9`) and `-run-2-of-2-` (at H1 `ddbb54bac206`) both passed in 2m42s and 2m45s. Their outputs (`lib/target/benchmark-native.json`) stay in each job's `outputs/` and were not applied to the working copy (the files differ from the jobs' commits). The comparison job the descriptions name is the submitter's to queue; the entry stays open until it passes.
- **Closed** 2026-11-07 on `vm-1`, by the job above, run after runs 1 and 2 (`20261107-164450-…`) passed.
- **Fresh benchmark** 2026-11-07 on `vm-1`: job `20261107-183709-vf-014-a-fresh-lib-benchmark-results-jso` (at `c9995ae17d82`) passed in 1h37m (peak 6.0 GiB against an estimate of 4.5): no false success or alarm on any engine, mode or staging policy. `lib/benchmark/results.json` and `RESULTS.md` were replaced by collect (applied, no conflicts), so the stale file is gone.

### VF-019: under `auto --confirm`, the six nullable and may-alias claims of H2 get "no engine wrote a harness", which the conformance test counts as a disagreement

- **Status**: closed by job `20261107-172721-nullable-and-one-array-parameters-in-pro` (at `a1e29ec6a2e7`, 2026-11-07, `vm-1`): both ignored conformance tests passed.
- **Raised**: 2026-11-07 on `vm-1`. Job `20261107-043420-nullable-and-one-array-parameters-in-pro` at `d404b15cbac6`
  (heap stream, H2's first step).
  - Step 1's `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` passed.
  - `the_corpus_agrees_with_the_jvm_under_auto_confirm` (`tests/conformance.rs:859`) failed with 20 disagreements.
- **Found**: 84 cases, 166 claims, 332 runs. The 20 disagreements are of two kinds:
  - **8 are VF-009's**: `boomTwice` and `enumBroken` at `n=0`, under strict and assume, unchanged.
  - **12 are new**: the six claims H2 widened, under `--gaps Strict` and `Assume`, each reported as "no engine wrote
    a harness". The claims are `twoArrays` with `may alias a,b` (two claims), `length` with `nullable a` (two), and
    `lengthOrMinusOne` with `nullable a` (two).

  The job's description expected these six to be refused under JBMC and `--confirm` (JBMC can't take a nullable or
  aliased input). So the refusal happens, but `--confirm` reports it as no harness at all, not as a named refusal,
  and the test counts it as a disagreement with the JVM. Not yet read in the code: whether `--confirm` refuses with
  a reason, or fails to make a harness and says nothing.
- **Needs**: `--confirm` refuses these with a named reason (an unverifiable result naming the input JBMC can't
  take). The test then reads a named refusal as no verdict, not a disagreement, as the heap stream's rule says:
  "`--confirm` refuses rather than confirming a different claim". This must not weaken the test: an unnamed "no
  harness" stays a failure. For the cleanup loop's jbmc stream, with VF-009, since the same test closes both.
- **Tracked in**: [`llm-dlc/loops/cleanup-jbmc.md`](../llm-dlc/loops/cleanup-jbmc.md) (J1).
- **Closes when**: job `20261107-043420-nullable-and-one-array-parameters-in-pro`, resubmitted unchanged at a fixing
  commit, passes.
- **Closed** 2026-11-07 on `vm-1`: job `20261107-172721-nullable-and-one-array-parameters-in-pro` (at `a1e29ec6a2e7`), the same job resubmitted after VF-009's fix, passed: both ignored conformance tests, `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` and `the_corpus_agrees_with_the_jvm_under_auto_confirm`, in 1236 s. The six claims read as refused by name, no verdict, as the job expected.

### VF-017: examples 150, 151 and 152 fail on the result schema, which has no `object` parameter kind

- **Status**: closed by jobs `20261107-164043-example-150-crosscut-retry-throttle-a-re`, `-151-` and `-152-` (at
  `e7270fd85890`, 2026-11-07, `vm-1`): each passed in about 6 s with `example:as-expected`, 5 outputs applied each.
  The schema fix landed, and the three results are recorded.
- **Raised**: 2026-11-07 on `vm-1`. Jobs `20261107-064330-example-150-crosscut-retry-throttle-a-re`,
  `20261107-064331-example-151-…` and `20261107-064331-example-152-…`, at `224431e7bb68` (heap stream).
- **Found**: each fails within 5 s, after `jvmcontract equivalence` exits 0, as `build.py` validates the result:
  `result.json: 'object' is not one of ['primitive', 'array', 'record']`. The path in the schema is
  `$defs/statement/properties/domain/properties/parameters/items/properties/kind` in
  `examples/schema/result.schema.json`. It is unchanged at `main` (`34e1d87b`), so the three examples can't be
  recorded there either. H2's object parameters write `kind: object`, and the schema was never extended for them.
- **Needs**: the schema allows `object`, with whatever else an object parameter's domain entry carries (its
  constructor, nullability, aliasing: check the statement jvmcontract writes). Then a `test_build.py` case
  validating such a result. For the cleanup loop's examples stream.
- **Tracked in**: [`llm-dlc/loops/cleanup-examples.md`](../llm-dlc/loops/cleanup-examples.md) (E1).
- **Closes when**: the three jobs, resubmitted after the fix, pass with each example's expected verdict: 150
  verified; 151 a violation differing only in `result == throttle`; 152 verified within the constructor-made domain.

### VF-016: examples 160 and 161 fail before any proof: their subject is a caller the patch doesn't change

- **Status**: closed by jobs `20261107-165152-example-160-a-changed-refill-helper-prov` and `20261107-165153-example-161-a-refill-helper-aligned-to-t` (at `35a9ea8fadaa`, 2026-11-07, `vm-1`): both passed as expected.
- **Raised**: 2026-11-07 on `vm-1`. Jobs `20261107-053635-example-160-a-changed-refill-helper-prov` and
  `20261107-053635-example-161-a-refill-helper-aligned-to-t`, at `85ee8db14dfb` (summaries stream).
- **Found**: each fails in 0.2 s with "the patch does not change the subject file
  examples/apps/crosscut/src/main/java/net/terminalvalue/crosscut/ratelimit/RetryAfter.java"
  (`examples/tools/build.py:3523`). The examples are about a changed helper, `TokenBucket`, proved on its own and
  then used in its caller's proof. So the subject (`RetryAfter#nanosUntilToken`) is the caller, and the patch only
  touches `TokenBucket.java`. The check is the same one VF-002 trips on, for another reason: there the patch creates
  the subject, here it leaves it alone.
- **Needs**: `build.py` takes a subject the patch doesn't change, when the change is in the subject's code closure.
  Its excerpts then show the changed file. Or the examples name the helper's file and keep the caller as the
  symbol. For the cleanup loop's examples stream, with VF-002.
- **Tracked in**: [`llm-dlc/loops/cleanup-examples.md`](../llm-dlc/loops/cleanup-examples.md) (E1).
- **Closes when**: both jobs, resubmitted after the fix, pass with their expected verdicts: 160 verified with
  `lastAfter` shared, 161 a violation with no helper shared.
- **Seen again** 2026-11-07 on `vm-1`, in jobs `20261107-163050-example-160-a-changed-refill-helper-prov` and
  `20261107-163051-example-161-a-refill-helper-aligned-to-t` (at `d32ddc64d1a4`, resubmitted by the cleanup loop's
  examples stream). The subject check is fixed: the patch applies, the crosscut tests run, and `jvmcontract
  equivalence` runs (0.4 s; it exited 0 for 160 and 1 for 161, which for 161 is the expected violation). Both then
  fail in `build.py` after the proof, validating the result: `result.json: Additional properties are not allowed
  ('proofCache' was unexpected)`. `claim_scope` (`examples/tools/build.py:795`, from `85ee8db`) writes
  `scope.proofCache` for a B9 proof with the proof cache, but `examples/schema/result.schema.json` (statement's
  `scope`, around line 1161) doesn't list it, and is unchanged at the current `main`. **Needs**: the schema allows
  `proofCache` in a claim's scope, with a `test_build.py` case validating such a result; the cleanup loop's examples
  stream. Then resubmit both jobs unchanged.
- **Closed** 2026-11-07 on `vm-1`: jobs `20261107-165152-example-160-a-changed-refill-helper-prov` and `20261107-165153-example-161-a-refill-helper-aligned-to-t` (at `35a9ea8fadaa`) passed in 7 s each, 160 verified and 161 a violation, both `as expected`; the schema now accepts `proofCache`. Results applied.

### VF-010: the own checker's regression proof of `Pricing#total` sometimes runs out of time: its branch probes depend on wall-clock time

- **Status**: closed by jobs `20261107-165544-vf-010-s-reproducer-at-the-fix-pricing-t` and `20261107-165544-vf-010-s-integration-tests-at-the-fix-li` (at `f606b0d80e31`, 2026-11-07, `vm-1`): 8 of 8 alike, 64 integration tests passed. The verdict comparison is still to do (VF-021).
- **Raised**: 2026-11-06 on cvm, inline, while triaging job `20261106-203452`; seen again in full inline suite runs on
  2026-11-06 and 2026-11-07 (commits `xrrxwxny`, `vrkpmtqv`, `pkuyvwwp`).
- **Found**: `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` (`lib/tests/integration.rs`) fails now and then
  on the own checker's regression proof of `fixtures.Pricing#total` (the rounding refactor) and passes alone. Of 8
  identical runs of `jvmcontract equivalence --target 'fixtures.Pricing#total' --engine native --timeout 40`, 6 found
  the violation in about 4 s (13 solver calls, 2 of 2 divisions built in full) and 2 ran out of time at the 8th solver
  call (0 of 2 built). As read: the branch probes (`bmc/mod.rs`, `probe`) are given as long as the solver calls so far
  took, at least a second, so which side of a branch is left undecided, and with it the path order and the queries,
  depends on the machine's speed. One order leaves a query that doesn't finish.
- **Needs**: probe budgets that don't depend on wall-clock time (a count of conflicts or of solver calls, say), with
  the 8-run reproducer above showing every run alike.
- **Tracked in**: `llm-dlc/loops/engine-priorities-jbmc.md` (step 3's notes), `llm-dlc/loops/engine-priorities.md` (Next,
  item 8).
- **Closes when**: the reproducer gives the same answer in 8 of 8 runs, and a job runs the integration tests with no
  failure.
- **Reproducer before the fix, 2026-11-07 on `vm-1`** (28 CPUs, x86_64), job
  `20261107-163057-vf-010-s-reproducer-before-the-fix-prici` at `c307e721bdc3`: it did **not** reproduce here. All 8
  runs found the violation in 3.1 to 4.8 s with identical numbers (5 paths, 13 solver calls, 120989 variables, 412482
  clauses). The job's step exits 1 when all 8 agree, which it expected to be the other way round, so the job is
  recorded as failed; it is not a verdict on any code. So `vm-1` can't show the problem before the fix, and so can't
  show it gone after: the 2 of 8 runs that timed out were on `cvm` (a slower machine). Whoever fixes it should check
  the fix by the probe budget no longer reading the clock (a code check, or a count of solver calls that is the same
  across the runs), and run the reproducer on `cvm` for the before/after.
- **Closed** 2026-11-07 on `vm-1`: at the fix (`f606b0d80e31`) job `20261107-165544-vf-010-s-reproducer-at-the-fix-pricing-t` passed (8 of 8 runs found the violation, 3.1 s each, the same numbers every time: 6 paths, 12 solver calls) and `20261107-165544-vf-010-s-integration-tests-at-the-fix-li` passed (64 passed, 0 failed). Caveat: `vm-1` did not reproduce the problem before the fix either (see above), so this shows the fix is stable and breaks nothing, not that it cures the timeouts seen on `cvm`. The benchmark pair that compares recorded verdicts across the fix did not run: both jobs were killed by SIGTERM (VF-021).

### VF-009: `auto --confirm` disagrees with the JVM on `boomTwice` and `enumBroken`: JBMC's refutation at `n=0` is spurious, the own checker is right

- **Status**: closed by job `20261107-172721-jbmc-s-extra-initializers-named-and-refu` (at `a1e29ec6a2e7`, 2026-11-07, `vm-1`): the `auto --confirm` and JBMC corpus tests passed.
- **Raised**: 2026-11-07 on `vm-1`. Job `20261107-010728-jbmc-s-extra-initializers-named-and-refu` (at `254f1d7a4893`), step 2 (steps 1 and 3 passed: the corpus under JBMC and auto, and the draft report's example).
- **Found**: `the_corpus_agrees_with_the_jvm_under_auto_confirm` (tests/conformance.rs:792) has 8 disagreements, all on
  `boomTwice [assert result == 2]` and `enumBroken [assert result == 12]`, under `--gaps Strict` and `Assume`: Auto
  reports a violation at `n=0` that the JVM does not reproduce (the interpreter gives 2 and 12, the harness holds), and
  `--confirm` says the engines disagree: the own checker proves the property on every input and JBMC 6.11.0 refutes it
  on `n=0`. The same shape as VF-007 (closed by job `20261106-231317`) but on methods that run an exception handler
  twice and an enum initializer; the job's change (extra initializers named and refused in the preflight) did not
  cover them. Step 3's JBMC output ("1 of 13 failed") is the expected violation of that example.
- **Needs**: the engine-priorities-jbmc loop: why JBMC refutes `boomTwice(n=0)` and `enumBroken(n=0)` (a class
  initializer JBMC runs that the JVM does not? the `--throw-runtime-exceptions` path?), and refuse or model it.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md). Deferred by
  the user on 2026-11-07, untriaged, until after the foundations loop; a candidate for the draft brief
  [`llm-dlc/loops/jbmc-upstream.md`](../llm-dlc/loops/jbmc-upstream.md) if JBMC's handling of a throwing initializer
  turns out to be the cause. Both methods are cases the engines-native stream added in Phase 5, step 3 (`ulstzomt`):
  the rest of that stream's cases agree with the JVM under JBMC and `auto` (jobs `20261107-012013`, `20261107-022319`),
  so this finding is all that is left of the engine-priorities brief's "conformance job for the native stream's step 3
  cases" (Next, item 8).
- **Closes when**: the same job, resubmitted unchanged at a fixing commit, has step 2 pass.
- **Triage run** 2026-11-07 on `vm-1`: job `20261107-163056-vf-009-triage-a-class-initializer-that-t` (at
  `2c352d909f21`, passed, 2m25s; it is evidence, it closes nothing). Step 1, the fixture
  `lib/tests/fixtures/jbmc-defects/F.java`: on the JVM `java -ea` prints `all hold, runs 4`. Stock JBMC 6.11.0 gives
  `VERIFICATION FAILED` on `wrapped`, `erroneous`, `once`, `enumWrapped`, `boomTwice` and `enumBroken`, and
  `VERIFICATION SUCCESSFUL` on `error`, alike with no flags, with `--throw-runtime-exceptions`, and with the flags
  jvmcontract passes. So the hypothesis holds: the divergence is in JBMC, not in jvmcontract's adapter. JBMC doesn't
  wrap a throw in a class initializer in `ExceptionInInitializerError` and doesn't mark the class erroneous
  (`NoClassDefFoundError` at its next use). Step 2, the corpus's two methods through `jvmcontract prove`: under
  `--engine jbmc` and `auto --confirm` both report a counterexample at `n=0` that "does not reproduce" in the
  interpreter, and `--confirm` reports the engines disagreeing, as in the entry. The log has the goto listings and each
  run's work directory. **Needs** (now more specific): refuse a target whose reachable code runs a class
  initializer that can throw (the preflight), or model the wrapping; a candidate for `jbmc-upstream.md`.
- **Seen again** 2026-11-07, unchanged (the same 8 disagreements), in job
  `20261107-043420-nullable-and-one-array-parameters-in-pro`, beside VF-019's 12. Taken by the cleanup loop's jbmc
  stream ([`cleanup-jbmc.md`](../llm-dlc/loops/cleanup-jbmc.md), J1).
- **Closed** 2026-11-07 on `vm-1`: job `20261107-172721-jbmc-s-extra-initializers-named-and-refu` (at `a1e29ec6a2e7`) passed all 3 steps: `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` and `the_corpus_agrees_with_the_jvm_under_auto_confirm` both ok, and the draft report's example gives JBMC's two failures. The resubmitted VF-019 job passed `auto_confirm` as well. A guard job, `20261107-171442-vf-009-s-guard-measured-the-41-recorded` (3 steps passed), shows the fix costs no recorded JBMC example: step 1 is as in `-000039` (only 037 differs, a JBMC defect), and no throwing-initializer line appears.

### VF-012: the own checker raises a false alarm on `conformance/leadingZerosLong/2`, so the benchmark step exits 1 and the encoding-timing check never ran

- **Status**: closed by job `20261107-033320-the-own-checker-s-encoding-timed-whole-p` (at `dc03b87fb961`, `vm-1`, 2026-11-07): both steps passed, so no false alarm and the timing comparison ran and passed
- **Raised**: 2026-11-07 on `vm-1` (run with `--memory 7G --workers 3`). Job
  `20261107-032249-the-own-checker-s-encoding-timed-whole-p` at `58b89dd9ce1c`.
- **Found**: step 1 (`lib/benchmark/run.py --engines native`) ran all 533 own-checker runs in 143 s and exited 1,
  because three runs are classed `false-alarm`: `conformance/leadingZerosLong/2` under strict, assume and advised. The
  own checker reports `violation` with witness `48` in 0.04 s (610 variables, 2114 clauses), and the JVM replay says
  `witnessOnTheJvm: holds`, i.e. the witness is spurious. The case is not in the committed `lib/benchmark/results.json`
  (new since that run, probably from the numberOfLeadingZeros change), so this is not a regression of the encoding
  timing. Step 2 (no run flagged `phasesExcess`; median seconds ratio against job `20261106-201041` at most 1.10) was
  skipped. Read from the saved JSON in the work directory: 0 of 533 runs carry `phasesExcess`, which is promising but
  is not the check the job names, and the ratio was not computed. No other reference disagreement.
- **Needs**: whoever owns the `Long.numberOfLeadingZeros` modelling in the own checker (the engine-priorities loop)
  fixes the encoding behind case `leadingZerosLong/2` or marks the case as expected-unsupported; then the job is
  resubmitted unchanged (`pipeline.py resubmit 20261107-032249-the-own-checker-s-encoding-timed-whole-p`).
- **Update 2026-11-07 (cause found, fixed in the benchmark runner)**: the own checker's witness is right, and the JVM
  replay misread it. Run inline, `jvmcontract prove ... 'conformance.Conformance#leadingZerosLong' --assert
  'result < 64' --engine native --gaps strict` reports `leadingZerosLong(arg0=0)`, outcome 64, which the JVM bears out.
  The tool writes a `long` input as a decimal string (`"0"`), and `lib/benchmark/run.py`'s `token()` took any
  one-character string for a `char` and passed its code unit: `ord('0')`, 48, where `numberOfLeadingZeros(48)` is 58.
  Every single-digit `long`, `float` or `double` witness, alone or in an array, was misread that way. This case is the
  first in the corpus whose witness is one. `witness_arguments` now reads an input as a `char` only if its declared
  type is one. `test_a_long_or_a_double_witness_of_one_digit_is_its_value_not_a_char` failed before the fix
  (`48;[48,-2,55];53`) and passes after it. Step 2's check run by hand on the job's saved
  `lib/target/benchmark-native.json`: 0 of 533 runs flagged, median ratio 0.963 (quartiles 0.871 to 1.006) over the 29
  runs of 0.1 s or more, 31.5 s against 32.0 s over the 356 paired runs. Resubmitted unchanged.
- **Tracked in**: the job's `logs/1-benchmark-own-checker-only.log`.
- **Closes when**: the resubmitted job passes (no false alarm, no `phasesExcess`, median ratio at most 1.10).
- **Result**: 533 own-checker runs, 0 flagged `phasesExcess` (reference job: 1 of 356); median seconds ratio 0.974 over 29 runs of 0.1 s or more (quartiles 0.872 to 1.002).

### VF-008: the conformance corpus under JBMC and auto: JBMC says `Verified` on `declaring`, which the JVM refutes

- **Status**: closed by job `20261107-012013-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `8b45798e6417`, 2026-11-07, `vm-1`): step 5 ran `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` and it passed (646 s). Not the same job resubmitted, but the same test.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 6.
- **Found**: `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` (tests/conformance.rs:749) reports 1 disagreement out of
  73 cases: `declaring [assert result == n + 107]`, `--gaps strict` on JBMC says Verified ("2 properties proved over
  n: int in 0.2 s; loops unwound 16 times with unwinding assertions") and the JVM refutes it. This is the unsoundness
  VF-001 describes, now on a case the strict policy was meant to cover.
- **Needs**: the engine-priorities-jbmc loop (or whoever owns the JBMC staging policy) to find why strict lets this
  proof through (a model or exception path unmodelled?), and add the case to the brief's Progress.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md); see also VF-001.
- **Closes when**: the same job, resubmitted unchanged at a fixing commit, has step 6 pass.

### VF-005: example 071 under strict: the first two proofs are `unverifiable` on JDK 25.0.5 where the job expects `verified` with no gap

- **Status**: closed by job `20261107-024759-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `854a0d8f756e`, 2026-11-07, `vm-1`): step 3, `071: the first two proofs stand with no gap`, passed, with obligations 0 and 1 verified and no gaps (the `Collection` stubs reached by JBMC's call graph and never entered), after the preflight's index fix (`xmslpytz`). Not the same job resubmitted, but the same assertion.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 3 (steps 1, 2, 4 and 5 passed: 013 under strict, and the contract library recorded on this JDK).
- **Found**: the assertion that obligations 0 and 1 of example 071's result are `verified` with no gaps fails: they are
  `unverifiable` with gaps `jdk-reference-method:java.util.Collection.toArray()...@jdk-25.0.5` and
  `jdk-primitive-method:java.util.Collection.isEmpty()Z@jdk-25.0.5`. Step 2 ran the example's own build as expected,
  so the example stands and the expectation about the models (Enum and List) is what does not hold: the models were
  not enough on JDK 25.0.5, or the recorded library does not cover `Collection`. (The 41-example job saw 071#0 and 071#1 unresolved on `Enum.<init>`/`List.of`, a different gap set.)
- **Update 2026-11-07**: job `20261107-012013-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `8b45798e6417`, `vm-1`) step 3 fails
  in a new way: the stubs on no path are now named as "no gaps" in the output (`note: JBMC's call graph reaches 2 stubs
  ... never enters ... no gaps: Collection.isEmpty(), Collection.toArray()`), but obligations 0 and 1 are still
  `unverifiable` with an empty gap list, where the job expects `verified`. Steps 2 (071 build), 4 (013 under strict) and 5 (corpus) passed.
  So the gap is gone and the verdict is not: something else in the strict path still withholds the proof.
- **Needs**: the submitter to say whether the `Collection` methods should be modelled or the expectation relaxed, and
  why an obligation with no gaps is `unverifiable` (see the verifier-output.txt of the job's 071 output).
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted unchanged at a commit that fixes it, passes step 3.

### VF-007: engine-priorities step 3: escaping exceptions: `auto --confirm` disagrees with the JVM on 12 claims, and an integration test times out

- **Status**: closed by job `20261106-231317-jbmc-s-defects-under-confirm-the-unmaske` (at `14607996bdca`, 2026-11-06, `vm-1`): the same three commands as `20261106-203452`, all three steps passed (33m53s, peak 1.3 GiB). The `Pricing#total` timeout did not recur.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203452-jbmc-s-escaping-exceptions-named-and-ref` (at `ffb68ef59525`), steps 1 and 3. Step 2 (corpus under JBMC and auto) passed.
- **Found**: step 3 (`the_corpus_agrees_with_the_jvm_under_auto_confirm`, tests/conformance.rs:689) has 12
  disagreements, all on methods that catch an exception (`caught`, `caughtAsRuntime`, `nestedHandler`, with `n=0`):
  Auto under `--gaps Strict` and `Assume` reports a violation the JVM does not reproduce (the harness holds), and
  `--confirm` says the engines disagree: the tool's own checker proves `n != 0 || result == -1` and JBMC refutes it on
  `n=0`, while the interpreter gives -1. So JBMC's counterexample is spurious on caught exceptions (not the checker).
  Step 1: integration test `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` (tests/integration.rs:1431) got
  Unverifiable ("the solver did not finish within the time limit") for `fixtures.Pricing#total`, expected Violation;
  62 other tests passed (703 s). That one may be a time limit on a 2 CPU job rather than a logic fault: not rerun to tell.
- **Needs**: the engine-priorities-jbmc loop: fix the handling of caught exceptions in the JBMC path, and decide whether
  the `Pricing#total` test needs a larger solver limit or a fixed expectation.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md).
- **Closes when**: the same job, resubmitted unchanged, passes all three steps.

### VF-006: engine-priorities step 4a: the 41-example gap-table job fails on a schema error, so no table exists

- **Status**: closed by job `20261107-000039-the-41-recorded-jbmc-examples-under-stri` (at `98bab48570e6`, 2026-11-07, `vm-1`): all three steps passed (4m22s, peak 1.1 GiB); 41 examples, 43 obligations in the table on both engines. 5 of 43 obligations differ in status between jbmc and native (013#0, 035#0, 052#0, 071#2, 127#0), as the brief wanted listed; 6 native obligations have no verdict at a gap (013#0, 037#0, 071#0, 071#1, 071#2, 127#0), and 037#0 is refused at a JBMC defect. Those are results for step 4a, not failures of the job.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-204220-the-41-recorded-jbmc-examples-under-stri` (at `61f5e48d1abf`).
- **Found**: steps 1 and 2 stop at "result.json: Additional properties are not allowed ('sat' was unexpected)" on
  example 013, in the result schema check of `build.py`'s attempt. Only 9 of the 41 examples reached the table (32 skipped as "not format 2"), so step 3's assertion `9 examples in the table, not 41` also fails. The same schema complaint ('newProblems' unexpected) is in older B12 results, so the result schema may lag the writer.
- **Update 2026-11-06**: rerun `20261106-231837-the-41-recorded-jbmc-examples-under-stri` (at `835d5f28cbfd`, `vm-1`) fails again in a new way: step 2 (own checker) exits 1 at "result.json: Additional properties are not allowed ('phasesExcess' was unexpected)" on a `jvmcontract prove` attempt (attempt 018), so `sat` is fixed but the schema still lags the writer on another field. Steps 1 passed. Only 12 of 41 examples reach the table (29 skipped as "not format 2"), so step 3 again fails with `12 examples in the table, not 41`. Example 013 differs from its expected verdict (013#0 unresolved on `TermOrder.<clinit>`); 071#0 and 071#1 are unresolved on `Enum.<init>`, `List.copyOf`, `List.of` (see VF-005).
- **Needs**: the submitter (engine-priorities step 4a): add `sat` and `phasesExcess` to the result schema (or stop writing them; check every field the writer emits against it), check that the 41 examples carry format-2 results with gaps recorded, then resubmit.
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted, passes with 41 examples in the table.

### VF-004: the CBMC 6.11.0 source-reading job's grep for `run_property_decider` matches nothing

- **Status**: closed (job `20261106-194328-cbmc-6-11-0-s-source-times-runtime-post`, passed 2026-11-06 at `3feadaf0f7a2`: the corrected grep matched and all three checks found their strings)
- **Raised**: 2026-11-06 on `vm-1` (run with `--memory 8G --workers 2`). Job
  `20261106-192959-cbmc-6-11-0-s-source-times-runtime-post` at `b4c0164b852f`.
- **Found**: both files download (sha256 in the log) and step 1 prints the `== bmc_util.cpp: run_property_decider`
  header, then exits 1 after 0.4 s with no further output. Under `set -euo pipefail` the next command,
  `grep -n -A45 "^decision_proceduret::resultt run_property_decider" bmc_util.cpp`, matched nothing: that return type
  and line layout is not how 6.11.0 declares the function (likely a different return type or the name on its own line
  after the type). So the job never reached the `Runtime Solver` / `Runtime Post-process` / `finish_eager_conversion`
  checks. This is a defect in the job's step, not a finding about CBMC. I did not edit the step.
- **Needs**: the submitter resubmits with a pattern that matches (for instance `grep -n -B2 -A45 "run_property_decider("`),
  or drops the `-n -A` display and keeps the three `grep -q` checks.
- **Tracked in**: the job's `logs/1-fetch-and-show-cbmc-6-11-0-s-s.log`.
- **Closes when**: the corrected job passes.

### VF-003: Bitwuzla 0.8.2 builds but the installed binary cannot load `libcadical.so`

- **Status**: closed (job `20261106-194049-bitwuzla-0-8-2-built-from-source-cadical`, passed 2026-11-06 at `66dd857b6891`: CaDiCaL linked static, `bitwuzla --version` 0.8.2, three smoke queries gave the expected sat/unsat, C API through pkg-config works)
- **Raised**: 2026-11-06 on this 24-CPU host (run with `--memory 8G --workers 2`). Job
  `20261106-192008-bitwuzla-0-8-2-built-from-source-for-the` at `3853fcc7e8b7`.
- **Found**: `lib/solvers/bitwuzla/build.sh 0.8.2` downloads, compiles (217 targets, 24 s, peak 1.9 GiB) and installs into
  `~/tools/bitwuzla/bitwuzla-0.8.2`, then its check exits 127: `bitwuzla: error while loading shared libraries:
  libcadical.so: cannot open shared object file`. The shared-library build links CaDiCaL as a shared subproject, but
  no `libcadical.so` exists anywhere under `~/tools/bitwuzla`: meson did not install it (or no rpath points at it).
  Deterministic; not a resource problem. The partial install is left in place.
- **Needs**: whoever owns the solver comparison fixes `build.sh`: install CaDiCaL's library into the prefix with an
  rpath, or build CaDiCaL static, and check with `ldd` before the version smoke test.
- **Tracked in**: the job's `logs/1-build-bitwuzla-0-8-2.log`.
- **Closes when**: the job, resubmitted after the fix, passes.

None yet.
