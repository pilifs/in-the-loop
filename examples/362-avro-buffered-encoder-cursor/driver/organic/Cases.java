package organic;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import org.apache.avro.io.BinaryEncoder;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        for (int code = 0; code < 16; code++) {
            ByteBuffer input = EncoderWindow.window(code);
            int start = input.position(), width = input.remaining();
            ByteArrayOutputStream sink = new ByteArrayOutputStream();
            BinaryEncoder encoder = EncoderWindow.encoder(sink);
            encoder.writeFixed(input);
            int[] cursor = {input.position(), input.limit()};
            encoder.flush();
            encoder.writeFixed(input);
            encoder.flush();
            byte[] raw = sink.toByteArray();
            int[] bytes = new int[raw.length];
            for (int i = 0; i < bytes.length; i++) bytes[i] = raw[i] & 255;
            row(code, fields("readOnly", input.isReadOnly(), "start", start, "width", width, "capacity", input.capacity()),
                fields("cursor", cursor, "repeated", bytes),
                fields("cursor", EncoderWindow.cursor(code), "repeated", EncoderWindow.repeated(code)));
        }
    }
}
