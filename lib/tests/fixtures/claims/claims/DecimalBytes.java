package claims;

import java.math.BigDecimal;
import java.math.BigInteger;

public final class DecimalBytes {
    public static boolean exact(boolean negative, boolean wide) {
        byte high = negative ? (byte)-128 : 127;
        byte[] bytes = wide ? new byte[]{high, (byte)255} : new byte[]{high};
        BigInteger integer = new BigInteger(bytes);
        BigDecimal decimal = new BigDecimal(integer, negative ? 2 : 0);
        int expected = wide ? high * 256 + 255 : high;
        bytes[0] = 0;
        return decimal.unscaledValue().intValueExact() == expected && decimal.scale() == (negative ? 2 : 0);
    }

    public static boolean empty() {
        try {
            new BigInteger(new byte[0]);
            return false;
        } catch (NumberFormatException expected) {
            return true;
        }
    }

    public static boolean wrongSign() {
        return new BigDecimal(new BigInteger(new byte[]{(byte)128}), 2).unscaledValue().intValueExact() == 128;
    }

    public static void main(String[] args) {
        for (boolean negative : new boolean[]{false, true})
            for (boolean wide : new boolean[]{false, true})
                if (!exact(negative, wide)) throw new AssertionError();
        if (!empty() || wrongSign()) throw new AssertionError();
    }
}
