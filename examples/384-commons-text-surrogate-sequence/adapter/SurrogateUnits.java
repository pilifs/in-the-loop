import java.io.IOException;
import java.io.Writer;
import org.apache.commons.text.translate.UnicodeUnpairedSurrogateRemover;

public final class SurrogateUnits {
    static final class Two implements CharSequence {
        final char a, b;
        Two(char a, char b) { this.a = a; this.b = b; }
        public int length() { return 2; }
        public char charAt(int i) {
            if (i == 0) return a;
            if (i == 1) return b;
            throw new IndexOutOfBoundsException();
        }
        public CharSequence subSequence(int start, int end) { throw new UnsupportedOperationException(); }
    }
    static final class Recording extends Writer {
        int units;
        public void write(char[] c, int off, int length) { units += length; }
        public void write(int ch) { units++; }
        public void flush() {}
        public void close() {}
    }
    static boolean surrogate(char c) { return c >= 0xD800 && c <= 0xDFFF; }
    static int count(char a, char b, boolean second, Recording writer) throws IOException {
        return new UnicodeUnpairedSurrogateRemover().translate(new Two(a, b), second ? 1 : 0, writer);
    }
    public static boolean translate(char a, char b, boolean second) throws IOException {
        boolean pair = a >= 0xD800 && a <= 0xDBFF && b >= 0xDC00 && b <= 0xDFFF;
        boolean remove = second ? surrogate(b) : surrogate(a) && !pair;
        Recording writer = new Recording();
        return count(a, b, second, writer) == (remove ? 1 : 0) && writer.units == 0;
    }
    public static boolean removeEvery(char a, char b) throws IOException {
        return count(a, b, false, new Recording()) == (surrogate(a) ? 1 : 0);
    }
}
