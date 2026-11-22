package datawork;

import javaslang.collection.List;

public final class MatrixReferences {
    // Each allocation is a distinct reference with the same value.
    public static final class Cell {
        @Override public boolean equals(Object other) { return other instanceof Cell; }
        @Override public int hashCode() { return 1; }
    }

    public static Object[] palette() {
        Object[] refs = new Object[8];
        for (int i = 1; i < refs.length; i++) refs[i] = new Cell();
        return refs;
    }

    public static Object[] select(Object[] refs, int choices) {
        Object[] cells = new Object[6];
        for (int i = 0; i < cells.length; i++) {
            cells[i] = refs[choices & 7];
            choices >>>= 3;
        }
        return cells;
    }

    public static List<List<Object>> matrix(Object[] cells, int height, int width) {
        List<List<Object>> result = List.empty();
        for (int r = height - 1; r >= 0; r--) {
            List<Object> row = List.empty();
            for (int c = width - 1; c >= 0; c--) row = row.prepend(cells[r * width + c]);
            result = result.prepend(row);
        }
        return result;
    }

    private static boolean matches(List<List<Object>> actual, Object[] cells, int height, int width, boolean transposed) {
        if (actual.length() != height) return false;
        int r = 0;
        for (List<Object> row : actual) {
            if (row.length() != width) return false;
            int c = 0;
            for (Object cell : row) {
                if (cell != cells[transposed ? c * height + r : r * width + c]) return false;
                c++;
            }
            r++;
        }
        return true;
    }

    public static int roundTrip(int choices, boolean wide) {
        int height = wide ? 2 : 3;
        int width = wide ? 3 : 2;
        Object[] cells = select(palette(), choices);
        List<List<Object>> input = matrix(cells, height, width);
        List<List<Object>> once = List.transpose(input);
        List<List<Object>> twice = List.transpose(once);
        return matches(once, cells, width, height, true)
                && matches(twice, cells, height, width, false)
                && matches(input, cells, height, width, false) ? 1 : 0;
    }

    public static List<List<Object>> edgeInput(int shape, Object cell) {
        List<List<Object>> empty = List.empty();
        List<Object> row = List.empty();
        if (shape == 0) return empty;
        if (shape == 1) return empty.prepend(row);
        if (shape == 2) return empty.prepend(row.prepend(cell));
        List<List<Object>> twoEmptyRows = empty.prepend(row).prepend(row);
        return shape == 3 ? twoEmptyRows : twoEmptyRows.prepend(row);
    }

    public static int boundaries(int shape, int choices) {
        Object cell = palette()[choices & 7];
        List<List<Object>> input = edgeInput(shape, cell);
        List<List<Object>> once = List.transpose(input);
        List<List<Object>> twice = List.transpose(once);
        if (shape < 3) {
            return once == input && twice == input && (shape != 2 || once.head().head() == cell) ? 1 : 0;
        }
        return input.length() == shape - 1 && once.isEmpty() && twice.isEmpty() ? 1 : 0;
    }
}
