package java.util.stream;

import java.util.function.IntPredicate;

/**
 * The model's stream of a String's code units: what {@code String.chars()} returns, each {@code char} as the
 * {@code int} it zero-extends to, in order. It is not a class of the JDK; it does what the JDK's sequential
 * {@code IntStream} over a String does for the three matches, as {@link SequentialArrayStream} says of a stream
 * over an array: used once, a null predicate a {@code NullPointerException}, a match stopped at the first unit that
 * decides it.
 */
final class CharsStream implements IntStream {
    private final String chars;
    private boolean linkedOrConsumed;

    private CharsStream(String chars) {
        this.chars = chars;
    }

    /** {@code chars.chars()}. */
    static IntStream of(String chars) {
        return new CharsStream(chars);
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
        for (int i = 0; i < chars.length(); i++) {
            if (!predicate.test(chars.charAt(i))) {
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
        for (int i = 0; i < chars.length(); i++) {
            if (predicate.test(chars.charAt(i))) {
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
        for (int i = 0; i < chars.length(); i++) {
            if (predicate.test(chars.charAt(i))) {
                return false;
            }
        }
        return true;
    }
}
