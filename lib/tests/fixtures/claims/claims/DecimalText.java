package claims;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.regex.Pattern;

public final class DecimalText {
    static int stage;
    static class Later {
        static final int complete;
        static {
            stage = 1;
            Pattern.compile("(?=z)");
            stage = complete = 2;
        }
    }
    public static int initializeLater() { return Later.complete; }
    public static int observedStage() { return stage; }

    public static boolean compilesBlock() { return Pattern.compile("\\p{InCombiningDiacriticalMarks}+") != null; }

    public static boolean rounding() {
        // Just above a binary32 midpoint. Rounding to binary64 first loses the increment.
        String half = "1.0000000596046448";
        return Float.floatToRawIntBits(Float.valueOf(half)) == 0x3f800001
            && Float.floatToRawIntBits((float)Double.parseDouble(half)) == 0x3f800000
            && Float.floatToRawIntBits(Float.parseFloat(" -1e-100f ")) == 0x80000000
            && Double.valueOf(" +2e400D").isInfinite();
    }

    public static boolean formatting() {
        String text = Float.toString(Float.MIN_VALUE);
        return text.equals("1.4E-45") && text != Float.toString(Float.MIN_VALUE)
            && Double.toString(Double.MIN_VALUE).equals("4.9E-324")
            && Double.toString(-0.0) == "-0.0" && Float.toString(Float.NaN) == "NaN";
    }

    public static boolean coefficient() {
        BigDecimal value = new BigDecimal("-0.100000001490116122");
        BigDecimal shorter = BigDecimal.valueOf(-0.10000000149011612);
        BigInteger coefficient = BigInteger.valueOf(-100000001490116122L);
        return value.scale() == 18 && value.unscaledValue().equals(coefficient)
            && value.compareTo(shorter) < 0 && shorter.compareTo(value) > 0
            && new BigDecimal("0.1250").compareTo(new BigDecimal("0.125")) == 0;
    }

    @SuppressWarnings("deprecation")
    public static boolean byteRange() {
        byte[] input = {0, (byte)0xff, (byte)0x80};
        String copy = new String(input, 0x1d8, 1, 2);
        input[1] = 1;
        return copy.length() == 2 && copy.charAt(0) == 0xd8ff && copy.charAt(1) == 0xd880;
    }

    public static void main(String[] args) {
        if (!rounding() || !byteRange() || !coefficient() || !compilesBlock()
                || initializeLater() != 2 || observedStage() != 2) throw new AssertionError();
        if (args.length != 0 && !formatting()) throw new AssertionError();
    }
}
