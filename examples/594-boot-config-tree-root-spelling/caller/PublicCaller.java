import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import org.springframework.boot.env.ConfigTreePropertySource;

public class PublicCaller {
    static String read(Path root) throws Exception {
        var source = new ConfigTreePropertySource("fixture", root);
        var names = Arrays.toString(source.getPropertyNames());
        var value = (ConfigTreePropertySource.Value) source.getProperty("a");
        if (value == null) return names + ":absent";
        try (var stream = value.getInputStream()) {
            byte[] bytes = stream.readAllBytes();
            return names + ":" + (bytes.length == 1 ? Byte.toUnsignedInt(bytes[0]) : Arrays.toString(bytes));
        }
    }

    public static String observe(String[] args) throws Exception {
        Path cfg = Files.createDirectory(Files.createTempDirectory("tree").resolve("cfg"));
        Files.write(cfg.resolve("a"), new byte[] {65});
        Path otherSpelling = cfg.resolve("..").resolve("cfg");
        if (!Files.isSameFile(cfg, otherSpelling)) throw new AssertionError("different roots");
        return switch (args[0]) {
            case "intent" -> read(otherSpelling);
            case "control" -> read(cfg);
            case "challenge" -> {
                Files.write(Files.createDirectory(cfg.resolve("..data")).resolve("a"), new byte[] {66});
                yield read(cfg) + "/" + read(otherSpelling);
            }
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
