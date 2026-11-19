package java.util.concurrent;

import java.util.HashMap;

/** Single-threaded registry operations for the native checker. It admits String keys and null
 * at these method entries. String equality and hashing have no user callbacks. */
public abstract class ConcurrentHashMap<K, V> implements ConcurrentMap<K, V> {
    private final HashMap<K, V> entries;

    public ConcurrentHashMap() {
        entries = new HashMap<>();
    }

    public ConcurrentHashMap(int capacity) {
        if (capacity < 0) {
            throw new IllegalArgumentException();
        }
        entries = new HashMap<>();
    }

    public V get(Object key) {
        if (key == null) {
            throw new NullPointerException();
        }
        return entries.get(key);
    }

    public V putIfAbsent(K key, V value) {
        if (key == null || value == null) {
            throw new NullPointerException();
        }
        V previous = entries.get(key);
        if (previous == null) {
            entries.put(key, value);
        }
        return previous;
    }

    public int size() {
        return entries.size();
    }

    public boolean isEmpty() {
        return entries.isEmpty();
    }
}
