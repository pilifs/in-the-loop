import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;
import org.apache.commons.compress.archivers.zip.*;

public class PublicCaller {
    static final String NAME = "COMPRESS-621.txt";
    static final byte[] BODY = "https://issues.apache.org/jira/browse/COMPRESS-621".getBytes(StandardCharsets.UTF_8);
    static final byte[] PREFIX = "Before Zip file".getBytes(StandardCharsets.US_ASCII);

    static String read(Path file) throws Exception {
        try (ZipFile zip = new ZipFile(file.toFile())) {
            List<String> names = Collections.list(zip.getEntries()).stream()
                    .map(ZipArchiveEntry::getName).collect(Collectors.toList());
            ZipArchiveEntry entry = zip.getEntry(NAME);
            String content = "missing";
            if (entry != null) {
                try (InputStream stream = zip.getInputStream(entry)) {
                    content = entry.getSize() + "/" + new String(stream.readAllBytes(), StandardCharsets.UTF_8);
                }
            }
            String prefix;
            try {
                // The same caller can exercise the common entry API before these accessors existed.
                long offset = (Long) ZipFile.class.getMethod("getFirstLocalFileHeaderOffset").invoke(zip);
                try (InputStream stream = (InputStream) ZipFile.class.getMethod("getContentBeforeFirstLocalFileHeader").invoke(zip)) {
                    prefix = offset + "/" + (stream == null ? "<null>" : new String(stream.readAllBytes(), StandardCharsets.US_ASCII));
                }
            } catch (NoSuchMethodException absent) {
                prefix = "<unavailable>";
            }
            return "names=" + names + " entry=" + content + " prefix=" + prefix;
        }
    }

    static byte[] archive(boolean writePreamble) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipArchiveOutputStream out = new ZipArchiveOutputStream(bytes)) {
            out.setUseZip64(Zip64Mode.Never);
            if (writePreamble) out.writePreamble(PREFIX);
            ZipArchiveEntry entry = new ZipArchiveEntry(NAME);
            entry.setTime(946684800000L);
            out.putArchiveEntry(entry);
            out.write(BODY);
            out.closeArchiveEntry();
        }
        return bytes.toByteArray();
    }

    static String compare(String file, byte[] bytes) throws Exception {
        // Walk the bytes before opening the archive with the public reader.
        byte[] header = {'P', 'K', 3, 4};
        int first = -1;
        for (int i = 0; i <= bytes.length - header.length; i++) {
            if (Arrays.equals(bytes, i, i + header.length, header, 0, header.length)) { first = i; break; }
        }
        return "physical=" + first + " " + read(Files.write(Path.of(file), bytes));
    }

    public static String observe(String[] args) throws Exception {
        Path fixture = Path.of("fixtures", "COMPRESS-621.zip");
        switch (args[0]) {
            case "fixture": return read(fixture);
            case "stripped":
                byte[] bytes = Files.readAllBytes(fixture);
                return read(Files.write(Path.of("plain.zip"), Arrays.copyOfRange(bytes, PREFIX.length, bytes.length)));
            case "writers":
                ByteArrayOutputStream prepended = new ByteArrayOutputStream();
                prepended.write(PREFIX);
                prepended.write(archive(false));
                return "prepended " + compare("prepended.zip", prepended.toByteArray())
                        + " | writer " + compare("writer.zip", archive(true));
            default: throw new IllegalArgumentException(args[0]);
        }
    }
}
