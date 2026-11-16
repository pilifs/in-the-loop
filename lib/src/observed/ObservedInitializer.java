import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;

/**
 * Written by jvmcontract (lib/src/observed.rs): initializes the class named by its one argument, first thing, with
 * the application class loader, and prints the static state the initializer left as one line of JSON after
 * "@observed ": each static field the class declares, with what the tool holds of its value (null, an integral or
 * boolean primitive, a String, a Class, a java.util.HashMap of String keys, an array of those) or, for any other
 * value, what it was. An object two fields hold is printed once and named twice. An initialization that throws is
 * printed as what it threw.
 */
public final class ObservedInitializer {
    private static final IdentityHashMap<Object, Integer> IDS = new IdentityHashMap<>();
    private static final List<String> OBJECTS = new ArrayList<>();

    private ObservedInitializer() {
    }

    public static void main(String[] args) {
        Class<?> c;
        try {
            c = Class.forName(args[0], true, ClassLoader.getSystemClassLoader());
        }
        catch (Throwable t) {
            Throwable cause = (t instanceof ExceptionInInitializerError && t.getCause() != null) ? t.getCause() : t;
            System.out.println("@observed {\"threw\":\"" + cause.getClass().getName() + "\"}");
            return;
        }
        StringBuilder fields = new StringBuilder();
        for (Field f : c.getDeclaredFields()) {
            if (!Modifier.isStatic(f.getModifiers())) {
                continue;
            }
            String value;
            try {
                f.setAccessible(true);
                value = f.getType().isPrimitive() ? primitive(f.getType(), f.get(null)) : value(f.get(null));
            }
            catch (Throwable t) {
                value = unheld("a field reflection does not read (" + t.getClass().getName() + ")");
            }
            if (fields.length() > 0) {
                fields.append(',');
            }
            fields.append("{\"name\":\"").append(f.getName()).append("\",\"value\":").append(value).append('}');
        }
        System.out.println("@observed {\"jdk\":\"" + System.getProperty("java.version") + "\",\"fields\":[" + fields
                + "],\"objects\":[" + String.join(",", OBJECTS) + "]}");
    }

    private static String unheld(String what) {
        return "{\"u\":\"" + what + "\"}";
    }

    private static String primitive(Class<?> type, Object boxed) {
        if (type == boolean.class) {
            return "{\"n\":" + (((Boolean) boxed) ? 1 : 0) + "}";
        }
        if (type == char.class) {
            return "{\"n\":" + (int) ((Character) boxed) + "}";
        }
        if (type == float.class || type == double.class) {
            return unheld("a " + type.getName());
        }
        return "{\"n\":" + ((Number) boxed).longValue() + "}";
    }

    private static String value(Object v) {
        if (v == null) {
            return "null";
        }
        Integer known = IDS.get(v);
        if (known != null) {
            return "{\"o\":" + known + "}";
        }
        Class<?> type = v.getClass();
        boolean map = type == HashMap.class;
        if (map) {
            for (Object key : ((Map<?, ?>) v).keySet()) {
                if (key != null && !(key instanceof String)) {
                    return unheld("a java.util.HashMap with a key of " + key.getClass().getName());
                }
            }
        }
        if (type.isArray() && (type.getComponentType() == float.class || type.getComponentType() == double.class)) {
            return unheld("an array of " + type.getComponentType().getName());
        }
        if (!(v instanceof String) && !(v instanceof Class) && !map && !type.isArray()) {
            return unheld("an object of " + type.getName());
        }
        // Numbered before what it holds is, so that an object that reaches itself ends.
        int id = OBJECTS.size();
        IDS.put(v, id);
        OBJECTS.add(null);
        StringBuilder o = new StringBuilder();
        if (v instanceof String) {
            String s = (String) v;
            o.append("{\"k\":\"string\",\"units\":[");
            for (int i = 0; i < s.length(); i++) {
                o.append(i == 0 ? "" : ",").append((int) s.charAt(i));
            }
            // A copy asks the pool: interning the String itself would put it there.
            o.append("],\"interned\":").append(new String(s.toCharArray()).intern() == s).append('}');
        }
        else if (v instanceof Class) {
            Class<?> named = (Class<?>) v;
            o.append("{\"k\":\"class\",\"name\":\"").append(named.isPrimitive() ? named.getName() : named.getName().replace('.', '/')).append("\"}");
        }
        else if (map) {
            o.append("{\"k\":\"map\",\"entries\":[");
            boolean first = true;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) v).entrySet()) {
                o.append(first ? "" : ",").append(value(e.getKey())).append(',').append(value(e.getValue()));
                first = false;
            }
            o.append("]}");
        }
        else {
            Class<?> element = type.getComponentType();
            o.append("{\"k\":\"array\",\"element\":\"").append(element.descriptorString()).append("\",\"cells\":[");
            for (int i = 0; i < Array.getLength(v); i++) {
                o.append(i == 0 ? "" : ",").append(element.isPrimitive() ? primitive(element, Array.get(v, i)) : value(Array.get(v, i)));
            }
            o.append("]}");
        }
        OBJECTS.set(id, o.toString());
        return "{\"o\":" + id + "}";
    }
}
