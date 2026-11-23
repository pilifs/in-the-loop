import org.apache.commons.lang3.Conversion;

public final class UnsignedNibble {
    static boolean[] bits(int m) { return new boolean[]{(m & 8) != 0, (m & 4) != 0, (m & 2) != 0, (m & 1) != 0}; }
    static char digit(int n) { return (char) (n < 10 ? '0' + n : 'a' + n - 10); }
    public static boolean nibble(int m, int offset) {
        try { return Conversion.binaryBeMsb0ToHexDigit(bits(m), offset) == digit(m >>> offset) && offset >= 0 && offset < 4; }
        catch (IndexOutOfBoundsException e) { return e.getClass() == IndexOutOfBoundsException.class && (offset < 0 || offset >= 4); }
    }
    public static boolean left(int m) { return Conversion.binaryBeMsb0ToHexDigit(bits(m), 1) == digit((m << 1) & 15); }
    public static boolean acceptsNegative() {
        try { Conversion.binaryBeMsb0ToHexDigit(bits(10), -1); return true; }
        catch (IndexOutOfBoundsException expected) { return false; }
    }
}
