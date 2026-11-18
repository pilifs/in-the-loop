package claims;

import java.util.Locale;

/**
 * Lower-casing under a locale that is an input (lib/src/bmc/locale.rs), against a definition written out over
 * charAt: on an ASCII String, Turkish and Azeri lower I to the dotless i (U+0131) and every locale lowers the other
 * capitals alike. Each method returns whether the JDK's answer is the definition's, for every index into the table
 * and every ASCII String: true on every input, to the engine's model and, on samples, on a JVM.
 */
public final class C {
    private C() {}

    /** Constants and plain language tags: Turkish and Azeri at 2, 3 and 6 (the tag's case does not matter), and tur, which is no tr. */
    public static final Locale[] LOCALES = {
        Locale.ROOT, Locale.forLanguageTag("en-US"), Locale.forLanguageTag("tr-TR"), Locale.forLanguageTag("az-Latn-AZ"),
        Locale.forLanguageTag("lt-LT"), Locale.US, Locale.forLanguageTag("TR"), Locale.forLanguageTag("tur"),
    };

    static boolean dotless(int k) {
        return k == 2 || k == 3 || k == 6;
    }

    static boolean ascii(String s) {
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) >= 128) return false;
        }
        return true;
    }

    /** Whether r is s lowered under LOCALES[k], and is s itself exactly when s has no capital. */
    static boolean lowers(int k, String s, String r) {
        if (r.length() != s.length()) return false;
        boolean capital = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            char want = c == 'I' && dotless(k) ? 'ı' : c >= 'A' && c <= 'Z' ? (char) (c | 0x20) : c;
            if (r.charAt(i) != want) return false;
            capital |= c >= 'A' && c <= 'Z';
        }
        return (r == s) == !capital;
    }

    /** toLowerCase(Locale) of a locale picked from the table at an index that is an input. */
    public static boolean given(int k, String s) {
        if (k < 0 || k >= LOCALES.length || !ascii(s)) return true;
        return lowers(k, s, s.toLowerCase(LOCALES[k]));
    }

    /** toLowerCase() under the default set last: two writes, each at an index that is an input. */
    public static boolean underTheDefault(int j, int k, String s) {
        if (j < 0 || j >= LOCALES.length || k < 0 || k >= LOCALES.length || !ascii(s)) return true;
        Locale.setDefault(LOCALES[j]);
        String first = s.toLowerCase();
        Locale.setDefault(LOCALES[k]);
        return lowers(j, s, first) && lowers(k, s, s.toLowerCase());
    }

    /** A null tag, a null default and a null locale each throw NullPointerException, and leave the default as it was. */
    public static boolean nulls(String s) {
        if (!ascii(s)) return true;
        Locale.setDefault(LOCALES[2]);
        int thrown = 0;
        try {
            Locale.forLanguageTag(null);
        } catch (NullPointerException e) {
            thrown++;
        }
        try {
            Locale.setDefault(null);
        } catch (NullPointerException e) {
            thrown++;
        }
        try {
            s.toLowerCase(null);
        } catch (NullPointerException e) {
            thrown++;
        }
        return thrown == 3 && lowers(2, s, s.toLowerCase());
    }

    /** Whether two Locales are one object is the JDK's cache's to say: the engine refuses the comparison. */
    public static boolean identical(int k) {
        return Locale.forLanguageTag("en-US") == Locale.US || k == k;
    }

    /** One Locale is itself, and no Locale is null. */
    public static boolean itself(int k) {
        if (k < 0 || k >= LOCALES.length) return true;
        Locale l = LOCALES[k];
        return l == l && l != null && Locale.ROOT == Locale.ROOT;
    }

    /** A unit outside ASCII is lowered by Unicode's tables and the locale's rules (U+0130 is two units in the root locale): the JDK's call. */
    public static boolean outsideAscii(String s) {
        return ("\u0130" + s).toLowerCase(Locale.ROOT).length() > s.length();
    }

    /**
     * Example 286's blocker on its real path (DataBinder.isAllowed:828 on 5.3.19, field.toLowerCase() under the JVM's
     * default against the disallowed "age"): only an ASCII spelling of age lowers to it. True for every String on a
     * JVM under every locale, since no code point outside ASCII lowers to a, g or e (main sweeps them); the checker
     * lowers ASCII only, so outside it the call is the JDK's, a gap.
     */
    public static boolean loweredToAge(String s) {
        boolean spelled = s.length() == 3 && (s.charAt(0) | 0x20) == 'a' && (s.charAt(1) | 0x20) == 'g' && (s.charAt(2) | 0x20) == 'e';
        return s.toLowerCase().equals("age") == spelled;
    }

    /** loweredToAge's premise on a JVM: under each locale of the table, every code point outside ASCII lowers to something that is not made of a, g and e alone. */
    public static void main(String[] args) {
        for (Locale l : LOCALES) {
            for (int cp = 128; cp <= Character.MAX_CODE_POINT; cp++) {
                String r = new String(Character.toChars(cp)).toLowerCase(l);
                if (r.chars().allMatch(c -> c == 'a' || c == 'g' || c == 'e')) {
                    System.out.println("U+" + Integer.toHexString(cp) + " lowers to " + r + " under " + l);
                    return;
                }
            }
        }
        System.out.println("no code point outside ASCII lowers to a, g or e");
    }

    /** Under a default that is a Locale the engine knows nothing of, toLowerCase() is the JDK's call. */
    public static boolean underAnUnknownDefault(String s) {
        Locale.setDefault(new Locale("tr"));
        return !ascii(s) || s.toLowerCase() != null;
    }
}
