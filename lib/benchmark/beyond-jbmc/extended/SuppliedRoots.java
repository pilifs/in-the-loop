import org.apache.commons.lang3.ArrayUtils;

public final class SuppliedRoots {
    public static final class Flat { public int value; public Flat() {} }
    public static final class Node { public Node next; }
    public static class Base { public int score() { return 4; } }
    public static final class Nine extends Base { public int score() { return 9; } }
    public static final class Seven extends Base { public int score() { return 7; } }
    static Node[] self() {Node a=new Node();a.next=a;return new Node[]{a};}

    public static boolean planes(char[][][] data) {
        if (data==null || data.length!=2) return true;
        char[][] left=data[0],right=data[1];
        ArrayUtils.reverse((Object[])data);
        return data[0]==right && data[1]==left;
    }
    public static boolean conditional(Flat[] a,Flat[] b) {
        if (a==null || a.length!=2 || b==null || b.length==0) return true;
        Flat at=a[1],bt=b[0];
        ArrayUtils.reverse(a);
        return b[0]==(a==b?at:bt);
    }
    public static boolean unconditional(Flat[] a,Flat[] b) {
        if (a==null || a.length!=2 || b==null || b.length==0) return true;
        Flat first=b[0];
        ArrayUtils.reverse(a);
        return b[0]==first;
    }
    public static boolean scalar(Flat[] a,Flat b) {
        if (a==null || a.length==0 || a[0]==null || b==null) return true;
        int prior=b.value; ++a[0].value;
        return b.value==(a[0]==b?prior+1:prior);
    }
    public static boolean dispatch(Base[] a) {
        if (a==null || a.length==0 || a[0]==null) return true;
        Base x=a[0];
        return x.score()==(x instanceof Nine?9:x instanceof Seven?7:4);
    }
    public static boolean noSelf(Node[] a) {
        return a==null || a.length==0 || a[0]==null || a[0].next!=a[0];
    }
}
