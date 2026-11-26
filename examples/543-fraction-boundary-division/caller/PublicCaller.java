import org.apache.commons.lang3.math.Fraction;

public class PublicCaller {
    static String divide(int a, int b, int c, int d) {
        try {
            var r = Fraction.getFraction(a, b).divideBy(Fraction.getFraction(c, d));
            return r.getNumerator() + "/" + r.getDenominator();
        } catch (ArithmeticException e) {
            return e.getClass().getSimpleName();
        }
    }

    public static String observe(String[] a) {
        int m = Integer.MIN_VALUE;
        return switch (a[0]) {
            case "control" -> divide(1, 1, m, 1) + ";" + divide(3, 4, 1, 2);
            case "challenge" -> divide(1, 1, m, 2) + ";" + divide(1, 1, m / 2, 1);
            default -> divide(m, 1, m, 1);
        };
    }
}
