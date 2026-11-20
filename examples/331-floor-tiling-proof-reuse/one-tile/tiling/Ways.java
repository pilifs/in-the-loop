package tiling;

public final class Ways {
    public static int tiles(int n) {
        if (n==0 || n==1)return 1;
        return tiles(n-1);
    }
}
