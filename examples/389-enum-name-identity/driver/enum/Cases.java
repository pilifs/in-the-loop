import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "lookup", "arguments", new String[]{"0"}),
                fields("holds", EnumNames.lookup(0)), fields());
        row(1, fields("entry", "lookup", "arguments", new String[]{"1"}),
                fields("holds", EnumNames.lookup(1)), fields());
        row(2, fields("entry", "lookup", "arguments", new String[]{"2"}),
                fields("holds", EnumNames.lookup(2)), fields());
        row(3, fields("entry", "lookup", "arguments", new String[]{"3"}),
                fields("holds", EnumNames.lookup(3)), fields());
        row(4, fields("entry", "lookup", "arguments", new String[]{"4"}),
                fields("holds", EnumNames.lookup(4)), fields());
        row(5, fields("entry", "ordinal", "arguments", new String[]{"false"}),
                fields("holds", EnumNames.ordinal(false)), fields());
        row(6, fields("entry", "ordinal", "arguments", new String[]{"true"}),
                fields("holds", EnumNames.ordinal(true)), fields());
        row(7, fields("entry", "alwaysZero", "arguments", new String[]{"false"}),
                fields("holds", EnumNames.alwaysZero(false)), fields());
        row(8, fields("entry", "alwaysZero", "arguments", new String[]{"true"}),
                fields("holds", EnumNames.alwaysZero(true)), fields());
    }
}
