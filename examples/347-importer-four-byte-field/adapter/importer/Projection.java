package importer;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;

/** A selector covers every combination of the five binary choices for the four-byte field. */
public final class Projection {
    static byte[] payload() {
        return new byte[]{'a', 'b', 'c', ',', (byte) 0xf0, (byte) 0x9f, (byte) 0x98, (byte) 0x80, '\n', 'c', ',', 'd', '\n'};
    }

    static byte[] source(int code) {
        byte[] plain = payload();
        if ((code & 16) == 0) return plain;
        byte[] result = new byte[plain.length + 3];
        result[0] = (byte) 0xef;
        result[1] = (byte) 0xbb;
        result[2] = (byte) 0xbf;
        System.arraycopy(plain, 0, result, 3, plain.length);
        return result;
    }

    static int start(int code) { return 1 + ((code >>> 1) & 1); }
    static int cap(int code) { return 1 + (code & 1); }

    static List<PageImporter.Row> read(int code) throws IOException {
        return PageImporter.page(source(code), (code & 8) != 0, (code & 4) != 0, start(code), cap(code));
    }

    private static int countExpected(int code) {
        return cap(code);
    }

    public static int bytes(int code) throws IOException {
        byte[] actual = PageImporter.remaining(source(code), (code & 8) != 0, (code & 4) != 0);
        return Arrays.equals(actual, payload()) ? 1 : 0;
    }

    public static int count(int code) throws IOException {
        return read(code).size() == countExpected(code) ? 1 : 0;
    }

    public static int page(int code) throws IOException {
        List<PageImporter.Row> actual = read(code);
        if (actual.size() != countExpected(code)) return 0;
        for (int i = 0; i < actual.size(); i++) {
            PageImporter.Row row = actual.get(i);
            String first = i == 0 ? "abc" : "c";
            String second = i == 0 ? "\ud83d\ude00" : "d";
            if (row.number() != start(code) + i || row.fields().size() != 2
                    || !first.equals(row.fields().get(0)) || !second.equals(row.fields().get(1))) return 0;
        }
        return 1;
    }
}
