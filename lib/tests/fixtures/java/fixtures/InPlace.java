package fixtures;

/** Methods that write into an array parameter, for properties with {@code \\old}. */
public final class InPlace {

    private InPlace() {}

    /** Reverses {@code a} in place. */
    public static void reverse(int[] a) {
        for (int i = 0, j = a.length - 1; i < j; i++, j--) {
            int t = a[i];
            a[i] = a[j];
            a[j] = t;
        }
    }

    /** Zeroes {@code a} from index {@code n} on, and (a bug) the element before it. */
    public static void zeroFrom(byte[] a, int n) {
        for (int i = Math.max(n - 1, 0); i < a.length; i++) {
            a[i] = 0;
        }
    }

    /** Sorts {@code keys} in place, moving {@code values} along, and returns how many pairs it moved. */
    public static int sortPairs(int[] keys, int[] values) {
        int moved = 0;
        for (int i = 1; i < keys.length; i++) {
            int key = keys[i];
            int value = values[i];
            int j = i;
            while (j > 0 && keys[j - 1] > key) {
                keys[j] = keys[j - 1];
                values[j] = values[j - 1];
                j--;
            }
            keys[j] = key;
            values[j] = value;
            if (j != i) {
                moved++;
            }
        }
        return moved;
    }
}
