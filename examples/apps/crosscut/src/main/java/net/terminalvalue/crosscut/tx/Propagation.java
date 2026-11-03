package net.terminalvalue.crosscut.tx;

/** The transaction propagation behaviours of {@code @Transactional(propagation = ...)}. */
public enum Propagation {
    REQUIRED,
    REQUIRES_NEW,
    SUPPORTS,
    NOT_SUPPORTED,
    MANDATORY,
    NEVER,
    NESTED
}
