package datawork;

import org.apache.commons.lang3.ArrayUtils;

public final class ToleranceSearch {
    // Preserve every finite value, infinity, and quiet NaN payload. A signaling
    // source word denotes the quiet NaN with the same sign and remaining payload.
    public static long cellBits(long word) {
        if ((word & Long.MAX_VALUE) > 0x7ff0000000000000L) {
            return word | 0x0008000000000000L;
        }
        return word;
    }

    // On either sign, finite magnitudes increase in raw unsigned magnitude order.
    private static boolean inWindow(long bits, int center) {
        long magnitude = bits & Long.MAX_VALUE;
        long quarter = 0x3fd0000000000000L;
        long threeQuarters = 0x3fe8000000000000L;
        if (center == 0) return magnitude <= quarter;
        return (bits < 0) == (center < 0) && magnitude >= quarter && magnitude <= threeQuarters;
    }

    public static int agrees(long first, long second, int start, int center) {
        long a = cellBits(first);
        long b = cellBits(second);
        double[] values = {Double.longBitsToDouble(a), Double.longBitsToDouble(b)};
        double needle = center < 0 ? -0.5 : center > 0 ? 0.5 : 0.0;
        int found = ArrayUtils.indexOf(values, needle, start, 0.25);
        int expected = start <= 0 && inWindow(a, center) ? 0
                : start <= 1 && inWindow(b, center) ? 1 : -1;
        return found == expected && Double.doubleToRawLongBits(values[0]) == a
                && Double.doubleToRawLongBits(values[1]) == b ? 1 : 0;
    }
}
