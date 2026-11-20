package tiling;

public final class Floor {
    public static int exact(int n){return Ways.tiles(n);}
    public static int parity(int n){return Ways.tiles(n)&1;}
}
