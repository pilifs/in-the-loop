package net.terminalvalue.mica.interp;

import static net.terminalvalue.mica.Tests.equal;
import static net.terminalvalue.mica.Tests.throwsArithmetic;

public final class ArithmeticTest {

    private ArithmeticTest() {}

    public static void divisionRoundsTowardsZero() {
        equal(2, Arithmetic.idiv(7, 3));
        equal(-2, Arithmetic.idiv(-7, 3));
        equal(-2, Arithmetic.idiv(7, -3));
        equal(2, Arithmetic.idiv(-7, -3));
    }

    public static void theRemainderTakesTheSignOfTheDividend() {
        equal(1, Arithmetic.irem(7, 3));
        equal(-1, Arithmetic.irem(-7, 3));
        equal(1, Arithmetic.irem(7, -3));
    }

    public static void quotientAndRemainderRecoverTheDividend() {
        for (int a : new int[] {0, 1, -1, 7, -7, 1 << 20, Integer.MAX_VALUE, Integer.MIN_VALUE}) {
            for (int b : new int[] {1, 2, -2, 3, 7, Integer.MAX_VALUE}) {
                equal(a, Arithmetic.idiv(a, b) * b + Arithmetic.irem(a, b));
            }
        }
    }

    public static void divisionByZeroThrows() {
        throwsArithmetic(() -> Arithmetic.idiv(1, 0));
        throwsArithmetic(() -> Arithmetic.irem(1, 0));
    }
}
