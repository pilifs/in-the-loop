package bench.held;

/** A saturating addition, testing the sign bits for overflow (v2); v1 widened to a long. */
public final class Saturating {
    private Saturating() {
    }

    public static int add(int a, int b) {
        int sum = a + b;
        if (((a ^ sum) & (b ^ sum)) < 0) {
            return a < 0 ? Integer.MIN_VALUE : Integer.MAX_VALUE;
        }
        return sum;
    }
}
