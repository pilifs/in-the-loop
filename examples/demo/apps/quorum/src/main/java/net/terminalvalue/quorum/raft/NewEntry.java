package net.terminalvalue.quorum.raft;

/**
 * What a follower holds at the index of the entry a leader sends: nothing was sent (a heartbeat), the follower's log
 * ends before the index, it holds the same entry there already, or it holds another one, from an earlier term.
 */
public enum NewEntry {
    NONE,
    ABSENT,
    SAME,
    CONFLICTING
}
