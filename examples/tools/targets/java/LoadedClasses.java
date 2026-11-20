import java.io.InputStream;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

class LoadedClasses {
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]).toRealPath();
        ClassLoader loader = Thread.currentThread().getContextClassLoader();
        for (int i = 1; i < args.length; i++) {
            Class<?> type = Class.forName(args[i], false, loader);
            Path jar = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
            String resource = "/" + type.getName().replace('.', '/') + ".class";
            try (InputStream bytes = type.getResourceAsStream(resource)) {
                String digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.readAllBytes()));
                System.out.println(type.getName() + "\t" + root.relativize(jar) + "\t" + digest);
            }
        }
    }
}
