package claims;

import java.util.BitSet;
import java.util.Collections;
import java.util.ConcurrentModificationException;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Properties;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

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

    public static boolean packedValue(boolean grow) {
        Map<String, BitSet> map = new HashMap<>();
        BitSet original = new BitSet(1);
        map.put("k", original);
        BitSet entry = map.entrySet().iterator().next().getValue();
        int index = grow ? 64 : 63;
        original.set(0);
        entry.set(index, true);
        entry.set(0, false);
        if (entry != original || original.get(0) || !original.get(index) || original.get(index + 1)) return false;
        try { entry.get(-1); return false; } catch (IndexOutOfBoundsException expected) { return true; }
    }

    public static boolean insertionOrder() {
        Map<String, String> map = new HashMap<>();
        map.put("B", "two"); map.put("A", "one");
        return "B".equals(map.keySet().iterator().next());
    }

    public static boolean backedSets() {
        Map<String, Boolean> map = new HashMap<>();
        Set<String> set = Collections.newSetFromMap(map);
        if (!set.add("k") || set.add("k") || map.get("k") != Boolean.TRUE) return false;
        try { Collections.newSetFromMap(map); return false; } catch (IllegalArgumentException expected) { }
        map.put("other", Boolean.FALSE);
        if (!set.contains("other") || !set.remove("k") || set.size() != 1) return false;
        try { Collections.newSetFromMap(null); return false; } catch (NullPointerException expected) { }
        return !map.containsKey("k") && set.iterator().next().equals("other");
    }

    public static boolean concurrentViews() {
        ConcurrentHashMap<String, Boolean> map = new ConcurrentHashMap<>();
        ConcurrentHashMap<String, Boolean> separate = new ConcurrentHashMap<>();
        Set<String> set = Collections.newSetFromMap(map);
        ConcurrentHashMap.KeySetView<String, Boolean> keys = map.keySet();
        return set.isEmpty() && set.size() == 0 && keys == map.keySet() && keys.getMap() == map
                && keys != separate.keySet() && keys.isEmpty() && keys.getMappedValue() == null;
    }

    static final class ThrowingHash {
        @Override public int hashCode() { throw new IllegalStateException(); }
    }

    public static boolean initialProperties() {
        Properties defaults = new Properties(4);
        Properties values = new Properties(defaults);
        values.putAll(defaults);
        values.putAll(values);
        if (!values.isEmpty() || defaults.size() != 0 || values.getProperty("absent") != null
                || !"fallback".equals(values.getProperty("absent", "fallback")) || values.containsKey("absent")
                || values.entrySet().iterator().hasNext()) return false;
        try { new Properties(-1); return false; } catch (IllegalArgumentException expected) { }
        try { values.getProperty(null); return false; } catch (NullPointerException expected) { }
        try { values.get(new ThrowingHash()); return false; } catch (IllegalStateException expected) { return true; }
    }

    public static boolean losesNonEmptyProperties() {
        Properties values = new Properties();
        values.putAll(Collections.singletonMap("k", "value"));
        return values.isEmpty();
    }

    public static void main(String[] args) {
        if (!remove(true) || !remove(false) || !collisions() || !mixed() || !copies() || insertionOrder()
                || !packedValue(false) || !packedValue(true) || !backedSets() || !concurrentViews() || !initialProperties()
                || losesNonEmptyProperties()) throw new AssertionError();
    }
}
