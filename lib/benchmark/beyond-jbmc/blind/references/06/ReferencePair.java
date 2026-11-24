public final class ReferencePair {
    public static boolean admitted(int n) { return n >= 0 && n <= 12; }
    public static long oldExpected(int n) { return new int[]{101,102,103,104,105,201,202,203,204,301,401,402,403}[n]; }
    public static long newExpected(int n) { return new int[]{101,102,103,104,105,201,202,203,204,301,401,402,403}[n]; }
    public static long controlExpected(int n) { return 1; }

    public static boolean primary(int n) {
        if (!admitted(n)) return true;
        long a=before.ReferenceAPI.primary(n), b=ReferenceAPI.primary(n);
        return a==oldExpected(n) && b==newExpected(n);
    }
    public static boolean control(int n) {
        if (!admitted(n)) return true;
        long a=before.ReferenceAPI.control(n), b=ReferenceAPI.control(n);
        return a==controlExpected(n) && b==controlExpected(n);
    }
    public static boolean inverse(int n) {
        return !admitted(n) || !primary(n);
    }
}
