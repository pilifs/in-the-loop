import java.util.*;
import org.agrona.collections.*;

public class PublicCaller {
    static void populate(Map<Integer,Integer> map) {
        for (int i = 1; i <= 3; i++) map.put(i, 10 * i);
    }

    static List<String> pairs(Object[] entries) {
        List<String> pairs = new ArrayList<>();
        for (Object item : entries) {
            Map.Entry<?,?> entry = (Map.Entry<?,?>) item;
            pairs.add(entry.getKey() + "=" + entry.getValue());
        }
        Collections.sort(pairs);
        return pairs;
    }

    static String shape(Object[] entries, List<String> pairs) {
        Set<Object> identities = Collections.newSetFromMap(new IdentityHashMap<>());
        Collections.addAll(identities, entries);
        return entries.getClass().getName() + "/" + entries.length + "/" + identities.size()
                + "/" + pairs.equals(Arrays.asList("1=10", "2=20", "3=30"));
    }

    static String arrays(Map<Integer,Integer> map) {
        populate(map);
        Object[] raw = map.entrySet().toArray();
        Map.Entry<?,?>[] typed = map.entrySet().toArray(new Map.Entry[0]);
        List<String> rawPairs = pairs(raw), typedPairs = pairs(typed);
        return shape(raw, rawPairs) + "," + shape(typed, typedPairs) + " pairs=" + rawPairs + "/" + typedPairs;
    }

    public static String observe(String[] args) {
        boolean avoid = !args[0].equals("allocating");
        Int2IntHashMap ints = new Int2IntHashMap(8, 0.6f, -127, avoid);
        if (args[0].equals("hash")) {
            populate(ints);
            Map.Entry<?,?>[] entries = ints.entrySet().toArray(new Map.Entry[0]);
            Set<Map.Entry<?,?>> set = new HashSet<>(Arrays.asList(entries));
            List<String> hashes = new ArrayList<>();
            for (Map.Entry<?,?> entry : entries) {
                Map.Entry<?,?> samePair = new AbstractMap.SimpleImmutableEntry<>(entry.getKey(), entry.getValue());
                hashes.add(entry.getKey() + "=" + entry.getValue() + "/" + entry.hashCode()
                        + "/" + samePair.hashCode() + "/" + entry.equals(samePair) + "/" + samePair.equals(entry));
            }
            Collections.sort(hashes);
            List<Boolean> hits = new ArrayList<>();
            for (int key = 1; key <= 3; key++) hits.add(set.contains(new AbstractMap.SimpleImmutableEntry<>(key, key * 10)));
            return "entry/actual/reference/equal=" + hashes + " hits=" + hits;
        }
        if (!avoid) return arrays(ints);
        return "int-int=" + arrays(ints) + " int-object=" + arrays(new Int2ObjectHashMap<Integer>(8, 0.6f, true))
                + " object-int=" + arrays(new Object2IntHashMap<Integer>(8, 0.6f, -127, true))
                + " object-object=" + arrays(new Object2ObjectHashMap<Integer,Integer>(8, 0.6f, true));
    }
}
