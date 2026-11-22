package foundation;

import com.fasterxml.jackson.core.io.CharTypes;
import java.security.MessageDigest;
import java.util.HexFormat;

public final class JacksonHex {
    public static boolean ascii(int unit) {
        int expected = unit >= '0' && unit <= '9' ? unit - '0'
            : unit >= 'A' && unit <= 'F' ? unit - 'A' + 10
            : unit >= 'a' && unit <= 'f' ? unit - 'a' + 10 : -1;
        return CharTypes.charToHex(unit) == expected;
    }

    public static int upperByte() { return CharTypes.charToHex(0x141); }

    public static void main(String[] args) throws Exception {
        for (int i = 0; i < 128; i++) if (!ascii(i)) throw new AssertionError(i);
        if (upperByte() != Integer.parseInt(args[0])) throw new AssertionError("upper byte");
        try (var stream = CharTypes.class.getResourceAsStream("CharTypes.class")) {
            System.out.println(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes())));
        }
    }
}
