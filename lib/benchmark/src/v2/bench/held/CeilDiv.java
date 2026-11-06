package bench.held;

/** The ceiling of a quotient by a positive divisor, from the quotient times the divisor (v2). */
public final class CeilDiv {
    private CeilDiv() {
    }

    public static int ceilDiv(int a, int b) {
        int q = a / b;
        return q * b < a ? q + 1 : q;
    }
}
