import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.core.io.ByteArrayResource;

public class PublicCaller extends Flatten {
    static final Object MARKER = new Object();
    static String value(Map<?,?> map, String key) {
        if (!map.containsKey(key)) return "absent";
        Object v = map.get(key);
        if (v == MARKER) return "marker";
        return "".equals(v) ? "blank" : String.valueOf(v);
    }
    static String values(Map<?,?> map) {
        return String.join(",", List.of("a","b","c","d","s").stream().map(k -> value(map, k)).toList());
    }
    Map<String,Object> load(Object marker) {
        var out = new LinkedHashMap<String,Object>();
        process((props, original) -> out.putAll(select(original, marker)));
        return out;
    }
    public static String observe(String[] args) {
        boolean containers = args[0].equals("containers");
        String yaml = "{a: null, b: ~, c: {}, d: '', s: value" + (containers ? ", e: []}" : "}");
        var resource = new ByteArrayResource(yaml.getBytes(StandardCharsets.UTF_8));
        if (args[0].equals("properties")) {
            var factory = new YamlPropertiesFactoryBean();
            factory.setResources(resource);
            factory.afterPropertiesSet();
            return values(factory.getObject());
        }
        var reader = new PublicCaller();
        reader.setResources(resource);
        if (containers) {
            var map = reader.load(MARKER);
            return "map=" + value(map,"c") + " list=" + value(map,"e");
        }
        String first = values(reader.load(null));
        return reader.canSelectMarker() ? first + " / " + values(reader.load(MARKER)) : first;
    }
}
