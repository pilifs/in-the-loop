package app;

/** The target's own class: the new version's initializer sets Seen.v to 1, and the method is the same in both. */
public class Own {
    static {
        Seen.v = 1;
    }

    public static int f(int k) {
        return k > 1000 ? Seen.v : 0;
    }
}
