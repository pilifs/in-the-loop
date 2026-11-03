---------------------------- MODULE CircuitBreaker ----------------------------
(***************************************************************************)
(* A circuit breaker as a system: the component that owns the breaker      *)
(* (Resilience4j's CircuitBreakerStateMachine, or the @CircuitBreaker      *)
(* aspect), the calls it lets through to a dependency that is up or down,  *)
(* the sliding window of their outcomes, the probes of the half-open       *)
(* state, and the clock that ends the open state's wait. TLC explores      *)
(* every interleaving within the bounds in CircuitBreaker.cfg and checks   *)
(* the invariants in every state it reaches; under CircuitBreakerLive.cfg  *)
(* it checks the three liveness properties at the end of the module, under *)
(* the fairness conditions of LiveSpec.                                    *)
(*                                                                         *)
(* The breaker's decision rule, Decide(state, event), is not written here. *)
(* It is generated from the behavioural contract of CircuitBreaker#decide  *)
(* (CircuitBreakerContract.tla), which jvmcontract proves the bytecode     *)
(* obeys on every input. The owner's part, which the kernel leaves to it,  *)
(* is written here: the window, the probe cap, the wait timer, and which   *)
(* outcomes it reports.                                                    *)
(*                                                                         *)
(* Simplifications: the window is count-based; a call fails exactly when   *)
(* the dependency is down; the owner stamps each permitted call with the   *)
(* metrics generation and drops the outcome of a call from an earlier      *)
(* generation (one permitted before the breaker opened, or before the      *)
(* probes started), which is what the OPEN rows of the kernel assume; a    *)
(* request that would exceed the probe cap is refused by the owner and is  *)
(* not modelled.                                                           *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, CircuitBreakerContract

CONSTANTS
    WindowSize,       \* calls recorded before CLOSED judges the failure rate (slidingWindowSize)
    FailureRate,      \* percentage of failures at or above which the breaker opens (failureRateThreshold)
    PermittedProbes,  \* calls let through in HALF_OPEN (permittedNumberOfCallsInHalfOpenState)
    WaitDuration,     \* ticks the breaker stays OPEN before it probes (waitDurationInOpenState)
    MaxInFlight       \* calls the caller can have outstanding at once; a bound on the model, not a setting

VARIABLES
    state,        \* the breaker: CLOSED, OPEN or HALF_OPEN
    dependency,   \* the service behind the breaker: UP or DOWN
    window,       \* the outcomes of the current metrics generation, oldest first; TRUE is a failure
    current,      \* permitted calls in flight that belong to the current metrics generation
    stale,        \* permitted calls in flight from an earlier generation; their outcomes are dropped
    waitLeft,     \* ticks left of the open state's wait; 0 means elapsed
    probedEarly,  \* history: a call was ever permitted while OPEN before the wait elapsed
    closedEarly   \* history: the breaker ever closed before every permitted probe had completed

vars == <<state, dependency, window, current, stale, waitLeft, probedEarly, closedEarly>>

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect
Failures(w) == Cardinality({i \in 1..Len(w) : w[i]})
Exceeded(w) == Len(w) > 0 /\ Failures(w) * 100 >= FailureRate * Len(w)

\* The sliding window: once full, the oldest outcome leaves as the newest arrives.
Record(w, failed) == IF Len(w) < WindowSize THEN Append(w, failed) ELSE Append(Tail(w), failed)

\* How many outcomes the current state needs before it judges the window.
Needed == IF state = "HALF_OPEN" THEN PermittedProbes ELSE WindowSize

(***************************************************************************)
(* The owner of the breaker.                                               *)
(***************************************************************************)

\* tryAcquirePermission: a caller asks for a call. The owner reports whether the wait has elapsed, and in
\* HALF_OPEN lets only PermittedProbes calls through. It applies whatever the kernel returns: PERMIT lets the
\* call through, RESET_METRICS starts a new generation (the window is cleared and the calls still in flight
\* become stale), START_WAIT starts the open state's wait, or starts it over.
Request ==
    /\ current + stale < MaxInFlight
    /\ state = "HALF_OPEN" => Len(window) + current < PermittedProbes
    /\ LET d == Decide(state, [kind |-> "CallRequested", waitElapsed |-> (waitLeft = 0)])
           reset == Has(d, "RESET_METRICS")
       IN /\ state' = IF d.kind = "Transition" THEN d.next ELSE state
          /\ window' = IF reset THEN <<>> ELSE window
          /\ stale' = IF reset THEN stale + current ELSE stale
          /\ current' = IF Has(d, "PERMIT") THEN (IF reset THEN 1 ELSE current + 1) ELSE current
          /\ waitLeft' = IF Has(d, "START_WAIT") THEN WaitDuration ELSE waitLeft
          /\ probedEarly' = (probedEarly \/ (state = "OPEN" /\ waitLeft > 0 /\ Has(d, "PERMIT")))
    /\ UNCHANGED <<dependency, closedEarly>>

\* onResult, for a call of the current generation: the owner records the outcome, judges the window, and
\* reports both to the kernel. START_WAIT starts the timer and ends the generation; RESET_METRICS starts a new
\* one, here as on a request.
Complete ==
    /\ current > 0
    /\ LET failed == (dependency = "DOWN")
           w == Record(window, failed)
           d == Decide(state, [kind |-> "CallCompleted", failed |-> failed,
                                windowComplete |-> (Len(w) >= Needed), thresholdExceeded |-> Exceeded(w)])
           opens == Has(d, "START_WAIT")
           reset == Has(d, "RESET_METRICS")
       IN /\ state' = IF d.kind = "Transition" THEN d.next ELSE state
          /\ window' = IF reset THEN <<>> ELSE w
          /\ current' = IF opens \/ reset THEN 0 ELSE current - 1
          /\ stale' = IF opens \/ reset THEN stale + current - 1 ELSE stale
          /\ waitLeft' = IF opens THEN WaitDuration ELSE waitLeft
          /\ closedEarly' = (closedEarly \/ (state = "HALF_OPEN" /\ state' = "CLOSED" /\ Len(w) < PermittedProbes))
    /\ UNCHANGED <<dependency, probedEarly>>

\* onResult, for a call from an earlier generation: dropped.
CompleteStale ==
    /\ stale > 0
    /\ stale' = stale - 1
    /\ UNCHANGED <<state, dependency, window, current, waitLeft, probedEarly, closedEarly>>

(***************************************************************************)
(* The environment.                                                        *)
(***************************************************************************)

\* The wait timer.
Tick ==
    /\ waitLeft > 0
    /\ waitLeft' = waitLeft - 1
    /\ UNCHANGED <<state, dependency, window, current, stale, probedEarly, closedEarly>>

\* The dependency goes down, or comes back.
DependencyFlips ==
    /\ dependency' = IF dependency = "UP" THEN "DOWN" ELSE "UP"
    /\ UNCHANGED <<state, window, current, stale, waitLeft, probedEarly, closedEarly>>

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ state = "CLOSED"
    /\ dependency \in {"UP", "DOWN"}
    /\ window = <<>>
    /\ current = 0
    /\ stale = 0
    /\ waitLeft = 0
    /\ probedEarly = FALSE
    /\ closedEarly = FALSE

Next == Request \/ Complete \/ CompleteStale \/ Tick \/ DependencyFlips

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

TypeOK ==
    /\ state \in {"CLOSED", "OPEN", "HALF_OPEN"}
    /\ dependency \in {"UP", "DOWN"}
    /\ window \in Seq(BOOLEAN) /\ Len(window) <= WindowSize
    /\ current \in 0..MaxInFlight /\ stale \in 0..MaxInFlight /\ current + stale <= MaxInFlight
    /\ waitLeft \in 0..WaitDuration
    /\ probedEarly \in BOOLEAN /\ closedEarly \in BOOLEAN

\* An open breaker lets nothing through until its wait has elapsed.
NoCallBeforeTheWait == ~probedEarly

\* While open, the dependency receives no call of the current generation: everything in flight was
\* permitted before the breaker opened.
OpenShieldsTheDependency == state = "OPEN" => current = 0

\* Half-open closes only once every permitted probe has completed: one good probe is not evidence enough.
ClosedOnlyAfterEveryProbe == ~closedEarly

\* Half-open lets at most PermittedProbes calls through, in flight or completed, before it decides.
ProbesAreLimited == state = "HALF_OPEN" => Len(window) + current <= PermittedProbes

\* A closed breaker never sits on a complete window whose failure rate is at the threshold: it opens on the
\* call that completes it.
ClosedOnlyBelowTheThreshold == state = "CLOSED" => ~(Len(window) = WindowSize /\ Exceeded(window))

(***************************************************************************)
(* Liveness. Checked by CircuitBreakerLive.cfg: the invariants above say   *)
(* what the breaker never does, these say what it eventually does.         *)
(***************************************************************************)

\* Fairness: what the model assumes gets round to happening. The caller keeps calling, which is what an open
\* breaker rejects and a half-open one probes with; every permitted call completes; and the clock ticks.
\* Nothing is assumed of the dependency: whether it comes back, or stays down, is the premise of each property
\* below, not an assumption of the model. Each condition is weak fairness: an action enabled from some point on
\* is eventually taken. The model is small enough for TLC to compute ENABLED of these actions as it goes.
Fairness ==
    /\ WF_vars(Request)
    /\ WF_vars(Complete)
    /\ WF_vars(CompleteStale)
    /\ WF_vars(Tick)

LiveSpec == Spec /\ Fairness

\* An open breaker does not stay open: its wait elapses, and the next call is let through as a probe.
AnOpenBreakerProbesAgain == (state = "OPEN") ~> (state = "HALF_OPEN")

\* A dependency that comes back for good is used again: from some point on the breaker is closed and stays so.
ARecoveredDependencyIsUsed == <>[](dependency = "UP") => <>[](state = "CLOSED")

\* A dependency that is down for good gets the wait between its probes: the breaker opens again and again,
\* so that no round of probes is followed by another without a wait.
ADeadDependencyIsLeftAlone == <>[](dependency = "DOWN") => []<>(state = "OPEN")

=============================================================================
