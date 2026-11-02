---
name: add-tla-model
description: Add a TLA+ model to a Java project, so that TLC checks the invariants its core logic must keep (an order lifecycle, a saga, a circuit breaker, a lease, an idempotency key, a workflow) over every interleaving within bounds. Finds or extracts the decision kernel, derives its behavioural contract from the bytecode with jvmcontract, generates the TLA+ operator from the contract, writes the model of the system around it with the invariants the user states, checks it with TLC, and wires the regeneration and the check into the build so the model stays tied to the code.
argument-hint: "[pkg.Class#method | pkg.Class | path] [--spec-dir DIR] [--deadlock] [--no-refactor] [the invariants, in words]"
disable-model-invocation: true
model: opus
allowed-tools: Bash(jvmcontract:*), Bash(javap:*), Bash(java -version), Bash(javac -version), Bash(find:*), Bash(diff:*), Bash(ls:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*)
---

# Add a TLA+ model to a Java project

You are adding a protocol model to the project in the current directory: a TLA+ specification of how its parts interact (services, handlers, queues, timers, callers) around the piece of code that decides what happens next, with the rules the user wants to hold stated as invariants, checked by TLC over every interleaving within small bounds. Read [reference.md](reference.md) for the shape the kernel needs, the model recipe, the TLA+ that matters here, and how to read TLC, before you write anything.

What makes the model worth more than a diagram: **the decision rule is not transcribed.** `jvmcontract derive` executes the kernel on every input and writes its behavioural contract; `jvmcontract tla` turns the contract into the TLA+ operator the model calls; the build regenerates both. A change to the kernel reaches the model through its proof, not through someone remembering to update a spec. Everything else in the model (what each transaction reads and writes, what can interleave) is written by you against the Java, action by action, and is only as faithful as that reading. Say so in the report and in the model's README.

Every TLC verdict is one of three, and you report them as such:

- **Verified**: every invariant holds in every reachable state within the bounds of the `.cfg`. Say the bounds and the state count. It is not a proof of the Java code: it is a proof of the model, whose kernel is the code's.
- **Violation**: TLC found an interleaving. Render the trace step by step, each step as the Java operation it stands for. It is a bug in the code, a mistake in the model, or an invariant that is wrong as stated, and you say which after checking the Java, never by weakening the invariant to make it pass.
- **Unverifiable**: TLC produced no verdict (a parse or evaluation error, a state space that did not finish). Give the message. Never present it as a pass.

## Arguments

`$ARGUMENTS`. Everything is optional:

- A target `pkg.Class#method`: the kernel to build the model around. `pkg.Class` or a path narrows the search for one. Nothing: find it.
- `--spec-dir DIR`: where the model goes (default `spec/` in the module that owns the kernel).
- `--deadlock`: also report a reachable state in which nothing can move (a thread waiting on itself, a saga that cannot finish). Needs a `Terminating` action in the model; see reference.md.
- `--no-refactor`: never change Java. If the project has no kernel of the right shape, write the operator by hand from the code and mark it as transcribed.
- Free text: the invariants in the user's words ("no two confirmed orders share a seat", "a request executes at most once", "money captured is always either on a confirmed order or being refunded"), the parts of the system to include, bounds to use. These are the point of the exercise: a model with only `TypeOK` has not checked anything the user cares about.

## Procedure

Say in one line what you are about to do before each step. Tell the user what you are writing to the project before you write it.

### 0. Preflight

Check `jvmcontract --version`, TLC (`~/tools/tla2tools.jar`, `$TLA2TOOLS_JAR`, or `tlc` on the `PATH`), `java -version`, and which build the project uses.

- No `jvmcontract`: `cargo install --git https://github.com/pilifs/in-the-loop --locked jvmcontract` (`curl -fsSL https://terminalvalue.net/verify-bytecode-skill/install.sh | bash` installs everything).
- No TLC: `bash "${CLAUDE_SKILL_DIR}/scripts/install-tlc.sh"` downloads `tla2tools.jar` into `~/tools` (needs `java`). Without TLC you can still derive the contract and write the model, but nothing is checked, and the report says so.
- Note the state of the working tree (`git status`), so the user can see exactly what the skill added.

