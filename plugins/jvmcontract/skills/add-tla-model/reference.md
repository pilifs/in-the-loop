# TLA+ models around a jvmcontract kernel, for the agent writing one

The full documentation of the tool is the crate's [README](https://github.com/pilifs/in-the-loop/blob/main/lib/README.md); the five models in the repository ([Box Office](https://github.com/pilifs/in-the-loop/blob/main/examples/demo/apps/boxoffice/spec/BoxOffice.tla), [two-phase commit](https://github.com/pilifs/in-the-loop/blob/main/examples/demo/apps/quorum/spec/TwoPhaseCommit.tla), [Raft leader election](https://github.com/pilifs/in-the-loop/blob/main/examples/demo/apps/quorum/spec/RaftElection.tla) with action properties, an inductive invariant and a symmetry set, [idempotent receiver](https://github.com/pilifs/in-the-loop/blob/main/examples/demo/apps/crosscut/spec/IdempotentReceiver.tla), [class initialization](https://github.com/pilifs/in-the-loop/blob/main/examples/demo/apps/mica/spec/ClassInit.tla), and the [circuit breaker](https://github.com/pilifs/in-the-loop/blob/main/examples/demo/apps/crosscut/spec/CircuitBreaker.tla) written with this skill) are the style to follow. This is what you need while adding one.

## The kernel's shape

`jvmcontract tla` turns a behavioural contract into an operator when every case has the form `method(STATE, Input[field=value, ...]) => outcome`:

| Part | Java | In the contract | In TLA+ |
|---|---|---|---|
| state | an enum, the first parameter | `PENDING_PAYMENT` | the string `"PENDING_PAYMENT"` |
| input | a sealed interface of records (or an enum), the second parameter; record fields are booleans, enums or small ints | `PaymentCaptured[seatsStillHeld=true]` | the record `[kind |-> "PaymentCaptured", seatsStillHeld |-> TRUE]` |
| outcome | a sealed type with `Transition(S next, List<E> effects)`, `Unchanged(String reason)`, `Rejected(String reason)`; `E` an enum | `Transition[next=CONFIRMED, effects=[SELL_SEATS]]` | `[kind |-> "Transition", next |-> "CONFIRMED", effects |-> <<"SELL_SEATS">>]`; `Unchanged` and `Rejected` have `effects |-> <<>>` |
| an exception | `throw` | `throws IllegalStateException` | `[kind |-> "Throws", exception |-> "...", effects |-> <<>>]` |

The method must be `static` and pure (`derive` proves it: no clock, no field read, no collaborator), and its domain finite; `derive` prints `(N cases, M methods proven pure, trusting ...)` or a refusal (`input domain is not finite`, `is not known to be pure`, `reads static field`). Rows where the state or the input is `null` are left out of the operator. A template, with the names of the Crosscut module (`Decision<S, E>` is generic and reusable as is):

```java
public sealed interface Decision<S extends Enum<S>, E extends Enum<E>> {
    record Transition<S extends Enum<S>, E extends Enum<E>>(S next, List<E> effects) implements Decision<S, E> {}
    record Unchanged<S extends Enum<S>, E extends Enum<E>>(String reason) implements Decision<S, E> {}
    record Rejected<S extends Enum<S>, E extends Enum<E>>(String reason) implements Decision<S, E> {}
}

public enum OrderStatus { PENDING_PAYMENT, CONFIRMED, DECLINED, REFUND_PENDING, REFUNDED }
public enum Effect { SELL_SEATS, RELEASE_SEATS, REQUEST_REFUND }

/** One record per thing that can happen to an order; a boolean per fact the handler reads before deciding. */
public sealed interface OrderInput {
    record PaymentCaptured(boolean seatsStillHeld) implements OrderInput {}
    record PaymentDeclined() implements OrderInput {}
    record CancellationRequested() implements OrderInput {}
}

public final class OrderLifecycle {
    /** A total function: every (status, input) has exactly one row. */
    public static Decision<OrderStatus, Effect> decide(OrderStatus status, OrderInput input) {
        return switch (input) {
            case PaymentCaptured c -> switch (status) {
                case PENDING_PAYMENT -> c.seatsStillHeld()
                        ? new Decision.Transition<>(CONFIRMED, List.of(SELL_SEATS))
                        : new Decision.Transition<>(REFUND_PENDING, List.of(REQUEST_REFUND));
                case CONFIRMED, REFUND_PENDING, REFUNDED -> new Decision.Unchanged<>("payment already recorded");
                case DECLINED -> new Decision.Transition<>(REFUND_PENDING, List.of(REQUEST_REFUND));
            };
            // ...
        };
    }
}
```

