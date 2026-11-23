import org.apache.commons.lang3.math.Fraction;
import org.apache.commons.lang3.mutable.MutableDouble;

public final class WideNumbers {
    static int nearestEven(int n) { return (n >>> 1) + ((n & 3) == 3 ? 1 : 0); }

    public static boolean fraction(int n) {
        return (double) Fraction.getFraction(n, 2).floatValue() == nearestEven(n);
    }
    public static boolean fractionOpcode(int n) { return (double) ((float) n / 2.0f) == nearestEven(n); }
    public static boolean floorOnly(int n) { return (double) Fraction.getFraction(n, 2).floatValue() == (n >>> 1); }

    // Every word in the exponent-31 binade has precisely these high twelve bits.
    static double input(long fraction) {
        return Double.longBitsToDouble(0x41e0000000000000L | (fraction & 0x000fffffffffffffL));
    }
    public static boolean narrow(long fraction) {
        double x = input(fraction);
        MutableDouble number = new MutableDouble(x);
        int high = number.intValue();
        number.setValue(-x);
        return high == Integer.MAX_VALUE && number.intValue() == Integer.MIN_VALUE;
    }
    public static boolean narrowOpcode(long fraction) {
        double x = input(fraction);
        return (int) x == Integer.MAX_VALUE && (int) -x == Integer.MIN_VALUE;
    }
    public static boolean wraps(long fraction) {
        double x = input(fraction);
        return new MutableDouble(x).intValue() == (int) (long) x;
    }
}
