package app;

import java.io.UnsupportedEncodingException;
import java.util.Arrays;

/**
 * The callees both versions share: the same bytes in old/ and new/. Each has a loop, so the call-level rule takes
 * it, and each depends on nothing but its arguments and its own code.
 */
public final class Shared {
    private Shared() {
    }

    /** Fills the array it is given with k. No instruction of its own stores into an array. */
    public static int fill(int[] cells, int k) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        Arrays.fill(cells, k);
        return rounds;
    }

    /** Copies the first array's first cell into the second's, through System.arraycopy. No instruction of its own
     * stores into an array. */
    public static int copy(int[] from, int[] cells) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        System.arraycopy(from, 0, cells, 0, 1);
        return rounds;
    }

    /** The array's identity as Object.toString gives it, through String.valueOf(Object). */
    public static String identity(int[] cells) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        return String.valueOf((Object) cells);
    }

    /** Whether it is given the very String the literal "key" is. */
    public static int isKey(String s) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        return s == "key" ? 1 : 0;
    }

    /** A String it builds: a new object at each call. */
    public static String name(int k) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < 3; i++) {
            b.append('x');
        }
        return b.toString();
    }

    /** One of two literals: the same object at each call that returns it. */
    public static String tag(int k) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        return k > 1 ? "big" : "small";
    }

    /** The length of "abc" in the named charset: UnsupportedEncodingException for a name the JDK does not know. */
    public static int size(String charset) throws UnsupportedEncodingException {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        return "abc".getBytes(charset).length + rounds;
    }

    /** k calls deep: a StackOverflowError for a k deep enough. */
    public static int depth(int k) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        return k <= 0 ? rounds : 1 + depth(k - 1);
    }

    /** An array of k longs: an OutOfMemoryError for k past what a JVM can make. */
    public static int make(int k) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        long[] a = new long[k];
        return a.length + rounds;
    }

    /** Throws an IllegalArgumentException with a message past 1. */
    public static int check(int k) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        if (k > 1) {
            throw new IllegalArgumentException("big");
        }
        return rounds;
    }
}
