-------------------------- MODULE TwoPhaseCommit --------------------------
(***************************************************************************)
(* Two-phase commit as a distributed system: a coordinator, the            *)
(* participants, the votes in flight between them, and the two timeouts    *)
(* that make the protocol interesting. TLC explores every interleaving for *)
(* the participants in TwoPhaseCommit.cfg, checks the invariants in every  *)
(* state it reaches, checks that every behaviour is one transaction commit *)
(* allows (TCommit.tla, the specification this protocol implements), and   *)
(* checks that every participant eventually decides, under the fairness    *)
(* conditions below.                                                       *)
(*                                                                         *)
(* The coordinator's decision rule, Decide(phase, event), is not written   *)
(* here. It is generated from the behavioural contract of                  *)
(* Coordinator#decide (CoordinatorContract.tla), which jvmcontract proves  *)
(* the bytecode obeys on every input. Each action names the Java operation *)
(* it stands for.                                                          *)
(*                                                                         *)
(* Simplifications: one transaction; messages are a set, so they can be    *)
(* reordered but not lost or duplicated; the coordinator's decision is a   *)
(* broadcast every participant can read.                                   *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, CoordinatorContract

CONSTANTS Participants

VARIABLES
    phase,      \* the coordinator's phase: COLLECTING, COMMITTED or ABORTED
    pstate,     \* participant -> WORKING, PREPARED, COMMITTED or ABORTED
    votes,      \* participant -> the vote the coordinator has counted: YES, NO or NONE
    inbox,      \* votes on their way to the coordinator: a set of [from, vote]
    decision    \* what the coordinator broadcast: NONE, COMMIT or ABORT

vars == <<phase, pstate, votes, inbox, decision>>

Counted == {p \in Participants : votes[p] # "NONE"}

(***************************************************************************)
(* The participants.                                                       *)
(***************************************************************************)

\* Participant.prepare: the participant either can do its part, votes YES and holds its locks until it hears the
\* decision, or cannot, votes NO and aborts at once.
Vote(p) ==
    /\ pstate[p] = "WORKING"
    /\ \E v \in {"YES", "NO"} :
        /\ pstate' = [pstate EXCEPT ![p] = IF v = "YES" THEN "PREPARED" ELSE "ABORTED"]
        /\ inbox' = inbox \cup {[from |-> p, vote |-> v]}
    /\ UNCHANGED <<phase, votes, decision>>

\* Participant.timeout: a participant that has not voted yet may give up on its own, and then never votes.
\* (One that voted YES may not: that is the blocking property of two-phase commit.)
ParticipantTimeout(p) ==
    /\ pstate[p] = "WORKING"
    /\ pstate' = [pstate EXCEPT ![p] = "ABORTED"]
    /\ UNCHANGED <<phase, votes, inbox, decision>>

\* Participant.learn: a participant applies the coordinator's decision.
Learn(p) ==
    /\ decision # "NONE"
    /\ pstate[p] \in {"WORKING", "PREPARED"}
    /\ pstate' = [pstate EXCEPT ![p] = IF decision = "COMMIT" THEN "COMMITTED" ELSE "ABORTED"]
    /\ UNCHANGED <<phase, votes, inbox, decision>>

(***************************************************************************)
(* The coordinator.                                                        *)
(***************************************************************************)

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect

\* CoordinatorTransitions.apply: the decision's effects, then the phase change.
Apply(d) ==
    IF d.kind = "Transition"
    THEN /\ phase' = d.next
         /\ decision' = IF Has(d, "SEND_COMMIT") THEN "COMMIT" ELSE IF Has(d, "SEND_ABORT") THEN "ABORT" ELSE decision
    ELSE UNCHANGED <<phase, decision>>

\* Coordinator.onVote: a vote in flight arrives; count it, then decide on the tally. (The vote is quantified over
\* the participants and the two values rather than over the inbox, so that TLC names the action in its traces.)
ReceiveVote(m) ==
    /\ m \in inbox
    /\ inbox' = inbox \ {m}
    /\ votes' = [votes EXCEPT ![m.from] = m.vote]
    /\ LET counted == {p \in Participants : votes'[p] # "NONE"}
           tally == [kind |-> "Tally",
                     complete |-> counted = Participants,
                     unanimous |-> \A p \in counted : votes'[p] = "YES"]
       IN Apply(Decide(phase, tally))
    /\ UNCHANGED pstate

\* Coordinator.onTimeout: the collection timer fires while votes are missing.
CoordinatorTimeout ==
    /\ phase = "COLLECTING"
    /\ Counted # Participants
    /\ Apply(Decide(phase, [kind |-> "Timeout", unanimousSoFar |-> \A p \in Counted : votes[p] = "YES"]))
    /\ UNCHANGED <<pstate, votes, inbox>>

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ phase = "COLLECTING"
    /\ pstate = [p \in Participants |-> "WORKING"]
    /\ votes = [p \in Participants |-> "NONE"]
    /\ inbox = {}
    /\ decision = "NONE"

Votes == [from : Participants, vote : {"YES", "NO"}]

Next ==
    \/ \E p \in Participants : Vote(p) \/ ParticipantTimeout(p) \/ Learn(p)
    \/ \E m \in Votes : ReceiveVote(m)
    \/ CoordinatorTimeout

\* Fairness: what each part is assumed to get round to. A working participant votes (or gives up) eventually, the
\* coordinator counts every vote that reaches it and fires its timer while votes are missing, and a participant
\* applies a decision that has been made. Nothing is assumed about which vote a participant casts, or about when
\* a participant gives up: those are the environment's choices, and the protocol must be live under all of them.
Fairness ==
    /\ \A p \in Participants : WF_vars(Vote(p)) /\ WF_vars(Learn(p))
    /\ \A m \in Votes : WF_vars(ReceiveVote(m))
    /\ WF_vars(CoordinatorTimeout)

Spec == Init /\ [][Next]_vars /\ Fairness

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

TypeOK ==
    /\ phase \in {"COLLECTING", "COMMITTED", "ABORTED"}
    /\ \A p \in Participants : pstate[p] \in {"WORKING", "PREPARED", "COMMITTED", "ABORTED"}
    /\ \A p \in Participants : votes[p] \in {"YES", "NO", "NONE"}
    /\ decision \in {"NONE", "COMMIT", "ABORT"}

\* Atomicity: once the coordinator or any participant has committed, no participant has aborted. Every
\* participant that decides, decides the same way.
Atomicity ==
    (phase = "COMMITTED" \/ \E p \in Participants : pstate[p] = "COMMITTED")
        => \A q \in Participants : pstate[q] # "ABORTED"

\* A participant commits only on the coordinator's say-so, and only after voting yes.
CommitFollowsTheCoordinator ==
    \A p \in Participants : pstate[p] = "COMMITTED" => phase = "COMMITTED" /\ votes[p] = "YES"

(***************************************************************************)
(* Temporal properties, checked after the invariants.                      *)
(***************************************************************************)

\* Liveness: every participant eventually commits or aborts. A participant that voted yes holds its locks until
\* it hears the decision, so a coordinator that never decides blocks it forever; this is the property that says
\* the coordinator always decides, and that the decision reaches everyone. TLC checks it under Fairness.
EveryParticipantDecides == \A p \in Participants : <>(pstate[p] \in {"COMMITTED", "ABORTED"})

\* Refinement: seen through the participants' states alone, every behaviour of the protocol is a behaviour of
\* transaction commit (TCommit.tla): a participant commits only once every participant is prepared or committed,
\* and aborts only while none has committed. TLC checks this as a temporal property, step by step.
TC == INSTANCE TCommit
ImplementsTransactionCommit == TC!TCSpec

=============================================================================
