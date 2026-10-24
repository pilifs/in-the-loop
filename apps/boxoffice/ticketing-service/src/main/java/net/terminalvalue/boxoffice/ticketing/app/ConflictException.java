package net.terminalvalue.boxoffice.ticketing.app;

/** The request is valid, but the current state does not allow it, for example because a seat is taken. */
public class ConflictException extends RuntimeException {
    public ConflictException(String message) {
        super(message);
    }
}
