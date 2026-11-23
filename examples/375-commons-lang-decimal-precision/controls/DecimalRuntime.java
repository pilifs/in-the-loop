import datawork.Decimals;
import java.math.BigDecimal;
import org.apache.commons.lang3.math.NumberUtils;

/** Observe the exact runtime class and value at the original public method on each artifact. */
public final class DecimalRuntime {
    static String observe(String text) {
        try {
            Number n = NumberUtils.createNumber(text);
            String type = n.getClass().getName();
            if (n.getClass() == BigDecimal.class) {
                BigDecimal d = (BigDecimal)n;
                return type + " " + d.unscaledValue() + " " + d.scale();
            }
            if (n.getClass() == Float.class) return type + " " + Float.floatToRawIntBits(n.floatValue());
            if (n.getClass() == Integer.class) return type + " " + n.intValue();
            throw new AssertionError("Unexpected result class " + type);
        } catch (NumberFormatException e) {
            return e.getClass().getName();
        }
    }

    public static void main(String[] args) {
        for (int code = 0; code < 3; code++) {
            String exact = Decimals.exact(code), control = Decimals.control(code);
            System.out.println(code + "\t" + exact + "\t" + observe(exact) + "\t" + control + "\t"
                    + observe(control) + "\t" + observe("1eE"));
        }
    }
}
