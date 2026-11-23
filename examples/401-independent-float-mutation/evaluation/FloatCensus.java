import java.util.Random;
import org.apache.commons.lang3.mutable.MutableFloat;

public final class FloatCensus {
    static void check(int x,int y) {
        float a=Float.intBitsToFloat(x),b=Float.intBitsToFloat(y);
        if(!FloatHistory.exact(a,b)||!FloatHistory.adjacent(2*a,2*b)||!FloatHistory.rounded(a,b))
            throw new AssertionError(Integer.toHexString(x)+"/"+Integer.toHexString(y));
    }
    public static void main(String[] args) {
        int[] edges={0,1,2,3,0x3fffff,0x400000,0x7ffffd,0x7ffffe,0x7fffff};
        for(int a:edges)for(int b:edges)check(0x3f800000+a,0x3f800000+b);
        Random random=new Random(360366L);
        for(int i=0;i<100000;i++)check(0x3f800000|random.nextInt(1<<23),0x3f800000|random.nextInt(1<<23));
        float x=Float.intBitsToFloat(0x3f800001), y=1f;
        MutableFloat a=new MutableFloat(x),b=new MutableFloat(x+2f);a.subtract(y);b.subtract(y+2f);
        int r=Float.floatToRawIntBits(a.floatValue()),s=Float.floatToRawIntBits(b.floatValue());
        if(r!=0x34000000||s!=0||FloatHistory.translated(x,y))throw new AssertionError();
        System.out.printf("100081 pairs; x=3f800001 y=3f800000 original=%08x translated=%08x%n",r,s);
    }
}
