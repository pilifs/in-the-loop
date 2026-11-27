import java.io.InputStream;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;

/** Export the class resource selected by this original bootstrap loader. */
public final class RuntimeHelperBytes {
    public static void main(String[] args) throws Exception {
        Class<?> owner = Class.forName(args[0], false, null);
        if (owner.getClassLoader() != null) throw new IllegalStateException("bootstrap class required");
        String file = owner.getName().replace('.', '/') + ".class";
        URL resource = owner.getResource("/" + file);
        if (resource == null || !resource.toString().equals("jrt:/java.base/" + file))
            throw new IllegalStateException("the helper must come from the selected runtime's java.base image");
        Path destination = Paths.get(args[1]).resolve(file);
        Files.createDirectories(destination.getParent());
        try (InputStream bytes = owner.getResourceAsStream("/" + file)) {
            Files.copy(bytes, destination, StandardCopyOption.REPLACE_EXISTING);
        }
        System.out.println(resource);
    }
}
