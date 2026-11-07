package net.terminalvalue.deliveries;

/** What the dead-letter topic carries: the receiver's last status, and how many attempts the delivery had. */
public record DeadLettered(int status, int attempts) {}
