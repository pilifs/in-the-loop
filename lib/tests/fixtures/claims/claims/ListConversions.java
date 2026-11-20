package claims;

import java.util.ArrayList;
import java.util.List;
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

    public static void main(String[] args) {
        if (!snapshots(false) || !snapshots(true) || !storesPrefix() || !shortCircuit(false) || !shortCircuit(true)
                || !digits(false) || !digits(true) || wrong()) throw new AssertionError();
    }
}
