package claims;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.ConcurrentModificationException;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;

/**
 * Registrations in order and classes by name: what a registry that looks through a servlet context's
 * registrations asks of the JDK (example 290). Each method returns whether the JDK's answer is the one a
 * definition written out gives, as the other fixtures' do; {@code Samples} runs them on a JVM, where a class is
 * initialized once for all the calls, so the definitions are written for a class initialized before, too.
 */
public final class M {
    private M() {}

    /** {@code Arrays.stream(int[])}: the three matches against the loops they stand for. */
    public static boolean ints(int[] a, int k) {
        boolean all = true, any = false;
        for (int x : a) {
            all &= x < k;
            any |= x == k;
        }
        return Arrays.stream(a).allMatch(x -> x < k) == all && Arrays.stream(a).anyMatch(x -> x == k) == any
                && Arrays.stream(a).noneMatch(x -> x == k) == !any;
    }

    /** The compiler's concatenation of an int, a short and a byte: the decimal digits a StringBuilder appends. */
    public static boolean numbered(int i, short s, byte b) {
        String made = "servlet" + i;
        return made.equals(new StringBuilder("servlet").append(i).toString()) && made.length() >= 8
                && ("" + s + ':' + b).equals(new StringBuilder().append((int) s).append(':').append((int) b).toString());
    }

    static final class At {
        final int i;

        At(int i) {
            this.i = i;
        }
    }

    static String key(int k) {
        return "k" + (char) ('a' + (k & 3));
    }

    /**
     * A LinkedHashMap's values: one for each distinct key, in the order the keys were first put, each the value put
     * last for its key; the collection is the map's one, of the map's size, and its iterator ends where they do.
     */
    public static boolean ordered(int[] keys) {
        Map<String, At> map = new LinkedHashMap<>();
        for (int i = 0; i < keys.length; i++) {
            map.put(key(keys[i]), new At(i));
        }
        int[] want = new int[keys.length];
        int n = 0;
        for (int i = 0; i < keys.length; i++) {
            boolean first = true;
            for (int j = 0; j < i; j++) {
                first &= (keys[j] & 3) != (keys[i] & 3);
            }
            if (first) {
                int last = i;
                for (int j = i + 1; j < keys.length; j++) {
                    if ((keys[j] & 3) == (keys[i] & 3)) {
                        last = j;
                    }
                }
                want[n++] = last;
            }
        }
        Collection<At> values = map.values();
        if (values != map.values() || values.size() != n || map.size() != n) {
            return false;
        }
        Iterator<At> it = values.iterator();
        for (int i = 0; i < n; i++) {
            if (!it.hasNext() || it.next().i != want[i]) {
                return false;
            }
        }
        if (it.hasNext()) {
            return false;
        }
        try {
            it.next();
            return false;
        }
        catch (NoSuchElementException e) {
            return true;
        }
    }

    /** An iterator fails fast once a key is added after it was made, and reads a value replaced after it was. */
    public static boolean failsFast(boolean adds) {
        Map<String, At> map = new LinkedHashMap<>();
        map.put("a", new At(0));
        Iterator<At> it = map.values().iterator();
        map.put(adds ? "b" : "a", new At(1));
        try {
            return it.next().i == 1 && !adds;
        }
        catch (ConcurrentModificationException e) {
            return adds;
        }
    }

    /**
     * The list {@code Arrays.asList} makes of an array: a view of it, of its length, whose elements are the
     * array's as they are when asked for, and whose {@code toArray()} is a new array of them.
     */
    public static boolean listed(int[] a) {
        int n = a.length;
        At[] made = new At[n];
        for (int i = 0; i < n; i++) {
            made[i] = new At(a[i]);
        }
        List<At> view = Arrays.asList(made);
        Object[] plain = view.toArray();
        if (view.size() != n || plain.length != n) {
            return false;
        }
        for (int i = 0; i < n; i++) {
            if (view.get(i) != made[i] || plain[i] != made[i]) {
                return false;
            }
        }
        if (n > 0) {
            made[0] = new At(1);
            if (view.get(0) != made[0] || plain[0] == made[0]) {
                return false;
            }
        }
        try {
            view.get(n);
            return false;
        }
        catch (ArrayIndexOutOfBoundsException e) {
            return true;
        }
    }

