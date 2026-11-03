package net.terminalvalue.quorum.twopc;

/** A vote on its way from a participant to the coordinator. */
public record VoteMessage(String from, Vote vote) {}
