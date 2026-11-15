package java.util;

/**
 * A model of the JDK's {@code java.util.HashMap} for JBMC and the tool's own checker, which have no bytecode they
 * can run for it: the JDK's reads a {@code float} load factor, which the own checker has no arithmetic for, and
 * JBMC stubs the class, so that a map a class initializer fills ({@code HttpMethod}'s names) answered anything.
 *
 * <p>Kept, as the JDK has them: {@code HashMap()}, {@code HashMap(int)} with its {@code IllegalArgumentException}
 * for a negative capacity, {@code get}, {@code containsKey}, {@code put}, {@code size} and {@code isEmpty}. A key is
 * found as the JDK finds one: an entry of the same hash ({@code hashCode()}, 0 for {@code null}) whose key is the
 * same reference or {@code equals} the one looked up, called on the key looked up with the entry's key as its
 * argument, and only on an entry of the same hash. {@code null} is a key and a value like any other.
 *
 * <p>The entries are one chain in insertion order, where the JDK's are a table of buckets. So what is left out is
 * what depends on the table: the order in which the entries of one hash are compared (the JDK's is insertion order
 * within a bucket too, until a bucket of eight becomes a tree, which orders {@code Comparable} keys by
 * {@code compareTo}), and resizing. Neither is observed by a key whose {@code equals} and {@code hashCode} only
 * compute, and a map is not iterated here: {@code keySet}, {@code values}, {@code entrySet}, {@code remove},
 * {@code putAll}, {@code clear}, the {@code compute} family and every other method are left out, so that JBMC stubs
 * them as before and the gap scan names them.
 *
 * <p>The interpreter keeps its own natives for {@code HashMap}, which behave the same (the values corpus,
 * {@code lib/tests/values.rs}, checks all three against a JVM).
 */
public abstract class HashMap<K, V> implements Map<K, V> {
    private Node first;
    private Node last;
    private int size;

    public HashMap() {
    }

    public HashMap(int initialCapacity) {
        if (initialCapacity < 0) {
            throw new IllegalArgumentException();
        }
    }

    public int size() {
        return size;
    }

    public boolean isEmpty() {
        return size == 0;
    }

    public V get(Object key) {
        Node e = find(key);
        return e == null ? null : (V) e.value;
    }

    public boolean containsKey(Object key) {
        return find(key) != null;
    }

    public V put(K key, V value) {
        Node e = find(key);
        if (e != null) {
            V old = (V) e.value;
            e.value = value;
            return old;
        }
        Node made = new Node(key == null ? 0 : key.hashCode(), key, value);
        if (last == null) {
            first = made;
        } else {
            last.next = made;
        }
        last = made;
        size++;
        return null;
    }

    private Node find(Object key) {
        int hash = key == null ? 0 : key.hashCode();
        for (Node e = first; e != null; e = e.next) {
            Object k;
            if (e.hash == hash && ((k = e.key) == key || (key != null && key.equals(k)))) {
                return e;
            }
        }
        return null;
    }

    static final class Node {
        final int hash;
        final Object key;
        Object value;
        Node next;

        Node(int hash, Object key, Object value) {
            this.hash = hash;
            this.key = key;
            this.value = value;
        }
    }
}
