import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import net.lingala.zip4j.ZipFile;

public class UpgradeProbe {
    private static String read(Path file) throws Exception {
        List<String> entries = new ArrayList<>();
        try (java.util.zip.ZipFile reader = new java.util.zip.ZipFile(file.toFile())) {
            Enumeration<? extends ZipEntry> names = reader.entries();
            while (names.hasMoreElements()) {
                ZipEntry entry = names.nextElement();
                try (var input = reader.getInputStream(entry)) {
                    byte[] bytes = input.readAllBytes();
                    entries.add(entry.getName() + "=" + (entry.isDirectory() ? "dir:" : "file:")
                            + java.util.HexFormat.of().formatHex(bytes));
                }
            }
        }
        Collections.sort(entries);
        return String.join(",", entries);
    }

    public static String observe(String[] args) throws Exception {
        boolean directory = args[0].equals("directory");
        String source = directory ? "cat/" : args[0].equals("isolated") ? "catalog" : "cat";
        String first = directory ? "dog/" : "dog";
        String second = directory ? "hound/" : "hound";
        Path file = Path.of("subject.zip");
        String[] names = directory ? new String[]{"cat/", "cat/a", "catalog", "other"}
                                   : new String[]{"cat", "catalog", "other"};
        try (ZipOutputStream writer = new ZipOutputStream(Files.newOutputStream(file))) {
            int payload = 0;
            for (String name : names) {
                ZipEntry entry = new ZipEntry(name);
                entry.setTime(946684800000L);
                writer.putNextEntry(entry);
                if (!entry.isDirectory()) writer.write(new byte[]{(byte) ++payload, (byte) (32 + payload)});
                writer.closeEntry();
            }
        }
        try (ZipFile archive = new ZipFile(file.toFile())) {
            archive.renameFile(source, first);
        }
        String intermediate = read(file);
        try (ZipFile archive = new ZipFile(file.toFile())) {
            archive.renameFile(first, second);
        }
        String persisted = read(file);
        if (!persisted.equals(read(file))) throw new AssertionError("independent second read disagrees");
        return intermediate + "|" + persisted;
    }
}
