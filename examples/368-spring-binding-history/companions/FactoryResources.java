package springwork;

import java.net.JarURLConnection;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Properties;
import org.springframework.beans.CachedIntrospectionResults;

/** The resource enumeration requested by the released factory-loader bootstrap. */
public final class FactoryResources {
    public static void main(String[] args) throws Exception {
        var loader = CachedIntrospectionResults.class.getClassLoader();
        if (loader != ClassLoader.getSystemClassLoader()) throw new AssertionError("unexpected Spring loader");
        var urls = loader.getResources("META-INF/spring.factories");
        while (urls.hasMoreElements()) {
            var jar = (JarURLConnection) urls.nextElement().openConnection();
            String name = Path.of(jar.getJarFileURL().toURI()).getFileName().toString();
            byte[] bytes;
            try (var stream = jar.getInputStream()) { bytes = stream.readAllBytes(); }
            Properties factories = new Properties();
            try (var stream = new java.io.ByteArrayInputStream(bytes)) { factories.load(stream); }
            String value = factories.getProperty("org.springframework.beans.BeanInfoFactory", "");
            String sha = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            System.out.println(name + "\t" + sha + "\t" + value);
        }
    }
}
