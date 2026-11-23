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

    public static void main(String[] args) throws Exception {
        if (!metadata() || !bindings() || !overridingInitialValue() || !split() || !locks() || !writer() || !membership())
            throw new AssertionError();
    }
}
