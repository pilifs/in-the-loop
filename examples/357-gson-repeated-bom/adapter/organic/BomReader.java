package organic;

import com.google.gson.Strictness;
import com.google.gson.stream.JsonReader;
import java.io.IOException;
import java.io.Reader;
import java.io.StringReader;

public final class BomReader {
    static final class Limited extends Reader {
        private final StringReader source;
        private final int cap;
        private final int[] trace;
        private int calls;

        Limited(String text, int cap, int[] trace) {
            this.source = new StringReader(text);
            this.cap = cap;
            this.trace = trace;
        }

        @Override public int read(char[] buffer, int offset, int length) throws IOException {
            int count = source.read(buffer, offset, Math.min(length, cap));
            if (trace != null) trace[calls++] = count;
            return count;
        }

        @Override public void close() { source.close(); }
        int calls() { return calls; }
    }

    static String input(int marks) {
        return marks == 0 ? "foo" : marks == 1 ? "\ufefffoo" : "\ufeff\ufefffoo";
    }

    static int cap(int code) { return code % 3 == 0 ? 1 : code % 3 == 1 ? 2 : 100; }

    static String read(Reader source) throws IOException {
        JsonReader reader = new JsonReader(source);
        reader.setStrictness(Strictness.LENIENT);
        return reader.nextString();
    }

    public static int chunked(int code) throws IOException {
        int marks = code / 3;
        String value = read(new Limited(input(marks), cap(code), null));
        return value.equals(marks == 2 ? "\ufefffoo" : "foo") ? 1 : 0;
    }

    public static int plain(int code) throws IOException {
        int marks = code / 3;
        String value = read(new StringReader(input(marks)));
        return value.equals(marks == 2 ? "\ufefffoo" : "foo") ? 1 : 0;
    }
}
