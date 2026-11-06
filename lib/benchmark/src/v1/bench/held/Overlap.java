package bench.held;

/** Two closed intervals: whether they meet, as not apart (v1), and how far they overlap, by int subtraction (v1), which overflows on wide intervals. */
public final class Overlap {
    private Overlap() {
    }

    public static boolean meets(Interval x, Interval y) {
        return !(x.hi() < y.lo() || y.hi() < x.lo());
    }

    public static int length(Interval x, Interval y) {
        return Math.max(0, Math.min(x.hi(), y.hi()) - Math.max(x.lo(), y.lo()));
    }
}
