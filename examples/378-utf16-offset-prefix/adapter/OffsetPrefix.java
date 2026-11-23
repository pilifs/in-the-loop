public final class OffsetPrefix {
    static boolean oracle(String text, String prefix, int off) {
        if (off < 0 || off > text.length() - prefix.length()) return false;
        for (int i = 0; i < prefix.length(); i++)
            if (text.charAt(off + i) != prefix.charAt(i)) return false;
        return true;
    }
    public static boolean small(int off, boolean empty) {
        return "ababa".startsWith(empty ? "" : "ba", off)
                == (empty ? off >= 0 && off <= 5 : off == 1 || off == 3);
    }
    public static boolean beforeEnd(int off) { return "ababa".startsWith("", off) == (off >= 0 && off < 5); }
    public static boolean wide(String text, String prefix, int off) {
        return text.startsWith(prefix, off) == oracle(text, prefix, off);
    }
    public static boolean nullPrefix(int off) {
        try { "ababa".startsWith(null, off); return false; }
        catch (NullPointerException expected) { return true; }
    }
}
