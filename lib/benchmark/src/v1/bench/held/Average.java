package bench.held;

/** The floor of the mean of two ints, widened to a long (v1). */
public final class Average {
    private Average() {
    }

    public static int mean(int a, int b) {
        return (int) (((long) a + b) >> 1);
    }
}
