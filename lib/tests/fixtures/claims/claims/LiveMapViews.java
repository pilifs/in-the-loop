package claims;

import java.util.ConcurrentModificationException;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Set;

public final class LiveMapViews {
    public static boolean remove(boolean entry) {
        Map<String, String> map = new HashMap<>();
        // Bucket order for B and A on both selected JDKs is the opposite of insertion order.
        map.put("B", "two");
        map.put("A", "one");
        Set<String> keys = map.keySet();
        Set<Map.Entry<String, String>> pairs = map.entrySet();
        if (keys != map.keySet() || pairs != map.entrySet()) return false;
        Iterator<?> iterator = entry ? pairs.iterator() : keys.iterator();
        try { iterator.remove(); return false; } catch (IllegalStateException expected) { }
        Object first = iterator.next();
        if (entry) {
            @SuppressWarnings("unchecked") Map.Entry<String, String> node = (Map.Entry<String, String>) first;
            if (!"A".equals(node.getKey()) || !"one".equals(node.setValue("changed")) || !"changed".equals(map.get("A"))) return false;
        } else if (!"A".equals(first)) return false;
        iterator.remove();
        if (keys.size() != 1 || pairs.size() != 1 || map.size() != 1 || map.containsKey("A") || !map.containsKey("B")) return false;
        iterator.next();
        if (iterator.hasNext()) return false;
        try { iterator.next(); return false; } catch (NoSuchElementException expected) { return true; }
    }

    public static boolean collisions() {
        Map<String, String> map = new HashMap<>();
        map.put("FB", "old");
        map.put("Ea", "other");
        map.put(null, null);
        Iterator<Map.Entry<String, String>> it = map.entrySet().iterator();
        if (it.next().getKey() != null) return false;
        Map.Entry<String, String> first = it.next();
        map.put("FB", "updated");
        if (!"updated".equals(first.getValue()) || !"FB".equals(first.getKey())) return false;
        it.remove();
        if (!"Ea".equals(it.next().getKey()) || map.containsKey("FB")) return false;
        map.put("added", "x");
        try { it.remove(); return false; } catch (ConcurrentModificationException expected) { return true; }
    }

    public static boolean mixed() {
        Map<String, String> hash = new HashMap<>(), linked = new LinkedHashMap<>();
        hash.put("B", "real"); linked.put("B", "linked");
        hash.put("A", "other"); linked.put("A", "later");
        return "A".equals(hash.keySet().iterator().next()) && "linked".equals(linked.values().iterator().next())
                && "real".equals(hash.get("B")) && "later".equals(linked.get("A"));
    }

    public static boolean copies() {
        Map<String, String> map = new HashMap<>();
        map.put("k", "v");
        Map<String, String> copy = Map.copyOf(map);
        return copy.equals(map) && map.equals(copy) && new LinkedHashMap<>(map).equals(copy);
    }

    public static boolean insertionOrder() {
        Map<String, String> map = new HashMap<>();
        map.put("B", "two"); map.put("A", "one");
        return "B".equals(map.keySet().iterator().next());
    }

    public static void main(String[] args) {
        if (!remove(true) || !remove(false) || !collisions() || !mixed() || !copies() || insertionOrder()) throw new AssertionError();
    }
}
