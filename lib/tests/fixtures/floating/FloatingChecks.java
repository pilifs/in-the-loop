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

    public static boolean zeroAngle(int n) {
        double x = n == 0 ? -0.0 : n == 1 ? +0.0 : 1.0;
        return Double.doubleToRawLongBits(Math.sin(x)) == Double.doubleToRawLongBits(x) && Math.cos(x) == 1.0;
    }

    public static boolean cosineBracket(int n) {
        // The two adjacent doubles enclosing cos(x) at and just past the binary64
        // approximation to -pi/2. Crossing the quadrant changes its sign.
        double x = n == 0 ? -0x1.921fb54442d18p0 : -0x1.921fb54442d19p0;
        double lower = n == 0 ? 0x1.1a62633145c06p-54 : -0x1.72cece675d1fdp-53;
        double upper = n == 0 ? 0x1.1a62633145c07p-54 : -0x1.72cece675d1fcp-53;
        double a = Math.cos(x), b = StrictMath.cos(x);
        return a >= lower && a <= upper && b >= lower && b <= upper;
    }

    public static boolean exactSine(int n) {
        return Math.sin(n == 0 ? -Math.PI / 2 : -9.0) == -1.0;
    }

    public static boolean nanExtrema(int n) {
        Number boxed = Double.valueOf(n == 0 ? -0.0 : 2.5);
        double x = boxed.doubleValue();
        double nan = Double.longBitsToDouble(0x7ff8000000000042L);
        return Double.doubleToLongBits(Math.min(x, nan)) == 0x7ff8000000000000L && Double.isNaN(Math.max(nan, x))
                && Double.doubleToRawLongBits(x) == (n == 0 ? Long.MIN_VALUE : 0x4004000000000000L);
    }

    public static long rawNaN(int n) {
        return Double.doubleToRawLongBits(Math.max(Double.longBitsToDouble(0x7ff8000000000042L), (double)n));
    }

    public static boolean integralPart(int n) {
        double[] x = {-0.0, -0.25, 0.25, Double.POSITIVE_INFINITY};
        double[] down = {-0.0, -1.0, +0.0, Double.POSITIVE_INFINITY};
        double[] up = {-0.0, -0.0, 1.0, Double.POSITIVE_INFINITY};
        return Double.doubleToRawLongBits(Math.floor(x[n])) == Double.doubleToRawLongBits(down[n])
            && Double.doubleToRawLongBits(Math.ceil(x[n])) == Double.doubleToRawLongBits(up[n]);
    }

    public static boolean axes(int n) {
        double[] y = {0.0, -0.0, 0.0, -0.0, 1.0, -1.0};
        double[] x = {1.0, 1.0, -1.0, -1.0, -0.0, +0.0};
        double[] answer = {0.0, -0.0, Math.PI, -Math.PI, Math.PI / 2, -Math.PI / 2};
        return Double.doubleToRawLongBits(Math.atan2(y[n], x[n])) == Double.doubleToRawLongBits(answer[n]);
    }

    public static boolean diagonalAngle(int n) { return Math.atan2(1.0, n) > 0.0; }

    public static boolean hypot(int n) {
        double[] a = {-0.0, 3.0, 0x1.8p701, 0x1.8p-699, Double.MIN_VALUE};
        double[] b = {-0.0, 4.0, 0x1.0p702, 0x1.0p-698, 0.0};
        double[] expected = {0.0, 5.0, 0x1.4p702, 0x1.4p-698, Double.MIN_VALUE};
        return Double.doubleToRawLongBits(Math.hypot(a[n], b[n])) == Double.doubleToRawLongBits(expected[n]);
    }

    public static boolean naiveHypot(int n) {
        double a = n == 0 ? 3.0 : 0x1.8p701;
        double b = n == 0 ? 4.0 : 0x1.0p702;
        return Math.hypot(a, b) == Math.sqrt(a * a + b * b);
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
        for (int n = 0; n < 6; n++) if (!axes(n)) throw new AssertionError(n);
        for (int n = 0; n < 5; n++) if (!hypot(n)) throw new AssertionError(n);
        if (!zeroAngle(0) || !zeroAngle(1) || zeroAngle(2)) throw new AssertionError();
        if (!cosineBracket(0) || !cosineBracket(1) || exactSine(1)) throw new AssertionError();
        if (!nanExtrema(0) || !nanExtrema(1)) throw new AssertionError();
        double nearMinusOne = Math.sin(-Math.PI / 2);
        if (!(nearMinusOne >= -1.0 && nearMinusOne <= -0x1.fffffffffffffp-1)) throw new AssertionError();
        if (!naiveHypot(0) || naiveHypot(1)) throw new AssertionError();
        for (int n = 0; n < 3; n++) if (root(n) != 1) throw new AssertionError(n);
        for (int n = 0; n < 4; n++) if (rounded(n) != 1 || !boundaries(n) || !integralPart(n)) throw new AssertionError(n);
        for (int n = 0; n <= 64; n++) if (correlated(n) != n * (n + 1)) throw new AssertionError(n);
        for (int n : new int[]{Integer.MIN_VALUE, -1, 0, 1, Integer.MAX_VALUE})
            if (!wideningSign(n) || !rotated(n)) throw new AssertionError(n);
        if (bucket(3) != 2 || bucket(4) != 4) throw new AssertionError();
        System.out.println(zeroBits(0) + " " + zeroBits(1) + " " + length(0) + " " + length(1) + " " + length(2));
    }
}
