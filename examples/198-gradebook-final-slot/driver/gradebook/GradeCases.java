package gradebook;

import java.util.Arrays;

/** Observe the return and the whole poststate of a fresh copy for every legal input. */
public final class GradeCases {
    public static void main(String[] args) {
        int combinations = 1;
        for (int length = 1; length <= 3; length++) {
            combinations *= 3;
            for (int code = 0; code < combinations; code++) {
                int[] original = new int[length];
                int digits = code;
                for (int i = 0; i < length; i++) {
                    original[i] = digits % 3;
                    digits /= 3;
                }
                for (int slot = 0; slot < length; slot++) {
                    for (int score = 0; score <= 2; score++) {
                        int[] actual = original.clone();
                        int previous = ScoreSheet.write(actual, slot, score);
                        System.out.printf("{\"scores\":%s,\"slot\":%d,\"score\":%d,\"result\":%d,\"after\":%s}%n",
                                Arrays.toString(original), slot, score, previous, Arrays.toString(actual));
                    }
                }
            }
        }
    }
}
