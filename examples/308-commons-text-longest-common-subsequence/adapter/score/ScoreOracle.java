package score;

/** Enumerate subsequences of one operand and test their membership in the other. */
public final class ScoreOracle {
    public static int expected(String left, String right) {
        int longest = 0;
        for (int mask = 0; mask < (1 << left.length()); mask++) {
            int next = 0;
            int length = 0;
            for (int i = 0; i < left.length(); i++) {
                if ((mask & (1 << i)) == 0) {
                    continue;
                }
                char selected = left.charAt(i);
                while (next < right.length() && right.charAt(next) != selected) {
                    next++;
                }
                if (next == right.length()) {
                    length = 0;
                    break;
                }
                next++;
                length++;
            }
            longest = Math.max(longest, length);
        }
        return longest;
    }

}
