import java.lang.reflect.Array;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;

/**
 * The JVM's side of the benchmark's groups 2 and 3 (lib/benchmark/corpus.json). Each case's claim is written out
 * here in Java, apart from the tool: not through the harness the tool generates, nor its expression language, so a
 * claim the tool states wrongly disagrees with this one. The versions are the compiled source trees under
 * lib/benchmark/src, one class loader each.
 *
 * Usage: {@code java Reference.java CLASSES REQUESTS}, where CLASSES holds a directory of classes per version
 * (broken, fixed, v1, v2, v3), and REQUESTS has a line per question:
 * <ul>
 * <li>{@code list}: print every case's id with its parameters;</li>
 * <li>{@code ID TAB check TAB ARGUMENTS}: does this input refute the claim? It prints {@code ID TAB refuted TAB
 * what happened}, {@code ID TAB holds}, or {@code ID TAB outside} for an input outside the claim's domain (its
 * assumption, its intended change, or a record its constructor refuses);</li>
 * <li>{@code ID TAB search TAB N}: look for a refuting input among boundary values and N inputs drawn with a fixed
 * seed. It prints {@code ID TAB refuted TAB ARGUMENTS TAB what happened}, or {@code ID TAB held TAB K} for K inputs
 * in the domain, none refuting it.</li>
 * </ul>
 * ARGUMENTS are flat and separated by {@code ;}, in the order the tool lists a witness's inputs: a record by its
 * components, an array as {@code [1,2]}, a char as its code unit, a boolean as {@code true} or {@code false}.
 *
 * A property holds on an input when the method returns and the assertion holds, or throws what its throws clause
 * says. A regression holds on an input when both versions return equal results and leave equal arrays, or throw the
 * same class, unless the input is one the change is meant to affect.
 */
public class Reference {
    static final String OUTSIDE = "\0outside";
    static Path classes;
    static final Map<String, URLClassLoader> LOADERS = new HashMap<>();

    interface Claim {
        String refute(Object[] in) throws Exception;
    }

    record Case(String id, String[] params, Claim claim) {
    }

    record Outcome(Object value, Throwable thrown, String text) {
    }

    public static void main(String[] args) throws Exception {
        classes = Path.of(args[0]);
        Map<String, Case> cases = new LinkedHashMap<>();
        for (Case c : cases()) cases.put(c.id(), c);
        for (String line : Files.readAllLines(Path.of(args[1]))) {
            if (line.isBlank()) continue;
            String[] field = line.split("\t", -1);
            if (field[0].equals("list")) {
                for (Case c : cases.values()) System.out.println(c.id() + "\t" + String.join(",", c.params()));
                continue;
            }
            Case c = cases.get(field[0]);
            if (c == null) {
                System.out.println(field[0] + "\terror\tno such case");
                continue;
            }
            try {
                if (field[1].equals("check")) {
                    String r = c.claim().refute(parse(c.params(), field[2]));
                    System.out.println(c.id() + (r == null ? "\tholds" : r.equals(OUTSIDE) ? "\toutside" : "\trefuted\t" + r));
                } else {
                    System.out.println(search(c, Integer.parseInt(field[2])));
                }
            } catch (Exception e) {
                System.out.println(c.id() + "\terror\t" + e);
            }
        }
    }

    // The cases, by the ids corpus.json gives them.

