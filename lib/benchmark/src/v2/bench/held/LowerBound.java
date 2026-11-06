package bench.held;

/** The first index whose element is at least the key in a sorted array, by a half-open bisection (v2). */
public final class LowerBound {
    private LowerBound() {
    }

    public static int lowerBound(int[] a, int key) {
        int lo = 0;
        int hi = a.length;
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (a[mid] < key) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        return lo;
    }
}
