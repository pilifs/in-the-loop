package app;

/** The previous version's failure: a RuntimeException a caller may retry. */
public class Marked extends RuntimeException implements Retryable {
    public Marked() {
        super("busy");
    }
}
