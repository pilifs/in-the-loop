package fractiongrid;

import org.apache.commons.math3.fraction.Fraction;

public final class Projection {
    private static int n(int code) { return code>=10?code-11:(code<5?1:-1)*(21474834+code%5); }
    public static int bits(int code) {
        int n=n(code);
        double actual=new Fraction(n,1).percentageValue();
        return Double.doubleToRawLongBits(actual)==Double.doubleToRawLongBits((double)(100L*n))?1:0;
    }
    public static int normal(int code) {
        try { new Fraction(n(code),1).percentageValue();return 1; } catch(ArithmeticException e){return 0;}
    }
}
