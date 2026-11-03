package net.terminalvalue.quorum.raft;

/**
 * A leader's AppendEntries request, as the append rule sees it: what the follower holds at the index of the entry
 * sent, and whether the leader's commit index, clipped to the last entry sent, is ahead of the follower's.
 */
public record AppendRequest(NewEntry entry, boolean commitAhead) {}
