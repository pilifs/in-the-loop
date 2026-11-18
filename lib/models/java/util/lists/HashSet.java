package java.util;

/**
 * The model of {@code java.util.HashSet}: a set as the keys of a {@code HashMap}, as the JDK's is, where the map is
 * the tool's {@code HashMap} model (lib/models/java/util/HashMap.java), so that an element is found as the JDK finds
 * one, by its {@code hashCode} and {@code equals}. The own checker runs it only for a check that asks for it
 * ({@code --model java.util.HashSet}); otherwise the class is the JDK's, whose calls the checker does not run.
 * Spring's {@code AbstractBindingResult} makes one for every binding result (its suppressed fields), which is why a
 * check through {@code DataBinder.bind} meets it on every path (example 286).
 *
 * <p>Kept, each as the JDK's does it: {@code HashSet()}; {@code add(E)}, true when the set had no element equal to
 * it; {@code contains(Object)}; {@code size()} and {@code isEmpty()}. {@code null} is an element like any other.
 *
 * <p>The value the map holds for each key is the set itself where the JDK's is one shared object; no method kept
 * returns it. The class is abstract, as the {@code HashMap} model is, so that it declares no method it does not keep.
 *
 * <p>Left out, each the JDK call it names: every other constructor and method ({@code HashSet(int)},
 * {@code HashSet(Collection)}, {@code remove}, {@code clear}, {@code iterator}, {@code toArray}, {@code addAll},
 * {@code equals}, {@code hashCode}, {@code clone}, ...; the model extends the JDK's {@code AbstractSet}, whose
 * methods the checker does not run). The map model has no iteration, which is what most of them need.
 */
public abstract class HashSet<E> extends AbstractSet<E> implements Set<E>, Cloneable, java.io.Serializable {
    // Not private: a private field would be read through a method javac adds.
    HashMap<E, Object> map;

    public HashSet() {
        map = new HashMap<>();
    }

    public boolean add(E e) {
        return map.put(e, this) == null;
    }

    public boolean contains(Object o) {
        return map.containsKey(o);
    }

    public int size() {
        return map.size();
    }

    public boolean isEmpty() {
        return map.isEmpty();
    }
}
