package tiling;

public final class Ways {
    public static int tiles(int n) {
        int a=1,b=1;
        for(int i=2;i<=n;i++) {int next=a+b;a=b;b=next;}
        return n==0?a:b;
    }
}
