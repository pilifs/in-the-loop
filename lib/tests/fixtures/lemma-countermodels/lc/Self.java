package lc;

/** Calls itself forever: no call of it returns, so no property of its result is true or false of a returned call. */
public final class Self {
    public static int forever(int n) {
        return forever(n);
    }

    /** Calls it once: never returns (StackOverflowError). */
    public static int once() {
        return forever(0);
    }
}
