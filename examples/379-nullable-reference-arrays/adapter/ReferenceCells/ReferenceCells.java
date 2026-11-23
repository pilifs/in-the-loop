public final class ReferenceCells {
    public static final class Item { int value; }

    static int kind(Item[] values) {
        if (values == null) return -2;
        if (values.length == 0) return -1;
        return values[0] == null ? 0 : 1;
    }
    public static boolean categories(Item[] values) { int k = kind(values); return k >= -2 && k <= 1; }
    public static boolean noNullCell(Item[] values) { return kind(values) != 0; }
    public static boolean noItemCell(Item[] values) { return kind(values) != 1; }
    public static boolean followsAlias(boolean shared, int initial) {
        Item first = new Item();
        first.value = initial;
        Item second = shared ? first : new Item();
        second.value = initial;
        Item[] values = {first, second};
        values[0].value++;
        return values[1].value == (shared ? initial + 1 : initial);
    }
    public static boolean alwaysShares(boolean shared) {
        Item first = new Item();
        Item[] values = {first, shared ? first : new Item()};
        values[0].value = 1;
        return values[1].value == 1;
    }
}
