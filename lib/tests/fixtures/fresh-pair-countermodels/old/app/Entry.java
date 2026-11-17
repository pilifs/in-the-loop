package app;

/**
 * The previous version of each countermodel of the pair of versions as the preservation stream left it
 * (lib/src/pairing.rs at zmvkptqz: each version from a fresh state, exceptions by class name). Run alone, each method
 * here and its namesake in {@code new/app/Entry.java} do different things on the input {@code main} runs.
 */
public final class Entry {
    private Entry() {}

    /** The first cell, or -1 for none. */
    public static int first(int[] cells) {
        return cells.length > 0 ? cells[0] : -1;
    }

    /** Throws this version's {@link Failure} at 1. */
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

    /** One method on one input, in a JVM of its own: see {@code new/app/Entry.java}. */
    public static void main(String[] args) {
        System.out.println(switch (args[0]) {
            case "first" -> "first=" + first(new int[] {5});
            case "failing" -> "failing=" + handled(1);
            default -> throw new IllegalStateException(args[0]);
        });
    }
}
