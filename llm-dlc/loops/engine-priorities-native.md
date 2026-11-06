# Stream brief: engine priorities, the own checker and the solver

One of two streams of [`engine-priorities.md`](engine-priorities.md) that run in parallel, each in its own jj
workspace on its own branch. The other is [`engine-priorities-jbmc.md`](engine-priorities-jbmc.md). Once both have
stopped, a reconcile loop merges them; [Streams](engine-priorities.md#streams) in the main brief says how.

Started with the other stream by `llm-dlc/tools/run-streams.sh engines` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh engines-native` from this stream's workspace
(`jj workspace root --name native`): the loop refuses any other.

**The main brief is the instruction.** Read [`engine-priorities.md`](engine-priorities.md) in full every cycle, and its
input [`engine-priorities-review.md`](engine-priorities-review.md) too. Its direction, evidence, working rules,
deferrals and decisions all apply here. This file only says which part of its plan is yours, and keeps your Progress.
Don't edit the main brief, the other stream's brief, or anything outside this file's `## Progress` section.

## Your phases

1. **1c** the Bitwuzla build job, queued first: it's long, and Phase 6 waits on it;
2. **4b** class initializers counted by shape, with `jvmcontract gaps` scans (static, inline). It decides Phase 5's
   scope, so it comes before Phase 5 here;
3. **5** class initializers in the own checker to the scope 4b supports, the `Enum.<init>`, `List.of` and
   `List.copyOf` models, and the queued strict rerun of 071 and 013;
4. **6a–6d** transcripts, the solver interface, the comparison job and the written recommendation.

Phase 5 is the core of this stream; do it before Phase 6 apart from 1c. While a Phase 5 job runs, go on with 6a and
6b.

Not yours: 1a, 1b, 2, 3, 4a and 4c. The JBMC stream defines how a result records its SAT backend (1b). Until that is
merged, record Bitwuzla's version and configuration in the Phase 6 job's own outputs; the reconcile loop fits them
into 1b's shape.

## Boundaries

You own the own checker and the solver: `lib/src/bmc/`, `lib/models/`, the new solver interface, the Bitwuzla build
and the Phase 6 transcripts, with their tests.

The JBMC stream owns `lib/src/jbmc.rs`, `jbmc_gaps.rs`, `jbmc_contracts.rs`, `phases.rs`, `deadline.rs`,
`lib/benchmark/` and `examples/tools/gap_table.py`. Don't change them. If your work needs a change there, record it
under Progress for the reconcile loop and work around it. Phase 6's comparison job therefore writes its own table
rather than changing the benchmark's.

Some files both streams may touch: `lib/src/main.rs` and `lib.rs` (CLI options, module list), `lib/tests/conformance.rs`
and `lib/tests/conformance/`, `lib/src/interp/`, `witness.rs`, `shrink.rs`, `Cargo.toml`. In those, add rather than
rewrite: new options, new cases and new functions, not reorganizations. Name every change to one of them under
Progress, so the reconcile loop knows where to look. The models in `lib/models` are on JBMC's class path as well: they
are yours, but say under Progress which JBMC results they may change.

## Working in a stream

- **Commit only here**, with `sync.py commit` as CLAUDE.md says. Never push, merge, rebase onto another branch, or
  move a bookmark. The branch is this workspace's `@-` line; the reconcile loop merges it.
- **Jobs.** Submit and commit jobs as usual. The runner works in the default workspace and also runs jobs committed
  here, at this commit (see `verification/README.md`). Results are collected there, not here: read them with
  `python3 "$(jj workspace root --name default)/verification/pipeline.py" report` and `status`, and the files under
  that workspace's `verification/results/`. Record what you take from a result under Progress with the job id. Its
  outputs (071's and 013's example pages, say) reach this branch only at the merge, so don't copy them in by hand; the
  reconcile loop updates the examples' `notes` from them.
- **Status.** The last line of `## Progress` is a status, kept current in every commit and read by
  `run-streams.sh`, which runs this loop unattended: `- Status: working` while there is work you can do,
  `- Status: waiting on jobs ID ...` when everything left waits on those jobs (it runs the loop again once their results
  are collected), `- Status: done` when your phases are finished, or `- Status: blocked: ...` with what needs the user.
- **Another session is not your concern** beyond the loop's usual rule: the JBMC stream works in its own directory
  and never touches this working copy.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `3761db96`,
  compacted), so you share its context with the other stream. What it settled is in the briefs; where your memory of
  it and a brief differ, the brief wins.

## Progress

