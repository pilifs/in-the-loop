package app;

/** `Hash` with one more call: the number of rounds comes through `Integer.parseInt(String)`, as
 * BCrypt.hashpw(byte[], String) reads its cost. The same in both versions. The checker runs that JDK method's own
 * bytecode, and `parseInt(String, int)` under it builds its messages with `String.format(String, Object[])` on JDK 25 and with a `StringBuilder` on JDK 21, so
 * a rule that takes the callee's code as closed only where no call into the JDK is given an `Object` has no name for
 * this callee on JDK 25 (`lib/src/shared.rs`, `reach`, after the preservation stream's kskmpmny). */
public final class Parsing {
    private static final int[] TABLE = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3};

    private int[] state;

    private Parsing() {}

    /** The digest: `Hash`'s, with 610 rounds for a salt that starts with `a` and 611 for any other. A null salt or
     * an empty one throws `IllegalArgumentException`. */
    public static String digest(byte[] data, String salt) {
        if (salt == null) {
            throw new IllegalArgumentException("salt cannot be null");
        }
        if (salt.length() < 1) {
            throw new IllegalArgumentException("Invalid salt");
        }
        Parsing h = new Parsing();
        h.state = TABLE.clone();
        int rounds = 600 + Integer.parseInt(salt.charAt(0) == 'a' ? "10" : "11");
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
