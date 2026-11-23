import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "small", "arguments", new String[]{"-1", "true"}),
                fields("holds", OffsetPrefix.small(-1, true)), fields());
        row(1, fields("entry", "small", "arguments", new String[]{"-1", "false"}),
                fields("holds", OffsetPrefix.small(-1, false)), fields());
        row(2, fields("entry", "small", "arguments", new String[]{"0", "true"}),
                fields("holds", OffsetPrefix.small(0, true)), fields());
        row(3, fields("entry", "small", "arguments", new String[]{"0", "false"}),
                fields("holds", OffsetPrefix.small(0, false)), fields());
        row(4, fields("entry", "small", "arguments", new String[]{"1", "true"}),
                fields("holds", OffsetPrefix.small(1, true)), fields());
        row(5, fields("entry", "small", "arguments", new String[]{"1", "false"}),
                fields("holds", OffsetPrefix.small(1, false)), fields());
        row(6, fields("entry", "small", "arguments", new String[]{"2", "true"}),
                fields("holds", OffsetPrefix.small(2, true)), fields());
        row(7, fields("entry", "small", "arguments", new String[]{"2", "false"}),
                fields("holds", OffsetPrefix.small(2, false)), fields());
        row(8, fields("entry", "small", "arguments", new String[]{"3", "true"}),
                fields("holds", OffsetPrefix.small(3, true)), fields());
        row(9, fields("entry", "small", "arguments", new String[]{"3", "false"}),
                fields("holds", OffsetPrefix.small(3, false)), fields());
        row(10, fields("entry", "small", "arguments", new String[]{"4", "true"}),
                fields("holds", OffsetPrefix.small(4, true)), fields());
        row(11, fields("entry", "small", "arguments", new String[]{"4", "false"}),
                fields("holds", OffsetPrefix.small(4, false)), fields());
        row(12, fields("entry", "small", "arguments", new String[]{"5", "true"}),
                fields("holds", OffsetPrefix.small(5, true)), fields());
        row(13, fields("entry", "small", "arguments", new String[]{"5", "false"}),
                fields("holds", OffsetPrefix.small(5, false)), fields());
        row(14, fields("entry", "small", "arguments", new String[]{"6", "true"}),
                fields("holds", OffsetPrefix.small(6, true)), fields());
        row(15, fields("entry", "small", "arguments", new String[]{"6", "false"}),
                fields("holds", OffsetPrefix.small(6, false)), fields());
        row(16, fields("entry", "beforeEnd", "arguments", new String[]{"-1"}),
                fields("holds", OffsetPrefix.beforeEnd(-1)), fields());
        row(17, fields("entry", "beforeEnd", "arguments", new String[]{"0"}),
                fields("holds", OffsetPrefix.beforeEnd(0)), fields());
        row(18, fields("entry", "beforeEnd", "arguments", new String[]{"4"}),
                fields("holds", OffsetPrefix.beforeEnd(4)), fields());
        row(19, fields("entry", "beforeEnd", "arguments", new String[]{"6"}),
                fields("holds", OffsetPrefix.beforeEnd(6)), fields());
        row(20, fields("entry", "beforeEnd", "arguments", new String[]{"5"}),
                fields("holds", OffsetPrefix.beforeEnd(5)), fields());
        row(21, fields("entry", "wide", "arguments", new String[]{"\"abab\"", "\"\"", "4"}),
                fields("holds", OffsetPrefix.wide("abab", "", 4)), fields());
        row(22, fields("entry", "wide", "arguments", new String[]{"\"abab\"", "\"ba\"", "1"}),
                fields("holds", OffsetPrefix.wide("abab", "ba", 1)), fields());
        row(23, fields("entry", "wide", "arguments", new String[]{"\"a\"", "\"a\"", "Integer.MIN_VALUE"}),
                fields("holds", OffsetPrefix.wide("a", "a", Integer.MIN_VALUE)), fields());
        row(24, fields("entry", "wide", "arguments", new String[]{"\"a\"", "\"\"", "Integer.MAX_VALUE"}),
                fields("holds", OffsetPrefix.wide("a", "", Integer.MAX_VALUE)), fields());
        row(25, fields("entry", "wide", "arguments", new String[]{"\"a\"", "new String(\"a\")", "0"}),
                fields("holds", OffsetPrefix.wide("a", new String("a"), 0)), fields());
        row(26, fields("entry", "wide", "arguments", new String[]{"\"\\uD800\"", "\"\\uD800\"", "0"}),
                fields("holds", OffsetPrefix.wide("\uD800", "\uD800", 0)), fields());
        row(27, fields("entry", "wide", "arguments", new String[]{"\"\\uDBFF\\uDFFF\"", "\"\\uDFFF\"", "1"}),
                fields("holds", OffsetPrefix.wide("\uDBFF\uDFFF", "\uDFFF", 1)), fields());
        row(28, fields("entry", "nullPrefix", "arguments", new String[]{"0"}),
                fields("holds", OffsetPrefix.nullPrefix(0)), fields());
        row(29, fields("entry", "nullPrefix", "arguments", new String[]{"5"}),
                fields("holds", OffsetPrefix.nullPrefix(5)), fields());
    }
}
