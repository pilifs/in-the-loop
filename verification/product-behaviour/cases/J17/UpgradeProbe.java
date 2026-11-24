import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import org.eclipse.collections.impl.map.mutable.UnifiedMap;
import org.eclipse.collections.api.block.predicate.Predicate2;

public class UpgradeProbe {
    private static final class Key {
        final int id;
        Key(int id) { this.id = id; }
        @Override public int hashCode() { return 17; }
        @Override public boolean equals(Object other) { return other instanceof Key && ((Key) other).id == id; }
    }

    public static String observe(String[] args) {
        boolean reverse = args[0].equals("reverse");
        int trials = 0, firstChanges = 0, secondChanges = 0, kept = 0, nulls = 0;
        for (int size = 0; size <= 6; size++) {
            for (int mask = 0; mask < (1 << size); mask++) {
                UnifiedMap<Key, Integer> actual = new UnifiedMap<>();
                Map<Key, Integer> reference = new HashMap<>();
                actual.put(null, 99);
                reference.put(null, 99);
                Set<Key> view = actual.keySet();
                for (int i = 0; i < size; i++) {
                    int id = reverse ? size - 1 - i : i;
                    actual.put(new Key(id), 10 + id);
                    reference.put(new Key(id), 10 + id);
                }
                int subset = mask;
                Predicate2<Key, Integer> remove = (key, value) -> key != null && (subset & (1 << key.id)) != 0;
                boolean first = actual.removeIf(remove);
                boolean expected = reference.entrySet().removeIf(e -> e.getKey() != null && (subset & (1 << e.getKey().id)) != 0);
                if (first != expected || !reference.equals(actual) || !view.equals(reference.keySet()))
                    throw new AssertionError("first removal differs at size=" + size + ", mask=" + mask);
                boolean second = actual.removeIf(remove);
                if (second || !reference.equals(actual) || !view.equals(reference.keySet())
                        || !Integer.valueOf(99).equals(actual.get(null)))
                    throw new AssertionError("second removal differs at size=" + size + ", mask=" + mask);
                firstChanges += first ? 1 : 0;
                secondChanges += second ? 1 : 0;
                kept += actual.size() - 1;
                nulls += view.contains(null) ? 1 : 0;
                trials++;
            }
        }
        return trials + "/" + firstChanges + "/" + secondChanges + "/" + kept + "/" + nulls;
    }
}
