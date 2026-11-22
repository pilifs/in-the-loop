package claims;

public final class LiteralReplacement {
    public static boolean contentsAndIdentity(String text) {
        String expanded = text.replace("\n", "\\n");
        String erased = text.replace("\n", "");
        StringBuilder copy = new StringBuilder();
        StringBuilder escape = new StringBuilder();
        boolean hit = false;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '\n') {
                escape.append('\\').append('n');
                hit = true;
            } else {
                copy.append(c);
                escape.append(c);
            }
        }
        return expanded.equals(escape.toString()) && erased.equals(copy.toString())
            && (expanded == text) == !hit && (erased == text) == !hit
            && (!hit || !erased.isEmpty() || erased == "") && text.replace("\n", "\n") == text;
    }

    public static boolean takesReplacementIdentity() {
        String withLine = new String(new char[]{'\n'});
        return withLine.replace("\n", "\\n") == "\\n";
    }

    static final class Sequence implements CharSequence {
        int calls;
        public int length() { return 1; }
        public char charAt(int i) { return 'x'; }
        public CharSequence subSequence(int start, int end) { return "x".subSequence(start, end); }
        public String toString() { calls++; return "x"; }
    }

    public static boolean callback() {
        Sequence target = new Sequence();
        String result = "xy".replace(target, "zz");
        return target.calls == 1 && "zzy".equals(result);
    }

    public static void main(String[] args) {
        for (String s : new String[]{"", "\0", "\n", "\n\n", "x\n", "\uD800\n\uDC00", "\u03A9", "\u00E9\n"})
            if (!contentsAndIdentity(s)) throw new AssertionError();
        if (takesReplacementIdentity() || !callback()) throw new AssertionError();
    }
}
