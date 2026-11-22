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

    public static boolean duplicate(boolean marked) {
        byte[] bytes = {9, 2, 3, 8};
        ByteBuffer original = ByteBuffer.wrap(bytes, 1, 2);
        if (marked) original.mark();
        ByteBuffer copy = original.duplicate();
        if (copy == original || copy.array() != bytes || copy.capacity() != 4 || copy.limit() != 3) return false;
        byte[] result = new byte[2];
        copy.get(result);
        if (result[0] != 2 || result[1] != 3 || original.position() != 1 || copy.position() != 3) return false;
        copy.put(1, (byte) 7);
        if (original.get(1) != 7 || bytes[1] != 7) return false;
        if (marked) {
            copy.reset();
            if (copy.position() != 1) return false;
        }
        return true;
    }

    public static boolean wrongSharedCursor() {
        ByteBuffer original = ByteBuffer.wrap(new byte[]{3, 7});
        original.duplicate().get();
        return original.position() == 1;
    }

    public static boolean readOnly(byte value) {
        byte[] backing = {1, 2, 3, 4};
        ByteBuffer original = ByteBuffer.wrap(backing, 1, 2);
        original.mark();
        ByteBuffer view = original.asReadOnlyBuffer();
        ByteBuffer copy = view.duplicate();
        backing[1] = value;
        if (view == original || copy == view || !copy.isReadOnly() || copy.hasArray()
                || copy.capacity() != 4 || copy.limit() != 3 || copy.get() != value
                || original.position() != 1 || view.position() != 1) return false;
        copy.reset();
        try {
            copy.put((byte) 7);
            return false;
        } catch (java.nio.ReadOnlyBufferException expected) {
            return copy.position() == 1 && backing[1] == value;
        }
    }

    public static void main(String[] args) {
        if (!window(false) || !window(true) || !whole() || !invalid() || !duplicate(false) || !duplicate(true)
                || !readOnly((byte) -17) || wrongSharedCursor()) throw new AssertionError();
    }
}
