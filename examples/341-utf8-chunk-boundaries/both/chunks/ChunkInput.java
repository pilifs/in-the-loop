package chunks;

import java.io.InputStream;
import java.util.Arrays;

public final class ChunkInput extends InputStream {
    final byte[] bytes;
    final int cuts;
    int position;
    public ChunkInput(byte[] bytes, int cuts) { this.bytes = bytes; this.cuts = cuts; }
    public int read() { return position == bytes.length ? -1 : bytes[position++] & 255; }
    public int read(byte[] destination, int offset, int length) {
        java.util.Objects.checkFromIndexSize(offset, length, destination.length);
        if (length == 0) return 0;
        if (position == bytes.length) return -1;
        int end = position + 1;
        while (end < bytes.length && end - position < length && (cuts & (1 << (end - 1))) == 0) end++;
        int count = end - position;
        System.arraycopy(bytes, position, destination, offset, count);
        position = end;
        return count;
    }
}
