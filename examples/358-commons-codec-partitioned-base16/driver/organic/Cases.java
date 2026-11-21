package organic;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws IOException {
        for (int code = 0; code < 2051; code++) {
            byte[] input = HexWrites.input(code);
            int cuts = HexWrites.cuts(code);
            List<Integer> lengths = new ArrayList<>();
            int from = 0;
            for (int i = 1; i <= input.length; i++) {
                if (i == input.length || (cuts & (1 << (i - 1))) != 0) {
                    lengths.add(i - from);
                    from = i;
                }
            }
            byte[] actual = HexWrites.decode(input, cuts);
            int[] unsigned = new int[actual.length];
            for (int i = 0; i < unsigned.length; i++) unsigned[i] = actual[i] & 255;
            row(code, fields("hex", new String(input, StandardCharsets.US_ASCII), "writes", lengths),
                fields("bytes", unsigned), fields("bytes", HexWrites.bytes(code)));
        }
    }
}
