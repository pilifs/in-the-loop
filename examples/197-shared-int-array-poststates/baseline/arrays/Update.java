package arrays;

public final class Update {
    public static int apply(int[] left, int[] right) {
        if (left != null && right != null && left.length > 0 && right.length > 0) {
            left[0] = 1;
        }
        return 0;
    }
}
