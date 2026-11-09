package fixture;

/** A constructed mutation of the fixed revision, never a real revision: the fix normalizes one side only, so it
 * refuses the lower case and forgets the upper. It must fail the same security claim and control as the vulnerable
 * revision does. Base revision: gate/after; its patch hash is recorded by build_fixtures.py. */
public final class Gate {
    /** The denied code, 'A'. */
    public static final int DENIED = 65;

    private Gate() {
    }

    /** Whether a field with this code may be bound. */
    public static boolean allowed(int code) {
        return code != DENIED + 32;
    }
}
