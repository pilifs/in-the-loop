import java.io.InputStream;
import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Written by jvmcontract (lib/src/observed.rs): initializes the class named by its first argument, first thing, with
 * the application class loader, and prints the static state the initializer left as one line of JSON after
 * "@observed ": each static field the class declares, with what the tool holds of its value (null, an integral or
 * boolean primitive, a String, a Class, a java.util.HashMap of String keys, an array of those) or, for any other
 * value, what it was. An object two fields hold is printed once and named twice. An initialization that throws is
 * printed as what it threw.
 *
 * With a second argument, the file the JVM logs each class initialization to (-Xlog:class+init), the line also says
 * what the state was observed on ("on"): the class file's sha256 and where it came from, the class path in order,
 * the JDK, the default locale, each system property the class path's code read with the value it had, and each class
 * of the class path the initialization initialized besides the class and its supertypes, with its class file's
 * sha256 and its static state as it was then. Without one, the class's state alone: what a class another
 * initialization initialized is compared with, initialized first thing in a JVM of its own.
 */
public final class ObservedInitializer {
    private static final Pattern INITIALIZING = Pattern.compile("Initializing '([^']+)'");

    private ObservedInitializer() {
    }

    /**
     * The system properties, recording each one the class path's code read and the value it had (null where it was
     * not set): a read whose caller, past System.getProperty and the getters Integer.getInteger, Long.getLong and
     * Boolean.getBoolean, is a class the application class loader loaded. The JDK's reads of its own configuration
     * (as it opens a JAR, or the first time a JDK class is used) are not the initializer's: the check takes the JDK
     * at its defaults throughout.
     */
    private static final class Recording extends Properties {
        final Map<String, String> read = new LinkedHashMap<>();
        final List<String> order = new ArrayList<>();
        private boolean busy;

        @Override
        public String getProperty(String key) {
            String value = super.getProperty(key);
            if (busy || read.containsKey(key)) {
                return value;
            }
            busy = true;
            try {
                if (byApplication(new Throwable().getStackTrace())) {
                    read.put(key, value);
                    order.add(key);
                }
            }
            finally {
                busy = false;
            }
            return value;
        }

        private static boolean byApplication(StackTraceElement[] stack) {
            for (int i = 1; i < stack.length; i++) {
                String c = stack[i].getClassName();
                if (c.equals("java.util.Properties") || c.equals("java.lang.System") || c.equals("java.lang.Integer") || c.equals("java.lang.Long") || c.equals("java.lang.Boolean")) {
                    continue;
                }
                return "app".equals(stack[i].getClassLoaderName());
            }
            return false;
        }
    }

