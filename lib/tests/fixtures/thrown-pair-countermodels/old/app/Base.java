package app;

/** The previous version's base failure: an IllegalArgumentException. */
public class Base extends IllegalArgumentException {
    public Base() {
        super("bad");
    }
}
