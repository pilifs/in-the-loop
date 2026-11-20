package trees;

import java.util.ConcurrentModificationException;
import java.util.Iterator;
import org.apache.commons.collections4.list.TreeList;

public final class Projection {
    private static int inspect(int code, int observer) {
        int word = code / 8;
        int n = word < 2 ? 1 : word < 6 ? 2 : 3;
        int bits = word - (n == 1 ? 0 : n == 2 ? 2 : 6);
        TreeList<String> list = new TreeList<>();
        for (int i = 0; i < n; i++) list.add(((bits >>> (n-1-i)) & 1) == 0 ? "A" : "B");
        Iterator<String> old = list.iterator();
        int which = code % 4;
        int index = which == 0 ? -1 : which == 1 ? n + 1 : which == 2 ? 5 : 10;
        boolean refused = false;
        try {
            if (((code / 4) & 1) == 0) list.add(index, "X");
            else list.remove(index);
        } catch (IndexOutOfBoundsException e) { refused = e.getClass() == IndexOutOfBoundsException.class; }
        if (observer == 0) return refused ? 1 : 0;
        if (observer == 1) {
            if (list.size() != n) return 0;
            for (int i = 0; i < n; i++) {
                String expected = ((bits >>> (n-1-i)) & 1) == 0 ? "A" : "B";
                if (!expected.equals(list.get(i))) return 0;
            }
            return 1;
        }
        String first = ((bits >>> (n-1)) & 1) == 0 ? "A" : "B";
        try { return first.equals((observer == 2 ? old : list.iterator()).next()) ? 1 : 0; }
        catch (ConcurrentModificationException failure) { return 0; }
    }

    public static int exception(int code) { return inspect(code, 0); }
    public static int contents(int code) { return inspect(code, 1); }
    public static int existing(int code) { return inspect(code, 2); }
    public static int fresh(int code) { return inspect(code, 3); }
}
