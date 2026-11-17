package app;

import java.util.Locale;

/**
 * The new version of each countermodel of the pair of versions (lib/src/pairing.rs). Run alone, each method gives
 * another result than its namesake in {@code old/app/Entry.java}; in the pair, where the previous version runs
 * first in the same JVM and the scope runs before both, the two agree.
 */
public final class Entry {
    private Entry() {}

    /** Lowers under the default locale: "I" becomes "i" under the JVM's own (not Turkish). */
    public static String locale(String s) {
        return s.toLowerCase();
    }

    /** Returns 1 when the library's static is set, which nothing in this version does. */
    public static int flag(int k) {
        return lib.Flags.on ? 1 : 0;
    }

    /** Throws another unchecked exception at 1. */
    public static int thrown(int k) {
        if (k == 1) {
            throw new lib.BException();
        }
        return k;
    }

    /** Throws a subclass of IllegalArgumentException at 1. */
    public static int argument(int k) {
        if (k == 1) {
            throw new lib.BadArgument();
        }
        return k;
    }

    /** Lowers under the Turkish locale, whatever the default. */
    public static String scoped(String s) {
        return s.toLowerCase(Locale.forLanguageTag("tr-TR"));
    }

    /** The scope given for {@link #scoped}: no input is meant to change, but reading it sets the default locale. */
    public static boolean special(String s) {
        Locale.setDefault(Locale.forLanguageTag("tr-TR"));
        return false;
    }

    /** What this version does with one method on one input, in a JVM of its own. */
    public static void main(String[] args) {
        System.out.println(args[0] + "=" + lib.Run.describe(() -> switch (args[0]) {
            case "locale" -> locale("I");
            case "flag" -> flag(0);
            case "thrown" -> thrown(1);
            case "argument" -> argument(1);
            case "scoped" -> scoped("I");
            default -> throw new IllegalStateException(args[0]);
        }));
    }
}
