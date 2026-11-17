package lc;

import java.security.MessageDigest;
import java.util.Arrays;

/** Final static arrays a method reads in bulk, through a call the engine models rather than an array load. */
public final class Cloned {
    public static final int[] T = {0};
    public static final byte[] KEY = {0};

    /** T's first cell, read off a copy of T. */
    public static int cloned() {
        return T.clone()[0];
    }

    /** The same through Arrays.copyOf. */
    public static int copiedOf() {
        return Arrays.copyOf(T, 1)[0];
    }

    /** Whether KEY is the one-byte array {0}. */
    public static boolean zeroKey() {
        return MessageDigest.isEqual(KEY, new byte[] {0});
    }
}
