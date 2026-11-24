import org.apache.commons.lang3.mutable.MutableFloat;

public final class FloatHistory {
    static boolean within(float x,float lo,float hi) { return x>=lo && x<hi; }
    static boolean subtract(MutableFloat receiver,float y,float lo,float hi) {
        float x=receiver.floatValue();
        if (!within(x,lo,hi) || !within(y,lo,hi)) return true;
        receiver.subtract(y);
        return (double)receiver.floatValue() == (double)x - (double)y;
    }
    public static boolean exactOn(MutableFloat receiver,float y) { return subtract(receiver,y,1f,2f); }
    public static boolean exact(float x,float y) { return exactOn(new MutableFloat(x),y); }
    public static boolean adjacent(float x,float y) { return subtract(new MutableFloat(x),y,2f,4f); }
    public static boolean translated(float x,float y) {
        if (!within(x,1f,2f) || !within(y,1f,2f)) return true;
        MutableFloat a=new MutableFloat(x), b=new MutableFloat(x+2f);
        a.subtract(y); b.subtract(y+2f);
        return a.floatValue()==b.floatValue();
    }
    public static boolean rounded(float x,float y) {
        if (!within(x,1f,2f) || !within(y,1f,2f)) return true;
        MutableFloat r=new MutableFloat(x); r.add(y);
        return r.floatValue()==(float)((double)x+(double)y);
    }
    public static boolean afterReturn(float x,float y) {
        if (!within(x,1f,2f) || !within(y,1f,2f)) return true;
        MutableFloat r=new MutableFloat(x); r.subtract(y); r.floatValue(); return false;
    }
}
