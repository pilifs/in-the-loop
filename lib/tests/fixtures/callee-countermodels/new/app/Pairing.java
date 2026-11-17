package app;

/** The callee over two arrays: it writes the first and then reads the second, so it gives another result when they are one array. The same in both versions. */
public final class Pairing {
    private static final int[] TABLE = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3};

    private int[] state;

    private Pairing() {}

    /** The digest: four letters from a state the table starts and 600 rounds (601 for a salt that starts with an odd
     * unit) mix the first four bytes into. A null salt or one shorter than a unit throws. */
    public static String digest(byte[] data, byte[] other, String salt) {
        if (salt == null) {
            throw new IllegalArgumentException("salt cannot be null");
        }
        if (salt.length() < 1) {
            throw new IllegalArgumentException("Invalid salt");
        }
        Pairing h = new Pairing();
        h.state = TABLE.clone();
        if (data.length > 0 && other.length > 0) {
            data[0]++;
            h.state[0] += other[0];
        }
        int rounds = 600 + (salt.charAt(0) & 1);
        for (int r = 0; r < rounds; r++) {
            h.round(data, r);
        }
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < 4; i++) {
            out.append((char) ('a' + (h.state[i] & 15)));
        }
        return out.toString();
    }

    private void round(byte[] data, int r) {
        state[r & 15] = state[r & 15] * 31 + ((r & 3) < data.length ? data[r & 3] : r) + state[(r + 1) & 15];
    }
}
