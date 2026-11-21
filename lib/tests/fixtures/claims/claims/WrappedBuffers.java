package claims;

import java.nio.ByteBuffer;

public class WrappedBuffers {
    public static boolean window(boolean narrow) {
        byte[] bytes = { 2, 4, 6, 8 };
        ByteBuffer buffer = ByteBuffer.wrap(bytes, 1, narrow ? 1 : 2);
        int limit = narrow ? 2 : 3;
        bytes[1] = 11;
        if (buffer.position() != 1 || buffer.limit() != limit || buffer.capacity() != 4
                || buffer.remaining() != limit - 1 || buffer.get(0) != 2 || buffer.get(1) != 11) return false;
        buffer.put(1, (byte) 13);
        if (bytes[1] != 13 || buffer.position() != 1) return false;
        try {
            buffer.get(limit);
            return false;
        } catch (IndexOutOfBoundsException out) {
            return out.getClass() == IndexOutOfBoundsException.class && out.getMessage() == null
                    && buffer.position() == 1;
        }
    }

    public static boolean whole() {
        byte[] bytes = { 7 };
        ByteBuffer b = ByteBuffer.wrap(bytes);
        if (b.get(0) != 7 || b.position() != 0 || b.limit() != 1) return false;
        try {
            b.get(-1);
            return false;
        } catch (IndexOutOfBoundsException expected) {
            return b.position() == 0;
        }
    }

    public static boolean invalid() {
        try {
            ByteBuffer.wrap(new byte[3], 2, 2);
            return false;
        } catch (IndexOutOfBoundsException expected) {
            return true;
        }
    }

    public static void main(String[] args) {
        if (!window(false) || !window(true) || !whole() || !invalid()) throw new AssertionError();
    }
}
