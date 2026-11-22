package campaign;
import java.nio.BufferUnderflowException;
import java.nio.ByteBuffer;

/** The read-only view immediately below Variant.getBinary, including its original nonzero position. */
public final class ReadOnlyChild {
    public static int child(byte[] bytes, int start, int length, int index) {
        ByteBuffer source = ByteBuffer.wrap(bytes).asReadOnlyBuffer();
        source.position(start - 5);
        source.limit(bytes.length - 1);
        ByteBuffer view = source.duplicate();
        view.position(start);
        view.limit(start + length);
        if (view == source || !view.isReadOnly() || view.hasArray() || view.capacity() != bytes.length
                || view.position() != start || view.limit() != start + length || view.remaining() != length)
            return 0;
        if (length != 0) {
            int absolute = start + index;
            if (view.get(absolute) != bytes[absolute]) return 0;
            bytes[absolute] ^= 1;
            if (view.get(absolute) != bytes[absolute]) return 0;
            view.position(start + length - 1);
            if (view.get() != bytes[start + length - 1]) return 0;
        }
        try {
            view.get();
            return 0;
        } catch (BufferUnderflowException expected) {
            return source.position() == start - 5 && source.limit() == bytes.length - 1
                    && view.position() == start + length ? 1 : 0;
        }
    }
}
