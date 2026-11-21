package organic;

import java.nio.ByteBuffer;
import org.apache.avro.hadoop.io.AvroDatumConverterFactory;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static Object read(ByteBuffer buffer, int i) {
        try {
            return (int) buffer.get(i);
        } catch (IndexOutOfBoundsException expected) {
            return expected.getClass().getName();
        }
    }

    public static void main(String[] args) {
        for (int code = 0; code < 21; code++) {
            int n = WritableBuffer.capacity(code), length = WritableBuffer.length(code);
            ByteBuffer b = WritableBuffer.converted(code);
            int[] bounds = {b.position(), b.limit(), b.capacity(), b.remaining()};
            int[][] prefix = new int[length][2];
            for (int i = 0; i < length; i++) { prefix[i][0] = b.get(i); prefix[i][1] = b.position(); }
            Object first = read(b, length);
            ByteBuffer direct = new AvroDatumConverterFactory.BytesWritableConverter().convert(WritableBuffer.input(n, length));
            Object nested = fields("limit", direct.limit(), "capacity", direct.capacity(),
                                   "first", read(direct, length), "position", direct.position());
            row(code, fields("capacity", n, "length", length),
                fields("bounds", bounds, "prefix", prefix, "rejected", fields("first", first, "position", b.position()),
                       "directLimit", nested),
                fields("bounds", WritableBuffer.bounds(code), "prefix", WritableBuffer.prefix(code),
                       "rejected", WritableBuffer.rejected(code), "directLimit", WritableBuffer.directLimit(code)));
        }
    }
}
