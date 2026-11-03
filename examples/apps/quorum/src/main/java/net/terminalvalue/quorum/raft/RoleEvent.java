package net.terminalvalue.quorum.raft;

/**
 * What can happen to a Raft server, as far as its role is concerned. Terms are abstracted to how they compare with
 * the server's own ({@link TermOrder}), which is all the role machine looks at; the log comparison of a vote is
 * {@link VoteRule}'s business.
 */
public sealed interface RoleEvent {

    /** No heartbeat arrived within the election timeout. */
    record ElectionTimeout() implements RoleEvent {}

    /** The votes of the current election were counted. */
    record VotesCounted(boolean majority) implements RoleEvent {}

    /** An AppendEntries RPC (a heartbeat or log entries) from a server that believes it is the leader. */
    record AppendEntries(TermOrder term) implements RoleEvent {}

    /** A RequestVote RPC from a candidate. */
    record RequestVote(TermOrder term) implements RoleEvent {}

    /** A reply to one of this server's own RPCs. */
    record Response(TermOrder term) implements RoleEvent {}
}
