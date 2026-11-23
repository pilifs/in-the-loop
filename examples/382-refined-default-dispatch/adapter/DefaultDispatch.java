public final class DefaultDispatch {
    interface Base { default int code(int x) { return x + 1; } }
    interface Refined extends Base { default int code(int x) { return Base.super.code(x) + 2; } }
    static class BaseFirst implements Base, Refined {}
    static class RefinedFirst implements Refined, Base {}
    static class Own implements Refined { public int code(int x) { return x + 4; } }

    static Base receiver(int kind) {
        if (kind == 0) return new BaseFirst();
        if (kind == 1) return new RefinedFirst();
        return new Own();
    }
    public static boolean dispatch(int kind, int x) { return receiver(kind).code(x) == x + (kind == 0 || kind == 1 ? 3 : 4); }
    public static boolean firstDeclared(int x) { return receiver(0).code(x) == x + 1; }
}
