package app;

import java.io.UnsupportedEncodingException;

/** The previous version: each method calls a callee of Shared, which both versions share, and reads its outcome. */
public final class Entry {
    private Entry() {
    }

    /** The cell the callee filled. */
    public static int filled(int k) {
        int[] cells = new int[1];
        Shared.fill(cells, k);
        return cells[0];
    }

    /** The cell the callee copied into. */
    public static int copied(int k) {
        int[] from = {k};
        int[] cells = new int[1];
        Shared.copy(from, cells);
        return cells[0];
    }

    /** Two arrays of one content, by the identities Object.toString shows. */
    public static int hashed(int k) {
        return Shared.identity(new int[1]).equals(Shared.identity(new int[1])) ? 1 : 0;
    }

    /** The literal itself. */
    public static int interned(int k) {
        if (k > 0) {
            return Shared.isKey("key");
        }
        return 0;
    }

    /** Two calls' results, by identity. */
    public static int same(int k) {
        return Shared.name(k) == Shared.name(k) ? 1 : 0;
    }

    /** A result against the literal it may be, by identity. */
    public static int tagged(int k) {
        return Shared.tag(k) == "big" ? 1 : 0;
    }

    /** A checked exception the callee's JDK call throws. */
    public static int encoded(int k) {
        try {
            return Shared.size("nope") + k;
        } catch (UnsupportedEncodingException e) {
            return -1;
        }
    }

    /** An Error the JVM raises in a deep call. */
    public static int overflowed(int k) {
        try {
            return Shared.depth(k);
        } catch (StackOverflowError e) {
            return -1;
        }
    }

    /** An Error the JVM raises for a large array. */
    public static int exhausted(int k) {
        try {
            return Shared.make(k);
        } catch (OutOfMemoryError e) {
            return -1;
        }
    }

    /** The message of the exception the callee made. */
    public static int messaged(int k) {
        try {
            return Shared.check(k);
        } catch (IllegalArgumentException e) {
            return e.getMessage() == null ? 0 : 1;
        }
    }

    public static void main(String[] args) {
        System.out.println("filled=" + filled(5) + " copied=" + copied(5) + " hashed=" + hashed(0) + " interned=" + interned(1) + " same=" + same(1)
                + " tagged=" + tagged(2) + " encoded=" + encoded(0) + " overflowed=" + overflowed(100_000_000)
                + " exhausted=" + exhausted(Integer.MAX_VALUE) + " messaged=" + messaged(2));
    }
}
