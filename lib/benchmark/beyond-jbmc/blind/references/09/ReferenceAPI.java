import org.cactoos.scalar.Sticky;
public final class ReferenceAPI {
    public static long primary(int n) {
        final int[] calls={0};
        Sticky<Integer> scalar=new Sticky<>(()->n+(++calls[0]));
        try {int first=scalar.value();
            if (scalar.value()!=first || scalar.value()!=first) return -1;
            return ((long)calls[0]<<32)|(first&0xffffffffL);
        } catch(Exception e){throw new IllegalStateException(e);}
    }
    public static long control(int n) {
        int[] calls={0};
        Sticky<Integer> a=new Sticky<>(()->{++calls[0];return n;}), b=new Sticky<>(()->{++calls[0];return n;});
        try {return a.value()==n && b.value()==n && calls[0]==2?1:0;}
        catch(Exception e){throw new IllegalStateException(e);}
    }
}
