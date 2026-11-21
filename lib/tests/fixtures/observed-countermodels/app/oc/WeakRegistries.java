package oc;

import java.util.Map;
import java.util.WeakHashMap;

public class WeakRegistries {
    static final class State {
        static final Object retained = new Object();
        static final Map<Object, Object> registry = new WeakHashMap<>();
        static final Map<Object, Object> alias = registry;
        static final Map<Object, Object> populated = new WeakHashMap<>();
        static {
            registry.put(retained, null);
            populated.put(retained, "present");
        }
    }

    static final class Callback {
        @Override public int hashCode() { throw new IllegalStateException(); }
    }

    public static boolean register() {
        Object key = new Object();
        return State.alias == State.registry && State.registry.put(key, null) == null
                && State.alias.get(key) == null && State.alias.put(key, null) == null
                && State.registry.get(null) == null;
    }

    public static boolean membership() { return State.registry.isEmpty(); }
    public static boolean nonNullWrite() { return State.alias.put(null, "present") == null; }
    public static boolean nonNullStartup() { return State.populated.get(null) == null; }
    public static boolean callback() { return State.registry.put(new Callback(), null) == null; }

    public static void main(String[] args) {
        if (!register() || membership() || !nonNullStartup() || !nonNullWrite()) throw new AssertionError();
        try { callback(); throw new AssertionError(); } catch (IllegalStateException expected) { }
    }
}
