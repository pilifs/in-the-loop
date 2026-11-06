package bench.held;

/** The non-negative remainder for a positive modulus, adding the modulus to a negative remainder only (v2). */
public final class FloorMod {
    private FloorMod() {
    }

    public static int mod(int a, int n) {
        int r = a % n;
        return r < 0 ? r + n : r;
    }
}
