package net.terminalvalue.mica.interp;

/**
 * The comparison instructions of JVMS §6.5 that push -1, 0 or 1: {@code lcmp}, and the floating-point pairs
 * {@code fcmpg}/{@code fcmpl} and {@code dcmpg}/{@code dcmpl}. The pairs differ only when an operand is NaN:
 * the {@code g} form pushes 1 and the {@code l} form -1, so that the compiler can pick the one that sends a NaN
 * down the false branch of the comparison it is compiling.
 */
public final class Comparison {

    private Comparison() {}

    /** {@code lcmp}. */
    public static int lcmp(long a, long b) {
        if (a < b) {
            return -1;
        }
        return a > b ? 1 : 0;
    }

    /**
     * {@code fcmpg} when {@code nanIsGreater}, else {@code fcmpl}. The comparison is the IEEE 754 one: -0.0
     * equals 0.0, and a NaN is neither less than, equal to, nor greater than anything.
     */
    public static int fcmp(float a, float b, boolean nanIsGreater) {
        if (a < b) {
            return -1;
        }
        if (a > b) {
            return 1;
        }
        if (a == b) {
            return 0;
        }
        return nanIsGreater ? 1 : -1;
    }

    /** {@code dcmpg} when {@code nanIsGreater}, else {@code dcmpl}. */
    public static int dcmp(double a, double b, boolean nanIsGreater) {
        if (a < b) {
            return -1;
        }
        if (a > b) {
            return 1;
        }
        if (a == b) {
            return 0;
        }
        return nanIsGreater ? 1 : -1;
    }
}
