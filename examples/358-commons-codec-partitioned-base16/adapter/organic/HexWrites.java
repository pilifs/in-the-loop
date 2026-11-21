package organic;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import org.apache.commons.codec.binary.Base16OutputStream;

public final class HexWrites {
    static int nibble(int twoBits) {
        switch (twoBits & 3) {
            case 0: return 0;
            case 1: return 1;
            case 2: return 10;
            default: return 15;
        }
    }

    static int digit(int nibble) { return nibble < 10 ? '0' + nibble : 'A' + nibble - 10; }

    static byte[] input(int code) {
        if (code >= 2048) return new byte[]{'4','1','4','2','4','3','4','4','4','5'};
        int word = code / 8;
        return new byte[]{(byte) digit(nibble(word >> 6)), (byte) digit(nibble(word >> 4)),
                          (byte) digit(nibble(word >> 2)), (byte) digit(nibble(word))};
    }

    // Bit i means that a write ends immediately after character i.
    static int cuts(int code) {
        if (code < 2048) return code & 7;
        if (code == 2048) return (1 << 2) | (1 << 6);
        if (code == 2049) return 0;
        return (1 << 1) | (1 << 5);
    }

    static byte[] decode(byte[] text, int cuts) throws IOException {
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        try (Base16OutputStream out = new Base16OutputStream(sink, false)) {
            int offset = 0;
            for (int end = 1; end <= text.length; end++) {
                if (end == text.length || (cuts & (1 << (end - 1))) != 0) {
                    out.write(text, offset, end - offset);
                    offset = end;
                }
            }
        }
        return sink.toByteArray();
    }

    public static int bytes(int code) throws IOException {
        byte[] result = decode(input(code), cuts(code));
        if (code >= 2048) {
            if (result.length != 5) return 0;
            for (int i = 0; i < 5; i++) if ((result[i] & 255) != 'A' + i) return 0;
            return 1;
        }
        int word = code / 8;
        int first = 16 * nibble(word >> 6) + nibble(word >> 4);
        int second = 16 * nibble(word >> 2) + nibble(word);
        return result.length == 2 && (result[0] & 255) == first && (result[1] & 255) == second ? 1 : 0;
    }
}
