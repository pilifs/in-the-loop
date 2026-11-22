package datawork;

import java.math.BigDecimal;
import org.apache.commons.lang3.math.NumberUtils;

public final class Decimals {
    public static String exact(int code) {
        return switch (code) { case 0 -> "0.100000001490116121"; case 1 -> "0.100000001490116122";
                              default -> "-0.100000001490116121"; };
    }
    public static String control(int code) { return code == 0 ? "0.1" : code == 1 ? "0.5" : "17"; }

    /** Parse the coefficient in bounded signed integer arithmetic and count the fractional digits. */
    public static int precise(int code) {
        String text = exact(code);
        Number parsed = NumberUtils.createNumber(text);
        if (!(parsed instanceof BigDecimal decimal)) return 0;
        long coeff = 0;
        int fractional = -1;
        for (int i = text.charAt(0) == '-' ? 1 : 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch == '.') fractional = 0;
            else {
                coeff = coeff * 10 + ch - '0';
                if (fractional >= 0) fractional++;
            }
        }
        if (text.charAt(0) == '-') coeff = -coeff;
        return decimal.scale() == fractional && decimal.unscaledValue().equals(java.math.BigInteger.valueOf(coeff)) ? 1 : 0;
    }

    public static int preserved(int code) {
        Number parsed = NumberUtils.createNumber(control(code));
        boolean ok = code == 2 ? parsed instanceof Integer && parsed.intValue() == 17
                : parsed instanceof Float && Float.floatToRawIntBits(parsed.floatValue()) == (code == 0 ? 0x3dcccccd : 0x3f000000);
        try { NumberUtils.createNumber("1eE"); return 0; }
        catch (NumberFormatException rejected) { return ok && rejected.getClass() == NumberFormatException.class ? 1 : 0; }
    }
}
