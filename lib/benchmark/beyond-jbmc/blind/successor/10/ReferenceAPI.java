import net.htmlparser.jericho.CharacterReference;

public final class ReferenceAPI {
    public static long primary(int n) {
        String s = CharacterReference.encode(n == 0 ? "\u20ac" : "&");
        if ("\u20ac".equals(s)) return 1;
        if ("&euro;".equals(s)) return 2;
        return "&amp;".equals(s) ? 3 : -1;
    }
    public static long control(int n) { return "&amp;".equals(CharacterReference.encode("&")) ? 1 : 0; }
}
