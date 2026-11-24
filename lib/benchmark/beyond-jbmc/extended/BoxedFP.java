import org.apache.commons.numbers.field.FP64;

public final class BoxedFP {
    private static FP64 value(long bits) { return FP64.of(Double.longBitsToDouble(bits)); }
    public static boolean zeroEquals() {
        FP64 x=value(0L),y=value(Long.MIN_VALUE);
        return x.equals(y) && y.equals(x) && x.compareTo(y)>0 && y.compareTo(x)<0
            && Double.doubleToRawLongBits(x.doubleValue())==0L && Double.doubleToRawLongBits(y.doubleValue())==Long.MIN_VALUE;
    }
    public static boolean zeroHashes() { return value(0L).hashCode()==value(Long.MIN_VALUE).hashCode(); }
    public static boolean nanEquality(long x,long y) {
        if (!nan(x) || !nan(y)) return true;
        FP64 a=value(x),b=value(y);
        return a.equals(b);
    }
    private static boolean nan(long v) { return (v & 0x7ff0000000000000L)==0x7ff0000000000000L && (v & 0xfffffffffffffL)!=0; }
    public static boolean nanOrder(long x,long y) {
        if (!nan(x) || !nan(y)) return true;
        FP64 a=value(x),b=value(y);
        return a.compareTo(b)==0 && a.hashCode()==b.hashCode()
            && Double.doubleToRawLongBits(a.doubleValue())==x && Double.doubleToRawLongBits(b.doubleValue())==y;
    }
}
