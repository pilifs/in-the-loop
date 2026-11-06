package bench.real;

/**
 * JDK-5045582, after the fix: {@code java.util.Arrays.binarySearch} took the midpoint of its range as
 * {@code (low + high) / 2}, which overflows once {@code low + high} passes {@code Integer.MAX_VALUE}, on an array
 * of more than 2^30 elements. JDK 6 fixed it with {@code (low + high) >>> 1}. Joshua Bloch, "Extra, Extra - Read
 * All About It: Nearly All Binary Searches and Mergesorts are Broken", Google Research blog, 2 June 2006.
 */
public final class Midpoint {
    private Midpoint() {
    }

    public static int midpoint(int low, int high) {
        return (low + high) >>> 1;
    }

    /** {@code Arrays.binarySearch0} for an {@code int[]}. */
    public static int search(int[] a, int key) {
        int low = 0;
        int high = a.length - 1;
        while (low <= high) {
            int mid = (low + high) >>> 1;
            int value = a[mid];
            if (value < key) {
                low = mid + 1;
            } else if (value > key) {
                high = mid - 1;
            } else {
                return mid;
            }
        }
        return -(low + 1);
    }
}
