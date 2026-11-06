package bench.held;

/** Prefix sums in place, from a running sum (v2). */
public final class PrefixSums {
    private PrefixSums() {
    }

    public static void accumulate(int[] a) {
        int sum = 0;
        for (int i = 0; i < a.length; i++) {
            sum += a[i];
            a[i] = sum;
        }
    }
}
