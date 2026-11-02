-------------------------- MODULE RaftReplication --------------------------
(***************************************************************************)
(* Raft log replication (Ongaro and Ousterhout, section 5.3 and 5.4) as a  *)
(* distributed system: the servers, their terms and votes, their logs, and *)
(* the AppendEntries RPCs that carry a leader's entries to the followers.  *)
(* RaftElection.tla checks the election with the logs fixed; this model    *)
(* has the logs live, so that leaders append entries, followers take them  *)
(* or refuse them, and the leader marks entries committed, and checks what *)
(* the paper claims of the logs (figure 3): log matching, that two logs    *)
(* that agree on an entry agree on everything before it; leader            *)
(* completeness, that a leader holds every entry committed before its      *)
(* term; and state machine safety, that no server applies a different      *)
(* entry at an index another has applied, with an action property that no  *)
(* committed entry is ever overwritten. TLC explores every interleaving    *)
(* for three servers, three terms and logs of up to two entries in         *)
(* RaftReplication.cfg, and RaftReplicationFigureEight.cfg gives a run    *)
(* four terms and one entry per leader, the budget of the paper's figure   *)
(* 8, the scenario in which a leader that counted replicas of an entry     *)
(* from an earlier term would commit what a later leader then overwrites.  *)
(*                                                                         *)
(* Four of the rules are not written here. Decide(role, event) is          *)
(* generated from the behavioural contract of RoleMachine#decide           *)
(* (RoleMachineContract.tla) and Vote!Decide from VoteRule#decide          *)
(* (VoteRuleContract.tla), as in the election model; Entries!Decide, what a *)
(* follower does with the entries a leader sends, from AppendRule#decide   *)
(* (AppendRuleContract.tla, as Entries!Decide, since Append is a sequence operator); and Commit!Decide, when a leader marks an     *)
(* entry committed, from CommitRule#decide (CommitRuleContract.tla).       *)
(* jvmcontract proves the bytecode obeys each on every input. The append   *)
(* rule sees the follower's log only as it stands against the leader's at  *)
(* the previous entry (MISSING, CONFLICTING, MATCHING) and at the entry    *)
(* sent (NONE, ABSENT, SAME, CONFLICTING), and the commit rule an entry    *)
(* only by its term against the leader's and whether a majority holds it:  *)
(* the comparing is what the Java around the rules does, and this model    *)
(* repeats it. Each action names the Java operation it stands for.         *)
(*                                                                         *)
(* Simplifications: an RPC is one step, the request and its reply          *)
(* together, as in the election model; a leader sends one entry per RPC,   *)
(* the one at the follower's next index, or none when the follower is      *)
(* caught up, which is a heartbeat; an entry is its term, since the        *)
(* properties are about indices and terms, and a client request is a step  *)
(* the leader takes on its own; a leader appends no entry on taking        *)
(* office; servers do not crash, which the properties need not assume      *)
(* against, since a crashed server is one that takes no step; and terms    *)
(* stop at MaxTerm and logs at MaxEntries, past which no timer fires and   *)
(* no client is served.                                                    *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, TLC, RoleMachineContract

Vote == INSTANCE VoteRuleContract
Entries == INSTANCE AppendRuleContract
Commit == INSTANCE CommitRuleContract

CONSTANTS
    Servers,
    MaxTerm,     \* the last term in which a timer fires
    MaxEntries   \* how many entries a leader's log may hold

VARIABLES
    role,         \* server -> FOLLOWER, CANDIDATE or LEADER
    currentTerm,  \* server -> its term
    votedFor,     \* server -> the server it voted for in its term, or "none"
    votes,        \* server -> the servers whose vote it holds in its term
    log,          \* server -> its log, a sequence of entry terms
    commitIndex,  \* server -> the index of the last entry it knows committed
    nextIndex,    \* leader -> server -> the index of the next entry to send it; 0 on a server that is not leading
    matchIndex    \* leader -> server -> the last index the leader knows the server's log to match its own; 0 on a server that is not leading

vars == <<role, currentTerm, votedFor, votes, log, commitIndex, nextIndex, matchIndex>>

Majority(S) == Cardinality(S) * 2 > Cardinality(Servers)
Min(a, b) == IF a < b THEN a ELSE b

\* The servers are interchangeable: two states that differ only by a permutation of their names behave alike, so a
\* configuration may tell TLC (SYMMETRY Perms) to explore one state of each such class.
Perms == Permutations(Servers)

\* How a message's term t compares with a server's own, which is all the role machine looks at.
OrderOf(own, t) == IF t > own THEN "NEWER" ELSE IF t = own THEN "CURRENT" ELSE "OLDER"
Order(s, t) == OrderOf(currentTerm[s], t)

LastTerm(l) == IF Len(l) = 0 THEN 0 ELSE l[Len(l)]

\* How candidate c's log compares with voter v's, as Server.onRequestVote computes it for the vote rule: by the term
\* of the last entry first, and between equal terms by length.
LogOrder(c, v) ==
    IF LastTerm(log[c]) # LastTerm(log[v]) THEN (IF LastTerm(log[c]) > LastTerm(log[v]) THEN "AHEAD" ELSE "BEHIND")
    ELSE IF Len(log[c]) > Len(log[v]) THEN "AHEAD" ELSE IF Len(log[c]) = Len(log[v]) THEN "EVEN" ELSE "BEHIND"

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect
Adopts(d) == d.kind = "Transition" /\ Has(d, "ADOPT_TERM")

\* A server after the role machine's decision on a message of term t: its role, and with ADOPT_TERM the message's
\* term, with the vote and the tally of the old term forgotten.
RoleAfter(s, d) == IF d.kind = "Transition" THEN d.next ELSE role[s]
TermAfter(s, d, t) == IF Adopts(d) THEN t ELSE currentTerm[s]
VotedForAfter(s, d) == IF Adopts(d) THEN "none" ELSE votedFor[s]
VotesAfter(s, d) == IF Adopts(d) THEN {} ELSE votes[s]

\* Each action below computes its next state as a record of the variables it may change, so that the step it takes
\* and whether a call it makes throws are one computation. The leader's bookkeeping follows the roles: a server that
\* takes office starts it afresh (Server.becomeLeader: every follower's next index at the end of the leader's log,
\* nothing known to match), one that leaves office drops it, and a leader that stays keeps what the step computed.
Fresh(l) == [s \in Servers |-> Len(log[l]) + 1]
Blank == [s \in Servers |-> 0]
NextIndexAfter(n) == [l \in Servers |-> IF n.role[l] # "LEADER" THEN Blank ELSE IF role[l] # "LEADER" THEN Fresh(l) ELSE n.nextIndex[l]]
MatchIndexAfter(n) == [l \in Servers |-> IF n.role[l] # "LEADER" THEN Blank ELSE IF role[l] # "LEADER" THEN Blank ELSE n.matchIndex[l]]
Step(n) ==
    /\ role' = n.role /\ currentTerm' = n.currentTerm /\ votedFor' = n.votedFor /\ votes' = n.votes
    /\ log' = n.log /\ commitIndex' = n.commitIndex
    /\ nextIndex' = NextIndexAfter(n) /\ matchIndex' = MatchIndexAfter(n)
Changes(n) == <<n.role, n.currentTerm, n.votedFor, n.votes, n.log, n.commitIndex, NextIndexAfter(n), MatchIndexAfter(n)>> # vars

(***************************************************************************)
(* The election, as in RaftElection.tla, with the logs live.               *)
(***************************************************************************)

\* Server.onElectionTimeout: no heartbeat arrived in time. The decision's effects: INCREMENT_TERM starts a new
\* term, in which the server has not voted yet; VOTE_FOR_SELF starts a new tally, the server's own vote in it;
\* REQUEST_VOTES is the canvass below, one server whose vote the tally lacks at a time.
TimeoutNext(s) ==
    LET d == Decide(role[s], [kind |-> "ElectionTimeout"])
        t == IF d.kind = "Transition" /\ Has(d, "INCREMENT_TERM") THEN currentTerm[s] + 1 ELSE currentTerm[s]
        self == d.kind = "Transition" /\ Has(d, "VOTE_FOR_SELF")
    IN [throws |-> d.kind = "Throws",
        role |-> [role EXCEPT ![s] = RoleAfter(s, d)],
        currentTerm |-> [currentTerm EXCEPT ![s] = t],
        votedFor |-> [votedFor EXCEPT ![s] = IF self THEN s ELSE IF t > currentTerm[s] THEN "none" ELSE @],
        votes |-> [votes EXCEPT ![s] = IF self THEN {s} ELSE @],
        log |-> log, commitIndex |-> commitIndex, nextIndex |-> nextIndex, matchIndex |-> matchIndex]

Timeout(s) == currentTerm[s] < MaxTerm /\ ~TimeoutNext(s).throws /\ Step(TimeoutNext(s))

\* Server.requestVote, one RPC: candidate c asks server v for its vote and gets the answer. On v, Server.onRequestVote:
\* the role machine first (a candidate's newer term is adopted), then the vote rule on the server as it then is, given
\* v's ballot as it stands for c and c's term and log against v's own: the log comparison is the election
\* restriction, which keeps a candidate without the committed entries from winning. On c, Server.onVote: the reply's
\* term goes through the role machine; a candidate adds a granted vote to its tally, and the tally goes through the
\* role machine as VotesCounted: a majority makes it the leader.
CanvassNext(c, v) ==
    LET dv == Decide(role[v], [kind |-> "RequestVote", term |-> Order(v, currentTerm[c])])
        tv == TermAfter(v, dv, currentTerm[c])
        free == VotedForAfter(v, dv)
        ballot == IF free = "none" THEN "OPEN" ELSE IF free = c THEN "FOR_THE_CANDIDATE" ELSE "FOR_ANOTHER"
        dg == Vote!Decide(ballot, [kind |-> "VoteRequest", term |-> OrderOf(tv, currentTerm[c]), log |-> LogOrder(c, v)])
        granted == dg.kind = "Transition" /\ Has(dg, "GRANT")
        dc == Decide(role[c], [kind |-> "Response", term |-> Order(c, tv)])
        tally == IF Adopts(dc) THEN {} ELSE IF granted THEN votes[c] \cup {v} ELSE votes[c]
        dt == Decide(RoleAfter(c, dc), [kind |-> "VotesCounted", majority |-> Majority(tally)])
    IN [throws |-> dv.kind = "Throws" \/ dg.kind = "Throws" \/ dc.kind = "Throws" \/ dt.kind = "Throws",
        role |-> [role EXCEPT ![v] = RoleAfter(v, dv), ![c] = IF dt.kind = "Transition" THEN dt.next ELSE RoleAfter(c, dc)],
        currentTerm |-> [currentTerm EXCEPT ![v] = tv, ![c] = TermAfter(c, dc, tv)],
        votedFor |-> [votedFor EXCEPT ![v] = IF granted THEN c ELSE free, ![c] = VotedForAfter(c, dc)],
        votes |-> [votes EXCEPT ![v] = VotesAfter(v, dv), ![c] = tally],
        log |-> log, commitIndex |-> commitIndex, nextIndex |-> nextIndex, matchIndex |-> matchIndex]

Canvass(c, v) ==
    /\ role[c] = "CANDIDATE"
    /\ v \notin votes[c] \cup {c}
    /\ ~CanvassNext(c, v).throws
    /\ Step(CanvassNext(c, v))

(***************************************************************************)
(* Replication.                                                            *)
(***************************************************************************)

\* Server.onClientRequest: a leader appends an entry of its term to its own log; the followers get it through
\* Replicate.
ClientRequest(l) ==
    /\ role[l] = "LEADER"
    /\ Len(log[l]) < MaxEntries
    /\ log' = [log EXCEPT ![l] = Append(@, currentTerm[l])]
    /\ UNCHANGED <<role, currentTerm, votedFor, votes, commitIndex, nextIndex, matchIndex>>

\* Server.appendEntries, one RPC: leader l sends server s the entry at s's next index, or a heartbeat if s is caught
\* up, with the entry before it and l's commit index, and gets the answer.
\* On s, Server.onAppendEntries: the role machine first (a newer term is adopted, a candidate yields to the leader
\* of its term, a stale leader is refused and its entries ignored), then the append rule on the log as it stands
\* against the leader's: at the previous entry, which s holds, holds another entry in place of, or lacks, and at the
\* entry sent, which s may hold already or hold another in place of. The rule's effects: TRUNCATE drops the
\* conflicting entry and everything after it, APPEND puts the entry sent at its index, ADVANCE_COMMIT moves s's
\* commit index up to l's, clipped to the last entry sent, as far as s now knows its log to match l's.
\* On l, Server.onAppendReply: the reply carries s's term, which goes through the role machine (a stale leader
\* steps down), and whether s accepted: if so, s's log matches l's through the entry sent and the next index moves
\* past it; if not, the next index backs up by one, and the next RPC tries from one entry earlier.
ReplicateNext(l, s) ==
    LET ds == Decide(role[s], [kind |-> "AppendEntries", term |-> Order(s, currentTerm[l])])
        ts == TermAfter(s, ds, currentTerm[l])
        heard == ds.kind = "Transition"
        prev == nextIndex[l][s] - 1
        at == IF prev = 0 \/ (prev <= Len(log[s]) /\ log[s][prev] = log[l][prev]) THEN "MATCHING"
              ELSE IF prev > Len(log[s]) THEN "MISSING" ELSE "CONFLICTING"
        sent == IF prev < Len(log[l]) THEN <<log[l][prev + 1]>> ELSE <<>>
        entry == IF sent = <<>> THEN "NONE"
                 ELSE IF prev + 1 > Len(log[s]) THEN "ABSENT"
                 ELSE IF log[s][prev + 1] = sent[1] THEN "SAME" ELSE "CONFLICTING"
        last == prev + Len(sent)
        commit == Min(commitIndex[l], last)
        da == IF heard THEN Entries!Decide(at, [kind |-> "AppendRequest", entry |-> entry, commitAhead |-> commit > commitIndex[s]])
              ELSE Entries!Rejected
        success == da.kind = "Unchanged" \/ (da.kind = "Transition" /\ da.next = "MATCHING")
        logs == IF da.kind # "Transition" THEN log[s]
                ELSE IF Has(da, "APPEND") THEN SubSeq(log[s], 1, prev) \o sent
                ELSE IF Has(da, "TRUNCATE") THEN SubSeq(log[s], 1, IF at = "MATCHING" THEN prev ELSE prev - 1)
                ELSE log[s]
        cs == IF da.kind = "Transition" /\ Has(da, "ADVANCE_COMMIT") THEN commit ELSE commitIndex[s]
        dl == Decide(role[l], [kind |-> "Response", term |-> Order(l, ts)])
    IN [throws |-> ds.kind = "Throws" \/ da.kind = "Throws" \/ dl.kind = "Throws",
        role |-> [role EXCEPT ![s] = RoleAfter(s, ds), ![l] = RoleAfter(l, dl)],
        currentTerm |-> [currentTerm EXCEPT ![s] = ts, ![l] = TermAfter(l, dl, ts)],
        votedFor |-> [votedFor EXCEPT ![s] = VotedForAfter(s, ds), ![l] = VotedForAfter(l, dl)],
        votes |-> [votes EXCEPT ![s] = VotesAfter(s, ds), ![l] = VotesAfter(l, dl)],
        log |-> [log EXCEPT ![s] = logs],
        commitIndex |-> [commitIndex EXCEPT ![s] = cs],
        nextIndex |-> [nextIndex EXCEPT ![l][s] = IF success THEN last + 1 ELSE IF @ > 1 THEN @ - 1 ELSE 1],
        matchIndex |-> [matchIndex EXCEPT ![l][s] = IF success THEN last ELSE @]]

Replicate(l, s) ==
    /\ role[l] = "LEADER"
    /\ s # l
    /\ ~ReplicateNext(l, s).throws
    /\ Step(ReplicateNext(l, s))

\* Server.advanceCommitIndex: a leader looks at an entry of its log it has not marked committed, and asks the commit
\* rule, given the entry's term against its own and whether a majority of the servers hold it, itself among them. On
\* the committed rule an entry of the leader's term held by a majority is committed, and with it everything before it,
\* which the commit index moving up to it says; an entry from an earlier term is not committed by counting, however
\* many hold it (figure 8), and is committed only when an entry of the leader's term after it is. The leader may ask
\* about any uncommitted entry, as figure 2 of the paper has it: a leader that asked only about the first would
\* never commit a log that starts with an earlier term's entry, which OwnEntriesAreCommitted below forbids.
Holders(l, i) == {s \in Servers : matchIndex[l][s] >= i} \cup {l}
CommitNext(l, i) ==
    LET d == Commit!Decide("PENDING", [kind |-> "Replication", term |-> Order(l, log[l][i]), majority |-> Majority(Holders(l, i))])
    IN [throws |-> d.kind = "Throws", commits |-> d.kind = "Transition" /\ d.next = "COMMITTED"]

AdvanceCommit(l) ==
    /\ role[l] = "LEADER"
    /\ \E i \in commitIndex[l] + 1..Len(log[l]) :
        /\ ~CommitNext(l, i).throws
        /\ CommitNext(l, i).commits
        /\ commitIndex' = [commitIndex EXCEPT ![l] = i]
    /\ UNCHANGED <<role, currentTerm, votedFor, votes, log, nextIndex, matchIndex>>

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ role = [s \in Servers |-> "FOLLOWER"]
    /\ currentTerm = [s \in Servers |-> 0]
    /\ votedFor = [s \in Servers |-> "none"]
    /\ votes = [s \in Servers |-> {}]
    /\ log = [s \in Servers |-> <<>>]
    /\ commitIndex = [s \in Servers |-> 0]
    /\ nextIndex = [s \in Servers |-> Blank]
    /\ matchIndex = [s \in Servers |-> Blank]

Next ==
    \/ \E s \in Servers : Timeout(s)
    \/ \E c, v \in Servers : Canvass(c, v)
    \/ \E l \in Servers : ClientRequest(l) \/ AdvanceCommit(l)
    \/ \E l, s \in Servers : Replicate(l, s)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants.                                                             *)
(***************************************************************************)

Logs == UNION {[1..n -> 1..MaxTerm] : n \in 0..MaxEntries}

TypeOK ==
    /\ role \in [Servers -> {"FOLLOWER", "CANDIDATE", "LEADER"}]
    /\ currentTerm \in [Servers -> 0..MaxTerm]
    /\ votedFor \in [Servers -> Servers \cup {"none"}]
    /\ votes \in [Servers -> SUBSET Servers]
    /\ log \in [Servers -> Logs]
    /\ \A s \in Servers : commitIndex[s] \in 0..Len(log[s])
    /\ nextIndex \in [Servers -> [Servers -> 0..MaxEntries + 1]]
    /\ matchIndex \in [Servers -> [Servers -> 0..MaxEntries]]
    /\ \A l \in Servers : role[l] # "LEADER" => nextIndex[l] = Blank /\ matchIndex[l] = Blank

\* The kernels' exceptions: each action's record says whether a call it makes to a rule throws, and no action takes
\* such a step; this invariant says there is none to take. The IllegalStateException the commit rule reserves for an
\* entry from a term after the leader's is then impossible indeed: a server adopts a leader's term before it takes
\* the leader's entries, so no log holds an entry from a term after its server's.
KernelNeverThrows ==
    /\ \A s \in Servers : currentTerm[s] < MaxTerm => ~TimeoutNext(s).throws
    /\ \A c, v \in Servers : role[c] = "CANDIDATE" /\ v \notin votes[c] \cup {c} => ~CanvassNext(c, v).throws
    /\ \A l, s \in Servers : role[l] = "LEADER" /\ s # l => ~ReplicateNext(l, s).throws
    /\ \A l \in Servers : role[l] = "LEADER" => \A i \in commitIndex[l] + 1..Len(log[l]) : ~CommitNext(l, i).throws

\* Election safety (figure 3): at most one leader per term.
ElectionSafety ==
    \A s, t \in Servers : role[s] = "LEADER" /\ role[t] = "LEADER" /\ currentTerm[s] = currentTerm[t] => s = t

\* Log matching (figure 3): if two logs hold an entry of the same term at the same index, they are the same through
\* that index. The append rule's consistency check is what makes it so: a follower takes an entry only after the
\* entry before it, which it then holds as the leader does, and so on back to the start.
LogMatching ==
    \A s, t \in Servers : \A i \in 1..Min(Len(log[s]), Len(log[t])) :
        log[s][i] = log[t][i] => \A j \in 1..i : log[s][j] = log[t][j]

\* Leader completeness (figure 3): a leader holds every entry committed in its term or before. What a server knows
\* committed was committed by a leader of a term no later than the server's own, and the election restriction keeps
\* a candidate without it from the votes of a majority. A leader of an earlier term than the server's may be stale,
\* about to step down, and need not hold it.
LeaderCompleteness ==
    \A l, s \in Servers : role[l] = "LEADER" /\ currentTerm[l] >= currentTerm[s] =>
        \A i \in 1..commitIndex[s] : i <= Len(log[l]) /\ log[l][i] = log[s][i]

\* State machine safety (figure 3): no two servers apply different entries at one index. What each applies is the
\* log through its commit index.
StateMachineSafety ==
    \A s, t \in Servers : \A i \in 1..Min(commitIndex[s], commitIndex[t]) : log[s][i] = log[t][i]

(***************************************************************************)
(* Action properties: what every step of the system satisfies.             *)
(***************************************************************************)

\* A committed entry is never overwritten, and a commit index never goes backwards: once a server has applied an
\* entry, that entry stays at its index for good. This is state machine safety as the paper argues it, step by step:
\* the invariant above compares two servers' applied prefixes, and this says no server's own prefix changes.
CommittedEntriesNeverChange ==
    [][\A s \in Servers : commitIndex'[s] >= commitIndex[s] /\ \A i \in 1..commitIndex[s] : log'[s][i] = log[s][i]]_vars

\* A term never goes backwards on any server.
TermsNeverDecrease == [][\A s \in Servers : currentTerm'[s] >= currentTerm[s]]_vars

\* A leader's log only grows: a leader never truncates or overwrites its own entries (the leader append-only
\* property of figure 3).
LeaderAppendOnly ==
    [][\A l \in Servers : role[l] = "LEADER" /\ role'[l] = "LEADER" => Len(log'[l]) >= Len(log[l]) /\ \A i \in 1..Len(log[l]) : log'[l][i] = log[l][i]]_vars

(***************************************************************************)
(* Liveness: what the cluster gets round to, under fairness.               *)
(***************************************************************************)

\* Leader l's heartbeat resets server s's election timer: the role machine's decision on it has RESET_ELECTION_TIMER.
Resets(l, s) ==
    /\ role[l] = "LEADER"
    /\ s # l
    /\ LET d == Decide(role[s], [kind |-> "AppendEntries", term |-> Order(s, currentTerm[l])])
       IN d.kind = "Transition" /\ Has(d, "RESET_ELECTION_TIMER")

\* A server whose election timer nothing resets: it is not a leader, and no leader's heartbeats reset it.
Unled(s) == role[s] # "LEADER" /\ \A l \in Servers : ~Resets(l, s)

\* Each action's enabling condition, as ENABLED <<A>>_vars would compute it: the action's guard, and a step that
\* changes some variable, which a heartbeat to a follower that is caught up and knows every commit does not. TLC
\* computes ENABLED of an action with the rules inside it slowly, as RaftElection.tla explains; these predicates are
\* the same condition evaluated directly, and EnablingAgrees at the end checks that they are. The check matters: a
\* predicate that holds where the action cannot take a step makes its fairness condition unsatisfiable, no run is
\* fair, and the liveness check passes with nothing checked.
CanTimeout(s) == currentTerm[s] < MaxTerm /\ ~TimeoutNext(s).throws /\ Changes(TimeoutNext(s))
CanCanvass(c, v) == role[c] = "CANDIDATE" /\ v \notin votes[c] \cup {c} /\ ~CanvassNext(c, v).throws /\ Changes(CanvassNext(c, v))
CanReplicate(l, s) == role[l] = "LEADER" /\ s # l /\ ~ReplicateNext(l, s).throws /\ Changes(ReplicateNext(l, s))
CanAdvanceCommit(l) ==
    role[l] = "LEADER" /\ \E i \in commitIndex[l] + 1..Len(log[l]) : ~CommitNext(l, i).throws /\ CommitNext(l, i).commits

\* Fairness: what each server is assumed to get round to. A server whose timer nothing resets times out; a candidate
\* with a vote to ask for asks; a leader sends every follower its next entry or a heartbeat, and marks committed what
\* the commit rule lets it. Nothing is assumed about the clients: a leader may get no request, or any number up to
\* MaxEntries, so the properties hold of every workload. Each condition is weak fairness, WF_vars(A), written out as
\* TLA+ defines it: if A is enabled from some point on, A happens infinitely often. The replication conditions are
\* one per leader and follower, since a leader that kept sending to one follower and never to another would be fair
\* to the pair of them as a whole and starve the second.
Fairness ==
    /\ \A s \in Servers : <>[](Unled(s) /\ CanTimeout(s)) => []<><<Unled(s) /\ Timeout(s)>>_vars
    /\ <>[](\E c, v \in Servers : CanCanvass(c, v)) => []<><<\E c, v \in Servers : Canvass(c, v)>>_vars
    /\ \A l, s \in Servers : <>[]CanReplicate(l, s) => []<><<Replicate(l, s)>>_vars
    /\ \A l \in Servers : <>[]CanAdvanceCommit(l) => []<><<AdvanceCommit(l)>>_vars

LiveSpec == Spec /\ Fairness

\* The term budget: every term stays below MaxTerm, past which the model's timers do not fire. A run that spends it
\* may end with no leader, three candidates that voted for themselves, and nothing then replicates: the properties
\* below are about the runs that stay within it, in which a leader is elected and, after the last timer fires, stays.
WithinTheBudget == [](\A s \in Servers : currentTerm[s] < MaxTerm)

\* Every entry in a leader's log reaches every follower: from some point on, each follower's log holds the leader's
\* log as a prefix. The consistency check backs the leader up one entry at a time to the last entry the two logs
\* share, and the entries after it go over one at a time, each overwriting what the follower held at its index.
FollowersCatchUp ==
    WithinTheBudget => <>[](\A l, s \in Servers : role[l] = "LEADER" =>
        Len(log[s]) >= Len(log[l]) /\ \A i \in 1..Len(log[l]) : log[s][i] = log[l][i])

\* Every follower learns what the leader has committed: from some point on, no follower's commit index is behind
\* the leader's. The leader's commit index travels with every request, a heartbeat included, and a follower takes it
\* as far as its log is known to match the leader's. Not that the commit indices agree: a server elected after a
\* commit it had not heard of, with no entry of its own term to commit, knows less than its followers, for good if no
\* client request comes; which is the paper's reason for the no-op entry a leader appends on taking office (section
\* 8), and this model leaves it out.
FollowersLearnCommits ==
    WithinTheBudget => <>[](\A l, s \in Servers : role[l] = "LEADER" => commitIndex[s] >= commitIndex[l])

\* An entry a leader appended in its term is committed, unless the leader is deposed first: the entry reaches a
\* majority, and the commit rule commits an entry of the leader's term that a majority holds, and with it everything
\* before it. Nothing is claimed of an entry from an earlier term on its own, which the commit rule commits only
\* along with a later entry of the leader's own term, and a leader that gets no client request never has one.
OwnEntriesAreCommitted ==
    WithinTheBudget => \A l \in Servers, i \in 1..MaxEntries :
        (role[l] = "LEADER" /\ i <= Len(log[l]) /\ log[l][i] = currentTerm[l]) ~> (commitIndex[l] >= i \/ role[l] # "LEADER")

\* The enabling predicates agree with ENABLED in every reachable state. Checked by RaftReplicationEnabled.cfg, which
\* takes TLC a while, for the reason the predicates exist; run it after changing an action.
EnablingAgrees ==
    /\ \A s \in Servers : CanTimeout(s) <=> ENABLED <<Timeout(s)>>_vars
    /\ \A c, v \in Servers : CanCanvass(c, v) <=> ENABLED <<Canvass(c, v)>>_vars
    /\ \A l, s \in Servers : CanReplicate(l, s) <=> ENABLED <<Replicate(l, s)>>_vars
    /\ \A l \in Servers : CanAdvanceCommit(l) <=> ENABLED <<AdvanceCommit(l)>>_vars

=============================================================================
