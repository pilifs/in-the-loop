package bench.held;

/** Prefix sums in place, each element adding the one before it (v1). */
public final class PrefixSums {
    private PrefixSums() {
    }

    public static void accumulate(int[] a) {
        for (int i = 1; i < a.length; i++) {
            a[i] += a[i - 1];
        }
    }
}
