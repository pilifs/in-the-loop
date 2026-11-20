package claims;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.ConcurrentModificationException;
import java.util.Iterator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.stream.Stream;

public final class ListConversions {
    public static boolean snapshots(boolean sized) {
        List<String> list = sized ? new ArrayList<>(1) : new ArrayList<>();
        if (!list.isEmpty()) return false;
        list.add("a");
        list.add(null);
        list.add("c");
        String[] source = {"old"};
        String[] fresh = list.toArray(source);
        String[] large = {"x", "x", "x", "x", "tail"};
        String[] reused = list.toArray(large);
        Object[] objects = list.toArray();
        if (source[0] != "old" || fresh == source || large != reused || large[3] != null || large[4] != "tail"
                || fresh.length != 3 || objects.getClass() != Object[].class || fresh.getClass() != String[].class) return false;
        if (!list.contains(null) || list.indexOf("c") != 2 || list.contains("absent")) return false;
        if (list.set(0, "b") != "a" || fresh[0] != "a" || list.get(0) != "b" || list.size() != 3) return false;
        ArrayList<String[]> rows = new ArrayList<>();
        rows.add(fresh);
        String[][] nested = rows.toArray(new String[0][]);
        Object primitiveRows = new int[1][1];
        return nested.length == 1 && nested[0] == fresh && primitiveRows instanceof Object[]
                && primitiveRows instanceof Cloneable[] && !(primitiveRows instanceof Object[][]);
    }

    public static boolean storesPrefix() {
        List<Object> list = new ArrayList<>(0);
        list.add("ok");
        list.add(new Object());
        String[] array = {"x", "y"};
        try {
            list.toArray(array);
            return false;
        } catch (ArrayStoreException expected) {
            return array[0] == "ok" && array[1] == "y";
        }
    }

    public static boolean shortCircuit(boolean include) {
        int[] calls = {0};
        String[] tokens = {"old", "new", "last"};
        boolean found = Stream.of(tokens).anyMatch(t -> { calls[0]++; return include && t == "new"; });
        return found == include && calls[0] == (include ? 2 : 3);
    }

    public static boolean digits(boolean large) {
        long value = large ? Long.MIN_VALUE : 0;
        String result = Long.toString(value);
        return result.equals(large ? "-9223372036854775808" : "0") && result != Long.toString(value);
    }

    public static boolean wrong() {
        ArrayList<String> list = new ArrayList<>(0);
        list.add("x");
        return list.toArray(new String[0]).length == 0;
    }

    public static boolean liveIterator(boolean invalidate) {
        List<String> list = new ArrayList<>(3);
        list.add("a"); list.add("b"); list.add("c");
        Iterator<String> it = list.iterator();
        try { it.remove(); return false; } catch (IllegalStateException expected) { }
        if (it.next() != "a") return false;
        list.set(1, "new");
        if (it.next() != "new") return false;
        it.remove();
        if (list.size() != 2 || list.get(1) != "c") return false;
        try { it.remove(); return false; } catch (IllegalStateException expected) { }
        if (invalidate) {
            list.remove("a");
            try { it.next(); return false; } catch (ConcurrentModificationException expected) { return true; }
        }
        if (!it.hasNext() || it.next() != "c" || it.hasNext()) return false;
        try { it.next(); return false; } catch (NoSuchElementException expected) { return true; }
    }

    public static boolean snapshotIterator() {
        List<String> list = new ArrayList<>(1);
        list.add("before");
        Iterator<String> it = list.iterator();
        list.set(0, "after");
        return it.next() == "before";
    }

    public static boolean nestedView(boolean invalidate) {
        List<String> root = new ArrayList<>(3);
        root.add("x"); root.add("a"); root.add("b");
        List<String> outer = root.subList(1, 3);
        List<String> inner = outer.subList(1, 2);
        if (inner.set(0, "new") != "b" || root.get(2) != "new") return false;
        root.set(2, "root");
        if (inner.get(0) != "root") return false;
        if (invalidate) {
            root.remove(0);
            try { inner.size(); return false; } catch (ConcurrentModificationException expected) { return true; }
        }
        if (inner.remove(0) != "root" || inner.size() != 0 || outer.size() != 1 || root.size() != 2) return false;
        try { root.subList(1, 0); return false; } catch (IllegalArgumentException expected) { return true; }
    }

    public static boolean arrayView() {
        String[] backing = {"a", "b"};
        List<String> list = Arrays.asList(backing);
        Iterator<String> it = list.iterator();
        backing[0] = "updated";
        if (it.next() != "updated" || list.set(1, "tail") != "b" || it.next() != "tail") return false;
        try { it.next(); return false; } catch (NoSuchElementException expected) { return backing[1] == "tail"; }
    }

    public static boolean viewEquality() {
        List<String> fixed = Arrays.asList("ab", "cd");
        List<String> list = new ArrayList<>(3);
        list.add("unused"); list.add("ab"); list.add("cd");
        List<String> view = list.subList(1, 3);
        if (!view.equals(fixed) || !fixed.equals(view) || !fixed.equals(List.of("ab", "cd"))) return false;
        Iterator<String> it = view.iterator();
        it.next();
        it.remove();
        return list.size() == 2 && view.size() == 1 && it.next() == "cd" && !fixed.equals(view) && !view.equals(fixed);
    }

    public static void main(String[] args) {
        if (!snapshots(false) || !snapshots(true) || !storesPrefix() || !shortCircuit(false) || !shortCircuit(true)
                || !digits(false) || !digits(true) || !liveIterator(false) || !liveIterator(true) || !nestedView(false) || !nestedView(true)
                || !arrayView() || !viewEquality() || snapshotIterator() || wrong()) throw new AssertionError();
    }
}
