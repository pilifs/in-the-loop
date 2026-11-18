package app;

/**
 * The callee both versions share: the same bytes in old/ and new/. It has a loop, so the call-level rule takes it,
 * and it returns a new array of a constant length that holds its argument.
 */
public final class Shared {
    private Shared() {
    }

    /** A new array of one cell, holding k. */
    public static int[] make(int k) {
        int[] cells = new int[1];
        int rounds = 0;
        for (int i = 0; i < 3; i++) {
            rounds += i;
        }
        cells[0] = k + rounds - 3;
        return cells;
    }
}
