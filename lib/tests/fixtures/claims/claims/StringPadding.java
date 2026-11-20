package claims;

import java.util.Arrays;

public final class StringPadding {
    public static boolean copy(boolean surrogate, boolean emptySuffix) {
        char unit = surrogate ? '\ud800' : '0';
        char[] buf = {'x', 'y'};
        Arrays.fill(buf, unit);
        String prefix = new String(buf);
        buf[0] = 'z';
        String end = emptySuffix ? "" : "8";
        String result = prefix.concat(end);
        return prefix.charAt(0) == unit && prefix.charAt(1) == unit && (result == prefix) == emptySuffix
                && result.length() == (emptySuffix ? 2 : 3) && result.charAt(0) == unit && (emptySuffix || result.charAt(2) == '8');
    }

    public static boolean boundaries() {
        char[] none = {};
        Arrays.fill(none, 'x');
        String blank = new String(none);
        if (blank == "" || !blank.isEmpty() || blank.concat("") != blank || blank.concat("x") == "x") return false;
        try {
            Arrays.fill((char[]) null, 'z');
            return false;
        } catch (NullPointerException expected) {
            try {
                new String((char[]) null);
            } catch (NullPointerException alsoExpected) {
                return true;
            }
            return false;
        }
    }

    public static boolean wrong() {
        char[] units = {'x'};
        Arrays.fill(units, '0');
        return new String(units).concat("1").equals("x1");
    }

    public static void main(String[] args) {
        for (boolean flag : new boolean[] {false, true}) {
            if (!copy(flag, false) || !copy(flag, true)) throw new AssertionError();
        }
        if (!boundaries() || wrong()) throw new AssertionError();
    }
}
