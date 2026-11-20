package maxgrid;

import org.apache.commons.lang3.math.NumberUtils;

public final class Projection {
    private static double value(int digit) {
        switch (digit) {
            case 0: return -1.0;
            case 1: return -0.0;
            case 2: return +0.0;
            default: return 1.0;
        }
    }

    private static int check(int code, boolean raw) {
        int remaining = code + 1;
        double[] values = new double[code < 4 ? 1 : code < 20 ? 2 : 3];
        int greatest = 0;
        for (int i = 0; i < values.length; i++) {
            int digit = (remaining - 1) % 4;
            values[i] = value(digit);
            if (digit > greatest) greatest = digit;
            remaining = (remaining - 1) / 4;
        }
        double actual = NumberUtils.max(values);
        double expected = value(greatest);
        if (!raw) return actual == expected ? 1 : 0;
        return Double.doubleToRawLongBits(actual) == Double.doubleToRawLongBits(expected) ? 1 : 0;
    }

    public static int numeric(int code) { return check(code, false); }
    public static int bits(int code) { return check(code, true); }
}
