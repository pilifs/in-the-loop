package importer;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;

/** A selector covers three documents and five independent binary choices. */
public final class Projection {
    static byte[] payload(int doc) {
        if (doc == 0) return new byte[]{'a', ',', 'b', '\n', 'c', ',', 'd', '\n'};
        if (doc == 1) return new byte[]{'x', ',', 'y', '\n'};
        return new byte[]{'z', ',', '1', '\n', 'z', ',', '2', '\n', 'z', ',', '3', '\n'};
    }

    static byte[] source(int code) {
        byte[] plain = payload(code >>> 5);
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
        int doc = code >>> 5;
        return Math.min(cap(code), doc == 0 ? 2 : doc == 1 ? 1 : 3);
    }

    public static int bytes(int code) throws IOException {
        byte[] actual = PageImporter.remaining(source(code), (code & 8) != 0, (code & 4) != 0);
        return Arrays.equals(actual, payload(code >>> 5)) ? 1 : 0;
    }

    public static int count(int code) throws IOException {
        return read(code).size() == countExpected(code) ? 1 : 0;
    }

    public static int page(int code) throws IOException {
        List<PageImporter.Row> actual = read(code);
        if (actual.size() != countExpected(code)) return 0;
        int doc = code >>> 5;
        for (int i = 0; i < actual.size(); i++) {
            PageImporter.Row row = actual.get(i);
            String first = doc == 0 ? (i == 0 ? "a" : "c") : doc == 1 ? "x" : "z";
            String second = doc == 0 ? (i == 0 ? "b" : "d") : doc == 1 ? "y" : (i == 0 ? "1" : "2");
            if (row.number() != start(code) + i || row.fields().size() != 2
                    || !first.equals(row.fields().get(0)) || !second.equals(row.fields().get(1))) return 0;
        }
        return 1;
    }
}
