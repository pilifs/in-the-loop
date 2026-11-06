package bench.held;

/** A closed interval of ints; the constructor refuses an empty one. */
public record Interval(int lo, int hi) {
    public Interval {
        if (lo > hi) {
            throw new IllegalArgumentException("empty interval");
        }
    }
}