    public static void main(String[] args) throws Exception {
        ClassLoader app = ClassLoader.getSystemClassLoader();
        String jdk = System.getProperty("java.version");
        String vendor = System.getProperty("java.vendor");
        String home = System.getProperty("java.home");
        String classPath = System.getProperty("java.class.path");
        String locale = Locale.getDefault().toLanguageTag();
        String format = Locale.getDefault(Locale.Category.FORMAT).toLanguageTag();
        String display = Locale.getDefault(Locale.Category.DISPLAY).toLanguageTag();
        Path log = args.length > 1 ? Path.of(args[1]) : null;
        Properties original = System.getProperties();
        Recording recording = new Recording();
        recording.putAll(original);
        long mark = log == null ? 0 : Files.size(log);
        Class<?> c;
        System.setProperties(recording);
        try {
            c = Class.forName(args[0], true, app);
        }
        catch (Throwable t) {
            System.setProperties(original);
            Throwable cause = (t instanceof ExceptionInInitializerError && t.getCause() != null) ? t.getCause() : t;
            System.out.println("@observed {\"threw\":\"" + cause.getClass().getName() + "\"}");
            return;
        }
        System.setProperties(original);
        String state = new Dump().of(c);
        if (log == null) {
            System.out.println("@observed {\"jdk\":" + text(jdk) + "," + state + "}");
            return;
        }
        // The classes the initialization initialized: what the JVM logged after the mark, of the class path.
        byte[] logged = Files.readAllBytes(log);
        String after = new String(logged, (int) Math.min(mark, logged.length), (int) Math.max(0, logged.length - mark), StandardCharsets.UTF_8);
        StringBuilder initialized = new StringBuilder();
        List<String> seen = new ArrayList<>();
        Matcher m = INITIALIZING.matcher(after);
        while (m.find()) {
            String internal = m.group(1);
            if (seen.contains(internal)) {
                continue;
            }
            seen.add(internal);
            Class<?> k;
            try {
                k = Class.forName(internal.replace('/', '.'), false, app);
            }
            catch (Throwable t) {
                continue;
            }
            if (k == c || k.getClassLoader() != app || k.isAssignableFrom(c) || k.getName().startsWith(ObservedInitializer.class.getName())) {
                continue;
            }
            initialized.append(initialized.length() == 0 ? "" : ",").append("{\"name\":").append(text(internal)).append(",\"sha256\":")
                    .append(text(sha256(app, internal))).append(',').append(new Dump().of(k)).append('}');
        }
        StringBuilder properties = new StringBuilder();
        for (String key : recording.order) {
            String value = recording.read.get(key);
            properties.append(properties.length() == 0 ? "" : ",").append("{\"name\":").append(text(key)).append(",\"value\":").append(value == null ? "null" : text(value)).append('}');
        }
        StringBuilder entries = new StringBuilder();
        for (String entry : classPath.split(java.io.File.pathSeparator)) {
            entries.append(entries.length() == 0 ? "" : ",").append(text(entry));
        }
        String internal = c.getName().replace('.', '/');
        java.security.CodeSource source = c.getProtectionDomain().getCodeSource();
        String from = source == null || source.getLocation() == null ? null : source.getLocation().toString();
        System.out.println("@observed {\"jdk\":" + text(jdk) + "," + state + ",\"on\":{\"sha256\":" + text(sha256(app, internal))
                + ",\"from\":" + (from == null ? "null" : text(from)) + ",\"classpath\":[" + entries + "],\"vendor\":" + text(vendor)
                + ",\"home\":" + text(home) + ",\"locale\":{\"default\":" + text(locale) + ",\"format\":" + text(format) + ",\"display\":"
                + text(display) + "},\"properties\":[" + properties + "],\"initialized\":[" + initialized + "]}}");
    }

    /** The sha256 of the class file the loader reads of the class, or "" where it reads none. */
    private static String sha256(ClassLoader loader, String internal) throws Exception {
        try (InputStream in = loader.getResourceAsStream(internal + ".class")) {
            if (in == null) {
                return "";
            }
            StringBuilder hex = new StringBuilder();
            for (byte b : MessageDigest.getInstance("SHA-256").digest(in.readAllBytes())) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        }
    }

    /** A JSON string. */
    private static String text(String s) {
        StringBuilder o = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (ch == '"' || ch == '\\') {
                o.append('\\').append(ch);
            }
            else if (ch < 0x20 || ch > 0x7e) {
                o.append(String.format("\\u%04x", (int) ch));
            }
            else {
                o.append(ch);
            }
        }
        return o.append('"').toString();
    }

    /** One class's static state, with the objects it holds numbered from 0. */
    private static final class Dump {
        private final IdentityHashMap<Object, Integer> ids = new IdentityHashMap<>();
        private final List<String> objects = new ArrayList<>();

        /** `"fields":[...],"objects":[...]` of the class's static fields. */
        String of(Class<?> c) {
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
            return "\"fields\":[" + fields + "],\"objects\":[" + String.join(",", objects) + "]";
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

        private String value(Object v) {
            if (v == null) {
                return "null";
            }
            Integer known = ids.get(v);
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
            int id = objects.size();
            ids.put(v, id);
            objects.add(null);
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
            objects.set(id, o.toString());
            return "{\"o\":" + id + "}";
        }
    }
}
