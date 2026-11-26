import org.apache.commons.compress.archivers.cpio.*;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class PublicCaller {
    static void entry(ByteArrayOutputStream out, String name, int ino, byte[] data, int checksum)
            throws IOException {
        StringBuilder header = new StringBuilder("070702");
        int[] fields = {
            ino, 0100644, 0, 0, 1, 0, data.length, 0, 0, 0, 0, name.length() + 1, checksum
        };
        for (int v : fields) header.append(String.format(Locale.ROOT, "%08x", v));
        out.write(header.toString().getBytes(StandardCharsets.US_ASCII));
        out.write(name.getBytes(StandardCharsets.US_ASCII));
        out.write(0);
        while (out.size() % 4 != 0) out.write(0);
        out.write(data);
        while (out.size() % 4 != 0) out.write(0);
    }

    static byte[] archive() throws Exception {
        var out = new ByteArrayOutputStream();
        entry(out, "a", 1, new byte[] {1, (byte) 128, 3}, 132);
        entry(out, "b", 2, new byte[] {7}, 7);
        entry(out, "TRAILER!!!", 0, new byte[0], 0);
        return out.toByteArray();
    }

    static String read(byte[] archive, int offset, int chunk, int prefix) throws Exception {
        var bytes = new ArrayList<Integer>();
        try (var in = new CpioArchiveInputStream(new ByteArrayInputStream(archive))) {
            String first = in.getNextEntry().getName();
            byte[] buf = new byte[offset + chunk];
            Arrays.fill(buf, (byte) prefix);
            int n;
            boolean intact = true;
            while ((n = in.read(buf, offset, chunk)) > 0) {
                for (int j = 0; j < offset; j++) intact &= (buf[j] & 255) == prefix;
                for (int j = 0; j < n; j++) bytes.add(buf[offset + j] & 255);
            }
            String second = in.getNextEntry().getName();
            int b = in.read();
            boolean end = in.getNextEntry() == null;
            return first
                    + ":"
                    + bytes
                    + "/eof="
                    + n
                    + "/"
                    + second
                    + ":"
                    + b
                    + "/end="
                    + end
                    + "/prefix="
                    + intact;
        } catch (IOException e) {
            return "IOException ("
                    + e.getClass().getSimpleName()
                    + ", checksum="
                    + e.getMessage().toLowerCase(java.util.Locale.ROOT).contains("crc")
                    + ")/"
                    + bytes;
        }
    }

    public static String observe(String[] a) throws Exception {
        var bytes = archive();
        return switch (a[0]) {
            case "control" -> read(bytes, 0, 3, 9);
            case "challenge" -> read(bytes, 1, 1, 0) + " / " + read(bytes, 1, 1, 255);
            default -> read(bytes, 2, 3, 9);
        };
    }
}
