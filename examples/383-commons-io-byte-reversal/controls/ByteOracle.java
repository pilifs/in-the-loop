import org.apache.commons.io.EndianUtils;

public final class ByteOracle {
    static void check(int i, long l) {
        if (EndianUtils.swapInteger(i) != Integer.reverseBytes(i) || EndianUtils.swapLong(l) != Long.reverseBytes(l))
            throw new AssertionError();
    }
    public static void main(String[] args) {
        for (int i = 0; i < 65536; i++) {
            int pattern = i << 16 | (i ^ 0xa55a);
            long wide = (long)pattern << 32 | Integer.toUnsignedLong(Integer.rotateLeft(pattern, 7) ^ 0x12345678);
            check(pattern, wide);
        }
        check(0, 0); check(1, 1); check(-1, -1);
        check(Integer.MIN_VALUE, Long.MIN_VALUE); check(Integer.MAX_VALUE, Long.MAX_VALUE);
        if (EndianUtils.swapInteger(1) == Integer.rotateLeft(1,16) || EndianUtils.swapLong(1) == Long.rotateLeft(1,32))
            throw new AssertionError();
        System.out.println("65536 patterned words and 5 boundaries per width; both rotations rejected at 1");
    }
}
