import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

public class NativeReadback {
    public static void main(String[] args) throws Exception {
        String value = UpgradeProbe.observe(args);
        var images = Files.readAllLines(Path.of("/proc/self/maps")).stream()
                .filter(s -> s.endsWith("libsqlitejdbc.so")).map(s -> s.substring(s.indexOf('/'))).distinct().toList();
        if (images.size() != 1) throw new AssertionError("ambiguous native image");
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(images.get(0))));
        Files.writeString(Path.of("native.sha256"), HexFormat.of().formatHex(digest));
        Files.writeString(Path.of("observation.txt"),value);
    }
}