    /**
     * An {@code ArrayList} of the elements added, in order: made empty with or without a capacity (a negative one
     * is refused), of their number, each where it was added, by {@code get}, by the iterator and in both arrays.
     */
    public static boolean collected(int[] a, int capacity) {
        List<At> list;
        try {
            list = capacity == 7 ? new ArrayList<>() : new ArrayList<>(capacity);
        }
        catch (IllegalArgumentException e) {
            return capacity < 0;
        }
        if (capacity < 0 || !list.isEmpty() || list.size() != 0) {
            return false;
        }
        int n = a.length;
        At[] made = new At[n];
        for (int i = 0; i < n; i++) {
            made[i] = new At(a[i]);
            if (!list.add(made[i]) || list.size() != i + 1 || list.isEmpty()) {
                return false;
            }
        }
        Object[] plain = list.toArray();
        At[] typed = list.toArray(new At[0]);
        if (plain.length != n || typed.length != n) {
            return false;
        }
        int met = 0;
        for (At at : list) {
            if (met >= n || at != made[met++]) {
                return false;
            }
        }
        if (met != n) {
            return false;
        }
        for (int i = 0; i < n; i++) {
            if (list.get(i) != made[i] || plain[i] != made[i] || typed[i] != made[i]) {
                return false;
            }
        }
        try {
            list.get(n);
            return false;
        }
        catch (IndexOutOfBoundsException e) {
        }
        try {
            list.get(-1);
            return false;
        }
        catch (IndexOutOfBoundsException e) {
            return true;
        }
    }

    /**
     * {@code toArray(T[])} of the first {@code k} elements: the given array where they fit, the elements first,
     * a null after them where there is room and the rest as it was; a new array of their number where they don't.
     */
    public static boolean filled(int[] a, int k) {
        int n = a.length;
        if (k < 0 || k > n) {
            return true;
        }
        ArrayList<At> list = new ArrayList<>();
        At[] made = new At[n];
        for (int i = 0; i < k; i++) {
            made[i] = new At(a[i]);
            list.add(made[i]);
        }
        At mark = new At(0);
        At[] given = new At[n];
        for (int i = 0; i < n; i++) {
            given[i] = mark;
        }
        At[] got = list.toArray(given);
        if (got != given) {
            return false;
        }
        for (int i = 0; i < n; i++) {
            if (got[i] != (i < k ? made[i] : i == k ? null : mark)) {
                return false;
            }
        }
        if (k == 0) {
            return true;
        }
        At[] small = new At[k - 1];
        At[] fresh = list.toArray(small);
        if (fresh == small || fresh.length != k) {
            return false;
        }
        for (int i = 0; i < k; i++) {
            if (fresh[i] != made[i]) {
                return false;
            }
        }
        return true;
    }

    /**
     * {@code addAll}: the other collection's elements after the list's own, in its order, true when it had any;
     * of another {@code ArrayList} and of the list {@code Arrays.asList} makes; a null collection is refused.
     */
    public static boolean appended(int[] a, int[] b, boolean view) {
        if (a.length + b.length > 3) {
            return true;
        }
        ArrayList<At> list = new ArrayList<>(a.length);
        At[] all = new At[a.length + b.length];
        for (int i = 0; i < a.length; i++) {
            all[i] = new At(a[i]);
            list.add(all[i]);
        }
        At[] more = new At[b.length];
        List<At> other = view ? Arrays.asList(more) : new ArrayList<>();
        for (int i = 0; i < b.length; i++) {
            more[i] = new At(b[i]);
            all[a.length + i] = more[i];
            if (!view) {
                other.add(more[i]);
            }
        }
        if (list.addAll(other) != (b.length > 0) || list.size() != all.length) {
            return false;
        }
        for (int i = 0; i < all.length; i++) {
            if (list.get(i) != all[i]) {
                return false;
            }
        }
        try {
            list.addAll(null);
            return false;
        }
        catch (NullPointerException e) {
            return list.size() == all.length;
        }
    }

