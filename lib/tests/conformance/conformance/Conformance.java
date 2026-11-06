package conformance;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;

/**
 * The conformance corpus of step 1d of llm-dlc/loops/sound-verdicts.md: small methods whose behaviour the JVM
 * decides. lib/tests/conformance.rs states claims about them, runs each claim through the tool's engines, and runs
 * the calls and each claim's harness on a real JVM, so that a verdict the JVM refutes is caught whichever engine
 * gave it. The interpreter, which replays the engines' witnesses, is checked against the JVM call by call.
 */
public class Conformance {

    // Gaps: JDK constructors that throw (the first a review's reproducer), a monitor on null (the other), a void
    // JDK mutator of an argument array, and a monitor on an object, which is no gap.

    public static int capacity(int n) { new java.util.ArrayList<Object>(n); return 1; }

    public static int builderCapacity(int n) { new StringBuilder(n); return 1; }

    public static int mapCapacity(int n) { new java.util.HashMap<Object, Object>(n); return 1; }

    public static int setCapacity(int n) { new java.util.HashSet<Object>(n); return 1; }

    public static int loadFactor(int n) { new java.util.HashMap<Object, Object>(4, n); return 1; }

    public static int nullMonitor(int n) { synchronized ((Object) null) { return 1; } }

    public static int monitor(int n) { Object lock = new Object(); synchronized (lock) { return n; } }

    public static int firstByte(byte[] out) { if (out.length == 0) return 0; new java.util.Random(1).nextBytes(out); return out[0]; }

    // Identity and initialization: a hidden field, literals compared by reference, class initializers.

    static class A { int x; }
    static class B extends A { int x; }
    static class Other { static String a() { return "a"; } }
    static class Boom {
        static final int[] TABLE = table();
        static int[] table() { throw new IllegalStateException("no table"); }
        static int value(int n) { return n; }
    }
    static class Base {
        static final int[] TABLE = table();
        static int[] table() { throw new IllegalStateException("no base table"); }
    }
    static class Derived extends Base { static int value(int n) { return n; } }
    static class Quiet {
        static final int[] TABLE = { 1, 2 };
        static int value(int n) { return n; }
    }

    public static int hiding(int n) { B b = new B(); b.x = n; ((A) b).x = 2; return b.x; }

    public static int hidden(int n) { B b = new B(); b.x = n; ((A) b).x = 2; return ((A) b).x; }

    public static boolean sameLiteral(int n) { String s = "a"; return s == Other.a(); }

    public static boolean otherLiteral(int n) { String s = "a"; String t = "b"; return s == t; }

    public static boolean sameClass(int n) { Class<?> c = Conformance.class; return c == Conformance.class; }

    public static boolean concatenated(int n) { String s = "a"; return (s + "") == s; }

    public static int boom(int n) { return Boom.value(n); }

    public static int inherited(int n) { return Derived.value(n); }

    public static int quiet(int n) { return Quiet.value(n); }

    // Class initialization (JVMS §5.5): static state, the order initializers run in, a use from inside one, a
    // field initializing only the class that declares it, a superinterface with a default method, an Error thrown
    // as it is, and an erroneous class used again.
    static class Trace {
        static int log;
        static int mark(int v) { log = log * 10 + v; return v; }
    }
    static class Counter { static int count = 5; }
    static class Made {
        static int count = 1;
        Made() { count++; }
    }
    static class Elder { static { Trace.mark(1); } }
    static class Younger extends Elder {
        static { Trace.mark(2); }
        static int value(int n) { return n; }
    }
    static class CycleA { static int a = CycleB.b + 1; }
    static class CycleB { static int b = CycleA.a + 1; }
    static class Holder { static int value = 7; }
    static class Sub extends Holder { static { Trace.mark(1); } }
    interface Greeter {
        int SEED = Trace.mark(3);
        default int greet() { return SEED; }
    }
    interface Bare { int OTHER = Trace.mark(4); }
    static class Hello implements Bare, Greeter { static int value(int n) { return n; } }
    static class Fatal {
        static final int[] TABLE = table();
        static int[] table() { throw new InternalError("fatal"); }
        static int value(int n) { return n; }
    }

