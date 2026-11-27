import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.json.JsonWriter;
import tools.jackson.core.JacksonException;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;

public class PublicCaller {
    static final JsonMapper READER = JsonMapper.builder().enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
    static String read(Map<String, Object> map, boolean named) {
        JsonWriter<Map<String, Object>> writer = JsonWriter.of(members -> {
            members.add("version", 1);
            if (named) members.add("pairs").usingPairs(Map::forEach);
            else members.add().usingPairs(Map::forEach);
        });
        String wire = writer.writeToString(map);
        try { return READER.readTree(wire).toString(); }
        catch (JacksonException invalid) { return "invalid-json"; }
    }
    public static String observe(String[] args) {
        if (args[0].equals("challenge")) return read(Map.of("version", 2), true) + " / " + read(Map.of(), true);
        var data = new LinkedHashMap<String, Object>();
        data.put("a", "A");
        data.put("b", "B");
        return read(data, args[0].equals("intent"));
    }
}
