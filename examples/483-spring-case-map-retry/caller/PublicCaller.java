import java.util.Locale;
import org.springframework.util.LinkedCaseInsensitiveMap;

public class PublicCaller {
    static String state(LinkedCaseInsensitiveMap<String> m) {
        return m.size() + "," + m.containsKey("key") + "," + m.get("key") + "," + m.keySet();
    }
    public static String observe(String[] args) {
        var m = new LinkedCaseInsensitiveMap<String>(Locale.ROOT);
        if (args[0].equals("existing")) {
            m.put("Key",null);
            return m.computeIfAbsent("KEY", k -> null) + ":" + state(m);
        }
        String first = m.computeIfAbsent("Key", k -> null) + ":" + state(m);
        if (args[0].equals("retry")) {
            var argument = new StringBuilder();
            m.computeIfAbsent("KEY", k -> {argument.append(k); return "v";});
            String keys = m.keySet().toString();
            return argument + ":" + keys + ":" + m.remove("kEy") + ":" + state(m);
        }
        var other = new LinkedCaseInsensitiveMap<String>(Locale.ROOT);
        var marker = new IllegalStateException();
        try { other.computeIfAbsent("Key", k -> {throw marker;}); }
        catch (IllegalStateException ex) { return first + (ex == marker ? " / marker:" : " / other:") + state(other); }
        return first + " / swallowed";
    }
}
