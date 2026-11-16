package java.util.stream;

import java.util.function.IntPredicate;

/**
 * The model's stream over an array of ints: what {@code java.util.Arrays.stream(int[])} returns, each element in
 * order. It is not a class of the JDK; it does what the JDK's sequential {@code IntStream} over an array does for
 * the three matches, as {@link SequentialArrayStream} says of a stream over an array of objects: a null array a
 * {@code NullPointerException} where the stream is made, the array's length the stream's from then on and its
 * elements read when the match runs, used once, a null predicate a {@code NullPointerException}, a match stopped
 * at the first int that decides it.
 */
final class IntArrayStream implements IntStream {
    private final int[] source;
    private final int length;
    private boolean linkedOrConsumed;

    private IntArrayStream(int[] source, int length) {
        this.source = source;
        this.length = length;
    }

    /** {@code java.util.Arrays.stream(array)}. */
    static IntStream of(int[] array) {
        return new IntArrayStream(array, array.length);
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
        for (int i = 0; i < length; i++) {
            if (!predicate.test(source[i])) {
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
        for (int i = 0; i < length; i++) {
            if (predicate.test(source[i])) {
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
        for (int i = 0; i < length; i++) {
            if (predicate.test(source[i])) {
                return false;
            }
        }
        return true;
    }
}
