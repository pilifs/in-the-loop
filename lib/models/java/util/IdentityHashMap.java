package java.util;

/**
 * The native checker's model of reference-key lookup and replacement. These
 * operations compare references, including null, and never call either object's
 * equals or hashCode. Iteration order is outside this model's operations.
 */
public abstract class IdentityHashMap<K, V> implements Map<K, V> {
    private static final class Binding<K, V> {
        final K key;
        V value;
        final Binding<K, V> next;

        Binding(K key, V value, Binding<K, V> next) {
            this.key = key;
            this.value = value;
            this.next = next;
        }
    }

    private Binding<K, V> first;
    private int size;

    public IdentityHashMap() {}

    public IdentityHashMap(int expectedMaxSize) {
        if (expectedMaxSize < 0) {
            throw new IllegalArgumentException("expectedMaxSize is negative: " + expectedMaxSize);
        }
    }

    private Binding<K, V> find(Object key) {
        for (Binding<K, V> b = first; b != null; b = b.next) {
            if (b.key == key) return b;
        }
        return null;
    }

    public V get(Object key) {
        Binding<K, V> b = find(key);
        return b == null ? null : b.value;
    }

    public boolean containsKey(Object key) {
        return find(key) != null;
    }

    public V put(K key, V value) {
        Binding<K, V> b = find(key);
        if (b == null) {
            first = new Binding<K, V>(key, value, first);
            size++;
            return null;
        }
        V previous = b.value;
        b.value = value;
        return previous;
    }

    public int size() {
        return size;
    }
}
