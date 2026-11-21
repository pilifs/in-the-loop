package oc;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

public class PublishedLookup {
    static class Base { Object name; }
    static class Holder extends Base {
        String name;
        Holder next;
        Map<String, Object> data;
        Object unobserved;
    }
    static class Root {
        static final Holder shared = new Holder();
        static final HashMap<String, Object> backing = new HashMap<>();
        static final AtomicReference<Holder> cell = new AtomicReference<>(shared);
        static {
            shared.next = shared;
            shared.data = backing;
            shared.name = "child";
            ((Base) shared).name = "base";
            shared.unobserved = new StringBuilder("opaque");
            backing.put("Aa", shared);
            backing.put("BB", null);
            backing.put(null, shared.unobserved);
            backing.put("\uD800", shared);
        }
    }
    public static boolean reads() {
        Holder h = Root.cell.get();
        if (h != Root.shared || h != h.next || h.data != Root.backing || !h.name.equals("child")
                || !"base".equals(((Base) h).name) || h.data.size() != 4 || h.data.isEmpty()) return false;
        if (h.data.get("Aa") != h || h.data.get("\uD800") != h || !h.data.containsKey("BB")
                || h.data.get("BB") != null || h.data.containsKey("absent") || h.data.get("absent") != null
                || !h.data.containsKey(null)) return false;
        h.name = "changed";
        Root.cell.set(null);
        return Root.cell.get() == null && Root.shared.name.equals("changed") && "base".equals(((Base) h).name);
    }
    public static boolean unknownValue() { return Root.shared.data.get(null) != null; }
    public static boolean mutation() {
        Root.backing.put("added", "value");
        return Root.shared.data.containsKey("added");
    }
    public static void main(String[] args) {
        if (!reads() || !unknownValue() || !mutation()) throw new AssertionError();
    }
}
