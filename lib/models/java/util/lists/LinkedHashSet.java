package java.util;

/**
 * The model of {@code java.util.LinkedHashSet}: the {@code HashSet} model (lib/models/java/util/lists/HashSet.java),
 * whose map finds an element as the JDK's does, by its {@code hashCode} and {@code equals}, with the elements also
 * kept in the order they were first added, as the JDK's linked map keeps its keys. The own checker runs it only for
 * a check that asks for it ({@code --model java.util.LinkedHashSet}), which runs the {@code HashSet} model above it
 * too; otherwise the class is the JDK's, whose calls the checker does not run. Spring's
 * {@code DefaultMessageCodesResolver} collects the message codes of every binding error in one (example 286).
 *
 * <p>Kept, each as the JDK's does it: {@code LinkedHashSet()}; {@code add(E)}, true when the set had no element
 * equal to it, which then comes last in the order; {@code toArray()} and {@code toArray(T[])}, the elements in that
 * order (into the given array when they fit, with a null after them when it is longer, else into a new array of its
 * class); and, from the {@code HashSet} model, {@code contains}, {@code size} and {@code isEmpty}.
 *
 * <p>Left out, each the JDK call it names: every other constructor and method ({@code LinkedHashSet(int)},
 * {@code LinkedHashSet(Collection)}, {@code iterator}, {@code remove}, {@code clear}, {@code addAll}, {@code spliterator},
 * {@code equals}, {@code hashCode}, {@code clone}, ...). None of the kept methods takes an element out, so the order
 * holds exactly the map's keys. A {@code toArray(T[])} whose array cannot hold an element is an
 * {@code ArrayStoreException} on a JVM, which the checker's array stores do not model.
 */
public abstract class LinkedHashSet<E> extends HashSet<E> implements Set<E>, Cloneable, java.io.Serializable {
    // Not private: a private field would be read through a method javac adds.
    Object[] order;

    public LinkedHashSet() {
        super();
        order = new Object[0];
    }

    public boolean add(E e) {
        if (!super.add(e)) {
            return false;
        }
        order = Arrays.copyOf(order, order.length + 1);
        order[order.length - 1] = e;
        return true;
    }

    public Object[] toArray() {
        return Arrays.copyOf(order, order.length);
    }

    @SuppressWarnings("unchecked")
    public <T> T[] toArray(T[] a) {
        int size = order.length;
        if (a.length < size) {
            // A new array of the given one's class, as long as the set.
            a = Arrays.copyOf(a, size);
        } else if (a.length > size) {
            a[size] = null;
        }
        for (int i = 0; i < size; i++) {
            a[i] = (T) order[i];
        }
        return a;
    }
}
