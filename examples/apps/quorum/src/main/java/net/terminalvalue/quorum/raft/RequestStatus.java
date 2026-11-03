package net.terminalvalue.quorum.raft;

/**
 * Where a leader stands with an AppendEntries request it sent a follower, when the reply comes in (Ongaro and
 * Ousterhout, section 5.3): the reply is awaited, telling the leader something about the follower's log its record
 * of the follower does not hold yet, or the record reflects it already and the reply is a late or repeated one: an
 * acceptance of entries the leader knows the follower holds, or a refusal the leader has already backed up from or
 * at an entry it knows the follower holds.
 */
public enum RequestStatus {
    AWAITED,
    ANSWERED
}
