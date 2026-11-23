import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "history", "arguments", new String[]{"-1", "0", "false"}),
                fields("holds", ArrayStores.history(-1, 0, false)), fields());
        row(1, fields("entry", "history", "arguments", new String[]{"-1", "0", "true"}),
                fields("holds", ArrayStores.history(-1, 0, true)), fields());
        row(2, fields("entry", "history", "arguments", new String[]{"-1", "1", "false"}),
                fields("holds", ArrayStores.history(-1, 1, false)), fields());
        row(3, fields("entry", "history", "arguments", new String[]{"-1", "1", "true"}),
                fields("holds", ArrayStores.history(-1, 1, true)), fields());
        row(4, fields("entry", "history", "arguments", new String[]{"-1", "2", "false"}),
                fields("holds", ArrayStores.history(-1, 2, false)), fields());
        row(5, fields("entry", "history", "arguments", new String[]{"-1", "2", "true"}),
                fields("holds", ArrayStores.history(-1, 2, true)), fields());
        row(6, fields("entry", "history", "arguments", new String[]{"0", "0", "false"}),
                fields("holds", ArrayStores.history(0, 0, false)), fields());
        row(7, fields("entry", "history", "arguments", new String[]{"0", "0", "true"}),
                fields("holds", ArrayStores.history(0, 0, true)), fields());
        row(8, fields("entry", "history", "arguments", new String[]{"0", "1", "false"}),
                fields("holds", ArrayStores.history(0, 1, false)), fields());
        row(9, fields("entry", "history", "arguments", new String[]{"0", "1", "true"}),
                fields("holds", ArrayStores.history(0, 1, true)), fields());
        row(10, fields("entry", "history", "arguments", new String[]{"0", "2", "false"}),
                fields("holds", ArrayStores.history(0, 2, false)), fields());
        row(11, fields("entry", "history", "arguments", new String[]{"0", "2", "true"}),
                fields("holds", ArrayStores.history(0, 2, true)), fields());
        row(12, fields("entry", "history", "arguments", new String[]{"1", "0", "false"}),
                fields("holds", ArrayStores.history(1, 0, false)), fields());
        row(13, fields("entry", "history", "arguments", new String[]{"1", "0", "true"}),
                fields("holds", ArrayStores.history(1, 0, true)), fields());
        row(14, fields("entry", "history", "arguments", new String[]{"1", "1", "false"}),
                fields("holds", ArrayStores.history(1, 1, false)), fields());
        row(15, fields("entry", "history", "arguments", new String[]{"1", "1", "true"}),
                fields("holds", ArrayStores.history(1, 1, true)), fields());
        row(16, fields("entry", "history", "arguments", new String[]{"1", "2", "false"}),
                fields("holds", ArrayStores.history(1, 2, false)), fields());
        row(17, fields("entry", "history", "arguments", new String[]{"1", "2", "true"}),
                fields("holds", ArrayStores.history(1, 2, true)), fields());
        row(18, fields("entry", "alwaysSucceeds", "arguments", new String[]{}),
                fields("holds", ArrayStores.alwaysSucceeds()), fields());
    }
}
