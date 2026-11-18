package app;

/** The code both versions share, the same bytes in each. */
public final class Shared {
    private Shared() {}

    /** Each array of a constant length, kept: 32 TiB in all once k >= 1, an OutOfMemoryError on any heap. */
    public static int kept(int k) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        Object[] keep = new Object[16384];
        for (int i = 0; i < k && i < 16384; i++) {
            Object[] row = new Object[16384];
            keep[i] = row;
            for (int j = 0; j < 16384; j++) {
                row[j] = new long[16384];
            }
        }
        return rounds;
    }

    /** k calls deep through an override: a StackOverflowError for a k deep enough. */
    public static int around(int k) {
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        return new Deep().f(k) + rounds;
    }
}