- **1c, resubmitted.**
  - **The first job failed.** Job `20261106-192008-bitwuzla-0-8-2-built-from-source-for-the` ran
    `lib/solvers/bitwuzla/build.sh 0.8.2` on vm-1 (x86_64; 23.7 s at 8 jobs, peak 1.9 GiB). The fetch, the build and
    the install into `~/tools/bitwuzla/bitwuzla-0.8.2` worked. Then the binary exited 127 on `libcadical.so`: the
    project-wide `-Ddefault_library=shared` reached the CaDiCaL subproject, and meson doesn't install a subproject's
    library. `build.json` wasn't written.
  - **The fix.** `build.sh` now passes `-Dcadical:default_library=static`, CaDiCaL's own default, so CaDiCaL is
    linked into Bitwuzla's shared libraries. A configure-only meson run on the failed job's tree showed the `cadical`
    target static and Bitwuzla's four libraries shared. The script also fails, naming the libraries, if `ldd` still
    finds one missing.
  - **The CaDiCaL inside it is 2.1.2** (Bitwuzla 0.8.2's wrap), not the engine's 1.9.5. 6c has to keep the two
    apart.
  - **Resubmitted** as job `20261106-194049-bitwuzla-0-8-2-built-from-source-cadical`. It brings back
    `lib/solvers/bitwuzla/build.json`: the commit, the tarball digest, the CaDiCaL it links, smoke answers and the C
    API version. It fetches from the network, and says so. The runner is x86_64, not the ARM64 the brief names.
    Phase 6c waits on this job.
- **4b, counted** (static, inline, JDK 25.0.5).
  - **The tool.** `jvmcontract gaps` now gives each `class-initializer` gap's `<clinit>` a shape (`initializer_shape` in
    `lib/src/bmc/gaps.rs`), read from the initializer's bytecode and the application methods it calls. The shapes are
    `enum`, `throws`, `other-statics`, `constants` or `other`, with traits such as `switch-map` and
    `arrays-of-references`.
  - **The count's driver.** `examples/tools/initializer_shapes.py` (new) runs the scan two ways:
    - over the 59 recorded examples the gap scan applies to (B9 and B11 on the javac apps), writing no notes;
    - over each app as a whole, every method a target. Box Office is its `ticketing-domain`, the module javac builds
      alone.
  - **Apps:** 49 initializers, all reached.
    - 36 `enum`.
    - 13 `other-statics`, every one a javac `$SwitchMap` class for a switch over an enum. It calls `values()` and
      `ordinal()`, fills an `int[]`, and catches `NoSuchFieldError`.
    - 0 `throws`, 0 `constants`, 0 `other`.
    - By app (enum + switch map): Mica 5+2, Crosscut 9+3, Quorum 19+7, Box Office 3+1.
  - **Recorded examples:** 2 of the 59 reach an initializer, 013 and 071 (both JBMC proofs). Each reaches the same four
    Quorum `raft` enums: `Ballot`, `LogOrder`, `TermOrder` and `VoteEffect`.
  - **The benchmark:** its only initializers are the conformance cases'. `Boom` and `Base` are `throws`, each
    through the static method its initializer calls; `Quiet` is `constants`, an `int` literal table.
  - **Phase 5's scope, from this count:** full JVMS §5.5. Constants-first would close `quiet` alone and nothing in
    the apps, while enums are three in four of the apps' initializers. Today the own checker also refuses any
    `getstatic` of a field that isn't a compile-time constant, so code that reads an enum constant is outside its
    fragment whatever the gaps. The order:
    1. application static fields as path state, and `<clinit>` run at the first `new`, `getstatic`, `putstatic` or
       `invokestatic`, with `ExceptionInInitializerError` and then `NoClassDefFoundError`. This closes `boom`,
       `inherited` and `quiet`.
    2. enums: the `Enum.<init>` model, and `$VALUES`, an array of references, which the engine refuses today.
    3. switch maps, if (2) brings arrays of references in.
    What stays out stays a named `class-initializer` gap.
  - **Limit:** the scan doesn't walk an initializer's body, so a class that only another initializer initializes is
    not counted. Over the apps every class is a target, so none is missed there.
  - **Shared files changed:** `lib/tests/integration.rs` (a new test,
    `the_gap_scan_gives_each_class_initializer_a_shape`), `lib/README.md` (a clause on `gaps`), `examples/README.md` (a
    paragraph on the new script), `examples/tools/initializer_shapes.py` (new). `jvmcontract gaps --json` gains an
    `initializers` list, which is absent when empty. `build.py` and `gap_table.py` don't read it.
  - **Not caused by this:** `examples/tools/test_build.py` fails 35 tests with `KeyError: 'verdict'` on committed
    results. This change touches nothing that test reads.
  - **Also not caused by this:** `the_corpus_agrees_with_the_jvm_on_the_tools_own_checker` fails 12 claims on this
    machine. The JDK is now 25.0.5, and `lib/models/contracts/checked.json` records its checks on 25.0.4.1, so the
    library's contracts for `capacity`, `builderCapacity`, `mapCapacity`, `setCapacity` and `firstByte` are not
    applied. Every other test passes: unit, integration (64) and skill.
  - **Before Phase 5's conformance cases:** record the library again on 25.0.5 with `gap-contracts --record`. That
    runs proofs, so it is a queued job.
