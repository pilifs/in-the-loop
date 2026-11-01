package fixtures;

/** Methods over arrays, for property proofs with quantifiers. */
public final class Search {

    private Search() {}

    /** Binary search over a sorted array: the index of {@code key}, or -1. */
    public static int find(int[] sorted, int key) {
        int low = 0;
        int high = sorted.length - 1;
        while (low <= high) {
            int mid = (low + high) >>> 1;
            if (sorted[mid] < key) {
                low = mid + 1;
            } else if (sorted[mid] > key) {
                high = mid - 1;
            } else {
                return mid;
            }
        }
        return -1;
    }

    /** The running sums of {@code xs}, into a new array. */
    public static long[] prefixSums(int[] xs) {
        long[] out = new long[xs.length];
        long sum = 0;
        for (int i = 0; i < xs.length; i++) {
            sum += xs[i];
            out[i] = sum;
        }
        return out;
    }

    /** Overwrites every element of {@code xs} that equals {@code from} with {@code to}, returning how many. */
    public static int replace(int[] xs, int from, int to) {
        int n = 0;
        for (int i = 0; i < xs.length; i++) {
            if (xs[i] == from) {
                xs[i] = to;
                n++;
            }
        }
        return n;
    }
}
