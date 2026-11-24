import org.apache.commons.codec.digest.MurmurHash3;
public final class CodecPublic {
    public static long[] historic(byte[] input,int off,int length,int seed) {
        return MurmurHash3.hash128(input,off,length,seed);
    }
    public static int hash32(byte[] input,int off,int length,int seed) {
        return MurmurHash3.hash32(input,off,length,seed);
    }
}
