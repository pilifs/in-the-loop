package arrays;

import java.util.Arrays;

/** Enumerate one representative of each heap up to renaming objects. */
public final class RootCases {
    static int[] content(int code) {
        if (code < 0) return null;
        int length = code == 0 ? 0 : code < 3 ? 1 : 2;
        int bits = code - ((1 << length) - 1);
        int[] value = new int[length];
        for (int i = 0; i < length; i++) value[i] = (bits >> (length - 1 - i)) & 1;
        return value;
    }

    static void observe(int l, int r, boolean shared) {
        int[] left = content(l);
        int[] right = shared ? left : content(r);
        int result = Update.apply(left, right);
        System.out.printf("{\"l\":%d,\"r\":%d,\"shared\":%b,\"result\":%d,\"left\":%s,\"right\":%s}%n",
                          l, r, shared, result, Arrays.toString(left), Arrays.toString(right));
    }

    public static void main(String[] args) {
        for (int l = -1; l < 7; l++) {
            for (int r = -1; r < 7; r++) observe(l, r, false);
            if (l >= 0) observe(l, l, true);
        }
    }
}