    /**
     * An {@code ArrayList}'s iterator fails fast once an element is added after it was made, an empty
     * {@code addAll} included, and is past the end after the last element.
     */
    public static boolean swept(int change) {
        ArrayList<At> list = new ArrayList<>();
        list.add(new At(0));
        Iterator<At> it = list.iterator();
        if (change == 1) {
            list.add(new At(1));
        }
        if (change == 2) {
            list.addAll(new ArrayList<>());
        }
        try {
            if (!it.hasNext() || it.next().i != 0 || it.hasNext()) {
                return false;
            }
        }
        catch (ConcurrentModificationException e) {
            return change == 1 || change == 2;
        }
        try {
            it.next();
            return false;
        }
        catch (NoSuchElementException e) {
            return change != 1 && change != 2;
        }
    }

    /** A method the {@code ArrayList} model does not keep: the JDK call it names. */
    public static boolean contained() {
        return !new ArrayList<At>().contains(null);
    }

    /** {@code Arrays.copyOf} of an array of references: a new array of the length asked for, the elements first. */
    public static boolean recopied(int[] a, int length) {
        int n = a.length;
        if (length > n + 1) {
            return true;
        }
        At[] made = new At[n];
        for (int i = 0; i < n; i++) {
            made[i] = new At(a[i]);
        }
        At[] copy;
        try {
            copy = Arrays.copyOf(made, length);
        }
        catch (NegativeArraySizeException e) {
            return length < 0;
        }
        if (length < 0 || copy == made || copy.length != length) {
            return false;
        }
        for (int i = 0; i < length; i++) {
            if (copy[i] != (i < n ? made[i] : null)) {
                return false;
            }
        }
        try {
            Arrays.copyOf((At[]) null, length);
            return false;
        }
        catch (NullPointerException e) {
            return true;
        }
    }

    /** A {@code ConcurrentHashMap} made empty, with or without a capacity: a negative one is refused. */
    public static boolean cached(int capacity) {
        Object plain = new java.util.concurrent.ConcurrentHashMap<String, At>();
        try {
            return new java.util.concurrent.ConcurrentHashMap<String, At>(capacity) != plain && capacity >= 0;
        }
        catch (IllegalArgumentException e) {
            return capacity < 0;
        }
    }

    /** {@code Collections.emptyMap()}: one map, never null. */
    public static boolean emptied() {
        return Collections.emptyMap() != null && Collections.emptyMap() == Collections.emptyMap();
    }

    static int clock;
    static int quietAt;
    static int baseAt;
    static int subAt;
    static int loudTries;

    interface Marked {
    }

    static class Quiet {
        static {
            quietAt = ++clock;
        }
    }

    static class Base {
        static {
            baseAt = ++clock;
        }
    }

    static class Sub extends Base implements Marked {
        static {
            subAt = ++clock;
        }
    }

    static class Loud {
        static {
            if (clock >= 0) {
                throw new IllegalStateException("loud");
            }
        }
    }

    /**
     * {@code Class.forName(String)}: the class of that name, initialized before the call returns, its superclass
     * before it and each once; {@code ClassNotFoundException} for a name no class has, and
     * {@code NullPointerException} for none.
     */
    public static boolean loaded(int k) throws ClassNotFoundException {
        if (k == 0) {
            Class<?> c = Class.forName("claims.M$Quiet");
            int at = quietAt;
            return c == Quiet.class && at != 0 && Class.forName("claims.M$Quiet") == c && quietAt == at;
        }
        if (k == 1) {
            boolean ran = subAt != 0;
            int before = clock;
            Class<?> c = Class.forName("claims.M$Sub");
            return c == Sub.class && baseAt != 0 && baseAt < subAt && clock == (ran ? before : before + (baseAt > before ? 2 : 1));
        }
        if (k == 2) {
            try {
                Class.forName("claims.M$Absent");
                return false;
            }
            catch (ClassNotFoundException e) {
                return true;
            }
        }
        try {
            Class.forName(null);
            return false;
        }
        catch (NullPointerException e) {
            return true;
        }
    }

