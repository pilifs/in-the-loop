package java.util.stream;

import java.util.function.IntPredicate;

/**
 * The model's stream of the ints from one up to another: what {@code IntStream.range(startInclusive, endExclusive)}
 * returns, each int in increasing order, none where the end is not above the start. It is not a class of the JDK;
 * it does what the JDK's sequential {@code IntStream} over a range does for the three matches, as
 * {@link SequentialArrayStream} says of a stream over an array: used once, a null predicate a
 * {@code NullPointerException}, a match stopped at the first int that decides it.
 */
final class RangeStream implements IntStream {
    private final int start;
    private final int end;
    private boolean linkedOrConsumed;

    private RangeStream(int start, int end) {
        this.start = start;
        this.end = end;
    }

    /** {@code IntStream.range(start, end)}. */
    static IntStream of(int start, int end) {
        return new RangeStream(start, end);
    }

    private void use() {
        if (linkedOrConsumed) {
            throw new IllegalStateException("stream has already been operated upon or closed");
        }
        linkedOrConsumed = true;
    }

    public boolean allMatch(IntPredicate predicate) {
        if (predicate == null) {
            throw new NullPointerException();
        }
        use();
        for (int i = start; i < end; i++) {
            if (!predicate.test(i)) {
                return false;
            }
        }
        return true;
    }

    public boolean anyMatch(IntPredicate predicate) {
        if (predicate == null) {
            throw new NullPointerException();
        }
        use();
        for (int i = start; i < end; i++) {
            if (predicate.test(i)) {
                return true;
            }
        }
        return false;
    }

    public boolean noneMatch(IntPredicate predicate) {
        if (predicate == null) {
            throw new NullPointerException();
        }
        use();
        for (int i = start; i < end; i++) {
            if (predicate.test(i)) {
                return false;
            }
        }
        return true;
    }
}
