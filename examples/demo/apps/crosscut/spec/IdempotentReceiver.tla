---------------------------- MODULE IdempotentReceiver ----------------------------
(***************************************************************************)
(* An idempotent receiver as a distributed system: a client that sends a   *)
(* request and retries it under the same idempotency key, the receiver     *)
(* with its record for the key, the attempts in flight between them, and   *)
(* the attempts executing inside the receiver. TLC explores every          *)
(* interleaving for the attempts in IdempotentReceiver.cfg and checks the  *)
(* invariants in every state it reaches.                                   *)
(*                                                                         *)
(* The receiver's decision rule, Decide(key, event), is not written here.  *)
(* It is generated from the behavioural contract of                        *)
(* IdempotentReceiver#decide (IdempotentReceiverContract.tla), which       *)
(* jvmcontract proves the bytecode obeys on every input. Each action names *)
(* the Java operation it stands for.                                       *)
(*                                                                         *)
(* Simplifications: one key, whose attempts all carry the same request     *)
(* (the fingerprint matches); the record does not expire within the run;   *)
(* the lookup of the record and the decision on it are one atomic step,    *)
(* which is what the filter's transaction provides.                        *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, IdempotentReceiverContract

CONSTANTS Attempts

VARIABLES
    key,        \* the receiver's record for the key: ABSENT, IN_PROGRESS or COMPLETED
    sent,       \* the attempts the client has sent so far
    inbox,      \* attempts that have arrived at the receiver and await its decision
    executing,  \* attempts the receiver is executing
    responses,  \* attempt -> the response the client got: NONE, RESULT, REPLAYED, FAILED or CONFLICT
    completed,  \* how many executions have produced a result
    stored      \* whether a response is stored under the key

vars == <<key, sent, inbox, executing, responses, completed, stored>>

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect

(***************************************************************************)
(* The client.                                                             *)
(***************************************************************************)

\* IdempotentClient.send: the client sends the request, or retries it because it has no response yet. It may
\* retry before the first attempt is answered, which is what a timeout does.
Send(a) ==
    /\ a \notin sent
    /\ sent' = sent \cup {a}
    /\ inbox' = inbox \cup {a}
    /\ UNCHANGED <<key, executing, responses, completed, stored>>

(***************************************************************************)
(* The receiver.                                                           *)
(***************************************************************************)

\* IdempotencyFilter.doFilter: the receiver looks the key up, decides, and applies the decision in one transaction.
Receive(a) ==
    /\ a \in inbox
    /\ inbox' = inbox \ {a}
    /\ LET d == Decide(key, [kind |-> "Request", sameFingerprint |-> TRUE])
       IN /\ key' = IF d.kind = "Transition" THEN d.next ELSE key
          /\ executing' = IF Has(d, "EXECUTE") THEN executing \cup {a} ELSE executing
          /\ responses' = [responses EXCEPT ![a] =
                              IF Has(d, "REPLAY_RESPONSE") THEN "REPLAYED"
                              ELSE IF d.kind = "Rejected" THEN "CONFLICT"
                              ELSE responses[a]]
    /\ UNCHANGED <<sent, completed, stored>>

\* IdempotencyFilter.onCompleted: the executing attempt produced a result; the receiver applies the decision
\* (which stores it) and answers.
Finish(a) ==
    /\ a \in executing
    /\ executing' = executing \ {a}
    /\ completed' = completed + 1
    /\ LET d == Decide(key, [kind |-> "Completed"])
       IN /\ key' = IF d.kind = "Transition" THEN d.next ELSE key
          /\ stored' = (stored \/ Has(d, "STORE_RESPONSE"))
    /\ responses' = [responses EXCEPT ![a] = "RESULT"]
    /\ UNCHANGED <<sent, inbox>>

\* IdempotencyFilter.onFailure: the executing attempt died (its transaction rolled back) without a result; the
\* receiver applies the decision (which releases the key, or stores the failure) and answers.
Fail(a) ==
    /\ a \in executing
    /\ executing' = executing \ {a}
    /\ LET d == Decide(key, [kind |-> "Failed"])
       IN /\ key' = IF d.kind = "Transition" THEN d.next ELSE key
          /\ stored' = (stored \/ Has(d, "STORE_RESPONSE"))
    /\ responses' = [responses EXCEPT ![a] = "FAILED"]
    /\ UNCHANGED <<sent, inbox, completed>>

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ key = "ABSENT"
    /\ sent = {}
    /\ inbox = {}
    /\ executing = {}
    /\ responses = [a \in Attempts |-> "NONE"]
    /\ completed = 0
    /\ stored = FALSE

Next == \E a \in Attempts : Send(a) \/ Receive(a) \/ Finish(a) \/ Fail(a)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

TypeOK ==
    /\ key \in {"ABSENT", "IN_PROGRESS", "COMPLETED"}
    /\ sent \subseteq Attempts
    /\ inbox \subseteq sent
    /\ executing \subseteq sent
    /\ \A a \in Attempts : responses[a] \in {"NONE", "RESULT", "REPLAYED", "FAILED", "CONFLICT"}
    /\ completed \in Nat
    /\ stored \in BOOLEAN

\* The request is never executed twice at the same time: no two attempts under one key run concurrently.
OneExecutionAtATime == Cardinality(executing) <= 1

\* The request's effect happens at most once: once an execution has produced a result, no attempt is executing
\* and none ever will.
AtMostOnce == completed <= 1 /\ (completed = 1 => executing = {})

\* A replayed response is a real one: the client is never answered with a stored response that does not exist.
ReplayedResponsesExist == (\E a \in Attempts : responses[a] = "REPLAYED") => stored

=============================================================================
