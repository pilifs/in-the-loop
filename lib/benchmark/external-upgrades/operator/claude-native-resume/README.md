# Claude NativeResume operator

**Native `--resume` preserved each authenticated first-party role’s complete prior tool result.** Fable and Opus each ran the public synthetic consumer on both revisions through the real case-only MCP. On a second payable request each recalled its own fresh nonce and both integers (`42`, `42`) without another tool call. No role returned the other nonce. All four native requests ran at high effort within their individual $0.75 and 120-second limits. The total client estimate was $0.0550996. [Live first-party receipt](evidence/live-resume.json) · [Shared operator profile](claude-native-resume.json) · [V0 build launch](v0-launch.json)

| Model | Initial wall time | Resumed wall time | Initial estimated cost | Resumed estimated cost |
| --- | ---: | ---: | ---: | ---: |
| Fable 5.2 | 3.070 s | 2.783 s | $0.0108052 | $0.0280840 |
| Opus 5.5 | 4.011 s | 2.209 s | $0.0054216 | $0.0107888 |

## History, tools and limits

The planner, each independent reviewer, the setup role and the proof role each has its own trusted case-private configuration folder and persistent native session UUID. An initial request uses `--session-id`. Later requests in that role use `--resume` with the exact same UUID. The first-party application looks up its ordinary login separately in its secure credential store. Neither the real case command nor the uncredentialed measurement namespace has access to that store. Cross-stage handoffs still use the approved plan, review decision and verification artifacts. A fresh independent reviewer gets only the released pair, its dependencies and the proposed plan. [Synthetic storage and decoy checks](evidence/synthetic-resume.json)

Before **each** payable request the controller gives a separate private network namespace a copy of only that role’s current case transcript and any of its own tool-result files. The installed client reconstructs the complete request against a loopback-only synthetic endpoint with a fabricated key and an empty secure store. The shadow checks the session identity, model, high effort, single registered case command, prior assistant history, previous visible tool/assistant value, and previous tool-result ID where applicable. The original transcript is hashed before and after measurement. The role’s sources and transcript never enter another case’s meter. [Scheduler context receipt](evidence/scheduler-shadow.json)

The controller reserves the full, uncompressed native request size in bytes plus an 8,192-token metadata/framing allowance and a maximum of 2,048 generated tokens. It settles the reservation with the native client's measured uncached input (including cache creation) and output, including reasoning. Cache reads are recorded separately. A missing usage receipt retains the reservation and stops the case. The shared limit is 250,000 tokens. The complete intake window, including queue and local measurement, is two hours. The runner retains the 900-second checkpoint, 15-minute human allowance, 4-vCPU and 16-GiB limits, and the original scorecard seal. Large retained contexts can stop before the numerical ceiling when the next full reservation cannot fit.

The native conversation is continuous within a role. The process and MCP connection restart after each authorized model request, automatic compaction is disabled, and a different role sees a distinct conversation. Those differences, the cost of measuring each retained context, and conservative reservation headroom remain relevant to comparisons with an uninterrupted team session. The implementation labels the scheduler explicitly and retains the first model-submitted text for grading even if the output gate later fails. [Case scheduler](run_case.py) · [Meter](resume_meter.py)

## Pairing two builds

Each report carries the same `profile_sha256` across products. The profile covers the model IDs, stage prompts, governor, role storage and isolated meter. The build-specific `launch_lock_sha256` binds the tested revision, complete staged tree (`staged_root_sha256`), original engine lock (`product_sha256`) and expected execution environment. The measured `environment_sha256` covers the kernel release and architecture, Bubblewrap binary and isolation policy, actual cgroup limits, case JDK, guest OS files and their modes. The tool-root projection excludes the product workflow and embedded lock, checker, and solver executables/libraries. Every report seals the launch file and the complete matched-environment manifest as evidence. The native context meter is an independent control image containing no tested product or solver bytes. [Identity implementation](identity.py)

Generate a prospective second build lock with `python3 "$op/identity.py" --build V1 --product "$STAGED_NEW_BUILD" --output "$NEW_LAUNCH"` and supply both `--launch-lock "$NEW_LAUNCH"` and its independently published `--launch-sha256` to the same scheduler. The release authority must bind the new product lock in the signed transfer declaration. The default launch file binds V0. [Qualification receipts](qualification.json)

## Run a separately admitted case

Prepare two immutable roots from the existing V0 tool root. The case JDK launchers pass `-Djava.io.tmpdir=/case/work/tmp`, or the `-J-D...` equivalent for the compiler and JDK utilities. The genuine Temurin binary hashes are retained. With all environment variables cleared, `java`, `javac`, `jar` and `javap` all reported this directory, and a real Java temporary file was created there. V0/Bitwuzla established the synthetic equivalence under these launchers. The live transport smoke preceded this additional JDK wrapper check. [JDK and native proof receipt](evidence/subject-jdk.json) · [Launcher identities](evidence/case-launchers.json)

```sh
op=lib/benchmark/external-upgrades/operator/claude-native-resume
python3 "$op/prepare_case_root.py" --base-product "$STAGED_BASE_V0" --output "$NEW_CASE_TOOLS"
python3 "$op/prepare_shadow.py" --product "$STAGED_BASE_V0" --output "$NEW_SHADOW_TOOLS"
python3 "$op/run_case.py" --cohort disclosed --received-at "$INTAKE_UTC" \
  --release "$RELEASE_DIR/pair" --pair-sha256 "$PAIR_SHA256" \
  --dependencies "$RELEASE_DIR/dependencies/manifest.json" --dependency-sha256 "$DEPENDENCY_SHA256" \
  --product "$NEW_CASE_TOOLS" --shadow-product "$NEW_SHADOW_TOOLS" \
  --case-dir "$NEW_PRIVATE_CASE" --reports "$NEW_PRIVATE_REPORT_STORE" \
  --github "$PUBLIC_REVIEW_TIME_REPOSITORY" --before "$ORIGINAL_BASE" --after "$ORIGINAL_HEAD"
```

Both roots must be staged before dispatching a job to an exported checkout. `prepare_shadow.py` uses the installed first-party executable or an explicit `--claude PATH`. The runner verifies the frozen hashes. The official intake still requires publicly shareable GitHub revisions or a supported registered example; local-only inputs seal as unavailable on the original route. A separately labeled assisted diagnostic needs separate storage. The main and transfer cohorts accept only cases in a signed roster binding this specific operator profile. Adopting it for a study is a prospective operator decision. A disclosed case can be rerun in its own report store without replacing either earlier opening report.