The handler then does, in one transaction: load the status, read the facts, build the input, call `decide`, apply each effect, store `next`. Whatever it does besides (caps, counters, timers, which outcomes it reports) is the owner's rule, and the model writes it down.

The commands:

```bash
jvmcontract derive 'pkg.Class#decide' --classes CLASSES [--classpath 'a.jar:b.jar'] [--json] > spec/Class.decide.contract
jvmcontract tla spec/Class.decide.contract spec/ClassContract.tla [--module NAME] [--operator Decide]
jvmcontract statemachine spec/Class.decide.contract [--format dot]      # Mermaid by default; names unreachable and terminal states
jvmcontract tlc spec/Model.tla [--deadlock] [--coverage] [--json] [--timeout 1800] [--workers 1] [--library DIR]
```

`tlc` runs TLC from `tla2tools.jar` (`$TLA2TOOLS_JAR`, else `~/tools/tla2tools.jar`, else `tlc` on the `PATH`) in the spec's directory, reading the `.cfg` of the same name, with one worker so the reported trace is stable, and `-deadlock` *off* unless `--deadlock` is given (a finished system is meant to stop). Exit code 0 is verified, 1 a violation or no verdict. `--json` prints `verdict` (`"Verified"`, `"Violation"`, `"Unverifiable"`), `invariant` (the invariant or property violated), `kind` (`invariant`, `deadlock`, `action` or `temporal`), `deadlock`, `properties` (the configuration's `PROPERTIES`), `states_generated`, `distinct_states`, `depth`, `seconds`, `trace` (a list of `{step, action, changes}`, `changes` being only the variables that changed), `lasso` and `stuttering` (for a temporal violation: the step the behaviour returns to, or that it stays in the last state forever) and `output`. `--library` is only for a project that commits copies of the standard modules; the jar has them.

## The model, as a recipe

```tla
---------------------------- MODULE Orders ----------------------------
(* What is modelled, one action per transaction of which Java operation, the simplifications. *)
EXTENDS Naturals, Sequences, FiniteSets, OrderLifecycleContract

CONSTANTS Customers, Seats, MaxTime       \* the bounds; the .cfg sets them

VARIABLES order,      \* customer -> status, or "NONE"            (the orders table)
          seat,       \* seat -> [status, holdId]                 (the seats table)
          events,     \* the topic payments.events, a sequence of [kind, order]
          time        \* the clock
vars == <<order, seat, events, time>>

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect

\* PaymentEventHandler.handle: one event, one transaction.
HandleEvent ==
    /\ events # <<>>
    /\ LET m == Head(events)
           c == m.order
           d == Decide(order[c], [kind |-> m.kind, seatsStillHeld |-> HeldBy(c) = hold[c].seats])
       IN /\ events' = Tail(events)
          /\ order' = IF d.kind = "Transition" THEN [order EXCEPT ![c] = d.next] ELSE order
          /\ seat' = IF Has(d, "SELL_SEATS") THEN Sold(c) ELSE IF Has(d, "RELEASE_SEATS") THEN Released(c) ELSE seat
    /\ UNCHANGED time

Tick == time < MaxTime /\ time' = time + 1 /\ UNCHANGED <<order, seat, events>>

Init == order = [c \in Customers |-> "NONE"] /\ seat = [s \in Seats |-> Available] /\ events = <<>> /\ time = 0
Next == HandleEvent \/ Tick \/ \E c \in Customers : PlaceOrder(c)
Spec == Init /\ [][Next]_vars

TypeOK == /\ \A c \in Customers : order[c] \in {"NONE", "PENDING_PAYMENT", "CONFIRMED", "DECLINED", "REFUND_PENDING", "REFUNDED"}
          /\ time \in 0..MaxTime

\* No double sale: two confirmed orders never share a seat.
NoDoubleSale == \A c1, c2 \in Customers : c1 # c2 /\ order[c1] = "CONFIRMED" /\ order[c2] = "CONFIRMED"
                    => hold[c1].seats \cap hold[c2].seats = {}
=============================================================================
```

