---------------------------- MODULE IdempotentReceiver ----------------------------
(***************************************************************************)
(* An idempotent receiver as a distributed system: a client that sends a   *)
(* request and retries it under the same idempotency key, the receiver     *)
(* with its record for the key, the attempts in flight between them, the   *)
(* attempts executing inside the receiver, and the sweeper that ends the   *)
(* record's time to live. TLC explores every interleaving for the attempts *)
(* in IdempotentReceiver.cfg, where the record never expires, and in       *)
(* IdempotentReceiverExpiring.cfg, where its time to live can pass at any  *)
(* point, and checks the invariants in every state it reaches.             *)
(*                                                                         *)
(* The receiver's decision rule, Decide(key, event), is not written here.  *)
(* It is generated from the behavioural contract of                        *)
(* IdempotentReceiver#decide (IdempotentReceiverContract.tla), which       *)
(* jvmcontract proves the bytecode obeys on every input. Each action names *)
(* the Java operation it stands for.                                       *)
(*                                                                         *)
(* Simplifications: one key, whose attempts all carry the same request     *)
(* (the fingerprint matches); the lookup of the record and the decision on *)
(* it are one atomic step, which is what the filter's transaction provides;*)
(* no clock, so when the record expires the sweeper's clock has measured   *)
(* the record's age and nothing else, in particular not whether an         *)
(* execution is still running.                                             *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, IdempotentReceiverContract

CONSTANTS
    Attempts,  \* the attempts the client can send
    Expires    \* whether the record's time to live can pass within the run

ASSUME Expires \in BOOLEAN

VARIABLES
    key,        \* the receiver's record for the key: ABSENT, IN_PROGRESS or COMPLETED
    sent,       \* the attempts the client has sent so far
    inbox,      \* attempts that have arrived at the receiver and await its decision
    executing,  \* attempts the receiver is executing
    responses,  \* attempt -> the response the client got: NONE, RESULT, REPLAYED, EMPTY, FAILED or CONFLICT
    completed,  \* how many executions have produced a result since the record was last released by the sweeper
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
\* A replay answers with whatever is stored under the key: the response, or nothing.
Receive(a) ==
    /\ a \in inbox
    /\ inbox' = inbox \ {a}
    /\ LET d == Decide(key, [kind |-> "Request", sameFingerprint |-> TRUE])
       IN /\ key' = IF d.kind = "Transition" THEN d.next ELSE key
          /\ executing' = IF Has(d, "EXECUTE") THEN executing \cup {a} ELSE executing
          /\ responses' = [responses EXCEPT ![a] =
                              IF Has(d, "REPLAY_RESPONSE") THEN (IF stored THEN "REPLAYED" ELSE "EMPTY")
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
(* The sweeper.                                                            *)
(***************************************************************************)

\* IdempotencySweeper.sweep: the record's time to live passed; the sweeper asks the receiver what to do with it
\* and applies the decision in one transaction. A release ends the record's lifetime: what the receiver remembers
\* of the key is gone, and an attempt arriving after it is a new request.
Expire ==
    /\ Expires
    /\ key # "ABSENT"
    /\ LET d == Decide(key, [kind |-> "Expired"])
       IN /\ key' = IF d.kind = "Transition" THEN d.next ELSE key
          /\ stored' = IF Has(d, "RELEASE_KEY") THEN FALSE ELSE stored
          /\ completed' = IF Has(d, "RELEASE_KEY") THEN 0 ELSE completed
    /\ UNCHANGED <<sent, inbox, executing, responses>>

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

Next ==
    \/ \E a \in Attempts : Send(a) \/ Receive(a) \/ Finish(a) \/ Fail(a)
    \/ Expire

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

TypeOK ==
    /\ key \in {"ABSENT", "IN_PROGRESS", "COMPLETED"}
    /\ sent \subseteq Attempts
    /\ inbox \subseteq sent
    /\ executing \subseteq sent
    /\ \A a \in Attempts : responses[a] \in {"NONE", "RESULT", "REPLAYED", "EMPTY", "FAILED", "CONFLICT"}
    /\ completed \in Nat
    /\ stored \in BOOLEAN

\* The request is never executed twice at the same time: no two attempts under one key run concurrently.
OneExecutionAtATime == Cardinality(executing) <= 1

\* The request's effect happens at most once: once an execution has produced a result, no attempt is executing
\* and none ever will, for as long as the record lives. While the record never expires (IdempotentReceiver.cfg)
\* this is at most once outright. Once it can (IdempotentReceiverExpiring.cfg), a retry that arrives after the
\* sweeper released the record is a new request to the receiver, which is what a time to live means, so the count
\* starts over at each release: at most once per lifetime of the record.
AtMostOnce == completed <= 1 /\ (completed = 1 => executing = {})

\* A replayed response is a real one: the client is never answered with a stored response that does not exist.
ReplayedResponsesExist == \A a \in Attempts : responses[a] # "EMPTY"

=============================================================================
