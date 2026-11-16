package loops;

import java.util.Arrays;

/**
 * A hash in the shape of bcrypt's: a state mixed with a key for 2^cost rounds, each round a pass over the state two
 * words at a time, each word looked up in a table at an index the state computes, the key read cyclically.
 */
public final class Rounds {

    private static final int[] TABLE = new int[128];

    static {
        for (int i = 0; i < TABLE.length; i++) {
            TABLE[i] = i * 0x9E3779B9;
        }
    }

    private Rounds() {
    }

    /** The digest of a key of at most 8 bytes; IllegalArgumentException for a longer one, or a cost outside 4 to 30. */
    public static int digest(byte[] key, int cost) {
        if (key.length > 8) {
            throw new IllegalArgumentException("key too long");
        }
        return mixed(key, cost);
    }

    /** The same with no limit on the key: what the length check was added to. */
    public static int unchecked(byte[] key, int cost) {
        return mixed(key, cost);
    }

    /** As digest, with a pass that steps past the state's end. */
    public static int overrun(byte[] key, int cost) {
        if (key.length > 8) {
            throw new IllegalArgumentException("key too long");
        }
        int[] state = new int[18];
        long rounds = 1L << (cost & 31);
        for (int i = 0; i < rounds; i++) {
            for (int j = 1; j < state.length; j += 2) {
                state[j] ^= i;
                state[j + 1] ^= key.length;
            }
        }
        return state[1];
    }

    /** A count kept in a field and in a static across more iterations than any bound. */
    public static int counted(int n) {
        Counter counter = new Counter();
        for (int i = 0; i < n; i++) {
            counter.count += 2;
            Counter.total++;
        }
        return counter.count;
    }

    /** A loop that never ends for a negative step: nothing grows in it. */
    public static int stuck(int step) {
        int at = 0;
        int seen = 0;
        while (at != 1000) {
            at = (at + step) & 1023;
            seen ^= at;
        }
        return seen;
    }

    /** An array made anew in each iteration: the loop changes a reference, which no invariant of numbers covers. */
    public static int renewed(int n) {
        int[] last = new int[1];
        for (int i = 0; i < n; i++) {
            last = new int[last.length];
        }
        return last.length;
    }

    /** A cell of the table the class's initializer fills in 128 iterations. */
    public static boolean table() {
        return TABLE[5] == 5 * 0x9E3779B9;
    }

    private static int mixed(byte[] key, int cost) {
        if (cost < 4 || cost > 30) {
            throw new IllegalArgumentException("bad cost");
        }
        int[] state = new int[18];
        int[] off = { 0 };
        long rounds = 1L << cost;
        byte[] k = Arrays.copyOf(key, key.length + 1);
        for (int i = 0; i < rounds; i++) {
            for (int j = 0; j < state.length; j += 2) {
                int w = word(k, off);
                state[j] ^= TABLE[(w >>> 8) & 0x7f] + w;
                state[j + 1] = TABLE[w & 0x7f] ^ state[j];
            }
        }
        return state[0] ^ state[17];
    }

    private static int word(byte[] data, int[] offp) {
        int w = 0;
        int off = offp[0];
        for (int i = 0; i < 4; i++) {
            w = (w << 8) | (data[off] & 0xff);
            off = (off + 1) % data.length;
        }
        offp[0] = off;
        return w;
    }

    static final class Counter {
        static int total;
        int count;
    }
}
