public final class RootShapes {
    public static final class Flat { int value; Flat(int n){value=n;} }
    static class Base { int score(){return 4;} }
    static final class Nine extends Base { int score(){return 9;} }
    static final class Seven extends Base { int score(){return 7;} }
    public static final class Node { public Node next; }
    public static boolean arrayRoots(int x,int y,boolean shared) {
        Flat one=new Flat(x),two=new Flat(y);
        Flat[] a={one,two},b=shared?a:new Flat[]{new Flat(x),new Flat(y)};
        Flat b0=b[0],b1=b[1];
        a[0]=two;a[1]=one;
        return b[0]==(shared?two:b0) && b[1]==(shared?one:b1) && b[0].value==(shared?y:x);
    }
    public static boolean unconditional(boolean shared) {
        Flat[] a={new Flat(4),new Flat(4)},b=shared?a:new Flat[]{new Flat(4),new Flat(4)};
        Flat orig=b[0],tmp=a[0];a[0]=a[1];a[1]=tmp;
        return b[0]==orig;
    }
    public static boolean scalarRoot(int initial,boolean shared) {
        Flat slot=new Flat(initial),scalar=shared?slot:new Flat(initial);Flat[] a={slot};
        a[0].value++;
        return a[0]==slot && (a[0]==scalar)==shared && a[0].value==initial+1 && scalar.value==(shared?initial+1:initial);
    }
    private static int override(int choice) {
        Base[] a={new Base(),new Nine(),new Seven()};
        return a[choice].score();
    }
    public static boolean mapping(int choice) { return choice<0 || choice>2 || override(choice)==(choice==0?4:choice==1?9:7); }
    public static boolean alwaysFour(int choice) { return choice<0 || choice>2 || override(choice)==4; }
    public static boolean linked(int shape) {
        if (shape<0 || shape>2) return true;
        Node a=new Node(),b=new Node();
        a.next=shape==0?null:shape==1?a:b;b.next=a;
        if (shape==0) return a.next==null;
        return a.next!=null && a.next.next==a && (a.next==a)==(shape==1);
    }
    public static boolean noSelf(int shape) {
        if (shape<0 || shape>2) return true;
        Node a=new Node(),b=new Node(); a.next=shape==0?null:shape==1?a:b;b.next=a;
        return a.next!=a;
    }
}
