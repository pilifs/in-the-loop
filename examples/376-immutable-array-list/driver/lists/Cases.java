import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "fromArray", "arguments", new String[]{"0"}),
                fields("holds", ListHistory.fromArray(0)), fields());
        row(1, fields("entry", "fromArray", "arguments", new String[]{"1"}),
                fields("holds", ListHistory.fromArray(1)), fields());
        row(2, fields("entry", "fromArray", "arguments", new String[]{"-1"}),
                fields("holds", ListHistory.fromArray(-1)), fields());
        row(3, fields("entry", "fromArray", "arguments", new String[]{"Integer.MIN_VALUE"}),
                fields("holds", ListHistory.fromArray(Integer.MIN_VALUE)), fields());
        row(4, fields("entry", "fromArray", "arguments", new String[]{"Integer.MAX_VALUE"}),
                fields("holds", ListHistory.fromArray(Integer.MAX_VALUE)), fields());
        row(5, fields("entry", "fromCollection", "arguments", new String[]{"0"}),
                fields("holds", ListHistory.fromCollection(0)), fields());
        row(6, fields("entry", "fromCollection", "arguments", new String[]{"1"}),
                fields("holds", ListHistory.fromCollection(1)), fields());
        row(7, fields("entry", "fromCollection", "arguments", new String[]{"-1"}),
                fields("holds", ListHistory.fromCollection(-1)), fields());
        row(8, fields("entry", "fromCollection", "arguments", new String[]{"Integer.MIN_VALUE"}),
                fields("holds", ListHistory.fromCollection(Integer.MIN_VALUE)), fields());
        row(9, fields("entry", "fromCollection", "arguments", new String[]{"Integer.MAX_VALUE"}),
                fields("holds", ListHistory.fromCollection(Integer.MAX_VALUE)), fields());
        row(10, fields("entry", "followsSlot", "arguments", new String[]{"0"}),
                fields("holds", ListHistory.followsSlot(0)), fields());
        row(11, fields("entry", "followsSlot", "arguments", new String[]{"1"}),
                fields("holds", ListHistory.followsSlot(1)), fields());
        row(12, fields("entry", "followsSlot", "arguments", new String[]{"-1"}),
                fields("holds", ListHistory.followsSlot(-1)), fields());
        row(13, fields("entry", "followsSlot", "arguments", new String[]{"Integer.MIN_VALUE"}),
                fields("holds", ListHistory.followsSlot(Integer.MIN_VALUE)), fields());
        row(14, fields("entry", "followsSlot", "arguments", new String[]{"Integer.MAX_VALUE"}),
                fields("holds", ListHistory.followsSlot(Integer.MAX_VALUE)), fields());
    }
}
