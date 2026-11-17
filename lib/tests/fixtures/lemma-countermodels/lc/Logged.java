package lc;

import java.util.function.IntSupplier;

/** A final static field holding a StringBuilder: the field is final, the builder is not. */
public final class Logged {
    public static final StringBuilder LOG = new StringBuilder();
    public static final IntSupplier LENGTH = LOG::length;

    /** The builder's length: 0 from a fresh class. */
    public static int logged() {
        return LOG.length();
    }

    /** The same through a method reference that captured the builder. */
    public static int loggedThroughLambda() {
        return LENGTH.getAsInt();
    }
}
