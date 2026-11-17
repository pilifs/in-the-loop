package lc;

/** A final static field its initializer copies from Table's array, which a caller can write once Table is initialized. */
public final class Copied {
    public static final int FIRST = Table.T[0];

    /** FIRST: what Table.T[0] was when Copied was initialized. */
    public static int first() {
        return FIRST;
    }
}
