-------------------------- MODULE TwoPhaseCommit --------------------------
(***************************************************************************)
(* Two-phase commit as a distributed system: a coordinator, the            *)
(* participants, the votes in flight between them, and the two timeouts    *)
(* that make the protocol interesting. TLC explores every interleaving for *)
(* the participants in TwoPhaseCommit.cfg, checks the invariants in every  *)
(* state it reaches, checks that every behaviour is one transaction commit *)
(* allows (TCommit.tla, the specification this protocol implements), and   *)
(* checks that every participant eventually decides, under the fairness    *)
(* conditions below. TwoPhaseCommitInductive.cfg checks that the invariant *)
(* Inductive, at the end, is inductive, which proves atomicity for runs of *)
(* any length. TwoPhaseCommitCrash.cfg lets the coordinator crash, between *)
(* steps or in the middle of one, after it has logged a phase change and   *)
(* before the broadcast goes out, and restart with what it logged; it      *)
(* checks the same invariants and properties over those runs, and          *)
(* TwoPhaseCommitCrashInductive.cfg the inductive step with crashes.       *)
(* TwoPhaseCommitParticipantCrash.cfg lets the participants crash as well, *)
(* after logging a vote and before sending it, or between steps, and       *)
(* restart on their own rule: a prepared participant holds its locks       *)
(* through a restart, which is what makes the protocol blocking; and       *)
(* TwoPhaseCommitParticipantCrashInductive.cfg checks the inductive step   *)
(* with those crashes among the steps. TwoPhaseCommitTrace.tla holds the   *)
(* Java nodes to this model: it walks their recorded runs and checks every *)
(* step against Next.                                                      *)
(*                                                                         *)
(* The coordinator's decision rule, Decide(phase, event), is not written   *)
(* here. It is generated from the behavioural contract of                  *)
(* Coordinator#decide (CoordinatorContract.tla), which jvmcontract proves  *)
(* the bytecode obeys on every input; so is the recovery rule, what a      *)
(* restarted coordinator does with the phase it logged, from Recovery#     *)
(* decide (RecoveryContract.tla), and the participant's rule, what a       *)
(* participant does when asked to prepare, when it gives up, when it reads *)
(* the decision and when it restarts, from Participant#decide              *)
(* (ParticipantContract.tla). Each action names the Java operation it      *)
(* stands for.                                                             *)
(*                                                                         *)
(* Simplifications: one transaction; messages are a set, so they can be    *)
(* reordered but not lost or duplicated; the coordinator's decision is a   *)
(* broadcast every participant can read; the coordinator logs every       *)
(* change to its phase and its tally, and a participant every change to    *)
(* its state, before acting on it, so a crash loses the step in progress   *)
(* and nothing else; a participant's restart is one step.                  *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, CoordinatorContract

Recovery == INSTANCE RecoveryContract
Participant == INSTANCE ParticipantContract

CONSTANTS
    Participants,
    MaxCrashes,             \* how many times the coordinator may crash in a run: 0 for a coordinator that stays up
    MaxParticipantCrashes   \* how many times the participants may crash in a run, between them: 0 for participants that stay up

ASSUME MaxCrashes \in Nat /\ MaxParticipantCrashes \in Nat

VARIABLES
    phase,      \* the coordinator's phase: COLLECTING, COMMITTED or ABORTED
    pstate,     \* participant -> WORKING, PREPARED, COMMITTED or ABORTED
    votes,      \* participant -> the vote the coordinator has counted: YES, NO or NONE
    inbox,      \* votes on their way to the coordinator: a set of [from, vote]
    decision,   \* what the coordinator broadcast: NONE, COMMIT or ABORT
    up,         \* whether the coordinator is running, or crashed and not yet restarted
    crashes,    \* how many times it has crashed
    pup,        \* participant -> whether it is running, or crashed and not yet restarted
    pcrashes    \* how many times the participants have crashed, between them

vars == <<phase, pstate, votes, inbox, decision, up, crashes, pup, pcrashes>>

Counted == {p \in Participants : votes[p] # "NONE"}

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect

(***************************************************************************)
(* The participants.                                                       *)
(***************************************************************************)

\* The vote a participant's decision sends, if any.
Sends(p, d) ==
    IF Has(d, "VOTE_YES") THEN {[from |-> p, vote |-> "YES"]} ELSE IF Has(d, "VOTE_NO") THEN {[from |-> p, vote |-> "NO"]} ELSE {}

\* A participant may crash in the middle of a step (while MaxParticipantCrashes allows): what it logged survives.
ParticipantCrashes(p) == pcrashes < MaxParticipantCrashes /\ pup' = [pup EXCEPT ![p] = FALSE] /\ pcrashes' = pcrashes + 1

\* ParticipantNode.act: a participant that is up logs the state its rule's decision moves it to, then sends the vote
\* the decision says, if any. It may crash after the log write: the logged state survives, and the vote is lost or
\* not, depending on whether the crash fell before or after the send. A decision that changes nothing is no step.
Act(p, d) ==
    /\ pup[p]
    /\ d.kind = "Transition"
    /\ pstate' = [pstate EXCEPT ![p] = d.next]
    /\ \/ inbox' = inbox \cup Sends(p, d) /\ UNCHANGED <<pup, pcrashes>>
       \/ ParticipantCrashes(p) /\ inbox' \in {inbox, inbox \cup Sends(p, d)}
    /\ UNCHANGED <<phase, votes, decision, up, crashes>>

\* Participant.prepare: asked to prepare, the participant either can do its part, votes YES and holds its locks until
\* it hears the decision, or cannot, votes NO and aborts at once. Which, the rule decides on `able`.
Vote(p) ==
    /\ pstate[p] = "WORKING"
    /\ \E v \in {"YES", "NO"} : Act(p, Participant!Decide(pstate[p], [kind |-> "Prepare", able |-> v = "YES"]))

\* Participant.timeout: a participant that has not voted yet may give up on its own, and then never votes.
\* (One that voted YES may not: that is the blocking property of two-phase commit, and the rule's Rejected row.)
ParticipantTimeout(p) ==
    /\ pstate[p] = "WORKING"
    /\ Act(p, Participant!Decide(pstate[p], [kind |-> "GiveUp"]))

\* Participant.learn: a participant reads the coordinator's decision and applies it.
Learn(p) ==
    /\ decision # "NONE"
    /\ pstate[p] \in {"WORKING", "PREPARED"}
    /\ Act(p, Participant!Decide(pstate[p], [kind |-> "Learned", outcome |-> decision]))

\* A participant crashes between steps: it loses nothing it logged, and takes no step until it restarts.
ParticipantCrash(p) ==
    /\ pup[p]
    /\ ParticipantCrashes(p)
    /\ UNCHANGED <<phase, pstate, votes, inbox, decision, up, crashes>>

\* Participant.recover: a participant restarts, reads the state it logged, and acts on the rule's decision. On the
\* committed rule, a prepared participant holds its locks and waits for the decision, since it cannot decide alone,
\* and one that had not voted aborts, as the coordinator will presume: no vote went out.
ParticipantRecover(p) ==
    /\ ~pup[p]
    /\ LET d == Participant!Decide(pstate[p], [kind |-> "Restarted"])
       IN /\ pstate' = [pstate EXCEPT ![p] = IF d.kind = "Transition" THEN d.next ELSE pstate[p]]
          /\ inbox' = inbox \cup Sends(p, d)
    /\ pup' = [pup EXCEPT ![p] = TRUE]
    /\ UNCHANGED <<phase, votes, decision, up, crashes, pcrashes>>

(***************************************************************************)
(* The coordinator.                                                        *)
(***************************************************************************)

Broadcast(d) == IF Has(d, "SEND_COMMIT") THEN "COMMIT" ELSE IF Has(d, "SEND_ABORT") THEN "ABORT" ELSE decision

\* The coordinator may crash in the middle of a step (while MaxCrashes allows): what it logged survives, what it
\* had not yet sent is lost.
Crashes == crashes < MaxCrashes /\ up' = FALSE /\ crashes' = crashes + 1

\* CoordinatorTransitions.apply: the phase change, which the coordinator logs, then the decision's effects, the
\* broadcast. The coordinator may crash between the two: the logged phase survives, the broadcast is lost, and
\* Recover has the recovery rule say what to do about it. A step that decides nothing logs what changed (the tally)
\* and may crash after that as well, which is the same as crashing right after the step.
Perform(d) ==
    IF d.kind = "Transition"
    THEN /\ phase' = d.next
         /\ \/ decision' = Broadcast(d) /\ up' = TRUE /\ UNCHANGED crashes
            \/ Crashes /\ UNCHANGED decision
    ELSE /\ UNCHANGED <<phase, decision>>
         /\ \/ up' = TRUE /\ UNCHANGED crashes
            \/ Crashes

\* A coordinator that is up acts on a decision; one that has crashed takes no step until it restarts.
Apply(d) == up /\ Perform(d)

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
    /\ UNCHANGED <<pstate, pup, pcrashes>>

\* Coordinator.onTimeout: the collection timer fires while votes are missing.
CoordinatorTimeout ==
    /\ phase = "COLLECTING"
    /\ Counted # Participants
    /\ Apply(Decide(phase, [kind |-> "Timeout", unanimousSoFar |-> \A p \in Counted : votes[p] = "YES"]))
    /\ UNCHANGED <<pstate, votes, inbox, pup, pcrashes>>

\* A crash between steps: the coordinator loses nothing it logged, and takes no step until it restarts.
Crash ==
    /\ up
    /\ Crashes
    /\ UNCHANGED <<phase, pstate, votes, inbox, decision, pup, pcrashes>>

\* Recovery.decide: the coordinator restarts, reads the phase it logged, and acts on the recovery rule's decision
\* the way it acts on any other, so the restart can itself be cut short by a crash. On the committed rule, a
\* logged decision is broadcast again, a step that changes nothing if the first broadcast went out, and no logged
\* decision aborts.
Recover ==
    /\ ~up
    /\ Perform(Recovery!Decide(phase, [kind |-> "Restarted"]))
    /\ UNCHANGED <<pstate, votes, inbox, pup, pcrashes>>

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ phase = "COLLECTING"
    /\ pstate = [p \in Participants |-> "WORKING"]
    /\ votes = [p \in Participants |-> "NONE"]
    /\ inbox = {}
    /\ decision = "NONE"
    /\ up = TRUE
    /\ crashes = 0
    /\ pup = [p \in Participants |-> TRUE]
    /\ pcrashes = 0

Votes == [from : Participants, vote : {"YES", "NO"}]

Next ==
    \/ \E p \in Participants : Vote(p) \/ ParticipantTimeout(p) \/ Learn(p)
    \/ \E m \in Votes : ReceiveVote(m)
    \/ CoordinatorTimeout
    \/ Crash
    \/ Recover
    \/ \E p \in Participants : ParticipantCrash(p) \/ ParticipantRecover(p)

\* Fairness: what each part is assumed to get round to. A working participant votes (or gives up) eventually, the
\* coordinator counts every vote that reaches it and fires its timer while votes are missing, a participant applies
\* a decision that has been made, and a crashed process restarts. Nothing is assumed about which vote a participant
\* casts, about when a participant gives up, or about when a process crashes, within its budget: those are the
\* environment's choices, and the protocol must be live under all of them.
\* The coordinator's conditions are on its steps that complete, `up'`: a crash is the environment's choice, not a
\* step the coordinator is due, and a step that decides nothing changes nothing when it completes, so fairness
\* must not be able to pick its crashing variant as the step it is owed.
Fairness ==
    /\ \A p \in Participants : WF_vars(Vote(p)) /\ WF_vars(Learn(p)) /\ WF_vars(ParticipantRecover(p))
    /\ \A m \in Votes : WF_vars(ReceiveVote(m) /\ up')
    /\ WF_vars(CoordinatorTimeout /\ up')
    /\ WF_vars(Recover /\ up')

Spec == Init /\ [][Next]_vars /\ Fairness

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

TypeOK ==
    /\ phase \in {"COLLECTING", "COMMITTED", "ABORTED"}
    /\ \A p \in Participants : pstate[p] \in {"WORKING", "PREPARED", "COMMITTED", "ABORTED"}
    /\ \A p \in Participants : votes[p] \in {"YES", "NO", "NONE"}
    /\ decision \in {"NONE", "COMMIT", "ABORT"}
    /\ up \in BOOLEAN
    /\ crashes \in 0..MaxCrashes
    /\ pup \in [Participants -> BOOLEAN]
    /\ pcrashes \in 0..MaxParticipantCrashes

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

(***************************************************************************)
(* The inductive invariant, for the inductive configurations.              *)
(***************************************************************************)

\* Atomicity is not inductive on its own: a state with the coordinator committed and a vote still in flight satisfies it,
\* and one step later the vote is counted as a no. What makes the step safe is what the reachable states say about the
\* votes, counted and in flight, which the conjuncts below spell out. Together with the invariants above they are closed
\* under Next, so TLC can check them from every state they admit (TwoPhaseCommitInductive.cfg; TwoPhaseCommitCrashInductive.cfg
\* with a crash or a restart of the coordinator among the steps; TwoPhaseCommitParticipantCrashInductive.cfg with those of
\* the participants as well) and prove the invariants for every run, of any length.

\* A participant's vote, counted by the coordinator or still on its way.
VotedYes(p) == votes[p] = "YES" \/ [from |-> p, vote |-> "YES"] \in inbox
VotedNo(p) == votes[p] = "NO" \/ [from |-> p, vote |-> "NO"] \in inbox

\* A vote in flight has not been counted yet, and a participant votes once.
VotesInFlightAreUncounted ==
    \A m \in inbox : votes[m.from] = "NONE" /\ \A n \in inbox : n.from = m.from => n = m

\* What the coordinator broadcast, if anything, is what its phase says. Nothing is broadcast while collecting, and a
\* decided coordinator may have nothing out yet: a crash can fall between the phase change, which it logs, and the
\* broadcast, which Recover then does.
DecisionMatchesThePhase ==
    decision \in {"NONE", CASE phase = "COLLECTING" -> "NONE" [] phase = "COMMITTED" -> "COMMIT" [] phase = "ABORTED" -> "ABORT"}

\* A coordinator that is up and decided has its decision out: it broadcast it when it decided, or on restarting.
BroadcastOnceUp == up /\ phase \in {"COMMITTED", "ABORTED"} => decision # "NONE"

\* The coordinator is down only after a crash; a run without one is the protocol as TwoPhaseCommit.cfg checks it.
DownOnlyAfterACrash == ~up => crashes > 0

\* Participants are down only after crashes: no more of them than have crashed.
ParticipantsDownOnlyAfterACrash == Cardinality({p \in Participants : ~pup[p]}) <= pcrashes

\* A participant's state agrees with its vote: working means it has not voted, prepared means it voted yes, unless a
\* crash took the vote after the state was logged, a no vote means it aborted, and a yes voter that aborted did so on
\* the coordinator's say-so.
ParticipantsAgreeWithTheirVotes ==
    \A p \in Participants :
        /\ pstate[p] = "WORKING" => ~VotedYes(p) /\ ~VotedNo(p)
        /\ pstate[p] = "PREPARED" => VotedYes(p) \/ (pcrashes > 0 /\ ~VotedNo(p))
        /\ VotedNo(p) => pstate[p] = "ABORTED"
        /\ pstate[p] = "ABORTED" /\ VotedYes(p) => phase = "ABORTED"

\* The coordinator commits only on every vote, counted and yes: nothing is in flight once it has committed.
CommitNeedsEveryVote == phase = "COMMITTED" => \A p \in Participants : votes[p] = "YES"

Inductive ==
    /\ TypeOK
    /\ Atomicity
    /\ CommitFollowsTheCoordinator
    /\ VotesInFlightAreUncounted
    /\ DecisionMatchesThePhase
    /\ ParticipantsAgreeWithTheirVotes
    /\ CommitNeedsEveryVote
    /\ BroadcastOnceUp
    /\ DownOnlyAfterACrash
    /\ ParticipantsDownOnlyAfterACrash

\* Inductive as an initial predicate: every state it admits, enumerated variable by variable, with each conjunct right
\* after the last variable it mentions, so that TLC discards a partial state as soon as a conjunct fails.
InductiveInit ==
    /\ phase \in {"COLLECTING", "COMMITTED", "ABORTED"}
    /\ decision \in {"NONE", "COMMIT", "ABORT"}
    /\ DecisionMatchesThePhase
    /\ pstate \in [Participants -> {"WORKING", "PREPARED", "COMMITTED", "ABORTED"}]
    /\ Atomicity
    /\ votes \in [Participants -> {"YES", "NO", "NONE"}]
    /\ CommitFollowsTheCoordinator
    /\ CommitNeedsEveryVote
    /\ inbox \in SUBSET Votes
    /\ VotesInFlightAreUncounted
    /\ pcrashes \in 0..MaxParticipantCrashes
    /\ ParticipantsAgreeWithTheirVotes
    /\ pup \in [Participants -> BOOLEAN]
    /\ ParticipantsDownOnlyAfterACrash
    /\ crashes \in 0..MaxCrashes
    /\ up \in BOOLEAN
    /\ DownOnlyAfterACrash
    /\ BroadcastOnceUp

=============================================================================
