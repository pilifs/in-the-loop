import com.google.gson.*;

import java.util.*;

public class PublicCaller {
    static String value(Number n, Class<?> type) {
        var gson = new Gson();
        var tree = gson.toJsonTree(n, type);
        var number = tree.getAsJsonPrimitive().getAsNumber();
        String text = gson.toJson(tree);
        String direct = gson.toJson(n, type);
        if (!text.equals(direct))
            throw new AssertionError("tree and stream differ: " + text + "/" + direct);
        return number.getClass().getSimpleName() + ":" + number + ":" + text;
    }

    public static String observe(String[] a) {
        return switch (a[0]) {
            case "control" -> value(1L, long.class) + "/" + value(1L, Long.class);
            case "challenge" -> value(257, Byte.class) + "/" + value((byte) 1, Byte.class);
            default -> {
                var values = new ArrayList<String>();
                for (var c :
                        List.of(
                                byte.class,
                                short.class,
                                int.class,
                                Byte.class,
                                Short.class,
                                Integer.class)) values.add(value(1, c));
                yield String.join("/", values);
            }
        };
    }
}
