package sc;

/**
 * A recursive method that writes, through the setter, a field of an object a static holds, and reads it after its call
 * of itself. Proved by induction on k, the call of itself is the hypothesis, which states the result only: what the
 * call writes is lost. On a JVM f(2) is -1: f(1) sets the level to 1 after f(2) set it to 2.
 */
public class Store {
    static final Bean BEAN = new Bean();

    public static int f(int k) {
        if (k <= 0) {
            return 0;
        }
        BEAN.setLevel(k);
        f(k - 1);
        return BEAN.level - k;
    }
}
