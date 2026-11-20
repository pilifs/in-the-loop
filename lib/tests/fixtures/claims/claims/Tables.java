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
    static class Base {
        final long offset;
        Base(long value) { offset = value; }
    }
    static final class Fixed extends Base {
        final int offset;
        final String name;
        Fixed(int value, String label) { super(1L << 40); offset = value; name = label; }
    }
    static final Fixed FIXED = new Fixed(-3, new String("UTC"));
    static final Base ALIAS = FIXED;
    static final Fixed OTHER = new Fixed(-3, FIXED.name);

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
