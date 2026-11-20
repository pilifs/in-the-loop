package seats;

public final class Seats {
    public static int[][] mark(int rows, int cols, int y, int x) {
        int[][] a = new int[rows][];
        int[] row = new int[cols];
        for (int i = 0; i < rows; i++) a[i] = row;
        a[y][x] = 1;
        return a;
    }
}
