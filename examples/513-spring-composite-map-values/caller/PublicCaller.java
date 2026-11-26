import org.springframework.util.CollectionUtils;

import java.util.*;

public class PublicCaller {
    static String remove(Collection<String> values, String key) {
        try {
            return String.valueOf(values.remove(key));
        } catch (UnsupportedOperationException e) {
            return e.getClass().getSimpleName();
        }
    }

    public static String observe(String[] args) {
        Map<String, String> first = new LinkedHashMap<>(Map.of("a", "x"));
        String scenario = args[0];
        var second = new LinkedHashMap<String, String>();
        second.put(
                scenario.equals("shadow") ? "a" : "b",
                switch (scenario) {
                    case "shadow" -> "hidden";
                    case "missing" -> "y";
                    default -> "x";
                });
        Map<String, String> map = CollectionUtils.compositeMap(first, second);
        var values = map.values();
        if (scenario.equals("missing")) {
            String before = remove(values, "absent") + ":" + first + ":" + second;
            return before + " / " + remove(values, "x") + ":" + first + ":" + second;
        }
        String outcome = remove(values, "x");
        if (scenario.equals("shadow"))
            return outcome
                    + ":"
                    + map.get("a")
                    + ":"
                    + new ArrayList<>(values)
                    + ":"
                    + values.size()
                    + ":"
                    + first
                    + ":"
                    + second;
        if (scenario.equals("second")) outcome = remove(values, "x");
        return outcome
                + ":"
                + first
                + ":"
                + second
                + ":"
                + new ArrayList<>(map.keySet())
                + ":"
                + Collections.frequency(values, "x");
    }
}