    /**
     * An initializer that throws: the first use is {@code ExceptionInInitializerError}, and every later one
     * {@code NoClassDefFoundError}, the class being erroneous from then on.
     */
    public static boolean erroneous() throws ClassNotFoundException {
        boolean both = true;
        for (int i = 0; i < 2; i++) {
            try {
                Class.forName("claims.M$Loud");
                return false;
            }
            catch (ExceptionInInitializerError e) {
                both &= loudTries++ == 0;
            }
            catch (NoClassDefFoundError e) {
                both &= loudTries++ > 0;
            }
        }
        return both;
    }

    /** {@code Class.isAssignableFrom}: whether the argument's class is the receiver's or below it. */
    public static boolean assignable(int k) throws ClassNotFoundException {
        Class<?> c = Class.forName(k == 0 ? "claims.M$Quiet" : k == 1 ? "claims.M$Sub" : "claims.M$Base");
        boolean below = k != 0, marked = k == 1;
        if (Base.class.isAssignableFrom(c) != below || Marked.class.isAssignableFrom(c) != marked) {
            return false;
        }
        if (!Object.class.isAssignableFrom(c) || !c.isAssignableFrom(c) || c.isAssignableFrom(Object.class)) {
            return false;
        }
        if (Sub.class.isAssignableFrom(c) != (k == 1) || c.isAssignableFrom(Sub.class) != below) {
            return false;
        }
        try {
            return c.isAssignableFrom(null);
        }
        catch (NullPointerException e) {
            return true;
        }
    }

    /** The thread a check runs on: one object, whose context class loader is the loader of the class path. */
    public static boolean threaded() throws ClassNotFoundException {
        Thread t = Thread.currentThread();
        ClassLoader loader = t.getContextClassLoader();
        return t == Thread.currentThread() && loader == M.class.getClassLoader()
                && Class.forName("claims.M$Base", false, loader) == Base.class;
    }

    /**
     * The state an initializer the checker does not run left ({@link Tables}): a map of names found by name, a
     * String a literal is and one it is not, numbers, an array.
     */
    public static boolean observed(int k) {
        String name = k == 0 ? "int" : k == 1 ? "boolean" : k == 2 ? "java.lang.String" : "long";
        Class<?> found = Tables.BY_NAME.get(name);
        if (k < 0 || k > 2 ? found != null || Tables.BY_NAME.containsKey(name) : !found.getName().equals(name)) {
            return false;
        }
        return Tables.BY_NAME.size() == Tables.COUNT && Tables.COUNT == 3 && Tables.MARKS.length == 2 && Tables.MARKS[1] == ']'
                && Tables.LABEL == "label" && Tables.PREFIX.equals("claims.") && Tables.PREFIX != "claims."
                && Tables.ORDER.length == 1 && Tables.ORDER[0] == String.class && Tables.SAME == Tables.BY_NAME && Tables.NONE == null;
    }

    /** A read of a field the observation holds no value of. */
    public static boolean unheld() {
        return Tables.WRAPPERS.size() == 2;
    }

    static class Served extends javax.claims.Library {
    }

    /**
     * A class of a JDK package that the class path holds ({@code javax.claims.Library}, as a servlet API's classes
     * are): initialized before a class below it, where the check has the observed state of its initializer.
     */
    public static boolean served() throws ClassNotFoundException {
        return Class.forName("claims.M$Served") == Served.class && javax.claims.Library.MARK == 7;
    }

    /** An initializer that throws on the JVM is not one to observe. */
    public static boolean thrown() {
        return Fails.MARK == 0;
    }
}
