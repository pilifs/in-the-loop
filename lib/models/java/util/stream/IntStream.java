package java.util.stream;

import java.util.function.IntPredicate;

/**
 * A model of the JDK's {@code java.util.stream.IntStream} for the tool's own checker: the matches a claim written
 * in Java asks of a String's code units, {@code field.chars().allMatch(c -> c < 128)}, implemented by
 * {@link CharsStream}. Every other method is left out, so that a call of one is the JDK call it names.
 */
public interface IntStream {
    boolean allMatch(IntPredicate predicate);

    boolean anyMatch(IntPredicate predicate);

    boolean noneMatch(IntPredicate predicate);
}
