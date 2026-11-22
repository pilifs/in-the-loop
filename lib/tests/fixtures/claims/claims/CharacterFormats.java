package claims;

import java.util.Arrays;
import java.util.Objects;

public final class CharacterFormats {
    static boolean failTable;
    static final class Lookup {
        static final int[] TABLE = new int[2];
        static {
            for (int i = 0; i < TABLE.length; i++) {
                if (i < 0) System.getProperties().size();
                if (i == 1 && failTable) throw new IllegalArgumentException();
                TABLE[i] = i;
            }
        }
    }

    public static boolean tableStartup(boolean fail) {
        failTable = fail;
        try {
            int n = Lookup.TABLE[1];
            return !fail && n == 1;
        } catch (ExceptionInInitializerError error) {
            if (!fail || !(error.getCause() instanceof IllegalArgumentException)) return false;
            try { return Lookup.TABLE.length == 0; } catch (NoClassDefFoundError expected) { return true; }
        }
    }

    public static boolean latinIdentifiers(char ch) {
        boolean expected = ch <= 8 || (ch >= 14 && ch <= 27) || ch == '$' || (ch >= '0' && ch <= '9')
            || (ch >= 'A' && ch <= 'Z') || ch == '_' || (ch >= 'a' && ch <= 'z')
            || (ch >= 0x7f && ch <= 0x9f) || (ch >= 0xa2 && ch <= 0xa5) || ch == 0xaa || ch == 0xad
            || ch == 0xb5 || ch == 0xba || (ch >= 0xc0 && ch <= 0xd6) || (ch >= 0xd8 && ch <= 0xf6) || ch >= 0xf8;
        return Character.isJavaIdentifierPart(ch) == expected && Character.isJavaIdentifierPart((int) ch) == expected;
    }

    public static boolean copiesAndFills(int value) {
        int[] source = {1, 2};
        int[] alias = source;
        Arrays.fill(source, value);
        int[] copy = Arrays.copyOf(source, 2);
        int[] grown = Arrays.copyOf(source, 3);
        if (copy == source || grown[2] != 0 || copy[1] != value || alias[0] != value) return false;
        copy[0] = ~value;
        if (grown[0] != value || source[0] != value) return false;
        try { Arrays.copyOf(source, -1); return false; } catch (NegativeArraySizeException expected) { }
        try { Arrays.fill((int[]) null, value); return false; } catch (NullPointerException expected) { return true; }
    }

    public static boolean outsideLatin1() { return !Character.isJavaIdentifierPart('\u0100'); }

    private enum Quote { SINGLE, DOUBLE }

    public static boolean hashContract(boolean quoted, boolean limit) {
        long rows = limit ? 2 : 10;
        Quote style = quoted ? Quote.SINGLE : Quote.DOUBLE;
        Object[] first = {quoted, rows, style};
        Object[] second = {Boolean.valueOf(quoted), Long.valueOf(rows), style};
        return Objects.hash(first) == Objects.hash(second) && Long.valueOf(rows) == Long.valueOf(rows)
                && Boolean.valueOf(quoted).hashCode() == (quoted ? 1231 : 1237)
                && Long.valueOf(rows).hashCode() == (int) rows;
    }

    public static boolean assumesDistinctHashes() {
        return Quote.SINGLE.hashCode() != Quote.DOUBLE.hashCode();
    }
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

    public static boolean clockSeed() {
        long time = System.currentTimeMillis();
        int seed = ((int)time + (int)(time >>> 32)) | 1;
        Object object = new Object();
        java.util.concurrent.atomic.AtomicReference<Object> ref = new java.util.concurrent.atomic.AtomicReference<>(object);
        if (ref.get() != object || System.identityHashCode(object) != System.identityHashCode(ref.get())) return false;
        ref.set(null);
        return (seed & 1) == 1 && ref.get() == null && System.identityHashCode(null) == 0;
    }
    public static boolean sameTime() { return System.currentTimeMillis() == System.currentTimeMillis(); }
    static final class Copyable implements Cloneable {
        Copyable copy() throws CloneNotSupportedException { return (Copyable) super.clone(); }
    }
    public static boolean copiedHash() throws CloneNotSupportedException {
        Copyable source = new Copyable();
        int hash = System.identityHashCode(source);
        return hash == System.identityHashCode(source.copy());
    }

    public static boolean expectsUnixContents() { return System.lineSeparator().equals("\n"); }
    public static boolean expectsInternedIdentity() { return System.lineSeparator() == "\n"; }

    public static void main(String[] args) {
        if (args.length == 1) {
            if (!tableStartup(Boolean.parseBoolean(args[0]))) throw new AssertionError("table initialization");
            return;
        }
        if (!clockSeed()) throw new AssertionError("clock and identity");
        for (int c = 0; c < 256; c++) if (!latinIdentifiers((char) c)) throw new AssertionError(c);
        if (outsideLatin1()) throw new AssertionError("U+0100 uses a different character table");
        if (!copiesAndFills(Integer.MIN_VALUE)) throw new AssertionError("array copy");
        if (!boxed(false) || !boxed(true) || !arrays(false) || !arrays(true) || wrong() || !separator()) throw new AssertionError();
        for (int i = 0; i < 4; i++) if (!cached(i)) throw new AssertionError();
        for (boolean q : new boolean[] {false, true}) if (!hashContract(q, false) || !hashContract(q, true)) throw new AssertionError();
    }
}
