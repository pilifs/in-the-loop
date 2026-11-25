import java.util.*;
import com.google.common.collect.ForwardingSet;
import com.google.common.collect.Sets;

public class PublicCaller {
    static class CountingSet extends ForwardingSet<Integer> {
        final Set<Integer> values = new LinkedHashSet<>(List.of(1, 2, 3, 4));
        int iterations;
        protected Set<Integer> delegate() { return values; }
        public Iterator<Integer> iterator() { iterations++; return values.iterator(); }
    }

    static String both(Set<Integer> a, Set<Integer> b) { return a.equals(b) + "," + b.equals(a); }

    public static String observe(String[] args) {
        var backing = new CountingSet();
        var view = Sets.difference(backing, Collections.singleton(4));
        if (args[0].equals("traversal")) {
            backing.iterations = 0;
            boolean equal = view.equals(Collections.emptySet());
            return equal + "; " + (backing.iterations == 0 ? "no iteration" : "iterated") + " (" + backing.iterations + ")";
        }
        if (args[0].equals("ordinary"))
            return both(view, new LinkedHashSet<>(List.of(3, 2, 1))) + "/" + both(view, Set.of(1, 2, 9));
        var exclude = new LinkedHashSet<>(List.of(3, 4));
        var left = Sets.difference(Set.of(1, 2, 3), Set.of(2, 3));
        var right = Sets.difference(Set.of(1, 2, 3), exclude);
        String before = both(left, right);
        exclude.remove(4);
        exclude.add(2);
        return before + "/" + both(left, right);
    }
}
