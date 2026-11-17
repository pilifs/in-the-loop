package claims;

import java.util.Locale;

/**
 * Countermodels: methods whose result depends on more than their arguments, or that do more than return. A proof by
 * induction replaces a method's calls of itself with the property, and a summary replaces a method's calls with a
 * lemma; both state a result of the arguments and nothing else, so each method here is one they must not stand in
 * for. Every property the tests state of them is false on a JVM, which {@code main} shows.
 */
public final class Effects {
    private Effects() {}

    static int count;
    static int level;
    static int[] table = {0};
    static final int[] FIXED = {0};

    /** Counts its calls in a static field and returns the count: 2 for n == 1, never 1. */
    public static int counting(int n) {
        count++;
        if (n == 0) {
            return count;
        }
        return counting(n - 1);
    }

    /** Throws at the bottom of every recursion: no call of it returns. */
    public static int throwing(int n) {
        if (n == 0) {
            throw new IllegalStateException("the bottom");
        }
        return throwing(n - 1) + 1;
    }

    /** Throws only where the caller is told it does (n below zero), and calls itself only on arguments that do not. */
    public static int checked(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("negative");
        }
        return n == 0 ? 0 : checked(n - 1) + 1;
    }

    /** Counts down, adding the static field at the bottom: n from a fresh class, where the field is 0. */
    public static int depth(int n) {
        return n == 0 ? level : depth(n - 1) + 1;
    }

    static final int LIMIT = Integer.parseInt("7");

    /** Reads a final static field its class's initializer computes: 7, whoever calls and whenever. */
    public static int limit() {
        return LIMIT;
    }

    /** Twice the limit, by two calls of the getter. */
    public static int twiceLimit() {
        return limit() + limit();
    }

    /** Reads a static field: 0 from a fresh class, and whatever was written since. */
    public static int level() {
        return level;
    }

    /** Reads the same field through a callee. */
    public static int levelIndirectly() {
        return level();
    }

    /** Reads an element of an array a static field holds. */
    public static int first() {
        return table[0];
    }

    /** Reads an element of an array a final static field holds: the field is final, the array is not. */
    public static int fixedFirst() {
        return FIXED[0];
    }

    /** Whether the text lower-cases to "i" under the default locale: true of "I" but under tr and az. */
    public static boolean lowersToI(String text) {
        return text.toLowerCase().equals("i");
    }

    /** Sets the default locale to Turkish, then asks: false, where a fresh JVM under the root locale says true. */
    public static boolean turkishThenLowers() {
        Locale.setDefault(Locale.forLanguageTag("tr"));
        return lowersToI("I");
    }

    /** Writes the field, then reads it by the getter: returns v. */
    public static int setThenLevel(int v) {
        level = v;
        return level();
    }

    /** The same through the indirect getter. */
    public static int setThenLevelIndirectly(int v) {
        level = v;
        return levelIndirectly();
    }

    /** Reads nothing: 0. */
    public static int zero() {
        return 0;
    }

    /** Writes the field, then calls a method that reads nothing: returns 0, whatever v is. */
    public static int setThenZero(int v) {
        level = v;
        return zero();
    }

    /** Writes the array's element, then reads it by the getter: returns v. */
    public static int setThenFirst(int v) {
        table[0] = v;
        return first();
    }

    /** Writes the final field's array, then reads it by the getter: returns v. */
    public static int setThenFixedFirst(int v) {
        FIXED[0] = v;
        return fixedFirst();
    }

    /** What a JVM says of each: the properties the tests state are false. */
    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        count = 0;
        out.append("counting(1)=").append(counting(1));
        try {
            int returned = throwing(1);
            out.append(" throwing(1)=").append(returned);
        } catch (IllegalStateException e) {
            out.append(" throwing(1)=IllegalStateException");
        }
        out.append(" checked(2)=").append(checked(2));
        out.append(" depth(3)=").append(depth(3));
        out.append(" setThenLevel(7)=").append(setThenLevel(7));
        out.append(" setThenLevelIndirectly(8)=").append(setThenLevelIndirectly(8));
        out.append(" setThenFirst(9)=").append(setThenFirst(9));
        out.append(" setThenFixedFirst(10)=").append(setThenFixedFirst(10));
        out.append(" twiceLimit()=").append(twiceLimit());
        Locale.setDefault(Locale.ROOT);
        out.append(" lowersToI(I)=").append(lowersToI("I"));
        out.append(" turkishThenLowers()=").append(turkishThenLowers());
        System.out.println(out);
    }
}
