package net.terminalvalue.quorum.raft;

/**
 * How far an entry of a leader's log has got, as the commit rule sees it: the entry's term against the leader's
 * current term, and whether a majority of the servers hold it, the leader among them.
 */
public record Replication(TermOrder term, boolean majority) {}
