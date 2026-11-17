package app;

/**
 * The previous version of each countermodel of the pair of versions as the preservation stream left it
 * (lib/src/pairing.rs at wokytpkz: an exception compared by its class's name and the names of the classes above it,
 * the scope read on copies of its own). Run alone, each method here and its namesake in {@code new/app/Entry.java}
 * do different things for the caller {@link #handled} on the input {@code main} runs.
 */
public final class Entry {
    private Entry() {}

    /** Throws a {@link Marked}, which this version's caller may retry, at 1. */
    public static int marked(int k) {
        if (k == 1) {
            throw new Marked();
        }
        return k;
    }

    /** Throws a RuntimeException caused by an IllegalArgumentException at 1. */
    public static int wrapped(int k) {
        if (k == 1) {
            throw new RuntimeException(new IllegalArgumentException("bad"));
        }
        return k;
    }

    /** Throws an IllegalArgumentException that says the input is negative at 1. */
    public static int messaged(int k) {
        if (k == 1) {
            throw new IllegalArgumentException("negative");
        }
        return k;
    }

    /** Throws a {@link Coded} of 403 (forbidden) at 1. */
    public static int coded(int k) {
        if (k == 1) {
            throw new Coded(403);
        }
        return k;
    }

    /** Throws a {@link Based}, an IllegalArgumentException in this version, at 1. */
    public static int based(int k) {
        if (k == 1) {
            throw new Based();
        }
        return k;
    }

    /** What a caller sees of each method at {@code k}: the result, or what its handlers make of the exception. */
    static String handled(String method, int k) {
        try {
            return Integer.toString(switch (method) {
                case "marked" -> marked(k);
                case "wrapped" -> wrapped(k);
                case "messaged" -> messaged(k);
                case "coded" -> coded(k);
                case "based" -> based(k);
                default -> throw new IllegalStateException(method);
            });
        } catch (Coded e) {
            return "code " + e.code;
        } catch (IllegalArgumentException e) {
            return "argument " + e.getMessage();
        } catch (RuntimeException e) {
            if (e instanceof Retryable) {
                return "retried";
            }
            return e.getCause() instanceof IllegalArgumentException ? "argument inside" : "escaped " + e.getClass().getName();
        }
    }

    /** One method on the input 1, in a JVM of its own. */
    public static void main(String[] args) {
        System.out.println(args[0] + "=" + handled(args[0], 1));
    }
}
