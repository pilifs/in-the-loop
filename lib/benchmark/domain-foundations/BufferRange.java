package foundation;
import java.nio.ByteBuffer;

/** The heap view returned to a caller of the selected JDK bytecode. */
public final class BufferRange {
    public static int wrap(byte[] bytes, int start, int length) {
        ByteBuffer view = ByteBuffer.wrap(bytes, start, length);
        return view.hasArray() && view.array() == bytes && view.arrayOffset() == 0 &&
            view.position() == start && view.limit() == start + length &&
            view.capacity() == bytes.length && view.remaining() == length ? 1 : 0;
    }
    public static int duplicate(byte[] bytes, int start, int length) {
        ByteBuffer view = ByteBuffer.wrap(bytes, start, length);
        ByteBuffer copy = view.duplicate();
        if (copy == view || copy.array() != bytes || copy.position() != start ||
            copy.limit() != start + length || copy.capacity() != bytes.length) return 0;
        byte[] result = new byte[length];
        copy.get(result);
        for (int i = 0; i < length; i++) if (result[i] != bytes[start + i]) return 0;
        return copy.position() == start + length && view.position() == start && view.limit() == start + length ? 1 : 0;
    }
}
