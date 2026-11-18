package app;

/** The previous version overrides area. */
public final class Square extends Base {
    @Override
    public int area(int k) {
        return k > 1000 ? 2 : 0;
    }
}
