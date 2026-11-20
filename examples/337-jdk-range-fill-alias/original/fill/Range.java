package fill;

import java.util.Arrays;

public final class Range {
    public static int apply(int[] a, int[] other, int from, int to, int value) {
        Arrays.fill(a, from, to, value);
        return a.length;
    }

    public static int observe(int[] a, int[] other, int from, int to, int value, int k) {
        Arrays.fill(a, from, to, value);
        return other[k];
    }
}
