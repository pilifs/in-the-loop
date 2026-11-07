package net.terminalvalue.deliveries;

/** What the retries topic carries: the receiver's status, and the number of the attempt the dispatcher makes next. */
public record RetryScheduled(int status, int attempt) {}
