package lib;

/** The other: a caller that catches {@link AException} does not catch this. */
public final class BException extends RuntimeException {
    public BException() {
        super("b");
    }
}
