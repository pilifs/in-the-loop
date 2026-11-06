package bench.held;

/** Reversing an array in place with two indices (v1). */
public final class Reverse {
    private Reverse() {
    }

    public static void reverse(int[] a) {
        for (int i = 0, j = a.length - 1; i < j; i++, j--) {
            int t = a[i];
            a[i] = a[j];
            a[j] = t;
        }
    }
}
