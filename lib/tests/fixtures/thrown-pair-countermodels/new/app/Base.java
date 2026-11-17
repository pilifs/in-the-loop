package app;

/** The new version's base failure, of the same name: an IllegalStateException. */
public class Base extends IllegalStateException {
    public Base() {
        super("bad");
    }
}
