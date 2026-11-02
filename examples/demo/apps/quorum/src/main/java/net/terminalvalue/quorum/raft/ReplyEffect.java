package net.terminalvalue.quorum.raft;

/**
 * What a leader does to its record of a follower on a reply: move the follower's match index up through the entries
 * accepted and its next index past them, or move the next index back by one, to try again from one entry earlier.
 */
public enum ReplyEffect {
    ADVANCE,
    BACK_UP
}
