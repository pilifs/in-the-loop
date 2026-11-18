package java.util;

/**
 * The model of {@code java.util.ArrayDeque} used as a stack: its elements in an array, the last pushed last, and
 * their number. The own checker runs it only for a check that asks for it ({@code --model java.util.ArrayDeque});
 * otherwise the class is the JDK's, whose calls the checker does not run. Spring's {@code AbstractErrors} makes one
 * for every binding result (its stack of nested paths), which is why a check through {@code DataBinder.bind} meets
 * it on every path (example 286).
 *
 * <p>Kept, each as the JDK's does it: {@code ArrayDeque()}; {@code push(E)} ({@code addFirst}), with its
 * {@code NullPointerException} for a null element; {@code pop()} ({@code removeFirst}), the element pushed last,
 * with its {@code NoSuchElementException} on an empty deque; {@code peek()} ({@code peekFirst}), that element or
 * {@code null}; {@code size()}, {@code isEmpty()} and {@code clear()}. The JDK's two exceptions have no message and
 * neither have these.
 *
 * <p>The capacity is not kept: the array is as long as the deque and grows with each element, which a program cannot
 * observe but for the memory it takes. The class is abstract, as the {@code HashMap} model is, so that it declares
 * no method it does not keep.
 *
 * <p>Left out, each the JDK call it names: every other constructor and method ({@code ArrayDeque(int)},
 * {@code ArrayDeque(Collection)}, {@code addFirst}, {@code addLast}, {@code offer}, {@code poll}, {@code add},
 * {@code remove}, {@code iterator}, {@code descendingIterator}, {@code contains}, {@code toArray}, {@code clone},
 * {@code toString}, ...; the model extends the JDK's {@code AbstractCollection}, whose methods the checker does not
 * run).
 */
public abstract class ArrayDeque<E> extends AbstractCollection<E> implements Deque<E>, Cloneable, java.io.Serializable {
    // Not private: a private field would be read through a method javac adds.
    Object[] elements;
    int size;

    public ArrayDeque() {
        elements = new Object[0];
    }

    public void push(E e) {
        if (e == null) {
            throw new NullPointerException();
        }
        elements = Arrays.copyOf(elements, size + 1);
        elements[size] = e;
        size++;
    }

    @SuppressWarnings("unchecked")
    public E pop() {
        if (size == 0) {
            throw new NoSuchElementException();
        }
        size--;
        E e = (E) elements[size];
        elements[size] = null;
        return e;
    }

    @SuppressWarnings("unchecked")
    public E peek() {
        return size == 0 ? null : (E) elements[size - 1];
    }

    public int size() {
        return size;
    }

    public boolean isEmpty() {
        return size == 0;
    }

    public void clear() {
        elements = new Object[0];
        size = 0;
    }
}
