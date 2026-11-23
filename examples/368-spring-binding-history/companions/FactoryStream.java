package springwork;

import java.io.IOException;
import java.net.JarURLConnection;
import org.springframework.beans.CachedIntrospectionResults;

/** Read the factory configuration through the same application loader as the binder. */
public final class FactoryStream {
    public static boolean matches(byte[] expected) throws IOException {
        var urls = CachedIntrospectionResults.class.getClassLoader().getResources("META-INF/spring.factories");
        if (!urls.hasMoreElements()) return false;
        var url = urls.nextElement();
        if (urls.hasMoreElements()) return false;
        var connection = url.openConnection();
        if (!(connection instanceof JarURLConnection) || connection.getURL() != url) return false;
        try (var stream = connection.getInputStream()) {
            for (byte b : expected) if (stream.read() != (b & 255)) return false;
            return stream.read() == -1;
        }
    }
}
