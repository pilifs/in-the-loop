package app;

import java.util.Locale;

/**
 * The previous version of each countermodel of the pair of versions (lib/src/pairing.rs): run alone, each method
 * here and its namesake in {@code new/app/Entry.java} give different results on the input {@code main} runs.
 */
public final class Entry {
    private Entry() {}

    /** Sets a Turkish default locale, then lowers: "I" becomes U+0131. */
    public static String locale(String s) {
        Locale.setDefault(Locale.forLanguageTag("tr-TR"));
        return s.toLowerCase();
    }

    /** Writes the library's static and returns 1. */
    public static int flag(int k) {
        lib.Flags.on = true;
        return 1;
    }

    /** Throws one unchecked exception at 1. */
    public static int thrown(int k) {
        if (k == 1) {
            throw new lib.AException();
        }
        return k;
    }

    /** Throws an IllegalArgumentException at 1. */
    public static int argument(int k) {
        if (k == 1) {
            throw new IllegalArgumentException("one");
        }
        return k;
    }

    /** Lowers under the default locale. */
    public static String scoped(String s) {
        return s.toLowerCase();
    }

    /** What this version does with one method on one input, in a JVM of its own: see {@code new/app/Entry.java}. */
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
