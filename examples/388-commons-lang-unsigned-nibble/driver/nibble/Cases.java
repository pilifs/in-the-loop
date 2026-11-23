import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "nibble", "arguments", new String[]{"0", "0"}),
                fields("holds", UnsignedNibble.nibble(0, 0)), fields());
        row(1, fields("entry", "nibble", "arguments", new String[]{"0", "1"}),
                fields("holds", UnsignedNibble.nibble(0, 1)), fields());
        row(2, fields("entry", "nibble", "arguments", new String[]{"0", "-1"}),
                fields("holds", UnsignedNibble.nibble(0, -1)), fields());
        row(3, fields("entry", "nibble", "arguments", new String[]{"0", "3"}),
                fields("holds", UnsignedNibble.nibble(0, 3)), fields());
        row(4, fields("entry", "nibble", "arguments", new String[]{"0", "4"}),
                fields("holds", UnsignedNibble.nibble(0, 4)), fields());
        row(5, fields("entry", "nibble", "arguments", new String[]{"0", "Integer.MIN_VALUE"}),
                fields("holds", UnsignedNibble.nibble(0, Integer.MIN_VALUE)), fields());
        row(6, fields("entry", "nibble", "arguments", new String[]{"0", "Integer.MAX_VALUE"}),
                fields("holds", UnsignedNibble.nibble(0, Integer.MAX_VALUE)), fields());
        row(7, fields("entry", "nibble", "arguments", new String[]{"10", "0"}),
                fields("holds", UnsignedNibble.nibble(10, 0)), fields());
        row(8, fields("entry", "nibble", "arguments", new String[]{"10", "1"}),
                fields("holds", UnsignedNibble.nibble(10, 1)), fields());
        row(9, fields("entry", "nibble", "arguments", new String[]{"10", "-1"}),
                fields("holds", UnsignedNibble.nibble(10, -1)), fields());
        row(10, fields("entry", "nibble", "arguments", new String[]{"10", "3"}),
                fields("holds", UnsignedNibble.nibble(10, 3)), fields());
        row(11, fields("entry", "nibble", "arguments", new String[]{"10", "4"}),
                fields("holds", UnsignedNibble.nibble(10, 4)), fields());
        row(12, fields("entry", "nibble", "arguments", new String[]{"10", "Integer.MIN_VALUE"}),
                fields("holds", UnsignedNibble.nibble(10, Integer.MIN_VALUE)), fields());
        row(13, fields("entry", "nibble", "arguments", new String[]{"10", "Integer.MAX_VALUE"}),
                fields("holds", UnsignedNibble.nibble(10, Integer.MAX_VALUE)), fields());
        row(14, fields("entry", "nibble", "arguments", new String[]{"15", "0"}),
                fields("holds", UnsignedNibble.nibble(15, 0)), fields());
        row(15, fields("entry", "nibble", "arguments", new String[]{"15", "1"}),
                fields("holds", UnsignedNibble.nibble(15, 1)), fields());
        row(16, fields("entry", "nibble", "arguments", new String[]{"15", "-1"}),
                fields("holds", UnsignedNibble.nibble(15, -1)), fields());
        row(17, fields("entry", "nibble", "arguments", new String[]{"15", "3"}),
                fields("holds", UnsignedNibble.nibble(15, 3)), fields());
        row(18, fields("entry", "nibble", "arguments", new String[]{"15", "4"}),
                fields("holds", UnsignedNibble.nibble(15, 4)), fields());
        row(19, fields("entry", "nibble", "arguments", new String[]{"15", "Integer.MIN_VALUE"}),
                fields("holds", UnsignedNibble.nibble(15, Integer.MIN_VALUE)), fields());
        row(20, fields("entry", "nibble", "arguments", new String[]{"15", "Integer.MAX_VALUE"}),
                fields("holds", UnsignedNibble.nibble(15, Integer.MAX_VALUE)), fields());
        row(21, fields("entry", "left", "arguments", new String[]{"0"}),
                fields("holds", UnsignedNibble.left(0)), fields());
        row(22, fields("entry", "left", "arguments", new String[]{"10"}),
                fields("holds", UnsignedNibble.left(10)), fields());
        row(23, fields("entry", "acceptsNegative", "arguments", new String[]{}),
                fields("holds", UnsignedNibble.acceptsNegative()), fields());
    }
}
