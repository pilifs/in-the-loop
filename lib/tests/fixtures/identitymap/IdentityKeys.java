package fixtures;

import java.util.IdentityHashMap;
import java.util.Map;

public final class IdentityKeys {
    static final class Key {
        public int hashCode() { throw new AssertionError("hashed a key"); }
        public boolean equals(Object other) { throw new AssertionError("called equals"); }
    }

    public static int bindings(int n) {
        Key first = new Key();
        Key second = n == 0 ? first : new Key();
        Map<Key, Boolean> map = new IdentityHashMap<>();
        Boolean marker = Boolean.valueOf(n != 0);
        Object erased = marker;
        if (erased.equals(null) || erased.equals(first) || erased.equals(Boolean.TRUE) != (n != 0)) return -1;
        map.put(first, marker);
        Boolean before = map.put(second, Boolean.FALSE);
        map.put(null, null);
        if (!map.containsKey(null) || map.get(null) != null) return -1;
        if (n == 0) return before == Boolean.FALSE && !map.get(first).booleanValue() ? map.size() : -1;
        return before == null && map.get(first) == Boolean.TRUE && map.get(first).booleanValue() ? map.size() : -1;
    }

    public static void main(String[] args) {
        System.out.println(bindings(0) + " " + bindings(1));
    }
}
