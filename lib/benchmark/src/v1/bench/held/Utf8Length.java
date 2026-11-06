package bench.held;

/** The bytes UTF-8 takes for a sequence of chars, each surrogate counted as three bytes as CESU-8 does, char by char (v1). */
public final class Utf8Length {
    private Utf8Length() {
    }

    public static int length(char[] cs) {
        int n = 0;
        for (char c : cs) {
            n += c < 0x80 ? 1 : c < 0x800 ? 2 : 3;
        }
        return n;
    }
}
