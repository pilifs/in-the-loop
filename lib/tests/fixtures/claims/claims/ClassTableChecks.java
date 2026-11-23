package claims;

import java.util.*;

public final class ClassTableChecks {
    public static boolean genericInterfaces() {
        var interfaces = StartupType.class.getGenericInterfaces();
        if (interfaces.length != 2 || interfaces[1] != StartupMarker.class) return false;
        var first = (java.lang.reflect.ParameterizedType) interfaces[0];
        if (first.getOwnerType() != null || first.getRawType() != StartupPair.class) return false;
        var args = first.getActualTypeArguments();
        if (args.length != 2 || args[0] != String.class || args[1] != Number.class) return false;
        args[0] = Long.class;
        interfaces[0] = Object.class;
        var again = StartupType.class.getGenericInterfaces();
        var reverse = (java.lang.reflect.ParameterizedType) StartupReverse.class.getGenericInterfaces()[1];
        return again != interfaces && again[0] == first && first.getActualTypeArguments()[0] == String.class
            && reverse.getActualTypeArguments()[0] == Number.class && reverse.getActualTypeArguments()[1] == String.class;
    }

    public static boolean nestedArgument() {
        return StartupNested.class.getGenericInterfaces().length == 1;
    }
    static final class Tables {
        private static final Class<?>[] EMPTY = {};
        private static final Map<Class<?>, Class<?>> keys = new IdentityHashMap<>(3);
        private static final Map<Class<?>, Class<?>> inverse = new IdentityHashMap<>(3);
        private static final Map<String, Class<?>> names = new HashMap<>(8);
        private static final Map<String, Class<?>> values = new HashMap<>(8);
        static {
            keys.put(Integer.class, int.class);
            keys.put(Boolean.class, boolean.class);
            keys.put(Void.class, void.class);
            for (Map.Entry<Class<?>, Class<?>> item : keys.entrySet()) {
                inverse.put(item.getValue(), item.getKey());
                register(item.getKey());
            }
            Set<Class<?>> types = new HashSet<>(8);
            types.addAll(keys.values());
            Collections.addAll(types, boolean[].class, int[].class);
            for (Class<?> type : types) {
                values.put(type.getName(), type);
            }
            register(String.class);
        }
        private static void register(Class<?>... types) {
            for (Class<?> type : types) {
                names.put(type.getName(), type);
            }
        }
    }

    // Two unequal keys have the same value. The last inverse write depends on
    // order even though every instruction in the loop and helper has the usual shape.
    static final class Tied {
        private static final Class<?>[] EMPTY = {};
        private static final Map<Class<?>,Class<?>> keys = new IdentityHashMap<>(2);
        private static final Map<Class<?>,Class<?>> inverse = new IdentityHashMap<>(2);
        private static final Map<String,Class<?>> names = new HashMap<>(8);
        static {
            keys.put(Boolean.class, int.class);
            keys.put(Integer.class, int.class);
            for (Map.Entry<Class<?>, Class<?>> item : keys.entrySet()) {
                inverse.put(item.getValue(), item.getKey());
                register(item.getKey());
            }
        }
        private static void register(Class<?>... types) {
            for (Class<?> type : types) names.put(type.getName(), type);
        }
    }

    public static boolean lookups() {
        return Tables.inverse.get(int.class) == Integer.class && Tables.inverse.get(void.class) == Void.class
            && Tables.inverse.get(String.class) == null && Tables.inverse.size() == 3
            && Tables.names.get(new String("java.lang.Boolean")) == Boolean.class
            && Tables.names.get("java.lang.String") == String.class && Tables.names.size() == 4
            && Tables.values.get("void") == void.class && Tables.values.get("[Z") == boolean[].class
            && Tables.values.get("int") == int.class && Tables.values.size() == 5
            && Tables.names.put("java.lang.Boolean", Void.class) == Boolean.class
            && Tables.names.get("java.lang.Boolean") == Void.class;
    }

