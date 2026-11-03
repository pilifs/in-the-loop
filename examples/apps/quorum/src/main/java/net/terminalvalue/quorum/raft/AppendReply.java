package net.terminalvalue.quorum.raft;

/** A follower's reply to an AppendEntries request, as the reply rule sees it: whether the follower accepted the request. */
public record AppendReply(boolean accepted) {}
