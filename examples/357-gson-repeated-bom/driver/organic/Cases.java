package organic;

import java.io.IOException;
import java.io.StringReader;
import java.util.Arrays;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static int[] units(String text) {
        int[] result = new int[text.length()];
        for (int i = 0; i < result.length; i++) result[i] = text.charAt(i);
        return result;
    }

    public static void main(String[] args) throws IOException {
        for (int code = 0; code < 9; code++) {
            int marks = code / 3, cap = BomReader.cap(code);
            String text = BomReader.input(marks);
            int[] reads = new int[16];
            BomReader.Limited source = new BomReader.Limited(text, cap, reads);
            String chunked = BomReader.read(source);
            System.err.println("marks=" + marks + " cap=" + cap + " reads=" + Arrays.toString(Arrays.copyOf(reads, source.calls())));
            row(code, fields("marks", marks, "cap", cap),
                fields("chunked", units(chunked), "plain", units(BomReader.read(new StringReader(text)))),
                fields("chunked", BomReader.chunked(code), "plain", BomReader.plain(code)));
        }
    }
}
