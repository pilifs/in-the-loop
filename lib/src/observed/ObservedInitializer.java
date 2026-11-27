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
        public int hashCode() {
            all();
            return super.hashCode();
        }

        @Override
        public boolean equals(Object other) {
            all();
            return super.equals(other);
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

    // The tracer breaks on this invocation and its normal return. Snapshot inspection runs afterwards.
    private static Class<?> initializeRoots(String[] args, ClassLoader app, boolean together, int end) throws Exception {
        Class<?> root = Class.forName(args[0], true, app);
        if (together) {
            for (int i = 3; i < end; i++) Class.forName(args[i], true, app);
        }
        return root;
    }

    private static String charsetProfile() {
        var value = java.nio.charset.Charset.defaultCharset();
        Class<?> type = value.getClass();
        return "{\"canonical\":" + text(value.name()) + ",\"implementation\":" + text(type.getName())
                + ",\"bootstrap\":" + (type.getClassLoader() == null) + ",\"module\":" + text(type.getModule().getName())
                + ",\"standardSingleton\":" + (value == StandardCharsets.UTF_8 || value == StandardCharsets.US_ASCII)
                + ",\"fileEncoding\":" + text(System.getProperty("file.encoding")) + ",\"locale\":" + text(System.getenv("LC_ALL"))
                + ",\"vm\":" + text(System.getProperty("java.vm.name")) + ",\"vmVersion\":" + text(System.getProperty("java.vm.version")) + "}";
    }

    static byte[] tablePair(String key, String value) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        for (String s : List.of(key, value)) {
            var buf = java.nio.ByteBuffer.allocate(4 + 2 * s.length()).putInt(s.length());
            for (int i = 0; i < s.length(); i++) buf.putChar(s.charAt(i));
            hash.update(buf.array());
        }
        return hash.digest();
    }

    static String tableDigest(List<byte[]> values) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        for (byte[] value : values) hash.update(value);
        return java.util.HexFormat.of().formatHex(hash.digest());
    }

    static String tableSnapshot(Properties table) throws Exception {
        if (table.getClass() != Properties.class) throw new IllegalStateException("custom system-properties table");
        List<byte[]> pairs = new ArrayList<>();
        table.forEach((k, v) -> {
            if (!(k instanceof String key) || !(v instanceof String value)) throw new IllegalStateException("non-string system property");
            try { pairs.add(tablePair(key, value)); } catch (Exception e) { throw new IllegalStateException(e); }
        });
        String order = tableDigest(pairs);
        pairs.sort(java.util.Arrays::compareUnsigned);
        return "{\"type\":\"java.util.Properties\",\"count\":" + pairs.size() + ",\"orderSha256\":" + text(order)
                + ",\"entriesSha256\":" + text(tableDigest(pairs)) + ",\"hashCode\":" + table.hashCode() + "}";
    }

    public static void main(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("--table-request")) {
            Path dir = Path.of(ObservedInitializer.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            args = Files.readAllLines(dir.resolve("startup.request"), StandardCharsets.UTF_8).toArray(String[]::new);
        }
        boolean charset = false, liveTable = false;
        while (args[0].startsWith("--record-")) {
            if (args[0].equals("--record-charset")) charset = true;
            else if (args[0].equals("--record-methods")) methodOwners = new IdentityHashMap<>();
            else if (args[0].equals("--record-table")) liveTable = true;
            else throw new IllegalArgumentException("unknown recorder option");
            args = java.util.Arrays.copyOfRange(args, 1, args.length);
        }
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
        boolean weakMapValues = args.length >= 3 && args[2].equals("together-weak-map-values");
        boolean together = weakMapValues || args.length >= 3 && args[2].equals("together");
        int rootsEnd = args.length;
        java.util.Set<String> captured = java.util.Set.of();
        if (together && args[rootsEnd - 1].startsWith("--capture-objects=")) {
            String list = args[--rootsEnd].substring("--capture-objects=".length());
            captured = new java.util.TreeSet<>(java.util.Arrays.asList(list.split(",", -1)));
        }
        boolean atRoot = unixRoot();
        boolean emptyEnvironment = emptyEnvironment();
        Properties original = System.getProperties();
        String beforeTable = liveTable ? tableSnapshot(original) : null;
        Recording recording = new Recording();
        if (!liveTable) recording.putAll(original);
        long mark = log == null ? 0 : Files.size(log);
        Class<?> c;
        if (!liveTable) System.setProperties(recording);
        try {
            c = initializeRoots(args, app, together, rootsEnd);
        }
        catch (Throwable t) {
            if (!liveTable) System.setProperties(original);
            Throwable cause = (t instanceof ExceptionInInitializerError && t.getCause() != null) ? t.getCause() : t;
            System.out.println("@observed {\"threw\":\"" + cause.getClass().getName() + "\"}");
            return;
        }
        if (!liveTable) System.setProperties(original);
        // Reflection and serialization can initialize additional classes. The boundary is
        // the return of Class.forName, before the observer inspects any subject fields.
        byte[] logged = log == null ? null : Files.readAllBytes(log);
        String profile = (charset ? ",\"charsetProfile\":" + charsetProfile() : "") + (methodOwners != null ? ",\"reflectiveMembers\":true" : "");
        if (liveTable) {
            if (original != System.getProperties() || !beforeTable.equals(tableSnapshot(original)))
                throw new IllegalStateException("live system-properties table changed during startup");
            profile += ",\"liveTable\":" + beforeTable;
        }
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
        if (!liveTable) changed.addAll(recording.changedFrom(original));
        // Alone, the class is what another initialization's is compared with: described in full.
        if (log == null) {
            System.out.println("@observed {\"jdk\":" + text(jdk) + profile + ",\"fixedProcessors\":" + fixedProcessors()
                    + ",\"emptyEnvironment\":" + (emptyEnvironment && emptyEnvironment()) + ",\"rootWorkingDirectory\":" + (atRoot && unixRoot()) + "," + new Dump(true).of(c) + "}");
            return;
        }
        // The classes the initialization initialized: what the JVM logged after the mark, of the class path.
        Dump dump = new Dump(false);
        dump.weakMapValues = weakMapValues;
        dump.captureObjects = captured;
        String fields = together ? null : dump.fieldsOf(c);
        String after = new String(logged, (int) Math.min(mark, logged.length), (int) Math.max(0, logged.length - mark), StandardCharsets.UTF_8);
        Map<String, Class<?>> members = new LinkedHashMap<>();
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
                // HotSpot's hidden classes have no resolvable binary name or independently addressable statics.
                if (together && !internal.contains("+0x") && !internal.contains("/0x"))
                    throw new IllegalStateException("cannot bind logged class " + internal, t);
                continue;
            }
            if (k == c || k.getClassLoader() != app || k.getName().startsWith(ObservedInitializer.class.getName())) {
                continue;
            }
            // An initializer may have caught another class's initialization failure.
            // An erroneous member cannot be installed as successfully initialized.
            if (together) Class.forName(k.getName(), true, app);
            members.put(internal, k);
        }
        if (together) {
            if (!seen.contains(c.getName().replace('.', '/')))
                throw new IllegalStateException("the root's initialization was absent from the JVM log");
            dump.owners.add(c);
            dump.owners.addAll(members.values());
            fields = dump.fieldsOf(c);
        }
        List<String> additionalRoots = new ArrayList<>();
        for (int i = 3; together && i < rootsEnd; i++) {
            String internal = args[i].replace('.', '/');
            if (!members.containsKey(internal))
                throw new IllegalStateException("additional root missing from the application initialization log: " + internal);
            additionalRoots.add(text(internal));
        }
        StringBuilder initialized = new StringBuilder();
        for (var member : members.entrySet()) {
            String name = member.getKey();
            Class<?> k = member.getValue();
            initialized.append(initialized.length() == 0 ? "" : ",").append("{\"name\":").append(text(name)).append(",\"sha256\":")
                    .append(text(sha256(app, name))).append(',').append(together ? dump.fieldsOf(k) : new Dump(true).of(k)).append('}');
        }
        String state = fields + "," + dump.objects();
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
                + text(display) + "},\"zone\":" + text(zone) + profile + ",\"preinitializeTogether\":" + together
                + ",\"weakMapValues\":" + weakMapValues
                + ",\"captureObjects\":[" + String.join(",", captured.stream().map(ObservedInitializer::text).toList()) + "]"
                + ",\"additionalRoots\":[" + String.join(",", additionalRoots) + "],\"rootWorkingDirectory\":" + (atRoot && unixRoot())
                + ",\"fixedProcessors\":" + fixedProcessors() + ",\"emptyEnvironment\":" + (emptyEnvironment && emptyEnvironment())
                + ",\"utcGregorian\":" + utcGregorian(c) + ",\"properties\":[" + properties + "],\"allProperties\":"
                + (recording.whole == null ? "null" : text(recording.whole)) + ",\"changed\":[" + changes + "],\"initialized\":[" + initialized + "]}}");
    }

    private static boolean emptyEnvironment() {
        try { return System.getenv().isEmpty(); }
        catch (SecurityException unavailable) { return false; }
    }

    private static boolean unixRoot() {
        return java.io.File.separatorChar == '/' && "/".equals(System.getProperty("user.dir"))
                && "/".equals(new java.io.File("").getAbsolutePath())
                && "/".equals(java.nio.file.Path.of("").toAbsolutePath().toString());
    }

    /** A positive, read-only VM option pins this value throughout startup. Read it after capturing the subject. */
    private static Integer fixedProcessors() {
        try {
            var bean = java.lang.management.ManagementFactory.getPlatformMXBean(com.sun.management.HotSpotDiagnosticMXBean.class);
            if (bean == null) return null;
            var option = bean.getVMOption("ActiveProcessorCount");
            int count = Integer.parseInt(option.getValue());
            return !option.isWriteable() && count > 0 && count == Runtime.getRuntime().availableProcessors() ? count : null;
        } catch (RuntimeException | LinkageError unavailable) {
            return null;
        }
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
    static String text(String s) {
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
    private static IdentityHashMap<java.lang.reflect.Method, Dump> methodOwners;
    private static final class MemberCaptureFailure extends RuntimeException {
        MemberCaptureFailure(String reason, Throwable cause) { super(reason, cause); }
    }

    private static String methodRecord(java.lang.reflect.Method method) throws Exception {
        Class<?> declaring = method.getDeclaringClass();
        ClassLoader loader = declaring.getClassLoader();
        if (loader != null && loader != ClassLoader.getSystemClassLoader())
            throw new IllegalStateException("unsupported reflective declaring loader for " + declaring.getName());
        String owner = declaring.getName().replace('.', '/');
        String descriptor = java.lang.invoke.MethodType.methodType(method.getReturnType(), method.getParameterTypes()).descriptorString();
        try (InputStream bytes = declaring.getResourceAsStream("/" + owner + ".class")) {
            if (bytes == null) throw new IllegalStateException("no declaring bytes for " + owner);
            String digest = java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.readAllBytes()));
            String module = declaring.getModule().getName();
            // isAccessible reads the override bit. canAccess also depends on a caller and a receiver.
            return "{\"k\":\"method\",\"owner\":" + text(owner) + ",\"name\":" + text(method.getName())
                    + ",\"descriptor\":" + text(descriptor) + ",\"modifiers\":" + method.getModifiers()
                    + ",\"accessibleOverride\":" + method.isAccessible() + ",\"loader\":" + text(loader == null ? "bootstrap" : "application")
                    + ",\"module\":" + (module == null ? "null" : text(module)) + ",\"declaringSha256\":" + text(digest) + "}";
        }
    }

    private static final class Dump {
        private final IdentityHashMap<Object, Integer> ids = new IdentityHashMap<>();
        private final List<String> objects = new ArrayList<>();
        private final java.util.Set<Class<?>> owners = new java.util.HashSet<>();
        private final boolean describe;
        private boolean weakMapValues;
        private java.util.Set<String> captureObjects = java.util.Set.of();
        private Class<?> owner;

        Dump(boolean describe) {
            this.describe = describe;
        }

        /** `"fields":[...],"objects":[...]` of the class's static fields. */
        String of(Class<?> c) {
            return fieldsOf(c) + "," + objects();
        }

        String objects() {
            return "\"objects\":[" + String.join(",", objects) + "]";
        }

        String fieldsOf(Class<?> c) {
            owner = c;
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
                    if (t instanceof MemberCaptureFailure failure) throw failure;
                    value = unread("a field reflection does not read (" + t.getClass().getName() + ")");
                }
                if (fields.length() > 0) {
                    fields.append(',');
                }
                fields.append("{\"name\":\"").append(f.getName()).append("\",\"value\":").append(value).append('}');
            }
            return "\"fields\":[" + fields + "]";
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

        /** Only the observed enum owns its constants. Another class's copy would lose singleton identity. */
        private List<Class<?>> valueHierarchy(Class<?> type) {
            if (!Modifier.isFinal(type.getModifiers()) || type.isHidden() || type.isArray()) return null;
            List<Class<?>> hierarchy = new ArrayList<>();
            boolean hasField = false;
            for (Class<?> c = type; c != Object.class; c = c.getSuperclass()) {
                if (c == Enum.class && (type == owner || owners.contains(type)) && type.isEnum()) return hierarchy;
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

        private String objectFields(List<Class<?>> hierarchy, Object instance, String kind) throws Exception {
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
                    String held;
                    if (kind.equals("instance") && f.getType() == float.class) {
                        held = "{\"n\":" + Float.floatToRawIntBits((Float) raw) + "}";
                    } else if (kind.equals("instance") && f.getType() == double.class) {
                        held = "{\"n\":" + Double.doubleToRawLongBits((Double) raw) + "}";
                    } else {
                        held = f.getType().isPrimitive() ? primitive(f.getType(), raw) : value(raw);
                    }
                    fields.add("{\"name\":" + text(f.getName()) + ",\"type\":" + text(f.getType().descriptorString()) + ",\"value\":" + held + "}");
                }
                String digest = sha256(c.getClassLoader(), name);
                classes.add("{\"name\":" + text(name) + ",\"sha256\":" + text(digest) + ",\"fields\":[" + String.join(",", fields) + "]}");
            }
            if (instance instanceof Enum<?> constant) {
                // Final bootstrap getters. The checker verifies their bytecode and refuses reads of other Enum fields.
                String digest = sha256(ClassLoader.getPlatformClassLoader(), "java/lang/Enum");
                classes.add("{\"name\":\"java/lang/Enum\",\"sha256\":" + text(digest) + ",\"fields\":["
                        + "{\"name\":\"name\",\"type\":\"Ljava/lang/String;\",\"value\":" + value(constant.name()) + "},"
                        + "{\"name\":\"ordinal\",\"type\":\"I\",\"value\":" + primitive(int.class, constant.ordinal()) + "}]}");
            }
            return "{\"k\":" + text(kind) + ",\"classes\":[" + String.join(",", classes) + "]}";
        }

        /** These instance fields belong to application class files the checker can bind independently. */
        private List<Class<?>> capturedHierarchy(Class<?> type) {
            if (type.isEnum() || type.isHidden() || type.getClassLoader() != ClassLoader.getSystemClassLoader()) return null;
            List<Class<?>> result = new ArrayList<>();
            for (Class<?> c = type; c != Object.class; c = c.getSuperclass()) {
                if (c == null || c.getClassLoader() != ClassLoader.getSystemClassLoader()) return null;
                for (Field f : c.getDeclaredFields()) {
                    if (Modifier.isStatic(f.getModifiers())) continue;
                    if (!f.trySetAccessible()) return null;
                }
                result.add(c);
            }
            return result;
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
            if (methodOwners != null && v instanceof java.lang.reflect.Method method) {
                Dump previous = methodOwners.putIfAbsent(method, this);
                if (previous != null && previous != this)
                    throw new MemberCaptureFailure("reflective object shared across separately captured classes; requires a joint heap", null);
                try {
                    String body = methodRecord(method);
                    int id = objects.size();
                    ids.put(v, id);
                    objects.add(body);
                    return "{\"o\":" + id + "}";
                } catch (Exception e) { throw new MemberCaptureFailure("cannot bind reflective member", e); }
            }
            boolean requested = captureObjects.contains(type.getName());
            boolean atomic = requested && type == java.util.concurrent.atomic.AtomicReference.class;
            List<Class<?>> captured = requested ? capturedHierarchy(type) : null;
            if (atomic || captured != null) {
                // Number the receiver before visiting its fields. An atomic cell and an application
                // object may share a child, or refer back to one another.
                int id = objects.size();
                ids.put(v, id);
                objects.add(null);
                try {
                    String body = atomic
                            ? "{\"k\":\"atomicReference\",\"value\":" + value(((java.util.concurrent.atomic.AtomicReference<?>) v).get()) + "}"
                            : objectFields(captured, v, "instance");
                    objects.set(id, body);
                    return "{\"o\":" + id + "}";
                } catch (Exception e) {
                    throw new IllegalStateException("cannot capture requested instance of " + type.getName(), e);
                }
            }
            boolean map = type == HashMap.class;
            boolean emptyConcurrentMap = type == java.util.concurrent.ConcurrentHashMap.class && ((Map<?, ?>) v).isEmpty();
            // GC can remove mappings, which preserves the all-null value invariant. Keep the
            // map's identity but neither its cardinality nor strong references to its keys.
            boolean nullValues = weakMapValues && type == java.util.WeakHashMap.class
                    && ((Map<?, ?>) v).values().stream().allMatch(java.util.Objects::isNull);
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
                    String held = objectFields(hierarchy, v, "value");
                    int id = objects.size();
                    ids.put(v, id);
                    objects.add(held);
                    return "{\"o\":" + id + "}";
                }
                catch (Exception e) { return unheld("an unreadable value of " + nameOf(type), v); }
            }
            if (!(v instanceof String) && !(v instanceof Class) && !map && !emptyConcurrentMap && !nullValues && !type.isArray()) {
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
            else if (nullValues) {
                o.append("{\"k\":\"weakMap\",\"allValuesNull\":true}");
            }
            else if (map) {
                o.append("{\"k\":").append(text(requested ? "lookupMap" : "map")).append(",\"entries\":[");
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
