import java.lang.reflect.Array;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * The JVM's side of lib/tests/conformance.rs. Reads lines of `call TAB pkg.Class#method TAB arguments` or
 * `check TAB harness-directory TAB arguments` from the file named by its second argument, and prints one line for
 * each: `returns V` or `throws C` for a call; `holds`, `refuted` (the harness threw AssertionError) or `throws C`
 * for a property harness the tool generated. Each line runs in a class loader of its own over the corpus (the first
 * argument), so that every call sees the classes uninitialized, as the engines do.
 *
 * Arguments are separated by `;`: an integer (a char as its code unit), `true` or `false`, `null`, an array such
 * as `[1,2]`, or `@i` for the same object as argument i. A result prints as Java's toString of it, except a boolean
 * as 1 or 0 and a char as its code unit, which is how the interpreter holds them.
 */
public class Runner {
    public static void main(String[] args) throws Exception {
        URL corpus = Path.of(args[0]).toUri().toURL();
        for (String line : Files.readAllLines(Path.of(args[1]))) {
            String[] field = line.split("\t", -1);
            boolean check = field[0].equals("check");
            List<URL> urls = new ArrayList<>();
            if (check) urls.add(Path.of(field[1]).toUri().toURL());
            urls.add(corpus);
            String className = check ? "PropertyHarness" : field[1].substring(0, field[1].indexOf('#'));
            String methodName = check ? "check" : field[1].substring(field[1].indexOf('#') + 1);
            String out;
            try (URLClassLoader loader = new URLClassLoader(urls.toArray(URL[]::new), ClassLoader.getPlatformClassLoader())) {
                Method method = null;
                for (Method m : Class.forName(className, false, loader).getDeclaredMethods()) {
                    if (m.getName().equals(methodName)) method = m;
                }
                method.setAccessible(true);
                Object[] values = arguments(method.getParameterTypes(), field[2]);
                try {
                    Object r = method.invoke(null, values);
                    out = check ? "holds" : "returns " + show(r);
                } catch (InvocationTargetException e) {
                    Throwable t = e.getCause();
                    out = check && t instanceof AssertionError ? "refuted" : "throws " + t.getClass().getName();
                }
            } catch (Throwable t) {
                out = "error " + t;
            }
            System.out.println(out);
        }
    }

    static Object[] arguments(Class<?>[] types, String text) {
        String[] tokens = text.isEmpty() ? new String[0] : text.split(";", -1);
        if (tokens.length != types.length) throw new IllegalArgumentException(types.length + " arguments expected: " + text);
        Object[] out = new Object[types.length];
        for (int i = 0; i < types.length; i++) {
            String t = tokens[i].trim();
            if (t.startsWith("@")) out[i] = out[Integer.parseInt(t.substring(1))];
            else if (t.equals("null")) out[i] = null;
            else out[i] = value(types[i], t);
        }
        return out;
    }

    static Object value(Class<?> type, String t) {
        if (type.isArray()) {
            String body = t.substring(1, t.length() - 1).trim();
            String[] parts = body.isEmpty() ? new String[0] : body.split(",");
            Object array = Array.newInstance(type.getComponentType(), parts.length);
            for (int i = 0; i < parts.length; i++) Array.set(array, i, value(type.getComponentType(), parts[i].trim()));
            return array;
        }
        if (type == boolean.class) return Boolean.parseBoolean(t);
        if (type == char.class) return (char) Integer.parseInt(t);
        long v = Long.parseLong(t);
        if (type == byte.class) return (byte) v;
        if (type == short.class) return (short) v;
        if (type == int.class) return (int) v;
        return v;
    }

    static String show(Object r) {
        if (r == null) return "null";
        if (r instanceof Boolean b) return b ? "1" : "0";
        if (r instanceof Character c) return Integer.toString(c);
        if (r.getClass().isArray()) {
            List<String> parts = new ArrayList<>();
            for (int i = 0; i < Array.getLength(r); i++) parts.add(show(Array.get(r, i)));
            return "[" + String.join(", ", parts) + "]";
        }
        return r.toString();
    }
}
