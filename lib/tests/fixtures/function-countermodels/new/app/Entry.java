package app;

import java.io.UnsupportedEncodingException;

/** The new version: each method calls the same callee of Shared as the previous version, or none. */
public final class Entry {
    private Entry() {
    }

    /** The callee's array is not read. */
    public static int filled(int k) {
        int[] cells = new int[1];
        Shared.fill(cells, k);
        return 0;
    }

    /** The callee's array is not read. */
    public static int copied(int k) {
        int[] from = {k};
        int[] cells = new int[1];
        Shared.copy(from, cells);
        return 0;
    }

    /** One array, by the identity Object.toString shows, against itself. */
    public static int hashed(int k) {
        String identity = Shared.identity(new int[1]);
        return identity.equals(identity) ? 1 : 0;
    }

    /** A String of the literal's content that is another object. */
    public static int interned(int k) {
        if (k > 0) {
            return Shared.isKey(new StringBuilder("ke").append('y').toString());
        }
        return 0;
    }

    /** One call's result, by identity with itself. */
    public static int same(int k) {
        String name = Shared.name(k);
        return name == name ? 1 : 0;
    }

    /** The callee is called, and its result not compared. */
    public static int tagged(int k) {
        Shared.tag(k);
        return 0;
    }

    /** The same call, another answer to the exception. */
    public static int encoded(int k) {
        try {
            return Shared.size("nope") + k;
        } catch (UnsupportedEncodingException e) {
            return -2;
        }
    }

    /** The same call, another answer to the Error. */
    public static int overflowed(int k) {
        try {
            return Shared.depth(k);
        } catch (StackOverflowError e) {
            return -2;
        }
    }

    /** The same call, another answer to the Error. */
    public static int exhausted(int k) {
        try {
            return Shared.make(k);
        } catch (OutOfMemoryError e) {
            return -2;
        }
    }

    /** The same call; the message is not read. */
    public static int messaged(int k) {
        try {
            return Shared.check(k);
        } catch (IllegalArgumentException e) {
            return 0;
        }
    }

    public static void main(String[] args) {
        System.out.println("filled=" + filled(5) + " copied=" + copied(5) + " hashed=" + hashed(0) + " interned=" + interned(1) + " same=" + same(1)
                + " tagged=" + tagged(2) + " encoded=" + encoded(0) + " overflowed=" + overflowed(100_000_000)
                + " exhausted=" + exhausted(Integer.MAX_VALUE) + " messaged=" + messaged(2));
    }
}
