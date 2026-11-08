# Stream brief: example targets, three independent positives and a migration

One of four streams of [`example-targets.md`](example-targets.md) that run in parallel, each in its own jj workspace on
its own branch. The others are [`example-targets-runtime.md`](example-targets-runtime.md),
[`example-targets-negative.md`](example-targets-negative.md) and [`example-targets-workflow.md`](example-targets-workflow.md).
Once all four are finished, the main brief's loop merges them ([Reconciling](example-targets.md#reconciling)) and runs
your packets through the merged infrastructure.

Started with the others by `llm-dlc/tools/run-streams.sh example-targets` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh example-targets-positive` from this stream's workspace
(`jj workspace root --name example-targets-positive`).

**The main brief is the instruction.** Read [`example-targets.md`](example-targets.md), the acceptance contract
[`example-targets-acceptance.md`](example-targets-acceptance.md) and [`example-targets-inputs/seeds.json`](example-targets-inputs/seeds.json)
in full every cycle, with their inputs. Their direction, starting point, working rules, safety rules, downloads policy,
deferrals and decisions all apply here. This file says which items are yours, and keeps your Progress. Within the
briefs, edit only this file's `## Progress` section.

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/example-targets-integration.md`, if it exists. A failure in
your files is your next piece of work; a conflict in a file you own is a coordination task, recorded under Progress.

## Goal

Scaffold accepted upstream changes that make demands like the negative cases', so the corpus shows whether the tool
keeps legitimate behaviour through real changes as well as finding violations. Upstream acceptance, expected result,
observed proof result and absolute security properties stay separate. A positive is not a CVE fix relabelled green:
these are three independent historical changes with explicit observation contracts, matched to the negative families
in their relevant semantics, not in every input type.

## Starting evidence

| Family | Positive commit | Parent |
|---|---|---|
| HTTP metric labels | Boot [`e8de5a6d95ffb45cd532c2a863e6a726e159b7e3`](https://github.com/spring-projects/spring-boot/commit/e8de5a6d95ffb45cd532c2a863e6a726e159b7e3), the `Outcome` enum | `9b8decf99c9665f219cdd3a7c3fa9aaa61aec3ca` |
| Binder decision strings | Framework [`db9a10bf3524923e8cd5be3f2b847002b8289f75`](https://github.com/spring-projects/spring-framework/commit/db9a10bf3524923e8cd5be3f2b847002b8289f75), the prefix optimization | `27bfcbbc823897169942ddc9a9ff9538486426c5` |
| Password bytes | Security [`fe9e4549780e940c9cef7f2991e75e0b686fc5d1`](https://github.com/spring-projects/spring-security/commit/fe9e4549780e940c9cef7f2991e75e0b686fc5d1), the predefined UTF-8 charset | `fb39d9c255196031a9622cfd197d1fb05fd96bb2` |

The outside review inspected the patches and parents; nothing was built, replayed or proved. These are commit pairs
with no published JARs, so they take runtime's pinned upstream build route, with the JDK each revision's build supports
(8, 11, 17, 21 and 25 are installed; controls run on 21 and 25 wherever the artifacts do). Check every SHA and parent against upstream before relying on it.

## Your items

Freeze the observation, domain, exceptional behaviour and dependency environment before any proof. Start with explicit
native strict checking through the shared interfaces; an advised or model-based attempt is separately labelled
evidence. Reuse the canonical claim keys and format 2; never replace unknown with success because upstream accepted the
change. Each revision's original artifacts run in their own JVM and classpath. Where reference identity changes but
values are the intended contract, justify the value observation in the case. A proof on a copied kernel is a derived
claim and doesn't inherit the original method's identity.

Each family has a nearby deliberate mutant that must fail the same observation, domain and property contract: a
constructed control with a base revision and a patch hash, a new canonical claim key and an explicit link to the case.
It guards against an adapter that misses the changed branch, a vacuous domain, or a report that accepts expected exit
codes.

### P1. Boot outcome enum (`e8de5a6`, 2019-09-05)

The patch adds `Outcome` with six cached tags and rewrites `WebMvcTags.outcome(HttpServletResponse)` to
`Outcome.forStatus(response.getStatus()).asTag()`; the old path used `HttpStatus.Series.resolve` and a switch. Scaffold
the real MVC entry over a null response or an arbitrary `int` status, observing tag key and value, termination and
specified exceptions: both revisions give the same label from the six-value set. Object identity is excluded on
purpose, since the patch moves allocation and caching. Probes: null; 99, 100, 199, 200, 299, 300, 399, 400, 499, 500,
599, 600; both `int` extremes. The outcome-range oracle is authored independently of the changed code. Mutation:
misclassify the 200 boundary. Record the enum, `Tag`, class-initialization and response-interface requirements, and the
complexity difference from the negative (an integer here, method strings there). The claim is limited to this MVC
entry: the eight-file patch also changes client paths and removes a client exception catch. Upstream `OutcomeTests`
document the intended ranges; they are not proof evidence.

### P2. Framework prefix optimization (`db9a10b`, 2021-04-21)

One expression in `PatternMatchUtils.simpleMatch(String,String)`:

```java
pattern.substring(0, firstIndex).equals(str.substring(0, firstIndex))
// becomes
pattern.startsWith(str.substring(0, firstIndex))
```

The length guard and the recursive wildcard algorithm stay. The contract is decision preservation, not a new locale or
case guarantee. Scaffold the original old and new methods over a declared bounded UTF-16 domain, nullable strings
included, observing the boolean and exceptions. Exercise empty and no-star patterns, leading, internal, trailing and
repeated stars, prefix mismatch and non-ASCII code units, with `(null,"x")`, `("*","")`, `("abc*","ab")`,
`("abc*","abcdef")`, `("abc*","xbcdef")`, `("a*c","abbbc")`, `("a*c","abbbd")`, `("a**c","abc")` and `("é*","éx")`. At
least one true and one false case reach the changed prefix branch. Mutation: drop the prefix condition. If recursion or
string semantics stop the verifier, write the reproducer and closure test; never narrow to a few literals while keeping
a claim over the declared domain. An induction proof is a separate, stronger scope.

### P3. Security UTF-8 rewrite (`fe9e454`, 2019-08-08)

`BCrypt.hashpw(String,String)` goes from `password.getBytes("UTF-8")` and its checked-exception wrapper to
`password.getBytes(StandardCharsets.UTF_8)`; the patch also changes a cached charset and test utilities, and only the
BCrypt entry is selected. Freeze the password and salt domains, JDK behaviour, and return and exception observations.
Use a fixed valid low-cost salt from an upstream test, not random salts. Probes: empty, ASCII, BMP non-ASCII,
supplementary characters, and 71, 72 and 73 bytes; decide explicitly whether malformed surrogates, a null password and
an invalid salt are in the domain, with their expected observations. This pair has no length restriction of its own:
the shared concern with CVE-2025-22228 is the UTF-8 representation. A conversion lemma with a checked unchanged-callee
summary, bound to the actual `hashpw(byte[],String)` bytecode, may allow a proof without re-proving BCrypt; without that
reuse the full claim stays unresolved beside a separate local lemma, and no cipher is substituted. Mutation: UTF-8 →
US-ASCII, with a short non-ASCII input.

### P4. Sensitivity and handoffs

Optionally catalog Boot's tag-allocation optimization [`d6761476803e519ecb74e2c7e1fd78ea2e165250`](https://github.com/spring-projects/spring-boot/commit/d6761476803e519ecb74e2c7e1fd78ea2e165250)
(parent `0bc7bef5e535e05a61a623f2db9e116583a83ca3`): it preserves method-tag values while both revisions still emit
arbitrary method names, so it can pass preservation and fail the finite-cardinality property on both sides. Use it to
test reporting semantics; it is never a secure positive. For observed failures, the gap packet of the main brief; after
two substantive attempts at one blocker, hand it off. 108 is unresolved and 109 has replay and class-initialization
traps: neither is a green control.

### P5. Migrate example 105

Own 105's case metadata and its source and claim packet (Commons Numbers `pow`, commons-numbers#223). Resolve its
historical revisions and artifacts afresh, keep its handwritten report, and select a small non-vacuous primitive
obligation for the new route. Runtime prepares and executes it, workflow ingests it, and Phase 5 runs it: gate A5 needs
an actual established or refuted native result, with independent replay where it applies. An honest unresolved refusal
doesn't pass. If a concrete blocker makes 105 impractical, document it and select 106. Inventory 105–109 without
rewriting their evidence, or treating 107's mixed, 108's unresolved or 109's deferred work as successful.

## Ownership and cooperation

- **Yours**: the three positive packets and the optional control in 305–314, their mutation controls, and 105's
  migration data (its sidecar and packet files; its `README.md` stays as written).
- **Not yours**: acquisition, builds and JVM execution (runtime); planning and ingestion (workflow); shared files (the
  coordinator). No downloader or parser code in a case folder. Ask through Progress.
- Until the merge, check a driver against artifacts you built or fetched by hand if you like, with hashes noted: a note,
  never evidence.

## Acceptance

At your finish, on your branch: all three positive packets with source locks checked against upstream, task and claim
definitions, independent controls, concrete probes, mutation controls, and a replay driver or a precise build blocker;
105's migration packet with its selected obligation. Any incomplete packet stays visibly partial. In Phase 5: at least
one positive pair runs original-JVM controls through the integrated path with its mutant failing the same claim (A4),
and 105 gives an actual established or refuted result (A5).

## Working rules

The main brief's [How to work through it](example-targets.md#how-to-work-through-it): the pipeline, the two-failure
timebox, the downloads policy and the safety rules. Queue upstream builds, and record each job's revision and id.

## Progress

- Not started. Forks after the main brief's [launch prerequisites](example-targets.md#launch-prerequisites), Phase 0
  included.
- Status: working

## Loop settings

- session: ddf78f27-05e0-438a-81be-8e7620b07bb7
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: example-targets-positive
- fork: e9be5afb-09c9-4473-a9e9-38f2fb61ca80

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when P1–P3, P5 and your acceptance are met (P4 is optional), or each is
deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream,
and is recorded under Progress. Don't expand into broad positive mining or cryptographic verification. Anything new you
find goes under Progress, for the main brief's for-review list.
