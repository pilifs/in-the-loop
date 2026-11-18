package app;

/** The new version's failure, of the same name and superclass: no longer one a caller may retry. */
public class Marked extends RuntimeException {
    public Marked() {
        super("busy");
    }
}
