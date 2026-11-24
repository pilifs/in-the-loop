import com.google.common.hash.Hashing;

/** Published Guava API on an eight-byte little-endian encoding of any long. */
public final class FarmFrame {
    private static long reference(long word) {
        long k = 0x9ae16a3b2f90404fL;
        long mul = k + 16;
        long a = word + k;
        long c = Long.rotateRight(word, 37) * mul + a;
        long d = (Long.rotateRight(a, 25) + word) * mul;
        long h = (c ^ d) * mul;
        h ^= h >>> 47;
        h = (d ^ h) * mul;
        return (h ^ (h >>> 47)) * mul;
    }

    static long fingerprint(long word) {
        byte[] buf = new byte[8];
        for (int i = 0; i < 8; i++) buf[i] = (byte)(word >>> (8*i));
        return Hashing.farmHashFingerprint64().hashBytes(buf, 0, 8).asLong();
    }

    public static boolean littleEndian(long word) { return fingerprint(word) == reference(word); }
    public static boolean flipped(long word) { return fingerprint(word) == reference(Long.reverseBytes(word)); }
}
