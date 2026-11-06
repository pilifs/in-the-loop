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
}
