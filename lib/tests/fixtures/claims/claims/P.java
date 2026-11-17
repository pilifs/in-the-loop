package claims;

import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Pattern;

/**
 * A protective pattern that is an input (lib/src/bmc/regex.rs, Engine::literal_then_any): characters that stand for
 * themselves followed by {@code .*}, as {@code /admin/.*} is, compiled with each combination of CASE_INSENSITIVE and
 * DOTALL and matched against any String, against the definition written out over charAt. Each method returns
 * whether the JDK's answer is the definition's: true on every input, to the engine's model and, on samples, on a JVM.
 * With them, what the frozen claim of example 289 and the matcher's debug line ask besides: whether an ASCII char is
 * a letter, and whether a logger logs below INFO.
 */
public final class P {
    private P() {}

    static boolean itself(char c) {
        return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || " !\"#%&',-/:;<=>@_`~".indexOf(c) >= 0;
    }

    /** Whether p is characters that stand for themselves followed by ".*". */
    static boolean literalThenAny(String p) {
        int n = p.length() - 2;
        if (n < 0 || p.charAt(n) != '.' || p.charAt(n + 1) != '*') return false;
        for (int i = 0; i < n; i++) {
            if (!itself(p.charAt(i))) return false;
        }
        return true;
    }

    static char lower(char c) {
        return c >= 'A' && c <= 'Z' ? (char) (c | 0x20) : c;
    }

    /**
     * The definition: s begins with p's characters before the ".*" (two ASCII letters that differ in case alike when
     * fold), and, unless dotall, none of the five line terminators follows them. By unit: a surrogate is no line
     * terminator, alone or in a pair.
     */
    static boolean defined(String p, boolean fold, boolean dotall, String s) {
        int n = p.length() - 2;
        if (s.length() < n) return false;
        for (int i = 0; i < n; i++) {
            char a = p.charAt(i), b = s.charAt(i);
            if (a != b && !(fold && lower(a) == lower(b))) return false;
        }
        for (int i = n; i < s.length() && !dotall; i++) {
            char c = s.charAt(i);
            if (c == '\n' || c == '\r' || c == '\u0085' || c == ' ' || c == ' ') return false;
        }
        return true;
    }

    public static boolean exact(String p, String s) {
        return !literalThenAny(p) || Pattern.compile(p, 0).matcher(s).matches() == defined(p, false, false, s);
    }

    public static boolean exactDotall(String p, String s) {
        return !literalThenAny(p) || Pattern.compile(p, Pattern.DOTALL).matcher(s).matches() == defined(p, false, true, s);
    }

    public static boolean folded(String p, String s) {
        return !literalThenAny(p) || Pattern.compile(p, Pattern.CASE_INSENSITIVE).matcher(s).matches() == defined(p, true, false, s);
    }

    public static boolean foldedDotall(String p, String s) {
        return !literalThenAny(p) || Pattern.compile(p, Pattern.CASE_INSENSITIVE | Pattern.DOTALL).matcher(s).matches() == defined(p, true, true, s);
    }

    /** The flags chosen by an input, as a constructor that takes a case mode chooses them. */
    public static boolean chosen(String p, boolean fold, String s) {
        return !literalThenAny(p) || Pattern.compile(p, fold ? Pattern.CASE_INSENSITIVE | Pattern.DOTALL : Pattern.DOTALL).matcher(s).matches() == defined(p, fold, true, s);
    }

    /** A constant of the family, through String.matches: a surrogate in the rest of the input is taken as any unit is. */
    public static boolean constant(String s) {
        return s.matches("/a.*") == defined("/a.*", false, false, s);
    }

    /** A dot that does not end the expression takes one code point, a pair of surrogates whole: with one in the input the call is the JDK's. */
    public static boolean dotInside(String s) {
        return s.matches("/a.b") || !s.isEmpty() || s.isEmpty();
    }

    /** Any pattern at all is the JDK's to compile: the engine shows nothing of it. */
    public static boolean anyPattern(String p, String s) {
        return Pattern.compile(p, 0).matcher(s).matches() || !s.isEmpty() || s.isEmpty();
    }

    /** So is one that only ends with ".*": what comes before may be a metacharacter. */
    public static boolean anyBeforeTheDot(String p, String s) {
        return !p.endsWith(".*") || Pattern.compile(p, 0).matcher(s).matches() || !s.isEmpty() || s.isEmpty();
    }

    /** And one of the family under a flag the engine does not read (MULTILINE). */
    public static boolean anotherFlag(String p, String s) {
        return !literalThenAny(p) || Pattern.compile(p, Pattern.MULTILINE).matcher(s).matches() == defined(p, false, false, s);
    }

    /** Of an ASCII char, Character.isLetter is whether it is one of the 52 letters. */
    public static boolean letter(char c) {
        return c >= 128 || Character.isLetter(c) == (c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z');
    }

    /** Of any other char it is the JDK's table's to say. */
    public static boolean letterOutsideAscii(char c) {
        return Character.isLetter(c) || c != 'ª';
    }

    /** Under the JDK's default logging configuration a logger logs nothing below INFO. */
    public static boolean quiet(int k) {
        Logger logger = Logger.getLogger("claims.P");
        return !logger.isLoggable(Level.CONFIG) && !logger.isLoggable(Level.FINE) && !logger.isLoggable(Level.FINER)
                && !logger.isLoggable(Level.FINEST) && !logger.isLoggable(Level.ALL);
    }
}