    public static int counter(int n) { Counter.count += n; return Counter.count; }

    public static int constructed(int n) { new Made(); new Made(); return Made.count + n; }

    public static int superFirst(int n) { Younger.value(n); return Trace.log; }

    public static int cycle(int n) { return CycleA.a + n; }

    public static int declaring(int n) { int v = Sub.value; return Trace.log * 100 + v + n; }

    public static int defaults(int n) { Hello.value(n); return Trace.log; }

    public static int fatal(int n) {
        try { return Fatal.value(n); } catch (ExceptionInInitializerError e) { return 1; } catch (InternalError e) { return 2; }
    }

    public static int boomTwice(int n) {
        int first = 0;
        try { Boom.value(n); } catch (ExceptionInInitializerError e) { first = 1; }
        try { return Boom.value(n); } catch (NoClassDefFoundError e) { return first + 1; }
    }

    // Enums and immutable lists (Phase 5 of llm-dlc/loops/engine-priorities.md): Enum.<init>(String, int),
    // List.of and List.copyOf, which lib/models models for JBMC, as the JVM runs them.

    enum Shade { DARK, LIGHT, PALE }

    public static int enumState(int n) {
        Shade s = n == 0 ? Shade.DARK : n == 1 ? Shade.LIGHT : Shade.PALE;
        return s.ordinal() * 10 + (s.name() == s.name() ? 1 : 0) + (s.toString() == s.name() ? 2 : 0) + (s.equals(Shade.LIGHT) ? 4 : 0);
    }

    // Enums in the tool's own checker (Phase 5, its last step): $VALUES, an array of references, at an index that is
    // an input; a switch through javac's $SwitchMap class; constants with bodies of their own and a field that
    // shares Enum's private `name`; an initializer that throws; and valueOf, which stays a gap.

    public static int enumValues(int n) {
        Shade[] all = Shade.values();
        Shade s = all[n];
        return s.ordinal() * 10 + all.length + (all == Shade.values() ? 100 : 0) + (all[s.ordinal()] == s ? 1000 : 0);
    }

    static int tone(Hue h) {
        switch (h) {
            case RED: return 1;
            case BLUE: return 3;
            default: return 2;
        }
    }

    public static int enumSwitch(int n) {
        Hue h = Hue.values()[n > 100 ? 2 : n & 1];
        return tone(h) * 10 + h.ordinal();
    }

    enum Step {
        UP(1) { int apply(int x) { return x + size; } },
        DOWN(2) { int apply(int x) { return x - size; } };
        final int size;
        final int name;
        Step(int size) { this.size = size; this.name = size * 100; }
        abstract int apply(int x);
    }

    public static int enumBodies(int n) {
        Step s = n > 0 ? Step.UP : Step.DOWN;
        return s.apply(n) * 10 + s.ordinal() + s.name + (s.name() == s.name() ? 1000 : 0);
    }

    enum Broken {
        ONE(0), TWO(1);
        final int inverse;
        Broken(int d) { inverse = 10 / d; }
    }

    public static int enumBroken(int n) {
        int first = 0;
        try { first = Broken.values().length; } catch (ExceptionInInitializerError e) { first = 1; }
        try { return first * 10 + Broken.TWO.inverse + n; } catch (NoClassDefFoundError e) { return first * 10 + 2; }
    }

    public static int enumValueOf(int n) {
        return Shade.valueOf("LIGHT").ordinal() + n;
    }

    public static int listSizes(int n) {
        Object a = new Object(), b = new Object(), c = new Object();
        List<Object> l = n == 0 ? List.of() : n == 1 ? List.of(a) : n == 2 ? List.of(a, b) : List.of(a, b, c);
        return l.size() * 10 + (l.isEmpty() ? 1 : 0);
    }

    public static int listNull(int n) {
        Object a = n > 0 ? new Object() : null;
        Object[] three = { new Object(), new Object(), n > 1 ? new Object() : null };
        int size = List.of(new Object(), a).size();
        return size + List.of(three).size();
    }

