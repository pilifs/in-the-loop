package gcd;

import java.util.Arrays;
import org.apache.commons.math.util.MathUtils;

public final class GcdCases {
    public static void main(String[] args) {
        for (int i = 0; i <= 20; i++) {
            int[] row = new int[21];
            for (int j = 0; j <= 20; j++) row[j] = MathUtils.gcd(1 << i, 1 << j);
            System.out.printf("{\"i\":%d,\"powers\":%s}%n", i, Arrays.toString(row));
        }
        int[] zero = new int[256];
        for (int n = 0; n < zero.length; n++) zero[n] = MathUtils.gcd(0, n);
        System.out.printf("{\"zero\":%s,\"apacheCase\":%d}%n",
                          Arrays.toString(zero), MathUtils.gcd(3 * (1 << 20), 9 * (1 << 15)));
    }
}
