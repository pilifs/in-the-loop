---------------------------- MODULE RaftElection ----------------------------
(***************************************************************************)
(* Raft leader election (Ongaro and Ousterhout, section 5.2) as a          *)
(* distributed system: the servers, their terms, their votes, and the      *)
(* RPCs between them. TLC explores every interleaving for the servers and  *)
(* terms in RaftElection.cfg, checks the invariants in every state it      *)
(* reaches, and checks the action properties on every step: that terms    *)
(* never go backwards, and that a leader never campaigns. Three more       *)
(* configurations check the same model other ways: RaftElectionFour.cfg   *)
(* has four servers, a cluster in which a tally can fall short of a       *)
(* majority by more than one vote, under a symmetry set;                  *)
(* RaftElectionInductive.cfg checks that the invariant Inductive below is *)
(* inductive, from every state it admits rather than from Init;           *)
(* RaftElectionLive.cfg checks the liveness properties at the end, under  *)
(* the fairness conditions stated with them; and RaftElectionLogs.cfg     *)
(* gives one server a log a deposed leader left behind, and checks that   *)
(* the election restriction keeps it from being elected.                  *)
(*                                                                         *)
(* Neither a server's role transitions nor its vote are written here.     *)
(* Decide(role, event) is generated from the behavioural contract of      *)
(* RoleMachine#decide (RoleMachineContract.tla), and Vote!Decide(ballot,  *)
(* request) from that of VoteRule#decide (VoteRuleContract.tla, brought   *)
(* in as an instance so that the two operators of one name can coexist);  *)
(* jvmcontract proves the bytecode obeys each on every input. The role    *)
(* machine sees a message's term only as it compares with the server's    *)
(* own (NEWER, CURRENT, OLDER), and the vote rule sees the voter's ballot *)
(* (OPEN, FOR_THE_CANDIDATE, FOR_ANOTHER) and the candidate's term and    *)
(* log as they compare with the voter's, as the Java does: the comparing  *)
(* is what VoteRule.grant adds around the rule, and this model repeats    *)
(* it. Each action names the Java operation it stands for.                *)
(*                                                                         *)
(* Simplifications: the logs are fixed, Logs below, since the model has   *)
(* no replication, so the election restriction is checked for the logs a *)
(* configuration gives and not for every log a run could build; a        *)
(* heartbeat carries no entries; an RPC is one step, the                  *)
(* request and its reply together, so a server always answers with the    *)
(* term it has now, and a stale server learns of a newer term the moment   *)
(* it talks to one that has it; terms stop at MaxTerm, past which no timer *)
(* fires; election timeouts fire whenever the model likes, and             *)
(* RESET_ELECTION_TIMER matters only to the fairness conditions, which     *)
(* assume that a timer no heartbeat resets fires eventually.               *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, TLC, RoleMachineContract

Vote == INSTANCE VoteRuleContract

CONSTANTS
    Servers,
    MaxTerm,
    LeftBehind    \* the servers whose log a deposed leader left behind: see Logs

VARIABLES
    role,         \* server -> FOLLOWER, CANDIDATE or LEADER
    currentTerm,  \* server -> its term
    votedFor,     \* server -> the server it voted for in its term, or "none"
    votes         \* server -> the servers whose vote it holds in its term

vars == <<role, currentTerm, votedFor, votes>>

Majority(S) == Cardinality(S) * 2 > Cardinality(Servers)

\* The servers are interchangeable: two states that differ only by a permutation of their names behave alike, so a
\* configuration may tell TLC (SYMMETRY Perms) to explore one state of each such class.
Perms == Permutations(Servers)

\* How a message's term t compares with a server's own, which is all the role machine looks at.
OrderOf(own, t) == IF t > own THEN "NEWER" ELSE IF t = own THEN "CURRENT" ELSE "OLDER"
Order(s, t) == OrderOf(currentTerm[s], t)

\* The logs, which nothing in this model changes, as a sequence of entry terms per server. Every server holds an
\* entry of term 1 and, at index 2, an entry of term 2, which is committed when a majority holds it; except the
\* servers in LeftBehind, which hold three entries of term 1 instead: the entries a leader of term 1 appended and
\* never got to commit before the cluster moved on, and never had replaced (figure 7 of the paper, server f). Such
\* a server's log is longer than the others' and behind them, and a vote rule that let it win would elect a leader
\* without the committed entry, which it would then overwrite. With LeftBehind empty, every log is the same.
Logs == [s \in Servers |-> IF s \in LeftBehind THEN <<1, 1, 1>> ELSE <<1, 2>>]

LastTerm(log) == IF Len(log) = 0 THEN 0 ELSE log[Len(log)]

\* How candidate c's log compares with voter v's, as Server.onRequestVote computes it for the vote rule: by the term
\* of the last entry first, and between equal terms by length.
LogOrder(c, v) ==
    IF LastTerm(Logs[c]) # LastTerm(Logs[v]) THEN (IF LastTerm(Logs[c]) > LastTerm(Logs[v]) THEN "AHEAD" ELSE "BEHIND")
    ELSE IF Len(Logs[c]) > Len(Logs[v]) THEN "AHEAD" ELSE IF Len(Logs[c]) = Len(Logs[v]) THEN "EVEN" ELSE "BEHIND"

Has(d, effect) == \E i \in 1..Len(d.effects) : d.effects[i] = effect
Adopts(d) == d.kind = "Transition" /\ Has(d, "ADOPT_TERM")

\* A server after the role machine's decision on a message of term t: its role, and with ADOPT_TERM the message's
\* term, with the vote and the tally of the old term forgotten.
RoleAfter(s, d) == IF d.kind = "Transition" THEN d.next ELSE role[s]
TermAfter(s, d, t) == IF Adopts(d) THEN t ELSE currentTerm[s]
VotedForAfter(s, d) == IF Adopts(d) THEN "none" ELSE votedFor[s]
VotesAfter(s, d) == IF Adopts(d) THEN {} ELSE votes[s]

\* Each action below computes its next state as a record of the four variables, so that the step it takes and
\* whether the step changes anything (the fairness conditions need to know) are one computation.
Step(n) == role' = n.role /\ currentTerm' = n.currentTerm /\ votedFor' = n.votedFor /\ votes' = n.votes
Changes(n) == <<n.role, n.currentTerm, n.votedFor, n.votes>> # vars

(***************************************************************************)
(* The servers.                                                            *)
(***************************************************************************)

\* Server.onElectionTimeout: no heartbeat arrived in time. The decision's effects: INCREMENT_TERM starts a new
\* term, in which the server has not voted yet (a vote is cast per term); VOTE_FOR_SELF starts a new tally, the
\* server's own vote in it, and is the only thing that empties a tally short of adopting a term; REQUEST_VOTES is
\* the canvass below, one server whose vote the tally lacks at a time.
TimeoutNext(s) ==
    LET d == Decide(role[s], [kind |-> "ElectionTimeout"])
        t == IF d.kind = "Transition" /\ Has(d, "INCREMENT_TERM") THEN currentTerm[s] + 1 ELSE currentTerm[s]
        self == d.kind = "Transition" /\ Has(d, "VOTE_FOR_SELF")
    IN [throws |-> d.kind = "Throws",
        role |-> [role EXCEPT ![s] = RoleAfter(s, d)],
        currentTerm |-> [currentTerm EXCEPT ![s] = t],
        votedFor |-> [votedFor EXCEPT ![s] = IF self THEN s ELSE IF t > currentTerm[s] THEN "none" ELSE @],
        votes |-> [votes EXCEPT ![s] = IF self THEN {s} ELSE @]]

Timeout(s) == currentTerm[s] < MaxTerm /\ ~TimeoutNext(s).throws /\ Step(TimeoutNext(s))

\* Server.requestVote, one RPC: candidate c asks server v for its vote and gets the answer.
\* On v, Server.onRequestVote: the role machine first (a candidate's newer term is adopted), then the vote rule on
\* the server as it then is, given v's ballot as it stands for c (open, cast for c, cast for another) and c's term
\* and log against v's own: a candidate from the past or with a log behind the voter's is refused, and otherwise
\* the vote is granted unless the ballot is cast for another candidate of the term. A granted vote is v's ballot.
\* On c, Server.onVote: the reply carries v's term, which goes through the role machine (a newer one is adopted);
\* a candidate adds a granted vote to its tally, and the tally goes through the role machine as VotesCounted: a
\* majority makes it the leader.
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
        votes |-> [votes EXCEPT ![v] = VotesAfter(v, dv), ![c] = tally]]

Canvass(c, v) ==
    /\ role[c] = "CANDIDATE"
    /\ v \notin votes[c] \cup {c}
    /\ ~CanvassNext(c, v).throws
    /\ Step(CanvassNext(c, v))

\* Server.appendEntries, one RPC: leader l sends server s a heartbeat and gets the answer.
\* On s, Server.onAppendEntries: a newer term is adopted, a candidate yields to the leader of its term, and a stale
\* leader is rejected. On l, Server.onAppendReply: the reply carries s's term, which goes through the role machine;
\* a stale leader steps down. (A leader that hears a leader of its own term throws in the Java; the model has no
\* step for it, and KernelNeverThrows, below, says there is never one to take.)
HeartbeatNext(l, s) ==
    LET ds == Decide(role[s], [kind |-> "AppendEntries", term |-> Order(s, currentTerm[l])])
        ts == TermAfter(s, ds, currentTerm[l])
        dl == Decide(role[l], [kind |-> "Response", term |-> Order(l, ts)])
    IN [throws |-> ds.kind = "Throws",
        role |-> [role EXCEPT ![s] = RoleAfter(s, ds), ![l] = RoleAfter(l, dl)],
        currentTerm |-> [currentTerm EXCEPT ![s] = ts, ![l] = TermAfter(l, dl, ts)],
        votedFor |-> [votedFor EXCEPT ![s] = VotedForAfter(s, ds), ![l] = VotedForAfter(l, dl)],
        votes |-> [votes EXCEPT ![s] = VotesAfter(s, ds), ![l] = VotesAfter(l, dl)]]

Heartbeat(l, s) ==
    /\ role[l] = "LEADER"
    /\ s # l
    /\ ~HeartbeatNext(l, s).throws
    /\ Step(HeartbeatNext(l, s))

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

\* The kernels' exceptions. Each action's record says whether a call it makes to the role machine or the vote rule
\* throws, and no action takes such a step; this invariant says there is none to take. The IllegalStateException
\* the Java reserves for an input it holds impossible (a leader hearing a leader of its own term) is then impossible
\* indeed, in every reachable state: a change that makes a kernel throw on an input the protocol can deliver
\* violates it.
KernelNeverThrows ==
    /\ \A s \in Servers : currentTerm[s] < MaxTerm => ~TimeoutNext(s).throws
    /\ \A c, v \in Servers : role[c] = "CANDIDATE" /\ v \notin votes[c] \cup {c} => ~CanvassNext(c, v).throws
    /\ \A l, s \in Servers : role[l] = "LEADER" /\ s # l => ~HeartbeatNext(l, s).throws

\* Election safety (Raft, figure 3): at most one leader per term.
ElectionSafety ==
    \A s, t \in Servers : role[s] = "LEADER" /\ role[t] = "LEADER" /\ currentTerm[s] = currentTerm[t] => s = t

\* A leader holds the votes of a majority of the servers, its own among them.
LeaderHasAMajority == \A s \in Servers : role[s] = "LEADER" => s \in votes[s] /\ Majority(votes[s])

\* Leader completeness (Raft, figure 3), for the logs of the configuration: a leader's log holds every committed
\* entry, an entry being committed once a majority of the servers hold it. The election restriction is what makes
\* it so: a candidate needs votes from a majority, and a voter grants only a candidate whose log is at least as up
\* to date as its own, so one of the voters holds the entry and the leader's log is at least as up to date as that
\* voter's. RaftElectionLogs.cfg checks it with a server left behind; with every log the same it holds trivially.
Entries == UNION {{<<i, Logs[s][i]>> : i \in DOMAIN Logs[s]} : s \in Servers}
Holds(s, e) == e[1] \in DOMAIN Logs[s] /\ Logs[s][e[1]] = e[2]
Committed(e) == Majority({s \in Servers : Holds(s, e)})
LeaderCompleteness == \A l \in Servers : role[l] = "LEADER" => \A e \in Entries : Committed(e) => Holds(l, e)

(***************************************************************************)
(* The inductive invariant. ElectionSafety holds in every reachable state,  *)
(* but a state that satisfies it and one step of Next do not give a state  *)
(* that satisfies it: TLC proves it reachable state by reachable state,    *)
(* and the proof says nothing about states a longer run or a bigger        *)
(* cluster would reach. Inductive is stronger, and closed under Next: from *)
(* any state it admits, reachable or not, every step lands in a state it   *)
(* admits (RaftElectionInductive.cfg checks exactly that, with Inductive   *)
(* as the initial predicate). Since Init satisfies it and it implies       *)
(* ElectionSafety, that is a proof of election safety by induction, for    *)
(* every run of the configured cluster however long, and it is the kind of *)
(* argument that carries over to any cluster size. Its conjuncts are the   *)
(* reasons two leaders cannot share a term: a leader's majority was cast   *)
(* for it in its term, a server casts one vote per term, so two majorities *)
(* of one term would need a voter they cannot share. A counterexample is   *)
(* one step: the state it starts from need not be reachable, so it is      *)
(* either a bug or a conjunct too strong for a correct change; the         *)
(* configurations that run from Init tell which.                           *)
(***************************************************************************)

\* A vote in a tally was cast in the tally's term: the voter is still in that term and voted for the tally's owner,
\* or has since moved to a newer term, in which it may vote again.
VotesAreBound ==
    \A s, v \in Servers : v \in votes[s] /\ v # s =>
        \/ currentTerm[v] > currentTerm[s]
        \/ currentTerm[v] = currentTerm[s] /\ votedFor[v] = s

\* No server's vote is in two tallies of one term.
TalliesOfATermAreDisjoint ==
    \A s, t \in Servers : s # t /\ currentTerm[s] = currentTerm[t] => votes[s] \cap votes[t] = {}

\* A candidate or leader voted for itself, and holds its own vote.
CampaignersVoteForThemselves ==
    \A s \in Servers : role[s] # "FOLLOWER" => votedFor[s] = s /\ s \in votes[s]

\* A tally is empty, or holds its owner's vote and its owner voted for itself: VOTE_FOR_SELF starts a tally, and
\* until a new term empties it the vote it started with stands.
TalliesHoldTheirOwnersVote == \A s \in Servers : votes[s] = {} \/ (s \in votes[s] /\ votedFor[s] = s)

\* Nothing happens in term 0: a timer that fires starts term 1.
TermZeroIsQuiet ==
    \A s \in Servers : currentTerm[s] = 0 => role[s] = "FOLLOWER" /\ votedFor[s] = "none" /\ votes[s] = {}

Inductive ==
    /\ TypeOK
    /\ ElectionSafety
    /\ LeaderHasAMajority
    /\ VotesAreBound
    /\ TalliesOfATermAreDisjoint
    /\ CampaignersVoteForThemselves
    /\ TalliesHoldTheirOwnersVote
    /\ TermZeroIsQuiet

\* Inductive, written so that TLC can enumerate the states it admits: each variable drawn from its type, and each
\* conjunct placed right after the last variable it mentions, so that TLC drops a partial state as soon as one
\* fails rather than after building all of them.
InductiveInit ==
    /\ currentTerm \in [Servers -> 0..MaxTerm]
    /\ role \in [Servers -> {"FOLLOWER", "CANDIDATE", "LEADER"}]
    /\ \A s \in Servers : currentTerm[s] = 0 => role[s] = "FOLLOWER"
    /\ ElectionSafety
    /\ votedFor \in [Servers -> Servers \cup {"none"}]
    /\ \A s \in Servers : role[s] # "FOLLOWER" => votedFor[s] = s
    /\ \A s \in Servers : currentTerm[s] = 0 => votedFor[s] = "none"
    /\ votes \in {f \in [Servers -> SUBSET Servers] : \A s \in Servers : f[s] = {} \/ s \in f[s]}
    /\ TalliesHoldTheirOwnersVote
    /\ Inductive

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

(***************************************************************************)
(* Liveness, checked by RaftElectionLive.cfg. Raft elects a leader by     *)
(* randomizing the election timeouts, so that eventually one server's     *)
(* timer fires alone: a matter of timing, which this model has no clock   *)
(* for, so it cannot say that a leader is elected within any number of    *)
(* terms (every term can split). What it states is weaker and still       *)
(* worth checking: under the fairness conditions below, a run that stays  *)
(* within its term budget elects a leader, so that the only way to have   *)
(* no leader is to keep spending terms, and a leader whose term the       *)
(* cluster has left steps down. A change can keep every safety property   *)
(* and break these: a retry that stays in its term leaves three           *)
(* candidates asking each other forever, and TLC shows the run.           *)
(***************************************************************************)

\* Leader l's heartbeat resets server s's election timer: the role machine's decision on it has RESET_ELECTION_TIMER.
Resets(l, s) ==
    /\ role[l] = "LEADER"
    /\ s # l
    /\ LET d == Decide(role[s], [kind |-> "AppendEntries", term |-> Order(s, currentTerm[l])])
       IN d.kind = "Transition" /\ Has(d, "RESET_ELECTION_TIMER")

\* A server whose election timer nothing resets: it is not a leader (a leader's election timer is off), and no
\* leader's heartbeats reset it.
Unled(s) == role[s] # "LEADER" /\ \A l \in Servers : ~Resets(l, s)

\* Each action's enabling condition, as ENABLED <<A>>_vars would compute it: the action's guard, and a step that
\* changes some variable. TLC computes ENABLED of an action with the role machine inside it slowly, once per step
\* of the liveness check, which made the check take a minute; these predicates are the same condition evaluated
\* directly, and EnablingAgrees at the end checks that they are.
CanTimeout(s) == currentTerm[s] < MaxTerm /\ ~TimeoutNext(s).throws /\ Changes(TimeoutNext(s))
CanCanvass(c, v) == role[c] = "CANDIDATE" /\ v \notin votes[c] \cup {c} /\ ~CanvassNext(c, v).throws /\ Changes(CanvassNext(c, v))
CanHeartbeat(l, s) == role[l] = "LEADER" /\ s # l /\ ~HeartbeatNext(l, s).throws /\ Changes(HeartbeatNext(l, s))

\* Fairness: what each server is assumed to get round to. A server whose timer nothing resets times out; a
\* candidate with a vote to ask for asks; a leader with a heartbeat to send sends it. Nothing is assumed about which
\* timer fires first, or how often: those are the environment's choices. Each condition is weak fairness,
\* WF_vars(A), written out as TLA+ defines it: if A is enabled from some point on, A happens infinitely often.
Fairness ==
    /\ \A s \in Servers : <>[](Unled(s) /\ CanTimeout(s)) => []<><<Unled(s) /\ Timeout(s)>>_vars
    /\ <>[](\E c, v \in Servers : CanCanvass(c, v)) => []<><<\E c, v \in Servers : Canvass(c, v)>>_vars
    /\ <>[](\E l, s \in Servers : CanHeartbeat(l, s)) => []<><<\E l, s \in Servers : Heartbeat(l, s)>>_vars

LiveSpec == Spec /\ Fairness

\* The term budget: every term stays below MaxTerm, past which the model's timers do not fire.
WithinTheBudget == [](\A s \in Servers : currentTerm[s] < MaxTerm)

\* A run that stays within the term budget elects a leader. With no leader, every server's timer keeps firing, and
\* each firing starts a term, so the only runs without a leader are the ones that spend the budget: a run in which
\* the terms stop and no leader comes is a cluster that has stopped trying.
ALeaderIsElected == WithinTheBudget => <>(\E s \in Servers : role[s] = "LEADER")

\* A leader whose term the cluster has left steps down: its heartbeat to a server with a newer term, or that
\* server's request for a vote, tells it.
StaleLeadersStepDown ==
    \A l \in Servers : (role[l] = "LEADER" /\ \E s \in Servers : currentTerm[s] > currentTerm[l]) ~> role[l] # "LEADER"

\* The enabling predicates agree with ENABLED in every reachable state. Checked by RaftElectionEnabled.cfg, which
\* takes TLC the better part of a minute, for the reason the predicates exist; run it after changing an action.
EnablingAgrees ==
    /\ \A s \in Servers : CanTimeout(s) <=> ENABLED <<Timeout(s)>>_vars
    /\ \A c, v \in Servers : CanCanvass(c, v) <=> ENABLED <<Canvass(c, v)>>_vars
    /\ \A l, s \in Servers : CanHeartbeat(l, s) <=> ENABLED <<Heartbeat(l, s)>>_vars

=============================================================================
