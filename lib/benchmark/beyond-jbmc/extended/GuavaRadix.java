import com.google.common.primitives.UnsignedInts;

public final class GuavaRadix {
    private static int parseWord(int word, boolean upper) {
        char[] digits = new char[8];
        String alphabet = upper ? "0123456789ABCDEF" : "0123456789abcdef";
        for (int pos = 7; pos >= 0; --pos) {
            digits[pos] = alphabet.charAt(word & 15);
            word >>>= 4;
        }
        return UnsignedInts.parseUnsignedInt(new String(digits), 16);
    }

    public static boolean word(int word, boolean upper) {
        return parseWord(word, upper) == word;
    }

    public static boolean outside(boolean negative) {
        try {
            UnsignedInts.parseUnsignedInt(negative ? "-1" : "100000000", 16);
            return false;
        } catch (NumberFormatException expected) {
            return true;
        }
    }

    public static boolean nonnegative(int word, boolean upper) {
        return parseWord(word, upper) >= 0;
    }
}