    public static int listChange(int n) {
        List<Object> l = n < 10 ? List.of(new Object()) : List.of(new Object(), new Object(), new Object());
        Object x = new Object();
        switch (n % 10) {
            case 1: l.add(x); break;
            case 2: l.set(0, x); break;
            case 3: l.remove(0); break;
            case 4: l.remove(x); break;
            case 5: l.clear(); break;
            case 6: l.addAll(List.of(x)); break;
            case 7: l.iterator().remove(); break;
            default: break;
        }
        return l.size();
    }

    public static int listCopySame(int n) {
        List<Object> l = n == 0 ? List.of() : n == 1 ? List.of(new Object()) : List.of(new Object(), new Object(), new Object());
        return (List.copyOf(l) == l ? 1 : 0) + (List.of() == List.of(new Object[0]) ? 2 : 0);
    }

    public static int listCopyMutable(int n) {
        if (n == 9) return List.copyOf((Collection<Object>) null).size();
        ArrayList<Object> m = new ArrayList<>();
        if (n > 0) m.add(new Object());
        if (n > 1) m.add(null);
        List<Object> c = List.copyOf(m);
        return (c == List.of() ? 1 : 0) + c.size() * 10 + (c == (Object) m ? 100 : 0);
    }

    public static int listGet(int n) {
        Object a = new Object(), c = new Object();
        List<Object> one = List.of(a);
        List<Object> three = List.of(new Object(), new Object(), c);
        if (n < 10) return one.get(n) == a ? 1 : 0;
        if (n < 20) return three.get(n - 10) == c ? 1 : 2;
        return List.of().get(n - 20) == null ? 3 : 4;
    }

    public static int listSearch(int n) {
        List<Integer> l = List.of(1, 2, 3);
        List<Integer> two = List.of(5, 5);
        Integer x = n == 0 ? null : Integer.valueOf(n);
        return (l.contains(x) ? 1 : 0) + l.indexOf(x) * 10 + two.lastIndexOf(x) * 100 + two.indexOf(x) * 1000;
    }

    public static int listEquals(int n) {
        List<Integer> a = List.of(1, 2);
        List<Integer> b = List.of(1, n);
        List<Integer> c = List.of(1, 2, n);
        return (a.equals(b) ? 1 : 0) + (a.hashCode() == b.hashCode() ? 2 : 0) + (a.equals(c) ? 4 : 0) + (c.equals(List.of(1, 2, 2)) ? 8 : 0);
    }

    public static int listIterate(int n) {
        int sum = 0;
        for (Integer i : List.of(1, 2, 3)) sum += i;
        Iterator<Object> it = List.of(new Object()).iterator();
        it.next();
        if (n > 0) it.next();
        return sum + (it.hasNext() ? 100 : 0);
    }

    public static int listOfArray(int n) {
        if (n == 9) return List.of((Object[]) null).size();
        Integer[] three = { 1, 2, 3 };
        Integer[] two = { 1, 2 };
        List<Integer> a = List.of(three);
        List<Integer> b = List.of(two);
        three[0] = n;
        two[0] = n;
        return a.get(0) + b.get(0) * 10 + (List.of(new Object[0]) == List.of() ? 100 : 0);
    }

    // Exceptions: finally overriding a return, handlers, nested handlers, bounds, casts, throwing null, rethrowing.

    @SuppressWarnings("finally")
    public static int finallyWins(int n) {
        try {
            if (n > 0) throw new IllegalStateException();
            return 1;
        } finally {
            return 2;
        }
    }

    public static int caught(int n) {
        try {
            return 10 / n;
        } catch (ArithmeticException e) {
            return -1;
        }
    }

    public static int nestedHandler(int n) {
        try {
            throw new IllegalArgumentException();
        } catch (RuntimeException e) {
            try {
                return 100 / n;
            } catch (ArithmeticException x) {
                return -2;
            }
        }
    }

    public static int element(int[] a, int i) { return a[i]; }

    public static int cast(int n) { A o = n > 0 ? new A() : new B(); return ((B) o).x; }

