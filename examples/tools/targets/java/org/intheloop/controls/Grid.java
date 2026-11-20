package org.intheloop.controls;

import java.lang.reflect.Array;
import java.util.LinkedHashMap;
import java.util.Map;

/** JSON lines for finite-observation JVM controls. The target runs on real objects before serialization. */
public final class Grid {
    private Grid() {}

    public static Map<String, Object> fields(Object... pairs) {
        Map<String, Object> map = new LinkedHashMap<>();
        if (pairs.length % 2 != 0) throw new IllegalArgumentException("missing field value");
        for (int i = 0; i < pairs.length; i += 2) {
            String key = (String) pairs[i];
            if (map.containsKey(key)) throw new IllegalArgumentException("duplicate field " + key);
            map.put(key, pairs[i + 1]);
        }
        return map;
    }

    public static void row(int id, Object input, Object direct, Object adapter) {
        System.out.println(json(fields("id", id, "input", input, "direct", direct, "adapter", adapter)));
    }

    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof Boolean || value instanceof Integer || value instanceof Long) return value.toString();
        if (value instanceof String) {
            StringBuilder text = new StringBuilder("\"");
            for (char ch : ((String) value).toCharArray()) {
                if (ch == '"' || ch == '\\') text.append('\\');
                if (ch < ' ' || Character.isSurrogate(ch)) text.append(String.format("\\u%04x", (int) ch));
                else text.append(ch);
            }
            return text.append('"').toString();
        }
        if (value instanceof Map<?, ?>) {
            java.util.StringJoiner fields = new java.util.StringJoiner(",", "{", "}");
            for (Map.Entry<?, ?> field : ((Map<?, ?>) value).entrySet()) {
                fields.add(json((String) field.getKey()) + ":" + json(field.getValue()));
            }
            return fields.toString();
        }
        if (value.getClass().isArray()) {
            java.util.StringJoiner cells = new java.util.StringJoiner(",", "[", "]");
            for (int i = 0; i < Array.getLength(value); i++) cells.add(json(Array.get(value, i)));
            return cells.toString();
        }
        if (value instanceof Iterable<?>) {
            java.util.StringJoiner cells = new java.util.StringJoiner(",", "[", "]");
            for (Object cell : (Iterable<?>) value) cells.add(json(cell));
            return cells.toString();
        }
        throw new IllegalArgumentException("unrepresented observation type " + value.getClass().getName());
    }
}
