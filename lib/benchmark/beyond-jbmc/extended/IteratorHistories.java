import org.roaringbitmap.*;

public final class IteratorHistories {
    static final int[] VALUES={10,20,30,65576,65586,65596};
    public static boolean forward(int steps) {
        if (steps<0 || steps>6) return true;
        RoaringBitmap bitmap=RoaringBitmap.bitmapOf(10,20,30,65576,65586,65596);
        IntIteratorFlyweight orig=new IntIteratorFlyweight(bitmap);
        PeekableIntIterator clone=orig.clone();
        for(int i=0;i<steps;i++) if (clone.next()!=VALUES[i]) return false;
        if (clone.hasNext()!=(steps<6) || steps<6 && clone.peekNext()!=VALUES[steps]) return false;
        for(int v:VALUES) if (!orig.hasNext() || orig.next()!=v) return false;
        return !orig.hasNext();
    }
    public static boolean reverse(int alternate) {
        if (alternate<0 || alternate>1) return true;
        RoaringBitmap bitmap=RoaringBitmap.bitmapOf(10,20,30,65576,65586,65596);
        ReverseIntIteratorFlyweight orig=new ReverseIntIteratorFlyweight(bitmap);
        PeekableIntIterator clone=orig.clone();
        try {
            for (int i=5;i>=0;--i) {
                if (!clone.hasNext() || clone.next()!=VALUES[i]) return false;
                if (alternate==1 && (!orig.hasNext() || orig.next()!=VALUES[i])) return false;
            }
            if (clone.hasNext()) return false;
            if (alternate==0) for (int i=5;i>=0;--i) if (!orig.hasNext() || orig.next()!=VALUES[i]) return false;
            return !orig.hasNext();
        } catch (ArrayIndexOutOfBoundsException e) { return false; }
    }
    public static boolean subset(int hole,int d) {
        if (hole<4 || hole>9997 || d<0 || d>2) return true;
        RoaringBitmap r=new RoaringBitmap(),query=new RoaringBitmap();
        for (int i=0;i<10000;++i) if (i!=hole) r.add(i);
        query.add((long)hole-4,hole+(long)d);
        return r.contains(query)==(d==0);
    }
    public static boolean interval(int hole,int d) {
        if (hole<4 || hole>9997 || d<0 || d>2) return true;
        RoaringBitmap r=new RoaringBitmap();
        r.add(0L,10000L); r.remove(hole);
        return r.contains(hole-4L,hole+(long)d)==(d==0);
    }
}
