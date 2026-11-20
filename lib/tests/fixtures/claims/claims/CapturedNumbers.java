package claims;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class CapturedNumbers {
    public static boolean span(boolean negative, boolean wide) {
        String first = negative ? (wide ? "-101" : "-8") : (wide ? "101" : "8");
        String input = "p:" + first + ".09!";
        Matcher m = Pattern.compile("(?:p:)((-?[0-9]+))\\.([0-9]{2})!").matcher(input);
        if (!m.matches()) return false;
        return m.group() == input && m.group(0) == input && m.group(1).equals(first) && m.group(2).equals(first)
                && m.group(3).equals("09") && Long.parseLong(m.group(2)) == (negative ? -1 : 1) * (wide ? 101 : 8);
    }

    public static boolean state(boolean bad) {
        Matcher m = Pattern.compile("(a)").matcher(bad ? "b" : "a");
        try {
            m.group(2);
            return false;
        } catch (IllegalStateException beforeMatch) {
            if (m.matches() == bad) return false;
        }
        try {
            m.group(2);
            return false;
        } catch (IllegalStateException noMatch) {
            return bad;
        } catch (IndexOutOfBoundsException noGroup) {
            return !bad && m.group(1) == m.group();
        }
    }

    public static boolean decimal(int code) {
        String[] text = {"+9223372036854775807", "-9223372036854775808", "9223372036854775808",
                "-9223372036854775809", "18446744073709551616", "1x", "-", "", "-0000000000000000000", "+123"};
        if (code < 0 || code >= text.length) return true;
        try {
            long result = Long.parseLong(text[code]);
            switch (code) {
                case 0: return result == Long.MAX_VALUE;
                case 1: return result == Long.MIN_VALUE;
                case 8: return result == 0L;
                case 9: return result == 123L;
                default: return false;
            }
        } catch (NumberFormatException expected) {
            return code >= 2 && code <= 7;
        }
    }

    public static boolean ambiguous() {
        Matcher m = Pattern.compile("(a*)(a*)").matcher("aa");
        return m.matches() && m.group(1).equals("aa");
    }

    public static boolean optional() {
        Matcher m = Pattern.compile("(a)?(b)").matcher("b");
        return m.matches() && m.group(1) == null;
    }

    public static boolean unicodeDigit() {
        return Long.parseLong("\u0661") == 1L;
    }

    public static boolean wrong() {
        Matcher m = Pattern.compile("(-?[0-9]+)\\.([0-9]{2})").matcher("-9.24");
        return m.matches() && Long.parseLong(m.group(1)) == 24;
    }

    public static void main(String[] args) {
        for (boolean flag : new boolean[] {false, true}) {
            if (!span(flag, false) || !span(flag, true) || !state(flag)) throw new AssertionError();
        }
        for (int i = -1; i <= 10; i++) if (!decimal(i)) throw new AssertionError();
        if (!ambiguous() || !optional() || !unicodeDigit() || wrong()) throw new AssertionError();
    }
}
