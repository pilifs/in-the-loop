package claims;

import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.Map;

/**
 * A library's tables, built as Spring's ClassUtils builds its own: through an IdentityHashMap, whose iteration
 * follows identity hash codes, and with a load factor, so the own checker does not run the initializer. What it
 * leaves has no input: the fixture of an observed initializer ({@code M.observed}).
 */
final class Tables {
    private Tables() {}

    static final Map<Class<?>, Class<?>> WRAPPERS = new IdentityHashMap<>();
    static final Map<String, Class<?>> BY_NAME = new HashMap<>(16, 0.75f);
    static final Map<String, Class<?>> SAME = BY_NAME;
    static final float RATIO = Float.parseFloat("0.75");
    static final char[] MARKS = { '[', ']' };
    static final Class<?>[] ORDER = { String.class };
    static final int COUNT;
    static final String PREFIX;
    static String LABEL = "label";
    static Object NONE;

    static {
        WRAPPERS.put(Integer.class, int.class);
        WRAPPERS.put(Boolean.class, boolean.class);
        for (Map.Entry<Class<?>, Class<?>> e : WRAPPERS.entrySet()) {
            BY_NAME.put(e.getValue().getName(), e.getValue());
        }
        BY_NAME.put(String.class.getName(), String.class);
        COUNT = BY_NAME.size();
        PREFIX = new StringBuilder("claims").append('.').toString();
    }
}