```
\* Orders.cfg: why these bounds are enough for the bugs the model is for.
SPECIFICATION Spec
CONSTANTS
    Customers = {alice, bob}
    Seats = {s1}
    MaxTime = 3
INVARIANTS
    TypeOK
    NoDoubleSale
```

Variables: a function `[id \in Ids |-> record]` for a table, a sequence for a queue or topic (`Append`, `Head`, `Tail`, `Len`), a set for an unordered inbox or a set of threads, a natural for a clock or counter, a string for an enum. The state machine's current state lives in the table (`order[c]`); the operator reads it and returns the next.

Actions: a guard (the enabling condition, what the handler checks or what must be in the queue), then the `LET d == Decide(...)` with the input built exactly as the Java builds it, then one conjunct per variable the Java writes (`x' = ...`), then `UNCHANGED <<every other variable>>`. A transaction is one action: if the Java reads, decides and writes in one transaction, the model does it in one step; if it does not (a read, then a write in another transaction), split the action and let anything interleave between them, because that is where the bugs are.

Environment: anything the system does not control is an action with no guard but a bound: the clock ticks, a dependency goes down or comes back, a message is redelivered (at-least-once delivery: `events' = Append(events, Head(events))` with a count to bound it), a request arrives, a timeout fires before the reply.

Invariants: `TypeOK` always. A rule over the state as it is now is a state predicate (`NoDoubleSale`). A rule about something that must never *happen* ("a call is never permitted while the breaker is open") is a history variable: a boolean set in the action when it happens, never reset, with the invariant `~happened`; or, when the rule counts what happened ("at most one leader elected per term", "one vote per server per term"), a set the steps add to, below. When the rule is about one step, what a variable may change into ("a leader never becomes a candidate", "a term never decreases"), an action property says it directly, `[][\A s \in Servers : role[s] = "LEADER" => role'[s] # "CANDIDATE"]_vars` under `PROPERTIES`; TLC checks it on every step, reports it by name (`Error: Action property NAME is violated.`), and the counterexample is the run up to the offending step. Prefer it to a history variable when both states of the step are legal and only the step is not. A rule "when X, then Y eventually" is liveness: a temporal property (`X ~> Y`, or `<>Y`) under fairness conditions in `Spec` (`WF_vars(Action)` for each action a part of the system is assumed to get round to, never for the environment's choices), listed under `PROPERTIES` in the `.cfg`. `jvmcontract tlc` checks it after the invariants and reports the counterexample as a prefix and how it goes on forever (stuttering, or a loop back to an earlier step). Prefer safety where it exists ("whenever nothing is in flight, the two services agree": `Quiet => Agreement`), and state liveness only for what the protocol promises to reach. A refinement, that the model implements a more abstract specification, is `Abs == INSTANCE AbstractModule` with `Refines == Abs!AbsSpec` under `PROPERTIES`; TLC checks it step by step as an action property. Symmetry sets are unsound with temporal properties, so leave `SYMMETRY` out of a configuration that has them.

A model can have more than one configuration: `jvmcontract tlc Spec.tla --config Other.cfg` runs the same module under other constants, under a symmetry set (`Perms == Permutations(Servers)` in the module, which needs `EXTENDS TLC`, and `SYMMETRY Perms` in the configuration; the constants must be model values), or as an inductive check. For the inductive check, write the inductive invariant `Inductive` (the invariant you want, strengthened until one step from any state it admits lands in a state it admits: what the tallies, votes and terms must agree on for the property to hold), an enumerable version `InductiveInit` (each variable drawn from its type, each conjunct right after the last variable it mentions, so that TLC prunes partial states early; keep the admitted states in the tens of thousands), and a configuration with `INIT InductiveInit`, `NEXT Next` and the conjuncts under `INVARIANTS` one by one, so that TLC names the one that fails. No counterexample proves the property by induction for runs of any length; a counterexample is one step from a state that need not be reachable, so run the ordinary configuration too to tell a bug from a conjunct that is too strong. A conjunct that a correct change can break (one about a role's tally that the change gives to another role, say) is too strong; keep each as weak as inductiveness allows. For a model with messages, the conjuncts that make the invariant inductive say what a message in flight means about its sender and the receiver (a vote in the inbox has not been counted; its sender's state agrees with it); the two-phase-commit model's `Inductive` admits 736 states against 728 reachable. In `build.py`, a model lists its extra configurations under `configurations`, each with a `label` and a `what`, and an example's verdict is the first configuration that fails; an invariant a starting state of the inductive check violates outright is reported as such.

A kernel that throws on an input it holds impossible (`throws IllegalStateException` in the contract, `[kind |-> "Throws", ...]` in the generated operator) is making a claim about the protocol. Have each action's next-state record carry a `throws` field (`d.kind = "Throws"` over the decisions it goes through), guard the action with `~XNext(...).throws`, and state the invariant `KernelNeverThrows`, that for every timer and RPC a state allows no decision throws, under `INVARIANTS` in every configuration. A change that makes the kernel throw on a reachable input then fails with the run that delivers it, and the inductive configuration says whether `Inductive` implies the claim.

A model can use more than one generated operator. Generate each into its own module (`jvmcontract tla VoteRule.decide.contract spec/VoteRuleContract.tla`) and bring the second in as a named instance, `Vote == INSTANCE VoteRuleContract`, used as `Vote!Decide(status, input)`: both modules define `Decide`, `Transition`, `Unchanged` and `Rejected`, which `EXTENDS` cannot take twice. In `build.py`, list it under the model's `operators` (contract, operator, symbol), so that it is regenerated from the patched code and an example whose subject is the second kernel finds the model. What the Java computes around a kernel to feed it (how a term, an id or a log compares with the server's own) the model repeats in TLA+ and hands to the operator, so a change there changes the Java and not the model: cover that arithmetic with property proofs. A constant the configuration cannot write as a value (a function, such as a log per server) is an operator in the module over a set the configuration can give (`Logs == [s \in Servers |-> IF s \in LeftBehind THEN ... ELSE ...]`, `LeftBehind = {s1}` in the `.cfg`, `{}` in the others); a property that such a constant decides (leader completeness for the logs given) is a witness for those values, and the README should say so.

