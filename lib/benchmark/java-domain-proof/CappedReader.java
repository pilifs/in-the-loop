package campaign;

import java.io.IOException;
import java.io.Reader;
import java.io.StringReader;
import java.util.Objects;

public final class CappedReader extends Reader {
    private final StringReader source;
    private final int cap;

    CappedReader(String text, int cap) {
        if (cap < 1) throw new IllegalArgumentException();
        this.source = new StringReader(text);
        this.cap = cap;
    }

    @Override public int read(char[] target, int start, int length) throws IOException {
        Objects.checkFromIndexSize(start, length, target.length);
        return source.read(target, start, Math.min(cap, length));
    }

    @Override public void close() {
        source.close();
    }

    public static int contract(int cap) throws IOException {
        try (CappedReader input = new CappedReader("abcdef", cap)) {
            char[] buffer = {'!', '?', '?', '?', '#'};
            int consumed = 0;
            while (consumed < 6) {
                int count = input.read(buffer, 1, 3);
                if (count < 1 || count > cap || count > 6 - consumed) return 0;
                for (int j = 0; j < count; j++) {
                    if (buffer[1+j] != 'a' + consumed + j) return 0;
                }
                if (buffer[0] != '!' || buffer[4] != '#') return 0;
                consumed += count;
            }
            return input.read(buffer, 1, 0) == 0 && input.read(buffer, 1, 3) == -1 ? 1 : 0;
        }
    }
}
