---------------------------- MODULE RaftElection ----------------------------
(***************************************************************************)
(* Raft leader election (Ongaro and Ousterhout, section 5.2) as a          *)
(* distributed system: the servers, their terms, their votes, and the      *)
(* RPCs between them. TLC explores every interleaving for the servers and  *)
(* terms in RaftElection.cfg, checks the invariants in every state it      *)
(* reaches, and checks the action properties on every step: that terms    *)
(* never go backwards, and that a leader never campaigns.                  *)
(*                                                                         *)
(* A server's role transitions, Decide(role, event), are not written here. *)
(* They are generated from the behavioural contract of RoleMachine#decide  *)
(* (RoleMachineContract.tla), which jvmcontract proves the bytecode obeys  *)
(* on every input. The role machine sees a message's term only as it       *)
(* compares with the server's own (NEWER, CURRENT, OLDER), as the Java     *)
(* does. The vote itself is VoteRule.grant without the log comparison:     *)
(* one vote per term, for the first candidate to ask. Each action names    *)
(* the Java operation it stands for.                                       *)
(*                                                                         *)
(* Simplifications: no log, so no election restriction and no entries      *)
(* (a heartbeat is an empty AppendEntries); an RPC is one step, the        *)
(* request and its reply together, so a server always answers with the    *)
(* term it has now, and a stale server learns of a newer term the moment   *)
(* it talks to one that has it; terms stop at MaxTerm, past which no timer *)
(* fires; election timeouts fire whenever the model likes, so              *)
(* RESET_ELECTION_TIMER has no counterpart. There is no liveness property:  *)
(* Raft elects a leader eventually by randomizing the timeouts, which is a *)
(* matter of timing, and this model has no clock.                          *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, RoleMachineContract

CONSTANTS Servers, MaxTerm

VARIABLES
    role,         \* server -> FOLLOWER, CANDIDATE or LEADER
    currentTerm,  \* server -> its term
    votedFor,     \* server -> the server it voted for in its term, or "none"
    votes         \* server -> the servers whose vote it holds in its term

vars == <<role, currentTerm, votedFor, votes>>

Majority(S) == Cardinality(S) * 2 > Cardinality(Servers)

\* How a message's term compares with the server's own, which is all the role machine looks at.
Order(s, t) == IF t > currentTerm[s] THEN "NEWER" ELSE IF t = currentTerm[s] THEN "CURRENT" ELSE "OLDER"

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect
Adopts(d) == d.kind = "Transition" /\ Has(d, "ADOPT_TERM")

\* A server after the role machine's decision on a message of term t: its role, and with ADOPT_TERM the message's
\* term, with the vote and the tally of the old term forgotten.
RoleAfter(s, d) == IF d.kind = "Transition" THEN d.next ELSE role[s]
TermAfter(s, d, t) == IF Adopts(d) THEN t ELSE currentTerm[s]
VotedForAfter(s, d) == IF Adopts(d) THEN "none" ELSE votedFor[s]
VotesAfter(s, d) == IF Adopts(d) THEN {} ELSE votes[s]

(***************************************************************************)
(* The servers.                                                            *)
(***************************************************************************)

\* Server.onElectionTimeout: no heartbeat arrived in time. The decision's effects: a new term, a vote for itself,
\* and (REQUEST_VOTES) the canvass below, one server at a time.
Timeout(s) ==
    /\ currentTerm[s] < MaxTerm
    /\ LET d == Decide(role[s], [kind |-> "ElectionTimeout"])
           t == IF d.kind = "Transition" /\ Has(d, "INCREMENT_TERM") THEN currentTerm[s] + 1 ELSE currentTerm[s]
       IN /\ role' = [role EXCEPT ![s] = RoleAfter(s, d)]
          /\ currentTerm' = [currentTerm EXCEPT ![s] = t]
          /\ votedFor' = [votedFor EXCEPT ![s] = IF d.kind = "Transition" /\ Has(d, "VOTE_FOR_SELF") THEN s
                                                 ELSE IF t > currentTerm[s] THEN "none" ELSE @]
          /\ votes' = [votes EXCEPT ![s] = IF d.kind = "Transition" /\ Has(d, "VOTE_FOR_SELF") THEN {s}
                                           ELSE IF t > currentTerm[s] THEN {} ELSE @]

\* Server.requestVote, one RPC: candidate c asks server v for its vote and gets the answer.
\* On v, Server.onRequestVote: the role machine first (a candidate's newer term is adopted), then the vote rule on
\* the server as it then is: a candidate from the past is refused, and otherwise the vote is granted when the
\* candidate's term is ahead of the server's, or the server has not voted in its term, or voted for this candidate.
\* On c, Server.onVote: the reply carries v's term, which goes through the role machine (a newer one is adopted);
\* a candidate adds a granted vote to its tally, and the tally goes through the role machine as VotesCounted: a
\* majority makes it the leader.
Canvass(c, v) ==
    /\ role[c] = "CANDIDATE"
    /\ v \notin votes[c] \cup {c}
    /\ LET dv == Decide(role[v], [kind |-> "RequestVote", term |-> Order(v, currentTerm[c])])
           tv == TermAfter(v, dv, currentTerm[c])
           free == VotedForAfter(v, dv)
           granted == currentTerm[c] >= tv /\ (currentTerm[c] > tv \/ free \in {"none", c})
           dc == Decide(role[c], [kind |-> "Response", term |-> Order(c, tv)])
           tally == IF Adopts(dc) THEN {} ELSE IF granted THEN votes[c] \cup {v} ELSE votes[c]
           dt == Decide(RoleAfter(c, dc), [kind |-> "VotesCounted", majority |-> Majority(tally)])
       IN /\ role' = [role EXCEPT ![v] = RoleAfter(v, dv), ![c] = IF dt.kind = "Transition" THEN dt.next ELSE RoleAfter(c, dc)]
          /\ currentTerm' = [currentTerm EXCEPT ![v] = tv, ![c] = TermAfter(c, dc, tv)]
          /\ votedFor' = [votedFor EXCEPT ![v] = IF granted THEN c ELSE free, ![c] = VotedForAfter(c, dc)]
          /\ votes' = [votes EXCEPT ![v] = VotesAfter(v, dv), ![c] = tally]

\* Server.appendEntries, one RPC: leader l sends server s a heartbeat and gets the answer.
\* On s, Server.onAppendEntries: a newer term is adopted, a candidate yields to the leader of its term, and a stale
\* leader is rejected. On l, Server.onAppendReply: the reply carries s's term, which goes through the role machine;
\* a stale leader steps down. (A leader that hears a leader of its own term throws in the Java; the model has no
\* step for it, and ElectionSafety says it never happens.)
Heartbeat(l, s) ==
    /\ role[l] = "LEADER"
    /\ s # l
    /\ LET ds == Decide(role[s], [kind |-> "AppendEntries", term |-> Order(s, currentTerm[l])])
           ts == TermAfter(s, ds, currentTerm[l])
           dl == Decide(role[l], [kind |-> "Response", term |-> Order(l, ts)])
       IN /\ ds.kind # "Throws"
          /\ role' = [role EXCEPT ![s] = RoleAfter(s, ds), ![l] = RoleAfter(l, dl)]
          /\ currentTerm' = [currentTerm EXCEPT ![s] = ts, ![l] = TermAfter(l, dl, ts)]
          /\ votedFor' = [votedFor EXCEPT ![s] = VotedForAfter(s, ds), ![l] = VotedForAfter(l, dl)]
          /\ votes' = [votes EXCEPT ![s] = VotesAfter(s, ds), ![l] = VotesAfter(l, dl)]

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ role = [s \in Servers |-> "FOLLOWER"]
    /\ currentTerm = [s \in Servers |-> 0]
    /\ votedFor = [s \in Servers |-> "none"]
    /\ votes = [s \in Servers |-> {}]

Next ==
    \/ \E s \in Servers : Timeout(s)
    \/ \E c, v \in Servers : Canvass(c, v)
    \/ \E l, s \in Servers : Heartbeat(l, s)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

TypeOK ==
    /\ role \in [Servers -> {"FOLLOWER", "CANDIDATE", "LEADER"}]
    /\ currentTerm \in [Servers -> 0..MaxTerm]
    /\ votedFor \in [Servers -> Servers \cup {"none"}]
    /\ votes \in [Servers -> SUBSET Servers]

\* Election safety (Raft, figure 3): at most one leader per term.
ElectionSafety ==
    \A s, t \in Servers : role[s] = "LEADER" /\ role[t] = "LEADER" /\ currentTerm[s] = currentTerm[t] => s = t

\* A leader holds the votes of a majority of the servers, its own among them.
LeaderHasAMajority == \A s \in Servers : role[s] = "LEADER" => s \in votes[s] /\ Majority(votes[s])

(***************************************************************************)
(* Action properties: what every step of the system satisfies, which an     *)
(* invariant cannot say because it is about one state at a time.           *)
(***************************************************************************)

\* A term never goes backwards on any server.
TermsNeverDecrease == [][\A s \in Servers : currentTerm'[s] >= currentTerm[s]]_vars

\* A leader never campaigns: it leaves office as the follower of a newer term, or by stepping down, never by
\* starting an election against itself. The states on either side of such a step are unremarkable, which is why
\* this is a property of steps.
LeadersNeverCampaign == [][\A s \in Servers : role[s] = "LEADER" => role'[s] # "CANDIDATE"]_vars

=============================================================================