    static List<Case> cases() {
        String[] ii = {"int", "int"};
        return List.of(
            new Case("real/midpoint/broken-property", ii, midpoint("broken")),
            new Case("real/midpoint/fixed-property", ii, midpoint("fixed")),
            new Case("real/midpoint/fix-confined", ii, regression("broken", "fixed", "bench.real.Midpoint", "midpoint",
                in -> (int) in[0] + (int) in[1] < 0)),
            new Case("real/midpoint/search-within-bound", new String[] {"int[]", "int"},
                regression("broken", "fixed", "bench.real.Midpoint", "search", in -> false)),
            new Case("real/bucket/broken-property", ii, bucket("broken")),
            new Case("real/bucket/fixed-property", ii, bucket("fixed")),
            new Case("real/bucket/fix-confined", ii, regression("broken", "fixed", "bench.real.Bucket", "index", in -> (int) in[0] < 0)),
            new Case("real/oddity/broken-property", new String[] {"int"}, oddity("broken")),
            new Case("real/oddity/fixed-property", new String[] {"int"}, oddity("fixed")),
            new Case("real/oddity/fix-confined", new String[] {"int"}, regression("broken", "fixed", "bench.real.Oddity", "isOdd", in -> (int) in[0] < 0)),
            new Case("real/checksum/broken-property", new String[] {"byte[]", "int", "int"}, checksum("broken")),
            new Case("real/checksum/fixed-property", new String[] {"byte[]", "int", "int"}, checksum("fixed")),
            new Case("real/checksum/fix-confined", new String[] {"byte[]", "int", "int"}, regression("broken", "fixed", "bench.real.Checksum", "sum",
                in -> (int) in[1] > 0 && (int) in[2] > 0 && (int) in[1] + (int) in[2] < 0)),
            new Case("held/saturating", ii, regression("v1", "v2", "bench.held.Saturating", "add", in -> false)),
            new Case("held/average/bits", ii, regression("v1", "v2", "bench.held.Average", "mean", in -> false)),
            new Case("held/average/unsigned-shift", ii, regression("v1", "v3", "bench.held.Average", "mean", in -> false)),
            new Case("held/floor-mod/wide-modulus", ii, regression("v1", "v2", "bench.held.FloorMod", "mod", in -> (int) in[1] <= 0)),
            new Case("held/floor-mod/jdk", ii, regression("v2", "v3", "bench.held.FloorMod", "mod", in -> (int) in[1] <= 0)),
            new Case("held/ceil-div", ii, regression("v1", "v2", "bench.held.CeilDiv", "ceilDiv", in -> (int) in[1] <= 0)),
            new Case("held/lower-bound", new String[] {"int[]", "int"},
                regression("v1", "v2", "bench.held.LowerBound", "lowerBound", in -> !sorted((int[]) in[0]))),
            new Case("held/utf8-length", new String[] {"char[]"}, regression("v1", "v2", "bench.held.Utf8Length", "length", in -> false)),
            new Case("held/reverse", new String[] {"int[]"}, regression("v1", "v2", "bench.held.Reverse", "reverse", in -> false)),
            new Case("held/prefix-sums", new String[] {"int[]"}, regression("v1", "v2", "bench.held.PrefixSums", "accumulate", in -> false)),
            new Case("held/overlap/meets", new String[] {"int", "int", "int", "int"},
                regression("v1", "v2", "bench.held.Overlap", "meets", in -> false)),
            new Case("held/overlap/length", new String[] {"int", "int", "int", "int"},
                regression("v1", "v2", "bench.held.Overlap", "length", in -> false)));
    }

    /** Assuming {@code 0 <= low <= high}, the midpoint returns and lies in {@code [low, high]}. */
    static Claim midpoint(String version) {
        return in -> {
            int low = (int) in[0];
            int high = (int) in[1];
            if (!(0 <= low && low <= high)) return OUTSIDE;
            Outcome o = call(version, "bench.real.Midpoint", "midpoint", low, high);
            return o.thrown() == null && low <= (int) o.value() && (int) o.value() <= high ? null : o.text();
        };
    }

    /** For a positive bucket count, the index returns and lies in {@code [0, buckets)}. */
    static Claim bucket(String version) {
        return in -> {
            int hash = (int) in[0];
            int buckets = (int) in[1];
            if (buckets <= 0) return OUTSIDE;
            Outcome o = call(version, "bench.real.Bucket", "index", hash, buckets);
            return o.thrown() == null && 0 <= (int) o.value() && (int) o.value() < buckets ? null : o.text();
        };
    }

    /** {@code isOdd} returns whether the lowest bit is set. */
    static Claim oddity(String version) {
        return in -> {
            int i = (int) in[0];
            Outcome o = call(version, "bench.real.Oddity", "isOdd", i);
            return o.thrown() == null && (boolean) o.value() == ((i & 1) == 1) ? null : o.text();
        };
    }

    /**
     * The sum throws IndexOutOfBoundsException exactly when the range is not in the array, and an empty range sums
     * to 0.
     */
    static Claim checksum(String version) {
        return in -> {
            byte[] b = (byte[]) in[0];
            int off = (int) in[1];
            int len = (int) in[2];
            boolean outOfRange = off < 0 || len < 0 || (long) off + len > b.length;
            Outcome o = call(version, "bench.real.Checksum", "sum", b.clone(), off, len);
            if (outOfRange) return o.thrown() != null && o.thrown().getClass() == IndexOutOfBoundsException.class ? null : o.text();
            return o.thrown() == null && (len != 0 || (int) o.value() == 0) ? null : o.text();
        };
    }

    interface Scope {
        boolean intended(Object[] in);
    }

