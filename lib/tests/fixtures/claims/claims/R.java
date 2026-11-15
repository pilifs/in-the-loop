package claims;

import java.util.Arrays;
import java.util.regex.Pattern;

/** The regex a claim states a glob with, against a matcher written out over charAt. */
public final class R {
    private R() {}

    static boolean same(char a, char b, boolean ignoreCase) {
        if (a == b) return true;
        if (!ignoreCase) return false;
        char x = a >= 'A' && a <= 'Z' ? (char) (a + 32) : a;
        char y = b >= 'A' && b <= 'Z' ? (char) (b + 32) : b;
        return x == y;
    }

    /** Whether the glob p ('*' any sequence, anything else itself) matches all of s: by positions reached. */
    static boolean glob(String p, String s, boolean ignoreCase) {
        boolean[] reach = new boolean[s.length() + 1];
        reach[0] = true;
        for (int i = 0; i < p.length(); i++) {
            char c = p.charAt(i);
            boolean[] next = new boolean[s.length() + 1];
            if (c == '*') {
                boolean seen = false;
                for (int j = 0; j <= s.length(); j++) {
                    seen |= reach[j];
                    next[j] = seen;
                }
            } else {
                for (int j = 0; j < s.length(); j++) {
                    next[j + 1] = reach[j] && same(c, s.charAt(j), ignoreCase);
                }
            }
            reach = next;
        }
        return reach[s.length()];
    }

    static boolean bmp(String s) {
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c >= 0xD800 && c <= 0xDFFF) return false;
        }
        return true;
    }

    static boolean regex(String p, String s, int flags) {
        return Pattern.compile(String.join(".*", Arrays.stream(p.split("\\*", -1)).map(Pattern::quote).toArray(String[]::new)), flags).matcher(s).matches();
    }

    public static boolean exact(String p, String s) {
        if (!bmp(p) || !bmp(s)) return true;
        return regex(p, s, Pattern.DOTALL) == glob(p, s, false);
    }

    public static boolean ignoringCase(String p, String s) {
        if (!bmp(p) || !bmp(s)) return true;
        return regex(p, s, Pattern.CASE_INSENSITIVE | Pattern.DOTALL) == glob(p, s, true);
    }

    /** Split at a character: as many parts as occurrences and one, which joined by it are the String. */
    public static boolean parts(String s) {
        String[] parts = s.split("\\*", -1);
        int stars = 0;
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) == '*') stars++;
        }
        if (parts.length != stars + 1) return false;
        if (stars == 0 && parts[0] != s) return false;
        StringBuilder all = new StringBuilder();
        int at = 0;
        for (int k = 0; k < parts.length; k++) {
            String part = parts[k];
            if (part.indexOf('*') >= 0) return false;
            if (stars > 0 && part.isEmpty() && part != "") return false;
            for (int i = 0; i < part.length(); i++) {
                if (s.charAt(at++) != part.charAt(i)) return false;
            }
            if (k + 1 < parts.length && s.charAt(at++) != '*') return false;
        }
        return at == s.length();
    }

    /** A constant regex in the engine's syntax: a dot without DOTALL stops at a line terminator. */
    public static boolean constant(String s) {
        if (!bmp(s)) return true;
        boolean want = s.length() >= 2 && s.charAt(0) == 'a' && s.charAt(s.length() - 1) == '+';
        for (int i = 1; i + 1 < s.length(); i++) {
            char c = s.charAt(i);
            want &= c != '\n' && c != '\r' && c != '\u0085' && c != ' ' && c != ' ';
        }
        return Pattern.compile("a.*\\+", 0).matcher(s).matches() == want;
    }

}
