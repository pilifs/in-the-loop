package datawork;

import javaslang.collection.List;

public final class Matrices {
    public static int[][] cells(int code) {
        int height = code == 0 ? 0 : code < 8 ? 1 : code < 57 ? 2 : 3;
        int n = code - (height == 3 ? 57 : height == 2 ? 8 : height);
        int[][] rows = new int[height][];
        for (int i = height - 1; i >= 0; i--) {
            int w = n % 7;
            n /= 7;
            rows[i] = w == 0 ? new int[0] : w <= 2 ? new int[]{w - 1} : new int[]{(w - 3) / 2, (w - 3) % 2};
        }
        return rows;
    }

    public static List<List<Integer>> list(int[][] rows) {
        List<List<Integer>> matrix = List.empty();
        for (int r = rows.length - 1; r >= 0; r--) {
            List<Integer> row = List.empty();
            for (int c = rows[r].length - 1; c >= 0; c--) row = row.prepend(rows[r][c]);
            matrix = matrix.prepend(row);
        }
        return matrix;
    }

    public static boolean rectangular(int[][] rows) {
        for (int r = 1; r < rows.length; r++) if (rows[r].length != rows[0].length) return false;
        return true;
    }

    public static int[][] observe(int[][] rows) {
        List<List<Integer>> output = List.transpose(list(rows));
        int[][] values = new int[output.length()][];
        int c = 0;
        for (List<Integer> column : output) {
            values[c] = new int[column.length()];
            int r = 0;
            for (int value : column) values[c][r++] = value;
            c++;
        }
        return values;
    }

    public static int contract(int code) {
        int[][] rows = cells(code);
        try {
            int[][] out = observe(rows);
            if (rows.length == 1 && rows[0].length == 0) return out.length == 1 && out[0].length == 0 ? 1 : 0;
            if (!rectangular(rows) || out.length != (rows.length == 0 ? 0 : rows[0].length)) return 0;
            for (int c = 0; c < out.length; c++) {
                if (out[c].length != rows.length) return 0;
                for (int r = 0; r < rows.length; r++) if (out[c][r] != rows[r][c]) return 0;
            }
            return 1;
        } catch (IllegalArgumentException rejected) {
            return !rectangular(rows) && rejected.getClass() == IllegalArgumentException.class ? 1 : 0;
        }
    }

    public static int rectangle(int code) {
        int[][] rows = cells(code);
        if (!rectangular(rows)) return 1;
        if (contract(code) == 0) return 0;
        List<List<Integer>> input = list(rows);
        return rows.length == 0 || rows[0].length == 0 || input.equals(List.transpose(List.transpose(input))) ? 1 : 0;
    }
}