    public static int throwNull(int n) {
        IllegalStateException e = n > 0 ? new IllegalStateException() : null;
        if (n > -5) throw e;
        return 0;
    }

    public static int rethrown(int n) {
        try {
            if (n < 0) throw new IllegalArgumentException();
            return n;
        } catch (IllegalArgumentException e) {
            throw new IllegalStateException();
        }
    }

    // Aliasing: two names for one array or object, inside the method and among the parameters.

    public static int aliasedLocals(int n) { int[] a = new int[2]; int[] b = a; b[0] = n; return a[0]; }

    public static int aliasedObjects(int n) { A p = new A(); A q = p; q.x = n; return p.x; }

    public static int twoArrays(int[] a, int[] b) { a[0] = 1; b[0] = 2; return a[0]; }

    public static int writeThrough(int[] a) { int[] b = a; if (b.length > 0) b[0] = 7; return a.length == 0 ? 7 : a[0]; }

    // Null arrays: as a parameter, and as a local.

    public static int length(int[] a) { return a.length; }

    public static int lengthOrMinusOne(int[] a) { return a == null ? -1 : a.length; }

    public static int nullLocal(int n) { int[] a = n > 0 ? new int[1] : null; return a.length; }

    // Records: a constructor that rejects, one that normalizes, and equals, which an invokedynamic implements.

    record Range(int lo, int hi) {
        Range {
            if (lo > hi) throw new IllegalArgumentException("lo > hi");
        }

        int span() { return hi - lo; }
    }
    // A record whose constructor meets a gap, for a statement whose vacuity the tool's own checker cannot settle.
    record Sized(int n) {
        Sized {
            new java.util.ArrayList<Object>(n);
        }

        int twice() { return 2 * n; }
    }
    record Clamp(int v) {
        Clamp {
            if (v < 0) v = 0;
        }
    }
    record Pair(int a, int b) {}

    public static int width(int lo, int hi) { Range r = new Range(lo, hi); return r.hi() - r.lo(); }

    public static int clamp(int n) { return new Clamp(n).v(); }

    public static boolean pairsEqual(int a, int b) { return new Pair(a, b).equals(new Pair(a, b)); }

    // Dispatch: an override, a super call, an interface's default method.

    static class Shape { int sides() { return 0; } }
    static class Square extends Shape { @Override int sides() { return 4; } }
    static class Child extends Square { @Override int sides() { return super.sides() + 1; } }
    interface Named { default int code() { return 1; } }
    static class Plain implements Named {}
    static class Custom implements Named { public int code() { return 2; } }

    public static int sides(int n) { Shape s = n > 0 ? new Square() : n < 0 ? new Child() : new Shape(); return s.sides(); }

    public static int code(int n) { Named x = n > 0 ? new Custom() : new Plain(); return x.code(); }

    // Arithmetic edge cases: MIN_VALUE / -1, negative remainders, shift counts out of range, narrowing, overflow.

    public static int divide(int a, int b) { return a / b; }

    public static long divideLong(long a, long b) { return a / b; }

    public static int remainder(int a, int b) { return a % b; }

    public static long remainderLong(long a, long b) { return a % b; }

    public static int shiftLeft(int x, int s) { return x << s; }

    public static long shiftLeftLong(long x, int s) { return x << s; }

    public static int shiftRight(int x, int s) { return x >> s; }

    public static int shiftUnsigned(int x, int s) { return x >>> s; }

    public static int square(int x) { return x * x; }

    public static int negate(int x) { return -x; }

    public static byte toByte(int x) { return (byte) x; }

    public static char toChar(int x) { return (char) x; }

    public static short toShort(int x) { return (short) x; }

    public static int fromLong(long x) { return (int) x; }

    public static char nextChar(char c) { return (char) (c + 1); }

    public static int absolute(int x) { return Math.abs(x); }

    public static int increment(int x) { x++; return x; }

    public static int byteSum(byte a, byte b) { return a + b; }
}

// A top-level enum: javac switches over it through a $SwitchMap class (Conformance$1), as it does for an enum of
// another class; over an enum nested in the same class it switches on ordinal() directly.
enum Hue { RED, GREEN, BLUE }
