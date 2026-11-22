package organic;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import org.apache.avro.io.BufferedBinaryEncoder;
import org.apache.avro.io.EncoderFactory;

public final class EncoderWindow {
    static int start(int code) { return (code & 4) == 0 ? 0 : 2; }
    static int width(int code) {
        return switch (code & 3) { case 0 -> 0; case 1 -> 4; case 2 -> 16; default -> 17; };
    }
    static int capacity(int code) { return width(code) <= 4 ? 6 : 20; }
    static ByteBuffer window(int code) {
        byte[] data = new byte[capacity(code)];
        for (int i = 0; i < data.length; i++) data[i] = (byte) (3 + 7 * i);
        ByteBuffer view = ByteBuffer.wrap(data, start(code), width(code));
        return code < 8 ? view : view.asReadOnlyBuffer();
    }
    static BufferedBinaryEncoder encoder(ByteArrayOutputStream sink) {
        return (BufferedBinaryEncoder) new EncoderFactory().configureBufferSize(32).binaryEncoder(sink, null);
    }
    public static int cursor(int code) throws IOException {
        ByteBuffer view = window(code);
        BufferedBinaryEncoder enc = encoder(new ByteArrayOutputStream());
        enc.writeFixed(view);
        return view.position() == start(code) && view.limit() == start(code) + width(code) ? 1 : 0;
    }
    public static int repeated(int code) throws IOException {
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        BufferedBinaryEncoder enc = encoder(sink);
        ByteBuffer view = window(code);
        enc.writeFixed(view);
        enc.flush();
        enc.writeFixed(view);
        enc.flush();
        byte[] actual = sink.toByteArray();
        int length = width(code);
        if (actual.length != 2 * length) return 0;
        for (int i = 0; i < length; i++) {
            byte expected = (byte) (3 + 7 * (start(code) + i));
            if (actual[i] != expected || actual[length + i] != expected) return 0;
        }
        return 1;
    }
}
