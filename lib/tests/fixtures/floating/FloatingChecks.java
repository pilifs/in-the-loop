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

    public static void main(String[] args) {
        for (int n = 0; n < 81; n++) if (order(n) != 1) throw new AssertionError(n);
        System.out.println(zeroBits(0) + " " + zeroBits(1) + " " + length(0) + " " + length(1) + " " + length(2));
    }
}
