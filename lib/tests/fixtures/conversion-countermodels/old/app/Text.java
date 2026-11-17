package app;

import java.io.UnsupportedEncodingException;
import java.nio.charset.StandardCharsets;

/** The previous version of the conversion countermodels. Each method converts a String `s` to bytes and returns what is at index `k`: the byte, or
 * for an index outside the bytes 256 and how many there are. So two conversions that give different bytes give
 * different results at some `s` and `k`, and a check compares one byte, not a sum of all of them. The other version is beside this one
 * (`../../new/app/Text.java`); the README says for each method what a JVM gives for both and what a check of the
 * pair may say. */
public final class Text {
    private Text() {}

    /** A String this short is encoded into an array of a constant size, which a checker that bounds a String's
     * length takes without knowing how large a computed size may be. */
    static final int SHORT = 4;

    /** Of the first `n` bytes, the one at `k`; outside them, 256 and `n` (no byte is that large). */
    static int at(byte[] b, int n, int k) {
        return k < 0 || k >= n ? 256 + n : b[k];
    }

    /** Of a conversion's bytes, the one at `k`. */
    static int weigh(byte[] b, int k) {
        return at(b, b.length, k);
    }

    /** UTF-8 written out, as the JDK encodes a String (`String.encodeUTF8`): one byte below 0x80, two below 0x800,
     * four for a high surrogate followed by a low one, three otherwise. `lone` is what a surrogate in no pair
     * becomes: 1 for the one byte '?', as the JDK has it, 3 for its three bytes (what "WTF-8" writes). `pairs`
     * false writes a pair as its two units, each by `lone` (what "CESU-8" writes with 3). The result is
     * what `at` gives of the bytes. */
    static int encoded(String s, int lone, boolean pairs, int k) {
        byte[] out = s.length() <= SHORT ? new byte[3 * SHORT] : new byte[3 * s.length()];
        int n = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < 0x80) {
                out[n++] = (byte) c;
            } else if (c < 0x800) {
                out[n++] = (byte) (0xC0 | c >> 6);
                out[n++] = (byte) (0x80 | c & 0x3F);
            } else if (pairs && c >= 0xD800 && c < 0xDC00 && i + 1 < s.length() && s.charAt(i + 1) >= 0xDC00 && s.charAt(i + 1) < 0xE000) {
                int point = 0x10000 + ((c - 0xD800) << 10) + (s.charAt(++i) - 0xDC00);
                out[n++] = (byte) (0xF0 | point >> 18);
                out[n++] = (byte) (0x80 | point >> 12 & 0x3F);
                out[n++] = (byte) (0x80 | point >> 6 & 0x3F);
                out[n++] = (byte) (0x80 | point & 0x3F);
            } else if (c >= 0xD800 && c < 0xE000 && lone == 1) {
                out[n++] = '?';
            } else {
                out[n++] = (byte) (0xE0 | c >> 12);
                out[n++] = (byte) (0x80 | c >> 6 & 0x3F);
                out[n++] = (byte) (0x80 | c & 0x3F);
            }
        }
        return at(out, n, k);
    }

    /** US-ASCII written out, as the JDK encodes a String (`String.encodeASCII`): a unit below 0x80 is itself, and
     * anything else is '?'. With `pairs`, a high surrogate followed by a low one is one '?' for the two, as the
     * JDK has it; without, each unit is its own '?'. The result is what `at` gives of the
     * bytes. */
    static int plain(String s, boolean pairs, int k) {
        byte[] out = s.length() <= SHORT ? new byte[SHORT] : new byte[s.length()];
        int n = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < 0x80) {
                out[n++] = (byte) c;
            } else {
                if (pairs && c >= 0xD800 && c < 0xDC00 && i + 1 < s.length() && s.charAt(i + 1) >= 0xDC00 && s.charAt(i + 1) < 0xE000) {
                    i++;
                }
                out[n++] = '?';
            }
        }
        return at(out, n, k);
    }

    /** The named conversion of 307's previous revision, with its handler. */
    static byte[] byName(String s, String name) {
        try {
            return s.getBytes(name);
        } catch (UnsupportedEncodingException e) {
            throw new AssertionError(name + " is not supported");
        }
    }

    /** 307's previous revision: the charset by its name, in a handler for a name the JDK lacks. */
    public static int named(String s, int k) {
        return weigh(byName(s, "UTF-8"), k);
    }

    /** The name is an alias of UTF-8 (the JDK's `charsets` list: UTF8, unicode-1-1-utf-8). */
    public static int alias(String s, int k) {
        return weigh(byName(s, "UTF8"), k);
    }

    /** UTF-8 written out, a lone surrogate as '?'. */
    public static int written(String s, int k) {
        return encoded(s, 1, true, k);
    }

    /** US-ASCII written out, a pair of surrogates as one '?'. */
    public static int asciiWritten(String s, int k) {
        return plain(s, true, k);
    }

    /** Another charset by its name: every unit from 0x80 is '?'. */
    public static int ascii(String s, int k) {
        return weigh(byName(s, "US-ASCII"), k);
    }

    /** Another charset by its name: a unit below 0x100 is one byte. */
    public static int latin(String s, int k) {
        return weigh(byName(s, "ISO-8859-1"), k);
    }

    /** A name no JDK has: the handler runs on every String. */
    public static int unknown(String s, int k) {
        try {
            return weigh(s.getBytes("UTF-9"), k);
        } catch (UnsupportedEncodingException e) {
            return -1;
        }
    }

    /** The name is chosen when the method runs: US-ASCII for a String of two units. */
    public static int chosen(String s, int k) {
        return weigh(byName(s, s.length() == 2 ? "US-ASCII" : "UTF-8"), k);
    }

    /** The platform's default charset: UTF-8 on JDK 18 and later unless the JVM is started with -Dfile.encoding=COMPAT. */
    public static int defaulted(String s, int k) {
        return weigh(s.getBytes(), k);
    }

    /** UTF-8 written out with a lone surrogate as its three bytes. */
    public static int lone(String s, int k) {
        return encoded(s, 3, true, k);
    }

    /** UTF-8 written out with a pair of surrogates as two units of three bytes each. */
    public static int paired(String s, int k) {
        return encoded(s, 3, false, k);
    }

    /** US-ASCII written out with each surrogate of a pair as its own '?'. */
    public static int asciiPairs(String s, int k) {
        return plain(s, false, k);
    }

    static String units(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            b.append(i == 0 ? "" : ",").append(Integer.toHexString(s.charAt(i)));
        }
        return b.toString();
    }

    interface Method {
        int at(String s, int k);
    }

    /** Each method on the Strings that tell the conversions apart, one line a method: `name unit,unit=results ...`,
     * the results at every index from -1 to 12, joined by `.`. An exception is its class's name. */
    public static void main(String[] args) {
        String[] inputs = {"", "a", "ab", "\u00E9", "\u20AC", "\uD800", "\uDC00", "\uD83D\uDE00", "\uDE00\uD83D", "a\u00E9", "\uD83D\uDE00a", null};
        Method[] methods = {Text::named, Text::alias, Text::written, Text::asciiWritten, Text::ascii, Text::latin, Text::unknown, Text::chosen, Text::defaulted,
            Text::lone, Text::paired, Text::asciiPairs};
        String[] names = {"named", "alias", "written", "asciiWritten", "ascii", "latin", "unknown", "chosen", "defaulted", "lone", "paired", "asciiPairs"};
        for (int m = 0; m < names.length; m++) {
            StringBuilder line = new StringBuilder(names[m]);
            for (String s : inputs) {
                StringBuilder got = new StringBuilder();
                for (int k = -1; k <= 12; k++) {
                    try {
                        got.append(k == -1 ? "" : ".").append(methods[m].at(s, k));
                    } catch (Throwable t) {
                        got.setLength(0);
                        got.append(t.getClass().getName());
                        break;
                    }
                }
                line.append(' ').append(s == null ? "null" : units(s)).append('=').append(got);
            }
            System.out.println(line);
        }
    }
}
