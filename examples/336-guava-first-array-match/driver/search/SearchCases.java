package search;

import com.google.common.primitives.Ints;
import java.util.Arrays;

public final class SearchCases {
    public static void main(String[] args) {
        int[] alphabet = {Integer.MIN_VALUE, 7, Integer.MAX_VALUE};
        int code = 0;
        for (int length = 0, patterns = 1; length <= 4; length++, patterns *= 3) {
            for (int pattern = 0; pattern < patterns; pattern++) {
                for (int target : alphabet) {
                    int[] input = new int[length];
                    int digits = pattern;
                    for (int i = 0; i < length; i++, digits /= 3) input[i] = alphabet[digits % 3];
                    String before = Arrays.toString(input);
                    int result = Ints.indexOf(input, target);
                    System.out.printf("{\"id\":%d,\"before\":%s,\"target\":%d,\"result\":%d,\"after\":%s}%n",
                            code++, before, target, result, Arrays.toString(input));
                }
            }
        }
    }
}
