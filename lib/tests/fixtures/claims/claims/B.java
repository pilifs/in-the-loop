package claims;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.regex.Pattern;

/**
 * Text as bytes and digits, and constant regexes with classes, groups and counts, each against a definition written
 * out over charAt and the cells: what a password check does with a hash's text (Spring Security's BCrypt).
 */
public final class B {
    private B() {}

    /** The UTF-8 encoding unit by unit: a pair of surrogates is four bytes, a surrogate alone is '?'. */
    public static boolean utf8(String s) {
        byte[] got = s.getBytes(StandardCharsets.UTF_8);
        byte[] want = new byte[3 * s.length()];
        int n = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < 0x80) {
                want[n++] = (byte) c;
            } else if (c < 0x800) {
                want[n++] = (byte) (0xC0 | c >> 6);
                want[n++] = (byte) (0x80 | c & 0x3F);
            } else if (c >= 0xD800 && c < 0xDC00 && i + 1 < s.length() && s.charAt(i + 1) >= 0xDC00 && s.charAt(i + 1) < 0xE000) {
                int point = 0x10000 + ((c - 0xD800) << 10) + (s.charAt(++i) - 0xDC00);
                want[n++] = (byte) (0xF0 | point >> 18);
                want[n++] = (byte) (0x80 | point >> 12 & 0x3F);
                want[n++] = (byte) (0x80 | point >> 6 & 0x3F);
                want[n++] = (byte) (0x80 | point & 0x3F);
            } else if (c >= 0xD800 && c < 0xE000) {
                want[n++] = '?';
            } else {
                want[n++] = (byte) (0xE0 | c >> 12);
                want[n++] = (byte) (0x80 | c >> 6 & 0x3F);
                want[n++] = (byte) (0x80 | c & 0x3F);
            }
        }
        if (got.length != n) return false;
        for (int i = 0; i < n; i++) {
            if (got[i] != want[i]) return false;
        }
        return true;
    }

    /** MessageDigest.isEqual: one array, or two of one length with the same bytes. */
    public static boolean equal(byte[] a, byte[] b) {
        boolean want = a.length == b.length;
        for (int i = 0; want && i < a.length; i++) {
            want = a[i] == b[i];
        }
        return MessageDigest.isEqual(a, b) == want && MessageDigest.isEqual(a, a) && !MessageDigest.isEqual(a, null) && MessageDigest.isEqual(null, null);
    }

    /** Arrays.copyOf: a new array with the elements up to the shorter length and zero after them. */
    public static boolean copied(byte[] a, int n) {
        if (n < 0) {
            try {
                Arrays.copyOf(a, n);
                return false;
            } catch (NegativeArraySizeException e) {
                return true;
            }
        }
        if (n > 4) return true;
        byte[] got = Arrays.copyOf(a, n);
        if (got == a || got.length != n) return false;
        for (int i = 0; i < n; i++) {
            if (got[i] != (i < a.length ? a[i] : 0)) return false;
        }
        return true;
    }

    /** Integer.parseInt of ASCII text: a sign, digits, a value within an int; NumberFormatException for anything else. */
    public static boolean parsed(String s) {
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) >= 0x80) return true;
        }
        boolean negative = !s.isEmpty() && s.charAt(0) == '-';
        int from = !s.isEmpty() && (s.charAt(0) == '-' || s.charAt(0) == '+') ? 1 : 0;
        boolean bad = from == s.length();
        long value = 0;
        for (int i = from; !bad && i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                bad = true;
            } else {
                value = value * 10 + (c - '0');
                bad = value > 2147483648L;
            }
        }
        bad |= !negative && value == 2147483648L;
        try {
            int got = Integer.parseInt(s);
            return !bad && got == (int) (negative ? -value : value);
        } catch (NumberFormatException e) {
            return bad;
        }
    }

    /**
     * A builder's appends of a String, a char and an int of at most three digits, read back with charAt: the digits
     * are the only ones with no leading zero whose value is the magnitude.
     */
    public static boolean appended(String s, char c, int n) {
        if (n < -999 || n > 999) return true;
        StringBuilder b = new StringBuilder();
        b.append(s).append(c).append(n);
        for (int i = 0; i < s.length(); i++) {
            if (b.charAt(i) != s.charAt(i)) return false;
        }
        int at = s.length();
        if (b.charAt(at++) != c) return false;
        if (n < 0 && b.charAt(at++) != '-') return false;
        int count = b.length() - at;
        if (count < 1 || count > 3 || count > 1 && b.charAt(at) == '0') return false;
        int value = 0;
        for (int i = at; i < b.length(); i++) {
            char digit = b.charAt(i);
            if (digit < '0' || digit > '9') return false;
            value = value * 10 + (digit - '0');
        }
        if (value != (n < 0 ? -n : n)) return false;
        try {
            b.charAt(b.length());
            return false;
        } catch (IndexOutOfBoundsException e) {
            return true;
        }
    }

    /** The digits of the ints at the ends of the range, and of some between. */
    public static boolean digits() {
        return new StringBuilder().append(Integer.MIN_VALUE).append(' ').append(Integer.MAX_VALUE).append(' ').append(0).append(' ').append(-1).append(' ').append(1000000007).append(' ').append(-90210).toString().equals("-2147483648 2147483647 0 -1 1000000007 -90210");
    }

    static boolean salt(char c) {
        return c == '.' || c == '/' || c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9';
    }

    /** String.matches with classes, a group of alternatives and a count: a bcrypt hash's shape, its salt cut to two. */
    public static boolean shaped(String s) {
        boolean want = s.length() == 9 && s.charAt(0) == '$' && s.charAt(1) == '2' && (s.charAt(2) == 'a' || s.charAt(2) == 'b' || s.charAt(2) == 'y') && s.charAt(3) == '$';
        if (want) {
            char tens = s.charAt(4);
            char ones = s.charAt(5);
            want = (tens == '0' && ones >= '4' && ones <= '9' || (tens == '1' || tens == '2') && ones >= '0' && ones <= '9' || tens == '3' && ones == '0') && s.charAt(6) == '$' && salt(s.charAt(7)) && salt(s.charAt(8));
        }
        return s.matches("\\$2[aby]\\$(0[4-9]|[12][0-9]|30)\\$[./A-Za-z0-9]{2}") == want;
    }

    /** A compiled pattern with an anchor, an optional group, a class by its letter and a range of counts. */
    public static boolean anchored(String s) {
        int n = s.length();
        boolean want = n >= 2 && s.charAt(0) == '$' && s.charAt(1) == '2';
        int at = 2;
        if (want && at < n && (s.charAt(at) == 'a' || s.charAt(at) == 'y' || s.charAt(at) == 'b')) at++;
        want = want && at + 4 <= n && s.charAt(at) == '$' && s.charAt(at + 1) >= '0' && s.charAt(at + 1) <= '9' && s.charAt(at + 2) >= '0' && s.charAt(at + 2) <= '9' && s.charAt(at + 3) == '$';
        at += 4;
        want = want && (n - at == 1 || n - at == 2);
        for (int i = at; want && i < n; i++) {
            want = salt(s.charAt(i));
        }
        return Pattern.compile("\\A\\$2(a|y|b)?\\$(\\d\\d)\\$[./0-9A-Za-z]{1,2}").matcher(s).matches() == want;
    }

    /** Bytes in a charset the engine has no model of: the JDK's call, which it does not run. */
    public static boolean latin(String s) {
        return s.getBytes(StandardCharsets.ISO_8859_1).length == s.length();
    }

    /** Digits outside ASCII are digits to the JDK ("\u0663" is 3): the model does not say so, and says it does not. */
    public static boolean unicodeDigits(String s) {
        try {
            return Integer.parseInt(s) < 1000;
        } catch (NumberFormatException e) {
            return true;
        }
    }

    /** Throws for text of more than two UTF-8 bytes: what a throws clause over a String's bytes states. */
    public static int guarded(String s) {
        byte[] bytes = s.getBytes(StandardCharsets.UTF_8);
        if (bytes.length > 2) {
            throw new IllegalArgumentException("more than two bytes");
        }
        return bytes.length;
    }

    static final class Made {}

    /** A String is its own toString(), through CharSequence too, and an object's class is the class it was made of. */
    public static boolean itself(String s) {
        CharSequence chars = s;
        return chars.toString() == s && new Made().getClass() == Made.class && new Made().getClass().getName().equals("claims.B$Made");
    }

    /** A class whose initializer picks a method reference by what the class path holds, as a logging adapter does. */
    public static boolean adapted(String s) {
        return Adapters.MAKE.apply(s) == s;
    }

    /** A class that excludes, a count with no upper end and an empty alternative, of text with no surrogate. */
    public static boolean excluded(String s) {
        if (!R.bmp(s)) return true;
        boolean want = s.isEmpty();
        if (s.length() >= 3) {
            char c = s.charAt(0);
            want = c < 'a' || c > 'c';
            for (int i = 1; i < s.length(); i++) {
                want &= s.charAt(i) == 'x';
            }
        }
        return s.matches("[^a-c]x{2,}|") == want;
    }
}
