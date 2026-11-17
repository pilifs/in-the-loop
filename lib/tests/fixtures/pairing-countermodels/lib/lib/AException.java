package lib;

/** One of two unrelated unchecked exceptions, neither of them a class the harness tells apart. */
public final class AException extends RuntimeException {
    public AException() {
        super("a");
    }
}
