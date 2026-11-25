import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import java.util.HashMap;

public class PublicCaller {
    public static String observe(String[] args) {
        var map = new HashMap<JsonPrimitive, String>();
        var key = new JsonPrimitive(42);
        if (args[0].equals("zero")) {
            map.put(new JsonPrimitive(-0.0), "first");
            var previous = map.put(JsonParser.parseString("0").getAsJsonPrimitive(), "next");
            int replacedSize = map.size();
            var removed = map.remove(new JsonPrimitive(0L));
            return previous + "/" + replacedSize + "/" + removed + "/" + map.size();
        }
        map.put(key, "saved");
        if (args[0].equals("types")) {
            return map.get(new JsonPrimitive("42")) + "/" + map.get(new JsonPrimitive(42));
        }
        var parsed = JsonParser.parseString(key.toString()).getAsJsonPrimitive();
        return "equals=" + key.equals(parsed) + "/" + parsed.equals(key)
                + " sameHash=" + (key.hashCode() == parsed.hashCode()) + " lookup=" + map.get(parsed)
                + " hashes=" + key.hashCode() + "/" + parsed.hashCode();
    }
}
