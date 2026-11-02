package net.terminalvalue.quorum.raft;

/** A voter's ballot in its current term, as it stands for the candidate asking: not cast, cast for that candidate, or cast for another. */
public enum Ballot {
    OPEN,
    FOR_THE_CANDIDATE,
    FOR_ANOTHER
}
