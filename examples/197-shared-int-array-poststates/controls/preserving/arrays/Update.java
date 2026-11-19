package arrays;

/** The same write after equivalent early exits. */
public final class Update {
    public static int apply(int[] left, int[] right) {
        if (right == null || left == null || right.length == 0 || left.length == 0) return 0;
        left[0] = 1;
        return 0;
    }
}
