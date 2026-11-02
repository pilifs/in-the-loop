package net.terminalvalue.quorum.raft;

/** A candidate's request for a vote, as the vote rule sees it: its term and its log, each against the voter's own. */
public record VoteRequest(TermOrder term, LogOrder log) {}
