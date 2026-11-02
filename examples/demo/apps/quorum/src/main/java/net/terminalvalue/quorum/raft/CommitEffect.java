package net.terminalvalue.quorum.raft;

/** What a leader does with an entry it marks committed: apply it, and everything before it, to the state machine. */
public enum CommitEffect {
    APPLY
}
