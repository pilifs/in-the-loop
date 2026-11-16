package claims;

import java.util.Random;

/**
 * The definitions of {@link B} against the JDK's methods on a JVM: each method of B returns whether the JDK's answer
 * is its definition's, so that it returns true on every sample says the definition is the JDK's there. The engine
 * proves the same methods return true of its models, on every input of a bound.
 */
public final class Samples {
    private Samples() {}

    static final char[] POOL = {'$', '2', 'a', 'b', 'y', 'c', 'x', '0', '1', '3', '4', '9', '.', '/', 'A', 'Z', 'z', '+', '-', ' ', '\n', '\u007f', '\u0080', '߿', 'ࠀ', '\ud800', '\udbff', '\udc00', '\udfff', '￿', '٣', 'k'};
    /** What lower-casing turns on: the capitals a locale may lower its own way, and the units beside the letters. */
    static final String CAPITALS = "IiJjAZaz[@`{ \u007f0";
    static String text(Random r, int most) {
        int n = r.nextInt(most + 1);
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) b.append(r.nextInt(4) == 0 ? (char) r.nextInt(65536) : POOL[r.nextInt(POOL.length)]);
        return b.toString();
    }
    static String digits(Random r) {
        String[] fixed = {"2147483647", "2147483648", "-2147483648", "-2147483649", "+0", "-0", "00000000000012", "99999999999", "+", "-", "", "4294967296", "+2147483647"};
        if (r.nextInt(3) == 0) return fixed[r.nextInt(fixed.length)];
        StringBuilder b = new StringBuilder();
        if (r.nextInt(3) == 0) b.append(r.nextBoolean() ? '-' : '+');
        int n = r.nextInt(12);
        for (int i = 0; i < n; i++) b.append(r.nextInt(20) == 0 ? 'x' : (char) ('0' + r.nextInt(10)));
        return b.toString();
    }
    static String hash(Random r) {
        String salt = "./ABCZabcz019";
        String[] heads = {"$2a$", "$2b$", "$2y$", "$2$", "$2c$", "$3a$"};
        String s = heads[r.nextInt(heads.length)] + (char) ('0' + r.nextInt(4)) + (char) ('0' + r.nextInt(10)) + "$";
        int n = r.nextInt(4);
        for (int i = 0; i < n; i++) s += r.nextInt(8) == 0 ? '!' : salt.charAt(r.nextInt(salt.length()));
        return s;
    }
    static void check(boolean ok, String what) { if (!ok) throw new AssertionError(what); }
    /** Samples as many inputs as the argument says (20000 with none), from a fixed seed. */
    public static void main(String[] args) {
        Random r = new Random(287);
        int samples = args.length > 0 ? Integer.parseInt(args[0]) : 20000;
        for (int i = 0; i < samples; i++) {
            String s = text(r, 6);
            check(B.utf8(s), "utf8 " + s.chars().boxed().toList());
            check(B.excluded(s), "excluded " + s);
            String x = r.nextBoolean() ? "kxx".substring(0, r.nextInt(4)) + "xxxx".substring(0, r.nextInt(5)) : s;
            check(B.excluded(x), "excluded " + x);
            String d = r.nextInt(4) == 0 ? s : digits(r);
            check(B.parsed(d), "parsed " + d);
            String h = hash(r);
            check(B.shaped(h), "shaped " + h);
            check(B.anchored(h), "anchored " + h);
            check(B.shaped(s) && B.anchored(s), "shape of " + s);
            byte[] a = new byte[r.nextInt(5)], b = new byte[r.nextInt(5)];
            for (int k = 0; k < a.length; k++) a[k] = (byte) r.nextInt(3);
            for (int k = 0; k < b.length; k++) b[k] = (byte) r.nextInt(3);
            check(B.equal(a, b) && B.equal(a, a.clone()), "equal");
            check(B.copied(a, r.nextInt(8) - 2), "copied");
            check(B.appended(s, (char) r.nextInt(65536), r.nextInt(2400) - 1200), "appended");
            // Lower-casing under a locale (C), on ASCII text with capitals: the default locale is put back after.
            StringBuilder t = new StringBuilder();
            for (int k = r.nextInt(7); k > 0; k--) t.append(r.nextInt(3) == 0 ? CAPITALS.charAt(r.nextInt(CAPITALS.length())) : (char) r.nextInt(128));
            java.util.Locale own = java.util.Locale.getDefault();
            int j = r.nextInt(C.LOCALES.length + 2) - 1, k = r.nextInt(C.LOCALES.length + 2) - 1;
            check(C.given(k, t.toString()), "given " + k + " " + t);
            check(C.underTheDefault(j, k, t.toString()), "underTheDefault " + j + " " + k + " " + t);
            check(C.nulls(t.toString()) && C.itself(k), "nulls " + t);
            check(C.given(k, s) && C.underTheDefault(j, k, s), "lowered outside ASCII " + s);
            java.util.Locale.setDefault(own);
        }
        check(B.digits(), "digits");
        System.out.println("all hold on " + samples + " samples");
    }
}
