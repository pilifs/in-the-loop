package app;

/** The same in both versions: a static method the new version's Child inherits. */
public class Two {
    public static int value(int k) {
        return k > 1000 ? 1 : 0;
    }
}
