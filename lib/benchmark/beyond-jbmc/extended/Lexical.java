import org.apache.commons.lang3.math.NumberUtils;

public final class Lexical {
    public static boolean partition(char c) {
        String text = new String(new char[]{'0', '.', c});
        boolean jdk;
        try {
            Double.parseDouble(text);
            jdk = true;
        } catch (NumberFormatException expected) { jdk = false; }
        boolean decimal = c >= '0' && c <= '9';
        boolean jdkOnly = c <= ' ' || c == 'd' || c == 'D' || c == 'f' || c == 'F';
        return NumberUtils.isParsable(text) == Character.isDigit(c) && jdk == (decimal || jdkOnly);
    }
    public static boolean commons(char c) {
        return NumberUtils.isParsable(new String(new char[]{'0','.',c})) == Character.isDigit(c);
    }
}
