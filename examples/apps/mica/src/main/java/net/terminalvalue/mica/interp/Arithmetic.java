package net.terminalvalue.mica.interp;

/**
 * The integer division instructions of JVMS §6.5, {@code idiv} and {@code irem}, as the interpreter executes
 * them on the host's integers. The host happens to be a JVM, whose {@code /} and {@code %} are these very
 * instructions, so the kernels are short; what they carry is the specification in their comments and the
 * properties the build proves of them.
 */
public final class Arithmetic {

    private Arithmetic() {}

    /**
     * {@code idiv}: the quotient rounded towards zero. Division by zero throws {@code ArithmeticException}.
     * The one overflow, {@code Integer.MIN_VALUE / -1}, is specified: the result is the dividend, and no
     * exception is thrown.
     */
    public static int idiv(int dividend, int divisor) {
        if (divisor == 0) {
            throw new ArithmeticException("/ by zero");
        }
        return dividend / divisor;
    }

    /** {@code irem}: the remainder, with the sign of the dividend, so that {@code (a / b) * b + (a % b) == a}. */
    public static int irem(int dividend, int divisor) {
        if (divisor == 0) {
            throw new ArithmeticException("/ by zero");
        }
        return dividend % divisor;
    }
}
