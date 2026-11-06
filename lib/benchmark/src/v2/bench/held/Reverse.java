package bench.held;

/** Reversing an array in place with one index (v2). */
public final class Reverse {
    private Reverse() {
    }

    public static void reverse(int[] a) {
        int n = a.length;
        for (int i = 0; i < n / 2; i++) {
            int t = a[i];
            a[i] = a[n - 1 - i];
            a[n - 1 - i] = t;
        }
    }
}
