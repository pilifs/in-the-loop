package arrays;

/** Two distinct non-null arrays of exactly one cell each. Their low two bits exhaust the four input heaps. */
public final class BinaryCells {
    public static int observe(int bits) {
        int[] left = {bits & 1};
        int[] right = {(bits >>> 1) & 1};
        Update.apply(left, right);
        return 2 * left[0] + right[0];
    }

    public static void main(String[] args) {
        for (String arg : args) System.out.println(observe(Integer.parseInt(arg)));
    }
}
