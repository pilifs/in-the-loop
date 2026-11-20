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
 * the JDK, the default locale and time zone, each system property the class path's code read with the value it had
 * (and the first class of it that read the properties as a whole, if one did), and each class of the class path the
 * initialization initialized besides the class, its supertypes among them, with its class file's sha256 and its
 * static state as it was then, and each setting of the JDK the initialization changed (the default locale and time
 * zone, a system property), read again after it ("changed"). Without one, the class's state alone: what a class
 * another initialization initialized is compared with, initialized first thing in a JVM of its own. In both, each
 * value of such a class the observation does not hold is also described in full ("d", see Describe), or said why it
 * is not ("why"), so that a write into it shows.
 */
public final class ObservedInitializer {
    private static final Pattern INITIALIZING = Pattern.compile("Initializing '([^']+)'");

    private ObservedInitializer() {
    }

    /**
     * The system properties, recording each one the class path's code read and the value it had (null where it was
     * not set): a read whose caller, past System.getProperty, the map's own methods and the getters
     * Integer.getInteger, Long.getLong and Boolean.getBoolean, is a class the application class loader loaded. A key
     * read through the map (get, getOrDefault, containsKey) is recorded as one read through getProperty is; a read of
     * the properties as a whole (their keys, entries or values, a copy, a listing) names the class that made it,
     * since the observation does not list every property. The JDK's reads of its own configuration (as it opens a
     * JAR, or the first time a JDK class is used) are not the initializer's: the check takes the JDK at its defaults
     * throughout, and the default locale and time zone, which it reads that way, are said beside.
     */
    private static final class Recording extends Properties {
        final Map<String, String> read = new LinkedHashMap<>();
        final List<String> order = new ArrayList<>();
        /** The first class of the class path that read the properties as a whole, or null. */
        String whole;
        private boolean busy;

        @Override
        public String getProperty(String key) {
            String value = super.getProperty(key);
            note(key, value);
            return value;
        }

        @Override
        public Object get(Object key) {
            Object value = super.get(key);
            keyed(key, value);
            return value;
        }

        @Override
        public Object getOrDefault(Object key, Object otherwise) {
            keyed(key, super.get(key));
            return super.getOrDefault(key, otherwise);
        }

        @Override
        public boolean containsKey(Object key) {
            keyed(key, super.get(key));
            return super.containsKey(key);
        }

        @Override
        public java.util.Set<Object> keySet() {
            all();
            return super.keySet();
        }

        @Override
        public java.util.Set<Map.Entry<Object, Object>> entrySet() {
            all();
            return super.entrySet();
        }

        @Override
        public java.util.Collection<Object> values() {
            all();
            return super.values();
        }

        @Override
        public java.util.Enumeration<Object> keys() {
            all();
            return super.keys();
        }

        @Override
        public java.util.Enumeration<Object> elements() {
            all();
            return super.elements();
        }

        @Override
        public java.util.Enumeration<?> propertyNames() {
            all();
            return super.propertyNames();
        }

        @Override
        public java.util.Set<String> stringPropertyNames() {
            all();
            return super.stringPropertyNames();
        }

        @Override
        public void forEach(java.util.function.BiConsumer<? super Object, ? super Object> action) {
            all();
            super.forEach(action);
        }

        @Override
        public boolean contains(Object value) {
            all();
            return super.contains(value);
        }

        @Override
        public boolean containsValue(Object value) {
            all();
            return super.containsValue(value);
        }

        @Override
        public int size() {
            all();
            return super.size();
        }

        @Override
        public boolean isEmpty() {
            all();
            return super.isEmpty();
        }

        @Override
        public Object clone() {
            all();
            return super.clone();
        }

        @Override
        public String toString() {
            all();
            return super.toString();
        }

        @Override
        public void list(java.io.PrintStream out) {
            all();
            super.list(out);
        }

        @Override
        public void list(java.io.PrintWriter out) {
            all();
            super.list(out);
        }

        @Override
        public void store(java.io.Writer writer, String comments) throws java.io.IOException {
            all();
            super.store(writer, comments);
        }

        @Override
        public void store(java.io.OutputStream out, String comments) throws java.io.IOException {
            all();
            super.store(out, comments);
        }

