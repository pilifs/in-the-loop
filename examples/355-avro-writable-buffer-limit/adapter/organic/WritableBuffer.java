package organic;

import java.nio.ByteBuffer;
import org.apache.avro.hadoop.io.AvroDatumConverter;
import org.apache.avro.hadoop.io.AvroDatumConverterFactory;
import org.apache.hadoop.io.BytesWritable;
import org.apache.hadoop.mapred.JobConf;

public final class WritableBuffer {
    static int capacity(int code) {
        int n = 0;
        while (code > n) { code -= n + 1; n++; }
        return n;
    }

    static int length(int code) {
        int n = capacity(code);
        return code - n * (n + 1) / 2;
    }

    static BytesWritable input(int n, int length) {
        byte[] data = new byte[n];
        for (int i = 0; i < n; i++) data[i] = (byte) (i + 1);
        BytesWritable writable = new BytesWritable(data);
        writable.setSize(length);
        return writable;
    }

    static ByteBuffer converted(int code) {
        AvroDatumConverterFactory factory = new AvroDatumConverterFactory(new JobConf(false));
        AvroDatumConverter<BytesWritable, ByteBuffer> converter = factory.create(BytesWritable.class);
        return converter.convert(input(capacity(code), length(code)));
    }

    static boolean firstRejected(ByteBuffer buffer, int index) {
        try {
            buffer.get(index);
            return false;
        } catch (IndexOutOfBoundsException expected) {
            return true;
        }
    }

    public static int bounds(int code) {
        ByteBuffer buffer = converted(code);
        return buffer.position() == 0 && buffer.limit() == length(code) && buffer.remaining() == length(code)
            && buffer.capacity() == capacity(code) ? 1 : 0;
    }

    public static int prefix(int code) {
        ByteBuffer buffer = converted(code);
        for (int i = 0; i < length(code); i++) if (buffer.get(i) != i + 1 || buffer.position() != 0) return 0;
        return buffer.position() == 0 ? 1 : 0;
    }

    public static int rejected(int code) {
        ByteBuffer buffer = converted(code);
        return firstRejected(buffer, length(code)) && buffer.position() == 0 ? 1 : 0;
    }

    public static int directLimit(int code) {
        ByteBuffer buffer = new AvroDatumConverterFactory.BytesWritableConverter().convert(input(capacity(code), length(code)));
        return buffer.limit() == length(code) && buffer.capacity() == capacity(code)
            && firstRejected(buffer, length(code)) && buffer.position() == 0 ? 1 : 0;
    }
}
