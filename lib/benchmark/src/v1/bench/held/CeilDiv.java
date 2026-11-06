package bench.held;

/** The ceiling of a quotient by a positive divisor, from the remainder (v1). */
public final class CeilDiv {
    private CeilDiv() {
    }

    public static int ceilDiv(int a, int b) {
        return a / b + (a % b > 0 ? 1 : 0);
    }
}
