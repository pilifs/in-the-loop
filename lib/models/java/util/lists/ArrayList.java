package java.util;

/**
 * The model of {@code java.util.ArrayList}: a list as an array of its elements and their number, as the JDK's is.
 * The own checker runs it only for a check that asks for it ({@code --model java.util.ArrayList}); otherwise the
 * class is the JDK's, whose calls the checker does not run.
 *
 * <p>Kept, each as the JDK's does it: {@code ArrayList()}; {@code ArrayList(int)}, with its
 * {@code IllegalArgumentException} for a negative capacity; {@code size()}, {@code isEmpty()}; {@code get(int)},
 * with its {@code IndexOutOfBoundsException}; {@code add(E)}, which returns true; {@code addAll(Collection)}, the
 * elements of the collection's {@code toArray()} appended, true if there were any; {@code toArray()} and
 * {@code toArray(T[])} (the given array when the elements fit, with a null after them when it is longer, else a
 * new array of its class); and {@code iterator()}, with {@code hasNext()} and {@code next()}, fail-fast
 * ({@code ConcurrentModificationException} after a change the iterator did not make, {@code NoSuchElementException}
 * past the end). Each change counts in {@code modCount}, {@code AbstractList}'s field.
 *
 * <p>The capacity is not kept: the array is as long as the list, whatever capacity was asked for, and grows with
 * each element. A program cannot observe it, but for the memory it takes: a JVM that cannot allocate the capacity
 * asked for throws {@code OutOfMemoryError}, and the model allocates nothing. The messages of the two exceptions
 * thrown here are the JDK's.
 *
 * <p>Left out, each the JDK call it names: every other constructor and method (the model extends the JDK's
 * {@code AbstractList}, whose methods the checker does not run: {@code set}, {@code remove}, {@code contains},
 * {@code indexOf}, {@code clear}, {@code equals}, {@code hashCode}, {@code listIterator}, {@code subList},
 * {@code forEach}, {@code stream}, ...), and the iterator's {@code remove()}. A {@code toArray(T[])} whose array
 * cannot hold an element is an {@code ArrayStoreException} on a JVM, which the checker's array stores do not model.
 */
public class ArrayList<E> extends AbstractList<E> implements List<E>, RandomAccess, Cloneable, java.io.Serializable {
    // Not private: the iterator reads them, and a private field would be read through a method javac adds.
    Object[] elements;
    int size;

    public ArrayList() {
        elements = new Object[0];
    }

    public ArrayList(int initialCapacity) {
        if (initialCapacity < 0) {
            throw new IllegalArgumentException("Illegal Capacity: " + initialCapacity);
        }
        elements = new Object[0];
    }

    public int size() {
        return size;
    }

    public boolean isEmpty() {
        return size == 0;
    }

    @SuppressWarnings("unchecked")
    public E get(int index) {
        if (index < 0 || index >= size) {
            throw new IndexOutOfBoundsException("Index " + index + " out of bounds for length " + size);
        }
        return (E) elements[index];
    }

    public boolean add(E e) {
        modCount++;
        elements = Arrays.copyOf(elements, size + 1);
        elements[size] = e;
        size++;
        return true;
    }

    public boolean addAll(Collection<? extends E> c) {
        Object[] a = c.toArray();
        modCount++;
        if (a.length == 0) {
            return false;
        }
        elements = Arrays.copyOf(elements, size + a.length);
        for (int i = 0; i < a.length; i++) {
            elements[size + i] = a[i];
        }
        size += a.length;
        return true;
    }

    public Object[] toArray() {
        return Arrays.copyOf(elements, size);
    }

    @SuppressWarnings("unchecked")
    public <T> T[] toArray(T[] a) {
        if (a.length < size) {
            // A new array of the given one's class: the copy of none of its elements, as long as the list.
            a = Arrays.copyOf(a, size);
        } else if (a.length > size) {
            a[size] = null;
        }
        for (int i = 0; i < size; i++) {
            a[i] = (T) elements[i];
        }
        return a;
    }

    public Iterator<E> iterator() {
        return new Itr();
    }

    private class Itr implements Iterator<E> {
        private int cursor;
        private int expectedModCount = modCount;

        Itr() {
        }

        public boolean hasNext() {
            return cursor != size;
        }

        @SuppressWarnings("unchecked")
        public E next() {
            if (modCount != expectedModCount) {
                throw new ConcurrentModificationException();
            }
            if (cursor >= size) {
                throw new NoSuchElementException();
            }
            return (E) elements[cursor++];
        }
    }
}
