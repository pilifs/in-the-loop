package values;

/**
 * Harness-shaped checks of the own checker's bounded Strings (lib/tests/values.rs): each static method throws an
 * AssertionError where its claim fails, as a generated harness does, and the checker is run on it directly. A
 * violation's witness is replayed here on the JVM (ValuesRunner) and must throw that AssertionError.
 */
public final class Checks {
    private Checks() {
    }

    static boolean vipBefore(String code) {
        return code.startsWith("VIP");
    }

    static boolean vipAfter(String code) {
        return code.length() >= 3 && code.charAt(0) == 'V' && code.charAt(1) == 'I' && code.charAt(2) == 'P';
    }

    static boolean vipShort(String code) {
        return code.length() >= 2 && code.charAt(0) == 'V' && code.charAt(1) == 'I';
    }

    /** The quote fixture's correct rewrite of Codes.vip: the same answer on every code. */
    public static void vipRewritten(String code) {
        if (vipBefore(code) != vipAfter(code)) {
            throw new AssertionError();
        }
    }

    /** The quote fixture's planted defect, a dropped prefix character: a code starting "VI" but not "VIP" differs. */
    public static void vipShortened(String code) {
        if (vipBefore(code) != vipShort(code)) {
            throw new AssertionError();
        }
    }

    /** equals compares content: the same as comparing the lengths and every code unit. */
    public static void equalsByUnits(String a, String b) {
        boolean same = a.length() == b.length();
        for (int i = 0; same && i < a.length(); i++) {
            same = a.charAt(i) == b.charAt(i);
        }
        if (a.equals(b) != same) {
            throw new AssertionError();
        }
    }

    /** A wrong claim, that equal Strings are one object: refuted by equal content behind distinct references. */
    public static void equalIsIdentical(String a, String b) {
        if (a.equals(b) && a != b) {
            throw new AssertionError();
        }
    }

    /** One reference is equal to itself, whatever its content. */
    public static void identicalIsEqual(String a, String b) {
        if (a == b && !a.equals(b)) {
            throw new AssertionError();
        }
    }

    /** equals of null, or of an object of another class, is false. */
    public static void equalsNullOrOther(String a) {
        if (a.equals(null) || a.equals(new Object())) {
            throw new AssertionError();
        }
    }

    /** A wrong claim, that no String is half a surrogate pair: refuted by a String of one isolated high surrogate. */
    public static void noLoneSurrogate(String s) {
        if (s.length() == 1 && s.charAt(0) >= 0xD800 && s.charAt(0) <= 0xDBFF) {
            throw new AssertionError();
        }
    }

    /** A supplementary character is two code units. */
    public static void pairIsTwoUnits(String s) {
        if (s.startsWith("😀") && (s.length() < 2 || s.charAt(0) != 0xD83D || s.charAt(1) != 0xDE00)) {
            throw new AssertionError();
        }
    }

    /** A supplementary character mishandled as one code unit: refuted by a String that starts with the pair. */
    public static void pairAsOneUnit(String s) {
        if (s.startsWith("😀") && s.charAt(0) != 0x1F600) {
            throw new AssertionError();
        }
    }

    /** A wrong claim, that no String holds a NUL after an 'A': refuted by "A\0". */
    public static void embeddedNul(String s) {
        if (s.length() == 2 && s.charAt(0) == 'A' && s.charAt(1) == 0) {
            throw new AssertionError();
        }
    }

    /** charAt throws StringIndexOutOfBoundsException out of range, and only there. */
    public static void charAtBounds(String s, int i) {
        boolean inside = i >= 0 && i < s.length();
        try {
            s.charAt(i);
        } catch (StringIndexOutOfBoundsException e) {
            if (inside) {
                throw new AssertionError();
            }
            return;
        }
        if (!inside) {
            throw new AssertionError();
        }
    }

    /** startsWith(null) throws a NullPointerException. */
    public static void startsWithNull(String s) {
        try {
            s.startsWith(null);
        } catch (NullPointerException e) {
            return;
        }
        throw new AssertionError();
    }

    /** isEmpty is a length of zero. */
    public static void emptyIsLengthZero(String s) {
        if (s.isEmpty() != (s.length() == 0)) {
            throw new AssertionError();
        }
    }

    /** Holds of every String of at most four code units, and fails on one of five. */
    public static void atMostFour(String s) {
        if (s.length() > 4) {
            throw new AssertionError();
        }
    }

    /** A concatenation's content: s + "!" is s, then '!'. */
    public static void concatenated(String s) {
        String t = s + "!";
        if (t.length() != s.length() + 1 || t.charAt(s.length()) != '!' || !t.startsWith(s)) {
            throw new AssertionError();
        }
    }

    /** Two Strings concatenated around a char. */
    public static void joined(String a, String b, char c) {
        String t = a + c + b;
        if (t.length() != a.length() + b.length() + 1 || t.charAt(a.length()) != c || !t.startsWith(a)) {
            throw new AssertionError();
        }
        if (b.length() > 0 && t.charAt(t.length() - 1) != b.charAt(b.length() - 1)) {
            throw new AssertionError();
        }
    }

    /** A wrong claim about a concatenation, that a + b never equals b + a when a and b differ: refuted. */
    public static void concatenationCommutes(String a, String b) {
        if (!a.equals(b) && (a + b).equals(b + a)) {
            throw new AssertionError();
        }
    }

    /** A null String is concatenated as "null". */
    public static void nullConcatenated(String s) {
        String t = "x" + s;
        if (s == null && !t.equals("xnull")) {
            throw new AssertionError();
        }
    }

    /** A literal is one interned object with its content. */
    public static void literal(String s) {
        String v = "VIP";
        if (v != "VIP" || v.length() != 3 || !v.equals("VIP") || v.charAt(2) != 'P') {
            throw new AssertionError();
        }
        if ("VIP".equals(s) != (s.length() == 3 && s.startsWith("VIP"))) {
            throw new AssertionError();
        }
    }

    /** Under a domain that lets the String be null: refuted by null. */
    public static void notNull(String s) {
        if (s == null) {
            throw new AssertionError();
        }
    }

    /** The length of a String that may be null: a NullPointerException, which leaves the check. */
    public static void lengthOfNullable(String s) {
        if (s.length() < 0) {
            throw new AssertionError();
        }
    }

    /** A number made into a String: numeric formatting is outside the model, so its length is a named gap. */
    public static void numbered(int n) {
        String t = "n" + n;
        if (t.length() == 0) {
            throw new AssertionError();
        }
    }

    /** Nine copies of a String of up to eight units: beyond the checker's content cap, a named limit. */
    public static void longJoin(String s) {
        String t = s + s + s + s + s + s + s + s + s;
        if (t.length() < 0) {
            throw new AssertionError();
        }
    }
}
