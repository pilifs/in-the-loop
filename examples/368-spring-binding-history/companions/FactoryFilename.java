package springwork;

import java.io.FilterInputStream;
import java.io.IOException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Properties;
import org.springframework.beans.CachedIntrospectionResults;
import org.springframework.core.io.UrlResource;
import org.springframework.core.io.support.PropertiesLoaderUtils;

public final class FactoryFilename {
    private static URL resource() throws IOException {
        var hits = CachedIntrospectionResults.class.getClassLoader().getResources("META-INF/spring.factories");
        if (!hits.hasMoreElements()) throw new AssertionError();
        var url = hits.nextElement();
        if (hits.hasMoreElements()) throw new AssertionError();
        return url;
    }

    public static int check() throws IOException {
        var url = resource();
        return url.getPath() == url.getFile() && "spring.factories".equals(new UrlResource(url).getFilename()) ? 1 : 0;
    }

    public static void main(String[] args) throws Exception {
        var url = resource();
        var props = PropertiesLoaderUtils.loadProperties(new UrlResource(url));
        String key = "org.springframework.beans.factory.generator.BeanRegistrationContributionProvider";
        if (props.size() != 1 || props.containsKey("org.springframework.beans.BeanInfoFactory")
                || !"org.springframework.aop.scope.ScopedProxyBeanRegistrationContributionProvider".equals(props.getProperty(key)))
            throw new AssertionError(props);
        int first, size;
        try (var original = url.openStream()) {
            byte[] buffer = new byte[8192];
            first = original.read(buffer);
            size = first + original.readAllBytes().length;
        }
        // Exercise the same JDK parser across the continuation and every possible fixed refill cap.
        for (int limit = 1; limit <= size; limit++) {
            final int chunk = limit;
            try (var input = new FilterInputStream(url.openStream()) {
                @Override public int read(byte[] b, int off, int len) throws IOException {
                    return super.read(b, off, Math.min(chunk, len));
                }
            }) {
                var chunked = new Properties();
                chunked.load(input);
                if (!chunked.equals(props)) throw new AssertionError(chunk);
            }
        }
        var hash = MessageDigest.getInstance("SHA-256").digest(url.getPath().getBytes(StandardCharsets.UTF_8));
        System.out.println(check() + " " + first + " " + size + " " + HexFormat.of().formatHex(hash));
    }
}
