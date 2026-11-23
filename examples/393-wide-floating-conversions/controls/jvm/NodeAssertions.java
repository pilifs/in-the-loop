public class NodeAssertions {
    public static void direct(long n) { assert NodeChecks.direct(n); }
    public static void same(long n) { assert NodeChecks.same(n); }
    public static void sub(double x) { assert NodeChecks.publicSubnormal(x); }
    public static void bad(double x) { assert NodeChecks.wrongSubnormal(x); }
    public static void intrinsic(double x) { assert NodeChecks.intrinsicSubnormal(x); }
    public static void commons(long n) { assert NodeChecks.commons(n); }
    public static void reachJ() { NodeChecks.same((1L<<54) + (1L<<30) + 1L); assert false; }
    public static void reachD() { NodeChecks.publicSubnormal(0x1p-150); assert false; }
    public static void main(String[] args) {
        java.util.Random rand = new java.util.Random(611);
        for (int i = 0; i < 100000; i++) {
            long n = NodeChecks.BASE + (rand.nextLong() & (NodeChecks.BASE - 1));
            double x = Double.longBitsToDouble(0x3690000000000000L | (rand.nextLong() & 0xfffffffffffffL));
            direct(n); commons(n); sub(x);
        }
        for (double x : new double[]{0x1p-150,Math.nextUp(0x1p-150),Math.nextDown(0x1p-149),0x1p-149}) sub(x);
        try { same((1L << 54) + (1L << 30) + 1); throw new Error(); }
        catch (AssertionError expected) { System.out.println("LongNode double-rounding witness"); }
        try { bad(0x1p-150); throw new Error(); }
        catch (AssertionError expected) { System.out.println("Half-minimum subnormal witness"); }
    }
}
