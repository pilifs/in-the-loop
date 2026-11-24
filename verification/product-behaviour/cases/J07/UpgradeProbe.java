import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.apache.commons.compress.archivers.tar.*;

public class UpgradeProbe {
    private static Path control() throws Exception {
        Path tar = Path.of("slash.tar");
        try (TarArchiveOutputStream out = new TarArchiveOutputStream(Files.newOutputStream(tar))) {
            TarArchiveEntry directory = new TarArchiveEntry("dir/");
            out.putArchiveEntry(directory); out.closeArchiveEntry();
            TarArchiveEntry file = new TarArchiveEntry("dir/file");
            file.setSize(2);
            out.putArchiveEntry(file); out.write(new byte[]{0,(byte)255}); out.closeArchiveEntry();
        }
        return tar;
    }
    public static String observe(String[] args) throws Exception {
        Path input = args[0].equals("upstream") ? Path.of("fixtures", "orjson.tar") : control();
        String first = null;
        for (int pass = 0; pass < 2; pass++) {
            MessageDigest rows = MessageDigest.getInstance("SHA-256");
            int count = 0, dirs = 0, files = 0, overlap = 0;
            long bytes = 0;
            try (TarFile tar = new TarFile(input)) {
                for (TarArchiveEntry e : tar.getEntries()) {
                    boolean d = e.isDirectory(), file = e.isFile();
                    try (InputStream stream = tar.getInputStream(e)) {
                        byte[] payload = stream.readAllBytes();
                        String sha = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(payload));
                        String row = e.getName() + "\t" + (e.getLinkFlag() & 255) + "\t" + d + "\t" + file
                                + "\t" + payload.length + "\t" + sha + "\n";
                        rows.update(row.getBytes(StandardCharsets.UTF_8));
                        bytes += payload.length;
                    }
                    count++; if (d) dirs++; if (file) files++; if (d && file) overlap++;
                }
            }
            String current = count + "/" + dirs + "/" + files + "/" + overlap + "/" + bytes + "/" + HexFormat.of().formatHex(rows.digest());
            if (first != null && !first.equals(current)) throw new AssertionError("second read disagrees");
            first = current;
        }
        return first;
    }
}
