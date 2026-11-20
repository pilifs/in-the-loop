package claims;

/** Each method compares a JDK String operation with its definition written out over charAt. */
public final class T {
    private T() {}

    static int refIndexOf(String s, String t, int from) {
        int n = s.length(), m = t.length();
        if (from < 0) from = 0;
        if (from > n) from = n;
        for (int i = from; i + m <= n; i++) {
            boolean all = true;
            for (int k = 0; k < m; k++) {
                if (s.charAt(i + k) != t.charAt(k)) { all = false; break; }
            }
            if (all) return i;
        }
        return -1;
    }

    public static boolean indexOfString(String s, String t, int from) {
        return s.indexOf(t, from) == refIndexOf(s, t, from) && s.indexOf(t) == refIndexOf(s, t, 0);
    }

    public static boolean indexOfChar(String s, char c, int from) {
        int want = -1;
        for (int i = Math.max(from, 0); i < s.length(); i++) {
            if (s.charAt(i) == c) { want = i; break; }
        }
        int first = -1;
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) == c) { first = i; break; }
        }
        return s.indexOf(c, from) == want && s.indexOf(c) == first;
    }

    /**
     * {@code lastIndexOf(int)}, written out: the last index whose unit is the character, or for a supplementary code
     * point whose unit and the next are its surrogate pair; -1 for none, and for a value that is no code point.
     */
    public static boolean lastIndexOfPoint(String s, int ch) {
        int want = -1;
        for (int i = 0; i < s.length(); i++) {
            if (ch >= 0 && ch < 0x10000) {
                if (s.charAt(i) == ch) want = i;
            } else if (ch >= 0x10000 && ch < 0x110000 && i + 1 < s.length()) {
                if (s.charAt(i) == 0xD800 + ((ch - 0x10000) >> 10) && s.charAt(i + 1) == 0xDC00 + ((ch - 0x10000) & 0x3ff)) want = i;
            }
        }
        return s.lastIndexOf(ch) == want;
    }

    public static boolean substring(String s, int b, int e) {
        String r;
        try {
            r = s.substring(b, e);
        } catch (StringIndexOutOfBoundsException x) {
            return b < 0 || e > s.length() || b > e;
        }
        if (b < 0 || e > s.length() || b > e) return false;
        if (r.length() != e - b) return false;
        for (int i = 0; i < r.length(); i++) {
            if (r.charAt(i) != s.charAt(b + i)) return false;
        }
        if ((r == s) != (b == 0 && e == s.length())) return false;
        if (e == b && !(b == 0 && e == s.length()) && r != "") return false;
        return s.substring(b).equals(s.substring(b, s.length()));
    }

    public static boolean endsWith(String s, String t) {
        boolean want = t.length() <= s.length();
        for (int k = 0; want && k < t.length(); k++) {
            if (s.charAt(s.length() - t.length() + k) != t.charAt(k)) want = false;
        }
        return s.endsWith(t) == want;
    }

    public static boolean lower(String s) {
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) >= 128) return true;
        }
        String r = s.toLowerCase();
        if (r.length() != s.length()) return false;
        boolean changed = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            char want = c >= 'A' && c <= 'Z' ? (char) (c + 32) : c;
            if (r.charAt(i) != want) return false;
            changed |= want != c;
        }
        return (r == s) == !changed;
    }

    public static boolean builder(String s, String t, int from, int b, int e) {
        StringBuilder sb = new StringBuilder(s);
        if (sb.length() != s.length()) return false;
        if (sb.indexOf(t, from) != refIndexOf(s, t, from)) return false;
        if (!sb.toString().equals(s)) return false;
        if ((sb.toString() == "") != s.isEmpty()) return false;
        String sub;
        try {
            sub = sb.substring(b, e);
        } catch (StringIndexOutOfBoundsException x) {
            return b < 0 || e > s.length() || b > e;
        }
        if (!sub.equals(s.substring(b, e))) return false;
        StringBuilder back = sb.delete(b, e);
        if (back != sb) return false;
        String want = s.substring(0, b) + s.substring(e);
        return sb.toString().equals(want) && sb.length() == s.length() - (e - b);
    }

    public static boolean deleteClamps(String s, int b, int e) {
        StringBuilder sb = new StringBuilder(s);
        try {
            sb.delete(b, e);
        } catch (StringIndexOutOfBoundsException x) {
            return b < 0 || b > Math.min(e, s.length());
        }
        if (b < 0 || b > Math.min(e, s.length())) return false;
        int end = Math.min(e, s.length());
        return sb.toString().equals(s.substring(0, b) + s.substring(end));
    }

    public static boolean longBuilder(int selector) {
        long value = Long.MIN_VALUE + (selector & 1);
        String expected = (selector & 1) == 0 ? "-9223372036854775808" : "-9223372036854775807";
        StringBuilder buf = new StringBuilder().append(value);
        if (!buf.toString().equals(expected)) return false;
        buf.setCharAt(1, 'X');
        try {
            buf.setCharAt(20, 'Y');
            return false;
        } catch (StringIndexOutOfBoundsException ex) {
            return buf.charAt(1) == 'X' && buf.charAt(19) == expected.charAt(19)
                && new StringBuilder().append(Long.MAX_VALUE).toString().equals("9223372036854775807");
        }
    }

    /** A call the checker has no model of changes the builder: what it held of the content is no longer so. */
    public static boolean reversed(String s) {
        StringBuilder sb = new StringBuilder(s);
        sb.reverse();
        return sb.length() == s.length();
    }
}
