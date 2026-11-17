package bc;

/** An initializer that has another class put a lambda of that class in its static, then sets its own. */
public class Rehooked {
    public static int k;

    static {
        Hooks.install(5);
        k = 7;
    }
}
