package mean;

import com.google.common.math.IntMath;
import com.google.common.math.LongMath;
import java.math.BigInteger;

public final class MeanCases {
    public static void main(String[] args) {
        for (int width : new int[]{32, 64}) {
            long min = width == 32 ? Integer.MIN_VALUE : Long.MIN_VALUE;
            long max = width == 32 ? Integer.MAX_VALUE : Long.MAX_VALUE;
            long[] grid = {min, min + 1, min / 2, -2, -1, 0, 1, 2, max / 2 + 1, max - 1, max};
            for (long x : grid) {
                for (long y : grid) {
                    long expect = BigInteger.valueOf(x).add(BigInteger.valueOf(y)).shiftRight(1).longValueExact();
                    long got = width == 32 ? IntMath.mean((int) x, (int) y) : LongMath.mean(x, y);
                    System.out.printf("{\"width\":%d,\"x\":%d,\"y\":%d,\"got\":%d,\"oracle\":%d}%n", width, x, y, got, expect);
                }
            }
        }
    }
}
