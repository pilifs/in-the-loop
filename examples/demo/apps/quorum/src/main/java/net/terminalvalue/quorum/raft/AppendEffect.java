package net.terminalvalue.quorum.raft;

/** What a follower does to its log on a request it accepts: drop the conflicting entry and everything after it, append the entry sent, advance its commit index. */
public enum AppendEffect {
    TRUNCATE,
    APPEND,
    ADVANCE_COMMIT
}
