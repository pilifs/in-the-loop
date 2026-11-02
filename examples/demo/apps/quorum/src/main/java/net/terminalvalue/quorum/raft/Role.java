package net.terminalvalue.quorum.raft;

/** The role of a Raft server. */
public enum Role {
    FOLLOWER,
    CANDIDATE,
    LEADER
}
