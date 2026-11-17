package app;

/** The same in both versions. */
public class Counter {
    static int v;

    static int set(int x) {
        v = x;
        return x;
    }
}
