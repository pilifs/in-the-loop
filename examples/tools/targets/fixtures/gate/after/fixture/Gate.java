package fixture;

/** The fixture's fixed revision: the deny check also refuses the other case of the denied name. */
public final class Gate {
    /** The denied code, 'A'. */
    public static final int DENIED = 65;

    private Gate() {
    }

    /** Whether a field with this code may be bound: every code but the denied one, in either case. */
    public static boolean allowed(int code) {
        return code != DENIED && code != DENIED + 32;
    }
}
