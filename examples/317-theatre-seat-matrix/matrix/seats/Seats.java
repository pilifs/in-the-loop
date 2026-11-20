package seats;

public final class Seats {
    public static int[][] mark(int rows, int cols, int y, int x) {
        int[][] a = new int[rows][cols];
        a[y][x] = 1;
        return a;
    }
}
