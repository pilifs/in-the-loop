/** VF-009's shapes (verification/findings.md): a class initializer that throws, on the JVM and in JBMC. Each entry
 * point is a void method with one assertion that holds on the JVM: run `java -ea F` (each on classes of its own, so
 * one run decides them all), and `jbmc F --function F.NAME` with and without `--throw-runtime-exceptions`.
 *
 * JVMS §5.5, step 11: an initializer that completes abruptly with an exception that is not an `Error` is wrapped in
 * `ExceptionInInitializerError`; step 12 marks the class erroneous, and step 5 makes every later initialization of an
 * erroneous class throw `NoClassDefFoundError`, without running the initializer again. */
public class F {
    static int runs;

    static int[] fail() { runs++; throw new IllegalStateException("no table"); }

    static class Wrap { static final int[] TABLE = fail(); static int value(int n) { return n; } }
    static class Twice { static final int[] TABLE = fail(); static int value(int n) { return n; } }
    static class Again { static final int[] TABLE = fail(); static int value(int n) { return n; } }
    static class Fatal { static final int[] TABLE = fatal(); static int[] fatal() { throw new InternalError("fatal"); } static int value(int n) { return n; } }
    static class Boom { static final int[] TABLE = fail(); static int value(int n) { return n; } }
    enum Divide { ONE(0), TWO(1); final int inverse; Divide(int d) { inverse = 10 / d; } }
    enum Broken { ONE(0), TWO(1); final int inverse; Broken(int d) { inverse = 10 / d; } }

    /** The first use: the `IllegalStateException` reaches the caller as an `ExceptionInInitializerError`. */
    public static void wrapped() {
        int r;
        try { Wrap.value(0); r = 0; } catch (ExceptionInInitializerError e) { r = 1; } catch (IllegalStateException e) { r = 2; }
        assert r == 1;
    }

    /** The second use of a class whose initializer failed throws `NoClassDefFoundError`. */
    public static void erroneous() {
        try { Twice.value(0); } catch (Throwable t) { }
        int r;
        try { Twice.value(0); r = 0; } catch (NoClassDefFoundError e) { r = 1; } catch (Throwable t) { r = 2; }
        assert r == 1;
    }

    /** The initializer runs once, however often the class is used after it failed. */
    public static void once() {
        int before = runs;
        try { Again.value(0); } catch (Throwable t) { }
        try { Again.value(0); } catch (Throwable t) { }
        assert runs == before + 1;
    }

    /** An `Error` is not wrapped: it reaches the caller as itself (the corpus's `fatal`, which agrees). */
    public static void error() {
        int r;
        try { Fatal.value(0); r = 0; } catch (ExceptionInInitializerError e) { r = 1; } catch (InternalError e) { r = 2; }
        assert r == 2;
    }

    /** An enum's initializer that divides by zero: an `ArithmeticException`, wrapped. */
    public static void enumWrapped() {
        int r;
        try { r = Divide.values().length; } catch (ExceptionInInitializerError e) { r = 1; } catch (ArithmeticException e) { r = 2; }
        assert r == 1;
    }

    /** The corpus's `boomTwice(0)`, which returns 2 on the JVM. */
    public static void boomTwice() {
        int first = 0, r;
        try { Boom.value(0); } catch (ExceptionInInitializerError e) { first = 1; }
        try { r = Boom.value(0); } catch (NoClassDefFoundError e) { r = first + 1; }
        assert r == 2;
    }

    /** The corpus's `enumBroken(0)`, which returns 12 on the JVM. */
    public static void enumBroken() {
        int first = 0, r;
        try { first = Broken.values().length; } catch (ExceptionInInitializerError e) { first = 1; }
        try { r = first * 10 + Broken.TWO.inverse; } catch (NoClassDefFoundError e) { r = first * 10 + 2; }
        assert r == 12;
    }

    public static void main(String[] args) {
        wrapped(); erroneous(); once(); error(); enumWrapped(); boomTwice(); enumBroken();
        System.out.println("all hold, runs " + runs);
    }
}
