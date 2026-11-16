package java.util.stream;

import java.util.function.IntPredicate;

/**
 * A model of the JDK's {@code java.util.stream.IntStream} for the tool's own checker: the matches a claim written
 * in Java asks of a String's code units, {@code field.chars().allMatch(c -> c < 128)}, implemented by
 * {@link CharsStream}, of the ints of a range, {@code IntStream.range(0, n).allMatch(i -> ...)}, implemented by
 * {@link RangeStream} (the static {@code range} is entered there, not declared here), and of the ints of an array,
 * {@code Arrays.stream(servlets).allMatch(s -> s == 0 || s == 1)}, implemented by {@link IntArrayStream}. Every
 * other method is left out, so that a call of one is the JDK call it names.
 */
public interface IntStream {
    boolean allMatch(IntPredicate predicate);

    boolean anyMatch(IntPredicate predicate);

    boolean noneMatch(IntPredicate predicate);
}
