package app;

/** The callee with a table its initializer computes from another class, `Seed`, whose method differs between the versions. This class is the same bytes in both. */
public final class Seeded {
    private static final int[] TABLE = Seed.table();

    private int[] state;

    private Seeded() {}

    /** The digest: four letters from a state the table starts and 600 rounds (601 for a salt that starts with an odd
     * unit) mix the first four bytes into. A null salt or one shorter than a unit throws. */
    public static String digest(byte[] data, String salt) {
        if (salt == null) {
            throw new IllegalArgumentException("salt cannot be null");
        }
        if (salt.length() < 1) {
            throw new IllegalArgumentException("Invalid salt");
        }
        Seeded h = new Seeded();
        h.state = TABLE.clone();
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