        @Override
        public void storeToXML(java.io.OutputStream os, String comment) throws java.io.IOException {
            all();
            super.storeToXML(os, comment);
        }

        @Override
        public void storeToXML(java.io.OutputStream os, String comment, String encoding) throws java.io.IOException {
            all();
            super.storeToXML(os, comment, encoding);
        }

        @Override
        public void storeToXML(java.io.OutputStream os, String comment, java.nio.charset.Charset charset) throws java.io.IOException {
            all();
            super.storeToXML(os, comment, charset);
        }

        private void keyed(Object key, Object value) {
            if (key instanceof String k) {
                note(k, value == null ? null : value.toString());
            }
            else {
                all();
            }
        }

        private void note(String key, String value) {
            if (busy || read.containsKey(key)) {
                return;
            }
            busy = true;
            try {
                if (reader(new Throwable().getStackTrace()) != null) {
                    read.put(key, value);
                    order.add(key);
                }
            }
            finally {
                busy = false;
            }
        }

        private void all() {
            if (busy || whole != null) {
                return;
            }
            busy = true;
            try {
                whole = reader(new Throwable().getStackTrace());
            }
            finally {
                busy = false;
            }
        }

        /** Each system property the initialization set, removed or changed, said with its value before and after. */
        List<String> changedFrom(Properties original) {
            busy = true;
            try {
                java.util.TreeSet<String> keys = new java.util.TreeSet<>();
                for (Object k : super.keySet()) {
                    keys.add(String.valueOf(k));
                }
                for (Object k : original.keySet()) {
                    keys.add(String.valueOf(k));
                }
                List<String> changed = new ArrayList<>();
                for (String k : keys) {
                    Object before = original.get(k);
                    Object after = super.get(k);
                    if (!java.util.Objects.equals(before, after)) {
                        changed.add("the system property " + k + ", from " + said(before) + " to " + said(after));
                    }
                }
                return changed;
            }
            finally {
                busy = false;
            }
        }

        private static String said(Object value) {
            return value == null ? "not set" : "\"" + value + "\"";
        }

        /** The class of the class path that made the read, past the map and the JDK's getters, or null. */
        private static String reader(StackTraceElement[] stack) {
            for (StackTraceElement frame : stack) {
                String c = frame.getClassName();
                if (c.equals(Recording.class.getName()) || c.equals("java.util.Properties") || c.equals("java.util.Hashtable") || c.equals("java.lang.System") || c.equals("java.lang.Integer") || c.equals("java.lang.Long") || c.equals("java.lang.Boolean")) {
                    continue;
                }
                return "app".equals(frame.getClassLoaderName()) ? c : null;
            }
            return null;
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
        String zone = java.util.TimeZone.getDefault().getID();
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
        // The JDK's settings the initialization changed, read again after it: the check runs what follows under the
        // ones before it.
        List<String> changed = new ArrayList<>();
        String[][] settings = {
            {"the default locale", locale, Locale.getDefault().toLanguageTag()},
            {"the default locale for formatting", format, Locale.getDefault(Locale.Category.FORMAT).toLanguageTag()},
            {"the default locale for display", display, Locale.getDefault(Locale.Category.DISPLAY).toLanguageTag()},
            {"the default time zone", zone, java.util.TimeZone.getDefault().getID()},
        };
        for (String[] s : settings) {
            if (!s[1].equals(s[2])) {
                changed.add(s[0] + ", from " + s[1] + " to " + s[2]);
            }
        }
        changed.addAll(recording.changedFrom(original));
        // Alone, the class is what another initialization's is compared with: described in full.
        String state = new Dump(log == null).of(c);
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
            if (k == c || k.getClassLoader() != app || k.getName().startsWith(ObservedInitializer.class.getName())) {
                continue;
            }
            initialized.append(initialized.length() == 0 ? "" : ",").append("{\"name\":").append(text(internal)).append(",\"sha256\":")
                    .append(text(sha256(app, internal))).append(',').append(new Dump(true).of(k)).append('}');
        }
        StringBuilder properties = new StringBuilder();
        for (String key : recording.order) {
            String value = recording.read.get(key);
            properties.append(properties.length() == 0 ? "" : ",").append("{\"name\":").append(text(key)).append(",\"value\":").append(value == null ? "null" : text(value)).append('}');
        }
        StringBuilder changes = new StringBuilder();
        for (String change : changed) {
            changes.append(changes.length() == 0 ? "" : ",").append(text(change));
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
                + text(display) + "},\"zone\":" + text(zone) + ",\"utcGregorian\":" + utcGregorian(c) + ",\"properties\":[" + properties + "],\"allProperties\":"
                + (recording.whole == null ? "null" : text(recording.whole)) + ",\"changed\":[" + changes + "],\"initialized\":[" + initialized + "]}}");
    }

