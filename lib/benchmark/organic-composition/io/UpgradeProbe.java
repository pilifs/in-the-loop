import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import org.apache.commons.io.input.CharSequenceInputStream;

public final class UpgradeProbe {
    private static final String HEX = "0123456789abcdef";

    private static String bytes(byte[] array) {
        StringBuilder encoded = new StringBuilder();
        for (byte value : array) {
            encoded.append(HEX.charAt((value & 255) >>> 4)).append(HEX.charAt(value & 15));
        }
        return encoded.toString();
    }

    // Negative operations rewind. Positive values encode destination offset * 10 + requested length.
    public static String observe(String[] args) throws IOException {
        Charset selected = args[1].equals("explicit") ? StandardCharsets.UTF_8 : null;
        int[] operations;
        String source = "Aé中Z";
        switch (args[0]) {
            case "two-resets": operations = new int[]{13,-1,13,-1,13,24,12,60}; break;
            case "after-eof": operations = new int[]{15,24,12,-1,15,24,12,-1,15,24,12,60}; break;
            case "once": operations = new int[]{13,-1,13,24,12,60}; break;
            case "short": source = "Aé"; operations = new int[]{24,-1,24,12,60}; break;
            default: throw new IllegalArgumentException("unregistered history");
        }
        CharSequenceInputStream stream = new CharSequenceInputStream(source, selected, 8);
        int prefix = stream.read();
        stream.mark(16);
        byte[] destination = {0x51, 0x62, 0x73, 0x14, 0x25, 0x36, 0x47};
        StringBuilder output = new StringBuilder().append(prefix);
        for (int op : operations) {
            if (op < 0) {
                stream.reset();
                output.append("/R");
            } else {
                int count = stream.read(destination, op / 10, op % 10);
                output.append('/').append(count).append('=').append(bytes(destination));
            }
        }
        return output.toString();
    }

    // Reach the identical original constructor before observer formatting or selector logic.
    public static boolean rewind() throws IOException {
        CharSequenceInputStream stream = new CharSequenceInputStream("Aé中Z", StandardCharsets.UTF_8, 8);
        stream.read();
        stream.mark(16);
        byte[] bytes = new byte[5];
        stream.read(bytes, 1, 3);
        stream.reset();
        stream.read(bytes, 1, 3);
        stream.reset();
        return stream.read(bytes, 1, 3) == 3 && bytes[1] == (byte)0xc3;
    }
}
