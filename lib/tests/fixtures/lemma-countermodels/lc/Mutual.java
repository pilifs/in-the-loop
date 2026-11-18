package lc;

/** Two methods that call each other forever: no call of either returns. */
public final class Mutual {
    public static int ping(int n) {
        return pong(n);
    }

    public static int pong(int n) {
        return ping(n);
    }
}