    /** A class with calendar state can qualify the factory environment for later calls.
     * The initialized application's own objects have already been recorded. */
    private static boolean utcGregorian(Class<?> observed) {
        try {
            if (java.util.Arrays.stream(observed.getDeclaredFields()).noneMatch(f -> Modifier.isStatic(f.getModifiers())
                    && (f.getType() == java.util.Calendar.class || f.getType() == java.util.TimeZone.class))) return false;
            if (System.getProperty("java.locale.providers") != null || System.getProperty("java.time.zone.DefaultZoneRulesProvider") != null) return false;
            ClassLoader loader = ClassLoader.getSystemClassLoader();
            for (String service : new String[]{"sun.util.spi.CalendarProvider", "java.util.spi.CalendarDataProvider", "java.time.zone.ZoneRulesProvider"}) {
                if (loader.getResources("META-INF/services/" + service).hasMoreElements()) return false;
            }
            java.util.TimeZone zone = java.util.TimeZone.getTimeZone("UTC");
            java.util.TimeZone defaultZone = java.util.TimeZone.getDefault();
            java.util.Calendar calendar = java.util.Calendar.getInstance();
            java.util.Calendar explicit = java.util.Calendar.getInstance(zone);
            if (zone == java.util.TimeZone.getTimeZone("UTC") || defaultZone == java.util.TimeZone.getDefault()
                    || calendar == explicit || calendar == java.util.Calendar.getInstance()) return false;
            for (java.util.Calendar c : new java.util.Calendar[]{calendar, explicit}) {
                if (c.getClass() != java.util.GregorianCalendar.class || !c.isLenient() || c.get(java.util.Calendar.ERA) != java.util.GregorianCalendar.AD
                        || ((java.util.GregorianCalendar)c).getGregorianChange().getTime() != -12219292800000L) return false;
            }
            for (java.util.TimeZone z : new java.util.TimeZone[]{zone, defaultZone, calendar.getTimeZone(), explicit.getTimeZone()}) {
                if (!z.getClass().getName().equals("sun.util.calendar.ZoneInfo") || !(z.getID().equals("UTC") || z.getID().equals("Etc/UTC"))
                        || z.getRawOffset() != 0 || z.useDaylightTime() || !z.toZoneId().getRules().isFixedOffset()) return false;
            }
            return true;
        }
        catch (java.io.IOException | RuntimeException | LinkageError | java.util.ServiceConfigurationError e) { return false; }
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

    /**
     * One class's static state, with the objects it holds numbered from 0; where `describe`, each value not held is
     * described in full beside what it is said to be (Describe).
     */
    private static final class Dump {
        private final IdentityHashMap<Object, Integer> ids = new IdentityHashMap<>();
        private final List<String> objects = new ArrayList<>();
        private final boolean describe;

        Dump(boolean describe) {
            this.describe = describe;
        }

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
                    value = unread("a field reflection does not read (" + t.getClass().getName() + ")");
                }
                if (fields.length() > 0) {
                    fields.append(',');
                }
                fields.append("{\"name\":\"").append(f.getName()).append("\",\"value\":").append(value).append('}');
            }
            return "\"fields\":[" + fields + "],\"objects\":[" + String.join(",", objects) + "]";
        }

        /** A value not held: what it is, and where describing, its description or why there is none. */
        private String unheld(String what, Object v) {
            if (!describe) {
                return "{\"u\":" + text(what) + "}";
            }
            try {
                return "{\"u\":" + text(what) + ",\"d\":" + text(new Describe().of(v)) + "}";
            }
            catch (Describe.Undescribed e) {
                return "{\"u\":" + text(what) + ",\"why\":" + text(e.getMessage()) + "}";
            }
        }

        /** A value reflection did not read. */
        private String unread(String what) {
            return describe ? "{\"u\":" + text(what) + ",\"why\":\"reflection does not read it\"}" : "{\"u\":" + text(what) + "}";
        }

        /**
         * A class's name as two JVMs give it alike: a hidden class (a lambda's) is named by what it was defined from,
         * without the address the JVM appends (`R$$Lambda/0x...`, `R$$Lambda$14/0x...`), which differs from one run
         * to the next for the same lambda.
         */
        static String nameOf(Class<?> type) {
            String name = type.getName();
            if (!type.isHidden()) {
                return name;
            }
            int lambda = name.indexOf("$$Lambda");
            return lambda >= 0 ? name.substring(0, lambda) + "$$Lambda" : name.substring(0, name.lastIndexOf('/') < 0 ? name.length() : name.lastIndexOf('/'));
        }

        private String primitive(Class<?> type, Object boxed) {
            if (type == boolean.class) {
                return "{\"n\":" + (((Boolean) boxed) ? 1 : 0) + "}";
            }
            if (type == char.class) {
                return "{\"n\":" + (int) ((Character) boxed) + "}";
            }
            if (type == float.class || type == double.class) {
                return unheld("a " + type.getName(), boxed);
            }
            return "{\"n\":" + ((Number) boxed).longValue() + "}";
        }

        /** A final application value with only final integral and String fields all the
         * way to Object. Read the complete layout without invoking any application code. */
        private List<Class<?>> valueHierarchy(Class<?> type) {
            if (!Modifier.isFinal(type.getModifiers()) || type.isHidden() || type.isArray()) return null;
            List<Class<?>> hierarchy = new ArrayList<>();
            boolean hasField = false;
            for (Class<?> c = type; c != Object.class; c = c.getSuperclass()) {
                if (c == null || c.getClassLoader() != ClassLoader.getSystemClassLoader()) return null;
                hierarchy.add(c);
                for (Field f : c.getDeclaredFields()) {
                    if (Modifier.isStatic(f.getModifiers())) continue;
                    Class<?> t = f.getType();
                    if (!Modifier.isFinal(f.getModifiers()) || (!t.isPrimitive() && t != String.class)
                            || t == float.class || t == double.class || !f.trySetAccessible()) return null;
                    hasField = true;
                }
            }
            return hasField ? hierarchy : null;
        }

        private String frozenValue(List<Class<?>> hierarchy, Object instance) throws Exception {
            List<String> classes = new ArrayList<>();
            for (Class<?> c : hierarchy) {
                String name = c.getName().replace('.', '/');
                List<String> fields = new ArrayList<>();
                Field[] declared = c.getDeclaredFields();
                java.util.Arrays.sort(declared, java.util.Comparator.comparing(Field::getName).thenComparing(f -> f.getType().descriptorString()));
                for (Field f : declared) {
                    if (Modifier.isStatic(f.getModifiers())) continue;
                    f.setAccessible(true);
                    Object raw = f.get(instance);
                    String held = f.getType().isPrimitive() ? primitive(f.getType(), raw) : value(raw);
                    fields.add("{\"name\":" + text(f.getName()) + ",\"type\":" + text(f.getType().descriptorString()) + ",\"value\":" + held + "}");
                }
                String digest = sha256(c.getClassLoader(), name);
                classes.add("{\"name\":" + text(name) + ",\"sha256\":" + text(digest) + ",\"fields\":[" + String.join(",", fields) + "]}");
            }
            return "{\"k\":\"value\",\"classes\":[" + String.join(",", classes) + "]}";
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
            boolean emptyConcurrentMap = type == java.util.concurrent.ConcurrentHashMap.class && ((Map<?, ?>) v).isEmpty();
            if (map) {
                for (Object key : ((Map<?, ?>) v).keySet()) {
                    if (key != null && !(key instanceof String)) {
                        return unheld("a java.util.HashMap with a key of " + nameOf(key.getClass()), v);
                    }
                }
            }
            if (type.isArray() && (type.getComponentType() == float.class || type.getComponentType() == double.class)) {
                return unheld("an array of " + type.getComponentType().getName(), v);
            }
            List<Class<?>> hierarchy = valueHierarchy(type);
            if (hierarchy != null) {
                try {
                    String held = frozenValue(hierarchy, v);
                    int id = objects.size();
                    ids.put(v, id);
                    objects.add(held);
                    return "{\"o\":" + id + "}";
                }
                catch (Exception e) { return unheld("an unreadable value of " + nameOf(type), v); }
            }
            if (!(v instanceof String) && !(v instanceof Class) && !map && !emptyConcurrentMap && !type.isArray()) {
                return unheld("an object of " + nameOf(type), v);
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
            else if (emptyConcurrentMap) {
                o.append("{\"k\":\"concurrentMap\",\"entries\":[]}");
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
    /**
     * A value the observation does not hold, described in full: what a class another class's initialization
     * initialized is compared by, after that initialization and alone, so that a write into an object it holds, or
     * a lambda put in place of another of its class, shows. A String, a boxed primitive (a float or double by its
     * bits) and a Class by what they are; an array by its cells; a lambda by the method it calls (read from its
     * class's constant pool) and the values it captured; an object of a class of the application by every field its
     * classes declare, and by what its first superclass of the JDK holds (Enum its name, a Reference its referent, a
     * ReentrantLock whether it is held, the abstract collections nothing); an object of the JDK by its contents
     * through the class's public methods (a map's entries and a collection's elements, sorted where the class keeps
     * no order of its own, a ResourceBundle's keys and values, a Pattern's source and flags, an atomic's value) or
     * by its value where it is one (a Locale, a URI, a java.time value). A ReferenceQueue is said as one: what it
     * holds is the collector's. Anything else is not described (Undescribed, with why), nor is a value past
     * LIMIT. An object met again on its own path is said as a reference back to it.
     */
    private static final class Describe {
        private static final int LIMIT = 200_000;
        private static final List<Class<?>> STATELESS = List.of(Object.class, Number.class, Record.class, java.util.AbstractMap.class, java.util.AbstractCollection.class,
                java.util.AbstractList.class, java.util.AbstractSequentialList.class, java.util.AbstractSet.class, java.util.AbstractQueue.class);
        private final IdentityHashMap<Object, Boolean> path = new IdentityHashMap<>();
        private int count;

        static final class Undescribed extends Exception {
            Undescribed(String why) {
                super(why, null, false, false);
            }
        }

        String of(Object v) throws Undescribed {
            if (++count > LIMIT) {
                throw new Undescribed("it holds more than " + LIMIT + " values");
            }
            if (v == null) {
                return "null";
            }
            if (v instanceof String s) {
                return text(s);
            }
            if (v instanceof Float f) {
                return "float 0x" + Integer.toHexString(Float.floatToRawIntBits(f));
            }
            if (v instanceof Double d) {
                return "double 0x" + Long.toHexString(Double.doubleToRawLongBits(d));
            }
            if (v instanceof Character ch) {
                return "char " + (int) ch;
            }
            if (v instanceof Integer || v instanceof Long || v instanceof Short || v instanceof Byte || v instanceof Boolean) {
                return v.getClass().getSimpleName() + " " + v;
            }
            if (v instanceof Class<?> k) {
                return "class " + (k.isArray() ? k.descriptorString() : Dump.nameOf(k));
            }
            Class<?> type = v.getClass();
            if (path.containsKey(v)) {
                return "^" + Dump.nameOf(type);
            }
            path.put(v, Boolean.TRUE);
            try {
                if (type.isArray()) {
                    StringBuilder o = new StringBuilder(type.getComponentType().descriptorString()).append('[');
                    for (int i = 0; i < Array.getLength(v); i++) {
                        o.append(i == 0 ? "" : ",").append(of(Array.get(v, i)));
                    }
                    return o.append(']').toString();
                }
                if (type.isHidden()) {
                    return hidden(v, type);
                }
                if (application(type)) {
                    return fields(v, type);
                }
                return jdk(v, type);
            }
            finally {
                path.remove(v);
            }
        }

        private static boolean application(Class<?> type) {
            ClassLoader loader = type.getClassLoader();
            return loader != null && loader != ClassLoader.getPlatformClassLoader();
        }

        /** The value of each instance field `type` declares, by name. */
        private String declared(Object v, Class<?> type) throws Undescribed {
            StringBuilder o = new StringBuilder();
            for (Field f : type.getDeclaredFields()) {
                if (Modifier.isStatic(f.getModifiers())) {
                    continue;
                }
                Object value;
                try {
                    f.setAccessible(true);
                    value = f.get(v);
                }
                catch (Throwable t) {
                    throw new Undescribed("reflection does not read " + Dump.nameOf(type) + "." + f.getName() + " (" + t.getClass().getName() + ")");
                }
                o.append(o.length() == 0 ? "" : ",").append(f.getName()).append('=').append(of(value));
            }
            return o.toString();
        }

        /** An object of the application: the fields each of its classes declares, then its JDK superclass's part. */
        private String fields(Object v, Class<?> type) throws Undescribed {
            StringBuilder o = new StringBuilder(Dump.nameOf(type)).append('{');
            Class<?> k = type;
            for (; k != null && application(k); k = k.getSuperclass()) {
                o.append(k == type ? "" : ";" + Dump.nameOf(k) + ":").append(declared(v, k));
            }
            o.append('}');
            if (k == null || STATELESS.contains(k)) {
                return o.toString();
            }
            if (k == Enum.class) {
                return o.append('.').append(((Enum<?>) v).name()).toString();
            }
            if (v instanceof java.lang.ref.Reference<?> r && !overridden(type, "get")) {
                return o.append("->").append(of(r.get())).toString();
            }
            if (v instanceof java.util.concurrent.locks.ReentrantLock lock && !overridden(type, "isLocked")) {
                return o.append(lock.isLocked() ? " held" : " not held").append(lock.hasQueuedThreads() ? ", awaited" : "").toString();
            }
            if (v instanceof Map<?, ?> m && !overridden(type, "entrySet")) {
                return o.append(entries(m)).toString();
            }
            if (v instanceof java.util.Collection<?> c && !overridden(type, "iterator")) {
                return o.append(elements(c)).toString();
            }
            throw new Undescribed("an object of " + Dump.nameOf(type) + ", which extends " + k.getName() + ", whose state the observer does not read");
        }

        /** Whether a class of the application declares the public method of `type` named so, with no parameters. */
        private static boolean overridden(Class<?> type, String name) {
            try {
                return application(type.getMethod(name).getDeclaringClass());
            }
            catch (NoSuchMethodException e) {
                return true;
            }
        }

        /** A lambda (or another hidden class): the methods its class calls, and the values it captured. */
        private String hidden(Object v, Class<?> type) throws Undescribed {
            StringBuilder o = new StringBuilder(Dump.nameOf(type)).append(" calling ");
            List<String> calls = new ArrayList<>();
            try {
                Object pool = Pool.GET.invoke(Pool.ACCESS, type);
                int size = (int) Pool.SIZE.invoke(pool);
                for (int i = 1; i < size; i++) {
                    if (!String.valueOf(Pool.TAG.invoke(pool, i)).endsWith("METHODREF")) {
                        continue;
                    }
                    String[] member = (String[]) Pool.MEMBER.invoke(pool, i);
                    String call = member[0] + "." + member[1] + member[2];
                    if (!call.equals("java/lang/Object.<init>()V")) {
                        calls.add(call);
                    }
                }
            }
            catch (Throwable t) {
                throw new Undescribed("which method " + Dump.nameOf(type) + " calls is not read (its constant pool: " + t.getClass().getName() + ")");
            }
            return o.append(String.join(" ", calls)).append('{').append(declared(v, type)).append('}').toString();
        }

        /** An object of the JDK, by what its public methods say it holds. */
        private String jdk(Object v, Class<?> type) throws Undescribed {
            String name = Dump.nameOf(type);
            if (v instanceof Enum<?> e) {
                return name + "." + e.name();
            }
            if (v instanceof Map<?, ?> m) {
                return name + entries(m);
            }
            if (v instanceof java.util.Collection<?> c) {
                return name + elements(c);
            }
            if (v instanceof java.lang.ref.Reference<?> r) {
                return name + "->" + of(r.get());
            }
            if (v instanceof java.lang.ref.ReferenceQueue<?>) {
                return name;
            }
            if (v instanceof java.util.regex.Pattern p) {
                return name + "{" + text(p.pattern()) + "," + p.flags() + "}";
            }
            if (v instanceof java.util.ResourceBundle b) {
                StringBuilder o = new StringBuilder(name).append('{').append(b.getLocale()).append(';');
                boolean first = true;
                for (String key : new java.util.TreeSet<>(b.keySet())) {
                    o.append(first ? "" : ",").append(text(key)).append('=').append(of(b.getObject(key)));
                    first = false;
                }
                return o.append('}').toString();
            }
            if (v instanceof java.util.concurrent.atomic.AtomicReference<?> a) {
                return name + "{" + of(a.get()) + "}";
            }
            if (v instanceof java.util.Optional<?> a) {
                return name + "{" + of(a.orElse(null)) + "}";
            }
            if (v instanceof java.util.concurrent.atomic.AtomicInteger || v instanceof java.util.concurrent.atomic.AtomicLong || v instanceof java.util.concurrent.atomic.AtomicBoolean
                    || v instanceof java.math.BigInteger || v instanceof java.math.BigDecimal || v instanceof Locale || v instanceof java.nio.charset.Charset
                    || v instanceof java.util.UUID || v instanceof java.net.URI || v instanceof java.net.URL || v instanceof java.io.File || v instanceof Path
                    || v instanceof java.time.temporal.TemporalAccessor || v instanceof java.time.temporal.TemporalAmount || v instanceof java.time.ZoneId) {
                return name + "{" + text(v.toString()) + "}";
            }
            throw new Undescribed("an object of " + name + ", a class of the JDK the observer does not describe");
        }

        /** A map's entries: in its order where it keeps one (sorted, linked), sorted otherwise. */
        private String entries(Map<?, ?> m) throws Undescribed {
            List<String> each = new ArrayList<>();
            for (Map.Entry<?, ?> e : m.entrySet()) {
                each.add(of(e.getKey()) + "=" + of(e.getValue()));
            }
            if (!(m instanceof java.util.SortedMap) && !(m instanceof java.util.LinkedHashMap)) {
                java.util.Collections.sort(each);
            }
            return "{" + String.join(",", each) + "}";
        }

        /** A collection's elements: in its order where it keeps one (a list, a deque, sorted, linked), sorted otherwise. */
        private String elements(java.util.Collection<?> c) throws Undescribed {
            List<String> each = new ArrayList<>();
            for (Object e : c) {
                each.add(of(e));
            }
            if (!(c instanceof List) && !(c instanceof java.util.Deque) && !(c instanceof java.util.SortedSet) && !(c instanceof java.util.LinkedHashSet)) {
                java.util.Collections.sort(each);
            }
            return "[" + String.join(",", each) + "]";
        }
    }

    /**
     * A class's constant pool, through the JDK's internal access, which the observer's JVM is given
     * (--add-exports java.base/jdk.internal.access and jdk.internal.reflect): the only place a lambda says which
     * method it calls.
     */
    private static final class Pool {
        static final Object ACCESS;
        static final java.lang.reflect.Method GET;
        static final java.lang.reflect.Method SIZE;
        static final java.lang.reflect.Method TAG;
        static final java.lang.reflect.Method MEMBER;

        static {
            Object access = null;
            java.lang.reflect.Method get = null;
            java.lang.reflect.Method size = null;
            java.lang.reflect.Method tag = null;
            java.lang.reflect.Method member = null;
            try {
                access = Class.forName("jdk.internal.access.SharedSecrets").getMethod("getJavaLangAccess").invoke(null);
                get = Class.forName("jdk.internal.access.JavaLangAccess").getMethod("getConstantPool", Class.class);
                Class<?> pool = Class.forName("jdk.internal.reflect.ConstantPool");
                size = pool.getMethod("getSize");
                tag = pool.getMethod("getTagAt", int.class);
                member = pool.getMethod("getMemberRefInfoAt", int.class);
            }
            catch (Throwable t) {
                // Left null: a lambda is then not described.
            }
            ACCESS = access;
            GET = get;
            SIZE = size;
            TAG = tag;
            MEMBER = member;
        }
    }
}
