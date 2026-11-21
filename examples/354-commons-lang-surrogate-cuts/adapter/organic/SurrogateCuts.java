package organic;

import org.apache.commons.lang3.StringUtils;

public final class SurrogateCuts {
    static final String GRIN = "\ud83d\ude00";
    static final String MIXED = "a\ud83d\ude00b";

    // Each node in the binary tree is the spelling of its ancestors followed by its final token.
    static String spelling(int node) {
        if (node == 1) return "";
        return spelling(node / 2) + ((node & 1) == 0 ? "a" : GRIN);
    }

    static int window(int code) {
        for (int node = 1; node <= 31; node++) {
            int widthChoices = spelling(node).length() + 2;
            int windows = widthChoices * widthChoices;
            if (code < windows) return node * 100 + code;
            code -= windows;
        }
        throw new IllegalArgumentException();
    }

    // Copy a token only when every one of its UTF-16 units lies inside the requested window.
    static String wholeTokens(String s, int start, int width) {
        StringBuilder kept = new StringBuilder();
        for (int p = 0; p < s.length();) {
            int cp = s.codePointAt(p);
            int next = p + Character.charCount(cp);
            if (p >= start && next <= start + width) kept.appendCodePoint(cp);
            p = next;
        }
        return kept.toString();
    }

    public static int truncate(int code) {
        int packed = window(code);
        String s = spelling(packed / 100);
        int side = s.length() + 2;
        int start = packed % 100 / side, width = packed % 100 % side;
        return StringUtils.truncate(s, start, width).equals(wholeTokens(s, start, width)) ? 1 : 0;
    }

    public static int fixedCut(int code) {
        int start = code % 36 / 6, width = code % 6;
        return StringUtils.truncate(MIXED, start, width).equals(wholeTokens(MIXED, start, width)) ? 1 : 0;
    }

    public static int abbreviate(int code) {
        int width = 4 + code % 2;
        String actual = StringUtils.abbreviate("\ud83d\ude00abcdef", width);
        return actual.equals(width == 4 ? "..." : "\ud83d\ude00...") ? 1 : 0;
    }
}
