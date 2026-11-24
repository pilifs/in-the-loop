import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;
import java.nio.ByteOrder;

/** Exercise both orders and the exact signature-polymorphic descriptors. */
public final class ViewChecks {
    private static final VarHandle BE = MethodHandles.byteArrayViewVarHandle(short[].class, ByteOrder.BIG_ENDIAN);
    private static final VarHandle LE = MethodHandles.byteArrayViewVarHandle(char[].class, ByteOrder.LITTLE_ENDIAN);
    private static final VarHandle LONG = MethodHandles.byteArrayViewVarHandle(long[].class, ByteOrder.LITTLE_ENDIAN);

    public static boolean signed(short value) {
        byte[] b = {11, 0, 0, 22};
        BE.set(b, 1, value);
        return b[0] == 11 && b[1] == (byte)(value >> 8) && b[2] == (byte)value && b[3] == 22
                && (short)BE.get(b, 1) == value && (char)LE.get(b, 1) == (char)Short.reverseBytes(value);
    }

    public static boolean bounds(int offset, long value) {
        byte[] b = {1, 2, 3, 4, 5, 6, 7, 8};
        try {
            LONG.set(b, offset, value);
            return offset == 0 && (long)LONG.get(b, offset) == value && b[0] == (byte)value && b[7] == (byte)(value >>> 56);
        } catch (ArrayIndexOutOfBoundsException expected) {
            if (offset == 0) return false;
            for (int i = 0; i < 8; ++i) if (b[i] != i+1) return false;
            return true;
        }
    }

    public static boolean opaqueIdentity() {
        return BE == MethodHandles.byteArrayViewVarHandle(short[].class, ByteOrder.BIG_ENDIAN);
    }

    public static boolean atomic(long value) {
        byte[] b = new byte[8];
        return LONG.compareAndSet(b, 0, 0L, value);
    }

    public static void main(String[] args) {
        for (short s : new short[]{0, 1, -1, 0x1234, Short.MIN_VALUE}) if (!signed(s)) throw new AssertionError();
        for (int i : new int[]{Integer.MIN_VALUE, -1, 0, 1, 8, Integer.MAX_VALUE})
            if (!bounds(i, 0x123456789abcdef0L)) throw new AssertionError();
        for (long v : new long[]{0, -1, Long.MIN_VALUE, 0x123456789abcdef0L})
            if (!FarmFrame.littleEndian(v)) throw new AssertionError();
        if (FarmFrame.flipped(0x123456789abcdef0L) || !atomic(123)) throw new AssertionError();
        System.out.println("primitive and bounds controls passed; Guava agrees on four words and rejects the flipped oracle");
    }
}
