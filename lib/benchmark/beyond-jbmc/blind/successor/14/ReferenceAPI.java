import java.nio.ByteBuffer;
import com.googlecode.mp4parser.boxes.mp4.objectdescriptors.BitWriterBuffer;
import com.googlecode.mp4parser.boxes.mp4.objectdescriptors.BitReaderBuffer;

public final class ReferenceAPI {
    private static ByteBuffer write(int n) {
        ByteBuffer b = ByteBuffer.wrap(new byte[]{0x33, 0, 0x55});
        b.position(1);
        BitWriterBuffer w = new BitWriterBuffer(b);
        w.writeBits(n >>> 5, 3);
        w.writeBits(n & 31, 5);
        return b;
    }
    public static long primary(int n) {
        ByteBuffer b = write(n);
        if (b.position() != 2 || (b.get(1) & 255) != n) return -1;
        b.position(1);
        BitReaderBuffer r = new BitReaderBuffer(b);
        int v = (r.readBits(3) << 5) | r.readBits(5);
        return b.position() == 2 && r.getPosition() == 8 ? v : -2;
    }
    public static long control(int n) {
        ByteBuffer b = write(n);
        return b.get(0) == 0x33 && b.get(2) == 0x55 ? 1 : 0;
    }
}
