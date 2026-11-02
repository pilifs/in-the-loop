package net.terminalvalue.quorum.raft;

/** How the term carried by a message compares with this server's current term. */
public enum TermOrder {
    OLDER,
    CURRENT,
    NEWER
}
