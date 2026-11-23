package springwork;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Properties;
import org.springframework.beans.CachedIntrospectionResults;
import org.springframework.core.io.UrlResource;
import org.springframework.core.io.support.PropertiesLoaderUtils;

public final class FactoryProperties {
    private static boolean matches(Properties properties) {
        return properties.size() == 1 && properties.getProperty("org.springframework.beans.BeanInfoFactory") == null
            && "org.springframework.aop.scope.ScopedProxyBeanRegistrationContributionProvider".equals(
                properties.getProperty("org.springframework.beans.factory.generator.BeanRegistrationContributionProvider"));
    }

    private static URL factory() throws IOException {
        var all = CachedIntrospectionResults.class.getClassLoader().getResources("META-INF/spring.factories");
        var url = all.nextElement();
        if (all.hasMoreElements()) throw new AssertionError();
        return url;
    }

    public static int check() throws IOException {
        return matches(PropertiesLoaderUtils.loadProperties(new UrlResource(factory()))) ? 1 : 0;
    }

    private static void partition(byte[] bytes, int first, int second) throws IOException {
        var input = new ByteArrayInputStream(bytes) {
            @Override public int read(byte[] out, int offset, int length) {
                int boundary = pos < first ? first : pos < second ? second : bytes.length;
                Arrays.fill(out, offset, offset + length, (byte) '#');
                return super.read(out, offset, Math.min(length, boundary - pos));
            }
        };
        var properties = new Properties();
        properties.load(input);
        if (!matches(properties) || input.read() != -1) throw new AssertionError(first + ", " + second);
    }

    public static void main(String[] args) throws Exception {
        byte[] bytes;
        try (var input = factory().openStream()) { bytes = input.readAllBytes(); }
        int n = bytes.length;
        int partitions = 1;
        partition(bytes, n, n);
        for (int first = 1; first < n; first++) {
            partition(bytes, first, n);
            partitions++;
            for (int second = first + 1; second < n; second++) {
                partition(bytes, first, second);
                partitions++;
            }
        }
        var url = MessageDigest.getInstance("SHA-256").digest(factory().getPath().getBytes(StandardCharsets.UTF_8));
        System.out.println(check() + " " + n + " " + partitions + " " + HexFormat.of().formatHex(url));
    }
}
