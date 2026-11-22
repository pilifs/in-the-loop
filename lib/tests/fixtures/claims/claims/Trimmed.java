package claims;

public class Trimmed {
    public static boolean edges(char left, char right) {
        String source = new String(new char[]{left, 'x', right});
        String actual = source.trim();
        int start = left <= 0x20 ? 1 : 0;
        int end = right <= 0x20 ? 2 : 3;
        if (actual.length() != end - start) return false;
        for (int i = start; i < end; i++) if (source.charAt(i) != actual.charAt(i - start)) return false;
        return actual == source || start != 0 || end != 3;
    }

    public static boolean freshPoolIdentity(char ch) {
        String fresh = new String(new char[]{ch});
        return fresh.intern() == fresh;
    }

    public static boolean samples() {
        String empty = new String(new char[0]);
        String identity = new String(new char[]{'a', 0, 'b'});
        return empty.trim() == empty && identity.trim() == identity && "\t \n".trim().length() == 0
                && " \u00a0 \t".trim().equals("\u00a0") && " \uD800".trim().charAt(0) == '\uD800';
    }

    public static boolean changedIdentity() { return " a ".trim() == "a"; }

    public static void main(String[] args) {
        for (char a : new char[]{0, 0x20, 0x21, 0xa0, 0xd800})
            for (char b : new char[]{0, 0x20, 0x21, 0xa0, 0xdc00}) if (!edges(a, b)) throw new AssertionError();
        if (!samples()) throw new AssertionError();
    }
}
