package bench.held;

/** Two closed intervals: whether they meet, each starting before the other ends (v2), and how far they overlap, by long subtraction saturated to an int (v2). */
public final class Overlap {
    private Overlap() {
    }

    public static boolean meets(Interval x, Interval y) {
        return x.lo() <= y.hi() && y.lo() <= x.hi();
    }

    public static int length(Interval x, Interval y) {
        long d = (long) Math.min(x.hi(), y.hi()) - Math.max(x.lo(), y.lo());
        return (int) Math.min(Integer.MAX_VALUE, Math.max(0L, d));
    }
}
