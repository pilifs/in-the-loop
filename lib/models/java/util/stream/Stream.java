package java.util.stream;

import java.util.function.Function;
import java.util.function.IntFunction;
import java.util.function.Predicate;

/**
 * A model of the JDK's {@code java.util.stream.Stream} for the tool's own checker, which has no bytecode it can run
 * for the JDK's pipelines (spliterators, sinks and flags behind every call): the operations a claim written in Java
 * asks of a sequential stream over an array, {@code java.util.Arrays.stream(patterns).anyMatch(p -> ...)}.
 *
 * <p>Kept, as the JDK has them for a sequential stream: {@code allMatch}, {@code anyMatch}, {@code noneMatch},
 * {@code map}, {@code collect(Collector)} and {@code toArray(IntFunction)}, implemented by {@link SequentialArrayStream}. Every other method is
 * left out, so that a call of one is the JDK call it names, a gap the checker refuses by name.
 */
public interface Stream<T> {
    boolean allMatch(Predicate<? super T> predicate);

    boolean anyMatch(Predicate<? super T> predicate);

    boolean noneMatch(Predicate<? super T> predicate);

    <R> Stream<R> map(Function<? super T, ? extends R> mapper);

    <R, A> R collect(Collector<? super T, A, R> collector);

    <A> A[] toArray(IntFunction<A[]> generator);
}
