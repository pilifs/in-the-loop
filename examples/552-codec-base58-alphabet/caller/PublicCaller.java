import org.apache.commons.codec.binary.Base58;

import java.nio.charset.StandardCharsets;
import java.util.*;

public class PublicCaller {
    static Base58 codec(boolean swapped) {
        if (!swapped) return new Base58();
        byte[] table =
                "213456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
                        .getBytes(StandardCharsets.US_ASCII);
        return Base58.builder().setEncodeTable(table).get();
    }

    public static String observe(String[] a) throws Exception {
        boolean swapped = !a[0].equals("control"), carry = a[0].equals("challenge");
        byte[] input = carry ? new byte[] {0, 58} : new byte[] {0, 0, 1};
        String literal = carry ? "212" : swapped ? "221" : "112";
        String wire = new String(codec(swapped).encode(input), StandardCharsets.US_ASCII);
        return "wire="
                + wire
                + ",decoded="
                + Arrays.toString(
                        codec(swapped).decode(literal.getBytes(StandardCharsets.US_ASCII)));
    }
}
