package bench.held;

/** The mean of two ints by an unsigned shift (v3): right for two non-negative ints, wrong below zero. */
public final class Average {
    private Average() {
    }

    public static int mean(int a, int b) {
        return (a + b) >>> 1;
    }
}
