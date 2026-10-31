---------------------------- MODULE ClassInit ----------------------------
(***************************************************************************)
(* Class initialization (JVMS 5.5) as a concurrent system: the threads     *)
(* that need a class, the class's initialization state, the thread          *)
(* recorded as its initializer, and the threads blocked on the             *)
(* initialization lock. TLC explores every interleaving for the threads in *)
(* ClassInit.cfg and checks the invariants in every state it reaches, and  *)
(* that no state is a deadlock: a state in which no thread can move.       *)
(*                                                                         *)
(* The runtime's decision rule, Decide(state, event), is not written here. *)
(* It is generated from the behavioural contract of                        *)
(* ClassInitialization#decide (ClassInitContract.tla), which jvmcontract   *)
(* proves the bytecode obeys on every input. Each action names the Java    *)
(* operation it stands for.                                                *)
(*                                                                         *)
(* Simplifications: one class, with no superclass or superinterface to     *)
(* initialize first; a thread that is done with the class stops; the       *)
(* decision and the state change are one atomic step, which is what the    *)
(* initialization lock LC provides.                                        *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, ClassInitContract

CONSTANTS Threads

VARIABLES
    state,        \* the class's initialization state: UNINITIALIZED, IN_PROGRESS, INITIALIZED or ERRONEOUS
    initializer,  \* the thread recorded as running the initializer, or "none"
    pc,           \* thread -> where it is: idle, running (the initializer), waiting (on LC), using, failed
    runs          \* how many times the initializer has been started

vars == <<state, initializer, pc, runs>>

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect

\* Where a thread goes with the effects of a decision on its request.
Where(d, here) ==
    IF Has(d, "RUN_INITIALIZER") THEN "running"
    ELSE IF Has(d, "PROCEED") THEN here
    ELSE IF Has(d, "WAIT") THEN "waiting"
    ELSE "failed"

(***************************************************************************)
(* The threads.                                                            *)
(***************************************************************************)

\* Runtime.initialize: a thread needs the class (new, getstatic, putstatic, invokestatic), takes LC, and acts on
\* the decision. A thread woken from waiting requests again, as step 2 directs.
Request(t) ==
    /\ pc[t] = "idle"
    /\ LET d == Decide(state, [kind |-> "Request", byInitializingThread |-> (initializer = t)])
       IN /\ state' = IF d.kind = "Transition" THEN d.next ELSE state
          /\ initializer' = IF Has(d, "RUN_INITIALIZER") THEN t ELSE initializer
          /\ runs' = IF Has(d, "RUN_INITIALIZER") THEN runs + 1 ELSE runs
          /\ pc' = [pc EXCEPT ![t] = Where(d, "using")]

\* Runtime.initialize from inside the initializer: <clinit> touches its own class (a static method, a static
\* field written by a helper), which is a request by the initializing thread.
Recurse(t) ==
    /\ pc[t] = "running"
    /\ LET d == Decide(state, [kind |-> "Request", byInitializingThread |-> (initializer = t)])
       IN /\ state' = IF d.kind = "Transition" THEN d.next ELSE state
          /\ pc' = [pc EXCEPT ![t] = Where(d, "running")]
    /\ UNCHANGED <<initializer, runs>>

\* Runtime.initialized: <clinit> returned; the waiters are woken, and the thread goes on to use the class.
Complete(t) ==
    /\ pc[t] = "running"
    /\ LET d == Decide(state, [kind |-> "Completed"])
       IN /\ state' = IF d.kind = "Transition" THEN d.next ELSE state
          /\ pc' = [u \in Threads |-> IF u = t THEN "using"
                                      ELSE IF pc[u] = "waiting" /\ Has(d, "NOTIFY_ALL") THEN "idle"
                                      ELSE pc[u]]
    /\ UNCHANGED <<initializer, runs>>

\* Runtime.initializationFailed: <clinit> threw; the waiters are woken, and the thread gets the error.
Fail(t) ==
    /\ pc[t] = "running"
    /\ LET d == Decide(state, [kind |-> "Failed", error |-> FALSE])
       IN /\ state' = IF d.kind = "Transition" THEN d.next ELSE state
          /\ pc' = [u \in Threads |-> IF u = t THEN "failed"
                                      ELSE IF pc[u] = "waiting" /\ Has(d, "NOTIFY_ALL") THEN "idle"
                                      ELSE pc[u]]
    /\ UNCHANGED <<initializer, runs>>

\* Every thread is done with the class: the system stops, which is not a deadlock.
Terminating ==
    /\ \A t \in Threads : pc[t] \in {"using", "failed"}
    /\ UNCHANGED vars

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ state = "UNINITIALIZED"
    /\ initializer = "none"
    /\ pc = [t \in Threads |-> "idle"]
    /\ runs = 0

Next ==
    \/ \E t \in Threads : Request(t) \/ Recurse(t) \/ Complete(t) \/ Fail(t)
    \/ Terminating

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

TypeOK ==
    /\ state \in {"UNINITIALIZED", "IN_PROGRESS", "INITIALIZED", "ERRONEOUS"}
    /\ initializer \in Threads \cup {"none"}
    /\ \A t \in Threads : pc[t] \in {"idle", "running", "waiting", "using", "failed"}
    /\ runs \in Nat

\* A thread uses the class only once it is initialized: no thread reads a static field before <clinit> has
\* assigned it, or calls a static method on a half-built class.
UsedOnlyWhenInitialized == \A t \in Threads : pc[t] = "using" => state = "INITIALIZED"

\* <clinit> runs at most once, whatever the threads do.
InitializedAtMostOnce == runs <= 1

\* Only the recorded initializer runs the initializer.
OneInitializer == \A t \in Threads : pc[t] = "running" => initializer = t

=============================================================================
