package app;

/** The previous version's failure: an IllegalArgumentException, which a caller's handler for one catches. */
public class Failure extends IllegalArgumentException {
    public Failure() {
        super("bad");
    }
}
