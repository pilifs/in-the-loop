package java.util.stream;

import java.util.function.Function;
import java.util.function.IntFunction;
import java.util.function.Predicate;
import java.util.function.BiConsumer;
import java.util.function.Supplier;

/**
 * The model's sequential stream over an array: what {@code java.util.Arrays.stream(T[])} returns, and each
 * {@code map} of it. It is not a class of the JDK, whose streams are pipelines of stages over a spliterator; it
 * does what such a pipeline does where it is sequential, sized and stateless, which a stream of an array and its
 * {@code map}s is.
 *
 * <p>As the JDK's: a stream is used once, an intermediate or a terminal operation on one already linked or
 * consumed throws {@code IllegalStateException}; a null function is a {@code NullPointerException}, thrown before
 * the stream counts as used; nothing is read or computed until the terminal operation runs, which takes the
 * array's elements one at a time, in order, each through every {@code map} before the next is read; a match stops
 * at the first element that decides it ({@code anyMatch} and {@code noneMatch} at the first the predicate holds of,
 * {@code allMatch} at the first it doesn't), and of no elements {@code allMatch} and {@code noneMatch} are true and
 * {@code anyMatch} false; {@code toArray(generator)} asks the generator for an array of the stream's length before
 * any element is computed ({@code IllegalStateException} if it has another length), and stores each into it (an
 * {@code ArrayStoreException} for one the array doesn't take). An element may be null. The array's length is the
 * stream's from when it is made; its elements are read when the terminal operation runs.
 *
 * <p>Collection uses the supplied collector's callbacks in the sequential JDK pipeline's order.
 * Left out: every other operation ({@code filter}, {@code forEach}, parallel streams, ...),
 * and the messages of the exceptions, which no check reads.
 */
final class SequentialArrayStream<T> implements Stream<T> {
    private final Object[] source;
    private final int length;
    private final SequentialArrayStream<?> upstream;
    private final Function<Object, Object> mapper;
    private boolean linkedOrConsumed;

    private SequentialArrayStream(Object[] source, int length, SequentialArrayStream<?> upstream, Function<Object, Object> mapper) {
        this.source = source;
        this.length = length;
        this.upstream = upstream;
        this.mapper = mapper;
    }

    /** {@code java.util.Arrays.stream(array)}: a {@code NullPointerException} for a null array. */
    static <T> Stream<T> of(T[] array) {
        return new SequentialArrayStream<T>(array, array.length, null, null);
    }

    private void use() {
        if (linkedOrConsumed) {
            throw new IllegalStateException("stream has already been operated upon or closed");
        }
        linkedOrConsumed = true;
    }

    /** The element at {@code i} through every stage down to this one. */
    private Object element(int i) {
        if (upstream == null) {
            return source[i];
        }
        return mapper.apply(upstream.element(i));
    }

    @SuppressWarnings("unchecked")
    public boolean allMatch(Predicate<? super T> predicate) {
        if (predicate == null) {
            throw new NullPointerException();
        }
        use();
        for (int i = 0; i < length; i++) {
            if (!predicate.test((T) element(i))) {
                return false;
            }
        }
        return true;
    }

    @SuppressWarnings("unchecked")
    public boolean anyMatch(Predicate<? super T> predicate) {
        if (predicate == null) {
            throw new NullPointerException();
        }
        use();
        for (int i = 0; i < length; i++) {
            if (predicate.test((T) element(i))) {
                return true;
            }
        }
        return false;
    }

    @SuppressWarnings("unchecked")
    public boolean noneMatch(Predicate<? super T> predicate) {
        if (predicate == null) {
            throw new NullPointerException();
        }
        use();
        for (int i = 0; i < length; i++) {
            if (predicate.test((T) element(i))) {
                return false;
            }
        }
        return true;
    }

    @SuppressWarnings("unchecked")
    public <R> Stream<R> map(Function<? super T, ? extends R> mapper) {
        if (mapper == null) {
            throw new NullPointerException();
        }
        use();
        return new SequentialArrayStream<R>(source, length, this, (Function<Object, Object>) (Function<?, ?>) mapper);
    }

    @SuppressWarnings("unchecked")
    public <R, A> R collect(Collector<? super T, A, R> collector) {
        java.util.Objects.requireNonNull(collector);
        Supplier<A> supplier = collector.supplier();
        BiConsumer<A, ? super T> accumulator = collector.accumulator();
        collector.combiner();
        use();
        // OpenJDK asks for the operation's order flag before constructing its accumulation sink.
        collector.characteristics().contains(Collector.Characteristics.UNORDERED);
        A container = supplier.get();
        for (int i = 0; i < length; i++) {
            accumulator.accept(container, (T) element(i));
        }
        if (collector.characteristics().contains(Collector.Characteristics.IDENTITY_FINISH)) {
            return (R) container;
        }
        return collector.finisher().apply(container);
    }

    @SuppressWarnings("unchecked")
    public <A> A[] toArray(IntFunction<A[]> generator) {
        use();
        Object[] array = generator.apply(length);
        if (array.length != length) {
            throw new IllegalStateException("Begin size is not equal to fixed size");
        }
        for (int i = 0; i < length; i++) {
            array[i] = element(i);
        }
        return (A[]) array;
    }
}
