package search;

import com.google.common.primitives.Longs;
import java.util.Arrays;

public final class SearchCases {
    public static void main(String[] args) {
        long[] alphabet = {Long.MIN_VALUE, 7L, (1L << 40) + 7L, Long.MAX_VALUE};
        int code = 0;
        for (int length = 0, patterns = 1; length <= 4; length++, patterns *= alphabet.length) {
            for (int pattern = 0; pattern < patterns; pattern++) {
                for (long target : alphabet) {
                    long[] input = new long[length];
                    int digits = pattern;
                    for (int i = 0; i < length; i++, digits /= alphabet.length) input[i] = alphabet[digits % alphabet.length];
                    String before = Arrays.toString(input);
                    int result = Longs.indexOf(input, target);
                    System.out.printf("{\"id\":%d,\"before\":%s,\"target\":%d,\"result\":%d,\"after\":%s}%n",
                            code++, before, target, result, Arrays.toString(input));
                }
            }
        }
    }
}
