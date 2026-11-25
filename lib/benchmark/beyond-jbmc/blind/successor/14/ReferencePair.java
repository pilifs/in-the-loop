public final class ReferencePair {
    public static boolean admitted(int n) { return n >= 0 && n <= 255; }
    public static long oldExpected(int n) { return n; }
    public static long newExpected(int n) { return n; }
    public static long controlExpected(int n) { return 1; }

    public static boolean primary(int n) {
        if (!admitted(n)) return true;
        try {
            long old = before.ReferenceAPI.primary(n), current = ReferenceAPI.primary(n);
            return old == oldExpected(n) && current == newExpected(n);
        } catch (Exception unexpected) { throw new IllegalStateException(unexpected); }
    }
    public static boolean control(int n) {
        if (!admitted(n)) return true;
        try {
            long old = before.ReferenceAPI.control(n), current = ReferenceAPI.control(n);
            return old == controlExpected(n) && current == controlExpected(n);
        } catch (Exception unexpected) { throw new IllegalStateException(unexpected); }
    }
    public static boolean inverse(int n) { return !admitted(n) || !primary(n); }
}