### 1. Find the compiled classes

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/find-classes.sh" . [module-dir]
```

It prints `BUILD` (maven, gradle or plain), `MODULE`, `CLASSES` (the module's class directories that exist, PATH-separated), `STALE` (1 if a source is newer than the classes), `CLASSPATH` (when a Maven `dependency:build-classpath` file is lying around) and `BUILD_CMD`, the command that compiles the module. If `CLASSES` is empty or `STALE=1`, run `BUILD_CMD`: it is the user's own project. If `derive` later refuses with a class it cannot find, the module has dependencies: get the classpath (Maven: `mvn dependency:build-classpath -Dmdep.outputFile=cp.txt`; Gradle: the init script of the `verify-bytecode` skill, `"${CLAUDE_SKILL_DIR}/../verify-bytecode/scripts/build.sh" . <module>` when that skill is installed) and pass it as `--classpath`.

### 2. Find the core logic

The kernel `jvmcontract tla` needs is a pure static method `decide(State, Input)` (the names are free) where `State` is an enum, `Input` is a sealed interface of records (or an enum) whose fields are booleans, enums or small ints, and the result is a sealed type with the cases `Transition(next, effects)`, `Unchanged(reason)` and `Rejected(reason)`, `effects` an enum. The exact shape, with a Java template, is in reference.md.

Look for it under the target the user gave, else in the main source set: enums that name states (`*Status`, `*State`, `*Phase`), `switch` statements over them, sealed interfaces of events or commands, classes named `*Lifecycle`, `*StateMachine`, `*Transitions`, `*Policy`, `*Coordinator`, `*Saga`, and the handlers that read a status and write another (`@Transactional` services, `@KafkaListener`s, `@Scheduled` sweepers, controllers returning 409). Read the Javadoc and the README for the rules the authors state ("every capture leads to CONFIRMED or to a refund"): those are invariants too. Then one of two cases:

- **A kernel of the right shape exists.** Confirm with `jvmcontract derive pkg.Class#decide --classes "$CLASSES"`: it prints `(N cases, M methods proven pure, ...)` and the table. A refusal names what is wrong (`input domain is not finite`: an `int` or `String` parameter; `is not known to be pure`: it reads a clock, a field, a collaborator). Fix nothing silently: show the user the refusal and what would make the method a kernel.
- **The logic is spread over handlers.** This is the usual case, and the extraction is the work. Propose the kernel: the state enum (it usually exists), one record per thing that can happen to an entity (a message, a command, a timer firing, a user action) with a boolean field for each fact the handler reads from the store before deciding (`seatsStillHeld`, `waitElapsed`), the effects enum (what the handler does after deciding: `SELL_SEATS`, `REQUEST_REFUND`, `PERMIT`), and `decide` as one total `switch` over `(state, input)`, moved line by line out of the handlers, which then become "load state, build the input from what they read, call `decide`, apply the effects, store the next state" in one transaction. Show the proposed types and the handler lines they replace, and **ask the user before editing** (`AskUserQuestion` when the session is interactive). With `--no-refactor`, or a no, write `Decide` by hand from the code into `<Name>Contract.tla`, mark the file and the README `transcribed, not generated`, and skip the regeneration in step 6.

Restrict to one kernel per run. A system with several state machines (orders and payments) gets the one whose invariants the user asked about; the other side is modelled as environment actions.

### 3. Derive the contract and generate the operator

```bash
mkdir -p "$SPEC"
jvmcontract derive 'pkg.Class#decide' --classes "$CLASSES" [--classpath "$CLASSPATH"] > "$SPEC/Class.decide.contract"
jvmcontract tla "$SPEC/Class.decide.contract" "$SPEC/ClassContract.tla"
jvmcontract statemachine "$SPEC/Class.decide.contract"     # Mermaid, for the README; names unreachable and terminal states
```

Read the contract once as a reviewer would: every row is one case the code decides, and a row that surprises you is either a bug to tell the user about now or a rule the model must respect. Rows with `null` are dropped by the generator; the model never passes null.

### 4. Write the model

`$SPEC/<Name>.tla` and `$SPEC/<Name>.cfg`, following the recipe and the skeleton in reference.md:

