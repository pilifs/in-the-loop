package datawork;

import org.apache.commons.lang3.ArrayUtils;

public final class NanSearch {
    static final long[] BITS = {0x7ff8000000000001L, 0xfff8000000000011L, 0x8000000000000000L, 0L, 0x3ff0000000000000L};
    public static long[] source(int code) {
        if (code == 901) return new long[]{0xfff0000000000000L, BITS[0], 0x7ff0000000000000L, BITS[2], BITS[3]};
        if (code < 3) return null;
        int n = code - 3, words = 1;
        for (int len = 0; len <= 3; len++, words *= 5) {
            int size = words * (len + 3);
            if (n < size) {
                int word = n / (len + 3);
                long[] cells = new long[len];
                for (int i = len - 1; i >= 0; i--) { cells[i] = BITS[word % 5]; word /= 5; }
                return cells;
            }
            n -= size;
        }
        throw new IllegalArgumentException();
    }
    public static int start(int code) {
        if (code == 901) return 0;
        if (code < 3) return code - 1;
        int n = code - 3, words = 1;
        for (int len = 0; len <= 3; len++, words *= 5) {
            int block = words * (len + 3);
            if (n < block) return n % (len + 3) - 1;
            n -= block;
        }
        throw new IllegalArgumentException();
    }
    public static double[] array(long[] bits) {
        if (bits == null) return null;
        double[] a = new double[bits.length];
        for (int i = 0; i < bits.length; i++) a[i] = Double.longBitsToDouble(bits[i]);
        return a;
    }
    static boolean nan(long bits) {
        return (bits & 0x7ff0000000000000L) == 0x7ff0000000000000L && (bits & 0xfffffffffffffL) != 0;
    }
    static int first(long[] bits, int start, long needle) {
        if (bits != null) for (int i = Math.max(0, start); i < bits.length; i++) {
            long x = bits[i];
            if (nan(needle) ? nan(x) : x == needle || (x << 1) == 0 && (needle << 1) == 0) return i;
        }
        return -1;
    }
    public static int search(double[] a, long needle, int start) {
        return ArrayUtils.indexOf(a, Double.longBitsToDouble(needle), start, 0.0);
    }
    static boolean untouched(double[] a, long[] bits) {
        if (a == null) return bits == null;
        for (int i = 0; i < a.length; i++) if (Double.doubleToRawLongBits(a[i]) != bits[i]) return false;
        return true;
    }
    static int check(int code, int lo, int hi) {
        long[] bits = source(code);
        double[] a = array(bits);
        int at = start(code);
        for (int t = lo; t < hi; t++)
            if (search(a, BITS[t], at) != first(bits, at, BITS[t]) || !untouched(a, bits)) return 0;
        return 1;
    }
    public static int nans(int code) { return check(code, 0, 2); }
    public static int numbers(int code) { return check(code, 2, 5); }
}
