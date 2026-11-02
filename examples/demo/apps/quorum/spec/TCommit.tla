------------------------------ MODULE TCommit ------------------------------
(***************************************************************************)
(* Transaction commit, as Lamport and Gray state it in "Consensus on       *)
(* Transaction Commit": what any commit protocol must achieve, with no     *)
(* coordinator, no messages and no timeouts. Each participant is working,  *)
(* prepared, committed or aborted; a participant may commit only once      *)
(* every participant is prepared or committed, and may abort only while   *)
(* none has committed. TwoPhaseCommit.tla is checked to implement this     *)
(* specification: every behaviour of the protocol, seen through the        *)
(* participants' states alone, is a behaviour allowed here.                *)
(*                                                                         *)
(* The names are the protocol's: WORKING, PREPARED, COMMITTED, ABORTED.    *)
(***************************************************************************)

CONSTANT Participants

VARIABLE pstate  \* participant -> WORKING, PREPARED, COMMITTED or ABORTED

TCTypeOK == pstate \in [Participants -> {"WORKING", "PREPARED", "COMMITTED", "ABORTED"}]

TCInit == pstate = [p \in Participants |-> "WORKING"]

\* Every participant is ready to commit, or has.
CanCommit == \A p \in Participants : pstate[p] \in {"PREPARED", "COMMITTED"}

\* No participant has committed.
NotCommitted == \A p \in Participants : pstate[p] # "COMMITTED"

\* A working participant gets ready to commit.
Prepare(p) ==
    /\ pstate[p] = "WORKING"
    /\ pstate' = [pstate EXCEPT ![p] = "PREPARED"]

\* A participant decides: commits only once every participant can, aborts only while none has committed.
Decide(p) ==
    \/ /\ pstate[p] = "PREPARED"
       /\ CanCommit
       /\ pstate' = [pstate EXCEPT ![p] = "COMMITTED"]
    \/ /\ pstate[p] \in {"WORKING", "PREPARED"}
       /\ NotCommitted
       /\ pstate' = [pstate EXCEPT ![p] = "ABORTED"]

TCNext == \E p \in Participants : Prepare(p) \/ Decide(p)

TCSpec == TCInit /\ [][TCNext]_pstate

\* No participant has committed while another has aborted.
TCConsistent == \A p, q \in Participants : ~(pstate[p] = "COMMITTED" /\ pstate[q] = "ABORTED")

=============================================================================
