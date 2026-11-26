import org.apache.commons.io.input.BoundedReader;

import java.io.StringReader;

public class MarkWindow {
    public static String observe(String[] args) throws Exception {
        int offset = Integer.parseInt(args[0]);
        var delegate = new StringReader("abcdefg");
        try (var reader = new BoundedReader(delegate, 6)) {
            for (int i = 0; i < offset; i++) {
                if (reader.read() != 'a' + i) throw new AssertionError("starting position");
            }
            reader.mark(2);
            var afterMark = new StringBuilder();
            int value;
            while ((value = reader.read()) != -1) afterMark.append((char) value);
            char next = (char) delegate.read();
            reader.reset();
            int first = reader.read();
            return "afterMark="
                    + afterMark
                    + ", delegate="
                    + next
                    + ", afterReset="
                    + (first == -1 ? "EOF" : Character.toString((char) first));
        }
    }
}
