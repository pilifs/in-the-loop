package bench.held;

/** The non-negative remainder for a positive modulus, by the JDK (v3). */
public final class FloorMod {
    private FloorMod() {
    }

    public static int mod(int a, int n) {
        return Math.floorMod(a, n);
    }
}
