package p;

/** The shapes JBMC 6.11.0 runs otherwise than the JVM, and their neighbours it runs as the JVM does: the fixture of
 * `jbmc_gaps`'s tests (README.md next to it says what JBMC does with each). One method per line. */
public class D {
    int v;
    public static int returned(int n) { try { return 10 / n; } catch (ArithmeticException e) { return -1; } }
    public static int field(D d) { try { return d.v; } catch (NullPointerException e) { return -1; } }
    public static int stored(int n) { try { int r = 10 / n; return r; } catch (ArithmeticException e) { return -1; } }
    public static int uncaught(int[] a, int i) { try { return a[i]; } catch (ArithmeticException e) { return -1; } }
    public static int called(int n) { try { return Math.abs(10 / n); } catch (ArithmeticException e) { return -1; } }
    public static int superCatch(int n) { try { int r = 10 / n; return r; } catch (RuntimeException e) { return -1; } }
    public static int thrown(int n) { try { if (n == 0) throw new IllegalArgumentException(); return 1; } catch (RuntimeException e) { return -1; } }
    public static int exact(int n) { try { if (n == 0) throw new IllegalStateException(); return 1; } catch (IllegalStateException e) { return -1; } }
    public static int shifted(int x, int s) { return x >> s; }
    public static long shiftedUnsigned(long x, int s) { return x >>> s; }
    public static int literal(int x) { return x >> 33; }
    public static int masked(int x, int s) { return x >>> (s & 31); }
    public static int halved(int x) { return x >> 1; }
    public static int left(int x, int s) { return x << s; }
    public static int declaring(int n) { return Sub.value + n; }
    public static void assigned(int n) { Sub.value = n; }
    public static int inherited(int n) { return Sub.get() + n; }
    public static int direct(int n) { return Holder.value + n; }
    public static int defaults(int n) { return Hello.value(n); }
    public static int created(int n) { new Sub(); return n; }
    public static int later(int n) { int k = n + 1000; return Sub.value + k; }
    public static int apart(int n) { return Holder.value + Quiet.value + Loud.value + n; }

    static int log;
    static class Holder { static int value = 7; static int get() { return value; } }
    static class Sub extends Holder { static { log = 1; } }
    interface Bare { int[] T = { 4 }; }
    interface Greeter { int[] S = { 3 }; default int greet() { return S[0]; } }
    static class Hello implements Bare, Greeter { static int value(int n) { return n; } }
    static class Quiet { static int value = 2; }
    static class Loud { static int value = 3; }

    // A class initializer that throws (VF-009): the JVM gives its caller an ExceptionInInitializerError, and a
    // NoClassDefFoundError at the class's next use; JBMC gives it the initializer's own exception, and the next use
    // runs on as if the class were initialized.
    public static int boomed(int n) { try { return Boom.value(n); } catch (ExceptionInInitializerError e) { return -1; } }
    public static int divided(int n) { try { return Ratio.inverse + n; } catch (ArithmeticException e) { return -1; } }
    public static int caughtAll(int n) { try { return Boom.value(n); } catch (Throwable t) { return -1; } }
    public static int escaped(int n) { return Boom.value(n); }
    public static int fatal(int n) { try { return Fatal.value(n); } catch (ExceptionInInitializerError e) { return -1; } }
    public static int quiet(int n) { try { return Quiet.value + n; } catch (ExceptionInInitializerError e) { return -1; } }
    public static int toned(int n) { try { return Tone.HIGH.level + n; } catch (ExceptionInInitializerError e) { return -1; } }
    public static int tabled(int n) { try { return Table.T[0] + n; } catch (ExceptionInInitializerError e) { return -1; } }
    public static int sized(int n) { try { return Sized.T.length + n; } catch (ExceptionInInitializerError e) { return -1; } }
    static class Boom { static final int[] TABLE = table(); static int[] table() { throw new IllegalStateException(); } static int value(int n) { return n; } }
    static class Ratio { static int inverse = 10 / log; }
    enum Tone { LOW(1), HIGH(2); final int level; Tone(int level) { this.level = level; } }
    static class Table { static final int[] T = { 1, 2 }; }
    static class Sized { static final int[] T = new int[log - 1]; }
    static class Fatal { static final int[] TABLE = table(); static int[] table() { throw new InternalError(); } static int value(int n) { return n; } }
}
