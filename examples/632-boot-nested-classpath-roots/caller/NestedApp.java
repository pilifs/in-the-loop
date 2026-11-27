import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

public class NestedApp {
    public static void main(String[] args) throws Exception {
        BootArchive.childBinding();
        ClassLoader loader = Thread.currentThread().getContextClassLoader();
        var resolver = new PathMatchingResourcePatternResolver(loader);
        String result;
        if (args[0].equals("challenge")) {
            var items = new ArrayList<String>();
            for (URL root : Collections.list(loader.getResources(""))) {
                String url = root.toExternalForm();
                String name = url.contains("/first.jar") ? "first" : url.contains("/second.jar") ? "second" : null;
                if (name == null) continue;
                try (var input = new URL(root, "library-marker.properties").openStream()) {
                    items.add(name + ":" + new String(input.readAllBytes(), StandardCharsets.US_ASCII));
                }
            }
            result = String.join(",", items);
        } else {
            boolean control = args[0].equals("control");
            var matches = new ArrayList<String>();
            try {
                for (var r : resolver.getResources(control ? "classpath:mapper/*.xml" : "classpath:*.properties")) {
                    if ((control ? "fixed.xml" : "root-marker.properties").equals(r.getFilename()))
                        matches.add(r.getContentAsString(StandardCharsets.US_ASCII));
                }
                result = (control ? "" : (loader.getResource("") != null) + ":") + String.join(",", matches);
            } catch (java.io.FileNotFoundException missing) {
                result = "missing-root";
            }
        }
        System.out.println("OBS " + result);
    }
}
