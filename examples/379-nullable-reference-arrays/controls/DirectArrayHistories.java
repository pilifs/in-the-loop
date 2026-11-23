/** Mutate the actual incoming Item[] and inspect its second cell after the write. */
public final class DirectArrayHistories {
    public static boolean tracksIdentity(ReferenceCells.Item[] values) {
        if (values == null || values.length != 2 || values[0] == null || values[1] == null) return true;
        int before = values[1].value;
        values[0].value++;
        return values[1].value == (values[0] == values[1] ? before + 1 : before);
    }

    private static boolean writesSecondAtMax(ReferenceCells.Item[] values, boolean expectWrite) {
        if (values == null || values.length != 2 || values[0] == null || values[1] == null) return true;
        if (values[0].value != Integer.MAX_VALUE || values[1].value != Integer.MAX_VALUE) return true;
        values[0].value++;
        return values[1].value == (expectWrite ? Integer.MIN_VALUE : Integer.MAX_VALUE);
    }

    public static boolean alwaysWritesSecond(ReferenceCells.Item[] values) {
        return writesSecondAtMax(values, true);
    }

    public static boolean neverWritesSecond(ReferenceCells.Item[] values) {
        return writesSecondAtMax(values, false);
    }
}

final class DirectCellsReplay {
    static ReferenceCells.Item[] pair(boolean shared, int initial) {
        ReferenceCells.Item first = new ReferenceCells.Item();
        ReferenceCells.Item second = shared ? first : new ReferenceCells.Item();
        first.value = second.value = initial;
        return new ReferenceCells.Item[]{first, second};
    }
}
