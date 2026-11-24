package claims;

public final class Radix {
    public static boolean hex(char c) {
        if (c >= 128) return true;
        int digit = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10
            : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
        try {
            return Integer.parseInt(new String(new char[]{'-', '2', c}), 16) == -32-digit && digit >= 0;
        } catch (NumberFormatException expected) {
            return digit < 0;
        }
    }

    private static boolean rejected(String text, int radix, boolean wide) {
        try {
            if (wide) Long.parseLong(text, radix);
            else Integer.parseInt(text, radix);
            return false;
        } catch (NumberFormatException expected) {
            return true;
        }
    }

    public static boolean limits() {
        return Integer.parseInt("-80000000", 16) == Integer.MIN_VALUE
            && Integer.parseInt("+7FffffFF", 16) == Integer.MAX_VALUE
            && Long.parseLong("-1y2p0ij32e8e8", 36) == Long.MIN_VALUE
            && Long.parseLong("+1Y2P0IJ32E8E7", 36) == Long.MAX_VALUE
            && rejected("80000000", 16, false) && rejected("-80000001", 16, false)
            && rejected("100000000000000000000", 16, false)
            && rejected("1y2p0ij32e8e8", 36, true) && rejected("-1y2p0ij32e8e9", 36, true)
            && Integer.parseInt("101", 2) == 5 && rejected("102", 2, false)
            && rejected(null, 16, true) && rejected("+", 16, false)
            && rejected("0", -1, false) && rejected("0", 37, true);
    }

    public static boolean unicode() { return Integer.parseInt("\u0661", 16) == 1; }
    public static boolean wrong(boolean withSign) { return Integer.parseInt(withSign ? "-a" : "A", 16) == 10; }

    public static void main(String[] args) {
        for (char c = 0; c < 128; ++c) if (!hex(c)) throw new AssertionError();
        if (!limits() || !unicode() || !wrong(false) || wrong(true)) throw new AssertionError();
    }
}