    /**
     * The two versions agree on every input outside the intended change: equal results and equal arrays after the
     * call, or the same exception class.
     */
    static Claim regression(String before, String after, String className, String method, Scope unchangedUnless) {
        return in -> {
            if (unchangedUnless.intended(in)) return OUTSIDE;
            return compare(before, after, className, method, in);
        };
    }

    static String compare(String before, String after, String className, String method, Object[] in) throws Exception {
        Object[] previousArgs = arguments(before, className, method, in);
        Object[] newArgs = arguments(after, className, method, in);
        if (previousArgs == null || newArgs == null) return OUTSIDE;
        Outcome previous = call(before, className, method, previousArgs);
        Outcome current = call(after, className, method, newArgs);
        String p = previous.text() + arrays(previousArgs);
        String c = current.text() + arrays(newArgs);
        return p.equals(c) ? null : "before: " + p + "; after: " + c;
    }

    /**
     * The method's arguments in a version, from the flat input: arrays copied, and a record parameter built by its
     * constructor from the next components; null when a constructor refuses them.
     */
    static Object[] arguments(String version, String className, String name, Object[] in) throws Exception {
        Method m = method(version, className, name);
        Class<?>[] types = m.getParameterTypes();
        Object[] out = new Object[types.length];
        int next = 0;
        for (int i = 0; i < types.length; i++) {
            if (types[i].isRecord()) {
                var components = types[i].getRecordComponents();
                Class<?>[] componentTypes = new Class<?>[components.length];
                Object[] values = new Object[components.length];
                for (int k = 0; k < components.length; k++) {
                    componentTypes[k] = components[k].getType();
                    values[k] = in[next++];
                }
                try {
                    out[i] = types[i].getDeclaredConstructor(componentTypes).newInstance(values);
                } catch (InvocationTargetException e) {
                    return null;
                }
            } else {
                out[i] = copy(in[next++]);
            }
        }
        return out;
    }

    // Calling a version's method.

    static URLClassLoader loader(String version) throws Exception {
        URLClassLoader l = LOADERS.get(version);
        if (l == null) {
            l = new URLClassLoader(new URL[] {classes.resolve(version).toUri().toURL()}, ClassLoader.getPlatformClassLoader());
            LOADERS.put(version, l);
        }
        return l;
    }

    static Method method(String version, String className, String name) throws Exception {
        for (Method m : Class.forName(className, true, loader(version)).getDeclaredMethods()) {
            if (m.getName().equals(name)) return m;
        }
        throw new NoSuchMethodException(version + ": " + className + "#" + name);
    }

    static Outcome call(String version, String className, String name, Object... args) throws Exception {
        Method m = method(version, className, name);
        try {
            Object r = m.invoke(null, args);
            return new Outcome(r, null, m.getReturnType() == void.class ? "returns" : "returns " + show(r));
        } catch (InvocationTargetException e) {
            Throwable t = e.getCause();
            return new Outcome(null, t, "throws " + t.getClass().getName());
        }
    }

