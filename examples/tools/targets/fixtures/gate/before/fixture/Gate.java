package fixture;

/** The fixture's vulnerable revision: a deny check that forgets one spelling of the denied name. */
public final class Gate {
    /** The denied code, 'A'. */
    public static final int DENIED = 65;

    private Gate() {
    }

    /** Whether a field with this code may be bound: every code but the denied one, compared as written. */
    public static boolean allowed(int code) {
        return code != DENIED;
    }
}
