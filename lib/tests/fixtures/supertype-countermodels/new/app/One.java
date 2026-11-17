package app;

/** The same in both versions: a static method the previous version's Child inherits. */
public class One {
    public static int value(int k) {
        return k > 1000 ? 2 : 0;
    }
}
