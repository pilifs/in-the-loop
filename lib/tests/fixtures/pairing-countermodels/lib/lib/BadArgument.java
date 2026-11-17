package lib;

/** A subclass of IllegalArgumentException: a caller may catch it and let its superclass through. */
public final class BadArgument extends IllegalArgumentException {
    public BadArgument() {
        super("bad");
    }
}
