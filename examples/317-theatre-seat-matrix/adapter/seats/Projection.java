package seats;

public final class Projection {
    private static int[] coordinate(int code) {
        for (int r = 1; r <= 3; r++) for (int c = 1; c <= 2; c++) {
            if (code < r * c) return new int[]{r, c, code / c, code % c};
            code -= r * c;
        }
        throw new IllegalArgumentException();
    }
    private static int[][] grid(int[] p) { return Seats.mark(p[0], p[1], p[2], p[3]); }
    public static int shape(int code) {
        int[] p = coordinate(code);
        int[][] a = grid(p);
        if (a.length != p[0]) return 0;
        for (int[] row : a) if (row.length != p[1]) return 0;
        return 1;
    }
    public static int cells(int code) {
        int[] p = coordinate(code);
        int[][] a = grid(p);
        if (a.length != p[0]) return 0;
        for (int i = 0; i < a.length; i++) {
            if (a[i].length != p[1]) return 0;
            for (int j = 0; j < a[i].length; j++) if (a[i][j] != (i == p[2] && j == p[3] ? 1 : 0)) return 0;
        }
        return 1;
    }
    public static int identity(int code) {
        int[][] a = grid(coordinate(code));
        for (int i = 0; i < a.length; i++) for (int j = 0; j < i; j++) if (a[i] == a[j]) return 0;
        return 1;
    }
}
