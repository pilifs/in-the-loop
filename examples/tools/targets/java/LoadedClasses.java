import java.io.InputStream;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;

class LoadedClasses {
    public static void main(String[] args) throws Exception {
        Path root = Paths.get(args[0]).toRealPath();
        ClassLoader loader = Thread.currentThread().getContextClassLoader();
        for (int i = 1; i < args.length; i++) {
            Class<?> type = Class.forName(args[i], false, loader);
            Path jar = Paths.get(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
            String resource = "/" + type.getName().replace('.', '/') + ".class";
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream bytes = type.getResourceAsStream(resource)) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = bytes.read(buffer)) != -1) digest.update(buffer, 0, n);
            }
            StringBuilder hex = new StringBuilder();
            for (byte b : digest.digest()) {
                hex.append(Character.forDigit((b & 255) >>> 4, 16));
                hex.append(Character.forDigit(b & 15, 16));
            }
            System.out.println(type.getName() + "\t" + root.relativize(jar) + "\t" + hex);
        }
    }
}
