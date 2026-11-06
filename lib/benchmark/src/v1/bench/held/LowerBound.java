package bench.held;

/** The first index whose element is at least the key in a sorted array, by a scan (v1). */
public final class LowerBound {
    private LowerBound() {
    }

    public static int lowerBound(int[] a, int key) {
        for (int i = 0; i < a.length; i++) {
            if (a[i] >= key) {
                return i;
            }
        }
        return a.length;
    }
}
