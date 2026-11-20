package tm;

/** Direct, independently observable controls for the JDK methods used by try-with-resources. */
public final class Suppression {
    static final class Tagged extends RuntimeException {
        // A field with the JDK's private name must remain a different field.
        final String suppressedExceptions = "mine";

        Tagged(boolean enabled) {
            super("primary", null, enabled, false);
        }
    }

    public static boolean ordered(boolean enabled, boolean swap) {
        Tagged primary = new Tagged(enabled);
        Throwable a = new Throwable("a");
        Throwable b = new Exception("b");
        Throwable first = swap ? b : a;
        Throwable next = swap ? a : b;
        Throwable[] empty = primary.getSuppressed();
        primary.addSuppressed(first);
        Throwable[] one = primary.getSuppressed();
        primary.addSuppressed(next);
        primary.addSuppressed(first);
        Throwable[] three = primary.getSuppressed();
        if (empty.length != 0 || empty != a.getSuppressed() || primary.suppressedExceptions != "mine") return false;
        if (!enabled) return one == empty && three == empty;
        if (one.length != 1 || one[0] != first || three.length != 3 || three[0] != first
                || three[1] != next || three[2] != first) return false;
        three[0] = null;
        Throwable[] again = primary.getSuppressed();
        return again != three && again[0] == first && one[0] == first;
    }

    public static boolean rejects(boolean enabled) {
        Tagged primary = new Tagged(enabled);
        try {
            primary.addSuppressed(primary);
            return false;
        } catch (IllegalArgumentException e) {
            if (e.getCause() != primary || !"Self-suppression not permitted".equals(e.getMessage())) return false;
        }
        try {
            primary.addSuppressed(null);
            return false;
        } catch (NullPointerException e) {
            return "Cannot suppress a null exception.".equals(e.getMessage()) && primary.getSuppressed().length == 0;
        }
    }

    public static boolean dropsDuplicate() {
        Throwable outer = new Throwable();
        Throwable inner = new Exception();
        outer.addSuppressed(inner);
        outer.addSuppressed(inner);
        return outer.getSuppressed().length == 1;
    }

    public static void main(String[] args) {
        for (boolean enabled : new boolean[] {false, true}) {
            if (!ordered(enabled, false) || !ordered(enabled, true) || !rejects(enabled)) throw new AssertionError();
        }
        if (dropsDuplicate()) throw new AssertionError();
    }
}