- **5, step 1: class initializers in the own checker** (inline; JVM 25.0.5).
  - **What the engine does now.** An application class's static fields are path state, merged like locals. Its
    initialization follows JVMS §5.5: at the first `new`, `getstatic`, `putstatic` or `invokestatic`, the superclass
    and the superinterfaces with a default method go first, then the `<clinit>` runs as bytecode. A use from inside
    the class's own initialization goes on. An exception leaving a `<clinit>` becomes `ExceptionInInitializerError`
    (an `Error` stays as it is). A later use of that class, or of one that waited on it, throws
    `NoClassDefFoundError`.
  - **What stays a gap.** A `<clinit>` outside the fragment stays a `class-initializer` gap
    (`gaps::runs_initializer`): one that reaches a refused construct, or reads or writes a static of a class whose
    initializer doesn't run. Over the apps that is all 49 (36 enums, through `$VALUES`, an array of references, and
    13 switch maps). `initializer_shapes.py --apps-only` still counts the same 49 as gaps.
  - **The gap scan** (`jvmcontract gaps`) walks the initializers the engine runs, like methods. It refuses a static
    field only of the JDK, or of a class whose initializer doesn't run. The refusal reasons for static fields are
    renamed to say which of those it is. Superinterfaces are now initialized in JVMS's order (an interface's
    superinterfaces before it); the old walk put them after.
  - **Conformance, checked on the JVM:**
    - `boom` and `inherited` are now violations whose witnesses replay, and `quiet` is verified, in every mode.
    - 8 new cases, 16 claims, all as the JVM decides them in every native mode: `counter`, `constructed`,
      `superFirst`, `cycle`, `declaring` (only the declaring class is initialized), `defaults`, `fatal` (an `Error`
      stays as it is) and `boomTwice` (`NoClassDefFoundError`).
    - The old engine gives none of them a verdict.
    - The test still fails only its 12 pre-existing library-record claims (above).
  - **Interpreter fixes, needed for the witnesses to replay as on the JVM** (`lib/src/interp/mod.rs`,
    `ensure_initialized`, `get_static`, `put_static`, a new `static_declarer`):
    - an erroneous state, and `NoClassDefFoundError` at a later use;
    - an `Error` not wrapped;
    - a superclass's failure making the class erroneous;
    - superinterfaces with default methods initialized;
    - `getstatic`/`putstatic` initializing the declaring class only.
    JBMC's witnesses are replayed by the same interpreter, so a JBMC counterexample through an erroneous class now
    replays as the JVM runs it. No model changed, so no JBMC result changes otherwise.
  - **Shared files changed:**
    - `lib/src/interp/mod.rs`, above.
    - `lib/tests/conformance.rs`: the cases, three recorded verdicts, and the comment on the corpus's contracts,
      whose two initializer contracts now close nothing.
    - `lib/tests/conformance/conformance/Conformance.java`: the cases' classes and methods.
    - `lib/tests/integration.rs`:
      - `identity_and_initialization_agree_with_the_jvm` has a new `Names` fixture, still a gap;
      - `the_gap_scan_names_what_the_own_checker_approximates` has `Primes`, walked;
      - `the_gap_scan_gives_each_class_initializer_a_shape` reads the shapes directly;
      - `a_contract_closes_its_gap_and_the_verdict_rests_on_it` adds a `String[]` to `Contracted.Table`, so it stays
        a gap.
    - `lib/README.md`: the fragment, the gap list, and the corpus's contract count, which is now 5 of 6.
    - Also changed, outside the listed shared files: `lib/src/advice.rs` and `lib/src/contract_proving.rs` (one
      wording each), and `examples/tools/initializer_shapes.py` (its docstring).
  - **For the reconcile loop:** `lib/benchmark/conformance.json` belongs to the JBMC stream, and it's now behind the
    corpus. `the_benchmark_takes_its_first_group_from_this_corpus` fails here until that file is regenerated with
    `JVMCONTRACT_BLESS=1 cargo test --test conformance the_benchmark_takes_its_first_group_from_this_corpus`: 16
    new claims, and `nativeStrict` for boom, inherited and quiet. All other tests pass: unit (145), integration (64),
    skill.
- **Next: Phase 5, step 2**: the `Enum.<init>(String, int)`, `List.of` and `List.copyOf` models in `lib/models`, with
  conformance cases checked on the JVM. Then queue the strict rerun of 071 and 013, together with the library's
  `gap-contracts --record` on 25.0.5. After that, enums in the own checker: arrays of references for `$VALUES`.
- Status: working

## Loop settings

- session: 63d80e44-36d9-4bcb-9e72-e31c6d9336ef
- model: claude-opus-5-5
- effort: high
- workspace: native
- fork: 3761db96-b870-47f7-aded-2ba264c165f4

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Phase 5 is the core of this stream:
don't stop before it is done unless a step waits on a job or on the user. When everything left waits on jobs, set the status
to `waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your
phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress
as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.
