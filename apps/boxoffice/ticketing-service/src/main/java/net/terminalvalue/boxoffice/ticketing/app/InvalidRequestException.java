package net.terminalvalue.boxoffice.ticketing.app;

public class InvalidRequestException extends RuntimeException {
    public InvalidRequestException(String message) {
        super(message);
    }
}
