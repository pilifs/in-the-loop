package lc;

import java.util.function.IntSupplier;

/** A lambda that captured an array, and the array, held by two final static fields. */
public final class Boxed {
    public static final int[] BOX;
    public static final IntSupplier FIRST;

    static {
        int[] b = {0};
        BOX = b;
        FIRST = () -> b[0];
    }

    /** The captured array's first cell: 0 from a fresh class. */
    public static int boxed() {
        return FIRST.getAsInt();
    }
}