    public static boolean exportedOrder() { return !Tables.inverse.entrySet().isEmpty(); }
    public static boolean lastWriter() { return Tied.inverse.get(int.class) == Boolean.class; }

    public static boolean classSet() {
        var array = new Class<?>[]{Integer.class, String.class, int.class, void.class};
        var set = Set.of(array);
        array[0] = Object.class;
        return set.size() == 4 && set.contains(Integer.class) && set.contains(int.class)
            && set.contains(void.class) && !set.contains(Object.class);
    }

    public static boolean orderedSet() {
        var set = new LinkedHashSet<String>();
        set.add("one"); set.add("two");
        if (set.add(new String("one"))) return false;
        var iterator = set.iterator();
        if (!iterator.next().equals("one")) return false;
        set.remove("one");
        set.add("one");
        try { iterator.next(); return false; }
        catch (ConcurrentModificationException expected) {
            var next = set.iterator();
            return next.next().equals("two") && next.next().equals("one") && !next.hasNext();
        }
    }

    public static boolean resources() throws Exception {
        var loader = ClassTableChecks.class.getClassLoader();
        String name = "META-INF/ordinal.fixture";
        var urls = loader.getResources(name);
        var other = loader.getResources(name);
        if (!urls.hasMoreElements() || !urls.hasMoreElements() || urls == other) return false;
        var one = urls.nextElement();
        var two = urls.nextElement();
        if (other.nextElement() == one || one == two || urls.hasMoreElements()) return false;
        if (!one.getPath().startsWith("file:/") || !one.getPath().endsWith("/first.jar!/" + name)
                || !two.getPath().endsWith("/second.jar!/" + name)
                || one.getPath() != one.getFile() || one.getPath() != one.getPath()) return false;
        try { urls.nextElement(); return false; }
        catch (NoSuchElementException exhausted) {}
        var connection = one.openConnection();
        if (!(connection instanceof java.net.JarURLConnection) || connection.getURL() != one || one.getUserInfo() != null) return false;
        try (var first = connection.getInputStream(); var second = two.openStream(); var repeat = one.openStream()) {
            byte[] tail = first.read() == 254 ? first.readAllBytes() : new byte[0];
            byte[] full = repeat.readAllBytes();
            if (tail.length != 1 || tail[0] != 17 || first.read() != -1 || second.read() != 34
                    || full.length != 2 || (full[0] & 255) != 254 || full[1] != 17) return false;
            full[0] = 0;
            return second.read() == -1 && !loader.getResources("META-INF/absent.fixture").hasMoreElements();
        }
    }

    private static java.io.InputStream stream(String name) throws Exception {
        return ClassTableChecks.class.getClassLoader().getResources(name).nextElement().openStream();
    }

    public static boolean properties() throws Exception {
        var p = new java.util.Properties();
        try (var in = stream("META-INF/good.fixture")) {
            p.load(in);
            return p.size() == 2 && "second".equals(p.getProperty("Aa"))
                && "12".equals(p.getProperty("BB")) && in.read() == -1;
        }
    }

    public static boolean abandonedRefill() throws Exception {
        try (var in = stream("META-INF/bad.fixture")) {
            try { new java.util.Properties().load(in); return false; }
            catch (IllegalArgumentException malformed) { return in.read() == -1; }
        }
    }

    public static boolean externalRefill() throws Exception {
        try (var in = stream("META-INF/good.fixture")) { return in.read(new byte[8192]) > 0; }
    }

    public static void main(String[] args) throws Exception {
        if (!lookups() || !exportedOrder() || !classSet() || !orderedSet() || !resources()
                || !genericInterfaces() || !nestedArgument() || !properties() || !externalRefill()) throw new AssertionError();
    }
}

interface StartupPair<A, B> {}
interface StartupMarker {}
final class StartupType implements StartupPair<String, Number>, StartupMarker {}
final class StartupReverse implements StartupMarker, StartupPair<Number, String> {}
final class StartupNested implements StartupPair<List<String>, Number> {}
