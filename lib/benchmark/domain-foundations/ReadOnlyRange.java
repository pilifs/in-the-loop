package foundation;
import java.nio.ByteBuffer;
import java.nio.ReadOnlyBufferException;

public final class ReadOnlyRange {
    public static int readOnly(byte[] bytes, int start, int length) {
        ByteBuffer original = ByteBuffer.wrap(bytes, start, length);
        ByteBuffer read = original.asReadOnlyBuffer();
        if (read == original || !read.isReadOnly() || read.hasArray() || read.capacity() != bytes.length
                || read.position() != start || read.limit() != start + length) return 0;
        if (length != 0) {
            bytes[start] ^= 1;
            if (read.get(start) != bytes[start]) return 0;
        }
        byte[] copied = new byte[length];
        read.get(copied, 0, length);
        for (int i = 0; i < length; i++) if (copied[i] != bytes[start+i]) return 0;
        try {
            read.put((byte) 7);
            return 0;
        } catch (ReadOnlyBufferException expected) {
            return read.position() == start+length && original.position() == start ? 1 : 0;
        }
    }
}
