import java.util.ArrayList;
import java.util.Arrays;
import java.util.Objects;
import org.apache.commons.collections4.MultiSet;
import org.apache.commons.collections4.multiset.HashMultiSet;

public class PublicCaller {
    static HashMultiSet<String> fixture() {
        var bag = new HashMultiSet<String>();
        bag.add("A", 3);
        bag.add("B", 2);
        return bag;
    }

    static String remove(HashMultiSet<String> bag, boolean entries, String wanted) {
        var it = entries ? bag.entrySet().iterator() : bag.uniqueSet().iterator();
        while (it.hasNext()) {
            Object item = it.next();
            String key = item instanceof MultiSet.Entry<?> e ? (String) e.getElement() : (String) item;
            if (wanted == null || key.equals(wanted)) {
                int old = bag.getCount(key);
                it.remove();
                return key + old;
            }
        }
        throw new AssertionError(wanted);
    }

    static String snapshot(HashMultiSet<String> bag) {
        var array = Arrays.stream(bag.toArray()).map(Objects::toString).sorted().toList();
        var entries = bag.entrySet().stream().map(e -> e.getElement() + "=" + e.getCount()).sorted().toList();
        return bag.size() + "/" + bag.getCount("A") + "/" + bag.getCount("B") + "/" + array
                + "/" + bag.uniqueSet().stream().sorted().toList() + "/" + entries;
    }

    public static String observe(String[] args) {
        var results = new ArrayList<String>();
        for (boolean entries : new boolean[]{false, true}) {
            var bag = fixture();
            if (args[0].equals("occurrence")) {
                var it = bag.iterator();
                String key = it.next();
                it.remove();
                return key + " " + snapshot(bag) + " correct=" + (bag.size() == 4
                        && bag.getCount("A") == (key.equals("A") ? 2 : 3)
                        && bag.getCount("B") == (key.equals("B") ? 1 : 2));
            }
            if (args[0].equals("reinsert")) {
                remove(bag, entries, "A");
                bag.add("A");
                remove(bag, !entries, "B");
                results.add(snapshot(bag));
            } else {
                String old = remove(bag, entries, null);
                String expected = old.equals("A3") ? "2/0/2/[B, B]/[B]/[B=2]" : "3/3/0/[A, A, A]/[A]/[A=3]";
                String state = snapshot(bag);
                results.add(old + " " + state + (entries ? " entriesCorrect=" : " uniqueCorrect=") + state.equals(expected));
            }
        }
        return String.join(" | ", results);
    }
}
