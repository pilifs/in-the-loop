package claims;

import java.util.Random;

/**
 * The definitions of {@link B}, {@link C}, {@link P} and {@link L}'s range against the JDK's methods on a JVM: each method returns whether the JDK's answer
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
    /** What a protective pattern's matching turns on: the line terminators, surrogates alone and in pairs, and letters that fold outside ASCII. */
    static final String AFTER = "\n\r\u0085\u2028\u2029\ud800\udc00\ud83d\ude00aAkK\u212a\u017f\u0130\u0131/?x\u000b\u000c\u001c";
    static final String LITERAL = "/adminADMINkKsSiI-_09 ~";
    /** A pattern of the family, or (one time in eight) any text. */
    static String protective(Random r) {
        if (r.nextInt(8) == 0) return text(r, 4);
        StringBuilder b = new StringBuilder();
        for (int k = r.nextInt(5); k > 0; k--) b.append(LITERAL.charAt(r.nextInt(LITERAL.length())));
        return b.append(".*").toString();
    }
    /** A text that begins as the pattern does, in either case of a letter, or nearly, and goes on with what matching turns on. */
    static String guarded(Random r, String pattern) {
        StringBuilder b = new StringBuilder();
        int n = Math.max(0, pattern.length() - 2) - (r.nextInt(6) == 0 ? 1 : 0);
        for (int i = 0; i < n; i++) {
            char c = pattern.charAt(i);
            b.append(r.nextInt(4) == 0 && Character.isLetter(c) ? (char) (c ^ 0x20) : r.nextInt(12) == 0 ? AFTER.charAt(r.nextInt(AFTER.length())) : c);
        }
        for (int k = r.nextInt(5); k > 0; k--) b.append(r.nextInt(3) == 0 ? POOL[r.nextInt(POOL.length)] : AFTER.charAt(r.nextInt(AFTER.length())));
        return b.toString();
    }
    static void check(boolean ok, String what) { if (!ok) throw new AssertionError(what); }
    /** Samples as many inputs as the argument says (20000 with none), from a fixed seed. */
    public static void main(String[] args) {
        Random r = new Random(287);
        int samples = args.length > 0 ? Integer.parseInt(args[0]) : 20000;
        for (int i = 0; i < samples; i++) {
            String s = text(r, 6);
            check(B.utf8(s), "utf8 " + s.chars().boxed().toList());
            check(B.named(s), "named " + s.chars().boxed().toList());
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
            // A protective pattern under each flag combination (P), and the range stream (L).
            String p = protective(r), u = r.nextInt(4) == 0 ? s : guarded(r, p);
            String shown = p + " on " + u.chars().boxed().toList();
            check(P.exact(p, u) && P.exactDotall(p, u) && P.folded(p, u) && P.foldedDotall(p, u), "protective " + shown);
            check(P.chosen(p, r.nextBoolean(), u) && P.anotherFlag(p, u), "protective, chosen " + shown);
            check(P.constant(u) && P.constant("/a" + u), "protective, constant " + shown);
            check(L.range(r.nextInt(9) - 4, r.nextInt(9) - 4, r.nextInt(9) - 4), "range");
            // Registrations in order and a number in a name (M).
            int[] keys = new int[r.nextInt(7)];
            for (int q = 0; q < keys.length; q++) keys[q] = r.nextInt();
            check(M.ordered(keys) && M.ints(keys, r.nextInt()) && M.failsFast(r.nextBoolean()), "ordered " + java.util.Arrays.toString(keys));
            int[] few = new int[r.nextInt(5)];
            for (int q = 0; q < few.length; q++) few[q] = r.nextInt(3);
            check(M.ints(few, r.nextInt(3)), "ints " + java.util.Arrays.toString(few));
            check(M.listed(few) && M.listed(keys) && M.emptied(), "listed " + java.util.Arrays.toString(few));
            int[] fewer = new int[r.nextInt(3)];
            check(M.collected(keys, r.nextInt(12) - 3) && M.collected(few, 7) && M.filled(keys, r.nextInt(keys.length + 3) - 1), "collected " + java.util.Arrays.toString(keys));
            check(M.appended(few.length + fewer.length > 3 ? fewer : few, fewer, r.nextBoolean()) && M.swept(r.nextInt(4)) && M.contained(), "appended " + java.util.Arrays.toString(few));
            check(M.cached(r.nextInt(600) - 300), "cached");
            check(M.recopied(keys, r.nextInt(keys.length + 4) - 2), "recopied " + java.util.Arrays.toString(keys));
            int n = r.nextInt(4) == 0 ? r.nextInt() : r.nextInt(2400) - 1200;
            check(M.numbered(n, (short) r.nextInt(), (byte) r.nextInt()), "numbered " + n);
        }
        check(M.numbered(Integer.MIN_VALUE, Short.MIN_VALUE, Byte.MIN_VALUE) && M.numbered(Integer.MAX_VALUE, Short.MAX_VALUE, Byte.MAX_VALUE) && M.numbered(0, (short) 0, (byte) 0), "numbered, the ends");
        // Classes by name (M): each class is initialized once in this JVM, so every case is asked twice.
        try {
            for (int twice = 0; twice < 2; twice++) {
                for (int k = 0; k < 4; k++) check(M.loaded(k) && M.observed(k), "loaded and observed " + k);
                for (int k = 0; k < 3; k++) check(M.assignable(k), "assignable " + k);
                check(M.erroneous() && M.threaded() && M.served(), "erroneous, threaded, served");
            }
        }
        catch (ClassNotFoundException e) {
            throw new AssertionError(e);
        }
        check(P.quiet(0), "quiet");
        for (int c = 0; c < 65536; c++) check(P.letter((char) c) && P.letterOutsideAscii((char) c), "letter " + c);
        check(B.digits(), "digits");
        System.out.println("all hold on " + samples + " samples");
    }
}
