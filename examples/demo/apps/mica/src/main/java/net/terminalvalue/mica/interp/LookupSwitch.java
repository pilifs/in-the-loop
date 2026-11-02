package net.terminalvalue.mica.interp;

/**
 * The {@code lookupswitch} instruction (JVMS §6.5): its match-offset pairs are sorted by match value so that an
 * implementation may search them by bisection, which this one does. A {@code Code} attribute holds at most 65535
 * bytes, and a pair takes eight, so a table has fewer than 8190 pairs.
 */
public final class LookupSwitch {

    private LookupSwitch() {}

    /** The index halfway between {@code low} and {@code high}, both inclusive. */
    public static int midpoint(int low, int high) {
        return (low + high) >>> 1;
    }

    /** The index of {@code key} in the sorted {@code matches}, or -1 when the default offset applies. */
    public static int find(int[] matches, int key) {
        int low = 0;
        int high = matches.length - 1;
        while (low <= high) {
            int mid = midpoint(low, high);
            int match = matches[mid];
            if (match < key) {
                low = mid + 1;
            } else if (match > key) {
                high = mid - 1;
            } else {
                return mid;
            }
        }
        return -1;
    }
}