- `EXTENDS Naturals, Sequences, FiniteSets, <Name>Contract`.
- One **constant** per bound (customers, seats, attempts, threads, ticks, window size), small: two or three of each. The `.cfg` sets them; its comment says why these bounds are enough for the bugs the model is for.
- One **variable** per thing that persists between transactions: each store or table (as a function from id to record), each queue or topic (a sequence), each timer or clock (a natural), plus history variables for rules of the form "X never happened".
- One **action per transaction**, named after the Java operation it stands for, in a comment on the action: a handler's transaction, a relay's publish, a sweeper, a clock tick, a caller's request, the environment (a dependency going down, a message redelivered when delivery is at least once). Each action calls `Decide(state, input)` with the input built from the state exactly as the handler builds it, applies `next` and each effect to the variables the Java writes, and lists every other variable under `UNCHANGED`. Whatever the kernel leaves to its owner (a probe cap, a generation stamp, a retry limit) is written here explicitly and named in the README as the owner's rule.
- `Init`, `Next` (the disjunction, quantified over the constants), `Spec == Init /\ [][Next]_vars`, and with `--deadlock` a `Terminating` action that stutters when the system is meant to be finished.
- **Invariants**: `TypeOK` first (every variable in its type, with the bounds), then one per rule the user stated, each named for the rule and preceded by a one-line comment in the user's words, then the rules the Javadoc and the README of the code state. A rule about an event ("the breaker closes only after every probe completed") becomes a history variable set in the action and an invariant that it is never set.

Write for a reader who did not see the Java: the header comment says what is modelled, what each action stands for, and the simplifications, in the style of the models in this repository.

### 5. Check it

```bash
jvmcontract tlc "$SPEC/<Name>.tla" [--deadlock] [--json]
```

One worker, so the trace is the same on every run; `--json` gives the verdict, the state counts and the trace as data; the `.cfg` next to the `.tla` is read automatically. Then:

- **Unverifiable** with a message: fix the model. The messages you will see and what they mean are in reference.md (an unassigned variable is almost always an unparenthesised `x' = a \/ b`).
- **Violation**: read the trace against the Java, step by step. If the Java really allows it, it is a finding: show the trace as a sequence of Java operations and stop changing the model. If an action does something the Java does not, fix the action and say what was wrong. If the invariant is wrong as stated (the rule has an exception the user did not mention), restate it with the user and record the restatement in the README. Never weaken an invariant or remove an action to get to green without saying so in the report.
- **Verified**: confirm the invariants can fail at all. Break the model once on purpose (drop a guard, let a stale outcome count, apply a known bad kernel) and check that an invariant fires; then restore it. A model whose invariants cannot be violated by any change has checked nothing. Report the breakage you tried.

Keep each run under a minute by keeping the bounds small; a model that explores more than a few hundred thousand states usually has a bound that does not matter for the invariants.

### 6. Wire it into the build

So that the model is checked, and the operator regenerated, whenever the kernel changes:

- Copy `${CLAUDE_SKILL_DIR}/templates/check.sh` to `$SPEC/check.sh` and fill its header (classes directory, target, file names, `--deadlock`). It derives the contract from the current classes, fails with the diff if the committed contract changed (so a change in what the kernel decides is reviewed as a contract diff, then committed with `check.sh --update`), regenerates the operator and runs TLC. Run it once.
- Add the one call to the build that the project uses: a Gradle `Exec` task or a Maven `exec-maven-plugin` execution bound to `verify`, or a step in the CI workflow after the compile step; the snippets are in reference.md. Tell the user that TLC needs `tla2tools.jar` on the CI machine (`scripts/install-tlc.sh` does it) and that the whole check takes seconds.
- Write `$SPEC/README.md` from `${CLAUDE_SKILL_DIR}/templates/README.md`: the files, the invariants in words, what the model leaves out, how to run it, and what a pass means and does not mean. If the operator was transcribed rather than generated, say so there and in the operator file.

### 7. Report

Reply with: the kernel (found or extracted, and what changed in the Java if anything), the contract's size (`N cases`), the model's actions and what each stands for, the verdict with the state count and bounds (or the trace, rendered), the deliberate breakage that showed the invariants bite, every file written, and the one command to rerun it. Then the limits, plainly: the model's actions are hand-written against the Java; a pass holds for the model within its bounds; liveness ("every order eventually settles") is not checked unless the user asked and you added a temporal property. Do not pad a verified model: one line per invariant.
