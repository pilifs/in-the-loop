package net.terminalvalue.boxoffice.ticketing.app;

public class NotFoundException extends RuntimeException {
    public NotFoundException(String message) {
        super(message);
    }
}
