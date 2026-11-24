import org.apache.commons.codec.digest.MurmurHash3;

public final class CachedCodec {
    public static boolean tail(byte value,int seed) {
        int k=Integer.rotateLeft(value*0xcc9e2d51,15)*0x1b873593;
        int h=(seed ^ k) ^ 1;
        h=(h ^ (h >>> 16))*0x85ebca6b;
        h=(h ^ (h >>> 13))*0xc2b2ae35;
        h^=h >>> 16;
        return MurmurHash3.hash32(new byte[]{value},0,1,seed)==h;
    }
    public static boolean empty128() {
        long[] value=MurmurHash3.hash128(new byte[0],0,0,-1);
        return value.length==2 && value[0]==0x6af1df4d9d3bc9ecL && value[1]==0x857421121ee6446bL;
    }
}
