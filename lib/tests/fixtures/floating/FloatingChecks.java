package fixtures;

import java.lang.reflect.Array;

public class FloatingChecks {
    private static final double[] VALUES = {
        Double.NEGATIVE_INFINITY, -1.0, -Double.MIN_VALUE, -0.0, 0.0,
        Double.MIN_VALUE, 1.0, Double.POSITIVE_INFINITY, Double.longBitsToDouble(0x7ff8000000000042L)
    };

    public static int order(int n) {
        int i = n / 9;
        int j = n % 9;
        double a = VALUES[i], b = VALUES[j];
        if (i == 8 || j == 8) {
            return !(a <= b) && !(a >= b) && a != b && (Double.isNaN(a) || Double.isNaN(b)) ? 1 : 0;
        }
        boolean bothZero = (i == 3 || i == 4) && (j == 3 || j == 4);
        if ((a < b) != (i < j && !bothZero) || (a == b) != (i == j || bothZero)) return 0;
        return Double.doubleToRawLongBits(Math.max(a, b)) == Double.doubleToRawLongBits(VALUES[Math.max(i, j)])
            && Double.doubleToRawLongBits(StrictMath.min(a, b)) == Double.doubleToRawLongBits(VALUES[Math.min(i, j)]) ? 1 : 0;
    }

    public static int zeroBits(int n) {
        float[][] cells = new float[2][1];
        cells[1][0] = n == 0 ? -0.0f : Float.intBitsToFloat(0x7fc01234);
        float x = cells[1][0];
        if (Float.isNaN(x)) {
            return Float.floatToIntBits(x) == 0x7fc00000 && Float.floatToRawIntBits(x) == 0x7fc01234 ? 2 : -1;
        }
        if (x != cells[0][0] || Float.floatToRawIntBits(Math.max(x, 0.0f)) != 0) return -1;
        return Float.floatToRawIntBits(Math.min(x, 0.0f)) == Integer.MIN_VALUE ? 1 : -1;
    }

    public static int length(int n) {
        Object value = n == 0 ? new double[3] : n == 1 ? null : "text";
        try { return Array.getLength(value); }
        catch (NullPointerException e) { return 1; }
        catch (IllegalArgumentException e) { return 2; }
    }

    public static int signaling(int n) {
        return Float.floatToRawIntBits(Float.intBitsToFloat(n));
    }

    public static int bucket(int n) {
        return (int) (1.2 * Integer.highestOneBit(n));
    }

    public static int root(int n) {
        double x = n == 0 ? -0.0 : n == 1 ? 2.0 : Double.POSITIVE_INFINITY;
        double y = Math.sqrt(x);
        if (n == 2) return Double.isInfinite(y) && !Double.isFinite(y) ? 1 : 0;
        long expected = n == 0 ? Long.MIN_VALUE : 0x3ff6a09e667f3bcdL;
        return Double.doubleToRawLongBits(y) == expected && Math.abs(y) >= 0.0 ? 1 : 0;
    }

    public static boolean boundaries(int n) {
        double[] values = {-0.0, -Double.MIN_VALUE, Double.MAX_VALUE, Double.NaN};
        double x = values[n];
        if (n == 0) return Double.doubleToRawLongBits(x - 0.0) == Long.MIN_VALUE;
        if (n == 1) return Double.doubleToRawLongBits(x / 2.0) == Long.MIN_VALUE;
        if (n == 2) return (int) (x * 2.0) == Integer.MAX_VALUE && (long) -x == Long.MIN_VALUE;
        return (int) x == 0 && (long) x == 0L;
    }

    public static boolean rotated(int n) {
        int bits = 0x9e3779b9;
        long wide = 0xc6a4a7935bd1e995L;
        return Integer.rotateLeft(bits, n) == ((bits << n) | (bits >>> -n))
            && Long.rotateRight(wide, n) == ((wide >>> n) | (wide << -n));
    }

    public static int rounded(int n) {
        long large = (1L << 53) + n;
        long[] expectedLowBits = {0L, 0L, 1L, 2L};
        long doubleBits = Double.doubleToRawLongBits((double) large);
        float single = (float) ((1 << 24) + n);
        return doubleBits - 0x4340000000000000L == expectedLowBits[n]
            && Float.floatToRawIntBits(single) - 0x4b800000 == expectedLowBits[n] ? 1 : 0;
    }

    public static int correlated(int n) {
        // Both operands vary with n. Losing their correlation admits many spurious pairs.
        double x = n;
        return (int) (x * (double) (n + 1));
    }

    public static boolean wideningSign(int n) {
        return (Double.doubleToRawLongBits((double) n) < 0) == (n < 0);
    }

    public static void main(String[] args) {
        for (int n = 0; n < 81; n++) if (order(n) != 1) throw new AssertionError(n);
        for (int n = 0; n < 3; n++) if (root(n) != 1) throw new AssertionError(n);
        for (int n = 0; n < 4; n++) if (rounded(n) != 1 || !boundaries(n)) throw new AssertionError(n);
        for (int n = 0; n <= 64; n++) if (correlated(n) != n * (n + 1)) throw new AssertionError(n);
        for (int n : new int[]{Integer.MIN_VALUE, -1, 0, 1, Integer.MAX_VALUE})
            if (!wideningSign(n) || !rotated(n)) throw new AssertionError(n);
        if (bucket(3) != 2 || bucket(4) != 4) throw new AssertionError();
        System.out.println(zeroBits(0) + " " + zeroBits(1) + " " + length(0) + " " + length(1) + " " + length(2));
    }
}
