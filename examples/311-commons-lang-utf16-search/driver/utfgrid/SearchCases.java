package utfgrid;

import org.apache.commons.lang3.StringUtils;

public final class SearchCases {
    private static final int[] alphabet = {'a', 'b', 0x2070e, 'z'};

    static void enumerate(int[] tokens, int length) {
        StringBuilder actual = new StringBuilder();
        int encoding = 0, place = 1;
        for (int position = 0; position < length; position++) {
            actual.appendCodePoint(alphabet[tokens[position]]);
            encoding += place * (tokens[position] + 1);
            place *= 3;
        }
        for (int needle = 0; needle < alphabet.length; needle++) {
            int direct = StringUtils.lastIndexOf(actual, alphabet[needle]);
            System.out.printf("{\"sequence\":%d,\"needle\":%d,\"direct\":%d,\"adapter\":%d,\"expected\":%d}%n",
                              encoding, needle, direct, Search.last(encoding, needle), Search.expected(encoding, needle));
        }
        if (length != tokens.length) {
            for (int token = 0; token < 3; token++) {
                tokens[length] = token;
                enumerate(tokens, length + 1);
            }
        }
    }

    public static void main(String[] args) { enumerate(new int[3], 0); }
}
