import java.io.IOException;

public final class QuotedPartition {
    public static boolean partition(int ordinal, int kind) throws IOException {
        if (ordinal<0 || ordinal>11110 || kind<0 || kind>3) return true;
        String s=JacksonNumbers.input(ordinal);
        long[] old=before.DatabindAPI.read(s,kind), current=DatabindAPI.read(s,kind);
        if (!JacksonNumbers.trailing(s)) {
            for (int i=0; i<4; ++i) if (old[i]!=current[i]) return false;
            return true;
        }
        boolean negative=s.charAt(0)=='-';
        int start=negative || s.charAt(0)=='+' ? 1 : 0;
        int magnitude=0;
        for (int i=start; i<s.length()-1; i++) magnitude=10*magnitude+(s.charAt(i)-'0');
        double d=negative ? -(double)magnitude : (double)magnitude;
        long value=kind==1 ? (long)Float.floatToRawIntBits((float)d)
                : kind==2 ? (long)(negative ? -magnitude : magnitude) : Double.doubleToRawLongBits(d);
        return old[0]==1 && current[0]==0 && current[1]==(kind==3?0:kind)
                && current[2]==value && current[3]==0;
    }
}
