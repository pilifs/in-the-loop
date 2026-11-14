# Stream brief: example targets, the CVE catalog and three negative packets

One of four streams of [`example-targets.md`](example-targets.md) that run in parallel, each in its own jj workspace on
its own branch. The others are [`example-targets-runtime.md`](example-targets-runtime.md),
[`example-targets-positive.md`](example-targets-positive.md) and [`example-targets-workflow.md`](example-targets-workflow.md).
Once all four are finished, the main brief's loop merges them ([Reconciling](example-targets.md#reconciling)) and runs
your packets through the merged infrastructure.

Started with the others by `llm-dlc/tools/run-streams.sh example-targets` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh example-targets-negative` from this stream's workspace
(`jj workspace root --name example-targets-negative`).

**The main brief is the instruction.** Read [`example-targets.md`](example-targets.md), the acceptance contract
[`example-targets-acceptance.md`](example-targets-acceptance.md) and [`example-targets-inputs/seeds.json`](example-targets-inputs/seeds.json)
in full every cycle, with their inputs. Their direction, starting point, working rules, safety rules, downloads policy,
deferrals and decisions all apply here. This file says which items are yours, and keeps your Progress. Within the
briefs, edit only this file's `## Progress` section.

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/example-targets-integration.md`, if it exists. A failure in
your files is your next piece of work; a conflict in a file you own is a coordination task, recorded under Progress.

## Goal

Turn three researched Spring vulnerabilities into durable packets a later agent can execute, prove or diagnose without
rediscovering revisions, security intent or reproduction conditions. Each keeps both the security question and the
legitimate behaviour the fix must preserve. A capability refusal is evidence about the verifier, not about the program.

## Starting evidence

The archived registry `example-targets-inputs/spring-cve-targets.research-2026-11-04.json` holds 15 researched CVEs,
none executed; its verifier review is from `4c279ba6` and stale. The three promoted entries, and the fix pairs the
outside review inspected:

| Case | Release pair | Exact fix pair, parent → change |
|---|---|---|
| CVE-2023-34055 | Boot `v2.7.17` → `v2.7.18` | `7ad6e4470c945ae0e39e63af28c47aebbe27bbc0` → `5490e73922b37a7f0bdde43eb318cb1038b45d60` |
| CVE-2022-22968 | Framework `v5.3.18` → `v5.3.19` | `0cf7f7bd890504061883c48e382dc23e0c5d4df0` → `a7cf19cec5ebd270f97a194d749e2d5701ad2ab7` |
| CVE-2025-22228 | Security `6.3.7` → `6.3.8` | `36ea1b11a7dae7904e3c70b5e10fb01152fec5d4` → `46f0dc6dfc8402cd556c598fdf2d31f9d46cdbf3` |

These are fix pairs; none is an established introducing pair. Release comparison and exact-patch comparison stay
separately named, and one execution pair is selected explicitly before a claim is frozen. Check every SHA and parent
against upstream (you may fetch, pinned) before relying on it.

## Your items

Every case has separate tasks for: the security property on the vulnerable revision (expected refuted); the **same
property** on the fixed revision (expected established); and preservation outside a stated allowed-change region
(expected established). There is no `fix` command: these are composed from `prove`, `compare` and `equivalence` tasks.
An all-input equivalence failure on a security fix may be intended, and an exit 1 establishes nothing. Each task keeps
its own receipt.

Original methods are called through minimal adapters, every adapter and model boundary recorded, static initialization
and exceptions kept. An adapter that maps the input to a safe enum first, catches every exception as success, or
replaces the vulnerable method with an assumed summary invalidates the claim.

### N0. The catalog

Import the fifteen CVEs into the router as numbered examples in 285–304, with advisory and patch links, distinct
release and commit pairs, unknown introductions and the original research date. Promote the three above in place,
numbered once. Each catalog-only entry shows its missing prerequisites and no proof verdict. Keep the later binder, URI,
traversal, dispatch and reflection cases discoverable without making them deep builds. Tags are additions to
`examples/tags.json`, in a block marked `negative`, or an interface request.

### N1. Method labels (CVE-2023-34055)

The MVC entry `WebMvcTags.method(HttpServletRequest)` first. The [patch](https://github.com/spring-projects/spring-boot/commit/5490e73922b37a7f0bdde43eb318cb1038b45d60)
limits method values to known HTTP methods or `UNKNOWN`; the [advisory](https://spring.io/security/cve-2023-34055/)
gives the release context. Freeze the version-specific output set, and keep known-method labels and the documented null
behaviour. Probes: `GET`, `POST`, a nonstandard token such as `XSCF` that reaches the original classifier unchanged, and
a null request. Record the tag key, value and exceptions; the benign controls must reject an implementation that maps
everything to `UNKNOWN`. This is a property of one metric label dimension: whole-application availability and the
WebFlux carrier are further obligations. Record an actual obstacle (request interfaces, `Tag`, enums, unrelated regex
class initialization) instead of removing it from the artifact. Mutation control: restore raw method emission in the
fixed target.

### N2. Binder case handling (CVE-2022-22968)

The actual `DataBinder` configuration and its `isAllowed` decision, with the [case-normalization patch](https://github.com/spring-projects/spring-framework/commit/a7cf19cec5ebd270f97a194d749e2d5701ad2ab7).
Pin the default locale explicitly. Start from the upstream `age`/`AGE` disallowed-field regression, a permitted field,
and the changed wildcard and map tests: copy the tests' intent and inputs, never the implementation, into the oracle.
Keep the predicate lemma apart from the stronger claim that protected bean fields can't be mutated through binding
(`protected-state-mutation`); if reflection or property resolution blocks the latter, keep both tasks and attach an
observed gap to the blocked one. A subclass exposing the protected predicate delegates to the original bytecode. Link
[CVE-2024-38820](https://spring.io/security/cve-2024-38820/) as the later locale challenge: locale invariance and
case-alias protection are different properties. Don't report the 2022 patch as an introduction without a stable oracle
and a reproduced parent/child transition. Mutation control: remove the normalization, or normalize one side only.

### N3. BCrypt byte boundary (CVE-2025-22228)

Freeze the March 2025 behaviour of the [length patch](https://github.com/spring-projects/spring-security/commit/46f0dc6dfc8402cd556c598fdf2d31f9d46cdbf3):
it rejects passwords over **72 UTF-8 bytes**. The public-entry claim is about `BCryptPasswordEncoder.matches` with an
otherwise valid stored hash; a byte-array guard lemma is narrower. Provide the valid stored hash independently of the
overlong check. Probes: 71, 72 and 73 bytes; a wrong in-range candidate; a multibyte candidate that crosses the limit
with fewer Java characters (36 × U+00E9 plus `x`, or 18 supplementary characters plus `x`, checked under the pinned
JDK). Never rely on `matches(overlong, encode(overlong))`: encoding can throw first (the upstream test does exactly
this). Bounds must reach the rejected branch: eight UTF-16 code units can't reach 73 bytes. Only the specified
rejection exception counts as the intended outcome. Pin stored-hash validation (it uses `java.util.regex`), UTF-8
semantics and any cryptographic summary; without unchanged-callee reasoning, record the precise gap rather than claim a
guard proof covers authentication. Mutation control: count Java characters instead of UTF-8 bytes.

### N4. The follow-up, and the handoffs

Add [CVE-2025-22234](https://spring.io/security/cve-2025-22234/) as research-only, linked to N3. The vendor attributes a
broken `DaoAuthenticationProvider` timing mitigation to the 22228 fix. Its repair pair is
`eb013944277879b4c1541857a5b8263f5235ff82` → [`c1aa99fdd2113a232986e9c3a44673ae752de840`](https://github.com/spring-projects/spring-security/commit/c1aa99fdd2113a232986e9c3a44673ae752de840),
in 6.3.8 → 6.3.9: long **new encodings** are refused and legacy matching is allowed. The earlier blanket rejection
property never silently becomes this different policy, and output or call-log equality proves no timing
noninterference. For every attempted blocker, the gap packet of the main brief; predicted gaps are labelled as such.
After two substantive failures on one obstacle, stop expanding the workaround and write the handoff.

## Ownership and cooperation

- **Yours**: the catalog folders and the three packets in 285–304: their `example.json`, `target.json`,
  `sources.lock.json`, `claims/`, `replay/`, `controls/`, local adapters, oracles, probes and notes.
- **Not yours**: acquisition, builds and JVM execution (runtime); planning and ingestion (workflow); shared files (the
  coordinator). No downloader or parser code in a case folder. Ask through Progress.
- Until the merge, check a driver against a pinned JAR fetched by hand if you like, with its sha256 noted: a note, never
  evidence.

## Acceptance

At your finish, on your branch: the catalog imported and valid against Phase 0's sidecar schema; all three packets with
source locks checked against upstream, task definitions, frozen-or-pending claim state, concrete probes, an independent
oracle, mutation controls, and a replay driver or a precise build blocker. A blocked packet is partial. In Phase 5, at
least one negative/fixed pair runs original-JVM controls through the integrated path (A3): the oracle observes the
vulnerable violation, the specified fixed response on the same trigger, and retained legitimate behaviour. Two process
exits are not enough. Proof success on every Spring task is not required.

## Working rules

The main brief's [How to work through it](example-targets.md#how-to-work-through-it): the pipeline, the two-failure
timebox, the downloads policy and the safety rules. Queue anything heavy, and record each job's revision and id.

## Progress

- Forked after the main brief's [launch prerequisites](example-targets.md#launch-prerequisites), Phase 0 included, on
  2026-11-14. No integration report existed yet at the first cycle.
- 2026-11-14, **N0 done: the catalog**, 285–300, one folder per CVE in the registry's rank order (285 CVE-2023-34055,
  286 CVE-2022-22968, 287 CVE-2025-22228, then 288–299 the other twelve, 300 CVE-2025-22234 from the seed file); 301–304
  stay free. Each has `example.json` (real-world, `security`, verdict label "not run"), a `target.json` and a
  hand-written `README.md`. The three promoted entries have role `negative` and no tasks yet; the rest role `catalog`,
  with the registry's model blockers as predicted (`observed: false`) handoff blockers and its next action. Every
  revision was **checked against upstream** (`sourceConfidence: checked-upstream`): the release tags (32 references) resolved with
  `git ls-remote` on github.com, all 17 fix commits and their recorded parents read from github.com (commits only, no
  trees), and each fix an ancestor of its fixed release and not of its vulnerable one (`git merge-base` on a treeless
  fetch since 120 days before the fix). All matched the registry, including its three recorded fixed-tag commits and the
  seed's 6.3.9 commit. Release and exact-fix pairs are separate; no execution pair is selected. Introductions: unknown,
  except 288 (candidate: 286's fix), 290 (candidate `039e0328`, not checked) and 300 (vendor-attributed: 287's fix).
  New tags at the end of each facet of `examples/tags.json`, listed in its `$negative` key: domain `metrics`,
  `data-binding`, `password-hashing`, `uri-parsing`, `resource-serving`, `expression-evaluation`; defect
  `denial-of-service`, `case-normalization`, `path-traversal`, `parser-differential`; technique `external-target`.
  The integration script passes on this workspace (contract 3 pass and 13 stubs, targets 41, `test_build` 190,
  `test_pipeline` 29, every sidecar valid). The import script was a one-off outside the repository; the folders are the
  record.
- **Interface request (coordinator, at the merge)**: regenerate the router (`build.py --index-only`) so 285–300 appear
  in `examples/README.md` and `index.json`, and so `find.py --tag external-target` or `--role catalog` finds them. This
  stream doesn't write those generated files.
- 2026-11-14, **N1 done: the method-label packet (285)**, ready for Phase 5's preparation. `target.json` selects the
  **release pair** (2.7.17 → 2.7.18, `published-artifact`). The exact-fix pair (`7ad6e447` → `5490e739`) has no
  published JAR, and the release pair carries it faithfully: each release's `WebMvcTags.java` has the exact-fix pair's
  blob (`e5e2147b`, `9f92c1ce`, also in the sources JARs), and `Tag`, `ImmutableTag` and `HttpMethod` are
  byte-identical across the two closures. Four tasks, all native strict and requiring the replay:
  - `replay`;
  - `vulnerable-security` (expected refuted) and `fixed-security` (expected established), sharing
    `claims/bounded-method-label.json`: the label is one of Framework 5.3's eight `HttpMethod` names or `UNKNOWN`, with
    the request nullable, `maxArrayLength` 8 and the exception observed;
  - `preservation` (expected established), on `claims/known-method-labels-preserved.json`, outside the allowed change
    "a non-null request whose method is none of the eight".

  The claim files are in the workflow stream's `example-target-claim/v1` (W1, on its branch). They validate against
  its schema, and W1's `plan_task` plans all four tasks from this folder (read-only, from its workspace).

  Also in the folder:
  - `sources.lock.json`: blobs, managed versions, the class path's seven JARs per release with their sha256 (sha1
    checked against Central), and `javap` facts;
  - the request carrier `MethodOnlyRequest`: the token as given, and every other servlet method throws and is recorded;
  - the adapter and driver, compiled with `--release 21`;
  - `controls/probes.json`, with 15 probes: the eight names and a null request as legitimate; `XSCF`, `get`, the
    empty token, a 64-char token and `CONNECT` as triggers; `UNKNOWN` as an edge;
  - `controls/oracle.py`, from the statement. Its `self-test` rejects an all-`UNKNOWN` implementation through the
    legitimate controls and preservation, and refuses malformed, incomplete, duplicated or over-reaching output;
  - the mutation `controls/raw-method-fallback.patch`: the fix with the raw token as the fallback's label, compiled
    into a copy of the 2.7.18 JAR.

  **Developer note, not evidence**: by hand with pinned JARs, on Temurin 21.0.13 and 25.0.5:
  - 2.7.17 fails at exactly the five triggers and passes every legitimate probe;
  - 2.7.18 holds and passes;
  - the mutant fails at the same five;
  - preservation holds, with the changes only in the allowed region;
  - each revision's lines are identical on both JDKs, and no probe read the request beyond `getMethod()`.

  No capability probe was queued: Phase 5 runs it on prepared artifacts. The three blockers are rewritten for this
  packet, still predicted, and the exact `jvmcontract gaps` probe is in `handoff.next`.

  **For review**: the frozen set is version-specific, so the fix labels `CONNECT` and `get` `UNKNOWN`. The claim fixes
  the set, not each token's label inside the allowed change, so a case-folding fix would pass it too. `WebFluxTags`'s
  fix moves classification into `ServerHttpRequest.getMethod()`, so its obligation rests on the server adapter. A null
  `getMethod()` is outside the domain (2.7.17 throws an NPE, 2.7.18 returns `UNKNOWN`).
- **Interface requests (at the merge)**, beside the router request above:
  1. *A constructed mutant as a revision*, as the positive stream's Progress asks: a negative sidecar can't name one,
     since a `fixture` revision is allowed only in a `control` role. Until then 285's mutant is a `controls` entry of
     kind `mutation`, with its base revision, its task (`fixed-security`) and the patch's sha256, and runtime's
     preparation needs a step that compiles the patched class into a copy of the base JAR.
  2. *How a driver is invoked*: a `driver` control names a source file only. 285's main class is
     `example285.driver.MethodTagDriver`, its arguments are `python3 controls/oracle.py argv`, and the oracle's entry
     points are `check(lines)` and `compare(before, after)`. Runtime's `run_controls` and workflow's ingestion need a
     field or a convention for these.
- 2026-11-14, **N2 done: the binder packet (286)**, ready for Phase 5's preparation. `target.json` selects the
  **release pair** (5.3.18 → 5.3.19, `published-artifact`, four JARs per release). The exact-fix pair has no published
  JAR, and the release pair carries it faithfully:
  - each release's `DataBinder.java` is the exact-fix pair's blob (`612dfc56`, `8ee5e43b`, also in the sources JARs);
  - the decision's helpers are byte-identical across the closures;
  - the release window's two `CachedIntrospectionResults` commits filter properties the probe bean doesn't have, and
    the driver prints the resolved properties on every run.

  Three claims, six tasks, all native strict and requiring the replay:
  - `replay`;
  - `vulnerable-security` (refuted) and `fixed-security` (established), the **decision lemma**
    (`claims/disallowed-field-denied-ignoring-case.json`): a field a canonical disallowed pattern matches ignoring
    ASCII case is denied;
  - `preservation` (established, `claims/permitted-fields-preserved.json`): outside the case aliases both releases
    decide alike;
  - `vulnerable-protected-state-mutation` (refuted) and `fixed-protected-state-mutation` (established), the
    **protected-state claim** on the actual `bind` (`claims/protected-age-not-mutated.json`): with `AGE` or `age`
    disallowed, binding a simple name never writes `age`.

  The domain is ASCII, a canonical field, and the default locale pinned to `Locale.ROOT`. The driver pins it before any
  Spring class loads, and the oracle refuses a run without it. The claims are Java over the adapters' parameters; their
  matching uses `java.util.regex` with ASCII `CASE_INSENSITIVE`, written independently of the patch. A Java harness
  confirmed that they agree with the oracle on every in-domain decision probe. They validate against W1's schema, and
  its `plan_task` plans all six.

  Also in the folder:
  - `sources.lock.json`;
  - the adapters: `ExposedDataBinder` (a subclass whose `decide` is one call of the protected `isAllowed`),
    `BinderDecisionAdapter`, `BindingAdapter` and `ProtectedBean`;
  - the driver `BinderDriver`;
  - `controls/probes.json`: 46 probes, 35 decisions and 11 bindings, on 10 configurations, five of them the upstream
    tests' inputs. Roles: 12 triggers, 30 legitimate, the regression's own inputs, and 3 edges outside the domain;
  - `controls/oracle.py`, from the statement. Its self-test tells case-sensitive, ignoring-case, deny-all and
    field-lowered binders apart;
  - the mutation `controls/pattern-side-unnormalized.patch`, on 5.3.19: one side normalized.

  **Developer note, not evidence**: by hand with pinned JARs, on Temurin 21.0.13 and 25.0.5:
  - 5.3.18 fails at exactly the 12 triggers (4 of them bindings that write `age`, `favouriteColour` or
    `someMap[key3]` through an alias) and passes every legitimate probe;
  - 5.3.19 holds and passes;
  - preservation holds, with changes only at the triggers and the regression's inputs;
  - the mutant fails 13 probes, the exact-case `favouriteColour` among them, and passes the legitimate ones;
  - lines are identical on both JDKs.

  No capability probe was queued. Four blockers are predicted: `toLowerCase` and regex, `String[]` construction, the
  `Class.forName` in spring-jcl's `LogAdapter.<clinit>` that `DataBinder.<clinit>` reaches, and the binder's
  reflection.

  **For review**:
  - *Final sigma.* Outside the ASCII domain, 5.3.19 is not even monotone. With the pattern `dataΣ*`, it allows
    `dataΣx`, which 5.3.18 denies by exact match: `String.toLowerCase` maps the pattern's `Σ` to a final `ς` and the
    field's to a medial `σ`. This is in any locale, and so not CVE-2024-38820's locale issue. Seen on the JVM
    (probe `sigma-exact`); not part of any claim.
  - *Locale.* Under `tr-TR`, 5.3.19 allows the alias `favouriteColour` against `FAVOURITECOLOUR` (example 288's
    property).
  - *The regression's value.* The upstream test's value `32x` doesn't convert, so on 5.3.18 that test fails on the
    suppressed fields only, not on a write. The probes add `32` and the advisory's `Age`.
  - *Further obligations.* Nested paths through a nested bean, and indexed names, are outside the protected-state
    claim. On the int `age`, an indexed name throws `InvalidPropertyException` on both releases.
- 2026-11-14, **N3 done: the BCrypt packet (287)**, ready for Phase 5's preparation. `target.json` selects the
  **release pair** (6.3.7 → 6.3.8, `published-artifact`: spring-security-crypto, then the spring-jcl each release
  manages, 6.1.17 and 6.1.18). The exact-fix pair has no published JAR, and the release pair carries it faithfully:
  - both releases' `BCrypt.java` and `BCryptPasswordEncoder.java` are the exact-fix pair's blobs (`0f8d082f` →
    `17292840`; `d17511b0` throughout), also in the sources JARs;
  - the window's only other crypto commit touches build files;
  - in the class files only `BCrypt.hashpw(byte[], String, boolean)` differs (compared method by method), and the
    encoder's classes and spring-jcl's are byte-identical.

  Three claims, six tasks, all native strict and requiring the replay:
  - `replay`;
  - `vulnerable-security` (refuted) and `fixed-security` (established), the **public claim**
    (`claims/overlong-candidate-rejected.json`), entered through a one-call adapter on the encoder's no-argument
    constructor. For a valid stored hash (minor a/b/y, cost 04–30) and a non-null candidate, `matches` throws
    `IllegalArgumentException` exactly when the candidate is longer than 72 UTF-8 bytes, and never returns true for one.
    The byte count is the JDK's `getBytes(UTF_8)`, and Strings are bounded at 80 units (73 bytes take at least 25);
  - `preservation` (established, `claims/in-range-matching-preserved.json`), outside "a non-null candidate longer than
    72 UTF-8 bytes", null and malformed stored values included;
  - `vulnerable-guard` (refuted) and `fixed-guard` (established), the **byte-array lemma** on
    `BCrypt.checkpw(byte[], String)` (`claims/overlong-bytes-rejected.json`). Their relation is `diagnostic`, with the
    security task as `parent`, which the lemma never settles.

  The claims validate against W1's schema, and `plan_task` plans all six. A generated Java harness evaluated the public
  claim's `assume`, `assert` and `throws` on every `matches` outcome, and they agree with the oracle on all three runs.

  Also in the folder:
  - `sources.lock.json`, with the 6.3.9 hashes for N4;
  - the adapter `PasswordMatchAdapter` and the driver `BCryptDriver`. Candidates go in and out as UTF-16 units, so
    lone surrogates survive, and every line carries the JDK's own byte count;
  - `controls/probes.json`: 9 stored hashes **made independently by pyca bcrypt 5.0.0** from recorded preimages
    (never `encode(overlong)`), and 33 probes. There are 9 triggers (72 bytes plus more: ASCII, minors b and y,
    36 × U+00E9 + `x`, 18 × U+1D11E + `x`, a split character, two byte arrays), 3 policy probes (overlong without the
    prefix, including 25 × U+20AC, the fewest units that cross), 15 legitimate (71 and 72 bytes, right and wrong) and 6
    edges;
  - `controls/oracle.py`, from the statement. It names a violation's kind (`authenticated`, `unrejected`,
    `wrong-exception`, `in-range-exception`) and refuses a run whose JDK counts other bytes. Its self-test rejects
    deny-all and reject-all, and checks every pre-written expectation against each revision's documented shape;
  - the mutation `controls/char-count-guard.patch` on 6.3.8: the String entries count UTF-16 units, and the byte
    guard is gone.

  **Developer note, not evidence**: by hand with pinned JARs (sha256 in the lock), on Temurin 21.0.13 and 25.0.5:
  - 6.3.7 fails at the 12 overlong probes (9 authenticated, 3 unrejected) and passes every legitimate one;
  - 6.3.8 holds and passes;
  - the mutant authenticates the 3 multibyte triggers and the 2 byte arrays, and passes the ASCII triggers and the
    legitimate probes;
  - preservation holds, with changes only at the 12;
  - every outcome is the one written before the run, and lines are identical on both JDKs.

  No capability probe was queued. Four blockers are predicted:
  - String expressions and regex;
  - String construction up to 80 units;
  - `crypt_raw` under "exactly" (resources). The precise gap: no cryptographic summary is claimed, and closing it needs
    a declared summary, or unchanged-callee pairing for preservation;
  - spring-jcl's `Class.forName` in the encoder's field initializers.

  **For review**:
  - *Lone surrogates.* 25 unpaired surrogates match a hash of 25 `?` on every revision (the JDK's lossy encoding; in
    range, so not this CVE).
  - *Cost 31.* A stored hash with cost 31 never terminates for an in-range candidate: `crypt_raw`'s `int` counter
    runs against 2^31 rounds. Read from the bytecode, not run.
  - *Long legacy passwords.* bcrypt's hash of a 73-byte password is that of its first 72 bytes, so 6.3.8 locks out a
    stored long password. That is N4's ground (6.3.9's legacy matching).
  - *Strictness.* The frozen claim asks for the rejection itself. The seed's "may reject" reading would also accept
    `false`, but `--throws` states only "exactly when". The oracle reports the two kinds apart.
- Next: N4, the follow-up (300, CVE-2025-22234), research-only and linked to N3. Record the repair pair `eb013944` →
  `c1aa99fd` (6.3.8 → 6.3.9) and its policy (long new encodings refused, legacy matching allowed) as a separate,
  unfrozen contract. State that no output or call-log equality establishes timing. Give each attempted blocker its gap
  packet, with predicted ones labelled. Then the handoffs, and check the three packets against the acceptance.
- Status: working

## Loop settings

- session: 70d4b729-3b1f-41d1-a89c-03fd78a71818
- model: claude-opus-5-5
- effort: high
- memory: 12G
- workspace: example-targets-negative
- fork: e9be5afb-09c9-4473-a9e9-38f2fb61ca80

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when N0–N4 and your acceptance are met, or each is deferred by the timebox
with the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under
Progress. Don't go on into an unbounded proof or introducing-commit investigation. Anything new you find goes under
Progress, for the main brief's for-review list.
