package claims;

import java.util.concurrent.ConcurrentHashMap;

public class Registries {
    static class State {
        static final ConcurrentHashMap<String, Object> FIRST = new ConcurrentHashMap<>();
        static final ConcurrentHashMap<String, Object> ALIAS = FIRST;
        static final ConcurrentHashMap<String, Object> OTHER = new ConcurrentHashMap<>();
        static final ConcurrentHashMap<String, Object> FILLED = new ConcurrentHashMap<>();
        static {
            FILLED.put("present", "value");
        }
    }

    public static boolean register(boolean useFirstKey) {
        String key = useFirstKey ? "Aa" : "BB"; // Distinct Strings with the same hash.
        String other = useFirstKey ? "BB" : "Aa";
        Object value = new Object();
        return State.FIRST == State.ALIAS && State.FIRST != State.OTHER && State.FIRST.isEmpty()
                && State.FIRST.putIfAbsent(key, value) == null && State.ALIAS.get(key) == value
                && State.ALIAS.putIfAbsent(new StringBuilder(key).toString(), other) == value
                && State.FIRST.putIfAbsent(other, key) == null && State.FIRST.size() == 2
                && State.FIRST.get(other) == key && State.OTHER.get(key) == null;
    }

    public static boolean nullsAndCapacity(int capacity) {
        try {
            ConcurrentHashMap<String, Object> map = new ConcurrentHashMap<>(capacity);
            if (capacity < 0) return false;
            try { map.putIfAbsent("key", null); return false; } catch (NullPointerException expected) {}
            try { map.putIfAbsent(null, "v"); return false; } catch (NullPointerException expected) {}
            try { map.get(null); return false; } catch (NullPointerException expected) {}
            return map.isEmpty();
        } catch (IllegalArgumentException expected) {
            return capacity < 0;
        }
    }

    public static boolean readPopulated() {
        return State.FILLED.isEmpty();
    }

    public static boolean nonStringKey() {
        return new ConcurrentHashMap<Object, Object>().putIfAbsent(new Object(), "v") == null;
    }

    public static void main(String[] args) {
        boolean firstKey = Boolean.parseBoolean(args[0]);
        if (!register(firstKey) || readPopulated() || !nonStringKey()
                || !nullsAndCapacity(-1) || !nullsAndCapacity(0) || !nullsAndCapacity(12)) {
            throw new AssertionError();
        }
    }
}
