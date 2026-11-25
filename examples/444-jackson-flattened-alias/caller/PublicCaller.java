import java.util.TreeMap;
import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonUnwrapped;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

public class PublicCaller {
    public record Inner(@JsonAlias("a") String c) {}
    public record Outer(@JsonUnwrapped Inner inner, String b) {}

    static String values(Outer outer) {
        return "child=" + (outer.inner() == null ? "<absent>" : outer.inner().c()) + " sibling=" + outer.b();
    }

    public static String observe(String[] args) {
        JsonMapper mapper = JsonMapper.builder().build();
        String key = args[0].equals("canonical") ? "c" : "a";
        Outer outer = mapper.readValue("{\"" + key + "\":\"Hello\",\"b\":\"World!\"}", Outer.class);
        if (!args[0].equals("roundtrip")) return values(outer);
        String emitted = mapper.writeValueAsString(outer);
        JsonNode tree = mapper.readTree(emitted);
        TreeMap<String, JsonNode> fields = new TreeMap<>();
        tree.properties().forEach(e -> fields.put(e.getKey(), e.getValue()));
        Outer second = mapper.readValue(emitted, Outer.class);
        return values(outer) + " object=" + tree.isObject() + " fields=" + fields
                + " reread=" + values(second) + " equal=" + outer.equals(second);
    }
}
