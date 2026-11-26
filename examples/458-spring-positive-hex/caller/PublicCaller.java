import java.math.BigInteger;
import org.springframework.util.NumberUtils;

public class PublicCaller {
    static String parse(String text, Class<? extends Number> target) {
        try {
            Number n = NumberUtils.parseNumber(text, target);
            return n.getClass().getSimpleName() + "=" + n;
        } catch (NumberFormatException e) {
            return e.getClass().getSimpleName();
        }
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "plus" -> parse("+0x7f", Integer.class) + " " + parse("+0x7f", BigInteger.class);
            case "signed" -> parse("-0x7f", Integer.class) + " " + parse("+127", BigInteger.class);
            case "width" -> parse("+0x80", Short.class) + " " + parse("+0x80", Byte.class)
                    + " " + parse("+#80", Short.class) + " " + parse("+#80", Byte.class);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
