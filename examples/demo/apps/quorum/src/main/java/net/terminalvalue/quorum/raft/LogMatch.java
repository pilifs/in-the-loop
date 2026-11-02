package net.terminalvalue.quorum.raft;

/**
 * How a follower's log stands at the entry before the ones a leader sends (Ongaro and Ousterhout, section 5.3): it
 * ends before that index, holds another entry there, or holds the leader's entry, in which case everything before it
 * matches the leader's log as well.
 */
public enum LogMatch {
    MISSING,
    CONFLICTING,
    MATCHING
}
