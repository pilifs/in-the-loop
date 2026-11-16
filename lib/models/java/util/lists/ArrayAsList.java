package java.util;

/**
 * The model's list over an array: what {@code java.util.Arrays.asList(T...)} returns. It is not a class of the
 * JDK, whose list of that kind is a class nested in {@code Arrays}; it does what that one does for the calls
 * kept: {@code size()}, the array's length; {@code get(int)}, the array's element, read when it is asked for (the
 * list is a view, so a later store into the array shows), with the array's own
 * {@code ArrayIndexOutOfBoundsException}; and {@code toArray()}, a new {@code Object[]} of the elements. A null
 * array is a {@code NullPointerException} where the list is made.
 *
 * <p>Left out, each the JDK call it names: every other method (it extends the JDK's {@code AbstractList}, whose
 * methods the checker does not run: {@code set}, {@code iterator}, {@code contains}, {@code toArray(T[])}, ...).
 */
final class ArrayAsList<E> extends AbstractList<E> {
    private final E[] a;

    private ArrayAsList(E[] a) {
        this.a = a;
    }

    /** {@code java.util.Arrays.asList(a)}. */
    static <T> List<T> of(T[] a) {
        if (a == null) {
            throw new NullPointerException();
        }
        return new ArrayAsList<T>(a);
    }

    public int size() {
        return a.length;
    }

    public E get(int index) {
        return a[index];
    }

    public Object[] toArray() {
        Object[] r = new Object[a.length];
        for (int i = 0; i < a.length; i++) {
            r[i] = a[i];
        }
        return r;
    }
}