Liveness of a model with a generated state machine: on a model of a few hundred states or fewer, plain `WF_vars(A)` on each action a part of the system is assumed to get round to is fine (the circuit-breaker model's four conditions check in a second over 102 states). On a bigger one, state the fairness conditions as weak fairness written out, `<>[]CanA => []<><<A>>_vars`, with `CanA` a state predicate (the action's guard, and that its step changes some variable), rather than as `WF_vars(A)`. TLC computes `ENABLED` of an action that evaluates the generated `Decide` symbolically, once per step of the liveness check, and `WF_vars` on three such actions took it a minute on 610 states where the written-out form takes a second; have each action compute its next state as a record (`TimeoutNext(s)`, then `Step(TimeoutNext(s))` for the action and `Changes(TimeoutNext(s))` for the predicate), and keep a configuration with the invariant `CanA <=> ENABLED <<A>>_vars` to run after changing an action. A bounded model cannot state that a leader is elected within any number of terms; condition the property on the bound (`[](\A s : currentTerm[s] < MaxTerm) => <>Leader`) and check that the stronger property a reader might expect fails, so the proof is not vacuous. No symmetry set in a liveness configuration: TLC's liveness checking is unsound under one. Write one property per fate of the environment the protocol answers to (the dependency behind a breaker comes back for good, or stays down for good: `<>[]Up => <>[]Closed`, `<>[]Down => []<>Open`), and assume nothing of the environment in the fairness conditions; a rule can satisfy the properties written for one fate and fail the one written for the other.

