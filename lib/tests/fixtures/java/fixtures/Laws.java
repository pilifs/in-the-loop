package fixtures;

/** Methods with properties to prove: a correct majority, a wrong one, and a symmetric maximum. */
public final class Laws {

    private Laws() {}

    /** The smallest number of nodes that is more than half of {@code n}. */
    public static int majority(int n) {
        if (n <= 0) {
            throw new IllegalArgumentException("a cluster has at least one node");
        }
        return n / 2 + 1;
    }

    /** Looks like a majority, and is not one for even {@code n}. */
    public static int roundedHalf(int n) {
        if (n <= 0) {
            throw new IllegalArgumentException("a cluster has at least one node");
        }
        return (n + 1) / 2;
    }

    public static long maxOf(long a, long b) {
        return a >= b ? a : b;
    }

    /** A property as a boolean method: it should return true on every input, and does not for a = b. */
    public static boolean maxIsStrict(long a, long b) {
        return maxOf(a, b) > a || maxOf(a, b) > b;
    }
}
