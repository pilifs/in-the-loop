package app;

/** The target's own class: the previous version's initializer sets Seen.v to 2, and the method is the same in both. */
public class Own {
    static {
        Seen.v = 2;
    }

    public static int f(int k) {
        return k > 1000 ? Seen.v : 0;
    }
}
