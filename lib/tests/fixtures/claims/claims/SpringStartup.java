package claims;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;

public final class SpringStartup {
    public record Component(String getName) {}
    public record Extra(String label) {
        public String getName() { return label; }
    }
    static final class Custom extends ThreadLocal<Object> {
        private final Object initial = new Object();
        @Override protected Object initialValue() { return initial; }
    }
    static final class OverrideGet extends ThreadLocal<Object> {
        @Override public Object get() { return this; }
    }
    static class Segment extends java.util.concurrent.locks.ReentrantLock {}
    static final class RefusingSegment extends Segment {
        @Override public boolean tryLock() { return false; }
    }

    public static boolean locks() {
        Segment s = new Segment();
        s.lock();
        if (!s.tryLock() || s.getHoldCount() != 2) return false;
        s.unlock();
        if (!s.isHeldByCurrentThread()) return false;
        s.unlock();
        return !s.isLocked() && !new RefusingSegment().tryLock();
    }

    public static boolean writer() {
        java.io.StringWriter out = new java.io.StringWriter();
        StringBuffer buffer = out.getBuffer();
        return buffer == out.getBuffer() && buffer != new java.io.StringWriter().getBuffer() && buffer.length() == 0;
    }

    public static boolean membership() {
        java.util.Set<String> names = java.util.Set.of(new String[]{"D"});
        if (names.size() != 1 || !names.contains(new String("D")) || names.contains("A")) return false;
        var single = names.iterator();
        if (!single.hasNext() || !"D".equals(single.next()) || single.hasNext()) return false;
        var pair = java.util.Set.of(new String[]{"A", "B"});
        var it = pair.iterator();
        String first = it.next();
        String last = it.next();
        return !it.hasNext() && first == pair.iterator().next()
            && (first.equals("A") && last.equals("B") || first.equals("B") && last.equals("A"));
    }

    public static boolean metadata() throws Exception {
        Method m = Component.class.getMethod("getName");
        Method extra = Extra.class.getMethod("getName");
        if (m == Component.class.getMethod("getName") || m.getDeclaringClass() != Component.class
                || extra.getDeclaringClass() != Extra.class || m.getParameterCount() != 0
                || m.getName() != "getName" || m.getReturnType() != String.class
                || Modifier.isStatic(m.getModifiers())) return false;
        if (Modifier.isStatic(Component.class.getDeclaredField(m.getName()).getModifiers())) return false;
        try {
            Extra.class.getDeclaredField(extra.getName());
            return false;
        } catch (NoSuchFieldException expected) {
            return extra.getName().equals(expected.getMessage());
        }
    }

    public static boolean bindings() {
        ThreadLocal<Object> a = new ThreadLocal<>();
        ThreadLocal<Object> b = new InheritableThreadLocal<>();
        Object v = new Object();
        if (a.get() != null || b.get() != null) return false;
        a.set(v);
        b.set(a);
        a.remove();
        if (a.get() != null || b.get() != a) return false;
        Custom custom = new Custom();
        custom.set(null);
        if (custom.get() != null) return false;
        custom.set(v);
        return custom.get() == v && new OverrideGet().get() != null;
    }

    public static boolean overridingInitialValue() {
        Custom c = new Custom();
        c.set(null);
        c.remove();
        return c.get() == c.initial;
    }

    public static boolean split() {
        String input = new String("word");
        String[] miss = input.split("\n");
        String[] parts = " > a\t> \u000bb  >  c > ".split("\\s+>\\s+");
        String[] adjacent = "a > > b".split("\\s+>\\s+");
        return miss.length == 1 && miss[0] == input && "".split("\n").length == 1
            && "\n\n".split("\n").length == 0 && parts.length == 4 && parts[0].isEmpty()
            && "a".equals(parts[1]) && "b".equals(parts[2]) && "c".equals(parts[3])
            && adjacent.length == 2 && "> b".equals(adjacent[1])
            && "a\u00a0>\u00a0b".split("\\s+>\\s+").length == 1;
    }

    static final class ConstantHash {
        @Override public int hashCode() { return 17; }
        int inherited() { return super.hashCode(); }
    }

    public static boolean cacheKeys() {
        ConstantHash key = new ConstantHash();
        ClassLoader loader = SpringStartup.class.getClassLoader();
        Object mirror = Component.class;
        return mirror.equals(Component.class) && !mirror.equals(Extra.class) && !mirror.equals(null)
            && key.hashCode() == 17 && key.inherited() == System.identityHashCode(key)
            && loader.hashCode() == System.identityHashCode(loader);
    }

    public static boolean indexSize() {
        var map = new java.util.IdentityHashMap<String, String>(9);
        String a = new String("a"), b = new String("a");
        map.put(a, "1");
        map.put(b, "2");
        if (map.size() != 2 || map.get(a) != "1" || map.get(b) != "2") return false;
        try {
            new java.util.IdentityHashMap<>(-2);
            return false;
        } catch (IllegalArgumentException expected) {
            return true;
        }
    }

    public static boolean queueState() {
        var queue = new java.lang.ref.ReferenceQueue<>();
        var counter = new java.util.concurrent.atomic.AtomicInteger(Integer.MAX_VALUE);
        return queue.poll() == null && counter.incrementAndGet() == Integer.MIN_VALUE
            && queue.poll() == null && counter.get() == Integer.MIN_VALUE;
    }

