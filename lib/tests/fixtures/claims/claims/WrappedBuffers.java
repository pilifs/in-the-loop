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

    public static boolean transfer(boolean backwards) {
        byte[] bytes = {10, 20, 30, 40};
        ByteBuffer destination = ByteBuffer.wrap(bytes);
        ByteBuffer source = destination.asReadOnlyBuffer();
        destination.position(backwards ? 0 : 1);
        source.position(backwards ? 1 : 0);
        source.limit(source.position() + 3);
        int destinationStart = destination.position();
        if (destination.put(source) != destination || source.hasRemaining()
                || destination.position() != destinationStart + 3) return false;
        if (backwards) return bytes[0] == 20 && bytes[1] == 30 && bytes[2] == 40 && bytes[3] == 40;
        return bytes[0] == 10 && bytes[1] == 10 && bytes[2] == 20 && bytes[3] == 30;
    }

    public static boolean indexedTransfer() {
        byte[] bytes = {1, 2, 3, 4};
        ByteBuffer dest = ByteBuffer.wrap(bytes, 1, 3).slice();
        ByteBuffer source = ByteBuffer.wrap(new byte[]{5, 6, 7}).asReadOnlyBuffer();
        dest.position(2);
        source.position(1);
        dest.put(1, source, 0, 2);
        return dest.position() == 2 && source.position() == 1
            && bytes[0] == 1 && bytes[1] == 2 && bytes[2] == 5 && bytes[3] == 6;
    }

    public static boolean rejectedTransfer() {
        ByteBuffer dst = ByteBuffer.wrap(new byte[]{8});
        ByteBuffer src = ByteBuffer.wrap(new byte[]{1, 2});
        try { dst.put(src); return false; } catch (java.nio.BufferOverflowException expected) { }
        try { dst.asReadOnlyBuffer().put(src); return false; }
        catch (java.nio.ReadOnlyBufferException expected) { }
        return dst.position() == 0 && src.position() == 0 && dst.get(0) == 8;
    }

    public static boolean wrongTransfer() {
        byte[] data = {1, 2, 3, 4};
        ByteBuffer.wrap(data, 1, 3).put(ByteBuffer.wrap(data, 0, 3));
        return data[3] == 1;
    }

    public static void main(String[] args) {
        if (!transfer(false) || !transfer(true) || !indexedTransfer() || !rejectedTransfer() || wrongTransfer()) throw new AssertionError();
        if (!window(false) || !window(true) || !whole() || !invalid() || !duplicate(false) || !duplicate(true)
                || !readOnly((byte) -17) || wrongSharedCursor()) throw new AssertionError();
    }
}
