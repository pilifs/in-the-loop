package claims;

import java.util.Arrays;
import java.util.Objects;

public final class CharacterFormats {
    public static boolean boxed(boolean high) {
        char c = high ? (char) 0xd800 : (char) 127;
        Character a = Character.valueOf(c), b = Character.valueOf(c);
        String s = String.valueOf(c);
        return a.charValue() == c && a.equals(b) && !a.equals(null) && !a.equals(s)
                && a.hashCode() == c && (high || a == b)
                && s.length() == 1 && s.charAt(0) == c && s != String.valueOf(c)
                && ("[" + a + "]").charAt(1) == c && String.valueOf((Object) a).equals(s);
    }

    public static boolean cached(int index) {
        char c = (char) (index & 3);
        return Character.valueOf(c) == Character.valueOf(c) && Character.valueOf(c).charValue() == c;
    }

    public static boolean arrays(boolean high) {
        Character c = high ? 'z' : (char) 0xffff;
        Object[] a = {null, c}, b = {null, Character.valueOf(c.charValue())};
        return Arrays.equals(a, b) && Objects.hash(a) == 31 * 31 + c.charValue()
                && !Arrays.equals(a, new Object[] {c, null})
                && Arrays.equals((Object[]) null, null) && Arrays.hashCode((Object[]) null) == 0;
    }

    public static boolean wrong() {
        return Objects.equals(Character.valueOf('A'), Character.valueOf('B'));
    }

    public static boolean separator() {
        String separator = System.lineSeparator();
        return separator != null && separator == System.lineSeparator();
    }

    public static boolean expectsUnixContents() { return System.lineSeparator().equals("\n"); }
    public static boolean expectsInternedIdentity() { return System.lineSeparator() == "\n"; }

    public static void main(String[] args) {
        if (!boxed(false) || !boxed(true) || !arrays(false) || !arrays(true) || wrong() || !separator()) throw new AssertionError();
        for (int i = 0; i < 4; i++) if (!cached(i)) throw new AssertionError();
    }
}