    public static boolean registeredQueue() {
        var queue = new java.lang.ref.ReferenceQueue<>();
        Object strong = new Object();
        var reference = new java.lang.ref.SoftReference<>(strong, queue);
        boolean empty = queue.poll() == null;
        java.lang.ref.Reference.reachabilityFence(strong);
        java.lang.ref.Reference.reachabilityFence(reference);
        return empty;
    }

    public static boolean queueDelivery() {
        var left = new java.lang.ref.ReferenceQueue<Object>();
        var right = new java.lang.ref.ReferenceQueue<Object>();
        var a = new java.lang.ref.SoftReference<>(new Object(), left);
        var b = new java.lang.ref.SoftReference<>(new Object(), left);
        var c = new java.lang.ref.SoftReference<>(new Object(), right);
        var first = left.poll();
        var second = left.poll();
        var other = right.poll();
        return (first == null || first == a || first == b) && (second == null || second == a || second == b)
            && (first == null || first != second && first.get() == null)
            && (other == null || other == c && c.get() == null)
            && (a.get() != null || a.get() == null);
    }

    public static boolean arrayForEach() {
        String[] source = {"first", "before"};
        String[] seen = new String[2];
        int[] index = {0};
        var mapped = java.util.Arrays.stream(source).map(String::trim);
        try { mapped.forEach(null); return false; } catch (NullPointerException expected) {}
        mapped.forEach(s -> { seen[index[0]++] = s; source[1] = "after"; });
        if (index[0] != 2 || !"first".equals(seen[0]) || !"after".equals(seen[1])) return false;
        var head = java.util.Arrays.stream(source);
        try { head.forEach(null); return false; } catch (NullPointerException expected) {}
        try { head.forEach(s -> {}); return false; } catch (IllegalStateException expected) {}
        return true;
    }

    public static boolean nestedHolds(boolean extra) {
        var lock = new java.util.concurrent.locks.ReentrantLock();
        if (extra) lock.lock();
        if (lock.isHeldByCurrentThread() != extra || !lock.tryLock()) return false;
        if (lock.getHoldCount() != (extra ? 2 : 1)) return false;
        lock.unlock();
        if (extra) lock.unlock();
        return !lock.isLocked() && lock.getHoldCount() == 0;
    }

    public static boolean mapCallbacks() {
        var map = new java.util.LinkedHashMap<String, Integer>();
        try { map.forEach(null); return false; }
        catch (NullPointerException expected) {}
        map.put("a", 1);
        map.put("b", 2);
        int[] visited = {0};
        map.forEach((k,v) -> {
            visited[0] = 10 * visited[0] + v;
            if (k.equals("a")) map.put("b", 3);
        });
        if (visited[0] != 13) return false;
        visited[0] = 0;
        try {
            map.forEach((k,v) -> {
                visited[0] = 10 * visited[0] + v;
                if (k.equals("a")) map.put("c", 4);
            });
            return false;
        } catch (java.util.ConcurrentModificationException expected) {
            return visited[0] == 134;
        }
    }

    public static boolean zones() {
        String id = new String("UTC");
        var zone = java.util.TimeZone.getTimeZone(id);
        var other = java.util.TimeZone.getTimeZone("UTC");
        if (zone == other || zone.getID() != id || zone.getRawOffset() != 0 || zone.getDSTSavings() != 0
                || zone.useDaylightTime()) return false;
        zone.setRawOffset(12345);
        zone.setID("changed");
        return zone.getRawOffset() == 12345 && zone.getID().equals("changed")
            && other.getRawOffset() == 0 && other.getID() == "UTC";
    }

    public static boolean writeRanges() {
        var writer = new java.io.StringWriter();
        StringBuffer buffer = writer.getBuffer();
        writer.write("Xabc\u00ff\u0100", 1, 4);
        String early = writer.toString();
        writer.write("0123456789abcdef", 0, 16);
        String later = writer.toString();
        return writer.getBuffer() == buffer && early.equals("abc\u00ff") && later != writer.toString()
            && buffer.length() == 20 && later.equals("abc\u00ff0123456789abcdef");
    }

    public static boolean guardedLines() {
        String sep = System.lineSeparator();
        if (!"\n".equals(sep) && !sep.equals("\r\n")) return true;
        var sink = new java.io.StringWriter();
        var writer = new java.io.PrintWriter(sink);
        writer.println("a"); writer.println("b");
        return sink.toString().equals("a" + sep + "b" + sep);
    }

    public static boolean excludesCRLF() {
        String sep = System.lineSeparator();
        if (sep.equals("\n")) return true;
        return !sep.equals("\r\n");
    }

    public static void main(String[] args) throws Exception {
        if (!metadata() || !bindings() || !overridingInitialValue() || !split() || !locks() || !writer() || !membership()
                || !cacheKeys() || !indexSize() || !queueState() || !registeredQueue() || !mapCallbacks()
                || !queueDelivery() || !arrayForEach() || !nestedHolds(true) || !nestedHolds(false)
                || !zones() || !writeRanges() || !guardedLines())
            throw new AssertionError();
    }
}
