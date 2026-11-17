package app;

/** The same in both versions. */
public class Setting implements java.util.function.IntUnaryOperator {
    public int applyAsInt(int x) {
        int c = Config.step;
        return x > 1000 ? c : 0;
    }
}