    static String arrays(Object[] args) {
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < args.length; i++) {
            if (args[i] != null && args[i].getClass().isArray()) s.append(", leaving argument ").append(i).append(' ').append(show(args[i]));
        }
        return s.toString();
    }

    static Object copy(Object v) {
        if (v instanceof int[] a) return a.clone();
        if (v instanceof byte[] a) return a.clone();
        if (v instanceof char[] a) return a.clone();
        return v;
    }

    static String show(Object r) {
        if (r == null) return "null";
        if (r instanceof Character c) return Integer.toString(c);
        if (r.getClass().isArray()) {
            List<String> parts = new ArrayList<>();
            for (int i = 0; i < Array.getLength(r); i++) parts.add(show(Array.get(r, i)));
            return "[" + String.join(", ", parts) + "]";
        }
        return r.toString();
    }

    static boolean sorted(int[] a) {
        for (int i = 0; i + 1 < a.length; i++) {
            if (a[i] > a[i + 1]) return false;
        }
        return true;
    }

    // Inputs: parsed from a request, or drawn for a search.

    static Object[] parse(String[] params, String text) {
        String[] tokens = text.isEmpty() ? new String[0] : text.split(";", -1);
        if (tokens.length != params.length) throw new IllegalArgumentException(params.length + " arguments expected: " + text);
        Object[] out = new Object[params.length];
        for (int i = 0; i < params.length; i++) out[i] = value(params[i], tokens[i].trim());
        return out;
    }

    static Object value(String type, String t) {
        if (type.endsWith("[]")) {
            String body = t.substring(1, t.length() - 1).trim();
            String[] parts = body.isEmpty() ? new String[0] : body.split(",");
            String element = type.substring(0, type.length() - 2);
            Object array = switch (element) {
                case "int" -> new int[parts.length];
                case "byte" -> new byte[parts.length];
                case "char" -> new char[parts.length];
                default -> throw new IllegalArgumentException(type);
            };
            for (int i = 0; i < parts.length; i++) Array.set(array, i, value(element, parts[i].trim()));
            return array;
        }
        return switch (type) {
            case "boolean" -> Boolean.parseBoolean(t);
            case "char" -> (char) Integer.parseInt(t);
            case "byte" -> (byte) Integer.parseInt(t);
            default -> Integer.parseInt(t);
        };
    }

    static final int[] BOUNDARY = {Integer.MIN_VALUE, Integer.MIN_VALUE + 1, -(1 << 30) - 1, -(1 << 30), -100000, -3, -2, -1, 0, 1, 2, 3,
        100000, 1 << 30, (1 << 30) + 1, Integer.MAX_VALUE - 1, Integer.MAX_VALUE};
    static final int[] FEW = {Integer.MIN_VALUE, -(1 << 30), -2, -1, 0, 1, 2, 1 << 30, Integer.MAX_VALUE};
    static final int MAX_ARRAY_LENGTH = 8;

    /** Boundary values first (every combination, for scalar parameters), then {@code n} seeded random inputs. */
    static String search(Case c, int n) throws Exception {
        List<Object[]> inputs = new ArrayList<>();
        boolean scalar = Arrays.stream(c.params()).allMatch(p -> p.equals("int"));
        if (scalar) {
            int[] values = c.params().length <= 2 ? BOUNDARY : FEW;
            int combinations = (int) Math.pow(values.length, c.params().length);
            for (int k = 0; k < combinations; k++) {
                Object[] in = new Object[c.params().length];
                int rest = k;
                for (int i = 0; i < in.length; i++) {
                    in[i] = values[rest % values.length];
                    rest /= values.length;
                }
                inputs.add(in);
            }
        }
        SplittableRandom random = new SplittableRandom(1);
        int domain = 0;
        for (int k = 0; k < inputs.size() + n; k++) {
            Object[] in = k < inputs.size() ? inputs.get(k) : draw(c.params(), random);
            String r = c.claim().refute(in);
            if (r != null && r.equals(OUTSIDE)) continue;
            domain++;
            if (r != null) return c.id() + "\trefuted\t" + format(in) + "\t" + r;
        }
        return c.id() + "\theld\t" + domain;
    }

    static Object[] draw(String[] params, SplittableRandom random) {
        Object[] in = new Object[params.length];
        for (int i = 0; i < params.length; i++) {
            int length = random.nextInt(MAX_ARRAY_LENGTH + 1);
            in[i] = switch (params[i]) {
                case "int" -> anInt(random);
                case "boolean" -> random.nextBoolean();
                case "int[]" -> {
                    int[] a = new int[length];
                    for (int k = 0; k < length; k++) a[k] = random.nextInt(4) == 0 ? anInt(random) : random.nextInt(-8, 9);
                    if (random.nextBoolean()) Arrays.sort(a);
                    yield a;
                }
                case "byte[]" -> {
                    byte[] a = new byte[length];
                    random.nextBytes(a);
                    yield a;
                }
                case "char[]" -> {
                    char[] a = new char[length];
                    char[] edges = {0, 0x7f, 0x80, 0x7ff, 0x800, 0xd800, 0xffff};
                    for (int k = 0; k < length; k++) a[k] = random.nextBoolean() ? edges[random.nextInt(edges.length)] : (char) random.nextInt(0x10000);
                    yield a;
                }
                default -> throw new IllegalArgumentException(params[i]);
            };
        }
        return in;
    }

    /** An int from a mix: small, boundary, near a power of two, or anywhere. */
    static int anInt(SplittableRandom random) {
        return switch (random.nextInt(4)) {
            case 0 -> random.nextInt(-16, 17);
            case 1 -> BOUNDARY[random.nextInt(BOUNDARY.length)];
            case 2 -> (1 << random.nextInt(31)) + random.nextInt(-2, 3);
            default -> random.nextInt();
        };
    }

    static String format(Object[] in) {
        List<String> parts = new ArrayList<>();
        for (Object v : in) parts.add(v.getClass().isArray() ? show(v).replace(" ", "") : show(v));
        return String.join(";", parts);
    }
}
