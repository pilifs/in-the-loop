package net.terminalvalue.quorum.raft;

/** What the server does when its role machine transitions. */
public enum RoleEffect {
    /** Take the term of the message that was ahead, and forget the vote cast in the old term. */
    ADOPT_TERM,
    INCREMENT_TERM,
    VOTE_FOR_SELF,
    REQUEST_VOTES,
    RESET_ELECTION_TIMER,
    SEND_HEARTBEATS
}
