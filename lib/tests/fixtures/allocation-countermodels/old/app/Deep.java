package app;

/** f calls g, which calls this f again. */
public final class Deep extends Node {
    @Override
    public int f(int k) {
        return k <= 0 ? 0 : 1 + g(k);
    }
}
