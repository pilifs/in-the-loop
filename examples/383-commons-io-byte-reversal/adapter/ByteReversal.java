import org.apache.commons.io.EndianUtils;

public final class ByteReversal {
    public static boolean reverseInt(int x) { return EndianUtils.swapInteger(x) == Integer.reverseBytes(x); }
    public static boolean reverseLong(long x) { return EndianUtils.swapLong(x) == Long.reverseBytes(x); }
    public static boolean rotateInt(int x) { return EndianUtils.swapInteger(x) == Integer.rotateLeft(x, 16); }
    public static boolean rotateLong(long x) { return EndianUtils.swapLong(x) == Long.rotateLeft(x, 32); }
}
