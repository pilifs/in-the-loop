import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;

public class AssetReader {
    public static void main(String[] args) throws Exception {
        var origin =
                PathMatchingResourcePatternResolver.class
                        .getProtectionDomain()
                        .getCodeSource()
                        .getLocation();
        if (!Path.of(origin.toURI()).equals(Path.of(args[0])))
            throw new IllegalStateException("wrong Spring resolver");
        var values = new ArrayList<String>();
        for (var resource :
                new PathMatchingResourcePatternResolver().getResources("classpath*:/**/q30.txt")) {
            try (var in = resource.getInputStream()) {
                values.add(new String(in.readAllBytes(), StandardCharsets.UTF_8));
            }
        }
        System.out.println("assets=" + values);
    }
}
