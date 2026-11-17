package app;

/** Its public method is the same in both versions; the private helper it calls is not. */
public class Step implements java.util.function.IntUnaryOperator {
    public int applyAsInt(int x) {
        return amount(x);
    }

    private int amount(int x) {
        return x > 1000 ? 2 : 0;
    }
}
