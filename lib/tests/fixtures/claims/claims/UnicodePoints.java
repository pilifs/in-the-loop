package claims;

import java.util.regex.Pattern;

public class UnicodePoints {
    static final class Blocks {
        static final Pattern MARKS = Pattern.compile("\\p{InCombiningDiacriticalMarks}+");
        static final Pattern OTHER = Pattern.compile("\\P{InBasicLatin}");
    }

    public static boolean encoding(int point) {
        StringBuilder out = new StringBuilder("x");
        if (point < 0 || point > 0x10ffff) {
            try { out.appendCodePoint(point); return false; } catch (IllegalArgumentException expected) {}
            try { Character.toChars(point); return false; } catch (IllegalArgumentException expected) {}
            return out.length() == 1 && out.charAt(0) == 'x';
        }
        char[] units = Character.toChars(point);
        if (out.appendCodePoint(point) != out || out.length() != units.length + 1 || out.charAt(0) != 'x') return false;
        if (point < 0x10000) {
            if (units.length != 1 || units[0] != (char) point) return false;
        } else {
            int offset = point - 0x10000;
            if (units.length != 2 || units[0] != (char) (0xd800 + offset / 1024)
                    || units[1] != (char) (0xdc00 + offset % 1024) || out.charAt(2) != units[1]) return false;
        }
        char first = units[0];
        units[0] = 0;
        return Character.toChars(point)[0] == first && out.charAt(1) == first;
    }

    public static boolean block(char c) {
        String s = new StringBuilder().append(c).toString();
        return Blocks.MARKS.matcher(s).matches() == (c >= 0x300 && c <= 0x36f)
                && (c >= 0xd800 && c <= 0xdfff || Blocks.OTHER.matcher(s).matches() == (c > 0x7f));
    }

    public static void main(String[] args) {
        for (int c = 0; c <= 0xffff; c++) {
            if (!block((char) c) || !encoding(c)) throw new AssertionError(c);
        }
        for (int c : new int[]{-1, Integer.MIN_VALUE, 0x10000, 0x2070e, 0x10ffff, 0x110000, Integer.MAX_VALUE}) {
            if (!encoding(c)) throw new AssertionError(c);
        }
    }
}
