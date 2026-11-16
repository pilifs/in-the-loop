package java.util;

/**
 * A model of the JDK's {@code java.util.LinkedHashMap} for the tool's own checker: a map that is iterated in the
 * order its keys were first put, which the model of {@link HashMap} already keeps its entries in (one chain, in
 * insertion order; a key put again keeps its place, as the JDK's insertion-ordered map has it).
 *
 * <p>Kept, as the JDK has them: {@code LinkedHashMap()} and {@code LinkedHashMap(int)} (an
 * {@code IllegalArgumentException} for a negative capacity), what {@link HashMap}'s model has ({@code put},
 * {@code get}, {@code containsKey}, {@code size}, {@code isEmpty}), and {@code values()}: one collection for the
 * map, the same object on every call, whose {@code size()} is the map's and whose {@code iterator()} gives the
 * values in insertion order, a value put for a key already held in that key's place. An iterator is fail-fast as
 * the JDK's is: {@code hasNext()} says whether an entry is left, and {@code next()} throws
 * {@code ConcurrentModificationException} when a key was added since the iterator was made, checked before it
 * throws {@code NoSuchElementException} past the end.
 *
 * <p>Left out, so that each is the JDK call it names: the other constructors (a load factor, access order,
 * another map), {@code keySet}, {@code entrySet}, {@code remove}, {@code clear} and every other method of
 * the map; every method of the values collection but {@code size} and {@code iterator} (it extends the JDK's
 * {@code AbstractCollection}, whose methods the checker does not run); the iterator's {@code remove} and
 * {@code forEachRemaining}.
 */
public abstract class LinkedHashMap<K, V> extends HashMap<K, V> {
    /** How many keys were added: what the JDK counts as the structural modifications this model has. */
    int modCount;
    private Collection<V> values;

    public LinkedHashMap() {
    }

    public LinkedHashMap(int initialCapacity) {
        super(initialCapacity);
    }

    public V put(K key, V value) {
        int before = size();
        V old = super.put(key, value);
        if (size() != before) {
            modCount++;
        }
        return old;
    }

    public Collection<V> values() {
        Collection<V> vs = values;
        if (vs == null) {
            vs = new LinkedValues<V>(this);
            values = vs;
        }
        return vs;
    }

    static final class LinkedValues<V> extends AbstractCollection<V> {
        private final LinkedHashMap<?, V> map;

        LinkedValues(LinkedHashMap<?, V> map) {
            this.map = map;
        }

        public int size() {
            return map.size();
        }

        public Iterator<V> iterator() {
            return new LinkedValueIterator<V>(map);
        }
    }

    static final class LinkedValueIterator<V> implements Iterator<V> {
        private final LinkedHashMap<?, V> map;
        private Node next;
        private final int expectedModCount;

        LinkedValueIterator(LinkedHashMap<?, V> map) {
            this.map = map;
            this.next = map.first;
            this.expectedModCount = map.modCount;
        }

        public boolean hasNext() {
            return next != null;
        }

        public V next() {
            Node e = next;
            if (map.modCount != expectedModCount) {
                throw new ConcurrentModificationException();
            }
            if (e == null) {
                throw new NoSuchElementException();
            }
            next = e.next;
            return (V) e.value;
        }
    }
}
