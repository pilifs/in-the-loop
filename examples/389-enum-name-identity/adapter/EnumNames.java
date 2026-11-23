public final class EnumNames {
    enum Mode { OPEN, CLOSED }
    public static boolean lookup(int kind) {
        String name = kind == 0 ? new String("OPEN") : kind == 1 ? new String("CLOSED") : kind == 2 ? null : kind == 3 ? "open" : "OTHER";
        try { return Mode.valueOf(name) == (kind == 0 ? Mode.OPEN : Mode.CLOSED) && kind < 2; }
        catch (NullPointerException e) { return kind == 2 && e.getClass() == NullPointerException.class; }
        catch (IllegalArgumentException e) { return kind >= 3 && e.getClass() == IllegalArgumentException.class; }
    }
    public static boolean ordinal(boolean closed) { return (closed ? Mode.CLOSED : Mode.OPEN).ordinal() == (closed ? 1 : 0); }
    public static boolean alwaysZero(boolean closed) { return (closed ? Mode.CLOSED : Mode.OPEN).ordinal() == 0; }
}
