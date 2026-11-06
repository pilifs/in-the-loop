package bench.held;

/** The floor of the mean of two ints, from the bits they share and the bits they do not (v2). */
public final class Average {
    private Average() {
    }

    public static int mean(int a, int b) {
        return (a & b) + ((a ^ b) >> 1);
    }
}
