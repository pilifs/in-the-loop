package bench.held;

/** The bytes UTF-8 takes for a sequence of chars, each surrogate counted as three bytes as CESU-8 does, with a fast path over a leading ASCII run (v2). */
public final class Utf8Length {
    private Utf8Length() {
    }

    public static int length(char[] cs) {
        int i = 0;
        int n = cs.length;
        while (i < n && cs[i] < 0x80) {
            i++;
        }
        int length = i;
        for (; i < n; i++) {
            char c = cs[i];
            if (c < 0x80) {
                length++;
            } else if (c < 0x800) {
                length += 2;
            } else {
                length += 3;
            }
        }
        return length;
    }
}