An action of the environment the model leaves out (a record's time to live passing, a timer firing, a message lost) leaves the kernel's rows for it dead: `jvmcontract tlc --coverage` lists them as never taken, and a change to them verifies vacuously. Put the action in the model behind a constant (`Expires \in BOOLEAN`, `/\ Expires` as the action's first conjunct) and give it its own configuration, so the first configuration keeps the stronger statement it could make without the action (at most once outright) and the second states what holds with it (at most once per lifetime of the record, the count starting over when the record is released). Without a clock the action can fire at any point, which is the honest model of a sweeper whose clock measures age and nothing else. Check the invariants a new action can undo: an invariant that compares something a client was answered earlier with the store now (`replayed => stored`) raises a false alarm once the store can be emptied after the reply, so state it at the moment it happens, by recording in the action what the client was answered with (`IF stored THEN "REPLAYED" ELSE "EMPTY"`) and forbidding the bad value (`\A a : responses[a] # "EMPTY"`).

A message the model delivers in one step is the same kind of omission: an RPC written as one action, the request and its reply together, means a server always answers with the term it has now and the asker takes the answer at once, so the kernel's rows for a reply from a term the asker has left are dead. Split the RPC in two behind a constant (`DelayedReplies`): the voter's half puts the reply in a set with the term it was answered in, the asker's half takes it whenever the model likes, and the one-step action stays, guarded by `~DelayedReplies`, so that the other configurations keep their state counts. Quantify the taking action over the servers (`Answer(c, v)`, with `CHOOSE` on the set inside) rather than over the set of replies, so that TLC names it in traces; bound to one outstanding reply per pair; add the new actions to the invariant that no reachable state lets the kernel throw; and bound the configuration to what the rows need (the Raft election with replies on the wire has 364,236 states at three terms and 20,351 at two, and a reply from term 1 taken in term 2 is all the configuration is for).

A rule the paper states about a whole run, which the state forgets, is the third: "at most one leader can be elected in a given term" holds of every state in a run in which the term's leader steps down and the term then elects another, and "a server votes for at most one candidate per term" cannot be seen once the voter moves to a newer term and its vote is gone. Add history variables of the set kind, `elected`, every `<<server, term>>` the server has led in, and `voted`, every `<<voter, term, candidate>>`, which each step extends with the leaders and the votes of the state it lands in (`elected' = elected \cup Led(n.role, n.currentTerm)`, a set, so a state that changes nothing adds nothing), and state the rule over the set (`\A e, f \in elected : e[2] = f[2] => e[1] = f[1]`). A history variable changes nothing about the run of the variables it is added to (Lamport and Merz, Auxiliary Variables in TLA+); it multiplies the states, each now carrying its history, so gate the recording behind a constant (`History`), on in one configuration, so that the others keep their state counts and the headline of every existing example stays the first violation its own configuration finds. Keep the `Changes` predicate the fairness conditions use over the state proper, not over `vars`. Leave the history out of the inductive configuration: the state does not determine it, so the inductive invariant says nothing about it, and the run-based configuration is the check.

A crash of a part that logs its state is a configuration of the same kind, with its own generated operator for what the part does on restart (`Recovery == INSTANCE RecoveryContract`, from a kernel `Recovery.decide(logged, Restarted)`). Add a `MaxCrashes` constant (`0` in the existing configurations, which then keep their state counts), an `up` variable and a count, a `Crash` action between steps, a crash branch inside the step that applies a decision (`phase' = d.next`, the logged part, with the broadcast lost and `up' = FALSE`), and a `Recover` action that hands the logged state to the recovery operator and applies its decision through the same step, so that a restart can be cut short too; put `WF_vars(Recover)` in `Fairness` and bound the crashes, since an unbounded crash loop is a behaviour no fairness forbids. Weaken the inductive conjunct that tied the broadcast to the logged phase to `decision \in {"NONE", ...}`, add one for what a restart must restore (`up /\ decided => decision # "NONE"`), and one that says the part is down only after a crash, so that the inductive configuration without crashes admits the same states as before and a second one, with `MaxCrashes = 1` and the part up or down in the initial predicate, proves the recovery rule by induction. A restart that aborts whatever was logged breaks the invariant that a participant commits only on the coordinator's say-so; a restart with nothing to redo breaks the restored conjunct by induction and the liveness property over a run, which is the headline when the run-based configuration is listed first.

Trace validation turns the model on the glue around the kernel, which the model otherwise takes on trust (that the log is written before the broadcast, that a crash loses nothing logged, that the tally the rule decides on is the tally). Write the nodes as a real system is written, with the kernel called where the model's action names it, a durable log, a network, and a fault injector that kills a node after any I/O operation (`faults.io()` after each log write and send, so that a scripted crash falls between any two). A test-side writer runs them through scripted scenarios, with the crashes where the model's crash configuration puts them, records the state after each step in the model's variables, as TLA+ records with one field per variable, and prints a module `Traces == << <<state, ...>>, ... >>` with a `Names` sequence beside it. The trace specification `EXTENDS` the model and the recorded runs, adds variables `run`, `step` and `scenario`, loads the first recorded state in its `Init` (`run \in 1..Len(Traces)`, one behaviour per run) and the next one in its `Next` (written out with primes, `phase' = s.phase /\ ...`: TLC does not prime an operator application), and lists `[][Next]_vars` of the model as a `PROPERTY`, an action property, with `step = 1 => Init` as an invariant. A recorded step the model has no action for is reported as the action property's counterexample, with the run and the state. Coverage is not attributed to a next-state relation evaluated as an action property, so run the configuration without it. Record the node's state from memory while it is up and from its log while it is down, so that a change that stops logging what the model says is logged shows at the crash. A scripted step is one recorded step: a crash scheduled after an I/O operation the node no longer performs, or performs for nothing, lands elsewhere, which is either a finding about the glue or a gap in the model (a restart with nothing to do, cut short by a crash, was two steps of the two-phase-commit model until `Perform` let a crash fall in any step). The check covers the scripted runs and no others; say so on the page, and keep the model's own configurations as the ones that cover every interleaving. When a second kind of process gains a log and a rule (the two-phase-commit participants), give it its own fault injector and crash budget (`MaxParticipantCrashes`, a `pup` function and a `pcrashes` count beside the coordinator's `up` and `crashes`), route every one of its actions through the generated operator with one `Act(p, d)` that logs the new state and sends what the effects say, with a crash branch after the log write in which the send may or may not have happened, and keep the inductive invariant honest about what a crash can leave behind (a prepared participant whose vote was lost: `PREPARED => VotedYes \/ (pcrashes > 0 /\ ~VotedNo)`), so that the configurations with the new budget at zero keep their state counts and the old examples their verdicts.

Deadlock: with `--deadlock`, a state with no enabled action is reported like a violation. A system that is meant to stop needs `Terminating == Done /\ UNCHANGED vars` in `Next`, and a waiting thread must have no enabled self-loop or TLC sees a successor and no deadlock.

Bounds: two of everything that can conflict (two customers, two threads, two attempts) plus one more where "the third one arrives late" matters; a clock of three or four ticks; a window or queue of two or three. State counts: the Box Office model has 3,604 states at two customers and one seat (two seconds) and about a hundred thousand at two seats and five ticks (under a minute); the idempotent receiver 168 states, the circuit breaker 102, class initialization with three threads a few hundred. A model past a million states has a bound that does not matter for the invariants.

## TLA+ that bites

- `x' = a \/ b` parses as `(x' = a) \/ b`. When `b` is true, `x'` is unassigned and TLC says `Successor state is not completely specified by action A of the next-state relation. The following variable is not assigned: x`. Write `x' = (a \/ b)`. The same for `/\` inside a longer expression: parenthesise the right-hand side of every `'=`.
- Every variable must be assigned in every action, by a primed conjunct or `UNCHANGED`. The message above names the one you forgot.
- `CASE` with no matching arm is an evaluation error (`Attempted to evaluate CASE with no matching arm` is not what TLC says; it says the arm set is incomplete, naming `Decide`). It means the model built an input the contract has no row for: a field misspelt, a `kind` the sealed type does not have, a boolean passed as a string. Compare the record literal with the arms of `<Name>Contract.tla`.
- Strings and records do not compare: `order[c] = "NONE"` is fine, but `order[c] = [kind |-> ...]` against a string is an error (`Attempted to check equality of string and record`). A table whose entries are records needs a record for "absent" too, or a separate set of present keys.
- `Seq(S)` is infinite: `x \in Seq(BOOLEAN)` is fine as a membership test in `TypeOK`, but never put `Seq(S)` in `Init` or quantify over it.
- `Nat` is fine in an invariant (`n \in Nat`) and never in `Init` or a `\E`.
- Model values: `Customers = {alice, bob}` in the `.cfg` gives abstract values that compare only to themselves; a string `"alice"` in the `.tla` is a different value. Use strings for enum states and effects, model values for ids.
- `EXCEPT` on a function: `[f EXCEPT ![k] = v]`, and `![k].field = v` for a record inside; `@` is the old value (`![c] = @ + 1`).
- Functions versus records: `[s \in Seats |-> ...]` is a function, `[status |-> "HELD"]` a record; `f[s]` and `r.status`.
- `Cardinality` needs `FiniteSets`; `Append`, `Head`, `Tail`, `Len`, `<<>>` need `Sequences`; `..`, `+`, `<` need `Naturals`.
- An operator used before its definition is an error: define `Has`, `HeldBy` and friends above the actions.
- A `\* comment` ends at the line; `(* ... *)` nests.
- Names: the module name must equal the file name; the `.cfg` has the same stem as the `.tla`.

## Reading TLC

`jvmcontract tlc` prints one line of verdict and the trace:

```
✓ every invariant holds in 102 distinct states, depth 19, in 0 s (TLC 2.19)

✗ invariant ClosedOnlyAfterEveryProbe is violated after 10 steps, depth 10, in 0 s (TLC 2.19)
  1. Initial predicate: closedEarly = FALSE, current = 0, dependency = "DOWN", ...
  2. Request: current = 1
  ...
  10. Complete: closedEarly = TRUE, current = 0, state = "CLOSED"

✗ temporal property EveryParticipantDecides is violated: after 6 steps the system stays in that state forever, in 0 s (TLC 2.19)
  ...                                                     # or: returns to step 4 and repeats steps 4 to 6 forever

⚠ TLC produced no verdict: Finished in 00s at (...)      # read `output` in --json for the Error: line
```

A trace step names the action and the variables it changed. Render it for the reader as Java operations: "step 8: `tryAcquirePermission` after the wait, one probe permitted (`Request`, HALF_OPEN)". The step count includes the initial state. The depth of a verified search is the longest behaviour explored.

`--coverage` adds, after the verdict, what it rests on: for each generated operator the specification uses (found by the header `jvmcontract tla` writes), how many rows of its contract a step of the model took, and the rows no step took:

```
Rows of net.terminalvalue.quorum.raft.VoteRule#decide a step of the model takes: 4 of 27; never taken (23):
  decide(OPEN, VoteRequest[term=OLDER, log=BEHIND]) => Rejected
  ...
```

It is TLC's `-coverage` read back against the `CASE` arms: an arm's guard is evaluated when no earlier arm matched, so an arm was taken as often as its guard was evaluated minus the next arm's, summed over the actions that evaluate the operator (an invariant that evaluates it, such as `KernelNeverThrows`, takes no step and is not counted). TLC's report folds a subtree whose counts are all equal into one line, which an action that always takes the same arm would be; the generated module's first arm therefore starts with `(\A i \in {1, 2} : i = i) /\`, a conjunct TLC evaluates twice, which keeps the counts unequal and the arms listed (regenerate operators written before this with `jvmcontract tla`, or the report shows rows as never taken that are). In `--json` it is `coverage`, one entry per operator with `rows[].case`, `outcome` and `taken`. A row no step takes is one the model says nothing about, whatever the verdict: a change to the Java that lands only on such rows is verified vacuously. Read a verified verdict with the rows the change altered (the contract diff) against this list; a row that is never taken because of an abstraction the model made (atomic RPCs never ask a voter twice; a tally counted in the step that fills it never arrives late) needs a test, a property, or a bigger model. A row that *throws* and is never taken is the opposite case, what the change asked for, and an invariant such as `KernelNeverThrows` is what proves no run can take it. A run that stops at a counterexample has explored a part of the model, and its counts say little.

`Unverifiable` with `output` saying `Parsing or semantic analysis failed` or `***Parse Error***`: a syntax error, with line and column. `Error: Successor state is not completely specified`: see above. `Error: TLC threw an unexpected exception` with `OutOfMemoryError`: shrink the bounds. `did not finish within N s`: shrink the bounds or raise `--timeout`.

## Wiring the check into a build

`check.sh` (from the template) is the one entry point. Call it from the build after the main classes are compiled:

Gradle (`build.gradle.kts`):

```kotlin
val checkModel by tasks.registering(Exec::class) {
    dependsOn(tasks.compileJava)
    commandLine("bash", "spec/check.sh")
}
tasks.check { dependsOn(checkModel) }
```

Maven (`pom.xml`, in `<build><plugins>`):

```xml
<plugin>
  <groupId>org.codehaus.mojo</groupId>
  <artifactId>exec-maven-plugin</artifactId>
  <version>3.5.0</version>
  <executions>
    <execution>
      <id>check-model</id>
      <phase>verify</phase>
      <goals><goal>exec</goal></goals>
      <configuration><executable>bash</executable><arguments><argument>spec/check.sh</argument></arguments></configuration>
    </execution>
  </executions>
</plugin>
```

GitHub Actions, after the build step:

```yaml
- run: curl -fsSL https://terminalvalue.net/verify-bytecode-skill/install.sh | NO_RUST=1 bash   # the skill and TLC; or cargo install jvmcontract
- run: bash spec/check.sh
```

The whole check is `derive` (milliseconds), `tla` (milliseconds) and TLC (seconds for a few thousand states).
