import java.util.Collection;
import java.util.List;

/**
 * Stubs JBMC's call graph reaches on a path it never takes. The model of {@code List.copyOf} hands back a list
 * {@code List.of} made, and calls {@code Collection.isEmpty} and {@code toArray}, which JBMC stubs, only for any
 * other collection: {@code copied} gives it none, {@code opaque} a collection JBMC knows nothing of.
 */
public class P {
    enum E { A, B }

    static int copied(int n) {
        List<E> l = List.copyOf(List.of(n > 0 ? E.A : E.B, E.B));
        return l.get(0).ordinal() + l.size();
    }

    static int opaque(Collection<E> c) {
        return List.copyOf(c).size();
    }
}
