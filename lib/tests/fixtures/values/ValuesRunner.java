import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/**
 * Runs the values stream's conformance cases on a JVM (lib/tests/values.rs): each line of standard input is a
 * class, a method and its int arguments; each line of output is what the call gave, in the form the test reads the
 * interpreter's in: "int N", "bool true", "str" and the String's code units in hex, "null", or "throws" and the
 * class of what it threw.
 */
public final class ValuesRunner {
    public static void main(String[] args) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        for (String line = in.readLine(); line != null; line = in.readLine()) {
            if (line.isBlank()) {
                continue;
            }
            String[] parts = line.trim().split(" ");
            Class<?> c = Class.forName(parts[0]);
            Method target = null;
            for (Method m : c.getDeclaredMethods()) {
                if (m.getName().equals(parts[1]) && m.getParameterCount() == parts.length - 2) {
                    target = m;
                }
            }
            if (target == null) {
                throw new IllegalArgumentException("no method " + line);
            }
            target.setAccessible(true);
            Object[] values = new Object[parts.length - 2];
            for (int i = 0; i < values.length; i++) {
                values[i] = Integer.decode(parts[i + 2]);
            }
            System.out.println(render(target, values));
        }
    }

    private static String render(Method target, Object[] values) throws IllegalAccessException {
        Object result;
        try {
            result = target.invoke(null, values);
        } catch (InvocationTargetException e) {
            return "throws " + e.getCause().getClass().getName();
        }
        if (result == null) {
            return "null";
        }
        if (result instanceof Boolean b) {
            return "bool " + b;
        }
        if (result instanceof Integer n) {
            return "int " + n;
        }
        if (result instanceof String s) {
            StringBuilder out = new StringBuilder("str");
            for (int i = 0; i < s.length(); i++) {
                out.append(String.format(" %04x", (int) s.charAt(i)));
            }
            return out.toString();
        }
        return "unrendered " + result.getClass().getName();
    }
}
