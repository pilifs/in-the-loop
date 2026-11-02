-------------------------- MODULE TwoPhaseCommitTrace --------------------------
(***************************************************************************)
(* Trace validation: the Java nodes of two-phase commit held to the model. *)
(* TwoPhaseCommitTraces.tla records the runs of the Java coordinator, its  *)
(* log and broadcast, and the participants through scripted scenarios,     *)
(* crashes included, one state per step in the model's variables. This     *)
(* specification walks each recorded run, one recorded state after the     *)
(* other, and asks two things of it: that it starts in the model's initial *)
(* state, and that every step is a step of the model's next-state          *)
(* relation, an action of one part or a stutter, which TLC checks as the   *)
(* action property EveryStepIsOneOfTheModel. A step the model has no       *)
(* action for is a step the glue took that the model never considered,     *)
(* and the model's verdicts do not cover it: TLC reports the run and the   *)
(* step. The model's invariants hold of the recorded states as well, since *)
(* they hold of every behaviour of the model.                              *)
(*                                                                         *)
(* The decision rules the nodes run are the ones the model's operators are *)
(* generated from, so what this checks is the glue: that the log is        *)
(* written before the broadcast, that a crash loses nothing logged, that   *)
(* the tally the rule decides on is the tally, that a participant does     *)
(* what Vote, ParticipantTimeout and Learn say.                            *)
(***************************************************************************)
EXTENDS TwoPhaseCommit, TwoPhaseCommitTraces

VARIABLES
    run,        \* which recorded run this behaviour walks
    step,       \* how far along it is
    scenario    \* the run's name, for the trace

TraceVars == <<vars, run, step, scenario>>

Recorded(s) ==
    /\ phase = s.phase
    /\ pstate = s.pstate
    /\ votes = s.votes
    /\ inbox = s.inbox
    /\ decision = s.decision
    /\ up = s.up
    /\ crashes = s.crashes

\* The next state is the next recorded one. (Written out with primes: TLC does not prime an operator application.)
Loads(s) ==
    /\ phase' = s.phase
    /\ pstate' = s.pstate
    /\ votes' = s.votes
    /\ inbox' = s.inbox
    /\ decision' = s.decision
    /\ up' = s.up
    /\ crashes' = s.crashes

TraceInit ==
    /\ run \in 1..Len(Traces)
    /\ step = 1
    /\ scenario = Names[run]
    /\ Recorded(Traces[run][1])

TraceNext ==
    /\ step < Len(Traces[run])
    /\ step' = step + 1
    /\ UNCHANGED <<run, scenario>>
    /\ Loads(Traces[run][step + 1])

TraceSpec == TraceInit /\ [][TraceNext]_TraceVars

\* The first recorded state of every run is the model's initial state.
StartsAtTheInitialState == step = 1 => Init

\* Every recorded step is a step of the model: an action of one of its parts, or a step that changes nothing.
EveryStepIsOneOfTheModel == [][Next]_vars

=============================================================================
