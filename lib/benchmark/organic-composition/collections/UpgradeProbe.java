import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.apache.commons.collections4.iterators.IteratorChain;
import org.apache.commons.collections4.iterators.UnmodifiableIterator;

public class UpgradeProbe {
    private static final class Decorated extends IteratorChain<String> {
        Decorated(List<String> list) { super(list.iterator()); }
        @Override public String next() { return "child-" + super.next(); }
    }

    private static String locks(IteratorChain<String> parent, IteratorChain<String> child) {
        return (parent.isLocked() ? "L" : "U") + (child.isLocked() ? "L" : "U");
    }

    private static String preadvance(IteratorChain<String> child) {
        return child.next();
    }

    public static String observe(String[] args) {
        String mode = args[0];
        List<String> backing = new ArrayList<>(Arrays.asList("a", "b", "c"));
        List<String> tail = Arrays.asList("d", "e");
        if (mode.equals("flat")) {
            IteratorChain<String> flat = new IteratorChain<>(backing.iterator(), tail.iterator());
            List<String> seen = new ArrayList<>();
            boolean first = flat.hasNext(), second = flat.hasNext();
            while (flat.hasNext()) seen.add(flat.next());
            return first + "/" + second + "/" + seen + "/" + backing + "/" + tail + "/" + flat.isLocked();
        }
        IteratorChain<String> child = mode.equals("override") ? new Decorated(backing) : new IteratorChain<>(backing.iterator());
        if (mode.equals("late")) {
            IteratorChain<String> parent = new IteratorChain<>(child);
            String initial = locks(parent, child);
            child.addIterator(Collections.singletonList("late").iterator());
            String attached = locks(parent, child);
            boolean ready = parent.hasNext();
            String visited = locks(parent, child);
            List<String> seen = new ArrayList<>();
            while (parent.hasNext()) seen.add(parent.next());
            String append;
            try { child.addIterator(Collections.singletonList("post").iterator()); append = "accepted"; }
            catch (UnsupportedOperationException locked) { append = "rejected"; }
            return initial + "/" + attached + "/" + ready + "/" + visited + "/" + seen + "/" + append;
        }
        String first = mode.equals("advanced") ? preadvance(child) : "unadvanced";
        IteratorChain<String> parent = new IteratorChain<>(
            mode.equals("unmodifiable") ? UnmodifiableIterator.unmodifiableIterator(child) : child, tail.iterator());
        boolean ready = parent.hasNext();
        String next = parent.next();
        String removed;
        try { parent.remove(); removed = "ok"; }
        catch (UnsupportedOperationException wrongTarget) { removed = wrongTarget.getClass().getSimpleName(); }
        List<String> rest = new ArrayList<>();
        while (parent.hasNext()) rest.add(parent.next());
        return first + "/" + ready + "/" + next + "/" + removed + "/" + rest + "/" + backing + "/" + tail + "/" + locks(parent, child);
    }

    public static boolean attached(boolean late) {
        return observe(new String[]{late ? "late" : "advanced"}).contains(late ? "late" : "/b/ok/");
    }
}
