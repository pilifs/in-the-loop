package bom;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import org.apache.commons.io.ByteOrderMark;
import org.apache.commons.io.input.BOMInputStream;

public final class Projection {
    static byte[] payload(int id) {
        if (id == 0) return new byte[0];
        if (id == 1) return new byte[]{65};
        return new byte[]{97, 44, 98, 10, 99, 44, 100, 10};
    }

    static byte[] prefixed(byte[] bytes, boolean bom) {
        if (!bom) return bytes;
        byte[] result = new byte[bytes.length + 3];
        result[0] = (byte) 239;
        result[1] = (byte) 187;
        result[2] = (byte) 191;
        System.arraycopy(bytes, 0, result, 3, bytes.length);
        return result;
    }

    static BOMInputStream open(int code) throws IOException {
        boolean bom = (code / 6) % 2 != 0;
        boolean include = (code / 3) % 2 != 0;
        ByteArrayInputStream delegate = new ByteArrayInputStream(prefixed(payload(code / 12), bom));
        BOMInputStream input = BOMInputStream.builder().setInputStream(delegate)
                .setByteOrderMarks(ByteOrderMark.UTF_8).setInclude(include).get();
        int mode = code % 3;
        if (mode == 2) input.mark(32);
        if (mode != 0) {
            input.read();
            input.reset();
        }
        return input;
    }

    public static int bytes(int code) throws IOException {
        try (BOMInputStream input = open(code)) {
            byte[] expected = prefixed(payload(code / 12), (code / 6) % 2 != 0 && (code / 3) % 2 != 0);
            for (byte value : expected) if (input.read() != (value & 255)) return 0;
            return input.read() == -1 ? 1 : 0;
        }
    }

    public static int eof(int code) throws IOException {
        try (BOMInputStream input = open(code)) {
            while (input.read() != -1) { }
            return input.read() == -1 ? 1 : 0;
        }
    }
}
