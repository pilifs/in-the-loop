import org.apache.commons.compress.archivers.tar.*;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class PublicCaller {
    static byte[] ascii(String s) {
        return s.getBytes(StandardCharsets.US_ASCII);
    }

    static void field(byte[] header, int start, String text) {
        byte[] data = ascii(text);
        System.arraycopy(data, 0, header, start, data.length);
    }

    static void member(ByteArrayOutputStream tar, String name, char type, byte[] data)
            throws Exception {
        byte[] h = new byte[512];
        field(h, 0, name);
        field(h, 100, "0000644");
        field(h, 108, "0000000");
        field(h, 116, "0000000");
        field(h, 124, String.format(Locale.ROOT, "%011o", data.length));
        field(h, 136, "00000000000");
        Arrays.fill(h, 148, 156, (byte) ' ');
        h[156] = (byte) type;
        field(h, 257, "ustar");
        field(h, 263, "00");
        int sum = 0;
        for (byte b : h) sum += b & 255;
        field(h, 148, String.format(Locale.ROOT, "%06o", sum));
        h[154] = 0;
        tar.write(h);
        tar.write(data);
        tar.write(new byte[(512 - data.length % 512) % 512]);
    }

    static String pax(String kv) {
        int n = kv.length() + 3;
        while (true) {
            String s = n + " " + kv + "\n";
            if (n == s.length()) return s;
            n = s.length();
        }
    }

    static byte[] archive(boolean aligned, String payload) throws Exception {
        var tar = new ByteArrayOutputStream();
        String records =
                pax("GNU.sparse.major=1")
                        + pax("GNU.sparse.minor=0")
                        + pax("GNU.sparse.name=sparse")
                        + pax("GNU.sparse.realsize=7");
        member(tar, "PaxHeaders/sparse", 'x', ascii(records));
        byte[] data = new byte[516];
        byte[] map = ascii("1\n3\n" + (aligned ? "0".repeat(506) : "") + "4\n");
        System.arraycopy(map, 0, data, 0, map.length);
        System.arraycopy(ascii(payload), 0, data, 512, 4);
        member(tar, "sparse", '0', data);
        member(tar, "tail", '0', ascii("Z"));
        tar.write(new byte[1024]);
        return tar.toByteArray();
    }

    public static String observe(String[] a) throws Exception {
        boolean tail = a[0].equals("challenge");
        try (var in =
                new TarArchiveInputStream(
                        new ByteArrayInputStream(
                                archive(!a[0].equals("control"), tail ? "WXYZ" : "ABCD")))) {
            if (!"sparse".equals(in.getNextEntry().getName()))
                throw new AssertionError("sparse entry");
            String first = Arrays.toString(in.readAllBytes());
            if (!tail) return first;
            String name = in.getNextEntry().getName();
            return first
                    + "/"
                    + name
                    + "/"
                    + new String(in.readAllBytes(), StandardCharsets.US_ASCII)
                    + "/"
                    + (in.getNextEntry() == null);
        }
    }
}
