package score;

import org.apache.commons.text.similarity.LongestCommonSubsequence;

/** Both CharSequence parameters of the public method receive actual Strings. */
public final class LcsScore {
    public static String word(int index) {
        switch (index) {
            case 0: return "";
            case 1: return "a";
            case 2: return "b";
            case 3: return "aa";
            case 4: return "ab";
            case 5: return "ba";
            case 6: return "bb";
            case 7: return "aaa";
            case 8: return "aab";
            case 9: return "aba";
            case 10: return "abb";
            case 11: return "baa";
            case 12: return "bab";
            case 13: return "bba";
            case 14: return "bbb";
            default: throw new IllegalArgumentException();
        }
    }

    public static int score(int left, int right) {
        return new LongestCommonSubsequence().apply(word(left), word(right));
    }
}
