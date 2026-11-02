package net.terminalvalue.quorum.raft;

/**
 * How up to date a candidate's log is against the voter's (Ongaro and Ousterhout, section 5.4.1): the term of the
 * last entry decides, and between equal terms the longer log is ahead.
 */
public enum LogOrder {
    BEHIND,
    EVEN,
    AHEAD
}
