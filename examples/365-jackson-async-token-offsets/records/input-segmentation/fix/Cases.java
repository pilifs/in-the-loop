package campaign;
import java.util.Arrays;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        long[] reference = DirectTokens.trace(0, 0);
        if (!DirectTokens.correctOffsets(reference)) throw new AssertionError("unwindowed reference");
        for (int code = 0; code < 128; code++) {
            long[] t = DirectTokens.trace(code & 31, code >> 5);
            row(code, fields("cuts", code & 31, "padding", code >> 5),
                fields("offsets", fields("trace", t, "matchesUnpadded", Arrays.equals(t, reference)),
                       "tokens", new long[]{t[0], t[3], t[6], t[9], t[10]}),
                fields("offsets", DirectTokens.offsets(code), "tokens", DirectTokens.tokens(code)));
        }
    }
}
