package app;

/**
 * The new version of each countermodel of the pair of versions (lib/src/pairing.rs). Run alone, each method does
 * another thing than its namesake in {@code old/app/Entry.java}; the pair finds them agreeing.
 */
public final class Entry {
    private Entry() {}

    /** 0 for a cell, or -1 for none: not the first cell. */
    public static int first(int[] cells) {
        return cells.length > 0 ? 0 : -1;
    }

    /**
     * The scope given for {@link #first}: no input is meant to change, but reading it writes the array it is given,
     * which is the one the pair then copies for each version.
     */
    public static boolean zeroed(int[] cells) {
        if (cells != null && cells.length > 0) {
            cells[0] = 0;
        }
        return false;
    }

    /** Throws this version's {@link Failure}, of the same name as the previous one's and another kind, at 1. */
    public static int failing(int k) {
        if (k == 1) {
            throw new Failure();
        }
        return k;
    }

    /** What a caller that handles an IllegalArgumentException sees of {@link #failing}. */
    static String handled(int k) {
        try {
            return Integer.toString(failing(k));
        } catch (IllegalArgumentException e) {
            return "handled";
        } catch (RuntimeException e) {
            return "escaped " + e.getClass().getName();
        }
    }

    /** One method on one input, in a JVM of its own. */
    public static void main(String[] args) {
        System.out.println(switch (args[0]) {
            case "first" -> "first=" + first(new int[] {5});
            case "failing" -> "failing=" + handled(1);
            default -> throw new IllegalStateException(args[0]);
        });
    }
}
