package app;

/** The new version's failure, of the same name: an IllegalStateException, which no handler for an IllegalArgumentException catches. */
public class Failure extends IllegalStateException {
    public Failure() {
        super("bad");
    }
}
