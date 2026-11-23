public final class RowIdentities {
    public static boolean nonNullOuter(int[][] rows) {
        return rows != null;
    }

    public static boolean noEmptyOuter(int[][] rows) {
        return rows == null || rows.length != 0;
    }

    public static boolean noDistinctEqualRows(int[][] rows) {
        if (rows == null || rows.length != 2) return true;
        int[] first = rows[0], second = rows[1];
        if (first == null || second == null || first == second) return true;
        return first.length != 1 || second.length != 1
            || first[0] != Integer.MIN_VALUE || second[0] != first[0];
    }
}
