package utfgrid;

import org.apache.commons.lang3.StringUtils;

public final class Search {
    static int character(int token) {
        return token == 0 ? 'a' : token == 1 ? 'b' : token == 2 ? 0x2070e : 'z';
    }

    public static int last(int encoding, int needle) {
        StringBuilder sequence = new StringBuilder();
        for (int n = encoding; n != 0; n = (n - 1) / 3) sequence.appendCodePoint(character((n - 1) % 3));
        return StringUtils.lastIndexOf(sequence, character(needle));
    }

    public static int expected(int encoding, int needle) {
        int index = 0, last = -1;
        for (int n = encoding; n != 0; n = (n - 1) / 3) {
            int token = (n - 1) % 3;
            if (token == needle) last = index;
            index += token == 2 ? 2 : 1;
        }
        return last;
    }
}
