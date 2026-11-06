package bench.held;

/** The non-negative remainder for a positive modulus, adding the modulus and taking the remainder again (v1), which overflows once the modulus passes 2^30. */
public final class FloorMod {
    private FloorMod() {
    }

    public static int mod(int a, int n) {
        return ((a % n) + n) % n;
    }
}
