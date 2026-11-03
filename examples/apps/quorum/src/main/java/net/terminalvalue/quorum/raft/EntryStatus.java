package net.terminalvalue.quorum.raft;

/** Whether a leader has marked an entry of its log committed. */
public enum EntryStatus {
    PENDING,
    COMMITTED
}
