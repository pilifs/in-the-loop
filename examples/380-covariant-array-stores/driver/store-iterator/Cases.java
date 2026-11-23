import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "history", "arguments", new String[]{"false", "false", "0"}),
                fields("holds", IteratorStores.history(false, false, 0)), fields());
        row(1, fields("entry", "history", "arguments", new String[]{"false", "false", "1"}),
                fields("holds", IteratorStores.history(false, false, 1)), fields());
        row(2, fields("entry", "history", "arguments", new String[]{"false", "false", "2"}),
                fields("holds", IteratorStores.history(false, false, 2)), fields());
        row(3, fields("entry", "history", "arguments", new String[]{"false", "true", "0"}),
                fields("holds", IteratorStores.history(false, true, 0)), fields());
        row(4, fields("entry", "history", "arguments", new String[]{"false", "true", "1"}),
                fields("holds", IteratorStores.history(false, true, 1)), fields());
        row(5, fields("entry", "history", "arguments", new String[]{"false", "true", "2"}),
                fields("holds", IteratorStores.history(false, true, 2)), fields());
        row(6, fields("entry", "history", "arguments", new String[]{"true", "false", "0"}),
                fields("holds", IteratorStores.history(true, false, 0)), fields());
        row(7, fields("entry", "history", "arguments", new String[]{"true", "false", "1"}),
                fields("holds", IteratorStores.history(true, false, 1)), fields());
        row(8, fields("entry", "history", "arguments", new String[]{"true", "false", "2"}),
                fields("holds", IteratorStores.history(true, false, 2)), fields());
        row(9, fields("entry", "history", "arguments", new String[]{"true", "true", "0"}),
                fields("holds", IteratorStores.history(true, true, 0)), fields());
        row(10, fields("entry", "history", "arguments", new String[]{"true", "true", "1"}),
                fields("holds", IteratorStores.history(true, true, 1)), fields());
        row(11, fields("entry", "history", "arguments", new String[]{"true", "true", "2"}),
                fields("holds", IteratorStores.history(true, true, 2)), fields());
    }
}
