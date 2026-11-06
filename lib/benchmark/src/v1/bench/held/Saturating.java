package bench.held;

/** A saturating addition, by widening to a long (v1); v2 tests the sign bits for overflow. */
public final class Saturating {
    private Saturating() {
    }

    public static int add(int a, int b) {
        long sum = (long) a + b;
        if (sum > Integer.MAX_VALUE) {
            return Integer.MAX_VALUE;
        }
        if (sum < Integer.MIN_VALUE) {
            return Integer.MIN_VALUE;
        }
        return (int) sum;
    }
}
